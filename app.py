"""STI API + Telegram webhook — Vercel serverless entry."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Vercel runs from this directory
HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "sti-scripts"
sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("STI_SERVERLESS_ROOT", "/tmp/sti")

from sti.config import load_env, paths  # noqa: E402
from sti.db import connect, get_agent_stats, recent_alerts, signal_history  # noqa: E402
from sti.pipeline import analyze_ticker, run_pipeline  # noqa: E402

load_env()
app = FastAPI(title="Stock Signal Intelligence API", version="2.1.0")


def _seed_serverless_memory(p: dict[str, Path]) -> None:
    """Copy bundled watchlist/weights into /tmp on cold start."""
    mem = HERE / "memory"
    p["memory"].mkdir(parents=True, exist_ok=True)
    for name in ("watchlist.md", "methodology-weights.md"):
        src = mem / name
        dst = p["memory"] / name
        if src.is_file() and not dst.is_file():
            shutil.copy(src, dst)


def _auth(x_api_key: str | None = Header(default=None)) -> None:
    required = os.environ.get("STI_API_KEY")
    if required and x_api_key != required:
        raise HTTPException(401, "Invalid API key")


def _dated_data_dir(p: dict[str, Path]) -> Path:
    from datetime import datetime, timezone

    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = p["data"] / d
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.on_event("startup")
def startup() -> None:
    p = paths()
    _seed_serverless_memory(p)
    connect(p["db"]).close()


@app.get("/")
def root():
    return {
        "service": "Stock Signal Intelligence",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/health",
        "telegram": "/telegram/webhook",
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0", "runtime": "vercel"}


@app.get("/signal/{ticker}")
def get_signal(ticker: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    conn = connect(p["db"])
    data_dir = _dated_data_dir(p)

    from fetch_market_data import fetch_ticker_bundle  # noqa: E402

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
    return run_pipeline(screener=screener, screener_limit=limit)


@app.get("/opportunities")
def opportunities(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    p = paths()
    from datetime import datetime, timezone

    scan_file = p["reports"] / f"scan-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    if not scan_file.is_file():
        result = run_pipeline()
        return result["signals"]
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


# --- Telegram ---

def _tg_send(chat_id: int, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    import requests

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4090], "parse_mode": "Markdown"},
            timeout=20,
        )
    except Exception:
        pass


def _format_signal(sig: dict) -> str:
    ticker = sig.get("ticker", "?")
    rec = sig.get("recommendation", "Hold")
    conf = sig.get("confidence_pct", 0)
    risk = sig.get("risk", {})
    explain = sig.get("explain", {})
    agents = sig.get("agent_scores", {})
    lines = [
        f"*{ticker}* — *{rec}* ({conf:.0f}% confidence)",
        f"Score: {sig.get('ensemble_score', 0):.2f}",
    ]
    if risk.get("stop_loss"):
        lines.append(
            f"Stop: ${risk['stop_loss']:.2f} | Target: ${risk.get('take_profit', 0):.2f} | R:R {risk.get('risk_reward_ratio', 0):.1f}"
        )
    if agents:
        parts = [f"{k.title()}: {v.get('signal', '?')}" for k, v in agents.items()]
        lines.append(" | ".join(parts))
    summary = explain.get("summary") or explain.get("why")
    if summary:
        lines.append(f"\n_{summary[:500]}_")
    return "\n".join(lines)


def _handle_telegram_command(chat_id: int, text: str) -> None:
    text = (text or "").strip()
    if not text or text.startswith("/start"):
        _tg_send(
            chat_id,
            "*STI Bot*\n\n"
            "Commands:\n"
            "`/signal AAPL` — analyze a ticker\n"
            "`/help` — this message",
        )
        return
    if text.startswith("/help"):
        _handle_telegram_command(chat_id, "/start")
        return
    if text.startswith("/signal"):
        parts = text.split()
        if len(parts) < 2:
            _tg_send(chat_id, "Usage: `/signal AAPL`")
            return
        ticker = parts[1].upper()
        _tg_send(chat_id, f"Analyzing *{ticker}*… (may take ~30s)")
        try:
            p = paths()
            conn = connect(p["db"])
            data_dir = _dated_data_dir(p)
            from fetch_market_data import fetch_ticker_bundle  # noqa: E402

            os.environ.setdefault("STI_DATA_CACHE_DIR", str(p["data"]))
            fetch_ticker_bundle(ticker, data_dir)
            sig = analyze_ticker(ticker, data_dir, conn, p)
            conn.close()
            if not sig:
                _tg_send(chat_id, f"No data for *{ticker}*")
                return
            _tg_send(chat_id, _format_signal(sig))
        except Exception as exc:
            _tg_send(chat_id, f"Error analyzing {ticker}: {exc}")
        return
    _tg_send(chat_id, "Unknown command. Try `/signal AAPL` or `/help`")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        raise HTTPException(403, "Invalid webhook secret")

    body = await request.json()
    msg = body.get("message") or body.get("edited_message")
    if not msg:
        return {"ok": True}
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if chat_id and text:
        _handle_telegram_command(chat_id, text)
    return {"ok": True}


@app.post("/telegram/set-webhook")
def telegram_set_webhook(
    url: str = Query(..., description="Public HTTPS URL ending in /telegram/webhook"),
    x_api_key: str | None = Header(default=None),
):
    """Register Telegram webhook (call once after deploy)."""
    _auth(x_api_key)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(400, "TELEGRAM_BOT_TOKEN not set")

    import requests

    payload: dict = {"url": url}
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        payload["secret_token"] = secret
    r = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json=payload, timeout=15)
    return r.json()
