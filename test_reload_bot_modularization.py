from __future__ import annotations

from types import SimpleNamespace

from reload_bot.modules import admin_logs, admin_moderation, admin_settings, donate, promo
from reload_bot.runtime import BotRuntime


class FakeApplication:
    def __init__(self):
        self.handlers = []

    def add_handler(self, handler, group=0):
        self.handlers.append((group, handler))


def build_runtime() -> BotRuntime:
    async def _async_noop(*args, **kwargs):
        return None

    return BotRuntime(
        db=SimpleNamespace(),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        t=lambda lang, key: f"{lang}:{key}",
        has_creator_panel_access=lambda *args, **kwargs: True,
        has_admin_level=lambda *args, **kwargs: True,
        safe_format_timestamp=lambda *args, **kwargs: "ts",
        parse_duration_to_seconds=lambda value: 3600,
        format_duration_compact=lambda value: "1h",
        resolve_user_identifier=lambda value: 123,
        format_player_label=lambda user_id, username=None, display_name=None: f"user:{user_id}",
        promo_kind_options=[("coins", "coins")],
        donate_options=[{"stars": 5, "label": "5"}],
        rarities={"basic": {}},
        rarity_order=["basic"],
        color_emojis={"basic": "⭐"},
        promo_announcement_chat="@chat",
        promo_announcement_link="https://t.me/chat",
        search_cooldown_default=1,
        daily_bonus_cooldown_default=2,
        auto_search_daily_limit_default=3,
        casino_win_prob_default=0.4,
        plantation_fertilizer_max_per_bed_default=4,
        plantation_neg_event_interval_sec_default=5,
        plantation_neg_event_chance_default=0.1,
        plantation_neg_event_max_active_default=0.2,
        plantation_neg_event_duration_sec_default=6,
        handlers={
            "promo_command": _async_noop,
            "promo_button_start": _async_noop,
            "promo_button_cancel": _async_noop,
            "show_admin_promo_menu": _async_noop,
            "admin_promo_wizard_start": _async_noop,
            "admin_promo_create_start": _async_noop,
            "admin_promo_list_active_show": _async_noop,
            "admin_promo_list_all_show": _async_noop,
            "admin_promo_deactivate_start": _async_noop,
            "admin_promo_stats_show": _async_noop,
            "promo_wiz_cancel": _async_noop,
            "promo_wiz_confirm": _async_noop,
            "admin_promo_deactivate_pick_show": _async_noop,
            "promo_wiz_delivery_select": _async_noop,
            "promo_wiz_kind_select": _async_noop,
            "promo_wiz_rarity_select": _async_noop,
            "promo_wiz_active_select": _async_noop,
            "admin_promo_deactivate_confirm": _async_noop,
            "admin_promo_deactivate_do": _async_noop,
            "handle_promo_create": _async_noop,
            "handle_promo_deactivate": _async_noop,
            "handle_promo_wiz_code": _async_noop,
            "handle_promo_wiz_value": _async_noop,
            "handle_promo_wiz_max_uses": _async_noop,
            "handle_promo_wiz_per_user": _async_noop,
            "handle_promo_wiz_expires": _async_noop,
        },
    )


def test_register_handlers_order_smoke():
    app = FakeApplication()
    runtime = build_runtime()

    donate.register_handlers(app, runtime)
    promo.register_handlers(app, runtime)
    admin_settings.register_handlers(app, runtime)
    admin_moderation.register_handlers(app, runtime)
    admin_logs.register_handlers(app, runtime)

    assert len(app.handlers) == 8


def test_text_action_routing_smoke():
    assert promo.can_handle_text_action("promo_wiz_code")
    assert promo.can_handle_text_action("promo_create")
    assert not promo.can_handle_text_action("settings_set_search_cd")

    assert admin_settings.can_handle_text_action("settings_set_search_cd")
    assert admin_settings.can_handle_text_action("settings_set_casino_luck_mult")
    assert not admin_settings.can_handle_text_action("promo_wiz_value")

    assert admin_moderation.can_handle_text_action("mod_ban")
    assert admin_moderation.can_handle_text_action("warn_clear")
    assert not admin_moderation.can_handle_text_action("settings_set_bonus_cd")

    assert admin_logs.can_handle_text_action("logs_player")
    assert not admin_logs.can_handle_text_action("mod_check")
