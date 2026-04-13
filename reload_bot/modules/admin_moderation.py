from __future__ import annotations

import html
import time
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes

from reload_bot.runtime import BotRuntime


TEXT_ACTIONS = {
    "mod_ban",
    "mod_unban",
    "mod_check",
    "mod_gift_block",
    "mod_gift_unblock",
    "warn_add",
    "warn_list",
    "warn_clear",
}


def can_handle_text_action(action: str | None) -> bool:
    return bool(action in TEXT_ACTIONS)


async def show_admin_moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not runtime.has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    banned_users = runtime.db.get_banned_users_count()
    keyboard = [
        [InlineKeyboardButton("🚫 Забанить пользователя", callback_data="admin_mod_ban")],
        [InlineKeyboardButton("✅ Разбанить пользователя", callback_data="admin_mod_unban")],
        [InlineKeyboardButton("🎁 Gift-блокировки", callback_data="admin_mod_gift_menu")],
        [InlineKeyboardButton("⚠️ Предупреждения", callback_data="admin_mod_warnings")],
        [InlineKeyboardButton("📋 Список банов", callback_data="admin_mod_banlist")],
        [InlineKeyboardButton("🔍 Проверить игрока", callback_data="admin_mod_check")],
        [InlineKeyboardButton("📝 История действий", callback_data="admin_mod_history")],
        [InlineKeyboardButton("🔙 Админ панель", callback_data="creator_panel")],
    ]
    text = (
        "🚫 <b>Модерация</b>\n\n"
        f"Заблокировано пользователей: <b>{banned_users}</b>\n\n"
        "<b>Доступные действия:</b>\n"
        "• Блокировка/разблокировка игроков\n"
        "• Gift-блокировки подарков\n"
        "• Система предупреждений\n"
        "• Проверка активности\n"
        "• История нарушений\n\n"
        "Выберите действие:"
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass


async def _start_simple_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime, text: str, cancel_to: str, action: str) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=cancel_to)]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass
    context.user_data["awaiting_admin_action"] = action


async def admin_mod_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "🚫 Бан пользователя\n\nОтправьте: <code>@username</code> или <code>user_id</code> и опционально длительность (например: 1d, 12h, 30m) и причину.\nПримеры:\n<code>@user 7d спам</code>\n<code>123456 1h флуд</code>\n<code>@user</code>",
        "admin_moderation_menu",
        "mod_ban",
    )


async def admin_mod_unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "✅ Разбан пользователя\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
        "admin_moderation_menu",
        "mod_unban",
    )


async def admin_mod_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "🔍 Проверка игрока\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
        "admin_moderation_menu",
        "mod_check",
    )


async def admin_warn_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "➕ Выдать предупреждение\n\nОтправьте: <code>@username</code> или <code>user_id</code> и причину\nПример: <code>@user спам</code>",
        "admin_mod_warnings",
        "warn_add",
    )


async def admin_warn_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "📄 Список предупреждений\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
        "admin_mod_warnings",
        "warn_list",
    )


async def admin_warn_clear_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "🗑️ Очистка предупреждений\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
        "admin_mod_warnings",
        "warn_clear",
    )


async def admin_mod_gift_block_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "➕ Gift-блокировка\n\nОтправьте: <code>@username</code> или <code>user_id</code>, опционально длительность и причину.\nПримеры:\n<code>@user 14d подозрительная серия</code>\n<code>123456789 3600 тест</code>\n<code>@user</code>",
        "admin_mod_gift_menu",
        "mod_gift_block",
    )


