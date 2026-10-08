"""Download the DDXPlus English release (CC-BY) into data/.

Files already present are skipped, so re-running is cheap.
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = {
    "release_evidences.json": "https://ndownloader.figshare.com/files/40278013",
    "release_conditions.json": "https://ndownloader.figshare.com/files/62561569",
    "release_test_patients.zip": "https://ndownloader.figshare.com/files/40278016",
}


def main() -> int:
    DATA.mkdir(exist_ok=True)
    for name, url in FILES.items():
        target = DATA / name
        if target.exists():
            print(f"skip {name} (present)")
            continue
        print(f"fetch {name} ...", flush=True)
        urllib.request.urlretrieve(url, target)
    csv_path = DATA / "release_test_patients.csv"
    if not csv_path.exists():
        with zipfile.ZipFile(DATA / "release_test_patients.zip") as zf:
            member = zf.namelist()[0]
            zf.extract(member, DATA)
            (DATA / member).rename(csv_path)
        print(f"extracted {csv_path.name}")
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
