"""Cleanup must verify its historical backup and preserve unrelated/modified state."""

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/clean_project.py"
SPEC = importlib.util.spec_from_file_location("bloomcare_clean_project", MODULE_PATH)
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


@pytest.fixture
def installation(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    old = tmp_path / "START-HERE-1.0.2.md"
    old.write_bytes(b"Historical installation guide\n")
    with zipfile.ZipFile(tmp_path / "docs/history.zip", "w") as archive:
        archive.writestr(old.name, old.read_bytes())
    inventory = {
        "archive": "docs/history.zip",
        "archive_sha256": cleanup.digest((tmp_path / "docs/history.zip").read_bytes()),
        "files": [{"path": old.name, "sha256": cleanup.digest(old.read_bytes())}],
    }
    (tmp_path / "scripts/legacy-cleanup.json").write_text(json.dumps(inventory))
    return tmp_path, old, inventory


def test_cleanup_preview_apply_repeat_and_runtime_preservation(installation):
    root, old, _ = installation
    private = root / "backend"
    private.mkdir()
    for name in [".env", "model-trust.json", "patient.db"]:
        (private / name).write_bytes(b"Private runtime state")
    assert cleanup.clean(root)["mode"] == "preview" and old.exists()
    assert cleanup.clean(root, apply=True)["archived_legacy_files_matched"] == 1
    assert not old.exists()
    assert cleanup.clean(root, apply=True)["already_absent"] == 1
    assert all(p.read_bytes() == b"Private runtime state" for p in private.iterdir())
    with zipfile.ZipFile(root / "docs/history.zip") as archive:
        assert archive.read(old.name) == b"Historical installation guide\n"


def test_cleanup_keeps_locally_edited_legacy_files(installation):
    root, old, _ = installation
    old.write_bytes(b"My deployment notes")
    result = cleanup.clean(root, apply=True)
    assert result["modified_files_preserved"] == [old.name]
    assert old.read_bytes() == b"My deployment notes"


def test_cleanup_rejects_tampered_archive_before_deletion(installation):
    root, old, _ = installation
    (root / "docs/history.zip").write_bytes(b"Invalid backup")
    with pytest.raises(ValueError, match="integrity"):
        cleanup.clean(root, apply=True)
    assert old.exists()


@pytest.mark.parametrize("name", ["../private.txt", "backend/.env", "docs/DEPLOYMENT.md"])
def test_cleanup_rejects_unsafe_inventory_paths(installation, name):
    root, old, inventory = installation
    inventory["files"][0]["path"] = name
    (root / "scripts/legacy-cleanup.json").write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match="Unsafe"):
        cleanup.clean(root, apply=True)
    assert old.exists()


def test_cleanup_refuses_symbolic_links(installation, tmp_path):
    root, old, _ = installation
    other = tmp_path / "unrelated.txt"
    other.write_bytes(old.read_bytes())
    old.unlink()
    try:
        old.symlink_to(other)
    except OSError:
        pytest.skip("Symbolic-link creation is unavailable in this Windows environment")
    with pytest.raises(ValueError, match="symbolic"):
        cleanup.clean(root, apply=True)
    assert other.exists()
