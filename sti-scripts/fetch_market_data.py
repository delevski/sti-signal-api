#!/usr/bin/env python3
"""Fetch multi-source US equity market data for STI module."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cache_manager import is_fresh, read_json, write_json  # noqa: E402


def _load_env() -> None:
    env_path = Path(os.environ.get("STI_PROJECT_ROOT", Path.cwd())) / ".env.sti"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _yf():
    import yfinance as yf  # lazy import

    return yf


def fetch_ohlcv(ticker: str, period: str = "6mo") -> dict[str, Any]:
    yf = _yf()
    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=True)
    if hist.empty:
        return {"ticker": ticker, "error": "no_data", "rows": []}
    rows = []
    for idx, row in hist.iterrows():
        rows.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
    info = {}
    try:
        info = {k: t.info.get(k) for k in ("shortName", "sector", "industry", "marketCap", "beta")}
    except Exception:
        pass
    return {"ticker": ticker, "period": period, "rows": rows, "info": info, "fetched_at": _now()}


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    yf = _yf()
    t = yf.Ticker(ticker)
    info = t.info or {}
    keys = (
        "trailingPE", "forwardPE", "priceToBook", "profitMargins",
        "revenueGrowth", "earningsGrowth", "debtToEquity", "returnOnEquity",
        "freeCashflow", "dividendYield", "earningsQuarterlyGrowth",
    )
    fundamentals = {k: info.get(k) for k in keys if k in info}
    cal = []
    try:
        cal_df = t.calendar
        if cal_df is not None and not getattr(cal_df, "empty", True):
            cal = cal_df.to_dict()
    except Exception:
        pass
    return {"ticker": ticker, "fundamentals": fundamentals, "calendar": cal, "fetched_at": _now()}


def fetch_news_finnhub(ticker: str, limit: int = 10) -> list[dict[str, Any]]:
    key = os.environ.get("STI_FINNHUB_KEY", "")
    if not key:
        return []
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = datetime.now(timezone.utc).replace(day=1).strftime("%Y-%m-%d")
    url = "https://finnhub.io/api/v1/company-news"
    r = requests.get(url, params={"symbol": ticker, "from": start, "to": end, "token": key}, timeout=15)
    r.raise_for_status()
    items = r.json()[:limit]
    return [{"headline": i.get("headline"), "source": i.get("source"), "datetime": i.get("datetime"), "summary": i.get("summary", "")[:300]} for i in items]


def fetch_news_yfinance(ticker: str, limit: int = 10) -> list[dict[str, Any]]:
    yf = _yf()
    t = yf.Ticker(ticker)
    news = []
    try:
        for item in (t.news or [])[:limit]:
            news.append({"headline": item.get("title"), "source": item.get("publisher"), "link": item.get("link")})
    except Exception:
        pass
    return news


def fetch_news(ticker: str) -> dict[str, Any]:
    news = fetch_news_finnhub(ticker)
    source = "finnhub"
    if not news:
        news = fetch_news_yfinance(ticker)
        source = "yfinance"
    return {"ticker": ticker, "source": source, "articles": news, "fetched_at": _now()}


def fetch_macro() -> dict[str, Any]:
    key = os.environ.get("STI_FRED_KEY", "")
    series = {"DFF": "fed_funds_rate", "CPIAUCSL": "cpi", "VIXCLS": "vix"}
    macro: dict[str, Any] = {"series": {}, "fetched_at": _now()}
    if not key:
        macro["note"] = "STI_FRED_KEY not set; macro section limited"
        return macro
    for sid, label in series.items():
        url = f"https://api.stlouisfed.org/fred/series/observations"
        r = requests.get(
            url,
            params={"series_id": sid, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 1},
            timeout=15,
        )
        if r.ok:
            obs = r.json().get("observations", [])
            if obs:
                macro["series"][label] = {"value": obs[0].get("value"), "date": obs[0].get("date")}
        time.sleep(0.2)
    return macro


def fetch_market_context(tickers: list[str]) -> dict[str, Any]:
    yf = _yf()
    benchmarks = {"SPY": "sp500", "QQQ": "nasdaq", "IWM": "russell2000"}
    ctx: dict[str, Any] = {"benchmarks": {}, "sectors": {}, "fetched_at": _now()}
    for sym, label in benchmarks.items():
        hist = yf.Ticker(sym).history(period="1mo")
        if not hist.empty:
            ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
            ctx["benchmarks"][label] = {"symbol": sym, "return_1m_pct": round(float(ret), 2)}
    sectors = set()
    for t in tickers:
        try:
            sec = yf.Ticker(t).info.get("sector")
            if sec:
                sectors.add(sec)
        except Exception:
            pass
    sector_map = {
        "Technology": "XLK", "Financial Services": "XLF", "Energy": "XLE",
        "Healthcare": "XLV", "Consumer Cyclical": "XLY",
    }
    for sec in sectors:
        etf = sector_map.get(sec)
        if etf:
            hist = yf.Ticker(etf).history(period="1mo")
            if not hist.empty:
                ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                ctx["sectors"][sec] = {"etf": etf, "return_1m_pct": round(float(ret), 2)}
    return ctx


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_ticker_bundle(ticker: str, data_dir: Path, period: str = "6mo") -> dict[str, Any]:
    """Fetch OHLCV, fundamentals, and news for one ticker into data_dir."""
    ticker = ticker.upper()
    data_dir.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {}
    for kind, fname, fn in (
        ("ohlcv", f"{ticker}_ohlcv.json", lambda: fetch_ohlcv(ticker, period)),
        ("fundamentals", f"{ticker}_fundamentals.json", lambda: fetch_fundamentals(ticker)),
        ("news", f"{ticker}_news.json", lambda: fetch_news(ticker)),
    ):
        data = fn()
        bundle[kind] = data
        (data_dir / fname).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        time.sleep(0.2)
    return bundle


def load_watchlist(path: Path) -> list[str]:
    if not path.is_file():
        return ["AAPL", "MSFT", "NVDA", "JPM", "XOM"]
    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sym = line.split()[0].upper()
        if sym.isalpha() and 1 <= len(sym) <= 5:
            tickers.append(sym)
    return tickers or ["AAPL"]


def main() -> int:
    _load_env()
    p = argparse.ArgumentParser(description="STI market data fetcher")
    p.add_argument("--ticker", action="append", help="Ticker symbol (repeatable)")
    p.add_argument("--watchlist", help="Path to watchlist.md")
    p.add_argument("--period", default="6mo")
    p.add_argument("--skip-cache", action="store_true")
    p.add_argument("--macro-only", action="store_true")
    p.add_argument("--json", action="store_true", help="Print summary JSON to stdout")
    args = p.parse_args()

    tickers = [t.upper() for t in (args.ticker or [])]
    if args.watchlist:
        tickers.extend(load_watchlist(Path(args.watchlist)))
    tickers = list(dict.fromkeys(tickers))

    results: dict[str, Any] = {"tickers": {}, "macro": None, "market_context": None}

    if args.macro_only:
        name = "macro.json"
        if not args.skip_cache and is_fresh(name):
            data = read_json(name)
        else:
            data = fetch_macro()
            write_json(name, data)
        print(json.dumps(data, indent=2))
        return 0

    if not tickers and args.watchlist is None:
        wl = Path(os.environ.get("STI_WATCHLIST_PATH", Path.cwd() / "_bmad/memory/sti-shared/watchlist.md"))
        tickers = load_watchlist(wl)

    for ticker in tickers:
        bundle: dict[str, Any] = {}
        for kind, fname, fn in (
            ("ohlcv", f"{ticker}_ohlcv.json", lambda t=ticker: fetch_ohlcv(t, args.period)),
            ("fundamentals", f"{ticker}_fundamentals.json", lambda t=ticker: fetch_fundamentals(t)),
            ("news", f"{ticker}_news.json", lambda t=ticker: fetch_news(t)),
        ):
            if not args.skip_cache and is_fresh(fname):
                bundle[kind] = read_json(fname)
            else:
                bundle[kind] = fn()
                write_json(fname, bundle[kind])
            time.sleep(0.3)
        results["tickers"][ticker] = bundle

    if not is_fresh("macro.json") or args.skip_cache:
        results["macro"] = fetch_macro()
        write_json("macro.json", results["macro"])
    else:
        results["macro"] = read_json("macro.json")

    if tickers:
        if not is_fresh("market_context.json") or args.skip_cache:
            results["market_context"] = fetch_market_context(tickers)
            write_json("market_context.json", results["market_context"])
        else:
            results["market_context"] = read_json("market_context.json")

    if args.json:
        print(json.dumps({"status": "ok", "ticker_count": len(tickers), "tickers": list(results["tickers"].keys())}, indent=2))
    else:
        print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
