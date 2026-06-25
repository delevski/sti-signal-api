"""Main STI pipeline — analyze tickers end-to-end."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure sti-scripts on path
_SCRIPT_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from cache_manager import read_json, write_json  # noqa: E402

from sti.alerts import check_signal_alerts
from sti.config import load_env, paths
from sti.db import adaptive_weights, connect, get_agent_stats, log_prediction, signal_history
from sti.ensemble import aggregate
from sti.explain import build as build_explain
from sti.fundamental import analyze as analyze_fundamental
from sti.quality import block_if_critical, check as quality_check
from sti.reports import render
from sti.risk import analyze as analyze_risk
from sti.screener import load_universe, rank_opportunities
from sti.sentiment import analyze as analyze_sentiment
from sti.technical import analyze as analyze_technical


def _load_weights_file(weights_path: Path) -> dict[str, float]:
    default = {"technical": 0.30, "fundamental": 0.25, "sentiment": 0.20, "risk": 0.25}
    if weights_path.is_file():
        for line in weights_path.read_text(encoding="utf-8").splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                k = k.strip().lstrip("-").strip()
                try:
                    default[k] = float(v.strip())
                except ValueError:
                    pass
    total = sum(default.values()) or 1
    return {k: v / total for k, v in default.items()}


def _dated_data_dir(p: dict[str, Path]) -> Path:
    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = p["data"] / d
    path.mkdir(parents=True, exist_ok=True)
    return path


def analyze_ticker(
    ticker: str,
    data_dir: Path,
    conn,
    p: dict[str, Path],
    min_confidence: float = 60.0,
    profile: str = "moderate",
) -> dict[str, Any] | None:
    ohlcv = read_json(f"{ticker}_ohlcv.json", data_dir.name) or {}
    if not ohlcv.get("rows"):
        ohlcv_path = data_dir / f"{ticker}_ohlcv.json"
        if ohlcv_path.is_file():
            ohlcv = json.loads(ohlcv_path.read_text(encoding="utf-8"))
    if not ohlcv.get("rows"):
        return None

    fund_path = data_dir / f"{ticker}_fundamentals.json"
    news_path = data_dir / f"{ticker}_news.json"
    fund = json.loads(fund_path.read_text()) if fund_path.is_file() else {}
    news = json.loads(news_path.read_text()) if news_path.is_file() else {}

    technical = analyze_technical(ohlcv["rows"])
    fundamental = analyze_fundamental(fund.get("fundamentals", {}), fund.get("info", ohlcv.get("info", {})))
    sentiment = analyze_sentiment(news)

    # Preliminary direction for risk
    prelim_scores = {"technical": technical, "fundamental": fundamental, "sentiment": sentiment}
    base_weights = _load_weights_file(p["weights"])
    weights = adaptive_weights(conn, base_weights)

    prelim = aggregate(
        {**prelim_scores, "risk": {"signal": "Hold", "confidence": 50}},
        weights,
        min_confidence=0,
    )
    risk = analyze_risk(technical, prelim.get("raw_recommendation", "Hold"), profile)

    agent_outputs = {
        "technical": technical,
        "fundamental": fundamental,
        "sentiment": sentiment,
        "risk": risk,
    }

    stats = get_agent_stats(conn)
    avg_hit = sum(s.get("win_rate", 0.5) for s in stats.values()) / max(len(stats), 1)

    ensemble = aggregate(agent_outputs, weights, min_confidence, historical_hit_rate=avg_hit)

    issues = quality_check(technical, risk, ensemble)
    if block_if_critical(issues):
        ensemble["recommendation"] = "Hold"
        ensemble["blocked"] = True

    macro_path = data_dir / "macro.json"
    macro = json.loads(macro_path.read_text()) if macro_path.is_file() else {}

    explain = build_explain(ticker, technical, fundamental, sentiment, risk, ensemble, macro)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signal: dict[str, Any] = {
        "ticker": ticker,
        "date": today,
        **ensemble,
        "risk_level": risk.get("risk_level"),
        "stop_loss": risk.get("stop_loss"),
        "take_profit_targets": risk.get("take_profit_targets"),
        "risk_reward_ratio": risk.get("risk_reward_ratio"),
        "position_size_pct": risk.get("position_size_pct"),
        "max_capital_allocation_pct": risk.get("max_capital_allocation_pct"),
        "technical": technical,
        "fundamental": fundamental,
        "sentiment": sentiment,
        "risk": risk,
        "evidence": {
            "technical": technical.get("indicators"),
            "fundamental": fundamental.get("metrics"),
            "sentiment": {"news_score": sentiment.get("news_score"), "catalysts": sentiment.get("catalysts")},
            "macro": macro.get("series"),
        },
        "explainability": explain,
        "quality_issues": issues,
        "agent_performance": stats,
    }

    # Persist
    p["signals"].mkdir(parents=True, exist_ok=True)
    json_path = p["signals"] / f"{ticker}-ensemble.json"
    json_path.write_text(json.dumps(signal, indent=2, default=str), encoding="utf-8")

    hist = signal_history(conn, ticker)
    html_path = p["signals"] / f"{ticker}-{today}.html"
    html_path.write_text(render(signal, ohlcv.get("rows"), hist), encoding="utf-8")

    log_prediction(conn, signal)

    # Append predictions log
    with open(p["predictions_log"], "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ticker": ticker, "date": today,
            "recommendation": signal["recommendation"],
            "confidence_pct": signal["confidence_pct"],
            "ensemble_score": signal.get("ensemble_score"),
        }) + "\n")

    alerts_path = str(p["alerts"])
    prev = hist[1] if len(hist) > 1 else None
    check_signal_alerts(conn, prev, signal, alerts_path)

    return signal


def run_pipeline(
    tickers: list[str] | None = None,
    screener: bool = False,
    screener_limit: int = 20,
    min_confidence: float = 60.0,
    skip_fetch: bool = False,
) -> dict[str, Any]:
    load_env()
    p = paths()
    conn = connect(p["db"])
    data_dir = _dated_data_dir(p)

    if not skip_fetch:
        import subprocess
        py = p["root"] / "_bmad-output" / "sti" / "venv" / "bin" / "python"
        if not py.exists():
            py = Path(sys.executable)
        fetch_script = p["root"] / "_bmad-output" / "sti" / "scripts" / "fetch_market_data.py"
        if not fetch_script.exists():
            fetch_script = _SCRIPT_ROOT / "fetch_market_data.py"
        universe = load_universe() if screener else None
        target = universe if screener else tickers
        if target is None:
            target = []
            for line in p["watchlist"].read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    target.append(line.split()[0].upper())

        for t in target:
            subprocess.run([str(py), str(fetch_script), "--ticker", t, "--skip-cache"], cwd=str(p["root"]), timeout=120)

    if screener:
        tickers = load_universe()[:screener_limit]
    elif tickers is None:
        tickers = []
        for line in p["watchlist"].read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                tickers.append(line.split()[0].upper())

    signals = []
    for t in tickers:
        sig = analyze_ticker(t, data_dir, conn, p, min_confidence)
        if sig:
            signals.append(sig)

    ranked = rank_opportunities(signals)
    report = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "count": len(signals),
        "signals": [{k: s.get(k) for k in ("ticker", "recommendation", "confidence_pct", "risk_reward_ratio", "opportunity_score")} for s in ranked],
    }
    out = p["reports"] / f"scan-{report['date']}.json"
    p["reports"].mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    from sti.dashboard import write_dashboard
    macro_p = data_dir / "macro.json"
    write_dashboard(p["reports"], out, macro_p if macro_p.is_file() else None)

    conn.close()
    return {"signals": ranked, "report_path": str(out)}
