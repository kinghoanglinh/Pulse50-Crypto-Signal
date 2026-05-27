import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse50.adapters.market_data import AssetMarketData
from record_outcomes import record_outcomes


class FixtureRouter:
    def get_asset_market_data(self, symbol, quote_asset="USDT"):
        return AssetMarketData(
            symbol=symbol,
            quote_asset=quote_asset,
            pair=f"{symbol}{quote_asset}",
            supported=True,
            provider_used="fixture",
            ticker={"last_price": 105.0},
            data_quality="OK",
        )


class RecordOutcomesTests(unittest.TestCase):
    def test_records_outcome_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            predictions = Path(tmp) / "predictions.jsonl"
            outcomes = Path(tmp) / "outcomes.jsonl"
            predictions.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-27T10:00:00+00:00",
                        "symbol": "BTC",
                        "price_at_signal": 100.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("record_outcomes.ProviderRouter", return_value=FixtureRouter()):
                count = record_outcomes(predictions, outcomes)

            self.assertEqual(count, 1)
            row = json.loads(outcomes.read_text(encoding="utf-8"))
            self.assertEqual(row["actual_return_pct"], 5.0)


if __name__ == "__main__":
    unittest.main()
