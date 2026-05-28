"""Evaluate Pulse50 prediction logs against outcome logs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def load_jsonl(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    return [json.loads(line) for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(predictions_path="predictions.jsonl", outcomes_path="outcomes.jsonl") -> dict:
    predictions = load_jsonl(predictions_path)
    outcomes = load_jsonl(outcomes_path)
    outcome_map = {(row["as_of"], row["symbol"]): row for row in outcomes}

    joined = []
    for prediction in predictions:
        outcome = outcome_map.get((prediction.get("as_of"), prediction.get("symbol")))
        if not outcome:
            continue
        actual_return = outcome.get("actual_return_pct")
        if actual_return is None:
            start = prediction.get("price_at_signal")
            end = outcome.get("price_after_15m", outcome.get("price_after_5m"))
            actual_return = ((end - start) / start) * 100 if start and end else None
        if actual_return is None:
            continue
        joined.append({**prediction, "actual_return_pct": actual_return, "actual_up": actual_return > 0})

    if not joined:
        return {"count": 0, "markdown": "| metric | value |\n|---|---|\n| joined_predictions | 0 |"}

    correct = [
        (row["direction"] == "UP" and row["actual_up"]) or (row["direction"] == "DOWN" and not row["actual_up"])
        for row in joined
        if row["direction"] in {"UP", "DOWN"}
    ]
    brier = mean([(row["probability_up"] - (1 if row["actual_up"] else 0)) ** 2 for row in joined])
    by_confidence = defaultdict(list)
    for row in joined:
        by_confidence[row.get("confidence", "Unknown")].append(row)

    metrics = {
        "count": len(joined),
        "hit_rate": round((sum(correct) / len(correct)) if correct else 0.0, 4),
        "avg_realized_return_pct": round(mean([row["actual_return_pct"] for row in joined]), 4),
        "brier_score": round(brier, 4),
        "confidence_counts": {key: len(value) for key, value in by_confidence.items()},
    }
    metrics["markdown"] = _markdown(metrics)
    return metrics


def write_calibration_csv(metrics: dict, path="calibration_report.csv") -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            if key != "markdown":
                writer.writerow([key, value])


def _markdown(metrics: dict) -> str:
    rows = ["| metric | value |", "|---|---|"]
    for key, value in metrics.items():
        if key != "markdown":
            rows.append(f"| {key} | {value} |")
    return "\n".join(rows)


if __name__ == "__main__":
    result = evaluate()
    write_calibration_csv(result)
    print(result["markdown"])
