"""Fetch and filter the Pulse50 crypto universe."""

from __future__ import annotations

import time
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - only before dependencies are installed
    requests = None

from pulse50.config import COINGECKO_API_KEY

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
DEFAULT_MARKET_PAGE_SIZE = 250

STABLECOIN_SYMBOLS = {
    "usdt",
    "usdc",
    "usds",
    "usdl",
    "usd1",
    "usdy",
    "usda",
    "usdm",
    "usdx",
    "usyc",
    "rlusd",
    "eurc",
    "eurt",
    "dai",
    "fdusd",
    "tusd",
    "usde",
    "usdd",
    "usdp",
    "pyusd",
    "frax",
    "lusd",
    "gusd",
}
STABLECOIN_NAME_HINTS = ("stablecoin", "tether", "dai")
WRAPPED_SYMBOLS = {"wbtc", "weth", "weeth", "cbeth", "reth", "steth", "wsteth"}


class UniverseProviderError(RuntimeError):
    """Raised when the universe provider cannot return usable market data."""


def is_stablecoin(asset: dict[str, Any]) -> bool:
    """Return True when an asset looks like a stablecoin."""
    symbol = str(asset.get("symbol") or "").lower()
    name = str(asset.get("name") or "").lower()

    if symbol in STABLECOIN_SYMBOLS:
        return True
    if "stablecoin" in name:
        return True
    if symbol.startswith("usd") and len(symbol) <= 6:
        return True
    if symbol.endswith("usd") and len(symbol) <= 6:
        return True
    if any(hint in name for hint in STABLECOIN_NAME_HINTS) and symbol in STABLECOIN_SYMBOLS:
        return True
    return False


def is_wrapped_asset(asset: dict[str, Any]) -> bool:
    """Return True when an asset is likely wrapped or liquid-staked exposure."""
    symbol = str(asset.get("symbol") or "").lower()
    name = str(asset.get("name") or "").lower()

    if symbol in WRAPPED_SYMBOLS:
        return True
    if name.startswith("wrapped ") or "wrapped bitcoin" in name or "wrapped ether" in name:
        return True
    if symbol.startswith(("w", "st")) and ("wrapped" in name or "staked" in name):
        return True
    return False


def filter_market_assets(
    assets: list[dict[str, Any]],
    universe_size: int = 50,
    exclude_stablecoins: bool = True,
    exclude_wrapped: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter raw provider assets into an eligible top-N market cap universe."""
    warnings: list[str] = []
    eligible: list[dict[str, Any]] = []

    for asset in assets:
        if asset.get("market_cap") is None:
            continue
        if exclude_stablecoins and is_stablecoin(asset):
            continue
        if exclude_wrapped and is_wrapped_asset(asset):
            continue

        eligible.append(
            {
                "id": asset.get("id"),
                "symbol": str(asset.get("symbol") or "").upper(),
                "name": asset.get("name"),
                "market_cap_rank": asset.get("market_cap_rank"),
                "market_cap": asset.get("market_cap"),
                "current_price": asset.get("current_price"),
            }
        )

        if len(eligible) >= universe_size:
            break

    if len(eligible) < universe_size:
        warnings.append(
            f"Only {len(eligible)} eligible assets found after stablecoin/wrapped asset filter"
        )

    return eligible, warnings


def fetch_top_market_assets(
    universe_size: int = 50,
    exclude_stablecoins: bool = True,
    session: Any | None = None,
) -> dict[str, Any]:
    """Fetch top market-cap assets from CoinGecko and return filtered universe metadata."""
    if requests is None and session is None:
        raise UniverseProviderError("requests is not installed; run pip install -r requirements.txt")

    http = session or requests
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": DEFAULT_MARKET_PAGE_SIZE,
        "page": 1,
        "sparkline": "false",
    }
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    response = None
    for attempt in range(3):
        response = http.get(COINGECKO_MARKETS_URL, params=params, headers=headers, timeout=10)
        if response.status_code != 429:
            break
        time.sleep(2 * (2**attempt))

    if response is None:
        raise UniverseProviderError("CoinGecko request was not executed")
    if response.status_code == 429:
        raise UniverseProviderError("CoinGecko rate limit reached after 3 retries")
    if response.status_code >= 400:
        raise UniverseProviderError(f"CoinGecko returned HTTP {response.status_code}")

    raw_assets = response.json()
    if not isinstance(raw_assets, list):
        raise UniverseProviderError("CoinGecko returned an unexpected payload")

    assets, warnings = filter_market_assets(
        raw_assets,
        universe_size=universe_size,
        exclude_stablecoins=exclude_stablecoins,
        exclude_wrapped=True,
    )

    return {
        "source": "coingecko",
        "count": universe_size,
        "actual_count": len(assets),
        "filters": [
            "market_cap_not_null",
            "exclude_stablecoins" if exclude_stablecoins else "include_stablecoins",
            "exclude_wrapped_assets",
        ],
        "assets": assets,
        "warnings": warnings,
    }
