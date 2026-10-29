from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app import appointment_service
from app.database import SessionLocal, engine
from app.main import app
from app.models import (
    Appointment,
    AppointmentEvent,
    AppointmentRecord,
    DoctorNote,
    DoctorProfile,
    User,
)

HEALTH = {
    "age_years": 27,
    "gestational_weeks": 24,
    "systolic_mmhg": 120,
    "diastolic_mmhg": 80,
    "glucose_mmol_l": 7,
    "temperature_c": 37,
    "heart_rate_bpm": 78,
}


def slot(days=2, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def request_body(accounts, **changes):
    return {
        "doctor_id": accounts["doctor1"],
        "scheduled_at": slot().isoformat(),
        "reason": "Review my saved observations",
        "share_profile": True,
        "health_record_ids": [],
        **changes,
    }


def book(client, accounts, **changes):
    response = client.post("/api/patients/me/appointments", json=request_body(accounts, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def decide(client, appointment, action="ACCEPT"):
    return client.post(
        f"/api/doctors/me/appointments/{appointment['id']}/decision",
        json={"action": action},
    )


def review_path(appointment):
    return f"/api/doctors/me/appointments/{appointment['id']}/review"


def note_path(appointment, role="doctors"):
    return f"/api/{role}/me/appointments/{appointment['id']}/notes"


def saved_record(client):
    response = client.post("/api/patients/me/health-records", json=HEALTH)
    assert response.status_code == 201
    return response.json()


def test_booking_acceptance_record_scope_and_note_visibility(client, accounts):
    sign_in(client)
    shared, unshared = saved_record(client), saved_record(client)
    appointment = book(client, accounts, health_record_ids=[shared["id"]])
    assert appointment["status"] == "PENDING" and not appointment["record_access_available"]
    assert appointment["duration_minutes"] == 30
    assert client.get("/api/patients/me/appointments?offset=0").json() == [appointment]
    sign_in(client, "doctor1")
    assert client.get("/api/doctors/me/appointments").json() == [appointment]
    assert client.get(review_path(appointment)).status_code == 403
    assert client.post(note_path(appointment), json={"body": "Too early"}).status_code == 403
    accepted = decide(client, appointment).json()
    assert accepted["status"] == "ACCEPTED" and accepted["record_access_available"]
    assert datetime.fromisoformat(accepted["access_until"]) == slot() + timedelta(hours=24)
    review = client.get(review_path(appointment))
    assert review.status_code == 200
    assert review.json()["records"] == [shared]
    assert review.json()["profile"]["user_id"] == accounts["patient1"]
    endpoint = f"/api/doctors/me/appointments/{appointment['id']}/records"
    assert client.get(f"{endpoint}/{shared['id']}/assessments").json() == []
    assert client.get(f"{endpoint}/{unshared['id']}/assessments").status_code == 404
    public = client.post(note_path(appointment), json={"body": "Public clinician note"})
    private = client.post(
        note_path(appointment),
        json={"body": "Private clinician note", "patient_visible": False},
    )
    assert public.status_code == private.status_code == 201
    assert len(client.get(note_path(appointment)).json()) == 2
    sign_in(client)
    visible = client.get(note_path(appointment, "patients")).json()
    assert [row["body"] for row in visible] == ["Public clinician note"]
    assert "Private clinician note" not in client.get("/api/patients/me/appointments").text
    assert "password" not in review.text and "email" not in review.text


def test_cross_patient_and_unrelated_doctor_are_denied(client, accounts):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/appointments").json() == []
    assert client.get(note_path(appointment, "patients")).status_code == 404
    assert (
        client.post(f"/api/patients/me/appointments/{appointment['id']}/cancel").status_code == 404
    )
    sign_in(client, "doctor2")
    assert client.get("/api/doctors/me/appointments").json() == []
    assert decide(client, appointment).status_code == 404
    assert client.get(review_path(appointment)).status_code == 404
    assert client.get(note_path(appointment)).status_code == 404
    assert client.post(note_path(appointment), json={"body": "Unauthorized"}).status_code == 404
    sign_in(client, "doctor1")
    assert decide(client, appointment).status_code == 200
    assert client.get(f"/api/patients/{accounts['patient1']}/profile").status_code == 404
    assert client.get("/api/patients/me/health-records").status_code == 403


def test_only_owned_records_can_be_shared_and_booking_is_atomic(client, accounts):
    sign_in(client, "patient2")
    other = saved_record(client)
    sign_in(client)
    own = saved_record(client)
    response = client.post(
        "/api/patients/me/appointments",
        json=request_body(accounts, health_record_ids=[own["id"], other["id"]]),
    )
    assert response.status_code == 404
    with SessionLocal() as db:
        for model in (Appointment, AppointmentRecord, AppointmentEvent):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_explicit_boolean_consent_required(client, accounts, value):
    sign_in(client)
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, share_profile=value),
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"patient_id": "someone-else"},
        {"status": "ACCEPTED"},
        {"accepted_at": "2026-01-01T00:00Z"},
    ],
)
def test_cannot_supply_ownership_or_acceptance(client, accounts, extra):
    sign_in(client)
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, **extra),
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "scheduled",
    [
        slot(-1).isoformat(),
        slot(91).isoformat(),
        slot().replace(tzinfo=None).isoformat(),
        slot().replace(minute=17).isoformat(),
        slot().replace(second=5).isoformat(),
    ],
)
def test_invalid_or_past_time_rejected(client, accounts, scheduled):
    sign_in(client)
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, scheduled_at=scheduled),
        ).status_code
        == 422
    )


