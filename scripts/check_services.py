"""Print safe setup diagnostics for the existing Windows installation; never sends data."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from app.integration_status import service_configuration  # noqa: E402


def main():
    for name, item in service_configuration().items():
        print(name.upper() + ": " + item["label"])
        print("  " + item["summary"])
        if item["missing"]:
            print("  Complete: " + ", ".join(item["missing"]))
        print("  CMD from BloomCare folder: " + item["command"])
    print("Restart the backend after changing settings. No external check or message was sent.")


if __name__ == "__main__":
    main()
