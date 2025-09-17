# file: Bot_new.py

import os
import logging
import random
import time
import asyncio
import secrets
import html
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ForceReply
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import database as db
from collections import defaultdict
import config
from typing import Dict
from fullhelp import fullhelp_command
from admin import admin_command
from admin2 import (
    admin2_command,
    receipt_command,
    verifyreceipt_command,
    tgstock_command,
    tgadd_command,
    tgset_command,
    stock_command,
    stockadd_command,
    stockset_command,
    addvip_command,
    addautosearch_command,
    listboosts_command,
    removeboost_command,
    booststats_command,
    boosthistory_command,
)
from constants import (
    SEARCH_COOLDOWN,
    DAILY_BONUS_COOLDOWN,
    ENERGY_IMAGES_DIR,
    RARITIES,
    COLOR_EMOJIS,
    RARITY_ORDER,
    ITEMS_PER_PAGE,
    VIP_EMOJI,
    VIP_COSTS,
    VIP_DURATIONS_SEC,
    TG_PREMIUM_COST,
    TG_PREMIUM_DURATION_SEC,
    ADMIN_USERNAMES,
    AUTO_SEARCH_DAILY_LIMIT,
    CASINO_WIN_PROB,
    RECEIVER_PRICES,
    RECEIVER_COMMISSION,
    SHOP_PRICES,
    SILK_EMOJIS,
)
import silk_ui
# --- Настройки ---
# Константы импортируются из constants.py

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Константы ---
# см. constants.py

# --- VIP настройки ---
# см. constants.py

# --- TG Premium настройки ---
# Стоимость (в септимах) и длительность (в секундах) для 3 месяцев
# (импортируются из constants.py)

# ADMIN_USERNAMES импортируется из constants.py
ADMIN_USER_IDS: set[int] = set()  # legacy, больше не используется для прав, оставлено для обратной совместимости

ADD_NAME, ADD_DESCRIPTION, ADD_SPECIAL, ADD_PHOTO = range(4)

PENDING_ADDITIONS: dict[int, dict] = {}
NEXT_PENDING_ID = 1

GIFT_OFFERS: dict[int, dict] = {}
NEXT_GIFT_ID = 1
GIFT_SELECT_TOKENS: dict[str, dict] = {}

# --- Блокировки для предотвращения даблкликов/гонок ---
_LOCKS: Dict[str, asyncio.Lock] = {}

# --- Ожидание причины отклонения (ключ = (chat_id, prompt_message_id)) ---
REJECT_PROMPTS: Dict[tuple[int, int], dict] = {}

def _get_lock(key: str) -> asyncio.Lock:
    lock = _LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[key] = lock
    return lock

# --- Магазин: кэш предложений на пользователя ---
# SHOP_OFFERS[user_id] = { 'offers': [ {idx, drink_id, drink_name, rarity} ], 'ts': int }
SHOP_OFFERS: Dict[int, dict] = {}

TEXTS = {
    'menu_title': {
        'ru': 'Привет, {user}!\n\nЧто будем делать?',
        'en': 'Hi, {user}!\n\nWhat shall we do?'
    },
    'search': {'ru': '🔎 Найти энергетик', 'en': '🔎 Find energy'},
    'inventory': {'ru': '📦 Инвентарь', 'en': '📦 Inventory'},
    'stats': {'ru': '📊 Статистика', 'en': '📊 Stats'},
    'settings': {'ru': '⚙️ Настройки', 'en': '⚙️ Settings'},
    # --- Settings menu ---
    'settings_title': {'ru': '⚙️ Настройки', 'en': '⚙️ Settings'},
    'current_language': {'ru': '🌐 Язык', 'en': '🌐 Language'},
    'auto_reminder': {'ru': '⏰ Автонапоминание', 'en': '⏰ Auto-reminder'},
    'on': {'ru': 'Вкл', 'en': 'On'},
    'off': {'ru': 'Выкл', 'en': 'Off'},
    'btn_change_lang': {'ru': '🌐 Изменить язык', 'en': '🌐 Change language'},
    'btn_toggle_rem': {'ru': '⏰ Переключить напоминание', 'en': '⏰ Toggle reminder'},
    'auto_search': {'ru': '🤖 Автопоиск VIP', 'en': '🤖 VIP Auto-search'},
    'btn_toggle_auto': {'ru': '🤖 Переключить автопоиск VIP', 'en': '🤖 Toggle VIP auto-search'},
    'auto_requires_vip': {'ru': 'Эта функция доступна только с активным V.I.P.', 'en': 'This feature requires an active V.I.P.'},
    'auto_enabled': {'ru': 'Автопоиск включён. Лимит: {limit}/сутки.', 'en': 'Auto-search enabled. Limit: {limit}/day.'},
    'auto_disabled': {'ru': 'Автопоиск выключен.', 'en': 'Auto-search disabled.'},
    'auto_limit_reached': {'ru': 'Дневной лимит автопоиска исчерпан. Автопоиск отключён до сброса.', 'en': 'Daily auto-search limit reached. Auto-search disabled until reset.'},
    'auto_vip_expired': {'ru': 'Срок V.I.P. истёк. Автопоиск отключён.', 'en': 'V.I.P. expired. Auto-search has been disabled.'},
    'btn_reset': {'ru': '🔄 Сброс данных', 'en': '🔄 Reset data'},
    'btn_back': {'ru': '🔙 Назад', 'en': '🔙 Back'},
    'choose_lang': {'ru': 'Выберите язык:', 'en': 'Choose language:'},
    'confirm_delete': {'ru': 'Точно удалить все ваши данные?', 'en': 'Really delete all your data?'},
    'data_deleted': {'ru': 'Ваши данные удалены. Перезапустите /start', 'en': 'Your data has been erased. Use /start to begin again.'},
    'daily_bonus': {'ru': '🎁 Ежедневный бонус', 'en': '🎁 Daily Bonus'},
    # --- Extra bonuses ---
    'extra_bonuses': {'ru': '🎁 Доп. Бонусы', 'en': '🎁 Extra Bonuses'},
    'extra_bonuses_title': {'ru': 'Выберите дополнительный бонус:', 'en': 'Choose an extra bonus:'},
    'tg_premium_3m': {'ru': 'ТГ премиум (3 мес)', 'en': 'TG Premium (3 mo)'},
    'steam_game_500': {'ru': 'Игра в стиме (500 грн)', 'en': 'Steam game (500 UAH)'},
    'tg_premium_details': {
        'ru': '<b>ТГ премиум (3 мес)</b>\n\nДоступно при наличии на складе. Вы можете приобрести, если товар в наличии.',
        'en': '<b>TG Premium (3 months)</b>\n\nAvailable while in stock. You can purchase when it is in stock.'
    },
    'steam_game_details': {
        'ru': '<b>Игра в стиме (500 грн)</b>\n\nДоступно при наличии на складе. Покупка возможна при наличии.',
        'en': '<b>Steam game (500 UAH)</b>\n\nAvailable while in stock. Purchase is possible when in stock.'
    },
    # TG Premium — тексты для покупки
    'tg_title': {'ru': '<b>ТГ премиум (3 мес)</b>', 'en': '<b>TG Premium (3 months)</b>'},
    'tg_price': {'ru': 'Цена: {cost} септимов', 'en': 'Price: {cost} septims'},
    'tg_stock': {'ru': 'Остаток на складе: {stock}', 'en': 'Stock left: {stock}'},
    'tg_until': {'ru': 'TG Premium активен до: {dt}', 'en': 'TG Premium active until: {dt}'},
    'tg_buy': {'ru': 'Купить', 'en': 'Buy'},
    'tg_not_enough': {'ru': 'Недостаточно монет.', 'en': 'Not enough coins.'},
    'tg_out_of_stock': {'ru': 'Нет в наличии.', 'en': 'Out of stock.'},
    'tg_bought': {'ru': 'Покупка успешна! 💎 До: {dt}\nБаланс: {coins}', 'en': 'Purchased! 💎 Until: {dt}\nBalance: {coins}'},
    'tg_insufficient': {'ru': '❗ Недостаточно монет: {coins}/{cost}', 'en': '❗ Not enough coins: {coins}/{cost}'},
    'tg_view_receipt': {'ru': '🧾 Показать чек', 'en': '🧾 View receipt'},
    'tg_my_receipts': {'ru': '🧾 Мои чеки', 'en': '🧾 My receipts'},
    # TG Premium — админ-команды (локализация)
    'tg_admin_stock_view': {
        'ru': 'Текущий остаток TG Premium: {stock}',
        'en': 'Current TG Premium stock: {stock}'
    },
    'tg_admin_added': {
        'ru': 'Остаток изменён на {delta}. Новый остаток: {stock}',
        'en': 'Stock changed by {delta}. New stock: {stock}'
    },
    'tg_admin_set': {
        'ru': 'Остаток установлен: {stock}',
        'en': 'Stock set to: {stock}'
    },
    'tg_admin_usage_add': {
        'ru': 'Использование: /tgadd <число> (может быть отрицательным)',
        'en': 'Usage: /tgadd <number> (may be negative)'
    },
    'tg_admin_usage_set': {
        'ru': 'Использование: /tgset <число>' ,
        'en': 'Usage: /tgset <number>'
    },
    'admin_denied_lvl3': {
        'ru': 'Нет прав: команда доступна только Создателю и ур.3.',
        'en': 'No permission: only Creator and level 3 admins.'
    },
    # --- V.I.P submenu ---
    'vip': {'ru': 'V.I.P', 'en': 'V.I.P'},
    'vip_title': {
        'ru': 'Выберите срок V.I.P:\n\nПреимущества:\n• 👑 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.5\n• 🎁 Кулдаун ежедневного бонуса — x0.5\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД',
        'en': 'Choose V.I.P duration:\n\nPerks:\n• 👑 Badge in the leaderboard\n• ⏱ Search cooldown — x0.5\n• 🎁 Daily bonus cooldown — x0.5\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown'
    },
    'vip_1d': {'ru': '1 День', 'en': '1 Day'},
    'vip_7d': {'ru': '7 дней', 'en': '7 days'},
    'vip_30d': {'ru': '30 дней', 'en': '30 days'},
    'vip_details_1d': {
        'ru': '<b>V.I.P на 1 день</b>\n\nПреимущества:\n• 👑 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.5\n• 🎁 Кулдаун ежедневного бонуса — x0.5\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n',
        'en': '<b>V.I.P for 1 day</b>\n\nPerks:\n• 👑 Badge in the leaderboard\n• ⏱ Search cooldown — x0.5\n• 🎁 Daily bonus cooldown — x0.5\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n'
    },
    'vip_details_7d': {
        'ru': '<b>V.I.P на 7 дней</b>\n\nПреимущества:\n• 👑 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.5\n• 🎁 Кулдаун ежедневного бонуса — x0.5\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n',
        'en': '<b>V.I.P for 7 days</b>\n\nPerks:\n• 👑 Badge in the leaderboard\n• ⏱ Search cooldown — x0.5\n• 🎁 Daily bonus cooldown — x0.5\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n'
    },
    'vip_details_30d': {
        'ru': '<b>V.I.P на 30 дней</b>\n\nПреимущества:\n• 👑 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.5\n• 🎁 Кулдаун ежедневного бонуса — x0.5\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n',
        'en': '<b>V.I.P for 30 days</b>\n\nPerks:\n• 👑 Badge in the leaderboard\n• ⏱ Search cooldown — x0.5\n• 🎁 Daily bonus cooldown — x0.5\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n'
    },
    'vip_buy': {'ru': 'Купить', 'en': 'Buy'},
    'vip_price': {'ru': 'Цена: {cost} септимов', 'en': 'Price: {cost} septims'},
    'vip_until': {'ru': 'V.I.P активен до: {dt}', 'en': 'V.I.P active until: {dt}'},
    'vip_not_enough': {'ru': 'Недостаточно монет.', 'en': 'Not enough coins.'},
    'vip_bought': {'ru': 'Покупка успешна! {emoji} До: {dt}\nБаланс: {coins}', 'en': 'Purchased! {emoji} Until: {dt}\nBalance: {coins}'},
    'vip_insufficient': {
        'ru': '❗ Недостаточно монет: {coins}/{cost}',
        'en': '❗ Not enough coins: {coins}/{cost}'
    },
    # --- VIP menu: auto-search info ---
    'vip_auto_header': {'ru': '\n<b>🤖 Автопоиск</b>', 'en': '\n<b>🤖 Auto-search</b>'},
    'vip_auto_state': {'ru': 'Состояние: {state}', 'en': 'State: {state}'},
    'vip_auto_today': {'ru': 'Сегодня: {count}/{limit}', 'en': 'Today: {count}/{limit}'},
    # --- Stars submenu ---
    'stars': {'ru': '⭐ Звезды', 'en': '⭐ Stars'},
    'stars_title': {'ru': 'Выберите пакет звёзд:', 'en': 'Choose a stars pack:'},
    'stars_500': {'ru': '500 звёзд', 'en': '500 stars'},
    'stars_details_500': {
        'ru': '<b>Пакет 500 звёзд</b>\n\nДоступно при наличии на складе. Вы можете приобрести пакет, если он в наличии.',
        'en': '<b>Pack of 500 stars</b>\n\nAvailable while in stock. You can purchase when it is in stock.'
    },
}

def t(lang: str, key: str) -> str:
    return TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get('ru', key))

# --- Функции-обработчики для кнопок ---

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню. УМЕЕТ ОБРАБАТЫВАТЬ ВОЗВРАТ С ФОТО."""
    user = update.effective_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)

    # Проверка кулдауна поиска (VIP — в 2 раза меньше)
    vip_active = db.is_vip(player.user_id)
    search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
    search_time_left = max(0, search_cd - (time.time() - player.last_search))
    lang = player.language

    base_search = t(lang, 'search')
    if search_time_left > 0:
        search_status = f"{base_search} (⏳ {int(search_time_left // 60)}:{int(search_time_left % 60):02d})"
    else:
        search_status = base_search

    # Проверка кулдауна ежедневного бонуса (VIP — в 2 раза меньше)
    bonus_cd = DAILY_BONUS_COOLDOWN / 2 if vip_active else DAILY_BONUS_COOLDOWN
    bonus_time_left = max(0, bonus_cd - (time.time() - player.last_bonus_claim))
    base_bonus = t(lang, 'daily_bonus')
    if bonus_time_left > 0:
        hours, remainder = divmod(int(bonus_time_left), 3600)
        minutes, seconds = divmod(remainder, 60)
        bonus_status = f"{base_bonus} (⏳ {hours:02d}:{minutes:02d}:{seconds:02d})"
    else:
        bonus_status = base_bonus

    keyboard = [
        [InlineKeyboardButton(search_status, callback_data='find_energy')],
        [InlineKeyboardButton(bonus_status, callback_data='claim_bonus')],
        [InlineKeyboardButton(t(lang, 'extra_bonuses'), callback_data='extra_bonuses')],
        [InlineKeyboardButton("🏙️ Города", callback_data='cities_menu')],
        [InlineKeyboardButton(t(lang, 'inventory'), callback_data='inventory')],
        [InlineKeyboardButton(t(lang, 'stats'), callback_data='stats')],
        [InlineKeyboardButton(t(lang, 'settings'), callback_data='settings')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    menu_text = t(lang, 'menu_title').format(user=user.mention_html())
    
    query = update.callback_query
    
    # Если это команда /start, а не нажатие кнопки
    if not query:
        await update.message.reply_html(menu_text, reply_markup=reply_markup)
        return

    message = query.message
    
    # >>>>> ГЛАВНОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ <<<<<
    # Если сообщение, с которого пришел запрос, содержит фото
    if message.photo:
        # Мы не можем его отредактировать. Удаляем и отправляем новое.
        try:
            await message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение с фото: {e}")
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # Если это обычное текстовое сообщение, редактируем его
        try:
            await message.edit_text(
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения в меню: {e}")


async def search_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: напоминание о завершении кулдауна поиска."""
    try:
        await context.bot.send_message(chat_id=context.job.chat_id, text="Кулдаун закончился! Можно искать снова.")
    except Exception as ex:
        logger.warning(f"Не удалось отправить напоминание (job): {ex}")

async def auto_search_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: периодически выполняет автопоиск для VIP-пользователей.
    Самопереназначается с интервалом, равным оставшемуся кулдауну.
    Останавливается при исчерпании лимита/окончании VIP/выключении пользователем.
    """
    try:
        user_id = context.job.chat_id
        player = db.get_or_create_player(user_id, str(user_id))

        # Если пользователь успел выключить автопоиск — выходим (не переназначаем)
        if not getattr(player, 'auto_search_enabled', False):
            return

        # Проверка VIP
        if not db.is_vip(user_id):
            db.update_player(user_id, auto_search_enabled=False)
            lang = player.language
            try:
                await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_vip_expired'))
            except Exception:
                pass
            return

        # Сброс дневного счётчика при наступлении reset_ts или если он не установлен
        now_ts = int(time.time())
        reset_ts = int(getattr(player, 'auto_search_reset_ts', 0) or 0)
        count = int(getattr(player, 'auto_search_count', 0) or 0)
        if reset_ts == 0 or now_ts >= reset_ts:
            count = 0
            reset_ts = now_ts + 24*60*60
            db.update_player(user_id, auto_search_count=count, auto_search_reset_ts=reset_ts)

        # Лимит в сутки (с учётом возможного буста)
        daily_limit = db.get_auto_search_daily_limit(user_id)
        if count >= daily_limit:
            db.update_player(user_id, auto_search_enabled=False)
            lang = player.language
            try:
                await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_limit_reached'))
            except Exception:
                pass
            return

        # Учитываем кулдаун (с VIP - x0.5)
        vip_active = True  # уже проверили выше
        eff_search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
        time_since_last = time.time() - float(getattr(player, 'last_search', 0) or 0.0)
        if time_since_last < eff_search_cd:
            delay = max(1.0, eff_search_cd - time_since_last)
            try:
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=delay,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
            except Exception:
                pass
            return

        # Анти-гонки: используем общий локер для поиска
        lock = _get_lock(f"user:{user_id}:search")
        if lock.locked():
            # Если параллельно идёт ручной поиск — попробуем позже
            try:
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=5,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
            except Exception:
                pass
            return
        async with lock:
            result = await _perform_energy_search(user_id, player.username or str(user_id), context)

        if result.get('status') == 'ok':
            # Инкремент счётчика и переназначение по кулдауну
            try:
                player = db.get_or_create_player(user_id, player.username or str(user_id))
                count = int(getattr(player, 'auto_search_count', 0) or 0) + 1
                db.update_player(user_id, auto_search_count=count)
            except Exception:
                pass

            # Отправим пользователю уведомление с найденным предметом
            try:
                img_path = result.get("image_path")
                if img_path and os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            caption=result.get("caption"),
                            reply_markup=result.get("reply_markup"),
                            parse_mode='HTML'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=result.get("caption"),
                        reply_markup=result.get("reply_markup"),
                        parse_mode='HTML'
                    )
            except Exception:
                pass

            # Если достигнут лимит — отключаем и уведомляем
            daily_limit = db.get_auto_search_daily_limit(user_id)
            if count >= daily_limit:
                db.update_player(user_id, auto_search_enabled=False)
                lang = player.language
                try:
                    await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_limit_reached'))
                except Exception:
                    pass
                return

            # Назначаем следующий запуск после полного КД
            try:
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=eff_search_cd,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
            except Exception:
                pass
            return

        elif result.get('status') == 'cooldown':
            delay = max(1.0, float(result.get('time_left', 5)))
            try:
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=delay,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
            except Exception:
                pass
            return
        elif result.get('status') == 'no_drinks':
            # Сообщим один раз и попробуем через 10 минут
            try:
                await context.bot.send_message(chat_id=user_id, text="В базе данных пока нет энергетиков для автопоиска.")
            except Exception:
                pass
            try:
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=600,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
            except Exception:
                pass
            return
    except Exception:
        logger.exception("[AUTO] Ошибка в auto_search_job")
        # На случай исключений попробуем снова через 1 минуту
        try:
            context.application.job_queue.run_once(
                auto_search_job,
                when=60,
                chat_id=context.job.chat_id if getattr(context, 'job', None) else None,
                name=f"auto_search_{context.job.chat_id}" if getattr(context, 'job', None) else None,
            )
        except Exception:
            pass

async def silk_harvest_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка готовности урожая шёлка."""
    try:
        import silk_city
        # Обновить статусы всех плантаций
        updated_count = silk_city.update_plantation_statuses()
        
        if updated_count > 0:
            logger.info(f"[SILK] Updated {updated_count} plantations to ready status")
            
            # Получить все готовые плантации и отправить уведомления
            ready_plantations = db.get_ready_silk_plantations()
            
            # Группировать по пользователям
            users_ready = {}
            for plantation in ready_plantations:
                user_id = plantation.player_id
                if user_id not in users_ready:
                    users_ready[user_id] = []
                users_ready[user_id].append(plantation)
            
            # Отправить уведомления
            for user_id, plantations in users_ready.items():
                await send_silk_harvest_notification(context, user_id, plantations)
    
    except Exception as e:
        logger.error(f"[SILK] Error in silk harvest reminder job: {e}")

async def send_silk_harvest_notification(context: ContextTypes.DEFAULT_TYPE, user_id: int, plantations: list):
    """Отправить уведомление о готовности урожая."""
    try:
        count = len(plantations)
        if count == 0:
            return
        
        if count == 1:
            plantation = plantations[0]
            text = (
                f"{SILK_EMOJIS['ready']} **Урожай готов!**\n\n"
                f"{SILK_EMOJIS['plantation']} Плантация: **{plantation.plantation_name}**\n"
                f"{SILK_EMOJIS['coins']} Ожидаемый доход: **{plantation.expected_yield:,}** септимов\n\n"
                f"Пора собирать шёлк!"
            )
        else:
            text = (
                f"{SILK_EMOJIS['ready']} **Урожай готов!**\n\n"
                f"{SILK_EMOJIS['plantation']} Готово к сбору: **{count} плантаций**\n\n"
            )
            
            total_expected = sum(p.expected_yield for p in plantations)
            for plantation in plantations:
                text += f"• {plantation.plantation_name} ({plantation.expected_yield:,} септимов)\n"
            
            text += f"\n{SILK_EMOJIS['coins']} Общий ожидаемый доход: **{total_expected:,}** септимов"
        
        keyboard = [
            [InlineKeyboardButton(f"{SILK_EMOJIS['plantation']} Мои плантации", callback_data='silk_plantations')],
            [InlineKeyboardButton(f"{SILK_EMOJIS['city']} Город Шёлка", callback_data='city_silk')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.warning(f"[SILK] Failed to send harvest notification to user {user_id}: {e}")

async def _perform_energy_search(user_id: int, username: str, context: ContextTypes.DEFAULT_TYPE):
    """
    Ядро логики поиска энергетика. Проверяет кулдаун, ищет напиток,
    обновляет БД и возвращает результат в виде словаря.
    """
    player = db.get_or_create_player(user_id, username)

    # Проверка кулдауна (VIP — в 2 раза меньше)
    current_time = time.time()
    vip_active = db.is_vip(user_id)
    eff_search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
    if current_time - player.last_search < eff_search_cd:
        time_left = eff_search_cd - (current_time - player.last_search)
        return {"status": "cooldown", "time_left": time_left}

    # Выбираем случайный энергетик
    all_drinks = db.get_all_drinks()
    if not all_drinks:
        return {"status": "no_drinks"}

    found_drink = random.choice(all_drinks)

    # Определяем редкость
    if found_drink.is_special:
        rarity = 'Special'
    else:
        rarity = random.choices(list(RARITIES.keys()), weights=list(RARITIES.values()), k=1)[0]

    # Добавляем в инвентарь и обновляем игрока + награда септимами
    septims_reward = random.randint(5, 10)
    if vip_active:
        septims_reward *= 2
    new_coins = (player.coins or 0) + septims_reward
    db.add_drink_to_inventory(user_id=user_id, drink_id=found_drink.id, rarity=rarity)
    db.update_player(user_id, last_search=current_time, coins=new_coins)
    logger.info(
        f"[SEARCH] User {username} ({user_id}) found {found_drink.name} | rarity={rarity} | +{septims_reward} coins -> {new_coins}"
    )

    # Планируем автонапоминание через JobQueue, если включено (учёт VIP-кулдауна)
    if player.remind and context.application and context.application.job_queue:
        try:
            context.application.job_queue.run_once(
                search_reminder_job,
                when=eff_search_cd,
                chat_id=user_id,
                name=f"search_reminder_{user_id}_{int(time.time())}",
            )
        except Exception as ex:
            logger.warning(f"Не удалось запланировать напоминание: {ex}")

    # Формируем сообщение
    rarity_emoji = COLOR_EMOJIS.get(rarity, '⚫')
    vip_ts = db.get_vip_until(user_id)
    vip_line = f"\n{VIP_EMOJI} V.I.P до: {time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_ts))}" if vip_ts and time.time() < vip_ts else ''
    # TODO: применить эффекты VIP (механика шансов/кд) по согласованию
    caption = (
        f"🎉 Ты нашел энергетик!{vip_line}\n\n"
        f"<b>Название:</b> {found_drink.name}\n"
        f"<b>Редкость:</b> {rarity_emoji} {rarity}\n"
        f"💰 <b>Награда:</b> +{septims_reward} септимов (баланс: {new_coins})\n\n"
        f"<i>{found_drink.description}</i>"
    )
    image_full_path = os.path.join(ENERGY_IMAGES_DIR, found_drink.image_path) if found_drink.image_path else None
    
    return {
        "status": "ok",
        "caption": caption,
        "image_path": image_full_path,
        "reply_markup": InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]])
    }


