"""Risk, quality, and safety controls."""

from __future__ import annotations

from typing import Any

from pulse50.config import NOT_ADVICE

BANNED_OUTPUT_TERMS = ("guaranteed", "certain", "invest now", "will go up", "buy now", "sell now")


def apply_risk_controls(signal: dict[str, Any], features: dict[str, Any], risk_mode: str) -> dict[str, Any]:
    warnings = []
    suppressed = False

    if signal["data_quality"] == "insufficient_data" and signal["confidence"] != "High":
        suppressed = True
        warnings.append("suppressed: insufficient data")
    if (features.get("spread_pct") or 0) > 0.5:
        suppressed = True
        warnings.append("suppressed: spread too wide")
    if (features.get("data_freshness_seconds") or 0) > 300:
        suppressed = True
        warnings.append("suppressed: stale market data")

    if signal["probability_up"] > 0.80:
        signal["probability_up"] = 0.80
        warnings.append("probability clamped for overconfidence")
    if signal["probability_up"] < 0.20:
        signal["probability_up"] = 0.20
        warnings.append("probability clamped for overconfidence")

    if risk_mode == "conservative":
        if signal["confidence"] != "High" or signal["risk_tier"] not in {"Low", "Medium"}:
            suppressed = True
            warnings.append("suppressed: conservative risk mode")
    elif risk_mode == "aggressive" and suppressed:
        warnings.append("included despite low-quality flags because risk_mode=aggressive")
        suppressed = False

    signal["warnings"] = warnings
    signal["suppressed"] = suppressed
    signal["not_advice"] = NOT_ADVICE
    _assert_safe_text(signal)
    return signal


def _assert_safe_text(payload: Any) -> None:
    text = str(payload).lower()
    for term in BANNED_OUTPUT_TERMS:
        if term in text:
            raise ValueError(f"unsafe output term detected: {term}")
