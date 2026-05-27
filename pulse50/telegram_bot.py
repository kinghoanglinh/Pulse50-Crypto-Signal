"""Telegram bot layer for Pulse50.

This module does not change the Swarms tool entrypoint. Anyone can deploy the
bot with their own `TELEGRAM_BOT_TOKEN`; no chat allowlist is enforced.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pulse50.config import NOT_ADVICE, TELEGRAM_BOT_TOKEN, TELEGRAM_DEFAULT_UNIVERSE_SIZE
from pulse50.main import analyze_pulse50_crypto_signals

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:  # pragma: no cover - import behavior is environment-specific
    Update = None
    Application = None
    CommandHandler = None
    ContextTypes = None


HELP_TEXT = """Pulse50 commands:
/scan - run a top signal scan
/top [n] - show top n signals
/coin SYMBOL - show one coin signal
/status - show provider and runtime status
/help - show commands

Research signal only. Not financial, investment, or trading advice."""


def build_application(token: str | None = None):
    """Build a python-telegram-bot Application."""
    if Application is None or CommandHandler is None:
        raise RuntimeError("python-telegram-bot is not installed")
    bot_token = token or TELEGRAM_BOT_TOKEN
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("status", status_command))
    return app


async def start_command(update, context) -> None:
    await _reply(update, "Pulse50 is online.\n\n" + HELP_TEXT)


async def help_command(update, context) -> None:
    await _reply(update, HELP_TEXT)


async def scan_command(update, context) -> None:
    response = await _run_scan()
    await _reply(update, format_scan_response(response, limit=5))


async def top_command(update, context) -> None:
    limit = _parse_limit(context.args, default=5)
    response = await _run_scan()
    await _reply(update, format_scan_response(response, limit=limit))


async def coin_command(update, context) -> None:
    if not context.args:
        await _reply(update, "Usage: /coin SOL")
        return
    symbol = context.args[0].upper()
    response = await _run_scan()
    await _reply(update, format_coin_response(response, symbol))


async def status_command(update, context) -> None:
    response = await _run_scan(universe_size=3)
    await _reply(update, format_status_response(response))


async def _run_scan(universe_size: int | None = None) -> dict[str, Any]:
    size = universe_size or TELEGRAM_DEFAULT_UNIVERSE_SIZE
    return await asyncio.to_thread(
        analyze_pulse50_crypto_signals,
        universe_size=size,
        _log_predictions=False,
    )


async def _reply(update, text: str) -> None:
    await update.effective_message.reply_text(text[:3900])


def _parse_limit(args: list[str], default: int) -> int:
    if not args:
        return default
    try:
        return max(1, min(20, int(args[0])))
    except ValueError:
        return default


def format_scan_response(response: dict[str, Any], limit: int = 5) -> str:
    signals = [signal for signal in response.get("signals", []) if not signal.get("suppressed")]
    if not signals:
        return "Pulse50 scan complete.\nNo active signals passed quality controls.\n\n" + NOT_ADVICE

    lines = ["Pulse50 Top Signals", ""]
    for signal in signals[:limit]:
        provider = signal.get("provider", {})
        lines.extend(
            [
                f"{signal['rank']}. {signal['symbol']} {signal['direction']} | p_up {signal['probability_up']:.0%}",
                f"Confidence: {signal['confidence']} | Risk: {signal['risk_tier']}",
                f"Provider: {provider.get('provider_used')} | Liquidity: {provider.get('liquidity_quality')}",
                f"Invalidation: {signal.get('invalidation_level')}",
                "",
            ]
        )
    lines.append(NOT_ADVICE)
    return "\n".join(lines)


def format_coin_response(response: dict[str, Any], symbol: str) -> str:
    for signal in response.get("signals", []):
        if signal.get("symbol") == symbol:
            provider = signal.get("provider", {})
            rationale = "; ".join(signal.get("rationale", []))
            return "\n".join(
                [
                    f"Pulse50 {symbol}",
                    f"Direction: {signal['direction']} | p_up {signal['probability_up']:.0%}",
                    f"Confidence: {signal['confidence']} | Risk: {signal['risk_tier']}",
                    f"Provider: {provider.get('provider_used')} | Quality: {signal.get('data_quality')}",
                    f"Invalidation: {signal.get('invalidation_level')}",
                    f"Rationale: {rationale}",
                    "",
                    NOT_ADVICE,
                ]
            )
    return f"No signal found for {symbol}. Try /scan or increase TELEGRAM_DEFAULT_UNIVERSE_SIZE."


def format_status_response(response: dict[str, Any]) -> str:
    metrics = response.get("run_metrics", {})
    sources = response.get("data_sources", [])
    source_text = ", ".join(
        f"{item.get('provider_used')}:{item.get('coverage_score')}" for item in sources
    ) or "none"
    return "\n".join(
        [
            "Pulse50 Status",
            f"Model: {response.get('model_version')}",
            f"Universe: {response.get('universe', {}).get('actual_count')} assets",
            f"Sources: {source_text}",
            f"Runtime: {metrics.get('total_run_time_seconds')}s",
            f"Warnings: {len(response.get('warnings', []))}",
        ]
    )


def main() -> None:
    app = build_application()
    app.run_polling()


if __name__ == "__main__":
    main()