async def admin_mod_gift_unblock_start(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    await _start_simple_prompt(
        update,
        context,
        runtime,
        "✅ Снять gift-блокировку\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
        "admin_mod_gift_menu",
        "mod_gift_unblock",
    )


async def admin_mod_banlist_show(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    items = runtime.db.list_active_bans(limit=50)
    if not items:
        text = "📋 Активные баны: нет"
    else:
        lines = ["📋 Активные баны:"]
        for item in items:
            until = item.get("banned_until")
            until_str = runtime.safe_format_timestamp(until) if until else "навсегда"
            lines.append(f"• {item['user_id']} — до: {until_str} — {item.get('reason') or '—'}")
        text = "\n".join(lines)
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_moderation_menu")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass


async def admin_mod_history_show(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    logs = runtime.db.get_moderation_logs(limit=30)
    if not logs:
        text = "📝 История модерации пуста"
    else:
        lines = ["📝 История модерации:"]
        for row in logs:
            ts = runtime.safe_format_timestamp(row.get("ts")) or "—"
            details = row.get("details") or ""
            lines.append(f"• {ts} — {row.get('action')} → {row.get('target_id')} {('— ' + details) if details else ''}")
        text = "\n".join(lines[:50])
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_moderation_menu")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass


async def admin_mod_warnings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Выдать предупреждение", callback_data="admin_warn_add")],
        [InlineKeyboardButton("📄 Список предупреждений", callback_data="admin_warn_list")],
        [InlineKeyboardButton("🗑️ Очистить предупреждения", callback_data="admin_warn_clear")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_moderation_menu")],
    ])
    try:
        await query.message.edit_text("⚠️ Предупреждения: выберите действие", reply_markup=kb)
    except BadRequest:
        pass


async def admin_mod_gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    items = runtime.db.list_active_gift_restrictions(limit=50)
    text = (
        "🎁 <b>Gift-блокировки</b>\n\n"
        f"Активных блокировок: <b>{len(items)}</b>\n\n"
        "Здесь можно просматривать, выдавать и снимать ограничения только на систему подарков."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Активные gift-блокировки", callback_data="admin_mod_gift_list")],
        [InlineKeyboardButton("➕ Выдать / переустановить", callback_data="admin_mod_gift_block")],
        [InlineKeyboardButton("✅ Снять gift-блокировку", callback_data="admin_mod_gift_unblock")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_moderation_menu")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest:
        pass


async def admin_mod_gift_list_show(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not runtime.has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    items = runtime.db.list_active_gift_restrictions(limit=50)
    if not items:
        text = "🎁 Активные gift-блокировки: нет"
    else:
        lines = ["🎁 <b>Активные gift-блокировки</b>"]
        for item in items:
            label = runtime.format_player_label(item["user_id"], item.get("username"), item.get("display_name"))
            until_str = runtime.safe_format_timestamp(item.get("blocked_until")) or "—"
            source = "авто" if item.get("source") == "auto" else f"admin:{item.get('blocked_by')}"
            reason = html.escape(item.get("reason") or "—")
            lines.append(
                f"• {html.escape(label)} — до: <b>{until_str}</b>\n"
                f"  Причина: {reason}\n"
                f"  Источник: {source}"
            )
        text = "\n".join(lines[:51])
    kb = [[InlineKeyboardButton("🔙 Gift-блокировки", callback_data="admin_mod_gift_menu")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except BadRequest:
        pass


def _kb(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]])


def _resolve_or_hint(runtime: BotRuntime, ident: str, back_callback: str) -> tuple[int | None, InlineKeyboardMarkup]:
    return runtime.resolve_user_identifier(ident), _kb(back_callback)


async def handle_text_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text_input: str, runtime: BotRuntime) -> bool:
    if action not in TEXT_ACTIONS:
        return False

    actor_id = update.effective_user.id

    if action == "mod_ban":
        parts = text_input.split(maxsplit=2)
        if not parts:
            await update.message.reply_html("❌ Укажите пользователя. Пример: <code>@user 7d спам</code>", reply_markup=_kb("admin_moderation_menu"))
            return True
        ident = parts[0]
        duration_sec = None
        reason = None
        if len(parts) >= 2:
            parsed = runtime.parse_duration_to_seconds(parts[1])
            if parsed:
                duration_sec = parsed
                if len(parts) == 3:
                    reason = parts[2]
            else:
                reason = " ".join(parts[1:])
        uid = runtime.resolve_user_identifier(ident)
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_moderation_menu"))
            return True
        if runtime.db.is_protected_user(uid):
            await update.message.reply_html("⛔ Нельзя банить администратора или создателя", reply_markup=_kb("admin_moderation_menu"))
            return True
        ok = runtime.db.ban_user(uid, banned_by=actor_id, reason=reason, duration_seconds=duration_sec)
        if ok:
            until_str = runtime.safe_format_timestamp(int(time.time()) + int(duration_sec)) if duration_sec else None
            text = f"✅ Пользователь {uid} забанен" + (f" до {until_str}" if until_str else " навсегда")
            if reason:
                text += f"\nПричина: {html.escape(reason)}"
            await update.message.reply_html(text, reply_markup=_kb("admin_moderation_menu"))
        else:
            await update.message.reply_html("❌ Не удалось забанить пользователя", reply_markup=_kb("admin_moderation_menu"))
        return True

    if action == "mod_unban":
        uid = runtime.resolve_user_identifier(text_input.strip())
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_moderation_menu"))
            return True
        ok = runtime.db.unban_user(uid, unbanned_by=actor_id)
        await update.message.reply_html("✅ Пользователь разбанен" if ok else "❌ Не удалось разбанить пользователя", reply_markup=_kb("admin_moderation_menu"))
        return True

    if action == "mod_check":
        uid = runtime.resolve_user_identifier(text_input.strip())
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден", reply_markup=_kb("admin_moderation_menu"))
            return True
        player = runtime.db.get_player(uid)
        banned = runtime.db.is_user_banned(uid)
        gift_restriction = runtime.db.get_gift_restriction_info(uid)
        warns = runtime.db.get_warnings(uid, limit=50)
        vip = runtime.db.is_vip(uid)
        vip_plus = runtime.db.is_vip_plus(uid)
        username = getattr(player, "username", None) if player else None
        gift_status = "✅ Активен"
        if gift_restriction:
            until = runtime.safe_format_timestamp(gift_restriction.get("blocked_until")) or "—"
            gift_status = f"🚫 Gift-блок до {until}"
        lines = [
            "🔍 <b>Проверка игрока</b>",
            f"ID: <b>{uid}</b>",
            f"Username: <b>@{html.escape(username)}</b>" if username else "Username: —",
            f"Баланс: <b>{getattr(player, 'coins', 0) if player else 0}</b>",
            f"VIP: {'активен' if vip else '—'} | VIP+: {'активен' if vip_plus else '—'}",
            f"Статус: {'🚫 Забанен' if banned else '✅ Активен'}",
            f"Gift-статус: {gift_status}",
            f"Предупреждений: <b>{len(warns)}</b>",
        ]
        if gift_restriction:
            lines.append(f"Gift-причина: {html.escape(gift_restriction.get('reason') or '—')}")
        await update.message.reply_html("\n".join(lines), reply_markup=_kb("admin_moderation_menu"))
        return True

    if action == "mod_gift_block":
        parts = text_input.split(maxsplit=2)
        if not parts:
            await update.message.reply_html("❌ Укажите пользователя. Пример: <code>@user 14d подозрительная серия</code>", reply_markup=_kb("admin_mod_gift_menu"))
            return True
        ident = parts[0]
        duration_sec = None
        reason = None
        if len(parts) >= 2:
            parsed = runtime.parse_duration_to_seconds(parts[1])
            if parsed:
                duration_sec = parsed
                if len(parts) == 3:
                    reason = parts[2]
            else:
                reason = " ".join(parts[1:])
        if duration_sec is None:
            duration_sec = runtime.db.get_gift_autoblock_settings()["duration_sec"]
        uid = runtime.resolve_user_identifier(ident)
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_mod_gift_menu"))
            return True
        block_reason = reason or "Ручная gift-блокировка администратором"
        blocked_until = int(time.time()) + int(duration_sec)
        ok = runtime.db.add_gift_restriction(uid, block_reason, blocked_until=blocked_until, blocked_by=actor_id)
        if ok:
            try:
                runtime.db.insert_moderation_log(actor_id=actor_id, action="gift_block", target_id=uid, details=block_reason)
            except Exception:
                pass
            await update.message.reply_html(
                "✅ Gift-блокировка выдана.\n"
                f"Пользователь: <b>{uid}</b>\n"
                f"До: <b>{runtime.safe_format_timestamp(blocked_until) or '—'}</b>\n"
                f"Длительность: <b>{runtime.format_duration_compact(duration_sec)}</b>\n"
                f"Причина: {html.escape(block_reason)}",
                reply_markup=_kb("admin_mod_gift_menu"),
            )
        else:
            await update.message.reply_html("❌ Не удалось выдать gift-блокировку", reply_markup=_kb("admin_mod_gift_menu"))
        return True

    if action == "mod_gift_unblock":
        uid = runtime.resolve_user_identifier(text_input.strip())
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_mod_gift_menu"))
            return True
        ok = runtime.db.remove_gift_restriction(uid)
        if ok:
            try:
                runtime.db.insert_moderation_log(actor_id=actor_id, action="gift_unblock", target_id=uid, details=None)
            except Exception:
                pass
        await update.message.reply_html("✅ Gift-блокировка снята" if ok else "❌ Не удалось снять gift-блокировку", reply_markup=_kb("admin_mod_gift_menu"))
        return True

    if action == "warn_add":
        parts = text_input.split(maxsplit=1)
        if not parts:
            await update.message.reply_html("❌ Укажите пользователя", reply_markup=_kb("admin_mod_warnings"))
            return True
        uid = runtime.resolve_user_identifier(parts[0])
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_mod_warnings"))
            return True
        reason = parts[1] if len(parts) > 1 else None
        ok = runtime.db.add_warning(uid, issued_by=actor_id, reason=reason)
        await update.message.reply_html("✅ Предупреждение выдано" if ok else "❌ Не удалось выдать предупреждение", reply_markup=_kb("admin_mod_warnings"))
        return True

    if action == "warn_list":
        uid = runtime.resolve_user_identifier(text_input.strip())
        if not uid:
            await update.message.reply_html("❌ Пользователь не найден.", reply_markup=_kb("admin_mod_warnings"))
            return True
        items = runtime.db.get_warnings(uid, limit=50)
        if not items:
            text = "📄 У пользователя нет предупреждений"
        else:
            lines = ["📄 Предупреждения:"]
            for warning in items:
                ts = runtime.safe_format_timestamp(warning.get("issued_at")) or "—"
                reason = html.escape(warning.get("reason") or "")
                lines.append(f"• {ts} — {reason}")
            text = "\n".join(lines[:100])
        await update.message.reply_html(text, reply_markup=_kb("admin_mod_warnings"))
        return True

    uid = runtime.resolve_user_identifier(text_input.strip())
    if not uid:
        await update.message.reply_html("❌ Пользователь не найден", reply_markup=_kb("admin_mod_warnings"))
        return True
    count = runtime.db.clear_warnings(uid)
    await update.message.reply_html(f"🗑️ Удалено предупреждений: <b>{count}</b>", reply_markup=_kb("admin_mod_warnings"))
    return True


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    if data == "admin_moderation_menu":
        await show_admin_moderation_menu(update, context, runtime)
    elif data == "admin_mod_ban":
        await admin_mod_ban_start(update, context, runtime)
    elif data == "admin_mod_unban":
        await admin_mod_unban_start(update, context, runtime)
    elif data == "admin_mod_banlist":
        await admin_mod_banlist_show(update, context, runtime)
    elif data == "admin_mod_check":
        await admin_mod_check_start(update, context, runtime)
    elif data == "admin_mod_history":
        await admin_mod_history_show(update, context, runtime)
    elif data == "admin_mod_warnings":
        await admin_mod_warnings_menu(update, context, runtime)
    elif data == "admin_warn_add":
        await admin_warn_add_start(update, context, runtime)
    elif data == "admin_warn_list":
        await admin_warn_list_start(update, context, runtime)
    elif data == "admin_warn_clear":
        await admin_warn_clear_start(update, context, runtime)
    elif data == "admin_mod_gift_menu":
        await admin_mod_gift_menu(update, context, runtime)
    elif data == "admin_mod_gift_list":
        await admin_mod_gift_list_show(update, context, runtime)
    elif data == "admin_mod_gift_block":
        await admin_mod_gift_block_start(update, context, runtime)
    elif data == "admin_mod_gift_unblock":
        await admin_mod_gift_unblock_start(update, context, runtime)


def register_handlers(application, runtime: BotRuntime) -> None:
    application.add_handler(
        CallbackQueryHandler(
            partial(handle_callback, runtime=runtime),
            pattern=r"^(admin_moderation_menu|admin_mod_|admin_warn_)",
        )
    )
