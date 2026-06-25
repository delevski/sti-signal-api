"""Quality control — detect illogical outputs."""

from __future__ import annotations

from typing import Any


def check(
    technical: dict,
    risk: dict,
    ensemble: dict,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    ind = technical.get("indicators", {})
    rsi = ind.get("rsi")
    tech_sig = technical.get("signal")
    risk_sig = risk.get("signal")
    final = ensemble.get("recommendation")

    if rsi is not None and rsi < 30 and tech_sig == "Sell":
        issues.append({
            "severity": "high",
            "code": "RSI_OVERSOLD_SELL",
            "message": f"RSI {rsi} indicates oversold but technical signal is Sell — review required",
        })
    if rsi is not None and rsi > 70 and tech_sig == "Buy":
        issues.append({
            "severity": "high",
            "code": "RSI_OVERBOUGHT_BUY",
            "message": f"RSI {rsi} indicates overbought but technical signal is Buy",
        })

    if tech_sig == "Buy" and risk_sig == "Buy" and final in ("Sell", "Strong Sell"):
        issues.append({
            "severity": "critical",
            "code": "AGENT_CONFLICT_UNEXPLAINED",
            "message": "Technical and Risk both Buy but final is Sell — must be explained in explainability block",
        })

    if ensemble.get("validation", {}).get("conflict") and final not in ("Hold",):
        issues.append({
            "severity": "medium",
            "code": "UNRESOLVED_CONFLICT",
            "message": "Agents disagree significantly; Hold may be more appropriate",
        })

    if not ensemble.get("formula", {}).get("plain_english"):
        issues.append({
            "severity": "critical",
            "code": "NO_TRACE",
            "message": "Recommendation lacks traceable formula explanation",
        })

    return issues


def block_if_critical(issues: list[dict]) -> bool:
    return any(i["severity"] == "critical" for i in issues)
