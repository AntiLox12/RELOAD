# file: admin2.py

from telegram import Update
from telegram.ext import ContextTypes
import database as db
from datetime import datetime
from constants import ADMIN_USERNAMES
import logging

# Set up logger
logger = logging.getLogger(__name__)

"""Bootstrap-админы по username берутся из constants.ADMIN_USERNAMES"""


def _fmt_ts(ts: int | None) -> str:
    """Форматирует Unix-время в человекочитаемую строку."""
    try:
        val = int(ts or 0)
        if val <= 0:
            return '-'
        return datetime.fromtimestamp(val).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return '-'

def _is_creator_or_lvl3(user) -> bool:
    is_creator = (user.username in ADMIN_USERNAMES)
    lvl = db.get_admin_level(user.id)
    return is_creator or lvl == 3

async def receipt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/receipt <id> — показать детали чека покупки (только Создатель и ур.3)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if not context.args:
        await msg.reply_text("Использование: /receipt <id>")
        return
    try:
        receipt_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("ID должен быть числом. Пример: /receipt 123")
        return

    rec = db.get_receipt_by_id(receipt_id)
    if not rec:
        await msg.reply_text("Чек не найден.")
        return

    text = (
        f"🧾 Чек #{rec.id}\n"
        f"Пользователь: {rec.user_id}\n"
        f"Тип: {getattr(rec, 'kind', '-')}\n"
        f"Сумма (септимы): {getattr(rec, 'amount_coins', 0)}\n"
        f"Длительность (сек): {getattr(rec, 'duration_seconds', 0)}\n"
        f"Куплено: {_fmt_ts(getattr(rec, 'purchased_at', 0))}\n"
        f"Действует до: {_fmt_ts(getattr(rec, 'valid_until', 0))}\n"
        f"Статус: {getattr(rec, 'status', '-')}\n"
        f"Проверено кем: {getattr(rec, 'verified_by', '-')}\n"
        f"Проверено когда: {_fmt_ts(getattr(rec, 'verified_at', 0))}\n"
        f"Дополнительно: {getattr(rec, 'extra', '-')}\n"
    )
    await msg.reply_text(text)


async def verifyreceipt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/verifyreceipt <id> — отметить чек как проверенный (только Создатель и ур.3)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if not context.args:
        await msg.reply_text("Использование: /verifyreceipt <id>")
        return
    try:
        receipt_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("ID должен быть числом. Пример: /verifyreceipt 123")
        return

    rec = db.get_receipt_by_id(receipt_id)
    if not rec:
        await msg.reply_text("Чек не найден.")
        return
    if getattr(rec, 'status', '') == 'verified':
        text = (
            f"🧾 Чек #{rec.id} уже проверен.\n"
            f"Статус: {rec.status}\n"
            f"Проверено кем: {getattr(rec, 'verified_by', '-')}\n"
            f"Проверено когда: {_fmt_ts(getattr(rec, 'verified_at', 0))}"
        )
        await msg.reply_text(text)
        return

    ok = db.verify_receipt(receipt_id, user.id)
    if not ok:
        await msg.reply_text("Не удалось проверить чек (возможно, не найден).")
        return

    rec2 = db.get_receipt_by_id(receipt_id)
    text = (
        f"✅ Чек #{receipt_id} помечен как проверенный.\n"
        f"Статус: {getattr(rec2, 'status', 'verified')}\n"
        f"Проверено кем: {getattr(rec2, 'verified_by', user.id)}\n"
        f"Проверено когда: {_fmt_ts(getattr(rec2, 'verified_at', int(datetime.now().timestamp())))}"
    )
    await msg.reply_text(text)


