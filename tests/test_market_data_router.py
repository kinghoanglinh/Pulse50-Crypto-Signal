import unittest

from pulse50.adapters.market_data import (
    AssetMarketData,
    CoinAPIProvider,
    MarketDataProviderError,
    ProviderCapability,
    ProviderRouter,
)


class FailingProvider:
    capability = ProviderCapability(
        name="primary",
        has_ohlcv=True,
        has_order_book=True,
        has_ticker=True,
        requires_api_key=True,
        normalized_multi_exchange=True,
    )

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        raise MarketDataProviderError("not configured")


class WorkingProvider:
    capability = ProviderCapability(
        name="fallback",
        has_ohlcv=True,
        has_order_book=False,
        has_ticker=True,
        requires_api_key=False,
        normalized_multi_exchange=True,
    )

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        return AssetMarketData(
            symbol=symbol.upper(),
            quote_asset=quote_asset,
            pair=f"{symbol.upper()}{quote_asset}",
            supported=True,
            provider_used=None,
            data_quality="OK",
        )


class ProviderRouterTests(unittest.TestCase):
    def test_routes_to_fallback_and_records_provider_metadata(self):
        router = ProviderRouter(providers=[FailingProvider(), WorkingProvider()])

        result = router.get_asset_market_data("btc")

        self.assertTrue(result.supported)
        self.assertEqual(result.provider_used, "fallback")
        self.assertEqual(result.pair, "BTCUSDT")
        self.assertEqual(result.coverage_score, 0.75)
        self.assertIn("primary: not configured", result.provider_fallbacks)

    def test_returns_unavailable_payload_when_all_providers_fail(self):
        router = ProviderRouter(providers=[FailingProvider()])

        result = router.get_asset_market_data("eth")

        self.assertFalse(result.supported)
        self.assertEqual(result.data_quality, "provider_unavailable")
        self.assertIsNone(result.provider_used)
        self.assertEqual(result.coverage_score, 0.0)


class MockResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class MockCoinAPISession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=10):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        if "BINANCE_SPOT_BTC_USDT" not in url:
            return MockResponse(404, {"error": "not found"})
        if "/ohlcv/" in url:
            limit = int(params["limit"])
            candles = [
                {
                    "time_period_start": f"2026-05-27T10:{minute:02d}:00.0000000Z",
                    "price_open": 100 + minute,
                    "price_high": 101 + minute,
                    "price_low": 99 + minute,
                    "price_close": 100.5 + minute,
                    "volume_traded": 10 + minute,
                    "trades_count": 5 + minute,
                }
                for minute in range(limit)
            ]
            return MockResponse(200, list(reversed(candles)))
        if "/orderbooks/" in url:
            return MockResponse(
                200,
                {
                    "time_exchange": "2026-05-27T10:30:00.0000000Z",
                    "bids": [{"price": 129.99, "size": 2}, {"price": 129.98, "size": 1}],
                    "asks": [{"price": 130.01, "size": 1}, {"price": 130.02, "size": 1}],
                },
            )
        return MockResponse(500, {"error": "unexpected"})


class CoinAPIProviderTests(unittest.TestCase):
    def test_fetches_and_normalizes_coinapi_market_data(self):
        session = MockCoinAPISession()
        provider = CoinAPIProvider(api_key="test-key", session=session)

        result = provider.get_asset_market_data("btc")

        self.assertTrue(result.supported)
        self.assertEqual(result.provider_used, "coinapi")
        self.assertEqual(result.pair, "BINANCE_SPOT_BTC_USDT")
        self.assertEqual(len(result.ohlcv_1m), 30)
        self.assertEqual(len(result.ohlcv_5m), 10)
        self.assertEqual(result.ohlcv_1m[0]["timestamp"], "2026-05-27T10:00:00.0000000Z")
        self.assertAlmostEqual(result.order_book["spread_pct"], 0.015384615384617082)
        self.assertEqual(result.liquidity_quality, "excellent")
        self.assertEqual(result.ticker["last_price"], 129.5)
        self.assertEqual(session.calls[0]["headers"]["X-CoinAPI-Key"], "test-key")

    def test_requires_api_key(self):
        provider = CoinAPIProvider(api_key="", session=MockCoinAPISession())

        with self.assertRaises(MarketDataProviderError):
            provider.get_asset_market_data("btc")


if __name__ == "__main__":
    unittest.main()
