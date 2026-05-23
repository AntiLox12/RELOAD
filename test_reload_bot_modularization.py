from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from gift_system import GiftFeature
import ordinary_plantation
from reload_bot.modules import admin_logs, admin_moderation, admin_settings, casino, donate, inventory, premium_shop, promo, receiver, swaga, user_settings
from reload_bot.runtime import BotRuntime
from telegram.ext import CallbackQueryHandler, CommandHandler


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


def build_gift_feature(logger=None) -> GiftFeature:
    async def _not_banned(*args, **kwargs):
        return False

    async def _async_noop(*args, **kwargs):
        return None

    return GiftFeature(
        logger=logger or SimpleNamespace(exception=lambda *args, **kwargs: None),
        abort_if_banned=_not_banned,
        register_group_if_needed=_async_noop,
        reply_auto_delete_message=_async_noop,
        schedule_auto_delete_message=_async_noop,
        get_rarity_emoji=lambda rarity: "*",
        get_lock=lambda key: asyncio.Lock(),
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


def test_gift_feature_registers_own_handlers():
    app = FakeApplication()
    feature = build_gift_feature()

    feature.register_handlers(app)

    handlers = [handler for _, handler in app.handlers]
    assert len(handlers) == 3
    assert sum(isinstance(handler, CommandHandler) for handler in handlers) == 2
    assert sum(isinstance(handler, CallbackQueryHandler) for handler in handlers) == 1


def test_gift_page_info_callback_is_not_parsed_as_page_number():
    class FailingLogger:
        def exception(self, *args, **kwargs):
            raise AssertionError("gift_page_info should not hit the generic callback error branch")

    feature = build_gift_feature(logger=FailingLogger())
    query = SimpleNamespace(
        data="gift_page_info",
        answer=AsyncMock(),
        from_user=SimpleNamespace(id=123),
        message=SimpleNamespace(message_id=456),
    )
    update = SimpleNamespace(callback_query=query)

    handled = asyncio.run(feature.handle_callback(update, SimpleNamespace()))

    assert handled is True
    query.answer.assert_awaited_once()


def test_ordinary_plantation_callback_boundaries():
    assert ordinary_plantation.can_handle_callback("market_plantation")
    assert ordinary_plantation.can_handle_callback("plantation_harvest_bed_1")
    assert ordinary_plantation.can_handle_callback("fert_apply_do_1_2")
    assert ordinary_plantation.can_handle_callback("snooze_remind_3")

    assert not ordinary_plantation.can_handle_callback("seed_coupon_shop_open:boosts")
    assert not ordinary_plantation.can_handle_callback("market_shop")


def test_swaga_callback_boundaries_and_commands():
    app = FakeApplication()

    swaga.register_handlers(app)

    handlers = [handler for _, handler in app.handlers]
    assert len(handlers) == 7
    assert sum(isinstance(handler, CommandHandler) for handler in handlers) == 6

    assert swaga.can_handle_callback("swaga_shop")
    assert swaga.can_handle_callback("swaga_admin_tracks")
    assert swaga.can_handle_callback("swaga_upgrade_Legendary_5_2")
    assert swaga.can_handle_callback("swaga_recent_tracks_page_2")
    assert not swaga.can_handle_callback("swagashop")
    assert not swaga.can_handle_callback("swaga")
    assert not swaga.can_handle_callback("menu")


def test_casino_callback_boundaries_and_noop_ack():
    assert casino.can_handle_callback("city_casino")
    assert casino.can_handle_callback("casino_game_blackjack")
    assert casino.can_handle_callback("casino_choice_roulette_color_red")
    assert casino.can_handle_callback("blackjack_hit")
    assert casino.can_handle_callback("mines_click_3")
    assert casino.can_handle_callback("crash_cashout")

    assert not casino.can_handle_callback("city_powerlines")
    assert not casino.can_handle_callback("casino")
    assert not casino.can_handle_callback("blackjack")

    query = SimpleNamespace(data="mines_noop", answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    runtime = SimpleNamespace(handlers={}, logger=SimpleNamespace(error=lambda *args, **kwargs: None), db=SimpleNamespace())

    handled = asyncio.run(casino.handle_callback(update, SimpleNamespace(), "mines_noop", runtime))

    assert handled is True
    query.answer.assert_awaited_once()


def test_premium_shop_callback_boundaries_and_duration_routing():
    calls = []

    async def _record(*args):
        calls.append(args)

    runtime = SimpleNamespace(
        handlers={
            "buy_vip": _record,
            "show_bonus_tg_premium": _record,
        }
    )
    update = SimpleNamespace()
    context = SimpleNamespace()

    assert premium_shop.can_handle_callback("vip_menu")
    assert premium_shop.can_handle_callback("buy_vip_30d")
    assert premium_shop.can_handle_callback("confirm_vip_plus_7d")
    assert premium_shop.can_handle_callback("stars_500")
    assert not premium_shop.can_handle_callback("vip")
    assert not premium_shop.can_handle_callback("buy_vip")
    assert not premium_shop.can_handle_callback("donate_menu")

    handled = asyncio.run(premium_shop.handle_callback(update, context, "buy_vip_30d", runtime))

    assert handled is True
    assert calls == [(update, context, "30d")]


def test_receiver_callback_boundaries_and_sell_routing():
    calls = []

    async def _sell_action(*args, **kwargs):
        calls.append((args, kwargs))

    runtime = SimpleNamespace(handlers={"handle_sell_action": _sell_action})
    query = SimpleNamespace(data="sell_42", answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace()

    assert receiver.can_handle_callback("market_receiver")
    assert receiver.can_handle_callback("receiver_qty_p2")
    assert receiver.can_handle_callback("receiver_item_sell:Basic:all")
    assert receiver.can_handle_callback("sellall_42")
    assert receiver.can_handle_callback("sellallbutone_42")
    assert receiver.can_handle_callback("view_receipt_5")
    assert receiver.can_handle_callback("view_5")
    assert not receiver.can_handle_callback("approve_5")
    assert not receiver.can_handle_callback("market_shop")

    handled = asyncio.run(receiver.handle_callback(update, context, "sell_42", runtime))

    assert handled is True
    assert calls == [((update, context, 42), {"sell_all": False})]


def test_user_settings_callback_boundaries_and_payload_routing():
    calls = []

    async def _set_quick_access(*args):
        calls.append(args)

    runtime = SimpleNamespace(handlers={"set_quick_access_target": _set_quick_access})
    update = SimpleNamespace()
    context = SimpleNamespace()

    assert user_settings.can_handle_callback("settings")
    assert user_settings.can_handle_callback("settings_lang")
    assert user_settings.can_handle_callback("quick_access_set:market_receiver")
    assert user_settings.can_handle_callback("autosell_toggle_Basic")
    assert user_settings.can_handle_callback("group_toggle_delete")
    assert not user_settings.can_handle_callback("settings_plantation_reminder")
    assert not user_settings.can_handle_callback("admin_settings_menu")

    handled = asyncio.run(
        user_settings.handle_callback(update, context, "quick_access_set:market_receiver", runtime)
    )

    assert handled is True
    assert calls == [(update, context, "market_receiver")]


def test_inventory_callback_boundaries_and_search_page_routing():
    calls = []

    async def _show_results(*args):
        calls.append(args)

    runtime = SimpleNamespace(handlers={"show_inventory_search_results": _show_results})
    query = SimpleNamespace(data="inventory_search_p3", answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={"last_inventory_search": "cola"})

    assert inventory.can_handle_callback("find_energy")
    assert inventory.can_handle_callback("claim_bonus")
    assert inventory.can_handle_callback("inventory_p2")
    assert inventory.can_handle_callback("inventory_search_p3")
    assert not inventory.can_handle_callback("receiver_qty_p2")
    assert not inventory.can_handle_callback("my_profile")

    handled = asyncio.run(inventory.handle_callback(update, context, "inventory_search_p3", runtime))

    assert handled is True
    assert calls == [(update, context, "cola", 3)]


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
