from __future__ import annotations

from functools import partial

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from reload_bot.runtime import BotRuntime


TEXT_ACTION_TO_HANDLER = {
    "promo_create": "handle_promo_create",
    "promo_deactivate": "handle_promo_deactivate",
    "promo_wiz_code": "handle_promo_wiz_code",
    "promo_wiz_value": "handle_promo_wiz_value",
    "promo_wiz_max_uses": "handle_promo_wiz_max_uses",
    "promo_wiz_per_user": "handle_promo_wiz_per_user",
    "promo_wiz_expires": "handle_promo_wiz_expires",
}


def _get_handler(runtime: BotRuntime, name: str):
    handler = runtime.handlers.get(name)
    if handler is None:
        raise KeyError(f"Missing promo runtime handler: {name}")
    return handler


async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _get_handler(runtime, "promo_command")(update, context)


async def handle_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    if data == "promo_enter":
        await _get_handler(runtime, "promo_button_start")(update, context)
    elif data == "promo_cancel":
        await _get_handler(runtime, "promo_button_cancel")(update, context)
    elif data == "admin_promo_menu":
        await _get_handler(runtime, "show_admin_promo_menu")(update, context)
    elif data == "admin_promo_wizard":
        await _get_handler(runtime, "admin_promo_wizard_start")(update, context)
    elif data == "admin_promo_create":
        await _get_handler(runtime, "admin_promo_create_start")(update, context)
    elif data == "admin_promo_list_active":
        await _get_handler(runtime, "admin_promo_list_active_show")(update, context)
    elif data == "admin_promo_list_all":
        await _get_handler(runtime, "admin_promo_list_all_show")(update, context)
    elif data == "admin_promo_deactivate":
        await _get_handler(runtime, "admin_promo_deactivate_start")(update, context)
    elif data == "admin_promo_stats":
        await _get_handler(runtime, "admin_promo_stats_show")(update, context)
    elif data == "promo_wiz_cancel":
        await _get_handler(runtime, "promo_wiz_cancel")(update, context)
    elif data == "promo_wiz_confirm":
        await _get_handler(runtime, "promo_wiz_confirm")(update, context)
    elif data.startswith("admin_promo_deactivate_pick"):
        await _get_handler(runtime, "admin_promo_deactivate_pick_show")(update, context)
    elif data.startswith("promo_wiz_delivery:"):
        await _get_handler(runtime, "promo_wiz_delivery_select")(update, context, data.split(":", 1)[1])
    elif data.startswith("promo_wiz_kind:"):
        await _get_handler(runtime, "promo_wiz_kind_select")(update, context, data.split(":", 1)[1])
    elif data.startswith("promo_wiz_rarity:"):
        await _get_handler(runtime, "promo_wiz_rarity_select")(update, context, data.split(":", 1)[1])
    elif data.startswith("promo_wiz_active:"):
        await _get_handler(runtime, "promo_wiz_active_select")(update, context, data.split(":", 1)[1] == "1")
    elif data.startswith("promo_deact:"):
        await _get_handler(runtime, "admin_promo_deactivate_confirm")(update, context, int(data.split(":", 1)[1]))
    elif data.startswith("promo_deact_do:"):
        await _get_handler(runtime, "admin_promo_deactivate_do")(update, context, int(data.split(":", 1)[1]))


def can_handle_text_action(action: str | None) -> bool:
    return bool(action in TEXT_ACTION_TO_HANDLER)


async def handle_text_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
    text_input: str,
    runtime: BotRuntime,
) -> bool:
    handler_name = TEXT_ACTION_TO_HANDLER.get(action)
    if not handler_name:
        return False
    await _get_handler(runtime, handler_name)(update, context, text_input)
    return True


def register_handlers(application, runtime: BotRuntime) -> None:
    application.add_handler(CommandHandler("promo", partial(promo_command, runtime=runtime)))
    application.add_handler(
        CallbackQueryHandler(
            partial(handle_promo_callback, runtime=runtime),
            pattern=r"^(promo_enter|promo_cancel|admin_promo_|promo_wiz_|promo_deact:|promo_deact_do:)",
        )
    )