async def find_energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает поиск энергетика при нажатии на кнопку."""
    query = update.callback_query
    user = query.from_user
    
    # Анти-даблклик: блокируем параллельный поиск у одного пользователя
    lock = _get_lock(f"user:{user.id}:search")
    if lock.locked():
        await query.answer("Поиск уже выполняется…", show_alert=True)
        return
    async with lock:
        # Предварительная проверка кулдауна для быстрого ответа
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        vip_active = db.is_vip(user.id)
        eff_search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
        if time.time() - player.last_search < eff_search_cd:
            await query.answer("Ещё не время! Подожди немного.", show_alert=True)
            return
        
        await query.answer()

        # Плавная анимация поиска
        search_frames = [
            "⏳ Ищем энергетик…",
            "🔍 Ищем энергетик…",
            "🕵️‍♂️ Ищем энергетик…"
        ]
        for frame in search_frames:
            try:
                await query.edit_message_text(frame)
            except BadRequest:
                pass  # может быть, если сообщение не изменилось
            await asyncio.sleep(0.7)

        # Выполняем основную логику
        result = await _perform_energy_search(user.id, user.username or user.first_name, context)

        # Отображаем результат
        if result["status"] == "no_drinks":
            await query.edit_message_text("В базе данных пока нет энергетиков! Запустите скрипт добавления.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]]))
            return
        
        # В случае успеха удаляем старое сообщение и отправляем новое
        await query.message.delete()
        
        if result["status"] == "ok":
            if result["image_path"] and os.path.exists(result["image_path"]):
                with open(result["image_path"], 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=photo,
                        caption=result["caption"],
                        reply_markup=result["reply_markup"],
                        parse_mode='HTML'
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=result["caption"],
                    reply_markup=result["reply_markup"],
                    parse_mode='HTML'
                )


async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логика получения ежедневного бонуса."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    
    # Анти-даблклик: один бонус за раз
    lock = _get_lock(f"user:{user.id}:bonus")
    if lock.locked():
        await query.answer("Запрос бонуса уже обрабатывается…", show_alert=True)
        return
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)

        # Проверка кулдауна
        current_time = time.time()
        vip_active = db.is_vip(user.id)
        eff_bonus_cd = DAILY_BONUS_COOLDOWN / 2 if vip_active else DAILY_BONUS_COOLDOWN
        if current_time - player.last_bonus_claim < eff_bonus_cd:
            time_left = int(eff_bonus_cd - (current_time - player.last_bonus_claim))
            hours, remainder = divmod(time_left, 3600)
            minutes, seconds = divmod(remainder, 60)
            await query.answer(f"Ещё рано! До бонуса: {hours:02d}:{minutes:02d}:{seconds:02d}", show_alert=True)
            return

    # Выбираем случайный энергетик
    all_drinks = db.get_all_drinks()
    if not all_drinks:
        await query.edit_message_text("В базе данных пока нет энергетиков! Бонус не может быть выдан.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]]))
        return
        
    found_drink = random.choice(all_drinks)

    # Определяем редкость
    if found_drink.is_special:
        rarity = 'Special'
    else:
        rarity = random.choices(list(RARITIES.keys()), weights=list(RARITIES.values()), k=1)[0]

    # Добавляем в инвентарь и обновляем игрока
    db.add_drink_to_inventory(user_id=user.id, drink_id=found_drink.id, rarity=rarity)
    db.update_player(user.id, last_bonus_claim=current_time)
    logger.info(
        f"[DAILY BONUS] User {user.username or user.id} ({user.id}) received {found_drink.name} | rarity={rarity}"
    )

    # Формируем сообщение
    rarity_emoji = COLOR_EMOJIS.get(rarity, '⚫')
    vip_ts = db.get_vip_until(user.id)
    vip_line = f"\n{VIP_EMOJI} V.I.P до: {time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_ts))}" if vip_ts and time.time() < vip_ts else ''
    # TODO: применить эффекты VIP (механика шансов/доп. бонусов) по согласованию
    caption = (
        f"🎉 Ты получил свой ежедневный бонус!{vip_line}\n\n"
        f"<b>Название:</b> {found_drink.name}\n"
        f"<b>Редкость:</b> {rarity_emoji} {rarity}\n\n"
        f"<i>{found_drink.description}</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.delete()
    
    image_full_path = os.path.join(ENERGY_IMAGES_DIR, found_drink.image_path) if found_drink.image_path else None
    if image_full_path and os.path.exists(image_full_path):
        with open(image_full_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь игрока с пагинацией."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    inventory_items = db.get_player_inventory_with_details(user_id)

    # Определяем страницу из callback_data: inventory_p{num}
    page = 1
    try:
        if query.data and query.data.startswith('inventory_p'):
            page = int(query.data.removeprefix('inventory_p'))
    except Exception:
        page = 1
    if page < 1:
        page = 1

    # Если пусто
    if not inventory_items:
        inventory_text = "Твой инвентарь пуст. Пора на поиски!"
        keyboard_rows = []
        total_pages = 1
    else:
        # Сортировка и пагинация
        sorted_items = sorted(
            inventory_items,
            key=lambda i: (
                RARITY_ORDER.index(i.rarity) if i.rarity in RARITY_ORDER else len(RARITY_ORDER),
                i.drink.name.lower(),
            )
        )
        total_items = len(sorted_items)
        total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if page > total_pages:
            page = total_pages
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_items = sorted_items[start_idx:end_idx]

        # Текст с учетом страницы
        inventory_text = (
            f"<b>📦 Твой инвентарь</b> — {total_items} предмет(ов)\n"
            f"Страница {page}/{total_pages}\n"
        )
        current_rarity = None
        for item in page_items:
            if item.rarity != current_rarity:
                rarity_emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
                inventory_text += f"\n<b>{rarity_emoji} {item.rarity}</b>\n"
                current_rarity = item.rarity
            inventory_text += f"• {item.drink.name} — <b>{item.quantity} шт.</b>\n"

        # Клавиатура с кнопками предметов (2 в строке)
        keyboard_rows = []
        current_row = []
        for item in page_items:
            btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {item.drink.name}"
            callback = f"view_{item.id}"
            current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
            if len(current_row) == 2:
                keyboard_rows.append(current_row)
                current_row = []
        if current_row:
            keyboard_rows.append(current_row)

    # Пагинация (кнопки навигации)
    if total_pages > 1:
        prev_page = max(1, page - 1)
        next_page = min(total_pages, page + 1)
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"inventory_p{prev_page}" if page > 1 else 'noop'),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"inventory_p{next_page}" if page < total_pages else 'noop'),
        ])

    # Кнопка назад в меню
    keyboard_rows.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    message = query.message
    # Если текущий месседж содержит медиа, удаляем и отправляем новое
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=inventory_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        try:
            await query.edit_message_text(inventory_text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            # На случай, если нельзя отредактировать (например, старое сообщение)
            await context.bot.send_message(
                chat_id=user_id,
                text=inventory_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику игрока."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    inventory_items = db.get_player_inventory_with_details(user_id)
    
    total_drinks = sum(item.quantity for item in inventory_items)
    unique_drinks = len(inventory_items)

    # Подсчитываем количество по редкостям
    rarity_counter = defaultdict(int)
    for item in inventory_items:
        rarity_counter[item.rarity] += item.quantity

    # Определяем топ-3 самых редких напитка (по редкости и затем количеству)
    top_items = sorted(
        inventory_items,
        key=lambda i: (RARITY_ORDER.index(i.rarity) if i.rarity in RARITY_ORDER else len(RARITY_ORDER), -i.quantity)
    )[:3]

    # VIP статус
    vip_ts = db.get_vip_until(user_id)
    vip_active = bool(vip_ts and time.time() < vip_ts)
    vip_line = (
        f"{VIP_EMOJI} V.I.P до: {time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_ts))}\n"
        if vip_active else f"{VIP_EMOJI} V.I.P: нет\n"
    )

    stats_text = (
        f"<b>📊 Твоя статистика:</b>\n\n"
        f"{vip_line}"
        f"💰 Монет: {player.coins}\n"
        f"🥤 Всего энергетиков: {total_drinks}\n"
        f"🔑 Уникальных видов: {unique_drinks}\n\n"
    )

    # Добавляем сводку по редкостям
    stats_text += "<b>По редкостям:</b>\n"
    for rarity in RARITY_ORDER:
        if rarity in rarity_counter:
            emoji = COLOR_EMOJIS.get(rarity, '⚫')
            stats_text += f"{emoji} {rarity}: {rarity_counter[rarity]}\n"
    stats_text += "\n"

    # Топ-3 редких напитка
    if top_items:
        stats_text += "<b>🏆 Твои редкие находки:</b>\n"
        for idx, item in enumerate(top_items, start=1):
            emoji = ['🥇', '🥈', '🥉'][idx - 1] if idx <= 3 else '▫️'
            rarity_emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
            stats_text += f"{emoji} {item.drink.name} ({rarity_emoji} {item.rarity}) — {item.quantity} шт.\n"

    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data='menu')]]

    # Единое поведение: если текущее сообщение с медиа — удаляем и шлём новое
    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_inventory_by_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь игрока с сортировкой по количеству (для Приёмника)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    inventory_items = db.get_player_inventory_with_details(user_id)

    # Определяем страницу из callback_data: receiver_qty_p{num}
    page = 1
    try:
        if query.data and query.data.startswith('receiver_qty_p'):
            page = int(query.data.removeprefix('receiver_qty_p'))
    except Exception:
        page = 1
    if page < 1:
        page = 1

    # Если пусто
    if not inventory_items:
        inventory_text = "Твой инвентарь пуст. Пора на поиски!"
        keyboard_rows = []
        total_pages = 1
    else:
        # Сортировка по количеству (от большего к меньшему) и пагинация
        sorted_items = sorted(
            inventory_items,
            key=lambda i: (-i.quantity, i.drink.name.lower()),  # Сначала по количеству (убывание), потом по имени
        )
        total_items = len(sorted_items)
        total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if page > total_pages:
            page = total_pages
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_items = sorted_items[start_idx:end_idx]

        # Текст с учетом страницы
        inventory_text = (
            f"<b>♻️ Приёмник: Инвентарь по количеству</b>\n"
            f"📎 Отсортировано по убыванию количества\n"
            f"Страница {page}/{total_pages}\n\n"
        )
        
        for item in page_items:
            rarity_emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
            # Вычисляем стоимость продажи
            unit_payout = int(RECEIVER_PRICES.get(item.rarity, 0) * (1.0 - RECEIVER_COMMISSION))
            total_value = unit_payout * item.quantity
            inventory_text += f"{rarity_emoji} <b>{item.drink.name}</b> — {item.quantity} шт. (~{total_value} монет)\n"

        # Клавиатура с кнопками предметов (2 в строке)
        keyboard_rows = []
        current_row = []
        for item in page_items:
            btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {item.drink.name} ({item.quantity})"
            callback = f"view_{item.id}"
            current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
            if len(current_row) == 2:
                keyboard_rows.append(current_row)
                current_row = []
        if current_row:
            keyboard_rows.append(current_row)

    # Пагинация (кнопки навигации)
    if total_pages > 1:
        prev_page = max(1, page - 1)
        next_page = min(total_pages, page + 1)
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"receiver_qty_p{prev_page}" if page > 1 else 'noop'),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"receiver_qty_p{next_page}" if page < total_pages else 'noop'),
        ])

    # Кнопки назад
    keyboard_rows.append([
        InlineKeyboardButton("📋 Обычный инвентарь", callback_data='inventory'),
        InlineKeyboardButton("♻️ К Приёмнику", callback_data='market_receiver')
    ])
    keyboard_rows.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    message = query.message
    # Если текущий месседж содержит медиа, удаляем и отправляем новое
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=inventory_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        try:
            await query.edit_message_text(inventory_text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            # На случай, если нельзя отредактировать (например, старое сообщение)
            await context.bot.send_message(
                chat_id=user_id,
                text=inventory_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )


async def view_inventory_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подробности конкретного напитка из инвентаря."""
    query = update.callback_query
    await query.answer()

    try:
        item_id = int(query.data.split('_')[1])
    except (IndexError, ValueError):
        await query.answer("Ошибка идентификатора предмета", show_alert=True)
        return

    inventory_item = db.get_inventory_item(item_id)
    if not inventory_item:
        await query.answer("Предмет не найден", show_alert=True)
        return

    drink = inventory_item.drink
    rarity = inventory_item.rarity
    rarity_emoji = COLOR_EMOJIS.get(rarity, '⚫')

    caption = (
        f"<b>{drink.name}</b>\n"
        f"Редкость: {rarity_emoji} {rarity}\n"
        f"Количество: <b>{inventory_item.quantity}</b> шт.\n\n"
        f"{drink.description}"
    )

    # Расчёт выплат для кнопок продажи
    unit_payout = int(RECEIVER_PRICES.get(rarity, 0) * (1.0 - RECEIVER_COMMISSION))
    total_payout_all = unit_payout * int(inventory_item.quantity)

    rows = []
    if unit_payout > 0:
        rows.append([InlineKeyboardButton(f"♻️ Продать 1 (+{unit_payout})", callback_data=f"sell_{inventory_item.id}")])
        if inventory_item.quantity > 1:
            rows.append([
                InlineKeyboardButton(
                    f"♻️ Продать всё {inventory_item.quantity} (+{total_payout_all})",
                    callback_data=f"sellall_{inventory_item.id}"
                )
            ])
        # Добавляем кнопку "Продать все кроме одного" только если предметов больше 1
        if inventory_item.quantity > 1:
            total_payout_all_but_one = unit_payout * (int(inventory_item.quantity) - 1)
            rows.append([
                InlineKeyboardButton(
                    f"♻️ Продать все кроме одного ({inventory_item.quantity - 1}) (+{total_payout_all_but_one})",
                    callback_data=f"sellallbutone_{inventory_item.id}"
                )
            ])
    rows.append([InlineKeyboardButton("🔙 Назад к инвентарю", callback_data='inventory')])
    keyboard = InlineKeyboardMarkup(rows)

    image_full_path = os.path.join(ENERGY_IMAGES_DIR, drink.image_path) if drink.image_path else None

    # Удаляем предыдущее сообщение (список инвентаря)
    try:
        await query.message.delete()
    except BadRequest:
        pass

    if image_full_path and os.path.exists(image_full_path):
        with open(image_full_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=caption,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )


# --- Приёмник: обработка продажи ---
async def handle_sell_action(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int, sell_all: bool):
    """Обрабатывает продажу одного предмета или всего количества через Приёмник."""
    query = update.callback_query
    user_id = query.from_user.id

    # Блокировка на (user_id, item_id), чтобы избежать двойных кликов
    lock = _get_lock(f"sell:{user_id}:{item_id}")
    async with lock:
        qty = 10**9 if sell_all else 1
        try:
            result = db.sell_inventory_item(user_id, item_id, qty)
        except Exception:
            await query.answer("Ошибка при продаже. Попробуйте позже.", show_alert=True)
            return

        if not result or not result.get("ok"):
            reason = (result or {}).get("reason")
            reason_map = {
                "not_found": "Предмет не найден",
                "forbidden": "Этот предмет принадлежит другому игроку",
                "bad_quantity": "Некорректное количество",
                "empty": "Количество равно 0",
                "unsupported_rarity": "Эта редкость пока не принимается",
                "exception": "Произошла ошибка. Повторите попытку",
            }
            msg = reason_map.get(reason, "Не удалось выполнить продажу. Повторите попытку позже.")
            await query.answer(msg, show_alert=True)
            return

        # Успешная продажа: обновляем экран инвентаря и шлём инфо-сообщение
        qsold = int(result.get("quantity_sold", 0))
        unit = int(result.get("unit_payout", 0))
        total = int(result.get("total_payout", 0))
        coins_after = int(result.get("coins_after", 0))
        left = int(result.get("item_left_qty", 0))

        # Обновляем инвентарь (внутри будет ответ на callback_query)
        await show_inventory(update, context)

        # Уведомляем об успехе отдельным сообщением (не alert, чтобы избежать двойного answer)
        success_text = (
            f"♻️ Продажа успешна: {qsold} шт. × {unit} = +{total} монет.\n"
            f"Баланс: {coins_after}. Осталось: {left}."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=success_text)
        except Exception:
            pass

