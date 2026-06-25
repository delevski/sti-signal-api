#!/usr/bin/env python3
"""STI backtest runner using vectorbt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_backtest(ticker: str, period: str = "2y", fast: int = 10, slow: int = 30) -> dict[str, Any]:
    import yfinance as yf

    try:
        import vectorbt as vbt
    except ImportError:
        return {"error": "vectorbt not installed", "ticker": ticker}

    data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if data.empty:
        return {"error": "no_data", "ticker": ticker}

    close = data["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    fast_ma = vbt.MA.run(close, fast)
    slow_ma = vbt.MA.run(close, slow)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    pf = vbt.Portfolio.from_signals(close, entries, exits, freq="1D")

    stats = pf.stats()
    metrics = {
        "win_rate": float(stats.get("Win Rate [%]", 0) or 0),
        "avg_return": float(stats.get("Avg Winning Trade [%]", 0) or 0),
        "max_drawdown": float(stats.get("Max Drawdown [%]", 0) or 0),
        "sharpe_ratio": float(stats.get("Sharpe Ratio", 0) or 0),
        "profit_factor": float(stats.get("Profit Factor", 0) or 0),
        "total_return_pct": float(stats.get("Total Return [%]", 0) or 0),
    }
    return {
        "ticker": ticker,
        "period": period,
        "strategy": f"ma_cross_{fast}_{slow}",
        "metrics": metrics,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--period", default="2y")
    p.add_argument("--fast", type=int, default=10)
    p.add_argument("--slow", type=int, default=30)
    p.add_argument("--output")
    args = p.parse_args()
    result = run_backtest(args.ticker.upper(), args.period, args.fast, args.slow)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
