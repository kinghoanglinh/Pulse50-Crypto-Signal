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
/scan - quet nhanh top 5 du doan Up/Down 15 phut
/top [n] - xem top n du doan, vi du /top 10
/coin SYMBOL - xem rieng 1 coin, vi du /coin SOL
/status - xem trang thai nguon du lieu/thoi gian chay
/help - xem danh sach lenh

Tin hieu chi dung cho prediction market 15 phut va nghien cuu. Khong phai loi khuyen tai chinh."""

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
        await _reply(update, "Cach dung: /coin SOL")
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
            BotCommand("scan", "Quet nhanh top 5 du doan"),
            BotCommand("top", "Xem top n du doan"),
            BotCommand("coin", "Xem rieng 1 coin"),
            BotCommand("status", "Trang thai bot/nguon data"),
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
        return "Pulse50 da quet xong.\nChua co du doan nao dat quality/risk controls.\n\n" + _vi_disclaimer()

    lines = ["Pulse50 Du Doan Up/Down 15 Phut", ""]
    for signal in signals[:limit]:
        provider = signal.get("provider", {})
        side = _prediction_side(signal.get("direction"))
        lines.extend(
            [
                f"{signal['rank']}. {signal['symbol']} | Du doan: {side}",
                f"Xac suat tang: {signal['probability_up']:.0%}",
                f"Gia realtime: {_fmt_price(signal.get('current_price'))}",
                f"Gia CMC tham chieu: {_fmt_price(signal.get('reference_price_cmc'))}",
                f"Moc gia ky vong: {_fmt_price(_target_price(signal))}",
                f"Moc vo hieu du doan: {_fmt_price(signal.get('invalidation_level'))}",
                f"Do tin cay: {_vi_confidence(signal['confidence'])} | Rui ro: {_vi_risk(signal['risk_tier'])}",
                f"Nguon realtime: {_vi_provider(provider.get('provider_used'))} | Do tre: {_fmt_age(provider.get('data_freshness_seconds'))}",
                f"Thanh khoan: {_vi_liquidity(provider.get('liquidity_quality'))}",
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
                    f"Du doan 15 phut: {_prediction_side(signal['direction'])}",
                    f"Xac suat tang: {signal['probability_up']:.0%}",
                    f"Gia realtime: {_fmt_price(signal.get('current_price'))}",
                    f"Gia CMC tham chieu: {_fmt_price(signal.get('reference_price_cmc'))}",
                    f"Moc gia ky vong: {_fmt_price(_target_price(signal))}",
                    f"Moc vo hieu du doan: {_fmt_price(signal.get('invalidation_level'))}",
                    f"Do tin cay: {_vi_confidence(signal['confidence'])} | Rui ro: {_vi_risk(signal['risk_tier'])}",
                    f"Nguon realtime: {_vi_provider(provider.get('provider_used'))} | Do tre: {_fmt_age(provider.get('data_freshness_seconds'))}",
                    f"Chat luong data: {_vi_data_quality(signal.get('data_quality'))}",
                    f"Ly do: {_vi_rationale(rationale)}",
                    "",
                    _vi_disclaimer(),
                ]
            )
    return f"Khong tim thay tin hieu cho {symbol}. Thu /scan hoac tang TELEGRAM_DEFAULT_UNIVERSE_SIZE."


def format_status_response(response: dict[str, Any]) -> str:
    metrics = response.get("run_metrics", {})
    sources = response.get("data_sources", [])
    source_text = ", ".join(
        f"{_vi_provider(item.get('provider_used'))}:{item.get('coverage_score')}" for item in sources
    ) or "none"
    return "\n".join(
        [
            "Trang thai Pulse50",
            f"Model: {response.get('model_version')}",
            f"So coin quet: {response.get('universe', {}).get('actual_count')}",
            f"Nguon du lieu: {source_text}",
            f"Thoi gian chay: {metrics.get('total_run_time_seconds')}s",
            f"Canh bao: {len(response.get('warnings', []))}",
        ]
    )


def _prediction_side(direction: str | None) -> str:
    return {"UP": "UP", "DOWN": "DOWN", "FLAT": "BO QUA"}.get(str(direction), "BO QUA")


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


def _vi_provider(value: str | None) -> str:
    return {
        "coinapi": "CoinAPI",
        "coingecko": "CoinGecko",
        "binance": "Binance",
        "fixture": "Du lieu test",
        None: "Khong co",
    }.get(value, str(value))


def _vi_data_quality(value: str | None) -> str:
    return {
        "OK": "Tot",
        "no_orderbook": "Thieu order book",
        "stale_cache": "Du lieu cache cu",
        "provider_unavailable": "Khong co nguon du lieu",
        "insufficient_data": "Thieu du lieu",
        None: "Khong ro",
    }.get(value, str(value))


def _vi_rationale(text: str) -> str:
    replacements = {
        "RSI is oversold": "RSI dang qua ban",
        "RSI is overbought": "RSI dang qua mua",
        "MACD momentum is positive": "Dong luc MACD dang tich cuc",
        "MACD momentum is negative": "Dong luc MACD dang tieu cuc",
        "Order book bid imbalance is supportive": "Order book nghieng ve phe mua",
        "Order book ask imbalance is heavy": "Order book nghieng ve phe ban",
        "15m EMA slope is rising": "EMA 15 phut dang doc len",
        "15m EMA slope is falling": "EMA 15 phut dang doc xuong",
        "Short EMA slope is rising": "EMA ngan han dang doc len",
        "Short EMA slope is falling": "EMA ngan han dang doc xuong",
        "15m momentum is positive": "Dong luc 15 phut dang tich cuc",
        "15m momentum is negative": "Dong luc 15 phut dang tieu cuc",
        "Volume is elevated versus recent baseline": "Volume cao hon nen gan day",
        "BTC regime is weak, bullish score suppressed": "BTC dang yeu nen diem UP bi giam",
        "BTC 15m regime is weak, UP score suppressed": "BTC khung 15 phut dang yeu nen diem UP bi giam",
        "Neutral short-horizon feature mix": "Tin hieu ngan han dang trung tinh",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _vi_disclaimer() -> str:
    return "Tin hieu chi dung cho prediction market 15 phut va nghien cuu. Khong phai loi khuyen tai chinh."


def _target_price(signal: dict[str, Any]) -> float | None:
    current_price = signal.get("current_price")
    expected_range = signal.get("expected_return_range_pct") or (None, None)
    direction = signal.get("direction")
    if current_price is None or direction == "FLAT":
        return None
    low_pct, high_pct = expected_range
    if direction == "UP" and high_pct is not None:
        return float(current_price) * (1 + (float(high_pct) / 100))
    if direction == "DOWN" and low_pct is not None:
        return float(current_price) * (1 + (float(low_pct) / 100))
    return None


def _fmt_price(value: Any) -> str:
    if value is None:
        return "Khong co"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number >= 100:
        return f"{number:.2f}"
    if number >= 1:
        return f"{number:.4f}"
    return f"{number:.8f}"


def _fmt_age(value: Any) -> str:
    if value is None:
        return "Khong ro"
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return str(value)
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f} phut"


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
