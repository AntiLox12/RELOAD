"""Centralized admin permission matrix and helpers for the bot."""

from __future__ import annotations

import database as db
from constants import ADMIN_USERNAMES


def get_effective_admin_level(user_id: int, username: str | None) -> int:
    """Return effective level: Creator=99, admin=1..3, regular user=0."""
    if username and username in ADMIN_USERNAMES:
        return 99
    return db.get_admin_level(user_id)


def has_admin_level(user_id: int, username: str | None, min_level: int) -> bool:
    return get_effective_admin_level(user_id, username) >= int(min_level)


def has_admin_panel_access(user_id: int, username: str | None) -> bool:
    """Admin panel entry for level 1+ and Creator."""
    return has_admin_level(user_id, username, 1)


def has_creator_panel_access(user_id: int, username: str | None) -> bool:
    """Full admin access for Creator or level 3 admin."""
    return has_admin_level(user_id, username, 3)


# Levels: 1 = overview, 2 = moderation, 3 = operations, 99 = Creator only
ADMIN_CALLBACK_LEVELS: dict[str, int] = {
    # Entry and overview
    "creator_panel": 1,
    "admin_bot_stats": 1,
    "admin_analytics": 1,
    "admin_analytics_export": 1,
    "admin_logs_menu": 1,
    # Moderation
    "admin_moderation_menu": 2,
    # Full operations (lvl 3+)
    "admin_grants_menu": 3,
    "admin_players_menu": 3,
    "admin_players_list": 3,
    "admin_players_top": 3,
    "admin_vip_menu": 3,
    "admin_stock_menu": 3,
    "admin_broadcast_menu": 3,
    "admin_broadcast_start": 3,
    "admin_drinks_menu": 3,
    "admin_promo_menu": 3,
    "admin_promo_wizard": 3,
    "admin_economy_menu": 3,
    "admin_events_menu": 3,
    "admin_settings_menu": 3,
    "creator_reset_bonus": 3,
    "creator_give_coins": 3,
    "creator_user_stats": 3,
    "creator_admins": 3,
    # Creator only
    "creator_wipe": 99,
    "creator_wipe_confirm": 99,
}


ADMIN_CALLBACK_PREFIX_LEVELS: list[tuple[str, int]] = [
    ("admin_logs_", 1),
    ("admin_mod_", 2),
    ("admin_warn_", 2),
    ("creator_admin_", 3),
    ("admin_player_", 3),
    ("admin_drink_", 3),
    ("admin_promo_", 3),
    ("admin_settings_", 3),
    ("admin_econ_", 3),
    ("admin_event_", 3),
    ("promo_wiz_", 3),
    ("promo_deact:", 3),
    ("promo_deact_do:", 3),
    ("drink_confirm_", 3),
    ("drink_cancel_", 3),
]


ADMIN_TEXT_ACTION_LEVELS: dict[str, int] = {
    "logs_player": 1,
    "mod_ban": 2,
    "mod_unban": 2,
    "mod_check": 2,
    "warn_add": 2,
    "warn_list": 2,
    "warn_clear": 2,
    # Default for other awaiting_admin_action values is level 3
}


CREATOR_TEXT_ACTION_LEVELS: dict[str, int] = {
    "reset_bonus": 3,
    "give_coins": 3,
    "user_stats": 3,
    "admin_add": 3,
    "admin_promote": 3,
    "admin_demote": 3,
    "admin_remove": 3,
    "vip_give": 3,
    "vip_plus_give": 3,
    "vip_remove": 3,
    "vip_plus_remove": 3,
    "broadcast": 3,
    "player_search": 3,
}


def get_required_level_for_callback(callback_data: str) -> int | None:
    level = ADMIN_CALLBACK_LEVELS.get(callback_data)
    if level is not None:
        return level
    for prefix, prefix_level in ADMIN_CALLBACK_PREFIX_LEVELS:
        if callback_data.startswith(prefix):
            return prefix_level
    return None