async def admin2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin2 — показать команды, доступные только Создателю и Главному админу (ур.3)."""
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    lvl = db.get_admin_level(user.id)
    if not is_creator and lvl != 3:
        await update.message.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    text = (
        "🛡️ Команды для привилегированных ролей\n\n"
        "— Создатель и Главный админ (ур.3):\n"
        "• /admin add <user_id> [username] [level 1-3] — добавить админа.\n"
        "• /admin remove <user_id> — удалить админа.\n"
        "• /admin level <user_id> <1-3> — изменить уровень админа.\n"
        "• /stock <kind> — показать текущий остаток склада по виду бонуса.\n"
        "• /stockadd <kind> <число> — изменить склад указанного бонуса на delta (может быть отрицательным).\n"
        "• /stockset <kind> <число> — установить склад указанного бонуса в значение.\n"
        "• /tgstock — показать текущий остаток TG Premium на складе.\n"
        "• /tgadd <число> — изменить склад TG Premium на указанное значение (может быть отрицательным).\n"
        "• /tgset <число> — установить склад TG Premium в указанное значение.\n"
        "• /receipt <id> — показать детали чека покупки.\n"
        "• /verifyreceipt <id> — отметить чек как проверенный.\n"
        "• /addvip <@username|all> <дни> — добавить VIP статус пользователю или всем.\n"
        "• /addautosearch <@username|all> <count> <days> — добавить автопоиск буст (дополнительные поиски в день) пользователю или всем.\n"
        "• /listboosts — показать всех пользователей с активными бустами автопоиска.\n"
        "• /removeboost <@username|user_id> — убрать буст автопоиска у пользователя.\n"
        "• /booststats — показать статистику по бустам автопоиска.\n"
        "• /boosthistory <@username|user_id> — показать историю бустов пользователя.\n\n"
        "— Только Создатель:\n"
        "• /incadd Название | Описание | [да/нет] — создать обычную заявку на добавление без пометок (для проверки модерации).\n"
        "• /inceditdrink <id> <name|description> <new_value> — создать обычную заявку на редактирование.\n"
        "• /incdelrequest <drink_id> [причина] — создать обычную заявку на удаление.\n\n"
        "• /addcoins <amount> <user_id|@username> — начислить монеты пользователю (только Создатель). Можно ответом: /addcoins <amount>\n"
        "• /delmoney <amount> <user_id|@username> — списать монеты у пользователя (только Создатель). Можно ответом: /delmoney <amount>\n\n"
        "— Прочее:\n"
        "• /fullhelp — полная справка по боту.\n"
    )
    await update.message.reply_text(text)


async def tgstock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tgstock — показать текущий остаток TG Premium на складе (Создатель и ур.3)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    stock = db.get_tg_premium_stock()
    await msg.reply_text(f"Текущий остаток TG Premium: {stock}")


async def tgadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tgadd <число> — изменить склад на delta (может быть отрицательным)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if not context.args:
        await msg.reply_text("Использование: /tgadd <число> (может быть отрицательным)")
        return
    try:
        delta = int(context.args[0])
    except ValueError:
        await msg.reply_text("Число должно быть целым. Пример: /tgadd 5")
        return
    new_stock = db.add_tg_premium_stock(delta)
    await msg.reply_text(f"Остаток изменён на {delta}. Новый остаток: {new_stock}")


async def tgset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tgset <число> — установить склад в указанное значение (>=0)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if not context.args:
        await msg.reply_text("Использование: /tgset <число>")
        return
    try:
        value = int(context.args[0])
    except ValueError:
        await msg.reply_text("Число должно быть целым. Пример: /tgset 10")
        return
    new_stock = db.set_tg_premium_stock(value)
    await msg.reply_text(f"Остаток установлен: {new_stock}")


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stock <kind> — показать текущий остаток склада по виду бонуса (Создатель и ур.3)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if not context.args:
        await msg.reply_text("Использование: /stock <kind>\nПример: /stock tg_premium")
        return
    kind = context.args[0].strip()
    stock = db.get_bonus_stock(kind)
    await msg.reply_text(f"Склад [{kind}]: {stock}")


async def stockadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stockadd <kind> <delta> — изменить склад (может быть отрицательным)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if len(context.args) < 2:
        await msg.reply_text("Использование: /stockadd <kind> <число> (может быть отрицательным)\nПример: /stockadd tg_premium 5")
        return
    kind = context.args[0].strip()
    try:
        delta = int(context.args[1])
    except ValueError:
        await msg.reply_text("Число должно быть целым. Пример: /stockadd tg_premium 5")
        return
    new_stock = db.add_bonus_stock(kind, delta)
    await msg.reply_text(f"Склад [{kind}] изменён на {delta}. Новый остаток: {new_stock}")


async def stockset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stockset <kind> <value> — установить склад (>=0)."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    if len(context.args) < 2:
        await msg.reply_text("Использование: /stockset <kind> <число>\nПример: /stockset tg_premium 10")
        return
    kind = context.args[0].strip()
    try:
        value = int(context.args[1])
    except ValueError:
        await msg.reply_text("Число должно быть целым. Пример: /stockset tg_premium 10")
        return
    new_stock = db.set_bonus_stock(kind, value)
    await msg.reply_text(f"Склад [{kind}] установлен: {new_stock}")


async def addautosearch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addautosearch <@username|all> <count> <days> — добавить автопоиск буст пользователю или всем."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    if len(context.args) < 3:
        await msg.reply_text(
            "Использование: /addautosearch <@username|all> <count> <days>\n"
            "Пример: /addautosearch @username 30 7\n"
            "Пример: /addautosearch all 20 3\n\n"
            "Добавляет дополнительные автопоиски на указанное количество дней."
        )
        return
    
    target = context.args[0].strip()
    try:
        count = int(context.args[1])
        if count <= 0:
            await msg.reply_text("Количество дополнительных поисков должно быть положительным числом.")
            return
    except ValueError:
        await msg.reply_text("Количество должно быть числом. Пример: /addautosearch @username 30 7")
        return
    
    try:
        days = int(context.args[2])
        if days <= 0:
            await msg.reply_text("Количество дней должно быть положительным числом.")
            return
    except ValueError:
        await msg.reply_text("Количество дней должно быть числом. Пример: /addautosearch @username 30 7")
        return
    
    if target.lower() == "all":
        # Добавляем буст всем пользователям
        try:
            updated_count = db.add_auto_search_boost_to_all(count, days)
            await msg.reply_text(
                f"✅ Автопоиск буст на {count} дополнительных поисков на {days} дней добавлен {updated_count} пользователям."
            )
        except Exception as e:
            await msg.reply_text(f"❌ Ошибка при добавлении буста всем: {e}")
    else:
        # Добавляем буст конкретному пользователю
        # Убираем @ если есть
        if target.startswith('@'):
            target = target[1:]
        
        # Ищем пользователя по username
        target_player = db.get_player_by_username(target)
        if not target_player:
            await msg.reply_text(f"❌ Пользователь @{target} не найден в базе данных.")
            return
        
        # Добавляем буст
        try:
            success = db.add_auto_search_boost(target_player.user_id, count, days)
            if success:
                # Добавляем запись в историю с информацией об админе
                try:
                    db.add_boost_history_record(
                        user_id=target_player.user_id,
                        username=target_player.username,
                        action='granted',
                        boost_count=count,
                        boost_days=days,
                        granted_by=user.id,
                        granted_by_username=user.username,
                        details=f"Выдан админом {user.username or f'ID:{user.id}'}"
                    )
                except Exception as e:
                    logger.warning(f"[BOOST_HISTORY] Failed to record boost grant for @{target}: {e}")
                
                # Получаем информацию о новом лимите
                new_limit = db.get_auto_search_daily_limit(target_player.user_id)
                from datetime import datetime
                import time
                player = db.get_or_create_player(target_player.user_id, target_player.username)
                boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
                boost_end_date = datetime.fromtimestamp(boost_until).strftime('%Y-%m-%d %H:%M:%S')
                
                # Уведомляем администратора
                await msg.reply_text(
                    f"✅ Автопоиск буст на {count} дополнительных поисков на {days} дней добавлен пользователю @{target}.\n"
                    f"Новый дневной лимит: {new_limit}\n"
                    f"Буст активен до: {boost_end_date}"
                )
                
                # Уведомляем пользователя о получении буста
                try:
                    boost_info = db.get_boost_info(target_player.user_id)
                    user_notification = (
                        f"🎉 Вы получили автопоиск буст!\n"
                        f"🚀 Дополнительные поиски: +{count}\n"
                        f"📅 Длительность: {days} дней\n"
                        f"📊 Новый дневной лимит: {new_limit}\n"
                        f"⏰ Буст активен до: {boost_info['boost_until_formatted']}\n\n"
                        f"Теперь вы можете делать больше автопоисков в день!"
                    )
                    
                    await context.bot.send_message(
                        chat_id=target_player.user_id,
                        text=user_notification
                    )
                    logger.info(f"[BOOST_NOTIFY] Notified user @{target} about received boost")
                except Exception as e:
                    logger.warning(f"[BOOST_NOTIFY] Failed to notify user @{target} about boost: {e}")
                    # Не прерываем выполнение команды из-за ошибки уведомления
                    
            else:
                await msg.reply_text(f"❌ Ошибка при добавлении буста пользователю @{target}.")
                
        except Exception as e:
            await msg.reply_text(f"❌ Ошибка при добавлении буста: {e}")


async def addvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addvip <@username|all> <days> — добавить VIP статус пользователю или всем."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    if len(context.args) < 2:
        await msg.reply_text("Использование: /addvip <@username|all> <дни>\nПример: /addvip @username 7\nПример: /addvip all 7")
        return
    
    target = context.args[0].strip()
    try:
        days = int(context.args[1])
        if days <= 0:
            await msg.reply_text("Количество дней должно быть положительным числом.")
            return
    except ValueError:
        await msg.reply_text("Количество дней должно быть числом. Пример: /addvip @username 7")
        return
    
    duration_seconds = days * 24 * 60 * 60  # конвертируем дни в секунды
    
    if target.lower() == "all":
        # Добавляем VIP всем пользователям
        try:
            from database import SessionLocal, Player
            import time
            
            db_session = SessionLocal()
            try:
                players = db_session.query(Player).all()
                count = 0
                
                for player in players:
                    now_ts = int(time.time())
                    current_vip = int(getattr(player, 'vip_until', 0) or 0)
                    start_ts = max(current_vip, now_ts) if current_vip > now_ts else now_ts
                    new_vip_until = start_ts + duration_seconds
                    
                    player.vip_until = new_vip_until
                    count += 1
                
                db_session.commit()
                await msg.reply_text(f"✅ VIP статус на {days} дней добавлен {count} пользователям.")
                
            except Exception as e:
                db_session.rollback()
                await msg.reply_text(f"❌ Ошибка при добавлении VIP всем: {e}")
            finally:
                db_session.close()
                
        except Exception as e:
            await msg.reply_text(f"❌ Ошибка: {e}")
    else:
        # Добавляем VIP конкретному пользователю
        # Убираем @ если есть
        if target.startswith('@'):
            target = target[1:]
        
        # Ищем пользователя по username
        target_player = db.get_player_by_username(target)
        if not target_player:
            await msg.reply_text(f"❌ Пользователь @{target} не найден в базе данных.")
            return
        
        # Добавляем VIP
        try:
            import time
            now_ts = int(time.time())
            current_vip = int(getattr(target_player, 'vip_until', 0) or 0)
            start_ts = max(current_vip, now_ts) if current_vip > now_ts else now_ts
            new_vip_until = start_ts + duration_seconds
            
            db.update_player(target_player.user_id, vip_until=new_vip_until)
            
            # Форматируем дату окончания VIP
            vip_end_date = datetime.fromtimestamp(new_vip_until).strftime('%Y-%m-%d %H:%M:%S')
            await msg.reply_text(f"✅ VIP статус на {days} дней добавлен пользователю @{target}.\nVIP активен до: {vip_end_date}")
            
        except Exception as e:
            await msg.reply_text(f"❌ Ошибка при добавлении VIP: {e}")


async def listboosts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/listboosts — показать всех пользователей с активными бустами автопоиска."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    import time
    from database import SessionLocal, Player
    
    dbs = SessionLocal()
    try:
        # Получаем всех игроков с активными бустами
        current_time = int(time.time())
        players_with_boosts = dbs.query(Player).filter(
            Player.auto_search_boost_until > current_time,
            Player.auto_search_boost_count > 0
        ).all()
        
        if not players_with_boosts:
            await msg.reply_text("📋 Активных бустов автопоиска нет.")
            return
        
        # Формируем список
        boost_list = ["📋 <b>Активные бусты автопоиска:</b>\n"]
        
        for player in players_with_boosts:
            from datetime import datetime
            boost_end = datetime.fromtimestamp(player.auto_search_boost_until).strftime('%d.%m.%Y %H:%M')
            user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
            boost_list.append(
                f"🚀 {user_info}: +{player.auto_search_boost_count} до {boost_end}"
            )
        
        # Отправляем список (разбиваем если слишком длинный)
        full_text = "\n".join(boost_list)
        if len(full_text) > 4000:
            # Разбиваем на части
            chunks = []
            current_chunk = "📋 <b>Активные бусты автопоиска:</b>\n"
            
            for i, boost_info in enumerate(boost_list[1:], 1):
                if len(current_chunk + boost_info + "\n") > 4000:
                    chunks.append(current_chunk)
                    current_chunk = f"📋 <b>Активные бусты (часть {len(chunks)+1}):</b>\n{boost_info}\n"
                else:
                    current_chunk += boost_info + "\n"
            
            if current_chunk.strip():
                chunks.append(current_chunk)
            
            for chunk in chunks:
                await msg.reply_text(chunk, parse_mode='HTML')
        else:
            await msg.reply_text(full_text, parse_mode='HTML')
            
    except Exception as e:
        await msg.reply_text(f"Ошибка при получении списка бустов: {str(e)}")
    finally:
        dbs.close()


async def removeboost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/removeboost <@username|user_id> — убрать буст автопоиска у пользователя."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    args = context.args
    if not args:
        await msg.reply_text("Использование: /removeboost <@username|user_id>")
        return
    
    target = args[0]
    
    # Определяем целевого пользователя
    target_user_id = None
    target_username = None
    
    if target.startswith('@'):
        target_username = target[1:].lower()
    else:
        try:
            target_user_id = int(target)
        except ValueError:
            await msg.reply_text("Неверный формат. Используйте @username или числовой ID.")
            return
    
    from database import SessionLocal, Player
    
    dbs = SessionLocal()
    try:
        # Ищем пользователя
        if target_user_id:
            player = dbs.query(Player).filter(Player.user_id == target_user_id).first()
        else:
            player = dbs.query(Player).filter(Player.username.ilike(target_username)).first()
        
        if not player:
            await msg.reply_text("Пользователь не найден.")
            return
        
        # Проверяем есть ли активный буст
        import time
        current_time = int(time.time())
        current_boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
        current_boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
        
        if current_boost_until <= current_time or current_boost_count <= 0:
            user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
            await msg.reply_text(f"У пользователя {user_info} нет активного буста автопоиска.")
            return
        
        # Убираем буст
        boost_info_before = {
            'boost_count': current_boost_count,
            'boost_until': current_boost_until
        }
        
        player.auto_search_boost_count = 0
        player.auto_search_boost_until = 0
        dbs.commit()
        
        # Добавляем запись в историю
        try:
            db.add_boost_history_record(
                user_id=player.user_id,
                username=player.username,
                action='removed',
                boost_count=current_boost_count,
                granted_by=user.id,
                granted_by_username=user.username,
                details=f"Убран админом {user.username or f'ID:{user.id}'}"
            )
        except Exception as e:
            logger.warning(f"[BOOST_HISTORY] Failed to record boost removal for {user_info}: {e}")
        
        user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        
        # Уведомляем администратора
        await msg.reply_text(f"✅ Буст автопоиска убран у пользователя {user_info}.")
        
        # Уведомляем пользователя об отмене буста
        try:
            from datetime import datetime
            boost_end_formatted = datetime.fromtimestamp(boost_info_before['boost_until']).strftime('%d.%m.%Y %H:%M')
            new_limit = db.get_auto_search_daily_limit(player.user_id)
            
            user_notification = (
                f"🚫 Ваш автопоиск буст был отменён администратором.\n"
                f"🚀 Отменённый буст: +{boost_info_before['boost_count']} поисков\n"
                f"📅 Действовал до: {boost_end_formatted}\n"
                f"📊 Новый дневной лимит: {new_limit}"
            )
            
            await context.bot.send_message(
                chat_id=player.user_id,
                text=user_notification
            )
            logger.info(f"[BOOST_NOTIFY] Notified user {user_info} about boost removal")
        except Exception as e:
            logger.warning(f"[BOOST_NOTIFY] Failed to notify user {user_info} about boost removal: {e}")
            # Не прерываем выполнение команды из-за ошибки уведомления
            
    except Exception as e:
        await msg.reply_text(f"Ошибка при удалении буста: {str(e)}")
    finally:
        dbs.close()


async def booststats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/booststats — показать статистику по бустам автопоиска."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    try:
        stats = db.get_boost_statistics()
        
        # Основная статистика
        stats_text = [
            "📊 <b>Статистика бустов автопоиска:</b>\n",
            f"🚀 Активные бусты: {stats['active_boosts']}",
            f"⏱ Истёкшие бусты: {stats['expired_boosts']}",
            f"📈 Средний буст: {stats['average_boost_count']} поисков"
        ]
        
        # Топ пользователей
        if stats['top_users']:
            stats_text.append("\n🏆 <b>Топ пользователей:</b>")
            for i, user_data in enumerate(stats['top_users'], 1):
                username = f"@{user_data['username']}" if user_data['username'] else f"ID: {user_data['user_id']}"
                from datetime import datetime
                until_date = datetime.fromtimestamp(user_data['boost_until']).strftime('%d.%m %H:%M')
                stats_text.append(
                    f"{i}. {username}: +{user_data['boost_count']} до {until_date}"
                )
        
        # Проверяем истекающие бусты
        expiring_soon = db.get_expiring_boosts(hours_ahead=24)
        if expiring_soon:
            stats_text.append(f"\n⚠️ <b>Истекают в ближайшие 24ч:</b> {len(expiring_soon)}")
            
            # Показываем первые 5
            for player in expiring_soon[:5]:
                username = f"@{player.username}" if player.username else f"ID: {player.user_id}"
                boost_info = db.get_boost_info(player.user_id)
                remaining = boost_info['time_remaining_formatted']
                stats_text.append(f"  • {username}: {remaining}")
            
            if len(expiring_soon) > 5:
                stats_text.append(f"  • ... и ещё {len(expiring_soon) - 5}")
        
        # Отправляем статистику
        full_text = "\n".join(stats_text)
        await msg.reply_text(full_text, parse_mode='HTML')
        
    except Exception as e:
        await msg.reply_text(f"Ошибка при получении статистики: {str(e)}")

async def boosthistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/boosthistory <@username|user_id> — показать историю бустов пользователя."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return
    
    args = context.args
    if not args:
        await msg.reply_text("Использование: /boosthistory <@username|user_id>")
        return
    
    target = args[0]
    
    # Определяем целевого пользователя
    target_user_id = None
    target_username = None
    
    if target.startswith('@'):
        target_username = target[1:].lower()
    else:
        try:
            target_user_id = int(target)
        except ValueError:
            await msg.reply_text("Неверный формат. Используйте @username или числовой ID.")
            return
    
    from database import SessionLocal, Player
    
    dbs = SessionLocal()
    try:
        # Ищем пользователя
        if target_user_id:
            player = dbs.query(Player).filter(Player.user_id == target_user_id).first()
        else:
            player = dbs.query(Player).filter(Player.username.ilike(target_username)).first()
        
        if not player:
            await msg.reply_text("Пользователь не найден.")
            return
        
        # Получаем историю бустов
        history = db.get_user_boost_history(player.user_id, limit=20)
        
        if not history:
            user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
            await msg.reply_text(f"📋 У пользователя {user_info} нет истории бустов.")
            return
        
        # Формируем сообщение
        user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        history_text = [f"📋 <b>История бустов пользователя {user_info}:</b>\n"]
        
        for record in history:
            history_text.append(f"📅 {record['formatted_date']}")
            history_text.append(f"   {record['action_text']}")
            if record['details']:
                history_text.append(f"   💡 {record['details']}")
            history_text.append("")  # пустая строка для разделения
        
        # Отправляем историю
        full_text = "\n".join(history_text)
        if len(full_text) > 4000:
            # Разбиваем на части
            chunks = []
            current_chunk = f"📋 <b>История бустов пользователя {user_info}:</b>\n"
            
            for line in history_text[1:]:  # пропускаем заголовок
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk)
                    current_chunk = f"📋 <b>История бустов (продолжение):</b>\n{line}\n"
                else:
                    current_chunk += line + "\n"
            
            if current_chunk.strip():
                chunks.append(current_chunk)
            
            for chunk in chunks:
                await msg.reply_text(chunk, parse_mode='HTML')
        else:
            await msg.reply_text(full_text, parse_mode='HTML')
            
    except Exception as e:
        await msg.reply_text(f"Ошибка при получении истории: {str(e)}")
    finally:
        dbs.close()
