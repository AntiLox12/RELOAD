from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from reload_bot.runtime import BotRuntime


CALLBACK_EXACT = {
    "market_receiver",
    "receiver_by_quantity",
    "my_receipts",
    "sell_all_confirm_1",
    "sell_all_confirm_2",
    "sell_all_execute",
    "sell_absolutely_all_but_one",
    "receiver_sell_by_rarity",
}

CALLBACK_PREFIXES = (
    "receiver_qty_p",
    "receiver_item_sell:",
    "sellall_",
    "sellallbutone_",
    "sell_",
    "view_receipt_",
    "view_",
    "rec_sell_rar_conf_",
    "rec_sell_rar_exec_",
)


def can_handle_callback(data: str | None) -> bool:
    if not data:
        return False
    return data in CALLBACK_EXACT or data.startswith(CALLBACK_PREFIXES)


async def _answer_error(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("Ошибка", show_alert=True)


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str | None,
    runtime: BotRuntime,
) -> bool:
    data = data or (update.callback_query.data if update.callback_query else "")
    if not can_handle_callback(data):
        return False

    handlers = runtime.handlers
    if data == "market_receiver":
        await handlers["show_market_receiver"](update, context)
    elif data == "receiver_by_quantity":
        await handlers["show_inventory_by_quantity"](update, context)
    elif data.startswith("receiver_qty_p"):
        await handlers["show_inventory_by_quantity"](update, context)
    elif data.startswith("receiver_item_sell:"):
        try:
            _, item_key, quantity_token = data.split(":", 2)
            await handlers["handle_receiver_item_sell"](update, context, item_key, quantity_token)
        except Exception:
            await _answer_error(update)
    elif data == "receiver_sell_by_rarity":
        await handlers["show_receiver_sell_by_rarity"](update, context)
    elif data.startswith("rec_sell_rar_conf_"):
        await handlers["confirm_receiver_sell_rarity"](update, context)
    elif data.startswith("rec_sell_rar_exec_"):
        await handlers["execute_receiver_sell_rarity"](update, context)
    elif data == "my_receipts":
        await handlers["my_receipts_handler"](update, context)
    elif data == "sell_all_confirm_1":
        await handlers["receiver_sell_all_confirm_1"](update, context)
    elif data == "sell_all_confirm_2":
        await handlers["receiver_sell_all_confirm_2"](update, context)
    elif data == "sell_all_execute":
        await handlers["handle_sell_all_inventory"](update, context)
    elif data.startswith("sellall_"):
        try:
            item_id = int(data.split("_")[1])
            await handlers["handle_sell_action"](update, context, item_id, sell_all=True)
        except Exception:
            await _answer_error(update)
    elif data.startswith("sellallbutone_"):
        try:
            item_id = int(data.split("_")[1])
            await handlers["handle_sell_all_but_one"](update, context, item_id)
        except Exception:
            await _answer_error(update)
    elif data == "sell_absolutely_all_but_one":
        await handlers["handle_sell_absolutely_all_but_one"](update, context)
    elif data.startswith("sell_"):
        try:
            item_id = int(data.split("_")[1])
            await handlers["handle_sell_action"](update, context, item_id, sell_all=False)
        except Exception:
            await _answer_error(update)
    elif data.startswith("view_receipt_"):
        await handlers["view_receipt_handler"](update, context)
    elif data.startswith("view_"):
        await handlers["view_inventory_item"](update, context)
    return True
