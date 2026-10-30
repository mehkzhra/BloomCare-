"""Exercise real model outputs, clinical authority, immutable history and consented services."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from conftest import sign_in
from pydantic import SecretStr
from sqlalchemy import func, select
from test_appointments import book, decide
from test_communication import upload
from test_pe_screening import PE_VALUES, create_assessment
from test_pe_screening import available as available  # noqa: F401
from test_pe_screening import pe_examples as pe_examples  # noqa: F401
from test_pe_screening import trained as trained  # noqa: F401

from app import care_plan_service, whatsapp_service
from app.assessment_service import pe_screening_required
from app.config import get_settings
from app.database import SessionLocal
from app.groq_service import GroqFailure
from app.models import (
    Assessment,
    AssessmentCarePlan,
    AssistantTurn,
    ClinicalReviewEvent,
    DoctorNote,
    HealthRecord,
    PEScreening,
    WhatsAppAlert,
)


def future_slot(days=3):
    return (
        (datetime.now(timezone.utc) + timedelta(days=days))
        .replace(minute=0, second=0, microsecond=0)
        .isoformat()
    )


def episode(client, accounts, examples):
    sign_in(client)
    record, assessment = create_assessment(client, examples)
    appointment = book(client, accounts, health_record_ids=[record["id"]])
    sign_in(client, "doctor1")
    assert decide(client, appointment).status_code == 200
    return record, assessment, appointment


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", SecretStr("test-only-provider-key"))
    calls = []

    def complete(_settings, messages):
        calls.append(messages)
        return (
            "Discuss your recorded screening results and follow-up questions with your care team."
        )

    monkeypatch.setattr(care_plan_service, "complete", complete)
    return calls


def test_one_form_real_models_warning_override_and_idempotency(
    client, accounts, available, pe_examples
):
    sign_in(client)
    body = {
        **pe_examples["LOW"],
        "clinical_indicators": {**PE_VALUES, "history_of_hypertension": True},
        "request_id": str(uuid4()),
    }
    first = client.post("/api/patients/me/complete-assessment", json=body)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["maternal_risk"] == "LOW"
    assert result["pe_required"] is True and result["pe_status"] == "COMPLETED"
    explanation = result["pe_screening"]["explanation"]
    assert len(explanation["features"]) == 13
    assert explanation["base_score"] + sum(
        f["contribution"] for f in explanation["features"]
    ) == pytest.approx(explanation["model_score"], abs=1e-7)
    assert (
        client.post("/api/patients/me/complete-assessment", json=body).json()["id"] == result["id"]
    )
    conflict = {**body, "age_years": body["age_years"] + 1}
    assert client.post("/api/patients/me/complete-assessment", json=conflict).status_code == 409
    with SessionLocal() as db:
        for model in [HealthRecord, Assessment, PEScreening]:
            assert db.scalar(select(func.count()).select_from(model)) == 1


@pytest.mark.parametrize(
    "observations,clinical",
    [
        ({"systolic_mmhg": 140}, {}),
        ({"diastolic_mmhg": 90}, {}),
        ({}, {"history_of_hypertension": True}),
        ({}, {"protein_uria": True}),
    ],
)
def test_warning_triggers_do_not_depend_on_a_high_classifier_label(observations, clinical):
    assert pe_screening_required("LOW", observations, clinical)


def test_unsupported_pe_readings_preserved_and_reported_without_inference(
    client, accounts, available, pe_examples
):
    sign_in(client)
    body = {
        **pe_examples["MEDIUM"],
        "systolic_mmhg": 140,
        "clinical_indicators": PE_VALUES,
        "request_id": str(uuid4()),
    }
    response = client.post("/api/patients/me/complete-assessment", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["observations"]["systolic_mmhg"] == 140
    assert result["pe_status"] == "OUTSIDE_COVERAGE" and result["pe_screening"] is None


def test_completed_pe_status_consistent_in_timeline_passport_and_family(
    client, accounts, available, pe_examples
):
    sign_in(client)
    record, assessment = create_assessment(client, pe_examples)
    completed = client.post(
        f"/api/patients/me/assessments/{assessment['id']}/pe", json=PE_VALUES
    ).json()
    assert completed["pe_status"] == "COMPLETED"
    timeline = client.get("/api/patients/me/timeline").json()
    assert (
        next(r for r in timeline if r["type"] == "ASSESSMENT")["details"]["pe_status"]
        == "COMPLETED"
    )
    passport = client.get("/api/patients/me/passport").json()
    assert "PE prediction is unavailable" not in passport["notice"]
    assert passport["assessments"][0]["pe_screening"]["risk"] == completed["pe_screening"]["risk"]
    invitation = client.post(
        "/api/family/invitations",
        json={
            "recipient_email": "patient2@example.com",
            "scopes": ["assessments"],
            "access_days": 7,
            "consent": True,
        },
    ).json()
    sign_in(client, "patient2")
    accepted = client.post("/api/family/accept", json={"code": invitation["invitation_code"]})
    assert accepted.status_code == 200, accepted.text
    grant = client.get("/api/family/grants").json()["received"][0]["id"]
    shared = client.get(f"/api/family/grants/{grant}/records").json()["assessments"][0]
    assert (
        shared["pe_status"] == "COMPLETED"
        and shared["pe_category"] == completed["pe_screening"]["risk"]
    )
    assert "observations" not in shared


def test_care_plan_consent_saved_version_and_provider_data_minimization(
    client, accounts, available, pe_examples, groq
):
    sign_in(client)
    _, assessment = create_assessment(client, pe_examples)
    path = f"/api/patients/me/assessments/{assessment['id']}/care-plan"
    assert client.post(path, json={"consent": False}).status_code == 422
    first = client.post(path, json={"consent": True})
    assert first.status_code == 200, first.text
    plan = first.json()["care_plan"]
    assert plan["current"] and "care team" in plan["content"]
    assert client.post(path, json={"consent": True}).json()["care_plan"]["id"] == plan["id"]
    assert len(groq) == 1
    assert (
        "patient1@example.com" not in groq[0][1]["content"]
        and '"patient_id"' not in groq[0][1]["content"]
    )
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AssessmentCarePlan)) == 1
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0
    completed = client.post(f"/api/patients/me/assessments/{assessment['id']}/pe", json=PE_VALUES)
    assert completed.status_code == 200
    assert completed.json()["care_plan"]["current"] is False
    second = client.post(path, json={"consent": True}).json()["care_plan"]
    assert second["current"] and second["id"] != plan["id"] and len(groq) == 2
    notifications = client.get("/api/notifications").json()["items"]
    assert any(
        n["kind"] == "CARE_PLAN_READY" and n["health_record_id"] == assessment["health_record_id"]
        for n in notifications
    )
    sign_in(client, "patient2")
    assert client.post(path, json={"consent": True}).status_code == 404


@pytest.mark.parametrize("failure", ["missing_key", "timeout", "unavailable"])
def test_care_plan_failure_saves_labelled_basic_guide(
    client, accounts, available, pe_examples, groq, monkeypatch, failure
):
    sign_in(client)
    _, assessment = create_assessment(client, pe_examples)

    def fail(*_args):
        if failure == "missing_key":
            pytest.fail("Missing-key fallback must not call the provider")
        if failure == "timeout":
            raise GroqFailure("GROQ_TIMEOUT", "Provider timed out", 504)
        raise GroqFailure("GROQ_UNAVAILABLE", "Provider unavailable", 503)

    if failure == "missing_key":
        monkeypatch.setattr(get_settings(), "groq_api_key", None)
    monkeypatch.setattr(care_plan_service, "complete", fail)
    path = f"/api/patients/me/assessments/{assessment['id']}/care-plan"
    response = client.post(path, json={"consent": True})
    assert response.status_code == 200, response.text
    plan = response.json()["care_plan"]
    assert plan["provider_model"] == "local-basic-guide-v1"
    assert "AI personalization unavailable" in plan["content"]
    saved = client.get(f"/api/patients/me/assessments/{assessment['id']}").json()["care_plan"]
    assert saved["id"] == plan["id"] and saved["current"]
    assert client.post(path, json={"consent": True}).json()["care_plan"]["id"] == plan["id"]
    sign_in(client, "patient2")
    assert client.post(path, json={"consent": True}).status_code == 404


def test_basic_guide_can_be_personalized_after_provider_recovers(
    client, accounts, available, pe_examples, groq, monkeypatch
):
    sign_in(client)
    _, assessment = create_assessment(client, pe_examples)
    path = f"/api/patients/me/assessments/{assessment['id']}/care-plan"
    key = get_settings().groq_api_key
    monkeypatch.setattr(get_settings(), "groq_api_key", None)
    plan = client.post(path, json={"consent": True}).json()["care_plan"]
    body = {"consent": True, "retry_personalization": True}
    assert client.post(path, json=body).status_code == 429
    with SessionLocal() as db:
        row = db.get(AssessmentCarePlan, plan["id"])
        row.updated_at -= timedelta(minutes=1)
        db.commit()
    # Another provider failure keeps the usable basic guide.
    failed = client.post(path, json=body).json()["care_plan"]
    assert failed["content"] == plan["content"] and failed["current"]
    with SessionLocal() as db:
        row = db.get(AssessmentCarePlan, plan["id"])
        row.updated_at -= timedelta(minutes=1)
        db.commit()
    monkeypatch.setattr(get_settings(), "groq_api_key", key)
    denied = client.post(path, json={"consent": False, "retry_personalization": True})
    assert denied.status_code == 422
    result = client.post(path, json=body).json()["care_plan"]
    assert result["id"] == plan["id"] and result["current"]
    assert result["provider_model"] == get_settings().groq_model
    assert "care team" in result["content"] and len(groq) == 1
    client.post(path, json=body)
    assert len(groq) == 1  # A successful AI plan is not repeatedly regenerated.


def test_clinical_review_versions_urgent_counts_notifications_and_authorization(
    client, accounts, available, pe_examples
):
    record, assessment, appointment = episode(client, accounts, pe_examples)
    path = f"/api/doctors/me/appointments/{appointment['id']}/assessments/{assessment['id']}/review"
    body = {
        "status": "URGENT_FOLLOW_UP",
        "reason": "Arrange prompt clinical follow-up",
        "expected_version": 0,
        "follow_up_at": future_slot(2),
    }
    urgent = client.put(path, json=body)
    assert urgent.status_code == 200, urgent.text
    assert urgent.json()["clinical_review"]["version"] == 1
    assert client.put(path, json=body).status_code == 409
    sign_in(client, "patient1")
    notification = next(
        n
        for n in client.get("/api/notifications").json()["items"]
        if n["kind"] == "URGENT_FOLLOW_UP"
    )
    assert notification["health_record_id"] == record["id"]
    assert client.put(path, json=body).status_code == 403
    history = client.get(f"/api/patients/me/assessments/{assessment['id']}/reviews").json()
    assert len(history) == 1
    sign_in(client, "admin")
    assert client.get("/api/admin/stats").json()["urgent_follow_ups"] == 1
    assert len(client.get("/api/admin/clinical-reviews?status=URGENT_FOLLOW_UP").json()) == 1
    sign_in(client, "doctor2")
    assert client.put(path, json=body).status_code == 404
    assert client.get("/api/doctors/me/cases").json() == []
    sign_in(client, "doctor1")
    response = client.put(
        path, json={"status": "REVIEWED", "reason": "Review completed", "expected_version": 1}
    )
    assert response.status_code == 200 and response.json()["clinical_review"]["version"] == 2
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ClinicalReviewEvent)) == 2


def test_notes_amendment_keeps_original_and_report_excludes_private_content(
    client, accounts, available, pe_examples
):
    _, assessment, appointment = episode(client, accounts, pe_examples)
    path = f"/api/doctors/me/appointments/{appointment['id']}/notes"
    first = client.post(
        path,
        json={
            "body": "Original clinical observation",
            "patient_visible": True,
            "assessment_id": assessment["id"],
        },
    ).json()
    amend = f"{path}/{first['id']}/amend"
    assert (
        client.post(amend, json={"body": "Hidden correction", "patient_visible": False}).status_code
        == 422
    )
    changed = client.post(
        amend, json={"body": "Corrected clinical observation", "patient_visible": True}
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["supersedes_id"] == first["id"]
    assert changed.json()["assessment_id"] == assessment["id"]
    assert client.post(amend, json={"body": "Second correction"}).status_code == 409
    assert (
        client.post(
            path,
            json={
                "body": "Private clinician text",
                "patient_visible": False,
                "assessment_id": assessment["id"],
            },
        ).status_code
        == 201
    )
    with SessionLocal() as db:
        assert db.get(DoctorNote, first["id"]).body == "Original clinical observation"
    sign_in(client)
    report = client.get(f"/api/patients/me/assessments/{assessment['id']}/report-data")
    assert report.status_code == 200 and "Corrected clinical observation" in report.text
    assert "Private clinician text" not in report.text
    sign_in(client, "patient2")
    assert (
        client.get(f"/api/patients/me/assessments/{assessment['id']}/report-data").status_code
        == 404
    )


def test_scoped_search_and_analytics_stop_after_grant_revocation(
    client, accounts, available, pe_examples
):
    record, assessment, appointment = episode(client, accounts, pe_examples)
    result = client.get("/api/doctors/me/cases?q=patient1&risk=" + assessment["maternal_risk"])
    assert result.status_code == 200, result.text
    assert len(result.json()) == 1
    assert client.get("/api/doctors/me/cases?q=patient2").json() == []
    assert client.get("/api/doctors/me/analytics").json()["total"] == 1
    assert client.get("/api/doctors/me/cases?from_at=2030-01-01T00:00:00Z").json() == []
    assert client.get("/api/doctors/me/cases?from_at=2026-01-01T00:00:00").status_code == 422
    sign_in(client)
    assert (
        len(client.get("/api/patients/me/assessments?risk=" + assessment["maternal_risk"]).json())
        == 1
    )
    assert (
        client.post(f"/api/patients/me/appointments/{appointment['id']}/cancel").status_code == 200
    )
    sign_in(client, "doctor1")
    assert client.get("/api/doctors/me/cases").json() == []
    assert client.get("/api/doctors/me/analytics").json()["total"] == 0


def test_follow_up_requires_patient_consent_and_acceptance_is_idempotent(
    client, accounts, available, pe_examples
):
    record, assessment, appointment = episode(client, accounts, pe_examples)
    body = {
        "assessment_id": assessment["id"],
        "scheduled_at": future_slot(5),
        "reason": "Review updated observations",
        "request_id": str(uuid4()),
    }
    path = f"/api/doctors/me/appointments/{appointment['id']}/follow-ups"
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert client.post(path, json=body).json()["id"] == proposal["id"]
    sign_in(client)
    path = f"/api/patients/me/follow-ups/{proposal['id']}/accept"
    assert client.post(path, json={"share_profile": False}).status_code == 422
    consent = {"share_profile": True, "health_record_ids": [record["id"]]}
    first = client.post(path, json=consent)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "PENDING"
    assert client.post(path, json=consent).json()["id"] == first.json()["id"]
    sign_in(client, "patient2")
    assert client.post(path, json=consent).status_code == 404


def test_rescheduling_closes_access_unshares_reports_and_checks_conflicts(
    client, accounts, available, pe_examples
):
    _, assessment, appointment = episode(client, accounts, pe_examples)
    sign_in(client)
    report = upload(client)
    assert (
        client.post(
            f"/api/patients/me/appointments/{appointment['id']}/reports",
            json={"report_id": report["id"], "consent": True},
        ).status_code
        == 201
    )
    current = client.get("/api/patients/me/appointments").json()[0]
    path = f"/api/patients/me/appointments/{appointment['id']}/reschedule"
    body = {
        "scheduled_at": future_slot(6),
        "reason": "Request a revised consultation",
        "share_profile": True,
        "expected_updated_at": current["updated_at"],
    }
    book(client, accounts, scheduled_at=body["scheduled_at"])
    assert client.patch(path, json=body).status_code == 409
    still = next(
        a
        for a in client.get("/api/patients/me/appointments").json()
        if a["id"] == appointment["id"]
    )
    assert still["status"] == "ACCEPTED" and still["record_access_available"]
    body["scheduled_at"] = future_slot(7)
    response = client.patch(path, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PENDING" and not response.json()["record_access_available"]
    sign_in(client, "doctor1")
    assert client.get(f"/api/doctors/me/appointments/{appointment['id']}/review").status_code == 403
    assert decide(client, response.json()).status_code == 200
    assert client.get(f"/api/doctors/me/appointments/{appointment['id']}/reports").json() == []


@pytest.fixture
def twilio(monkeypatch):
    settings = get_settings()
    for key, value in {
        "twilio_account_sid": "AC" + "a" * 32,
        "twilio_auth_token": SecretStr("test-only-token"),
        "twilio_whatsapp_from": "+15555550100",
        "twilio_allowed_recipients": "+15555550101",
    }.items():
        monkeypatch.setattr(settings, key, value)
    calls = []

    def request(_settings, method, sid=None, data=None):
        calls.append((method, data))
        return {"sid": "SM" + "b" * 32, "status": "queued" if method == "POST" else "delivered"}

    monkeypatch.setattr(whatsapp_service, "provider_request", request)
    return calls


def test_whatsapp_queued_is_not_delivered_nonce_dedup_and_status_refresh(
    client, accounts, available, pe_examples, twilio
):
    sign_in(client)
    _, assessment = create_assessment(client, pe_examples)
    path = f"/api/patients/me/assessments/{assessment['id']}/alerts"
    body = {"recipient": "+15555550101", "request_id": str(uuid4()), "consent": True}
    first = client.post(path, json=body)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "QUEUED"
    assert first.json()["recipient"] == "••••0101"
    assert client.post(path, json=body).json()["id"] == first.json()["id"] and len(twilio) == 1
    assert (
        "patient1@example.com" not in twilio[0][1]["Body"]
        and "systolic" not in twilio[0][1]["Body"]
    )
    assert (
        client.get(f"/api/patients/me/alerts/{first.json()['id']}").json()["status"] == "DELIVERED"
    )
    sign_in(client, "patient2")
    assert client.get(f"/api/patients/me/alerts/{first.json()['id']}").status_code == 404


def test_whatsapp_authorized_recipient_consent_and_timeout_never_resends(
    client, accounts, available, pe_examples, twilio, monkeypatch
):
    sign_in(client)
    _, assessment = create_assessment(client, pe_examples)
    path = f"/api/patients/me/assessments/{assessment['id']}/alerts"
    body = {"recipient": "+15555550101", "request_id": str(uuid4()), "consent": True}
    assert client.post(path, json={**body, "consent": False}).status_code == 422
    assert client.post(path, json={**body, "recipient": "+15555550102"}).status_code == 422
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("test")

    monkeypatch.setattr(whatsapp_service, "provider_request", timeout)
    first = client.post(path, json=body)
    assert first.json()["status"] == "UNCERTAIN"
    assert client.post(path, json=body).json()["id"] == first.json()["id"]
    assert len(calls) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WhatsAppAlert)) == 1


def test_pregnancy_stage_uses_saved_dates_and_admin_search_is_role_scoped(client, accounts):
    sign_in(client)
    assert client.get("/api/patients/me/pregnancy-tracker").json()["estimated_weeks"] is None
    due = (datetime.now(timezone.utc) + timedelta(weeks=12)).date().isoformat()
    assert (
        client.put(
            "/api/patients/me/profile", json={"due_date": due, "preferred_language": "en"}
        ).status_code
        == 200
    )
    tracker = client.get("/api/patients/me/pregnancy-tracker").json()
    assert tracker["estimated_weeks"] == 28 and tracker["trimester"] == 3
    assert len(tracker["milestones"]) == 6
    assert client.get("/api/admin/accounts?q=doctor1").status_code == 403
    sign_in(client, "admin")
    rows = client.get("/api/admin/accounts?q=doctor1&role=doctor&active=true").json()
    assert len(rows) == 1 and rows[0]["id"] == accounts["doctor1"]
