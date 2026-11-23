"""Download the AdventureWorks sample data and the Postgres port, check them, get them ready.

    python scripts/fetch_source.py

1. Microsoft's AdventureWorks OLTP install script zip (the CSVs), from the official
   microsoft/sql-server-samples GitHub release. Public sample data about a made-up bike company.
2. lorint/AdventureWorks-for-Postgres at a pinned commit (MIT licence): install.sql builds the
   68 tables in Postgres and loads the CSVs.
3. Checks both against the SHA-256 recorded below, so a changed download is refused, not run.
4. Converts the CSVs for Postgres (scripts/convert_csvs.py).

Everything lands in data/download/, which is in .gitignore.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "data" / "download"
sys.path.insert(0, str(ROOT / "scripts"))
from convert_csvs import convert  # noqa: E402

MS_URL = "https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks-oltp-install-script.zip"
MS_SHA = "58962e94ea386ef7cd3d8a08211bfd42a79d9b81bdd68fd4b6b0051de6c5bd42"
LORINT_COMMIT = "b474991f0df1c4bf55ca4735eb0254ca0709eed2"
LORINT_URL = f"https://github.com/lorint/AdventureWorks-for-Postgres/archive/{LORINT_COMMIT}.zip"
INSTALL_SHA = "27f71c99365aa5f44dba5d3b7ca092a654fcf50e6931c4dbe96ba2a13f8b7e0e"


def get(url: str) -> bytes:
    print("downloading", url)
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    csv_dir, port_dir = DL / "csv", DL / "postgres_port"
    if (port_dir / "install.sql").exists() and any(csv_dir.glob("*.csv")):
        print("already downloaded; delete data/download to fetch again")
        return 0
    for d in (csv_dir, port_dir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    ms = get(MS_URL)
    if sha(ms) != MS_SHA:
        sys.exit(f"Microsoft zip checksum changed ({sha(ms)}). Read what changed before trusting it.")
    with zipfile.ZipFile(io.BytesIO(ms)) as z:
        for name in z.namelist():
            if name.lower().endswith(".csv") and "/" not in name.strip("/"):
                (csv_dir / name).write_bytes(z.read(name))

    port = get(LORINT_URL)
    with zipfile.ZipFile(io.BytesIO(port)) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if base in ("install.sql", "LICENSE", "README.md", "update_csvs.rb"):
                (port_dir / base).write_bytes(z.read(name))
    got = sha((port_dir / "install.sql").read_bytes())
    if got != INSTALL_SHA:
        sys.exit(f"install.sql checksum changed ({got}). Read it before running it.")

    files = sorted(csv_dir.glob("*.csv"))
    changed = [f.name for f in files if convert(f)]
    print(f"{len(files)} CSVs saved to {csv_dir.relative_to(ROOT)}, {len(changed)} converted for Postgres")
    print(f"install.sql saved to {port_dir.relative_to(ROOT)} (checksum matches the one that was read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
