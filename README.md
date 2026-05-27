# Pulse50 Multi-Source Crypto Signal Engine

Pulse50 Crypto Signal is a production-oriented Swarms Marketplace tool for
probabilistic 5-minute crypto market signals across the top 50 large-cap crypto
assets.

The product is designed as a multi-source signal engine. Binance is only one
fallback provider; production routing can prefer normalized providers such as
CoinAPI, then market-wide CoinGecko data, then exchange-specific Binance spot
data when appropriate.

The product is designed as a research signal tool, not an assurance engine and
not financial, investment, or trading advice.

## Build Status

Current phase: Phase 2 - Production Market Data Provider Layer

BRD source of truth:

```text
docs/Pulse50_Crypto_Signal_BRD_v1.1.locked.docx
```

## Planned Tool Function

```python
def analyze_pulse50_crypto_signals(
    universe_size: int = 50,
    exclude_stablecoins: bool = True,
    horizon_minutes: int = 5,
    quote_asset: str = "USDT",
    include_debug_features: bool = False,
    risk_mode: str = "balanced",
) -> dict:
    ...
```

## Output Schema

The tool returns a JSON-serializable dictionary with:

- `as_of`: ISO timestamp
- `universe`: source, requested count, actual count, filters
- `signals`: ranked signal objects with direction, probability, confidence,
  risk tier, invalidation level, rationale, provider metadata, warnings, and
  non-advice text
- `summary`: human-readable top signal summary
- `warnings`: provider, universe, stale-cache, and quality notes
- `data_sources`: provider usage, fallback, coverage, freshness, and liquidity
  metadata
- `debug_features`: optional feature dictionary when requested

## Safety Positioning

Every response must include:

```text
Research signal only. Not financial, investment, or trading advice. Past signals do not guarantee future results.
```

## Production Data Architecture

- CoinAPI: preferred normalized multi-exchange provider when configured
- CoinGecko: market-wide fallback for price/OHLCV coverage
- Binance: exchange-specific fallback for liquid spot pairs and order book data
- Every output records provider used, fallbacks, coverage score, freshness, and
  liquidity quality

## Project Layout

```text
Pulse50-Crypto-Signal/
  README.md
  requirements.txt
  .env.example
  .gitignore
  pulse50/
  tests/
  examples/
  docs/
```

## Calibration

Every run can append prediction rows to `predictions.jsonl`. Once 5-minute
outcomes are available in `outcomes.jsonl`, run:

```bash
python evaluate.py
```

The evaluator prints hit rate, average realized return, Brier score, and
confidence bucket counts, then writes `calibration_report.csv`.
