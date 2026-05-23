from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from reload_bot.runtime import BotRuntime


CALLBACK_EXACT = {
    "settings",
    "settings_lang",
    "settings_quick_access",
    "settings_reminder",
    "settings_auto",
    "settings_autosell",
    "settings_reset",
    "lang_ru",
    "lang_en",
    "reset_yes",
    "reset_no",
    "group_toggle_notify",
    "group_toggle_delete",
}

CALLBACK_PREFIXES = (
    "quick_access_set:",
    "autosell_toggle_",
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
    data = data or (update.callback_query.data if update.callback_query else "")
    if not can_handle_callback(data):
        return False

    handlers = runtime.handlers
    if data == "settings":
        await handlers["show_settings"](update, context)
    elif data == "settings_lang":
        await handlers["settings_lang_menu"](update, context)
    elif data == "settings_quick_access":
        await handlers["show_settings_quick_access"](update, context)
    elif data.startswith("quick_access_set:"):
        await handlers["set_quick_access_target"](update, context, data.split(":", 1)[1])
    elif data == "settings_reminder":
        await handlers["toggle_reminder"](update, context)
    elif data == "settings_auto":
        await handlers["toggle_auto_search"](update, context)
    elif data == "settings_autosell":
        await handlers["show_autosell_menu"](update, context)
    elif data.startswith("autosell_toggle_"):
        rarity = data.removeprefix("autosell_toggle_")
        await handlers["toggle_autosell_rarity"](update, context, rarity)
    elif data == "settings_reset":
        await handlers["reset_prompt"](update, context)
    elif data == "lang_ru":
        await handlers["set_language"](update, context, "ru")
    elif data == "lang_en":
        await handlers["set_language"](update, context, "en")
    elif data == "reset_yes":
        await handlers["reset_confirm"](update, context, True)
    elif data == "reset_no":
        await handlers["reset_confirm"](update, context, False)
    elif data == "group_toggle_notify":
        await handlers["toggle_group_notifications"](update, context)
    elif data == "group_toggle_delete":
        await handlers["toggle_group_auto_delete"](update, context)
    return True
