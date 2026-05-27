"""Validated output schema for Pulse50."""

from __future__ import annotations

from typing import Literal

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - only before dependencies are installed
    BaseModel = object

    def Field(default=None, **_: object):
        return default


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
    warnings: list[str]
    not_advice: str
    model_version: str
    data_sources: list[ProviderMeta] = Field(default_factory=list)
    debug_features: dict | None = None
