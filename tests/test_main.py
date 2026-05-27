import unittest

from pulse50.main import analyze_pulse50_crypto_signals
from tests.fixtures import market_data


class FixtureRouter:
    def get_asset_market_data(self, symbol, quote_asset="USDT"):
        return market_data(symbol=symbol, start=100 if symbol == "BTC" else 50, step=0.25)


class MainToolTests(unittest.TestCase):
    def test_tool_returns_valid_response_from_fixtures(self):
        response = analyze_pulse50_crypto_signals(
            universe_size=2,
            include_debug_features=True,
            _router=FixtureRouter(),
            _universe_payload={
                "source": "fixture",
                "count": 2,
                "actual_count": 2,
                "filters": ["test"],
                "assets": [
                    {"symbol": "BTC", "name": "Bitcoin"},
                    {"symbol": "ETH", "name": "Ethereum"},
                ],
                "warnings": [],
            },
            _log_predictions=False,
        )

        self.assertEqual(response["universe"]["actual_count"], 2)
        self.assertEqual(len(response["signals"]), 2)
        self.assertIn("Top Pulse50 signals", response["summary"])
        self.assertIn("BTC", response["debug_features"])
        self.assertEqual(response["run_metrics"]["estimated_provider_weight_or_credits"], 0)
        self.assertIn("not_advice", response)


if __name__ == "__main__":
    unittest.main()
