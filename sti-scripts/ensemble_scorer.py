#!/usr/bin/env python3
"""STI ensemble signal scorer — weighted aggregation with risk veto."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SIGNAL_ORDER = ["Strong Sell", "Sell", "Hold", "Buy", "Strong Buy"]
SIGNAL_VALUES = {s: i for i, s in enumerate(SIGNAL_ORDER)}


def _load_weights(path: Path | None) -> dict[str, float]:
    default = {"technical": 0.30, "fundamental": 0.25, "sentiment": 0.20, "risk": 0.25}
    if path and path.is_file():
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                k = k.strip().lstrip("-").strip()
                try:
                    default[k] = float(v.strip())
                except ValueError:
                    pass
    total = sum(default.values()) or 1.0
    return {k: v / total for k, v in default.items()}


def signal_to_score(signal: str) -> float:
    return SIGNAL_VALUES.get(signal, 2) / 4.0


def score_to_signal(score: float) -> str:
    idx = max(0, min(4, round(score * 4)))
    return SIGNAL_ORDER[idx]


def strong_label(signal: str, confidence: float) -> str:
    if confidence >= 75 and signal == "Buy":
        return "Strong Buy"
    if confidence >= 75 and signal == "Sell":
        return "Strong Sell"
    return signal


def aggregate(agent_scores: dict[str, dict[str, Any]], weights: dict[str, float], min_confidence: float = 60.0) -> dict[str, Any]:
    weighted = 0.0
    conf_sum = 0.0
    details: dict[str, Any] = {}
    risk = agent_scores.get("risk", {})
    veto = bool(risk.get("veto", False))

    for agent, w in weights.items():
        data = agent_scores.get(agent, {})
        sig = data.get("signal", "Hold")
        conf = float(data.get("confidence", 50))
        weighted += signal_to_score(sig) * w * (conf / 100.0)
        conf_sum += conf * w
        details[agent] = {"signal": sig, "confidence": conf, "weight": w}

    ensemble_score = weighted
    base_signal = score_to_signal(ensemble_score)
    confidence_pct = round(conf_sum, 1)

    risk_level = risk.get("risk_level", "Medium")
    if veto or (risk_level == "High" and confidence_pct < 70):
        base_signal = "Hold"
        confidence_pct = min(confidence_pct, 55)

    recommendation = strong_label(base_signal, confidence_pct)
    if confidence_pct < min_confidence:
        recommendation = "Hold"
        details["suppressed"] = f"below min confidence {min_confidence}"

    return {
        "recommendation": recommendation,
        "confidence_pct": confidence_pct,
        "risk_level": risk_level,
        "agent_scores": details,
        "methodology_weights": weights,
        "veto_applied": veto,
        "disclaimer": "Probabilistic prediction, not financial advice.",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="JSON file with agent_scores")
    p.add_argument("--weights", help="methodology-weights.md path")
    p.add_argument("--min-confidence", type=float, default=60.0)
    p.add_argument("--output", help="Write result JSON")
    args = p.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    weights = _load_weights(Path(args.weights) if args.weights else None)
    result = aggregate(data.get("agent_scores", data), weights, args.min_confidence)
    result.update({k: data[k] for k in ("ticker", "stop_loss", "take_profit_targets", "position_size_pct", "evidence") if k in data})

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
