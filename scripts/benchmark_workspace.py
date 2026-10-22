"""Bounded, authenticated workspace benchmark using a disposable synthetic SQLite database."""

import argparse
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]


def run(users, clients, rounds):
    with TemporaryDirectory(prefix="bloomcare-benchmark-") as temporary:
        os.environ.update(
            DATABASE_URL="sqlite:///" + str(Path(temporary) / "synthetic.db"),
            JWT_SECRET=secrets.token_urlsafe(48),
            COOKIE_SECURE="false",
            BLOOMCARE_RESEARCH_ASSESSMENTS="false",
        )
        sys.path.insert(0, str(ROOT / "backend"))
        from app.database import Base, SessionLocal, engine
        from app.main import app
        from app.models import HealthRecord, PatientProfile, User
        from app.security import hasher, issue_token
        from fastapi.testclient import TestClient

        Base.metadata.create_all(engine)
        identities = []
        password_hash = hasher.hash(secrets.token_urlsafe(24))
        try:
            with SessionLocal() as db:
                for i in range(users):
                    user = User(
                        email=f"synthetic-{i}@example.invalid",
                        full_name=f"Synthetic {i}",
                        role="patient",
                        password_hash=password_hash,
                        patient_profile=PatientProfile(),
                    )
                    db.add(user)
                    db.flush()
                    records = []
                    for _ in range(5):
                        record = HealthRecord(
                            patient_id=user.id,
                            observations={
                                "age_years": 27,
                                "gestational_weeks": 24,
                                "systolic_mmhg": 120,
                                "diastolic_mmhg": 80,
                                "glucose_mmol_l": 6,
                                "temperature_c": 37,
                                "heart_rate_bpm": 78,
                            },
                        )
                        db.add(record)
                        db.flush()
                        records.append(record.id)
                    identities.append((issue_token(user), set(records)))
                db.commit()

            def visit(identity):
                token, expected_records = identity
                observations = []
                with TestClient(app) as client:
                    client.cookies.set("bloomcare_session", token)
                    for _ in range(rounds):
                        started = perf_counter()
                        response = client.get("/api/patients/me/workspace")
                        elapsed = (perf_counter() - started) * 1000
                        isolated = False
                        if response.status_code == 200:
                            data = response.json()
                            isolated = (
                                data["counts"]["records"] == 5
                                and {r["id"] for r in data["records"]}
                                == expected_records
                            )
                        observations.append((elapsed, response.status_code, isolated))
                return observations

            started = perf_counter()
            with ThreadPoolExecutor(max_workers=clients) as pool:
                results = [
                    row for batch in pool.map(visit, identities) for row in batch
                ]
            duration = perf_counter() - started
            times = sorted(row[0] for row in results)
            return {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "users": users,
                "concurrent_clients": clients,
                "requests": len(results),
                "rounds_per_user": rounds,
                "duration_seconds": duration,
                "p50_ms": median(times),
                "p95_ms": times[min(len(times) - 1, int(len(times) * 0.95))],
                "max_ms": max(times),
                "successful_200": sum(row[1] == 200 for row in results),
                "ownership_checks_passed": sum(row[2] for row in results),
                "scope": (
                    "In-process FastAPI TestClient; logged-in synthetic users; "
                    "disposable SQLite; no ML/provider/video workload or real network"
                ),
                "limitations": (
                    "Not a deployed PostgreSQL/100-concurrent-user benchmark; "
                    "does not establish production response-time or availability targets."
                ),
            }
        finally:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (
        not 1 <= args.users <= 500
        or not 1 <= args.clients <= 32
        or not 1 <= args.rounds <= 10
    ):
        parser.error("Use 1-500 users, 1-32 concurrent clients and 1-10 rounds.")
    if args.output.exists():
        parser.error("Choose a new report path; previous reports are not overwritten.")
    report = run(args.users, args.clients, args.rounds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if (
        report["successful_200"] != report["requests"]
        or report["ownership_checks_passed"] != report["requests"]
    ):
        raise SystemExit("Benchmark detected a failed response or ownership check.")


if __name__ == "__main__":
    main()
