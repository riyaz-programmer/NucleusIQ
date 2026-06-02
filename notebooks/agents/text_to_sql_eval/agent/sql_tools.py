from __future__ import annotations

from pathlib import Path

from nucleusiq.tools.decorators import tool

from .db import get_readonly_connection, is_safe_select

_MAX_ROWS = 50
_active_db: Path | None = None


def set_active_db(path: Path | None) -> None:
    """Point tools at chinook.sqlite or chinook_fat.sqlite (context demo)."""
    global _active_db
    _active_db = path


def _db_path() -> Path:
    from .db import DB_PATH

    return _active_db if _active_db is not None else DB_PATH


def make_sql_tools() -> list:
    @tool
    def sql_list_tables() -> str:
        """List all table names in the database. Call this FIRST to discover the schema."""
        conn = get_readonly_connection(_db_path())
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            return ", ".join(r[0] for r in rows)
        finally:
            conn.close()

    @tool
    def sql_schema(table_names: str) -> str:
        """Return CREATE statements for comma-separated table names."""
        conn = get_readonly_connection(_db_path())
        try:
            wanted = [t.strip() for t in table_names.split(",") if t.strip()]
            out: list[str] = []
            for name in wanted:
                row = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (name,),
                ).fetchone()
                out.append(row[0] if row else f"-- no table named {name}")
            return "\n\n".join(out)
        finally:
            conn.close()

    @tool
    def sql_query_checker(query: str) -> str:
        """Validate SQL for safety before running. Returns OK or BLOCKED."""
        if not is_safe_select(query):
            return "BLOCKED: query contains a write/DDL statement."
        return "OK: query is a read-only SELECT."

    @tool
    def sql_query(query: str) -> str:
        """Execute a read-only SELECT; returns up to 50 rows as text."""
        if not is_safe_select(query):
            return "ERROR: write/DDL statements are not allowed. Use SELECT only."
        conn = get_readonly_connection(_db_path())
        try:
            cur = conn.execute(query)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS)
            header = " | ".join(cols)
            body = "\n".join(" | ".join(str(v) for v in row) for row in rows)
            more = "\n... (truncated)" if len(rows) == _MAX_ROWS else ""
            return f"{header}\n{body}{more}" if cols else "(no rows)"
        except Exception as e:
            return f"SQL ERROR: {e}"
        finally:
            conn.close()

    return [sql_list_tables, sql_schema, sql_query_checker, sql_query]
