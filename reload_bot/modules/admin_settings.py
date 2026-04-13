from __future__ import annotations

from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes

from reload_bot.runtime import BotRuntime


TEXT_ACTIONS = {
    "settings_set_search_cd",
    "settings_set_bonus_cd",
    "settings_set_auto_base",
    "settings_set_auto_vip_mult",
    "settings_set_auto_vip_plus_mult",
    "settings_set_gift_limit",
    "settings_set_gift_duration",
    "settings_set_fertilizer_max",
    "settings_set_neg_interval",
    "settings_set_neg_chance",
    "settings_set_neg_max_active",
    "settings_set_neg_duration",
    "settings_set_casino_win_prob",
    "settings_set_casino_luck_mult",
}


def can_handle_text_action(action: str | None) -> bool:
    return bool(action in TEXT_ACTIONS)


async def show_admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("⏱️ Кулдауны", callback_data="admin_settings_cooldowns")],
        [InlineKeyboardButton("🤖 Автопоиск", callback_data="admin_settings_autosearch")],
        [InlineKeyboardButton("🎁 Gift-защита", callback_data="admin_settings_gift_protection")],
        [InlineKeyboardButton("💰 Лимиты", callback_data="admin_settings_limits")],
        [InlineKeyboardButton("🎰 Настройки казино", callback_data="admin_settings_casino")],
        [InlineKeyboardButton("🏪 Настройки магазина", callback_data="admin_settings_shop")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="admin_settings_notifications")],
        [InlineKeyboardButton("🌐 Локализация", callback_data="admin_settings_localization")],
        [InlineKeyboardButton("⚠️ Негативные эффекты", callback_data="admin_settings_negative_effects")],
        [InlineKeyboardButton("🔙 Админ панель", callback_data="creator_panel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "Управление параметрами работы бота:\n\n"
        "⏱️ <b>Кулдауны</b> - время ожидания между действиями\n"
        "🤖 <b>Автопоиск</b> - лимиты и коэффициенты VIP/VIP+\n"
        "🎁 <b>Gift-защита</b> - автоблокировки и anti-abuse подарков\n"
        "💰 <b>Лимиты</b> - ограничения на операции\n"
        "🎰 <b>Казино</b> - настройки игр и шансов\n"
        "🏪 <b>Магазин</b> - цены и ассортимент\n"
        "🔔 <b>Уведомления</b> - настройки уведомлений\n"
        "🌐 <b>Локализация</b> - языки интерфейса\n\n"
        "Выберите раздел:"
    )

    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_settings_limits(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    fert_max = max(
        1,
        runtime.db.get_setting_int(
            "plantation_fertilizer_max_per_bed",
            runtime.plantation_fertilizer_max_per_bed_default,
        ),
    )

    text = (
        "💰 <b>Лимиты</b>\n\n"
        f"🌿 Лимит удобрений на грядку: <b>{int(fert_max)}</b>\n\n"
        "Выберите действие:"
    )
    keyboard = [
        [InlineKeyboardButton("🧪 Изменить лимит удобрений", callback_data="admin_settings_set_fertilizer_max")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def admin_settings_set_fertilizer_max_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_limits")]]
    try:
        await query.message.edit_text(
            "Введите новый лимит удобрений на грядку (целое число ≥ 1):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_fertilizer_max"


async def show_admin_settings_negative_effects(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    interval = runtime.db.get_setting_int(
        "plantation_negative_event_interval_sec",
        runtime.plantation_neg_event_interval_sec_default,
    )
    chance = runtime.db.get_setting_float(
        "plantation_negative_event_chance",
        runtime.plantation_neg_event_chance_default,
    )
    max_active = runtime.db.get_setting_float(
        "plantation_negative_event_max_active",
        runtime.plantation_neg_event_max_active_default,
    )
    duration = runtime.db.get_setting_int(
        "plantation_negative_event_duration_sec",
        runtime.plantation_neg_event_duration_sec_default,
    )

    text = (
        "⚠️ <b>Негативные эффекты</b>\n\n"
        f"⏱️ Интервал: <b>{int(interval)}</b> сек.\n"
        f"🎲 Шанс: <b>{round(float(chance) * 100, 2)}%</b>\n"
        f"📉 Лимит активных: <b>{round(float(max_active) * 100, 2)}%</b>\n"
        f"⌛ Длительность: <b>{int(duration)}</b> сек.\n\n"
        "Выберите, что изменить:"
    )
    keyboard = [
        [InlineKeyboardButton("⏱️ Интервал", callback_data="admin_settings_set_neg_interval")],
        [InlineKeyboardButton("🎲 Шанс", callback_data="admin_settings_set_neg_chance")],
        [InlineKeyboardButton("📉 Лимит активных", callback_data="admin_settings_set_neg_max_active")],
        [InlineKeyboardButton("⌛ Длительность", callback_data="admin_settings_set_neg_duration")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def admin_settings_set_neg_interval_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_negative_effects")]]
    try:
        await query.message.edit_text(
            "Введите интервал в секундах (целое число ≥ 60):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_neg_interval"


async def admin_settings_set_neg_chance_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_negative_effects")]]
    try:
        await query.message.edit_text(
            "Введите шанс (0..1 или проценты 1–100):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_neg_chance"


async def admin_settings_set_neg_max_active_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_negative_effects")]]
    try:
        await query.message.edit_text(
            "Введите лимит активных (0..1 или проценты 1–100):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_neg_max_active"


async def admin_settings_set_neg_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_negative_effects")]]
    try:
        await query.message.edit_text(
            "Введите длительность эффекта в секундах (целое число ≥ 60):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_neg_duration"


async def show_admin_settings_autosearch(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    base_limit = runtime.db.get_setting_int("auto_search_daily_limit_base", runtime.auto_search_daily_limit_default)
    vip_mult = runtime.db.get_setting_float("auto_search_vip_daily_mult", 1.0)
    vip_plus_mult = runtime.db.get_setting_float("auto_search_vip_plus_daily_mult", 2.0)

    text = (
        "🤖 <b>Автопоиск — лимиты</b>\n\n"
        f"Базовый дневной лимит: <b>{int(base_limit)}</b>\n"
        f"VIP множитель: <b>{vip_mult}</b>\n"
        f"VIP+ множитель: <b>{vip_plus_mult}</b>\n\n"
        "Выберите, что изменить:"
    )
    keyboard = [
        [InlineKeyboardButton("Изменить базовый лимит", callback_data="admin_settings_set_auto_base")],
        [InlineKeyboardButton("Изменить VIP множитель", callback_data="admin_settings_set_auto_vip_mult")],
        [InlineKeyboardButton("Изменить VIP+ множитель", callback_data="admin_settings_set_auto_vip_plus_mult")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_settings_gift_protection(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
    except BadRequest:
        pass

    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    settings = runtime.db.get_gift_autoblock_settings()
    duration_sec = int(settings["duration_sec"])
    duration_days = round(duration_sec / 86400, 2)
    status_text = "включена" if settings["enabled"] else "выключена"
    toggle_text = "Выключить защиту" if settings["enabled"] else "Включить защиту"

    text = (
        "🎁 <b>Gift-защита</b>\n\n"
        f"Статус: <b>{status_text}</b>\n"
        f"Лимит подряд одному получателю: <b>{int(settings['consecutive_limit'])}</b>\n"
        f"Длительность блокировки: <b>{duration_sec}</b> сек. ({duration_days} дн., {runtime.format_duration_compact(duration_sec)})\n\n"
        "Настройки применяются к автоматической anti-abuse блокировке в системе подарков."
    )
    keyboard = [
        [InlineKeyboardButton(f"🛡️ {toggle_text}", callback_data="admin_settings_gift_toggle")],
        [InlineKeyboardButton("🔢 Изменить лимит подряд", callback_data="admin_settings_set_gift_limit")],
        [InlineKeyboardButton("⏳ Изменить длительность", callback_data="admin_settings_set_gift_duration")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def admin_settings_set_gift_limit_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_gift_protection")]]
    try:
        await query.message.edit_text(
            "Введите новый лимит подряд одному получателю (целое число ≥ 1):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_gift_limit"


async def admin_settings_set_gift_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_gift_protection")]]
    try:
        await query.message.edit_text(
            "Введите длительность gift-блокировки: <code>14d</code>, <code>12h</code> или <code>3600</code>.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_gift_duration"


async def show_admin_settings_casino(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    win_prob = runtime.db.get_setting_float("casino_win_prob", runtime.casino_win_prob_default)
    win_prob = max(0.0, min(1.0, float(win_prob)))
    percent = round(win_prob * 100, 2)
    luck_mult = runtime.db.get_setting_float("casino_luck_mult", 1.0)
    try:
        luck_mult = float(luck_mult)
    except Exception:
        luck_mult = 1.0
    luck_mult = max(0.1, min(5.0, luck_mult))

    text = (
        "🎰 <b>Настройки казино — удача</b>\n\n"
        f"Шанс победы (классические ставки): <b>{percent}%</b>\n"
        f"Внутреннее значение: <b>{win_prob}</b>\n\n"
        f"Множитель удачи (все игры): <b>x{luck_mult}</b>\n\n"
        "Применяется к:\n"
        "• Быстрые ставки в казино\n"
        "• Пользовательские ставки\n\n"
        "• Все игры в казино (общий шанс)\n\n"
        "Выберите действие:"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 Изменить шанс победы", callback_data="admin_settings_set_casino_win_prob")],
        [InlineKeyboardButton("🍀 Множитель удачи", callback_data="admin_settings_set_casino_luck_mult")],
        [InlineKeyboardButton("♻️ Сбросить шанс", callback_data="admin_settings_casino_reset_prob")],
        [InlineKeyboardButton("♻️ Сбросить удачу", callback_data="admin_settings_casino_reset_luck")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def admin_settings_set_casino_win_prob_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_casino")]]
    text = (
        "🎲 <b>Шанс победы в казино</b>\n\n"
        "Введите число:\n"
        "• от 0 до 1 (например, 0.35)\n"
        "• или в процентах 1–99 (например, 35)\n\n"
        "Текущая настройка влияет на классические ставки."
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_casino_win_prob"


async def admin_settings_set_casino_luck_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_casino")]]
    text = (
        "🍀 <b>Множитель удачи в казино</b>\n\n"
        "Увеличивает шанс победы во всех играх.\n"
        "Введите число (например 1.2, 1.5, 2):\n"
        "• 1.0 — без изменений\n"
        "• 1.5 — +50% к шансам\n"
        "• 2.0 — в 2 раза больше\n"
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_casino_luck_mult"


async def admin_settings_set_auto_base_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_autosearch")]]
    try:
        await query.message.edit_text(
            "Введите новый базовый дневной лимит автопоиска (целое число ≥ 0):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_auto_base"


async def admin_settings_set_auto_vip_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_autosearch")]]
    try:
        await query.message.edit_text(
            "Введите VIP множитель дневного лимита (число ≥ 0, например 1 или 1.5):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_auto_vip_mult"


async def admin_settings_set_auto_vip_plus_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_autosearch")]]
    try:
        await query.message.edit_text(
            "Введите VIP+ множитель дневного лимита (число ≥ 0, например 2):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_auto_vip_plus_mult"


async def show_admin_settings_cooldowns(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    search_cd = runtime.db.get_setting_int("search_cooldown", runtime.search_cooldown_default)
    bonus_cd = runtime.db.get_setting_int("daily_bonus_cooldown", runtime.daily_bonus_cooldown_default)
    text = (
        "⏱️ <b>Кулдауны</b>\n\n"
        f"Поиск: <b>{int(search_cd // 60)} мин</b> ({search_cd} сек)\n"
        f"Ежедневный бонус: <b>{int(bonus_cd // 3600)} ч</b> ({bonus_cd} сек)\n\n"
        "Выберите, что изменить:"
    )
    keyboard = [
        [InlineKeyboardButton("Изменить поиск", callback_data="admin_settings_set_search_cd")],
        [InlineKeyboardButton("Изменить бонус", callback_data="admin_settings_set_bonus_cd")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings_menu")],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def admin_settings_set_search_cd_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_cooldowns")]]
    try:
        await query.message.edit_text(
            "Введите новый кулдаун поиска в секундах:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_search_cd"


async def admin_settings_set_bonus_cd_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_settings_cooldowns")]]
    try:
        await query.message.edit_text(
            "Введите новый кулдаун ежедневного бонуса в секундах:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "settings_set_bonus_cd"


async def _handle_gift_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    current = runtime.db.get_setting_bool("gift_autoblock_enabled", True)
    ok = runtime.db.set_setting_bool("gift_autoblock_enabled", not current)
    await query.answer("✅ Настройка обновлена" if ok else "❌ Ошибка", show_alert=True)
    await show_admin_settings_gift_protection(update, context, runtime)


async def _handle_casino_reset_prob(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    ok = runtime.db.set_setting_float("casino_win_prob", runtime.casino_win_prob_default)
    await query.answer("✅ Сброшено" if ok else "❌ Ошибка", show_alert=True)
    await show_admin_settings_casino(update, context, runtime)


async def _handle_casino_reset_luck(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    if not runtime.has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    ok = runtime.db.set_setting_float("casino_luck_mult", 1.0)
    await query.answer("✅ Сброшено" if ok else "❌ Ошибка", show_alert=True)
    await show_admin_settings_casino(update, context, runtime)


async def _handle_placeholder(update: Update) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer("⚙️ Функция в разработке!", show_alert=True)


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    if data == "admin_settings_menu":
        await show_admin_settings_menu(update, context, runtime)
    elif data == "admin_settings_limits":
        await show_admin_settings_limits(update, context, runtime)
    elif data == "admin_settings_set_fertilizer_max":
        await admin_settings_set_fertilizer_max_start(update, context, runtime)
    elif data == "admin_settings_negative_effects":
        await show_admin_settings_negative_effects(update, context, runtime)
    elif data == "admin_settings_set_neg_interval":
        await admin_settings_set_neg_interval_start(update, context, runtime)
    elif data == "admin_settings_set_neg_chance":
        await admin_settings_set_neg_chance_start(update, context, runtime)
    elif data == "admin_settings_set_neg_max_active":
        await admin_settings_set_neg_max_active_start(update, context, runtime)
    elif data == "admin_settings_set_neg_duration":
        await admin_settings_set_neg_duration_start(update, context, runtime)
    elif data == "admin_settings_cooldowns":
        await show_admin_settings_cooldowns(update, context, runtime)
    elif data == "admin_settings_set_search_cd":
        await admin_settings_set_search_cd_start(update, context, runtime)
    elif data == "admin_settings_set_bonus_cd":
        await admin_settings_set_bonus_cd_start(update, context, runtime)
    elif data == "admin_settings_autosearch":
        await show_admin_settings_autosearch(update, context, runtime)
    elif data == "admin_settings_set_auto_base":
        await admin_settings_set_auto_base_start(update, context, runtime)
    elif data == "admin_settings_set_auto_vip_mult":
        await admin_settings_set_auto_vip_mult_start(update, context, runtime)
    elif data == "admin_settings_set_auto_vip_plus_mult":
        await admin_settings_set_auto_vip_plus_mult_start(update, context, runtime)
    elif data == "admin_settings_gift_protection":
        await show_admin_settings_gift_protection(update, context, runtime)
    elif data == "admin_settings_set_gift_limit":
        await admin_settings_set_gift_limit_start(update, context, runtime)
    elif data == "admin_settings_set_gift_duration":
        await admin_settings_set_gift_duration_start(update, context, runtime)
    elif data == "admin_settings_gift_toggle":
        await _handle_gift_toggle(update, context, runtime)
    elif data == "admin_settings_casino":
        await show_admin_settings_casino(update, context, runtime)
    elif data == "admin_settings_set_casino_win_prob":
        await admin_settings_set_casino_win_prob_start(update, context, runtime)
    elif data == "admin_settings_set_casino_luck_mult":
        await admin_settings_set_casino_luck_mult_start(update, context, runtime)
    elif data == "admin_settings_casino_reset_prob":
        await _handle_casino_reset_prob(update, context, runtime)
    elif data == "admin_settings_casino_reset_luck":
        await _handle_casino_reset_luck(update, context, runtime)
    elif data in {"admin_settings_shop", "admin_settings_notifications", "admin_settings_localization"}:
        await _handle_placeholder(update)


async def handle_text_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
    text_input: str,
    runtime: BotRuntime,
) -> bool:
    if action not in TEXT_ACTIONS:
        return False

    if action == "settings_set_search_cd":
        keyboard = [[InlineKeyboardButton("⏱️ Кулдауны", callback_data="admin_settings_cooldowns")]]
        try:
            new_cd = int(text_input.strip())
            if new_cd <= 0:
                raise ValueError
            ok = runtime.db.set_setting_int("search_cooldown", new_cd)
            message = (
                f"✅ Кулдаун поиска обновлён: <b>{new_cd}</b> сек."
                if ok
                else "❌ Не удалось сохранить настройку"
            )
        except Exception:
            message = "❌ Введите целое число секунд (>0)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_bonus_cd":
        keyboard = [[InlineKeyboardButton("⏱️ Кулдауны", callback_data="admin_settings_cooldowns")]]
        try:
            new_cd = int(text_input.strip())
            if new_cd <= 0:
                raise ValueError
            ok = runtime.db.set_setting_int("daily_bonus_cooldown", new_cd)
            message = (
                f"✅ Кулдаун ежедневного бонуса обновлён: <b>{new_cd}</b> сек."
                if ok
                else "❌ Не удалось сохранить настройку"
            )
        except Exception:
            message = "❌ Введите целое число секунд (>0)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_auto_base":
        keyboard = [[InlineKeyboardButton("🤖 Автопоиск", callback_data="admin_settings_autosearch")]]
        try:
            new_val = int(text_input.strip())
            if new_val < 0:
                raise ValueError
            ok = runtime.db.set_setting_int("auto_search_daily_limit_base", new_val)
            message = (
                f"✅ Базовый дневной лимит автопоиска обновлён: <b>{new_val}</b>"
                if ok
                else "❌ Не удалось сохранить настройку"
            )
        except Exception:
            message = "❌ Введите целое число (≥ 0)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_auto_vip_mult":
        keyboard = [[InlineKeyboardButton("🤖 Автопоиск", callback_data="admin_settings_autosearch")]]
        try:
            new_val = float(text_input.strip().replace(",", "."))
            if new_val < 0:
                raise ValueError
            ok = runtime.db.set_setting_float("auto_search_vip_daily_mult", new_val)
            message = f"✅ VIP множитель обновлён: <b>{new_val}</b>" if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите число (≥ 0), например 1 или 1.5"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_auto_vip_plus_mult":
        keyboard = [[InlineKeyboardButton("🤖 Автопоиск", callback_data="admin_settings_autosearch")]]
        try:
            new_val = float(text_input.strip().replace(",", "."))
            if new_val < 0:
                raise ValueError
            ok = runtime.db.set_setting_float("auto_search_vip_plus_daily_mult", new_val)
            message = f"✅ VIP+ множитель обновлён: <b>{new_val}</b>" if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите число (≥ 0), например 2"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_gift_limit":
        keyboard = [[InlineKeyboardButton("🎁 Gift-защита", callback_data="admin_settings_gift_protection")]]
        try:
            new_val = int(text_input.strip())
            if new_val < 1:
                raise ValueError
            ok = runtime.db.set_setting_int("gift_autoblock_consecutive_limit", new_val)
            message = f"✅ Лимит gift-защиты обновлён: <b>{new_val}</b>" if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите целое число (≥ 1)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_gift_duration":
        keyboard = [[InlineKeyboardButton("🎁 Gift-защита", callback_data="admin_settings_gift_protection")]]
        try:
            duration_sec = runtime.parse_duration_to_seconds(text_input.strip())
            if not duration_sec:
                raise ValueError
            ok = runtime.db.set_setting_int("gift_autoblock_duration_sec", int(duration_sec))
            message = (
                f"✅ Длительность gift-блокировки обновлена: <b>{duration_sec}</b> сек. ({runtime.format_duration_compact(duration_sec)})"
                if ok
                else "❌ Не удалось сохранить настройку"
            )
        except Exception:
            message = "❌ Введите длительность в формате 14d, 12h или 3600"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_fertilizer_max":
        keyboard = [[InlineKeyboardButton("💰 Лимиты", callback_data="admin_settings_limits")]]
        try:
            new_val = int(text_input.strip())
            if new_val < 1:
                raise ValueError
            ok = runtime.db.set_setting_int("plantation_fertilizer_max_per_bed", new_val)
            message = f"✅ Лимит удобрений обновлён: <b>{new_val}</b>" if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите целое число (≥ 1)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_neg_interval":
        keyboard = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data="admin_settings_negative_effects")]]
        try:
            new_val = int(text_input.strip())
            if new_val < 60:
                raise ValueError
            ok = runtime.db.set_setting_int("plantation_negative_event_interval_sec", new_val)
            message = f"✅ Интервал обновлён: <b>{new_val}</b> сек." if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите целое число (≥ 60)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_neg_duration":
        keyboard = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data="admin_settings_negative_effects")]]
        try:
            new_val = int(text_input.strip())
            if new_val < 60:
                raise ValueError
            ok = runtime.db.set_setting_int("plantation_negative_event_duration_sec", new_val)
            message = f"✅ Длительность обновлена: <b>{new_val}</b> сек." if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите целое число (≥ 60)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if action == "settings_set_casino_luck_mult":
        keyboard = [[InlineKeyboardButton("🎰 Казино", callback_data="admin_settings_casino")]]
        raw = (text_input or "").strip().replace(",", ".")
        try:
            val = float(raw)
            if val < 0.1 or val > 5:
                raise ValueError
            ok = runtime.db.set_setting_float("casino_luck_mult", val)
            message = f"✅ Множитель удачи обновлён: <b>x{val}</b>" if ok else "❌ Не удалось сохранить настройку"
        except Exception:
            message = "❌ Введите число от 0.1 до 5.0 (например 1.5)"
        await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    keyboard = {
        "settings_set_neg_chance": "admin_settings_negative_effects",
        "settings_set_neg_max_active": "admin_settings_negative_effects",
        "settings_set_casino_win_prob": "admin_settings_casino",
    }[action]
    reply = [[InlineKeyboardButton("🔙 Назад", callback_data=keyboard)]]
    raw = (text_input or "").strip().replace(",", ".")
    try:
        val = float(raw)
        if val > 1:
            val = val / 100.0
        if action == "settings_set_casino_win_prob":
            if val <= 0 or val >= 1:
                raise ValueError
            ok = runtime.db.set_setting_float("casino_win_prob", val)
            message = f"✅ Шанс победы обновлён: <b>{round(val * 100, 2)}%</b> (={val})" if ok else "❌ Не удалось сохранить настройку"
        else:
            if val <= 0 or val > 1:
                raise ValueError
            setting_name = "plantation_negative_event_chance" if action == "settings_set_neg_chance" else "plantation_negative_event_max_active"
            label = "Шанс" if action == "settings_set_neg_chance" else "Лимит активных"
            ok = runtime.db.set_setting_float(setting_name, val)
            message = f"✅ {label} обновлён: <b>{round(val * 100, 2)}%</b>" if ok else "❌ Не удалось сохранить настройку"
    except Exception:
        if action == "settings_set_casino_win_prob":
            message = "❌ Введите число от 0 до 1 или процент 1–99"
        else:
            message = "❌ Введите число 0..1 или проценты 1–100"
    await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(reply))
    return True


def register_handlers(application, runtime: BotRuntime) -> None:
    application.add_handler(
        CallbackQueryHandler(
            partial(handle_settings_callback, runtime=runtime),
            pattern=r"^admin_settings_",
        )
    )
