# file: admin.py

from telegram import Update
from telegram.ext import ContextTypes
import database as db
from constants import ADMIN_USERNAMES

# Bootstrap-админы берутся из constants.ADMIN_USERNAMES


def _format_admin_assignment_notice(result: dict) -> str:
    tier = "Admin+" if str(result.get('tier') or '') == 'admin_plus' else 'Admin'
    vip_seconds = int(result.get('vip_remaining_seconds', 0) or 0)
    vip_plus_seconds = int(result.get('vip_plus_remaining_seconds', 0) or 0)
    vip_coins = int(result.get('vip_compensation', 0) or 0)
    vip_plus_coins = int(result.get('vip_plus_compensation', 0) or 0)
    total = int(result.get('total_compensation', 0) or 0)
    return "\n".join([
        f"🛡 Вам назначен статус {tier}.",
        "",
        "Активные VIP/VIP+ были отключены и конвертированы в септимы:",
        f"• VIP: {vip_seconds} сек. → {vip_coins} септимов",
        f"• VIP+: {vip_plus_seconds} сек. → {vip_plus_coins} септимов",
        f"• Итого: {total} септимов",
    ])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    "/admin add|remove|list — управление администраторами. add/remove работают по reply или ID."
    user = update.effective_user
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return

    args = context.args or []
    if not args:
        # Подробная справка для админов (динамически по уровню)
        is_creator = (user.username in ADMIN_USERNAMES)
        lvl = db.get_admin_level(user.id)
        lines = ["📘 Команды для администраторов:\n"]
        lines.append("• /admin list — показать список админов с ролями.")
        # Блок управления администраторами — только Создатель и ур.3
        if is_creator or lvl == 3:
            lines.extend([
                "• /admin add <user_id> [username] [level 1-3] — добавить админа (Создатель и ур.3). По умолчанию level=1.",
                "• /admin remove <user_id> — удалить админа (Создатель и ур.3).",
                "• /admin level <user_id> <1-3> — изменить уровень админа (Создатель и ур.3).",
                "",
            ])
        lines.extend([
            "🛡️ Модерация:",
            "• /requests — список заявок с кнопками.",
            "   Удаление: ур.2+ или Создатель. Добавление: ур.1+ одобряет, отклонение — ур.2+. Редактирование: предлагать — ур.1+, одобрять — ур.3 или Создатель.",
            "• /add — начать подачу заявки на добавление (в личке бота).",
            "• /delrequest <drink_id> [причина] — подать заявку на удаление (в личке бота).",
            "• /editdrink <drink_id> <name|description> <new_value> — подать заявку на правку (в личке бота).",
            "• /check <id> — показать карточку энергетика по ID (только для администраторов).",
            "• /id — список соответствий ID → название энергетика (только для админов, в личке).",
            "",
            "ℹ️ Все решения модерации сопровождаются уведомлениями инициатору и другим админам.",
        ])
        await update.message.reply_text("\n".join(lines))
        return

    action = args[0].lower()

    if action == 'list':
        admins = db.get_admin_users()
        if not admins:
            await update.message.reply_text("Админы: —")
            return
        # Обновим (при наличии доступа) username админов по их текущим профилям
        refreshed = []
        for a in admins:
            current_uname = a.username
            try:
                chat_obj = await context.bot.get_chat(a.user_id)
                if getattr(chat_obj, 'username', None):
                    new_uname = chat_obj.username
                    if new_uname != current_uname:
                        db.add_admin_user(a.user_id, new_uname)  # идемпотентно обновит username
                        current_uname = new_uname
            except Exception:
                pass
            level = getattr(a, 'level', None)
            try:
                level = int(level) if level is not None else 1
            except Exception:
                level = 1
            refreshed.append((a.user_id, current_uname, level))
        # Сортируем: Создатели сверху, затем по уровню (3→2→1), затем по username/ID
        refreshed.sort(key=lambda t: (
            0 if (t[1] and t[1] in ADMIN_USERNAMES) else 1,
            - (t[2] if isinstance(t[2], int) else 1),
            (t[1] or '').lower(),
            t[0]
        ))
        lines = ["Админы:"]
        for uid, uname, lvl in refreshed:
            shown = f"@{uname}" if uname else "—"
            if uname and uname in ADMIN_USERNAMES:
                role = "Создатель"
            else:
                role = "Главный админ" if lvl == 3 else ("Старший модератор" if lvl == 2 else "Младший модератор")
            lines.append(f"- {uid} ({shown}) — {role}")
        if ADMIN_USERNAMES:
            head_list = ", ".join([f"@{u}" for u in ADMIN_USERNAMES])
            lines.append("")
            lines.append(f"Создатели: {head_list}")
        await update.message.reply_text("\n".join(lines))
        return

    # Управлять администраторами могут Создатели и ур.3
    if action in ('add', 'remove', 'level'):
        is_creator = (user.username in ADMIN_USERNAMES)
        lvl = db.get_admin_level(user.id)
        if not is_creator and lvl != 3:
            await update.message.reply_text("Нет прав: требуется уровень 3 или Создатель.")
            return

    # Обработка смены уровня
    if action == 'level':
        target_id = None
        new_level = None
        if update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id
            # ожидаем уровень как первый аргумент после 'level'
            if len(args) >= 2 and args[1].isdigit():
                new_level = int(args[1])
        elif len(args) >= 3 and args[1].isdigit() and args[2].isdigit():
            target_id = int(args[1])
            new_level = int(args[2])
        else:
            await update.message.reply_text("Использование: /admin level <user_id> <1-3> или по ответу: /admin level <1-3>")
            return
        if new_level not in (1, 2, 3):
            await update.message.reply_text("Уровень должен быть 1, 2 или 3")
            return
        try:
            chat_obj = await context.bot.get_chat(target_id)
            target_username = getattr(chat_obj, 'username', None)
        except Exception:
            target_username = None
        assign_res = db.assign_admin_level(target_id, new_level, username=target_username)
        ok = bool(assign_res.get('ok'))
        if ok:
            try:
                db.insert_moderation_log(user.id, 'admin_level_change', target_id=target_id, details=f"level={new_level}")
            except Exception:
                pass
            try:
                await context.bot.send_message(target_id, _format_admin_assignment_notice(assign_res))
            except Exception:
                pass
        await update.message.reply_text("Уровень обновлён" if ok else "Не найден админ с таким ID")
        return

    # add/remove
    target_id = None
    target_username = None
    level_to_set = None

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
        # Если указан уровень после 'add' при ответе
        if len(args) >= 2 and args[1].isdigit():
            maybe = int(args[1])
            if 1 <= maybe <= 3:
                level_to_set = maybe
    elif len(args) >= 2 and args[1].isdigit():
        target_id = int(args[1])
        # далее может идти username и/или уровень
        if len(args) == 3:
            if args[2].isdigit() and 1 <= int(args[2]) <= 3:
                level_to_set = int(args[2])
            else:
                target_username = args[2]
        elif len(args) >= 4:
            target_username = args[2]
            if args[3].isdigit() and 1 <= int(args[3]) <= 3:
                level_to_set = int(args[3])
    else:
        await update.message.reply_text("Укажите user_id или ответьте на сообщение пользователя")
        return

    if action == 'add':
        # Если username не передан, попробуем получить его из профиля
        if not target_username:
            try:
                chat_obj = await context.bot.get_chat(target_id)
                target_username = getattr(chat_obj, 'username', None)
            except Exception:
                target_username = None
        assign_res = db.assign_admin_level(target_id, level_to_set if level_to_set is not None else 1, username=target_username)
        created = bool(assign_res.get('ok'))
        if created:
            try:
                db.insert_moderation_log(user.id, 'admin_add', target_id=target_id, details=f"level={level_to_set if level_to_set is not None else 1}")
            except Exception:
                pass
            try:
                await context.bot.send_message(target_id, _format_admin_assignment_notice(assign_res))
            except Exception:
                pass
        await update.message.reply_text("Добавлен" if created else "Уже был админом")
    elif action == 'remove':
        removed = db.remove_admin_user(target_id)
        if removed:
            try:
                db.insert_moderation_log(user.id, 'admin_remove', target_id=target_id)
            except Exception:
                pass
        await update.message.reply_text("Удалён" if removed else "Не найден")
    else:
        await update.message.reply_text("Неизвестное действие")
