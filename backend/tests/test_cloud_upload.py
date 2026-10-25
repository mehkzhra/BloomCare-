"""Private uploads contain the pinned runtime model and exclude credentials and records."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_cloud_upload.py"
SPEC = importlib.util.spec_from_file_location("bloomcare_cloud_upload", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def upload_source(tmp_path):
    root, models = tmp_path / "source", tmp_path / "models"
    root.mkdir()
    models.mkdir()
    hashes = {}
    for name in MODULE.PE_FILES:
        content = json.dumps({"synthetic": name}).encode()
        (models / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    files = {
        "backend/app/pe_model.py": (
            f'ARTIFACT_SHA256 = "{hashes["forest.json"]}"\n'
            f'MANIFEST_SHA256 = "{hashes["manifest.json"]}"\n'
        ),
        "backend/app/pe_explanation.py": (
            f'WEIGHTS_SHA256 = "{hashes["explanation-weights.json"]}"\n'
        ),
        "backend/tests/fixtures/maternal_risk_uci.csv": "synthetic,fixture\n",
        "frontend/package.json": '{"name":"synthetic-source"}',
        "deploy/render.Dockerfile": "FROM node:24-alpine\nRUN npm run build\nEXPOSE 10000\n",
        ".dockerignore": "**/.env*\nprivate-builds\n",
    }
    entries = []
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        content = path.read_bytes()
        entries.append({
            "path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        })
    (root / "DELIVERY-MANIFEST.json").write_text(json.dumps({"files": entries}))
    (root / "backend/.env").write_text("DO_NOT_INCLUDE_REAL_SETTINGS")
    (root / "backend/.env.snapdeploy").write_text("DO_NOT_INCLUDE_CLOUD_SETTINGS")
    (root / "backend/model-trust.json").write_text("DO_NOT_INCLUDE_LOCAL_TRUST")
    (root / "backend/old.dump").write_text("DO_NOT_INCLUDE_DATABASE")
    (models / "parity-fixtures.json").write_text("DO_NOT_INCLUDE_EXTRA_MODEL_DATA")
    return root, models


def test_upload_has_dockerfile_and_only_required_private_assets(upload_source, tmp_path):
    root, models = upload_source
    output = tmp_path / "private-builds/upload.zip"
    MODULE.package(root, models, output)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert "Dockerfile" in names and "deploy/render.Dockerfile" not in names
        assert "backend/tests/fixtures/maternal_risk_uci.csv" in names
        assert b"VITE_CALL_SIGNAL_POLL_MS=3000" in archive.read("Dockerfile")
        assert sorted(name.rsplit("/", 1)[-1] for name in names if "/artifacts/" in name) == (
            sorted(MODULE.PE_FILES)
        )
        assert not any(".env" in name or name.endswith(".dump") for name in names)
        assert b"DO_NOT_INCLUDE" not in b"".join(archive.read(name) for name in names)


@pytest.mark.parametrize("changed", ["frontend/package.json", "private-model"])
def test_changed_source_or_model_stops_before_writing_upload(upload_source, tmp_path, changed):
    root, models = upload_source
    path = models / "explanation-weights.json" if changed == "private-model" else root / changed
    path.write_text("changed")
    output = tmp_path / "upload.zip"
    with pytest.raises(ValueError, match="verification|manifest"):
        MODULE.package(root, models, output)
    assert not output.exists()


def test_manifest_cannot_read_files_outside_source(upload_source, tmp_path):
    root, models = upload_source
    path = root / "DELIVERY-MANIFEST.json"
    manifest = json.loads(path.read_text())
    manifest["files"].append({"path": "backend/../../outside.env"})
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe source path"):
        MODULE.package(root, models, tmp_path / "upload.zip")


def test_windows_checkout_restores_only_the_exact_pinned_source(upload_source, tmp_path):
    root, models = upload_source
    path = root / "backend/app/pe_model.py"
    expected = path.read_bytes()
    path.write_bytes(expected.replace(b"\n", b"\r\n"))
    output = tmp_path / "upload.zip"
    MODULE.package(root, models, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.read("backend/app/pe_model.py") == expected
