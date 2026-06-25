#!/usr/bin/env python3
"""STI performance tracker — score predictions vs actuals, update weights."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_predictions(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def score_prediction(pred: dict, actual_return_pct: float) -> dict[str, Any]:
    rec = pred.get("recommendation", "Hold")
    correct = False
    if rec in ("Buy", "Strong Buy") and actual_return_pct > 0:
        correct = True
    elif rec in ("Sell", "Strong Sell") and actual_return_pct < 0:
        correct = True
    elif rec == "Hold" and abs(actual_return_pct) < 2:
        correct = True
    return {"correct": correct, "actual_return_pct": actual_return_pct, "recommendation": rec}


def compute_metrics(scored: list[dict]) -> dict[str, Any]:
    if not scored:
        return {"win_rate": 0, "count": 0}
    wins = sum(1 for s in scored if s.get("correct"))
    returns = [s.get("actual_return_pct", 0) for s in scored]
    avg_ret = sum(returns) / len(returns) if returns else 0
    return {
        "win_rate": round(wins / len(scored) * 100, 2),
        "count": len(scored),
        "avg_return_pct": round(avg_ret, 2),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def update_weights(metrics_by_agent: dict[str, dict], weights_path: Path) -> None:
  """Simple weight nudge based on per-agent accuracy."""
  lines = ["# Methodology weights (auto-updated by sti-workflow-learn)\n"]
  total = 0.0
  raw = {}
  for agent, m in metrics_by_agent.items():
      acc = m.get("accuracy", 0.5)
      raw[agent] = max(0.1, acc)
      total += raw[agent]
  for agent, v in raw.items():
      lines.append(f"{agent}: {round(v / total, 3)}")
  weights_path.parent.mkdir(parents=True, exist_ok=True)
  weights_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True, help="predictions-log.jsonl")
    p.add_argument("--returns", required=True, help="JSON map ticker->return_pct")
    p.add_argument("--metrics-output")
    p.add_argument("--weights-output")
    args = p.parse_args()

    preds = load_predictions(Path(args.predictions))
    returns = json.loads(Path(args.returns).read_text(encoding="utf-8"))
    scored = []
    for pred in preds:
        ticker = pred.get("ticker")
        if ticker in returns:
            s = score_prediction(pred, float(returns[ticker]))
            s["ticker"] = ticker
            scored.append(s)

    metrics = compute_metrics(scored)
    if args.metrics_output:
        Path(args.metrics_output).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if args.weights_output:
        agent_acc = {a: {"accuracy": 0.5} for a in ("technical", "fundamental", "sentiment", "risk")}
        update_weights(agent_acc, Path(args.weights_output))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
