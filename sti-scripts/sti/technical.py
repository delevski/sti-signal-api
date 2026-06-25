"""Advanced technical analysis with pandas-ta."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None


def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def _pivot_levels(lows: pd.Series, highs: pd.Series, lookback: int = 20) -> tuple[float, float]:
    support = float(lows.tail(lookback).min())
    resistance = float(highs.tail(lookback).max())
    return support, resistance


def analyze(rows: list[dict]) -> dict[str, Any]:
    if len(rows) < 30:
        return {
            "signal": "Hold",
            "confidence": 45,
            "rationale": "Insufficient history for reliable technical analysis",
            "indicators": {},
            "score": 0.5,
        }

    df = _rows_to_df(rows)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    last = float(close.iloc[-1])

    indicators: dict[str, Any] = {"last_close": round(last, 2)}

    # RSI
    if ta:
        rsi_s = ta.rsi(close, length=14)
        macd_df = ta.macd(close)
        bb = ta.bbands(close, length=20)
        atr_s = ta.atr(high, low, close, length=14)
        adx_df = ta.adx(high, low, close, length=14)
    else:
        rsi_s = macd_df = bb = atr_s = adx_df = None

    rsi = float(rsi_s.iloc[-1]) if rsi_s is not None and not pd.isna(rsi_s.iloc[-1]) else 50.0
    indicators["rsi"] = round(rsi, 1)

    # MACD
    macd_signal = "neutral"
    if macd_df is not None and not macd_df.empty:
        cols = list(macd_df.columns)
        macd_col = next((c for c in cols if c.startswith("MACD_") and "h" not in c and "s" not in c), cols[0] if cols else None)
        macd_h = next((c for c in cols if "MACDh" in c or c.endswith("h")), None)
        if macd_col and macd_h:
            macd_v = float(macd_df[macd_col].iloc[-1])
            hist_v = float(macd_df[macd_h].iloc[-1])
            indicators["macd"] = round(macd_v, 3)
            indicators["macd_histogram"] = round(hist_v, 3)
            prev_hist = float(macd_df[macd_h].iloc[-2]) if len(macd_df) > 1 else 0
            if hist_v > 0 and prev_hist <= 0:
                macd_signal = "bullish_cross"
            elif hist_v < 0 and prev_hist >= 0:
                macd_signal = "bearish_cross"
            elif hist_v > 0:
                macd_signal = "bullish"
            else:
                macd_signal = "bearish"
    indicators["macd_signal"] = macd_signal

    # Bollinger
    if bb is not None and not bb.empty:
        bbl = [c for c in bb.columns if c.startswith("BBL")][0]
        bbu = [c for c in bb.columns if c.startswith("BBU")][0]
        bb_lower, bb_upper = float(bb[bbl].iloc[-1]), float(bb[bbu].iloc[-1])
        indicators["bb_lower"] = round(bb_lower, 2)
        indicators["bb_upper"] = round(bb_upper, 2)
        if last <= bb_lower:
            indicators["bb_position"] = "below_lower"
        elif last >= bb_upper:
            indicators["bb_position"] = "above_upper"
        else:
            indicators["bb_position"] = "inside"

    # ATR
    atr = float(atr_s.iloc[-1]) if atr_s is not None and not pd.isna(atr_s.iloc[-1]) else last * 0.02
    indicators["atr"] = round(atr, 2)
    indicators["atr_pct"] = round(atr / last * 100, 2)

    # VWAP (session proxy over last 20 bars)
    typical = (high + low + close) / 3
    vwap = float((typical * volume).tail(20).sum() / volume.tail(20).sum())
    indicators["vwap"] = round(vwap, 2)
    indicators["price_vs_vwap"] = "above" if last > vwap else "below"

    # Volume profile proxy — high volume node
    vol_mean = float(volume.tail(20).mean())
    vol_last = float(volume.iloc[-1])
    indicators["volume_ratio"] = round(vol_last / vol_mean, 2) if vol_mean else 1.0

    # Support / resistance
    support, resistance = _pivot_levels(low, high)
    indicators["support"] = round(support, 2)
    indicators["resistance"] = round(resistance, 2)

    # Trend strength (ADX)
    trend_strength = 25.0
    if adx_df is not None and not adx_df.empty:
        adx_col = [c for c in adx_df.columns if c.startswith("ADX")][0]
        trend_strength = float(adx_df[adx_col].iloc[-1]) if not pd.isna(adx_df[adx_col].iloc[-1]) else 25.0
    indicators["adx"] = round(trend_strength, 1)
    indicators["trend_strength"] = "strong" if trend_strength > 25 else "weak"

    sma20 = float(close.tail(20).mean())
    sma50 = float(close.tail(50).mean()) if len(close) >= 50 else sma20
    indicators["sma20"] = round(sma20, 2)
    indicators["sma50"] = round(sma50, 2)

    # Composite score 0..1 (higher = more bullish)
    score = 0.5
    votes: list[str] = []

    if last > sma20 > sma50:
        score += 0.12
        votes.append("uptrend (price > SMA20 > SMA50)")
    elif last < sma20 < sma50:
        score -= 0.12
        votes.append("downtrend")

    if rsi < 30:
        score += 0.08
        votes.append(f"RSI oversold ({rsi:.0f})")
    elif rsi > 70:
        score -= 0.08
        votes.append(f"RSI overbought ({rsi:.0f})")

    if macd_signal in ("bullish", "bullish_cross"):
        score += 0.1
        votes.append(f"MACD {macd_signal}")
    elif macd_signal in ("bearish", "bearish_cross"):
        score -= 0.1
        votes.append(f"MACD {macd_signal}")

    if indicators.get("bb_position") == "below_lower":
        score += 0.06
        votes.append("price at lower Bollinger band")
    elif indicators.get("bb_position") == "above_upper":
        score -= 0.06
        votes.append("price at upper Bollinger band")

    if indicators.get("price_vs_vwap") == "above" and trend_strength > 25:
        score += 0.05
        votes.append("price above VWAP with trend")

    score = max(0.0, min(1.0, score))

    if score >= 0.62:
        signal = "Buy"
    elif score <= 0.38:
        signal = "Sell"
    else:
        signal = "Hold"

    # Confidence from distance from neutral + trend strength
    raw_conf = 50 + abs(score - 0.5) * 80 + min(trend_strength, 30) * 0.3
    confidence = round(min(85, max(40, raw_conf)), 1)

    return {
        "signal": signal,
        "confidence": confidence,
        "score": round(score, 4),
        "rationale": "; ".join(votes) if votes else "Mixed technical signals",
        "indicators": indicators,
        "supporting": votes,
        "contradicting": [],
    }
