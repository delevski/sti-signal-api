#!/usr/bin/env python3
"""STI v2 production pipeline entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sti.config import load_env
from sti.pipeline import run_pipeline


def main() -> int:
    load_env()
    p = argparse.ArgumentParser(description="STI v2 production pipeline")
    p.add_argument("--screener", action="store_true", help="Scan expanded universe")
    p.add_argument("--limit", type=int, default=20, help="Screener ticker limit")
    p.add_argument("--ticker", action="append", help="Specific tickers")
    p.add_argument("--min-confidence", type=float, default=60.0)
    p.add_argument("--skip-fetch", action="store_true")
    args = p.parse_args()

    result = run_pipeline(
        tickers=args.ticker,
        screener=args.screener,
        screener_limit=args.limit,
        min_confidence=args.min_confidence,
        skip_fetch=args.skip_fetch,
    )
    print(json.dumps({"status": "ok", "count": len(result["signals"]), "report": result["report_path"]}, indent=2))
    for s in result["signals"][:15]:
        print(f"  {s.get('ticker','?'):6} {s.get('recommendation','?'):12} {s.get('confidence_pct',0):5.1f}%  R/R={s.get('risk_reward_ratio','?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
