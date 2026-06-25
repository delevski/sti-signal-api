"""News and sentiment with catalyst detection."""

from __future__ import annotations

import re
from typing import Any

POSITIVE = re.compile(
    r"\b(beat|surge|gain|upgrade|record|growth|acquisition|partnership|approval|buyback|dividend hike)\b",
    re.I,
)
NEGATIVE = re.compile(
    r"\b(miss|fall|cut|downgrade|lawsuit|investigation|recall|bankruptcy|layoff|guidance cut|sec probe|fine|recall)\b",
    re.I,
)
CATALYST_TAGS = {
    "earnings": re.compile(r"\b(earnings|EPS|quarterly results|Q[1-4])\b", re.I),
    "guidance": re.compile(r"\b(guidance|outlook|forecast)\b", re.I),
    "mna": re.compile(r"\b(merger|acquisition|acquire|takeover)\b", re.I),
    "regulatory": re.compile(r"\b(regulatory|SEC|FDA|antitrust|fine)\b", re.I),
    "legal": re.compile(r"\b(lawsuit|sued|litigation)\b", re.I),
}


def _tag_catalysts(text: str) -> list[str]:
    tags = []
    for name, pat in CATALYST_TAGS.items():
        if pat.search(text):
            tags.append(name)
    return tags


def analyze(news_bundle: dict) -> dict[str, Any]:
    articles = news_bundle.get("articles", [])
    source = news_bundle.get("source", "unknown")

    pos_score, neg_score = 0, 0
    catalysts: list[dict[str, Any]] = []
    influential: list[dict[str, str]] = []

    for art in articles[:15]:
        headline = art.get("headline") or art.get("title") or ""
        summary = art.get("summary") or ""
        text = f"{headline} {summary}"
        if POSITIVE.search(text):
            pos_score += 1
            influential.append({"headline": headline[:120], "impact": "positive", "source": art.get("source", source)})
        if NEGATIVE.search(text):
            neg_score += 1
            influential.append({"headline": headline[:120], "impact": "negative", "source": art.get("source", source)})
        tags = _tag_catalysts(text)
        if tags:
            catalysts.append({"headline": headline[:100], "tags": tags})

    total = max(len(articles), 1)
    news_score = 0.5 + (pos_score - neg_score) / (total * 2)
    news_score = max(0.0, min(1.0, news_score))

    if news_score >= 0.58:
        signal = "Buy"
    elif news_score <= 0.42:
        signal = "Sell"
    else:
        signal = "Hold"

    confidence = round(50 + abs(news_score - 0.5) * 90, 1)
    if len(articles) < 3:
        confidence = min(confidence, 55)
        signal = "Hold"

    supporting = [i["headline"] for i in influential if i["impact"] == "positive"][:3]
    contradicting = [i["headline"] for i in influential if i["impact"] == "negative"][:3]

    return {
        "signal": signal,
        "confidence": min(85, confidence),
        "score": round(news_score, 4),
        "news_score": round(news_score, 3),
        "source": source,
        "article_count": len(articles),
        "catalysts": catalysts[:5],
        "influential_news": influential[:5],
        "rationale": f"news_score={news_score:.2f} from {len(articles)} articles ({source})",
        "supporting": supporting,
        "contradicting": contradicting,
    }
