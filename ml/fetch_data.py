"""Fetch a verified public dataset directly from its original repository."""

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
SOURCE_URL = "https://archive.ics.uci.edu/static/public/863/maternal+health+risk.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/863/maternal+health+risk"
CSV_NAME = "Maternal Health Risk Data Set.csv"
EXPECTED_CSV_SHA256 = "a1f7025719f84715096e0d1f95ae2e56b57809b9b15449e1836c96a7d976ae9b"


def fetch_data():
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    target = data_dir / "maternal_risk_uci.csv"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED_CSV_SHA256:
            raise ValueError("Existing CSV differs from the verified source; move it and retry")
        return target
    request = Request(SOURCE_URL, headers={"User-Agent": "BloomCare-Independent-Training/0.2"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("Source download is unexpectedly large")
    with ZipFile(io.BytesIO(payload)) as archive:
        if CSV_NAME not in archive.namelist() or archive.getinfo(CSV_NAME).file_size > 2_000_000:
            raise ValueError("Source archive does not contain the expected CSV")
        csv_bytes = archive.read(CSV_NAME)
    digest = hashlib.sha256(csv_bytes).hexdigest()
    if digest != EXPECTED_CSV_SHA256:
        raise ValueError("UCI source changed. Review its contents and provenance before training")
    target.write_bytes(csv_bytes)
    metadata = {
        "source_repository": "UCI Machine Learning Repository",
        "source_page": SOURCE_PAGE,
        "download_url": SOURCE_URL,
        "citation": "Ahmed, M. (2020). Maternal Health Risk [Dataset]. UCI Machine Learning "
        "Repository. https://doi.org/10.24432/C5DP5D",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "sha256": digest,
        "old_project_artifacts_used": False,
    }
    (data_dir / "source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    print(f"Verified independent dataset saved to {fetch_data()}")
