"""SQLite schema, persistence and read helpers.

The module keeps the original ``get_or_create_ipo`` / ``save_gmp`` API used by
the scrapers, and adds the query helpers the analysis layer needs
(``get_candidates`` and ``get_gmp_history``).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src import config
from src.database.migrations import apply_migrations


def _resolve_path(db_path: str | Path | None = None) -> Path:
    """Return an absolute database path.

    Relative paths passed explicitly by callers are resolved against the repo
    root too, so behaviour does not depend on the current working directory.
    """

    path = Path(db_path) if db_path is not None else config.DB_PATH
    if not path.is_absolute():
        path = config.REPO_ROOT / path
    return path


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection.

    Prefer :func:`connect` (a context manager) for new code; this function is
    kept because it was part of the original public API.
    """

    path = _resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


@contextmanager
def connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""

    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path | None = None) -> None:
    """Apply any pending schema migrations (idempotent).

    The schema itself lives in :mod:`src.database.migrations`; this function
    only opens a connection and runs whatever has not run yet.
    """

    with connect(db_path) as connection:
        apply_migrations(connection)


_SCHEMA_READY: set[Path] = set()


def ensure_schema(db_path: str | Path | None = None) -> None:
    """Create/upgrade the schema once per process for a given database."""

    path = _resolve_path(db_path)
    if path in _SCHEMA_READY:
        return

    initialize_database(path)
    _SCHEMA_READY.add(path)


def get_or_create_ipo(ipo: Any, db_path: str | Path | None = None) -> int:
    """Find an IPO by ``normalized_name``, updating it, or insert a new row.

    Only fields supplied by the incoming scraper are written. ``COALESCE``
    prevents a source with partial data from erasing values another source
    already provided.
    """

    ensure_schema(db_path)

    with connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM ipos WHERE normalized_name = ?",
            (ipo.normalized_name,),
        )
        row = cursor.fetchone()

        if row:
            ipo_db_id = int(row[0])

            cursor.execute(
                """
                UPDATE ipos
                SET
                    name = COALESCE(?, name),
                    category = COALESCE(?, category),
                    issue_price = COALESCE(?, issue_price),
                    estimated_listing_price =
                        COALESCE(?, estimated_listing_price),
                    ipo_size_cr = COALESCE(?, ipo_size_cr),
                    pe = COALESCE(?, pe),
                    open_date = COALESCE(?, open_date),
                    close_date = COALESCE(?, close_date),
                    listing_date = COALESCE(?, listing_date),
                    status = COALESCE(?, status),
                    gmp_indicator = COALESCE(?, gmp_indicator),
                    sector = COALESCE(?, sector),
                    exchange = COALESCE(?, exchange),
                    lot_size = COALESCE(?, lot_size),
                    subscription = COALESCE(?, subscription),
                    issue_price_lower = COALESCE(?, issue_price_lower),
                    issue_price_upper = COALESCE(?, issue_price_upper),
                    source_url = COALESCE(?, source_url),
                    rhp_url = COALESCE(?, rhp_url)
                WHERE id = ?
                """,
                (
                    ipo.name,
                    ipo.category,
                    ipo.issue_price,
                    ipo.estimated_listing_price,
                    ipo.ipo_size_cr,
                    ipo.pe,
                    ipo.open_date,
                    ipo.close_date,
                    ipo.listing_date,
                    ipo.status,
                    ipo.gmp_indicator,
                    ipo.sector,
                    ipo.exchange,
                    ipo.lot_size,
                    ipo.subscription,
                    ipo.issue_price_lower,
                    ipo.issue_price_upper,
                    ipo.source_url,
                    ipo.rhp_url,
                    ipo_db_id,
                ),
            )

            return ipo_db_id

        cursor.execute(
            """
            INSERT INTO ipos (
                normalized_name,
                name,
                category,
                issue_price,
                estimated_listing_price,
                ipo_size_cr,
                pe,
                open_date,
                close_date,
                listing_date,
                status,
                gmp_indicator,
                sector,
                exchange,
                lot_size,
                subscription,
                issue_price_lower,
                issue_price_upper,
                source_url,
                rhp_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ipo.normalized_name,
                ipo.name,
                ipo.category,
                ipo.issue_price,
                ipo.estimated_listing_price,
                ipo.ipo_size_cr,
                ipo.pe,
                ipo.open_date,
                ipo.close_date,
                ipo.listing_date,
                ipo.status,
                ipo.gmp_indicator,
                ipo.sector,
                ipo.exchange,
                ipo.lot_size,
                ipo.subscription,
                ipo.issue_price_lower,
                ipo.issue_price_upper,
                ipo.source_url,
                ipo.rhp_url,
            ),
        )

        return int(cursor.lastrowid)


def save_gmp(
    ipo_id: int,
    gmp: float | None,
    gmp_percent: float | None,
    source: str,
    *,
    recorded_at: str | None = None,
    scrape_run_id: int | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Record one GMP observation for an IPO/source/UTC-day.

    Re-running a scrape on the same day updates that day's row instead of
    appending a duplicate. The unique index on
    ``(ipo_id, source, snapshot_date)`` makes this an atomic upsert.
    """

    ensure_schema(db_path)
    timestamp = recorded_at or datetime.now(UTC).isoformat()
    snapshot_date = timestamp[:10]

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO gmp_history (
                ipo_id,
                source,
                gmp,
                gmp_percent,
                recorded_at,
                snapshot_date,
                scrape_run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ipo_id, source, snapshot_date)
            DO UPDATE SET
                gmp = excluded.gmp,
                gmp_percent = excluded.gmp_percent,
                recorded_at = excluded.recorded_at,
                scrape_run_id = COALESCE(
                    excluded.scrape_run_id,
                    gmp_history.scrape_run_id
                )
            """,
            (
                ipo_id,
                source,
                gmp,
                gmp_percent,
                timestamp,
                snapshot_date,
                scrape_run_id,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM gmp_history
            WHERE ipo_id = ? AND source = ? AND snapshot_date = ?
            """,
            (ipo_id, source, snapshot_date),
        ).fetchone()

        return int(row["id"])


