"""Market screener — discover opportunities beyond watchlist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# S&P 100 subset for production scanning (expand via sp500.txt)
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY", "AVGO", "JPM",
    "XOM", "UNH", "V", "MA", "PG", "JNJ", "HD", "COST", "ABBV", "MRK",
    "CVX", "PEP", "KO", "WMT", "BAC", "CRM", "AMD", "TMO", "CSCO", "ACN",
    "LIN", "MCD", "ABT", "DHR", "TXN", "NEE", "PM", "INTC", "QCOM", "UNP",
    "RTX", "HON", "LOW", "UPS", "AMAT", "IBM", "CAT", "GE", "SPGI", "INTU",
]


def load_universe(path: Path | None = None) -> list[str]:
    if path and path.is_file():
        tickers = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().upper()
            if line and not line.startswith("#"):
                tickers.append(line.split()[0])
        if tickers:
            return tickers
    custom = Path(__file__).resolve().parent / "data" / "sp500_sample.txt"
    if custom.is_file():
        return [l.strip().upper() for l in custom.read_text().splitlines() if l.strip()]
    return DEFAULT_UNIVERSE


def rank_opportunities(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank by risk/reward × confidence."""
    ranked = []
    for s in signals:
        if s.get("recommendation") == "Hold" and s.get("suppressed"):
            continue
        rr = s.get("risk_reward_ratio") or s.get("risk", {}).get("risk_reward_ratio") or 1.0
        conf = s.get("confidence_pct", 0) / 100.0
        score = rr * conf
        ranked.append({**s, "opportunity_score": round(score, 3)})
    ranked.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    return ranked
