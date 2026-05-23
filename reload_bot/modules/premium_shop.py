from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from reload_bot.runtime import BotRuntime


CALLBACK_EXACT = {
    "bonus_tg_premium",
    "buy_tg_premium",
    "bonus_steam_game",
    "buy_stars_500",
    "buy_steam_game",
    "vip_menu",
    "vip_plus_menu",
    "vip_1d",
    "vip_7d",
    "vip_30d",
    "vip_plus_1d",
    "vip_plus_7d",
    "vip_plus_30d",
    "buy_vip_1d",
    "buy_vip_7d",
    "buy_vip_30d",
    "confirm_vip_plus_1d",
    "confirm_vip_plus_7d",
    "confirm_vip_plus_30d",
    "buy_vip_plus_1d",
    "buy_vip_plus_7d",
    "buy_vip_plus_30d",
    "stars_menu",
    "stars_500",
}


def can_handle_callback(data: str | None) -> bool:
    return bool(data in CALLBACK_EXACT)


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str | None,
    runtime: BotRuntime,
) -> bool:
    if not can_handle_callback(data):
        return False

    handlers = runtime.handlers
    if data == "bonus_tg_premium":
        await handlers["show_bonus_tg_premium"](update, context)
    elif data == "buy_tg_premium":
        await handlers["buy_tg_premium"](update, context)
    elif data == "bonus_steam_game":
        await handlers["show_bonus_steam_game"](update, context)
    elif data == "buy_stars_500":
        await handlers["buy_stars_500"](update, context)
    elif data == "buy_steam_game":
        await handlers["buy_steam_game"](update, context)
    elif data == "vip_menu":
        await handlers["show_vip_menu"](update, context)
    elif data == "vip_plus_menu":
        await handlers["show_vip_plus_menu"](update, context)
    elif data in {"vip_1d", "vip_7d", "vip_30d"}:
        duration = data.removeprefix("vip_")
        await handlers[f"show_vip_{duration}"](update, context)
    elif data in {"vip_plus_1d", "vip_plus_7d", "vip_plus_30d"}:
        duration = data.removeprefix("vip_plus_")
        await handlers[f"show_vip_plus_{duration}"](update, context)
    elif data in {"buy_vip_1d", "buy_vip_7d", "buy_vip_30d"}:
        duration = data.removeprefix("buy_vip_")
        await handlers["buy_vip"](update, context, duration)
    elif data in {"confirm_vip_plus_1d", "confirm_vip_plus_7d", "confirm_vip_plus_30d"}:
        duration = data.removeprefix("confirm_vip_plus_")
        await handlers["confirm_vip_plus_purchase"](update, context, duration)
    elif data in {"buy_vip_plus_1d", "buy_vip_plus_7d", "buy_vip_plus_30d"}:
        duration = data.removeprefix("buy_vip_plus_")
        await handlers["buy_vip_plus"](update, context, duration)
    elif data == "stars_menu":
        await handlers["show_stars_menu"](update, context)
    elif data == "stars_500":
        await handlers["show_stars_500"](update, context)
    return True
