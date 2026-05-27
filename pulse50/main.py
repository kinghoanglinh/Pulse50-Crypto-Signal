"""Swarms tool entrypoint for Pulse50 Crypto Signal."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pulse50.adapters.market_data import AssetMarketData, ProviderRouter
from pulse50.adapters.universe import UniverseProviderError, fetch_top_market_assets
from pulse50.config import MODEL_VERSION, NOT_ADVICE
from pulse50.engine.features import compute_features, compute_regime_context
from pulse50.engine.risk import apply_risk_controls
from pulse50.engine.signal import generate_signal, rank_signals
from pulse50.schema.output import validate_response


def analyze_pulse50_crypto_signals(
    universe_size: int = 50,
    exclude_stablecoins: bool = True,
    horizon_minutes: int = 5,
    quote_asset: str = "USDT",
    include_debug_features: bool = False,
    risk_mode: str = "balanced",
    _router: ProviderRouter | None = None,
    _universe_payload: dict[str, Any] | None = None,
) -> dict:
    """Analyze top crypto assets for probabilistic 5-minute research signals."""
    warnings: list[str] = []
    if horizon_minutes != 5:
        warnings.append("horizon_minutes must equal 5 in v1; proceeding with 5")
        horizon_minutes = 5

    universe_payload = _universe_payload
    if universe_payload is None:
        try:
            universe_payload = fetch_top_market_assets(
                universe_size=universe_size,
                exclude_stablecoins=exclude_stablecoins,
            )
        except UniverseProviderError as exc:
            universe_payload = {
                "source": "coingecko",
                "count": universe_size,
                "actual_count": 0,
                "filters": ["provider_unavailable"],
                "assets": [],
                "warnings": [f"universe provider failed: {exc}"],
            }

    warnings.extend(universe_payload.get("warnings", []))
    assets = universe_payload.get("assets", [])
    router = _router or ProviderRouter()

    market_data_by_symbol: dict[str, AssetMarketData] = {}
    for asset in assets:
        symbol = str(asset.get("symbol", "")).upper()
        if not symbol:
            continue
        data = router.get_asset_market_data(symbol, quote_asset=quote_asset)
        market_data_by_symbol[symbol] = data
        warnings.extend(data.warnings)

    regime_context = compute_regime_context(market_data_by_symbol)
    debug_features: dict[str, Any] = {}
    signals = []

    for symbol, market_data in market_data_by_symbol.items():
        if not market_data.supported:
            warnings.append(f"{symbol}: market data unavailable")
            continue
        features = compute_features(market_data, regime_context=regime_context)
        debug_features[symbol] = features
        signal = generate_signal(features)
        signal["provider"]["provider_fallbacks"] = market_data.provider_fallbacks
        signals.append(apply_risk_controls(signal, features, risk_mode=risk_mode))

    ranked_signals = rank_signals(signals)
    payload = {
        "as_of": datetime.now(UTC).isoformat(),
        "universe": {
            "source": universe_payload.get("source", "unknown"),
            "count": universe_payload.get("count", universe_size),
            "actual_count": universe_payload.get("actual_count", len(assets)),
            "filters": universe_payload.get("filters", []),
        },
        "signals": ranked_signals,
        "summary": _summary(ranked_signals),
        "warnings": warnings,
        "not_advice": NOT_ADVICE,
        "model_version": MODEL_VERSION,
        "data_sources": _data_sources(ranked_signals),
        "debug_features": debug_features if include_debug_features else None,
    }
    return validate_response(payload)


def _summary(signals: list[dict[str, Any]]) -> str:
    active = [signal for signal in signals if not signal.get("suppressed")]
    top = active[:5]
    if not top:
        return "No active Pulse50 signals passed quality and risk controls."
    parts = [
        f"{signal['rank']}. {signal['symbol']} {signal['direction']} "
        f"p_up={signal['probability_up']:.2f} confidence={signal['confidence']}"
        for signal in top
    ]
    return "Top Pulse50 signals: " + "; ".join(parts)


def _data_sources(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    sources = []
    for signal in signals:
        provider = signal.get("provider", {})
        key = (provider.get("provider_used"), provider.get("coverage_score"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(provider)
    return sources


if __name__ == "__main__":
    print(analyze_pulse50_crypto_signals())
