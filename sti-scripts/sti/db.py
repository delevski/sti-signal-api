"""SQLite persistence for predictions and agent performance."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    recommendation TEXT,
    confidence_pct REAL,
    ensemble_score REAL,
    agent_scores_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER,
    ticker TEXT,
    horizon_days INTEGER,
    return_pct REAL,
    correct INTEGER,
    evaluated_at TEXT,
    FOREIGN KEY(prediction_id) REFERENCES predictions(id)
);
CREATE TABLE IF NOT EXISTS agent_stats (
    agent TEXT PRIMARY KEY,
    total INTEGER DEFAULT 0,
    correct INTEGER DEFAULT 0,
    avg_return REAL DEFAULT 0,
    win_rate REAL DEFAULT 0.5,
    sharpe REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    profit_factor REAL DEFAULT 1,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    date TEXT,
    recommendation TEXT,
    confidence_pct REAL,
    snapshot_json TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    ticker TEXT,
    message TEXT,
    created_at TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_prediction(conn: sqlite3.Connection, signal: dict[str, Any]) -> int:
    cur = conn.execute(
        """INSERT INTO predictions (ticker, date, recommendation, confidence_pct, ensemble_score, agent_scores_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            signal.get("ticker"),
            signal.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            signal.get("recommendation"),
            signal.get("confidence_pct"),
            signal.get("ensemble_score"),
            json.dumps(signal.get("agent_scores", {})),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.execute(
        """INSERT INTO signal_history (ticker, date, recommendation, confidence_pct, snapshot_json)
           VALUES (?, ?, ?, ?, ?)""",
        (
            signal.get("ticker"),
            signal.get("date"),
            signal.get("recommendation"),
            signal.get("confidence_pct"),
            json.dumps(signal),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_agent_stats(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute("SELECT * FROM agent_stats").fetchall()
    if not rows:
        return {
            a: {"win_rate": 0.5, "accuracy": 0.5, "sharpe": 0, "max_drawdown": 0, "profit_factor": 1, "total": 0}
            for a in ("technical", "fundamental", "sentiment", "risk")
        }
    return {r["agent"]: dict(r) for r in rows}


def update_agent_stats(conn: sqlite3.Connection, agent: str, correct: bool, ret: float) -> None:
    row = conn.execute("SELECT * FROM agent_stats WHERE agent = ?", (agent,)).fetchone()
    if row:
        total = row["total"] + 1
        correct_n = row["correct"] + (1 if correct else 0)
        avg_ret = (row["avg_return"] * row["total"] + ret) / total
    else:
        total, correct_n, avg_ret = 1, (1 if correct else 0), ret
    win_rate = correct_n / total if total else 0.5
    conn.execute(
        """INSERT INTO agent_stats (agent, total, correct, avg_return, win_rate, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(agent) DO UPDATE SET
           total=excluded.total, correct=excluded.correct, avg_return=excluded.avg_return,
           win_rate=excluded.win_rate, updated_at=excluded.updated_at""",
        (agent, total, correct_n, avg_ret, win_rate, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def adaptive_weights(conn: sqlite3.Connection, base: dict[str, float]) -> dict[str, float]:
    stats = get_agent_stats(conn)
    raw = {}
    for agent, w in base.items():
        acc = stats.get(agent, {}).get("win_rate", 0.5)
        # Penalize poor performers — floor at 0.05
        raw[agent] = max(0.05, w * (0.5 + acc))
    total = sum(raw.values()) or 1
    return {k: round(v / total, 4) for k, v in raw.items()}


def log_alert(conn: sqlite3.Connection, alert_type: str, ticker: str, message: str) -> None:
    conn.execute(
        "INSERT INTO alerts (type, ticker, message, created_at) VALUES (?, ?, ?, ?)",
        (alert_type, ticker, message, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def recent_alerts(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def signal_history(conn: sqlite3.Connection, ticker: str, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT date, recommendation, confidence_pct FROM signal_history WHERE ticker = ? ORDER BY id DESC LIMIT ?",
        (ticker, limit),
    ).fetchall()
    return [dict(r) for r in rows]
