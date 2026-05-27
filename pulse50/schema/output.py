"""Validated output schema for Pulse50."""

from __future__ import annotations

from typing import Any, Literal

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - only before dependencies are installed
    BaseModel = None

    def Field(default=None, default_factory=None, **_: object):
        if default_factory is not None:
            return default_factory()
        return default


if BaseModel is not None:

    class ProviderMeta(BaseModel):
        provider_used: str | None
        provider_fallbacks: list[str] = Field(default_factory=list)
        coverage_score: float = Field(ge=0.0, le=1.0)
        data_freshness_seconds: float | None = None
        liquidity_quality: Literal["unknown", "poor", "fair", "good", "excellent"]


    class SignalItem(BaseModel):
        rank: int | None
        symbol: str
        pair: str | None
        direction: Literal["UP", "DOWN", "FLAT"]
        probability_up: float = Field(ge=0.0, le=1.0)
        expected_return_range_pct: tuple[float, float]
        confidence: Literal["Low", "Medium", "High"]
        risk_tier: Literal["Low", "Medium", "High", "Extreme"]
        invalidation_level: float | None
        rationale: list[str]
        data_quality: str
        provider: ProviderMeta
        warnings: list[str] = Field(default_factory=list)
        suppressed: bool = False
        not_advice: str


    class UniverseMeta(BaseModel):
        source: str
        count: int
        actual_count: int
        filters: list[str]


    class Pulse50Response(BaseModel):
        as_of: str
        universe: UniverseMeta
        signals: list[SignalItem]
        summary: str
        warnings: list[str]
        not_advice: str
        model_version: str
        data_sources: list[ProviderMeta] = Field(default_factory=list)
        debug_features: dict | None = None


def validate_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate response with Pydantic when available, otherwise run light checks."""
    if BaseModel is not None:
        response = Pulse50Response(**payload)
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response.dict()

    required = {"as_of", "universe", "signals", "summary", "warnings", "not_advice", "model_version"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"Pulse50Response missing fields: {sorted(missing)}")
    for signal in payload["signals"]:
        probability = signal.get("probability_up")
        if probability is None or not 0 <= probability <= 1:
            raise ValueError("Signal probability_up must be between 0 and 1")
    return payload
