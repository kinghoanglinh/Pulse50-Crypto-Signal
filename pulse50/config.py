"""Configuration and environment variable access for Pulse50."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY", "")
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")

DEFAULT_UNIVERSE_SIZE = 50
DEFAULT_QUOTE_ASSET = "USDT"
DEFAULT_HORIZON_MINUTES = 5
MODEL_VERSION = "v1.0-rules"
NOT_ADVICE = (
    "Research signal only. Not financial, investment, or trading advice. "
    "Past signals do not guarantee future results."
)
