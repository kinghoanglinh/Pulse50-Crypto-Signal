import unittest

from pulse50.telegram_bot import format_coin_response, format_scan_response, format_status_response


class TelegramFormatterTests(unittest.TestCase):
    def test_format_scan_response(self):
        response = {
            "signals": [
                {
                    "rank": 1,
                    "symbol": "SOL",
                    "direction": "UP",
                    "probability_up": 0.62,
                    "confidence": "Medium",
                    "risk_tier": "Low",
                    "invalidation_level": 83.34,
                    "suppressed": False,
                    "provider": {"provider_used": "binance", "liquidity_quality": "excellent"},
                }
            ]
        }

        text = format_scan_response(response)

        self.assertIn("Pulse50 Top Keo 5 Phut", text)
        self.assertIn("SOL | LONG", text)
        self.assertIn("xac suat tang", text)
        self.assertIn("Tin hieu chi dung cho nghien cuu", text)

    def test_format_coin_response(self):
        response = {
            "signals": [
                {
                    "symbol": "BTC",
                    "direction": "FLAT",
                    "probability_up": 0.5,
                    "confidence": "Low",
                    "risk_tier": "Low",
                    "data_quality": "no_orderbook",
                    "invalidation_level": None,
                    "rationale": ["Neutral short-horizon feature mix"],
                    "provider": {"provider_used": "coingecko"},
                }
            ]
        }

        text = format_coin_response(response, "BTC")

        self.assertIn("Pulse50 BTC", text)
        self.assertIn("Huong: DUNG NGOAI", text)
        self.assertIn("Tin hieu ngan han dang trung tinh", text)

    def test_format_status_response(self):
        response = {
            "model_version": "v1.0-rules",
            "universe": {"actual_count": 3},
            "data_sources": [{"provider_used": "coinapi", "coverage_score": 1.0}],
            "run_metrics": {"total_run_time_seconds": 1.23},
            "warnings": [],
        }

        text = format_status_response(response)

        self.assertIn("Trang thai Pulse50", text)
        self.assertIn("CoinAPI:1.0", text)


if __name__ == "__main__":
    unittest.main()
