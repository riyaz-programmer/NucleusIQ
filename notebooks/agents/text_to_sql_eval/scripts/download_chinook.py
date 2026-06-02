"""Download Chinook SQLite sample database."""

from __future__ import annotations

import urllib.request
from pathlib import Path

URL = (
    "https://github.com/lerocha/chinook-database/raw/master/"
    "ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
)
PKG_ROOT = Path(__file__).resolve().parent.parent
OUT = PKG_ROOT / "data" / "chinook.sqlite"


def download() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL} -> {OUT}")
    urllib.request.urlretrieve(URL, OUT)
    import sqlite3

    conn = sqlite3.connect(OUT)
    n = conn.execute(
        "SELECT COUNT(*) FROM Customer WHERE Country='Canada'"
    ).fetchone()[0]
    conn.close()
    print(f"Sanity check: Canada customers = {n} (expected 8)")
    return OUT


if __name__ == "__main__":
    download()
