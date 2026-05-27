# Pulse50 Crypto Signal — Codex Build Task List
**BRD Reference:** Pulse50_Crypto_Signal_BRD_v1.1.docx  
**Build Phase:** Phase 0 — BRD Lock, then Phase 1 — Repo & Architecture Prep  
**Target:** Swarms Marketplace Tool  
**Last updated:** 2026-05-27

---

## How to use this file
Work through tasks **top to bottom**. Each task has:
- A clear goal
- Acceptance criteria (AC) — done = all AC pass
- Notes for implementation decisions

Mark each task `[x]` when complete before moving to the next.

---

## Build Phase Map

This project should be built in gates. Do not jump into live signal generation
until the earlier gates pass.

| Phase | Goal | Exit Gate |
|---|---|---|
| Phase 0 - BRD Lock | Confirm product scope, safety posture, and v1.1 BRD consistency. | BRD metadata, requirements, schema, and marketplace direction are internally consistent. |
| Phase 1 - Repo & Architecture Prep | Create an isolated repo/folder, dependency plan, and module boundaries. | Project scaffold runs locally with no secrets and no import errors. |
| Phase 2 - Tool Build | Build the live Pulse50 signal tool. | `analyze_pulse50_crypto_signals()` returns valid schema for live or fixture data. |
| Phase 3 - Backtest & Calibration | Store predictions, join outcomes, and evaluate signal quality. | Calibration report runs and produces hit rate, Brier score, and confidence-bucket metrics. |
| Phase 4 - Swarms Marketplace Prep | Package tool for submission. | README, use cases, example output, cover image, and safety audit are complete. |
| Phase 5 - Pro Upgrade | Add streaming, alerts, multi-exchange, futures/open-interest, and ML. | Only start after v1 has real usage or reviews. |

---

## PHASE 0 - BRD Lock

### T-00 - Final BRD Consistency Pass
- [x] Update the BRD metadata from `Version: 1.0` to `Version: 1.1`
- [x] Add a short Version History table:
  - `1.0 - Initial BRD`
  - `1.1 - Added eligible asset shortfall handling and API rate-limit requirements`
- [x] Confirm the tool is positioned as probabilistic research signals, not guaranteed prediction
- [x] Confirm v1 product type is `Tool`, not Agent
- [x] Confirm v1 excludes stablecoins/wrapped assets by default
- [x] Confirm output schema includes data quality, warnings, and non-advice disclaimer

**AC:** BRD v1.1 is internally consistent and ready to serve as build source of truth.

---

## PHASE 1 - Repo & Architecture Prep

### T-00A - Create Isolated Product Repo
- [x] Create a new independent repo/folder for Pulse50, separate from DealScope and LaunchForge
- [x] Recommended repo name:
  ```text
  Pulse50-Crypto-Signal
  ```
- [x] Add initial files:
  ```text
  README.md
  requirements.txt
  .gitignore
  .env.example
  pulse50/
  tests/
  examples/
  docs/
  ```
- [x] Do not copy any DealScope agent code into this repo
- [x] Add BRD link or copy under `docs/`

**AC:** Pulse50 has its own clean workspace/repo with no unrelated project files.

### T-00B - Dependency & Secret Plan
- [x] Define required env vars in `.env.example`:
  ```text
  COINGECKO_API_KEY=
  COINMARKETCAP_API_KEY=
  BINANCE_BASE_URL=https://api.binance.com
  ```
- [x] Confirm all API keys are optional for local fixture tests
- [x] Confirm secrets are read only from env vars
- [x] Add `.env` to `.gitignore`

**AC:** Local tests can run without real API keys; live mode requires env vars only.

---

## PHASE 2 — Tool Build

### T-01 · Project Scaffold
- [x] Create repo/folder structure:
  ```
  pulse50/
  ├── main.py               # Swarms tool entrypoint
  ├── config.py             # Env vars, constants, defaults
  ├── adapters/
  │   ├── universe.py       # CoinGecko / CoinMarketCap
  │   └── market_data.py    # Binance OHLCV, ticker, order book
  ├── cache/
  │   └── store.py          # In-memory or Redis cache
  ├── engine/
  │   ├── features.py       # Feature computation
  │   ├── signal.py         # Signal generation
  │   └── risk.py           # Risk/safety layer
  ├── schema/
  │   └── output.py         # Pydantic output schema
  ├── tests/
  │   └── ...
  └── requirements.txt
  ```
