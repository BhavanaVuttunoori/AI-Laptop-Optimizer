"""
database.py
SQLite persistence layer using sqlite3 directly (no ORM dependency).
Handles metric logging, retrieval, and pruning.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import pandas as pd

from config import config, DB_PATH

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """Context manager that yields a connection and commits/rolls back on exit."""
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db() -> None:
    """Create tables if they do not already exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS system_metrics (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT    NOT NULL,
        cpu       REAL    NOT NULL,
        memory    REAL    NOT NULL,
        disk      REAL    NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ai_recommendations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT NOT NULL,
        prompt_hash TEXT NOT NULL,
        content     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS anomalies (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp  TEXT NOT NULL,
        metric     TEXT NOT NULL,
        value      REAL NOT NULL,
        score      REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_metrics_ts ON system_metrics(timestamp);
    """
    with get_connection() as conn:
        conn.executescript(ddl)
    logger.info("Database initialized at %s", DB_PATH)


def insert_metric(cpu: float, memory: float, disk: float) -> None:
    """Persist a single metrics snapshot."""
    sql = "INSERT INTO system_metrics (timestamp, cpu, memory, disk) VALUES (?, ?, ?, ?)"
    with get_connection() as conn:
        conn.execute(sql, (datetime.now().isoformat(), cpu, memory, disk))
    _prune_old_rows()


def _prune_old_rows() -> None:
    """Keep the table under the configured row limit to prevent unbounded growth."""
    limit = config.monitor.history_limit_rows
    sql = """
    DELETE FROM system_metrics
    WHERE id NOT IN (
        SELECT id FROM system_metrics ORDER BY id DESC LIMIT ?
    )
    """
    with get_connection() as conn:
        conn.execute(sql, (limit,))


def fetch_metrics(limit: Optional[int] = None) -> pd.DataFrame:
    """Return metrics as a DataFrame, most-recent rows first."""
    sql = "SELECT timestamp, cpu, memory, disk FROM system_metrics ORDER BY id DESC"
    if limit:
        sql += f" LIMIT {limit}"
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    if not rows:
        return pd.DataFrame(columns=["timestamp", "cpu", "memory", "disk"])
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.iloc[::-1].reset_index(drop=True)  # chronological order


def cache_ai_recommendation(prompt_hash: str, content: str) -> None:
    sql = "INSERT INTO ai_recommendations (timestamp, prompt_hash, content) VALUES (?, ?, ?)"
    with get_connection() as conn:
        conn.execute(sql, (datetime.now().isoformat(), prompt_hash, content))


def fetch_cached_recommendation(prompt_hash: str) -> Optional[str]:
    """Return cached recommendation if available (avoids repeat API calls)."""
    sql = """
    SELECT content FROM ai_recommendations
    WHERE prompt_hash = ?
    ORDER BY id DESC LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (prompt_hash,)).fetchone()
    return row["content"] if row else None


def insert_anomaly(metric: str, value: float, score: float) -> None:
    sql = "INSERT INTO anomalies (timestamp, metric, value, score) VALUES (?, ?, ?, ?)"
    with get_connection() as conn:
        conn.execute(sql, (datetime.now().isoformat(), metric, value, score))


def fetch_recent_anomalies(limit: int = 20) -> pd.DataFrame:
    sql = "SELECT * FROM anomalies ORDER BY id DESC LIMIT ?"
    with get_connection() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    if not rows:
        return pd.DataFrame(columns=["id", "timestamp", "metric", "value", "score"])
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df