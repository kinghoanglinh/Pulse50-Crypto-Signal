"""Record 5-minute outcomes for Pulse50 prediction logs."""

from __future__ import annotations

import json
from pathlib import Path

from pulse50.adapters.market_data import ProviderRouter
from evaluate import load_jsonl


def record_outcomes(
    predictions_path="predictions.jsonl",
    outcomes_path="outcomes.jsonl",
    quote_asset="USDT",
) -> int:
    predictions = load_jsonl(predictions_path)
    existing = {
        (row.get("as_of"), row.get("symbol"))
        for row in load_jsonl(outcomes_path)
    }
    router = ProviderRouter()
    rows = []

    for prediction in predictions:
        key = (prediction.get("as_of"), prediction.get("symbol"))
        if key in existing or not prediction.get("symbol"):
            continue
        market_data = router.get_asset_market_data(prediction["symbol"], quote_asset=quote_asset)
        latest_price = market_data.ticker.get("last_price")
        start_price = prediction.get("price_at_signal")
        actual_return = ((latest_price - start_price) / start_price) * 100 if latest_price and start_price else None
        rows.append(
            {
                "as_of": prediction.get("as_of"),
                "symbol": prediction.get("symbol"),
                "price_after_5m": latest_price,
                "actual_return_pct": actual_return,
                "provider_used": market_data.provider_used,
                "data_quality": market_data.data_quality,
            }
        )

    if not rows:
        return 0

    with Path(outcomes_path).open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


if __name__ == "__main__":
    print(f"recorded_outcomes={record_outcomes()}")
