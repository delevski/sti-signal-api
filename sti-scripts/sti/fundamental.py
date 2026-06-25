"""Fundamental analysis — growth, debt, ownership, revisions."""

from __future__ import annotations

from typing import Any


def analyze(fundamentals: dict, info: dict | None = None) -> dict[str, Any]:
    f = fundamentals or {}
    info = info or {}
    metrics = {
        "trailing_pe": f.get("trailingPE"),
        "forward_pe": f.get("forwardPE"),
        "price_to_book": f.get("priceToBook"),
        "revenue_growth": f.get("revenueGrowth"),
        "earnings_growth": f.get("earningsGrowth"),
        "earnings_quarterly_growth": f.get("earningsQuarterlyGrowth"),
        "free_cashflow": f.get("freeCashflow"),
        "debt_to_equity": f.get("debtToEquity"),
        "return_on_equity": f.get("returnOnEquity"),
        "profit_margins": f.get("profitMargins"),
        "institutional_ownership": info.get("heldPercentInstitutions"),
        "insider_ownership": info.get("heldPercentInsiders"),
        "analyst_recommendation": info.get("recommendationKey"),
        "target_mean_price": info.get("targetMeanPrice"),
    }

    score = 0.5
    votes: list[str] = []
    contradict: list[str] = []

    rev_g = metrics.get("revenue_growth")
    if rev_g is not None:
        if rev_g > 0.1:
            score += 0.1
            votes.append(f"revenue growth {rev_g*100:.1f}%")
        elif rev_g < 0:
            score -= 0.1
            contradict.append(f"revenue declining ({rev_g*100:.1f}%)")

    earn_g = metrics.get("earnings_growth")
    if earn_g is not None:
        if earn_g > 0.15:
            score += 0.08
            votes.append(f"earnings growth {earn_g*100:.1f}%")
        elif earn_g < 0:
            score -= 0.08
            contradict.append(f"earnings contraction")

    dte = metrics.get("debt_to_equity")
    if dte is not None:
        if dte > 150:
            score -= 0.1
            contradict.append(f"high debt/equity ({dte:.0f})")
        elif dte < 50:
            score += 0.05
            votes.append("conservative debt levels")

    roe = metrics.get("return_on_equity")
    if roe is not None and roe > 0.15:
        score += 0.06
        votes.append(f"strong ROE ({roe*100:.1f}%)")

    pe = metrics.get("trailing_pe")
    if pe is not None:
        if pe > 45:
            score -= 0.08
            contradict.append(f"elevated P/E ({pe:.1f})")
        elif pe < 20:
            score += 0.06
            votes.append(f"reasonable P/E ({pe:.1f})")

    rec = metrics.get("analyst_recommendation")
    if rec in ("buy", "strong_buy"):
        score += 0.06
        votes.append(f"analyst consensus: {rec}")
    elif rec in ("sell", "strong_sell"):
        score -= 0.06
        contradict.append(f"analyst consensus: {rec}")

    inst = metrics.get("institutional_ownership")
    if inst is not None and inst > 0.6:
        votes.append(f"institutional ownership {inst*100:.0f}%")

    score = max(0.0, min(1.0, score))
    if score >= 0.58:
        signal = "Buy"
    elif score <= 0.42:
        signal = "Sell"
    else:
        signal = "Hold"

    confidence = round(50 + abs(score - 0.5) * 70, 1)

    return {
        "signal": signal,
        "confidence": min(80, confidence),
        "score": round(score, 4),
        "rationale": "; ".join(votes) if votes else "Neutral fundamentals",
        "metrics": metrics,
        "supporting": votes,
        "contradicting": contradict,
    }