- [x] `requirements.txt` includes: `requests`, `pandas`, `numpy`, `ta`, `pydantic`, `python-dotenv`
- [x] `config.py` reads all API keys from env vars only — never hardcoded

**AC:** `python main.py` runs without import errors; no secrets in code.

---

### T-02 · Universe Adapter (`adapters/universe.py`)
Goal: fetch and filter the current top-N crypto assets by market cap.

- [x] Call CoinGecko `GET /coins/markets` with params:
  - `vs_currency=usd`, `order=market_cap_desc`, `per_page=250`, `page=1`
  - Single call returns 250 coins → filter down to top 50 eligible
- [x] Filter out: stablecoins (category or symbol heuristic), wrapped assets (`WBTC`, `WETH`, etc.), assets with `null` market cap
- [x] Return list of dicts: `{id, symbol, name, market_cap_rank, market_cap, current_price}`
- [x] If CoinGecko returns fewer than 50 eligible assets after filtering:
  - Proceed with `actual_count`
  - Add warning: `"Only N eligible assets found after stablecoin filter"`
  - Never pad or duplicate
- [x] Exponential backoff on HTTP 429 (max 3 retries, base delay 2s)
- [x] Support `COINGECKO_API_KEY` env var for Pro tier (add `x-cg-pro-api-key` header)
- [x] Accept `universe_size` param (default 50), `exclude_stablecoins` bool (default True)

**AC:** Returns list of 40–50 dicts in <5s; 429 triggers retry without crash; stablecoins absent from output.

---

### T-03 · Production Market Data Provider Layer (`adapters/market_data.py`)
Goal: fetch normalized OHLCV, ticker stats, and order book data from multiple providers, not a single exchange.

- [x] Create provider abstraction:
  - `MarketDataProvider`
  - `ProviderCapability`
  - `AssetMarketData`
  - `ProviderRouter`
- [x] Treat Binance as an exchange-specific fallback provider, not the product core
- [x] Add production provider priority:
  - `coinapi` first when configured
  - `coingecko` as market-wide fallback
  - `binance` as liquid spot fallback
- [x] Add provider metadata to normalized output:
  - `provider_used`
  - `provider_fallbacks`
  - `coverage_score`
  - `data_freshness_seconds`
  - `liquidity_quality`
- [x] Add `COINAPI_API_KEY` and `COINAPI_BASE_URL` env vars
- [x] Implement CoinAPI live OHLCV/ticker/order-book fetching
- [x] Implement CoinGecko fallback OHLCV/price fetching
- [x] Implement Binance fallback pair mapping, OHLCV, ticker, and order book fetching
- [x] If a provider lacks order book, keep signal usable but downgrade liquidity confidence
- [x] If every provider fails, return `provider_unavailable` payload, not an unhandled exception
- [x] Respect each provider's rate limits and log estimated request weight/credits per run

**AC:** For BTC/ETH/SOL, provider router returns valid normalized market data from the best available provider, records fallbacks, and never hides source quality.

---

### T-04 · Cache Layer (`cache/store.py`)
Goal: avoid hitting rate limits on repeated calls; serve stale-but-valid data when provider is slow.

- [x] In-memory dict cache with TTL per entry type:
  - Universe list: TTL 5 minutes
  - OHLCV candles: TTL 60 seconds
  - Order book: TTL 15 seconds
  - Ticker: TTL 30 seconds
  - Provider capability metadata: TTL 15 minutes
- [x] `get(key)` returns `(data, age_seconds)` — caller decides if stale
- [x] `set(key, data)` with timestamp
- [x] If cached data is stale beyond threshold → include `"stale_cache": true` in data quality flags
- [x] Thread-safe (use `threading.Lock` or simple dict — single-process for v1)

**AC:** Second call within TTL returns cached data without HTTP request; age is accessible to callers.

---

### T-05 · Feature Engine (`engine/features.py`)
Goal: compute all signal features from raw OHLCV + ticker + order book data.

Implement the following feature groups per asset:

| Feature | Source | Notes |
|---|---|---|
| `return_1m`, `return_3m`, `return_5m` | 1m OHLCV closes | Percentage returns |
| `ema_slope_5` | 1m closes | EMA(5) slope over last 3 bars |
| `rsi_14` | 1m closes | RSI(14) via `ta` library |
| `macd_signal` | 1m closes | MACD histogram sign |
| `atr_5m` | 5m OHLCV | ATR(5) in % of price |
| `realized_vol_5m` | 1m returns | Std dev of last 5 returns |
| `volume_spike` | 1m volume | Last bar volume / 10-bar avg volume |
| `taker_buy_ratio` | Ticker | `taker_buy_base_vol / volume` |
| `spread_pct` | Order book | `(ask - bid) / mid * 100` |
| `book_imbalance` | Order book | `(bid_vol - ask_vol) / (bid_vol + ask_vol)` |
| `data_quality` | All sources | `OK` / `insufficient_data` / `stale_cache` / `no_orderbook` |

