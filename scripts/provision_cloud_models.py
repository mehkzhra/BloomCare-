"""Provision pinned PE assets privately; never print credentials or model content."""

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deploy.private_models import database_engine, expected_hashes, seed  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "ml/artifacts/legacy_pe_v0.7.1")
    args = parser.parse_args()
    engine = None
    try:
        url = getpass.getpass("Current LIVE Neon database URL (hidden): ").strip()
        engine = database_engine(url)
        with engine.begin() as connection:
            seed(connection, args.model_dir, expected_hashes())
    except Exception:  # noqa: BLE001 - database errors may contain credentials
        raise SystemExit(
            "Provisioning failed. Check the live database URL, connection and original PE files. "
            "Credentials and model contents were not printed."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()
    print("READY: Three verified PE assets saved privately to the selected database.")
    print("Existing patient records and environment settings were not changed.")


if __name__ == "__main__":
    main()
