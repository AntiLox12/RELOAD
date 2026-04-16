# file: admin2.py

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from datetime import datetime
from constants import ADMIN_USERNAMES, ENERGY_IMAGES_DIR, RARITIES, COLOR_EMOJIS
import logging
import os
import re
import random
import time

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


def _parse_yes_no(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    val = value.strip().lower()
    return val in ('y', 'yes', 'true', '1', 'да', 'д', 'on')

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
        "• /addexdrink <id> | <name> | <description> | [special=yes/no] — создать/обновить энергетик с фиксированным ID (для эксклюзивов).\n"
        "• /giveexdrink <user_id|@username> <drink_id> <rarity> [qty=1] — выдать пользователю эксклюзивный энергетик с нужной редкостью.\n"
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


async def setrareemoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return

    args = context.args or []
    if len(args) < 2:
        await msg.reply_text(
            "Использование: /setrareemoji <rarity> <emoji>\n"
            "Если в названии редкости есть пробелы — пишите её словами, эмодзи последним аргументом.\n"
            "Пример: /setrareemoji Грустный Вайб 😔"
        )
        return

    emoji = str(args[-1]).strip()
    rarity = " ".join([str(x) for x in args[:-1]]).strip()
    if not rarity or not emoji:
        await msg.reply_text("❌ Пустая редкость или эмодзи.")
        return

    try:
        ok = bool(db.set_rarity_emoji_override(rarity, emoji))
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка БД: {e}")
        return

    if not ok:
        await msg.reply_text("❌ Не удалось сохранить (проверьте аргументы).")
        return

    try:
        COLOR_EMOJIS[str(rarity)] = str(emoji)
    except Exception:
        pass

    await msg.reply_text(f"✅ Эмодзи для редкости '{rarity}' установлен: {emoji}")


async def listrareemoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return

    try:
        rows = db.list_rarity_emoji_overrides()
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка БД: {e}")
        return

    if not rows:
        await msg.reply_text("Список пуст.")
        return

    lines = []
    for rarity, emoji in rows:
        lines.append(f"{emoji} {rarity}")
    await msg.reply_text("\n".join(lines))


ADDEX_PHOTO = 7

async def addexdrink_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addexdrink <id> | <name> | <description> | [special=yes/no] | [rarity] — начало добавления."""
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return ConversationHandler.END

    raw = (msg.text or "").partition(" ")[2].strip()
    if not raw:
        await msg.reply_text("Использование: /addexdrink <id> | <name> | <description> | [special=yes/no]\nПример: /addexdrink 9001 | Achievement Cola | За событие | yes")
        return ConversationHandler.END

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await msg.reply_text("Нужно минимум 3 части через '|': <id> | <name> | <description> | [special=yes/no] | [rarity]")
        return ConversationHandler.END

    try:
        drink_id = int(parts[0])
    except ValueError:
        await msg.reply_text(f"❌ ID '{parts[0]}' должен быть числом.\nПример: /addexdrink 9001 | ...")
        return ConversationHandler.END

    name = parts[1]
    description = parts[2]
    special = _parse_yes_no(parts[3], default=True) if len(parts) >= 4 else True
    rarity = parts[4] if len(parts) >= 5 else None

    # Сохраняем данные во временное хранилище
    context.user_data['addex_data'] = {
        'id': drink_id,
        'name': name,
        'description': description,
        'special': special,
        'rarity': rarity
    }

    await msg.reply_text(
        f"📝 Данные получены:\nID: {drink_id}\nНазвание: {name}\nСпец: {special}\n\n"
        "📸 Теперь отправьте <b>ФОТО</b> энергетика или нажмите /skip для пропуска."
    )
    return ADDEX_PHOTO

async def addexdrink_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото для addexdrink."""
    msg = update.message
    data = context.user_data.get('addex_data')
    if not data:
        await msg.reply_text("Ошибка контекста. Начните заново /addexdrink")
        return ConversationHandler.END

    image_path = None
    if msg.photo:
        try:
            photo_file = msg.photo[-1]
            file = await context.bot.get_file(photo_file.file_id)
            os.makedirs(ENERGY_IMAGES_DIR, exist_ok=True)
            image_path = f"{int(time.time())}_{random.randint(1000,9999)}.jpg"
            await file.download_to_drive(os.path.join(ENERGY_IMAGES_DIR, image_path))
        except Exception as e:
            await msg.reply_text(f"❌ Ошибка загрузки фото: {e}")
            return ConversationHandler.END
    
    return await _finalize_addex(update, context, data, image_path)

async def addexdrink_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск фото для addexdrink."""
    data = context.user_data.get('addex_data')
    if not data:
        await update.message.reply_text("Ошибка контекста. Начните заново /addexdrink")
        return ConversationHandler.END
    
    return await _finalize_addex(update, context, data, None)

async def _finalize_addex(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, image_path: str | None):
    try:
        drink = db.add_energy_drink_with_id(
            data['id'], 
            data['name'], 
            data['description'], 
            image_path=image_path, 
            is_special=data['special'],
            default_rarity=data.get('rarity')
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при сохранении: {e}")
        return ConversationHandler.END

    extra = ""
    rarity = data.get('rarity')
    special = data.get('special')
    
    if rarity:
        extra = f"\n⚠️ Редкость '{rarity}' СОХРАНЕНА как дефолтная. При выдаче (/giveexdrink) её можно не указывать."
        if not special and rarity not in RARITIES:
             extra += "\n❗ Внимание: НЕ-специальный энергетик с нестандартной редкостью."

    await update.message.reply_text(
        f"✅ Энергетик сохранён!\nID: {drink.id}\nНазвание: {drink.name}\nОсобенный: {'да' if drink.is_special else 'нет'}{extra}"
    )
    context.user_data.pop('addex_data', None)
    return ConversationHandler.END

async def addexdrink_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('addex_data', None)
    await update.message.reply_text("❌ Добавление отменено.")
    return ConversationHandler.END


async def giveexdrink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/giveexdrink <user_id|@username> <drink_id> [rarity] [qty=1] — выдать эксклюзивный энергетик.
    Если rarity не указан, берется дефолтный из базы.
    """
    msg = update.message
    user = update.effective_user
    if not _is_creator_or_lvl3(user):
        await msg.reply_text("Нет прав: команда доступна только Создателю и ур.3.")
        return

    args = context.args or []
    if len(args) < 2:
        await msg.reply_text("Использование: /giveexdrink <user_id|@username> <drink_id> [rarity] [qty=1]")
        return

    target_raw = args[0]
    drink_id_raw = args[1]
    
    # Парсим drink_id
    try:
        m = re.search(r"\d+", str(drink_id_raw))
        if not m:
            raise ValueError("no digits")
        drink_id = int(m.group(0))
    except ValueError:
        await msg.reply_text("ID энергетика должен быть числом.")
        return

    # Парсим target (user_id или username)
    target_id: int | None = None
    target_username: str | None = None
    try:
        raw = str(target_raw).strip()
        if raw.lstrip('+').isdigit():
            target_id = int(raw)
        else:
            target_username = raw[1:] if raw.startswith('@') else raw
    except Exception:
        target_id = None
        target_username = None

    # Логика разбора 3 и 4 аргументов (rarity, qty)
    # Возможные варианты:
    # 2 args: user drink -> rarity=default, qty=1
    # 3 args: user drink qty(int) -> rarity=default, qty=N
    # 3 args: user drink rarity(str) -> rarity=STR, qty=1
    # 4 args: user drink rarity qty -> rarity=STR, qty=N
    
    rarity = None
    qty = 1
    
    if len(args) >= 3:
        arg3 = args[2]
        # Проверяем, число ли это
        if arg3.isdigit():
            # Это количество, значит редкость не указана (флаг авто)
            qty = int(arg3)
        else:
            # Это строка, значит редкость
            rarity = arg3
            
    if len(args) >= 4:
        # Если было 4 аргумента, то 3-й точно редкость, а 4-й количество
        if args[3].isdigit():
            qty = int(args[3])
    
    # Если редкость не определена из аргументов, берем из базы
    if not rarity:
        drink = db.get_drink_by_id(drink_id)
        if drink and isinstance(drink, dict):
            # В get_drink_by_id возвращается словарь, но там может не быть default_rarity, т.к. мы его только добавили
            pass 
        # Лучше запросить через модель напрямую, если хелпер не обновлен
        # Но у нас есть db.get_drink_by_id. 
        # Давайте обновим get_drink_by_id в database.py или сделаем прямой запрос тут? 
        # Проще пока сделать фоллбэк: если нет в базе - ошибка или дефолт
        
        # Попробуем получить default_rarity через сессию (или обновим get_drink_by_id, но это лишний шаг)
        # В database.py get_drink_by_id возвращает dict, но мы не обновляли его код, чтобы возвращал default_rarity.
        # Поэтому сделаем прямой запрос к DB или используем add_energy_drink_with_id (нет, он для записи)
        
        # Получим default_rarity "хаком" или добавим функцию в db. 
        # Добавим функцию get_drink_default_rarity в db в следующем шаге? Нет, лучше сразу тут, если есть доступ к DB session? 
        # В admin2.py импортирован db, но сессии там нет.
        # Сделаем запрос через существующий механизм или добавим хелпер.
        # Пока предположим, что rarity обязателен, если нет дефолта.
        
        # Давайте запросим default_rarity.
        try:
            default_rarity = None
            try:
                default_rarity = getattr(drink, 'default_rarity', None)
            except Exception:
                default_rarity = None
            if not default_rarity and isinstance(drink, dict):
                default_rarity = drink.get('default_rarity')
            if default_rarity:
                rarity = str(default_rarity)
        except Exception:
            rarity = None

    # Валидируем drink
    drink_obj = db.get_drink_by_id(drink_id)
    if not drink_obj:
        await msg.reply_text(f"❌ Энергетик с ID {drink_id} не найден.")
        return

    # Если редкость всё ещё не определена — просим указать
    if not rarity:
        await msg.reply_text("❌ Редкость не указана и в базе нет default_rarity для этого напитка. Укажите rarity вручную: /giveexdrink <user> <drink_id> <rarity> [qty]")
        return

    # Валидируем qty
    try:
        qty = int(qty)
    except Exception:
        qty = 1
    if qty <= 0:
        await msg.reply_text("❌ Количество должно быть положительным числом.")
        return

    # Разрешение пользователя через единый поиск
    if target_id is None:
        ident = f"@{target_username}" if target_username else str(target_raw)
        res = db.find_player_by_identifier(ident)
        if res.get('reason') == 'multiple':
            lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            await msg.reply_text("\n".join(lines))
            return
        if res.get('ok') and res.get('player'):
            p = res['player']
            target_id = int(getattr(p, 'user_id', 0) or 0) or None
            target_username = getattr(p, 'username', None) or target_username
        else:
            # Фоллбэк: попробуем получить ID через Telegram
            if target_username:
                try:
                    chat_obj = await context.bot.get_chat(f"@{target_username}")
                    if getattr(chat_obj, 'id', None):
                        target_id = int(chat_obj.id)
                except Exception:
                    pass

    if target_id is None:
        shown = f"@{target_username}" if target_username else str(target_raw)
        await msg.reply_text(f"❌ Не удалось определить пользователя {shown}.")
        return

    # Регистрируем игрока, чтобы инвентарь был привязан к players
    try:
        db.get_or_create_player(target_id, target_username or str(target_id))
    except Exception:
        pass

    # Выдаём
    ok = False
    try:
        ok = bool(db.add_custom_drink_to_inventory(target_id, drink_id, str(rarity), int(qty)))
    except Exception:
        ok = False

    if not ok:
        await msg.reply_text("❌ Не удалось выдать энергетик (ошибка БД).")
        return

    # Сообщение об успехе
    try:
        drink_name = (drink_obj or {}).get('name') if isinstance(drink_obj, dict) else getattr(drink_obj, 'name', None)
    except Exception:
        drink_name = None
    drink_name = drink_name or f"ID {drink_id}"
    shown = f"@{target_username}" if target_username else str(target_id)
    await msg.reply_text(f"✅ Выдано: {drink_name} (ID {drink_id})\nПользователь: {shown}\nРедкость: {rarity}\nКол-во: {qty}")

    return


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
        res = db.find_player_by_identifier(target)
        if res.get('reason') == 'multiple':
            lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            await msg.reply_text("\n".join(lines))
            return
        if not (res.get('ok') and res.get('player')):
            await msg.reply_text(f"❌ Пользователь {target} не найден в базе данных.")
            return
        target_player = res['player']
        
        # Добавляем буст
        try:
            success = db.add_auto_search_boost(target_player.user_id, count, days)
            if success:
                # Заметка: запись в boost_history уже добавляется внутри db.add_auto_search_boost()
                
                # Получаем информацию о новом лимите
                new_limit = db.get_auto_search_daily_limit(target_player.user_id)
                from datetime import datetime
                import time
                player = db.get_or_create_player(target_player.user_id, target_player.username)
                boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
                boost_end_date = datetime.fromtimestamp(boost_until).strftime('%Y-%m-%d %H:%M:%S')
                
                # Уведомляем администратора
                shown = f"@{getattr(target_player, 'username', None)}" if getattr(target_player, 'username', None) else str(target_player.user_id)
                await msg.reply_text(
                    f"✅ Автопоиск буст на {count} дополнительных поисков на {days} дней добавлен пользователю {shown}.\n"
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
        res = db.find_player_by_identifier(target)
        if res.get('reason') == 'multiple':
            lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            await msg.reply_text("\n".join(lines))
            return
        if not (res.get('ok') and res.get('player')):
            await msg.reply_text(f"❌ Пользователь {target} не найден в базе данных.")
            return
        target_player = res['player']
        
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
            shown = f"@{getattr(target_player, 'username', None)}" if getattr(target_player, 'username', None) else str(target_player.user_id)
            await msg.reply_text(f"✅ VIP статус на {days} дней добавлен пользователю {shown}.\nVIP активен до: {vip_end_date}")
            
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
    res = db.find_player_by_identifier(target)
    if res.get('reason') == 'multiple':
        lines = ["Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        await msg.reply_text("\n".join(lines))
        return
    if not (res.get('ok') and res.get('player')):
        await msg.reply_text("Пользователь не найден.")
        return
    target_user_id = int(res['player'].user_id)
    player = db.get_or_create_player(target_user_id, res['player'].username)
    boost_info_before = db.get_boost_info(target_user_id)
    if not boost_info_before.get('is_active'):
        user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        await msg.reply_text(f"РЈ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_info} РЅРµС‚ Р°РєС‚РёРІРЅРѕРіРѕ Р±СѓСЃС‚Р° Р°РІС‚РѕРїРѕРёСЃРєР°.")
        return

    removed = db.remove_auto_search_boost(
        target_user_id,
        removed_by=user.id,
        removed_by_username=user.username,
        history_action='removed',
    )
    if not removed:
        await msg.reply_text("РќРµ СѓРґР°Р»РѕСЃСЊ СѓР±СЂР°С‚СЊ Р±СѓСЃС‚.")
        return

    user_info = f"@{player.username}" if player.username else f"ID: {player.user_id}"
    await msg.reply_text(f"вњ… Р‘СѓСЃС‚ Р°РІС‚РѕРїРѕРёСЃРєР° СѓР±СЂР°РЅ Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_info}.")

    try:
        from datetime import datetime
        boost_end_formatted = datetime.fromtimestamp(int(boost_info_before.get('boost_until', 0) or 0)).strftime('%d.%m.%Y %H:%M')
        new_limit = db.get_auto_search_daily_limit(player.user_id)
        user_notification = (
            f"рџљ« Р’Р°С€ Р°РІС‚РѕРїРѕРёСЃРє Р±СѓСЃС‚ Р±С‹Р» РѕС‚РјРµРЅС‘РЅ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРј.\n"
            f"рџљЂ РћС‚РјРµРЅС‘РЅРЅС‹Р№ Р±СѓСЃС‚: +{int(boost_info_before.get('boost_count', 0) or 0)} РїРѕРёСЃРєРѕРІ\n"
            f"рџ“… Р”РµР№СЃС‚РІРѕРІР°Р» РґРѕ: {boost_end_formatted}\n"
            f"рџ“Љ РќРѕРІС‹Р№ РґРЅРµРІРЅРѕР№ Р»РёРјРёС‚: {new_limit}"
        )
        await context.bot.send_message(chat_id=player.user_id, text=user_notification)
    except Exception as e:
        logger.warning(f"[BOOST_NOTIFY] Failed to notify user {user_info} about boost removal: {e}")
    return
    
    from database import SessionLocal, Player
    
    dbs = SessionLocal()
    try:
        # Ищем пользователя
        player = dbs.query(Player).filter(Player.user_id == target_user_id).first()
        
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
    res = db.find_player_by_identifier(target)
    if res.get('reason') == 'multiple':
        lines = ["Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        await msg.reply_text("\n".join(lines))
        return
    if not (res.get('ok') and res.get('player')):
        await msg.reply_text("Пользователь не найден.")
        return
    target_user_id = int(res['player'].user_id)
    
    from database import SessionLocal, Player
    
    dbs = SessionLocal()
    try:
        # Ищем пользователя
        player = dbs.query(Player).filter(Player.user_id == target_user_id).first()
        
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