- [x] All features computed per asset; missing source → `None`, not crash
- [x] `include_debug_features=True` → return raw feature dict alongside signal
- [x] BTC/ETH regime: compute `btc_5m_return` and `eth_5m_return` as cross-asset context for all assets

**AC:** Feature dict for BTC contains all fields (or explicit `None`); no exceptions on missing order book data.

---

### T-06 · Signal Engine (`engine/signal.py`)
Goal: produce 5-minute probabilistic signal from feature dict.

**Phase 1: deterministic rule ensemble** (no ML needed for v1)

- [x] **Direction scoring:** weighted sum of feature signals:
  - RSI < 30 → bullish +1, RSI > 70 → bearish -1
  - MACD histogram positive → bullish +0.5
  - `book_imbalance` > 0.2 → bullish +0.5, < -0.2 → bearish -0.5
  - `volume_spike` > 1.5 → amplify direction signal by 1.2x
  - `ema_slope_5` positive → bullish +0.5
  - BTC regime: if `btc_5m_return` < -0.3% → suppress bullish signals by 0.5x
- [x] **Probability mapping:** map score to `probability_up` via sigmoid or linear clamp to [0.35, 0.75] — never output 0 or 1
- [x] **Direction:** UP if `probability_up > 0.55`, DOWN if `< 0.45`, else FLAT
- [x] **Expected return range:** `±atr_5m * 0.8` to `±atr_5m * 1.5` (directional)
- [x] **Confidence:** Low if data_quality issues or `|probability_up - 0.5| < 0.05`; High if all features present and `|prob - 0.5| > 0.15`; else Medium
- [x] **Risk tier:** based on `atr_5m` and `realized_vol_5m` thresholds (define in config)
- [x] **Invalidation level:** price ± 1×ATR from current price (direction-dependent)
- [x] **Rationale:** list top 2-3 contributing features in plain English

**AC:** Every signal has `probability_up` in (0.35, 0.75); FLAT signals appear when score is neutral; no division-by-zero.

---

### T-07 · Risk & Safety Engine (`engine/risk.py`)
Goal: suppress weak signals, attach mandatory disclaimers, enforce output safety.

- [x] **Suppress signals** (return `null` signal with warning) if:
  - `data_quality == "insufficient_data"` and `confidence != "High"`
  - `spread_pct > 0.5%` (too wide, poor liquidity)
  - Asset candles are older than 5 minutes (stale)
- [x] **Risk mode filtering:**
  - `conservative`: only output signals where `confidence == "High"` and `risk_tier` in `["Low", "Medium"]`
  - `balanced` (default): output all non-suppressed signals
  - `aggressive`: include suppressed signals with a `"low_quality"` warning flag
- [x] **Mandatory disclaimer:** every signal and every response root must include:
  `"not_advice": "Research signal only. Not financial, investment, or trading advice. Past signals do not guarantee future results."`
- [x] **Overconfidence check:** if any signal has `probability_up > 0.80` or `< 0.20` → clamp and add warning

**AC:** No output contains "guaranteed", "will", "certain", or direct trade instructions; suppressed signals have explicit reason.

---

### T-08 · Ranking Engine (in `engine/signal.py` or separate)
Goal: rank all asset signals by quality.

- [x] Score = `|probability_up - 0.5|` × confidence_weight × (1 / risk_weight)
  - `confidence_weight`: High=1.0, Medium=0.7, Low=0.3
  - `risk_weight`: Low=1.0, Medium=1.2, High=1.5, Extreme=2.0
- [x] Sort descending by score; assign `rank` 1..N
- [x] Suppressed signals ranked last with `rank: null`

**AC:** Top-ranked signal always has higher `|prob - 0.5|` × confidence than second-ranked.

---

### T-09 · Output Schema (`schema/output.py`)
Goal: define and validate the full JSON output.

- [x] Use Pydantic v2 models:

