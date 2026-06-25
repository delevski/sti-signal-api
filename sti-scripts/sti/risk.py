"""Risk management — ATR stops, position sizing, R/R."""

from __future__ import annotations

from typing import Any


RISK_PROFILE = {
    "conservative": {"max_position_pct": 2.0, "max_portfolio_pct": 15.0, "atr_mult_stop": 2.5},
    "moderate": {"max_position_pct": 3.5, "max_portfolio_pct": 25.0, "atr_mult_stop": 2.0},
    "aggressive": {"max_position_pct": 5.0, "max_portfolio_pct": 40.0, "atr_mult_stop": 1.5},
}


def analyze(
    technical: dict,
    ensemble_direction: str = "Hold",
    profile: str = "moderate",
    portfolio_exposure_pct: float = 0.0,
) -> dict[str, Any]:
    ind = technical.get("indicators", {})
    last = ind.get("last_close", 0)
    atr = ind.get("atr", last * 0.02 if last else 1)
    support = ind.get("support", last - 2 * atr if last else 0)
    resistance = ind.get("resistance", last + 2 * atr if last else 0)
    atr_pct = ind.get("atr_pct", 2.0)

    cfg = RISK_PROFILE.get(profile, RISK_PROFILE["moderate"])
    mult = cfg["atr_mult_stop"]

    if ensemble_direction in ("Buy", "Strong Buy"):
        stop = round(max(support, last - mult * atr), 2)
        tp1 = round(last + 2 * atr, 2)
        tp2 = round(min(resistance, last + 4 * atr), 2)
    elif ensemble_direction in ("Sell", "Strong Sell"):
        stop = round(min(resistance, last + mult * atr), 2)
        tp1 = round(last - 2 * atr, 2)
        tp2 = round(last - 4 * atr, 2)
    else:
        stop = round(last - mult * atr, 2)
        tp1 = round(last + 1.5 * atr, 2)
        tp2 = round(last + 3 * atr, 2)

    risk_per_share = abs(last - stop) if last else atr
    reward_per_share = abs(tp1 - last) if last else atr
    rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else 0

    risk_level = "Low" if atr_pct < 2 else "Medium" if atr_pct < 4 else "High"

    # Position size — Kelly-inspired cap
    edge = technical.get("score", 0.5) - 0.5
    kelly_pct = max(0, min(cfg["max_position_pct"], abs(edge) * 20))
    position_pct = round(min(kelly_pct, cfg["max_position_pct"]), 2)

    remaining = cfg["max_portfolio_pct"] - portfolio_exposure_pct
    if position_pct > remaining:
        position_pct = round(max(0, remaining), 2)

    veto = False
    veto_reason = ""
    if risk_level == "High" and ensemble_direction in ("Buy", "Strong Buy") and technical.get("confidence", 0) < 65:
        veto = True
        veto_reason = "High volatility with insufficient technical confidence for long entry"
    if rr_ratio < 1.0 and ensemble_direction in ("Buy", "Sell", "Strong Buy", "Strong Sell"):
        veto = True
        veto_reason = veto_reason or f"Risk/reward ratio {rr_ratio} below 1.0"

    risk_score = 0.5
    if risk_level == "Low":
        risk_score = 0.6
    elif risk_level == "High":
        risk_score = 0.35

    if ensemble_direction in ("Buy", "Strong Buy"):
        risk_signal = "Buy" if not veto else "Hold"
    elif ensemble_direction in ("Sell", "Strong Sell"):
        risk_signal = "Sell" if not veto else "Hold"
    else:
        risk_signal = "Hold"

    return {
        "signal": risk_signal,
        "confidence": 75 if risk_level == "Low" else 60 if risk_level == "Medium" else 50,
        "score": round(risk_score, 4),
        "veto": veto,
        "veto_reason": veto_reason,
        "risk_level": risk_level,
        "stop_loss": stop,
        "take_profit_targets": [tp1, tp2],
        "risk_reward_ratio": rr_ratio,
        "position_size_pct": position_pct,
        "max_capital_allocation_pct": cfg["max_portfolio_pct"],
        "portfolio_exposure_limit_pct": cfg["max_portfolio_pct"],
        "rationale": f"ATR={atr:.2f} ({atr_pct}%), R/R={rr_ratio}, profile={profile}",
        "supporting": [f"stop at {stop}", f"R/R {rr_ratio}"],
        "contradicting": [veto_reason] if veto_reason else [],
    }
