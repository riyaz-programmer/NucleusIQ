from __future__ import annotations

import sqlite3
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PKG_ROOT / "data" / "chinook.sqlite"
FAT_DB_PATH = PKG_ROOT / "data" / "chinook_fat.sqlite"

DANGEROUS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
}


def get_readonly_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open SQLite read-only (DML/DDL cannot commit)."""
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run: python scripts/download_chinook.py"
        )
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def is_safe_select(query: str) -> bool:
    tokens = set(query.upper().replace(";", " ").split())
    return not (tokens & DANGEROUS)
