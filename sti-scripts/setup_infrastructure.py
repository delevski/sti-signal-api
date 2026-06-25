#!/usr/bin/env python3
"""STI setup infrastructure — venv, memory folders, env template."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


WATCHLIST_SEED = """# STI Watchlist — one ticker per line
AAPL
MSFT
NVDA
JPM
XOM
"""

INDEX_SEED = """# STI Shared Memory Index

Last updated: (setup)

## Curated Files
- watchlist.md — active tickers
- methodology-weights.md — ensemble weights
- predictions-log.jsonl — prediction history
- performance/metrics.json — aggregate metrics

## Recent Activity
- Module installed
"""

WEIGHTS_SEED = """# Methodology weights
technical: 0.30
fundamental: 0.25
sentiment: 0.20
risk: 0.25
"""

ENV_TEMPLATE = """# STI API keys (all optional — degraded mode without them)
STI_ALPHA_VANTAGE_KEY=
STI_FINNHUB_KEY=
STI_FRED_KEY=
STI_PROJECT_ROOT={project_root}
STI_DATA_CACHE_DIR={project_root}/_bmad-output/sti/data
STI_WATCHLIST_PATH={project_root}/_bmad/memory/sti-shared/watchlist.md
"""


def scaffold(project_root: Path, venv: bool = True) -> dict:
    root = project_root.resolve()
    created = []

    dirs = [
        root / "_bmad/memory/sti-shared/daily",
        root / "_bmad/memory/sti-shared/signals",
        root / "_bmad/memory/sti-shared/performance",
        root / "_bmad/memory/sti-shared/backtests",
        root / "_bmad-output/sti/data",
        root / "_bmad-output/sti/signals",
        root / "_bmad-output/sti/reports",
        root / "_bmad-output/sti/scripts",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        created.append(str(d))

    mem = root / "_bmad/memory/sti-shared"
    files = {
        mem / "watchlist.md": WATCHLIST_SEED,
        mem / "index.md": INDEX_SEED,
        mem / "methodology-weights.md": WEIGHTS_SEED,
        mem / "predictions-log.jsonl": "",
        mem / "performance/metrics.json": json.dumps({"win_rate": 0, "count": 0}, indent=2),
        root / ".env.sti": ENV_TEMPLATE.format(project_root=root),
        root / "_bmad-output/sti/reports/dashboard.html": "<!DOCTYPE html><html><body><h1>STI Dashboard</h1><p>Signal reports appear in _bmad-output/sti/signals/</p></body></html>",
    }
    for path, content in files.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(str(path))

    scripts_src = Path(__file__).resolve().parent
    scripts_dst = root / "_bmad-output/sti/scripts"
    for name in (
        "cache_manager.py", "fetch_market_data.py", "ensemble_scorer.py",
        "report_generator.py", "backtest_runner.py", "performance_tracker.py",
        "requirements.txt",
    ):
        src = scripts_src / name
        if src.is_file():
            dst = scripts_dst / name
            if not dst.exists() or src.read_bytes() != dst.read_bytes():
                dst.write_bytes(src.read_bytes())
                created.append(str(dst))

    venv_path = root / "_bmad-output/sti/venv"
    if venv and not (venv_path / "bin/python").exists() and not (venv_path / "Scripts/python.exe").exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=False)
        pip = venv_path / "bin" / "pip"
        if not pip.exists():
            pip = venv_path / "Scripts" / "pip.exe"
        req = scripts_dst / "requirements.txt"
        if pip.exists() and req.is_file():
            subprocess.run([str(pip), "install", "-q", "-r", str(req)], check=False)
        created.append(str(venv_path))

    return {"status": "ok", "created": created}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=".")
    p.add_argument("--no-venv", action="store_true")
    args = p.parse_args()
    result = scaffold(Path(args.project_root), venv=not args.no_venv)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
