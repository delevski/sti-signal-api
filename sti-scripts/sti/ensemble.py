"""Transparent ensemble with validation and calibration."""

from __future__ import annotations

from typing import Any

from sti.config import SIGNAL_ORDER, SIGNAL_VALUES


def signal_to_score(signal: str) -> float:
    return SIGNAL_VALUES.get(signal, 2) / 4.0


def score_to_signal(score: float) -> str:
    idx = max(0, min(4, round(score * 4)))
    return SIGNAL_ORDER[idx]


def validate_agreement(agent_outputs: dict[str, dict]) -> dict[str, Any]:
    """Signal validation layer — detect conflict."""
    signals = {a: o.get("signal", "Hold") for a, o in agent_outputs.items() if a != "suppressed"}
    buy_votes = sum(1 for s in signals.values() if s in ("Buy", "Strong Buy"))
    sell_votes = sum(1 for s in signals.values() if s in ("Sell", "Strong Sell"))
    hold_votes = sum(1 for s in signals.values() if s == "Hold")

    conflict = buy_votes > 0 and sell_votes > 0
    agreement_ratio = max(buy_votes, sell_votes, hold_votes) / max(len(signals), 1)

    penalty = 0.0
    if conflict:
        penalty = 0.15
    elif agreement_ratio < 0.5:
        penalty = 0.08

    return {
        "conflict": conflict,
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "hold_votes": hold_votes,
        "agreement_ratio": round(agreement_ratio, 2),
        "confidence_penalty": penalty,
        "validated": not conflict or agreement_ratio >= 0.5,
    }


def calibrate_confidence(raw_confidence: float, historical_hit_rate: float | None) -> dict[str, Any]:
    """Blend raw score with historical success rate."""
    if historical_hit_rate is None:
        hit = 0.5
    else:
        hit = historical_hit_rate
    calibrated = raw_confidence * 0.6 + hit * 100 * 0.4
    spread = 8 + (1 - hit) * 12  # wider interval when less certain
    return {
        "confidence_pct": round(calibrated, 1),
        "confidence_interval_low": round(max(0, calibrated - spread), 1),
        "confidence_interval_high": round(min(100, calibrated + spread), 1),
        "uncertainty": "high" if spread > 15 else "medium" if spread > 10 else "low",
        "historical_hit_rate": round(hit * 100, 1) if hit else None,
    }


def aggregate(
    agent_outputs: dict[str, dict[str, Any]],
    weights: dict[str, float],
    min_confidence: float = 60.0,
    historical_hit_rate: float | None = None,
) -> dict[str, Any]:
    validation = validate_agreement(agent_outputs)
    risk = agent_outputs.get("risk", {})
    veto = bool(risk.get("veto", False))

    # Transparent formula: ensemble_score = Σ(weight_i × signal_score_i × agent_confidence_i)
    breakdown: list[dict[str, Any]] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for agent, w in weights.items():
        data = agent_outputs.get(agent, {})
        sig = data.get("signal", "Hold")
        conf = float(data.get("confidence", 50)) / 100.0
        agent_score = signal_to_score(sig)
        contribution = w * agent_score * conf
        weighted_sum += contribution
        weight_total += w * conf
        breakdown.append({
            "agent": agent,
            "signal": sig,
            "agent_confidence_pct": round(conf * 100, 1),
            "weight": w,
            "signal_score": round(agent_score, 3),
            "contribution": round(contribution, 4),
            "formula_term": f"{w:.3f} × {agent_score:.3f} × {conf:.2f}",
        })

    ensemble_score = weighted_sum / max(weight_total, 0.01)
    base_signal = score_to_signal(ensemble_score)
    raw_confidence = 50 + abs(ensemble_score - 0.5) * 100
    raw_confidence -= validation["confidence_penalty"] * 100

    cal = calibrate_confidence(raw_confidence, historical_hit_rate)
    confidence_pct = cal["confidence_pct"]

    if veto:
        base_signal = "Hold"
        confidence_pct = min(confidence_pct, 55)

    recommendation = base_signal
    if confidence_pct >= 75 and base_signal == "Buy":
        recommendation = "Strong Buy"
    elif confidence_pct >= 75 and base_signal == "Sell":
        recommendation = "Strong Sell"

    suppressed = False
    if confidence_pct < min_confidence and recommendation not in ("Hold",):
        recommendation = "Hold"
        suppressed = True

    formula_plain = (
        f"ensemble_score = Σ(weight × signal_score × confidence) = {ensemble_score:.4f} → {base_signal}. "
        f"After calibration: {confidence_pct}% confidence."
    )

    return {
        "recommendation": recommendation,
        "raw_recommendation": base_signal,
        "confidence_pct": confidence_pct,
        "confidence_calibration": cal,
        "ensemble_score": round(ensemble_score, 4),
        "validation": validation,
        "veto_applied": veto,
        "suppressed": suppressed,
        "agent_scores": {b["agent"]: {k: b[k] for k in ("signal", "agent_confidence_pct", "weight", "contribution")} for b in breakdown},
        "score_breakdown": breakdown,
        "methodology_weights": weights,
        "formula": {
            "expression": "Σ(weight_i × signal_score_i × confidence_i) / Σ(weight_i × confidence_i)",
            "signal_scores": "Strong Sell=0, Sell=0.25, Hold=0.5, Buy=0.75, Strong Buy=1.0",
            "ensemble_score": round(ensemble_score, 4),
            "plain_english": formula_plain,
        },
        "disclaimer": "Probabilistic prediction, not financial advice.",
    }
