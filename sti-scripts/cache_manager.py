#!/usr/bin/env python3
"""STI cache manager — TTL-aware read/write for market data snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    env = os.environ.get("STI_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def cache_dir() -> Path:
    base = os.environ.get("STI_DATA_CACHE_DIR")
    if base:
        return Path(base.replace("{project-root}", str(_project_root()))).resolve()
    return _project_root() / "_bmad-output" / "sti" / "data"


def dated_dir(date: str | None = None) -> Path:
    d = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = cache_dir() / d
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(name: str, date: str | None = None) -> Path:
    return dated_dir(date) / name


def read_json(name: str, date: str | None = None) -> dict[str, Any] | None:
    path = cache_path(name, date)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, data: dict[str, Any], date: str | None = None) -> Path:
    path = cache_path(name, date)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def is_fresh(name: str, max_age_hours: float = 4.0, date: str | None = None) -> bool:
    path = cache_path(name, date)
    if not path.is_file():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age < max_age_hours * 3600
