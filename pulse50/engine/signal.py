"""Rule-based signal generation and ranking."""

from __future__ import annotations

import math
from typing import Any


def generate_signal(features: dict[str, Any]) -> dict[str, Any]:
    score = 0.0
    rationale: list[str] = []

    for field, threshold, weight, label_up, label_down in (
        ("return_1m", 0.03, 0.4, "1m momentum is positive", "1m momentum is negative"),
        ("return_3m", 0.08, 0.5, "3m momentum is positive", "3m momentum is negative"),
        ("return_5m", 0.12, 0.5, "5m momentum is positive", "5m momentum is negative"),
    ):
        value = features.get(field)
        if value is None:
            continue
        if value > threshold:
            score += weight
            rationale.append(label_up)
        elif value < -threshold:
            score -= weight
            rationale.append(label_down)

    rsi = features.get("rsi_14")
    if rsi is not None:
        if rsi > 78 and score > 0:
            score *= 0.75
            rationale.append("RSI is hot, UP edge reduced")
        elif rsi < 22 and score < 0:
            score *= 0.75
            rationale.append("RSI is weak, DOWN edge reduced")

    if features.get("macd_signal") == "positive":
        score += 0.5
        rationale.append("MACD momentum is positive")
    elif features.get("macd_signal") == "negative":
        score -= 0.5
        rationale.append("MACD momentum is negative")

    imbalance = features.get("book_imbalance")
    if imbalance is not None:
        if imbalance > 0.2:
            score += 0.5
            rationale.append("Order book bid imbalance is supportive")
        elif imbalance < -0.2:
            score -= 0.5
            rationale.append("Order book ask imbalance is heavy")

    ema_slope = features.get("ema_slope_5")
    if ema_slope is not None:
        if ema_slope > 0:
            score += 0.5
            rationale.append("Short EMA slope is rising")
        elif ema_slope < 0:
            score -= 0.5
            rationale.append("Short EMA slope is falling")

    volume_spike = features.get("volume_spike")
    if volume_spike and volume_spike > 1.5:
        score *= 1.2
        rationale.append("Volume is elevated versus recent baseline")

    btc_regime = features.get("btc_5m_return")
    if btc_regime is not None and btc_regime < -0.3 and score > 0:
        score *= 0.5
        rationale.append("BTC regime is weak, bullish score suppressed")

    probability_up = _score_to_probability(score)
    direction = "UP" if probability_up > 0.55 else "DOWN" if probability_up < 0.45 else "FLAT"
    confidence = _confidence(probability_up, features)
    risk_tier = _risk_tier(features)
    expected_range = _expected_return_range(features, direction)

    return {
        "rank": None,
        "symbol": features["symbol"],
        "pair": features.get("pair"),
        "current_price": features.get("current_price"),
        "reference_price_cmc": features.get("reference_price_cmc"),
        "reference_price_cmc_updated_at": features.get("reference_price_cmc_updated_at"),
        "direction": direction,
        "probability_up": probability_up,
        "expected_return_range_pct": expected_range,
        "confidence": confidence,
        "risk_tier": risk_tier,
        "invalidation_level": _invalidation_level(features, direction),
        "rationale": rationale[:3] or ["Neutral short-horizon feature mix"],
        "data_quality": features.get("data_quality", "missing"),
        "provider": {
            "provider_used": features.get("provider_used"),
            "provider_fallbacks": [],
            "coverage_score": features.get("coverage_score") or 0.0,
            "data_freshness_seconds": features.get("data_freshness_seconds"),
            "liquidity_quality": features.get("liquidity_quality") or "unknown",
        },
    }


def rank_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rank_score(signal: dict[str, Any]) -> float:
        if signal.get("suppressed"):
            return -1
        confidence_weight = {"High": 1.0, "Medium": 0.7, "Low": 0.3}.get(signal["confidence"], 0.3)
        risk_weight = {"Low": 1.0, "Medium": 1.2, "High": 1.5, "Extreme": 2.0}.get(signal["risk_tier"], 2.0)
        return abs(signal["probability_up"] - 0.5) * confidence_weight * (1 / risk_weight)

    ranked = sorted(signals, key=rank_score, reverse=True)
    rank = 1
    for signal in ranked:
        if signal.get("suppressed"):
            signal["rank"] = None
        else:
            signal["rank"] = rank
            rank += 1
    return ranked


def _score_to_probability(score: float) -> float:
    probability = 1 / (1 + math.exp(-score / 2))
    return round(min(0.75, max(0.35, probability)), 4)


def _confidence(probability_up: float, features: dict[str, Any]) -> str:
    edge = abs(probability_up - 0.5)
    quality = features.get("data_quality")
    if quality != "OK" or edge < 0.05:
        return "Low"
    if edge > 0.15 and features.get("coverage_score", 0) >= 0.75:
        return "High"
    return "Medium"


def _risk_tier(features: dict[str, Any]) -> str:
    vol = max(features.get("atr_5m") or 0, features.get("realized_vol_5m") or 0)
    if vol < 0.4:
        return "Low"
    if vol < 0.9:
        return "Medium"
    if vol < 1.8:
        return "High"
    return "Extreme"


def _expected_return_range(features: dict[str, Any], direction: str) -> tuple[float, float]:
    atr = features.get("atr_5m") or features.get("realized_vol_5m") or 0.2
    low = round(atr * 0.8, 4)
    high = round(atr * 1.5, 4)
    if direction == "DOWN":
        return (-high, -low)
    if direction == "FLAT":
        return (-low, low)
    return (low, high)


def _invalidation_level(features: dict[str, Any], direction: str) -> float | None:
    price = features.get("current_price")
    atr_pct = features.get("atr_5m")
    if not price or atr_pct is None:
        return None
    delta = price * (atr_pct / 100)
    if direction == "UP":
        return round(price - delta, 8)
    if direction == "DOWN":
        return round(price + delta, 8)
    return None