def record_ipo_source(
    ipo_id: int,
    source: str,
    *,
    source_ipo_id: int | str | None = None,
    source_url: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Upsert the provenance link between a canonical IPO and a source row."""

    ensure_schema(db_path)
    now = datetime.now(UTC).isoformat()
    source_id = str(source_ipo_id) if source_ipo_id is not None else None

    with connect(db_path) as connection:
        if source_id is not None:
            row = connection.execute(
                """
                SELECT id FROM ipo_sources
                WHERE source = ? AND source_ipo_id = ?
                """,
                (source, source_id),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT id FROM ipo_sources
                WHERE ipo_id = ? AND source = ? AND source_ipo_id IS NULL
                """,
                (ipo_id, source),
            ).fetchone()

        if row:
            connection.execute(
                """
                UPDATE ipo_sources
                SET ipo_id = ?,
                    source_url = COALESCE(?, source_url),
                    last_seen_at = ?
                WHERE id = ?
                """,
                (ipo_id, source_url, now, row["id"]),
            )
            return int(row["id"])

        cursor = connection.execute(
            """
            INSERT INTO ipo_sources (
                ipo_id,
                source,
                source_ipo_id,
                source_url,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ipo_id, source, source_id, source_url, now, now),
        )
        return int(cursor.lastrowid)


def get_ipo_sources(
    ipo_id: int,
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return every source record linked to one canonical IPO."""

    ensure_schema(db_path)

    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, ipo_id, source, source_ipo_id, source_url,
                   first_seen_at, last_seen_at
            FROM ipo_sources
            WHERE ipo_id = ?
            ORDER BY source ASC
            """,
            (ipo_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_ipo_with_gmp(
    ipo: Any,
    source: str,
    *,
    scrape_run_id: int | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Save/update an IPO, its GMP observation and its source provenance."""

    ipo_db_id = get_or_create_ipo(ipo, db_path=db_path)

    save_gmp(
        ipo_id=ipo_db_id,
        gmp=ipo.gmp,
        gmp_percent=ipo.gmp_percent,
        source=source,
        scrape_run_id=scrape_run_id,
        db_path=db_path,
    )

    record_ipo_source(
        ipo_db_id,
        source=source,
        source_ipo_id=ipo.ipo_id,
        source_url=ipo.source_url,
        db_path=db_path,
    )

    return ipo_db_id


def get_ipo(
    ipo_id: int,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return one IPO row as a dictionary, or ``None`` if it does not exist."""

    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM ipos WHERE id = ?",
            (ipo_id,),
        ).fetchone()

    return dict(row) if row else None


def get_gmp_history(
    ipo_id: int,
    *,
    limit: int | None = 30,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return GMP observations for one IPO, newest first."""

    query = """
        SELECT id, ipo_id, source, gmp, gmp_percent, recorded_at,
               snapshot_date, scrape_run_id
        FROM gmp_history
        WHERE ipo_id = ?
        ORDER BY recorded_at DESC, id DESC
    """
    parameters: list[Any] = [ipo_id]

    if limit is not None:
        query += " LIMIT ?"
        parameters.append(int(limit))

    with connect(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


_SCORED_IPOS_CTE = """
    WITH latest AS (
        SELECT
            g.*,
            ROW_NUMBER() OVER (
                PARTITION BY ipo_id
                ORDER BY recorded_at DESC, id DESC
            ) AS row_number
        FROM gmp_history g
    ),
    scored AS (
        SELECT
            i.*,
            l.gmp AS latest_gmp,
            l.gmp_percent AS latest_gmp_percent_source,
            l.source AS latest_gmp_source,
            l.recorded_at AS latest_gmp_recorded_at,
            CASE
                WHEN l.gmp_percent IS NOT NULL
                    THEN l.gmp_percent
                WHEN l.gmp IS NOT NULL
                     AND i.issue_price IS NOT NULL
                     AND i.issue_price > 0
                    THEN (l.gmp * 100.0) / i.issue_price
                ELSE NULL
            END AS latest_gmp_percent,
            CASE
                WHEN l.gmp_percent IS NULL
                     AND l.gmp IS NOT NULL
                     AND i.issue_price IS NOT NULL
                     AND i.issue_price > 0
                    THEN 1
                ELSE 0
            END AS latest_gmp_percent_derived
        FROM ipos i
        LEFT JOIN latest l
            ON l.ipo_id = i.id
           AND l.row_number = 1
    )
"""


_IPO_SORT_COLUMNS = {
    "name": "name",
    "gmp_percent": "latest_gmp_percent",
    "close_date": "close_date",
    "subscription": "subscription",
    "pe": "pe",
    "issue_price": "issue_price",
    "updated_at": "latest_gmp_recorded_at",
}


def _ipo_filters(
    status: str | None,
    min_gmp_percent: float | None,
    q: str | None = None,
) -> tuple[str, list[Any]]:
    """Build the optional WHERE clause shared by list/count queries."""

    conditions: list[str] = []
    parameters: list[Any] = []

    if status:
        conditions.append("LOWER(status) = LOWER(?)")
        parameters.append(status.strip())

    if min_gmp_percent is not None:
        conditions.append("latest_gmp_percent >= ?")
        parameters.append(float(min_gmp_percent))

    if q and q.strip():
        # ``instr`` treats % and _ literally, unlike LIKE.
        conditions.append("instr(LOWER(name), LOWER(?)) > 0")
        parameters.append(q.strip())

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, parameters


def _ipo_order_by(sort: str | None, order: str | None) -> str:
    """Build a whitelisted ORDER BY clause, keeping missing values last."""

    key = (sort or "name").strip().lower()
    column = _IPO_SORT_COLUMNS.get(key)
    if column is None:
        raise ValueError(f"Unsupported sort field: {sort!r}")

    direction = "DESC" if (order or "asc").strip().lower() == "desc" else "ASC"

    # SQLite sorts NULLs first on ASC and last on DESC; force them last either way.
    return f"ORDER BY {column} IS NULL, {column} {direction}, name ASC"


def list_ipos(
    *,
    status: str | None = None,
    min_gmp_percent: float | None = None,
    q: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return IPOs (with their latest GMP) for the API/dashboard."""

    where, parameters = _ipo_filters(status, min_gmp_percent, q)
    query = (
        f"{_SCORED_IPOS_CTE}"
        "SELECT * FROM scored "
        f"{where} "
        f"{_ipo_order_by(sort, order)} "
        "LIMIT ? OFFSET ?"
    )
    parameters.extend([int(limit), int(offset)])

    with connect(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


def count_ipos(
    *,
    status: str | None = None,
    min_gmp_percent: float | None = None,
    q: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Count IPOs matching the same filters as :func:`list_ipos`."""

    where, parameters = _ipo_filters(status, min_gmp_percent, q)
    query = f"{_SCORED_IPOS_CTE}SELECT COUNT(*) AS total FROM scored {where}"

    with connect(db_path) as connection:
        row = connection.execute(query, parameters).fetchone()

    return int(row["total"]) if row else 0


def get_candidates(
    min_gmp_percent: float = 20.0,
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return IPOs whose latest GMP percentage meets the threshold.

    The latest observation is selected per IPO with ``ROW_NUMBER()``. When a
    source supplies an absolute GMP but no percentage, the percentage is
    derived from the issue price and flagged with ``latest_gmp_percent_derived``
    so callers can display it honestly.
    """

    query = (
        f"{_SCORED_IPOS_CTE}"
        "SELECT * FROM scored "
        "WHERE latest_gmp_percent IS NOT NULL "
        "  AND latest_gmp_percent >= ? "
        "ORDER BY latest_gmp_percent DESC, name ASC"
    )

    with connect(db_path) as connection:
        rows = connection.execute(query, (float(min_gmp_percent),)).fetchall()

    return [dict(row) for row in rows]


def save_analysis_report(
    analysis: Any,
    *,
    db_path: str | Path | None = None,
) -> int:
    """Persist an analysis object (JSON payload + score + verdict)."""

    ensure_schema(db_path)

    if hasattr(analysis, "model_dump_json"):
        payload = analysis.model_dump_json()
    else:
        payload = json.dumps(analysis, default=str)

    created_at = datetime.now(UTC).isoformat()

    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO analysis_reports (
                ipo_id,
                score,
                verdict,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(analysis.ipo_id),
                float(analysis.score),
                str(analysis.verdict),
                payload,
                created_at,
            ),
        )
        return int(cursor.lastrowid)


def create_scrape_run(
    source: str,
    *,
    db_path: str | Path | None = None,
) -> int:
    """Record the start of a scrape run and return its id."""

    ensure_schema(db_path)
    started_at = datetime.now(UTC).isoformat()

    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO scrape_runs (
                source, status, started_at, rows_scraped, rows_saved, rows_failed
            )
            VALUES (?, 'running', ?, 0, 0, 0)
            """,
            (source, started_at),
        )
        return int(cursor.lastrowid)


def update_scrape_run(
    run_id: int,
    *,
    status: str | None = None,
    rows_scraped: int | None = None,
    rows_saved: int | None = None,
    rows_failed: int | None = None,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    """Update a scrape run's progress or mark it completed/failed."""

    ensure_schema(db_path)
    updates: list[str] = []
    params: list[Any] = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if rows_scraped is not None:
        updates.append("rows_scraped = ?")
        params.append(rows_scraped)
    if rows_saved is not None:
        updates.append("rows_saved = ?")
        params.append(rows_saved)
    if rows_failed is not None:
        updates.append("rows_failed = ?")
        params.append(rows_failed)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if status in ("completed", "failed"):
        updates.append("completed_at = ?")
        params.append(datetime.now(UTC).isoformat())

    if not updates:
        return

    params.append(run_id)
    with connect(db_path) as connection:
        connection.execute(
            f"UPDATE scrape_runs SET {', '.join(updates)} WHERE id = ?",
            params,
        )


def get_scrape_runs(
    *,
    source: str | None = None,
    limit: int = 10,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return recent scrape runs, newest first."""

    ensure_schema(db_path)
    query = """
        SELECT id, source, status, started_at, completed_at,
               rows_scraped, rows_saved, rows_failed, error_message
        FROM scrape_runs
    """
    params: list[Any] = []
    if source is not None:
        query += " WHERE source = ?"
        params.append(source)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    with connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_latest_analysis(
    ipo_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return the newest stored analysis payload for one IPO."""

    ensure_schema(db_path)

    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT payload
            FROM analysis_reports
            WHERE ipo_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (ipo_id,),
        ).fetchone()

    return json.loads(row["payload"]) if row else None


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
