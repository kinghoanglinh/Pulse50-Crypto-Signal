import unittest

from pulse50.adapters.market_data import (
    AssetMarketData,
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


if __name__ == "__main__":
    unittest.main()
