"""Alert dispatch — file log + optional webhook."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

import requests

from sti.db import log_alert


def emit(
    conn: sqlite3.Connection,
    alert_type: str,
    ticker: str,
    message: str,
    alerts_file: str | None = None,
) -> None:
    entry = {
        "type": alert_type,
        "ticker": ticker,
        "message": message,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    log_alert(conn, alert_type, ticker, message)
    if alerts_file:
        with open(alerts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    webhook = os.environ.get("STI_ALERT_WEBHOOK")
    if webhook:
        try:
            requests.post(webhook, json=entry, timeout=10)
        except Exception:
            pass


def check_signal_alerts(
    conn: sqlite3.Connection,
    prev: dict | None,
    current: dict,
    alerts_path: str,
) -> None:
    ticker = current.get("ticker", "")
    rec = current.get("recommendation", "Hold")
    prev_rec = (prev or {}).get("recommendation")

    if rec in ("Buy", "Strong Buy") and prev_rec not in ("Buy", "Strong Buy"):
        emit(conn, "NEW_BUY", ticker, f"New {rec} signal at {current.get('confidence_pct')}%", alerts_path)
    if rec in ("Sell", "Strong Sell") and prev_rec not in ("Sell", "Strong Sell"):
        emit(conn, "NEW_SELL", ticker, f"New {rec} signal at {current.get('confidence_pct')}%", alerts_path)

    for art in current.get("sentiment", {}).get("catalysts", [])[:2]:
        if "earnings" in art.get("tags", []) or "regulatory" in art.get("tags", []):
            emit(conn, "MAJOR_NEWS", ticker, art.get("headline", "Major catalyst"), alerts_path)
