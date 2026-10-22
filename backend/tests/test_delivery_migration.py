"""Upgrade an existing populated v0.7 database without changing its historical rows."""

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select, text


def test_populated_0009_database_upgrades_without_rewriting_records(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    database = tmp_path / "previous-release.sqlite"
    environment = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "JWT_SECRET": "test-only-secret-abcdefghijklmnopqrstuvwxyz-0123456789-XYZ",
    }

    def alembic(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=backend,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    alembic("upgrade", "0009_pe_screening")
    engine = create_engine(environment["DATABASE_URL"])
    old = MetaData()
    old.reflect(engine)
    now = datetime.now(timezone.utc)
    measurements = {
        "age_years": 25,
        "gestational_weeks": 28.0,
        "systolic_mmhg": 120,
        "diastolic_mmhg": 80,
        "glucose_mmol_l": 7.0,
        "temperature_c": 37.0,
        "heart_rate_bpm": 80,
    }
    with engine.begin() as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        for identity, role in [("legacy-patient", "patient"), ("legacy-doctor", "doctor")]:
            db.execute(
                old.tables["users"]
                .insert()
                .values(
                    id=identity,
                    email=identity + "@example.com",
                    full_name=identity,
                    password_hash="test-only-existing-hash",
                    role=role,
                    active=True,
                    created_at=now,
                )
            )
        db.execute(
            old.tables["health_records"]
            .insert()
            .values(
                id="legacy-record",
                patient_id="legacy-patient",
                observations=measurements,
                created_at=now,
            )
        )
        db.execute(
            old.tables["model_versions"]
            .insert()
            .values(
                id="legacy-model",
                version="migration-fixture-only",
                artifact_sha256="a" * 64,
                manifest={"fixture": True},
                registered_at=now,
            )
        )
        db.execute(
            old.tables["assessments"]
            .insert()
            .values(
                id="legacy-assessment",
                patient_id="legacy-patient",
                health_record_id="legacy-record",
                model_version_id="legacy-model",
                observations_snapshot=measurements,
                maternal_risk="MEDIUM",
                class_scores={"LOW": 0.1, "MEDIUM": 0.8, "HIGH": 0.1},
                explanation={"fixture": True},
                pe_required=True,
                pe_status="UNAVAILABLE",
                pe_reason="Original stored reason",
                research_only=True,
                created_at=now,
            )
        )
        db.execute(
            old.tables["appointments"]
            .insert()
            .values(
                id="legacy-appointment",
                patient_id="legacy-patient",
                doctor_id="legacy-doctor",
                scheduled_at=now + timedelta(days=2),
                reason="Original appointment",
                status="ACCEPTED",
                consent_at=now,
                accepted_at=now,
                access_until=now + timedelta(days=3),
                closed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        db.execute(
            old.tables["appointment_records"]
            .insert()
            .values(appointment_id="legacy-appointment", health_record_id="legacy-record")
        )
        db.execute(
            old.tables["doctor_notes"]
            .insert()
            .values(
                id="legacy-note",
                appointment_id="legacy-appointment",
                author_id="legacy-doctor",
                body="Original private note must survive",
                patient_visible=False,
                created_at=now,
            )
        )
        db.execute(
            old.tables["pe_screenings"]
            .insert()
            .values(
                id="legacy-pe",
                assessment_id="legacy-assessment",
                observations_snapshot={"fixture": True},
                risk="LOW",
                class_scores={"LOW": 0.8, "MEDIUM": 0.1, "HIGH": 0.1},
                model_snapshot={"fixture": True},
                created_at=now,
            )
        )
        db.execute(
            old.tables["notifications"]
            .insert()
            .values(
                id="legacy-notification",
                recipient_id="legacy-patient",
                kind="CLINICIAN_NOTE",
                appointment_id="legacy-appointment",
                read=False,
                created_at=now,
            )
        )
    names = [
        "users",
        "health_records",
        "assessments",
        "appointments",
        "doctor_notes",
        "pe_screenings",
        "notifications",
    ]
    with engine.connect() as db:
        before = {
            name: [dict(row) for row in db.execute(select(old.tables[name])).mappings()]
            for name in names
        }
    engine.dispose()
    alembic("upgrade", "head")
    alembic("check")
    current = MetaData()
    current.reflect(engine)
    with engine.connect() as db:
        for name in names:
            columns = [current.tables[name].c[c.name] for c in old.tables[name].columns]
            assert [dict(row) for row in db.execute(select(*columns)).mappings()] == before[name]
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
        assert db.execute(select(current.tables["users"].c.session_version)).scalars().all() == [
            0,
            0,
        ]
        assert db.execute(select(current.tables["users"].c.email_verified_at)).scalars().all() == [
            None,
            None,
        ]
        assert db.execute(
            select(
                current.tables["health_records"].c.removed_at,
                current.tables["health_records"].c.removal_reason,
            )
        ).one() == (None, None)
        assert db.execute(
            select(
                current.tables["assessments"].c.removed_at,
                current.tables["assessments"].c.removal_reason,
            )
        ).one() == (None, None)
        assert {
            "assessment_care_plans",
            "clinical_reviews",
            "clinical_review_events",
            "follow_up_proposals",
            "whatsapp_alerts",
            "email_action_tokens",
            "auth_rate_buckets",
        }.issubset(current.tables)
    engine.dispose()
