"""Create and populate the fictional shipping database.

Safe to re-run; it rebuilds the tables from scratch.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

SCHEMA = """
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS trailers;
DROP TABLE IF EXISTS facilities;

CREATE TABLE facilities (
    code              TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    outbound_enabled  INTEGER NOT NULL
);

CREATE TABLE trailers (
    trailer_id        TEXT PRIMARY KEY,
    status            TEXT NOT NULL,
    last_inspection   TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id       TEXT PRIMARY KEY,
    status            TEXT NOT NULL,
    trailer_id        TEXT,
    location          TEXT NOT NULL,
    priority          TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (trailer_id) REFERENCES trailers (trailer_id),
    FOREIGN KEY (location) REFERENCES facilities (code)
);
"""

FACILITIES = [
    ("SEA", "Seattle", 1),
    ("PDX", "Portland", 1),
    ("DFW", "Dallas Fort Worth", 1),
    ("BOI", "Boise", 0),
]

TRAILERS = [
    ("TRL-204", "ACTIVE", "2026-07-15"),
    ("TRL-207", "ACTIVE", "2026-07-28"),
    ("TRL-311", "MAINTENANCE", "2026-05-20"),
    ("TRL-402", "ACTIVE", "2026-08-11"),
    ("TRL-455", "RETIRED", "2025-11-02"),
]

SHIPMENTS = [
    # The canonical demo case: no trailer assigned at all.
    ("SHP-1007", "CREATED", None, "SEA", "STANDARD", "2026-08-30 04:12:03"),
    ("SHP-1008", "IN_TRANSIT", "TRL-204", "PDX", "EXPRESS", "2026-08-30 04:15:41"),
    # Trailer assigned but swept into MAINTENANCE overnight.
    ("SHP-1010", "CREATED", "TRL-311", "DFW", "EXPRESS", "2026-08-30 08:11:22"),
    # Everything valid except the facility is inbound only.
    ("SHP-1013", "CREATED", "TRL-402", "BOI", "STANDARD", "2026-08-30 09:04:55"),
    ("SHP-1014", "READY_FOR_DISPATCH", "TRL-207", "SEA", "ECONOMY", "2026-08-30 13:22:31"),
    ("SHP-1002", "DELIVERED", "TRL-204", "SEA", "STANDARD", "2026-08-28 22:05:00"),
]


def seed() -> Path:
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO facilities VALUES (?, ?, ?)", FACILITIES)
        conn.executemany("INSERT INTO trailers VALUES (?, ?, ?)", TRAILERS)
        conn.executemany("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?)", SHIPMENTS)
        conn.commit()
    finally:
        conn.close()
    return settings.sqlite_path


if __name__ == "__main__":
    path = seed()
    print(f"Seeded {len(SHIPMENTS)} shipments, {len(TRAILERS)} trailers -> {path}")