def test_offsets_normalize_to_utc_and_duplicate_records_rejected(client, accounts):
    sign_in(client)
    record = saved_record(client)
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, health_record_ids=[record["id"], record["id"]]),
        ).status_code
        == 422
    )
    requested = slot().astimezone(timezone(timedelta(hours=5))).isoformat()
    appointment = book(client, accounts, scheduled_at=requested)
    assert datetime.fromisoformat(appointment["scheduled_at"]) == slot()


def test_unapproved_and_inactive_doctors_cannot_receive_or_review(client, accounts):
    sign_in(client)
    with SessionLocal() as db:
        db.get(DoctorProfile, accounts["doctor1"]).approved = False
        db.get(User, accounts["doctor2"]).active = False
        db.commit()
    assert client.get("/api/doctors").json() == []
    for key in ("doctor1", "doctor2", "patient2", "admin"):
        assert (
            client.post(
                "/api/patients/me/appointments",
                json=request_body(accounts, doctor_id=accounts[key]),
            ).status_code
            == 404
        )
    sign_in(client, "doctor1")
    assert client.get("/api/doctors/me/appointments").status_code == 403


def test_active_slot_conflicts_and_cancellation_releases_slot(client, accounts):
    sign_in(client)
    first = book(client, accounts)
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, doctor_id=accounts["doctor2"]),
        ).status_code
        == 409
    )
    sign_in(client, "patient2")
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts),
        ).status_code
        == 409
    )
    sign_in(client)
    cancelled = client.post(f"/api/patients/me/appointments/{first['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert book(client, accounts)["status"] == "PENDING"


def test_simultaneous_requests_cannot_double_book_a_doctor(accounts):
    barrier = Barrier(2)
    body = request_body(accounts)

    def request(session):
        barrier.wait(timeout=30)
        return session.post(
            "/api/patients/me/appointments", json=body
        ).status_code

    # Password verification and client startup are setup, not the booking race.
    # Finish them before starting the bounded synchronization wait.
    with ExitStack() as stack:
        sessions = []
        for account in ("patient1", "patient2"):
            session = stack.enter_context(TestClient(app))
            sign_in(session, account)
            sessions.append(session)
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(request, sessions))
    assert sorted(statuses) == [201, 409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
        assert db.scalar(select(func.count()).select_from(AppointmentEvent)) == 1


@pytest.mark.parametrize("action", ["REJECT", "CANCEL", "COMPLETE"])
def test_terminal_state_revokes_access_and_cannot_be_reopened(client, accounts, action):
    sign_in(client)
    record = saved_record(client)
    appointment = book(client, accounts, health_record_ids=[record["id"]])
    sign_in(client, "doctor1")
    if action != "REJECT":
        assert decide(client, appointment).status_code == 200
        assert (
            client.post(note_path(appointment), json={"body": "Persistent public note"}).status_code
            == 201
        )
    assert decide(client, appointment, action).status_code == 200
    assert client.get(review_path(appointment)).status_code == 403
    assert client.post(note_path(appointment), json={"body": "Access ended"}).status_code == 403
    assert (
        client.get(
            f"/api/doctors/me/appointments/{appointment['id']}/records/{record['id']}/assessments",
        ).status_code
        == 403
    )
    assert decide(client, appointment).status_code == 409
    if action != "REJECT":
        assert client.get(note_path(appointment)).json()[0]["body"] == "Persistent public note"
        sign_in(client)
        assert (
            client.get(note_path(appointment, "patients")).json()[0]["body"]
            == "Persistent public note"
        )


def test_patient_cancellation_revokes_accepted_grant(client, accounts):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "doctor1")
    assert decide(client, appointment).status_code == 200
    sign_in(client)
    assert (
        client.post(f"/api/patients/me/appointments/{appointment['id']}/cancel").status_code == 200
    )
    sign_in(client, "doctor1")
    assert client.get(review_path(appointment)).status_code == 403


