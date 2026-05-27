# Pulse50 Crypto Signal

Pulse50 Crypto Signal is a Swarms Marketplace tool for probabilistic 5-minute
crypto market signals across the top 50 large-cap crypto assets.

The product is designed as a research signal tool, not a guaranteed prediction
engine and not financial, investment, or trading advice.

## Build Status

Current phase: Phase 1 - Repo & Architecture Prep

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

## Safety Positioning

Every response must include:

```text
Research signal only. Not financial, investment, or trading advice. Past signals do not guarantee future results.
```

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
