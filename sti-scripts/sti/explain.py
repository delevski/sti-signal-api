"""Plain-English explainability."""

from __future__ import annotations

from typing import Any


def build(
    ticker: str,
    technical: dict,
    fundamental: dict,
    sentiment: dict,
    risk: dict,
    ensemble: dict,
    macro: dict | None = None,
) -> dict[str, Any]:
    why: list[str] = []
    supports: list[str] = []
    contradicts: list[str] = []
    invalidate: list[str] = []

    rec = ensemble.get("recommendation", "Hold")
    val = ensemble.get("validation", {})

    for agent, data in [("Technical", technical), ("Fundamental", fundamental), ("Sentiment", sentiment), ("Risk", risk)]:
        supports.extend([f"[{agent}] {s}" for s in data.get("supporting", [])])
        contradicts.extend([f"[{agent}] {c}" for c in data.get("contradicting", [])])

    if rec in ("Buy", "Strong Buy"):
        why.append(f"{ticker} received a {rec} because the weighted ensemble score favors bullish factors.")
    elif rec in ("Sell", "Strong Sell"):
        why.append(f"{ticker} received a {rec} because bearish factors outweigh bullish ones in the ensemble.")
    else:
        why.append(f"{ticker} is Hold — confidence below threshold or agents disagree.")

    if val.get("conflict"):
        why.append(f"Agent conflict detected: {val.get('buy_votes')} buy vs {val.get('sell_votes')} sell votes.")
        invalidate.append("Strong opposing agent signals could reverse the recommendation.")

    if risk.get("veto"):
        why.append(f"Risk veto: {risk.get('veto_reason', 'risk limits exceeded')}")

    if ensemble.get("suppressed"):
        why.append("Actionable signal suppressed — calibrated confidence below minimum threshold.")

    ind = technical.get("indicators", {})
    if ind.get("rsi", 50) < 30:
        invalidate.append("RSI oversold bounce could invalidate a Sell thesis.")
    if ind.get("rsi", 50) > 70:
        invalidate.append("RSI overbought pullback could invalidate a Buy thesis.")

    if macro and macro.get("series", {}).get("vix", {}).get("value"):
        vix = float(macro["series"]["vix"]["value"])
        if vix > 25:
            invalidate.append(f"Elevated VIX ({vix}) increases gap risk and whipsaw probability.")

    plain = " ".join(why)
    if supports:
        plain += f" Supporting: {'; '.join(supports[:4])}."
    if contradicts:
        plain += f" Contradicting: {'; '.join(contradicts[:3])}."

    return {
        "why": why,
        "supporting_data": supports,
        "contradicting_data": contradicts,
        "could_invalidate": invalidate,
        "plain_english": plain,
        "formula_summary": ensemble.get("formula", {}).get("plain_english", ""),
    }
