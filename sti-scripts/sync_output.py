#!/usr/bin/env python3
"""Sync sti-scripts to _bmad-output/sti/scripts."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[3]
src = root / "skills" / "shared" / "sti-scripts"
dst = root / "_bmad-output" / "sti" / "scripts"
dst.mkdir(parents=True, exist_ok=True)
for item in src.iterdir():
    if item.name == "__pycache__":
        continue
    target = dst / item.name
    if item.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(item, target)
    else:
        shutil.copy2(item, target)
print(f"Synced {src} -> {dst}")
