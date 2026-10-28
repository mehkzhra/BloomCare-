"""Private, checksum-pinned PE assets stored in the deployment PostgreSQL database."""

import ast
import hashlib
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "forest.json": ("pe_model.py", "ARTIFACT_SHA256"),
    "manifest.json": ("pe_model.py", "MANIFEST_SHA256"),
    "explanation-weights.json": ("pe_explanation.py", "WEIGHTS_SHA256"),
}
MAX_BYTES = 4 * 1024 * 1024


def expected_hashes(root=ROOT):
    result = {}
    for name, (module, constant) in ASSETS.items():
        tree = ast.parse((root / "backend/app" / module).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == constant for target in node.targets
            ):
                result[name] = ast.literal_eval(node.value)
                break
        if name not in result:
            raise ValueError("Missing model integrity contract")
    return result


def validate(payloads, hashes):
    if set(payloads) != set(hashes):
        raise ValueError("Incomplete private model bundle")
    for name, payload in payloads.items():
        if len(payload) > MAX_BYTES or hashlib.sha256(payload).hexdigest() != hashes[name]:
            raise ValueError("Private model checksum verification failed")


def database_engine(url):
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("A PostgreSQL database URL is required")
    return create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10})


def seed(connection, directory, hashes):
    payloads = {name: (directory / name).read_bytes() for name in hashes}
    validate(payloads, hashes)
    # Versioned keys retain the previous model assets for image rollback.
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS bloomcare_runtime_assets "
        "(sha256 VARCHAR(64) PRIMARY KEY, payload TEXT NOT NULL)"
    ))
    for name, payload in payloads.items():
        connection.execute(text(
            "INSERT INTO bloomcare_runtime_assets (sha256, payload) VALUES (:sha, :payload) "
            "ON CONFLICT (sha256) DO UPDATE SET payload = EXCLUDED.payload"
        ), {"sha": hashes[name], "payload": payload.decode("utf-8")})


def restore(connection, directory, hashes):
    payloads = {}
    for name, sha in hashes.items():
        # Limit data returned even if the storage table was accidentally corrupted.
        value = connection.execute(text(
            "SELECT payload FROM bloomcare_runtime_assets "
            "WHERE sha256 = :sha AND length(payload) <= :limit"
        ), {"sha": sha, "limit": MAX_BYTES}).scalar_one_or_none()
        if value is None:
            raise ValueError("Private model assets must be provisioned before startup")
        payloads[name] = value.encode("utf-8")
    validate(payloads, hashes)
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        temporary = directory / (name + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(directory / name)


def ensure_private_models(url, root=ROOT):
    directory = root / "ml/artifacts/legacy_pe_v0.7.1"
    hashes = expected_hashes(root)
    if all((directory / name).is_file() for name in hashes):
        validate({name: (directory / name).read_bytes() for name in hashes}, hashes)
        return
    engine = database_engine(url)
    try:
        with engine.connect() as connection:
            restore(connection, directory, hashes)
    finally:
        engine.dispose()
