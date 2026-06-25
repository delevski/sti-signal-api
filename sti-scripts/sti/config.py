"""Paths, env, and configuration."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("STI_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    # skills/shared/sti-scripts/sti/config.py -> project root
    return Path(__file__).resolve().parents[4]


def load_env() -> None:
    env_path = project_root() / ".env.sti"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _serverless_base() -> Path | None:
    """Ephemeral storage on Vercel / AWS Lambda."""
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        base = Path(os.environ.get("STI_SERVERLESS_ROOT", "/tmp/sti"))
        base.mkdir(parents=True, exist_ok=True)
        return base
    return None


def paths() -> dict[str, Path]:
    root = project_root()
    sl = _serverless_base()
    if sl:
        for sub in ("data", "signals", "reports", "memory"):
            (sl / sub).mkdir(parents=True, exist_ok=True)
        return {
            "root": sl,
            "memory": sl / "memory",
            "data": sl / "data",
            "signals": sl / "signals",
            "reports": sl / "reports",
            "db": sl / "predictions.db",
            "watchlist": sl / "memory" / "watchlist.md",
            "weights": sl / "memory" / "methodology-weights.md",
            "predictions_log": sl / "memory" / "predictions-log.jsonl",
            "alerts": sl / "alerts.jsonl",
        }
    return {
        "root": root,
        "memory": root / "_bmad" / "memory" / "sti-shared",
        "data": root / "_bmad-output" / "sti" / "data",
        "signals": root / "_bmad-output" / "sti" / "signals",
        "reports": root / "_bmad-output" / "sti" / "reports",
        "db": root / "_bmad-output" / "sti" / "predictions.db",
        "watchlist": root / "_bmad" / "memory" / "sti-shared" / "watchlist.md",
        "weights": root / "_bmad" / "memory" / "sti-shared" / "methodology-weights.md",
        "predictions_log": root / "_bmad" / "memory" / "sti-shared" / "predictions-log.jsonl",
        "alerts": root / "_bmad-output" / "sti" / "alerts.jsonl",
    }


SIGNAL_ORDER = ["Strong Sell", "Sell", "Hold", "Buy", "Strong Buy"]
SIGNAL_VALUES = {s: i for i, s in enumerate(SIGNAL_ORDER)}
MIN_CONFIDENCE_DEFAULT = float(os.environ.get("STI_MIN_CONFIDENCE", "60"))
