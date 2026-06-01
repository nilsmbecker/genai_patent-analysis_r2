from __future__ import annotations

from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS patents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    patent_number TEXT  NOT NULL DEFAULT '',
    source      TEXT    NOT NULL DEFAULT '',
    pdf_path    TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patent_id   INTEGER NOT NULL,
    agent       TEXT    NOT NULL,
    result_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(patent_id) REFERENCES patents(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_results_patent_agent
    ON agent_results (patent_id, agent);

CREATE INDEX IF NOT EXISTS idx_patents_number ON patents (patent_number);
"""


def get_connection(database_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
