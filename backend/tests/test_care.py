from datetime import datetime, timedelta, timezone

import pytest
from conftest import sign_in
from test_appointments import book, decide

SYMPTOM = {
    "description": "Nausea",
    "severity": "MILD",
    "occurred_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
}
MEDICINE = {
    "name": "Prescribed medicine",
    "dose": "As prescribed",
    "schedule": "Morning",
    "prescriber": "Doctor One",
}


def test_symptom_medication_persist_and_timeline(client, accounts):
    sign_in(client)
    assert client.post("/api/patients/me/symptoms", json=SYMPTOM).status_code == 201
    med = client.post("/api/patients/me/medications", json=MEDICINE)
    assert med.status_code == 201
    assert client.get("/api/patients/me/symptoms").json()[0]["description"] == "Nausea"
    assert len(client.get("/api/patients/me/medications").json()) == 1
    rows = client.get("/api/patients/me/timeline").json()
    assert {r["type"] for r in rows} == {"SYMPTOM", "MEDICATION"}
    assert [r["at"] for r in rows] == sorted([r["at"] for r in rows], reverse=True)
    passport = client.get("/api/patients/me/passport").json()
    assert passport["active_medications"][0]["name"] == MEDICINE["name"]
    url = "/api/patients/me/medications/" + med.json()["id"]
    assert client.patch(url, json={"active": False}).status_code == 200
    assert client.get("/api/patients/me/passport").json()["active_medications"] == []
    assert client.patch(url, json={"active": True}).status_code == 200


def test_patient_isolation_and_no_doctor_access(client, accounts):
    sign_in(client)
    med = client.post("/api/patients/me/medications", json=MEDICINE).json()
    client.post("/api/patients/me/symptoms", json=SYMPTOM)
    sign_in(client, "patient2")
    for path in ("symptoms", "medications", "timeline"):
        assert client.get("/api/patients/me/" + path).json() == []
    assert (
        client.patch(
            "/api/patients/me/medications/" + med["id"], json={"active": False}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/patients/me/passport").json()["patient"]["email"] == "patient2@example.com"
    )
    sign_in(client, "doctor1")
    for path in ("symptoms", "medications", "timeline", "passport"):
        assert client.get("/api/patients/me/" + path).status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"occurred_at": "2035-01-01T00:00:00Z"},
        {"occurred_at": "2026-01-01T00:00:00"},
        {"severity": "DANGEROUS"},
        {"patient_id": "forged"},
        {"description": ""},
    ],
)
def test_invalid_or_forged_symptom(client, accounts, change):
    sign_in(client)
    assert client.post("/api/patients/me/symptoms", json={**SYMPTOM, **change}).status_code == 422


def test_medication_validation_and_unauthenticated(client, accounts):
    assert client.get("/api/patients/me/passport").status_code == 401
    sign_in(client)
    assert (
        client.post("/api/patients/me/medications", json={**MEDICINE, "active": False}).status_code
        == 422
    )
    med = client.post("/api/patients/me/medications", json=MEDICINE).json()
    assert (
        client.patch(
            "/api/patients/me/medications/" + med["id"], json={"active": "false"}
        ).status_code
        == 422
    )
    assert client.get("/api/patients/me/timeline?offset=-1").status_code == 422


def test_private_note_excluded_from_export(client, accounts):
    sign_in(client)
    appointment = book(client, accounts)
    sign_in(client, "doctor1")
    assert decide(client, appointment).status_code == 200
    url = "/api/doctors/me/appointments/" + appointment["id"] + "/notes"
    assert (
        client.post(
            url, json={"body": "Private clinician content", "patient_visible": False}
        ).status_code
        == 201
    )
    assert (
        client.post(
            url, json={"body": "Visible clinician content", "patient_visible": True}
        ).status_code
        == 201
    )
    sign_in(client)
    for path in ("timeline", "passport"):
        result = client.get("/api/patients/me/" + path)
        assert result.status_code == 200
        assert "Visible clinician content" in result.text
        assert "Private clinician content" not in result.text
