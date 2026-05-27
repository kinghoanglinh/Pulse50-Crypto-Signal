from pulse50.adapters.market_data import AssetMarketData


def candles(count=30, start=100.0, step=0.25):
    return [
        {
            "timestamp": f"2026-05-27T10:{index:02d}:00+00:00",
            "open": start + (index * step),
            "high": start + (index * step) + 0.4,
            "low": start + (index * step) - 0.4,
            "close": start + (index * step) + 0.1,
            "volume": 100 + index,
            "trades_count": 10 + index,
            "taker_buy_base_volume": 55 + index,
        }
        for index in range(count)
    ]


def market_data(symbol="BTC", start=100.0, step=0.25):
    return AssetMarketData(
        symbol=symbol,
        quote_asset="USDT",
        pair=f"{symbol}USDT",
        supported=True,
        provider_used="fixture",
        provider_fallbacks=[],
        coverage_score=0.9,
        data_freshness_seconds=10,
        liquidity_quality="excellent",
        ohlcv_1m=candles(30, start=start, step=step),
        ohlcv_5m=candles(10, start=start, step=step * 5),
        ticker={"last_price": start + 1},
        order_book={
            "spread_pct": 0.02,
            "book_imbalance": 0.3,
            "bid_volume": 10,
            "ask_volume": 5,
        },
        data_quality="OK",
    )
