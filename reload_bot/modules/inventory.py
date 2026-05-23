from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from reload_bot.runtime import BotRuntime


CALLBACK_EXACT = {
    "find_energy",
    "claim_bonus",
    "daily_bonus_info",
    "inventory",
    "inventory_search_start",
    "inventory_search_cancel",
}

CALLBACK_PREFIXES = (
    "inventory_p",
    "inventory_search_p",
)


def can_handle_callback(data: str | None) -> bool:
    if not data:
        return False
    return data in CALLBACK_EXACT or data.startswith(CALLBACK_PREFIXES)


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str | None,
    runtime: BotRuntime,
) -> bool:
    query = update.callback_query
    data = data or (query.data if query else "")
    if not can_handle_callback(data):
        return False

    handlers = runtime.handlers
    if data == "find_energy":
        await handlers["find_energy"](update, context)
    elif data == "claim_bonus":
        await handlers["claim_daily_bonus"](update, context)
    elif data == "daily_bonus_info":
        await handlers["show_daily_bonus_info"](update, context)
    elif data == "inventory":
        await handlers["show_inventory"](update, context)
    elif data.startswith("inventory_p"):
        await handlers["show_inventory"](update, context)
    elif data == "inventory_search_start":
        await handlers["start_inventory_search"](update, context)
    elif data == "inventory_search_cancel":
        await handlers["inventory_search_cancel"](update, context)
    elif data.startswith("inventory_search_p"):
        try:
            page = int(data.removeprefix("inventory_search_p"))
            search_query = context.user_data.get("last_inventory_search", "")
            if search_query:
                await handlers["show_inventory_search_results"](update, context, search_query, page)
            elif query:
                await query.answer("Поисковый запрос не найден. Начните новый поиск.", show_alert=True)
        except Exception:
            if query:
                await query.answer("Ошибка пагинации", show_alert=True)
    return True
