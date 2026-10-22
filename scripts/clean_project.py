"""Remove exact, archived legacy release files; preserve modified and runtime files."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
OLD_COMMANDS = {
    "finish-preeclampsia.cmd",
    "update-appointments.cmd",
    "update-assessment.cmd",
    "update-care.cmd",
    "update-communication.cmd",
    "update-interface.cmd",
    "update-preeclampsia.cmd",
    "update-remaining.cmd",
    "update-roles.cmd",
}
LIVE_REPORTS = {
    "ml/training_reports/v1.0.0/comparison.json",
    "ml/training_reports/pe-v1.0.0/pe-retraining-report.json",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed_legacy_path(name):
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts or str(path) != name:
        return False
    if len(path.parts) == 1:
        return re.fullmatch(r"START-HERE-\d+\.\d+\.\d+\.md", name) is not None
    if path.parts[0] == "scripts" and len(path.parts) == 2:
        return path.name in OLD_COMMANDS
    if path.parts[0] == "docs" and len(path.parts) == 2:
        return path.suffix in {".md", ".json"} and (
            re.search(r"-\d+\.\d+\.\d+\.", path.name) is not None
            or path.name in {"VERIFICATION.md", "REFERENCE_INSPECTION.md"}
        )
    return (
        len(path.parts) == 4
        and path.parts[:2] == ("ml", "training_reports")
        and path.parts[2] in {"v1.0.0", "pe-v1.0.0"}
        and path.suffix == ".json"
        and name not in LIVE_REPORTS
    )


def safe_target(root, name):
    current = root
    for component in PurePosixPath(name).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("Cleanup refuses symbolic links")
    return current


def clean(root=ROOT, *, apply=False):
    root = Path(root).resolve()
    manifest_path = safe_target(root, "scripts/legacy-cleanup.json")
    archive_path = safe_target(root, "docs/history.zip")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["archive"] != "docs/history.zip":
        raise ValueError("Unexpected cleanup archive")
    archive_bytes = archive_path.read_bytes()
    if digest(archive_bytes) != manifest["archive_sha256"]:
        raise ValueError("History archive failed its integrity check; no files removed")
    items = manifest["files"]
    names = [item["path"] for item in items]
    if len(names) != len(set(names)) or not all(allowed_legacy_path(name) for name in names):
        raise ValueError("Unsafe cleanup inventory; no files removed")
    # Verify the entire backup before removing even the first source file.
    with zipfile.ZipFile(archive_path) as archive:
        for item in items:
            if digest(archive.read(item["path"])) != item["sha256"]:
                raise ValueError("Archived file mismatch; no files removed")
    planned, modified, absent = [], [], 0
    for item in items:
        path = safe_target(root, item["path"])
        if not path.exists():
            absent += 1
        elif not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            modified.append(item["path"])
        else:
            planned.append((path, item))
    if apply:
        for path, item in planned:
            # Recheck immediately before unlinking; changed originals are retained.
            safe_target(root, item["path"])
            if not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
                modified.append(item["path"])
                continue
            path.unlink()
    return {
        "mode": "applied" if apply else "preview",
        "archived_legacy_files_matched": len(planned),
        "modified_files_preserved": modified,
        "already_absent": absent,
        "history_archive": "docs/history.zip",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Remove only verified archived copies")
    arguments = parser.parse_args()
    try:
        result = clean(apply=arguments.apply)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        raise SystemExit("Cleanup stopped safely. Check the combined release files.") from None
    print(json.dumps(result, indent=2))
    print("Private runtime files and locally edited legacy files are preserved.")


if __name__ == "__main__":
    main()
