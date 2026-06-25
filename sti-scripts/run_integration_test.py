#!/usr/bin/env python3
"""STI end-to-end integration test — fetch, analyze, ensemble, report."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
SCRIPTS = PROJECT / "_bmad-output" / "sti" / "scripts"
VENV_PY = PROJECT / "_bmad-output" / "sti" / "venv" / "bin" / "python"
if not VENV_PY.exists():
    VENV_PY = Path(sys.executable)
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DATA_DIR = PROJECT / "_bmad-output" / "sti" / "data" / TODAY
SIGNALS_DIR = PROJECT / "_bmad-output" / "sti" / "signals"
MEM = PROJECT / "_bmad" / "memory" / "sti-shared"
WATCHLIST = MEM / "watchlist.md"


def run(cmd: list[str], timeout: int = 300) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=PROJECT)
    return {"ok": r.returncode == 0, "code": r.returncode, "stdout": r.stdout[-2000:], "stderr": r.stderr[-500:]}


def load_watchlist() -> list[str]:
    tickers = []
    for line in WATCHLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(line.split()[0].upper())
    return tickers


def analyze_technical(ohlcv: dict) -> dict:
    rows = ohlcv.get("rows", [])
    if len(rows) < 20:
        return {"signal": "Hold", "confidence": 50, "rationale": "insufficient data", "indicators": {}}
    closes = [r["close"] for r in rows]
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma20
    last = closes[-1]
    rsi_period = 14
    gains, losses = [], []
    for i in range(-rsi_period, 0):
        d = closes[i] - closes[i - 1]
        (gains if d > 0 else losses).append(abs(d))
    avg_gain = sum(gains) / rsi_period if gains else 0.001
    avg_loss = sum(losses) / rsi_period if losses else 0.001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    signal = "Hold"
    confidence = 55
    if last > sma20 > sma50 and 40 < rsi < 70:
        signal, confidence = "Buy", 68
    elif last < sma20 < sma50 and rsi > 60:
        signal, confidence = "Sell", 65
    elif rsi < 30:
        signal, confidence = "Buy", 62
    elif rsi > 70:
        signal, confidence = "Sell", 60

    return {
        "signal": signal,
        "confidence": confidence,
        "rationale": f"price={last:.2f} sma20={sma20:.2f} sma50={sma50:.2f} rsi={rsi:.1f}",
        "indicators": {"rsi": round(rsi, 1), "sma20": round(sma20, 2), "sma50": round(sma50, 2), "last_close": round(last, 2)},
    }


def analyze_fundamental(fund: dict) -> dict:
    f = fund.get("fundamentals", {})
    pe = f.get("trailingPE")
    roe = f.get("returnOnEquity")
    signal, confidence = "Hold", 55
    if pe and pe < 25 and roe and roe > 0.15:
        signal, confidence = "Buy", 60
    elif pe and pe > 40:
        signal, confidence = "Sell", 58
    return {"signal": signal, "confidence": confidence, "rationale": f"PE={pe} ROE={roe}", "fundamentals": f}


def analyze_sentiment(news: dict) -> dict:
    articles = news.get("articles", [])
    score = 0.5
    if articles:
        pos = sum(1 for a in articles if a.get("headline") and any(w in (a.get("headline") or "").lower() for w in ("beat", "surge", "gain", "upgrade")))
        neg = sum(1 for a in articles if a.get("headline") and any(w in (a.get("headline") or "").lower() for w in ("miss", "fall", "cut", "downgrade")))
        score = 0.5 + (pos - neg) * 0.1
    signal = "Buy" if score > 0.55 else "Sell" if score < 0.45 else "Hold"
    confidence = int(50 + abs(score - 0.5) * 80)
    return {"signal": signal, "confidence": min(confidence, 75), "rationale": f"news_score={score:.2f} articles={len(articles)}", "news_score": round(score, 2)}


def analyze_risk(ohlcv: dict, tech: dict) -> dict:
    rows = ohlcv.get("rows", [])
    if len(rows) < 14:
        return {"signal": "Hold", "confidence": 50, "veto": True, "risk_level": "High"}
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    trs = [highs[i] - lows[i] for i in range(-14, 0)]
    atr = sum(trs) / len(trs)
    last = closes[-1]
    stop = round(last - 2 * atr, 2)
    tp1 = round(last + 2 * atr, 2)
    tp2 = round(last + 4 * atr, 2)
    vol = (max(closes[-20:]) - min(closes[-20:])) / last if len(closes) >= 20 else 0.1
    risk_level = "High" if vol > 0.15 else "Medium" if vol > 0.08 else "Low"
    profile_mult = {"conservative": 2, "moderate": 3.5, "aggressive": 5}.get("moderate", 3.5)
    return {
        "signal": tech.get("signal", "Hold"),
        "confidence": 75 if risk_level == "Low" else 65,
        "veto": risk_level == "High" and tech.get("confidence", 0) < 70,
        "risk_level": risk_level,
        "stop_loss": stop,
        "take_profit_targets": [tp1, tp2],
        "position_size_pct": profile_mult,
    }


def main() -> int:
    results = {"steps": [], "signals": []}
    tickers = load_watchlist()
    print(f"=== STI Integration Test — {TODAY} ===")
    print(f"Watchlist: {tickers}\n")

    # Step 1: Market pulse
    print("[1/4] Fetching market data...")
    fetch = run([
        str(VENV_PY), str(SCRIPTS / "fetch_market_data.py"),
        "--watchlist", str(WATCHLIST), "--skip-cache", "--json",
    ], timeout=600)
    results["steps"].append({"step": "market_pulse", **fetch})
    print(f"  {'OK' if fetch['ok'] else 'FAIL'}: {fetch['stdout'].strip()[-200:]}")

    # Step 2: Per-ticker analysis + ensemble
    print("\n[2/4] Analyzing tickers and generating signals...")
    weights_path = MEM / "methodology-weights.md"
    for ticker in tickers:
        ohlcv_path = DATA_DIR / f"{ticker}_ohlcv.json"
        fund_path = DATA_DIR / f"{ticker}_fundamentals.json"
        news_path = DATA_DIR / f"{ticker}_news.json"
        if not ohlcv_path.is_file():
            print(f"  SKIP {ticker}: no OHLCV data")
            continue

        ohlcv = json.loads(ohlcv_path.read_text())
        fund = json.loads(fund_path.read_text()) if fund_path.is_file() else {}
        news = json.loads(news_path.read_text()) if news_path.is_file() else {}

        tech = analyze_technical(ohlcv)
        fund_a = analyze_fundamental(fund)
        sent = analyze_sentiment(news)
        risk = analyze_risk(ohlcv, tech)

        draft = {
            "ticker": ticker,
            "agent_scores": {
                "technical": {k: v for k, v in tech.items() if k != "indicators"},
                "fundamental": fund_a,
                "sentiment": sent,
                "risk": risk,
            },
            "evidence": {"technical": tech.get("indicators", {}), "fundamental": fund_a.get("fundamentals", {}), "sentiment": {"news_score": sent.get("news_score")}},
            "stop_loss": risk.get("stop_loss"),
            "take_profit_targets": risk.get("take_profit_targets"),
            "position_size_pct": risk.get("position_size_pct"),
        }
        draft_path = SIGNALS_DIR / f"{ticker}-draft.json"
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")

        ens_path = SIGNALS_DIR / f"{ticker}-ensemble.json"
        ens = run([
            str(VENV_PY), str(SCRIPTS / "ensemble_scorer.py"),
            "--input", str(draft_path),
            "--weights", str(weights_path),
            "--min-confidence", "60",
            "--output", str(ens_path),
        ])
        html_path = SIGNALS_DIR / f"{ticker}-{TODAY}.html"
        if ens_path.is_file():
            run([str(VENV_PY), str(SCRIPTS / "report_generator.py"), "--input", str(ens_path), "--output", str(html_path)])
            ensemble = json.loads(ens_path.read_text())
            results["signals"].append(ensemble)
            print(f"  {ticker}: {ensemble.get('recommendation')} @ {ensemble.get('confidence_pct')}% risk={ensemble.get('risk_level')}")

    # Step 3: Backtest sample
    print("\n[3/4] Running backtest on AAPL...")
    bt_path = MEM / "backtests" / f"AAPL-ma-{TODAY}.json"
    bt = run([
        str(VENV_PY), str(SCRIPTS / "backtest_runner.py"),
        "--ticker", "AAPL", "--period", "1y", "--output", str(bt_path),
    ], timeout=180)
    results["steps"].append({"step": "backtest", **bt})
    if bt_path.is_file():
        metrics = json.loads(bt_path.read_text()).get("metrics", {})
        print(f"  OK: win_rate={metrics.get('win_rate')}% sharpe={metrics.get('sharpe_ratio')} max_dd={metrics.get('max_drawdown')}%")

    # Step 4: Summary
    print("\n[4/4] Test summary")
    ranked = sorted(results["signals"], key=lambda x: x.get("confidence_pct", 0), reverse=True)
    print(f"  Signals generated: {len(ranked)}")
    for s in ranked:
        print(f"    {s.get('ticker','?'):5} {s.get('recommendation','?'):12} {s.get('confidence_pct',0):5.1f}%")

    report_path = PROJECT / "skills" / "reports" / f"sti-integration-test-{TODAY}.json"
    report_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\n  Full report: {report_path}")
    print(f"  HTML reports: {SIGNALS_DIR}/")
    print("\n=== Test complete ===")
    return 0 if results["signals"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