def test_repeat_decisions_are_idempotent_and_do_not_extend_access(client, accounts):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "doctor1")
    first = decide(client, appointment)
    assert first.status_code == 200
    assert decide(client, appointment).json() == first.json()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AppointmentEvent)) == 2
    assert decide(client, appointment, "REJECT").status_code == 409


def test_access_expires_without_renewal_and_rechecks_approval(client, accounts, monkeypatch):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "doctor1")
    accepted = decide(client, appointment).json()
    with SessionLocal() as db:
        db.get(DoctorProfile, accounts["doctor1"]).approved = False
        db.commit()
    assert client.get(review_path(appointment)).status_code == 403
    with SessionLocal() as db:
        db.get(DoctorProfile, accounts["doctor1"]).approved = True
        db.commit()
    expiration = datetime.fromisoformat(accepted["access_until"])
    monkeypatch.setattr(appointment_service, "utc_now", lambda: expiration)
    assert client.get(review_path(appointment)).status_code == 403
    assert client.post(note_path(appointment), json={"body": "Expired"}).status_code == 403
    repeated = decide(client, appointment).json()
    assert not repeated["record_access_available"]
    assert repeated["access_until"] == accepted["access_until"]


def test_different_episodes_do_not_share_or_revoke_each_others_grants(client, accounts):
    sign_in(client)
    a, b = saved_record(client), saved_record(client)
    first = book(client, accounts, health_record_ids=[a["id"]])
    second = book(
        client,
        accounts,
        doctor_id=accounts["doctor2"],
        scheduled_at=(slot() + timedelta(minutes=30)).isoformat(),
        health_record_ids=[b["id"]],
    )
    for account, appointment in (("doctor1", first), ("doctor2", second)):
        sign_in(client, account)
        assert decide(client, appointment).status_code == 200
    sign_in(client)
    assert client.post(f"/api/patients/me/appointments/{first['id']}/cancel").status_code == 200
    sign_in(client, "doctor2")
    assert [r["id"] for r in client.get(review_path(second)).json()["records"]] == [b["id"]]
    assert client.get(review_path(first)).status_code == 404


def test_note_authorship_visibility_and_body_cannot_be_forged(client, accounts):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "doctor1")
    assert decide(client, appointment).status_code == 200
    for payload in (
        {"body": "Forged", "author_id": accounts["doctor2"]},
        {"body": "   "},
        {"body": "Too long " * 600},
        {"body": "Boolean", "patient_visible": "false"},
    ):
        assert client.post(note_path(appointment), json=payload).status_code == 422
    assert client.put(note_path(appointment), json={"body": "Rewrite"}).status_code == 405
    sign_in(client)
    assert (
        client.post(note_path(appointment), json={"body": "Patient cannot write"}).status_code
        == 403
    )
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoctorNote)) == 0


@pytest.mark.parametrize(
    "path",
    [
        "/api/patients/me/appointments",
        "/api/doctors/me/appointments",
        "/api/doctors/me/appointments/unknown/review",
        "/api/patients/me/appointments/unknown/notes",
        "/api/doctors/me/appointments/unknown/notes",
    ],
)
def test_appointment_routes_require_sign_in(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "account,path",
    [
        ("admin", "/api/patients/me/appointments"),
        ("admin", "/api/doctors/me/appointments"),
        ("patient1", "/api/doctors/me/appointments"),
        ("doctor1", "/api/patients/me/appointments"),
    ],
)
def test_appointment_routes_require_the_correct_role(client, accounts, account, path):
    sign_in(client, account)
    assert client.get(path).status_code == 403


def test_history_pagination_and_actual_admin_count(client, accounts):
    with SessionLocal() as db:
        for index in range(55):
            db.add(
                Appointment(
                    patient_id=accounts["patient1"],
                    doctor_id=accounts["doctor1"],
                    scheduled_at=slot() + timedelta(minutes=index * 30),
                    reason="History",
                    consent_at=datetime.now(timezone.utc),
                    status="PENDING",
                )
            )
        db.commit()
    sign_in(client)
    page1 = client.get("/api/patients/me/appointments?offset=0").json()
    page2 = client.get("/api/patients/me/appointments?offset=50").json()
    assert len(page1) == 50 and len(page2) == 5
    assert not {r["id"] for r in page1} & {r["id"] for r in page2}
    assert client.get("/api/patients/me/appointments?offset=-1").status_code == 422
    sign_in(client, "admin")
    assert client.get("/api/admin/stats").json()["appointments"] == 55


def test_readiness_detects_a_missing_appointment_table(client):
    assert client.get("/api/health/ready").status_code == 200
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE doctor_notes"))
    result = client.get("/api/health/ready")
    assert result.status_code == 503 and result.json() == {"status": "database_not_ready"}
