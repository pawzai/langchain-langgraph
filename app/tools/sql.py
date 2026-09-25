"""Read-only SQL access to the sample shipping database.

Two independent layers of protection, because a model can always be talked into emitting a
DELETE:

1. `validate_sql` rejects anything that is not a single bare SELECT.
2. The connection itself is opened with SQLite's `mode=ro` URI flag, so even a statement that
   slipped past validation cannot write.
"""

from __future__ import annotations

import re
import sqlite3

from langchain_core.tools import tool

from app.config import settings

MAX_ROWS = 50

# Presented to the model so it can write valid queries without guessing column names.
DATABASE_SCHEMA = """
facilities(code TEXT PK, name TEXT, outbound_enabled INTEGER)   -- 1 = outbound allowed
trailers(trailer_id TEXT PK, status TEXT, last_inspection TEXT) -- status: ACTIVE | MAINTENANCE | RETIRED
shipments(shipment_id TEXT PK, status TEXT, trailer_id TEXT NULL, location TEXT,
          priority TEXT, created_at TEXT)
          -- status: CREATED | READY_FOR_DISPATCH | IN_TRANSIT | DELIVERED | ON_HOLD
          -- trailer_id is NULL when no trailer is assigned
          -- location references facilities.code
""".strip()

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)


class SqlSafetyError(ValueError):
    """Raised when a query is not a safe read-only SELECT."""


def validate_sql(query: str) -> str:
    """Return a normalised, safe SELECT statement or raise SqlSafetyError."""
    if not query or not query.strip():
        raise SqlSafetyError("Empty query.")

    cleaned = re.sub(r"--[^\n]*", " ", query)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().rstrip(";").strip()

    if ";" in cleaned:
        raise SqlSafetyError("Multiple statements are not allowed.")

    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SqlSafetyError("Only SELECT queries are allowed.")

    if _FORBIDDEN.search(cleaned):
        raise SqlSafetyError("Query contains a write or schema-modifying keyword.")

    if not re.search(r"\blimit\b", lowered):
        cleaned = f"{cleaned} LIMIT {MAX_ROWS}"

    return cleaned


def run_query(query: str) -> list[dict]:
    """Execute a validated SELECT against a read-only connection."""
    safe = validate_sql(query)
    uri = f"file:{settings.sqlite_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(safe).fetchmany(MAX_ROWS)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _format(rows: list[dict]) -> str:
    if not rows:
        return "Query returned no rows."
    header = " | ".join(rows[0].keys())
    body = "\n".join(
        " | ".join("NULL" if v is None else str(v) for v in r.values()) for r in rows
    )
    return f"{header}\n{'-' * len(header)}\n{body}"


@tool
def query_database(query: str) -> str:
    """Run a read-only SELECT against the shipping database and return the rows.

    Only SELECT statements are permitted. Use this to inspect shipment rows, trailer status and
    facility configuration.

    Schema:
    facilities(code, name, outbound_enabled)
    trailers(trailer_id, status, last_inspection)
    shipments(shipment_id, status, trailer_id, location, priority, created_at)
    """
    try:
        return _format(run_query(query))
    except SqlSafetyError as exc:
        return f"Query rejected by safety validation: {exc}"
    except sqlite3.Error as exc:
        return f"Database error: {exc}"
