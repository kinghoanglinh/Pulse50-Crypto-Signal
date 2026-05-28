"""Production market data provider layer for Pulse50.

The market-data architecture is intentionally multi-provider. Binance is a
useful free source, but not the product core. Paid/normalized providers such
as CoinAPI can be preferred in production, with CoinGecko/Binance as fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from pulse50.config import (
    BINANCE_BASE_URL,
    COINAPI_API_KEY,
    COINAPI_BASE_URL,
    COINGECKO_API_KEY,
    COINGECKO_BASE_URL,
    COINMARKETCAP_API_KEY,
    COINMARKETCAP_BASE_URL,
    PROVIDER_PRIORITY,
)
from pulse50.cache.store import CACHE_TTLS, TTLCache, default_cache

try:
    import requests
except ImportError:  # pragma: no cover - only before dependencies are installed
    requests = None


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

    exchange_priority = ("BINANCE", "COINBASE", "KRAKEN", "BITSTAMP", "OKX")

    def __init__(
        self,
        api_key: str = COINAPI_API_KEY,
        base_url: str = COINAPI_BASE_URL,
        session: Any | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        if not self.api_key:
            raise MarketDataProviderError("coinapi api key is not configured")
        if self.session is None:
            raise MarketDataProviderError("requests is not installed")

        errors: list[str] = []
        for symbol_id in self._candidate_symbol_ids(symbol, quote_asset):
            try:
                return self._fetch_symbol(symbol.upper(), quote_asset, symbol_id)
            except MarketDataProviderError as exc:
                errors.append(f"{symbol_id}: {exc}")

        raise MarketDataProviderError("; ".join(errors) or "no coinapi symbol candidates")

    def _candidate_symbol_ids(self, symbol: str, quote_asset: str) -> list[str]:
        base = symbol.upper()
        requested_quote = quote_asset.upper()
        quotes = [requested_quote]
        if requested_quote == "USDT":
            quotes.append("USD")
        elif requested_quote == "USD":
            quotes.append("USDT")

        candidates: list[str] = []
        for exchange in self.exchange_priority:
            for quote in quotes:
                candidates.append(f"{exchange}_SPOT_{base}_{quote}")
        return candidates

    def _fetch_symbol(self, symbol: str, quote_asset: str, symbol_id: str) -> AssetMarketData:
        ohlcv_1m = self._fetch_ohlcv(symbol_id, "1MIN", 30)
        ohlcv_5m = self._fetch_ohlcv(symbol_id, "5MIN", 10)
        if len(ohlcv_1m) < 10:
            raise MarketDataProviderError("insufficient 1m candles")

        order_book, order_book_warning = self._fetch_order_book(symbol_id)
        latest_candle = ohlcv_1m[-1]
        data_freshness = _freshness_seconds(latest_candle.get("timestamp"))
        liquidity_quality = _liquidity_quality(order_book)
        data_quality = "OK" if not order_book_warning else "no_orderbook"

        warnings = []
        if order_book_warning:
            warnings.append(order_book_warning)

        return AssetMarketData(
            symbol=symbol,
            quote_asset=quote_asset,
            pair=symbol_id,
            supported=True,
            provider_used=self.capability.name,
            coverage_score=1.0 if order_book else 0.75,
            data_freshness_seconds=data_freshness,
            liquidity_quality=liquidity_quality,
            ohlcv_1m=ohlcv_1m,
            ohlcv_5m=ohlcv_5m,
            ticker={
                "last_price": latest_candle.get("close"),
                "last_volume": latest_candle.get("volume"),
                "trades_count": latest_candle.get("trades_count"),
            },
            order_book=order_book,
            data_quality=data_quality,
            warnings=warnings,
        )

    def _fetch_ohlcv(self, symbol_id: str, period_id: str, limit: int) -> list[dict[str, Any]]:
        payload = self._get(
            f"/v1/ohlcv/{symbol_id}/latest",
            params={"period_id": period_id, "limit": limit},
        )
        if not isinstance(payload, list):
            raise MarketDataProviderError(f"unexpected {period_id} ohlcv payload")

        candles = [_normalize_coinapi_candle(item) for item in payload]
        candles = [candle for candle in candles if candle]
        candles.sort(key=lambda candle: str(candle["timestamp"]))
        return candles

    def _fetch_order_book(self, symbol_id: str) -> tuple[dict[str, Any], str | None]:
        try:
            payload = self._get(
                f"/v1/orderbooks/{symbol_id}/current",
                params={"limit_levels": 5},
            )
        except MarketDataProviderError as exc:
            return {}, f"coinapi order book unavailable: {exc}"

        if not isinstance(payload, dict):
            return {}, "coinapi order book returned unexpected payload"

        return _normalize_coinapi_order_book(payload), None

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"X-CoinAPI-Key": self.api_key}
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, headers=headers, params=params or {}, timeout=3)
        except Exception as exc:
            raise MarketDataProviderError(f"network error: {exc}") from exc

        if response.status_code == 404:
            raise MarketDataProviderError("symbol not found")
        if response.status_code == 429:
            raise MarketDataProviderError("rate limit reached")
        if response.status_code == 401:
            raise MarketDataProviderError("unauthorized api key")
        if response.status_code >= 400:
            raise MarketDataProviderError(f"http {response.status_code}")
        return response.json()


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

    symbol_ids = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "TRX": "tron",
        "LINK": "chainlink",
        "AVAX": "avalanche-2",
        "SUI": "sui",
        "TON": "the-open-network",
        "SHIB": "shiba-inu",
        "DOT": "polkadot",
        "BCH": "bitcoin-cash",
        "LTC": "litecoin",
        "NEAR": "near",
        "UNI": "uniswap",
        "APT": "aptos",
        "ICP": "internet-computer",
    }

    def __init__(
        self,
        base_url: str = COINGECKO_BASE_URL,
        api_key: str = COINGECKO_API_KEY,
        session: Any | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        if self.session is None:
            raise MarketDataProviderError("requests is not installed")
        coingecko_id = self.symbol_ids.get(symbol.upper())
        if not coingecko_id:
            raise MarketDataProviderError(f"no coingecko id mapping for {symbol.upper()}")
        quote_currency = "usd" if quote_asset.upper() in {"USDT", "USD"} else quote_asset.lower()
        payload = self._get(
            f"/coins/{coingecko_id}/market_chart",
            params={"vs_currency": quote_currency, "days": "1"},
        )
        prices = payload.get("prices", []) if isinstance(payload, dict) else []
        volumes = payload.get("total_volumes", []) if isinstance(payload, dict) else []
        if len(prices) < 10:
            raise MarketDataProviderError("insufficient coingecko price points")

        ohlcv = _coingecko_prices_to_candles(prices, volumes)
        latest = ohlcv[-1]
        return AssetMarketData(
            symbol=symbol.upper(),
            quote_asset=quote_asset.upper(),
            pair=f"{coingecko_id}/{quote_currency}",
            supported=True,
            provider_used=self.capability.name,
            coverage_score=0.75,
            data_freshness_seconds=_freshness_seconds(latest.get("timestamp")),
            liquidity_quality="unknown",
            ohlcv_1m=ohlcv[-30:],
            ohlcv_5m=ohlcv[-10:],
            ticker={"last_price": latest.get("close"), "last_volume": latest.get("volume")},
            order_book={},
            data_quality="no_orderbook",
            warnings=["coingecko fallback has no order book data"],
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key
        try:
            response = self.session.get(f"{self.base_url}{path}", headers=headers, params=params or {}, timeout=3)
        except Exception as exc:
            raise MarketDataProviderError(f"network error: {exc}") from exc
        if response.status_code == 404:
            raise MarketDataProviderError("asset not found")
        if response.status_code == 429:
            raise MarketDataProviderError("rate limit reached")
        if response.status_code >= 400:
            raise MarketDataProviderError(f"http {response.status_code}")
        return response.json()


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
    known_liquid_pairs = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def __init__(self, base_url: str = BINANCE_BASE_URL, session: Any | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests

    def get_asset_market_data(self, symbol: str, quote_asset: str = "USDT") -> AssetMarketData:
        if self.session is None:
            raise MarketDataProviderError("requests is not installed")

        pair = f"{symbol.upper()}{quote_asset.upper()}"
        if not self._pair_is_trading(pair):
            raise MarketDataProviderError(f"{pair} is not a trading spot pair")

        ohlcv_1m = self._fetch_klines(pair, "1m", 30)
        ohlcv_5m = self._fetch_klines(pair, "5m", 10)
        if len(ohlcv_1m) < 10:
            raise MarketDataProviderError("insufficient 1m candles")

        ticker = self._fetch_ticker(pair)
        order_book = self._fetch_order_book(pair)
        latest_candle = ohlcv_1m[-1]

        return AssetMarketData(
            symbol=symbol.upper(),
            quote_asset=quote_asset.upper(),
            pair=pair,
            supported=True,
            provider_used=self.capability.name,
            coverage_score=0.8,
            data_freshness_seconds=_freshness_seconds(latest_candle.get("timestamp")),
            liquidity_quality=_liquidity_quality(order_book),
            ohlcv_1m=ohlcv_1m,
            ohlcv_5m=ohlcv_5m,
            ticker=ticker,
            order_book=order_book,
            data_quality="OK",
        )

    def _pair_is_trading(self, pair: str) -> bool:
        if pair in self.known_liquid_pairs:
            return True
        payload = self._get("/api/v3/exchangeInfo", params={"symbol": pair})
        symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
        return any(item.get("symbol") == pair and item.get("status") == "TRADING" for item in symbols)

    def _fetch_klines(self, pair: str, interval: str, limit: int) -> list[dict[str, Any]]:
        payload = self._get(
            "/api/v3/klines",
            params={"symbol": pair, "interval": interval, "limit": limit},
        )
        if not isinstance(payload, list):
            raise MarketDataProviderError(f"unexpected {interval} kline payload")
        candles = [_normalize_binance_kline(item) for item in payload]
        return [candle for candle in candles if candle]

    def _fetch_ticker(self, pair: str) -> dict[str, Any]:
        payload = self._get("/api/v3/ticker/price", params={"symbol": pair})
        if not isinstance(payload, dict):
            raise MarketDataProviderError("unexpected ticker payload")
        return {
            "last_price": _float_or_none(payload.get("price")),
            "price_change_pct_24h": _float_or_none(payload.get("priceChangePercent")),
            "volume": _float_or_none(payload.get("volume")),
            "quote_volume": _float_or_none(payload.get("quoteVolume")),
            "weighted_avg_price": _float_or_none(payload.get("weightedAvgPrice")),
        }

    def _fetch_order_book(self, pair: str) -> dict[str, Any]:
        payload = self._get("/api/v3/depth", params={"symbol": pair, "limit": 5})
        if not isinstance(payload, dict):
            raise MarketDataProviderError("unexpected order book payload")
        return _normalize_binance_order_book(payload)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(f"{self.base_url}{path}", params=params or {}, timeout=3)
        except Exception as exc:
            raise MarketDataProviderError(f"network error: {exc}") from exc
        if response.status_code == 404:
            raise MarketDataProviderError("symbol not found")
        if response.status_code == 429:
            raise MarketDataProviderError("rate limit reached")
        if response.status_code >= 400:
            raise MarketDataProviderError(f"http {response.status_code}")
        return response.json()


class CoinMarketCapPriceClient:
    """Batch latest-price client for BTC/ETH/SOL reference prices."""

    def __init__(
        self,
        api_key: str = COINMARKETCAP_API_KEY,
        base_url: str = COINMARKETCAP_BASE_URL,
        session: Any | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests

    def get_latest_prices(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not self.api_key or self.session is None or not symbols:
            return {}
        try:
            response = self.session.get(
                f"{self.base_url}/v3/cryptocurrency/quotes/latest",
                headers={"X-CMC_PRO_API_KEY": self.api_key},
                params={"symbol": ",".join(symbols), "convert": "USD"},
                timeout=2,
            )
        except Exception:
            return {}
        if response.status_code >= 400:
            return {}
        payload = response.json()
        return _parse_cmc_quotes(payload)


class ProviderRouter:
    """Try providers in priority order and return the first usable normalized result."""

    def __init__(
        self,
        providers: list[MarketDataProvider] | None = None,
        cache: TTLCache | None = default_cache,
    ):
        provider_map: dict[str, MarketDataProvider] = {
            "coinapi": CoinAPIProvider(),
            "coingecko": CoinGeckoProvider(),
            "binance": BinanceProvider(),
        }
        self.providers = providers or [
            provider_map[name] for name in PROVIDER_PRIORITY if name in provider_map
        ]
        self.cache = cache

    def get_asset_market_data(
        self,
        symbol: str,
        quote_asset: str = "USDT",
    ) -> AssetMarketData:
        cache_key = f"asset_market_data:{symbol.upper()}:{quote_asset.upper()}"
        cached_stale: AssetMarketData | None = None
        stale_age_seconds: float | None = None
        if self.cache is not None:
            cached, age_seconds = self.cache.get(cache_key)
            if isinstance(cached, AssetMarketData):
                cached.data_freshness_seconds = age_seconds
                cached.warnings = [*cached.warnings, f"served_from_cache age_seconds={age_seconds:.2f}"]
                return cached
            stale_value, stale_age_seconds = self.cache.get_stale(cache_key)
            if isinstance(stale_value, AssetMarketData):
                cached_stale = stale_value

        fallbacks: list[str] = []

        for provider in self.providers:
            provider_name = provider.capability.name
            try:
                result = provider.get_asset_market_data(symbol, quote_asset)
                result.provider_used = provider_name
                result.provider_fallbacks = fallbacks
                result.coverage_score = max(result.coverage_score, self._coverage_score(provider))
                if self.cache is not None:
                    self.cache.set(cache_key, result, CACHE_TTLS["asset_market_data"])
                return result
            except MarketDataProviderError as exc:
                fallbacks.append(f"{provider_name}: {exc}")

        if cached_stale is not None:
            cached_stale.provider_fallbacks = fallbacks
            cached_stale.data_freshness_seconds = stale_age_seconds
            cached_stale.data_quality = "stale_cache"
            cached_stale.warnings = [
                *cached_stale.warnings,
                f"served_from_stale_cache age_seconds={stale_age_seconds:.2f}",
            ]
            return cached_stale

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


def _normalize_coinapi_candle(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return {
            "timestamp": item.get("time_period_start"),
            "open": float(item["price_open"]),
            "high": float(item["price_high"]),
            "low": float(item["price_low"]),
            "close": float(item["price_close"]),
            "volume": float(item.get("volume_traded") or 0.0),
            "trades_count": int(item.get("trades_count") or 0),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _normalize_coinapi_order_book(payload: dict[str, Any]) -> dict[str, Any]:
    bids = [
        {"price": float(level["price"]), "size": float(level["size"])}
        for level in payload.get("bids", [])
        if "price" in level and "size" in level
    ]
    asks = [
        {"price": float(level["price"]), "size": float(level["size"])}
        for level in payload.get("asks", [])
        if "price" in level and "size" in level
    ]
    return _order_book_metrics(
        bids=bids,
        asks=asks,
        timestamp=payload.get("time_exchange") or payload.get("time_coinapi"),
    )


def _normalize_binance_kline(item: list[Any]) -> dict[str, Any] | None:
    try:
        return {
            "timestamp": datetime.fromtimestamp(int(item[0]) / 1000, tz=UTC).isoformat(),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "close_time": datetime.fromtimestamp(int(item[6]) / 1000, tz=UTC).isoformat(),
            "quote_volume": float(item[7]),
            "trades_count": int(item[8]),
            "taker_buy_base_volume": float(item[9]),
            "taker_buy_quote_volume": float(item[10]),
        }
    except (IndexError, TypeError, ValueError):
        return None


def _normalize_binance_order_book(payload: dict[str, Any]) -> dict[str, Any]:
    bids = [
        {"price": float(price), "size": float(size)}
        for price, size in payload.get("bids", [])
    ]
    asks = [
        {"price": float(price), "size": float(size)}
        for price, size in payload.get("asks", [])
    ]
    return _order_book_metrics(bids=bids, asks=asks, timestamp=None)


def _coingecko_prices_to_candles(
    prices: list[list[Any]],
    volumes: list[list[Any]],
) -> list[dict[str, Any]]:
    volume_by_ts = {int(row[0]): float(row[1]) for row in volumes if len(row) >= 2}
    candles = []
    for row in prices:
        if len(row) < 2:
            continue
        timestamp_ms = int(row[0])
        price = float(row[1])
        candles.append(
            {
                "timestamp": datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume_by_ts.get(timestamp_ms, 0.0),
                "trades_count": 0,
            }
        )
    return candles


def _parse_cmc_quotes(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    output: dict[str, dict[str, Any]] = {}
    if isinstance(data, list):
        iterable = [(str(item.get("symbol", "")), item) for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        iterable = data.items()
    else:
        iterable = []
    for key, raw_value in iterable:
        items = raw_value if isinstance(raw_value, list) else [raw_value]
        for item in items:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or key).upper()
            quote_container = item.get("quote", {})
            if isinstance(quote_container, dict):
                quote = quote_container.get("USD", {})
            elif isinstance(quote_container, list):
                quote = next(
                    (entry for entry in quote_container if entry.get("symbol") == "USD"),
                    quote_container[0] if quote_container else {},
                )
            else:
                quote = {}
            if not quote and item.get("quotes"):
                quote = (item["quotes"][0].get("quote", {}) or {}).get("USD", {})
            price = quote.get("price")
            if price is None:
                continue
            rank = item.get("cmc_rank")
            existing = output.get(symbol)
            if existing:
                existing_rank = existing.get("cmc_rank")
                if existing_rank and (rank is None or existing_rank <= rank):
                    continue
            output[symbol] = {
                "price": float(price),
                "last_updated": quote.get("last_updated") or quote.get("timestamp"),
                "cmc_rank": rank,
                "source": "coinmarketcap",
            }
    return output


def _freshness_seconds(timestamp: Any) -> float | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(UTC) - parsed).total_seconds())


def _liquidity_quality(order_book: dict[str, Any]) -> str:
    spread_pct = order_book.get("spread_pct")
    if spread_pct is None:
        return "unknown"
    if spread_pct <= 0.03:
        return "excellent"
    if spread_pct <= 0.10:
        return "good"
    if spread_pct <= 0.30:
        return "fair"
    return "poor"


def _order_book_metrics(
    bids: list[dict[str, float]],
    asks: list[dict[str, float]],
    timestamp: Any,
) -> dict[str, Any]:
    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    spread_pct = None
    if best_bid and best_ask:
        mid = (best_bid + best_ask) / 2
        spread_pct = ((best_ask - best_bid) / mid) * 100 if mid else None

    bid_volume = sum(level["size"] for level in bids)
    ask_volume = sum(level["size"] for level in asks)
    imbalance = None
    if bid_volume + ask_volume > 0:
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    return {
        "timestamp": timestamp,
        "bids": bids,
        "asks": asks,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread_pct": spread_pct,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "book_imbalance": imbalance,
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
