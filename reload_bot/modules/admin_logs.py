from __future__ import annotations

from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes

from reload_bot.runtime import BotRuntime


TEXT_ACTIONS = {"logs_player"}


def can_handle_text_action(action: str | None) -> bool:
    return bool(action in TEXT_ACTIONS)


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📝 Логи системы", callback_data="admin_logs_menu")]])


async def show_admin_logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        runtime.logger.error("show_admin_logs_menu: query is None")
        return

    try:
        await query.answer()
        user = query.from_user
        if not user:
            runtime.logger.error("show_admin_logs_menu: user is None")
            return
        if not runtime.has_admin_level(user.id, user.username, 1):
            await query.answer("⚠ Доступ запрещён!", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("📊 Последние действия", callback_data="admin_logs_recent")],
            [InlineKeyboardButton("💰 Транзакции", callback_data="admin_logs_transactions")],
            [InlineKeyboardButton("🎰 Игры в казино", callback_data="admin_logs_casino")],
            [InlineKeyboardButton("🛒 Покупки", callback_data="admin_logs_purchases")],
            [InlineKeyboardButton("👤 Действия игрока", callback_data="admin_logs_player")],
            [InlineKeyboardButton("⚠️ Ошибки системы", callback_data="admin_logs_errors")],
            [InlineKeyboardButton("🔙 Админ панель", callback_data="creator_panel")],
        ]
        text = (
            "📝 <b>Логи системы</b>\n\n"
            "Просмотр истории действий в боте:\n\n"
            "📊 <b>Последние действия</b> - общая активность\n"
            "💰 <b>Транзакции</b> - перемещение монет\n"
            "🎰 <b>Казино</b> - игры и ставки\n"
            "🛒 <b>Покупки</b> - магазин и обмены\n"
            "👤 <b>Игрок</b> - действия конкретного пользователя\n"
            "⚠️ <b>Ошибки</b> - системные проблемы\n\n"
            "Выберите тип логов:"
        )
        if not query.message:
            runtime.logger.error("show_admin_logs_menu: query.message is None")
            return
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest as error:
            runtime.logger.error("BadRequest in show_admin_logs_menu: %s", error)
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
    except Exception as error:
        runtime.logger.error("Ошибка в show_admin_logs_menu: %s", error, exc_info=True)
        try:
            await query.answer("❌ Ошибка при открытии меню логов", show_alert=True)
        except Exception:
            pass


