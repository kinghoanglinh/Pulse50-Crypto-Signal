"""Feature computation for Pulse50 signals."""

from __future__ import annotations

from statistics import mean, stdev
from typing import Any

from pulse50.adapters.market_data import AssetMarketData


def compute_features(
    market_data: AssetMarketData,
    regime_context: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    closes = [float(candle["close"]) for candle in market_data.ohlcv_1m if candle.get("close") is not None]
    volumes = [float(candle.get("volume") or 0.0) for candle in market_data.ohlcv_1m]
    current_price = closes[-1] if closes else market_data.ticker.get("last_price")
    returns = _returns(closes)

    features = {
        "symbol": market_data.symbol,
        "pair": market_data.pair,
        "current_price": current_price,
        "reference_price_cmc": market_data.ticker.get("cmc_price"),
        "reference_price_cmc_updated_at": market_data.ticker.get("cmc_last_updated"),
        "return_1m": _pct_change(closes, 1),
        "return_3m": _pct_change(closes, 3),
        "return_5m": _pct_change(closes, 5),
        "ema_slope_5": _ema_slope(closes, period=5, lookback=3),
        "rsi_14": _rsi(closes, period=14),
        "macd_signal": _macd_histogram_sign(closes),
        "atr_5m": _atr_pct(market_data.ohlcv_5m, period=5),
        "realized_vol_5m": stdev(returns[-5:]) if len(returns) >= 5 else None,
        "volume_spike": _volume_spike(volumes),
        "taker_buy_ratio": _taker_buy_ratio(market_data.ohlcv_1m[-1] if market_data.ohlcv_1m else {}),
        "spread_pct": market_data.order_book.get("spread_pct"),
        "book_imbalance": market_data.order_book.get("book_imbalance"),
        "data_quality": market_data.data_quality,
        "provider_used": market_data.provider_used,
        "coverage_score": market_data.coverage_score,
        "liquidity_quality": market_data.liquidity_quality,
        "data_freshness_seconds": market_data.data_freshness_seconds,
        "btc_5m_return": None,
        "eth_5m_return": None,
    }
    if regime_context:
        features["btc_5m_return"] = regime_context.get("BTC")
        features["eth_5m_return"] = regime_context.get("ETH")
    return features


def compute_regime_context(market_data_by_symbol: dict[str, AssetMarketData]) -> dict[str, float | None]:
    return {
        symbol: _pct_change(
            [float(candle["close"]) for candle in data.ohlcv_1m if candle.get("close") is not None],
            5,
        )
        for symbol, data in market_data_by_symbol.items()
        if symbol in {"BTC", "ETH"}
    }


def _pct_change(values: list[float], lookback: int) -> float | None:
    if len(values) <= lookback:
        return None
    previous = values[-1 - lookback]
    if previous == 0:
        return None
    return ((values[-1] - previous) / previous) * 100


def _returns(values: list[float]) -> list[float]:
    output = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous:
            output.append(((values[index] - previous) / previous) * 100)
    return output


def _ema_slope(values: list[float], period: int, lookback: int) -> float | None:
    if len(values) < period + lookback:
        return None
    ema_values = _ema(values, period)
    previous = ema_values[-1 - lookback]
    if previous == 0:
        return None
    return ((ema_values[-1] - previous) / previous) * 100


def _ema(values: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append((value * alpha) + (output[-1] * (1 - alpha)))
    return output


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for index in range(1, period + 1):
        delta = values[-index] - values[-index - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd_histogram_sign(values: list[float]) -> str | None:
    if len(values) < 26:
        return None
    macd_line = _ema(values, 12)[-1] - _ema(values, 26)[-1]
    signal = _ema([_ema(values[: idx + 1], 12)[-1] - _ema(values[: idx + 1], 26)[-1] for idx in range(25, len(values))], 9)[-1]
    hist = macd_line - signal
    if hist > 0:
        return "positive"
    if hist < 0:
        return "negative"
    return "neutral"


def _atr_pct(candles: list[dict[str, Any]], period: int) -> float | None:
    if len(candles) < period:
        return None
    true_ranges = []
    for candle in candles[-period:]:
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        true_ranges.append(max(high - low, abs(high - close), abs(low - close)))
    current = float(candles[-1]["close"])
    if current == 0:
        return None
    return (mean(true_ranges) / current) * 100


def _volume_spike(volumes: list[float]) -> float | None:
    if len(volumes) < 11:
        return None
    baseline = mean(volumes[-11:-1])
    if baseline == 0:
        return None
    return volumes[-1] / baseline


def _taker_buy_ratio(latest_candle: dict[str, Any]) -> float | None:
    taker = latest_candle.get("taker_buy_base_volume")
    volume = latest_candle.get("volume")
    if taker is None or not volume:
        return None
    return float(taker) / float(volume)
