"""Create a private Docker source upload with pinned PE assets and no credentials."""

import argparse
import ast
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PE_FILES = {
    "forest.json": ("pe_model.py", "ARTIFACT_SHA256"),
    "manifest.json": ("pe_model.py", "MANIFEST_SHA256"),
    "explanation-weights.json": ("pe_explanation.py", "WEIGHTS_SHA256"),
}


def pinned_hash(root, module, name):
    tree = ast.parse((root / "backend/app" / module).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                return value
    raise ValueError("The application model integrity contract is missing.")


def source_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Unsafe source path in the delivery manifest.")
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Source files must stay inside the project.")
    return resolved


def runtime_source(name):
    path = PurePosixPath(name)
    if any(part.startswith(".env") for part in path.parts):
        return False
    if path.name == "model-trust.json" or path.suffix in {".dump", ".backup", ".db"}:
        return False
    if name.startswith("backend/tests/"):
        return name == "backend/tests/fixtures/maternal_risk_uci.csv"
    if name.startswith(("backend/", "frontend/")):
        return True
    if name.startswith("ml/"):
        return len(path.parts) == 2 and (path.suffix == ".py" or path.name == "requirements.txt")
    return name in {
        ".dockerignore", "deploy/prepare_cloud_model.py", "deploy/start_cloud.py",
        "deploy/private_models.py",
        "deploy/render.Dockerfile",
    }


def package(root, model_directory, destination):
    manifest = json.loads((root / "DELIVERY-MANIFEST.json").read_text(encoding="utf-8"))
    files = {}
    for entry in manifest["files"]:
        name = entry["path"]
        path = source_path(root, name)
        if not runtime_source(name):
            continue
        content = path.read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            # Windows Git may check text out as CRLF. Accept only an exact match
            # to the pinned canonical bytes after restoring LF line endings.
            content = content.replace(b"\r\n", b"\n")
            if (
                len(content) != entry["bytes"]
                or hashlib.sha256(content).hexdigest() != entry["sha256"]
            ):
                raise ValueError("Source differs from the delivery manifest: " + name)
        if name in files:
            raise ValueError("Duplicate source path in the delivery manifest.")
        files[name] = content
    for name, (module, constant) in PE_FILES.items():
        content = (model_directory / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != pinned_hash(root, module, constant):
            raise ValueError("Private PE file failed integrity verification: " + name)
        files["ml/artifacts/legacy_pe_v0.7.1/" + name] = content
    dockerfile = files.pop("deploy/render.Dockerfile").decode("utf-8")
    # This public build setting reduces signaling requests on shared free-host quotas.
    dockerfile = dockerfile.replace(
        "RUN npm run build",
        "ARG VITE_CALL_SIGNAL_POLL_MS=3000\n"
        "ENV VITE_CALL_SIGNAL_POLL_MS=$VITE_CALL_SIGNAL_POLL_MS\nRUN npm run build",
    )
    files["Dockerfile"] = dockerfile.encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output.getvalue())
    return {"files": len(files), "bytes": destination.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "ml/artifacts/legacy_pe_v0.7.1")
    arguments = parser.parse_args()
    destination = ROOT / "private-builds/BloomCare-Cloud-Upload.zip"
    try:
        result = package(ROOT, arguments.model_dir, destination)
    except (ValueError, OSError, KeyError) as error:
        message = (
            str(error) if isinstance(error, ValueError) else "Check source and private model files."
        )
        raise SystemExit(message) from None
    print(f"Created {destination} ({result['files']} files, {result['bytes']} bytes).")
    print(
        "Private hosting upload only: includes the PE model; keep it out of public Git/registries."
    )
    print("Database records, credentials and the private settings export are not included.")


if __name__ == "__main__":
    main()
