import unittest

from pulse50.adapters.universe import filter_market_assets


class UniverseFilterTests(unittest.TestCase):
    def test_filters_stablecoins_wrapped_and_null_market_cap(self):
        raw_assets = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "market_cap_rank": 1,
                "market_cap": 10,
                "current_price": 1,
            },
            {
                "id": "tether",
                "symbol": "usdt",
                "name": "Tether",
                "market_cap_rank": 2,
                "market_cap": 9,
                "current_price": 1,
            },
            {
                "id": "usds",
                "symbol": "usds",
                "name": "USDS",
                "market_cap_rank": 3,
                "market_cap": 8.5,
                "current_price": 1,
            },
            {
                "id": "wrapped-bitcoin",
                "symbol": "wbtc",
                "name": "Wrapped Bitcoin",
                "market_cap_rank": 4,
                "market_cap": 8,
                "current_price": 1,
            },
            {
                "id": "missing-cap",
                "symbol": "abc",
                "name": "ABC",
                "market_cap_rank": 4,
                "market_cap": None,
                "current_price": 1,
            },
            {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "market_cap_rank": 5,
                "market_cap": 7,
                "current_price": 1,
            },
        ]

        assets, warnings = filter_market_assets(raw_assets, universe_size=3)

        self.assertEqual([asset["symbol"] for asset in assets], ["BTC", "ETH"])
        self.assertEqual(len(assets), 2)
        self.assertIn("Only 2 eligible assets", warnings[0])


if __name__ == "__main__":
    unittest.main()
