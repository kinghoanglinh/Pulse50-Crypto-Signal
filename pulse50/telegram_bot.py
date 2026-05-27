"""Telegram bot layer for Pulse50.

This module does not change the Swarms tool entrypoint. Anyone can deploy the
bot with their own `TELEGRAM_BOT_TOKEN`; no chat allowlist is enforced.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pulse50.config import NOT_ADVICE, TELEGRAM_BOT_TOKEN, TELEGRAM_DEFAULT_UNIVERSE_SIZE
from pulse50.main import analyze_pulse50_crypto_signals

try:
    from telegram import BotCommand, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:  # pragma: no cover - import behavior is environment-specific
    BotCommand = None
    Update = None
    Application = None
    CommandHandler = None
    ContextTypes = None


HELP_TEXT = """Lenh Pulse50:
/scan - quet nhanh top 5 keo
/top [n] - xem top n keo, vi du /top 10
/coin SYMBOL - xem rieng 1 coin, vi du /coin SOL
/status - xem trang thai provider/runtime
/help - xem danh sach lenh

Tin hieu chi dung cho nghien cuu. Khong phai loi khuyen tai chinh hay lenh vao vi the."""

logger = logging.getLogger(__name__)


def build_application(token: str | None = None):
    """Build a python-telegram-bot Application."""
    if Application is None or CommandHandler is None:
        raise RuntimeError("python-telegram-bot is not installed")
    bot_token = token or TELEGRAM_BOT_TOKEN
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    app = Application.builder().token(bot_token).post_init(set_bot_commands).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_error_handler(error_handler)
    return app


async def start_command(update, context) -> None:
    await _reply(update, "Pulse50 da san sang.\n\n" + HELP_TEXT)


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
    logger.info("Replying to chat_id=%s", update.effective_chat.id if update.effective_chat else "unknown")
    await update.effective_message.reply_text(text[:3900])


async def error_handler(update: object, context) -> None:
    logger.exception("Telegram handler failed. update=%s", update, exc_info=context.error)


async def set_bot_commands(app) -> None:
    if BotCommand is None:
        return
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Bat dau dung Pulse50"),
            BotCommand("scan", "Quet nhanh top 5 keo"),
            BotCommand("top", "Xem top n keo"),
            BotCommand("coin", "Xem rieng 1 coin"),
            BotCommand("status", "Trang thai bot/provider"),
            BotCommand("help", "Huong dan lenh"),
        ]
    )


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
        return "Pulse50 da quet xong.\nChua co keo nao dat quality/risk controls.\n\n" + _vi_disclaimer()

    lines = ["Pulse50 Top Keo 5 Phut", ""]
    for signal in signals[:limit]:
        provider = signal.get("provider", {})
        side = _trade_side(signal.get("direction"))
        lines.extend(
            [
                f"{signal['rank']}. {signal['symbol']} | {side} | p_up {signal['probability_up']:.0%}",
                f"Do tin cay: {_vi_confidence(signal['confidence'])} | Rui ro: {_vi_risk(signal['risk_tier'])}",
                f"Nguon: {provider.get('provider_used')} | Thanh khoan: {_vi_liquidity(provider.get('liquidity_quality'))}",
                f"Gia vo hieu keo: {signal.get('invalidation_level')}",
                "",
            ]
        )
    lines.append(_vi_disclaimer())
    return "\n".join(lines)


def format_coin_response(response: dict[str, Any], symbol: str) -> str:
    for signal in response.get("signals", []):
        if signal.get("symbol") == symbol:
            provider = signal.get("provider", {})
            rationale = "; ".join(signal.get("rationale", []))
            return "\n".join(
                [
                    f"Pulse50 {symbol}",
                    f"Huong: {_trade_side(signal['direction'])} | p_up {signal['probability_up']:.0%}",
                    f"Do tin cay: {_vi_confidence(signal['confidence'])} | Rui ro: {_vi_risk(signal['risk_tier'])}",
                    f"Nguon: {provider.get('provider_used')} | Chat luong data: {signal.get('data_quality')}",
                    f"Gia vo hieu keo: {signal.get('invalidation_level')}",
                    f"Ly do: {rationale}",
                    "",
                    _vi_disclaimer(),
                ]
            )
    return f"Khong tim thay tin hieu cho {symbol}. Thu /scan hoac tang TELEGRAM_DEFAULT_UNIVERSE_SIZE."


def format_status_response(response: dict[str, Any]) -> str:
    metrics = response.get("run_metrics", {})
    sources = response.get("data_sources", [])
    source_text = ", ".join(
        f"{item.get('provider_used')}:{item.get('coverage_score')}" for item in sources
    ) or "none"
    return "\n".join(
        [
            "Trang thai Pulse50",
            f"Model: {response.get('model_version')}",
            f"So coin quet: {response.get('universe', {}).get('actual_count')}",
            f"Nguon data: {source_text}",
            f"Thoi gian chay: {metrics.get('total_run_time_seconds')}s",
            f"Canh bao: {len(response.get('warnings', []))}",
        ]
    )


def _trade_side(direction: str | None) -> str:
    return {"UP": "LONG", "DOWN": "SHORT", "FLAT": "DUNG NGOAI"}.get(str(direction), "DUNG NGOAI")


def _vi_confidence(value: str) -> str:
    return {"High": "Cao", "Medium": "Trung binh", "Low": "Thap"}.get(value, value)


def _vi_risk(value: str) -> str:
    return {"Low": "Thap", "Medium": "Trung binh", "High": "Cao", "Extreme": "Rat cao"}.get(value, value)


def _vi_liquidity(value: str | None) -> str:
    return {
        "excellent": "Rat tot",
        "good": "Tot",
        "fair": "Tam duoc",
        "poor": "Kem",
        "unknown": "Khong ro",
    }.get(str(value), str(value))


def _vi_disclaimer() -> str:
    return "Tin hieu chi dung cho nghien cuu. Khong phai loi khuyen tai chinh hay lenh vao vi the."


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        level=logging.INFO,
    )
    app = build_application()
    logger.info("Starting Pulse50 Telegram bot polling")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