async def show_admin_logs_recent(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    logs = runtime.db.get_recent_logs(limit=20)
    text = "📊 <b>Последние действия</b>\n\n"
    if logs:
        for log in logs:
            status = "✅" if log["success"] else "❌"
            timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
            text += f"{status} <b>{log['username']}</b> ({log['user_id']})\n"
            text += f"├ Действие: <i>{log['action_type']}</i>\n"
            if log["action_details"]:
                text += f"├ Детали: {log['action_details'][:50]}\n"
            if log["amount"]:
                text += f"└ Сумма: {log['amount']}\n"
            text += f"⏰ {timestamp_str}\n\n"
    else:
        text += "<i>Логов пока нет</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs_recent")],
        [InlineKeyboardButton("🔙 Логи", callback_data="admin_logs_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_logs_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    logs = runtime.db.get_logs_by_type("transaction", limit=20)
    text = "💰 <b>Транзакции</b>\n\n"
    if logs:
        for log in logs:
            status = "✅" if log["success"] else "❌"
            timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
            text += f"{status} <b>{log['username']}</b>\n"
            if log["amount"]:
                sign = "+" if log["amount"] > 0 else ""
                text += f"├ Сумма: {sign}{log['amount']} 💰\n"
            if log["action_details"]:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Транзакций пока нет</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs_transactions")],
        [InlineKeyboardButton("🔙 Логи", callback_data="admin_logs_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_logs_casino(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    logs = runtime.db.get_logs_by_type("casino", limit=20)
    text = "🎰 <b>Игры в казино</b>\n\n"
    if logs:
        for log in logs:
            status = "✅ Выигрыш" if log["success"] else "❌ Проигрыш"
            timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
            text += f"{status} - <b>{log['username']}</b>\n"
            if log["amount"]:
                sign = "+" if log["amount"] > 0 else ""
                text += f"├ {sign}{log['amount']} 💰\n"
            if log["action_details"]:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Логов казино пока нет</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs_casino")],
        [InlineKeyboardButton("🔙 Логи", callback_data="admin_logs_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_logs_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    logs = runtime.db.get_logs_by_type("purchase", limit=20)
    text = "🛒 <b>Покупки</b>\n\n"
    if logs:
        for log in logs:
            status = "✅" if log["success"] else "❌"
            timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
            text += f"{status} <b>{log['username']}</b>\n"
            if log["amount"]:
                text += f"├ Цена: {log['amount']} 💰\n"
            if log["action_details"]:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Покупок пока нет</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs_purchases")],
        [InlineKeyboardButton("🔙 Логи", callback_data="admin_logs_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def show_admin_logs_player_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    text = (
        "👤 <b>Действия игрока</b>\n\n"
        "Отправьте <code>@username</code> или <code>user_id</code> игрока\n\n"
        "Или нажмите Отмена"
    )
    try:
        await query.message.edit_text(text, reply_markup=_back_kb(), parse_mode="HTML")
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = "logs_player"


async def show_admin_logs_errors(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 1):
        await query.answer("⚠ Доступ запрещён!", show_alert=True)
        return

    logs = runtime.db.get_error_logs(limit=20)
    text = "⚠️ <b>Ошибки системы</b>\n\n"
    if logs:
        for log in logs:
            timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
            text += f"❌ <b>{log['username']}</b> ({log['user_id']})\n"
            text += f"├ Действие: <i>{log['action_type']}</i>\n"
            if log["action_details"]:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "✅ <i>Ошибок не обнаружено!</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs_errors")],
        [InlineKeyboardButton("🔙 Логи", callback_data="admin_logs_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def handle_text_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
    text_input: str,
    runtime: BotRuntime,
) -> bool:
    if action != "logs_player":
        return False

    player = None
    result = runtime.db.find_player_by_identifier(text_input)
    if result.get("ok") and result.get("player"):
        player = result["player"]
    else:
        try:
            user_id = int(str(text_input).strip().lstrip("@"))
            player = runtime.db.get_or_create_player(user_id, f"User{user_id}")
        except Exception:
            player = None

    if not player:
        response = f"❌ Пользователь {text_input} не найден!"
    else:
        logs = runtime.db.get_user_logs(player.user_id, limit=15)
        response = f"👤 <b>Логи игрока @{player.username or player.user_id}</b>\n\n"
        if logs:
            for log in logs:
                status = "✅" if log["success"] else "❌"
                timestamp_str = runtime.safe_format_timestamp(log["timestamp"])
                response += f"{status} <i>{log['action_type']}</i>\n"
                if log["action_details"]:
                    response += f"├ {log['action_details'][:50]}\n"
                if log["amount"]:
                    sign = "+" if log["amount"] > 0 else ""
                    response += f"├ {sign}{log['amount']} 💰\n"
                response += f"└ {timestamp_str}\n\n"
        else:
            response += "<i>Логов для этого игрока пока нет</i>"

    await update.message.reply_html(response, reply_markup=_back_kb())
    return True


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    if data == "admin_logs_menu":
        await show_admin_logs_menu(update, context, runtime)
    elif data == "admin_logs_recent":
        await show_admin_logs_recent(update, context, runtime)
    elif data == "admin_logs_transactions":
        await show_admin_logs_transactions(update, context, runtime)
    elif data == "admin_logs_casino":
        await show_admin_logs_casino(update, context, runtime)
    elif data == "admin_logs_purchases":
        await show_admin_logs_purchases(update, context, runtime)
    elif data == "admin_logs_player":
        await show_admin_logs_player_start(update, context, runtime)
    elif data == "admin_logs_errors":
        await show_admin_logs_errors(update, context, runtime)


def register_handlers(application, runtime: BotRuntime) -> None:
    application.add_handler(
        CallbackQueryHandler(
            partial(handle_callback, runtime=runtime),
            pattern=r"^admin_logs_",
        )
    )
