"""Tests for numbered migrations and the legacy-database upgrade path."""

from __future__ import annotations

import sqlite3

from src.database import db
from src.database.migrations import MIGRATIONS


def test_initialize_records_every_migration_once(tmp_path):
    db_path = tmp_path / "test.db"

    db.initialize_database(db_path)
    db.initialize_database(db_path)  # idempotent

    with sqlite3.connect(db_path) as connection:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

    assert versions == [migration.version for migration in MIGRATIONS]


def test_legacy_database_is_upgraded_and_gmp_rows_deduped(tmp_path):
    db_path = tmp_path / "legacy.db"

    # Simulate a database created before migrations existed: base tables only,
    # with two GMP observations on the same day and one on the next day.
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE ipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            normalized_name TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE gmp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ipo_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            gmp REAL,
            gmp_percent REAL,
            recorded_at TEXT NOT NULL
        );

        INSERT INTO ipos (normalized_name, name) VALUES ('example', 'Example Ltd');
        INSERT INTO gmp_history (ipo_id, source, gmp, gmp_percent, recorded_at)
        VALUES
            (1, 'test', 10.0, 10.0, '2026-01-01T01:00:00+00:00'),
            (1, 'test', 20.0, 20.0, '2026-01-01T09:00:00+00:00'),
            (1, 'test', 30.0, 30.0, '2026-01-02T09:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    db.initialize_database(db_path)

    history = db.get_gmp_history(1, limit=None, db_path=db_path)

    # Same-day duplicates collapse to the newest row; different days survive.
    assert [row["gmp"] for row in history] == [30.0, 20.0]
    assert {row["snapshot_date"] for row in history} == {
        "2026-01-01",
        "2026-01-02",
    }

    with sqlite3.connect(db_path) as upgraded:
        columns = {
            row[1]
            for row in upgraded.execute("PRAGMA table_info(gmp_history)")
        }
        ipo_columns = {
            row[1] for row in upgraded.execute("PRAGMA table_info(ipos)")
        }

    assert {"snapshot_date", "scrape_run_id"} <= columns
    assert {"sector", "subscription", "rhp_url"} <= ipo_columns

    # Migration 6 backfills provenance from the existing history.
    sources = db.get_ipo_sources(1, db_path=db_path)
    assert [row["source"] for row in sources] == ["test"]
