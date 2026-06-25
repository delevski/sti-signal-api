"""FastAPI server for external STI access."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sti.config import load_env, paths
from sti.db import connect, get_agent_stats, recent_alerts, signal_history
from sti.pipeline import analyze_ticker, run_pipeline

load_env()
app = FastAPI(title="Stock Signal Intelligence API", version="2.0.0")


def _auth(x_api_key: str | None = Header(default=None)) -> None:
    required = os.environ.get("STI_API_KEY")
    if required and x_api_key != required:
        raise HTTPException(401, "Invalid API key")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/signal/{ticker}")
def get_signal(ticker: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    load_env()
    p = paths()
    from datetime import datetime, timezone
    from sti.pipeline import _dated_data_dir

    conn = connect(p["db"])
    data_dir = _dated_data_dir(p)

    from fetch_market_data import fetch_ticker_bundle

    os.environ.setdefault("STI_DATA_CACHE_DIR", str(p["data"]))
    fetch_ticker_bundle(ticker.upper(), data_dir)

    sig = analyze_ticker(ticker.upper(), data_dir, conn, p)
    conn.close()
    if not sig:
        raise HTTPException(404, f"No data for {ticker}")
    return JSONResponse(sig)


@app.get("/signal/{ticker}/report", response_class=HTMLResponse)
def get_signal_report(ticker: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    html_path = p["signals"] / f"{ticker.upper()}-{today}.html"
    if not html_path.is_file():
        get_signal(ticker, x_api_key)
        html_path = p["signals"] / f"{ticker.upper()}-{today}.html"
    if not html_path.is_file():
        raise HTTPException(404, "Report not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/scan")
def scan(
    screener: bool = Query(False),
    limit: int = Query(20, le=50),
    x_api_key: str | None = Header(default=None),
):
    _auth(x_api_key)
    result = run_pipeline(screener=screener, screener_limit=limit)
    return result


@app.get("/opportunities")
def opportunities(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    from datetime import datetime, timezone
    scan_file = p["reports"] / f"scan-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    if not scan_file.is_file():
        result = run_pipeline()
        return result["signals"]
    import json
    return json.loads(scan_file.read_text())


@app.get("/performance/agents")
def agent_performance(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    conn = connect(p["db"])
    stats = get_agent_stats(conn)
    conn.close()
    return stats


@app.get("/alerts")
def alerts(limit: int = 20, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    conn = connect(p["db"])
    data = recent_alerts(conn, limit)
    conn.close()
    return data


@app.get("/history/{ticker}")
def history(ticker: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    conn = connect(p["db"])
    hist = signal_history(conn, ticker.upper())
    conn.close()
    return hist
