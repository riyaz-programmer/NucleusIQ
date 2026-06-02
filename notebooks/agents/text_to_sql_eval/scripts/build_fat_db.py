"""Copy Chinook DB and attach many wide tables for context-pressure demo."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
SRC = PKG_ROOT / "data" / "chinook.sqlite"
DST = PKG_ROOT / "data" / "chinook_fat.sqlite"
NUM_TABLES = 60
COLS_PER_TABLE = 40


def build() -> Path:
    if not SRC.is_file():
        from scripts.download_chinook import download

        download()
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, DST)
    conn = sqlite3.connect(DST)
    for t in range(NUM_TABLES):
        cols = ", ".join(
            f"col_{c} TEXT /* padding for large schema dumps */"
            for c in range(COLS_PER_TABLE)
        )
        conn.execute(f"CREATE TABLE IF NOT EXISTS wide_table_{t} (id INTEGER PRIMARY KEY, {cols})")
    conn.commit()
    conn.close()
    print(f"Built {DST} with {NUM_TABLES} extra wide tables")
    return DST


if __name__ == "__main__":
    build()
