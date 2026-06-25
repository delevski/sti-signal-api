#!/usr/bin/env bash
set -euo pipefail
DEST="$(cd "$(dirname "$0")" && pwd)/sti-scripts"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/skills/shared/sti-scripts"

if [ ! -d "$SRC" ]; then
  if [ -d "$DEST/sti" ]; then
    echo "Using committed sti-scripts bundle"
    exit 0
  fi
  echo "ERROR: no skills/shared/sti-scripts and no bundled sti-scripts" >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$DEST"
rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='api/' \
  --exclude='backtest_runner.py' \
  --exclude='run_integration_test.py' \
  --exclude='setup_infrastructure.py' \
  --exclude='ensemble_scorer.py' \
  --exclude='report_generator.py' \
  --exclude='sync_output.py' \
  --exclude='sti/dashboard.py' \
  "$SRC/" "$DEST/"
mkdir -p "$DEST/api"
cp "$SRC/api/main.py" "$DEST/api/main.py"
echo "Bundled STI scripts to $DEST"
