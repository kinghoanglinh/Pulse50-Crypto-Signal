import unittest

from pulse50.engine.features import compute_features, compute_regime_context
from pulse50.engine.risk import apply_risk_controls
from pulse50.engine.signal import generate_signal, rank_signals
from tests.fixtures import market_data


class EnginePipelineTests(unittest.TestCase):
    def test_generates_rankable_safe_signal(self):
        data = market_data("BTC")
        context = compute_regime_context({"BTC": data})
        features = compute_features(data, context)
        signal = apply_risk_controls(generate_signal(features), features, risk_mode="balanced")

        self.assertEqual(signal["symbol"], "BTC")
        self.assertGreaterEqual(signal["probability_up"], 0.35)
        self.assertLessEqual(signal["probability_up"], 0.75)
        self.assertIn(signal["direction"], {"UP", "DOWN", "FLAT"})
        self.assertIn("not_advice", signal)

    def test_ranking_assigns_active_ranks(self):
        btc_features = compute_features(market_data("BTC", step=0.3), {"BTC": 1.0})
        eth_features = compute_features(market_data("ETH", step=0.05), {"BTC": 1.0})
        signals = [
            apply_risk_controls(generate_signal(btc_features), btc_features, "balanced"),
            apply_risk_controls(generate_signal(eth_features), eth_features, "balanced"),
        ]

        ranked = rank_signals(signals)

        self.assertEqual(ranked[0]["rank"], 1)
        self.assertEqual(ranked[1]["rank"], 2)


if __name__ == "__main__":
    unittest.main()