```python
class SignalItem(BaseModel):
    rank: Optional[int]
    symbol: str
    pair: str
    direction: Literal["UP", "DOWN", "FLAT"]
    probability_up: float          # 0.00–1.00
    expected_return_range_pct: tuple[float, float]
    confidence: Literal["Low", "Medium", "High"]
    risk_tier: Literal["Low", "Medium", "High", "Extreme"]
    invalidation_level: Optional[float]
    rationale: list[str]
    data_quality: str
    not_advice: str

class UniverseMeta(BaseModel):
    source: str
    count: int
    actual_count: int
    filters: list[str]

class Pulse50Response(BaseModel):
    as_of: str                     # ISO-8601
    universe: UniverseMeta
    signals: list[SignalItem]
    warnings: list[str]
    not_advice: str
    model_version: str
    debug_features: Optional[dict] = None
```

- [x] Validate every response before returning — raise clearly if schema fails
- [x] `model_version` = `"v1.0-rules"` for Phase 1 rule-based engine

**AC:** Pydantic validation passes on a real BTC/ETH/SOL response; invalid fields raise `ValidationError` not silent wrong output.

---

### T-10 · Swarms Tool Interface (`main.py`)
Goal: expose `analyze_pulse50_crypto_signals` as a callable Swarms tool.

- [x] Function signature:
```python
def analyze_pulse50_crypto_signals(
    universe_size: int = 50,
    exclude_stablecoins: bool = True,
    horizon_minutes: int = 5,
    quote_asset: str = "USDT",
    include_debug_features: bool = False,
    risk_mode: str = "balanced",
) -> dict:
```
- [x] Orchestrate: Universe → Market Data → Cache → Features → Signal → Risk → Rank → Schema → return
- [x] Return both JSON-serializable dict AND human-readable summary string (top 5 signals)
- [x] Log: provider latency, missing pairs count, stale candle count, total run time, model version
- [x] If any provider fully fails → return partial result with warnings; never raise unhandled exception to caller
- [x] `horizon_minutes` must equal 5 in v1; if other value passed → return error in warnings, proceed with 5

**AC:** Single call to `analyze_pulse50_crypto_signals()` returns valid `Pulse50Response` dict within 20s for 50 assets.

---

## PHASE 3 — Backtest & Calibration Hooks

### T-11 · Prediction Logger
- [x] After each run, append to local JSONL file `predictions.jsonl`:
  ```json
  {"as_of": "...", "symbol": "BTC", "direction": "UP", "probability_up": 0.61, "price_at_signal": 67000.0}
  ```
- [x] Scheduled or manual: after 5 minutes, fetch actual close price and append to `outcomes.jsonl`
- [x] Store `model_version` with every entry

**AC:** After 10 runs, `predictions.jsonl` has 10×N entries; outcomes can be joined on `as_of` + `symbol`.

### T-12 · Calibration Report
- [x] Script `evaluate.py` reads predictions + outcomes and outputs:
  - Hit rate (direction correct %)
  - Average realized return for UP/DOWN signals
  - Brier score for `probability_up`
  - Precision/recall by confidence tier
  - Calibration table: predicted prob bucket vs actual UP rate
- [x] Output as markdown table + CSV

**AC:** `python evaluate.py` runs on 50+ predictions and prints all metrics without error.

---

## PHASE 4 — Swarms Marketplace Prep

### T-13 · Marketplace Listing Assets
- [x] Write `README.md` with: overview, inputs, output schema, example call, example output, limitations, disclaimer
- [x] Write `use_cases.md` with 3 use cases (from BRD Section 10)
- [x] Generate one real example output JSON (run tool, save to `examples/example_output.json`)
- [x] Create cover image (1280×640px) — clean dark background, "Pulse50" branding, signal UI mockup

**AC:** README covers all input params and schema fields; example JSON validates against Pydantic schema.

### T-14 · Quality & Safety Audit
- [x] Search all output strings for banned words: `guaranteed`, `will go up`, `certain`, `invest now`, `buy`, `sell` as direct instruction
- [x] Confirm `not_advice` present in every signal and root response
- [x] Run 5 live scans and verify no schema validation errors
- [x] Confirm API keys never appear in logs or output

**AC:** Zero banned words in output; 5/5 live scans return valid schema.

---

## Done Definition
A build is **shippable** when:
1. `analyze_pulse50_crypto_signals()` returns valid schema for 50 assets in <20s
2. All FR-01 through FR-10 acceptance criteria pass
3. Safety audit T-14 passes with zero violations
4. At least one real example output saved in `examples/`
5. `predictions.jsonl` logger working (T-11)
