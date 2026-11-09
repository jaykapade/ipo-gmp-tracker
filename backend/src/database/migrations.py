"""Numbered, idempotent SQLite migrations.

``initialize_database()`` calls :func:`apply_migrations`. Each migration runs
once and its version is recorded in ``schema_migrations``. Adding a new change
means appending a ``Migration`` to :data:`MIGRATIONS` — never editing an old
one that may already have run on someone's database.

Why numbered migrations? ``ALTER TABLE`` blocks scattered through the schema
code are hard to reason about and impossible to audit. A migration list gives
you a history you can read top to bottom.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _add_missing_columns(
    connection: sqlite3.Connection,
    table: str,
    columns: dict[str, str],
) -> None:
    existing = _column_names(connection, table)
    for column_name, column_type in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"
            )


def _m001_initial_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS ipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            normalized_name TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,

            category TEXT,

            issue_price REAL,
            estimated_listing_price REAL,

            ipo_size_cr TEXT,
            pe REAL,

            open_date TEXT,
            close_date TEXT,
            listing_date TEXT,

            status TEXT,
            gmp_indicator TEXT,

            sector TEXT,
            exchange TEXT,
            lot_size TEXT,
            subscription REAL,
            issue_price_lower REAL,
            issue_price_upper REAL,
            source_url TEXT,
            rhp_url TEXT
        );

        CREATE TABLE IF NOT EXISTS gmp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ipo_id INTEGER NOT NULL,

            source TEXT NOT NULL,

            gmp REAL,
            gmp_percent REAL,

            recorded_at TEXT NOT NULL,

            FOREIGN KEY (ipo_id)
                REFERENCES ipos(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS analysis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ipo_id INTEGER NOT NULL,

            score REAL NOT NULL,
            verdict TEXT NOT NULL,
            payload TEXT NOT NULL,

            created_at TEXT NOT NULL,

            FOREIGN KEY (ipo_id)
                REFERENCES ipos(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_gmp_history_ipo_recorded
        ON gmp_history (ipo_id, recorded_at DESC);

        CREATE INDEX IF NOT EXISTS idx_analysis_reports_ipo_created
        ON analysis_reports (ipo_id, created_at DESC);
        """
    )


def _m002_ipos_extended_columns(connection: sqlite3.Connection) -> None:
    _add_missing_columns(
        connection,
        "ipos",
        {
            "category": "TEXT",
            "issue_price": "REAL",
            "estimated_listing_price": "REAL",
            "ipo_size_cr": "TEXT",
            "pe": "REAL",
            "open_date": "TEXT",
            "close_date": "TEXT",
            "listing_date": "TEXT",
            "status": "TEXT",
            "gmp_indicator": "TEXT",
            "sector": "TEXT",
            "exchange": "TEXT",
            "lot_size": "TEXT",
            "subscription": "REAL",
            "issue_price_lower": "REAL",
            "issue_price_upper": "REAL",
            "source_url": "TEXT",
            "rhp_url": "TEXT",
        },
    )


def _m003_scrape_runs(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source TEXT NOT NULL,
            status TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            rows_scraped INTEGER NOT NULL DEFAULT 0,
            rows_saved INTEGER NOT NULL DEFAULT 0,
            rows_failed INTEGER NOT NULL DEFAULT 0,

            error_message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_scrape_runs_source_started
        ON scrape_runs (source, started_at DESC);
        """
    )


def _m004_ipo_sources(connection: sqlite3.Connection) -> None:
    """Provenance: link one canonical IPO to each source's own record.

    ``ipos.ipo_id`` used to hold a source-specific id, which is ambiguous when
    two sources disagree. This table keeps that information honestly.
    """

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS ipo_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ipo_id INTEGER NOT NULL,
            source TEXT NOT NULL,

            source_ipo_id TEXT,
            source_url TEXT,

            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,

            FOREIGN KEY (ipo_id)
                REFERENCES ipos(id)
                ON DELETE CASCADE,

            UNIQUE (source, source_ipo_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ipo_sources_ipo
        ON ipo_sources (ipo_id, source);
        """
    )


def _m005_gmp_dedupe(connection: sqlite3.Connection) -> None:
    """One GMP row per IPO/source/UTC-day instead of unbounded duplicates."""

    _add_missing_columns(
        connection,
        "gmp_history",
        {
            "snapshot_date": "TEXT",
            "scrape_run_id": "INTEGER",
        },
    )

    connection.execute(
        """
        UPDATE gmp_history
        SET snapshot_date = substr(recorded_at, 1, 10)
        WHERE snapshot_date IS NULL
        """
    )

    # Keep the newest row in each day bucket before adding the unique index.
    connection.execute(
        """
        DELETE FROM gmp_history
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM gmp_history
            GROUP BY ipo_id, source, snapshot_date
        )
        """
    )

    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_gmp_history_unique_snapshot
        ON gmp_history (ipo_id, source, snapshot_date);

        CREATE INDEX IF NOT EXISTS idx_gmp_history_scrape_run
        ON gmp_history (scrape_run_id);
        """
    )


def _m006_backfill_ipo_sources(connection: sqlite3.Connection) -> None:
    """Seed provenance from history for rows scraped before migration 4.

    GMP history records which source saw each IPO, so it is enough to create
    the link. ``source_ipo_id`` stays ``NULL`` because the old schema did not
    keep it separately.
    """

    connection.execute(
        """
        INSERT INTO ipo_sources (
            ipo_id,
            source,
            source_ipo_id,
            source_url,
            first_seen_at,
            last_seen_at
        )
        SELECT
            g.ipo_id,
            g.source,
            NULL,
            i.source_url,
            MIN(g.recorded_at),
            MAX(g.recorded_at)
        FROM gmp_history g
        JOIN ipos i ON i.id = g.ipo_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM ipo_sources s
            WHERE s.ipo_id = g.ipo_id AND s.source = g.source
        )
        GROUP BY g.ipo_id, g.source, i.source_url
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial schema", _m001_initial_schema),
    Migration(2, "ipos extended columns", _m002_ipos_extended_columns),
    Migration(3, "scrape runs", _m003_scrape_runs),
    Migration(4, "ipo source provenance", _m004_ipo_sources),
    Migration(5, "gmp snapshot dedupe", _m005_gmp_dedupe),
    Migration(6, "backfill ipo sources", _m006_backfill_ipo_sources),
)


def apply_migrations(connection: sqlite3.Connection) -> list[int]:
    """Apply pending migrations and return the versions that ran."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )

    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations")
    }

    ran: list[int] = []
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue

        migration.apply(connection)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (
                migration.version,
                migration.name,
                datetime.now(UTC).isoformat(),
            ),
        )
        ran.append(migration.version)

    return ran