# --- Приёмник: обработка продажи всех кроме одного ---
async def handle_sell_all_but_one(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    """Обрабатывает продажу всех предметов кроме одного через Приёмник."""
    query = update.callback_query
    user_id = query.from_user.id

    # Блокировка на (user_id, item_id), чтобы избежать двойных кликов
    lock = _get_lock(f"sell_all_but_one:{user_id}:{item_id}")
    async with lock:
        try:
            result = db.sell_all_but_one(user_id, item_id)
        except Exception:
            await query.answer("Ошибка при продаже. Попробуйте позже.", show_alert=True)
            return

        if not result or not result.get("ok"):
            reason = (result or {}).get("reason")
            reason_map = {
                "not_found": "Предмет не найден",
                "forbidden": "Этот предмет принадлежит другому игроку",
                "not_enough_items": "Недостаточно предметов (нужно больше 1)",
                "unsupported_rarity": "Эта редкость пока не принимается",
                "exception": "Произошла ошибка. Повторите попытку",
            }
            msg = reason_map.get(reason, "Не удалось выполнить продажу. Повторите попытку позже.")
            await query.answer(msg, show_alert=True)
            return

        # Успешная продажа: обновляем экран инвентаря и шлём инфо-сообщение
        qsold = int(result.get("quantity_sold", 0))
        unit = int(result.get("unit_payout", 0))
        total = int(result.get("total_payout", 0))
        coins_after = int(result.get("coins_after", 0))
        left = int(result.get("item_left_qty", 0))

        # Обновляем инвентарь (внутри будет ответ на callback_query)
        await show_inventory(update, context)

        # Уведомляем об успехе отдельным сообщением
        success_text = (
            f"♻️ Продажа всех кроме одного успешна: {qsold} шт. × {unit} = +{total} монет.\n"
            f"Баланс: {coins_after}. Осталось: {left}."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=success_text)
        except Exception:
            pass

# --- Доп. Бонусы: подменю и элементы ---
async def show_extra_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подменю дополнительных бонусов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    text = t(lang, 'extra_bonuses_title')
    # Остатки на складе
    tg_stock = db.get_tg_premium_stock()
    steam_stock = db.get_bonus_stock('steam_game')
    stars_stock = db.get_bonus_stock('stars_500')
    # Информативные строки о наличии
    text += "\n" + (f"TG Premium — {'in stock' if lang == 'en' else 'в наличии'}: {tg_stock}")
    text += "\n" + (f"{'Steam game' if lang == 'en' else 'Игра в Steam'} — {'in stock' if lang == 'en' else 'в наличии'}: {steam_stock}")
    text += "\n" + (f"{'Stars 500' if lang == 'en' else 'Звёзды 500'} — {'in stock' if lang == 'en' else 'в наличии'}: {stars_stock}")
    keyboard = []
    # Показываем TG Premium только если есть остаток на складе
    if tg_stock > 0:
        keyboard.append([InlineKeyboardButton(t(lang, 'tg_premium_3m'), callback_data='bonus_tg_premium')])
    # Показываем Steam игру, если есть остаток
    if steam_stock > 0:
        keyboard.append([InlineKeyboardButton(t(lang, 'steam_game_500'), callback_data='bonus_steam_game')])
    # VIP доступен всегда
    keyboard.append([InlineKeyboardButton(t(lang, 'vip'), callback_data='vip_menu')])
    # Показываем Звёзды, если есть остаток
    if stars_stock > 0:
        keyboard.append([InlineKeyboardButton(t(lang, 'stars'), callback_data='stars_menu')])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_city_casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран Казино в городе ХайТаун."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)

    text = (
        "<b>🎰 Казино ХайТаун</b>\n"
        f"Ваш баланс: <b>{coins}</b> септимов.\n\n"
        f"Ставка 1:1, шанс ~{int(CASINO_WIN_PROB * 100)}%. Играть на свой риск!"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 Ставка 10", callback_data='casino_bet_10'), InlineKeyboardButton("🎲 50", callback_data='casino_bet_50')],
        [InlineKeyboardButton("🎲 100", callback_data='casino_bet_100'), InlineKeyboardButton("🎲 500", callback_data='casino_bet_500')],
        [InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_casino_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "<b>📜 Правила Казино</b>\n\n"
        f"• Игра: подбрасывание монеты (шанс ~{int(CASINO_WIN_PROB * 100)}% в пользу заведения).\n"
        "• Выплата: 1 к 1 (вы получаете свою ставку и столько же сверху).\n"
        "• Ставка списывается сразу. При победе начисляется двойная сумма.\n"
        "• Играйте ответственно."
    )
    keyboard = [
        [InlineKeyboardButton("🔙 В Казино", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
    ]
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def handle_casino_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Обрабатывает ставку игрока."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if int(amount) <= 0:
        await query.answer("Неверная ставка", show_alert=True)
        return

    lock = _get_lock(f"user:{user.id}:casino")
    if lock.locked():
        await query.answer("Игра уже обрабатывается…", show_alert=True)
        return
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins_before = int(getattr(player, 'coins', 0) or 0)
        if coins_before < int(amount):
            await query.answer("Недостаточно септимов", show_alert=True)
            # просто перерисуем экран казино
            await show_city_casino(update, context)
            return

        # Списываем ставку
        after_debit = db.increment_coins(user.id, -int(amount))
        if after_debit is None:
            await query.answer("Ошибка при списании", show_alert=True)
            return

        # Разыгрываем исход — вероятность задаётся константой
        win = random.random() < CASINO_WIN_PROB
        coins_after = after_debit
        result_line = ""
        if win:
            coins_after = db.increment_coins(user.id, int(amount) * 2) or after_debit + int(amount) * 2
            result_line = f"🎉 Победа! Вы получаете +{amount} септимов."
        else:
            result_line = f"💥 Поражение! Списано {amount} септимов."

        # Перерисовываем экран с обновлённым балансом и результатом
        text = (
            "<b>🎰 Казино ХайТаун</b>\n"
            f"{result_line}\n"
            f"Баланс: <b>{int(coins_after)}</b> септимов.\n\n"
            f"Ставка 1:1, шанс ~{int(CASINO_WIN_PROB * 100)}%. Играть на свой риск!"
        )
        keyboard = [
            [InlineKeyboardButton("🎲 Ставка 10", callback_data='casino_bet_10'), InlineKeyboardButton("🎲 50", callback_data='casino_bet_50')],
            [InlineKeyboardButton("🎲 100", callback_data='casino_bet_100'), InlineKeyboardButton("🎲 500", callback_data='casino_bet_500')],
            [InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
        ]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def open_casino_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает Казино по текстовому триггеру (сообщение)."""
    msg = update.effective_message
    user = update.effective_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)

    text = (
        "<b>🎰 Казино ХайТаун</b>\n"
        f"Ваш баланс: <b>{coins}</b> септимов.\n\n"
        f"Ставка 1:1, шанс ~{int(CASINO_WIN_PROB * 100)}%. Играть на свой риск!"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 Ставка 10", callback_data='casino_bet_10'), InlineKeyboardButton("🎲 50", callback_data='casino_bet_50')],
        [InlineKeyboardButton("🎲 100", callback_data='casino_bet_100'), InlineKeyboardButton("🎲 500", callback_data='casino_bet_500')],
        [InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
    ]
    await msg.reply_html(text=text, reply_markup=InlineKeyboardMarkup(keyboard))


async def buy_steam_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка бонуса «Игра в Steam» за внутриигровую валюту с защитой от даблкликов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Защита от даблкликов
    lock = _get_lock(f"user:{user.id}:buy_steam_game")
    if lock.locked():
        await query.answer("Обработка…" if lang != 'en' else 'Processing…', show_alert=False)
        return

    async with lock:
        res = db.purchase_bonus_with_stock(user.id, kind='steam_game', cost_coins=TG_PREMIUM_COST, duration_seconds=0, extra='500')
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer('Недостаточно монет' if lang != 'en' else 'Not enough coins', show_alert=True)
            elif reason == 'out_of_stock':
                await query.answer('Нет в наличии' if lang != 'en' else 'Out of stock', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.' if lang != 'en' else 'Error. Please try later.', show_alert=True)
            return

        coins_left = res.get('coins_left')
        receipt_id = int(res.get('receipt_id') or 0)

        if lang == 'en':
            text = f"Steam game bonus purchased! Coins left: {coins_left}"
        else:
            text = f"Бонус «Игра в Steam» куплен! Остаток монет: {coins_left}"
        if receipt_id:
            if lang == 'en':
                text += f"\nReceipt ID: {receipt_id}"
            else:
                text += f"\nID чека: {receipt_id}"

        keyboard = []
        if receipt_id:
            keyboard.append([InlineKeyboardButton(t(lang, 'tg_view_receipt'), callback_data=f'view_receipt_{receipt_id}')])
        keyboard.append([InlineKeyboardButton(t(lang, 'tg_my_receipts'), callback_data='my_receipts')])
        keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def show_market_plantation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню Плантации."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    # TODO: В будущем здесь будет статистика плантаций игрока
    text = (
        "<b>🌱 Плантация</b>\n\n"
        "Добро пожаловать в систему плантаций!\n"
        "Здесь вы сможете выращивать энергетики и собирать урожай.\n\n"
        "<i>🚧 Система находится в разработке</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🌾 Мои грядки", callback_data='plantation_my_beds')],
        [InlineKeyboardButton("🛒 Купить семена", callback_data='plantation_shop')],
        [InlineKeyboardButton("🧪 Купить удобрения", callback_data='plantation_fertilizers_shop')],
        [InlineKeyboardButton("🧪 Мои удобрения", callback_data='plantation_fertilizers_inv')],
        [InlineKeyboardButton("➕ Купить грядку", callback_data='plantation_buy_bed')],
        [InlineKeyboardButton("🥕 Собрать урожай", callback_data='plantation_harvest')],
        [InlineKeyboardButton("🌍 Общие плантации", callback_data='plantation_community')],
        [InlineKeyboardButton("💧 Полить грядки", callback_data='plantation_water')],
        [InlineKeyboardButton("📊 Статистика", callback_data='plantation_stats')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


# === PLANTATION MENU FUNCTIONS ===

async def show_plantation_my_beds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои грядки."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    # Гарантируем грядки и читаем текущее состояние
    try:
        db.ensure_player_beds(user.id)
    except Exception:
        pass
    beds = db.get_player_beds(user.id) or []

    lines = ["<b>🌾 Мои грядки</b>"]
    actions = []
    for b in beds:
        idx = int(getattr(b, 'bed_index', 0) or 0)
        state = str(getattr(b, 'state', 'empty') or 'empty')
        st = getattr(b, 'seed_type', None)
        if state == 'empty':
            lines.append(f"🌱 Грядка {idx}: Пустая")
            actions.append([InlineKeyboardButton(f"➕ Посадить в {idx}", callback_data=f'plantation_choose_{idx}')])
        elif state == 'withered':
            lines.append(f"🌱 Грядка {idx}: Завяла")
            actions.append([InlineKeyboardButton(f"🔁 Пересадить {idx}", callback_data=f'plantation_choose_{idx}')])
        elif state == 'growing':
            name = html.escape(getattr(st, 'name', 'Семена')) if st else 'Семена'
            grow = int(getattr(st, 'grow_time_sec', 0) or 0) if st else 0
            planted = int(getattr(b, 'planted_at', 0) or 0)
            passed = max(0, int(time.time()) - planted)
            remain = max(0, grow - passed)
            last = int(getattr(b, 'last_watered_at', 0) or 0)
            interval = int(getattr(st, 'water_interval_sec', 0) or 0) if st else 0
            next_water = max(0, interval - (int(time.time()) - last)) if last and interval else 0
            
            # Проверяем статус удобрения
            fert_status = db.get_fertilizer_status(b)
            
            prog = f"⏳ До созревания: { _fmt_time(remain) }" if remain else "⏳ Проверка готовности…"
            water_info = "💧 Можно поливать" if not next_water else f"💧 Через { _fmt_time(next_water) }"
            
            # Добавляем информацию об удобрении
            if fert_status['active']:
                fert_info = f"🧪 {fert_status['fertilizer_name']}: { _fmt_time(fert_status['time_left']) }"
            else:
                fert_info = "🧪 Удобрения нет"
            
            lines.append(f"🌱 Грядка {idx}: Растёт {name}\n{prog}\n{water_info}\n{fert_info}")
            actions.append([
                InlineKeyboardButton(f"💧 Полить {idx}", callback_data=f'plantation_water_{idx}'),
                InlineKeyboardButton(f"🧪 Удобрить {idx}", callback_data=f'fert_pick_for_bed_{idx}')
            ])
        elif state == 'ready':
            name = html.escape(getattr(st, 'name', 'Семена')) if st else 'Семена'
            lines.append(f"🌱 Грядка {idx}: Готово! ({name})")
            actions.append([InlineKeyboardButton(f"🥕 Собрать {idx}", callback_data=f'plantation_harvest_bed_{idx}')])
        else:
            lines.append(f"🌱 Грядка {idx}: {state}")

    if not beds:
        lines.append("\nНет доступных грядок.")

    keyboard = []
    keyboard.extend(actions)
    keyboard.append([InlineKeyboardButton("🛒 Купить семена", callback_data='plantation_shop')])
    keyboard.append([InlineKeyboardButton("🧪 Купить удобрения", callback_data='plantation_fertilizers_shop'), InlineKeyboardButton("🧪 Мои удобрения", callback_data='plantation_fertilizers_inv')])
    keyboard.append([InlineKeyboardButton("➕ Купить грядку", callback_data='plantation_buy_bed')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_plantation_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Магазин семян."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    seed_types = []
    try:
        drinks = db.get_all_drinks() or []
        if drinks:
            pick = random.sample(drinks, min(3, len(drinks)))
            seed_types = db.ensure_seed_types_for_drinks([int(d.id) for d in pick]) or []
        else:
            seed_types = db.list_seed_types() or []
    except Exception:
        seed_types = db.list_seed_types() or []

    lines = [f"<b>🛒 Магазин семян</b>", f"\n💰 Баланс: {int(getattr(player, 'coins', 0) or 0)} септимов"]
    keyboard = []
    if seed_types:
        lines.append("\nДоступные семена:")
        for st in seed_types:
            name = html.escape(getattr(st, 'name', 'Семена'))
            price = int(getattr(st, 'price_coins', 0) or 0)
            ymin = int(getattr(st, 'yield_min', 0) or 0)
            ymax = int(getattr(st, 'yield_max', 0) or 0)
            grow_m = int((int(getattr(st, 'grow_time_sec', 0) or 0)) / 60)
            lines.append(f"🌱 {name} — {price}💰, урожай {ymin}-{ymax}, рост ~{grow_m} мин")
            keyboard.append([
                InlineKeyboardButton("Купить 1", callback_data=f'plantation_buy_{st.id}_1'),
                InlineKeyboardButton("Купить 5", callback_data=f'plantation_buy_{st.id}_5'),
            ])
    else:
        lines.append("\nПока нет доступных семян. Загляните позже.")

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_community_seed_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    try:
        is_admin = bool(db.is_admin(user.id) or (user.username in ADMIN_USERNAMES))
    except Exception:
        is_admin = bool(user.username in ADMIN_USERNAMES)
    if not is_admin:
        await query.answer("Нет прав", show_alert=True)
        return
    # Если уже есть проекты — не создаём повторно
    existing = db.list_community_plantations(limit=1) or []
    if existing:
        await query.answer("Проекты уже существуют", show_alert=True)
        await show_plantation_community(update, context)
        return
    # Создаём пару демонстрационных проектов
    try:
        db.create_community_plantation(
            title="Летний урожай Monster",
            description="Кооперативный проект по выращиванию. Присоединяйтесь и вносите свой вклад!",
            created_by=user.id,
        )
        db.create_community_plantation(
            title="Редкие семена Burn",
            description="Набор участников открыт. Цель — собрать редкие семена для общего дела.",
            created_by=user.id,
        )
        await query.answer("Демо-проекты добавлены", show_alert=False)
    except Exception:
        await query.answer("Ошибка при создании проектов", show_alert=True)
    await show_plantation_community(update, context)

async def show_plantation_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор урожая."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    beds = db.get_player_beds(user.id) or []
    ready = [b for b in beds if str(getattr(b, 'state', '')) == 'ready']
    lines = ["<b>🥕 Сбор урожая</b>"]
    keyboard = []
    if ready:
        lines.append("\nДоступно к сбору:")
        for b in ready:
            idx = int(getattr(b, 'bed_index', 0) or 0)
            st = getattr(b, 'seed_type', None)
            name = html.escape(getattr(st, 'name', 'Растение')) if st else 'Растение'
            lines.append(f"• Грядка {idx}: {name} — Готово")
            keyboard.append([InlineKeyboardButton(f"🥕 Собрать {idx}", callback_data=f'plantation_harvest_bed_{idx}')])
        # Кнопка массового сбора всех готовых грядок
        keyboard.append([InlineKeyboardButton("✅ Собрать всё", callback_data='plantation_harvest_all')])
    else:
        lines.append("\nПока нет готового урожая.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_plantation_community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общие плантации."""
    query = update.callback_query
    await query.answer()
    lines = ["<b>🌍 Общие плантации</b>"]
    keyboard = []
    user = query.from_user
    # Определим права админа (для возможности быстро создать демо-проекты)
    try:
        is_admin = bool(db.is_admin(user.id) or (user.username in ADMIN_USERNAMES))
    except Exception:
        is_admin = bool(user.username in ADMIN_USERNAMES)
    try:
        projects = db.list_community_plantations(limit=10) or []
    except Exception:
        projects = []
    if projects:
        lines.append("\nДоступные проекты:")
        for p in projects:
            title = html.escape(getattr(p, 'title', 'Проект'))
            lines.append(f"• {title}")
            keyboard.append([InlineKeyboardButton(f"▶ Открыть: {title}", callback_data=f"community_view_{p.id}")])
    else:
        lines.append("\nПока нет проектов. Загляните позже.")
        if is_admin:
            keyboard.append([InlineKeyboardButton("➕ Добавить демо-проекты", callback_data='community_seed_demo')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_community_project(update: Update, context: ContextTypes.DEFAULT_TYPE, project_id: int):
    query = update.callback_query
    await query.answer()
    cp = db.get_community_plantation_by_id(project_id)
    if not cp:
        await query.answer("Проект не найден", show_alert=True)
        await show_plantation_community(update, context)
        return
    user = query.from_user
    title = html.escape(getattr(cp, 'title', 'Проект'))
    desc = html.escape(getattr(cp, 'description', '') or '')
    # Статистика проекта
    try:
        stats = db.get_community_stats(project_id) or {}
    except Exception:
        stats = {}
    goal = int(stats.get('goal', 0) or 0)
    progress = int(stats.get('progress', 0) or 0)
    participants = int(stats.get('participants', 0) or 0)
    status = str(stats.get('status') or 'active')
    percent = int((progress * 100) // goal) if goal > 0 else 0
    # Участие пользователя
    try:
        part = db.get_community_participant(project_id, user.id)
    except Exception:
        part = None
    my_contrib = int(getattr(part, 'contributed_amount', 0) or 0) if part else 0

    lines = [f"<b>🌍 {title}</b>"]
    if desc:
        lines.append(f"\n{desc}")
    # Прогресс
    bar = _progress_bar(progress, goal, width=16)
    lines.append("")
    lines.append(f"Прогресс: {progress}/{goal} ({percent}%)")
    lines.append(bar)
    lines.append(f"👥 Участников: {participants} | Статус: {'✅ завершён' if status == 'completed' else '🟢 активен'}")
    if my_contrib > 0:
        lines.append(f"Ваш вклад: {my_contrib} септимов")

    keyboard = []
    if status == 'active':
        if not part:
            keyboard.append([InlineKeyboardButton("🤝 Присоединиться", callback_data=f'community_join_{project_id}')])
        # Быстрые суммы взносов
        keyboard.append([
            InlineKeyboardButton("💰 10", callback_data=f'community_contrib_{project_id}_10'),
            InlineKeyboardButton("💰 50", callback_data=f'community_contrib_{project_id}_50'),
            InlineKeyboardButton("💰 100", callback_data=f'community_contrib_{project_id}_100'),
            InlineKeyboardButton("💰 500", callback_data=f'community_contrib_{project_id}_500'),
        ])
    else:
        # Проект завершён — возможность забрать награду
        keyboard.append([InlineKeyboardButton("🎁 Забрать награду", callback_data=f'community_claim_{project_id}')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='plantation_community')])

    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_plantation_water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полив грядок."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    beds = db.get_player_beds(user.id) or []
    lines = ["<b>💧 Полив грядок</b>"]
    keyboard = []
    any_growing = False
    now_ts = int(time.time())
    for b in beds:
        if str(getattr(b, 'state', '')) != 'growing':
            continue
        st = getattr(b, 'seed_type', None)
        idx = int(getattr(b, 'bed_index', 0) or 0)
        any_growing = True
        last = int(getattr(b, 'last_watered_at', 0) or 0)
        interval = int(getattr(st, 'water_interval_sec', 0) or 0) if st else 0
        next_in = max(0, interval - (now_ts - last)) if last and interval else 0
        name = html.escape(getattr(st, 'name', 'Растение')) if st else 'Растение'
        if next_in:
            lines.append(f"• Грядка {idx}: {name} — полив через { _fmt_time(next_in) }")
            keyboard.append([InlineKeyboardButton(f"⏳ Рано ({idx})", callback_data='noop')])
        else:
            lines.append(f"• Грядка {idx}: {name} — можно поливать")
            keyboard.append([InlineKeyboardButton(f"💧 Полить {idx}", callback_data=f'plantation_water_{idx}')])
    if not any_growing:
        lines.append("\nНет растущих грядок для полива.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_plantation_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика плантации."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    beds = db.get_player_beds(user.id) or []
    inv = db.get_seed_inventory(user.id) or []

    counts = {'empty': 0, 'growing': 0, 'ready': 0, 'withered': 0}
    for b in beds:
        s = str(getattr(b, 'state', 'empty') or 'empty')
        counts[s] = counts.get(s, 0) + 1

    lines = ["<b>📊 Статистика плантации</b>"]
    lines.append(f"\n💰 Баланс: {int(getattr(player, 'coins', 0) or 0)} септимов")
    lines.append(f"🌾 Грядок: {len(beds)} (пустых {counts.get('empty',0)}, растёт {counts.get('growing',0)}, готово {counts.get('ready',0)}, завяло {counts.get('withered',0)})")
    if inv:
        lines.append("\n🌱 Семена в инвентаре:")
        for it in inv:
            st = getattr(it, 'seed_type', None)
            name = html.escape(getattr(st, 'name', 'Семена')) if st else 'Семена'
            qty = int(getattr(it, 'quantity', 0) or 0)
            if qty > 0:
                lines.append(f"• {name}: {qty} шт.")
    else:
        lines.append("\n🌱 Семян нет.")

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')]]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# === FERTILIZERS: SHOP, INVENTORY, APPLY ===

async def show_plantation_fertilizers_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Магазин удобрений."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    try:
        fertilizers = db.list_fertilizers() or []
    except Exception:
        fertilizers = []

    lines = [f"<b>🧪 Магазин удобрений</b>", f"\n💰 Баланс: {int(getattr(player, 'coins', 0) or 0)} септимов"]
    keyboard = []
    if fertilizers:
        lines.append("\nДоступные удобрения:")
        for fz in fertilizers:
            name = html.escape(getattr(fz, 'name', 'Удобрение'))
            desc = html.escape(getattr(fz, 'description', '') or '')
            price = int(getattr(fz, 'price_coins', 0) or 0)
            eff = html.escape(getattr(fz, 'effect', '') or '')
            dur_m = int((int(getattr(fz, 'duration_sec', 0) or 0)) / 60)
            lines.append(f"• {name} — {price}💰 | эффект: {eff} | длительность: ~{dur_m} мин\n  {desc}")
            keyboard.append([
                InlineKeyboardButton("Купить 1", callback_data=f'fert_buy_{fz.id}_1'),
                InlineKeyboardButton("Купить 5", callback_data=f'fert_buy_{fz.id}_5'),
            ])
    else:
        lines.append("\nПока нет удобрений. Загляните позже.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_fertilizer_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, fertilizer_id: int, quantity: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:fert_buy")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.purchase_fertilizer(user.id, int(fertilizer_id), int(quantity))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer('Недостаточно монет', show_alert=True)
            elif reason == 'no_such_fertilizer':
                await query.answer('Удобрение не найдено', show_alert=True)
            elif reason == 'invalid_quantity':
                await query.answer('Неверное количество', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer(f"Куплено! Баланс: {res.get('coins_left')}", show_alert=False)
        await show_plantation_fertilizers_shop(update, context)

async def show_plantation_fertilizers_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвентарь удобрений."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    try:
        inv = db.get_fertilizer_inventory(user.id) or []
    except Exception:
        inv = []
    lines = ["<b>🧪 Мои удобрения</b>"]
    keyboard = []
    any_items = False
    for it in inv:
        qty = int(getattr(it, 'quantity', 0) or 0)
        fz = getattr(it, 'fertilizer', None)
        if not fz or qty <= 0:
            continue
        any_items = True
        name = html.escape(getattr(fz, 'name', 'Удобрение'))
        lines.append(f"• {name}: {qty} шт.")
        keyboard.append([
            InlineKeyboardButton(f"Применить", callback_data=f'fert_apply_pick_{fz.id}')
        ])
    if not any_items:
        lines.append("\nУ вас нет удобрений.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_fertilizer_apply_pick_bed(update: Update, context: ContextTypes.DEFAULT_TYPE, fertilizer_id: int):
    """Выбор грядки для применения указанного удобрения."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    beds = db.get_player_beds(user.id) or []
    lines = ["<b>🧪 Выберите грядку для удобрения</b>"]
    keyboard = []
    eligible = False
    for b in beds:
        idx = int(getattr(b, 'bed_index', 0) or 0)
        state = str(getattr(b, 'state', ''))
        if state != 'growing':
            continue
        eligible = True
        st = getattr(b, 'seed_type', None)
        name = html.escape(getattr(st, 'name', 'Растение')) if st else 'Растение'
        lines.append(f"• Грядка {idx}: {name} — растёт")
        keyboard.append([InlineKeyboardButton(f"Удобрить {idx}", callback_data=f'fert_apply_do_{idx}_{fertilizer_id}')])
    if not eligible:
        lines.append("\nНет растущих грядок для удобрения.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='plantation_fertilizers_inv')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_fertilizer_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int, fertilizer_id: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:fert_apply")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.apply_fertilizer(user.id, int(bed_index), int(fertilizer_id))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_growing':
                await query.answer('Грядка не в состоянии роста', show_alert=True)
            elif reason == 'fertilizer_active':
                await query.answer('На грядке уже активен эффект удобрения', show_alert=True)
            elif reason == 'no_fertilizer_in_inventory':
                await query.answer('Нет такого удобрения в инвентаре', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer('Удобрение применено!', show_alert=False)
        await show_plantation_my_beds(update, context)

async def show_fertilizer_pick_for_bed(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    """Выбор удобрения из инвентаря для конкретной грядки."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    inv = db.get_fertilizer_inventory(user.id) or []
    lines = [f"<b>🧪 Выберите удобрение для грядки {bed_index}</b>"]
    keyboard = []
    any_items = False
    for it in inv:
        qty = int(getattr(it, 'quantity', 0) or 0)
        fz = getattr(it, 'fertilizer', None)
        if not fz or qty <= 0:
            continue
        any_items = True
        name = html.escape(getattr(fz, 'name', 'Удобрение'))
        keyboard.append([InlineKeyboardButton(f"{name} ({qty})", callback_data=f'fert_apply_do_{bed_index}_{fz.id}')])
    if not any_items:
        lines.append("\nУ вас нет удобрений.")
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='plantation_my_beds')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_plantation_buy_bed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:buy_bed")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.purchase_next_bed(user.id)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'limit_reached':
                await query.answer('Лимит грядок достигнут', show_alert=True)
            elif reason == 'not_enough_coins':
                await query.answer('Недостаточно монет', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            idx = res.get('bed_index')
            await query.answer(f"Грядка куплена! #{idx}. Баланс: {res.get('coins_left')}", show_alert=False)
        await show_plantation_my_beds(update, context)

# Placeholder handlers for buttons
async def show_plantation_join_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)

async def show_plantation_my_contribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)

async def show_plantation_community_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)

async def show_plantation_water_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Нечего поливать", show_alert=True)

async def show_plantation_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)


def _fmt_time(seconds: int) -> str:
    seconds = int(max(0, int(seconds or 0)))
    if seconds < 60:
        return f"{seconds}с"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}м {s}с" if s else f"{m}м"
    h, m = divmod(m, 60)
    return f"{h}ч {m}м"


def _progress_bar(value: int, total: int, width: int = 10) -> str:
    """Простой текстовый прогресс-бар."""
    v = int(max(0, int(value or 0)))
    t = int(max(0, int(total or 0)))
    if t <= 0:
        t = 1
    filled = int((v * width) // t)
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"

async def handle_community_join(update: Update, context: ContextTypes.DEFAULT_TYPE, project_id: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:community_join")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.join_community_project(project_id, user.id)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'no_project':
                await query.answer('Проект не найден', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer('Вы присоединились к проекту!', show_alert=False)
        await show_community_project(update, context, project_id)

async def handle_community_contrib(update: Update, context: ContextTypes.DEFAULT_TYPE, project_id: int, amount: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:community_contrib")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.contribute_to_community_project(project_id, user.id, int(amount))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'invalid_amount':
                await query.answer('Неверная сумма взноса', show_alert=True)
            elif reason == 'not_enough_coins':
                await query.answer('Недостаточно монет', show_alert=True)
            elif reason == 'completed':
                await query.answer('Проект уже завершён', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer(f"Взнос принят: {int(amount)}. Баланс: {res.get('coins_left')}", show_alert=False)
        await show_community_project(update, context, project_id)

async def handle_community_claim(update: Update, context: ContextTypes.DEFAULT_TYPE, project_id: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:community_claim")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.claim_community_reward(project_id, user.id)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_completed':
                await query.answer('Проект ещё не завершён', show_alert=True)
            elif reason == 'not_participant':
                await query.answer('Вы не участник проекта', show_alert=True)
            elif reason == 'already_claimed':
                await query.answer('Награда уже получена', show_alert=True)
            elif reason == 'no_progress':
                await query.answer('Нечего распределять', show_alert=True)
            elif reason == 'no_contribution':
                await query.answer('У вас нет вклада в проект', show_alert=True)
            elif reason == 'no_state':
                await query.answer('Состояние проекта не найдено', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer(f"Начислено: {res.get('claimed_coins', 0)}. Баланс: {res.get('coins_after')}", show_alert=True)
        await show_community_project(update, context, project_id)

async def show_plantation_choose_seed(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    inv = db.get_seed_inventory(user.id) or []
    lines = [f"<b>🌱 Выбор семян для грядки {bed_index}</b>"]
    keyboard = []
    available = [(it.seed_type, int(getattr(it, 'quantity', 0) or 0)) for it in inv if int(getattr(it, 'quantity', 0) or 0) > 0 and it.seed_type]
    if available:
        lines.append("\nДоступно к посадке:")
        for st, qty in available:
            name = html.escape(getattr(st, 'name', 'Семена'))
            lines.append(f"• {name}: {qty} шт.")
            keyboard.append([InlineKeyboardButton(f"Посадить {name}", callback_data=f'plantation_plant_{bed_index}_{st.id}')])
    else:
        lines.append("\nУ вас нет семян. Купите их в магазине.")
        keyboard.append([InlineKeyboardButton("🛒 Открыть магазин", callback_data='plantation_shop')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='plantation_my_beds')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def handle_plantation_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, seed_type_id: int, quantity: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:plantation_buy")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.purchase_seeds(user.id, seed_type_id, quantity)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer('Недостаточно монет', show_alert=True)
            elif reason == 'no_such_seed':
                await query.answer('Семена не найдены', show_alert=True)
            elif reason == 'invalid_quantity':
                await query.answer('Неверное количество', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer(f"Куплено: {quantity}. Остаток: {res.get('coins_left')}", show_alert=False)
        await show_plantation_shop(update, context)


async def handle_plantation_plant(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int, seed_type_id: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:plantation_plant")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.plant_seed(user.id, bed_index, seed_type_id)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'no_seeds':
                await query.answer('Нет семян этого типа', show_alert=True)
            elif reason == 'bed_not_empty':
                await query.answer('Грядка занята', show_alert=True)
            elif reason == 'no_such_bed':
                await query.answer('Грядка не найдена', show_alert=True)
            elif reason == 'no_such_seed':
                await query.answer('Семена не найдены', show_alert=True)
            else:
                await query.answer('Ошибка при посадке', show_alert=True)
        else:
            await query.answer('Посажено!', show_alert=False)
        await show_plantation_my_beds(update, context)


async def handle_plantation_water(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:plantation_water")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.water_bed(user.id, bed_index)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'too_early_to_water':
                nxt = int(res.get('next_water_in') or 0)
                await query.answer(f"Рано. Через { _fmt_time(nxt) }", show_alert=True)
            elif reason == 'not_growing':
                await query.answer('Сейчас нечего поливать', show_alert=True)
            elif reason == 'no_such_bed':
                await query.answer('Грядка не найдена', show_alert=True)
            else:
                await query.answer('Ошибка при поливе', show_alert=True)
        else:
            await query.answer('Полито!', show_alert=False)
        await show_plantation_my_beds(update, context)


async def handle_plantation_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:plantation_harvest")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        res = db.harvest_bed(user.id, bed_index)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_ready':
                await query.answer('Ещё не созрело', show_alert=True)
            elif reason == 'no_seed':
                await query.answer('Пустая грядка', show_alert=True)
            elif reason == 'no_such_bed':
                await query.answer('Грядка не найдена', show_alert=True)
            else:
                await query.answer('Ошибка при сборе', show_alert=True)
        else:
            amount = int(res.get('yield') or 0)
            items_added = int(res.get('items_added') or 0)
            drink_id = int(res.get('drink_id') or 0)
            rarity_counts = res.get('rarity_counts') or {}

            # Короткое подтверждение
            await query.answer(f"Собрано: {items_added}", show_alert=False)

            # Детальный отчёт с фото и эффектами
            try:
                drink = db.get_drink_by_id(drink_id)
            except Exception:
                drink = None
            name = html.escape(getattr(drink, 'name', 'Энергетик'))

            lines = [
                "<b>🥕 Урожай собран</b>",
                f"{name}: <b>{items_added}</b>" + (f" из {amount}" if items_added != amount else ""),
            ]
            for r in RARITY_ORDER:
                cnt = int((rarity_counts.get(r) or 0))
                if cnt > 0:
                    emoji = COLOR_EMOJIS.get(r, '')
                    lines.append(f"{emoji} {r}: <b>{cnt}</b>")

            # Эффекты (полив, удобрение, негативные статусы, множитель)
            eff = res.get('effects') or {}
            wc = int(eff.get('water_count') or 0)
            fert_active = bool(eff.get('fertilizer_active'))
            fert_name = eff.get('fertilizer_name') or ''
            status_raw = (eff.get('status_effect') or '').lower()
            yield_mult = float(eff.get('yield_multiplier') or 1.0)
            status_map = {'weeds': 'сорняки', 'pests': 'вредители', 'drought': 'засуха'}
            status_h = status_map.get(status_raw, '—' if not status_raw else status_raw)
            lines.append("")
            lines.append("<i>Эффекты</i>:")
            lines.append(f"• Поливов: {wc}")
            if fert_active:
                if fert_name:
                    lines.append(f"• Удобрение: активно ({html.escape(str(fert_name))})")
                else:
                    lines.append("• Удобрение: активно")
            else:
                lines.append("• Удобрение: нет")
            lines.append(f"• Негативный статус: {status_h}")
            lines.append(f"• Множитель урожая: x{yield_mult:.2f}")

            text = "\n".join(lines)
            image_full_path = os.path.join(ENERGY_IMAGES_DIR, getattr(drink, 'image_path', None)) if drink and getattr(drink, 'image_path', None) else None
            try:
                if image_full_path and os.path.exists(image_full_path):
                    with open(image_full_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=user.id, photo=photo, caption=text, parse_mode='HTML')
                else:
                    await context.bot.send_message(chat_id=user.id, text=text, parse_mode='HTML')
            except Exception:
                # Если отправка фото не удалась — пробуем текст
                try:
                    await context.bot.send_message(chat_id=user.id, text=text, parse_mode='HTML')
                except Exception:
                    pass
        await show_plantation_my_beds(update, context)

async def handle_plantation_harvest_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:plantation_harvest")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return
    async with lock:
        beds = db.get_player_beds(user.id) or []
        ready = [b for b in beds if str(getattr(b, 'state', '')) == 'ready']
        if not ready:
            await query.answer('Пока нет готового урожая', show_alert=True)
            return

        total_items = 0
        total_amount = 0
        agg_rarity: dict[str, int] = {}
        per_drink: dict[int, dict] = {}

        for b in ready:
            idx = int(getattr(b, 'bed_index', 0) or 0)
            res = db.harvest_bed(user.id, idx)
            if not res.get('ok'):
                continue

            amount = int(res.get('yield') or 0)
            items_added = int(res.get('items_added') or 0)
            drink_id = int(res.get('drink_id') or 0)
            rarity_counts = res.get('rarity_counts') or {}
            eff = res.get('effects') or {}

            total_items += items_added
            total_amount += amount
            for k, v in (rarity_counts or {}).items():
                try:
                    agg_rarity[k] = int(agg_rarity.get(k, 0) or 0) + int(v or 0)
                except Exception:
                    pass

            if drink_id not in per_drink:
                try:
                    d = db.get_drink_by_id(drink_id)
                except Exception:
                    d = None
                per_drink[drink_id] = {
                    'name': html.escape(getattr(d, 'name', 'Энергетик')),
                    'items_added': 0,
                    'amount': 0,
                    'rarity_counts': {}
                }
            per_drink[drink_id]['items_added'] += items_added
            per_drink[drink_id]['amount'] += amount
            for k, v in (rarity_counts or {}).items():
                try:
                    per_drink[drink_id]['rarity_counts'][k] = int(per_drink[drink_id]['rarity_counts'].get(k, 0) or 0) + int(v or 0)
                except Exception:
                    pass

            # Отправляем детальное сообщение по каждой грядке с фото
            try:
                drink = db.get_drink_by_id(drink_id)
            except Exception:
                drink = None
            name = html.escape(getattr(drink, 'name', 'Энергетик'))

            lines = [
                f"<b>🥕 Сбор: грядка {idx}</b>",
                f"{name}: <b>{items_added}</b>" + (f" из {amount}" if items_added != amount else ""),
            ]
            for r in RARITY_ORDER:
                cnt = int((rarity_counts.get(r) or 0))
                if cnt > 0:
                    emoji = COLOR_EMOJIS.get(r, '')
                    lines.append(f"{emoji} {r}: <b>{cnt}</b>")

            wc = int(eff.get('water_count') or 0)
            fert_active = bool(eff.get('fertilizer_active'))
            fert_name = eff.get('fertilizer_name') or ''
            status_raw = (eff.get('status_effect') or '').lower()
            yield_mult = float(eff.get('yield_multiplier') or 1.0)
            status_map = {'weeds': 'сорняки', 'pests': 'вредители', 'drought': 'засуха'}
            status_h = status_map.get(status_raw, '—' if not status_raw else status_raw)
            lines.append("")
            lines.append("<i>Эффекты</i>:")
            lines.append(f"• Поливов: {wc}")
            if fert_active:
                if fert_name:
                    lines.append(f"• Удобрение: активно ({html.escape(str(fert_name))})")
                else:
                    lines.append("• Удобрение: активно")
            else:
                lines.append("• Удобрение: нет")
            lines.append(f"• Негативный статус: {status_h}")
            lines.append(f"• Множитель урожая: x{yield_mult:.2f}")
            text = "\n".join(lines)

            image_full_path = os.path.join(ENERGY_IMAGES_DIR, getattr(drink, 'image_path', None)) if drink and getattr(drink, 'image_path', None) else None
            try:
                if image_full_path and os.path.exists(image_full_path):
                    with open(image_full_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=user.id, photo=photo, caption=text, parse_mode='HTML')
                else:
                    await context.bot.send_message(chat_id=user.id, text=text, parse_mode='HTML')
            except Exception:
                try:
                    await context.bot.send_message(chat_id=user.id, text=text, parse_mode='HTML')
                except Exception:
                    pass

        # Короткое сводное уведомление
        await query.answer(f"Собрано: {total_items}", show_alert=False)

        # Сводный отчёт
        lines = [
            "<b>🥕 Сбор завершён</b>",
            f"Итого собрано: <b>{total_items}</b>" + (f" из {total_amount}" if total_items != total_amount else ""),
        ]
        for r in RARITY_ORDER:
            cnt = int((agg_rarity.get(r) or 0))
            if cnt > 0:
                emoji = COLOR_EMOJIS.get(r, '')
                lines.append(f"{emoji} {r}: <b>{cnt}</b>")
        if per_drink:
            lines.append("")
            lines.append("<b>По напиткам:</b>")
            for _did, info in per_drink.items():
                d_name = info.get('name', 'Напиток')
                ia = int(info.get('items_added') or 0)
                am = int(info.get('amount') or 0)
                lines.append(f"• {d_name}: <b>{ia}</b>" + (f" из {am}" if ia != am else ""))
        text = "\n".join(lines)
        try:
            await context.bot.send_message(chat_id=user.id, text=text, parse_mode='HTML')
        except Exception:
            pass

        await show_plantation_my_beds(update, context)

async def show_market_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю Рынок: Магазин, Приёмник."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language  # на будущее, сейчас текст на русском

    text = "<b>🛒 Рынок</b>\nВыберите раздел:"
    keyboard = [
        [InlineKeyboardButton("🏬 Магазин", callback_data='market_shop')],
        [InlineKeyboardButton("♻️ Приёмник", callback_data='market_receiver')],
        [InlineKeyboardButton("🌱 Плантация", callback_data='market_plantation')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
 
async def show_cities_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню Города: список доступных городов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = "<b>🏙️ Города</b>\nВыберите город:"
    keyboard = [
        [InlineKeyboardButton("🏰 Город ХайТаун", callback_data='city_hightown')],
        [InlineKeyboardButton("🧵 Город Шёлка", callback_data='city_silk')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_city_hightown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Город ХайТаун: разделы города (бывший Рынок)."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = "<b>🏰 Город ХайТаун</b>\nВыберите раздел:"
    keyboard = [
        [InlineKeyboardButton("🏬 Магазин", callback_data='market_shop')],
        [InlineKeyboardButton("♻️ Приёмник", callback_data='market_receiver')],
        [InlineKeyboardButton("🌱 Плантация", callback_data='market_plantation')],
        [InlineKeyboardButton("🎰 Казино", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_market_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран Магазина: 50 офферов из БД, автообновление каждые 4 часа, покупка с ценой."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    # Определяем страницу: из callback или из user_data (после покупки)
    data = query.data or 'market_shop'
    forced_page = context.user_data.pop('shop_page_override', None)
    page = 1
    if forced_page:
        try:
            page = max(1, int(forced_page))
        except Exception:
            page = 1
    elif data.startswith('shop_p_'):
        try:
            page = max(1, int(data.split('_')[-1]))
        except Exception:
            page = 1

    # Получаем персистентные офферы
    offers, last_ts = db.get_or_refresh_shop_offers()
    if not offers:
        text = "<b>🏬 Магазин</b>\nПока нет доступных товаров."
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        return

    total = len(offers)
    page_size = 10
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = min(total, start + page_size)

    now_ts = int(time.time())
    next_in = max(0, (int(last_ts or 0) + 4 * 60 * 60) - now_ts)

    # Текст
    lines = [
        "<b>🏬 Магазин</b>",
        f"Доступно предложений: <b>{total}</b>",
        f"Страница <b>{page}</b> из <b>{total_pages}</b>",
        (f"Обновление через: <i>{_fmt_time(next_in)}</i>" if next_in > 0 else "Обновляется..."),
        "",
    ]
    for off in offers[start:end]:
        rarity = str(off.rarity)
        price = int(SHOP_PRICES.get(rarity, 0))
        emoji = COLOR_EMOJIS.get(rarity, '⚪')
        name = html.escape(getattr(off.drink, 'name', 'Энергетик'))
        lines.append(f"{off.offer_index}. {emoji} {rarity} — <b>{name}</b> — <b>{price}🪙</b>")
    text = "\n".join(lines)

    # Кнопки
    kb = []
    # Пагинация
    if total_pages > 1:
        prev_cb = f"shop_p_{page-1}" if page > 1 else 'noop'
        next_cb = f"shop_p_{page+1}" if page < total_pages else 'noop'
        kb.append([InlineKeyboardButton("⬅️", callback_data=prev_cb), InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'), InlineKeyboardButton("➡️", callback_data=next_cb)])
    # Кнопки покупки для текущей страницы
    for off in offers[start:end]:
        rarity = str(off.rarity)
        price = int(SHOP_PRICES.get(rarity, 0))
        kb.append([InlineKeyboardButton(f"Купить {off.offer_index} ({price}🪙)", callback_data=f"shop_buy_{off.offer_index}_p{page}")])
    # Навигация
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')])
    kb.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(kb)

    # Отрисовка
    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_shop_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, offer_index: int, page: int):
    query = update.callback_query
    user = query.from_user
    lock = _get_lock(f"user:{user.id}:shop_buy")
    async with lock:
        res = db.purchase_shop_offer(user.id, int(offer_index))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer("Недостаточно монет", show_alert=True)
            elif reason == 'no_offer':
                await query.answer("Оффер недоступен", show_alert=True)
            else:
                await query.answer("Ошибка покупки", show_alert=True)
        else:
            dn = res.get('drink_name')
            rr = res.get('rarity')
            coins = res.get('coins_left')
            await query.answer(f"Куплено: {dn} ({rr}). Баланс: {coins}", show_alert=True)
 
async def show_market_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран Приёмника: прайс-лист продажи и переход в инвентарь."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    # Собираем прайс-лист (выплата за 1 шт. с учётом комиссии)
    lines = [
        "<b>♻️ Приёмник</b>",
        "Сдавайте лишние энергетики и получайте монеты.",
        f"Комиссия: {int(RECEIVER_COMMISSION*100)}% (выплата = {100-int(RECEIVER_COMMISSION*100)}% от цены)",
        "",
        "<b>Прайс-лист (за 1 шт.)</b>",
    ]
    for r in RARITY_ORDER:
        if r in RECEIVER_PRICES:
            base = int(RECEIVER_PRICES[r])
            payout = int(base * (1.0 - float(RECEIVER_COMMISSION)))
            emoji = COLOR_EMOJIS.get(r, '⚫')
            lines.append(f"{emoji} {r}: {payout} монет")
    text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("📦 Открыть инвентарь", callback_data='inventory')],
        [InlineKeyboardButton("📊 По количеству", callback_data='receiver_by_quantity')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю Звезды с выбором пакета."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    stock = db.get_bonus_stock('stars_500')
    text = t(lang, 'stars_title')
    text += f"\n{'In stock' if lang == 'en' else 'В наличии'}: {stock}"
    keyboard = []
    if stock > 0:
        keyboard.append([InlineKeyboardButton(t(lang, 'stars_500'), callback_data='stars_500')])
    keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def buy_vip(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_key: str):
    """Покупка VIP на указанный срок (plan_key: '1d'|'7d'|'30d')."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    if plan_key not in VIP_COSTS or plan_key not in VIP_DURATIONS_SEC:
        await query.answer("Ошибка плана", show_alert=True)
        return

    # Защита от даблкликов
    lock = _get_lock(f"user:{user.id}:buy_vip")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return

    async with lock:
        cost = VIP_COSTS[plan_key]
        duration = VIP_DURATIONS_SEC[plan_key]
        res = db.purchase_vip(user.id, cost, duration)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer(t(lang, 'vip_not_enough'), show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
            return

        vip_until_ts = res.get('vip_until') or db.get_vip_until(user.id)
        coins_left = res.get('coins_left')
        until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(int(vip_until_ts))) if vip_until_ts else '—'

        text = t(lang, 'vip_bought').format(emoji=VIP_EMOJI, dt=until_str, coins=coins_left)
        keyboard = [
            [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='vip_menu')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def view_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подробности одного чека по ID с проверкой прав."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    data = query.data or ''
    try:
        rid_str = data.split('view_receipt_', 1)[1]
        receipt_id = int(rid_str)
    except Exception:
        await query.answer("Неверные данные", show_alert=True)
        return

    rec = db.get_receipt_by_id(receipt_id)
    if not rec:
        await query.answer("Чек не найден", show_alert=True)
        return

    # Проверка доступа: владелец или ур.3/Создатель
    is_creator = (user.username in ADMIN_USERNAMES)
    if rec.user_id != user.id:
        lvl = db.get_admin_level(user.id)
        if not is_creator and lvl != 3:
            await query.answer("Нет прав", show_alert=True)
            return

    def fmt_ts(ts: int | None) -> str:
        if not ts:
            return '—'
        try:
            return time.strftime('%d.%m.%Y %H:%M', time.localtime(int(ts)))
        except Exception:
            return str(ts)

    kind_title = 'TG Premium' if getattr(rec, 'kind', '') == 'tg_premium' else str(getattr(rec, 'kind', '—'))
    duration_days = int((getattr(rec, 'duration_seconds', 0) or 0) // (24 * 60 * 60))
    status = getattr(rec, 'status', '—')
    verified_by = getattr(rec, 'verified_by', None)
    verified_at = getattr(rec, 'verified_at', None)

    text_lines = [
        f"<b>Чек #{getattr(rec, 'id', '?')}</b>",
        f"Пользователь: {getattr(rec, 'user_id', '?')}",
        f"Вид: {html.escape(kind_title)}",
        f"Сумма: {getattr(rec, 'amount_coins', 0)}",
        f"Срок: {duration_days} дн.",
        f"Куплено: {fmt_ts(getattr(rec, 'purchased_at', None))}",
        f"Действует до: {fmt_ts(getattr(rec, 'valid_until', None))}",
        f"Статус: {html.escape(str(status))}",
    ]
    if verified_by:
        text_lines.append(f"Проверено админом: {verified_by} в {fmt_ts(verified_at)}")
    text = "\n".join(text_lines)

    keyboard = [
        [InlineKeyboardButton(t(lang, 'tg_my_receipts'), callback_data='my_receipts')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def my_receipts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список последних чеков пользователя с кнопками для просмотра."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    recs = db.get_receipts_by_user(user.id, limit=10)
    if not recs:
        text = "У вас пока нет чеков." if lang != 'en' else "You have no receipts yet."
        keyboard = [
            [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        return

    header = "Ваши последние чеки:" if lang != 'en' else "Your recent receipts:"
    text = header

    keyboard_rows = []
    for r in recs:
        rid = getattr(r, 'id', None)
        status = getattr(r, 'status', '—')
        if not rid:
            continue
        label = f"Чек #{rid} — {status}" if lang != 'en' else f"Receipt #{rid} — {status}"
        keyboard_rows.append([InlineKeyboardButton(label, callback_data=f'view_receipt_{rid}')])

    keyboard_rows.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
    keyboard_rows.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def myreceipts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /myreceipts — показать список последних чеков пользователя."""
    msg = update.message
    user = update.effective_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    recs = db.get_receipts_by_user(user.id, limit=10)
    if not recs:
        text = "У вас пока нет чеков." if lang != 'en' else "You have no receipts yet."
        keyboard = [
            [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await msg.reply_html(text, reply_markup=reply_markup)
        except Exception:
            await msg.reply_text(text, reply_markup=reply_markup)
        return

    header = "Ваши последние чеки:" if lang != 'en' else "Your recent receipts:"
    text = header

    keyboard_rows = []
    for r in recs:
        rid = getattr(r, 'id', None)
        status = getattr(r, 'status', '—')
        if not rid:
            continue
        label = f"Чек #{rid} — {status}" if lang != 'en' else f"Receipt #{rid} — {status}"
        keyboard_rows.append([InlineKeyboardButton(label, callback_data=f'view_receipt_{rid}')])

    keyboard_rows.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
    keyboard_rows.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    try:
        await msg.reply_html(text, reply_markup=reply_markup)
    except Exception:
        await msg.reply_text(text, reply_markup=reply_markup)

async def show_stars_500(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали пакета 500 звёзд (заглушка)."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Текст с ценой и балансом
    stock = db.get_bonus_stock('stars_500')
    text = t(lang, 'stars_details_500')
    text += f"\n{'Price' if lang == 'en' else 'Цена'}: {TG_PREMIUM_COST}"
    text += f"\n{'In stock' if lang == 'en' else 'В наличии'}: {stock}"
    current_coins = int(player.coins or 0)
    if current_coins < TG_PREMIUM_COST:
        if lang == 'en':
            text += f"\nNot enough coins: {current_coins}/{TG_PREMIUM_COST}"
        else:
            text += f"\nНедостаточно монет: {current_coins}/{TG_PREMIUM_COST}"

    # Кнопки с покупкой
    keyboard = []
    if stock > 0:
        buy_label = ("Buy" if lang == 'en' else 'Купить') + f" — {TG_PREMIUM_COST}"
        keyboard.append([InlineKeyboardButton(buy_label, callback_data='buy_stars_500')])
    keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='stars_menu')])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю V.I.P с выбором длительности."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    text = t(lang, 'vip_title')
    # Добавим блок о текущем состоянии автопоиска VIP
    try:
        auto_state = t(lang, 'on') if getattr(player, 'auto_search_enabled', False) else t(lang, 'off')
        auto_count = int(getattr(player, 'auto_search_count', 0) or 0)
        auto_limit = db.get_auto_search_daily_limit(user.id)  # Используем новую функцию с учётом бустов
        text += t(lang, 'vip_auto_header')
        text += "\n" + t(lang, 'vip_auto_state').format(state=auto_state)
        text += "\n" + t(lang, 'vip_auto_today').format(count=auto_count, limit=auto_limit)
        
        # Добавляем информацию о бусте, если он активен
        boost_info = db.get_boost_info(user.id)
        if boost_info['is_active']:
            rocket_emoji = "🚀"
            clock_emoji = "⏰"
            
            # Получаем детальную информацию о бусте
            boost_text_parts = [
                f"\n{rocket_emoji} <b>Автопоиск буст:</b>",
                f"📊 Дополнительно: +{boost_info['boost_count']} поисков",
                f"{clock_emoji} Осталось: {boost_info['time_remaining_formatted']}",
                f"📅 Истекает: {boost_info['boost_until_formatted']}"
            ]
            
            boost_display = "\n".join(boost_text_parts)
            text += boost_display
        elif boost_info['has_boost']:
            # Буст есть, но не активен (истёк)
            text += f"\n⏱ <i>Буст автопоиска истёк</i>"
            
        # Добавляем ссылку на историю бустов (если есть история)
        try:
            history = db.get_user_boost_history(user.id, limit=1)
            if history:
                text += f"\n\n📋 Для просмотра истории бустов напишите /myboosts"
        except Exception:
            pass
    except Exception:
        pass
    
    # Ensure text is properly encoded to avoid Unicode issues
    try:
        text = text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        pass
    keyboard = [
        [InlineKeyboardButton(t(lang, 'vip_1d'), callback_data='vip_1d')],
        [InlineKeyboardButton(t(lang, 'vip_7d'), callback_data='vip_7d')],
        [InlineKeyboardButton(t(lang, 'vip_30d'), callback_data='vip_30d')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_vip_1d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    cost = VIP_COSTS['1d']
    vip_until = db.get_vip_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_until)) if vip_until else None
    text = t(lang, 'vip_details_1d')
    text += f"\n{t(lang, 'vip_price').format(cost=cost)}"
    if until_str:
        text += f"\n{t(lang, 'vip_until').format(dt=until_str)}"
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{t(lang, 'vip_insufficient').format(coins=current_coins, cost=cost)}"
    keyboard = [
        [InlineKeyboardButton(f"{t(lang, 'vip_buy')} — {cost}", callback_data='buy_vip_1d')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='vip_menu')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_vip_7d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    cost = VIP_COSTS['7d']
    vip_until = db.get_vip_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_until)) if vip_until else None
    text = t(lang, 'vip_details_7d')
    text += f"\n{t(lang, 'vip_price').format(cost=cost)}"
    if until_str:
        text += f"\n{t(lang, 'vip_until').format(dt=until_str)}"
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{t(lang, 'vip_insufficient').format(coins=current_coins, cost=cost)}"
    keyboard = [
        [InlineKeyboardButton(f"{t(lang, 'vip_buy')} — {cost}", callback_data='buy_vip_7d')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='vip_menu')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_vip_30d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    cost = VIP_COSTS['30d']
    vip_until = db.get_vip_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_until)) if vip_until else None
    text = t(lang, 'vip_details_30d')
    text += f"\n{t(lang, 'vip_price').format(cost=cost)}"
    if until_str:
        text += f"\n{t(lang, 'vip_until').format(dt=until_str)}"
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{t(lang, 'vip_insufficient').format(coins=current_coins, cost=cost)}"
    keyboard = [
        [InlineKeyboardButton(f"{t(lang, 'vip_buy')} — {cost}", callback_data='buy_vip_30d')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='vip_menu')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_bonus_tg_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран TG Premium (3 мес): цена, склад, текущий статус и кнопка покупки."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Данные для экрана
    stock = db.get_tg_premium_stock()
    current_coins = int(player.coins or 0)
    tg_until = db.get_tg_premium_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(tg_until)) if tg_until else None

    # Текст
    parts = [t(lang, 'tg_title')]
    parts.append(t(lang, 'tg_price').format(cost=TG_PREMIUM_COST))
    parts.append(t(lang, 'tg_stock').format(stock=stock))
    if until_str:
        parts.append(t(lang, 'tg_until').format(dt=until_str))
    if current_coins < TG_PREMIUM_COST:
        parts.append(t(lang, 'tg_insufficient').format(coins=current_coins, cost=TG_PREMIUM_COST))
    text = "\n".join(parts)

    keyboard = []
    if stock > 0:
        keyboard.append([InlineKeyboardButton(f"{t(lang, 'tg_buy')} — {TG_PREMIUM_COST}", callback_data='buy_tg_premium')])
    keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def buy_stars_500(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка пакета 500 звёзд за внутриигровую валюту с защитой от даблкликов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Защита от даблкликов
    lock = _get_lock(f"user:{user.id}:buy_stars_500")
    if lock.locked():
        await query.answer("Обработка…" if lang != 'en' else 'Processing…', show_alert=False)
        return

    async with lock:
        res = db.purchase_bonus_with_stock(user.id, kind='stars_500', cost_coins=TG_PREMIUM_COST, duration_seconds=0, extra='500')
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer('Недостаточно монет' if lang != 'en' else 'Not enough coins', show_alert=True)
            elif reason == 'out_of_stock':
                await query.answer('Нет в наличии' if lang != 'en' else 'Out of stock', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.' if lang != 'en' else 'Error. Please try later.', show_alert=True)
            return

        coins_left = res.get('coins_left')
        receipt_id = int(res.get('receipt_id') or 0)

        if lang == 'en':
            text = f"500 Stars purchased! Coins left: {coins_left}"
        else:
            text = f"Пакет 500 звёзд куплен! Остаток монет: {coins_left}"
        if receipt_id:
            if lang == 'en':
                text += f"\nReceipt ID: {receipt_id}"
            else:
                text += f"\nID чека: {receipt_id}"

        keyboard = []
        if receipt_id:
            keyboard.append([InlineKeyboardButton(t(lang, 'tg_view_receipt'), callback_data=f'view_receipt_{receipt_id}')])
        keyboard.append([InlineKeyboardButton(t(lang, 'tg_my_receipts'), callback_data='my_receipts')])
        keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='stars_menu')])
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def buy_tg_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка TG Premium (3 мес) за внутриигровую валюту с защитой от даблкликов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Защита от даблкликов
    lock = _get_lock(f"user:{user.id}:buy_tg_premium")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return

    async with lock:
        res = db.purchase_tg_premium(user.id, TG_PREMIUM_COST, TG_PREMIUM_DURATION_SEC)
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await query.answer(t(lang, 'tg_not_enough'), show_alert=True)
            elif reason == 'out_of_stock':
                await query.answer(t(lang, 'tg_out_of_stock'), show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
            return

        tg_until_ts = res.get('tg_premium_until') or db.get_tg_premium_until(user.id)
        coins_left = res.get('coins_left')
        until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(int(tg_until_ts))) if tg_until_ts else '—'

        receipt_id = int(res.get('receipt_id') or 0)
        text = t(lang, 'tg_bought').format(dt=until_str, coins=coins_left)
        if receipt_id:
            if lang == 'en':
                text += f"\nReceipt ID: {receipt_id}"
            else:
                text += f"\nID чека: {receipt_id}"
        keyboard = []
        if receipt_id:
            keyboard.append([InlineKeyboardButton(t(lang, 'tg_view_receipt'), callback_data=f'view_receipt_{receipt_id}')])
        keyboard.append([InlineKeyboardButton(t(lang, 'tg_my_receipts'), callback_data='my_receipts')])
        keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_bonus_steam_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали бонуса: игра в Steam (500 грн)."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    stock = db.get_bonus_stock('steam_game')
    text = t(lang, 'steam_game_details')
    text += f"\n{'Price' if lang == 'en' else 'Цена'}: {TG_PREMIUM_COST}"
    text += f"\n{'In stock' if lang == 'en' else 'В наличии'}: {stock}"
    current_coins = int(player.coins or 0)
    if current_coins < TG_PREMIUM_COST:
        if lang == 'en':
            text += f"\nNot enough coins: {current_coins}/{TG_PREMIUM_COST}"
        else:
            text += f"\nНедостаточно монет: {current_coins}/{TG_PREMIUM_COST}"

    keyboard = []
    if stock > 0:
        buy_label = ("Buy" if lang == 'en' else 'Купить') + f" — {TG_PREMIUM_COST}"
        keyboard.append([InlineKeyboardButton(buy_label, callback_data='buy_steam_game')])
    keyboard.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


# --- Основные обработчики команд и кнопок ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    # Регистрируем группу, если команда в группе
    try:
        await register_group_if_needed(update)
    except Exception:
        pass
    db.get_or_create_player(user.id, user.username or user.first_name)
    await show_menu(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все нажатия на inline-кнопки."""
    # Регистрируем группу, если нажатие было в группе
    try:
        await register_group_if_needed(update)
    except Exception:
        pass
    query = update.callback_query
    data = query.data
    
    # Чтобы не падало, если кнопка без данных
    if not data:
        await query.answer()
        return

    if data == 'menu':
        await show_menu(update, context)
    elif data == 'find_energy':
        await find_energy(update, context)
    elif data == 'claim_bonus':
        await claim_daily_bonus(update, context)
    elif data == 'inventory':
        await show_inventory(update, context)
    elif data.startswith('inventory_p'):
        # Пагинация инвентаря
        await show_inventory(update, context)
    elif data.startswith('receiver_qty_p'):
        # Пагинация инвентаря по количеству для Приёмника
        await show_inventory_by_quantity(update, context)
    elif data == 'stats':
        await show_stats(update, context)
    elif data == 'extra_bonuses':
        await show_extra_bonuses(update, context)
    elif data == 'cities_menu':
        await show_cities_menu(update, context)
    elif data == 'city_hightown' or data == 'market_menu':
        await show_city_hightown(update, context)
    elif data == 'city_silk':
        await silk_ui.show_city_silk(update, context)
    elif data == 'silk_plantations':
        await silk_ui.show_silk_plantations(update, context)
    elif data == 'silk_market':
        await silk_ui.show_silk_market(update, context)
    elif data == 'silk_inventory':
        await silk_ui.show_silk_inventory(update, context)
    elif data == 'silk_stats':
        await silk_ui.show_silk_stats(update, context)
    elif data == 'silk_create_plantation':
        await silk_ui.show_silk_create_plantation(update, context)
    elif data.startswith('silk_plant_'):
        level = data.split('_')[-1]
        await silk_ui.handle_silk_plant(update, context, level)
    elif data.startswith('silk_harvest_'):
        plantation_id = int(data.split('_')[-1])
        await silk_ui.handle_silk_harvest(update, context, plantation_id)
    elif data.startswith('silk_sell_'):
        # silk_sell_{silk_type}_{quantity}
        try:
            _, _, silk_type, quantity_str = data.split('_')
            await silk_ui.handle_silk_sell(update, context, silk_type, quantity_str)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'city_casino':
        await show_city_casino(update, context)
    elif data == 'market_shop':
        await show_market_shop(update, context)
    elif data == 'market_receiver':
        await show_market_receiver(update, context)
    elif data == 'receiver_by_quantity':
        await show_inventory_by_quantity(update, context)
    elif data == 'market_plantation':
        await show_market_plantation(update, context)
    elif data.startswith('shop_p_'):
        await show_market_shop(update, context)
    elif data.startswith('shop_buy_'):
        # shop_buy_{offerIndex}_p{page}
        try:
            _, _, idx, p = data.split('_')
            page = int(p[1:]) if p.startswith('p') else 1
            await handle_shop_buy(update, context, int(idx), int(page))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'plantation_my_beds':
        await show_plantation_my_beds(update, context)
    elif data == 'plantation_shop':
        await show_plantation_shop(update, context)
    elif data == 'plantation_fertilizers_shop':
        await show_plantation_fertilizers_shop(update, context)
    elif data == 'plantation_fertilizers_inv':
        await show_plantation_fertilizers_inventory(update, context)
    elif data == 'plantation_harvest':
        await show_plantation_harvest(update, context)
    elif data == 'plantation_harvest_all':
        await handle_plantation_harvest_all(update, context)
    elif data == 'plantation_community':
        await show_plantation_community(update, context)
    elif data == 'plantation_water':
        await show_plantation_water(update, context)
    elif data == 'plantation_stats':
        await show_plantation_stats(update, context)
    elif data == 'plantation_buy_bed':
        await handle_plantation_buy_bed(update, context)
    elif data == 'plantation_join_project':
        await show_plantation_join_project(update, context)
    elif data == 'plantation_my_contribution':
        await show_plantation_my_contribution(update, context)
    elif data == 'plantation_community_rewards':
        await show_plantation_community_rewards(update, context)
    elif data == 'plantation_water_all':
        await show_plantation_water_all(update, context)
    elif data == 'plantation_leaderboard':
        await show_plantation_leaderboard(update, context)
    elif data == 'community_seed_demo':
        await handle_community_seed_demo(update, context)
    elif data.startswith('community_view_'):
        try:
            pid = int(data.split('_')[-1])
            await show_community_project(update, context, pid)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('community_join_'):
        try:
            pid = int(data.split('_')[-1])
            await handle_community_join(update, context, pid)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('community_contrib_'):
        # community_contrib_{pid}_{amount}
        try:
            _, _, pid, amount = data.split('_')
            await handle_community_contrib(update, context, int(pid), int(amount))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('community_claim_'):
        try:
            pid = int(data.split('_')[-1])
            await handle_community_claim(update, context, pid)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('casino_bet_'):
        try:
            amount = int(data.split('_')[-1])
            await handle_casino_bet(update, context, amount)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'casino_rules':
        await show_casino_rules(update, context)
    elif data.startswith('plantation_buy_'):
        # plantation_buy_{seed_id}_{qty}
        try:
            _, _, sid, qty = data.split('_')
            await handle_plantation_buy(update, context, int(sid), int(qty))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('fert_buy_'):
        # fert_buy_{fert_id}_{qty}
        try:
            _, _, fid, qty = data.split('_')
            await handle_fertilizer_buy(update, context, int(fid), int(qty))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('fert_apply_pick_'):
        # fert_apply_pick_{fert_id}
        try:
            fid = int(data.split('_')[-1])
            await show_fertilizer_apply_pick_bed(update, context, fid)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('fert_apply_do_'):
        # fert_apply_do_{bed}_{fert}
        try:
            _, _, _, bed, fid = data.split('_')
            await handle_fertilizer_apply(update, context, int(bed), int(fid))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('fert_pick_for_bed_'):
        # fert_pick_for_bed_{bed}
        try:
            bed_idx = int(data.split('_')[-1])
            await show_fertilizer_pick_for_bed(update, context, bed_idx)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('plantation_choose_'):
        # plantation_choose_{bed}
        try:
            bed_idx = int(data.split('_')[-1])
            await show_plantation_choose_seed(update, context, bed_idx)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('plantation_plant_'):
        # plantation_plant_{bed}_{seed}
        try:
            _, _, bed, seed = data.split('_')
            await handle_plantation_plant(update, context, int(bed), int(seed))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('plantation_water_'):
        # plantation_water_{bed}
        try:
            bed_idx = int(data.split('_')[-1])
            await handle_plantation_water(update, context, bed_idx)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('plantation_harvest_bed_'):
        # plantation_harvest_bed_{bed}
        try:
            bed_idx = int(data.split('_')[-1])
            await handle_plantation_harvest(update, context, bed_idx)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'bonus_tg_premium':
        await show_bonus_tg_premium(update, context)
    elif data == 'buy_tg_premium':
        await buy_tg_premium(update, context)
    elif data == 'bonus_steam_game':
        await show_bonus_steam_game(update, context)
    elif data == 'buy_stars_500':
        await buy_stars_500(update, context)
    elif data == 'buy_steam_game':
        await buy_steam_game(update, context)
    elif data == 'vip_menu':
        await show_vip_menu(update, context)
    elif data == 'vip_1d':
        await show_vip_1d(update, context)
    elif data == 'vip_7d':
        await show_vip_7d(update, context)
    elif data == 'vip_30d':
        await show_vip_30d(update, context)
    elif data == 'buy_vip_1d':
        await buy_vip(update, context, '1d')
    elif data == 'buy_vip_7d':
        await buy_vip(update, context, '7d')
    elif data == 'buy_vip_30d':
        await buy_vip(update, context, '30d')
    elif data == 'stars_menu':
        await show_stars_menu(update, context)
    elif data == 'stars_500':
        await show_stars_500(update, context)
    elif data == 'noop':
        # Заглушка для неактивных кнопок (например, пагинации на крайних страницах)
        await query.answer()
    elif data == 'my_receipts':
        await my_receipts_handler(update, context)
    elif data.startswith('sellall_'):
        try:
            item_id = int(data.split('_')[1])
            await handle_sell_action(update, context, item_id, sell_all=True)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('sellallbutone_'):
        try:
            item_id = int(data.split('_')[1])
            await handle_sell_all_but_one(update, context, item_id)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('sell_'):
        try:
            item_id = int(data.split('_')[1])
            await handle_sell_action(update, context, item_id, sell_all=False)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('view_receipt_'):
        await view_receipt_handler(update, context)
    elif data.startswith('view_'):
        await view_inventory_item(update, context)
    elif data.startswith('approve_'):
        await approve_pending(update, context)
    elif data.startswith('reject_'):
        await reject_pending(update, context)
    elif data.startswith('delapprove_'):
        await approve_pending_deletion(update, context)
    elif data.startswith('delreject_'):
        await reject_pending_deletion(update, context)
    elif data.startswith('editapprove_'):
        await approve_pending_edit(update, context)
    elif data.startswith('editreject_'):
        await reject_pending_edit(update, context)
    elif data == 'settings':
        await show_settings(update, context)
    elif data == 'settings_lang':
        await settings_lang_menu(update, context)
    elif data == 'settings_reminder':
        await toggle_reminder(update, context)
    elif data == 'settings_auto':
        await toggle_auto_search(update, context)
    elif data == 'settings_reset':
        await reset_prompt(update, context)
    elif data == 'lang_ru':
        await set_language(update, context, 'ru')
    elif data == 'lang_en':
        await set_language(update, context, 'en')
    elif data == 'reset_yes':
        await reset_confirm(update, context, True)
    elif data == 'reset_no':
        await reset_confirm(update, context, False)
    elif data.startswith('selectgift2_'):
        # Новый формат: selectgift2_{token} -> payload в GIFT_SELECT_TOKENS
        token = data.split('_', 1)[1]
        payload = GIFT_SELECT_TOKENS.pop(token, None)
        if not payload:
            await query.answer("Просрочено или неверно", show_alert=True)
        else:
            await handle_select_gift(update, context, payload)
    elif data.startswith('giftresp_'):
        # giftresp_{id}_yes/no
        try:
            _prefix, gid, resp = data.split('_', 2)
            gift_id = int(gid)
            accepted = resp == 'yes'
            await handle_gift_response(update, context, gift_id, accepted)
        except Exception:
            await query.answer("Ошибка", show_alert=True)

async def group_register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрирует группу при любом групповом сообщении/команде."""
    try:
        await register_group_if_needed(update)
    except Exception:
        pass

async def editdrink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/editdrink <id> <field> <new_value> — подать заявку на редактирование (админы ур.1+, только в личке)."""
    user = update.effective_user
    chat = update.effective_chat
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return
    if chat.type != 'private':
        await update.message.reply_text("Этой командой можно пользоваться только в личных сообщениях боту.")
        return
    args = context.args or []
    if len(args) < 3 or not args[0].isdigit():
        await update.message.reply_text("Использование: /editdrink <drink_id> <name|description> <new_value>")
        return
    drink_id = int(args[0])
    field = args[1].lower().strip()
    if field in ('название', 'имя'):
        field = 'name'
    if field in ('описание', 'desc'):  # поддержка локализации
        field = 'description'
    if field not in ('name', 'description'):
        await update.message.reply_text("Поле должно быть name или description")
        return
    new_value = " ".join(args[2:]).strip()
    if not new_value:
        await update.message.reply_text("Новое значение не должно быть пустым")
        return
    drink = db.get_drink_by_id(drink_id)
    if not drink:
        await update.message.reply_text("Напиток с таким ID не найден.")
        return
    pending = db.create_pending_edit(proposer_id=user.id, drink_id=drink_id, field=field, new_value=new_value)
    # Лог
    try:
        db.insert_moderation_log(user.id, 'create_edit_request', request_id=pending.id, target_id=drink_id, details=f"field={field}")
    except Exception:
        pass
    # Уведомляем админов
    admin_ids = db.get_admin_user_ids()
    if admin_ids:
        await asyncio.gather(*[send_edit_proposal_to_admin(context, pending.id, aid) for aid in admin_ids])
    await update.message.reply_text("Заявка на редактирование отправлена на модерацию.")

async def send_edit_proposal_to_admin(context: ContextTypes.DEFAULT_TYPE, request_id: int, admin_chat_id: int):
    pending = db.get_pending_edit_by_id(request_id)
    if not pending or pending.status != 'pending':
        return
    drink = db.get_drink_by_id(pending.drink_id)
    drink_name = drink.name if drink else f"ID {pending.drink_id}"
    # Экранируем данные для HTML
    drink_name_html = html.escape(str(drink_name))
    field_html = html.escape(str(pending.field))
    new_value_html = html.escape(str(pending.new_value))
    caption = (
        f"<b>Заявка на редактирование #{request_id}</b>\n"
        f"Напиток: {drink_name_html} (ID {pending.drink_id})\n"
        f"Поле: {field_html}\n"
        f"Новое значение: {new_value_html}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Применить правку", callback_data=f"editapprove_{request_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"editreject_{request_id}")]
    ])
    await context.bot.send_message(chat_id=admin_chat_id, text=caption, reply_markup=keyboard, parse_mode='HTML')

async def approve_pending_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Одобренить могут только ур.3 или Создатель
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    if not is_creator:
        lvl = db.get_admin_level(user.id)
        if lvl != 3:
            await query.answer("Нет прав: требуется уровень 3 или Создатель.", show_alert=True)
            return
    try:
        request_id = int(query.data.split('_')[1])
    except Exception:
        await query.answer("Неверные данные", show_alert=True)
        return
    pending = db.get_pending_edit_by_id(request_id)
    if not pending or pending.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return
    # Применяем правку
    ok = db.update_energy_drink_field(pending.drink_id, pending.field, pending.new_value)
    if not ok:
        await query.answer("Не удалось применить изменение (возможен конфликт).", show_alert=True)
        return
    db.mark_pending_edit_approved(request_id, user.id)
    # Лог
    try:
        db.insert_moderation_log(user.id, 'approve_edit', request_id=request_id, target_id=pending.drink_id, details=f"field={pending.field}")
    except Exception:
        pass
    # Ответ и уведомления
    try:
        await query.edit_message_text("✅ Правка применена.")
    except BadRequest:
        pass
    try:
        await context.bot.send_message(chat_id=pending.proposer_id, text=f"Ваша заявка #{request_id} на редактирование одобрена и применена.")
    except Exception:
        pass
    try:
        actor = update.effective_user
        admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
        if admin_ids:
            actor_name = f"@{actor.username}" if actor.username else actor.first_name
            drink = db.get_drink_by_id(pending.drink_id)
            drink_name = drink.name if drink else f"ID {pending.drink_id}"
            notif = f"✏️ Правка заявки #{request_id} применена {actor_name}. Напиток: {drink_name}, поле: {pending.field}"
            await asyncio.gather(*[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids], return_exceptions=True)
    except Exception:
        pass

async def reject_pending_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Отклонять могут только ур.3 или Создатель
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    if not is_creator:
        lvl = db.get_admin_level(user.id)
        if lvl != 3:
            await query.answer("Нет прав: требуется уровень 3 или Создатель.", show_alert=True)
            return
    try:
        request_id = int(query.data.split('_')[1])
    except Exception:
        await query.answer("Неверные данные", show_alert=True)
        return
    pending = db.get_pending_edit_by_id(request_id)
    if not pending or pending.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return
    # Запрашиваем причину через ForceReply
    try:
        await query.edit_message_text("Отклонение: отправьте причину в ответ на следующее сообщение (или '-' без причины).")
    except BadRequest:
        pass
    prompt = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Причина отклонения правки заявки #{request_id}:",
        reply_markup=ForceReply(selective=True)
    )
    REJECT_PROMPTS[(prompt.chat_id, prompt.message_id)] = {
        'kind': 'edit',
        'request_id': request_id,
        'origin_chat_id': query.message.chat_id,
        'origin_message_id': query.message.message_id,
        'reviewer_id': user.id,
        'origin_has_media': bool(getattr(query.message, 'photo', None)),
    }


async def incadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/incadd — Создатель создаёт обычную заявку на добавление (для проверки модерации).
    Формат: /incadd Название | Описание | [да/нет]
    Можно ответить на сообщение с фото, чтобы прикрепить изображение.
    """
    user = update.effective_user
    # Только Создатель
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("Нет прав: только Создатель может использовать эту команду.")
        return

    # Парсинг аргументов: "Название | Описание | [да/нет]"
    if not context.args:
        await update.message.reply_text(
            "Использование: /incadd Название | Описание | [да/нет]\n"
            "Подсказка: можно ответить на сообщение с фото, чтобы прикрепить изображение."
        )
        return

    raw = " ".join(context.args).strip()
    parts = [p.strip() for p in raw.split("|")]
    if not parts or not parts[0]:
        await update.message.reply_text("Укажите название. Пример: /incadd Nitro Cola | Мощный заряд энергии | нет")
        return
    name = parts[0]
    description = parts[1] if len(parts) > 1 else ""
    special_raw = (parts[2] if len(parts) > 2 else "").lower()
    is_special = special_raw in {"да", "yes", "y", "д"}

    # Фото из reply (необязательно)
    file_id = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        try:
            file_id = update.message.reply_to_message.photo[-1].file_id
        except Exception:
            file_id = None

    # Создаём обычную заявку от имени создателя (без пометок)
    pending = db.create_pending_addition(
        proposer_id=user.id,
        name=name,
        description=description,
        is_special=is_special,
        file_id=file_id,
    )
    # Аудит-лог создания заявки создателем
    try:
        db.insert_moderation_log(user.id, 'create_add_request', request_id=pending.id, details=f"name={name}")
    except Exception:
        pass

    # Рассылаем администраторам как обычно
    admin_ids = db.get_admin_user_ids()
    if admin_ids:
        await asyncio.gather(*[send_proposal_to_admin(context, pending.id, admin_id) for admin_id in admin_ids])
        await update.message.reply_text("Заявка отправлена администраторам на одобрение.")
    else:
        await update.message.reply_text("Администраторы не настроены. Обратитесь к владельцу бота.")

async def delrequest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delrequest <drink_id> [reason] — создать заявку на удаление энергетика (админы, ТОЛЬКО в личке)."""
    user = update.effective_user
    chat = update.effective_chat
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return
    if chat.type != 'private':
        await update.message.reply_text("Этой командой можно пользоваться только в личных сообщениях боту.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /delrequest <drink_id> [причина]")
        return
    drink_id = int(context.args[0])
    reason = " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
    drink = db.get_drink_by_id(drink_id)
    if not drink:
        await update.message.reply_text("Напиток с таким ID не найден.")
        return
    pending = db.create_pending_deletion(proposer_id=user.id, drink_id=drink_id, reason=reason)
    # Уведомляем всех админов (одобрять/отклонять смогут только главные)
    admin_ids = db.get_admin_user_ids()
    if admin_ids:
        await asyncio.gather(*[send_deletion_proposal_to_admin(context, pending.id, aid) for aid in admin_ids])
    await update.message.reply_text(f"Заявка на удаление '{drink.name}' (ID {drink.id}) отправлена на модерацию.")

async def inceditdrink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/inceditdrink <id> <field> <new_value> — создать обычную заявку на редактирование (только Создатель)."""
    user = update.effective_user
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("Нет прав: только Создатель может использовать эту команду.")
        return
    args = context.args or []
    if len(args) < 3 or not args[0].isdigit():
        await update.message.reply_text("Использование: /inceditdrink <drink_id> <name|description> <new_value>")
        return
    drink_id = int(args[0])
    field = args[1].lower().strip()
    if field in ('название', 'имя'):
        field = 'name'
    if field in ('описание', 'desc'):
        field = 'description'
    if field not in ('name', 'description'):
        await update.message.reply_text("Поле должно быть name или description")
        return
    new_value = " ".join(args[2:]).strip()
    if not new_value:
        await update.message.reply_text("Новое значение не должно быть пустым")
        return
    drink = db.get_drink_by_id(drink_id)
    if not drink:
        await update.message.reply_text("Напиток с таким ID не найден.")
        return
    pending = db.create_pending_edit(proposer_id=user.id, drink_id=drink_id, field=field, new_value=new_value)
    try:
        db.insert_moderation_log(user.id, 'create_edit_request', request_id=pending.id, target_id=drink_id, details=f"field={field}")
    except Exception:
        pass
    admin_ids = db.get_admin_user_ids()
    if admin_ids:
        await asyncio.gather(*[send_edit_proposal_to_admin(context, pending.id, aid) for aid in admin_ids])
    await update.message.reply_text("Заявка на редактирование отправлена на модерацию.")

async def incdelrequest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/incdelrequest <drink_id> [reason] — создать обычную заявку на удаление (только Создатель)."""
    user = update.effective_user
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("Нет прав: только Создатель может использовать эту команду.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /incdelrequest <drink_id> [причина]")
        return
    drink_id = int(context.args[0])
    reason = " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
    drink = db.get_drink_by_id(drink_id)
    if not drink:
        await update.message.reply_text("Напиток с таким ID не найден.")
        return
    pending = db.create_pending_deletion(proposer_id=user.id, drink_id=drink_id, reason=reason)
    try:
        db.insert_moderation_log(user.id, 'create_delete_request', request_id=pending.id, target_id=drink_id)
    except Exception:
        pass
    admin_ids = db.get_admin_user_ids()
    if admin_ids:
        await asyncio.gather(*[send_deletion_proposal_to_admin(context, pending.id, aid) for aid in admin_ids])
    await update.message.reply_text(f"Заявка на удаление '{drink.name}' (ID {drink.id}) отправлена на модерацию.")

async def send_deletion_proposal_to_admin(context: ContextTypes.DEFAULT_TYPE, request_id: int, admin_chat_id: int):
    pending = db.get_pending_deletion_by_id(request_id)
    if not pending or pending.status != 'pending':
        return
    drink = db.get_drink_by_id(pending.drink_id)
    drink_name = drink.name if drink else f"ID {pending.drink_id}"
    # Экранируем HTML
    drink_name_html = html.escape(str(drink_name))
    reason_html = html.escape(str(pending.reason)) if getattr(pending, 'reason', None) else '—'
    caption = (
        f"<b>Заявка на удаление #{request_id}</b>\n"
        f"Напиток: {drink_name_html} (ID {pending.drink_id})\n"
        f"Причина: {reason_html}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить удаление", callback_data=f"delapprove_{request_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"delreject_{request_id}")]
    ])
    await context.bot.send_message(chat_id=admin_chat_id, text=caption, reply_markup=keyboard, parse_mode='HTML')

async def approve_pending_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Разрешено ур.3 или Создателям
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    if not is_creator:
        lvl = db.get_admin_level(user.id)
        if lvl != 3:
            await query.answer("Нет прав: требуется уровень 3 или Создатель.", show_alert=True)
            return
    try:
        request_id = int(query.data.split('_')[1])
    except Exception:
        await query.answer("Неверные данные", show_alert=True)
        return
    pending = db.get_pending_deletion_by_id(request_id)
    if not pending or pending.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return
    drink = db.get_drink_by_id(pending.drink_id)
    drink_name = drink.name if drink else f"ID {pending.drink_id}"
    # Пытаемся удалить
    deleted = db.delete_energy_drink(pending.drink_id)
    db.mark_pending_deletion_approved(request_id, update.effective_user.id)
    # Аудит-лог
    try:
        db.insert_moderation_log(user.id, 'approve_delete', request_id=request_id, target_id=pending.drink_id, details=f"deleted={deleted}")
    except Exception:
        pass
    try:
        await query.edit_message_text("✅ Удаление одобрено." + (" Напиток удалён." if deleted else " Напиток уже отсутствует."))
    except BadRequest:
        pass
    # Уведомляем инициатора
    try:
        await context.bot.send_message(chat_id=pending.proposer_id, text=f"Ваша заявка #{request_id} на удаление '{drink_name}' одобрена. Напиток удалён.")
    except Exception:
        pass
    # Уведомляем остальных админов
    try:
        actor = update.effective_user
        admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
        if admin_ids:
            actor_name = f"@{actor.username}" if actor.username else actor.first_name
            notif = f"🗑️ Удаление заявки #{request_id} одобрено {actor_name}. Напиток: {drink_name}"
            await asyncio.gather(*[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids], return_exceptions=True)
    except Exception:
        pass

async def reject_pending_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Разрешено ур.3 или Создателям
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    if not is_creator:
        lvl = db.get_admin_level(user.id)
        if lvl != 3:
            await query.answer("Нет прав: требуется уровень 3 или Создатель.", show_alert=True)
            return
    try:
        request_id = int(query.data.split('_')[1])
    except Exception:
        await query.answer("Неверные данные", show_alert=True)
        return
    pending = db.get_pending_deletion_by_id(request_id)
    if not pending or pending.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return
    # Запрашиваем причину через ForceReply
    try:
        await query.edit_message_text("Отклонение: отправьте причину в ответ на следующее сообщение (или '-' без причины).")
    except BadRequest:
        pass
    prompt = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Причина отклонения удаления заявки #{request_id}:",
        reply_markup=ForceReply(selective=True)
    )
    REJECT_PROMPTS[(prompt.chat_id, prompt.message_id)] = {
        'kind': 'del',
        'request_id': request_id,
        'origin_chat_id': query.message.chat_id,
        'origin_message_id': query.message.message_id,
        'reviewer_id': user.id,
        'origin_has_media': bool(getattr(query.message, 'photo', None)),
    }

async def handle_reject_reason_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ с причиной отклонения (reply на ForceReply-сообщение)."""
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    key = (msg.chat_id, msg.reply_to_message.message_id)
    data = REJECT_PROMPTS.get(key)
    if not data:
        return
    # Разрешаем отвечать только модератору, который нажал "Отклонить"
    if msg.from_user and data.get('reviewer_id') and msg.from_user.id != data['reviewer_id']:
        try:
            await msg.reply_text("Ответ с причиной может дать только модератор, инициировавший отклонение.")
        except Exception:
            pass
        return
    reason_raw = (msg.text or '').strip()
    reason = None if reason_raw in ('-', '—', '') else reason_raw
    kind = data['kind']
    request_id = data['request_id']
    reviewer_id = data['reviewer_id']
    origin_chat_id = data['origin_chat_id']
    origin_message_id = data['origin_message_id']

    try:
        if kind == 'edit':
            pending = db.get_pending_edit_by_id(request_id)
            if not pending or pending.status != 'pending':
                await msg.reply_text("Заявка уже обработана или не найдена.")
                return
            db.mark_pending_edit_rejected(request_id, reviewer_id, reason)
            try:
                db.insert_moderation_log(reviewer_id, 'reject_edit', request_id=request_id, target_id=pending.drink_id, details=f"field={pending.field}; reason={reason or '-'}")
            except Exception:
                pass
            # Уведомления
            try:
                await context.bot.send_message(chat_id=pending.proposer_id, text=f"Ваша заявка #{request_id} на редактирование отклонена.\nПричина: {reason or '—'}")
            except Exception:
                pass
            try:
                actor = update.effective_user
                admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
                if admin_ids:
                    actor_name = f"@{actor.username}" if actor.username else actor.first_name
                    drink = db.get_drink_by_id(pending.drink_id)
                    drink_name = drink.name if drink else f"ID {pending.drink_id}"
                    notif = f"🚫 Правка заявки #{request_id} отклонена {actor_name}. Напиток: {drink_name}, поле: {pending.field}\nПричина: {reason or '—'}"
                    await asyncio.gather(*[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids], return_exceptions=True)
            except Exception:
                pass
        elif kind == 'add':
            proposal = db.get_pending_by_id(request_id)
            if not proposal or proposal.status != 'pending':
                await msg.reply_text("Заявка уже обработана или не найдена.")
                return
            db.mark_pending_as_rejected(request_id, reviewer_id, reason)
            try:
                db.insert_moderation_log(reviewer_id, 'reject_add', request_id=request_id, details=f"name={proposal.name}; reason={reason or '-'}")
            except Exception:
                pass
            try:
                await context.bot.send_message(chat_id=proposal.proposer_id, text=f"Ваша заявка #{request_id} на добавление отклонена.\nПричина: {reason or '—'}")
            except Exception:
                pass
            try:
                actor = update.effective_user
                admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
                if admin_ids:
                    actor_name = f"@{actor.username}" if actor.username else actor.first_name
                    notif = f"🚫 Заявка на добавление #{request_id} отклонена {actor_name}. Название: {proposal.name}\nПричина: {reason or '—'}"
                    await asyncio.gather(*[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids], return_exceptions=True)
            except Exception:
                pass
        elif kind == 'del':
            pending = db.get_pending_deletion_by_id(request_id)
            if not pending or pending.status != 'pending':
                await msg.reply_text("Заявка уже обработана или не найдена.")
                return
            db.mark_pending_deletion_rejected(request_id, reviewer_id, reason)
            try:
                db.insert_moderation_log(reviewer_id, 'reject_delete', request_id=request_id, target_id=pending.drink_id, details=(reason or None))
            except Exception:
                pass
            drink = db.get_drink_by_id(pending.drink_id)
            drink_name = drink.name if drink else f"ID {pending.drink_id}"
            try:
                await context.bot.send_message(chat_id=pending.proposer_id, text=f"Ваша заявка #{request_id} на удаление '{drink_name}' отклонена.\nПричина: {reason or '—'}")
            except Exception:
                pass
            try:
                actor = update.effective_user
                admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
                if admin_ids:
                    actor_name = f"@{actor.username}" if actor.username else actor.first_name
                    notif = f"🚫 Удаление заявки #{request_id} отклонено {actor_name}. Напиток: {drink_name}\nПричина: {reason or '—'}"
                    await asyncio.gather(*[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids], return_exceptions=True)
            except Exception:
                pass
        # Пытаемся обновить исходное сообщение с заявкой
        origin_has_media = data.get('origin_has_media', False)
        try:
            if origin_has_media:
                await context.bot.edit_message_caption(
                    chat_id=origin_chat_id,
                    message_id=origin_message_id,
                    caption=f"❌ Отклонено. Причина: {reason or '—'}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=origin_chat_id,
                    message_id=origin_message_id,
                    text=f"❌ Отклонено. Причина: {reason or '—'}"
                )
        except BadRequest:
            pass
        await msg.reply_text("Готово: отклонено.")
        # Удаляем ожидание причины только после успешной обработки
        REJECT_PROMPTS.pop(key, None)
    except Exception as e:
        try:
            await msg.reply_text(f"Ошибка при обработке отклонения: {e}")
        except Exception:
            pass

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/register — вручную зарегистрировать группу для рассылок (только в группах)."""
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда доступна только в группах.")
        return
    created = db.upsert_group_chat(chat.id, chat.title)
    if created:
        await update.message.reply_text("Группа зарегистрирована для уведомлений.")
    else:
        await update.message.reply_text("Группа уже была зарегистрирована.")

async def register_group_if_needed(update: Update):
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        try:
            db.upsert_group_chat(chat_id=chat.id, title=chat.title)
        except Exception:
            pass


# --- Диагностика: логирование всех команд в группах ---
async def debug_log_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        logger.info(
            "[CMD] chat_id=%s type=%s user_id=%s username=%s text=%s",
            getattr(chat, 'id', None),
            getattr(chat, 'type', None),
            getattr(user, 'id', None),
            getattr(user, 'username', None),
            getattr(msg, 'text', None),
        )
    except Exception:
        pass


# -------- Команда /add ---------

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления энергетика."""
    user = update.effective_user
    # Регистрируем bootstrap-админа при первом обращении
    if user.username in ADMIN_USERNAMES:
        try:
            db.add_admin_user(user.id, user.username)
        except Exception:
            pass
    # Кулдаун 6 часов для не-админов
    is_admin = db.is_admin(user.id) or (user.username in ADMIN_USERNAMES)
    if not is_admin:
        try:
            player = db.get_or_create_player(user.id, user.username or "")
            now = int(time.time())
            cooldown = 6 * 60 * 60  # 6 часов
            last_add = getattr(player, 'last_add', 0) or 0
            if last_add and (now - last_add) < cooldown:
                remain = cooldown - (now - last_add)
                hrs = remain // 3600
                mins = (remain % 3600) // 60
                text = "Вы уже отправляли заявку недавно. Повторно можно через "
                if hrs > 0:
                    text += f"{hrs} ч "
                text += f"{mins} мин."
                await update.message.reply_text(text)
                return ConversationHandler.END
        except Exception:
            # В случае ошибки проверки кулдауна не блокируем пользователя
            pass
    await update.message.reply_text("Введите название энергетика:")
    context.user_data.clear()
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("Введите описание:")
    return ADD_DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text.strip()
    await update.message.reply_text("Является ли энергетик специальным? (да/нет):")
    return ADD_SPECIAL

async def add_special(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    context.user_data['is_special'] = text in ('да', 'yes', 'y', 'д')
    await update.message.reply_text("Пришлите фото энергетика или отправьте /skip, чтобы пропустить:")
    return ADD_PHOTO

async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Фото получено
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data['file_id'] = photo_file.file_id
    else:
        context.user_data['file_id'] = None
    return await finalize_addition(update, context)

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['file_id'] = None
    return await finalize_addition(update, context)

async def finalize_addition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальный этап: добавляем сразу или создаём заявку."""
    global NEXT_PENDING_ID
    user = update.effective_user
    data = context.user_data

    if db.is_admin(user.id) or (user.username in ADMIN_USERNAMES):
        # Админ – добавляем сразу
        image_path = None
        if data.get('file_id'):
            # скачиваем
            file = await context.bot.get_file(data['file_id'])
            os.makedirs(ENERGY_IMAGES_DIR, exist_ok=True)
            image_path = f"{int(time.time())}_{random.randint(1000,9999)}.jpg"
            await file.download_to_drive(os.path.join(ENERGY_IMAGES_DIR, image_path))
        db.add_energy_drink(
            name=data['name'],
            description=data['description'],
            image_path=image_path,
            is_special=data['is_special']
        )
        await update.message.reply_text("Энергетик успешно добавлен!")
    else:
        # Обычный пользователь – создаём заявку
        pending = db.create_pending_addition(
            proposer_id=user.id,
            name=data['name'],
            description=data['description'],
            is_special=data['is_special'],
            file_id=data.get('file_id')
        )
        # Обновляем метку кулдауна для не-администратора
        try:
            if not (db.is_admin(user.id) or (user.username in ADMIN_USERNAMES)):
                db.update_player(user.id, last_add=int(time.time()))
        except Exception:
            pass
        # Отправляем всем администраторам
        admin_ids = db.get_admin_user_ids()
        if admin_ids:
            await asyncio.gather(*[send_proposal_to_admin(context, pending.id, admin_id) for admin_id in admin_ids])
            await update.message.reply_text("Заявка отправлена администраторам на одобрение.")
        else:
            await update.message.reply_text("Администраторы не настроены. Обратитесь к владельцу бота.")
    return ConversationHandler.END

async def send_proposal_to_admin(context: ContextTypes.DEFAULT_TYPE, request_id: int, admin_chat_id: int):
    proposal = db.get_pending_by_id(request_id)
    if not proposal or proposal.status != 'pending':
        return
    caption = (
        f"<b>Новая заявка #{request_id}</b>\n"
        f"Название: {proposal.name}\n"
        f"Описание: {proposal.description}\n"
        f"Специальный: {'Да' if proposal.is_special else 'Нет'}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")]
    ])
    if proposal.file_id:
        await context.bot.send_photo(
            chat_id=admin_chat_id,
            photo=proposal.file_id,
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

async def approve_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not db.is_admin(update.effective_user.id) and (update.effective_user.username not in ADMIN_USERNAMES):
        await query.answer("Нет прав", show_alert=True)
        return
    request_id = int(query.data.split('_')[1])
    proposal = db.get_pending_by_id(request_id)
    if not proposal or proposal.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return

    # Запрет самопринятия: нельзя одобрять собственную заявку
    actor = update.effective_user
    if proposal.proposer_id == actor.id:
        await query.answer("Нельзя одобрять собственную заявку", show_alert=True)
        return

    # Сохраняем энергетик
    image_path = None
    if proposal.file_id:
        file = await context.bot.get_file(proposal.file_id)
        os.makedirs(ENERGY_IMAGES_DIR, exist_ok=True)
        image_path = f"{int(time.time())}_{random.randint(1000,9999)}.jpg"
        await file.download_to_drive(os.path.join(ENERGY_IMAGES_DIR, image_path))
    db.add_energy_drink(
        name=proposal.name,
        description=proposal.description,
        image_path=image_path,
        is_special=proposal.is_special
    )
    db.mark_pending_as_approved(request_id, update.effective_user.id)
    # Аудит-лог
    try:
        db.insert_moderation_log(actor.id, 'approve_add', request_id=request_id, details=f"name={proposal.name}")
    except Exception:
        pass
    # Уведомляем — редактируем исходное сообщение безопасно по типу
    has_media = bool(getattr(query.message, 'photo', None))
    try:
        if has_media:
            await query.edit_message_caption(caption="✅ Одобрено и добавлено в базу.")
        else:
            await query.edit_message_text("✅ Одобрено и добавлено в базу.")
    except BadRequest:
        pass
    await context.bot.send_message(chat_id=proposal.proposer_id, text="Ваш энергетик одобрен и добавлен! 🎉")
    # Уведомляем остальных администраторов о решении модерации
    try:
        actor = update.effective_user
        admin_ids = [aid for aid in db.get_admin_user_ids() if aid != actor.id]
        if admin_ids:
            actor_name = f"@{actor.username}" if actor.username else actor.first_name
            notif = f"✅ Заявка #{request_id} одобрена {actor_name}.\nНазвание: {proposal.name}"
            await asyncio.gather(
                *[context.bot.send_message(chat_id=aid, text=notif) for aid in admin_ids],
                return_exceptions=True
            )
    except Exception:
        pass

async def reject_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Для отклонения добавления — ур.2+ или Создатель
    user = update.effective_user
    is_creator = (user.username in ADMIN_USERNAMES)
    if not is_creator:
        lvl = db.get_admin_level(user.id)
        if lvl < 2:
            await query.answer("Нет прав: требуется уровень 2+ или Создатель.", show_alert=True)
            return
    request_id = int(query.data.split('_')[1])
    proposal = db.get_pending_by_id(request_id)
    if not proposal or proposal.status != 'pending':
        await query.answer("Заявка не найдена", show_alert=True)
        return
    # Запрашиваем причину через ForceReply — безопасно редактируем исходное сообщение
    has_media = bool(getattr(query.message, 'photo', None))
    try:
        if has_media:
            await query.edit_message_caption(caption="Отклонение: отправьте причину в ответ на следующее сообщение (или '-' без причины).")
        else:
            await query.edit_message_text("Отклонение: отправьте причину в ответ на следующее сообщение (или '-' без причины).")
    except BadRequest:
        pass
    prompt = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Причина отклонения заявки на добавление #{request_id}:",
        reply_markup=ForceReply(selective=True)
    )
    REJECT_PROMPTS[(prompt.chat_id, prompt.message_id)] = {
        'kind': 'add',
        'request_id': request_id,
        'origin_chat_id': query.message.chat_id,
        'origin_message_id': query.message.message_id,
        'reviewer_id': user.id,
    }

async def requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/requests — список ожидающих заявок с кнопками модерации."""
    user = update.effective_user
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return
    pendings = db.get_pending_additions(limit=10)
    edit_pendings = db.get_pending_edits(limit=10)
    del_pendings = db.get_pending_deletions(limit=10)
    if not pendings and not edit_pendings and not del_pendings:
        await update.message.reply_text("Ожидающих заявок нет")
        return
    if pendings:
        for p in pendings:
            caption = (
                f"#{p.id} — {p.name}\n"
                f"Специальный: {'Да' if p.is_special else 'Нет'}\n"
                f"Описание: {p.description}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{p.id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{p.id}")]
            ])
            if p.file_id:
                await update.message.reply_photo(photo=p.file_id, caption=caption, reply_markup=keyboard)
            else:
                await update.message.reply_text(text=caption, reply_markup=keyboard)
    if edit_pendings:
        await update.message.reply_text("— Заявки на редактирование —")
        for ep in edit_pendings:
            drink = db.get_drink_by_id(ep.drink_id)
            drink_name = drink.name if drink else f"ID {ep.drink_id}"
            cap = (
                f"#EDIT{ep.id} — {drink_name} (ID {ep.drink_id})\n"
                f"Поле: {ep.field}\n"
                f"Новое значение: {ep.new_value}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Применить правку", callback_data=f"editapprove_{ep.id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"editreject_{ep.id}")]
            ])
            await update.message.reply_text(text=cap, reply_markup=kb)
    if del_pendings:
        await update.message.reply_text("— Заявки на удаление —")
        for dp in del_pendings:
            drink = db.get_drink_by_id(dp.drink_id)
            drink_name = drink.name if drink else f"ID {dp.drink_id}"
            cap = (
                f"#DEL{dp.id} — {drink_name} (ID {dp.drink_id})\n"
                f"Причина: {dp.reason or '—'}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить удаление", callback_data=f"delapprove_{dp.id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"delreject_{dp.id}")]
            ])
            await update.message.reply_text(text=cap, reply_markup=kb)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/id — показать соответствие ID -> название энергетика. Только для админов, только в личке."""
    user = update.effective_user
    chat = update.effective_chat
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return
    if chat.type != 'private':
        await update.message.reply_text("Эта команда доступна только в личных сообщениях боту.")
        return
    drinks = db.get_all_drinks()
    if not drinks:
        await update.message.reply_text("В базе данных нет энергетиков.")
        return
    # Сортируем по ID
    drinks_sorted = sorted(drinks, key=lambda d: d.id)
    lines = [f"{d.id}: {d.name}" for d in drinks_sorted]
    header = f"Всего энергетиков: {len(lines)}\n"
    # Чанкуем по длине сообщения ~3500 символов
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > 3500:
            await update.message.reply_text(chunk.rstrip())
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await update.message.reply_text(chunk.rstrip())

async def addcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addcoins — только для Создателя. Начисляет монеты пользователю по ID или username.
    Использование:
    /addcoins <amount> <user_id|@username>
    или ответом на сообщение: /addcoins <amount>
    """
    user = update.effective_user
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("Нет прав: команда доступна только Создателю.")
        return

    args = context.args or []
    target_id = None
    target_username = None
    amount = None

    # Вариант: ответ на сообщение
    if update.message.reply_to_message:
        if not args or not args[0].lstrip('+').isdigit():
            await update.message.reply_text("Использование: ответом на сообщение — /addcoins <amount>")
            return
        amount = int(args[0])
        target_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
    else:
        if len(args) < 2:
            await update.message.reply_text("Использование: /addcoins <amount> <user_id|@username>")
            return
        a, b = args[0], args[1]
        id_or_username = None
        if a.lstrip('+').isdigit() and not b.lstrip('+').isdigit():
            amount = int(a)
            id_or_username = b
        elif b.lstrip('+').isdigit() and not a.lstrip('+').isdigit():
            amount = int(b)
            id_or_username = a
        elif a.lstrip('+').isdigit() and b.lstrip('+').isdigit():
            amount = int(a)
            id_or_username = b
        else:
            await update.message.reply_text("Не удалось распознать аргументы. Использование: /addcoins <amount> <user_id|@username>")
            return
        if id_or_username.startswith('@'):
            target_username = id_or_username[1:]
        elif id_or_username.isdigit():
            target_id = int(id_or_username)
        else:
            target_username = id_or_username

    if amount is None or amount <= 0:
        await update.message.reply_text("Сумма должна быть положительным целым числом.")
        return

    # Разрешение username -> ID, если нужно
    if target_id is None and target_username:
        try:
            chat_obj = await context.bot.get_chat(f"@{target_username}")
            if getattr(chat_obj, 'id', None):
                target_id = chat_obj.id
        except Exception:
            pass
        if target_id is None:
            player = db.get_player_by_username(target_username)
            if player:
                target_id = int(player.user_id)

    if target_id is None:
        await update.message.reply_text("Не удалось определить пользователя по указанному идентификатору/username.")
        return

    new_balance = db.increment_coins(target_id, amount)
    if new_balance is None:
        await update.message.reply_text("Не удалось обновить баланс. Попробуйте позже.")
        return

    # Аудит-лог (не критично при ошибке)
    try:
        db.insert_moderation_log(user.id, 'grant_coins', target_id=target_id, details=f"amount={amount}")
    except Exception:
        pass

    shown = f"@{target_username}" if target_username else str(target_id)
    await update.message.reply_text(f"✅ Начислено {amount} септимов пользователю {shown}.\nНовый баланс: {new_balance}")

async def delmoney_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delmoney — только для Создателя. Списывает монеты у пользователя по ID или username.
    Использование:
    /delmoney <amount> <user_id|@username>
    или ответом на сообщение: /delmoney <amount>
    """
    user = update.effective_user
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("Нет прав: команда доступна только Создателю.")
        return

    args = context.args or []
    target_id = None
    target_username = None
    amount = None

    # Вариант: ответ на сообщение
    if update.message.reply_to_message:
        if not args or not args[0].lstrip('+').isdigit():
            await update.message.reply_text("Использование: ответом на сообщение — /delmoney <amount>")
            return
        amount = int(args[0])
        target_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
    else:
        if len(args) < 2:
            await update.message.reply_text("Использование: /delmoney <amount> <user_id|@username>")
            return
        a, b = args[0], args[1]
        id_or_username = None
        if a.lstrip('+').isdigit() and not b.lstrip('+').isdigit():
            amount = int(a)
            id_or_username = b
        elif b.lstrip('+').isdigit() and not a.lstrip('+').isdigit():
            amount = int(b)
            id_or_username = a
        elif a.lstrip('+').isdigit() and b.lstrip('+').isdigit():
            amount = int(a)
            id_or_username = b
        else:
            await update.message.reply_text("Не удалось распознать аргументы. Использование: /delmoney <amount> <user_id|@username>")
            return
        if id_or_username.startswith('@'):
            target_username = id_or_username[1:]
        elif id_or_username.isdigit():
            target_id = int(id_or_username)
        else:
            target_username = id_or_username

    if amount is None or amount <= 0:
        await update.message.reply_text("Сумма должна быть положительным целым числом.")
        return

    # Разрешение username -> ID, если нужно
    if target_id is None and target_username:
        try:
            chat_obj = await context.bot.get_chat(f"@{target_username}")
            if getattr(chat_obj, 'id', None):
                target_id = chat_obj.id
        except Exception:
            pass
        if target_id is None:
            player = db.get_player_by_username(target_username)
            if player:
                target_id = int(player.user_id)

    if target_id is None:
        await update.message.reply_text("Не удалось определить пользователя по указанному идентификатору/username.")
        return

    result = db.decrement_coins(target_id, amount)
    if not result.get('ok'):
        if result.get('insufficient'):
            current = result.get('current_balance', 0)
            requested = result.get('requested_amount', amount)
            await update.message.reply_text(f"❌ Недостаточно средств у пользователя.\nТекущий баланс: {current} септимов\nЗапрошено: {requested} септимов")
        else:
            await update.message.reply_text("Не удалось обновить баланс. Попробуйте позже.")
        return

    # Аудит-лог (не критично при ошибке)
    try:
        db.insert_moderation_log(user.id, 'remove_coins', target_id=target_id, details=f"amount={amount}")
    except Exception:
        pass

    shown = f"@{target_username}" if target_username else str(target_id)
    new_balance = result.get('new_balance', 0)
    removed_amount = result.get('removed_amount', amount)
    await update.message.reply_text(f"✅ Списано {removed_amount} септимов у пользователя {shown}.\nНовый баланс: {new_balance}")

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END


def log_existing_drinks():
    """Выводит в логи список всех энергетиков, присутствующих в базе."""
    drinks = db.get_all_drinks()
    if not drinks:
        logger.info("[DRINKS] База пуста.")
        return
    logger.info("[DRINKS] Список энергетиков:")
    for d in drinks:
        logger.info(f"- {d.id}: {d.name}")

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)

    lang = player.language
    lang_readable = 'Русский' if lang == 'ru' else 'English'
    reminder_state = t(lang, 'on') if player.remind else t(lang, 'off')
    auto_state = t(lang, 'on') if getattr(player, 'auto_search_enabled', False) else t(lang, 'off')

    # Доп. информация: когда сбросится автопоиск VIP и сколько попыток осталось сегодня (показывать всегда)
    reset_info = ""
    now_ts = int(time.time())
    reset_ts = int(getattr(player, 'auto_search_reset_ts', 0) or 0)
    count = int(getattr(player, 'auto_search_count', 0) or 0)
    try:
        daily_limit = int(db.get_auto_search_daily_limit(user_id))
    except Exception:
        daily_limit = 0
    left_today = max(0, daily_limit - count) if daily_limit > 0 else 0
    if reset_ts > now_ts:
        left = reset_ts - now_ts
        prefix = "⏳ До сброса автопоиска: " if lang == 'ru' else "⏳ Auto-search resets in: "
        usage_ru = f" (осталось {left_today}/{daily_limit})" if lang == 'ru' else ""
        usage_en = f" (left {left_today}/{daily_limit} today)" if lang == 'en' else ""
        reset_info = f"{prefix}{_fmt_time(left)}{usage_ru or usage_en}\n"
    else:
        reset_info = ("⏳ До сброса автопоиска: —\n" if lang == 'ru' else "⏳ Auto-search reset: —\n")

    text = (
        f"<b>{t(lang, 'settings_title')}</b>\n\n"
        f"{t(lang, 'current_language')}: {lang_readable}\n"
        f"{t(lang, 'auto_reminder')}: {reminder_state}\n"
        f"{t(lang, 'auto_search')}: {auto_state}\n"
    )

    if reset_info:
        text += reset_info

    keyboard = [
        [InlineKeyboardButton(t(lang, 'btn_change_lang'), callback_data='settings_lang')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_rem'), callback_data='settings_reminder')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_auto'), callback_data='settings_auto')],
        [InlineKeyboardButton(t(lang, 'btn_reset'), callback_data='settings_reset')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='menu')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def settings_lang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
    lang = player.language
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data='lang_ru'), InlineKeyboardButton("English", callback_data='lang_en')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='settings')]
    ]
    await query.edit_message_text(t(lang, 'choose_lang'), reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str):
    query = update.callback_query
    await query.answer()

    db.update_player(query.from_user.id, language=lang_code)
    await query.answer("Язык обновлён" if lang_code == 'ru' else 'Language updated', show_alert=True)
    # Возврат в меню настроек
    await show_settings(update, context)

async def toggle_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
    new_state = not player.remind
    db.update_player(player.user_id, remind=new_state)
    await query.answer("Изменено" , show_alert=True)
    await show_settings(update, context)

async def toggle_auto_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = player.language

    current = bool(getattr(player, 'auto_search_enabled', False))
    if not current:
        # Включаем — проверим VIP
        if not db.is_vip(user_id):
            await query.answer(t(lang, 'auto_requires_vip'), show_alert=True)
            await show_settings(update, context)
            return
        db.update_player(user_id, auto_search_enabled=True)
        # Сбросим окно, если не задано
        now_ts = int(time.time())
        reset_ts = int(getattr(player, 'auto_search_reset_ts', 0) or 0)
        if reset_ts == 0:
            db.update_player(user_id, auto_search_reset_ts=now_ts + 24*60*60)
        # Снесём предыдущие задачи и запланируем новую
        try:
            jobs = context.application.job_queue.get_jobs_by_name(f"auto_search_{user_id}")
            for j in jobs:
                j.schedule_removal()
        except Exception:
            pass
        try:
            context.application.job_queue.run_once(
                auto_search_job,
                when=1,
                chat_id=user_id,
                name=f"auto_search_{user_id}",
            )
        except Exception:
            pass
        try:
            current_limit = db.get_auto_search_daily_limit(user_id)
            await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_enabled').format(limit=current_limit))
        except Exception:
            pass
    else:
        # Выключаем
        db.update_player(user_id, auto_search_enabled=False)
        try:
            jobs = context.application.job_queue.get_jobs_by_name(f"auto_search_{user_id}")
            for j in jobs:
                j.schedule_removal()
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_disabled'))
        except Exception:
            pass
    await show_settings(update, context)

async def reset_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
    lang = player.language
    keyboard = [
        [InlineKeyboardButton("✅ Yes" if lang=='en' else "✅ Да", callback_data='reset_yes'),
         InlineKeyboardButton("❌ No" if lang=='en' else "❌ Нет", callback_data='reset_no')]
    ]
    await query.edit_message_text(t(lang, 'confirm_delete'), reply_markup=InlineKeyboardMarkup(keyboard))

async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, confirm: bool):
    query = update.callback_query
    await query.answer()
    if confirm:
        db.delete_player(query.from_user.id)
        player_lang = 'ru'
        try:
            player_lang = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name).language
        except:
            pass
        await query.edit_message_text(t(player_lang, 'data_deleted'))
    else:
        await show_settings(update, context)


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает таблицу лидеров."""
    leaderboard_data = db.get_leaderboard()
    
    if not leaderboard_data:
        text = "Еще никто не нашел ни одного энергетика. Будь первым!"
        await update.message.reply_text(text)
        return

    text = "🏆 <b>Таблица лидеров по количеству энергетиков:</b>\n\n"
    
    medals = {0: '🥇', 1: '🥈', 2: '🥉'}
    
    for i, (user_id, username, total_drinks, vip_until) in enumerate(leaderboard_data):
        place = i + 1
        medal = medals.get(i, f" {place}.")
        # Экранируем имя пользователя для HTML
        safe_username = username.replace('<', '&lt;').replace('>', '&gt;')
        vip_badge = f" {VIP_EMOJI}" if (vip_until and int(time.time()) < int(vip_until)) else ""
        text += f"{medal} {safe_username}{vip_badge} - <b>{total_drinks} шт.</b>\n"

    await update.message.reply_html(text)


async def show_money_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает таблицу лидеров по деньгам."""
    money_leaderboard_data = db.get_money_leaderboard()
    
    if not money_leaderboard_data:
        text = "💰 Еще никто не накопил денег. Будь первым!"
        await update.message.reply_text(text)
        return

    text = "💰 <b>Таблица лидеров по деньгам:</b>\n\n"
    
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    
    for player_data in money_leaderboard_data:
        position = player_data['position']
        username = player_data['username']
        coins = player_data['coins']
        user_id = player_data['user_id']
        
        medal = medals.get(position, f" {position}.")
        # Экранируем имя пользователя для HTML
        safe_username = username.replace('<', '&lt;').replace('>', '&gt;')
        
        # Проверяем VIP статус
        vip_until = db.get_vip_until(user_id)
        vip_badge = f" {VIP_EMOJI}" if (vip_until and int(time.time()) < int(vip_until)) else ""
        
        text += f"{medal} {safe_username}{vip_badge} - <b>{coins:,} септимов</b>\n"

    await update.message.reply_html(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет справочное сообщение."""
    user = update.effective_user
    # Динамические кулдауны
    search_minutes = SEARCH_COOLDOWN // 60
    bonus_hours = DAILY_BONUS_COOLDOWN // 3600
    text = (
        f"👋 Привет, {user.mention_html()}!\n\n"
        "Я бот для коллекционирования энергетиков. Вот что доступно:\n\n"
        "<b>Главное меню:</b>\n"
        f"• 🔎 <b>Найти энергетик</b> — раз в {search_minutes} мин. можно испытать удачу и найти случайный энергетик.\n"
        f"• 🎁 <b>Ежедневный бонус</b> — раз в {bonus_hours} ч. гарантированный энергетик.\n"
        "• 📦 <b>Инвентарь</b> — все ваши найденные напитки (есть пагинация).\n"
        "• 🏙️ <b>Города</b> — выбор города (ХайТаун: Магазин, Приёмник, Плантация).\n"
        "• 📊 <b>Статистика</b> — личные показатели.\n"
        "• ⚙️ <b>Настройки</b> — выбор языка и сброс прогресса.\n\n"
        "<b>Команды:</b>\n"
        "/start — показать главное меню.\n"
        "/leaderboard — таблица лидеров по энергетикам.\n"
        "/moneyleaderboard — таблица лидеров по деньгам.\n"
        "/find — быстро найти энергетик (работает и в группах).\n"
        "/myreceipts — ваши последние чеки TG Premium.\n"
        "/myboosts — ваша история автопоиск бустов.\n"
        "/help — это сообщение.\n\n"
        "<b>Подсказки:</b>\n"
        "• Можно просто написать в чат \"<b>Найти энергетик</b>\", \"<b>Найди энергетик</b>\" или \"<b>Получить энергетик</b>\" — я всё пойму.\n"
        "• В группах можно дарить напитки друзьям: /gift @username (бот пришлёт выбор в личку)."
    )
    await update.message.reply_html(text, disable_web_page_preview=True)

async def myboosts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myboosts — показать историю бустов пользователя."""
    user = update.effective_user
    
    try:
        # Получаем историю бустов пользователя
        history = db.get_user_boost_history(user.id, limit=20)
        
        if not history:
            await update.message.reply_text("📋 У вас пока нет истории бустов автопоиска.")
            return
        
        # Формируем сообщение
        history_text = ["📋 <b>Ваша история бустов автопоиска:</b>\n"]
        
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
            current_chunk = "📋 <b>Ваша история бустов автопоиска:</b>\n"
            
            for line in history_text[1:]:  # пропускаем заголовок
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk)
                    current_chunk = "📋 <b>История бустов (продолжение):</b>\n" + line + "\n"
                else:
                    current_chunk += line + "\n"
            
            if current_chunk.strip():
                chunks.append(current_chunk)
            
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='HTML')
        else:
            await update.message.reply_text(full_text, parse_mode='HTML')
            
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении истории: {str(e)}")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для поиска энергетика."""
    msg = update.effective_message
    if not msg or not getattr(msg, 'text', None):
        return
    incoming = msg.text or ""
    normalized = "".join(ch for ch in incoming.lower() if ch.isalnum() or ch.isspace()).strip()
    # Поддержка вариантов ввода и пунктуации
    casino_triggers = {"найти казино", "найди казино", "casino"}
    if any(trigger in normalized for trigger in casino_triggers):
        await open_casino_from_text(update, context)
        return
    find_triggers = {"найти энергетик", "найди энергетик", "получить энергетик", "find energy", "получить по ебалу энергетиком"}
    if not any(trigger in normalized for trigger in find_triggers):
        return

    user = update.effective_user
    # Анти-даблклик для поиска из текста
    lock = _get_lock(f"user:{user.id}:search")
    if lock.locked():
        await msg.reply_text("Поиск уже выполняется…")
        return
    async with lock:
        # Предварительная проверка кулдауна (учёт VIP), чтобы не показывать спиннер впустую
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        now_ts = time.time()
        vip_active = db.is_vip(user.id)
        eff_search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
        if now_ts - player.last_search < eff_search_cd:
            time_left = eff_search_cd - (now_ts - player.last_search)
            await msg.reply_text(f"Ещё не время! Подожди немного (⏳ {int(time_left // 60)}:{int(time_left % 60):02d}).")
            return

        search_message = await msg.reply_text("⏳ Ищем энергетик…")

        result = await _perform_energy_search(user.id, user.username or user.first_name, context)

        if result["status"] == "no_drinks":
            try:
                await search_message.edit_text("В базе данных пока нет энергетиков!")
            except BadRequest:
                await msg.reply_text("В базе данных пока нет энергетиков!")
            return

        try:
            await search_message.delete()
        except BadRequest:
            pass

        if result["status"] == 'ok':
            if result["image_path"] and os.path.exists(result["image_path"]):
                with open(result["image_path"], 'rb') as photo:
                    await msg.reply_photo(
                        photo=photo,
                        caption=result["caption"],
                        reply_markup=result["reply_markup"],
                        parse_mode='HTML'
                    )
            else:
                await msg.reply_html(
                    text=result["caption"],
                    reply_markup=result["reply_markup"]
                )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /find для поиска энергетика (особенно полезна в группах)."""
    msg = update.effective_message
    if not msg:
        return
    user = update.effective_user
    # Анти-даблклик для команды /find
    lock = _get_lock(f"user:{user.id}:search")
    if lock.locked():
        await msg.reply_text("Поиск уже выполняется…")
        return
    async with lock:
        result = await _perform_energy_search(user.id, user.username or user.first_name, context)

    if result['status'] == 'cooldown':
        time_left = result["time_left"]
        await msg.reply_text(f"Ещё не время! Подожди немного (⏳ {int(time_left // 60)}:{int(time_left % 60):02d}).")
        return

    if result['status'] == 'no_drinks':
        await msg.reply_text("В базе данных пока нет энергетиков!")
        return

    if result["status"] == 'ok':
        if result["image_path"] and os.path.exists(result["image_path"]):
            with open(result["image_path"], 'rb') as photo:
                await msg.reply_photo(
                    photo=photo,
                    caption=result["caption"],
                    reply_markup=result["reply_markup"],
                    parse_mode='HTML'
                )
        else:
            await msg.reply_html(
                text=result["caption"],
                reply_markup=result["reply_markup"]
            )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/check <ID> — показывает, как выглядит энергетик: фото, название, описание."""
    # Регистрируем группу при использовании в группе (не мешает в ЛС)
    try:
        await register_group_if_needed(update)
    except Exception:
        pass

    msg = update.message
    user = update.effective_user
    # Доступ только для админов (уровни 1–3) и Создателя
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await msg.reply_text("Нет прав")
        return
    if not context.args:
        await msg.reply_text("Использование: /check <ID>")
        return
    try:
        drink_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("ID должен быть числом. Пример: /check 42")
        return

    drink = db.get_drink_by_id(drink_id)
    if not drink:
        await msg.reply_text("Энергетик с таким ID не найден.")
        return

    caption = (
        f"<b>{drink.name}</b>\n\n"
        f"<i>{drink.description}</i>"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]])

    image_full_path = os.path.join(ENERGY_IMAGES_DIR, drink.image_path) if drink.image_path else None
    if image_full_path and os.path.exists(image_full_path):
        try:
            with open(image_full_path, 'rb') as photo:
                await msg.reply_photo(photo=photo, caption=caption, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            # На случай проблем с файлом — отправим без фото
            await msg.reply_html(text=caption, reply_markup=keyboard)
    else:
        await msg.reply_html(text=caption, reply_markup=keyboard)


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/gift @username — инициирует дарение энергетика. Работает только в группах."""
    try:
        logger.info(
            "[GIFT] invoked: chat_id=%s type=%s user_id=%s args=%s",
            getattr(update.effective_chat, 'id', None),
            getattr(update.effective_chat, 'type', None),
            getattr(update.effective_user, 'id', None),
            context.args if hasattr(context, 'args') else None,
        )
    except Exception:
        pass
    await register_group_if_needed(update)
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Этой командой можно пользоваться только в группах.")
        return

    # Определяем получателя: приоритет — ответ на сообщение (reply), затем аргумент @username
    recipient_id = None
    recipient_username = None
    recipient_display = None

    reply = getattr(update.message, 'reply_to_message', None)
    if reply and getattr(reply, 'from_user', None):
        ruser = reply.from_user
        # Нельзя дарить сообщениям без пользователя (на всякий случай)
        if getattr(ruser, 'is_bot', False):
            await update.message.reply_text("Нельзя дарить ботам.")
            return
        recipient_id = ruser.id
        recipient_username = ruser.username or None
        # Отображаемое имя для подписи в группе (если нет username)
        display = getattr(ruser, 'full_name', None) or " ".join([n for n in [ruser.first_name, ruser.last_name] if n])
        recipient_display = f"@{recipient_username}" if recipient_username else (display or str(recipient_id))
    else:
        # Аргументы: пытаемся получить из context.args, а если пусто — распарсить из текста команды
        args = context.args if hasattr(context, 'args') else []
        if not args:
            try:
                raw = (getattr(update.message, 'text', None) or '').strip()
                m = re.match(r"^/gift(?:@\w+)?\s+(\S+)", raw, flags=re.IGNORECASE)
                if m:
                    args = [m.group(1)]
            except Exception:
                pass
        if not args:
            await update.message.reply_text("Использование: /gift @username\nЛибо ответьте на сообщение пользователя в группе и отправьте /gift")
            return
        recipient_username = args[0].lstrip("@").strip()
        recipient_display = f"@{recipient_username}"
    giver_id = update.effective_user.id

    # Безопасно читаем инвентарь дарителя
    try:
        inventory_items = db.get_player_inventory_with_details(giver_id)
    except Exception:
        logger.exception("[GIFT] Failed to fetch inventory for giver %s", giver_id)
        await update.message.reply_text("Ошибка при чтении инвентаря. Попробуйте позже.")
        return
    if not inventory_items:
        await update.message.reply_text("Ваш инвентарь пуст — нечего дарить.")
        return

    # Клавиатура выбора напитка
    keyboard_rows = []
    try:
        for item in inventory_items:
            drink_name = item.drink.name
            rarity = item.rarity
            quantity = item.quantity
            button_text = f"{drink_name} ({rarity}) x{quantity}"
            token = secrets.token_urlsafe(8)
            GIFT_SELECT_TOKENS[token] = {
                'group_id': update.effective_chat.id,
                'recipient_username': recipient_username or "",
                'recipient_id': recipient_id,
                'recipient_display': recipient_display,
                'item_id': item.id,
            }
            cb_data = f"selectgift2_{token}"
            keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=cb_data)])
    except Exception:
        logger.exception("[GIFT] Failed to build gift keyboard for giver %s", giver_id)
        await update.message.reply_text("Ошибка при формировании списка подарков. Попробуйте позже.")
        return

    # Пытаемся написать дарителю в личку. Если бот не может — сообщаем в группе, что нужно нажать Start.
    try:
        await context.bot.send_message(
            chat_id=giver_id,
            text="Выберите энергетик, который хотите подарить:",
            reply_markup=InlineKeyboardMarkup(keyboard_rows)
        )
        # Сообщаем в группе, что список отправлен в личку
        try:
            await update.message.reply_text("Отправил список вам в личные сообщения.")
        except Exception:
            pass
    except Forbidden:
        await update.message.reply_text(
            "Не могу написать вам в личку. Откройте чат с ботом и нажмите Start, после этого повторите команду."
        )
        return
    except Exception as e:
        logger.exception("[GIFT] Failed to send DM to giver %s: %s", giver_id, e)
        await update.message.reply_text("Не удалось отправить список в личные сообщения. Попробуйте позже.")
        return
    
    


async def handle_select_gift(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    query = update.callback_query
    await query.answer()

    giver_id = query.from_user.id

    group_id = payload.get('group_id')
    item_id = payload.get('item_id')
    recipient_username = (payload.get('recipient_username') or '').strip()
    recipient_id = payload.get('recipient_id')
    recipient_display = payload.get('recipient_display') or (f"@{recipient_username}" if recipient_username else None)

    # Проверяем что предмет у дарителя
    item = db.get_inventory_item(item_id)
    if not item or item.player_id != giver_id or item.quantity <= 0:
        await query.answer("Этот напиток недоступен.", show_alert=True)
        return

    global NEXT_GIFT_ID
    gift_id = NEXT_GIFT_ID
    NEXT_GIFT_ID += 1

    GIFT_OFFERS[gift_id] = {
        "giver_id": giver_id,
        "giver_name": query.from_user.username or query.from_user.first_name,
        "recipient_username": recipient_username,
        "recipient_id": recipient_id,
        "recipient_display": recipient_display,
        "item_id": item_id,
        "drink_id": item.drink.id,
        "drink_name": item.drink.name,
        "rarity": item.rarity,
        "group_id": group_id
    }

    # Сообщение в группу
    recip_text = GIFT_OFFERS[gift_id].get('recipient_display') or (f"@{recipient_username}" if recipient_username else "получателю")
    # Если нет @username, экранируем имя для HTML
    recip_html = recip_text if recip_text.startswith('@') else html.escape(str(recip_text))
    caption = (
        f"@{GIFT_OFFERS[gift_id]['giver_name']} хочет подарить {recip_html} напиток "
        f"<b>{html.escape(item.drink.name)}</b> ({html.escape(item.rarity)}). Принять?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data=f"giftresp_{gift_id}_yes"),
         InlineKeyboardButton("❌ Нет", callback_data=f"giftresp_{gift_id}_no")]
    ])

    await context.bot.send_message(
        chat_id=group_id,
        text=caption,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

    await query.edit_message_text("Подарок предложен! Ожидаем ответ.")


async def handle_gift_response(update: Update, context: ContextTypes.DEFAULT_TYPE, gift_id: int, accepted: bool):
    query = update.callback_query
    await query.answer()
    # Анти-даблклик: защита от двойного принятия одного и того же подарка
    lock = _get_lock(f"gift:{gift_id}")
    if lock.locked():
        await query.answer("Этот подарок уже обрабатывается…", show_alert=True)
        return
    async with lock:
        offer = GIFT_OFFERS.get(gift_id)
        if not offer:
            await query.answer("Предложение не найдено.", show_alert=True)
            return

    # Допускаем только указанного получателя: сперва по id, иначе по username
    rec_id = offer.get('recipient_id')
    rec_un = (offer.get('recipient_username') or '').lower()
    if rec_id:
        if query.from_user.id != rec_id:
            await query.answer("Это не вам предназначалось!", show_alert=True)
            return
    elif rec_un:
        if not query.from_user.username or query.from_user.username.lower() != rec_un:
            await query.answer("Это не вам предназначалось!", show_alert=True)
            return

    if not accepted:
        # Отклонено
        try:
            await query.edit_message_text("❌ Подарок отклонён.")
        except BadRequest:
            pass
        del GIFT_OFFERS[gift_id]
        return

    # Фикс: сначала фиксируем drink_id, затем списываем и зачисляем
    drink_id = offer.get('drink_id')
    if not drink_id:
        inv_item = db.get_inventory_item(offer['item_id'])
        drink_id = getattr(inv_item, 'drink_id', None) if inv_item else None
    if not drink_id:
        await query.edit_message_text("Не удалось определить напиток для передачи.")
        del GIFT_OFFERS[gift_id]
        return

    # Принятие: передаём предмет
    success = db.decrement_inventory_item(offer['item_id'])
    if not success:
        await query.edit_message_text("Не удалось передать подарок (предмет исчез).")
        del GIFT_OFFERS[gift_id]
        return

    # Добавляем получателю
    recipient_id = query.from_user.id
    db.add_drink_to_inventory(recipient_id, drink_id, offer['rarity'])
    # log
    logger.info(
        f"[GIFT] {offer['giver_name']} -> {query.from_user.username or query.from_user.id}: {offer['drink_name']} ({offer['rarity']})"
    )

    try:
        await query.edit_message_text("✅ Подарок принят!")
    except BadRequest:
        pass

    # Уведомления приватно
    await context.bot.send_message(chat_id=offer['giver_id'], text="Ваш подарок принят! 🎉")
    await context.bot.send_message(chat_id=recipient_id, text="Вы получили подарок! Загляните в инвентарь.")
    del GIFT_OFFERS[gift_id]


def main():
    """Запускает бота."""
    db.ensure_schema()
    # Инициализируем дефолтные типы семян для плантации (идемпотентно)
    try:
        db.ensure_default_seed_types()
    except Exception as e:
        logger.warning(f"[PLANTATION] Failed to ensure default seed types: {e}")
    # Инициализируем дефолтные удобрения для плантации (идемпотентно)
    try:
        db.ensure_default_fertilizers()
    except Exception as e:
        logger.warning(f"[PLANTATION] Failed to ensure default fertilizers: {e}")
    log_existing_drinks()
    
    # application = ApplicationBuilder().token(TOKEN).build()
    application = ApplicationBuilder().token(config.TOKEN).build()

    # Регистрируем обработчики
    # Диагностический логгер команд в группах (не блокирует выполнение)
    # Переносим в более позднюю группу, чтобы не влиять на срабатывание CommandHandler("gift", ...)
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.COMMAND, debug_log_commands), group=2)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("moneyleaderboard", show_money_leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myboosts", myboosts_command))
    application.add_handler(CommandHandler("fullhelp", fullhelp_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("admin2", admin2_command))
    application.add_handler(CommandHandler("requests", requests_command))
    application.add_handler(CommandHandler("delrequest", delrequest_command))
    application.add_handler(CommandHandler("editdrink", editdrink_command))
    application.add_handler(CommandHandler("incadd", incadd_command))
    application.add_handler(CommandHandler("inceditdrink", inceditdrink_command))
    application.add_handler(CommandHandler("incdelrequest", incdelrequest_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("addcoins", addcoins_command))
    application.add_handler(CommandHandler("delmoney", delmoney_command))
    application.add_handler(CommandHandler("myreceipts", myreceipts_command))
    application.add_handler(CommandHandler("receipt", receipt_command))
    application.add_handler(CommandHandler("verifyreceipt", verifyreceipt_command))
    application.add_handler(CommandHandler("tgstock", tgstock_command))
    application.add_handler(CommandHandler("tgadd", tgadd_command))
    application.add_handler(CommandHandler("tgset", tgset_command))
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("stockadd", stockadd_command))
    application.add_handler(CommandHandler("stockset", stockset_command))
    application.add_handler(CommandHandler("addvip", addvip_command))
    application.add_handler(CommandHandler("addautosearch", addautosearch_command))
    application.add_handler(CommandHandler("listboosts", listboosts_command))
    application.add_handler(CommandHandler("removeboost", removeboost_command))
    application.add_handler(CommandHandler("booststats", booststats_command))
    application.add_handler(CommandHandler("boosthistory", boosthistory_command))
    # Handler для добавления энергетиков
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), add_name)],
            ADD_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), add_description)],
            ADD_SPECIAL: [MessageHandler(filters.TEXT & (~filters.COMMAND), add_special)],
            ADD_PHOTO: [MessageHandler(filters.PHOTO, add_photo), CommandHandler("skip", skip_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )
    application.add_handler(add_conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    # ВАЖНО: перехватываем ответы на ForceReply с причиной отклонения до общего текстового обработчика
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, handle_reject_reason_reply, block=True), group=0)
    # Общий текстовый обработчик — после reply-хендлера
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler), group=1)
    # Регистрируем /gift раньше, чтобы исключить перехват другими обработчиками
    application.add_handler(CommandHandler("gift", gift_command))
    # Тихая регистрация групп по любым групповым сообщениям/командам
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, group_register_handler))
    application.add_handler(CommandHandler("find", find_command))
    application.add_handler(CommandHandler("check", check_command))
    
    # Логируем информацию о боте после старта (диагностика: верный ли бот запущен)
    async def _log_bot_info(context: ContextTypes.DEFAULT_TYPE):
        try:
            me = await context.bot.get_me()
            logger.info("[BOOT] Running as @%s (id=%s)", getattr(me, 'username', None), getattr(me, 'id', None))
        except Exception as e:
            logger.warning("[BOOT] Failed to get bot info: %s", e)

    # Периодическая проверка групп: отправляем не чаще 8 часов (ограничение внутри функции)
    async def notify_groups_job(context: ContextTypes.DEFAULT_TYPE):
        groups = db.get_enabled_group_chats()
        if not groups:
            return
        interval_sec = 8 * 60 * 60
        now_ts = int(time.time())
        for g in groups:
            try:
                # Пропускаем, если ещё не прошло 8 часов с последнего уведомления в этой группе
                last = int(getattr(g, 'last_notified', 0) or 0)
                if last and (now_ts - last) < interval_sec:
                    continue
                text = (
                    "⚠️ Напоминание: вы можете отправить свой энергетик на модерацию через команду /add в личке бота.\n"
                    "Придумайте название, описание и приложите фото — админы рассмотрят заявку!"
                )
                await context.bot.send_message(chat_id=g.chat_id, text=text)
                db.update_group_last_notified(g.chat_id)
                logger.info(f"[NOTIFY] Sent reminder to group {g.chat_id} ({getattr(g, 'title', None)})")
            except Exception as e:
                logger.warning(f"[NOTIFY] Failed to send to group {getattr(g, 'chat_id', '?')}: {e}")
                continue

    # Периодическая проверка истекающих бустов автопоиска
    async def boost_expiration_monitoring_job(context: ContextTypes.DEFAULT_TYPE):
        """Проверяет истекающие бусты и уведомляет пользователей и админов."""
        try:
            # Проверяем бусты, истекающие в следующие 2 часа
            expiring_boosts = db.get_expiring_boosts(hours_ahead=2)
            
            for player in expiring_boosts:
                try:
                    # Уведомляем пользователя
                    boost_info = db.get_boost_info(player.user_id)
                    if boost_info['is_active']:
                        remaining_time = boost_info['time_remaining_formatted']
                        username = f"@{player.username}" if player.username else f"ID: {player.user_id}"
                        
                        user_message = (
                            f"⏰ Внимание! Ваш автопоиск буст скоро истекает!\n"
                            f"🚀 Осталось: {remaining_time}\n"
                            f"📊 Дополнительные поиски: +{boost_info['boost_count']}"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=player.user_id,
                                text=user_message
                            )
                            logger.info(f"[BOOST_MONITOR] Sent expiration warning to {username}")
                        except Exception as e:
                            logger.warning(f"[BOOST_MONITOR] Failed to notify user {username}: {e}")
                        
                        # Уведомляем админов о скором истечении
                        admin_ids = db.get_admin_user_ids()
                        admin_message = (
                            f"⏰ Буст автопоиска у {username} истекает!\n"
                            f"🚀 Буст: +{boost_info['boost_count']} поисков\n"
                            f"⏱ Осталось: {remaining_time}\n"
                            f"📅 Истекает: {boost_info['boost_until_formatted']}"
                        )
                        
                        for admin_id in admin_ids:
                            try:
                                await context.bot.send_message(
                                    chat_id=admin_id,
                                    text=admin_message
                                )
                            except Exception as e:
                                logger.warning(f"[BOOST_MONITOR] Failed to notify admin {admin_id}: {e}")
                                
                except Exception as e:
                    logger.warning(f"[BOOST_MONITOR] Error processing player {player.user_id}: {e}")
                    continue
            
            # Проверяем и убираем истёкшие бусты (с нулевой задержкой)
            expired_boosts = db.get_expiring_boosts(hours_ahead=0)
            for player in expired_boosts:
                try:
                    # Проверяем, что буст действительно истёк
                    boost_info = db.get_boost_info(player.user_id)
                    if not boost_info['is_active'] and boost_info['boost_count'] > 0:
                        # Сохраняем информацию о бусте для истории
                        expired_boost_count = boost_info['boost_count']
                        
                        # Убираем истёкший буст
                        db.remove_auto_search_boost(player.user_id)
                        
                        # Добавляем запись в историю об истечении
                        try:
                            db.add_boost_history_record(
                                user_id=player.user_id,
                                username=player.username,
                                action='expired',
                                boost_count=expired_boost_count,
                                details=f"Автоматически убран по истечении срока"
                            )
                        except Exception as e:
                            logger.warning(f"[BOOST_HISTORY] Failed to record boost expiration for {username}: {e}")
                        
                        username = f"@{player.username}" if player.username else f"ID: {player.user_id}"
                        
                        # Уведомляем пользователя об истечении
                        user_message = (
                            f"⏱ Ваш автопоиск буст истёк!\n"
                            f"🚀 Было: +{boost_info['boost_count']} дополнительных поисков\n"
                            f"📊 Теперь дневной лимит: {db.get_auto_search_daily_limit(player.user_id)}"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=player.user_id,
                                text=user_message
                            )
                            logger.info(f"[BOOST_MONITOR] Notified {username} about boost expiration")
                        except Exception as e:
                            logger.warning(f"[BOOST_MONITOR] Failed to notify user {username} about expiration: {e}")
                        
                        # Уведомляем админов об истечении
                        admin_ids = db.get_admin_user_ids()
                        admin_message = (
                            f"⏱ Буст автопоиска у {username} истёк!\n"
                            f"🚀 Было: +{boost_info['boost_count']} поисков\n"
                            f"📊 Новый лимит: {db.get_auto_search_daily_limit(player.user_id)}"
                        )
                        
                        for admin_id in admin_ids:
                            try:
                                await context.bot.send_message(
                                    chat_id=admin_id,
                                    text=admin_message
                                )
                            except Exception as e:
                                logger.warning(f"[BOOST_MONITOR] Failed to notify admin {admin_id} about expiration: {e}")
                                
                except Exception as e:
                    logger.warning(f"[BOOST_MONITOR] Error processing expired boost for player {player.user_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.exception(f"[BOOST_MONITOR] Error in boost monitoring job: {e}")

    if application.job_queue:
        # лог бота через 2 сек после старта
        application.job_queue.run_once(_log_bot_info, when=2)
        # Запускаем каждые 15 минут; сам лимит 8 часов контролируется внутри notify_groups_job по last_notified
        scheduler_interval = 15 * 60
        first_delay = 60  # минимум 60 сек, чтобы избежать гонок старта
        application.job_queue.run_repeating(notify_groups_job, interval=scheduler_interval, first=first_delay)
        
        # Мониторинг истекающих бустов автопоиска (каждые 30 минут)
        boost_monitor_interval = 30 * 60  # 30 минут
        boost_monitor_delay = 120  # начинаем через 2 минуты после старта
        application.job_queue.run_repeating(boost_expiration_monitoring_job, interval=boost_monitor_interval, first=boost_monitor_delay)
        
        # Мониторинг плантаций шёлка (каждые 5 минут)
        silk_monitor_interval = 5 * 60  # 5 минут
        silk_monitor_delay = 45  # начинаем через 45 секунд после старта
        application.job_queue.run_repeating(silk_harvest_reminder_job, interval=silk_monitor_interval, first=silk_monitor_delay)

        # --- Восстановление задач автопоиска VIP после рестарта ---
        try:
            players = db.get_players_with_auto_search_enabled()
        except Exception as e:
            players = []
            logger.warning(f"[AUTO] Не удалось получить список игроков для восстановления автопоиска: {e}")

        if players:
            restored = 0
            for idx, p in enumerate(players):
                try:
                    user_id = getattr(p, 'user_id', None)
                    if not user_id:
                        continue
                    # Отключим автопоиск, если VIP уже не активен
                    if not db.is_vip(user_id):
                        try:
                            db.update_player(user_id, auto_search_enabled=False)
                        except Exception:
                            pass
                        continue
                    # Рассчитываем задержку первого запуска с учётом кулдауна (для VIP)
                    vip_active = True
                    eff_search_cd = SEARCH_COOLDOWN / 2 if vip_active else SEARCH_COOLDOWN
                    last_search_ts = float(getattr(p, 'last_search', 0) or 0.0)
                    time_since_last = max(0.0, time.time() - last_search_ts)
                    delay = eff_search_cd - time_since_last
                    # Минимальная задержка и рассев по индексу, чтобы не запускать всё разом
                    base_stagger = 5.0 + float(idx % 10)
                    when_delay = max(base_stagger, delay, 1.0)
                    try:
                        application.job_queue.run_once(
                            auto_search_job,
                            when=when_delay,
                            chat_id=user_id,
                            name=f"auto_search_{user_id}",
                        )
                        restored += 1
                    except Exception as e:
                        logger.warning(f"[AUTO] Не удалось восстановить задачу автопоиска для {user_id}: {e}")
                except Exception:
                    logger.exception("[AUTO] Ошибка при попытке восстановить автопоиск пользователя")
                    continue
            if restored:
                logger.info(f"[AUTO] Восстановлено задач автопоиска: {restored}")

    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()