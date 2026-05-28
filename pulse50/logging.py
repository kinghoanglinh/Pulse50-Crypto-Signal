"""Prediction logging for calibration and post-run evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_predictions(response: dict[str, Any], path: str | Path = "predictions.jsonl") -> int:
    """Append one JSONL row per signal and return rows written."""
    output_path = Path(path)
    rows = []
    for signal in response.get("signals", []):
        rows.append(
            {
                "as_of": response.get("as_of"),
                "symbol": signal.get("symbol"),
                "direction": signal.get("direction"),
                "probability_up": signal.get("probability_up"),
                "price_at_signal": _price_from_debug(response, signal.get("symbol")),
                "horizon_minutes": (response.get("run_metrics") or {}).get("horizon_minutes", 15),
                "confidence": signal.get("confidence"),
                "model_version": response.get("model_version"),
            }
        )

    if not rows:
        return 0

    with output_path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def _price_from_debug(response: dict[str, Any], symbol: str | None) -> float | None:
    if not symbol:
        return None
    debug = response.get("debug_features") or {}
    features = debug.get(symbol) or {}
    return features.get("current_price")
