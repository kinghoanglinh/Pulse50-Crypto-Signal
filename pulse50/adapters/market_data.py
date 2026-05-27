"""Production market data provider layer for Pulse50.

The market-data architecture is intentionally multi-provider. Binance is a
useful free source, but not the product core. Paid/normalized providers such
as CoinAPI can be preferred in production, with CoinGecko/Binance as fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pulse50.config import (
    BINANCE_BASE_URL,
    COINAPI_API_KEY,
    COINAPI_BASE_URL,
    PROVIDER_PRIORITY,
)


class MarketDataProviderError(RuntimeError):
    """Raised when a provider cannot return usable market data."""


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    has_ohlcv: bool
    has_order_book: bool
    has_ticker: bool
    requires_api_key: bool
    normalized_multi_exchange: bool


@dataclass
class AssetMarketData:
    symbol: str
    quote_asset: str
    pair: str | None
    supported: bool
    provider_used: str | None
    provider_fallbacks: list[str] = field(default_factory=list)
    coverage_score: float = 0.0
    data_freshness_seconds: float | None = None
    liquidity_quality: str = "unknown"
    ohlcv_1m: list[dict[str, Any]] = field(default_factory=list)
    ohlcv_5m: list[dict[str, Any]] = field(default_factory=list)
    ticker: dict[str, Any] = field(default_factory=dict)
    order_book: dict[str, Any] = field(default_factory=dict)
    data_quality: str = "missing"
    warnings: list[str] = field(default_factory=list)


class MarketDataProvider(Protocol):
    capability: ProviderCapability

    def get_asset_market_data(
        self,
        symbol: str,
        quote_asset: str = "USDT",
    ) -> AssetMarketData:
        """Return normalized market data for one asset."""


class CoinAPIProvider:
    """Institutional-style normalized provider.

    This provider is the preferred production source when an API key is
    available. Endpoint calls are implemented in a later task; this class
    already owns capability metadata and routing behavior.
    """

    capability = ProviderCapability(
        name="coinapi",
        has_ohlcv=True,
        has_order_book=True,
        has_ticker=True,
        requires_api_key=True,
        normalized_multi_exchange=True,
    )

    def __init__(self, api_key: str = COINAPI_API_KEY, base_url: str = COINAPI_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        if not self.api_key:
            raise MarketDataProviderError("coinapi api key is not configured")
        raise MarketDataProviderError("coinapi live fetching is not implemented yet")


class CoinGeckoProvider:
    """Market-wide fallback provider for OHLCV/price data."""

    capability = ProviderCapability(
        name="coingecko",
        has_ohlcv=True,
        has_order_book=False,
        has_ticker=True,
        requires_api_key=False,
        normalized_multi_exchange=True,
    )

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        raise MarketDataProviderError("coingecko live market-data fetching is not implemented yet")


class BinanceProvider:
    """Exchange-specific fallback provider for liquid spot pairs."""

    capability = ProviderCapability(
        name="binance",
        has_ohlcv=True,
        has_order_book=True,
        has_ticker=True,
        requires_api_key=False,
        normalized_multi_exchange=False,
    )

    def __init__(self, base_url: str = BINANCE_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        raise MarketDataProviderError("binance live market-data fetching is not implemented yet")


class ProviderRouter:
    """Try providers in priority order and return the first usable normalized result."""

    def __init__(self, providers: list[MarketDataProvider] | None = None):
        provider_map: dict[str, MarketDataProvider] = {
            "coinapi": CoinAPIProvider(),
            "coingecko": CoinGeckoProvider(),
            "binance": BinanceProvider(),
        }
        self.providers = providers or [
            provider_map[name] for name in PROVIDER_PRIORITY if name in provider_map
        ]

    def get_asset_market_data(
        self,
        symbol: str,
        quote_asset: str = "USDT",
    ) -> AssetMarketData:
        fallbacks: list[str] = []

        for provider in self.providers:
            provider_name = provider.capability.name
            try:
                result = provider.get_asset_market_data(symbol, quote_asset)
                result.provider_used = provider_name
                result.provider_fallbacks = fallbacks
                result.coverage_score = max(result.coverage_score, self._coverage_score(provider))
                return result
            except MarketDataProviderError as exc:
                fallbacks.append(f"{provider_name}: {exc}")

        return AssetMarketData(
            symbol=symbol.upper(),
            quote_asset=quote_asset,
            pair=None,
            supported=False,
            provider_used=None,
            provider_fallbacks=fallbacks,
            coverage_score=0.0,
            data_quality="provider_unavailable",
            warnings=["No configured market data provider returned usable data"],
        )

    @staticmethod
    def _coverage_score(provider: MarketDataProvider) -> float:
        capability = provider.capability
        score = 0.0
        score += 0.35 if capability.has_ohlcv else 0.0
        score += 0.25 if capability.has_order_book else 0.0
        score += 0.20 if capability.has_ticker else 0.0
        score += 0.20 if capability.normalized_multi_exchange else 0.0
        return round(score, 2)
