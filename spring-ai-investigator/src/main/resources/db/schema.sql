DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS trailers;
DROP TABLE IF EXISTS facilities;

CREATE TABLE facilities (
    code             TEXT PRIMARY KEY,
    name             TEXT    NOT NULL,
    outbound_enabled INTEGER NOT NULL
);

CREATE TABLE trailers (
    trailer_id      TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    last_inspection TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    trailer_id  TEXT,
    location    TEXT NOT NULL,
    priority    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (trailer_id) REFERENCES trailers (trailer_id),
    FOREIGN KEY (location) REFERENCES facilities (code)
);
