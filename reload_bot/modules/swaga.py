from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from modules.swaga import swaga_admin
from modules.swaga import swagashop


CALLBACK_EXACT = {
    "swaga_shop",
    "swaga_cards_inv",
    "swaga_chests_inv",
    "swaga_tracks_inv",
    "swaga_recent_tracks",
}

CALLBACK_PREFIXES = (
    "swaga_admin_",
    "swaga_exchange_",
    "swaga_upgrade_",
    "swaga_open_",
    "swaga_tracks_page_",
    "swaga_recent_tracks_page_",
    "swaga_play_",
)


def can_handle_callback(data: str | None) -> bool:
    if not data:
        return False
    return data in CALLBACK_EXACT or data.startswith(CALLBACK_PREFIXES)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str | None = None) -> bool:
    data = data or (update.callback_query.data if update.callback_query else "")
    if not can_handle_callback(data):
        return False

    if data == "swaga_shop":
        await swagashop.show_swaga_shop(update, context)
    elif data.startswith("swaga_admin_"):
        await swaga_admin.handle_swaga_admin_callback(update, context)
    elif data == "swaga_cards_inv":
        await swagashop.show_swaga_cards_inv(update, context)
    elif data == "swaga_chests_inv":
        await swagashop.show_swaga_chests_inv(update, context)
    elif data == "swaga_tracks_inv":
        await swagashop.show_swaga_tracks_inv(update, context, page=1)
    elif data == "swaga_recent_tracks":
        await swagashop.show_recent_swaga_tracks(update, context, page=1)
    elif data.startswith("swaga_exchange_"):
        rarity = data.split("swaga_exchange_", 1)[1]
        await swagashop.handle_swaga_exchange(update, context, rarity)
    elif data.startswith("swaga_upgrade_"):
        payload = data.split("swaga_upgrade_", 1)[1]
        parts = payload.rsplit("_", 2)
        if len(parts) == 3:
            rarity, cost, reward_qty = parts
            await swagashop.handle_swaga_upgrade(update, context, rarity, cost=int(cost), reward_qty=int(reward_qty))
        else:
            await swagashop.handle_swaga_upgrade(update, context, payload)
    elif data.startswith("swaga_open_"):
        rarity = data.split("swaga_open_", 1)[1]
        await swagashop.handle_swaga_open_chest(update, context, rarity)
    elif data.startswith("swaga_tracks_page_"):
        page = int(data.split("swaga_tracks_page_", 1)[1])
        await swagashop.show_swaga_tracks_inv(update, context, page=page)
    elif data.startswith("swaga_recent_tracks_page_"):
        page = int(data.split("swaga_recent_tracks_page_", 1)[1])
        await swagashop.show_recent_swaga_tracks(update, context, page=page)
    elif data.startswith("swaga_play_"):
        track_id = int(data.split("swaga_play_", 1)[1])
        await swagashop.handle_swaga_play_track(update, context, track_id)
    return True


def register_handlers(application) -> None:
    application.add_handler(CommandHandler("swagashop", swagashop.show_swaga_shop))
    application.add_handler(CommandHandler("swagainv", swagashop.show_swaga_shop))
    application.add_handler(swaga_admin.addswaga_conv_handler)
    application.add_handler(CommandHandler("giveswagacards", swaga_admin.giveswagacards_command))
    application.add_handler(CommandHandler(["swagaid", "swagalist", "swagatracks"], swaga_admin.swagaid_command))
    application.add_handler(CommandHandler(["swagaedit", "editswaga", "editswagatrack"], swaga_admin.swagaedit_command))
    application.add_handler(CommandHandler(["swagadel", "delswaga", "delswagatrack"], swaga_admin.swagadel_command))
