"""Idempotent durable local ingestion with tenant-safe read queries."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from product_intelligence.contracts import ProductEvent

DDL = """
CREATE TABLE IF NOT EXISTS raw_events (
    event_id TEXT PRIMARY KEY,
    event_time TEXT NOT NULL,
    account_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    feature_name TEXT,
    experiment_id TEXT,
    variant TEXT,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON raw_events(event_time);
CREATE INDEX IF NOT EXISTS idx_events_account_time ON raw_events(account_id,event_time);
CREATE TABLE IF NOT EXISTS daily_account_usage (
    day TEXT NOT NULL,
    account_id TEXT NOT NULL,
    active_users INTEGER NOT NULL,
    feature_events INTEGER NOT NULL,
    PRIMARY KEY(day,account_id)
);
"""


def connect(path: str | Path = "product_analytics.sqlite") -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(DDL)
    return db


def ingest(db: sqlite3.Connection, event: ProductEvent) -> bool:
    event.validate_semantics()
    with db:
        cursor = db.execute(
            """INSERT OR IGNORE INTO raw_events
            (event_id,event_time,account_id,user_id,event_name,feature_name,experiment_id,variant,ingested_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (event.event_id, event.event_time.isoformat(), event.account_id, event.user_id,
             event.event_name, event.feature_name, event.experiment_id, event.variant,
             datetime.now(timezone.utc).isoformat()),
        )
    if cursor.rowcount != 1:
        existing = db.execute(
            """SELECT event_time,account_id,user_id,event_name,feature_name,experiment_id,variant
               FROM raw_events WHERE event_id=?""", (event.event_id,)).fetchone()
        requested = (event.event_time.isoformat(), event.account_id, event.user_id,
                     event.event_name, event.feature_name, event.experiment_id, event.variant)
        if existing is None or tuple(existing) != requested:
            raise ValueError("Conflicting payload for previously seen event_id")
    return cursor.rowcount == 1


def materialize_daily(db: sqlite3.Connection, from_day: str, through_day: str) -> int:
    """Rebuild bounded event-time partitions so late arrivals can correct previous aggregates."""
    if from_day > through_day:
        raise ValueError("Invalid date range")
    with db:
        db.execute("DELETE FROM daily_account_usage WHERE day BETWEEN ? AND ?",
                   (from_day, through_day))
        db.execute(
            """INSERT INTO daily_account_usage(day,account_id,active_users,feature_events)
            SELECT substr(event_time,1,10), account_id,
                   COUNT(DISTINCT CASE WHEN event_name='feature_used' THEN user_id END),
                   SUM(CASE WHEN event_name='feature_used' THEN 1 ELSE 0 END)
            FROM raw_events
            WHERE substr(event_time,1,10) BETWEEN ? AND ?
            GROUP BY substr(event_time,1,10), account_id""",
            (from_day, through_day),
        )
    return db.execute("SELECT COUNT(*) FROM daily_account_usage WHERE day BETWEEN ? AND ?",
                      (from_day, through_day)).fetchone()[0]
