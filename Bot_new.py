# file: Bot_new.py

import os
import logging
import random
import time
import asyncio
import json
import secrets
import html
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ForceReply, Message, User, InputMediaPhoto
from telegram.error import BadRequest, Forbidden, RetryAfter, TimedOut, NetworkError
from telegram.request import HTTPXRequest
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
from database import SessionLocal, Player
from sqlalchemy import func
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
    setrareemoji_command,
    listrareemoji_command,
    addvip_command,
    addautosearch_command,
    listboosts_command,
    removeboost_command,
    booststats_command,
    boosthistory_command,
    addexdrink_start,
    addexdrink_photo,
    addexdrink_skip,
    addexdrink_cancel,
    giveexdrink_command,
)
from vip_plus_handlers import (
    show_vip_plus_menu,
    show_vip_plus_1d,
    show_vip_plus_7d,
    show_vip_plus_30d,
    buy_vip_plus,
    confirm_vip_plus_purchase,
    toggle_auto_search_silent,
)
from constants import (
    SEARCH_COOLDOWN,
    DAILY_BONUS_COOLDOWN,
    ENERGY_IMAGES_DIR,
    DAILY_BONUS_REWARDS,
    RARITIES,
    COLOR_EMOJIS,
    RARITY_ORDER,
    ITEMS_PER_PAGE,
    FAVORITE_DRINK_WEIGHT_MULT,
    VIP_EMOJI,
    VIP_COSTS,
    VIP_DURATIONS_SEC,
    VIP_PLUS_EMOJI,
    VIP_PLUS_COSTS,
    VIP_PLUS_DURATIONS_SEC,
    TG_PREMIUM_COST,
    TG_PREMIUM_DURATION_SEC,
    ADMIN_USERNAMES,
    AUTO_SEARCH_DAILY_LIMIT,
    CASINO_WIN_PROB,
    CASINO_MAX_BET,
    CASINO_MIN_BET,
    CASINO_GAMES,
    SLOT_SYMBOLS,
    SLOT_PAYOUTS,
    CASINO_ANIMATIONS,
    CASINO_ACHIEVEMENTS,
    RECEIVER_PRICES,
    RECEIVER_COMMISSION,
    SHOP_PRICES,
    SILK_EMOJIS,
    BLACKJACK_SUITS,
    BLACKJACK_RANKS,
    BLACKJACK_VALUES,
    BLACKJACK_MULTIPLIER,
    BLACKJACK_BJ_MULTIPLIER,
    MINES_GRID_SIZE,
    MINES_MIN_COUNT,
    MINES_MAX_COUNT,
    MINES_DEFAULT_COUNT,
    CRASH_UPDATE_INTERVAL,
    CRASH_GROWTH_RATE,
    CRASH_MAX_MULTIPLIER,
    PLANTATION_FERTILIZER_MAX_PER_BED,
    PLANTATION_NEG_EVENT_INTERVAL_SEC,
    PLANTATION_NEG_EVENT_CHANCE,
    PLANTATION_NEG_EVENT_MAX_ACTIVE,
    PLANTATION_NEG_EVENT_DURATION_SEC,
)
import silk_ui
import swagashop
import swaga_admin
from admin_permissions import (
    get_effective_admin_level,
    has_admin_level,
    has_admin_panel_access,
    has_creator_panel_access,
    get_required_level_for_callback,
    ADMIN_TEXT_ACTION_LEVELS,
    CREATOR_TEXT_ACTION_LEVELS,
)
# --- Настройки ---
# Константы импортируются из constants.py

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def _tg_call_with_retry(call, *, retries=3, base_delay=1.5, **kwargs):
    last_exc = None
    for attempt in range(int(retries)):
        try:
            return await call(**kwargs)
        except RetryAfter as e:
            last_exc = e
            delay = float(getattr(e, 'retry_after', 1.0) or 1.0)
            await asyncio.sleep(max(0.0, delay))
        except (TimedOut, NetworkError, OSError) as e:
            last_exc = e
            if attempt >= int(retries) - 1:
                break
            await asyncio.sleep(float(base_delay) * (2 ** attempt))
        except Exception as e:
            last_exc = e
            break
    if last_exc:
        raise last_exc


async def _send_photo_long(call, **kwargs):
    kwargs.setdefault('read_timeout', 60.0)
    kwargs.setdefault('write_timeout', 60.0)
    kwargs.setdefault('connect_timeout', 20.0)
    kwargs.setdefault('pool_timeout', 20.0)
    return await _tg_call_with_retry(call, retries=3, base_delay=1.5, **kwargs)


async def _send_media_group_long(call, **kwargs):
    kwargs.setdefault('read_timeout', 60.0)
    kwargs.setdefault('write_timeout', 60.0)
    kwargs.setdefault('connect_timeout', 20.0)
    kwargs.setdefault('pool_timeout', 20.0)
    return await _tg_call_with_retry(call, retries=3, base_delay=1.5, **kwargs)

def safe_format_timestamp(timestamp, format_str='%d.%m.%Y %H:%M'):
    """Безопасное форматирование временной метки."""
    if not timestamp:
        return None
    try:
        # Проверяем что таймстамп в разумных пределах
        if timestamp < 0 or timestamp > 4102444800:  # максимум до 2100 года
            return None
        return time.strftime(format_str, time.localtime(timestamp))
    except (OSError, ValueError, OverflowError) as e:
        logger.warning(f"Invalid timestamp {timestamp}: {e}")
        return None

def create_progress_bar(percent: float, length: int = 10, filled: str = '█', empty: str = '░') -> str:
    """Создает визуальный прогресс-бар."""
    if percent < 0:
        percent = 0
    elif percent > 100:
        percent = 100
    
    filled_length = int(length * percent / 100)
    empty_length = length - filled_length
    
    return filled * filled_length + empty * empty_length

# --- Константы ---
# см. constants.py

# --- VIP настройки ---
# см. constants.py

# --- TG Premium настройки ---
# Стоимость (в септимах) и длительность (в секундах) для 3 месяцев
# (импортируются из constants.py)

# ADMIN_USERNAMES импортируется из constants.py
ADMIN_USER_IDS: set[int] = set()  # legacy, больше не используется для прав, оставлено для обратной совместимости

ADD_NAME, ADD_DESCRIPTION, ADD_SPECIAL, ADD_PHOTO, ADDP_NAME, ADDP_DESCRIPTION, ADDP_PHOTO, ADDEX_PHOTO = range(8)

# Константы для conversation handler казино
CASINO_CUSTOM_BET = range(1)

# Константы для conversation handler удобрений
FERTILIZER_CUSTOM_QTY = range(1)
SEED_CUSTOM_QTY = range(1)

PENDING_ADDITIONS: dict[int, dict] = {}
NEXT_PENDING_ID = 1

GIFT_OFFERS: dict[int, dict] = {}
NEXT_GIFT_ID = 1
GIFT_SELECT_TOKENS: dict[str, dict] = {}
GIFT_SELECTION_STATE: dict[int, dict] = {}  # {user_id: {recipient_info, inventory_items}}

# --- Блокировки для предотвращения даблкликов/гонок ---
_LOCKS: Dict[str, asyncio.Lock] = {}

# --- Ожидание причины отклонения (ключ = (chat_id, prompt_message_id)) ---
REJECT_PROMPTS: Dict[tuple[int, int], dict] = {}

# --- Система автоудаления сообщений для групп (ключ = message_id) ---
AUTO_DELETE_MESSAGES: Dict[str, dict] = {}

def _get_lock(key: str) -> asyncio.Lock:
    lock = _LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[key] = lock
    return lock

# --- Магазин: кэш предложений на пользователя ---
# SHOP_OFFERS[user_id] = { 'offers': [ {idx, drink_id, drink_name, rarity} ], 'ts': int }
SHOP_OFFERS: Dict[int, dict] = {}

# --- Блэкджек: активные игры ---
# BLACKJACK_GAMES[user_id] = { 'bet': int, 'player_hand': list, 'dealer_hand': list, 'deck': list, 'status': str }
BLACKJACK_GAMES: Dict[int, dict] = {}

# --- Мины: активные игры ---
# MINES_GAMES[user_id] = { 'bet': int, 'mines_count': int, 'grid': list, 'revealed': set, 'status': str, 'multiplier': float }
MINES_GAMES: Dict[int, dict] = {}

# --- Краш: активные игры ---
# CRASH_GAMES[user_id] = { 'bet': int, 'multiplier': float, 'crash_point': float, 'status': str, 'task': asyncio.Task }
CRASH_GAMES: Dict[int, dict] = {}

TEXTS = {
    'menu_title': {
        'ru': '⚡ <b>Добро пожаловать, {user}!</b>\n\n'
              '💰 <b>Баланс:</b> {coins} септимов\n'
              '🔋 <b>Энергетиков:</b> {energy_count}\n'
              '⭐ <b>Рейтинг:</b> {rating}\n'
              '{vip_status}\n'
              '━━━━━━━━━━━━━━━━\n'
              '<i>Выберите действие:</i>',
        'en': '⚡ <b>Welcome, {user}!</b>\n\n'
              '💰 <b>Balance:</b> {coins} septims\n'
              '🔋 <b>Energy drinks:</b> {energy_count}\n'
              '⭐ <b>Rating:</b> {rating}\n'
              '{vip_status}\n'
              '━━━━━━━━━━━━━━━━\n'
              '<i>Choose an action:</i>'
    },
    'search': {'ru': '🔎 Найти энергетик', 'en': '🔎 Find energy'},
    'inventory': {'ru': '📦 Инвентарь', 'en': '📦 Inventory'},
    'stats': {'ru': '📊 Статистика', 'en': '📊 Stats'},
    'my_profile': {'ru': '👤 Мой профиль', 'en': '👤 My profile'},
    'favorite_energy_drinks': {'ru': '⭐ Избранные энергетики', 'en': '⭐ Favorite Energy Drinks'},
    'favorites_title': {'ru': '<b>⭐ Избранные энергетики</b>', 'en': '<b>⭐ Favorite Energy Drinks</b>'},
    'favorites_slot': {'ru': 'Слот {n}: {value}', 'en': 'Slot {n}: {value}'},
    'favorites_empty': {'ru': 'Пусто', 'en': 'Empty'},
    'favorites_pick_title': {'ru': '<b>⭐ Выбор избранного — слот {n}</b>', 'en': '<b>⭐ Pick favorite — slot {n}</b>'},
    'favorites_pick_empty_inventory': {'ru': '❌ Инвентарь пуст. Нечего добавить в избранное.', 'en': '❌ Inventory is empty. Nothing to add to favorites.'},
    'favorites_back_profile': {'ru': '🔙 Назад', 'en': '🔙 Back'},
    'settings': {'ru': '⚙️ Настройки', 'en': '⚙️ Settings'},
    # --- Settings menu ---
    'settings_title': {'ru': '⚙️ Настройки', 'en': '⚙️ Settings'},
    'current_language': {'ru': '🌐 Язык', 'en': '🌐 Language'},
    'auto_reminder': {'ru': '⏰ Автонапоминание', 'en': '⏰ Auto-reminder'},
    'plantation_reminder': {'ru': '💧 Напоминание о поливе', 'en': '💧 Watering reminder'},
    'on': {'ru': 'Вкл', 'en': 'On'},
    'off': {'ru': 'Выкл', 'en': 'Off'},
    'btn_change_lang': {'ru': '🌐 Изменить язык', 'en': '🌐 Change language'},
    'btn_toggle_rem': {'ru': '⏰ Переключить напоминание', 'en': '⏰ Toggle reminder'},
    'btn_toggle_plantation_rem': {'ru': '💧 Переключить напоминание о поливе', 'en': '💧 Toggle watering reminder'},
    'auto_search': {'ru': '🤖 Автопоиск VIP', 'en': '🤖 VIP Auto-search'},
    'btn_toggle_auto': {'ru': '🤖 Переключить автопоиск VIP', 'en': '🤖 Toggle VIP auto-search'},
    'auto_requires_vip': {'ru': 'Эта функция доступна только с активным V.I.P.', 'en': 'This feature requires an active V.I.P.'},
    'auto_enabled': {'ru': 'Автопоиск включён. Лимит: {limit}/сутки.', 'en': 'Auto-search enabled. Limit: {limit}/day.'},
    'auto_disabled': {'ru': 'Автопоиск выключен.', 'en': 'Auto-search disabled.'},
    'auto_limit_reached': {'ru': 'Дневной лимит автопоиска исчерпан. Автопоиск отключён до сброса.', 'en': 'Daily auto-search limit reached. Auto-search disabled until reset.'},
    'auto_vip_expired': {'ru': 'Срок V.I.P. истёк. Автопоиск отключён.', 'en': 'V.I.P. expired. Auto-search has been disabled.'},
    'autosell': {'ru': '🧾 Автопродажа', 'en': '🧾 Auto-sell'},
    'autosell_title': {'ru': '🧾 Автопродажа энергетиков', 'en': '🧾 Auto-sell energy drinks'},
    'autosell_desc': {
        'ru': 'Выберите, какие редкости продавать автоматически сразу после нахождения. Энергетик не попадёт в инвентарь, а сразу будет продан по цене Приёмника.',
        'en': 'Choose which rarities to auto-sell immediately after search. The drink will not go to inventory, it will be sold at Receiver price.'
    },
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
    # --- VIP+ submenu ---
    'vip_plus': {'ru': VIP_PLUS_EMOJI + ' V.I.P+', 'en': VIP_PLUS_EMOJI + ' V.I.P+'},
    'vip_plus_title': {
        'ru': 'Выберите срок V.I.P+:\n\nПреимущества:\n• 💎 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.25 (в 4 раза быстрее!)\n• 🎁 Кулдаун ежедневного бонуса — x0.25 (в 4 раза быстрее!)\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n• 🚀 Автопоиск: x2 к дневному лимиту',
        'en': 'Choose V.I.P+ duration:\n\nPerks:\n• 💎 Badge in the leaderboard\n• ⏱ Search cooldown — x0.25 (4x faster!)\n• 🎁 Daily bonus cooldown — x0.25 (4x faster!)\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n• 🚀 Auto-search: x2 daily limit'
    },
    'vip_plus_1d': {'ru': '1 День', 'en': '1 Day'},
    'vip_plus_7d': {'ru': '7 дней', 'en': '7 days'},
    'vip_plus_30d': {'ru': '30 дней', 'en': '30 days'},
    'vip_plus_details_1d': {
        'ru': '<b>V.I.P+ на 1 день</b>\n\nПреимущества:\n• 💎 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.25 (в 4 раза быстрее!)\n• 🎁 Кулдаун ежедневного бонуса — x0.25 (в 4 раза быстрее!)\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n• 🚀 Автопоиск: x2 к дневному лимиту\n',
        'en': '<b>V.I.P+ for 1 day</b>\n\nPerks:\n• 💎 Badge in the leaderboard\n• ⏱ Search cooldown — x0.25 (4x faster!)\n• 🎁 Daily bonus cooldown — x0.25 (4x faster!)\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n• 🚀 Auto-search: x2 daily limit\n'
    },
    'vip_plus_details_7d': {
        'ru': '<b>V.I.P+ на 7 дней</b>\n\nПреимущества:\n• 💎 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.25 (в 4 раза быстрее!)\n• 🎁 Кулдаун ежедневного бонуса — x0.25 (в 4 раза быстрее!)\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n• 🚀 Автопоиск: x2 к дневному лимиту\n',
        'en': '<b>V.I.P+ for 7 days</b>\n\nPerks:\n• 💎 Badge in the leaderboard\n• ⏱ Search cooldown — x0.25 (4x faster!)\n• 🎁 Daily bonus cooldown — x0.25 (4x faster!)\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n• 🚀 Auto-search: x2 daily limit\n'
    },
    'vip_plus_details_30d': {
        'ru': '<b>V.I.P+ на 30 дней</b>\n\nПреимущества:\n• 💎 Значок в таблице лидеров\n• ⏱ Кулдаун поиска — x0.25 (в 4 раза быстрее!)\n• 🎁 Кулдаун ежедневного бонуса — x0.25 (в 4 раза быстрее!)\n• 💰 Награда монет за поиск — x2\n• 🔔 Напоминание о поиске срабатывает по сокращённому КД\n• 🚀 Автопоиск: x2 к дневному лимиту\n',
        'en': '<b>V.I.P+ for 30 days</b>\n\nPerks:\n• 💎 Badge in the leaderboard\n• ⏱ Search cooldown — x0.25 (4x faster!)\n• 🎁 Daily bonus cooldown — x0.25 (4x faster!)\n• 💰 Coin reward from search — x2\n• 🔔 Search reminder respects reduced cooldown\n• 🚀 Auto-search: x2 daily limit\n'
    },
    'vip_plus_buy': {'ru': 'Купить', 'en': 'Buy'},
    'vip_plus_price': {'ru': 'Цена: {cost} септимов', 'en': 'Price: {cost} septims'},
    'vip_plus_until': {'ru': 'V.I.P+ активен до: {dt}', 'en': 'V.I.P+ active until: {dt}'},
    'vip_plus_not_enough': {'ru': 'Недостаточно монет.', 'en': 'Not enough coins.'},
    'vip_plus_bought': {'ru': 'Покупка успешна! {emoji} До: {dt}\nБаланс: {coins}', 'en': 'Purchased! {emoji} Until: {dt}\nBalance: {coins}'},
    'vip_plus_insufficient': {
        'ru': '❗ Недостаточно монет: {coins}/{cost}',
        'en': '❗ Not enough coins: {coins}/{cost}'
    },
    # --- Stars submenu ---
    'stars': {'ru': '⭐ Звезды', 'en': '⭐ Stars'},
    'stars_title': {'ru': 'Выберите пакет звёзд:', 'en': 'Choose a stars pack:'},
    'stars_500': {'ru': '500 звёзд', 'en': '500 stars'},
    'stars_details_500': {
        'ru': '<b>Пакет 500 звёзд</b>\n\nДоступно при наличии на складе. Вы можете приобрести пакет, если он в наличии.',
        'en': '<b>Pack of 500 stars</b>\n\nAvailable while in stock. You can purchase when it is in stock.'
    },
    # --- Групповые настройки ---
    'group_settings_title': {
        'ru': '⚙️ Настройки группы',
        'en': '⚙️ Group Settings'
    },
    'group_settings_desc': {
        'ru': 'Настройки доступны только создателям групп.',
        'en': 'Settings are only available to group creators.'
    },
    'group_notifications': {
        'ru': '🔔 Уведомления',
        'en': '🔔 Notifications'
    },
    'group_auto_delete': {
        'ru': '🗑️ Автоудаление сообщений',
        'en': '🗑️ Auto-delete messages'
    },
    'btn_toggle_notifications': {
        'ru': '🔔 Переключить уведомления',
        'en': '🔔 Toggle notifications'
    },
    'btn_toggle_auto_delete': {
        'ru': '🗑️ Переключить автоудаление',
        'en': '🗑️ Toggle auto-delete'
    },
    'notifications_enabled': {
        'ru': '✅ Уведомления включены',
        'en': '✅ Notifications enabled'
    },
    'notifications_disabled': {
        'ru': '❌ Уведомления отключены',
        'en': '❌ Notifications disabled'
    },
    'auto_delete_enabled': {
        'ru': '✅ Автоудаление включено (5 мин)',
        'en': '✅ Auto-delete enabled (5 min)'
    },
    'auto_delete_disabled': {
        'ru': '❌ Автоудаление отключено',
        'en': '❌ Auto-delete disabled'
    },
    'group_access_denied': {
        'ru': '❌ Нет прав доступа. Только создатели групп могут изменять настройки.',
        'en': '❌ Access denied. Only group creators can change settings.'
    },
    'group_only_command': {
        'ru': '❌ Эта команда доступна только в группах.',
        'en': '❌ This command is only available in groups.'
    }
}

def t(lang: str, key: str) -> str:
    return TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get('ru', key))

def _rating_bonus_percent(rating_value: int, max_bonus: float) -> float:
    try:
        r = int(rating_value or 0)
    except Exception:
        r = 0
    r = max(0, min(1000, r))
    try:
        mb = float(max_bonus or 0.0)
    except Exception:
        mb = 0.0
    mb = max(0.0, mb)
    return mb * (r / 1000.0)

def _rarity_weights_with_rating(base_weights: dict, rating_value: int, max_bonus: float) -> dict:
    bonus = _rating_bonus_percent(rating_value, max_bonus)
    order = ['Basic', 'Medium', 'Elite', 'Absolute', 'Majestic']
    out = {}
    for k, v in (base_weights or {}).items():
        try:
            out[str(k)] = float(v)
        except Exception:
            out[str(k)] = 0.0
    for i, rk in enumerate(order):
        if rk not in out:
            continue
        w = float(out.get(rk, 0.0) or 0.0)
        if rk == 'Basic':
            factor = max(0.05, 1.0 - bonus)
        else:
            denom = max(1, (len(order) - 1))
            tier = i / float(denom)
            factor = 1.0 + (bonus * tier)
        out[rk] = max(0.0, w * factor)
    if sum(v for v in out.values() if v > 0) <= 0:
        out = {'Basic': 1.0}
    return out

def _daily_bonus_weights_with_rating(rewards: dict, rating_value: int, max_bonus: float) -> dict:
    bonus = _rating_bonus_percent(rating_value, max_bonus)
    out = {}
    weights_only = {}
    for k, info in (rewards or {}).items():
        try:
            w = float((info or {}).get('weight', 0) or 0)
        except Exception:
            w = 0.0
        weights_only[str(k)] = max(0.0, w)
    non_coins = {k: w for k, w in weights_only.items() if k != 'coins'}
    max_non_coins = max(non_coins.values()) if non_coins else 0.0
    for k, w in weights_only.items():
        if k == 'coins':
            factor = max(0.05, 1.0 - bonus)
        else:
            if max_non_coins > 0:
                rarity_score = 1.0 - min(1.0, (w / max_non_coins))
            else:
                rarity_score = 1.0
            factor = 1.0 + (bonus * rarity_score)
        out[k] = max(0.0, float(w) * float(factor))
    if sum(v for v in out.values() if v > 0) <= 0:
        out = {'coins': 1.0}
    return out

# --- Функции-обработчики для кнопок ---

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню. УМЕЕТ ОБРАБАТЫВАТЬ ВОЗВРАТ С ФОТО."""
    user = update.effective_user
    player = db.get_or_create_player(user.id, username=getattr(user, 'username', None), display_name=(getattr(user, 'full_name', None) or getattr(user, 'first_name', None)))

    # Проверка кулдауна поиска (VIP+ — x0.25, VIP — x0.5)
    vip_plus_active = db.is_vip_plus(user.id)
    vip_active = db.is_vip(user.id)
    
    base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
    if vip_plus_active:
        search_cd = base_search_cd / 4  # x0.25 для VIP+
    elif vip_active:
        search_cd = base_search_cd / 2  # x0.5 для VIP
    else:
        search_cd = base_search_cd       # x1.0 для обычных
    last_search_val = float(getattr(player, 'last_search', 0) or 0)
    search_time_left = max(0, search_cd - (time.time() - last_search_val))
    lang = getattr(player, 'language', 'ru') or 'ru'

    base_search = t(lang, 'search')
    if search_time_left > 0:
        search_status = f"{base_search} (⏳ {int(search_time_left // 60)}:{int(search_time_left % 60):02d})"
    else:
        search_status = f"{base_search} ✅"

    # Проверка кулдауна ежедневного бонуса (VIP+ — x4 скорость, VIP — x2 скорость)
    base_bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
    if vip_plus_active:
        bonus_cd = base_bonus_cd / 4
    elif vip_active:
        bonus_cd = base_bonus_cd / 2
    else:
        bonus_cd = base_bonus_cd
    last_bonus_claim_val = float(getattr(player, 'last_bonus_claim', 0) or 0)
    bonus_time_left = max(0, bonus_cd - (time.time() - last_bonus_claim_val))
    base_bonus = t(lang, 'daily_bonus')
    if bonus_time_left > 0:
        hours, remainder = divmod(int(bonus_time_left), 3600)
        minutes, seconds = divmod(remainder, 60)
        bonus_status = f"{base_bonus} (⏳ {hours:02d}:{minutes:02d}:{seconds:02d})"
    else:
        bonus_status = f"{base_bonus} ✅"

    # Формируем текст статуса VIP
    vip_status_text = ""
    if vip_plus_active:
        vip_plus_until_val = int(getattr(player, 'vip_plus_until', 0) or 0)
        vip_until = safe_format_timestamp(vip_plus_until_val, '%d.%m.%Y %H:%M')
        if lang == 'ru':
            vip_status_text = f"💎 <b>Статус:</b> {VIP_PLUS_EMOJI} V.I.P+ (до {vip_until})"
        else:
            vip_status_text = f"💎 <b>Status:</b> {VIP_PLUS_EMOJI} V.I.P+ (until {vip_until})"
    elif vip_active:
        vip_until_val = int(getattr(player, 'vip_until', 0) or 0)
        vip_until = safe_format_timestamp(vip_until_val, '%d.%m.%Y %H:%M')
        if lang == 'ru':
            vip_status_text = f"👑 <b>Статус:</b> {VIP_EMOJI} V.I.P (до {vip_until})"
        else:
            vip_status_text = f"👑 <b>Status:</b> {VIP_EMOJI} V.I.P (until {vip_until})"
    else:
        if lang == 'ru':
            vip_status_text = "📊 <b>Статус:</b> Обычный игрок"
        else:
            vip_status_text = "📊 <b>Status:</b> Regular player"

    # Получаем количество энергетиков в инвентаре
    energy_count = len(db.get_player_inventory_with_details(user.id))

    # Улучшенная структура кнопок
    bonus_info_label = "ℹ️ Инфо" if lang != 'en' else "ℹ️ Info"
    keyboard = [
        # Основные действия
        [InlineKeyboardButton(search_status, callback_data='find_energy')],
        [
            InlineKeyboardButton(bonus_status, callback_data='claim_bonus'),
            InlineKeyboardButton(bonus_info_label, callback_data='daily_bonus_info'),
        ],
        # Бонусы и города в одной строке
        [
            InlineKeyboardButton("🎁 Бонусы", callback_data='extra_bonuses'),
            InlineKeyboardButton("🏙️ Города", callback_data='cities_menu')
        ],
        # Профиль в одной строке
        [
            InlineKeyboardButton(t(lang, 'inventory'), callback_data='inventory'),
            InlineKeyboardButton(t(lang, 'my_profile'), callback_data='my_profile')
        ],
        [InlineKeyboardButton("🛒 Свага Шоп", callback_data='swaga_shop')],
        [InlineKeyboardButton("🎟 Промокод", callback_data='promo_enter')],
        # Настройки
        [InlineKeyboardButton(t(lang, 'settings'), callback_data='settings')],
    ]
    
    # Добавляем кнопку "Админ панель" для всех админ-уровней и Создателя
    if has_admin_panel_access(user.id, user.username):
        keyboard.append([InlineKeyboardButton("⚙️ Админ панель", callback_data='creator_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    menu_text = t(lang, 'menu_title').format(
        user=user.mention_html(),
        coins=player.coins,
        energy_count=energy_count,
        rating=int(getattr(player, 'rating', 0) or 0),
        vip_status=vip_status_text
    )
    
    query = update.callback_query
    
    # Если это команда /start, а не нажатие кнопки
    if not query:
        await update.message.reply_html(menu_text, reply_markup=reply_markup)
        return

    # Если это нажатие на кнопку, редактируем/заменяем предыдущее сообщение
    message = query.message
    if getattr(message, 'photo', None):
        # Мы не можем отредактировать сообщение с фото. Удаляем и отправляем новое.
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


# --- Админ панель для Создателя ---
# Функции прав (get_effective_admin_level, has_admin_level, has_admin_panel_access,
# has_creator_panel_access, get_required_level_for_callback) и словари
# (ADMIN_TEXT_ACTION_LEVELS, CREATOR_TEXT_ACTION_LEVELS) импортируются
# из admin_permissions.py (см. строки 118-126).


async def show_creator_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает улучшенную админ панель для Создателя и админов 3 уровня."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    # Проверка доступа (любой админский уровень или Создатель)
    if not has_admin_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем краткую статистику для отображения
    try:
        total_users = db.get_total_users_count()
        active_vip = db.get_active_vip_count()
        active_vip_plus = db.get_active_vip_plus_count()
        total_admins = len(db.get_admin_users())
    except:
        total_users = active_vip = active_vip_plus = total_admins = 0
    
    keyboard: list[list[InlineKeyboardButton]] = []
    admin_level = get_effective_admin_level(user.id, user.username)

    # Уровень 1: обзорные разделы (без влияния на экономику/пользователей)
    if admin_level >= 1:
        keyboard.append([InlineKeyboardButton("📈 Статистика бота", callback_data='admin_bot_stats')])
        keyboard.append([InlineKeyboardButton("📊 Расширенная аналитика", callback_data='admin_analytics')])
        keyboard.append([InlineKeyboardButton("📝 Логи системы", callback_data='admin_logs_menu')])

    # Уровень 2: модерация пользователей
    if admin_level >= 2:
        keyboard.append([InlineKeyboardButton("🚫 Модерация", callback_data='admin_moderation_menu')])

    # Уровень 3: полный доступ к операционным разделам
    if admin_level >= 3:
        keyboard.extend([
            [InlineKeyboardButton("👤 Управление игроками", callback_data='admin_players_menu')],
            [InlineKeyboardButton("🎁 Быстрые выдачи", callback_data='admin_grants_menu')],
            [InlineKeyboardButton("💎 Управление VIP", callback_data='admin_vip_menu')],
            [InlineKeyboardButton("📦 Управление складом", callback_data='admin_stock_menu')],
            [InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')],
            [InlineKeyboardButton("👥 Админы", callback_data='creator_admins')],
            [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast_menu')],
            [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')],
            [InlineKeyboardButton("⚙️ Настройки бота", callback_data='admin_settings_menu')],
            [InlineKeyboardButton("💼 Экономика", callback_data='admin_economy_menu')],
            [InlineKeyboardButton("🎮 События", callback_data='admin_events_menu')],
        ])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    try:
        is_creator = bool(user.username) and (user.username in ADMIN_USERNAMES)
    except Exception:
        is_creator = False
    if is_creator:
        keyboard.insert(-1, [InlineKeyboardButton("🧨 Вайп", callback_data='creator_wipe')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⚙️ <b>Админ панель</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"💎 VIP: <b>{active_vip}</b> | VIP+: <b>{active_vip_plus}</b>\n"
        f"🛡️ Администраторов: <b>{total_admins}</b>\n\n"
        "Выберите раздел:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_grants_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрые выдачи: монеты, VIP, VIP+."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    text = (
        "🎁 <b>Быстрые выдачи</b>\n\n"
        "Выберите, что выдать:\n"
        "• Монеты\n"
        "• VIP / VIP+\n\n"
        "Форматы ввода:\n"
        "• <code>@username количество</code> или <code>количество @username</code>\n"
        "• <code>@username дни</code> или <code>дни @username</code>\n"
        "• Можно использовать <code>user_id</code> вместо @username"
    )

    keyboard = [
        [InlineKeyboardButton("💰 Выдать монеты", callback_data='creator_give_coins')],
        [InlineKeyboardButton("👑 Выдать VIP", callback_data='admin_vip_give')],
        [InlineKeyboardButton("💎 Выдать VIP+", callback_data='admin_vip_plus_give')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_settings_autosearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    base_limit = db.get_setting_int('auto_search_daily_limit_base', AUTO_SEARCH_DAILY_LIMIT)
    vip_mult = db.get_setting_float('auto_search_vip_daily_mult', 1.0)
    vip_plus_mult = db.get_setting_float('auto_search_vip_plus_daily_mult', 2.0)

    text = (
        "🤖 <b>Автопоиск — лимиты</b>\n\n"
        f"Базовый дневной лимит: <b>{int(base_limit)}</b>\n"
        f"VIP множитель: <b>{vip_mult}</b>\n"
        f"VIP+ множитель: <b>{vip_plus_mult}</b>\n\n"
        "Выберите, что изменить:"
    )
    kb = [
        [InlineKeyboardButton("Изменить базовый лимит", callback_data='admin_settings_set_auto_base')],
        [InlineKeyboardButton("Изменить VIP множитель", callback_data='admin_settings_set_auto_vip_mult')],
        [InlineKeyboardButton("Изменить VIP+ множитель", callback_data='admin_settings_set_auto_vip_plus_mult')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_settings_menu')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_settings_casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает настройки удачи в казино."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    win_prob = db.get_setting_float('casino_win_prob', CASINO_WIN_PROB)
    win_prob = max(0.0, min(1.0, float(win_prob)))
    percent = round(win_prob * 100, 2)
    luck_mult = db.get_setting_float('casino_luck_mult', 1.0)
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

    kb = [
        [InlineKeyboardButton("🎲 Изменить шанс победы", callback_data='admin_settings_set_casino_win_prob')],
        [InlineKeyboardButton("🍀 Множитель удачи", callback_data='admin_settings_set_casino_luck_mult')],
        [InlineKeyboardButton("♻️ Сбросить шанс", callback_data='admin_settings_casino_reset_prob')],
        [InlineKeyboardButton("♻️ Сбросить удачу", callback_data='admin_settings_casino_reset_luck')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_settings_menu')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_settings_set_casino_win_prob_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_casino')]]
    text = (
        "🎲 <b>Шанс победы в казино</b>\n\n"
        "Введите число:\n"
        "• от 0 до 1 (например, 0.35)\n"
        "• или в процентах 1–99 (например, 35)\n\n"
        "Текущая настройка влияет на классические ставки."
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_casino_win_prob'


async def admin_settings_set_casino_luck_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_casino')]]
    text = (
        "🍀 <b>Множитель удачи в казино</b>\n\n"
        "Увеличивает шанс победы во всех играх.\n"
        "Введите число (например 1.2, 1.5, 2):\n"
        "• 1.0 — без изменений\n"
        "• 1.5 — +50% к шансам\n"
        "• 2.0 — в 2 раза больше\n"
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_casino_luck_mult'


async def admin_settings_set_auto_base_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_autosearch')]]
    try:
        await query.message.edit_text("Введите новый базовый дневной лимит автопоиска (целое число ≥ 0):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_auto_base'


async def admin_settings_set_auto_vip_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_autosearch')]]
    try:
        await query.message.edit_text("Введите VIP множитель дневного лимита (число ≥ 0, например 1 или 1.5):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_auto_vip_mult'


async def admin_settings_set_auto_vip_plus_mult_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_autosearch')]]
    try:
        await query.message.edit_text("Введите VIP+ множитель дневного лимита (число ≥ 0, например 2):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_auto_vip_plus_mult'


async def admin_player_rating_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    context.user_data['admin_player_action'] = 'rating'
    context.user_data['admin_player_id'] = player_id
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if player:
            username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
            current_rating = int(getattr(player, 'rating', 0) or 0)
            text = (
                f"⭐ <b>Изменение рейтинга</b>\n\n"
                f"Игрок: {username_display}\n"
                f"Текущий рейтинг: <b>{current_rating}</b> ⭐\n\n"
                f"Отправьте новое значение рейтинга или изменение:\n"
                f"• <code>100</code> - установить\n"
                f"• <code>+10</code> - добавить\n"
                f"• <code>-5</code> - убрать\n\n"
                f"Диапазон: 0..1000\n\n"
                f"Или нажмите Отмена"
            )
        else:
            text = "❌ Игрок не найден!"
    finally:
        dbs.close()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f'admin_player_details:{player_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def creator_wipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not (user.username and user.username in ADMIN_USERNAMES):
        await query.answer("⛔ Доступ только Создателю!", show_alert=True)
        return
    kb = [
        [InlineKeyboardButton("✅ Подтвердить вайп", callback_data='creator_wipe_confirm')],
        [InlineKeyboardButton("❌ Отмена", callback_data='creator_panel')],
    ]
    try:
        await query.message.edit_text(
            "⚠️ Вы собираетесь выполнить ПОЛНЫЙ ВАЙП данных.\n\n"
            "Будут удалены все пользователи, инвентари, логи, промокоды, настройки и прочее.\n"
            "Список энергетиков будет сохранён.\n\n"
            "Подтверждаете?",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass


async def creator_wipe_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not (user.username and user.username in ADMIN_USERNAMES):
        await query.answer("⛔ Доступ только Создателю!", show_alert=True)
        return
    try:
        users = db.get_all_users_for_broadcast()
    except Exception:
        users = []
    try:
        groups = db.get_enabled_group_chats()
    except Exception:
        groups = []
    notify_text = (
        "🧨 Глобальный вайп данных бота выполнен.\n\n"
        "Все пользовательские данные и прогресс были сброшены.\n"
        "Список энергетиков сохранён."
    )
    ok_u = 0
    ok_g = 0
    # Сначала уведомляем группы
    for g in groups or []:
        try:
            await context.bot.send_message(chat_id=getattr(g, 'chat_id', None), text=notify_text)
            ok_g += 1
            await asyncio.sleep(0.02)
        except Exception:
            pass
    # Затем пользователей
    for uid in users or []:
        try:
            await context.bot.send_message(chat_id=uid, text=notify_text)
            ok_u += 1
            await asyncio.sleep(0.02)
        except Exception:
            pass
    try:
        db.insert_moderation_log(actor_id=user.id, action='wipe_all', details=f'groups={ok_g}, users={ok_u}')
    except Exception:
        pass
    res = False
    try:
        res = db.wipe_all_except_drinks()
    except Exception:
        res = False
    text = "✅ Вайп выполнен" if res else "❌ Ошибка при вайпе"
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')]]))
    except BadRequest:
        pass

async def admin_mod_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_moderation_menu')]]
    try:
        await query.message.edit_text(
            "🚫 Бан пользователя\n\nОтправьте: <code>@username</code> или <code>user_id</code> и опционально длительность (например: 1d, 12h, 30m) и причину.\nПримеры:\n<code>@user 7d спам</code>\n<code>123456 1h флуд</code>\n<code>@user</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'mod_ban'


async def admin_mod_unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_moderation_menu')]]
    try:
        await query.message.edit_text(
            "✅ Разбан пользователя\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'mod_unban'


async def admin_mod_banlist_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    items = db.list_active_bans(limit=50)
    if not items:
        text = "📋 Активные баны: нет"
    else:
        lines = ["📋 Активные баны:"]
        for it in items:
            uid = it['user_id']
            until = it.get('banned_until')
            until_str = safe_format_timestamp(until) if until else 'навсегда'
            reason = it.get('reason') or '—'
            lines.append(f"• {uid} — до: {until_str} — {reason}")
        text = "\n".join(lines)
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass


async def admin_mod_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_moderation_menu')]]
    try:
        await query.message.edit_text(
            "🔍 Проверка игрока\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'mod_check'


async def admin_mod_history_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    logs = db.get_moderation_logs(limit=30)
    if not logs:
        text = "📝 История модерации пуста"
    else:
        lines = ["📝 История модерации:"]
        for r in logs:
            ts = safe_format_timestamp(r.get('ts')) or '—'
            act = r.get('action')
            tgt = r.get('target_id')
            det = r.get('details') or ''
            lines.append(f"• {ts} — {act} → {tgt} {('— ' + det) if det else ''}")
        text = "\n".join(lines[:50])
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass


async def admin_mod_warnings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Выдать предупреждение", callback_data='admin_warn_add')],
        [InlineKeyboardButton("📄 Список предупреждений", callback_data='admin_warn_list')],
        [InlineKeyboardButton("🗑️ Очистить предупреждения", callback_data='admin_warn_clear')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')],
    ])
    try:
        await query.message.edit_text("⚠️ Предупреждения: выберите действие", reply_markup=kb)
    except BadRequest:
        pass


async def admin_warn_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_mod_warnings')]]
    try:
        await query.message.edit_text(
            "➕ Выдать предупреждение\n\nОтправьте: <code>@username</code> или <code>user_id</code> и причину\nПример: <code>@user спам</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'warn_add'


async def admin_warn_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_mod_warnings')]]
    try:
        await query.message.edit_text(
            "📄 Список предупреждений\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'warn_list'


async def admin_warn_clear_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_admin_level(query.from_user.id, query.from_user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_mod_warnings')]]
    try:
        await query.message.edit_text(
            "🗑️ Очистка предупреждений\n\nОтправьте: <code>@username</code> или <code>user_id</code>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'warn_clear'


def _parse_duration_to_seconds(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip().lower()
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        try:
            val = int(s)
            return val if val > 0 else None
        except Exception:
            return None
    num = int(m.group(1))
    unit = m.group(2)
    mult = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(unit, 1)
    return num * mult


def _resolve_user_identifier(text: str) -> int | None:
    t = (text or '').strip()
    if not t:
        return None
    res = db.find_player_by_identifier(t)
    if res.get('ok') and res.get('player'):
        return int(getattr(res['player'], 'user_id', 0) or 0) or None
    try:
        return int(t)
    except Exception:
        return None


async def abort_if_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет бан пользователя и, если активен, показывает причину и блокирует действие."""
    try:
        user = update.effective_user
        if not user:
            return False
        ban = db.get_active_ban(user.id)
        if not ban:
            return False
        reason = ban.get('reason') or '—'
        until = ban.get('banned_until')
        until_str = safe_format_timestamp(until) if until else 'навсегда'
        text = (
            "🚫 Ваш аккаунт заблокирован.\n"
            f"Причина: {html.escape(reason)}\n"
            f"Срок: {until_str}"
        )
        q = getattr(update, 'callback_query', None)
        if q:
            try:
                await q.answer(text, show_alert=True)
            except Exception:
                pass
        else:
            try:
                await reply_auto_delete_message(update.effective_message, text, context=context)
            except Exception:
                pass
        return True
    except Exception:
        return False


async def show_admin_settings_cooldowns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
    bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
    text = (
        "⏱️ <b>Кулдауны</b>\n\n"
        f"Поиск: <b>{int(search_cd // 60)} мин</b> ({search_cd} сек)\n"
        f"Ежедневный бонус: <b>{int(bonus_cd // 3600)} ч</b> ({bonus_cd} сек)\n\n"
        "Выберите, что изменить:"
    )
    kb = [
        [InlineKeyboardButton("Изменить поиск", callback_data='admin_settings_set_search_cd')],
        [InlineKeyboardButton("Изменить бонус", callback_data='admin_settings_set_bonus_cd')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_settings_menu')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_settings_set_search_cd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_cooldowns')]]
    try:
        await query.message.edit_text("Введите новый кулдаун поиска в секундах:", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_search_cd'


async def admin_settings_set_bonus_cd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_cooldowns')]]
    try:
        await query.message.edit_text("Введите новый кулдаун ежедневного бонуса в секундах:", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_bonus_cd'

async def creator_reset_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс сброса ежедневного бонуса."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "🔄 <b>Сброс ежедневного бонуса</b>\n\n"
        "Отправьте:\n"
        "• <code>@username</code> - для конкретного пользователя\n"
        "• <code>all</code> - для всех пользователей\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    # Устанавливаем состояние ожидания ввода
    context.user_data['awaiting_creator_action'] = 'reset_bonus'
    return 'AWAITING_INPUT'


async def creator_give_coins_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс выдачи монет."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "💰 <b>Выдача монет</b>\n\n"
        "Отправьте в формате:\n"
        "<code>@username количество</code> или <code>количество @username</code>\n"
        "<code>user_id количество</code> также подходит\n\n"
        "Пример: <code>@user 1000</code> или <code>1000 @user</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'give_coins'
    return 'AWAITING_INPUT'


async def creator_user_stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс получения статистики пользователя."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "📊 <b>Статистика пользователя</b>\n\n"
        "Отправьте <code>@username</code> пользователя\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'user_stats'
    return 'AWAITING_INPUT'


async def creator_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовый ввод для админ команд."""
    user = update.effective_user
    
    if not has_admin_panel_access(user.id, user.username):
        return
    
    action = context.user_data.get('awaiting_creator_action')
    if not action:
        return

    required_level = CREATOR_TEXT_ACTION_LEVELS.get(action, 3)
    if not has_admin_level(user.id, user.username, required_level):
        await update.message.reply_html("⛔ Недостаточный уровень доступа для этого действия.")
        context.user_data.pop('awaiting_creator_action', None)
        return
    
    text_input = (update.message.text or update.message.caption or "").strip()
    
    if action == 'reset_bonus':
        await handle_reset_bonus(update, context, text_input)
    elif action == 'give_coins':
        await handle_give_coins(update, context, text_input)
    elif action == 'user_stats':
        await handle_user_stats(update, context, text_input)
    elif action == 'admin_add':
        await handle_admin_add(update, context, text_input)
    elif action == 'admin_promote':
        await handle_admin_promote(update, context, text_input)
    elif action == 'admin_demote':
        await handle_admin_demote(update, context, text_input)
    elif action == 'admin_remove':
        await handle_admin_remove(update, context, text_input)
    elif action == 'vip_give':
        await handle_vip_give(update, context, text_input)
    elif action == 'vip_plus_give':
        await handle_vip_plus_give(update, context, text_input)
    elif action == 'vip_remove':
        await handle_vip_remove(update, context, text_input)
    elif action == 'vip_plus_remove':
        await handle_vip_plus_remove(update, context, text_input)
    elif action == 'broadcast':
        await handle_broadcast(update, context, text_input)
    elif action == 'player_search':
        await handle_player_search(update, context, text_input)
    
    # Очищаем состояние
    context.user_data.pop('awaiting_creator_action', None)


async def admin_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовый ввод для новых админ команд (энергетики, логи, управление игроками)."""
    user = update.effective_user
    
    if not has_admin_panel_access(user.id, user.username):
        return
    
    action = context.user_data.get('awaiting_admin_action')
    initial_action = action
    player_action = context.user_data.get('admin_player_action')
    
    if not action and not player_action:
        return
    
    text_input = (update.message.text or update.message.caption or "").strip()

    # Ограничиваем текстовые админ-действия по единой матрице, даже если состояние уже было установлено.
    action_required_level = ADMIN_TEXT_ACTION_LEVELS.get(action, 3)

    if action and not has_admin_level(user.id, user.username, action_required_level):
        await update.message.reply_html("⛔ Недостаточный уровень доступа для этого действия.")
        context.user_data.pop('awaiting_admin_action', None)
        return
    if player_action and not has_admin_level(user.id, user.username, 3):
        await update.message.reply_html("⛔ Недостаточный уровень доступа для этого действия.")
        context.user_data.pop('admin_player_action', None)
        context.user_data.pop('admin_player_id', None)
        return
    
    if player_action == 'balance':
        await handle_player_balance(update, context, text_input)
        context.user_data.pop('admin_player_action', None)
        context.user_data.pop('admin_player_id', None)
    elif player_action == 'rating':
        await handle_player_rating(update, context, text_input)
        context.user_data.pop('admin_player_action', None)
        context.user_data.pop('admin_player_id', None)
    elif action:
        if action == 'drink_add':
            await handle_drink_add(update, context, text_input)
        elif action == 'drink_edit':
            await handle_drink_edit(update, context, text_input)
        elif action == 'drink_delete':
            await handle_drink_delete(update, context, text_input)
        elif action == 'drink_search':
            await handle_drink_search(update, context, text_input)
        elif action == 'drink_rename_id':
            try:
                did = int(text_input)
                d = db.get_drink_by_id(did)
                if not d:
                    await update.message.reply_html("❌ Энергетик не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
                else:
                    context.user_data['edit_drink_id'] = did
                    context.user_data['awaiting_admin_action'] = 'drink_rename_value'
                    await update.message.reply_html("Отправьте новое название", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
                    return
            except Exception:
                await update.message.reply_html("❌ ID должен быть числом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
        elif action == 'drink_rename_value':
            did = context.user_data.get('edit_drink_id')
            if not did:
                await update.message.reply_html("❌ Сессия редактирования не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
            else:
                context.user_data['pending_rename'] = text_input
                d = db.get_drink_by_id(int(did))
                old_name = (d or {}).get('name') if isinstance(d, dict) else None
                lines = []
                if old_name is not None:
                    lines.append(f"Изменить название: <b>{old_name}</b> → <b>{text_input}</b>")
                else:
                    lines.append(f"Изменить название на: <b>{text_input}</b>")
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Подтвердить", callback_data='drink_confirm_rename')],
                    [InlineKeyboardButton("❌ Отмена", callback_data='drink_cancel_rename')]
                ])
                await update.message.reply_html("\n".join(lines), reply_markup=kb)
        elif action == 'drink_redesc_id':
            try:
                did = int(text_input)
                d = db.get_drink_by_id(did)
                if not d:
                    await update.message.reply_html("❌ Энергетик не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
                else:
                    context.user_data['edit_drink_id'] = did
                    context.user_data['awaiting_admin_action'] = 'drink_redesc_value'
                    await update.message.reply_html("Отправьте новое описание", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
                    return
            except Exception:
                await update.message.reply_html("❌ ID должен быть числом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
        elif action == 'drink_redesc_value':
            did = context.user_data.get('edit_drink_id')
            if not did:
                await update.message.reply_html("❌ Сессия редактирования не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
            else:
                context.user_data['pending_redesc'] = text_input
                d = db.get_drink_by_id(int(did))
                old_desc = (d or {}).get('description') if isinstance(d, dict) else None
                lines = []
                if old_desc is not None:
                    lines.append("Изменить описание:")
                    lines.append(f"<i>{old_desc[:300]}</i>")
                    lines.append("→")
                    lines.append(f"<i>{text_input[:300]}</i>")
                else:
                    lines.append("Новое описание:")
                    lines.append(f"<i>{text_input[:300]}</i>")
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Подтвердить", callback_data='drink_confirm_redesc')],
                    [InlineKeyboardButton("❌ Отмена", callback_data='drink_cancel_redesc')]
                ])
                await update.message.reply_html("\n".join(lines), reply_markup=kb)
        elif action == 'drink_update_photo_id':
            try:
                did = int(text_input)
                d = db.get_drink_by_id(did)
                if not d:
                    await update.message.reply_html("❌ Энергетик не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
                else:
                    context.user_data['edit_drink_id'] = did
                    context.user_data['awaiting_admin_action'] = 'drink_update_photo_wait_file'
                    await update.message.reply_html("Пришлите фото напитка", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
                    return
            except Exception:
                await update.message.reply_html("❌ ID должен быть числом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]))
        elif action == 'logs_player':
            await handle_logs_player(update, context, text_input)
        elif action == 'promo_create':
            await handle_promo_create(update, context, text_input)
        elif action == 'promo_deactivate':
            await handle_promo_deactivate(update, context, text_input)
        elif action == 'promo_wiz_code':
            await handle_promo_wiz_code(update, context, text_input)
        elif action == 'promo_wiz_value':
            await handle_promo_wiz_value(update, context, text_input)
        elif action == 'promo_wiz_max_uses':
            await handle_promo_wiz_max_uses(update, context, text_input)
        elif action == 'promo_wiz_per_user':
            await handle_promo_wiz_per_user(update, context, text_input)
        elif action == 'promo_wiz_expires':
            await handle_promo_wiz_expires(update, context, text_input)
        elif action == 'broadcast':
            if getattr(update.message, 'audio', None):
                await handle_admin_broadcast_audio(update, context, text_input)
            else:
                await handle_admin_broadcast(update, context, text_input)
        elif action == 'settings_set_search_cd':
            kb = [[InlineKeyboardButton("⏱️ Кулдауны", callback_data='admin_settings_cooldowns')]]
            try:
                new_cd = int(text_input.strip())
                if new_cd <= 0:
                    raise ValueError
                ok = db.set_setting_int('search_cooldown', new_cd)
                if ok:
                    await update.message.reply_html(f"✅ Кулдаун поиска обновлён: <b>{new_cd}</b> сек.", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число секунд (>0)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_bonus_cd':
            kb = [[InlineKeyboardButton("⏱️ Кулдауны", callback_data='admin_settings_cooldowns')]]
            try:
                new_cd = int(text_input.strip())
                if new_cd <= 0:
                    raise ValueError
                ok = db.set_setting_int('daily_bonus_cooldown', new_cd)
                if ok:
                    await update.message.reply_html(f"✅ Кулдаун ежедневного бонуса обновлён: <b>{new_cd}</b> сек.", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число секунд (>0)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_auto_base':
            kb = [[InlineKeyboardButton("🤖 Автопоиск", callback_data='admin_settings_autosearch')]]
            try:
                new_val = int(text_input.strip())
                if new_val < 0:
                    raise ValueError
                ok = db.set_setting_int('auto_search_daily_limit_base', new_val)
                if ok:
                    await update.message.reply_html(f"✅ Базовый дневной лимит автопоиска обновлён: <b>{new_val}</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число (≥ 0)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_auto_vip_mult':
            kb = [[InlineKeyboardButton("🤖 Автопоиск", callback_data='admin_settings_autosearch')]]
            try:
                new_val = float(text_input.strip().replace(',', '.'))
                if new_val < 0:
                    raise ValueError
                ok = db.set_setting_float('auto_search_vip_daily_mult', new_val)
                if ok:
                    await update.message.reply_html(f"✅ VIP множитель обновлён: <b>{new_val}</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число (≥ 0), например 1 или 1.5", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_auto_vip_plus_mult':
            kb = [[InlineKeyboardButton("🤖 Автопоиск", callback_data='admin_settings_autosearch')]]
            try:
                new_val = float(text_input.strip().replace(',', '.'))
                if new_val < 0:
                    raise ValueError
                ok = db.set_setting_float('auto_search_vip_plus_daily_mult', new_val)
                if ok:
                    await update.message.reply_html(f"✅ VIP+ множитель обновлён: <b>{new_val}</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число (≥ 0), например 2", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_fertilizer_max':
            kb = [[InlineKeyboardButton("💰 Лимиты", callback_data='admin_settings_limits')]]
            try:
                new_val = int(text_input.strip())
                if new_val < 1:
                    raise ValueError
                ok = db.set_setting_int('plantation_fertilizer_max_per_bed', new_val)
                if ok:
                    await update.message.reply_html(f"✅ Лимит удобрений обновлён: <b>{new_val}</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число (≥ 1)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_neg_interval':
            kb = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data='admin_settings_negative_effects')]]
            try:
                new_val = int(text_input.strip())
                if new_val < 60:
                    raise ValueError
                ok = db.set_setting_int('plantation_negative_event_interval_sec', new_val)
                if ok:
                    await update.message.reply_html(f"✅ Интервал обновлён: <b>{new_val}</b> сек.", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число (≥ 60)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_neg_chance':
            kb = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data='admin_settings_negative_effects')]]
            raw = (text_input or '').strip().replace(',', '.')
            try:
                val = float(raw)
                if val > 1:
                    val = val / 100.0
                if val <= 0 or val > 1:
                    raise ValueError
                ok = db.set_setting_float('plantation_negative_event_chance', val)
                if ok:
                    await update.message.reply_html(f"✅ Шанс обновлён: <b>{round(val * 100, 2)}%</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число 0..1 или проценты 1–100", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_neg_max_active':
            kb = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data='admin_settings_negative_effects')]]
            raw = (text_input or '').strip().replace(',', '.')
            try:
                val = float(raw)
                if val > 1:
                    val = val / 100.0
                if val <= 0 or val > 1:
                    raise ValueError
                ok = db.set_setting_float('plantation_negative_event_max_active', val)
                if ok:
                    await update.message.reply_html(f"✅ Лимит активных обновлён: <b>{round(val * 100, 2)}%</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число 0..1 или проценты 1–100", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_neg_duration':
            kb = [[InlineKeyboardButton("⚠️ Негативные эффекты", callback_data='admin_settings_negative_effects')]]
            try:
                new_val = int(text_input.strip())
                if new_val < 60:
                    raise ValueError
                ok = db.set_setting_int('plantation_negative_event_duration_sec', new_val)
                if ok:
                    await update.message.reply_html(f"✅ Длительность обновлена: <b>{new_val}</b> сек.", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите целое число (≥ 60)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_casino_win_prob':
            kb = [[InlineKeyboardButton("🎰 Казино", callback_data='admin_settings_casino')]]
            raw = (text_input or '').strip().replace(',', '.')
            try:
                val = float(raw)
                # Если ввели в процентах (1..99), переводим в доли
                if val > 1:
                    val = val / 100.0
                if val <= 0 or val >= 1:
                    raise ValueError
                ok = db.set_setting_float('casino_win_prob', val)
                if ok:
                    await update.message.reply_html(f"✅ Шанс победы обновлён: <b>{round(val * 100, 2)}%</b> (={val})", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число от 0 до 1 или процент 1–99", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'settings_set_casino_luck_mult':
            kb = [[InlineKeyboardButton("🎰 Казино", callback_data='admin_settings_casino')]]
            raw = (text_input or '').strip().replace(',', '.')
            try:
                val = float(raw)
                if val < 0.1 or val > 5:
                    raise ValueError
                ok = db.set_setting_float('casino_luck_mult', val)
                if ok:
                    await update.message.reply_html(f"✅ Множитель удачи обновлён: <b>x{val}</b>", reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_html("❌ Не удалось сохранить настройку", reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await update.message.reply_html("❌ Введите число от 0.1 до 5.0 (например 1.5)", reply_markup=InlineKeyboardMarkup(kb))
        elif action == 'mod_ban':
            # Формат: <id|@username> [duration] [reason...]
            parts = text_input.split(maxsplit=2)
            if not parts:
                await update.message.reply_html("❌ Укажите пользователя. Пример: <code>@user 7d спам</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]]))
            else:
                ident = parts[0]
                duration_sec = None
                reason = None
                if len(parts) >= 2:
                    d = _parse_duration_to_seconds(parts[1])
                    if d:
                        duration_sec = d
                        if len(parts) == 3:
                            reason = parts[2]
                    else:
                        # duration не распознан — считаем это началом причины
                        reason = " ".join(parts[1:])
                uid = _resolve_user_identifier(ident)
                if not uid:
                    await update.message.reply_html(
                        "❌ Пользователь не найден.\n\n"
                        "Подсказка:\n"
                        "• Попросите пользователя написать боту /start (чтобы он появился в базе)\n"
                        "• Либо введите его числовой ID",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]])
                    )
                else:
                    if db.is_protected_user(uid):
                        await update.message.reply_html(
                            "⛔ Нельзя банить администратора или создателя",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Модерация", callback_data='admin_moderation_menu')]])
                        )
                    else:
                        ok = db.ban_user(uid, banned_by=update.effective_user.id, reason=reason, duration_seconds=duration_sec)
                        if ok:
                            until_str = None
                            if duration_sec:
                                until_str = safe_format_timestamp(int(time.time()) + int(duration_sec))
                            text = f"✅ Пользователь {uid} забанен" + (f" до {until_str}" if until_str else " навсегда")
                            if reason:
                                text += f"\nПричина: {html.escape(reason)}"
                            await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Модерация", callback_data='admin_moderation_menu')]]))
                        else:
                            await update.message.reply_html("❌ Не удалось забанить пользователя", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]]))
        elif action == 'mod_unban':
            ident = text_input.strip()
            uid = _resolve_user_identifier(ident)
            if not uid:
                await update.message.reply_html(
                    "❌ Пользователь не найден.\n\n"
                    "Подсказка:\n"
                    "• Попросите пользователя написать боту /start\n"
                    "• Либо введите его числовой ID",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]])
                )
            else:
                ok = db.unban_user(uid, unbanned_by=update.effective_user.id)
                await update.message.reply_html("✅ Пользователь разбанен" if ok else "❌ Не удалось разбанить пользователя", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Модерация", callback_data='admin_moderation_menu')]]))
        elif action == 'mod_check':
            ident = text_input.strip()
            uid = _resolve_user_identifier(ident)
            if not uid:
                await update.message.reply_html("❌ Пользователь не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_moderation_menu')]]))
            else:
                player = db.get_player(uid)
                banned = db.is_user_banned(uid)
                warns = db.get_warnings(uid, limit=50)
                vip = db.is_vip(uid)
                vip_plus = db.is_vip_plus(uid)
                username = getattr(player, 'username', None) if player else None
                text_lines = [
                    "🔍 <b>Проверка игрока</b>",
                    f"ID: <b>{uid}</b>",
                    f"Username: <b>@{html.escape(username)}</b>" if username else "Username: —",
                    f"Баланс: <b>{getattr(player, 'coins', 0) if player else 0}</b>",
                    f"VIP: {'активен' if vip else '—'} | VIP+: {'активен' if vip_plus else '—'}",
                    f"Статус: {'🚫 Забанен' if banned else '✅ Активен'}",
                    f"Предупреждений: <b>{len(warns)}</b>",
                ]
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Модерация", callback_data='admin_moderation_menu')]])
                await update.message.reply_html("\n".join(text_lines), reply_markup=kb)
        elif action == 'warn_add':
            parts = text_input.split(maxsplit=1)
            if not parts:
                await update.message.reply_html("❌ Укажите пользователя", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_mod_warnings')]]))
            else:
                ident = parts[0]
                reason = parts[1] if len(parts) > 1 else None
                uid = _resolve_user_identifier(ident)
                if not uid:
                    await update.message.reply_html(
                        "❌ Пользователь не найден.\n\n"
                        "Подсказка:\n"
                        "• Попросите пользователя написать боту /start\n"
                        "• Либо введите его числовой ID",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_mod_warnings')]])
                    )
                else:
                    ok = db.add_warning(uid, issued_by=update.effective_user.id, reason=reason)
                    await update.message.reply_html("✅ Предупреждение выдано" if ok else "❌ Не удалось выдать предупреждение", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Предупреждения", callback_data='admin_mod_warnings')]]))
        elif action == 'warn_list':
            ident = text_input.strip()
            uid = _resolve_user_identifier(ident)
            if not uid:
                await update.message.reply_html(
                    "❌ Пользователь не найден.\n\n"
                    "Подсказка:\n"
                    "• Попросите пользователя написать боту /start\n"
                    "• Либо введите его числовой ID",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_mod_warnings')]])
                )
            else:
                items = db.get_warnings(uid, limit=50)
                if not items:
                    text = "📄 У пользователя нет предупреждений"
                else:
                    lines = ["📄 Предупреждения:"]
                    for w in items:
                        ts = safe_format_timestamp(w.get('issued_at')) or '—'
                        rs = html.escape(w.get('reason') or '')
                        lines.append(f"• {ts} — {rs}")
                    text = "\n".join(lines[:100])
                await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Предупреждения", callback_data='admin_mod_warnings')]]))
        elif action == 'warn_clear':
            ident = text_input.strip()
            uid = _resolve_user_identifier(ident)
            if not uid:
                await update.message.reply_html("❌ Пользователь не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_mod_warnings')]]))
            else:
                count = db.clear_warnings(uid)
                await update.message.reply_html(f"🗑️ Удалено предупреждений: <b>{count}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Предупреждения", callback_data='admin_mod_warnings')]]))
        
        # Очищаем состояние только если обработчик не перевёл нас на следующий шаг.
        # (Например, мастер промокодов выставляет новый awaiting_admin_action на каждом шаге.)
        if context.user_data.get('awaiting_admin_action') == initial_action:
            context.user_data.pop('awaiting_admin_action', None)


async def handle_drink_add(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает добавление энергетика."""
    keyboard = [[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = [p.strip() for p in text_input.split('|')]
    if len(parts) != 3:
        response = "❌ Неверный формат! Используйте: Название | Описание | Специальный (да/нет)"
    else:
        name, description, is_special_str = parts
        is_special = is_special_str.lower() in ['да', 'yes', 'true', '1']
        
        success = db.admin_add_drink(name, description, is_special)
        if success:
            response = f"✅ Энергетик <b>{name}</b> успешно добавлен!"
            # Логируем действие
            db.log_action(
                user_id=update.effective_user.id,
                username=update.effective_user.username,
                action_type='admin_action',
                action_details=f'Добавлен энергетик: {name}',
                success=True
            )
        else:
            response = f"❌ Энергетик с таким названием уже существует!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_drink_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает редактирование энергетика."""
    keyboard = [[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = [p.strip() for p in text_input.split('|')]
    if len(parts) != 4:
        response = "❌ Неверный формат! Используйте: ID | Название | Описание | Специальный (да/нет или -)"
    else:
        drink_id_str, name, description, is_special_str = parts
        
        try:
            drink_id = int(drink_id_str)
            
            # Получаем текущий напиток
            drink = db.get_drink_by_id(drink_id)
            if not drink:
                response = f"❌ Энергетик с ID {drink_id} не найден!"
            else:
                # Определяем, что менять
                new_name = name if name != '-' else None
                new_description = description if description != '-' else None
                new_is_special = None
                if is_special_str != '-':
                    new_is_special = is_special_str.lower() in ['да', 'yes', 'true', '1']
                
                success = db.admin_update_drink(drink_id, new_name, new_description, new_is_special)
                if success:
                    response = f"✅ Энергетик <b>{drink['name']}</b> успешно обновлён!"
                    # Логируем действие
                    db.log_action(
                        user_id=update.effective_user.id,
                        username=update.effective_user.username,
                        action_type='admin_action',
                        action_details=f'Изменён энергетик: {drink["name"]} (ID: {drink_id})',
                        success=True
                    )
                else:
                    response = f"❌ Ошибка при обновлении энергетика!"
        except ValueError:
            response = "❌ ID должен быть числом!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_drink_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает удаление энергетика."""
    keyboard = [[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        drink_id = int(text_input)
        
        # Получаем информацию о напитке перед удалением
        drink = db.get_drink_by_id(drink_id)
        if not drink:
            response = f"❌ Энергетик с ID {drink_id} не найден!"
        else:
            drink_name = drink['name']
            success = db.admin_delete_drink(drink_id)
            if success:
                response = f"✅ Энергетик <b>{drink_name}</b> (ID: {drink_id}) успешно удалён!"
                # Логируем действие
                db.log_action(
                    user_id=update.effective_user.id,
                    username=update.effective_user.username,
                    action_type='admin_action',
                    action_details=f'Удалён энергетик: {drink_name} (ID: {drink_id})',
                    success=True
                )
            else:
                response = f"❌ Ошибка при удалении энергетика!"
    except ValueError:
        response = "❌ ID должен быть числом!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_drink_search(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает поиск энергетика."""
    keyboard = [[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    drinks = db.search_drinks_by_name(text_input)
    
    if drinks:
        response = f"🔍 <b>Результаты поиска: \"{text_input}\"</b>\n\n"
        response += f"Найдено: <b>{len(drinks)}</b> напитков\n\n"
        
        for drink in drinks[:20]:  # Показываем первые 20
            special = "⭐" if drink['is_special'] else ""
            img = "🖼️" if drink['has_image'] else ""
            response += f"{special}{img} <b>{drink['name']}</b> (ID: {drink['id']})\n"
            response += f"<i>{drink['description'][:50]}...</i>\n\n"
        
        if len(drinks) > 20:
            response += f"<i>...и ещё {len(drinks) - 20} напитков</i>"
    else:
        response = f"❌ Напитки по запросу \"{text_input}\" не найдены"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_logs_player(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает просмотр логов конкретного игрока."""
    keyboard = [[InlineKeyboardButton("📝 Логи системы", callback_data='admin_logs_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    player = None
    res = db.find_player_by_identifier(text_input)
    if res.get('ok') and res.get('player'):
        player = res['player']
    else:
        try:
            user_id = int(str(text_input).strip().lstrip('@'))
            player = db.get_or_create_player(user_id, f"User{user_id}")
        except Exception:
            player = None
    
    if not player:
        response = f"❌ Пользователь {text_input} не найден!"
    else:
        logs = db.get_user_logs(player.user_id, limit=15)
        
        response = f"👤 <b>Логи игрока @{player.username or player.user_id}</b>\n\n"
        
        if logs:
            for log in logs:
                status = "✅" if log['success'] else "❌"
                timestamp_str = safe_format_timestamp(log['timestamp'])
                response += f"{status} <i>{log['action_type']}</i>\n"
                if log['action_details']:
                    response += f"├ {log['action_details'][:50]}\n"
                if log['amount']:
                    sign = "+" if log['amount'] > 0 else ""
                    response += f"├ {sign}{log['amount']} 💰\n"
                response += f"└ {timestamp_str}\n\n"
        else:
            response += "<i>Логов для этого игрока пока нет</i>"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_reset_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает сброс ежедневного бонуса."""
    keyboard = [[InlineKeyboardButton("⚙️ Админ панель", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if text_input.lower() == 'all':
        # Сбрасываем бонус для всех
        try:
            count = db.reset_all_daily_bonus()
            response = f"✅ Ежедневный бонус сброшен для <b>{count}</b> пользователей!"
        except Exception as e:
            logger.error(f"Ошибка сброса бонусов: {e}")
            response = f"❌ Ошибка: {e}"
    elif text_input.strip():
        res = db.find_player_by_identifier(text_input)
        if res.get('ok') and res.get('player'):
            player = res['player']
            db.update_player(player.user_id, last_bonus_claim=0)
            username = getattr(player, 'username', None)
            shown = f"@{username}" if username else str(player.user_id)
            response = f"✅ Ежедневный бонус сброшен для {shown}!"
        elif res.get('reason') == 'multiple':
            lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            response = "\n".join(lines)
        else:
            response = f"❌ Пользователь {text_input} не найден!"
    else:
        response = "❌ Неверный формат! Используйте @username или all"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_give_coins(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает выдачу монет."""
    keyboard = [[InlineKeyboardButton("⚙️ Админ панель", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = (text_input or '').split()
    if len(parts) != 2:
        response = "❌ Неверный формат! Используйте: @username количество или количество @username"
    else:
        ident = parts[0]
        try:
            # Разрешаем формат "количество @username"
            if parts[0].lstrip('+-').isdigit() and not parts[1].lstrip('+-').isdigit():
                ident = parts[1]
                amount = int(parts[0])
            else:
                amount = int(parts[1])
            res = db.find_player_by_identifier(ident)
            if res.get('ok') and res.get('player'):
                player = res['player']
                username = getattr(player, 'username', None)
                new_balance = db.increment_coins(player.user_id, amount)
                # Логируем транзакцию
                admin_user = update.effective_user
                db.log_action(
                    user_id=player.user_id,
                    username=(username or str(player.user_id)),
                    action_type='transaction',
                    action_details=f'Админская выдача: выдано админом @{admin_user.username or admin_user.first_name}',
                    amount=amount,
                    success=True
                )
                shown = f"@{username}" if username else str(player.user_id)
                response = f"✅ Выдано <b>{amount}</b> септимов пользователю {shown}\nНовый баланс: <b>{new_balance}</b>"
            elif res.get('reason') == 'multiple':
                lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
                for c in (res.get('candidates') or []):
                    cu = c.get('username')
                    lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
                response = "\n".join(lines)
            else:
                response = f"❌ Пользователь {ident} не найден!"
        except ValueError:
            response = "❌ Количество должно быть числом!"
        except Exception as e:
            logger.error(f"Ошибка выдачи монет: {e}")
            response = f"❌ Ошибка: {e}"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает получение статистики пользователя."""
    keyboard = [[InlineKeyboardButton("⚙️ Админ панель", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('ok') and res.get('player'):
        player = res['player']
        username = getattr(player, 'username', None)
        if player:
            # Получаем дополнительную информацию
            inventory_count = len(db.get_player_inventory_with_details(player.user_id))
            vip_until = db.get_vip_until(player.user_id)
            vip_plus_until = db.get_vip_plus_until(player.user_id)
            
            vip_status = "Нет"
            if vip_plus_until and time.time() < vip_plus_until:
                vip_status = f"VIP+ до {safe_format_timestamp(vip_plus_until)}"
            elif vip_until and time.time() < vip_until:
                vip_status = f"VIP до {safe_format_timestamp(vip_until)}"
            
            last_bonus = safe_format_timestamp(player.last_bonus_claim) if player.last_bonus_claim else "Никогда"
            last_search = safe_format_timestamp(player.last_search) if player.last_search else "Никогда"
            
            response = (
                f"📊 <b>Статистика пользователя @{username}</b>\n\n" if username else f"📊 <b>Статистика пользователя {player.user_id}</b>\n\n"
                f"<b>ID:</b> {player.user_id}\n"
                f"<b>Баланс:</b> {player.coins} 🪙\n"
                f"<b>Инвентарь:</b> {inventory_count} предметов\n"
                f"<b>VIP статус:</b> {vip_status}\n"
                f"<b>Последний поиск:</b> {last_search}\n"
                f"<b>Последний бонус:</b> {last_bonus}\n"
                f"<b>Язык:</b> {player.language}"
            )
        else:
            response = f"❌ Пользователь {text_input} не найден!"
    elif res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    else:
        response = "❌ Неверный формат! Используйте: @username"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_player_search(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает поиск игрока."""
    text_input = (text_input or '').strip()
    res = db.find_player_by_identifier(text_input)
    if res.get('ok') and res.get('player'):
        await show_player_details(update, context, int(res['player'].user_id))
        return
    if res.get('reason') == 'multiple':
        keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        lines = [f"❌ Найдено несколько игроков по запросу: <code>{text_input}</code>", "", "Уточните запрос. Кандидаты:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"• @{cu} (ID: {c.get('user_id')})" if cu else f"• ID: {c.get('user_id')}")
        await update.message.reply_html("\n".join(lines), reply_markup=reply_markup)
        return

    keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    response = f"❌ Игрок не найден!\n\nВы искали: <code>{text_input}</code>\n\nИспользуйте:\n• <code>@username</code> или просто <code>username</code>\n• <code>user_id</code> (число)"
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_player_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает изменение баланса игрока."""
    player_id = context.user_data.get('admin_player_id')
    if not player_id:
        response = "❌ Ошибка: ID игрока не найден!"
        keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(response, reply_markup=reply_markup)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            response = "❌ Игрок не найден!"
            keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_html(response, reply_markup=reply_markup)
            return
        
        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        current_balance = player.coins
        
        # Парсим ввод
        text_input = text_input.strip()
        new_balance = None
        
        if text_input.startswith('+'):
            # Добавить
            try:
                amount = int(text_input[1:])
                new_balance = db.increment_coins(player_id, amount)
                # Логируем транзакцию
                admin_user = update.effective_user
                db.log_action(
                    user_id=player_id,
                    username=username_display,
                    action_type='transaction',
                    action_details=f'Админская выдача: добавлено админом @{admin_user.username or admin_user.first_name}',
                    amount=amount,
                    success=True
                )
                response = f"✅ Добавлено <b>{amount:,}</b> септимов игроку {username_display}\nНовый баланс: <b>{new_balance:,}</b> 🪙"
            except ValueError:
                response = "❌ Неверный формат! Используйте число после +"
        elif text_input.startswith('-'):
            # Убрать
            try:
                amount = int(text_input[1:])
                result = db.decrement_coins(player_id, amount)
                if result['ok']:
                    new_balance = result['new_balance']
                    # Логируем транзакцию
                    admin_user = update.effective_user
                    db.log_action(
                        user_id=player_id,
                        username=username_display,
                        action_type='transaction',
                        action_details=f'Админское снятие: убрано админом @{admin_user.username or admin_user.first_name}',
                        amount=-amount,
                        success=True
                    )
                    response = f"✅ Убрано <b>{amount:,}</b> септимов у игрока {username_display}\nНовый баланс: <b>{new_balance:,}</b> 🪙"
                else:
                    response = f"❌ {result.get('reason', 'Ошибка при уменьшении баланса')}"
            except ValueError:
                response = "❌ Неверный формат! Используйте число после -"
        else:
            # Установить баланс
            try:
                amount = int(text_input)
                db.update_player(player_id, coins=amount)
                new_balance = amount
                response = f"✅ Баланс игрока {username_display} установлен: <b>{new_balance:,}</b> 🪙"
            except ValueError:
                response = "❌ Неверный формат! Используйте число для установки баланса"
        
        keyboard = [[InlineKeyboardButton("🔙 К игроку", callback_data=f'admin_player_details:{player_id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(response, reply_markup=reply_markup)
    finally:
        dbs.close()


async def handle_player_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    player_id = context.user_data.get('admin_player_id')
    if not player_id:
        response = "❌ Ошибка: ID игрока не найден!"
        keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(response, reply_markup=reply_markup)
        return

    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            response = "❌ Игрок не найден!"
            keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_html(response, reply_markup=reply_markup)
            return

        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        current_rating = int(getattr(player, 'rating', 0) or 0)
        text_input = (text_input or '').strip()

        admin_user = update.effective_user
        new_rating = None

        if text_input.startswith('+'):
            try:
                delta = int(text_input[1:])
                new_rating = db.change_player_rating(player_id, delta)
                if new_rating is None:
                    response = "❌ Ошибка при изменении рейтинга"
                else:
                    db.log_action(
                        user_id=player_id,
                        username=username_display,
                        action_type='admin_action',
                        action_details=f'Админское изменение рейтинга: +{delta} (админ @{admin_user.username or admin_user.first_name})',
                        amount=delta,
                        success=True
                    )
                    response = f"✅ Рейтинг игрока {username_display}: <b>{current_rating}</b> → <b>{new_rating}</b> ⭐"
            except ValueError:
                response = "❌ Неверный формат! Используйте число после +"
        elif text_input.startswith('-'):
            try:
                delta = int(text_input[1:])
                new_rating = db.change_player_rating(player_id, -delta)
                if new_rating is None:
                    response = "❌ Ошибка при изменении рейтинга"
                else:
                    db.log_action(
                        user_id=player_id,
                        username=username_display,
                        action_type='admin_action',
                        action_details=f'Админское изменение рейтинга: -{delta} (админ @{admin_user.username or admin_user.first_name})',
                        amount=-delta,
                        success=True
                    )
                    response = f"✅ Рейтинг игрока {username_display}: <b>{current_rating}</b> → <b>{new_rating}</b> ⭐"
            except ValueError:
                response = "❌ Неверный формат! Используйте число после -"
        else:
            try:
                value = int(text_input)
                new_rating = db.set_player_rating(player_id, value)
                if new_rating is None:
                    response = "❌ Ошибка при установке рейтинга"
                else:
                    db.log_action(
                        user_id=player_id,
                        username=username_display,
                        action_type='admin_action',
                        action_details=f'Админская установка рейтинга: {current_rating} -> {new_rating} (админ @{admin_user.username or admin_user.first_name})',
                        amount=new_rating,
                        success=True
                    )
                    response = f"✅ Рейтинг игрока {username_display} установлен: <b>{new_rating}</b> ⭐"
            except ValueError:
                response = "❌ Неверный формат! Используйте число для установки рейтинга"

        keyboard = [[InlineKeyboardButton("🔙 К игроку", callback_data=f'admin_player_details:{player_id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(response, reply_markup=reply_markup)
    finally:
        dbs.close()


async def handle_admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает добавление админа."""
    keyboard = [[InlineKeyboardButton("👥 Админы", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = text_input.split()
    if len(parts) != 2:
        response = "❌ Неверный формат! Используйте: @username уровень (1-3)"
    else:
        ident = parts[0]
        try:
            level = int(parts[1])
            if level not in (1, 2, 3):
                response = "❌ Уровень должен быть 1, 2 или 3!"
            else:
                res = db.find_player_by_identifier(ident)
                if res.get('reason') == 'multiple':
                    lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
                    for c in (res.get('candidates') or []):
                        cu = c.get('username')
                        lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
                    response = "\n".join(lines)
                elif not (res.get('ok') and res.get('player')):
                    response = f"❌ Пользователь {ident} не найден в базе!"
                else:
                    player = res['player']
                    username = getattr(player, 'username', None)
                    success = db.add_admin_user(player.user_id, username, level)
                    shown = f"@{username}" if username else str(player.user_id)
                    if success:
                        response = f"✅ Админ {shown} добавлен с уровнем {level}!"
                    else:
                        response = f"⚠️ {shown} уже является админом. Используйте повышение/понижение уровня."
        except ValueError:
            response = "❌ Уровень должен быть числом (1, 2 или 3)!"
        except Exception as e:
            logger.error(f"Ошибка добавления админа: {e}")
            response = f"❌ Ошибка: {e}"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_admin_promote(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает повышение уровня админа."""
    keyboard = [[InlineKeyboardButton("👥 Админы", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    elif not (res.get('ok') and res.get('player')):
        response = "❌ Неверный формат! Используйте: @username"
    else:
        player = res['player']
        username = getattr(player, 'username', None)
        shown = f"@{username}" if username else str(player.user_id)
        current_level = db.get_admin_level(player.user_id)
        if current_level == 0:
            response = f"❌ {shown} не является админом!"
        elif current_level >= 3:
            response = f"⚠️ {shown} уже имеет максимальный уровень (3)!"
        else:
            new_level = current_level + 1
            success = db.set_admin_level(player.user_id, new_level)
            if success:
                response = f"✅ Уровень админа {shown} повышен: {current_level} → {new_level}"
            else:
                response = "❌ Ошибка при повышении уровня!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_admin_demote(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает понижение уровня админа."""
    keyboard = [[InlineKeyboardButton("👥 Админы", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    elif not (res.get('ok') and res.get('player')):
        response = "❌ Неверный формат! Используйте: @username"
    else:
        player = res['player']
        username = getattr(player, 'username', None)
        shown = f"@{username}" if username else str(player.user_id)
        current_level = db.get_admin_level(player.user_id)
        if current_level == 0:
            response = f"❌ {shown} не является админом!"
        elif current_level <= 1:
            response = f"⚠️ {shown} имеет минимальный уровень (1). Используйте 'Уволить' для удаления."
        else:
            new_level = current_level - 1
            success = db.set_admin_level(player.user_id, new_level)
            if success:
                response = f"✅ Уровень админа {shown} понижен: {current_level} → {new_level}"
            else:
                response = "❌ Ошибка при понижении уровня!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает увольнение админа."""
    keyboard = [[InlineKeyboardButton("👥 Админы", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    elif not (res.get('ok') and res.get('player')):
        response = "❌ Неверный формат! Используйте: @username"
    else:
        player = res['player']
        username = getattr(player, 'username', None)
        shown = f"@{username}" if username else str(player.user_id)
        current_level = db.get_admin_level(player.user_id)
        if current_level == 0:
            response = f"❌ {shown} не является админом!"
        else:
            success = db.remove_admin_user(player.user_id)
            if success:
                response = f"✅ Админ {shown} (уровень {current_level}) уволен!"
            else:
                response = "❌ Ошибка при увольнении админа!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_vip_give(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает выдачу VIP."""
    keyboard = [[InlineKeyboardButton("💎 Управление VIP", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = text_input.split()
    if len(parts) != 2:
        response = "❌ Неверный формат! Используйте: @username дни или дни @username"
    else:
        ident = parts[0]
        try:
            # Разрешаем формат "дни @username"
            if parts[0].lstrip('+-').isdigit() and not parts[1].lstrip('+-').isdigit():
                ident = parts[1]
                days = int(parts[0])
            else:
                days = int(parts[1])
            res = db.find_player_by_identifier(ident)
            if res.get('reason') == 'multiple':
                lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
                for c in (res.get('candidates') or []):
                    cu = c.get('username')
                    lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
                response = "\n".join(lines)
            elif not (res.get('ok') and res.get('player')):
                response = f"❌ Пользователь {ident} не найден!"
            else:
                player = res['player']
                duration_seconds = days * 86400
                success = db.set_vip_for_user(player.user_id, duration_seconds)
                username = getattr(player, 'username', None)
                shown = f"@{username}" if username else str(player.user_id)
                if success:
                    response = f"✅ VIP выдан пользователю {shown} на <b>{days}</b> дней!"
                else:
                    response = "❌ Ошибка при выдаче VIP!"
        except ValueError:
            response = "❌ Количество дней должно быть числом!"
        except Exception as e:
            logger.error(f"Ошибка выдачи VIP: {e}")
            response = f"❌ Ошибка: {e}"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_vip_plus_give(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает выдачу VIP+."""
    keyboard = [[InlineKeyboardButton("💎 Управление VIP", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    parts = text_input.split()
    if len(parts) != 2:
        response = "❌ Неверный формат! Используйте: @username дни или дни @username"
    else:
        ident = parts[0]
        try:
            # Разрешаем формат "дни @username"
            if parts[0].lstrip('+-').isdigit() and not parts[1].lstrip('+-').isdigit():
                ident = parts[1]
                days = int(parts[0])
            else:
                days = int(parts[1])
            res = db.find_player_by_identifier(ident)
            if res.get('reason') == 'multiple':
                lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
                for c in (res.get('candidates') or []):
                    cu = c.get('username')
                    lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
                response = "\n".join(lines)
            elif not (res.get('ok') and res.get('player')):
                response = f"❌ Пользователь {ident} не найден!"
            else:
                player = res['player']
                duration_seconds = days * 86400
                success = db.set_vip_plus_for_user(player.user_id, duration_seconds)
                username = getattr(player, 'username', None)
                shown = f"@{username}" if username else str(player.user_id)
                if success:
                    response = f"✅ VIP+ выдан пользователю {shown} на <b>{days}</b> дней!"
                else:
                    response = "❌ Ошибка при выдаче VIP+!"
        except ValueError:
            response = "❌ Количество дней должно быть числом!"
        except Exception as e:
            logger.error(f"Ошибка выдачи VIP+: {e}")
            response = f"❌ Ошибка: {e}"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_vip_remove(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает отзыв VIP."""
    keyboard = [[InlineKeyboardButton("💎 Управление VIP", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    elif not (res.get('ok') and res.get('player')):
        response = "❌ Неверный формат! Используйте: @username"
    else:
        player = res['player']
        username = getattr(player, 'username', None)
        shown = f"@{username}" if username else str(player.user_id)
        success = db.remove_vip_from_user(player.user_id)
        if success:
            response = f"✅ VIP отозван у пользователя {shown}!"
        else:
            response = "❌ Ошибка при отзыве VIP!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_vip_plus_remove(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает отзыв VIP+."""
    keyboard = [[InlineKeyboardButton("💎 Управление VIP", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    res = db.find_player_by_identifier(text_input)
    if res.get('reason') == 'multiple':
        lines = ["❌ Найдено несколько пользователей, уточните запрос:"]
        for c in (res.get('candidates') or []):
            cu = c.get('username')
            lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
        response = "\n".join(lines)
    elif not (res.get('ok') and res.get('player')):
        response = "❌ Неверный формат! Используйте: @username"
    else:
        player = res['player']
        username = getattr(player, 'username', None)
        shown = f"@{username}" if username else str(player.user_id)
        success = db.remove_vip_plus_from_user(player.user_id)
        if success:
            response = f"✅ VIP+ отозван у пользователя {shown}!"
        else:
            response = "❌ Ошибка при отзыве VIP+!"
    
    await update.message.reply_html(response, reply_markup=reply_markup)


async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    """Обрабатывает рассылку сообщений."""
    keyboard = [[InlineKeyboardButton("⚙️ Админ панель", callback_data='creator_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not text_input or len(text_input) < 3:
        response = "❌ Сообщение слишком короткое!"
        await update.message.reply_html(response, reply_markup=reply_markup)
        return
    
    # Получаем список всех пользователей
    user_ids = db.get_all_users_for_broadcast()
    total = len(user_ids)
    
    await update.message.reply_html(
        f"📢 <b>Начинаю рассылку...</b>\n\n"
        f"Всего пользователей: {total}\n"
        f"Это может занять некоторое время.",
        reply_markup=reply_markup
    )
    
    # Отправляем сообщения
    success_count = 0
    fail_count = 0
    
    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text_input,
                parse_mode='HTML'
            )
            success_count += 1
            # Небольшая задержка, чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    # Отчёт
    response = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: <b>{success_count}</b>\n"
        f"❌ Не отправлено: <b>{fail_count}</b>\n"
        f"📊 Всего: <b>{total}</b>"
    )
    
    await update.message.reply_html(response, reply_markup=reply_markup)


# --- Управление админами ---

async def show_admins_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает панель управления админами."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем список всех админов
    admins = db.get_admin_users()
    
    text = "👥 <b>Управление админами</b>\n\n"
    
    if admins:
        text += "<b>Список админов:</b>\n\n"
        for admin in admins:
            level_emoji = "⭐" * admin.level
            username_display = f"@{admin.username}" if admin.username else f"ID: {admin.user_id}"
            text += f"{level_emoji} <b>Уровень {admin.level}</b> - {username_display}\n"
    else:
        text += "<i>Админов нет</i>\n"
    
    text += "\n<b>Выберите действие:</b>"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить нового админа", callback_data='creator_admin_add')],
        [InlineKeyboardButton("⬆️ Повысить уровень", callback_data='creator_admin_promote')],
        [InlineKeyboardButton("⬇️ Понизить уровень", callback_data='creator_admin_demote')],
        [InlineKeyboardButton("❌ Уволить админа", callback_data='creator_admin_remove')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def creator_admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления админа."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "➕ <b>Добавление нового админа</b>\n\n"
        "Отправьте в формате:\n"
        "<code>@username уровень</code>\n\n"
        "Где уровень: 1, 2 или 3\n"
        "Пример: <code>@admin 2</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'admin_add'


async def creator_admin_promote_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс повышения уровня админа."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "⬆️ <b>Повышение уровня админа</b>\n\n"
        "Отправьте <code>@username</code> админа\n\n"
        "Уровень будет повышен на 1\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'admin_promote'


async def creator_admin_demote_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс понижения уровня админа."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "⬇️ <b>Понижение уровня админа</b>\n\n"
        "Отправьте <code>@username</code> админа\n\n"
        "Уровень будет понижен на 1\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'admin_demote'


async def creator_admin_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс увольнения админа."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "❌ <b>Увольнение админа</b>\n\n"
        "Отправьте <code>@username</code> админа\n\n"
        "⚠️ Админ будет полностью удален!\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='creator_admins')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'admin_remove'


# --- Новые обработчики улучшенной админ панели ---

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную статистику бота."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем статистику
    stats = db.get_bot_statistics()
    
    text = (
        "📈 <b>Статистика бота</b>\n\n"
        "<b>👥 Пользователи:</b>\n"
        f"• Всего: {stats.get('total_users', 0)}\n"
        f"• Активны сегодня: {stats.get('active_today', 0)}\n"
        f"• Активны за неделю: {stats.get('active_week', 0)}\n\n"
        "<b>💎 VIP:</b>\n"
        f"• VIP: {stats.get('active_vip', 0)}\n"
        f"• VIP+: {stats.get('active_vip_plus', 0)}\n\n"
        "<b>🥤 Напитки:</b>\n"
        f"• Всего видов: {stats.get('total_drinks', 0)}\n"
        f"• В инвентарях: {stats.get('total_inventory_items', 0)}\n\n"
        "<b>💰 Экономика:</b>\n"
        f"• Всего монет: {stats.get('total_coins', 0):,}\n\n"
        "<b>🛍️ Покупки:</b>\n"
        f"• Всего покупок: {stats.get('total_purchases', 0)}\n"
        f"• Сегодня: {stats.get('purchases_today', 0)}\n\n"
        "<b>🏆 Топ-5 по монетам:</b>\n"
    )
    
    for i, (user_id, username, coins) in enumerate(stats.get('top_coins', [])[:5], 1):
        username_display = f"@{username}" if username else f"ID:{user_id}"
        text += f"{i}. {username_display} — {coins:,} 🪙\n"
    
    text += "\n<b>🥤 Топ-5 по напиткам:</b>\n"
    for i, (user_id, username, total) in enumerate(stats.get('top_drinks', [])[:5], 1):
        username_display = f"@{username}" if username else f"ID:{user_id}"
        text += f"{i}. {username_display} — {total}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_bot_stats')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_players_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления игроками."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем статистику
    total_users = db.get_total_users_count()
    active_vip = db.get_active_vip_count()
    active_vip_plus = db.get_active_vip_plus_count()
    
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск игрока", callback_data='admin_player_search')],
        [InlineKeyboardButton("📋 Список игроков", callback_data='admin_players_list')],
        [InlineKeyboardButton("🎁 Быстрые выдачи", callback_data='admin_grants_menu')],
        [InlineKeyboardButton("🔄 Сбросить бонус", callback_data='creator_reset_bonus')],
        [InlineKeyboardButton("📊 Статистика игрока", callback_data='creator_user_stats')],
        [InlineKeyboardButton("💎 Топ игроков", callback_data='admin_players_top')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "👤 <b>Управление игроками</b>\n\n"
        f"👥 Всего игроков: <b>{total_users}</b>\n"
        f"💎 VIP: <b>{active_vip}</b> | VIP+: <b>{active_vip_plus}</b>\n\n"
        "Выберите действие:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_player_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс поиска игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "🔍 <b>Поиск игрока</b>\n\n"
        "Отправьте:\n"
        "• <code>@username</code> - для поиска по username\n"
        "• <code>user_id</code> - для поиска по ID (число)\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_players_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'player_search'
    return 'AWAITING_INPUT'


async def admin_players_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список игроков с фильтрами."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем список фильтров из callback_data если есть
    filter_type = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            filter_type = parts[1]
    
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        
        if filter_type == 'vip':
            players = dbs.query(Player).filter(Player.vip_until > current_time).order_by(Player.coins.desc()).limit(20).all()
            title = "💎 <b>Игроки с VIP</b>\n\n"
        elif filter_type == 'vip_plus':
            players = dbs.query(Player).filter(Player.vip_plus_until > current_time).order_by(Player.coins.desc()).limit(20).all()
            title = "⭐ <b>Игроки с VIP+</b>\n\n"
        elif filter_type == 'top':
            players = dbs.query(Player).order_by(Player.coins.desc()).limit(20).all()
            title = "💎 <b>Топ игроков по балансу</b>\n\n"
        else:
            players = dbs.query(Player).order_by(Player.user_id.desc()).limit(20).all()
            title = "📋 <b>Список игроков</b> (последние 20)\n\n"
        
        text = title
        
        if players:
            for idx, player in enumerate(players, 1):
                username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
                vip_status = ""
                if player.vip_plus_until and current_time < player.vip_plus_until:
                    vip_status = " ⭐VIP+"
                elif player.vip_until and current_time < player.vip_until:
                    vip_status = " 💎VIP"
                text += f"{idx}. {username_display}{vip_status}\n"
                text += f"   💰 <b>{player.coins}</b> септимов\n\n"
        else:
            text += "<i>Игроки не найдены</i>\n\n"
    finally:
        dbs.close()
    
    keyboard = [
        [InlineKeyboardButton("💎 VIP игроки", callback_data='admin_players_list:vip')],
        [InlineKeyboardButton("⭐ VIP+ игроки", callback_data='admin_players_list:vip_plus')],
        [InlineKeyboardButton("🏆 Топ по балансу", callback_data='admin_players_list:top')],
        [InlineKeyboardButton("📋 Все игроки", callback_data='admin_players_list:all')],
        [InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_players_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ игроков."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        top_players = dbs.query(Player).order_by(Player.coins.desc()).limit(10).all()
        
        text = "🏆 <b>Топ 10 игроков по балансу</b>\n\n"
        
        if top_players:
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            current_time = int(time.time())
            
            for idx, player in enumerate(top_players):
                medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
                username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
                vip_status = ""
                if player.vip_plus_until and current_time < player.vip_plus_until:
                    vip_status = " ⭐VIP+"
                elif player.vip_until and current_time < player.vip_until:
                    vip_status = " 💎VIP"
                
                text += f"{medal} {username_display}{vip_status}\n"
                text += f"   💰 <b>{player.coins:,}</b> септимов\n\n"
        else:
            text += "<i>Игроки не найдены</i>\n\n"
    finally:
        dbs.close()
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_players_top')],
        [InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_player_details(update: Update, context: ContextTypes.DEFAULT_TYPE, player_id: int = None):
    """Показывает детальную информацию об игроке."""
    query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
    
    # Если это callback с данными
    if query and query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        if query:
            await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    user = query.from_user if query else update.effective_user
    if not has_creator_panel_access(user.id, user.username):
        if query:
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        
        if not player:
            text = f"❌ Игрок с ID {player_id} не найден!"
            keyboard = [[InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query:
                try:
                    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
                except BadRequest:
                    pass
            else:
                await update.message.reply_html(text, reply_markup=reply_markup)
            return
        
        # Получаем дополнительную информацию
        inventory = db.get_player_inventory_with_details(player_id)
        inventory_count = len(inventory)
        
        current_time = int(time.time())
        vip_status = "Нет"
        if player.vip_plus_until and current_time < player.vip_plus_until:
            vip_status = f"⭐ VIP+ до {safe_format_timestamp(player.vip_plus_until)}"
        elif player.vip_until and current_time < player.vip_until:
            vip_status = f"💎 VIP до {safe_format_timestamp(player.vip_until)}"
        
        last_bonus = safe_format_timestamp(player.last_bonus_claim) if player.last_bonus_claim else "Никогда"
        last_search = safe_format_timestamp(player.last_search) if player.last_search else "Никогда"
        
        # Проверяем, является ли игрок админом
        admin_level = db.get_admin_level(player_id)
        admin_status = f"Уровень {admin_level}" if admin_level > 0 else "Нет"
        
        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        
        text = (
            f"👤 <b>Информация об игроке</b>\n\n"
            f"<b>Username:</b> {username_display}\n"
            f"<b>ID:</b> <code>{player.user_id}</code>\n"
            f"<b>Баланс:</b> <b>{player.coins:,}</b> 🪙\n"
            f"<b>Рейтинг:</b> <b>{int(getattr(player, 'rating', 0) or 0)}</b> ⭐\n"
            f"<b>Инвентарь:</b> {inventory_count} предметов\n"
            f"<b>VIP статус:</b> {vip_status}\n"
            f"<b>Админ:</b> {admin_status}\n"
            f"<b>Последний поиск:</b> {last_search}\n"
            f"<b>Последний бонус:</b> {last_bonus}\n"
            f"<b>Язык:</b> {player.language}\n"
            f"<b>Автопоиск:</b> {'✅' if player.auto_search_enabled else '❌'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("💰 Изменить баланс", callback_data=f'admin_player_balance:{player_id}')],
            [InlineKeyboardButton("⭐ Изменить рейтинг", callback_data=f'admin_player_rating:{player_id}')],
            [InlineKeyboardButton("💎 Управление VIP", callback_data=f'admin_player_vip:{player_id}')],
            [InlineKeyboardButton("👥 Селюки игрока", callback_data=f'admin_player_selyuki:{player_id}')],
            [InlineKeyboardButton("📝 Логи игрока", callback_data=f'admin_player_logs:{player_id}')],
            [InlineKeyboardButton("🔄 Сбросить бонус", callback_data=f'admin_player_reset_bonus:{player_id}')],
            [InlineKeyboardButton("🔙 Управление игроками", callback_data='admin_players_menu')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            try:
                await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                pass
        else:
            await update.message.reply_html(text, reply_markup=reply_markup)
    finally:
        dbs.close()


async def admin_player_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс изменения баланса игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем player_id из callback_data
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    context.user_data['admin_player_action'] = 'balance'
    context.user_data['admin_player_id'] = player_id
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if player:
            username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
            text = (
                f"💰 <b>Изменение баланса</b>\n\n"
                f"Игрок: {username_display}\n"
                f"Текущий баланс: <b>{player.coins:,}</b> 🪙\n\n"
                f"Отправьте новое количество монет или изменение:\n"
                f"• <code>1000</code> - установить баланс\n"
                f"• <code>+500</code> - добавить\n"
                f"• <code>-200</code> - убрать\n\n"
                f"Или нажмите Отмена"
            )
        else:
            text = "❌ Игрок не найден!"
    finally:
        dbs.close()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f'admin_player_details:{player_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_player_vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления VIP для конкретного игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем player_id из callback_data
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            await query.answer("❌ Игрок не найден", show_alert=True)
            return
        
        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        current_time = int(time.time())
        
        vip_status = "Нет"
        if player.vip_plus_until and current_time < player.vip_plus_until:
            vip_status = f"⭐ VIP+ до {safe_format_timestamp(player.vip_plus_until)}"
        elif player.vip_until and current_time < player.vip_until:
            vip_status = f"💎 VIP до {safe_format_timestamp(player.vip_until)}"
        
        text = (
            f"💎 <b>Управление VIP</b>\n\n"
            f"Игрок: {username_display}\n"
            f"Текущий статус: {vip_status}\n\n"
            f"Выберите действие:"
        )
    finally:
        dbs.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Выдать VIP", callback_data=f'admin_player_vip_give:{player_id}')],
        [InlineKeyboardButton("➕ Выдать VIP+", callback_data=f'admin_player_vip_plus_give:{player_id}')],
        [InlineKeyboardButton("❌ Отозвать VIP", callback_data=f'admin_player_vip_remove:{player_id}')],
        [InlineKeyboardButton("❌ Отозвать VIP+", callback_data=f'admin_player_vip_plus_remove:{player_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data=f'admin_player_details:{player_id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_player_logs_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи конкретного игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем player_id из callback_data
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            await query.answer("❌ Игрок не найден", show_alert=True)
            return
        
        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        logs = db.get_user_logs(player_id, limit=15)
        
        text = f"📝 <b>Логи игрока {username_display}</b>\n\n"
        
        if logs:
            for log in logs:
                status = "✅" if log['success'] else "❌"
                timestamp_str = safe_format_timestamp(log['timestamp'])
                text += f"{status} <i>{log['action_type']}</i>\n"
                if log['action_details']:
                    text += f"├ {log['action_details'][:50]}\n"
                if log['amount']:
                    sign = "+" if log['amount'] > 0 else ""
                    text += f"├ {sign}{log['amount']} 💰\n"
                text += f"└ {timestamp_str}\n\n"
        else:
            text += "<i>Логов для этого игрока пока нет</i>"
    finally:
        dbs.close()
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f'admin_player_details:{player_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_player_selyuki_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает селюков конкретного игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем player_id из callback_data
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            username_display = f"ID: {player_id}"
        else:
            username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        
        # Получаем селюков игрока
        selyuki = db.get_player_selyuki(player_id)
        
        text = f"👥 <b>СЕЛЮКИ ИГРОКА {username_display}</b>\n\n"
        
        if not selyuki:
            text += "<i>У игрока пока нет селюков.</i>"
        else:
            for s in selyuki:
                stype = str(getattr(s, 'type', '') or '')
                lvl = int(getattr(s, 'level', 1) or 1)
                bal = int(getattr(s, 'balance_septims', 0) or 0)
                enabled = bool(getattr(s, 'is_enabled', False))
                status = "✅ Вкл" if enabled else "🚫 Выкл"
                
                if stype == 'farmer':
                    text += f"👨‍🌾 <b>Селюк фермер</b>\n"
                elif stype == 'silkmaker':
                    text += f"🧵 <b>Селюк шёлковод</b>\n"
                elif stype == 'trickster':
                    text += f"🧮 <b>Селюк махинаций</b>\n"
                elif stype == 'buyer':
                    text += f"🛒 <b>Селюк покупатель</b>\n"
                elif stype == 'boss':
                    text += f"👑 <b>Босс селюков</b>\n"
                else:
                    text += f"❓ <b>Неизвестный тип</b> ({stype})\n"
                
                text += f"   • Уровень: {lvl}\n"
                text += f"   • Баланс: {bal:,} 💎\n"
                text += f"   • Статус: {status}\n\n"
    finally:
        dbs.close()
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f'admin_player_details:{player_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_player_reset_bonus_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет сброс бонуса для конкретного игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем player_id из callback_data
    player_id = None
    if query.data and ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1:
            try:
                player_id = int(parts[1])
            except ValueError:
                pass
    
    if not player_id:
        await query.answer("❌ Ошибка: ID игрока не указан", show_alert=True)
        return
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == player_id).first()
        if not player:
            await query.answer("❌ Игрок не найден", show_alert=True)
            return
        
        db.update_player(player_id, last_bonus_claim=0)
        username_display = f"@{player.username}" if player.username else f"ID: {player.user_id}"
        
        await query.answer(f"✅ Бонус сброшен для {username_display}!", show_alert=False)
        
        # Обновляем страницу игрока
        await show_player_details(update, context, player_id)
    finally:
        dbs.close()


async def show_admin_vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления VIP."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Выдать VIP", callback_data='admin_vip_give')],
        [InlineKeyboardButton("➕ Выдать VIP+", callback_data='admin_vip_plus_give')],
        [InlineKeyboardButton("❌ Отозвать VIP", callback_data='admin_vip_remove')],
        [InlineKeyboardButton("❌ Отозвать VIP+", callback_data='admin_vip_plus_remove')],
        [InlineKeyboardButton("📋 Список VIP", callback_data='admin_vip_list')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "💎 <b>Управление VIP</b>\n\n"
        "Выберите действие:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления складом."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    logger.info(f"[ADMIN_STOCK] Пользователь {user.id} (@{user.username}) открывает меню склада")
    
    if not has_creator_panel_access(user.id, user.username):
        logger.warning(f"[ADMIN_STOCK] Отказ в доступе для пользователя {user.id}")
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    try:
        # Получаем информацию о складе
        logger.info("[ADMIN_STOCK] Получаем информацию о складе...")
        stock_info = db.get_stock_info()
        logger.info(f"[ADMIN_STOCK] Получено записей о складе: {len(stock_info)}")
        
        text = "📦 <b>Управление складом</b>\n\n"
        text += "<b>Текущие остатки:</b>\n"
        
        if stock_info:
            for kind, amount in stock_info.items():
                text += f"• {kind}: <b>{amount}</b>\n"
        else:
            text += "<i>Склад пуст или данные недоступны</i>\n"
        
        text += "\n<b>Для изменения склада:</b>\n"
        text += "• <code>/stockset &lt;вид&gt; &lt;количество&gt;</code>\n"
        text += "• <code>/stockadd &lt;вид&gt; &lt;число&gt;</code>\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data='admin_stock_menu')],
            [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest as e:
            logger.warning(f"Не удалось отредактировать сообщение склада: {e}")
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка в show_admin_stock_menu: {e}")
        await query.answer("❌ Произошла ошибка при загрузке склада", show_alert=True)


async def show_admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню рассылки."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    total_users = db.get_total_users_count()
    
    keyboard = [
        [InlineKeyboardButton("📢 Начать рассылку", callback_data='admin_broadcast_start')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "📢 <b>Рассылка сообщений</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n\n"
        "⚠️ <b>Внимание!</b>\n"
        "Рассылка отправит сообщение всем пользователям бота.\n"
        "Используйте эту функцию осторожно!\n\n"
        "Нажмите кнопку ниже, чтобы начать."
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс рассылки."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "📝 <b>Создание рассылки</b>\n\n"
        "Отправьте <b>текст</b> для рассылки\n"
        "или загрузите <b>аудио (музыку)</b> с подписью.\n"
        "Поддерживается HTML-разметка в подписи.\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'broadcast'


async def admin_vip_give_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс выдачи VIP."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "➕ <b>Выдача VIP</b>\n\n"
        "Отправьте в формате:\n"
        "<code>@username дни</code> или <code>дни @username</code>\n"
        "<code>user_id дни</code> также подходит\n\n"
        "Пример: <code>@user 30</code> или <code>30 @user</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'vip_give'


async def admin_vip_plus_give_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс выдачи VIP+."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "➕ <b>Выдача VIP+</b>\n\n"
        "Отправьте в формате:\n"
        "<code>@username дни</code> или <code>дни @username</code>\n"
        "<code>user_id дни</code> также подходит\n\n"
        "Пример: <code>@user 30</code> или <code>30 @user</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'vip_plus_give'


async def admin_vip_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс отзыва VIP."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "❌ <b>Отзыв VIP</b>\n\n"
        "Отправьте <code>@username</code> пользователя\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'vip_remove'


async def admin_vip_plus_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс отзыва VIP+."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "❌ <b>Отзыв VIP+</b>\n\n"
        "Отправьте <code>@username</code> пользователя\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_vip_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_creator_action'] = 'vip_plus_remove'


async def admin_vip_list_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список VIP пользователей."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем всех VIP пользователей
    dbs = db.SessionLocal()
    try:
        current_time = int(time.time())
        vip_users = dbs.query(db.Player).filter(db.Player.vip_until > current_time).order_by(db.Player.vip_until.desc()).limit(20).all()
        vip_plus_users = dbs.query(db.Player).filter(db.Player.vip_plus_until > current_time).order_by(db.Player.vip_plus_until.desc()).limit(20).all()
    finally:
        dbs.close()
    
    text = "📋 <b>Список VIP пользователей</b>\n\n"
    
    if vip_plus_users:
        text += "<b>💎 VIP+:</b>\n"
        for p in vip_plus_users[:10]:
            username_display = f"@{p.username}" if p.username else f"ID:{p.user_id}"
            until_str = safe_format_timestamp(p.vip_plus_until)
            text += f"• {username_display} до {until_str}\n"
        if len(vip_plus_users) > 10:
            text += f"<i>...и ещё {len(vip_plus_users) - 10}</i>\n"
        text += "\n"
    else:
        text += "<b>💎 VIP+:</b> <i>нет</i>\n\n"
    
    if vip_users:
        text += "<b>💎 VIP:</b>\n"
        for p in vip_users[:10]:
            username_display = f"@{p.username}" if p.username else f"ID:{p.user_id}"
            until_str = safe_format_timestamp(p.vip_until)
            text += f"• {username_display} до {until_str}\n"
        if len(vip_users) > 10:
            text += f"<i>...и ещё {len(vip_users) - 10}</i>\n"
    else:
        text += "<b>💎 VIP:</b> <i>нет</i>\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Управление VIP", callback_data='admin_vip_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


# --- Расширенная аналитика ---

async def show_admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает расширенную аналитику бота."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    try:
        # Получаем полную статистику
        stats = db.get_bot_statistics()
        boost_stats = db.get_boost_statistics()
        
        # Основная статистика
        total_users = stats.get('total_users', db.get_total_users_count())
        total_drinks = stats.get('total_drinks', db.get_total_drinks_count())
        total_items_in_inventories = stats.get('total_inventory_items', db.get_total_inventory_items())
        total_coins = stats.get('total_coins', db.get_total_coins_in_system())
        
        # VIP статистика
        active_vip = stats.get('active_vip', db.get_active_vip_count())
        active_vip_plus = stats.get('active_vip_plus', db.get_active_vip_plus_count())
        
        # Активность
        active_today = stats.get('active_today', db.get_active_users_today())
        active_week = stats.get('active_week', db.get_active_users_week())
        
        # Покупки
        total_purchases = stats.get('total_purchases', 0)
        purchases_today = stats.get('purchases_today', 0)
        
        # Бусты
        active_boosts = boost_stats.get('active_boosts', 0)
        expired_boosts = boost_stats.get('expired_boosts', 0)
        avg_boost_count = boost_stats.get('average_boost_count', 0)
        
        # Дополнительная статистика
        active_promo = db.get_active_promo_count()
        banned_users = db.get_banned_users_count()
        active_events = db.get_active_events_count()
        
        # Экономика
        avg_coins = total_coins // total_users if total_users > 0 else 0
        active_percent = round((active_today / total_users * 100), 1) if total_users > 0 else 0
        vip_percent = round(((active_vip + active_vip_plus) / total_users * 100), 1) if total_users > 0 else 0
        
        # Топ игроков
        top_coins = stats.get('top_coins', [])[:5]
        top_drinks = stats.get('top_drinks', [])[:5]
        
        # Формируем текст с расширенной аналитикой
        text = (
            "📊 <b>Расширенная аналитика</b>\n\n"
            
            "👥 <b>Пользователи:</b>\n"
            f"├ Всего пользователей: <b>{total_users:,}</b>\n"
            f"├ Активных сегодня: <b>{active_today:,}</b> ({active_percent}%)\n"
            f"├ Активных за неделю: <b>{active_week:,}</b>\n"
            f"└ Заблокированных: <b>{banned_users:,}</b>\n\n"
            
            "💎 <b>VIP статистика:</b>\n"
            f"├ VIP активных: <b>{active_vip:,}</b>\n"
            f"├ VIP+ активных: <b>{active_vip_plus:,}</b>\n"
            f"└ Всего VIP: <b>{active_vip + active_vip_plus:,}</b> ({vip_percent}%)\n\n"
            
            "🥤 <b>Энергетики:</b>\n"
            f"├ Всего видов напитков: <b>{total_drinks:,}</b>\n"
            f"└ Предметов в инвентарях: <b>{total_items_in_inventories:,}</b>\n\n"
            
            "💰 <b>Экономика:</b>\n"
            f"├ Всего монет в системе: <b>{total_coins:,}</b>\n"
            f"├ Среднее у игрока: <b>{avg_coins:,}</b>\n"
            f"├ Всего покупок: <b>{total_purchases:,}</b>\n"
            f"└ Покупок сегодня: <b>{purchases_today:,}</b>\n\n"
            
            "⚡ <b>Бусты автопоиска:</b>\n"
            f"├ Активных бустов: <b>{active_boosts:,}</b>\n"
            f"├ Истёкших бустов: <b>{expired_boosts:,}</b>\n"
            f"└ Среднее кол-во: <b>{avg_boost_count}</b>\n\n"
            
            "🎯 <b>Дополнительно:</b>\n"
            f"├ Активных промокодов: <b>{active_promo:,}</b>\n"
            f"└ Активных событий: <b>{active_events:,}</b>\n"
        )
        
        # Добавляем топ игроков, если есть данные
        if top_coins:
            text += "\n🏆 <b>Топ-5 по монетам:</b>\n"
            for i, (user_id, username, coins) in enumerate(top_coins, 1):
                display_name = f"@{username}" if username and username != str(user_id) else f"ID:{user_id}"
                text += f"{i}. {display_name}: <b>{coins:,}</b>\n"
        
        if top_drinks:
            text += "\n🥤 <b>Топ-5 по напиткам:</b>\n"
            for i, (user_id, username, drinks) in enumerate(top_drinks, 1):
                display_name = f"@{username}" if username and username != str(user_id) else f"ID:{user_id}"
                text += f"{i}. {display_name}: <b>{drinks:,}</b>\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data='admin_analytics')],
            [InlineKeyboardButton("📈 Экспорт данных", callback_data='admin_analytics_export')],
            [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    except Exception as e:
        logger.error(f"Ошибка в show_admin_analytics: {e}")
        await query.answer("❌ Ошибка при загрузке аналитики", show_alert=True)


async def export_admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует данные аналитики в текстовом формате."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    try:
        from datetime import datetime
        import time
        
        # Получаем статистику
        stats = db.get_bot_statistics()
        boost_stats = db.get_boost_statistics()
        
        # Основная статистика
        total_users = stats.get('total_users', db.get_total_users_count())
        total_drinks = stats.get('total_drinks', db.get_total_drinks_count())
        total_items_in_inventories = stats.get('total_inventory_items', db.get_total_inventory_items())
        total_coins = stats.get('total_coins', db.get_total_coins_in_system())
        
        # VIP статистика
        active_vip = stats.get('active_vip', db.get_active_vip_count())
        active_vip_plus = stats.get('active_vip_plus', db.get_active_vip_plus_count())
        
        # Активность
        active_today = stats.get('active_today', db.get_active_users_today())
        active_week = stats.get('active_week', db.get_active_users_week())
        
        # Покупки
        total_purchases = stats.get('total_purchases', 0)
        purchases_today = stats.get('purchases_today', 0)
        
        # Бусты
        active_boosts = boost_stats.get('active_boosts', 0)
        expired_boosts = boost_stats.get('expired_boosts', 0)
        avg_boost_count = boost_stats.get('average_boost_count', 0)
        
        # Дополнительная статистика
        active_promo = db.get_active_promo_count()
        banned_users = db.get_banned_users_count()
        active_events = db.get_active_events_count()
        
        # Экономика
        avg_coins = total_coins // total_users if total_users > 0 else 0
        active_percent = round((active_today / total_users * 100), 1) if total_users > 0 else 0
        vip_percent = round(((active_vip + active_vip_plus) / total_users * 100), 1) if total_users > 0 else 0
        
        # Топ игроков
        top_coins = stats.get('top_coins', [])[:10]
        top_drinks = stats.get('top_drinks', [])[:10]
        
        # Формируем экспортируемые данные
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        export_text = (
            f"📊 ЭКСПОРТ АНАЛИТИКИ БОТА\n"
            f"Дата экспорта: {timestamp}\n"
            f"{'='*50}\n\n"
            
            f"👥 ПОЛЬЗОВАТЕЛИ:\n"
            f"├ Всего пользователей: {total_users:,}\n"
            f"├ Активных сегодня: {active_today:,} ({active_percent}%)\n"
            f"├ Активных за неделю: {active_week:,}\n"
            f"└ Заблокированных: {banned_users:,}\n\n"
            
            f"💎 VIP СТАТИСТИКА:\n"
            f"├ VIP активных: {active_vip:,}\n"
            f"├ VIP+ активных: {active_vip_plus:,}\n"
            f"└ Всего VIP: {active_vip + active_vip_plus:,} ({vip_percent}%)\n\n"
            
            f"🥤 ЭНЕРГЕТИКИ:\n"
            f"├ Всего видов напитков: {total_drinks:,}\n"
            f"└ Предметов в инвентарях: {total_items_in_inventories:,}\n\n"
            
            f"💰 ЭКОНОМИКА:\n"
            f"├ Всего монет в системе: {total_coins:,}\n"
            f"├ Среднее у игрока: {avg_coins:,}\n"
            f"├ Всего покупок: {total_purchases:,}\n"
            f"└ Покупок сегодня: {purchases_today:,}\n\n"
            
            f"⚡ БУСТЫ АВТОПОИСКА:\n"
            f"├ Активных бустов: {active_boosts:,}\n"
            f"├ Истёкших бустов: {expired_boosts:,}\n"
            f"└ Среднее кол-во: {avg_boost_count}\n\n"
            
            f"🎯 ДОПОЛНИТЕЛЬНО:\n"
            f"├ Активных промокодов: {active_promo:,}\n"
            f"└ Активных событий: {active_events:,}\n\n"
        )
        
        # Добавляем топ игроков
        if top_coins:
            export_text += f"🏆 ТОП-10 ПО МОНЕТАМ:\n"
            for i, (user_id, username, coins) in enumerate(top_coins, 1):
                display_name = f"@{username}" if username and username != str(user_id) else f"ID:{user_id}"
                export_text += f"{i}. {display_name}: {coins:,}\n"
            export_text += "\n"
        
        if top_drinks:
            export_text += f"🥤 ТОП-10 ПО НАПИТКАМ:\n"
            for i, (user_id, username, drinks) in enumerate(top_drinks, 1):
                display_name = f"@{username}" if username and username != str(user_id) else f"ID:{user_id}"
                export_text += f"{i}. {display_name}: {drinks:,}\n"
        
        # Отправляем как сообщение (Telegram имеет лимит на длину сообщения)
        if len(export_text) > 4096:
            # Если текст слишком длинный, отправляем частями
            parts = [export_text[i:i+4096] for i in range(0, len(export_text), 4096)]
            for part in parts:
                await query.message.reply_text(f"<pre>{part}</pre>", parse_mode='HTML')
        else:
            await query.message.reply_text(f"<pre>{export_text}</pre>", parse_mode='HTML')
        
        await query.answer("✅ Данные экспортированы!", show_alert=False)
        
    except Exception as e:
        logger.error(f"Ошибка в export_admin_analytics: {e}")
        await query.answer("❌ Ошибка при экспорте данных", show_alert=True)


# --- Управление энергетиками ---

async def show_admin_drinks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления энергетиками."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    context.user_data.pop('awaiting_admin_action', None)
    context.user_data.pop('edit_drink_id', None)
    context.user_data.pop('pending_rename', None)
    context.user_data.pop('pending_redesc', None)
    context.user_data.pop('pending_photo', None)
    
    total_drinks = db.get_total_drinks_count()
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить энергетик", callback_data='admin_drink_add')],
        [InlineKeyboardButton("🖼 Обновить фото", callback_data='admin_drink_update_photo')],
        [InlineKeyboardButton("✏️ Изм. название", callback_data='admin_drink_rename')],
        [InlineKeyboardButton("📝 Изм. описание", callback_data='admin_drink_redesc')],
        [InlineKeyboardButton("❌ Удалить", callback_data='admin_drink_delete')],
        [InlineKeyboardButton("📋 Список всех", callback_data='admin_drink_list')],
        [InlineKeyboardButton("🔍 Поиск", callback_data='admin_drink_search')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🔧 <b>Управление энергетиками</b>\n\n"
        f"📊 Всего напитков в базе: <b>{total_drinks}</b>\n\n"
        "Выберите действие:"
    )
    
    try:
        message = query.message
        if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
            try:
                await message.delete()
            except BadRequest:
                pass
            await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_drink_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления энергетика."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "➕ <b>Добавление энергетика</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>Название | Описание | Специальный</code>\n\n"
        "Пример:\n"
        "<code>Red Bull | Классический энергетик | нет</code>\n\n"
        "Специальный: <code>да</code> или <code>нет</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'drink_add'


async def admin_drink_list_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех энергетиков с пагинацией."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    # Получаем номер страницы
    data = query.data
    page = 1
    if data.startswith('admin_drink_list_p'):
        try:
            page = int(data.split('_')[-1])
        except:
            page = 1
    
    # Получаем список напитков
    result = db.get_all_drinks_paginated(page=page, page_size=15)
    drinks = result['drinks']
    total = result['total']
    total_pages = result['total_pages']
    
    text = f"📋 <b>Список энергетиков</b>\n\n"
    text += f"Страница <b>{page}</b> из <b>{total_pages}</b>\n"
    text += f"Всего напитков: <b>{total}</b>\n\n"
    
    if drinks:
        for drink in drinks:
            special = "⭐" if drink['is_special'] else ""
            img = "🖼️" if drink['has_image'] else ""
            text += f"{special}{img} <b>{drink['name']}</b> (ID: {drink['id']})\n"
            text += f"<i>{drink['description'][:50]}...</i>\n\n"
    else:
        text += "<i>Напитков не найдено</i>"
    
    # Формируем кнопки пагинации
    keyboard = []
    
    # Навигация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'admin_drink_list_p{page-1}'))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f'admin_drink_list_p{page+1}'))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("🔙 Управление энергетиками", callback_data='admin_drinks_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_drink_list_show_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    drinks = db.get_all_drinks()
    if not drinks:
        try:
            await query.message.reply_text("В базе данных нет энергетиков.")
        except BadRequest:
            pass
        return

    drinks_sorted = sorted(drinks, key=lambda d: d.id)
    lines = [f"{d.id}: {d.name}" for d in drinks_sorted]
    header = f"Всего энергетиков: {len(lines)}\n"
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > 3500:
            try:
                await query.message.reply_text(chunk.rstrip())
            except BadRequest:
                pass
            chunk = ""
        chunk += line + "\n"
    if chunk:
        try:
            await query.message.reply_text(chunk.rstrip())
        except BadRequest:
            pass


async def admin_drink_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс поиска энергетика."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "🔍 <b>Поиск энергетика</b>\n\n"
        "Отправьте название или часть названия напитка для поиска\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'drink_search'


async def admin_drink_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс редактирования энергетика."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "✏️ <b>Редактирование энергетика</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>ID | Новое название | Новое описание | Специальный</code>\n\n"
        "Пример:\n"
        "<code>5 | Red Bull Gold | Золотая версия | да</code>\n\n"
        "Чтобы не изменять поле, используйте <code>-</code>\n"
        "Пример: <code>5 | - | Новое описание | -</code>\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'drink_edit'


async def admin_drink_rename_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    text = (
        "✏️ <b>Изменение названия</b>\n\n"
        "Отправьте <b>ID</b> энергетика для изменения названия\n\n"
        "Или нажмите Отмена"
    )
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'drink_rename_id'


async def admin_drink_redesc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    text = (
        "📝 <b>Изменение описания</b>\n\n"
        "Отправьте <b>ID</b> энергетика для изменения описания\n\n"
        "Или нажмите Отмена"
    )
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'drink_redesc_id'


async def admin_drink_update_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    text = (
        "🖼 <b>Обновление фото</b>\n\n"
        "Отправьте <b>ID</b> энергетика, затем бот попросит прислать фото.\n\n"
        "Или нажмите Отмена"
    )
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'drink_update_photo_id'


async def admin_drink_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс удаления энергетика."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "❌ <b>Удаление энергетика</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Удаление напитка также удалит его из всех инвентарей игроков!\n\n"
        "Отправьте <b>ID</b> энергетика для удаления\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_drinks_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'drink_delete'


async def admin_promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    text = (
        "🎁 <b>Создание промокода</b>\n\n"
        "Формат общий:\n"
        "<code>CODE | kind | value | max_uses | per_user_limit | expires(YYYY-MM-DD HH:MM или -) | active(да/нет)</code>\n\n"
        "Для kind = <b>drink</b> используйте <b>8 полей</b> (value = DRINK_ID):\n"
        "<code>CODE | drink | DRINK_ID | max_uses | per_user_limit | expires | active | rarity</code>\n\n"
        "rarity можно указать как <code>-</code>, чтобы использовать встроенную редкость энергетика (default_rarity).\n"
        "Иначе: " + ", ".join(list(RARITIES.keys()))
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'promo_create'


async def admin_promo_list_active_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    promos = db.list_promos(active_only=True)
    lines = ["🎁 <b>Активные промокоды</b>\n"]
    if promos:
        for p in promos[:50]:
            exp = p['expires_at']
            exp_str = safe_format_timestamp(exp) if exp else '—'
            extra = f" rarity={p.get('rarity') or '-'}" if str(p.get('kind','')).lower() == 'drink' else ''
            lines.append(f"• <b>{p['code']}</b> [{p['kind']}] val={p['value']}{extra} used={p['used']}/{p['max_uses'] or '∞'} per_user={p['per_user_limit'] or '∞'} exp={exp_str}")
    else:
        lines.append("<i>Нет активных промокодов</i>")
    lines.append("\n")
    keyboard = [[InlineKeyboardButton("🔙 Промокоды", callback_data='admin_promo_menu')]]
    try:
        await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_promo_list_all_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    promos = db.list_promos(active_only=False)
    lines = ["🎁 <b>Все промокоды</b>\n"]
    if promos:
        for p in promos[:100]:
            exp = p['expires_at']
            exp_str = safe_format_timestamp(exp) if exp else '—'
            active_mark = '✅' if p['active'] else '❌'
            extra = f" rarity={p.get('rarity') or '-'}" if str(p.get('kind','')).lower() == 'drink' else ''
            lines.append(f"{active_mark} <b>{p['code']}</b> [{p['kind']}] val={p['value']}{extra} used={p['used']}/{p['max_uses'] or '∞'} per_user={p['per_user_limit'] or '∞'} exp={exp_str}")
    else:
        lines.append("<i>Промокодов нет</i>")
    lines.append("\n")
    keyboard = [[InlineKeyboardButton("🔙 Промокоды", callback_data='admin_promo_menu')]]
    try:
        await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_promo_deactivate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    text = (
        "❌ <b>Деактивация промокода</b>\n\n"
        "Отправьте <code>ID</code> или <code>CODE</code> промокода"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'promo_deactivate'


async def admin_promo_stats_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    active_count = db.get_active_promo_count()
    usage_total = db.get_promo_usage_total()
    text = (
        "📈 <b>Статистика промокодов</b>\n\n"
        f"Активных промокодов: <b>{active_count}</b>\n"
        f"Всего активаций: <b>{usage_total}</b>"
    )
    keyboard = [[InlineKeyboardButton("🔙 Промокоды", callback_data='admin_promo_menu')]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass


async def handle_promo_create(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    parts = [p.strip() for p in text_input.split('|')]
    keyboard = [[InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')]]
    if len(parts) not in (7, 8):
        await update.message.reply_html("❌ Неверный формат. См. подсказку вверху экрана.", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    code, kind = parts[0], parts[1]
    kind_l = kind.strip().lower()
    # Для drink ожидаем 8 полей (включая rarity)
    if kind_l == 'drink' and len(parts) != 8:
        await update.message.reply_html("❌ Для kind=drink укажите 8 полей: CODE | drink | DRINK_ID | max_uses | per_user_limit | expires | active | rarity", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if kind_l == 'drink':
        value_s, max_uses_s, per_user_s, expires_s, active_s, rarity_s = parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    else:
        value_s, max_uses_s, per_user_s, expires_s, active_s = parts[2], parts[3], parts[4], parts[5], parts[6]
        rarity_s = None
    try:
        value = int(value_s)
        max_uses = int(max_uses_s)
        per_user = int(per_user_s)
        if expires_s == '-':
            expires = None
        else:
            try:
                from datetime import datetime
                expires = int(datetime.strptime(expires_s, "%Y-%m-%d %H:%M").timestamp())
            except Exception:
                await update.message.reply_html("❌ Неверная дата. Формат: YYYY-MM-DD HH:MM", reply_markup=InlineKeyboardMarkup(keyboard))
                return
        active = active_s.lower() in ['да', 'yes', 'true', '1']
        # Валидация rarity для drink
        rarity_final = None
        if kind_l == 'drink':
            # Разрешённые значения — ключи RARITIES (без учёта регистра)
            valid = list(RARITIES.keys())
            if not rarity_s:
                await update.message.reply_html("❌ Укажите rarity для drink. Доступно: " + ", ".join(valid) + " или <code>-</code> (встроенная)", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            if rarity_s.strip() == '-':
                rarity_final = None
            else:
                rarity_map = {r.lower(): r for r in valid}
                rarity_final = rarity_map.get(rarity_s.strip().lower())
                if not rarity_final:
                    await update.message.reply_html("❌ Неверная rarity. Доступно: " + ", ".join(valid) + " или <code>-</code>", reply_markup=InlineKeyboardMarkup(keyboard))
                    return
        res = db.create_promo(code, kind, value, max_uses, per_user, expires, active, rarity=rarity_final)
        if res.get('ok'):
            ok_suffix = f" (rarity: {rarity_final})" if rarity_final else (" (rarity: встроенная)" if kind_l == 'drink' else "")
            await update.message.reply_html(f"✅ Создан промокод <b>{code}</b>{ok_suffix}", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            reason = res.get('reason')
            await update.message.reply_html(f"❌ Ошибка создания: {reason}", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await update.message.reply_html("❌ Ошибка обработки входных данных", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_promo_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = [[InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')]]
    s = text_input.strip()
    ok = False
    try:
        pid = int(s)
        ok = db.deactivate_promo_by_id(pid)
    except Exception:
        ok = db.deactivate_promo_by_code(s)
    await update.message.reply_html("✅ Деактивирован" if ok else "❌ Не найден", reply_markup=InlineKeyboardMarkup(keyboard))


def _gen_promo_code(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(int(length)))


async def admin_promo_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    context.user_data['promo_wiz'] = {}
    context.user_data['awaiting_admin_action'] = 'promo_wiz_code'
    text = (
        "🧙 <b>Мастер создания промокода</b>\n\n"
        "Шаг 1/6: отправьте <b>код</b> промокода\n"
        "• Можно написать <code>-</code>, чтобы я сгенерировал код автоматически"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
        [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def handle_promo_wiz_code(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
        [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')],
    ])
    code = (text_input or '').strip()
    if code == '-':
        code = _gen_promo_code(10)
    if not code or len(code) < 3:
        await update.message.reply_html("❌ Код слишком короткий. Отправьте другой код (минимум 3 символа) или <code>-</code> для генерации.", reply_markup=keyboard)
        return
    wiz = context.user_data.get('promo_wiz') or {}
    wiz['code'] = code
    context.user_data['promo_wiz'] = wiz
    context.user_data.pop('awaiting_admin_action', None)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Монеты", callback_data='promo_wiz_kind:coins'),
            InlineKeyboardButton("👑 VIP", callback_data='promo_wiz_kind:vip'),
        ],
        [
            InlineKeyboardButton("💎 VIP+", callback_data='promo_wiz_kind:vip_plus'),
            InlineKeyboardButton("🥤 Энергетик", callback_data='promo_wiz_kind:drink'),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    text = (
        "🧙 <b>Мастер создания промокода</b>\n\n"
        f"Код: <code>{html.escape(code)}</code>\n\n"
        "Шаг 2/6: выберите тип награды (kind)"
    )
    await update.message.reply_html(text, reply_markup=kb)


async def promo_wiz_kind_select(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    wiz = context.user_data.get('promo_wiz') or {}
    wiz['kind'] = str(kind).strip().lower()
    wiz.pop('rarity', None)
    context.user_data['promo_wiz'] = wiz
    context.user_data['awaiting_admin_action'] = 'promo_wiz_value'
    hint = "монеты" if wiz['kind'] == 'coins' else ("дни VIP" if wiz['kind'] == 'vip' else ("дни VIP+" if wiz['kind'] == 'vip_plus' else "ID энергетика"))
    text = (
        "🧙 <b>Мастер создания промокода</b>\n\n"
        f"Код: <code>{html.escape(str(wiz.get('code','')))}</code>\n"
        f"Тип: <b>{html.escape(wiz['kind'])}</b>\n\n"
        f"Шаг 3/6: отправьте значение (value) — <b>{hint}</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def handle_promo_wiz_value(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    wiz = context.user_data.get('promo_wiz') or {}
    kind = str(wiz.get('kind') or '').strip().lower()
    try:
        value = int(str(text_input).strip())
    except Exception:
        await update.message.reply_html("❌ Значение должно быть числом.", reply_markup=keyboard)
        return
    if kind == 'coins' and value <= 0:
        await update.message.reply_html("❌ Монеты должны быть > 0.", reply_markup=keyboard)
        return
    if kind in ('vip', 'vip_plus') and value <= 0:
        await update.message.reply_html("❌ Дни должны быть > 0.", reply_markup=keyboard)
        return
    if kind == 'drink':
        d = db.get_drink_by_id(value)
        if not d:
            await update.message.reply_html("❌ Энергетик с таким ID не найден.", reply_markup=keyboard)
            return
    wiz['value'] = value
    context.user_data['promo_wiz'] = wiz
    if kind == 'drink':
        context.user_data.pop('awaiting_admin_action', None)
        # Реальные редкости берём из констант. "Встроенная" означает: rarity=None (будет использована default_rarity напитка)
        rarity_list = [r for r in RARITY_ORDER if r in COLOR_EMOJIS]
        kb_rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton("🏷️ Встроенная", callback_data='promo_wiz_rarity:__default__')]
        ]
        row: list[InlineKeyboardButton] = []
        for r in rarity_list:
            label = f"{COLOR_EMOJIS.get(r, '')} {r}".strip()
            row.append(InlineKeyboardButton(label, callback_data=f'promo_wiz_rarity:{r}'))
            if len(row) == 2:
                kb_rows.append(row)
                row = []
        if row:
            kb_rows.append(row)
        kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')])
        kb = InlineKeyboardMarkup(kb_rows)
        text = (
            "🧙 <b>Мастер создания промокода</b>\n\n"
            f"Код: <code>{html.escape(str(wiz.get('code','')))}</code>\n"
            f"Тип: <b>{html.escape(kind)}</b>\n"
            f"Drink ID: <b>{value}</b>\n\n"
            "Шаг 4/6: выберите редкость (rarity)"
        )
        await update.message.reply_html(text, reply_markup=kb)
        return
    context.user_data['awaiting_admin_action'] = 'promo_wiz_max_uses'
    await update.message.reply_html(
        "Шаг 4/6: отправьте <b>max_uses</b> (0 = без лимита)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')]])
    )


async def promo_wiz_rarity_select(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    wiz = context.user_data.get('promo_wiz') or {}
    r_in = str(rarity).strip()
    # Спец-значение: используем встроенную редкость напитка (default_rarity)
    if r_in == '__default__':
        wiz.pop('rarity', None)
        rarity_final = None
    else:
        valid = [r for r in RARITY_ORDER if r in COLOR_EMOJIS]
        rarity_map = {r.lower(): r for r in valid}
        rarity_final = rarity_map.get(r_in.lower())
        if not rarity_final:
            await query.answer("Неверная редкость", show_alert=True)
            return
        wiz['rarity'] = rarity_final
    context.user_data['promo_wiz'] = wiz
    context.user_data['awaiting_admin_action'] = 'promo_wiz_max_uses'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    rarity_text = "встроенная" if rarity_final is None else str(rarity_final)
    text = (
        "🧙 <b>Мастер создания промокода</b>\n\n"
        f"Код: <code>{html.escape(str(wiz.get('code','')))}</code>\n"
        f"Тип: <b>{html.escape(str(wiz.get('kind','')))}</b>\n"
        f"Значение: <b>{html.escape(str(wiz.get('value','')))}</b>\n"
        f"Редкость: <b>{html.escape(rarity_text)}</b>\n\n"
        "Шаг 5/6: отправьте <b>max_uses</b> (0 = без лимита)"
    )
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def handle_promo_wiz_max_uses(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    wiz = context.user_data.get('promo_wiz') or {}
    try:
        v = int(str(text_input).strip())
        if v < 0:
            raise ValueError
    except Exception:
        await update.message.reply_html("❌ max_uses должен быть целым числом (0 или больше).", reply_markup=keyboard)
        return
    wiz['max_uses'] = v
    context.user_data['promo_wiz'] = wiz
    context.user_data['awaiting_admin_action'] = 'promo_wiz_per_user'
    await update.message.reply_html(
        "Шаг 6/6: отправьте <b>per_user_limit</b> (0 = без лимита на пользователя)",
        reply_markup=keyboard
    )


async def handle_promo_wiz_per_user(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    wiz = context.user_data.get('promo_wiz') or {}
    try:
        v = int(str(text_input).strip())
        if v < 0:
            raise ValueError
    except Exception:
        await update.message.reply_html("❌ per_user_limit должен быть целым числом (0 или больше).", reply_markup=keyboard)
        return
    wiz['per_user_limit'] = v
    context.user_data['promo_wiz'] = wiz
    context.user_data['awaiting_admin_action'] = 'promo_wiz_expires'
    await update.message.reply_html(
        "Отправьте срок действия: <code>YYYY-MM-DD HH:MM</code> или <code>-</code> (без срока)",
        reply_markup=keyboard
    )


async def handle_promo_wiz_expires(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    wiz = context.user_data.get('promo_wiz') or {}
    expires_s = (text_input or '').strip()
    expires = None
    if expires_s and expires_s != '-':
        try:
            from datetime import datetime
            expires = int(datetime.strptime(expires_s, "%Y-%m-%d %H:%M").timestamp())
        except Exception:
            await update.message.reply_html("❌ Неверная дата. Формат: <code>YYYY-MM-DD HH:MM</code> или <code>-</code>.", reply_markup=keyboard)
            return
    wiz['expires_at'] = expires
    context.user_data['promo_wiz'] = wiz
    context.user_data.pop('awaiting_admin_action', None)
    exp_str = safe_format_timestamp(expires) if expires else '—'
    rarity = wiz.get('rarity')
    rarity_line = f"Рarity: <b>{html.escape(str(rarity))}</b>\n" if rarity else ""
    text = (
        "🧾 <b>Проверьте промокод</b>\n\n"
        f"Код: <code>{html.escape(str(wiz.get('code','')))}</code>\n"
        f"Kind: <b>{html.escape(str(wiz.get('kind','')))}</b>\n"
        f"Value: <b>{html.escape(str(wiz.get('value','')))}</b>\n"
        + rarity_line +
        f"max_uses: <b>{html.escape(str(wiz.get('max_uses', 0)))}</b>\n"
        f"per_user_limit: <b>{html.escape(str(wiz.get('per_user_limit', 0)))}</b>\n"
        f"expires: <b>{html.escape(exp_str)}</b>\n\n"
        "Активировать сразу?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data='promo_wiz_active:1'), InlineKeyboardButton("❌ Нет", callback_data='promo_wiz_active:0')],
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    await update.message.reply_html(text, reply_markup=kb)


async def promo_wiz_active_select(update: Update, context: ContextTypes.DEFAULT_TYPE, active: bool):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    wiz = context.user_data.get('promo_wiz') or {}
    wiz['active'] = bool(active)
    context.user_data['promo_wiz'] = wiz
    exp_str = safe_format_timestamp(wiz.get('expires_at')) if wiz.get('expires_at') else '—'
    rarity = wiz.get('rarity')
    rarity_line = f"Rarity: <b>{html.escape(str(rarity))}</b>\n" if rarity else ""
    text = (
        "✅ <b>Готово к созданию</b>\n\n"
        f"Код: <code>{html.escape(str(wiz.get('code','')))}</code>\n"
        f"Kind: <b>{html.escape(str(wiz.get('kind','')))}</b>\n"
        f"Value: <b>{html.escape(str(wiz.get('value','')))}</b>\n"
        + rarity_line +
        f"max_uses: <b>{html.escape(str(wiz.get('max_uses', 0)))}</b>\n"
        f"per_user_limit: <b>{html.escape(str(wiz.get('per_user_limit', 0)))}</b>\n"
        f"expires: <b>{html.escape(exp_str)}</b>\n"
        f"active: <b>{'да' if wiz.get('active') else 'нет'}</b>\n\n"
        "Создать промокод?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Создать", callback_data='promo_wiz_confirm')],
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_wiz_cancel')],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def promo_wiz_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    wiz = context.user_data.get('promo_wiz') or {}
    code = wiz.get('code')
    kind = wiz.get('kind')
    value = int(wiz.get('value') or 0)
    max_uses = int(wiz.get('max_uses') or 0)
    per_user = int(wiz.get('per_user_limit') or 0)
    expires = wiz.get('expires_at')
    active = bool(wiz.get('active', True))
    rarity = wiz.get('rarity')
    res = db.create_promo(str(code), str(kind), int(value), int(max_uses), int(per_user), expires, active, rarity=rarity)
    context.user_data.pop('promo_wiz', None)
    context.user_data.pop('awaiting_admin_action', None)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')]])
    if res.get('ok'):
        suffix = f" (rarity: {html.escape(str(rarity))})" if rarity else ""
        try:
            await query.message.edit_text(f"✅ Создан промокод <b>{html.escape(str(code))}</b>{suffix}", reply_markup=kb, parse_mode='HTML')
        except BadRequest:
            pass
    else:
        reason = html.escape(str(res.get('reason')))
        try:
            await query.message.edit_text(f"❌ Ошибка создания: {reason}", reply_markup=kb, parse_mode='HTML')
        except BadRequest:
            pass


async def promo_wiz_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data.pop('promo_wiz', None)
    context.user_data.pop('awaiting_admin_action', None)
    await show_admin_promo_menu(update, context)


async def admin_promo_deactivate_pick_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    data = query.data or ''
    page = 1
    if ':' in data:
        try:
            page = int(data.split(':', 1)[1])
        except Exception:
            page = 1
    promos = db.list_promos(active_only=True)
    per_page = 10
    total = len(promos)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    chunk = promos[start:start + per_page]
    lines = ["❌ <b>Деактивация (выбор)</b>\n"]
    if not chunk:
        lines.append("<i>Нет активных промокодов</i>")
    else:
        for p in chunk:
            extra = f" rarity={p.get('rarity') or '-'}" if str(p.get('kind','')).lower() == 'drink' else ''
            lines.append(f"• <b>{html.escape(p['code'])}</b> [{html.escape(str(p['kind']))}] val={p['value']}{extra} used={p['used']}/{p['max_uses'] or '∞'}")
    kb_rows: list[list[InlineKeyboardButton]] = []
    for p in chunk:
        kb_rows.append([InlineKeyboardButton(f"⛔ {p['code']}", callback_data=f"promo_deact:{p['id']}")])
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_promo_deactivate_pick:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{pages}", callback_data='noop'))
    if page < pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_promo_deactivate_pick:{page+1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton("🔙 Промокоды", callback_data='admin_promo_menu')])
    try:
        await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_promo_deactivate_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, promo_id: int):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    promos = db.list_promos(active_only=False)
    p = next((x for x in promos if int(x.get('id')) == int(promo_id)), None)
    if not p:
        await query.answer("Не найден", show_alert=True)
        return
    exp = p.get('expires_at')
    exp_str = safe_format_timestamp(exp) if exp else '—'
    extra = f"\nrarity: <b>{html.escape(str(p.get('rarity') or '-'))}</b>" if str(p.get('kind','')).lower() == 'drink' else ""
    text = (
        "❌ <b>Подтверждение деактивации</b>\n\n"
        f"ID: <b>{p['id']}</b>\n"
        f"CODE: <code>{html.escape(p['code'])}</code>\n"
        f"kind: <b>{html.escape(str(p['kind']))}</b>\n"
        f"value: <b>{html.escape(str(p['value']))}</b>\n"
        + extra +
        f"\nused: <b>{p.get('used', 0)}</b>\n"
        f"expires: <b>{html.escape(exp_str)}</b>\n\n"
        "Деактивировать?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ Деактивировать", callback_data=f"promo_deact_do:{p['id']}")],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_promo_deactivate_pick')],
        [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')],
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def admin_promo_deactivate_do(update: Update, context: ContextTypes.DEFAULT_TYPE, promo_id: int):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    ok = db.deactivate_promo_by_id(int(promo_id))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Деактивация (выбор)", callback_data='admin_promo_deactivate_pick')],
        [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promo_menu')],
    ])
    text = "✅ Деактивирован" if ok else "❌ Не найден"
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except BadRequest:
        pass


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str):
    user = update.effective_user
    if not has_creator_panel_access(user.id, user.username):
        return
    recipients = db.get_all_users_for_broadcast()
    total = len(recipients)
    ok = 0
    fail = 0
    for uid in recipients:
        try:
            await context.bot.send_message(chat_id=uid, text=text_input, parse_mode='HTML')
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    try:
        db.log_action(user.id, user.username, 'admin_action', f'broadcast: ok={ok}, fail={fail}', success=True)
    except Exception:
        pass
    await update.message.reply_html(f"📢 Рассылка завершена. Успешно: <b>{ok}</b> / Не доставлено: <b>{fail}</b> (всего: {total})")

async def handle_admin_broadcast_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, caption_input: str):
    user = update.effective_user
    if not has_creator_panel_access(user.id, user.username):
        return
    audio = getattr(update.message, 'audio', None)
    if not audio:
        await update.message.reply_html("❌ Пришлите аудио-файл (музыку) или отправьте текстовый пост.")
        return
    file_id = audio.file_id
    recipients = db.get_all_users_for_broadcast()
    total = len(recipients)
    ok = 0
    fail = 0
    for uid in recipients:
        try:
            await context.bot.send_audio(
                chat_id=uid,
                audio=file_id,
                caption=caption_input if caption_input else None,
                parse_mode='HTML' if caption_input else None,
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    try:
        db.log_action(user.id, user.username, 'admin_action', f'broadcast_audio: ok={ok}, fail={fail}', success=True)
    except Exception:
        pass
    await update.message.reply_html(f"🎵 Рассылка аудио завершена. Успешно: <b>{ok}</b> / Не доставлено: <b>{fail}</b> (всего: {total})")

async def show_admin_promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления промокодами."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    active_promos = db.get_active_promo_count()
    
    keyboard = [
        [InlineKeyboardButton("🧙 Мастер создания", callback_data='admin_promo_wizard')],
        [InlineKeyboardButton("➕ Быстро создать (строка)", callback_data='admin_promo_create')],
        [InlineKeyboardButton("📋 Активные промокоды", callback_data='admin_promo_list_active')],
        [InlineKeyboardButton("🗂️ Все промокоды", callback_data='admin_promo_list_all')],
        [InlineKeyboardButton("❌ Деактивировать (выбор)", callback_data='admin_promo_deactivate_pick')],
        [InlineKeyboardButton("❌ Деактивировать (ID/CODE)", callback_data='admin_promo_deactivate')],
        [InlineKeyboardButton("📊 Статистика использования", callback_data='admin_promo_stats')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🎁 <b>Управление промокодами</b>\n\n"
        f"✅ Активных промокодов: <b>{active_promos}</b>\n\n"
        "Промокоды позволяют выдавать игрокам:\n"
        "• 💰 Монеты\n"
        "• 💎 VIP/VIP+ статус\n"
        "• 🥤 Энергетики\n"
        "• 🎁 Специальные награды\n\n"
        "Выберите действие:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


# --- Настройки бота ---

async def show_admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек бота."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("⏱️ Кулдауны", callback_data='admin_settings_cooldowns')],
        [InlineKeyboardButton("🤖 Автопоиск", callback_data='admin_settings_autosearch')],
        [InlineKeyboardButton("💰 Лимиты", callback_data='admin_settings_limits')],
        [InlineKeyboardButton("🎰 Настройки казино", callback_data='admin_settings_casino')],
        [InlineKeyboardButton("🏪 Настройки магазина", callback_data='admin_settings_shop')],
        [InlineKeyboardButton("🔔 Уведомления", callback_data='admin_settings_notifications')],
        [InlineKeyboardButton("🌐 Локализация", callback_data='admin_settings_localization')],
        [InlineKeyboardButton("⚠️ Негативные эффекты", callback_data='admin_settings_negative_effects')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "Управление параметрами работы бота:\n\n"
        "⏱️ <b>Кулдауны</b> - время ожидания между действиями\n"
        "🤖 <b>Автопоиск</b> - лимиты и коэффициенты VIP/VIP+\n"
        "💰 <b>Лимиты</b> - ограничения на операции\n"
        "🎰 <b>Казино</b> - настройки игр и шансов\n"
        "🏪 <b>Магазин</b> - цены и ассортимент\n"
        "🔔 <b>Уведомления</b> - настройки уведомлений\n"
        "🌐 <b>Локализация</b> - языки интерфейса\n\n"
        "Выберите раздел:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_settings_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает настройки лимитов."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    fert_max = max(1, db.get_setting_int('plantation_fertilizer_max_per_bed', PLANTATION_FERTILIZER_MAX_PER_BED))

    text = (
        "💰 <b>Лимиты</b>\n\n"
        f"🌿 Лимит удобрений на грядку: <b>{int(fert_max)}</b>\n\n"
        "Выберите действие:"
    )
    kb = [
        [InlineKeyboardButton("🧪 Изменить лимит удобрений", callback_data='admin_settings_set_fertilizer_max')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_settings_menu')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_settings_set_fertilizer_max_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_limits')]]
    try:
        await query.message.edit_text("Введите новый лимит удобрений на грядку (целое число ≥ 1):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_fertilizer_max'


async def show_admin_settings_negative_effects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки негативных эффектов на плантациях."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return

    interval = db.get_setting_int('plantation_negative_event_interval_sec', PLANTATION_NEG_EVENT_INTERVAL_SEC)
    chance = db.get_setting_float('plantation_negative_event_chance', PLANTATION_NEG_EVENT_CHANCE)
    max_active = db.get_setting_float('plantation_negative_event_max_active', PLANTATION_NEG_EVENT_MAX_ACTIVE)
    duration = db.get_setting_int('plantation_negative_event_duration_sec', PLANTATION_NEG_EVENT_DURATION_SEC)

    text = (
        "⚠️ <b>Негативные эффекты</b>\n\n"
        f"⏱️ Интервал: <b>{int(interval)}</b> сек.\n"
        f"🎲 Шанс: <b>{round(float(chance) * 100, 2)}%</b>\n"
        f"📊 Лимит активных: <b>{round(float(max_active) * 100, 2)}%</b>\n"
        f"⌛ Длительность: <b>{int(duration)}</b> сек.\n\n"
        "Выберите, что изменить:"
    )
    kb = [
        [InlineKeyboardButton("⏱️ Интервал", callback_data='admin_settings_set_neg_interval')],
        [InlineKeyboardButton("🎲 Шанс", callback_data='admin_settings_set_neg_chance')],
        [InlineKeyboardButton("📊 Лимит активных", callback_data='admin_settings_set_neg_max_active')],
        [InlineKeyboardButton("⌛ Длительность", callback_data='admin_settings_set_neg_duration')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_settings_menu')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        pass


async def admin_settings_set_neg_interval_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_negative_effects')]]
    try:
        await query.message.edit_text("Введите интервал в секундах (целое число ≥ 60):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_neg_interval'


async def admin_settings_set_neg_chance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_negative_effects')]]
    try:
        await query.message.edit_text("Введите шанс (0..1 или проценты 1–100):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_neg_chance'


async def admin_settings_set_neg_max_active_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_negative_effects')]]
    try:
        await query.message.edit_text("Введите лимит активных (0..1 или проценты 1–100):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_neg_max_active'


async def admin_settings_set_neg_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_creator_panel_access(query.from_user.id, query.from_user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    kb = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_settings_negative_effects')]]
    try:
        await query.message.edit_text("Введите длительность эффекта в секундах (целое число ≥ 60):", reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        pass
    context.user_data['awaiting_admin_action'] = 'settings_set_neg_duration'


# --- Модерация ---

async def show_admin_moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню модерации."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 2):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    banned_users = db.get_banned_users_count()
    
    keyboard = [
        [InlineKeyboardButton("🚫 Забанить пользователя", callback_data='admin_mod_ban')],
        [InlineKeyboardButton("✅ Разбанить пользователя", callback_data='admin_mod_unban')],
        [InlineKeyboardButton("⚠️ Предупреждения", callback_data='admin_mod_warnings')],
        [InlineKeyboardButton("📋 Список банов", callback_data='admin_mod_banlist')],
        [InlineKeyboardButton("🔍 Проверить игрока", callback_data='admin_mod_check')],
        [InlineKeyboardButton("📝 История действий", callback_data='admin_mod_history')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🚫 <b>Модерация</b>\n\n"
        f"Заблокировано пользователей: <b>{banned_users}</b>\n\n"
        "<b>Доступные действия:</b>\n"
        "• Блокировка/разблокировка игроков\n"
        "• Система предупреждений\n"
        "• Проверка активности\n"
        "• История нарушений\n\n"
        "Выберите действие:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


# --- Логи системы ---

async def show_admin_logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню логов системы."""
    try:
        query = update.callback_query
        if not query:
            logger.error("show_admin_logs_menu: query is None")
            return
        
        await query.answer()
        
        user = query.from_user
        if not user:
            logger.error("show_admin_logs_menu: user is None")
            return
        
        if not has_admin_level(user.id, user.username, 1):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Последние действия", callback_data='admin_logs_recent')],
            [InlineKeyboardButton("💰 Транзакции", callback_data='admin_logs_transactions')],
            [InlineKeyboardButton("🎰 Игры в казино", callback_data='admin_logs_casino')],
            [InlineKeyboardButton("🛒 Покупки", callback_data='admin_logs_purchases')],
            [InlineKeyboardButton("👤 Действия игрока", callback_data='admin_logs_player')],
            [InlineKeyboardButton("⚠️ Ошибки системы", callback_data='admin_logs_errors')],
            [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
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
            logger.error("show_admin_logs_menu: query.message is None")
            return
        
        try:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest as e:
            logger.error(f"BadRequest при редактировании сообщения в show_admin_logs_menu: {e}")
            # Попробуем отправить новое сообщение, если не удалось отредактировать
            try:
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as send_error:
                logger.error(f"Ошибка при отправке нового сообщения: {send_error}")
    except Exception as e:
        logger.error(f"Ошибка в show_admin_logs_menu: {e}", exc_info=True)
        query = getattr(update, 'callback_query', None)
        if query:
            try:
                await query.answer("❌ Ошибка при открытии меню логов", show_alert=True)
            except:
                pass


async def show_admin_logs_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние действия в системе."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    logs = db.get_recent_logs(limit=20)
    
    text = "📊 <b>Последние действия</b>\n\n"
    
    if logs:
        for log in logs:
            status = "✅" if log['success'] else "❌"
            timestamp_str = safe_format_timestamp(log['timestamp'])
            text += f"{status} <b>{log['username']}</b> ({log['user_id']})\n"
            text += f"├ Действие: <i>{log['action_type']}</i>\n"
            if log['action_details']:
                details = log['action_details'][:50]
                text += f"├ Детали: {details}\n"
            if log['amount']:
                text += f"└ Сумма: {log['amount']}\n"
            text += f"⏰ {timestamp_str}\n\n"
    else:
        text += "<i>Логов пока нет</i>"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_logs_recent')],
        [InlineKeyboardButton("🔙 Логи", callback_data='admin_logs_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_logs_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи транзакций."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    logs = db.get_logs_by_type('transaction', limit=20)
    
    text = "💰 <b>Транзакции</b>\n\n"
    
    if logs:
        for log in logs:
            status = "✅" if log['success'] else "❌"
            timestamp_str = safe_format_timestamp(log['timestamp'])
            text += f"{status} <b>{log['username']}</b>\n"
            if log['amount']:
                sign = "+" if log['amount'] > 0 else ""
                text += f"├ Сумма: {sign}{log['amount']} 💰\n"
            if log['action_details']:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Транзакций пока нет</i>"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_logs_transactions')],
        [InlineKeyboardButton("🔙 Логи", callback_data='admin_logs_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_logs_casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи игр в казино."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    logs = db.get_logs_by_type('casino', limit=20)
    
    text = "🎰 <b>Игры в казино</b>\n\n"
    
    if logs:
        for log in logs:
            status = "✅ Выигрыш" if log['success'] else "❌ Проигрыш"
            timestamp_str = safe_format_timestamp(log['timestamp'])
            text += f"{status} - <b>{log['username']}</b>\n"
            if log['amount']:
                sign = "+" if log['amount'] > 0 else ""
                text += f"├ {sign}{log['amount']} 💰\n"
            if log['action_details']:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Логов казино пока нет</i>"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_logs_casino')],
        [InlineKeyboardButton("🔙 Логи", callback_data='admin_logs_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_logs_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи покупок."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    logs = db.get_logs_by_type('purchase', limit=20)
    
    text = "🛒 <b>Покупки</b>\n\n"
    
    if logs:
        for log in logs:
            status = "✅" if log['success'] else "❌"
            timestamp_str = safe_format_timestamp(log['timestamp'])
            text += f"{status} <b>{log['username']}</b>\n"
            if log['amount']:
                text += f"├ Цена: {log['amount']} 💰\n"
            if log['action_details']:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "<i>Покупок пока нет</i>"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_logs_purchases')],
        [InlineKeyboardButton("🔙 Логи", callback_data='admin_logs_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def show_admin_logs_player_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс просмотра логов игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "👤 <b>Действия игрока</b>\n\n"
        "Отправьте <code>@username</code> или <code>user_id</code> игрока\n\n"
        "Или нажмите Отмена"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_logs_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass
    
    context.user_data['awaiting_admin_action'] = 'logs_player'


async def show_admin_logs_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи ошибок."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_admin_level(user.id, user.username, 1):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    logs = db.get_error_logs(limit=20)
    
    text = "⚠️ <b>Ошибки системы</b>\n\n"
    
    if logs:
        for log in logs:
            timestamp_str = safe_format_timestamp(log['timestamp'])
            text += f"❌ <b>{log['username']}</b> ({log['user_id']})\n"
            text += f"├ Действие: <i>{log['action_type']}</i>\n"
            if log['action_details']:
                text += f"├ {log['action_details'][:60]}\n"
            text += f"└ {timestamp_str}\n\n"
    else:
        text += "✅ <i>Ошибок не обнаружено!</i>"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_logs_errors')],
        [InlineKeyboardButton("🔙 Логи", callback_data='admin_logs_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


# --- Управление экономикой ---

async def show_admin_economy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления экономикой."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    total_coins = db.get_total_coins_in_system()
    
    keyboard = [
        [InlineKeyboardButton("💰 Цены в магазине", callback_data='admin_econ_shop_prices')],
        [InlineKeyboardButton("🎰 Ставки казино", callback_data='admin_econ_casino_bets')],
        [InlineKeyboardButton("🎁 Награды", callback_data='admin_econ_rewards')],
        [InlineKeyboardButton("📈 Инфляция", callback_data='admin_econ_inflation')],
        [InlineKeyboardButton("💎 Стоимость VIP", callback_data='admin_econ_vip_prices')],
        [InlineKeyboardButton("🔄 Курсы обмена", callback_data='admin_econ_exchange')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "💼 <b>Управление экономикой</b>\n\n"
        f"💰 Монет в системе: <b>{total_coins:,}</b>\n\n"
        "<b>Настройка экономических параметров:</b>\n"
        "• Цены на товары и услуги\n"
        "• Размеры наград и бонусов\n"
        "• Ставки в играх\n"
        "• Курсы обмена\n\n"
        "Выберите раздел:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


# --- События ---

async def show_admin_events_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления событиями."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if not has_creator_panel_access(user.id, user.username):
        await query.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    active_events = db.get_active_events_count()
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать событие", callback_data='admin_event_create')],
        [InlineKeyboardButton("📋 Активные события", callback_data='admin_event_list_active')],
        [InlineKeyboardButton("🗂️ Все события", callback_data='admin_event_list_all')],
        [InlineKeyboardButton("✏️ Редактировать", callback_data='admin_event_edit')],
        [InlineKeyboardButton("❌ Завершить событие", callback_data='admin_event_end')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_event_stats')],
        [InlineKeyboardButton("🔙 Админ панель", callback_data='creator_panel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🎮 <b>Управление событиями</b>\n\n"
        f"🎪 Активных событий: <b>{active_events}</b>\n\n"
        "<b>Типы событий:</b>\n"
        "🎉 Временные акции\n"
        "💰 Бонусные периоды\n"
        "🎁 Раздачи наград\n"
        "🏆 Конкурсы\n"
        "⚡ Усиленные дропы\n\n"
        "Выберите действие:"
    )
    
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        pass


async def search_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: напоминание о завершении кулдауна поиска."""
    try:
        await context.bot.send_message(chat_id=context.job.chat_id, text="Кулдаун закончился! Можно искать снова.")
    except Exception as ex:
        logger.warning(f"Не удалось отправить напоминание (job): {ex}")

async def plantation_water_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: напоминание о возможности полива грядки."""
    try:
        if not hasattr(context, 'job') or not context.job:
            return
        user_id = context.job.chat_id
        bed_index = context.job.data.get('bed_index', 0)

        auto_res = db.try_farmer_autowater(user_id, bed_index)
        player = None
        try:
            player = db.get_player(user_id)
        except Exception:
            player = None
        silent_farmer = bool(getattr(player, 'farmer_silent', False)) if player else False

        keyboard = [
            [InlineKeyboardButton("🌱 Перейти к плантациям", callback_data='market_plantation')],
            [InlineKeyboardButton("💤 Отложить 10м", callback_data=f'snooze_remind_{bed_index}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if auto_res.get('ok'):
            try:
                db.try_farmer_auto_fertilize(user_id)
            except Exception:
                pass
            if not silent_farmer:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👨‍🌾 Селюк фермер полил грядку {bed_index} (−{auto_res.get('cost', 50)} септимов с его баланса).",
                    reply_markup=reply_markup
                )
            # Планируем следующий полив
            water_interval = auto_res.get('water_interval_sec', 1800)
            context.job_queue.run_once(
                plantation_water_reminder_job,
                when=water_interval,
                chat_id=user_id,
                data={'bed_index': bed_index},
                name=f"plantation_water_reminder_{user_id}_{bed_index}"
            )
            return

        reason = auto_res.get('reason') if isinstance(auto_res, dict) else None
        # Если job сработал слишком рано (например, пользователь полил вручную раньше), перепланируем
        if reason == 'too_early_to_water':
            nxt = int(auto_res.get('next_water_in') or 0)
            if nxt > 0:
                try:
                    context.job_queue.run_once(
                        plantation_water_reminder_job,
                        when=nxt,
                        chat_id=user_id,
                        data={'bed_index': bed_index},
                        name=f"plantation_water_reminder_{user_id}_{bed_index}"
                    )
                except Exception:
                    pass
            return
        
        # Если грядка пустая или удалена - прекращаем напоминания
        if reason in ('no_seed', 'no_bed', 'no_such_bed'):
            return
        if reason == 'not_growing':
            try:
                bed_state = str(auto_res.get('bed_state') or '')
            except Exception:
                bed_state = ''
            if bed_state in ('empty', 'withered', 'ready'):
                return

        if reason == 'remind_disabled':
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                "👨‍🌾 Селюк фермер не может работать, пока выключены напоминания о поливе.\n"
                "Включите напоминания в настройках, чтобы фермер поливал грядки автоматически."
            )
        elif reason == 'not_enough_balance':
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                "👨‍🌾 Селюку фермеру не хватает септимов на балансе, полей грядку вручную или пополни баланс селюка."
            )
        elif reason == 'min_balance_guard':
            mb = int(auto_res.get('min_balance') or 0)
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                f"👨‍🌾 Фермер не поливает, потому что включена защита минимального остатка ({mb} 💎)."
            )
        elif reason == 'daily_limit_reached':
            dl = int(auto_res.get('daily_limit') or 0)
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                f"👨‍🌾 Фермер не поливает, потому что достигнут дневной лимит расходов ({dl} 💎)."
            )
        elif reason == 'disabled_by_settings':
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                "👨‍🌾 Автополив у фермера выключен в настройках."
            )
        elif reason == 'not_growing':
             # Если уже не growing, значит, возможно, уже выросло или удалено
             return
        elif reason == 'selyuk_disabled':
            text = (
                f"💧 Грядка {bed_index} готова к поливу!\n\n"
                "👨‍🌾 Селюк фермер сейчас выключен. Полейте грядку вручную или включите фермера."
            )
        else:
            text = f"💧 Грядка {bed_index} готова к поливу!"

        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup
        )
    except Exception as ex:
        logger.warning(f"Не удалось отправить напоминание о поливе (job): {ex}")


async def global_farmer_harvest_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: глобальный автоматический сбор урожая для всех пользователей с фермером 2 уровня."""
    try:
        user_ids = db.get_users_with_level2_farmers()
        for user_id in user_ids:
            silent_farmer = False
            lock = _get_lock(f"user:{user_id}:farmer_global")
            if lock.locked():
                continue
            async with lock:
                try:
                    player = None
                    try:
                        player = db.get_player(int(user_id))
                    except Exception:
                        player = None
                    silent_farmer = bool(getattr(player, 'farmer_silent', False)) if player else False

                    res = db.try_farmer_auto_harvest(user_id)
                    if res.get('ok') and res.get('harvested'):
                        items = res['harvested']
                        if not silent_farmer:
                            text = "👨‍🌾 <b>Селюк фермер собрал урожай!</b>\n\n"
                            for item in items:
                                bed_idx = item.get('bed_index')
                                amount = item.get('items_added')
                                drink_name = item.get('drink_name', "Неизвестный")
                                text += f"• Грядка {bed_idx}: {amount} шт. ({drink_name})\n"
                            
                            text += "\nУрожай добавлен в инвентарь."
                            
                            try:
                                await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"Ошибка автосбора для user {user_id}: {e}")

                # После сбора урожая пытаемся посадить новые семена (для 3 уровня)
                try:
                    plant_res = db.try_farmer_auto_plant(user_id)
                    if plant_res.get('ok') and plant_res.get('planted'):
                        planted = plant_res['planted']
                        if not silent_farmer:
                            plant_text = "🌱 <b>Селюк фермер посадил новые семена!</b>\n\n"
                            for p in planted:
                                plant_text += f"• Грядка {p['bed_index']}: {p['seed_name']}\n"
                            
                            try:
                                await context.bot.send_message(chat_id=user_id, text=plant_text, parse_mode='HTML')
                            except Exception:
                                pass

                        try:
                            jq = None
                            if hasattr(context, 'job_queue') and context.job_queue:
                                jq = context.job_queue
                            elif context.application and context.application.job_queue:
                                jq = context.application.job_queue
                            if jq:
                                for p in planted:
                                    try:
                                        bed_idx = int(p.get('bed_index') or 0)
                                    except Exception:
                                        bed_idx = 0
                                    if bed_idx <= 0:
                                        continue
                                    try:
                                        current_jobs = jq.get_jobs_by_name(f"plantation_water_reminder_{user_id}_{bed_idx}")
                                        for job in current_jobs:
                                            job.schedule_removal()
                                    except Exception:
                                        pass

                                    try:
                                        jq.run_once(
                                            plantation_water_reminder_job,
                                            when=1,
                                            chat_id=int(user_id),
                                            data={'bed_index': bed_idx},
                                            name=f"plantation_water_reminder_{user_id}_{bed_idx}",
                                        )
                                    except Exception as ex:
                                        logger.warning(f"Не удалось запланировать автополив после автопосадки для user {user_id}, bed {bed_idx}: {ex}")
                        except Exception as ex:
                            logger.warning(f"Не удалось обработать планирование автополива после автопосадки для user {user_id}: {ex}")
                except Exception as e:
                    logger.warning(f"Ошибка автопосадки для user {user_id}: {e}")
    except Exception as ex:
        logger.warning(f"Ошибка в global_farmer_harvest_job: {ex}")


async def global_farmer_fertilize_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        user_ids = db.get_users_with_level4_farmers()
        for user_id in user_ids:
            lock = _get_lock(f"user:{user_id}:farmer_global")
            if lock.locked():
                continue
            async with lock:
                try:
                    db.try_farmer_auto_fertilize(user_id)
                except Exception as e:
                    logger.warning(f"Ошибка автоудобрения для user {user_id}: {e}")
    except Exception as ex:
        logger.warning(f"Ошибка в global_farmer_fertilize_job: {ex}")


async def global_negative_effects_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        now_ts = int(time.time())
        interval = db.get_setting_int('plantation_negative_event_interval_sec', PLANTATION_NEG_EVENT_INTERVAL_SEC)
        last_ts = int(context.bot_data.get('neg_effects_last_ts', 0) or 0)
        if interval > 0 and (now_ts - last_ts) < int(interval):
            return
        res = db.apply_negative_effects_job()
        if res.get('ok'):
            context.bot_data['neg_effects_last_ts'] = now_ts
    except Exception as ex:
        logger.warning(f"Ошибка в global_negative_effects_job: {ex}")


async def farmer_summary_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        due = db.get_players_with_farmer_summaries_due()
        for row in due:
            user_id = int(row.get('user_id') or 0)
            if user_id <= 0:
                continue
            stats = row.get('stats') or {}
            wc = int(stats.get('water_count') or 0)
            wsp = int(stats.get('water_spent') or 0)
            hc = int(stats.get('harvest_count') or 0)
            hi = int(stats.get('harvest_items') or 0)
            pc = int(stats.get('plant_count') or 0)

            lines = ["👨‍🌾 <b>Сводка фермера</b>", ""]
            if wc:
                lines.append(f"💧 Поливов: <b>{wc}</b> (потрачено: <b>{wsp}</b> 💎)")
            if hc:
                lines.append(f"🥕 Сборов: <b>{hc}</b> (предметов: <b>{hi}</b>)")
            if pc:
                lines.append(f"🌱 Посадок: <b>{pc}</b>")
            if len(lines) <= 2:
                continue

            try:
                await context.bot.send_message(chat_id=user_id, text="\n".join(lines), parse_mode='HTML')
                db.clear_farmer_stats_after_summary(user_id)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Ошибка в farmer_summary_job: {e}")

async def plantation_harvest_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: автоматический сбор урожая (для селюка 2 уровня)."""
    try:
        if not hasattr(context, 'job') or not context.job:
            return
        user_id = context.job.chat_id
        
        # Пытаемся собрать урожай
        res = db.try_farmer_auto_harvest(user_id)
        if res.get('ok') and res.get('harvested'):
            items = res['harvested']
            count = len(items)
            
            # Формируем сообщение
            text = f"👨‍🌾 <b>Селюк фермер (Ур. 2) собрал урожай!</b>\n\n"
            for item in items:
                bed_idx = item['bed_index']
                drink_id = item['drink_id']
                amount = item['yield']
                # Получаем название напитка (нужен доп. запрос или кэш, но для скорости просто ID или generic)
                # Лучше получить название из БД
                drink_name = "Энергетик"
                try:
                    d_obj = db.get_drink_by_id(drink_id)
                    if d_obj:
                        drink_name = d_obj.name
                except:
                    pass
                    
                text += f"• Грядка {bed_idx}: {amount} шт. ({drink_name})\n"
            
            text += "\nУрожай добавлен в инвентарь."
            
            try:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            except Exception:
                pass
                
    except Exception as ex:
        logger.warning(f"Ошибка в plantation_harvest_job: {ex}")

async def snooze_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Отложить' (Snooze)."""
    query = update.callback_query
    await query.answer()
    
    data = query.data  # ожидаем 'snooze_remind_<bed_index>'
    try:
        bed_index = int(data.split('_')[-1])
    except (ValueError, IndexError):
        return

    user_id = query.from_user.id
    
    # Планируем новое напоминание через 10 минут (600 сек)
    delay_sec = 600
    
    try:
        # Удаляем старые (на всякий случай)
        current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user_id}_{bed_index}")
        for job in current_jobs:
            job.schedule_removal()
            
        context.application.job_queue.run_once(
            plantation_water_reminder_job,
            when=delay_sec,
            chat_id=user_id,
            data={'bed_index': bed_index},
            name=f"plantation_water_reminder_{user_id}_{bed_index}",
        )
        
        await query.edit_message_text(
            text=f"💤 Напоминание отложено на 10 минут.",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка при откладывании напоминания: {e}")
        await query.answer("Ошибка", show_alert=True)


async def _send_auto_search_summary(user_id: int, player: Player, context: ContextTypes.DEFAULT_TYPE, reason: str = 'limit'):
    """Отправляет сводный отчет по автопоиску (для тихого режима)."""
    try:
        stats_json = getattr(player, 'auto_search_session_stats', '{}') or '{}'
        try:
            stats = json.loads(stats_json)
        except:
            stats = {}
        
        total_found = stats.get('total_found', 0)
        if total_found == 0:
            return

        total_coins = stats.get('total_coins', 0)
        rarities = stats.get('rarities', {})
        
        text = f"📊 <b>Отчет автопоиска</b>\n\n"
        text += f"🔎 Найдено: {total_found}\n"
        text += f"💰 Монеты: {total_coins}\n\n"
        
        for r, c in rarities.items():
            emoji = COLOR_EMOJIS.get(r, '⚫')
            text += f"{emoji} {r}: {c}\n"
            
        if reason == 'limit':
            text += "\n🏁 <i>Дневной лимит исчерпан.</i>"
        elif reason == 'vip_expired':
            text += "\n⚠️ <i>VIP статус истёк.</i>"
        elif reason == 'disabled':
            text += "\n🛑 <i>Автопоиск остановлен.</i>"
            
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        
        # Сбрасываем статистику
        db.update_player(user_id, auto_search_session_stats='{}')
        
    except Exception as e:
        logger.error(f"[AUTO] Failed to send summary for {user_id}: {e}")


async def auto_search_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue: периодически выполняет автопоиск для VIP-пользователей.
    Самопереназначается с интервалом, равным оставшемуся кулдауну.
    Останавливается при исчерпании лимита/окончании VIP/выключении пользователем.
    """
    try:
        # Безопасное получение user_id
        if not hasattr(context, 'job') or not context.job:
            logger.warning("[AUTO] context.job отсутствует в auto_search_job")
            return
        user_id = context.job.chat_id
        if not user_id:
            logger.warning("[AUTO] user_id отсутствует в auto_search_job")
            return
        player = db.get_or_create_player(user_id, str(user_id))

        # Если пользователь успел выключить автопоиск — выходим (не переназначаем)
        if not getattr(player, 'auto_search_enabled', False):
            # Если был тихий режим и есть статистика — отправим отчет
            if getattr(player, 'auto_search_silent', False):
                await _send_auto_search_summary(user_id, player, context, reason='disabled')
            return

        # Проверка VIP
        if not db.is_vip(user_id):
            # Если был тихий режим — отчет
            if getattr(player, 'auto_search_silent', False):
                await _send_auto_search_summary(user_id, player, context, reason='vip_expired')
                
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
            # Если был тихий режим — отчет
            if getattr(player, 'auto_search_silent', False):
                await _send_auto_search_summary(user_id, player, context, reason='limit')
                
            db.update_player(user_id, auto_search_enabled=False)
            lang = player.language
            try:
                await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_limit_reached'))
            except Exception:
                pass
            return

        # Учитываем кулдаун (VIP+ - x0.25, VIP - x0.5)
        vip_plus_active = db.is_vip_plus(user_id)
        vip_active = db.is_vip(user_id)  # сначала проверяли VIP выше
        
        base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
        if vip_plus_active:
            eff_search_cd = base_search_cd / 4
        elif vip_active:
            eff_search_cd = base_search_cd / 2
        else:
            eff_search_cd = base_search_cd
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
            except Exception as e:
                logger.warning(f"[AUTO] Не удалось запланировать автопоиск (кулдаун) для {user_id}: {e}")
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
            except Exception as e:
                logger.warning(f"[AUTO] Не удалось запланировать автопоиск (lock) для {user_id}: {e}")
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

            # Проверяем режим (тихий или обычный)
            is_silent = getattr(player, 'auto_search_silent', False)
            logger.info(f"[AUTO] User {user_id} silent mode: {is_silent}")
            
            if is_silent:
                # Накапливаем статистику
                try:
                    stats_json = getattr(player, 'auto_search_session_stats', '{}') or '{}'
                    try:
                        stats = json.loads(stats_json)
                    except:
                        stats = {}
                    
                    # Обновляем данные
                    found_count = int(result.get('found_count', 1) or 1)
                    stats['total_found'] = stats.get('total_found', 0) + found_count
                    
                    # Извлекаем награду из лога или результата (в result нет точной суммы, но мы можем примерно восстановить или передать из _perform_energy_search)
                    # В _perform_energy_search мы не возвращаем точную сумму монет, добавим это.
                    # Пока возьмем из caption парсингом или просто добавим в result
                    earned_coins = result.get('earned_coins', 0) # Нужно добавить в _perform_energy_search
                    stats['total_coins'] = stats.get('total_coins', 0) + earned_coins
                    
                    rarities = result.get('rarities')
                    if not rarities:
                        rarity_one = result.get('rarity')
                        rarities = [rarity_one] if rarity_one else []
                    if 'rarities' not in stats:
                        stats['rarities'] = {}
                    for rarity in rarities:
                        if not rarity:
                            continue
                        stats['rarities'][rarity] = stats['rarities'].get(rarity, 0) + 1
                    
                    db.update_player(user_id, auto_search_session_stats=json.dumps(stats))
                    logger.debug(f"[AUTO] Silent search stats updated for {user_id}")
                except Exception as e:
                    logger.error(f"[AUTO] Failed to update silent stats: {e}")
            else:
                # Отправим пользователю уведомление с найденным предметом (как раньше)
                try:
                    img_paths = result.get("image_paths") or []
                    existing = [p for p in img_paths if p and os.path.exists(p)]
                    found_count = int(result.get('found_count', 1) or 1)
                    if found_count >= 2 and len(existing) >= 2:
                        f1 = None
                        f2 = None
                        try:
                            f1 = open(existing[0], 'rb')
                            f2 = open(existing[1], 'rb')
                            media = [
                                InputMediaPhoto(media=f1, caption=result.get("caption"), parse_mode='HTML'),
                                InputMediaPhoto(media=f2),
                            ]
                            await _send_media_group_long(context.bot.send_media_group, chat_id=user_id, media=media)
                        finally:
                            try:
                                if f1:
                                    f1.close()
                            except Exception:
                                pass
                            try:
                                if f2:
                                    f2.close()
                            except Exception:
                                pass
                    elif existing:
                        with open(existing[0], 'rb') as photo:
                            await _send_photo_long(
                                context.bot.send_photo,
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
                # Если был тихий режим — отчет
                if is_silent:
                    await _send_auto_search_summary(user_id, player, context, reason='limit')
                    
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
                logger.debug(f"[AUTO] Запланирован следующий автопоиск для {user_id} через {eff_search_cd} сек")
            except Exception as e:
                logger.error(f"[AUTO] Критическая ошибка: не удалось запланировать следующий автопоиск для {user_id}: {e}")
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
            except Exception as e:
                logger.warning(f"[AUTO] Не удалось запланировать автопоиск (cooldown result) для {user_id}: {e}")
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
            except Exception as e:
                logger.warning(f"[AUTO] Не удалось запланировать автопоиск (no_drinks) для {user_id}: {e}")
            return
    except Exception:
        logger.exception("[AUTO] Ошибка в auto_search_job")
        # На случай исключений попробуем снова через 1 минуту
        try:
            if hasattr(context, 'job') and context.job and context.job.chat_id:
                user_id = context.job.chat_id
                context.application.job_queue.run_once(
                    auto_search_job,
                    when=60,
                    chat_id=user_id,
                    name=f"auto_search_{user_id}",
                )
        except Exception as e:
            logger.warning(f"[AUTO] Не удалось перезапустить auto_search_job после ошибки: {e}")

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
    rating_value = int(getattr(player, 'rating', 0) or 0)

    # Проверка кулдауна (VIP — x0.5, VIP+ — x0.25)
    current_time = time.time()
    vip_plus_active = db.is_vip_plus(user_id)
    vip_active = db.is_vip(user_id)
    
    base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
    if vip_plus_active:
        eff_search_cd = base_search_cd / 4
    elif vip_active:
        eff_search_cd = base_search_cd / 2
    else:
        eff_search_cd = base_search_cd
    if current_time - player.last_search < eff_search_cd:
        time_left = eff_search_cd - (current_time - player.last_search)
        return {"status": "cooldown", "time_left": time_left}

    # Выбираем случайный энергетик с учетом системы "горячих" и "холодных" напитков
    weighted_drinks = db.get_weighted_drinks_list()
    if not weighted_drinks:
        return {"status": "no_drinks"}

    favorite_drink_ids: set[int] = set()
    try:
        favorite_drink_ids = db.get_player_favorite_drink_ids(user_id)
    except Exception:
        favorite_drink_ids = set()

    luck_charges = int(getattr(player, 'luck_coupon_charges', 0) or 0)
    used_luck_coupon = False
    double_drop_chance = 0.50 if luck_charges > 0 else 0.10
    found_count = 2 if (random.random() < double_drop_chance) else 1
    if found_count == 2 and luck_charges > 0:
        used_luck_coupon = True
        try:
            db.update_player(user_id, luck_coupon_charges=max(0, luck_charges - 1))
            luck_charges = max(0, luck_charges - 1)
        except Exception:
            pass

    drops: list[dict] = []
    rarities_found: list[str] = []

    # Базовая награда монет за факт поиска (один раз за поиск)
    septims_reward = random.randint(5, 10)
    if vip_active:
        septims_reward *= 2

    coins_before = int(player.coins or 0)
    coins_after = coins_before + septims_reward

    total_autosell_payout = 0

    for _ in range(found_count):
        if favorite_drink_ids:
            weights = [FAVORITE_DRINK_WEIGHT_MULT if int(getattr(d, 'id', 0) or 0) in favorite_drink_ids else 1.0 for d in weighted_drinks]
            found_drink = random.choices(weighted_drinks, weights=weights, k=1)[0]
        else:
            found_drink = random.choice(weighted_drinks)

        # Определяем "температуру" найденного напитка ДО записи находки
        drink_temp = db.get_drink_temperature(found_drink.id)

        # Записываем находку в статистику (ПОСЛЕ определения температуры)
        db.record_drink_discovery(found_drink.id)

        # Определяем редкость
        if found_drink.is_special:
            rarity = 'Special'
        else:
            rw = _rarity_weights_with_rating(RARITIES, rating_value, 0.10)
            rarity = random.choices(list(rw.keys()), weights=list(rw.values()), k=1)[0]
        rarities_found.append(rarity)

        # Автопродажа: если включена для данной редкости и такой напиток уже есть в инвентаре,
        # не кладём новый экземпляр в инвентарь, а сразу продаём по цене Приёмника.
        autosell_enabled = False
        autosell_payout = 0
        try:
            # Эксклюзивность: если в инвентаре ещё нет такого drink_id+rarity, НЕ автопродаём
            already_have = db.has_inventory_item(user_id, found_drink.id, rarity)
            if already_have and db.is_autosell_enabled(user_id, rarity):
                autosell_enabled = True
                try:
                    unit_payout = int(db.get_receiver_unit_payout_with_rating(rarity, rating_value) or 0)
                except Exception:
                    unit_payout = 0
                if unit_payout > 0:
                    autosell_payout = unit_payout
                    coins_after += autosell_payout
                    total_autosell_payout += autosell_payout
        except Exception:
            autosell_enabled = False

        # Если автопродажа не сработала (отключена или цена 0) — добавляем напиток в инвентарь
        if (not autosell_enabled) or autosell_payout <= 0:
            db.add_drink_to_inventory(user_id=user_id, drink_id=found_drink.id, rarity=rarity)

        drops.append({
            'drink': found_drink,
            'rarity': rarity,
            'temp': drink_temp,
            'autosell_enabled': autosell_enabled,
            'autosell_payout': autosell_payout,
        })

    # Свага-карточки: гарантированно 10 шт. за каждый поиск
    swaga_cards_found = []
    try:
        from constants import SWAGA_RARITIES
        from database import SessionLocal, SwagaCardInventory
        swaga_drops = random.choices(list(SWAGA_RARITIES.keys()), weights=list(SWAGA_RARITIES.values()), k=10)
        
        # Считаем сколько каждой редкости выпало
        drop_counts = {}
        for sr in swaga_drops:
            swaga_cards_found.append(sr)
            drop_counts[sr] = drop_counts.get(sr, 0) + 1
        
        db_session = SessionLocal()
        try:
            for rarity_name, qty in drop_counts.items():
                rec = db_session.query(SwagaCardInventory).filter_by(user_id=int(user_id), rarity=rarity_name).first()
                if rec:
                    rec.quantity += qty
                else:
                    db_session.add(SwagaCardInventory(user_id=int(user_id), rarity=rarity_name, quantity=qty))
            db_session.commit()
            logger.info(f"[SWAGA] Saved {len(swaga_drops)} swaga cards for user {user_id}")
        except Exception as e:
            db_session.rollback()
            logger.error(f"[SWAGA] Error saving swaga cards for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"[SWAGA] Error generating Swaga Cards for user {user_id}: {e}")
        import traceback
        traceback.print_exc()

    # Обновляем игрока: фиксируем время поиска, новый баланс и рейтинг
    new_rating = db.increment_rating(user_id, 1)
    db.update_player(user_id, last_search=current_time, coins=coins_after)
    try:
        names = ", ".join([d['drink'].name for d in drops])
    except Exception:
        names = "?"
    logger.info(
        f"[SEARCH] User {username} ({user_id}) found x{found_count}: {names} | +{septims_reward} coins, autosell_total={total_autosell_payout} -> {coins_after}"
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
    
    # Проверяем VIP статус с приоритетом VIP+
    vip_plus_ts = db.get_vip_plus_until(user_id)
    vip_ts = db.get_vip_until(user_id)
    current_time = time.time()
    
    if vip_plus_ts and current_time < vip_plus_ts and safe_format_timestamp(vip_plus_ts):
        vip_line = f"\n{VIP_PLUS_EMOJI} VIP+ до: {safe_format_timestamp(vip_plus_ts)}"
    elif vip_ts and current_time < vip_ts and safe_format_timestamp(vip_ts):
        vip_line = f"\n{VIP_EMOJI} V.I.P до: {safe_format_timestamp(vip_ts)}"
    else:
        vip_line = ''
    
    if found_count == 1 and drops:
        d0 = drops[0]
        found_drink = d0['drink']
        rarity = d0['rarity']
        drink_temp = d0['temp']
        autosell_enabled = d0['autosell_enabled']
        autosell_payout = d0['autosell_payout']

        rarity_emoji = COLOR_EMOJIS.get(rarity, '⚫')
        if drink_temp == 'hot':
            temp_emoji = '🔥'
            temp_text = 'Горячий напиток! (давно не попадался)'
        elif drink_temp == 'cold':
            temp_emoji = '❄️'
            temp_text = 'Холодный напиток (недавно находили)'
        else:
            temp_emoji = '🌡️'
            temp_text = 'Нейтральный'

        caption_lines = [
            f"🎉 Ты нашел энергетик!{vip_line}",
            "",
            f"<b>Название:</b> {found_drink.name}",
            f"<b>Редкость:</b> {rarity_emoji} {rarity}",
            f"{temp_emoji} <b>Статус:</b> <i>{temp_text}</i>",
            f"💰 <b>Награда:</b> +{septims_reward} септимов",
        ]

        if autosell_enabled and autosell_payout > 0:
            caption_lines.append(f"🧾 <b>Автопродажа:</b> +{autosell_payout} септимов (энергетик сразу продан через Приёмник)")

        caption_lines.append(f"💰 <b>Баланс:</b> {coins_after}")
        if new_rating is not None:
            caption_lines.append(f"⭐ <b>Рейтинг:</b> {new_rating}")
            
        if swaga_cards_found:
            swaga_counts = {}
            for seq in swaga_cards_found:
                swaga_counts[seq] = swaga_counts.get(seq, 0) + 1
            swaga_text = ", ".join([f"{c}x {st}" for st, c in swaga_counts.items()])
            caption_lines.append(f"🎫 <b>Свага-карточки (10):</b> {swaga_text}")
            
        caption_lines.append("")
        caption_lines.append(f"<i>{found_drink.description}</i>")
    else:
        caption_lines = [
            f"🎉 Джекпот! Ты нашел 2 энергетика!{vip_line}",
            "",
        ]

        if used_luck_coupon:
            caption_lines.append(f"🎲 <b>Купон удачи:</b> использован (осталось {luck_charges})")
            caption_lines.append("")

        for idx, d in enumerate(drops, start=1):
            found_drink = d['drink']
            rarity = d['rarity']
            drink_temp = d['temp']
            autosell_enabled = d['autosell_enabled']
            autosell_payout = d['autosell_payout']

            rarity_emoji = COLOR_EMOJIS.get(rarity, '⚫')
            if drink_temp == 'hot':
                temp_emoji = '🔥'
                temp_text = 'Горячий напиток! (давно не попадался)'
            elif drink_temp == 'cold':
                temp_emoji = '❄️'
                temp_text = 'Холодный напиток (недавно находили)'
            else:
                temp_emoji = '🌡️'
                temp_text = 'Нейтральный'

            caption_lines.append(f"<b>{idx}) {found_drink.name}</b>")
            caption_lines.append(f"<b>Редкость:</b> {rarity_emoji} {rarity}")
            caption_lines.append(f"{temp_emoji} <b>Статус:</b> <i>{temp_text}</i>")
            if autosell_enabled and autosell_payout > 0:
                caption_lines.append(f"🧾 <b>Автопродажа:</b> +{autosell_payout} септимов (энергетик сразу продан через Приёмник)")
            caption_lines.append("")
            caption_lines.append(f"<i>{found_drink.description}</i>")
            caption_lines.append("")

        caption_lines.append(f"💰 <b>Награда за поиск:</b> +{septims_reward} септимов")
        if total_autosell_payout > 0:
            caption_lines.append(f"🧾 <b>Автопродажа всего:</b> +{total_autosell_payout} септимов")
        caption_lines.append(f"💰 <b>Баланс:</b> {coins_after}")
        if new_rating is not None:
            caption_lines.append(f"⭐ <b>Рейтинг:</b> {new_rating}")

        if swaga_cards_found:
            swaga_counts = {}
            for seq in swaga_cards_found:
                swaga_counts[seq] = swaga_counts.get(seq, 0) + 1
            swaga_text = ", ".join([f"{c}x {st}" for st, c in swaga_counts.items()])
            caption_lines.append(f"🎫 <b>Свага-карточки (10):</b> {swaga_text}")

    caption = "\n".join(caption_lines)
    image_paths: list[str | None] = []
    try:
        for d in drops:
            p = getattr(d['drink'], 'image_path', None)
            image_paths.append(os.path.join(ENERGY_IMAGES_DIR, p) if p else None)
    except Exception:
        image_paths = []
    image_full_path = image_paths[0] if (found_count == 1 and image_paths) else None
    
    return {
        "status": "ok",
        "caption": caption,
        "image_path": image_full_path,
        "image_paths": image_paths,
        "reply_markup": InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]]),
        "earned_coins": septims_reward + total_autosell_payout,
        "found_count": found_count,
        "rarities": rarities_found,
        "rarity": (rarities_found[0] if rarities_found else 'Basic')
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
        vip_plus_active = db.is_vip_plus(user.id)
        vip_active = db.is_vip(user.id)
        base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
        if vip_plus_active:
            eff_search_cd = base_search_cd / 4
        elif vip_active:
            eff_search_cd = base_search_cd / 2
        else:
            eff_search_cd = base_search_cd
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
            img_paths = result.get("image_paths") or []
            existing = [p for p in img_paths if p and os.path.exists(p)]
            found_count = int(result.get('found_count', 1) or 1)
            if found_count >= 2 and len(existing) >= 2:
                f1 = None
                f2 = None
                try:
                    f1 = open(existing[0], 'rb')
                    f2 = open(existing[1], 'rb')
                    media = [
                        InputMediaPhoto(media=f1, caption=result.get("caption"), parse_mode='HTML'),
                        InputMediaPhoto(media=f2),
                    ]
                    await _send_media_group_long(context.bot.send_media_group, chat_id=query.message.chat_id, media=media)
                finally:
                    try:
                        if f1:
                            f1.close()
                    except Exception:
                        pass
                    try:
                        if f2:
                            f2.close()
                    except Exception:
                        pass
            elif existing:
                with open(existing[0], 'rb') as photo:
                    await _send_photo_long(
                        context.bot.send_photo,
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


async def show_roulette_animation(context: ContextTypes.DEFAULT_TYPE, chat_id: int, selected_reward: str) -> None:
    """
    Показывает анимацию текстовой рулетки с движущейся стрелочкой.
    Длительность: 3 секунды.
    """
    # Список наград для отображения
    rewards_display = [
        ('coins', '💰 400 септимов'),
        ('absolute_drink', '🟣 Энергетик Absolute'),
        ('vip_3d', '👑 VIP на 3 дня'),
        ('vip_plus_7d', '💎 VIP+ на 7 дней'),
        ('vip_plus_30d', '🎊 VIP+ на 30 дней'),
        ('selyuk_fragment', '🧩 Фрагмент Селюка'),
    ]
    
    # Находим индекс выбранной награды
    selected_index = next((i for i, (key, _) in enumerate(rewards_display) if key == selected_reward), 0)
    
    # Отправляем начальное сообщение
    roulette_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🎰 <b>Крутим рулетку...</b>",
        parse_mode='HTML'
    )
    
    # Анимация: прокручиваем рулетку 3 секунды
    duration = 3.0  # секунд
    frames = 12  # количество кадров анимации
    frame_delay = duration / frames  # задержка между кадрами
    
    # Создаём случайную последовательность для эффекта прокрутки
    current_pos = 0
    prev_pos = -1  # Предыдущая позиция для проверки изменений
    
    for frame in range(frames):
        # На последних кадрах замедляемся и останавливаемся на выбранной награде
        if frame < frames - 5:
            # Быстрая прокрутка
            current_pos = (current_pos + 1) % len(rewards_display)
        elif frame < frames - 1:
            # Замедление перед выбранной наградой
            if current_pos != selected_index:
                current_pos = (current_pos + 1) % len(rewards_display)
        else:
            # Финальная позиция - выбранная награда
            current_pos = selected_index
        
        # Обновляем сообщение только если позиция изменилась
        if current_pos != prev_pos:
            # Формируем текст рулетки
            roulette_text = "🎰 <b>Крутим рулетку...</b>\n\n"
            for i, (_, display_name) in enumerate(rewards_display):
                if i == current_pos:
                    roulette_text += f"➡️ <b>{display_name}</b>\n"
                else:
                    roulette_text += f"     {display_name}\n"
            
            # Обновляем сообщение
            try:
                await roulette_message.edit_text(
                    text=roulette_text,
                    parse_mode='HTML'
                )
                prev_pos = current_pos
            except RetryAfter as e:
                try:
                    await asyncio.sleep(float(getattr(e, 'retry_after', 1)))
                except Exception:
                    await asyncio.sleep(1)
            except Exception as e:
                # Игнорируем ошибки редактирования
                pass
        
        # Задержка между кадрами
        await asyncio.sleep(frame_delay)
    
    # Удаляем сообщение с рулеткой после завершения
    try:
        await roulette_message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение рулетки: {e}")


async def show_daily_bonus_info(update: Update, context: ContextTypes.DEFAULT_TYPE, already_answered: bool = False) -> None:
    query = update.callback_query
    if not already_answered:
        await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'
    rating_value = int(getattr(player, 'rating', 0) or 0)

    vip_plus_active = db.is_vip_plus(user.id)
    vip_active = db.is_vip(user.id)
    base_bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
    if vip_plus_active:
        eff_bonus_cd = base_bonus_cd / 4
    elif vip_active:
        eff_bonus_cd = base_bonus_cd / 2
    else:
        eff_bonus_cd = base_bonus_cd

    now = time.time()
    last_bonus_claim_val = float(getattr(player, 'last_bonus_claim', 0) or 0)
    time_left = max(0, eff_bonus_cd - (now - last_bonus_claim_val))
    hours, remainder = divmod(int(time_left), 3600)
    minutes, seconds = divmod(remainder, 60)

    reward_labels = {
        'coins': '💰 400 септимов' if lang != 'en' else '💰 400 coins',
        'absolute_drink': '🟣 Энергетик Absolute' if lang != 'en' else '🟣 Absolute energy drink',
        'vip_3d': '👑 VIP на 3 дня' if lang != 'en' else '👑 VIP for 3 days',
        'vip_plus_7d': '💎 VIP+ на 7 дней' if lang != 'en' else '💎 VIP+ for 7 days',
        'vip_plus_30d': '🎊 VIP+ на 30 дней' if lang != 'en' else '🎊 VIP+ for 30 days',
        'selyuk_fragment': '🧩 Фрагмент Селюка' if lang != 'en' else '🧩 Selyuk fragment',
    }

    adjusted = _daily_bonus_weights_with_rating(DAILY_BONUS_REWARDS, rating_value, 0.05)
    total_weight = sum(float(w or 0) for w in adjusted.values())
    if total_weight <= 0:
        total_weight = 1.0

    lines = []
    for key, info in DAILY_BONUS_REWARDS.items():
        try:
            w = float(adjusted.get(key, 0) or 0)
        except Exception:
            w = 0.0
        pct = (w / total_weight) * 100.0
        lines.append(f"- {reward_labels.get(key, key)} — <b>{pct:.2f}%</b>")

    if lang != 'en':
        title = "🎁 <b>Ежедневный бонус</b>"
        timer_line = f"⏳ До следующего: <b>{hours:02d}:{minutes:02d}:{seconds:02d}</b>" if time_left > 0 else "✅ <b>Бонус доступен прямо сейчас!</b>"
        vip_line = "⚡ VIP ускоряет в 2 раза, VIP+ — в 4 раза."
        bonus_line = f"⭐ Бонус рейтинга к редким наградам: <b>до +5%</b> (сейчас: <b>+{_rating_bonus_percent(rating_value, 0.05) * 100:.2f}%</b>)."
        rewards_title = "🎰 <b>Награды и шансы:</b>"
        claim_label = "🎁 Забрать бонус"
    else:
        title = "🎁 <b>Daily Bonus</b>"
        timer_line = f"⏳ Next in: <b>{hours:02d}:{minutes:02d}:{seconds:02d}</b>" if time_left > 0 else "✅ <b>Bonus is available now!</b>"
        vip_line = "⚡ VIP is 2x faster, VIP+ is 4x faster."
        bonus_line = f"⭐ Rating bonus to rare rewards: <b>up to +5%</b> (now: <b>+{_rating_bonus_percent(rating_value, 0.05) * 100:.2f}%</b>)."
        rewards_title = "🎰 <b>Rewards & odds:</b>"
        claim_label = "🎁 Claim bonus"

    text = "\n".join([
        title,
        "",
        timer_line,
        vip_line,
        bonus_line,
        "",
        rewards_title,
        *lines,
    ])

    keyboard = [
        [InlineKeyboardButton(claim_label, callback_data='claim_bonus')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.edit_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


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
        lang = getattr(player, 'language', 'ru') or 'ru'
        rating_value = int(getattr(player, 'rating', 0) or 0)

        # Проверка кулдауна
        current_time = time.time()
        vip_plus_active = db.is_vip_plus(user.id)
        vip_active = db.is_vip(user.id)
        base_bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
        if vip_plus_active:
            eff_bonus_cd = base_bonus_cd / 4
        elif vip_active:
            eff_bonus_cd = base_bonus_cd / 2
        else:
            eff_bonus_cd = base_bonus_cd
        if current_time - player.last_bonus_claim < eff_bonus_cd:
            time_left = int(eff_bonus_cd - (current_time - player.last_bonus_claim))
            hours, remainder = divmod(time_left, 3600)
            minutes, seconds = divmod(remainder, 60)
            try:
                await query.answer(f"Ещё рано! До бонуса: {hours:02d}:{minutes:02d}:{seconds:02d}")
            except Exception:
                pass
            await show_daily_bonus_info(update, context, already_answered=True)
            return

        chat_id = query.message.chat_id

        # Выбираем награду по весам из рулетки
        reward_types = list(DAILY_BONUS_REWARDS.keys())
        adjusted = _daily_bonus_weights_with_rating(DAILY_BONUS_REWARDS, rating_value, 0.05)
        reward_weights = [float(adjusted.get(r, 0) or 0) for r in reward_types]
        selected_reward = random.choices(reward_types, weights=reward_weights, k=1)[0]
        reward_info = DAILY_BONUS_REWARDS[selected_reward]

        found_drink = None
        if selected_reward == 'absolute_drink':
            all_drinks = db.get_all_drinks()
            non_special_drinks = [d for d in all_drinks if not d.is_special]
            if non_special_drinks:
                found_drink = random.choice(non_special_drinks)
            else:
                selected_reward = 'coins'
                reward_info = DAILY_BONUS_REWARDS[selected_reward]

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Показываем текстовую анимацию рулетки
        await show_roulette_animation(context, chat_id, selected_reward)

        # Обрабатываем награду в зависимости от типа
        caption = ""
        reward_log = ""
        new_rating = db.increment_rating(user.id, 1)

        if selected_reward == 'coins':
            # Награда 1: 400 септимов
            coins_amount = reward_info['amount']
            new_coins = db.increment_coins(user.id, coins_amount)
            if new_coins is None:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось выдать бонус. Попробуй ещё раз позже.",
                )
                return
            db.update_player(user.id, last_bonus_claim=current_time)

            caption = (
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"💰 Вы выиграли <b>{coins_amount} септимов</b>!\n\n"
                f"Текущий баланс: <b>{new_coins}</b> 🪙"
            )
            if new_rating is not None:
                caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
            reward_log = f"+{coins_amount} coins -> {new_coins}"

        elif selected_reward == 'absolute_drink':
            # Награда 2: Случайный энергетик Absolute (не Special)
            rarity = 'Absolute'
            rarity_emoji = COLOR_EMOJIS.get(rarity, '🟣')
            try:
                db.add_drink_to_inventory(user_id=user.id, drink_id=found_drink.id, rarity=rarity)
            except Exception:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось выдать бонус. Попробуй ещё раз позже.",
                )
                return
            db.update_player(user.id, last_bonus_claim=current_time)

            caption = (
                f"🎉 <b>Невероятная удача!</b>\n\n"
                f"Вы получили эксклюзивный энергетик редкости <b>{rarity_emoji} {rarity}</b>!\n\n"
                f"<b>Название:</b> {found_drink.name}\n"
                f"<b>Редкость:</b> {rarity_emoji} {rarity}\n\n"
                f"<i>{found_drink.description}</i>"
            )
            if new_rating is not None:
                caption += f"\n\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
            reward_log = f"{found_drink.name} | rarity={rarity}"

        elif selected_reward == 'vip_3d':
            # Награда 3: VIP на 3 дня или VIP+ на 1 день если уже есть VIP+
            vip_plus_ts = db.get_vip_plus_until(user.id)
            current_time_check = time.time()

            if vip_plus_ts and current_time_check < vip_plus_ts:
                new_vip_plus_ts = db.extend_vip_plus(user.id, 1 * 24 * 60 * 60)
                db.update_player(user.id, last_bonus_claim=current_time)

                caption = (
                    f"🎉 <b>Элитная награда!</b>\n\n"
                    f"{VIP_PLUS_EMOJI} Вы получили <b>+1 день VIP+</b>!\n\n"
                    f"VIP+ активен до: {safe_format_timestamp(new_vip_plus_ts)}"
                )
                if new_rating is not None:
                    caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
                reward_log = "+1 day VIP+"
            else:
                new_vip_ts = db.extend_vip(user.id, 3 * 24 * 60 * 60)
                db.update_player(user.id, last_bonus_claim=current_time)

                caption = (
                    f"🎉 <b>Отличная награда!</b>\n\n"
                    f"{VIP_EMOJI} Вы получили <b>VIP на 3 дня</b>!\n\n"
                    f"VIP активен до: {safe_format_timestamp(new_vip_ts)}"
                )
                if new_rating is not None:
                    caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
                reward_log = "VIP 3 days"

        elif selected_reward == 'vip_plus_7d':
            # Награда 4: VIP+ на 7 дней
            new_vip_plus_ts = db.extend_vip_plus(user.id, 7 * 24 * 60 * 60)
            db.update_player(user.id, last_bonus_claim=current_time)

            caption = (
                f"🎉 <b>Фантастическая награда!</b>\n\n"
                f"{VIP_PLUS_EMOJI} Вы получили <b>VIP+ на 7 дней</b>!\n\n"
                f"VIP+ активен до: {safe_format_timestamp(new_vip_plus_ts)}"
            )
            if new_rating is not None:
                caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
            reward_log = "VIP+ 7 days"

        elif selected_reward == 'vip_plus_30d':
            # Награда 5: VIP+ на 30 дней (джекпот!)
            new_vip_plus_ts = db.extend_vip_plus(user.id, 30 * 24 * 60 * 60)
            db.update_player(user.id, last_bonus_claim=current_time)

            caption = (
                f"🎊 <b>ДЖЕКПОТ!!!</b> 🎊\n\n"
                f"{VIP_PLUS_EMOJI} Вы сорвали куш — <b>VIP+ на 30 дней</b>!\n\n"
                f"VIP+ активен до: {safe_format_timestamp(new_vip_plus_ts)}"
            )
            if new_rating is not None:
                caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
            reward_log = "VIP+ 30 days (JACKPOT!)"

        elif selected_reward == 'selyuk_fragment':
            # Награда 6: Фрагмент Селюка
            amount = reward_info.get('amount', 1)
            new_fragments = db.increment_selyuk_fragments(user.id, amount)
            db.update_player(user.id, last_bonus_claim=current_time)

            caption = (
                f"🎉 <b>Редкая находка!</b>\n\n"
                f"🧩 Вы нашли <b>Фрагмент Селюка</b> ({amount} шт.)!\n\n"
                f"Всего фрагментов: <b>{new_fragments}</b>"
            )
            if new_rating is not None:
                caption += f"\n⭐ Ваш рейтинг: <b>{new_rating}</b>"
            reward_log = f"Selyuk Fragment +{amount} -> {new_fragments}"

        # Логируем результат
        logger.info(
            f"[DAILY BONUS ROULETTE] User {user.username or user.id} ({user.id}) | "
            f"reward={selected_reward} | {reward_log}"
        )

        # Отправляем финальное сообщение с наградой
        back_label = "🔙 В меню" if lang == 'ru' else "🔙 Menu"
        keyboard = [[InlineKeyboardButton(back_label, callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Если выпал энергетик - отправляем с фото, иначе - просто текст
        if found_drink and getattr(found_drink, 'image_path', None):
            image_full_path = os.path.join(ENERGY_IMAGES_DIR, found_drink.image_path)
            if os.path.exists(image_full_path):
                try:
                    with open(image_full_path, 'rb') as photo:
                        await _send_photo_long(
                            context.bot.send_photo,
                            chat_id=chat_id,
                            photo=photo,
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
                except Exception as e:
                    logger.warning(f"Не удалось отправить фото энергетика: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            # Для всех остальных наград - просто текст
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

        try:
            # Удаляем старое сообщение
            await query.message.delete()
        except Exception:
            pass


async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь игрока с пагинацией."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    inventory_items = db.get_player_inventory_with_details(user_id)
    sorted_items = []

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
            display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
            inventory_text += f"• {display_name} — <b>{item.quantity} шт.</b>\n"

        # Клавиатура с кнопками предметов (2 в строке)
        keyboard_rows = []
        current_row = []
        for item in page_items:
            display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
            btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {display_name}"
            callback = f"view_{item.id}_p{page}"
            current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
            if len(current_row) == 2:
                keyboard_rows.append(current_row)
                current_row = []
        if current_row:
            keyboard_rows.append(current_row)

    # Пагинация (кнопки навигации) с циклической навигацией
    if total_pages > 1:
        # Циклическая навигация: с первой страницы предыдущая - это последняя
        prev_page = total_pages if page == 1 else page - 1
        # Циклическая навигация: с последней страницы следующая - это первая
        next_page = 1 if page == total_pages else page + 1
        
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"inventory_p{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"inventory_p{next_page}"),
        ])

    # Кнопка поиска по названию и назад в меню
    keyboard_rows.append([InlineKeyboardButton("🔎 Поиск по названию", callback_data='inventory_search_start')])
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


async def start_inventory_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик начала поиска по названию в инвентаре."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Устанавливаем флаг ожидания поиска
    context.user_data['awaiting_inventory_search'] = True
    
    # Формируем сообщение с инструкцией
    search_text = (
        "🔎 <b>Поиск по названию в инвентаре</b>\n\n"
        "Введите название энергетика, который хотите найти в своём инвентаре.\n"
        "Поиск не чувствителен к регистру."
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отменить поиск", callback_data='inventory_search_cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(search_text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(
            chat_id=user_id,
            text=search_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


async def show_inventory_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str, page: int = 1):
    """Показывает результаты поиска по инвентарю с пагинацией."""
    user_id = update.effective_user.id
    inventory_items = db.get_player_inventory_with_details(user_id)
    
    # Фильтруем по поисковому запросу (нечувствительно к регистру)
    search_lower = search_query.lower()
    filtered_items = [
        item for item in inventory_items
        if search_lower in item.drink.name.lower()
    ]
    
    # Сохраняем поисковый запрос в context для пагинации
    context.user_data['last_inventory_search'] = search_query
    
    if page < 1:
        page = 1
    
    # Если ничего не найдено
    if not filtered_items:
        search_text = (
            f"🔎 <b>Результаты поиска: \"{search_query}\"</b>\n\n"
            "❌ Ничего не найдено в вашем инвентаре.\n"
            "Попробуйте изменить поисковый запрос."
        )
        keyboard_rows = [
            [InlineKeyboardButton("🔄 Новый поиск", callback_data='inventory_search_start')],
            [InlineKeyboardButton("📦 К инвентарю", callback_data='inventory')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_rows)
        
        message = update.effective_message
        if isinstance(update, Update) and update.callback_query:
            try:
                await update.callback_query.edit_message_text(search_text, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=search_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            await message.reply_text(search_text, reply_markup=reply_markup, parse_mode='HTML')
        return
    
    # Сортировка по редкости
    sorted_items = sorted(
        filtered_items,
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
    
    # Формируем текст результатов
    search_text = (
        f"🔎 <b>Результаты поиска: \"{search_query}\"</b>\n"
        f"Найдено: {total_items} предмет(ов)\n"
        f"Страница {page}/{total_pages}\n"
    )
    
    current_rarity = None
    for item in page_items:
        if item.rarity != current_rarity:
            rarity_emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
            search_text += f"\n<b>{rarity_emoji} {item.rarity}</b>\n"
            current_rarity = item.rarity
        display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
        search_text += f"• {display_name} — <b>{item.quantity} шт.</b>\n"
    
    # Клавиатура с кнопками предметов (2 в строке)
    keyboard_rows = []
    current_row = []
    for item in page_items:
        display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
        btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {display_name}"
        callback = f"view_{item.id}_sp{page}"
        current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
        if len(current_row) == 2:
            keyboard_rows.append(current_row)
            current_row = []
    if current_row:
        keyboard_rows.append(current_row)
    
    # Пагинация
    if total_pages > 1:
        prev_page = total_pages if page == 1 else page - 1
        next_page = 1 if page == total_pages else page + 1
        
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"inventory_search_p{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"inventory_search_p{next_page}"),
        ])
    
    # Кнопки управления
    keyboard_rows.append([
        InlineKeyboardButton("🔄 Новый поиск", callback_data='inventory_search_start'),
        InlineKeyboardButton("📦 К инвентарю", callback_data='inventory')
    ])
    keyboard_rows.append([InlineKeyboardButton("🔙 В меню", callback_data='menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    
    # Отправляем или редактируем сообщение
    message = update.effective_message
    if isinstance(update, Update) and update.callback_query:
        try:
            await update.callback_query.edit_message_text(search_text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(
                chat_id=user_id,
                text=search_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        await message.reply_text(search_text, reply_markup=reply_markup, parse_mode='HTML')


async def inventory_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет поиск и возвращает к инвентарю."""
    query = update.callback_query
    await query.answer()
    
    # Очищаем флаг ожидания поиска
    context.user_data.pop('awaiting_inventory_search', None)
    context.user_data.pop('last_inventory_search', None)
    
    # Возвращаемся к инвентарю
    await show_inventory(update, context)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает расширенную статистику игрока."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    lang = player.language

    rating_value = int(getattr(player, 'rating', 0) or 0)
    rating_bonus = db.get_rating_bonus_percent(rating_value)
    if lang == 'ru':
        rating_line = f"⭐ <b>Рейтинг:</b> {rating_value}\n💹 <b>Бонус продажи:</b> +{rating_bonus:.1f}%"
    else:
        rating_line = f"⭐ <b>Rating:</b> {rating_value}\n💹 <b>Sell bonus:</b> +{rating_bonus:.1f}%"
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
    vip_plus_ts = db.get_vip_plus_until(user_id)
    vip_active = bool(vip_ts and time.time() < vip_ts)
    vip_plus_active = bool(vip_plus_ts and time.time() < vip_plus_ts)

    base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
    if vip_plus_active:
        search_cd = base_search_cd / 4
    elif vip_active:
        search_cd = base_search_cd / 2
    else:
        search_cd = base_search_cd
    last_search_val = float(getattr(player, 'last_search', 0) or 0)
    search_time_left = max(0, search_cd - (time.time() - last_search_val))

    base_bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
    if vip_plus_active:
        bonus_cd = base_bonus_cd / 4
    elif vip_active:
        bonus_cd = base_bonus_cd / 2
    else:
        bonus_cd = base_bonus_cd
    last_bonus_claim_val = float(getattr(player, 'last_bonus_claim', 0) or 0)
    bonus_time_left = max(0, bonus_cd - (time.time() - last_bonus_claim_val))
    
    # === ЗАГОЛОВОК И ПРОФИЛЬ ===
    stats_text = f"<b>📊 Статистика игрока</b>\n"
    stats_text += f"━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Информация о пользователе
    username_display = f"@{user.username}" if user.username else user.first_name
    stats_text += f"👤 <b>Игрок:</b> {username_display}\n"
    stats_text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    
    # VIP статус
    if vip_plus_active:
        vip_until_str = safe_format_timestamp(vip_plus_ts, '%d.%m.%Y %H:%M')
        stats_text += f"💎 <b>Статус:</b> {VIP_PLUS_EMOJI} V.I.P+ (до {vip_until_str})\n"
    elif vip_active:
        vip_until_str = safe_format_timestamp(vip_ts, '%d.%m.%Y %H:%M')
        stats_text += f"👑 <b>Статус:</b> {VIP_EMOJI} V.I.P (до {vip_until_str})\n"
    else:
        stats_text += f"📊 <b>Статус:</b> Обычный игрок\n"
    
    stats_text += f"\n"

    # === БАЛАНС И КОЛЛЕКЦИЯ ===
    stats_text += f"<b>💰 Экономика и коллекция:</b>\n"
    stats_text += f"• Монет: <b>{player.coins:,}</b> 🪙\n"
    stats_text += f"• Всего энергетиков: <b>{total_drinks}</b> 🥤\n"
    stats_text += f"• Уникальных видов: <b>{unique_drinks}</b> 🔑\n"
    
    # Прогресс коллекции (процент от всех напитков)
    try:
        total_points = db.get_total_collection_points()
        if total_points > 0:
            # unique_drinks - это количество записей в inventory_items, 
            # что соответствует уникальным парам (напиток, редкость).
            # Это именно то, что нам нужно для числителя.
            collection_percent = (unique_drinks / total_points) * 100
            progress_bar = create_progress_bar(collection_percent, length=10)
            stats_text += f"• Прогресс коллекции: {progress_bar} {collection_percent:.1f}%\n"
    except:
        pass
    
    stats_text += f"\n"

    # === АКТИВНОСТЬ ===
    stats_text += f"<b>⚡ Активность:</b>\n"
    
    # Последний поиск
    if player.last_search:
        last_search_str = safe_format_timestamp(player.last_search, '%d.%m.%Y %H:%M')
        stats_text += f"• Последний поиск: {last_search_str}\n"
    else:
        stats_text += f"• Последний поиск: Еще не было\n"
    
    # Последний бонус
    if player.last_bonus_claim:
        last_bonus_str = safe_format_timestamp(player.last_bonus_claim, '%d.%m.%Y %H:%M')
        stats_text += f"• Последний бонус: {last_bonus_str}\n"
    else:
        stats_text += f"• Последний бонус: Еще не было\n"
    
    # Автопоиск (только для VIP)
    if vip_active or vip_plus_active:
        auto_status = "Включен ✅" if player.auto_search_enabled else "Выключен ❌"
        stats_text += f"• Автопоиск: {auto_status}\n"
        
        # Получаем актуальный счетчик с учетом сброса
        now_ts = int(time.time())
        reset_ts = int(player.auto_search_reset_ts or 0)
        current_count = int(player.auto_search_count or 0)
        
        # Если время сброса прошло, счетчик должен быть 0
        if reset_ts == 0 or now_ts >= reset_ts:
            current_count = 0
        
        # Получаем правильный лимит с учетом VIP+ и бустов
        try:
            daily_limit = db.get_auto_search_daily_limit(user_id)
        except:
            # Если ошибка, используем базовый лимит
            daily_limit = AUTO_SEARCH_DAILY_LIMIT
            if vip_plus_active:
                daily_limit *= 2
        
        stats_text += f"  └ Поисков сегодня: {current_count}/{daily_limit}\n"
        
        # Показываем время до сброса если счетчик активен
        if reset_ts > now_ts and current_count > 0:
            time_to_reset = reset_ts - now_ts
            hours = time_to_reset // 3600
            minutes = (time_to_reset % 3600) // 60
            if hours > 0:
                stats_text += f"  └ Сброс через: {hours} ч. {minutes} мин.\n"
            elif minutes > 0:
                stats_text += f"  └ Сброс через: {minutes} мин.\n"
    
    stats_text += f"\n"

    # === СТАТИСТИКА КАЗИНО ===
    casino_total_games = (player.casino_wins or 0) + (player.casino_losses or 0)
    if casino_total_games > 0:
        stats_text += f"<b>🎰 Статистика казино:</b>\n"
        stats_text += f"• Всего игр: <b>{casino_total_games}</b>\n"
        stats_text += f"• Побед: <b>{player.casino_wins or 0}</b> 🎉\n"
        stats_text += f"• Поражений: <b>{player.casino_losses or 0}</b> 😔\n"
        
        if casino_total_games > 0:
            win_rate = (player.casino_wins or 0) / casino_total_games * 100
            stats_text += f"• Винрейт: <b>{win_rate:.1f}%</b>\n"
        
        stats_text += f"\n"

    # === ПО РЕДКОСТЯМ ===
    if rarity_counter:
        stats_text += f"<b>🎨 По редкостям:</b>\n"
        for rarity in RARITY_ORDER:
            if rarity in rarity_counter:
                emoji = COLOR_EMOJIS.get(rarity, '⚫')
                stats_text += f"{emoji} {rarity}: <b>{rarity_counter[rarity]}</b>\n"
        stats_text += f"\n"

    # === ТОП-3 РЕДКИХ НАХОДОК ===
    if top_items:
        stats_text += f"<b>🏆 Редкие находки:</b>\n"
        for idx, item in enumerate(top_items, start=1):
            emoji = ['🥇', '🥈', '🥉'][idx - 1] if idx <= 3 else '▫️'
            rarity_emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
            stats_text += f"{emoji} {item.drink.name} ({rarity_emoji} {item.rarity}) × {item.quantity}\n"
        stats_text += f"\n"

    # === ДОСТИЖЕНИЯ ===
    achievements = []
    
    # Достижения по коллекции
    if unique_drinks >= 100:
        achievements.append("🏅 Коллекционер (100+ видов)")
    elif unique_drinks >= 50:
        achievements.append("🎖️ Собиратель (50+ видов)")
    elif unique_drinks >= 25:
        achievements.append("⭐ Энтузиаст (25+ видов)")
    
    # Достижения по балансу
    if player.coins >= 1000000:
        achievements.append("💎 Миллионер")
    elif player.coins >= 100000:
        achievements.append("💰 Богач")
    
    # Достижения казино
    if (player.casino_wins or 0) >= 100:
        achievements.append("🎰 Мастер казино")
    elif (player.casino_wins or 0) >= 50:
        achievements.append("🎲 Везунчик")
    
    # Достижения VIP
    if vip_plus_active:
        achievements.append("💎 VIP+ персона")
    elif vip_active:
        achievements.append("👑 VIP персона")
    
    if achievements:
        stats_text += f"<b>🏅 Достижения:</b>\n"
        for achievement in achievements:
            stats_text += f"• {achievement}\n"
    
    stats_text += f"\n━━━━━━━━━━━━━━━━━━━"

    back_label = "🔙 Назад" if lang == 'ru' else "🔙 Back"
    back_callback = 'my_profile' if query.data == 'profile_stats' else 'menu'
    keyboard = [[InlineKeyboardButton(back_label, callback_data=back_callback)]]

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


async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    lang = player.language

    username_display = f"@{user.username}" if user.username else user.first_name

    vip_ts = db.get_vip_until(user_id)
    vip_plus_ts = db.get_vip_plus_until(user_id)
    vip_active = bool(vip_ts and time.time() < vip_ts)
    vip_plus_active = bool(vip_plus_ts and time.time() < vip_plus_ts)

    base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
    if vip_plus_active:
        search_cd = base_search_cd / 4
    elif vip_active:
        search_cd = base_search_cd / 2
    else:
        search_cd = base_search_cd
    last_search_val = float(getattr(player, 'last_search', 0) or 0)
    search_time_left = max(0, search_cd - (time.time() - last_search_val))

    base_bonus_cd = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN)
    if vip_plus_active:
        bonus_cd = base_bonus_cd / 4
    elif vip_active:
        bonus_cd = base_bonus_cd / 2
    else:
        bonus_cd = base_bonus_cd
    last_bonus_claim_val = float(getattr(player, 'last_bonus_claim', 0) or 0)
    bonus_time_left = max(0, bonus_cd - (time.time() - last_bonus_claim_val))

    if vip_plus_active:
        vip_until_str = safe_format_timestamp(vip_plus_ts, '%d.%m.%Y %H:%M')
        status_line = f"💎 <b>Статус:</b> {VIP_PLUS_EMOJI} V.I.P+ (до {vip_until_str})" if lang == 'ru' else f"💎 <b>Status:</b> {VIP_PLUS_EMOJI} V.I.P+ (until {vip_until_str})"
    elif vip_active:
        vip_until_str = safe_format_timestamp(vip_ts, '%d.%m.%Y %H:%M')
        status_line = f"👑 <b>Статус:</b> {VIP_EMOJI} V.I.P (до {vip_until_str})" if lang == 'ru' else f"👑 <b>Status:</b> {VIP_EMOJI} V.I.P (until {vip_until_str})"
    else:
        status_line = "📊 <b>Статус:</b> Обычный игрок" if lang == 'ru' else "📊 <b>Status:</b> Regular player"

    timing_lines = []
    if lang == 'ru':
        if search_time_left > 0:
            timing_lines.append(f"🔎 <b>Поиск:</b> ⏳ {int(search_time_left // 60)}:{int(search_time_left % 60):02d}")
        else:
            timing_lines.append("🔎 <b>Поиск:</b> ✅")

        if bonus_time_left > 0:
            hours, remainder = divmod(int(bonus_time_left), 3600)
            minutes, seconds = divmod(remainder, 60)
            timing_lines.append(f"🎁 <b>Бонус:</b> ⏳ {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            timing_lines.append("🎁 <b>Бонус:</b> ✅")
    else:
        if search_time_left > 0:
            timing_lines.append(f"🔎 <b>Search:</b> ⏳ {int(search_time_left // 60)}:{int(search_time_left % 60):02d}")
        else:
            timing_lines.append("🔎 <b>Search:</b> ✅")

        if bonus_time_left > 0:
            hours, remainder = divmod(int(bonus_time_left), 3600)
            minutes, seconds = divmod(remainder, 60)
            timing_lines.append(f"🎁 <b>Bonus:</b> ⏳ {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            timing_lines.append("🎁 <b>Bonus:</b> ✅")

    timing_block = "\n" + "\n".join(timing_lines) if timing_lines else ""

    auto_line = ""
    if vip_active or vip_plus_active:
        auto_enabled = bool(getattr(player, 'auto_search_enabled', False))
        auto_state = "Включен ✅" if auto_enabled else "Выключен ❌"

        now_ts = int(time.time())
        reset_ts = int(getattr(player, 'auto_search_reset_ts', 0) or 0)
        current_count = int(getattr(player, 'auto_search_count', 0) or 0)
        if reset_ts == 0 or now_ts >= reset_ts:
            current_count = 0
        try:
            daily_limit = db.get_auto_search_daily_limit(user_id)
        except Exception:
            daily_limit = AUTO_SEARCH_DAILY_LIMIT
            if vip_plus_active:
                daily_limit *= 2

        if lang == 'ru':
            auto_line = f"\n🤖 <b>Автопоиск:</b> {auto_state}\n📊 <b>Сегодня:</b> {current_count}/{daily_limit}"
        else:
            auto_line = f"\n🤖 <b>Auto-search:</b> {auto_state}\n📊 <b>Today:</b> {current_count}/{daily_limit}"

    # Получаем рейтинг пользователя
    rating = int(getattr(player, 'rating', 0) or 0)
    rating_line = f"🏆 <b>Рейтинг:</b> {rating}" if rating > 0 else ""
    
    title = "<b>👤 Мой профиль</b>" if lang == 'ru' else "<b>👤 My profile</b>"
    profile_text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Игрок:</b> {username_display}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>Баланс:</b> {int(getattr(player, 'coins', 0) or 0)} 🪙\n"
        f"{rating_line}\n"
        f"{status_line}"
        f"{timing_block}"
        f"{auto_line}"
    )

    try:
        pending_cnt = db.get_pending_friend_requests_count(user_id)
    except Exception:
        pending_cnt = 0
    if pending_cnt and int(pending_cnt) > 0:
        friends_label = (f"👥 Друзья ({int(pending_cnt)})" if lang == 'ru' else f"👥 Friends ({int(pending_cnt)})")
    else:
        friends_label = "👥 Друзья" if lang == 'ru' else "👥 Friends"
    stats_label = "📊 Статистика" if lang == 'ru' else "📊 Stats"
    boosts_label = "🚀 Бусты" if lang == 'ru' else "🚀 Boosts"
    promo_label = "🎟 Промокод" if lang == 'ru' else "🎟 Promo"
    vip_label = "👑 VIP" if lang == 'ru' else "👑 VIP"
    vip_plus_label = f"{VIP_PLUS_EMOJI} VIP+"
    favorites_label = t(lang, 'favorite_energy_drinks')
    back_label = "🔙 В меню" if lang == 'ru' else "🔙 Menu"

    keyboard = [
        [InlineKeyboardButton(friends_label, callback_data='profile_friends')],
        [InlineKeyboardButton(stats_label, callback_data='profile_stats')],
        [InlineKeyboardButton(boosts_label, callback_data='profile_boosts')],
        [InlineKeyboardButton(favorites_label, callback_data='profile_favorites')],
        [InlineKeyboardButton(promo_label, callback_data='promo_enter')],
        [InlineKeyboardButton(vip_label, callback_data='vip_menu'), InlineKeyboardButton(vip_plus_label, callback_data='vip_plus_menu')],
        [InlineKeyboardButton(back_label, callback_data='menu')],
    ]

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_profile_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # сбрасываем режимы ожидания ввода в разделе друзей
    try:
        context.user_data.pop('awaiting_friend_username_search', None)
        context.user_data.pop('awaiting_friend_transfer', None)
    except Exception:
        pass

    try:
        pending_cnt = db.get_pending_friend_requests_count(user.id)
    except Exception:
        pending_cnt = 0
    pending_cnt = int(pending_cnt or 0)

    title = "👥 <b>Друзья</b>" if lang == 'ru' else "👥 <b>Friends</b>"
    text_lines = [title, "", "━━━━━━━━━━━━━━━━━━━", ""]
    if lang == 'ru':
        text_lines.append(f"📨 Заявки в друзья: <b>{pending_cnt}</b>")
        text_lines.append("Выберите действие ниже.")
    else:
        text_lines.append(f"📨 Friend requests: <b>{pending_cnt}</b>")
        text_lines.append("Choose an action below.")
    text = "\n".join(text_lines)

    kb = []
    kb.append([InlineKeyboardButton("➕ Добавить друга" if lang == 'ru' else "➕ Add friend", callback_data='friends_add_start')])
    kb.append([InlineKeyboardButton(("📨 Заявки" if lang == 'ru' else "📨 Requests") + (f" ({pending_cnt})" if pending_cnt > 0 else ""), callback_data='friends_requests_0')])
    kb.append([InlineKeyboardButton("👤 Мои друзья" if lang == 'ru' else "👤 My friends", callback_data='friends_list_0')])
    kb.append([InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='my_profile')])
    keyboard = kb

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def friends_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    context.user_data['awaiting_friend_username_search'] = True

    text = (
        "Введите ник друга (без @ или с @). Я покажу совпадения." if lang == 'ru'
        else "Enter friend's username (with or without @). I'll show matches."
    )
    kb = [[InlineKeyboardButton("❌ Отмена" if lang == 'ru' else "❌ Cancel", callback_data='profile_friends')]]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb))


async def friends_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str, page: int = 0):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.effective_user

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    # Используем существующую систему поиска игроков
    res = db.find_player_by_identifier(search_query)
    if res.get('ok') and res.get('player'):
        p = res.get('player')
        uid = int(getattr(p, 'user_id', 0) or 0)
        uname = getattr(p, 'username', None) or str(uid)

        if uid == int(user.id):
            text = "Нельзя добавить себя." if lang == 'ru' else "You can't add yourself."
            kb = [[InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='profile_friends')]]
        else:
            title = "➕ <b>Добавить друга</b>" if lang == 'ru' else "➕ <b>Add friend</b>"
            text = (
                f"{title}\n\n"
                f"Найден пользователь: @{html.escape(str(uname))}\n"
                f"🆔 <code>{uid}</code>"
                if lang == 'ru'
                else f"{title}\n\nFound user: @{html.escape(str(uname))}\n🆔 <code>{uid}</code>"
            )
            kb = [
                [InlineKeyboardButton("✅ Отправить заявку" if lang == 'ru' else "✅ Send request", callback_data=f'friends_add_pick:{uid}')],
                [InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='profile_friends')],
            ]

        if query:
            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        else:
            await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if res.get('reason') == 'multiple':
        candidates = res.get('candidates') or []
        title = "➕ <b>Добавить друга</b>" if lang == 'ru' else "➕ <b>Add friend</b>"
        if lang == 'ru':
            text = f"{title}\n\nНайдено несколько пользователей, выберите:" 
        else:
            text = f"{title}\n\nMultiple users found, pick one:"

        kb = []
        for c in candidates:
            try:
                uid = int(c.get('user_id') or 0)
            except Exception:
                uid = 0
            uname = c.get('username') or str(uid)
            if not uid or uid == int(user.id):
                continue
            kb.append([InlineKeyboardButton(f"@{uname} (ID {uid})", callback_data=f'friends_add_pick:{uid}')])
        kb.append([InlineKeyboardButton("🔎 Новый поиск" if lang == 'ru' else "🔎 New search", callback_data='friends_add_start')])
        kb.append([InlineKeyboardButton("❌ Отмена" if lang == 'ru' else "❌ Cancel", callback_data='profile_friends')])

        if query:
            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        else:
            await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    text = "❌ Ник не найден. Попробуйте ещё раз." if lang == 'ru' else "❌ No matches. Try again."
    kb = [
        [InlineKeyboardButton("🔎 Новый поиск" if lang == 'ru' else "🔎 New search", callback_data='friends_add_start')],
        [InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='profile_friends')],
    ]
    if query:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def friends_add_pick(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    try:
        res = db.send_friend_request(user.id, int(target_user_id))
    except Exception:
        res = {"ok": False, "reason": "exception"}

    if not res.get('ok'):
        reason = res.get('reason')
        if reason == 'self':
            msg = "Нельзя добавить себя." if lang == 'ru' else "You can't add yourself."
        elif reason == 'already_friends':
            msg = "Вы уже друзья." if lang == 'ru' else "You're already friends."
        elif reason == 'already_sent':
            msg = "Заявка уже отправлена." if lang == 'ru' else "Request already sent."
        else:
            msg = "❌ Ошибка. Попробуйте позже." if lang == 'ru' else "❌ Error. Try later."
        await query.answer(msg, show_alert=True)
        await show_profile_friends(update, context)
        return

    msg_ok = "✅ Заявка отправлена!" if lang == 'ru' else "✅ Friend request sent!"
    if res.get('auto_accepted'):
        msg_ok = "✅ Вы теперь друзья!" if lang == 'ru' else "✅ You're now friends!"
    await query.answer(msg_ok, show_alert=True)

    try:
        sender_name = user.username or user.first_name or str(user.id)
        notify_text = f"👥 Вам пришла заявка в друзья от @{sender_name}." if lang == 'ru' else f"👥 You received a friend request from @{sender_name}."
        await context.bot.send_message(chat_id=int(target_user_id), text=notify_text)
    except Exception:
        pass

    await show_profile_friends(update, context)


async def friends_requests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    res = db.list_pending_incoming_friend_requests(user.id, page=page, per_page=6)
    items = (res or {}).get('items') or []
    total = int((res or {}).get('total') or 0)
    per_page = int((res or {}).get('per_page') or 6)

    title = "📨 <b>Заявки в друзья</b>" if lang == 'ru' else "📨 <b>Friend requests</b>"
    text_lines = [title, "", "━━━━━━━━━━━━━━━━━━━", ""]
    if not items:
        text_lines.append("Пока нет заявок." if lang == 'ru' else "No requests yet.")
    text = "\n".join(text_lines)

    kb = []
    for it in items:
        rid = int(it.get('request_id') or 0)
        uid = int(it.get('from_user_id') or 0)
        uname = it.get('from_username') or str(uid)
        kb.append([InlineKeyboardButton(f"@{uname} (ID {uid})", callback_data=f'friends_req_open:{rid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f'friends_requests_{page-1}'))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f'friends_requests_{page+1}'))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='profile_friends')])
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')


async def friends_open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_user_id: int):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.effective_user

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    if not db.are_friends(user.id, int(friend_user_id)):
        text = "❌ Этот игрок не у вас в друзьях." if lang == 'ru' else "❌ This player is not in your friends list."
        kb = [[InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='friends_list_0')]]
        if query:
            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    try:
        dbs = SessionLocal()
        p = dbs.query(Player).filter(Player.user_id == int(friend_user_id)).first()
    finally:
        try:
            dbs.close()
        except Exception:
            pass

    uname = getattr(p, 'username', None) if p else None
    uname_disp = f"@{uname}" if uname else f"ID {int(friend_user_id)}"

    title = "👥 <b>Друг</b>" if lang == 'ru' else "👥 <b>Friend</b>"
    if lang == 'ru':
        text = (
            f"{title}\n\n"
            f"{html.escape(uname_disp)}\n"
            f"🆔 <code>{int(friend_user_id)}</code>\n\n"
            f"Лимиты:\n"
            f"- Монеты: до 10 000 в сутки\n"
            f"- Фрагменты: до 5 в сутки\n"
            f"- VIP на 7 дней: раз в 2 недели (только VIP, без VIP+)\n"
            f"- Рейтинг: до 3 за 48 часов"
        )
    else:
        text = (
            f"{title}\n\n"
            f"{html.escape(uname_disp)}\n"
            f"🆔 <code>{int(friend_user_id)}</code>\n\n"
            f"Limits:\n"
            f"- Coins: up to 10,000 per day\n"
            f"- Fragments: up to 5 per day\n"
            f"- VIP 7d: once per 2 weeks (VIP only, no VIP+)\n"
            f"- Rating: up to 3 per 48 hours"
        )

    kb = [
        [InlineKeyboardButton("💰 Передать монеты" if lang == 'ru' else "💰 Send coins", callback_data=f'friends_give_coins:{int(friend_user_id)}')],
        [InlineKeyboardButton("🧩 Передать фрагменты" if lang == 'ru' else "🧩 Send fragments", callback_data=f'friends_give_fragments:{int(friend_user_id)}')],
        [InlineKeyboardButton("👑 Подарить VIP (7 дней)" if lang == 'ru' else "👑 Gift VIP (7 days)", callback_data=f'friends_give_vip7:{int(friend_user_id)}')],
        [InlineKeyboardButton("🏆 Передать рейтинг" if lang == 'ru' else "🏆 Send rating", callback_data=f'friends_give_rating:{int(friend_user_id)}')],
        [InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='friends_list_0')],
    ]
    if query:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    else:
        await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb))


async def friends_start_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, to_user_id: int):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    context.user_data['awaiting_friend_transfer'] = {"kind": str(kind), "to_user_id": int(to_user_id)}

    if kind == 'coins':
        prompt = "Введите количество монет (1..10000 за сутки):" if lang == 'ru' else "Enter coin amount (1..10000 per day):"
    elif kind == 'fragments':
        prompt = "Введите количество фрагментов (1..5 за сутки):" if lang == 'ru' else "Enter fragments amount (1..5 per day):"
    else:
        prompt = "Введите количество рейтинга (1..3 за 48 часов):" if lang == 'ru' else "Enter rating amount (1..3 per 48 hours):"

    kb = [[InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data=f'friends_open:{int(to_user_id)}')]]
    try:
        await query.edit_message_text(prompt, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=prompt, reply_markup=InlineKeyboardMarkup(kb))


async def friends_request_open(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    res = db.list_pending_incoming_friend_requests(user.id, page=0, per_page=50)
    items = (res or {}).get('items') or []
    target = None
    for it in items:
        if int(it.get('request_id') or 0) == int(request_id):
            target = it
            break
    if not target:
        await query.answer("Заявка не найдена." if lang == 'ru' else "Request not found.", show_alert=True)
        await friends_requests_menu(update, context, page=0)
        return

    uname = target.get('from_username') or str(target.get('from_user_id'))
    uid = int(target.get('from_user_id') or 0)

    title = "🤝 <b>Предложение дружбы</b>" if lang == 'ru' else "🤝 <b>Friend request</b>"
    text = f"{title}\n\nОт: @{html.escape(str(uname))} (ID <code>{uid}</code>)" if lang == 'ru' else f"{title}\n\nFrom: @{html.escape(str(uname))} (ID <code>{uid}</code>)"

    kb = [
        [
            InlineKeyboardButton("✅ Принять" if lang == 'ru' else "✅ Accept", callback_data=f'friends_req_accept:{request_id}'),
            InlineKeyboardButton("❌ Отклонить" if lang == 'ru' else "❌ Reject", callback_data=f'friends_req_reject:{request_id}')
        ],
        [InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='friends_requests_0')]
    ]
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')


async def friends_req_accept(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    res = db.accept_friend_request(user.id, int(request_id))
    if not res or not res.get('ok'):
        await query.answer("❌ Не удалось принять." if lang == 'ru' else "❌ Failed to accept.", show_alert=True)
        await friends_requests_menu(update, context, page=0)
        return

    from_uid = int(res.get('from_user_id') or 0)
    try:
        await context.bot.send_message(chat_id=from_uid, text="✅ Вашу заявку в друзья приняли!" if lang == 'ru' else "✅ Your friend request was accepted!")
    except Exception:
        pass

    await query.answer("✅ Добавлен в друзья" if lang == 'ru' else "✅ Added", show_alert=True)
    await show_profile_friends(update, context)


async def friends_req_reject(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    res = db.reject_friend_request(user.id, int(request_id))
    if not res or not res.get('ok'):
        await query.answer("❌ Не удалось отклонить." if lang == 'ru' else "❌ Failed to reject.", show_alert=True)
        await friends_requests_menu(update, context, page=0)
        return

    from_uid = int(res.get('from_user_id') or 0)
    try:
        await context.bot.send_message(chat_id=from_uid, text="❌ Вашу заявку в друзья отклонили." if lang == 'ru' else "❌ Your friend request was rejected.")
    except Exception:
        pass

    await query.answer("✅ Отклонено" if lang == 'ru' else "✅ Rejected", show_alert=True)
    await show_profile_friends(update, context)


async def friends_list_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    res = db.list_friends(user.id, page=page, per_page=8)
    items = (res or {}).get('items') or []
    total = int((res or {}).get('total') or 0)
    per_page = int((res or {}).get('per_page') or 8)

    title = "👤 <b>Мои друзья</b>" if lang == 'ru' else "👤 <b>My friends</b>"
    text_lines = [title, "", "━━━━━━━━━━━━━━━━━━━", ""]
    if not items:
        text_lines.append("Список пуст." if lang == 'ru' else "List is empty.")
    text = "\n".join(text_lines)

    kb = []
    for it in items:
        uid = int(it.get('user_id') or 0)
        uname = it.get('username') or str(uid)
        kb.append([InlineKeyboardButton(f"@{uname} (ID {uid})", callback_data=f'friends_open:{uid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f'friends_list_{page-1}'))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f'friends_list_{page+1}'))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🔙 Назад" if lang == 'ru' else "🔙 Back", callback_data='profile_friends')])
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')


def _farmer_fert_priority_from_player(player: Player) -> list[int]:
    try:
        prio_ids = json.loads(getattr(player, 'farmer_fert_priority', '[]') or '[]')
        prio_ids = [int(x) for x in prio_ids] if isinstance(prio_ids, list) else []
    except Exception:
        prio_ids = []
    return prio_ids


async def show_selyuk_farmer_fert_priority(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    prio_ids = _farmer_fert_priority_from_player(player)
    inv = db.get_fertilizer_inventory(user.id) or []

    ferts = []
    for it in inv:
        fz = getattr(it, 'fertilizer', None)
        qty = int(getattr(it, 'quantity', 0) or 0)
        if not fz:
            continue
        ferts.append((fz, qty))
    ferts.sort(key=lambda x: int(getattr(x[0], 'id', 0) or 0))

    prio_names = []
    id_to_name = {int(getattr(fz, 'id', 0) or 0): html.escape(getattr(fz, 'name', 'Удобрение')) for fz, _ in ferts}
    for fid in prio_ids:
        if fid in id_to_name:
            prio_names.append(id_to_name[fid])

    text = "🧪 <b>Приоритет удобрений (ур.4)</b>\n\n"
    if prio_names:
        text += "Текущий приоритет:\n" + "\n".join([f"{i+1}. {n}" for i, n in enumerate(prio_names[:10])])
    else:
        text += "Пока пусто. Добавь удобрения в приоритет ниже."

    per_page = 6
    page = max(0, int(page or 0))
    start = page * per_page
    chunk = ferts[start:start+per_page]
    keyboard = []

    for fz, qty in chunk:
        fid = int(getattr(fz, 'id', 0) or 0)
        name = html.escape(getattr(fz, 'name', 'Удобрение'))
        in_prio = fid in set(prio_ids)
        if in_prio:
            keyboard.append([InlineKeyboardButton(f"🗑️ Убрать: {name}", callback_data=f'selyuk_farmer_fert_prio_rm_{fid}_{page}')])
        else:
            keyboard.append([InlineKeyboardButton(f"➕ В приоритет: {name} (x{qty})", callback_data=f'selyuk_farmer_fert_prio_add_{fid}_{page}')])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f'selyuk_farmer_fert_prio_{page-1}'))
    if start + per_page < len(ferts):
        nav.append(InlineKeyboardButton("➡️", callback_data=f'selyuk_farmer_fert_prio_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_settings')])
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_profile_boosts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    title = "🚀 <b>Бусты</b>" if lang == 'ru' else "🚀 <b>Boosts</b>"
    text_lines = [title, "", "━━━━━━━━━━━━━━━━━━━", ""]

    try:
        boost_info = db.get_boost_info(user.id)
        if boost_info.get('is_active'):
            if lang == 'ru':
                text_lines.append(f"✅ Активен автопоиск-буст")
                text_lines.append(f"📊 Дополнительно: +{boost_info.get('boost_count', 0)} поисков")
                text_lines.append(f"⏰ Осталось: {boost_info.get('time_remaining_formatted', '—')}")
                text_lines.append(f"📅 Истекает: {boost_info.get('boost_until_formatted', '—')}")
            else:
                text_lines.append("✅ Auto-search boost is active")
                text_lines.append(f"📊 Extra: +{boost_info.get('boost_count', 0)} searches")
                text_lines.append(f"⏰ Remaining: {boost_info.get('time_remaining_formatted', '—')}")
                text_lines.append(f"📅 Expires: {boost_info.get('boost_until_formatted', '—')}")
        elif boost_info.get('has_boost'):
            text_lines.append("⏱ Буст автопоиска истёк" if lang == 'ru' else "⏱ Auto-search boost expired")
        else:
            text_lines.append("ℹ️ Активных бустов нет" if lang == 'ru' else "ℹ️ No active boosts")
    except Exception:
        text_lines.append("ℹ️ Активных бустов нет" if lang == 'ru' else "ℹ️ No active boosts")

    try:
        history = db.get_user_boost_history(user.id, limit=5)
        if history:
            text_lines.append("")
            text_lines.append("<b>Последние:</b>" if lang == 'ru' else "<b>Recent:</b>")
            for record in history:
                dt = record.get('formatted_date') or ''
                action = record.get('action_text') or ''
                if dt and action:
                    text_lines.append(f"• {dt} — {action}")
    except Exception:
        pass

    text = "\n".join(text_lines)
    back_label = "🔙 Назад" if lang == 'ru' else "🔙 Back"
    keyboard = [[InlineKeyboardButton(back_label, callback_data='my_profile')]]

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_inventory_by_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь игрока с сортировкой по количеству (для Приёмника)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    inventory_items = db.get_player_inventory_with_details(user_id)
    sorted_items = []

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
            # Вычисляем стоимость продажи с учётом рейтинга
            unit_payout = int(db.get_receiver_unit_payout_for_user(user_id, item.rarity) or 0)
            total_value = unit_payout * item.quantity
            inventory_text += f"{rarity_emoji} <b>{item.drink.name}</b> — {item.quantity} шт. (~{total_value} монет)\n"

        # Клавиатура с кнопками предметов (2 в строке)
        keyboard_rows = []
        current_row = []
        for item in page_items:
            btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {item.drink.name} ({item.quantity})"
            callback = f"view_{item.id}_rp{page}"
            current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
            if len(current_row) == 2:
                keyboard_rows.append(current_row)
                current_row = []
        if current_row:
            keyboard_rows.append(current_row)

    # Пагинация (кнопки навигации) с циклической навигацией
    if total_pages > 1:
        # Циклическая навигация: с первой страницы предыдущая - это последняя
        prev_page = total_pages if page == 1 else page - 1
        # Циклическая навигация: с последней страницы следующая - это первая
        next_page = 1 if page == total_pages else page + 1
        
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"receiver_qty_p{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"receiver_qty_p{next_page}"),
        ])

    # Кнопка массовой продажи - показываем только если есть предметы для продажи
    if sorted_items:
        # Проверяем, есть ли что продавать (предметы с количеством > 1)
        has_items_to_sell = any(item.quantity > 1 for item in sorted_items)
        if has_items_to_sell:
            keyboard_rows.append([
                InlineKeyboardButton(
                    "🗑️ Продать АБСОЛЮТНО все кроме одного",
                    callback_data='sell_absolutely_all_but_one'
                )
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
    user_id = query.from_user.id

    try:
        # Парсим callback_data: view_{item_id} или view_{item_id}_p{page} или view_{item_id}_rp{page}
        parts = query.data.split('_')
        item_id = int(parts[1])
        
        # Определяем страницу и тип инвентаря
        page = 1
        inventory_type = 'normal'  # normal, receiver или search
        
        if len(parts) > 2:
            page_part = parts[2]
            if page_part.startswith('p'):
                page = int(page_part[1:])
                inventory_type = 'normal'
            elif page_part.startswith('rp'):
                page = int(page_part[2:])
                inventory_type = 'receiver'
            elif page_part.startswith('sp'):
                page = int(page_part[2:])
                inventory_type = 'search'
                
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
    unit_payout = int(db.get_receiver_unit_payout_for_user(user_id, rarity) or 0)
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
    
    # Кнопка возврата с сохранением страницы
    if inventory_type == 'receiver':
        back_callback = f'receiver_qty_p{page}'
        back_text = '🔙 Назад к Приёмнику'
    elif inventory_type == 'search':
        back_callback = f'inventory_search_p{page}'
        back_text = '🔙 Назад к поиску'
    else:
        back_callback = f'inventory_p{page}' if page > 1 else 'inventory'
        back_text = '🔙 Назад к инвентарю'
        
    rows.append([InlineKeyboardButton(back_text, callback_data=back_callback)])
    keyboard = InlineKeyboardMarkup(rows)

    image_full_path = os.path.join(ENERGY_IMAGES_DIR, drink.image_path) if drink.image_path else None

    # Удаляем предыдущее сообщение (список инвентаря)
    try:
        await query.message.delete()
    except BadRequest:
        pass

    if image_full_path and os.path.exists(image_full_path):
        with open(image_full_path, 'rb') as photo:
            await _send_photo_long(
                context.bot.send_photo,
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


async def show_profile_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    title = t(lang, 'favorites_title')

    slot_values = []
    for i in (1, 2, 3):
        item_id = int(getattr(player, f'favorite_drink_{i}', 0) or 0)
        if item_id > 0:
            inv_item = db.get_inventory_item(item_id)
            if inv_item and int(getattr(inv_item, 'player_id', 0) or 0) == int(user_id) and getattr(inv_item, 'drink', None):
                name = str(getattr(inv_item.drink, 'name', '') or '').strip() or ("Энергетик" if lang == 'ru' else "Energy drink")
                slot_values.append((i, name))
            else:
                slot_values.append((i, t(lang, 'favorites_empty')))
        else:
            slot_values.append((i, t(lang, 'favorites_empty')))

    lines = [title, "━━━━━━━━━━━━━━━━━━━", ""]
    for i, val in slot_values:
        lines.append(t(lang, 'favorites_slot').format(n=i, value=val))

    text = "\n".join(lines)

    keyboard = []
    for i, val in slot_values:
        label = f"{i}. {val}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"fav_slot_{i}")])
    keyboard.append([InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='my_profile')])

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_favorites_pick_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE, slot: int, page: int = 1):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    slot = int(slot or 0)
    if slot not in (1, 2, 3):
        await query.answer("Ошибка", show_alert=True)
        return

    inventory_items = db.get_player_inventory_with_details(user_id)
    if not inventory_items:
        await query.answer(t(lang, 'favorites_pick_empty_inventory'), show_alert=True)
        await show_profile_favorites(update, context)
        return

    # Сортировка как в show_inventory
    sorted_items = sorted(
        inventory_items,
        key=lambda i: (
            RARITY_ORDER.index(i.rarity) if i.rarity in RARITY_ORDER else len(RARITY_ORDER),
            i.drink.name.lower(),
        )
    )

    total_items = len(sorted_items)
    total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = sorted_items[start_idx:end_idx]

    text = (
        f"{t(lang, 'favorites_pick_title').format(n=slot)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{t(lang, 'inventory')}: {total_items}\n"
        f"{('Страница' if lang == 'ru' else 'Page')} {page}/{total_pages}"
    )

    keyboard_rows = []
    current_row = []
    for item in page_items:
        display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
        btn_text = f"{COLOR_EMOJIS.get(item.rarity,'⚫')} {display_name}"
        callback = f"fav_pick_{slot}_{item.id}_p{page}"
        current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
        if len(current_row) == 2:
            keyboard_rows.append(current_row)
            current_row = []
    if current_row:
        keyboard_rows.append(current_row)

    if total_pages > 1:
        prev_page = total_pages if page == 1 else page - 1
        next_page = 1 if page == total_pages else page + 1
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"fav_pick_page_{slot}_{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"fav_pick_page_{slot}_{next_page}"),
        ])

    keyboard_rows.append([InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='profile_favorites')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


# --- Приёмник: обработка продажи ---
async def show_profile_favorites_v2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    context.user_data.pop('awaiting_favorites_search', None)
    context.user_data.pop('awaiting_favorites_search_slot', None)
    context.user_data.pop('favorites_last_search_query', None)
    context.user_data.pop('favorites_last_search_slot', None)

    title = t(lang, 'favorites_title')
    inventory_items = db.get_player_inventory_with_details(user_id) or []
    by_item_id = {int(getattr(it, 'id', 0) or 0): it for it in inventory_items}

    rarity_slot_counts = {rarity: 0 for rarity in RARITY_ORDER}
    rarity_qty_counts = {rarity: 0 for rarity in RARITY_ORDER}
    slot_values = []
    for i in (1, 2, 3):
        item_id = int(getattr(player, f'favorite_drink_{i}', 0) or 0)
        inv_item = by_item_id.get(item_id)
        if item_id > 0 and inv_item and getattr(inv_item, 'drink', None):
            rarity = str(getattr(inv_item, 'rarity', '') or 'Unknown')
            qty = int(getattr(inv_item, 'quantity', 0) or 0)
            name = str(getattr(inv_item.drink, 'name', '') or '').strip() or ("Энергетик" if lang == 'ru' else "Energy drink")
            emoji = COLOR_EMOJIS.get(rarity, '⚫')
            slot_values.append((i, f"{emoji} {name} x{qty}", True))
            if rarity in rarity_slot_counts:
                rarity_slot_counts[rarity] += 1
                rarity_qty_counts[rarity] += max(0, qty)
        else:
            slot_values.append((i, t(lang, 'favorites_empty'), False))

    lines = [title, "━━━━━━━━━━━━━━━━━━━", ""]
    for i, val, _ in slot_values:
        lines.append(t(lang, 'favorites_slot').format(n=i, value=val))

    lines.append("")
    lines.append("<b>🎨 По редкостям избранного:</b>" if lang == 'ru' else "<b>🎨 Favorite rarities:</b>")
    for rarity in RARITY_ORDER:
        emoji = COLOR_EMOJIS.get(rarity, '⚫')
        slots_count = int(rarity_slot_counts.get(rarity, 0) or 0)
        qty_count = int(rarity_qty_counts.get(rarity, 0) or 0)
        if lang == 'ru':
            lines.append(f"• {emoji} {rarity}: слотов {slots_count}, суммарно {qty_count} шт.")
        else:
            lines.append(f"• {emoji} {rarity}: slots {slots_count}, total {qty_count} pcs")

    text = "\n".join(lines)

    keyboard = []
    for i, val, is_filled in slot_values:
        keyboard.append([InlineKeyboardButton(f"{i}. {val}", callback_data=f"fav_slot_{i}")])
        keyboard.append([InlineKeyboardButton("🔎 Поиск по названию" if lang == 'ru' else "🔎 Search by name", callback_data=f"fav_search_start_{i}")])
        if is_filled:
            keyboard.append([InlineKeyboardButton(f"🗑 Очистить слот {i}" if lang == 'ru' else f"🗑 Clear slot {i}", callback_data=f"fav_clear_{i}")])
    keyboard.append([InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='my_profile')])

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_favorites_pick_inventory_v2(update: Update, context: ContextTypes.DEFAULT_TYPE, slot: int, page: int = 1):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    slot = int(slot or 0)
    if slot not in (1, 2, 3):
        await query.answer("Ошибка" if lang == 'ru' else "Error", show_alert=True)
        return

    inventory_items = db.get_player_inventory_with_details(user_id)
    if not inventory_items:
        await query.answer(t(lang, 'favorites_pick_empty_inventory'), show_alert=True)
        await show_profile_favorites_v2(update, context)
        return

    sorted_items = sorted(
        inventory_items,
        key=lambda i: (
            RARITY_ORDER.index(i.rarity) if i.rarity in RARITY_ORDER else len(RARITY_ORDER),
            i.drink.name.lower(),
        )
    )

    total_items = len(sorted_items)
    total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = sorted_items[start_idx:end_idx]

    text = (
        f"{t(lang, 'favorites_pick_title').format(n=slot)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{t(lang, 'inventory')}: {total_items}\n"
        f"{('Страница' if lang == 'ru' else 'Page')} {page}/{total_pages}"
    )

    keyboard_rows = []
    current_row = []
    for item in page_items:
        display_name = item.drink.name or ("Плантационный энергетик" if getattr(getattr(item, 'drink', None), 'is_plantation', False) else "Энергетик")
        btn_text = f"{COLOR_EMOJIS.get(item.rarity, '⚫')} {display_name}"
        callback = f"fav_pick_{slot}_{item.id}_p{page}"
        current_row.append(InlineKeyboardButton(btn_text, callback_data=callback))
        if len(current_row) == 2:
            keyboard_rows.append(current_row)
            current_row = []
    if current_row:
        keyboard_rows.append(current_row)

    if total_pages > 1:
        prev_page = total_pages if page == 1 else page - 1
        next_page = 1 if page == total_pages else page + 1
        keyboard_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"fav_pick_page_{slot}_{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"fav_pick_page_{slot}_{next_page}"),
        ])

    keyboard_rows.append([InlineKeyboardButton("🔎 Поиск по названию" if lang == 'ru' else "🔎 Search by name", callback_data=f"fav_search_start_{slot}")])
    keyboard_rows.append([InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='profile_favorites')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def start_favorites_search(update: Update, context: ContextTypes.DEFAULT_TYPE, slot: int):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    slot = int(slot or 0)
    if slot not in (1, 2, 3):
        await query.answer("Ошибка" if lang == 'ru' else "Error", show_alert=True)
        return

    context.user_data['awaiting_favorites_search'] = True
    context.user_data['awaiting_favorites_search_slot'] = slot

    prompt_text = (
        f"🔎 <b>{'Поиск для избранного' if lang == 'ru' else 'Search for favorite'}</b>\n\n"
        f"{'Введите название или часть названия энергетика.' if lang == 'ru' else 'Send a drink name or part of it.'}\n"
        f"{'Поиск нечувствителен к регистру.' if lang == 'ru' else 'Search is case-insensitive.'}"
    )
    kb = [[InlineKeyboardButton("❌ Отмена" if lang == 'ru' else "❌ Cancel", callback_data=f"fav_slot_{slot}")]]
    try:
        await query.edit_message_text(prompt_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user_id, text=prompt_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')


async def show_favorites_search_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    slot: int,
    search_query: str,
    page: int = 1,
):
    user_id = update.effective_user.id
    player = db.get_or_create_player(user_id, update.effective_user.username or update.effective_user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    slot = int(slot or 0)
    if slot not in (1, 2, 3):
        return

    inventory_items = db.get_player_inventory_with_details(user_id) or []
    search_lower = (search_query or '').strip().lower()
    filtered_items = [it for it in inventory_items if search_lower and search_lower in str(getattr(getattr(it, 'drink', None), 'name', '')).lower()]

    context.user_data['favorites_last_search_query'] = search_query
    context.user_data['favorites_last_search_slot'] = slot

    if page < 1:
        page = 1

    if not filtered_items:
        text = (
            f"🔎 <b>{'Результаты поиска' if lang == 'ru' else 'Search results'}: \"{html.escape(search_query)}\"</b>\n\n"
            f"{'❌ Ничего не найдено в инвентаре.' if lang == 'ru' else '❌ No items found in your inventory.'}"
        )
        kb = [
            [InlineKeyboardButton("🔄 Новый поиск" if lang == 'ru' else "🔄 New search", callback_data=f"fav_search_start_{slot}")],
            [InlineKeyboardButton("📋 К выбору из списка" if lang == 'ru' else "📋 Back to list", callback_data=f"fav_slot_{slot}")],
            [InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='profile_favorites')],
        ]
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            except BadRequest:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        else:
            await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    sorted_items = sorted(
        filtered_items,
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

    text = (
        f"🔎 <b>{'Результаты поиска' if lang == 'ru' else 'Search results'}: \"{html.escape(search_query)}\"</b>\n"
        f"{'Слот' if lang == 'ru' else 'Slot'}: {slot}\n"
        f"{'Найдено' if lang == 'ru' else 'Found'}: {total_items}\n"
        f"{'Страница' if lang == 'ru' else 'Page'} {page}/{total_pages}\n"
    )

    kb_rows = []
    row = []
    for item in page_items:
        name = item.drink.name or ("Энергетик" if lang == 'ru' else "Energy drink")
        emoji = COLOR_EMOJIS.get(item.rarity, '⚫')
        row.append(InlineKeyboardButton(f"{emoji} {name}", callback_data=f"fav_pick_{slot}_{item.id}_p{page}"))
        if len(row) == 2:
            kb_rows.append(row)
            row = []
    if row:
        kb_rows.append(row)

    if total_pages > 1:
        prev_page = total_pages if page == 1 else page - 1
        next_page = 1 if page == total_pages else page + 1
        kb_rows.append([
            InlineKeyboardButton("⬅️", callback_data=f"fav_search_page_{slot}_{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data='noop'),
            InlineKeyboardButton("➡️", callback_data=f"fav_search_page_{slot}_{next_page}"),
        ])

    kb_rows.append([InlineKeyboardButton("🔄 Новый поиск" if lang == 'ru' else "🔄 New search", callback_data=f"fav_search_start_{slot}")])
    kb_rows.append([InlineKeyboardButton("📋 К выбору из списка" if lang == 'ru' else "📋 Back to list", callback_data=f"fav_slot_{slot}")])
    kb_rows.append([InlineKeyboardButton(t(lang, 'favorites_back_profile'), callback_data='profile_favorites')])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode='HTML')
    else:
        await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb_rows))


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

        # Логируем транзакцию
        user = query.from_user
        db.log_action(
            user_id=user_id,
            username=user.username or user.first_name,
            action_type='transaction',
            action_details=f'Приёмник: продано {qsold} шт. по {unit} монет за шт.',
            amount=total,
            success=True
        )

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

# --- Приёмник: обработка продажи абсолютно всех кроме одного ---
async def handle_sell_absolutely_all_but_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает продажу АБСОЛЮТНО всех энергетиков кроме одного экземпляра каждого типа через Приёмник."""
    query = update.callback_query
    user_id = query.from_user.id

    # Блокировка на пользователя, чтобы избежать двойных кликов
    lock = _get_lock(f"sell_all_abs:{user_id}")
    async with lock:
        try:
            result = db.sell_absolutely_all_but_one(user_id)
        except Exception:
            await query.answer("Ошибка при массовой продаже. Попробуйте позже.", show_alert=True)
            return

        if not result or not result.get("ok"):
            reason = (result or {}).get("reason")
            reason_map = {
                "no_items": "У вас нет предметов в инвентаре",
                "nothing_to_sell": "Нет предметов для продажи (все предметы в единственном экземпляре)",
                "exception": "Произошла ошибка. Повторите попытку",
            }
            msg = reason_map.get(reason, "Не удалось выполнить массовую продажу. Повторите попытку позже.")
            await query.answer(msg, show_alert=True)
            return

        # Успешная продажа: обновляем экран и шлём инфо-сообщение
        total_sold = int(result.get("total_items_sold", 0))
        total_earned = int(result.get("total_earned", 0))
        items_processed = int(result.get("items_processed", 0))
        coins_after = int(result.get("coins_after", 0))

        # Обновляем инвентарь
        await show_inventory_by_quantity(update, context)

        # Уведомляем об успехе отдельным сообщением
        success_text = (
            f"♻️ Массовая продажа успешна!\n"
            f"Обработано типов: {items_processed}\n"
            f"Продано предметов: {total_sold} шт.\n"
            f"Заработано: +{total_earned} монет\n"
            f"Баланс: {coins_after} монет"
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=success_text)
        except Exception:
            pass


async def receiver_sell_all_confirm_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "<b>🗑️ Продать все</b>\n\n"
        "Вы собираетесь продать <b>все</b> энергетики из инвентаря через Приёмник.\n"
        "Это действие нельзя отменить.\n\n"
        "Продолжить?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data='sell_all_confirm_2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='market_receiver')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def receiver_sell_all_confirm_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "<b>⚠️ Второе подтверждение</b>\n\n"
        "Точно продать <b>ВСЕ</b> энергетики?\n"
        "Если в Приёмнике нет цены на редкость, такие предметы будут пропущены."
    )
    keyboard = [
        [InlineKeyboardButton("🔥 Продать все", callback_data='sell_all_execute')],
        [InlineKeyboardButton("❌ Отмена", callback_data='market_receiver')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_sell_all_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    lock = _get_lock(f"sell_all_inventory:{user_id}")
    async with lock:
        try:
            result = db.sell_all_inventory(user_id)
        except Exception:
            await query.answer("Ошибка при массовой продаже. Попробуйте позже.", show_alert=True)
            return

        if not result or not result.get('ok'):
            reason = (result or {}).get('reason')
            reason_map = {
                'no_items': 'У вас нет предметов в инвентаре',
                'nothing_to_sell': 'Нет предметов для продажи',
                'exception': 'Произошла ошибка. Повторите попытку',
            }
            msg = reason_map.get(reason, 'Не удалось выполнить продажу. Повторите попытку позже.')
            await query.answer(msg, show_alert=True)
            return

        total_sold = int(result.get('total_items_sold', 0))
        total_earned = int(result.get('total_earned', 0))
        items_processed = int(result.get('items_processed', 0))
        skipped_items = int(result.get('skipped_items', 0))
        coins_after = int(result.get('coins_after', 0))

        user = query.from_user
        try:
            db.log_action(
                user_id=user_id,
                username=user.username or user.first_name,
                action_type='transaction',
                action_details=f'Приёмник: продано всё. Обработано типов: {items_processed}. Пропущено: {skipped_items}.',
                amount=total_earned,
                success=True
            )
        except Exception:
            pass

        await show_inventory_by_quantity(update, context)

        success_text = (
            f"♻️ Продажа всех энергетиков успешна!\n"
            f"Обработано типов: {items_processed}\n"
            f"Продано предметов: {total_sold} шт.\n"
            f"Пропущено (нет цены): {skipped_items}\n"
            f"Заработано: +{total_earned} монет\n"
            f"Баланс: {coins_after} монет"
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
    # VIP+ доступен всегда
    keyboard.append([InlineKeyboardButton(t(lang, 'vip_plus'), callback_data='vip_plus_menu')])
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
    """Экран Казино в городе ХайТаун - главное меню с выбором игр."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    # Получаем статистику казино
    casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
    casino_losses = int(getattr(player, 'casino_losses', 0) or 0)
    casino_total = casino_wins + casino_losses
    win_rate = (casino_wins / casino_total * 100) if casino_total > 0 else 0

    text = (
        "<b>🎰 Казино ХайТаун</b>\n\n"
        f"💰 Ваш баланс: <b>{coins}</b> септимов\n"
        f"📊 Статистика: {casino_wins}✅ / {casino_losses}❌ ({win_rate:.1f}%)\n\n"
        "🎮 <b>Выберите игру:</b>\n"
    )

    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data='casino_game_coin_flip')],
        [InlineKeyboardButton("🎲 Кости", callback_data='casino_game_dice'), 
         InlineKeyboardButton("📊 Больше/Меньше", callback_data='casino_game_high_low')],
        [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data='casino_game_roulette_color'),
         InlineKeyboardButton("🎯 Рулетка (число)", callback_data='casino_game_roulette_number')],
        [InlineKeyboardButton("🎰 Слоты", callback_data='casino_game_slots')],
        [InlineKeyboardButton("🃏 Блэкджек", callback_data='casino_game_blackjack')],
        [InlineKeyboardButton("💣 Мины", callback_data='casino_game_mines'),
         InlineKeyboardButton("📈 Краш", callback_data='casino_game_crash')],
        [InlineKeyboardButton("🏀 Баскетбол", callback_data='casino_game_basketball'),
         InlineKeyboardButton("⚽ Футбол", callback_data='casino_game_football')],
        [InlineKeyboardButton("🎳 Боулинг", callback_data='casino_game_bowling'),
         InlineKeyboardButton("🎯 Дартс", callback_data='casino_game_darts')],
        [InlineKeyboardButton("🏆 Достижения", callback_data='casino_achievements'),
         InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
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
    """Показывает правила всех игр казино."""
    query = update.callback_query
    await query.answer()

    text = (
        "<b>📜 Правила Казино ХайТаун</b>\n\n"
        "🎮 <b>Доступные игры:</b>\n\n"
        
        "🪙 <b>Монетка</b>\n"
        "├ Выберите Орёл или Решка\n"
        "├ Шанс: 50%\n"
        "└ Выплата: x2\n\n"
        
        "🎲 <b>Кости</b>\n"
        "├ Выберите число от 1 до 6\n"
        "├ Шанс: ~17%\n"
        "└ Выплата: x5.5\n\n"
        
        "📊 <b>Больше/Меньше</b>\n"
        "├ Выберите больше или меньше 50\n"
        "├ Шанс: 49%\n"
        "└ Выплата: x1.95\n\n"
        
        "🎡 <b>Рулетка (цвет)</b>\n"
        "├ Выберите Красное или Чёрное\n"
        "├ Шанс: ~49%\n"
        "└ Выплата: x2\n\n"
        
        "🎯 <b>Рулетка (число)</b>\n"
        "├ Угадай число 0-36\n"
        "├ Шанс: ~3%\n"
        "└ Выплата: x35\n\n"
        
        "🎰 <b>Слоты</b>\n"
        "├ Три символа в ряд\n"
        "├ Шанс: 15%\n"
        "└ Выплата: до x20\n\n"
        
        f"⚙️ <b>Лимиты:</b>\n"
        f"• Мин. ставка: {CASINO_MIN_BET} септимов\n"
        f"• Макс. ставка: {CASINO_MAX_BET} септимов\n\n"
        
        "🏆 <b>Достижения:</b>\n"
        "Получайте награды за победы!\n\n"
        
        "⚠️ Играйте ответственно!"
    )
    keyboard = [
        [InlineKeyboardButton("🔙 В Казино", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
    ]
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


# === НОВЫЕ ФУНКЦИИ ДЛЯ ИГР КАЗИНО ===

async def show_casino_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    """Показывает экран выбора для конкретной игры - сначала выбор, потом ставка."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)

    game_info = CASINO_GAMES.get(game_type, CASINO_GAMES['coin_flip'])
    
    # Для игр с выбором показываем экран выбора, для слотов - сразу ставки
    if game_type in ['coin_flip', 'dice', 'high_low', 'roulette_color', 'roulette_number']:
        await show_game_choice_screen(update, context, game_type, game_info, coins)
    else:  # slots и другие игры без выбора
        await show_bet_selection_screen(update, context, game_type, game_info, coins, None)


async def show_game_choice_screen(update, context, game_type: str, game_info: dict, coins: int):
    """Показывает экран выбора варианта для игры."""
    query = update.callback_query
    user = query.from_user
    
    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"📋 {game_info['description']}\n"
        f"🎯 Шанс выигрыша: {int(game_info['win_prob'] * 100)}%\n"
        f"💰 Множитель: x{game_info['multiplier']}\n\n"
        f"💵 Ваш баланс: <b>{coins}</b> септимов\n\n"
    )
    
    keyboard = []
    
    if game_type == 'coin_flip':
        text += "Выберите на что ставите:"
        keyboard = [
            [InlineKeyboardButton("🦅 Орёл", callback_data=f'casino_choice_{game_type}_heads'),
             InlineKeyboardButton("🪙 Решка", callback_data=f'casino_choice_{game_type}_tails')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_casino')],
        ]
    
    elif game_type == 'dice':
        text += "Выберите число от 1 до 6:"
        keyboard = [
            [InlineKeyboardButton("1️⃣", callback_data=f'casino_choice_{game_type}_1'),
             InlineKeyboardButton("2️⃣", callback_data=f'casino_choice_{game_type}_2'),
             InlineKeyboardButton("3️⃣", callback_data=f'casino_choice_{game_type}_3')],
            [InlineKeyboardButton("4️⃣", callback_data=f'casino_choice_{game_type}_4'),
             InlineKeyboardButton("5️⃣", callback_data=f'casino_choice_{game_type}_5'),
             InlineKeyboardButton("6️⃣", callback_data=f'casino_choice_{game_type}_6')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_casino')],
        ]
    
    elif game_type == 'high_low':
        text += "Число будет больше или меньше 50?"
        keyboard = [
            [InlineKeyboardButton("📈 Больше 50", callback_data=f'casino_choice_{game_type}_high'),
             InlineKeyboardButton("📉 Меньше 50", callback_data=f'casino_choice_{game_type}_low')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_casino')],
        ]
    
    elif game_type == 'roulette_color':
        text += "Выберите цвет:"
        keyboard = [
            [InlineKeyboardButton("🔴 Красное", callback_data=f'casino_choice_{game_type}_red'),
             InlineKeyboardButton("⚫ Чёрное", callback_data=f'casino_choice_{game_type}_black')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_casino')],
        ]
    
    elif game_type == 'roulette_number':
        text += "Выберите число от 0 до 36:"
        # Показываем по 6 чисел в строке
        keyboard = []
        for i in range(0, 37, 6):
            row = []
            for num in range(i, min(i+6, 37)):
                row.append(InlineKeyboardButton(str(num), callback_data=f'casino_choice_{game_type}_{num}'))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='city_casino')])
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_bet_selection_screen(update, context, game_type: str, game_info: dict, coins: int, choice):
    """Показывает экран выбора ставки после выбора варианта."""
    query = update.callback_query
    user = query.from_user
    
    # Формируем текст с выбором игрока
    choice_text = ""
    if choice:  # Если был выбор (не слоты)
        if game_type == 'coin_flip':
            choice_text = f"Ваш выбор: <b>{'🦅 Орёл' if choice == 'heads' else '🪙 Решка'}</b>\n"
        elif game_type == 'dice':
            choice_text = f"Ваше число: <b>{choice}</b>\n"
        elif game_type == 'high_low':
            choice_text = f"Ваш выбор: <b>{'📈 Больше 50' if choice == 'high' else '📉 Меньше 50'}</b>\n"
        elif game_type == 'roulette_color':
            choice_text = f"Ваш цвет: <b>{'🔴 Красное' if choice == 'red' else '⚫ Чёрное'}</b>\n"
        elif game_type == 'roulette_number':
            choice_text = f"Ваше число: <b>{choice}</b>\n"
    
    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"{choice_text}"
        f"🎯 Шанс выигрыша: {int(game_info['win_prob'] * 100)}%\n"
        f"💰 Множитель: до x{game_info['multiplier'] if game_type != 'slots' else '10'}\n\n"
        f"💵 Ваш баланс: <b>{coins}</b> септимов\n\n"
        "Выберите ставку:"
    )

    # Формируем callback_data в зависимости от наличия выбора
    if choice:
        bet_callback = f'casino_bet_{game_type}_{choice}'
        change_button = [InlineKeyboardButton("🔙 Изменить выбор", callback_data=f'casino_game_{game_type}')]
    else:
        bet_callback = f'casino_bet_{game_type}_none'
        change_button = []

    keyboard = [
        [InlineKeyboardButton("💵 100", callback_data=f'{bet_callback}_100'),
         InlineKeyboardButton("💵 500", callback_data=f'{bet_callback}_500')],
        [InlineKeyboardButton("💵 1,000", callback_data=f'{bet_callback}_1000'),
         InlineKeyboardButton("💵 5,000", callback_data=f'{bet_callback}_5000')],
        [InlineKeyboardButton("💵 10,000", callback_data=f'{bet_callback}_10000'),
         InlineKeyboardButton("💵 25,000", callback_data=f'{bet_callback}_25000')],
    ]
    
    if change_button:
        keyboard.append(change_button)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в казино", callback_data='city_casino')])

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def play_casino_game_native(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str, bet_amount: int, player_choice: str = None):
    """Играет в игру с нативной анимацией Telegram (dice)."""
    query = update.callback_query
    user = query.from_user
    chat_id = user.id
    
    # Проверяем баланс
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    current_coins = int(getattr(player, 'coins', 0) or 0)
    
    if current_coins < bet_amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return

    # Списываем ставку
    db.increment_coins(user.id, -bet_amount)
    
    # Отправляем анимацию
    emoji = CASINO_GAMES[game_type]['emoji']
    try:
        # Удаляем сообщение с меню, чтобы не мешало (опционально, но лучше оставить для контекста)
        # await query.message.delete()
        pass
    except Exception:
        pass

    # Отправляем дайс
    dice_msg = await context.bot.send_dice(chat_id=chat_id, emoji=emoji)
    value = dice_msg.dice.value
    
    # Планируем удаление дайса через 8 секунд
    async def delete_dice_later(msg, delay):
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except Exception:
            pass
            
    asyncio.create_task(delete_dice_later(dice_msg, 8))
    
    # Ждем анимацию
    await asyncio.sleep(4)
    
    win = False
    multiplier = 0.0
    result_text = ""
    base_prob = 0.0
    
    # Логика для разных игр
    if game_type == 'dice':
        # Кости: угадать число (1-6)
        target = int(player_choice)
        win = (value == target)
        base_prob = 1 / 6
        multiplier = CASINO_GAMES['dice']['multiplier']
        result_text = f"🎲 Выпало: <b>{value}</b> (Ваш выбор: {target})"
        
    elif game_type == 'slots':
        # Слоты: 1-64
        # 64: 777 (x10)
        # 43: Виноград (x5)
        # 22: Лимон (x3)
        # 1: BAR (x2)
        base_prob = 4 / 64
        if value == 64:
            win = True
            multiplier = 10.0
            result_text = "🎰 <b>ДЖЕКПОТ! (777)</b>"
        elif value == 43:
            win = True
            multiplier = 5.0
            result_text = "🍇 <b>Виноград!</b>"
        elif value == 22:
            win = True
            multiplier = 3.0
            result_text = "🍋 <b>Лимон!</b>"
        elif value == 1:
            win = True
            multiplier = 2.0
            result_text = "🍫 <b>BAR!</b>"
        else:
            win = False
            result_text = "🎰 Попробуйте ещё раз!"
            
    elif game_type == 'basketball':
        # Баскетбол: 4, 5 - попадание
        if value in [4, 5]:
            win = True
            multiplier = CASINO_GAMES['basketball']['multiplier']
            result_text = "🏀 <b>Попадание!</b>"
        else:
            win = False
            result_text = "🏀 Промах..."
        base_prob = 2 / 6
            
    elif game_type == 'football':
        # Футбол: 3, 4, 5 - гол
        if value in [3, 4, 5]:
            win = True
            multiplier = CASINO_GAMES['football']['multiplier']
            result_text = "⚽ <b>ГОООЛ!</b>"
        else:
            win = False
            result_text = "⚽ Мимо ворот..."
        base_prob = 3 / 6
            
    elif game_type == 'bowling':
        # Боулинг: 6 - страйк
        if value == 6:
            win = True
            multiplier = CASINO_GAMES['bowling']['multiplier']
            result_text = "🎳 <b>СТРАЙК!</b>"
        else:
            win = False
            result_text = f"🎳 Сбито кеглей: {value}"
        base_prob = 1 / 6
            
    elif game_type == 'darts':
        # Дартс: 6 - яблочко
        if value == 6:
            win = True
            multiplier = CASINO_GAMES['darts']['multiplier']
            result_text = "🎯 <b>В ЯБЛОЧКО!</b>"
        else:
            win = False
            result_text = "🎯 Мимо центра..."
        base_prob = 1 / 6

    # Лаки-оверрайд: повышенная удача для всех нативных игр
    if not win and base_prob > 0:
        extra = _casino_extra_win_chance(base_prob)
        if extra > 0 and random.random() < extra:
            win = True
            if multiplier <= 0:
                # Фоллбек множителя, если его не было
                multiplier = CASINO_GAMES.get(game_type, {}).get('multiplier', 2.0)
            result_text += "\n🍀 Удача сработала!"

    # Обработка результата
    winnings = 0
    if win:
        winnings = int(bet_amount * multiplier)
        db.increment_coins(user.id, winnings)
        # Обновляем статистику
        p = db.get_player(user.id)
        db.update_player_stats(user.id, casino_wins=(p.casino_wins or 0) + 1)
    else:
        p = db.get_player(user.id)
        db.update_player_stats(user.id, casino_losses=(p.casino_losses or 0) + 1)

    # Проверка достижений
    player = db.get_or_create_player(user.id, user.username)
    achievement_bonus = check_casino_achievements(user.id, player)
    
    # Показываем результат
    game_info = CASINO_GAMES[game_type]
    
    await show_game_result(query, user, game_info, bet_amount, win, winnings, 
                          player.coins, result_text, achievement_bonus, context)


async def play_casino_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str, player_choice: str, bet_amount: int):
    """Играет в выбранную игру казино с выбором игрока."""
    # Перенаправляем на нативные игры
    if game_type in ['dice', 'slots', 'basketball', 'football', 'bowling', 'darts']:
        await play_casino_game_native(update, context, game_type, bet_amount, player_choice)
        return

    query = update.callback_query
    user = query.from_user
    
    # Проверка лимитов
    if bet_amount < CASINO_MIN_BET or bet_amount > CASINO_MAX_BET:
        await query.answer(f"Ставка должна быть от {CASINO_MIN_BET} до {CASINO_MAX_BET}", show_alert=True)
        return

    lock = _get_lock(f"user:{user.id}:casino")
    if lock.locked():
        await query.answer("Игра уже обрабатывается...", show_alert=True)
        return

    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, 'coins', 0) or 0)

        if coins < bet_amount:
            await query.answer("Недостаточно септимов", show_alert=True)
            return

        # Списываем ставку
        db.increment_coins(user.id, -bet_amount)

        # Получаем информацию об игре
        game_info = CASINO_GAMES.get(game_type, CASINO_GAMES['coin_flip'])
        
        # Определяем результат в зависимости от игры с учётом выбора игрока
        win = False
        result_text = ""
        multiplier = game_info['multiplier']
        
        if game_type == 'coin_flip':
            win, result_text = play_coin_flip(game_info, player_choice)
        elif game_type == 'dice':
            win, result_text, multiplier = play_dice(game_info, player_choice)
        elif game_type == 'high_low':
            win, result_text = play_high_low(game_info, player_choice)
        elif game_type == 'roulette_color':
            win, result_text = play_roulette_color(game_info, player_choice)
        elif game_type == 'roulette_number':
            win, result_text, multiplier = play_roulette_number(game_info, player_choice)
        elif game_type == 'slots':
            win, result_text, multiplier = play_slots(game_info)
        else:
            win = _casino_roll_win(game_info['win_prob'])
            result_text = "🎲 Результат определён"

        # Начисляем выигрыш
        winnings = 0
        if win:
            winnings = int(bet_amount * multiplier)
            db.increment_coins(user.id, winnings)
            # Обновляем статистику побед
            current_wins = int(getattr(player, 'casino_wins', 0) or 0)
            db.update_player_stats(user.id, casino_wins=current_wins + 1)
            # Логируем выигрыш
            db.log_action(
                user_id=user.id,
                username=user.username or user.first_name,
                action_type='casino',
                action_details=f'{game_type}: ставка {bet_amount}, выигрыш {winnings}',
                amount=winnings,
                success=True
            )
        else:
            # Обновляем статистику поражений
            current_losses = int(getattr(player, 'casino_losses', 0) or 0)
            db.update_player_stats(user.id, casino_losses=current_losses + 1)
            # Логируем проигрыш
            db.log_action(
                user_id=user.id,
                username=user.username or user.first_name,
                action_type='casino',
                action_details=f'{game_type}: ставка {bet_amount}, проигрыш',
                amount=-bet_amount,
                success=False
            )

        # Проверяем достижения
        achievement_bonus = check_casino_achievements(user.id, player)

        # Формируем сообщение о результате
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        new_balance = int(getattr(player, 'coins', 0) or 0)
        
        # Логируем результат для отладки
        logger.info(f"Casino game result - Type: {game_type}, Win: {win}, Result text: {result_text[:50]}...")
        
        await show_game_result(query, user, game_info, bet_amount, win, winnings, 
                              new_balance, result_text, achievement_bonus, context)


def _casino_luck_mult() -> float:
    try:
        m = float(db.get_setting_float('casino_luck_mult', 1.0))
    except Exception:
        m = 1.0
    return max(0.1, min(5.0, m))


def _casino_adjusted_prob(base_prob: float) -> float:
    base = max(0.0, min(1.0, float(base_prob)))
    adj = base * _casino_luck_mult()
    return max(0.0, min(0.95, adj))


def _casino_roll_win(base_prob: float) -> bool:
    return random.random() < _casino_adjusted_prob(base_prob)


def _casino_extra_win_chance(base_prob: float) -> float:
    base = max(0.0, min(1.0, float(base_prob)))
    adj = _casino_adjusted_prob(base)
    return max(0.0, adj - base)


def play_coin_flip(game_info, player_choice):
    """Игра: подбрасывание монеты."""
    # player_choice: 'heads' или 'tails'
    win = _casino_roll_win(0.5)
    result = player_choice if win else ('tails' if player_choice == 'heads' else 'heads')
    
    result_emoji = '🦅 Орёл' if result == 'heads' else '🪙 Решка'
    choice_emoji = '🦅 Орёл' if player_choice == 'heads' else '🪙 Решка'
    
    result_text = (
        f"🎲 Ваш выбор: <b>{choice_emoji}</b>\n"
        f"🪙 Выпало: <b>{result_emoji}</b>\n"
        f"{'✅ Совпадение!' if win else '❌ Не угадали'}"
    )
    return win, result_text


def play_dice(game_info, player_choice):
    """Игра: игральная кость."""
    # player_choice: '1' до '6'
    player_number = int(player_choice)
    win = _casino_roll_win(1 / 6)
    if win:
        dice_result = player_number
    else:
        other = [n for n in range(1, 7) if n != player_number]
        dice_result = random.choice(other)
    
    result_text = (
        f"🎯 Ваше число: <b>{player_number}</b>\n"
        f"🎲 Выпало: <b>{dice_result}</b>\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали'}"
    )
    multiplier = game_info['multiplier'] if win else game_info['multiplier']
    return win, result_text, multiplier


def play_high_low(game_info, player_choice):
    """Игра: больше/меньше 50."""
    # player_choice: 'high' или 'low'
    win = _casino_roll_win(0.49)
    if player_choice == 'high':
        if win:
            number = random.randint(51, 100)
        else:
            number = random.randint(1, 50)
    else:
        if win:
            number = random.randint(1, 49)
        else:
            number = random.randint(50, 100)
    
    is_higher = number > 50
    
    choice_text = '📈 Больше 50' if player_choice == 'high' else '📉 Меньше 50'
    actual_text = '📈 Больше 50' if is_higher else '📉 Меньше 50'
    result_text = (
        f"🎯 Ваш выбор: <b>{choice_text}</b>\n"
        f"📊 Выпало: <b>{number}</b> ({actual_text})\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали'}"
    )
    return win, result_text


def play_roulette_color(game_info, player_choice):
    """Игра: рулетка - красное/чёрное."""
    # player_choice: 'red' или 'black'
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    black_numbers = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
    win = _casino_roll_win(18 / 37)
    if win:
        if player_choice == 'red':
            number = random.choice(red_numbers)
            color_code = 'red'
            color = '🔴 Красное'
        else:
            number = random.choice(black_numbers)
            color_code = 'black'
            color = '⚫ Чёрное'
    else:
        # Проигрыш: либо противоположный цвет, либо 0
        if random.random() < 0.15:
            number = 0
            color_code = 'green'
            color = '🟢 Зелёное'
        else:
            if player_choice == 'red':
                number = random.choice(black_numbers)
                color_code = 'black'
                color = '⚫ Чёрное'
            else:
                number = random.choice(red_numbers)
                color_code = 'red'
                color = '🔴 Красное'
    
    choice_text = '🔴 Красное' if player_choice == 'red' else '⚫ Чёрное'
    result_text = (
        f"🎯 Ваш выбор: <b>{choice_text}</b>\n"
        f"🎡 Выпало: <b>{number}</b> ({color})\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали' if color_code != 'green' else '❌ Выпал зелёный 0'}"
    )
    return win, result_text


def play_roulette_number(game_info, player_choice):
    """Игра: рулетка - угадай число."""
    # player_choice: '0' до '36'
    player_number = int(player_choice)
    win = _casino_roll_win(1 / 37)
    if win:
        number = player_number
    else:
        other = [n for n in range(0, 37) if n != player_number]
        number = random.choice(other)
    
    result_text = (
        f"🎯 Ваше число: <b>{player_number}</b>\n"
        f"🎡 Выпало: <b>{number}</b>\n"
        f"{'✅ Точное попадание!' if win else '❌ Не угадали'}"
    )
    multiplier = game_info['multiplier'] if win else game_info['multiplier']
    return win, result_text, multiplier


def play_slots(game_info):
    """Игра: слоты."""
    win = _casino_roll_win(CASINO_GAMES['slots']['win_prob'])
    if win:
        combination = random.choice(list(SLOT_PAYOUTS.keys()))
        slot1, slot2, slot3 = combination[0], combination[1], combination[2]
        multiplier = SLOT_PAYOUTS.get(combination, 3.0)
    else:
        # Генерируем комбинацию без выигрыша
        while True:
            slot1 = random.choice(SLOT_SYMBOLS)
            slot2 = random.choice(SLOT_SYMBOLS)
            slot3 = random.choice(SLOT_SYMBOLS)
            if not (slot1 == slot2 == slot3):
                break
        combination = f"{slot1}{slot2}{slot3}"
        multiplier = 0
    
    # Формируем красивый результат
    if win:
        result_text = (
            f"🎰 Результат:\n"
            f"┏━━━━━━━━━━━━━┓\n"
            f"┃  <b>{slot1} {slot2} {slot3}</b>  ┃\n"
            f"┗━━━━━━━━━━━━━┛\n"
            f"💫 Множитель: <b>x{int(multiplier)}</b>"
        )
    else:
        result_text = (
            f"🎰 Результат:\n"
            f"┏━━━━━━━━━━━━━┓\n"
            f"┃  <b>{slot1} {slot2} {slot3}</b>  ┃\n"
            f"┗━━━━━━━━━━━━━┛"
        )
    
    return win, result_text, multiplier


def check_casino_achievements(user_id, player):
    """Проверяет и выдает достижения казино."""
    casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
    unlocked_achievements = getattr(player, 'casino_achievements', '') or ''
    
    bonus = 0
    new_achievement = None
    
    for ach_id, ach_data in CASINO_ACHIEVEMENTS.items():
        if ach_id not in unlocked_achievements and casino_wins >= ach_data['wins']:
            # Выдаем достижение
            unlocked_achievements += f"{ach_id},"
            db.update_player_stats(user_id, casino_achievements=unlocked_achievements)
            bonus = ach_data['reward']
            new_achievement = ach_data
            db.increment_coins(user_id, bonus)
            break
    
    return {'bonus': bonus, 'achievement': new_achievement} if new_achievement else None


async def show_game_result(query, user, game_info, bet_amount, win, winnings, 
                           new_balance, result_text, achievement_bonus, context):
    """Показывает результат игры."""
    if win:
        profit = winnings - bet_amount
        result_line = f"🎉 <b>ПОБЕДА!</b> 🎉\n💰 Выигрыш: +{profit} септимов"
    else:
        result_line = f"💥 <b>Поражение</b>\n💸 Потеряно: {bet_amount} септимов"

    achievement_text = ""
    if achievement_bonus:
        ach = achievement_bonus['achievement']
        achievement_text = f"\n\n🏆 <b>Достижение разблокировано!</b>\n{ach['name']}: {ach['desc']}\n💰 Бонус: +{achievement_bonus['bonus']} септимов"

    # Добавляем разделитель для лучшей читаемости
    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{result_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{result_line}\n"
        f"💵 Баланс: <b>{new_balance}</b> септимов"
        f"{achievement_text}"
    )
    
    # Логируем для отладки
    logger.info(f"Showing casino result, text length: {len(text)}, has result_text: {bool(result_text)}")

    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data=f'casino_game_{list(CASINO_GAMES.keys())[list(CASINO_GAMES.values()).index(game_info)]}')],
        [InlineKeyboardButton("🎮 Другая игра", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Выход", callback_data='city_hightown')],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


# === БЛЭКДЖЕК ===

def create_blackjack_deck():
    """Создаёт и перемешивает колоду для блэкджека."""
    deck = [(rank, suit) for suit in BLACKJACK_SUITS for rank in BLACKJACK_RANKS]
    random.shuffle(deck)
    return deck


def calculate_hand_value(hand):
    """Подсчитывает очки руки с учётом туза (1 или 11)."""
    value = 0
    aces = 0
    for rank, suit in hand:
        value += BLACKJACK_VALUES[rank]
        if rank == 'A':
            aces += 1
    # Если перебор и есть тузы, считаем их как 1
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value


def format_card(card):
    """Форматирует карту для отображения."""
    rank, suit = card
    return f"{rank}{suit}"


def format_hand(hand, hide_second=False):
    """Форматирует руку для отображения."""
    if hide_second and len(hand) >= 2:
        return f"{format_card(hand[0])} 🂠"
    return " ".join(format_card(card) for card in hand)


async def show_blackjack_bet_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран выбора ставки для блэкджека."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        "<b>🃏 Блэкджек (21)</b>\n\n"
        "📋 <b>Правила:</b>\n"
        "• Набери 21 или ближе к 21, чем дилер\n"
        "• Не перебери (больше 21 = проигрыш)\n"
        "• Туз = 1 или 11, картинки = 10\n"
        "• Блэкджек (21 на первых 2 картах) = x2.5\n"
        "• Обычный выигрыш = x2\n\n"
        f"💵 Ваш баланс: <b>{coins}</b> септимов\n\n"
        "Выберите ставку:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💵 100", callback_data='blackjack_bet_100'),
         InlineKeyboardButton("💵 500", callback_data='blackjack_bet_500')],
        [InlineKeyboardButton("💵 1,000", callback_data='blackjack_bet_1000'),
         InlineKeyboardButton("💵 5,000", callback_data='blackjack_bet_5000')],
        [InlineKeyboardButton("💵 10,000", callback_data='blackjack_bet_10000'),
         InlineKeyboardButton("💵 25,000", callback_data='blackjack_bet_25000')],
        [InlineKeyboardButton("🔙 Назад в казино", callback_data='city_casino')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def start_blackjack_game(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_amount: int):
    """Начинает игру в блэкджек: раздаёт карты."""
    query = update.callback_query
    user = query.from_user
    
    # Проверка лимитов
    if bet_amount < CASINO_MIN_BET or bet_amount > CASINO_MAX_BET:
        await query.answer(f"Ставка должна быть от {CASINO_MIN_BET} до {CASINO_MAX_BET}", show_alert=True)
        return
    
    lock = _get_lock(f"user:{user.id}:blackjack")
    if lock.locked():
        await query.answer("Игра уже обрабатывается...", show_alert=True)
        return
    
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, 'coins', 0) or 0)
        
        if coins < bet_amount:
            await query.answer("Недостаточно септимов", show_alert=True)
            return
        
        # Списываем ставку
        db.increment_coins(user.id, -bet_amount)
        
        # Создаём игру
        deck = create_blackjack_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        
        BLACKJACK_GAMES[user.id] = {
            'bet': bet_amount,
            'player_hand': player_hand,
            'dealer_hand': dealer_hand,
            'deck': deck,
            'status': 'playing'
        }
        
        player_value = calculate_hand_value(player_hand)
        
        # Проверяем блэкджек у игрока
        if player_value == 21:
            # Блэкджек! Сразу проверяем дилера
            dealer_value = calculate_hand_value(dealer_hand)
            if dealer_value == 21:
                # Оба блэкджека - ничья
                await finish_blackjack_game(update, context, user.id, 'push')
            else:
                # Игрок выиграл блэкджеком
                await finish_blackjack_game(update, context, user.id, 'blackjack')
            return
        
        # Показываем игровой экран
        await show_blackjack_game_screen(update, context, user.id)


async def show_blackjack_game_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Показывает текущее состояние игры."""
    query = update.callback_query
    
    game = BLACKJACK_GAMES.get(user_id)
    if not game:
        await query.answer("Игра не найдена", show_alert=True)
        return
    
    player_hand = game['player_hand']
    dealer_hand = game['dealer_hand']
    bet = game['bet']
    
    player_value = calculate_hand_value(player_hand)
    
    text = (
        "<b>🃏 Блэкджек</b>\n\n"
        f"💰 Ставка: <b>{bet}</b> септимов\n\n"
        f"🎩 Дилер: {format_hand(dealer_hand, hide_second=True)}\n"
        f"   Очки: <b>?</b>\n\n"
        f"👤 Вы: {format_hand(player_hand)}\n"
        f"   Очки: <b>{player_value}</b>\n\n"
    )
    
    if player_value == 21:
        text += "🎯 <b>21! Отличная рука!</b>"
    elif player_value > 21:
        text += "💥 <b>Перебор!</b>"
    
    # Кнопки действий
    keyboard = []
    if player_value < 21:
        row = [
            InlineKeyboardButton("🃏 Ещё", callback_data='blackjack_hit'),
            InlineKeyboardButton("✋ Хватит", callback_data='blackjack_stand')
        ]
        # Удвоение только на первых двух картах
        if len(player_hand) == 2:
            row.append(InlineKeyboardButton("💰 x2", callback_data='blackjack_double'))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Сдаться", callback_data='blackjack_surrender')])
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            pass


async def handle_blackjack_hit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок берёт ещё одну карту."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = BLACKJACK_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    # Берём карту
    game['player_hand'].append(game['deck'].pop())
    player_value = calculate_hand_value(game['player_hand'])
    
    if player_value > 21:
        # Перебор - проигрыш
        await finish_blackjack_game(update, context, user.id, 'bust')
    elif player_value == 21:
        # Ровно 21 - автоматически останавливаемся
        await handle_blackjack_stand(update, context)
    else:
        # Продолжаем игру
        await show_blackjack_game_screen(update, context, user.id)


async def handle_blackjack_stand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок останавливается, ход дилера."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = BLACKJACK_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    # Дилер добирает карты до 17
    dealer_hand = game['dealer_hand']
    deck = game['deck']
    
    while calculate_hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
    
    player_value = calculate_hand_value(game['player_hand'])
    dealer_value = calculate_hand_value(dealer_hand)
    
    # Определяем результат
    if dealer_value > 21:
        result = 'dealer_bust'
    elif player_value > dealer_value:
        result = 'win'
    elif player_value < dealer_value:
        result = 'lose'
    else:
        result = 'push'
    
    await finish_blackjack_game(update, context, user.id, result)


async def handle_blackjack_double(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок удваивает ставку и берёт одну карту."""
    query = update.callback_query
    user = query.from_user
    
    game = BLACKJACK_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    # Проверяем, что можно удвоить (только на первых двух картах)
    if len(game['player_hand']) != 2:
        await query.answer("Удвоение возможно только на первых двух картах", show_alert=True)
        return
    
    # Проверяем баланс для удвоения
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    bet = game['bet']
    
    if coins < bet:
        await query.answer("Недостаточно септимов для удвоения", show_alert=True)
        return
    
    await query.answer()
    
    # Списываем дополнительную ставку
    db.increment_coins(user.id, -bet)
    game['bet'] = bet * 2
    
    # Берём ровно одну карту
    game['player_hand'].append(game['deck'].pop())
    player_value = calculate_hand_value(game['player_hand'])
    
    if player_value > 21:
        # Перебор
        await finish_blackjack_game(update, context, user.id, 'bust')
    else:
        # Автоматически останавливаемся после удвоения
        await handle_blackjack_stand(update, context)


async def handle_blackjack_surrender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок сдаётся и теряет половину ставки."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = BLACKJACK_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    await finish_blackjack_game(update, context, user.id, 'surrender')


async def finish_blackjack_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, result: str):
    """Завершает игру и показывает результат."""
    query = update.callback_query
    user = query.from_user
    
    game = BLACKJACK_GAMES.get(user_id)
    if not game:
        return
    
    game['status'] = 'finished'
    bet = game['bet']
    player_hand = game['player_hand']
    dealer_hand = game['dealer_hand']
    
    player_value = calculate_hand_value(player_hand)
    dealer_value = calculate_hand_value(dealer_hand)
    
    winnings = 0
    win = False
    luck_applied = False
    # Шанс удачи: если проигрыш, пробуем перевернуть исход
    if result in ('bust', 'lose'):
        extra = _casino_extra_win_chance(0.45)
        if extra > 0 and random.random() < extra:
            result = 'win'
            luck_applied = True
    
    # Определяем выплату
    if result == 'blackjack':
        winnings = int(bet * BLACKJACK_BJ_MULTIPLIER)
        result_emoji = "🎰"
        result_text = "БЛЭКДЖЕК!"
        win = True
    elif result == 'win' or result == 'dealer_bust':
        winnings = int(bet * BLACKJACK_MULTIPLIER)
        result_emoji = "🎉"
        result_text = "ПОБЕДА!" if result == 'win' else "Дилер перебрал!"
        win = True
    elif result == 'push':
        winnings = bet  # Возврат ставки
        result_emoji = "🤝"
        result_text = "Ничья"
    elif result == 'surrender':
        winnings = bet // 2  # Возврат половины ставки
        result_emoji = "🏳️"
        result_text = "Сдались"
    elif result == 'bust':
        result_emoji = "💥"
        result_text = "Перебор!"
    else:  # lose
        result_emoji = "😢"
        result_text = "Проигрыш"
    
    # Начисляем выигрыш
    if winnings > 0:
        db.increment_coins(user_id, winnings)
    
    # Обновляем статистику
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    if win:
        current_wins = int(getattr(player, 'casino_wins', 0) or 0)
        db.update_player_stats(user_id, casino_wins=current_wins + 1)
    elif result not in ['push', 'surrender']:
        current_losses = int(getattr(player, 'casino_losses', 0) or 0)
        db.update_player_stats(user_id, casino_losses=current_losses + 1)
    
    # Логируем
    db.log_action(
        user_id=user_id,
        username=user.username or user.first_name,
        action_type='casino',
        action_details=f'blackjack: ставка {bet}, результат {result}, выплата {winnings}',
        amount=winnings - bet if result != 'push' else 0,
        success=win
    )
    
    # Проверяем достижения
    achievement_bonus = check_casino_achievements(user_id, player)
    
    # Формируем итоговое сообщение
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    new_balance = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        f"<b>🃏 Блэкджек — {result_emoji} {result_text}</b>\n\n"
        f"🎩 Дилер: {format_hand(dealer_hand)}\n"
        f"   Очки: <b>{dealer_value}</b>\n\n"
        f"👤 Вы: {format_hand(player_hand)}\n"
        f"   Очки: <b>{player_value}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    
    if win:
        profit = winnings - bet
        text += f"💰 Выигрыш: <b>+{profit}</b> септимов\n"
    elif result == 'push':
        text += f"↩️ Возврат ставки: <b>{winnings}</b> септимов\n"
    elif result == 'surrender':
        text += f"↩️ Возврат половины: <b>{winnings}</b> септимов\n"
    else:
        text += f"💸 Потеряно: <b>{bet}</b> септимов\n"
    
    text += f"💵 Баланс: <b>{new_balance}</b> септимов"
    if luck_applied:
        text += "\n🍀 Удача изменила исход!"
    
    if achievement_bonus:
        ach = achievement_bonus['achievement']
        text += f"\n\n🏆 <b>Достижение!</b>\n{ach['name']}: {ach['desc']}\n💰 Бонус: +{achievement_bonus['bonus']}"
    
    # Очищаем игру
    del BLACKJACK_GAMES[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='casino_game_blackjack')],
        [InlineKeyboardButton("🎮 Другая игра", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Выход", callback_data='city_hightown')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            pass


# === МИНЫ (MINES) ===

def create_mines_grid(mines_count: int):
    """Создаёт поле для игры в мины."""
    total_cells = MINES_GRID_SIZE * MINES_GRID_SIZE
    grid = [False] * total_cells  # False = безопасно, True = мина
    
    # Расставляем мины случайным образом
    mine_positions = random.sample(range(total_cells), mines_count)
    for pos in mine_positions:
        grid[pos] = True
    
    return grid


def calculate_mines_multiplier(mines_count: int, revealed_count: int) -> float:
    """Вычисляет множитель для игры в мины."""
    total = MINES_GRID_SIZE * MINES_GRID_SIZE
    safe_cells = total - mines_count
    
    if revealed_count == 0:
        return 1.0
    
    # Формула: вероятность открыть N безопасных ячеек
    multiplier = 1.0
    for i in range(revealed_count):
        prob = (safe_cells - i) / (total - i)
        if prob <= 0:
            break
        multiplier /= prob
    
    # Учитываем комиссию казино (3%)
    multiplier *= 0.97
    
    return round(multiplier, 2)


async def show_mines_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран настройки игры в мины - выбор кол-ва мин."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        "<b>💣 Мины</b>\n\n"
        "📋 <b>Правила:</b>\n"
        "• Поле 5×5 (25 ячеек)\n"
        "• Чем больше мин — тем выше множитель\n"
        "• Открывайте ячейки и избегайте мин\n"
        "• Можно забрать выигрыш в любой момент\n"
        "• Попали на мину = потеряли ставку\n\n"
        f"💵 Баланс: <b>{coins}</b> септимов\n\n"
        "Выберите количество мин:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💣 3 мины", callback_data='mines_count_3'),
         InlineKeyboardButton("💣 5 мин", callback_data='mines_count_5')],
        [InlineKeyboardButton("💣 10 мин", callback_data='mines_count_10'),
         InlineKeyboardButton("💣 15 мин", callback_data='mines_count_15')],
        [InlineKeyboardButton("💣 20 мин", callback_data='mines_count_20'),
         InlineKeyboardButton("💣 24 мины", callback_data='mines_count_24')],
        [InlineKeyboardButton("🔙 Назад в казино", callback_data='city_casino')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_mines_bet_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, mines_count: int):
    """Экран выбора ставки для игры в мины."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    # Показываем потенциальные множители
    m1 = calculate_mines_multiplier(mines_count, 1)
    m3 = calculate_mines_multiplier(mines_count, 3)
    m5 = calculate_mines_multiplier(mines_count, 5)
    
    text = (
        f"<b>💣 Мины — {mines_count} мин</b>\n\n"
        f"📊 <b>Множители:</b>\n"
        f"• 1 ячейка: x{m1}\n"
        f"• 3 ячейки: x{m3}\n"
        f"• 5 ячеек: x{m5}\n\n"
        f"💵 Баланс: <b>{coins}</b> септимов\n\n"
        "Выберите ставку:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💵 100", callback_data=f'mines_bet_{mines_count}_100'),
         InlineKeyboardButton("💵 500", callback_data=f'mines_bet_{mines_count}_500')],
        [InlineKeyboardButton("💵 1,000", callback_data=f'mines_bet_{mines_count}_1000'),
         InlineKeyboardButton("💵 5,000", callback_data=f'mines_bet_{mines_count}_5000')],
        [InlineKeyboardButton("💵 10,000", callback_data=f'mines_bet_{mines_count}_10000'),
         InlineKeyboardButton("💵 25,000", callback_data=f'mines_bet_{mines_count}_25000')],
        [InlineKeyboardButton("🔙 Изменить мины", callback_data='casino_game_mines')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def start_mines_game(update: Update, context: ContextTypes.DEFAULT_TYPE, mines_count: int, bet_amount: int):
    """Начинает игру в мины."""
    query = update.callback_query
    user = query.from_user
    
    if bet_amount < CASINO_MIN_BET or bet_amount > CASINO_MAX_BET:
        await query.answer(f"Ставка должна быть от {CASINO_MIN_BET} до {CASINO_MAX_BET}", show_alert=True)
        return
    
    lock = _get_lock(f"user:{user.id}:mines")
    if lock.locked():
        await query.answer("Игра уже обрабатывается...", show_alert=True)
        return
    
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, 'coins', 0) or 0)
        
        if coins < bet_amount:
            await query.answer("Недостаточно септимов", show_alert=True)
            return
        
        # Списываем ставку
        db.increment_coins(user.id, -bet_amount)
        
        # Создаём игру
        grid = create_mines_grid(mines_count)
        
        MINES_GAMES[user.id] = {
            'bet': bet_amount,
            'mines_count': mines_count,
            'grid': grid,
            'revealed': set(),
            'status': 'playing',
            'multiplier': 1.0
        }
        
        await show_mines_game_screen(update, context, user.id)


async def show_mines_game_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Показывает игровое поле мин."""
    query = update.callback_query
    
    game = MINES_GAMES.get(user_id)
    if not game:
        await query.answer("Игра не найдена", show_alert=True)
        return
    
    bet = game['bet']
    mines_count = game['mines_count']
    revealed = game['revealed']
    multiplier = game['multiplier']
    potential_win = int(bet * multiplier)
    
    text = (
        f"<b>💣 Мины — {mines_count} мин</b>\n\n"
        f"💰 Ставка: <b>{bet}</b>\n"
        f"📈 Множитель: <b>x{multiplier}</b>\n"
        f"💵 Выигрыш: <b>{potential_win}</b>\n"
        f"✅ Открыто: <b>{len(revealed)}</b> ячеек\n"
    )
    if game.get('luck_saved'):
        text += "🍀 <b>Удача:</b> мина обезврежена!\n"
        game['luck_saved'] = False
    
    # Строим клавиатуру-поле
    keyboard = []
    for row in range(MINES_GRID_SIZE):
        row_buttons = []
        for col in range(MINES_GRID_SIZE):
            cell_idx = row * MINES_GRID_SIZE + col
            if cell_idx in revealed:
                # Открытая безопасная ячейка
                row_buttons.append(InlineKeyboardButton("💎", callback_data=f'mines_noop'))
            else:
                # Закрытая ячейка
                row_buttons.append(InlineKeyboardButton("⬜", callback_data=f'mines_click_{cell_idx}'))
        keyboard.append(row_buttons)
    
    # Кнопка забрать выигрыш
    if len(revealed) > 0:
        keyboard.append([InlineKeyboardButton(f"💰 Забрать {potential_win}", callback_data='mines_cashout')])
    
    keyboard.append([InlineKeyboardButton("🔙 Сдаться", callback_data='mines_forfeit')])
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            pass


async def handle_mines_click(update: Update, context: ContextTypes.DEFAULT_TYPE, cell_idx: int):
    """Обработка клика по ячейке."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = MINES_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    if cell_idx in game['revealed']:
        return
    
    # Проверяем, мина ли это
    if game['grid'][cell_idx]:
        # Попали на мину! Проверяем удачу
        total = MINES_GRID_SIZE * MINES_GRID_SIZE
        safe_cells = total - game['mines_count']
        revealed_count = len(game['revealed'])
        base_prob = (safe_cells - revealed_count) / max(1, (total - revealed_count))
        extra = _casino_extra_win_chance(base_prob)
        if extra > 0 and random.random() < extra:
            game['grid'][cell_idx] = False
            game['luck_saved'] = True
        else:
            await finish_mines_game(update, context, user.id, 'exploded', cell_idx)
            return

    if not game['grid'][cell_idx]:
        # Безопасная ячейка
        game['revealed'].add(cell_idx)
        game['multiplier'] = calculate_mines_multiplier(game['mines_count'], len(game['revealed']))
        
        # Проверяем, все ли безопасные ячейки открыты
        total = MINES_GRID_SIZE * MINES_GRID_SIZE
        safe_cells = total - game['mines_count']
        if len(game['revealed']) >= safe_cells:
            # Все открыты - автоматический выигрыш
            await finish_mines_game(update, context, user.id, 'win')
        else:
            await show_mines_game_screen(update, context, user.id)


async def handle_mines_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок забирает выигрыш."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = MINES_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    if len(game['revealed']) == 0:
        await query.answer("Откройте хотя бы одну ячейку!", show_alert=True)
        return
    
    await finish_mines_game(update, context, user.id, 'cashout')


async def handle_mines_forfeit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок сдаётся."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = MINES_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    await finish_mines_game(update, context, user.id, 'forfeit')


async def finish_mines_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, result: str, exploded_cell: int = -1):
    """Завершает игру в мины."""
    query = update.callback_query
    user = query.from_user
    
    game = MINES_GAMES.get(user_id)
    if not game:
        return
    
    game['status'] = 'finished'
    bet = game['bet']
    multiplier = game['multiplier']
    grid = game['grid']
    revealed = game['revealed']
    mines_count = game['mines_count']
    
    winnings = 0
    win = False
    
    if result == 'cashout' or result == 'win':
        winnings = int(bet * multiplier)
        result_emoji = "💰"
        result_text = "ВЫИГРЫШ!" if result == 'win' else "Забрали выигрыш!"
        win = True
    elif result == 'exploded':
        result_emoji = "💥"
        result_text = "ВЗРЫВ!"
    else:  # forfeit
        result_emoji = "🏳️"
        result_text = "Сдались"
    
    # Начисляем выигрыш
    if winnings > 0:
        db.increment_coins(user_id, winnings)
    
    # Обновляем статистику
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    if win:
        current_wins = int(getattr(player, 'casino_wins', 0) or 0)
        db.update_player_stats(user_id, casino_wins=current_wins + 1)
    elif result == 'exploded':
        current_losses = int(getattr(player, 'casino_losses', 0) or 0)
        db.update_player_stats(user_id, casino_losses=current_losses + 1)
    
    # Логируем
    db.log_action(
        user_id=user_id,
        username=user.username or user.first_name,
        action_type='casino',
        action_details=f'mines: ставка {bet}, мин {mines_count}, результат {result}, множитель x{multiplier}',
        amount=winnings - bet if win else -bet,
        success=win
    )
    
    # Показываем поле с минами
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    new_balance = int(getattr(player, 'coins', 0) or 0)
    
    # Формируем визуализацию поля
    field_lines = []
    for row in range(MINES_GRID_SIZE):
        row_symbols = []
        for col in range(MINES_GRID_SIZE):
            cell_idx = row * MINES_GRID_SIZE + col
            if grid[cell_idx]:  # Мина
                if cell_idx == exploded_cell:
                    row_symbols.append("💥")
                else:
                    row_symbols.append("💣")
            elif cell_idx in revealed:
                row_symbols.append("💎")
            else:
                row_symbols.append("⬜")
        field_lines.append(" ".join(row_symbols))
    field_text = "\n".join(field_lines)
    
    text = (
        f"<b>💣 Мины — {result_emoji} {result_text}</b>\n\n"
        f"<code>{field_text}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    
    if win:
        profit = winnings - bet
        text += f"💰 Выигрыш: <b>+{profit}</b> (x{multiplier})\n"
    else:
        text += f"💸 Потеряно: <b>{bet}</b> септимов\n"
    
    text += f"💵 Баланс: <b>{new_balance}</b> септимов"
    
    # Очищаем игру
    del MINES_GAMES[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='casino_game_mines')],
        [InlineKeyboardButton("🎮 Другая игра", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Выход", callback_data='city_hightown')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            pass


# === КРАШ (CRASH) ===

def generate_crash_point() -> float:
    """Генерирует случайную точку краша."""
    # Используем экспоненциальное распределение для реалистичного краша
    # Большинство крашей происходит рано, но иногда бывают высокие множители
    import math
    e = 2.71828
    house_edge = 0.04  # 4% преимущество казино
    
    # Генерируем случайное число
    r = random.random()
    if r < house_edge:
        return 1.0  # Мгновенный краш
    
    # Формула: crash_point = 0.99 / (1 - r)
    crash = 0.99 / (1 - r)
    crash = crash * _casino_luck_mult()
    return min(round(crash, 2), CRASH_MAX_MULTIPLIER)


async def show_crash_bet_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран выбора ставки для игры Краш."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        "<b>📈 Краш</b>\n\n"
        "📋 <b>Правила:</b>\n"
        "• Множитель растёт от 1.00x\n"
        "• Нажмите 'Забрать' чтобы зафиксировать выигрыш\n"
        "• Если произойдёт КРАШ — вы потеряете ставку\n"
        "• Чем дольше ждёте — тем выше риск!\n\n"
        f"💵 Баланс: <b>{coins}</b> септимов\n\n"
        "Выберите ставку:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💵 100", callback_data='crash_bet_100'),
         InlineKeyboardButton("💵 500", callback_data='crash_bet_500')],
        [InlineKeyboardButton("💵 1,000", callback_data='crash_bet_1000'),
         InlineKeyboardButton("💵 5,000", callback_data='crash_bet_5000')],
        [InlineKeyboardButton("💵 10,000", callback_data='crash_bet_10000'),
         InlineKeyboardButton("💵 25,000", callback_data='crash_bet_25000')],
        [InlineKeyboardButton("🔙 Назад в казино", callback_data='city_casino')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def start_crash_game(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_amount: int):
    """Начинает игру Краш."""
    query = update.callback_query
    user = query.from_user
    
    if bet_amount < CASINO_MIN_BET or bet_amount > CASINO_MAX_BET:
        await query.answer(f"Ставка должна быть от {CASINO_MIN_BET} до {CASINO_MAX_BET}", show_alert=True)
        return
    
    # Проверяем, нет ли уже активной игры
    if user.id in CRASH_GAMES:
        game = CRASH_GAMES[user.id]
        if game.get('status') == 'playing':
            await query.answer("У вас уже есть активная игра!", show_alert=True)
            return
    
    lock = _get_lock(f"user:{user.id}:crash")
    if lock.locked():
        await query.answer("Игра уже обрабатывается...", show_alert=True)
        return
    
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, 'coins', 0) or 0)
        
        if coins < bet_amount:
            await query.answer("Недостаточно септимов", show_alert=True)
            return
        
        # Списываем ставку
        db.increment_coins(user.id, -bet_amount)
        
        # Генерируем точку краша
        crash_point = generate_crash_point()
        
        CRASH_GAMES[user.id] = {
            'bet': bet_amount,
            'multiplier': 1.0,
            'crash_point': crash_point,
            'status': 'playing',
            'message_id': None,
            'chat_id': query.message.chat_id,
            'task': None
        }
        
        # Показываем начальный экран
        await show_crash_game_screen(update, context, user.id)
        
        # Запускаем асинхронную анимацию
        task = asyncio.create_task(crash_animation_loop(context, user.id, user.username or user.first_name))
        CRASH_GAMES[user.id]['task'] = task


async def show_crash_game_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Показывает экран игры Краш."""
    query = update.callback_query
    
    game = CRASH_GAMES.get(user_id)
    if not game:
        return
    
    bet = game['bet']
    multiplier = game['multiplier']
    potential_win = int(bet * multiplier)
    
    # Визуальная шкала множителя
    bar_length = min(int(multiplier * 2), 20)
    bar = "🟢" * bar_length + "⬜" * (20 - bar_length)
    
    text = (
        f"<b>📈 КРАШ</b>\n\n"
        f"<code>{bar}</code>\n\n"
        f"📊 Множитель: <b>x{multiplier:.2f}</b>\n"
        f"💰 Ставка: <b>{bet}</b>\n"
        f"💵 Выигрыш: <b>{potential_win}</b>\n\n"
        "⚡ <i>Нажмите 'Забрать' пока не поздно!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"💰 ЗАБРАТЬ {potential_win}", callback_data='crash_cashout')],
    ]
    
    try:
        msg = await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        game['message_id'] = msg.message_id
    except BadRequest:
        pass


async def crash_animation_loop(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str):
    """Асинхронный цикл анимации краша - НЕ блокирует бота."""
    try:
        while True:
            await asyncio.sleep(CRASH_UPDATE_INTERVAL)
            
            game = CRASH_GAMES.get(user_id)
            if not game or game['status'] != 'playing':
                break
            
            # Увеличиваем множитель
            game['multiplier'] = round(game['multiplier'] + CRASH_GROWTH_RATE + (game['multiplier'] * 0.05), 2)
            
            # Проверяем краш
            if game['multiplier'] >= game['crash_point']:
                game['status'] = 'crashed'
                await finish_crash_game_internal(context, user_id, username, 'crashed')
                break
            
            # Обновляем экран
            bet = game['bet']
            multiplier = game['multiplier']
            potential_win = int(bet * multiplier)
            
            bar_length = min(int(multiplier * 2), 20)
            bar = "🟢" * bar_length + "⬜" * (20 - bar_length)
            
            text = (
                f"<b>📈 КРАШ</b>\n\n"
                f"<code>{bar}</code>\n\n"
                f"📊 Множитель: <b>x{multiplier:.2f}</b>\n"
                f"💰 Ставка: <b>{bet}</b>\n"
                f"💵 Выигрыш: <b>{potential_win}</b>\n\n"
                "⚡ <i>Нажмите 'Забрать' пока не поздно!</i>"
            )
            
            keyboard = [
                [InlineKeyboardButton(f"💰 ЗАБРАТЬ {potential_win}", callback_data='crash_cashout')],
            ]
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game['chat_id'],
                    message_id=game['message_id'],
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            except Exception:
                pass
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Crash animation error: {e}")


async def handle_crash_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игрок забирает выигрыш."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    game = CRASH_GAMES.get(user.id)
    if not game or game['status'] != 'playing':
        await query.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    game['status'] = 'cashed_out'
    
    # Отменяем задачу анимации
    if game.get('task'):
        game['task'].cancel()
    
    await finish_crash_game(update, context, user.id, 'cashout')


async def finish_crash_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, result: str):
    """Завершает игру Краш (вызывается при cashout)."""
    query = update.callback_query
    user = query.from_user
    
    game = CRASH_GAMES.get(user_id)
    if not game:
        return
    
    bet = game['bet']
    multiplier = game['multiplier']
    crash_point = game['crash_point']
    
    winnings = 0
    win = False
    
    if result == 'cashout':
        winnings = int(bet * multiplier)
        result_emoji = "💰"
        result_text = f"ЗАБРАЛИ на x{multiplier:.2f}!"
        win = True
    else:
        result_emoji = "💥"
        result_text = f"КРАШ на x{crash_point:.2f}!"
    
    # Начисляем выигрыш
    if winnings > 0:
        db.increment_coins(user_id, winnings)
    
    # Обновляем статистику
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    if win:
        current_wins = int(getattr(player, 'casino_wins', 0) or 0)
        db.update_player_stats(user_id, casino_wins=current_wins + 1)
    else:
        current_losses = int(getattr(player, 'casino_losses', 0) or 0)
        db.update_player_stats(user_id, casino_losses=current_losses + 1)
    
    # Логируем
    db.log_action(
        user_id=user_id,
        username=user.username or user.first_name,
        action_type='casino',
        action_details=f'crash: ставка {bet}, результат {result}, множитель x{multiplier:.2f}, crash_point x{crash_point:.2f}',
        amount=winnings - bet if win else -bet,
        success=win
    )
    
    player = db.get_or_create_player(user_id, user.username or user.first_name)
    new_balance = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        f"<b>📈 Краш — {result_emoji} {result_text}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    
    if win:
        profit = winnings - bet
        text += f"💰 Выигрыш: <b>+{profit}</b> (x{multiplier:.2f})\n"
    else:
        text += f"💸 Потеряно: <b>{bet}</b> септимов\n"
        text += f"📊 Краш был на: <b>x{crash_point:.2f}</b>\n"
    
    text += f"💵 Баланс: <b>{new_balance}</b> септимов"
    
    # Очищаем игру
    del CRASH_GAMES[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='casino_game_crash')],
        [InlineKeyboardButton("🎮 Другая игра", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Выход", callback_data='city_hightown')],
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            pass


async def finish_crash_game_internal(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, result: str):
    """Завершает игру Краш (вызывается из анимации при краше)."""
    game = CRASH_GAMES.get(user_id)
    if not game:
        return
    
    bet = game['bet']
    multiplier = game['multiplier']
    crash_point = game['crash_point']
    chat_id = game['chat_id']
    message_id = game['message_id']
    
    # Обновляем статистику
    player = db.get_or_create_player(user_id, username)
    current_losses = int(getattr(player, 'casino_losses', 0) or 0)
    db.update_player_stats(user_id, casino_losses=current_losses + 1)
    
    # Логируем
    db.log_action(
        user_id=user_id,
        username=username,
        action_type='casino',
        action_details=f'crash: ставка {bet}, КРАШ, crash_point x{crash_point:.2f}',
        amount=-bet,
        success=False
    )
    
    player = db.get_or_create_player(user_id, username)
    new_balance = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        f"<b>📈 Краш — 💥 КРАШ на x{crash_point:.2f}!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💸 Потеряно: <b>{bet}</b> септимов\n"
        f"💵 Баланс: <b>{new_balance}</b> септимов"
    )
    
    # Очищаем игру
    del CRASH_GAMES[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='casino_game_crash')],
        [InlineKeyboardButton("🎮 Другая игра", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 Выход", callback_data='city_hightown')],
    ]
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception:
        pass


async def show_casino_achievements_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает страницу достижений казино."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    
    casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
    unlocked = getattr(player, 'casino_achievements', '') or ''

    text = "<b>🏆 Достижения Казино</b>\n\n"
    
    for ach_id, ach_data in CASINO_ACHIEVEMENTS.items():
        if ach_id in unlocked:
            status = "✅"
        else:
            status = "🔒"
        
        text += f"{status} <b>{ach_data['name']}</b>\n"
        text += f"   {ach_data['desc']}\n"
        text += f"   Награда: {ach_data['reward']} септимов\n"
        text += f"   Прогресс: {casino_wins}/{ach_data['wins']}\n\n"

    keyboard = [
        [InlineKeyboardButton("🔙 В Казино", callback_data='city_casino')],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def handle_casino_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Обрабатывает ставку игрока."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if int(amount) <= 0:
        await query.answer("Неверная ставка", show_alert=True)
        return
    
    # Добавляем валидацию лимитов
    if int(amount) > CASINO_MAX_BET:
        await query.answer(f"Ставка слишком большая. Максимум: {CASINO_MAX_BET}", show_alert=True)
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
        win_prob = db.get_setting_float('casino_win_prob', CASINO_WIN_PROB)
        win_prob = max(0.0, min(1.0, float(win_prob)))
        win = random.random() < _casino_adjusted_prob(win_prob)
        coins_after = after_debit
        result_line = ""
        if win:
            coins_after = db.increment_coins(user.id, int(amount) * 2) or after_debit + int(amount) * 2
            result_line = f"🎉 Победа! Вы получаете +{amount} септимов."
            # Обновляем статистику побед
            current_wins = int(getattr(player, 'casino_wins', 0) or 0)
            db.update_player_stats(user.id, casino_wins=current_wins + 1)
        else:
            result_line = f"💥 Поражение! Списано {amount} септимов."
            # Обновляем статистику поражений
            current_losses = int(getattr(player, 'casino_losses', 0) or 0)
            db.update_player_stats(user.id, casino_losses=current_losses + 1)

        # Перерисовываем экран с обновлённым балансом и результатом (новое меню)
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
        casino_losses = int(getattr(player, 'casino_losses', 0) or 0)
        casino_total = casino_wins + casino_losses
        win_rate = (casino_wins / casino_total * 100) if casino_total > 0 else 0
        
        text = (
            "<b>🎰 Казино ХайТаун</b>\n\n"
            f"{result_line}\n"
            f"💵 Баланс: <b>{int(coins_after)}</b> септимов\n"
            f"📊 Статистика: {casino_wins}✅ / {casino_losses}❌ ({win_rate:.1f}%)\n\n"
            "🎮 <b>Выберите игру:</b>"
        )
        keyboard = [
            [InlineKeyboardButton("🪙 Монетка", callback_data='casino_game_coin_flip')],
            [InlineKeyboardButton("🎲 Кости", callback_data='casino_game_dice'), 
             InlineKeyboardButton("📊 Больше/Меньше", callback_data='casino_game_high_low')],
            [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data='casino_game_roulette_color'),
             InlineKeyboardButton("🎯 Рулетка (число)", callback_data='casino_game_roulette_number')],
            [InlineKeyboardButton("🎰 Слоты", callback_data='casino_game_slots')],
            [InlineKeyboardButton("🏆 Достижения", callback_data='casino_achievements'),
             InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
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
    
    # Получаем статистику казино
    casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
    casino_losses = int(getattr(player, 'casino_losses', 0) or 0)
    casino_total = casino_wins + casino_losses
    win_rate = (casino_wins / casino_total * 100) if casino_total > 0 else 0

    text = (
        "<b>🎰 Казино ХайТаун</b>\n\n"
        f"💰 Ваш баланс: <b>{coins}</b> септимов\n"
        f"📊 Статистика: {casino_wins}✅ / {casino_losses}❌ ({win_rate:.1f}%)\n\n"
        "🎮 <b>Выберите игру:</b>\n"
    )

    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data='casino_game_coin_flip')],
        [InlineKeyboardButton("🎲 Кости", callback_data='casino_game_dice'), 
         InlineKeyboardButton("📊 Больше/Меньше", callback_data='casino_game_high_low')],
        [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data='casino_game_roulette_color'),
         InlineKeyboardButton("🎯 Рулетка (число)", callback_data='casino_game_roulette_number')],
        [InlineKeyboardButton("🎰 Слоты", callback_data='casino_game_slots')],
        [InlineKeyboardButton("🏀 Баскетбол", callback_data='casino_game_basketball'),
         InlineKeyboardButton("⚽ Футбол", callback_data='casino_game_football')],
        [InlineKeyboardButton("🎳 Боулинг", callback_data='casino_game_bowling'),
         InlineKeyboardButton("🎯 Дартс", callback_data='casino_game_darts')],
        [InlineKeyboardButton("🏆 Достижения", callback_data='casino_achievements'),
         InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
        [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
    ]
    await msg.reply_html(text=text, reply_markup=InlineKeyboardMarkup(keyboard))


# === НОВЫЕ ФУНКЦИИ КАЗИНО С ПОЛЬЗОВАТЕЛЬСКИМИ СТАВКАМИ ===

async def start_custom_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает conversation для ввода пользовательской ставки."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    text = (
        "<b>🂰 Введите свою ставку</b>\n\n"
        f"Ваш баланс: <b>{coins}</b> септимов\n"
        f"Минимальная ставка: <b>{CASINO_MIN_BET}</b> септимов\n"
        f"Максимальная ставка: <b>{CASINO_MAX_BET}</b> септимов\n\n"
        "Напишите сумму своей ставки:"
    )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data='city_casino')]
    ]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    return CASINO_CUSTOM_BET


async def handle_custom_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод пользовательской ставки."""
    user = update.effective_user
    msg = update.effective_message
    
    if not msg or not msg.text:
        await msg.reply_text("Пожалуйста, введите число.")
        return CASINO_CUSTOM_BET
    
    try:
        bet_amount = int(msg.text.strip())
    except ValueError:
        await msg.reply_text("Неверный формат. Пожалуйста, введите целое число.")
        return CASINO_CUSTOM_BET
    
    # Валидация ставки
    if bet_amount < CASINO_MIN_BET:
        await msg.reply_text(f"Ставка слишком маленькая. Минимум: {CASINO_MIN_BET} септимов.")
        return CASINO_CUSTOM_BET
    
    if bet_amount > CASINO_MAX_BET:
        await msg.reply_text(f"Ставка слишком большая. Максимум: {CASINO_MAX_BET} септимов.")
        return CASINO_CUSTOM_BET
    
    # Проверяем баланс
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    if coins < bet_amount:
        await msg.reply_text(f"Недостаточно септимов. У вас: {coins}, нужно: {bet_amount}")
        return CASINO_CUSTOM_BET
    
    # Выполняем ставку
    lock = _get_lock(f"user:{user.id}:casino")
    if lock.locked():
        await msg.reply_text("Игра уже обрабатывается…")
        return ConversationHandler.END
    
    async with lock:
        # Повторно проверяем баланс
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins_before = int(getattr(player, 'coins', 0) or 0)
        if coins_before < bet_amount:
            await msg.reply_text("Недостаточно септимов")
            # Показываем казино и завершаем conversation
            await show_casino_after_custom_bet(msg, user, context)
            return ConversationHandler.END
        
        # Списываем ставку
        after_debit = db.increment_coins(user.id, -bet_amount)
        if after_debit is None:
            await msg.reply_text("Ошибка при списании")
            return ConversationHandler.END
        
        # Разыгрываем исход
        win_prob = db.get_setting_float('casino_win_prob', CASINO_WIN_PROB)
        win_prob = max(0.0, min(1.0, float(win_prob)))
        win = random.random() < _casino_adjusted_prob(win_prob)
        coins_after = after_debit
        result_line = ""
        if win:
            coins_after = db.increment_coins(user.id, bet_amount * 2) or after_debit + bet_amount * 2
            result_line = f"🎉 Победа! Вы получаете +{bet_amount} септимов."
            # Обновляем статистику побед
            current_wins = int(getattr(player, 'casino_wins', 0) or 0)
            db.update_player_stats(user.id, casino_wins=current_wins + 1)
        else:
            result_line = f"💥 Поражение! Списано {bet_amount} септимов."
            # Обновляем статистику поражений
            current_losses = int(getattr(player, 'casino_losses', 0) or 0)
            db.update_player_stats(user.id, casino_losses=current_losses + 1)
        
        # Показываем результат с новым главным меню
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
        casino_losses = int(getattr(player, 'casino_losses', 0) or 0)
        casino_total = casino_wins + casino_losses
        win_rate = (casino_wins / casino_total * 100) if casino_total > 0 else 0
        
        text = (
            "<b>🎰 Казино ХайТаун</b>\n\n"
            f"{result_line}\n"
            f"💵 Баланс: <b>{int(coins_after)}</b> септимов\n"
            f"📊 Статистика: {casino_wins}✅ / {casino_losses}❌ ({win_rate:.1f}%)\n\n"
            "🎮 <b>Выберите игру:</b>"
        )
        keyboard = [
            [InlineKeyboardButton("🪙 Монетка", callback_data='casino_game_coin_flip')],
            [InlineKeyboardButton("🎲 Кости", callback_data='casino_game_dice'), 
             InlineKeyboardButton("📊 Больше/Меньше", callback_data='casino_game_high_low')],
            [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data='casino_game_roulette_color'),
             InlineKeyboardButton("🎯 Рулетка (число)", callback_data='casino_game_roulette_number')],
            [InlineKeyboardButton("🎰 Слоты", callback_data='casino_game_slots')],
            [InlineKeyboardButton("🏀 Баскетбол", callback_data='casino_game_basketball'),
             InlineKeyboardButton("⚽ Футбол", callback_data='casino_game_football')],
            [InlineKeyboardButton("🎳 Боулинг", callback_data='casino_game_bowling'),
             InlineKeyboardButton("🎯 Дартс", callback_data='casino_game_darts')],
            [InlineKeyboardButton("🏆 Достижения", callback_data='casino_achievements'),
             InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
            [InlineKeyboardButton("🔙 Назад", callback_data='city_hightown')],
        ]
        
        await msg.reply_html(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    return ConversationHandler.END


async def cancel_custom_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет ввод пользовательской ставки."""
    query = update.callback_query
    if query:
        await query.answer()
        # Показываем обычное казино
        await show_city_casino(update, context)
    return ConversationHandler.END


async def show_casino_after_custom_bet(msg, user, context):
    """Показывает казино после завершения custom bet."""
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    
    # Получаем статистику казино
    casino_wins = int(getattr(player, 'casino_wins', 0) or 0)
    casino_losses = int(getattr(player, 'casino_losses', 0) or 0)
    casino_total = casino_wins + casino_losses
    win_rate = (casino_wins / casino_total * 100) if casino_total > 0 else 0

    text = (
        "<b>🎰 Казино ХайТаун</b>\n\n"
        f"💰 Ваш баланс: <b>{coins}</b> септимов\n"
        f"📊 Статистика: {casino_wins}✅ / {casino_losses}❌ ({win_rate:.1f}%)\n\n"
        "🎮 <b>Выберите игру:</b>\n"
    )

    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data='casino_game_coin_flip')],
        [InlineKeyboardButton("🎲 Кости", callback_data='casino_game_dice'), 
         InlineKeyboardButton("📊 Больше/Меньше", callback_data='casino_game_high_low')],
        [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data='casino_game_roulette_color'),
         InlineKeyboardButton("🎯 Рулетка (число)", callback_data='casino_game_roulette_number')],
        [InlineKeyboardButton("🎰 Слоты", callback_data='casino_game_slots')],
        [InlineKeyboardButton("🏀 Баскетбол", callback_data='casino_game_basketball'),
         InlineKeyboardButton("⚽ Футбол", callback_data='casino_game_football')],
        [InlineKeyboardButton("🎳 Боулинг", callback_data='casino_game_bowling'),
         InlineKeyboardButton("🎯 Дартс", callback_data='casino_game_darts')],
        [InlineKeyboardButton("🏆 Достижения", callback_data='casino_achievements'),
         InlineKeyboardButton("📜 Правила", callback_data='casino_rules')],
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

    context.user_data['last_plantation_screen'] = 'market'

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    if lang == 'en':
        text = (
            "<b>🌱 Plantation</b>\n\n"
            "Grow energy drinks on beds and harvest them when ready.\n\n"
            "⭐ Harvest reward: <b>+3 rating</b> for each harvest.\n"
            "⭐ Rating affects drop rates: up to <b>+10%</b> for rare drinks from search and up to <b>+5%</b> for rare daily rewards."
        )
    else:
        text = (
            "<b>🌱 Плантация</b>\n\n"
            "Выращивайте энергетики на грядках и собирайте урожай, когда он готов.\n\n"
            "⭐ Награда за сбор: <b>+3 рейтинга</b> за каждый сбор урожая.\n"
            "⭐ Рейтинг влияет на шансы: до <b>+10%</b> к редким напиткам из поиска и до <b>+5%</b> к редким наградам ежедневного бонуса."
        )
    
    keyboard = [
        [InlineKeyboardButton("🌾 Мои грядки", callback_data='plantation_my_beds')],
        [InlineKeyboardButton("🛒 Купить семена", callback_data='plantation_shop')],
        [InlineKeyboardButton("🧪 Купить удобрения", callback_data='plantation_fertilizers_shop')],
        [InlineKeyboardButton("💰 Цены на грядки", callback_data='plantation_bed_prices')],
        [InlineKeyboardButton("➕ Купить грядку", callback_data='plantation_buy_bed')],
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

async def show_plantation_bed_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    try:
        db.ensure_player_beds(user.id)
    except Exception:
        pass

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, 'coins', 0) or 0)
    beds = db.get_player_beds(user.id) or []
    owned = len(beds)

    lines = [
        "<b>💰 Цены на грядки</b>",
        f"\n💰 Баланс: {coins} септимов",
        "\nСтоимость покупки новых грядок:",
        "1-я грядка — бесплатно (выдаётся автоматически)",
        "2-я грядка — 1000💰",
        "3-я грядка — 2000💰",
        "4-я грядка — 4000💰",
        "5-я грядка — 8000💰",
    ]

    if owned >= 5:
        lines.append("\n✅ У вас уже максимум грядок (5/5)")
    else:
        next_index = owned + 1
        next_price = 0
        if next_index >= 2:
            next_price = 1000 * (2 ** (next_index - 2))
        if next_index <= 1:
            lines.append("\nСледующая грядка: бесплатно")
        else:
            lines.append(f"\nСледующая грядка ({next_index}-я): {next_price}💰")

    keyboard = []
    if owned < 5:
        keyboard.append([InlineKeyboardButton("➕ Купить следующую грядку", callback_data='plantation_buy_bed')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_plantation_my_beds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои грядки."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    context.user_data['last_plantation_screen'] = 'beds'
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    max_fert = max(1, db.get_setting_int('plantation_fertilizer_max_per_bed', PLANTATION_FERTILIZER_MAX_PER_BED))
    lang = getattr(player, 'language', 'ru') or 'ru'
    # Гарантируем грядки и читаем текущее состояние
    try:
        db.ensure_player_beds(user.id)
    except Exception:
        pass
    beds = db.get_player_beds(user.id) or []

    if lang == 'en':
        lines = ["<b>🌾 My beds</b>", "⭐ Each harvest gives <b>+3 rating</b>."]
    else:
        lines = ["<b>🌾 Мои грядки</b>", "⭐ Каждый сбор урожая даёт <b>+3 рейтинга</b>."]
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
            # Получаем фактическое время роста с учетом удобрения
            actual_grow_time = db.get_actual_grow_time(b)
            base_grow_time = int(getattr(st, 'grow_time_sec', 0) or 0) if st else 0
            planted = int(getattr(b, 'planted_at', 0) or 0)
            passed = max(0, int(time.time()) - planted)
            remain = max(0, actual_grow_time - passed)
            last = int(getattr(b, 'last_watered_at', 0) or 0)
            interval = int(getattr(st, 'water_interval_sec', 0) or 0) if st else 0
            next_water = max(0, interval - (int(time.time()) - last)) if last and interval else 0
            
            # Проверяем статус удобрений
            fert_status = db.get_fertilizer_status(b, check_duration=True)
            fert_total_status = db.get_fertilizer_status(b, check_duration=False)
            
            prog = f"⏳ До созревания: { _fmt_time(remain) }" if remain else "⏳ Проверка готовности…"
            water_info = "💧 Можно поливать" if not next_water else f"💧 Через { _fmt_time(next_water) }"

            growth_line = None
            try:
                if base_grow_time > 0 and actual_grow_time > 0 and actual_grow_time < base_grow_time:
                    pct = int(round((1.0 - (float(actual_grow_time) / float(base_grow_time))) * 100.0))
                    growth_line = f"⚡ Рост: -{pct}% ({_fmt_time(base_grow_time)} → {_fmt_time(actual_grow_time)})"
                elif actual_grow_time > 0:
                    growth_line = f"⚡ Рост: {_fmt_time(actual_grow_time)}"
            except Exception:
                growth_line = None

            fert_lines = []
            try:
                info_list = list(fert_status.get('fertilizers_info', []) or [])
            except Exception:
                info_list = []
            slots_used = len(info_list)
            total_count = _count_bed_total_fertilizers(b)
            protection_used = _count_bed_resilience_fertilizers(b)
            main_used = max(0, total_count - protection_used)
            total_limit = max_fert + 1
            fert_header = (
                f"🧪 Удобрения: {main_used}/{max_fert} | "
                f"🛡️ защита {protection_used}/1 | "
                f"всего {total_count}/{total_limit}"
            )
            fert_lines.append(fert_header)
            if total_count >= total_limit:
                fert_lines.append("⚠️ Лимит удобрений исчерпан до сбора")

            try:
                total_mult = float(fert_total_status.get('total_multiplier') or 1.0)
            except Exception:
                total_mult = 1.0

            if total_mult > 1.0:
                try:
                    fert_lines.append(f"🌾 Урожай: x{total_mult:.2f}")
                except Exception:
                    fert_lines.append("🌾 Урожай: x1.00")

            if slots_used > 0:
                try:
                    info_list.sort(key=lambda x: int(x.get('time_left') or 0), reverse=True)
                except Exception:
                    pass

                icon_map = {
                    'mega_yield': '🌾',
                    'yield': '🌾',
                    'quality': '💎',
                    'complex': '🌟',
                    'growth_quality': '⚡',
                    'time': '⚡',
                    'growth': '⚡',
                    'nutrition': '🌿',
                    'bio': '🌿',
                    'resilience': '🛡️',
                    'basic': '🧪',
                }

                for fi in info_list:
                    try:
                        fn = html.escape(str(fi.get('name') or 'Удобрение'))
                        mult = float(fi.get('multiplier') or 1.0)
                        tl = int(fi.get('time_left') or 0)
                        et = str(fi.get('effect_type') or 'basic')
                        ico = icon_map.get(et, '🧪')
                        fert_lines.append(f"• {fn} {ico} x{mult:.2f} — {_fmt_time(tl)}")
                    except Exception:
                        continue
            else:
                try:
                    if growth_line and base_grow_time > 0 and actual_grow_time > 0 and actual_grow_time < base_grow_time:
                        fert_lines[0] = f"{fert_header} (ускорение сохранено)"
                except Exception:
                    pass

            status_line = None
            try:
                se = (getattr(b, 'status_effect', '') or '').strip().lower()
                if se:
                    lvl = int(getattr(b, 'status_effect_level', 1) or 1)
                    status_map = {'weeds': 'сорняки', 'pests': 'вредители', 'drought': 'засуха'}
                    status_h = status_map.get(se, se)
                    status_line = f"⚠️ Негатив: {status_h} (ур.{lvl})"
            except Exception:
                status_line = None

            block = [f"🌱 Грядка {idx}: Растёт {name}", prog, water_info]
            if status_line:
                block.append(status_line)
            if growth_line:
                block.append(growth_line)
            block.extend(fert_lines)
            lines.append("\n".join(block))
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
    keyboard.append([InlineKeyboardButton("💰 Цены на грядки", callback_data='plantation_bed_prices')])
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
            # Исключаем энергетики с is_special=True из семян для плантаций
            non_special_drinks = [d for d in drinks if not getattr(d, 'is_special', False)]
            if non_special_drinks:
                pick = random.sample(non_special_drinks, min(3, len(non_special_drinks)))
                seed_types = db.ensure_seed_types_for_drinks([int(d.id) for d in pick]) or []
            else:
                # Если нет обычных энергетиков, фильтруем существующие семена
                all_seed_types = db.list_seed_types() or []
                seed_types = [st for st in all_seed_types 
                            if st.drink_id and st.drink 
                            and not getattr(st.drink, 'is_special', False)]
        else:
            # Фильтруем существующие семена от Special энергетиков
            all_seed_types = db.list_seed_types() or []
            seed_types = [st for st in all_seed_types 
                        if st.drink_id and st.drink 
                        and not getattr(st.drink, 'is_special', False)]
    except Exception:
        # Фильтруем существующие семена от Special энергетиков
        all_seed_types = db.list_seed_types() or []
        seed_types = [st for st in all_seed_types 
                    if st.drink_id and st.drink 
                    and not getattr(st.drink, 'is_special', False)]

    prev_ids = context.user_data.pop('plantation_shop_message_ids', None)
    if isinstance(prev_ids, list) and prev_ids:
        for mid in prev_ids:
            try:
                await context.bot.delete_message(chat_id=user.id, message_id=int(mid))
            except Exception:
                pass

    try:
        if query.message:
            await query.message.delete()
    except BadRequest:
        pass

    sent_ids: list[int] = []
    balance = int(getattr(player, 'coins', 0) or 0)
    header_text = f"<b>🛒 Магазин семян</b>\n\n💰 Баланс: {balance} септимов"
    try:
        msg = await context.bot.send_message(chat_id=user.id, text=header_text, parse_mode='HTML')
        sent_ids.append(int(msg.message_id))
    except Exception:
        pass

    if seed_types:
        for st in seed_types:
            drink = None
            try:
                did = int(getattr(st, 'drink_id', 0) or 0)
            except Exception:
                did = 0
            if did:
                try:
                    drink = db.get_drink_by_id(did)
                except Exception:
                    drink = None
            name = html.escape(getattr(st, 'name', 'Семена'))
            desc = html.escape((getattr(st, 'description', None) or (getattr(drink, 'description', None) if drink else None) or '').strip())
            price = int(getattr(st, 'price_coins', 0) or 0)
            ymin = int(getattr(st, 'yield_min', 0) or 0)
            ymax = int(getattr(st, 'yield_max', 0) or 0)
            grow_m = int((int(getattr(st, 'grow_time_sec', 0) or 0)) / 60)

            caption_lines = [f"<b>🌱 {name}</b>"]
            if desc:
                caption_lines.append(desc)
            caption_lines.append("")
            caption_lines.append(f"💰 Цена: <b>{price}</b> септимов / 1 шт.")
            caption_lines.append(f"🥕 Урожай: {ymin}-{ymax}")
            caption_lines.append(f"⏱️ Рост: ~{grow_m} мин")
            caption = "\n".join(caption_lines)

            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Купить", callback_data=f'seed_buy_custom_{st.id}')]])

            image_path = getattr(drink, 'image_path', None) if drink else None
            image_full_path = os.path.join(ENERGY_IMAGES_DIR, image_path) if image_path else None

            try:
                if image_full_path and os.path.exists(image_full_path):
                    with open(image_full_path, 'rb') as photo:
                        m = await context.bot.send_photo(chat_id=user.id, photo=photo, caption=caption, reply_markup=kb, parse_mode='HTML')
                else:
                    m = await context.bot.send_message(chat_id=user.id, text=caption, reply_markup=kb, parse_mode='HTML')
                sent_ids.append(int(m.message_id))
            except Exception:
                pass
    else:
        try:
            m = await context.bot.send_message(chat_id=user.id, text="Пока нет доступных семян. Загляните позже.")
            sent_ids.append(int(m.message_id))
        except Exception:
            pass

    nav_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='market_plantation')]])
    try:
        m = await context.bot.send_message(chat_id=user.id, text="Что дальше?", reply_markup=nav_kb)
        sent_ids.append(int(m.message_id))
    except Exception:
        pass

    context.user_data['plantation_shop_message_ids'] = sent_ids


async def start_seed_custom_buy_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        seed_type_id = int(query.data.split('_')[-1])
        return await start_seed_custom_buy(update, context, seed_type_id)
    except Exception:
        await query.answer("Ошибка. Попробуйте позже.", show_alert=True)
        return ConversationHandler.END


def _build_seed_buy_prompt_text(seed_type, balance: int) -> tuple[str, int, int]:
    name = html.escape(getattr(seed_type, 'name', 'Семена'))
    price = int(getattr(seed_type, 'price_coins', 0) or 0)
    max_qty = (balance // price) if price > 0 else 0
    text = f"<b>🛒 Покупка семян</b>\n\n"
    text += f"<b>{name}</b>\n"
    text += f"💰 Цена: {price} септимов за 1 шт.\n"
    text += f"💰 Ваш баланс: {balance} септимов\n"
    text += f"📦 Максимум: {max_qty} шт.\n\n"
    if max_qty > 0:
        text += f"<i>Введите количество для покупки (1-{max_qty}):</i>"
    else:
        text += "<i>У вас недостаточно монет для покупки этих семян.</i>"
    return text, price, max_qty


async def start_seed_custom_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, seed_type_id: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    context.user_data['seed_custom_buy_id'] = int(seed_type_id)

    seed_type = None
    try:
        seed_type = db.get_seed_type_by_id(int(seed_type_id))
    except Exception:
        seed_type = None
    if not seed_type:
        await query.answer("Семена не найдены", show_alert=True)
        return ConversationHandler.END

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    balance = int(getattr(player, 'coins', 0) or 0)

    text, _, max_qty = _build_seed_buy_prompt_text(seed_type, balance)
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='seed_custom_cancel')]]

    try:
        if max_qty <= 0:
            await query.answer("Недостаточно монет", show_alert=True)
            await show_plantation_shop(update, context)
            return ConversationHandler.END

        if getattr(query.message, 'photo', None):
            await query.edit_message_caption(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return SEED_CUSTOM_QTY
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            return SEED_CUSTOM_QTY
        except Exception:
            return ConversationHandler.END


async def seed_custom_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    seed_type_id = context.user_data.get('seed_custom_buy_id')
    if not seed_type_id:
        await query.answer("Ошибка: семена не выбраны", show_alert=True)
        return ConversationHandler.END

    seed_type = None
    try:
        seed_type = db.get_seed_type_by_id(int(seed_type_id))
    except Exception:
        seed_type = None
    if not seed_type:
        await query.answer("Семена не найдены", show_alert=True)
        return ConversationHandler.END

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    balance = int(getattr(player, 'coins', 0) or 0)

    text, _, _ = _build_seed_buy_prompt_text(seed_type, balance)
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='seed_custom_cancel')]]

    try:
        if getattr(query.message, 'photo', None):
            await query.edit_message_caption(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except BadRequest:
        pass

    return SEED_CUSTOM_QTY


async def seed_custom_buy_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    seed_type_id = context.user_data.get('seed_custom_buy_id')
    if not seed_type_id:
        await query.answer("Ошибка: семена не выбраны", show_alert=True)
        return ConversationHandler.END

    seed_type = None
    try:
        seed_type = db.get_seed_type_by_id(int(seed_type_id))
    except Exception:
        seed_type = None
    if not seed_type:
        await query.answer("Семена не найдены", show_alert=True)
        return ConversationHandler.END

    price = int(getattr(seed_type, 'price_coins', 0) or 0)
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    balance = int(getattr(player, 'coins', 0) or 0)
    max_qty = (balance // price) if price > 0 else 0
    if max_qty <= 0:
        await query.answer("Недостаточно монет", show_alert=True)
        return SEED_CUSTOM_QTY

    lock = _get_lock(f"user:{user.id}:plantation_seed_buy")
    if lock.locked():
        await query.answer("Обработка…", show_alert=False)
        return SEED_CUSTOM_QTY

    async with lock:
        res = db.purchase_seeds(user.id, int(seed_type_id), int(max_qty))
        if not res.get('ok'):
            await query.answer("Не удалось купить", show_alert=True)
            return SEED_CUSTOM_QTY

        name = html.escape(getattr(seed_type, 'name', 'Семена'))
        text = (
            f"✅ <b>Куплено!</b>\n\n"
            f"{name} x {max_qty}\n"
            f"💰 Баланс: {res.get('coins_left')} септимов\n"
            f"📦 В инвентаре: {res.get('inventory_qty')} шт."
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Вернуться в магазин", callback_data='plantation_shop')]])
        try:
            if getattr(query.message, 'photo', None):
                await query.edit_message_caption(text, reply_markup=keyboard, parse_mode='HTML')
            else:
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        except BadRequest:
            pass

    return ConversationHandler.END


async def handle_seed_custom_qty_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if not msg or not msg.text:
        await msg.reply_text("Пожалуйста, введите число.")
        return SEED_CUSTOM_QTY

    seed_type_id = context.user_data.get('seed_custom_buy_id')
    if not seed_type_id:
        await msg.reply_text("Ошибка: семена не выбраны.")
        return ConversationHandler.END

    try:
        quantity = int(msg.text.strip())
    except ValueError:
        await msg.reply_text("❌ Неверный формат. Пожалуйста, введите целое число.")
        return SEED_CUSTOM_QTY

    if quantity <= 0:
        await msg.reply_text("❌ Количество должно быть больше 0.")
        return SEED_CUSTOM_QTY

    if quantity > 1000:
        await msg.reply_text("❌ Слишком много! Максимум 1000 шт. за раз.")
        return SEED_CUSTOM_QTY

    seed_type = None
    try:
        seed_type = db.get_seed_type_by_id(int(seed_type_id))
    except Exception:
        seed_type = None
    if not seed_type:
        await msg.reply_text("❌ Семена не найдены.")
        return ConversationHandler.END

    price = int(getattr(seed_type, 'price_coins', 0) or 0)
    if price <= 0:
        await msg.reply_text("❌ Эти семена сейчас недоступны для покупки.")
        return ConversationHandler.END

    total_cost = price * int(quantity)
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    balance = int(getattr(player, 'coins', 0) or 0)

    if total_cost > balance:
        max_qty = (balance // price) if price > 0 else 0
        text = f"❌ Недостаточно монет!\nНужно: {total_cost} септимов\nУ вас: {balance} септимов"
        keyboard = [
            [InlineKeyboardButton("✏️ Ввести другое количество", callback_data='seed_custom_retry')],
        ]
        if max_qty > 0:
            keyboard.append([InlineKeyboardButton(f"🪙 Купить максимум ({max_qty})", callback_data='seed_custom_buy_max')])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='seed_custom_cancel')])
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return SEED_CUSTOM_QTY

    lock = _get_lock(f"user:{user.id}:plantation_seed_buy")
    if lock.locked():
        await msg.reply_text("⏳ Обработка предыдущей покупки...")
        return SEED_CUSTOM_QTY

    async with lock:
        res = db.purchase_seeds(user.id, int(seed_type_id), int(quantity))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await msg.reply_text('❌ Недостаточно монет')
                return SEED_CUSTOM_QTY
            elif reason == 'no_such_seed':
                await msg.reply_text('❌ Семена не найдены')
                return ConversationHandler.END
            elif reason == 'invalid_quantity':
                await msg.reply_text('❌ Неверное количество')
                return SEED_CUSTOM_QTY
            else:
                await msg.reply_text('❌ Ошибка. Попробуйте позже.')
                return ConversationHandler.END
        else:
            name = html.escape(getattr(seed_type, 'name', 'Семена'))
            await msg.reply_html(
                f"✅ <b>Куплено!</b>\n\n"
                f"{name} x {quantity}\n"
                f"💰 Баланс: {res.get('coins_left')} септимов\n"
                f"📦 В инвентаре: {res.get('inventory_qty')} шт."
            )

        keyboard = [[InlineKeyboardButton("🛒 Вернуться в магазин", callback_data='plantation_shop')]]
        await msg.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END


async def cancel_seed_custom_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await show_plantation_shop(update, context)
    return ConversationHandler.END

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
    """Статистика плантации - улучшенная версия с красивым интерфейсом."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    beds = db.get_player_beds(user.id) or []
    seed_inv = db.get_seed_inventory(user.id) or []
    
    # Получаем инвентарь удобрений
    try:
        fert_inv = db.get_fertilizer_inventory(user.id) or []
    except Exception:
        fert_inv = []
    
    # Получаем информацию о фермере
    try:
        farmer = db.get_selyuk_by_type(user.id, 'farmer')
    except Exception:
        farmer = None

    # Подсчёт состояний грядок
    counts = {'empty': 0, 'growing': 0, 'ready': 0, 'withered': 0}
    growing_info = []  # Информация о растущих грядках
    ready_info = []    # Информация о готовых грядках
    
    now_ts = int(time.time())
    
    for b in beds:
        s = str(getattr(b, 'state', 'empty') or 'empty')
        counts[s] = counts.get(s, 0) + 1
        
        if s == 'growing':
            st = getattr(b, 'seed_type', None)
            if st:
                actual_grow_time = db.get_actual_grow_time(b)
                planted = int(getattr(b, 'planted_at', 0) or 0)
                passed = max(0, now_ts - planted)
                remain = max(0, actual_grow_time - passed)
                progress = min(100, int((passed / actual_grow_time) * 100)) if actual_grow_time > 0 else 0
                growing_info.append({
                    'idx': int(getattr(b, 'bed_index', 0) or 0),
                    'name': getattr(st, 'name', 'Растение'),
                    'remain': remain,
                    'progress': progress
                })
        elif s == 'ready':
            st = getattr(b, 'seed_type', None)
            if st:
                ready_info.append({
                    'idx': int(getattr(b, 'bed_index', 0) or 0),
                    'name': getattr(st, 'name', 'Растение')
                })

    # === ФОРМИРУЕМ КРАСИВЫЙ ТЕКСТ ===
    coins = int(getattr(player, 'coins', 0) or 0)
    
    lines = [
        "╔══════════════════════════╗",
        "║   📊 <b>СТАТИСТИКА ПЛАНТАЦИИ</b>   ║",
        "╚══════════════════════════╝",
        ""
    ]
    
    # Блок баланса
    lines.append(f"💰 <b>Баланс:</b> {coins:,} септимов".replace(',', ' '))
    lines.append("")
    
    # Блок грядок с визуальным отображением
    total_beds = len(beds)
    lines.append(f"🌾 <b>Грядки ({total_beds} шт.):</b>")
    
    # Визуальная полоса состояний
    if total_beds > 0:
        bar_length = 12
        empty_blocks = int(counts['empty'] / total_beds * bar_length)
        growing_blocks = int(counts['growing'] / total_beds * bar_length)
        ready_blocks = int(counts['ready'] / total_beds * bar_length)
        withered_blocks = int(counts['withered'] / total_beds * bar_length)
        
        # Корректируем для точности
        total_blocks = empty_blocks + growing_blocks + ready_blocks + withered_blocks
        if total_blocks < bar_length and total_beds > 0:
            if counts['growing'] > 0:
                growing_blocks += bar_length - total_blocks
            elif counts['empty'] > 0:
                empty_blocks += bar_length - total_blocks
        
        visual_bar = "⬜" * empty_blocks + "🌱" * growing_blocks + "✅" * ready_blocks + "💀" * withered_blocks
        lines.append(f"   {visual_bar}")
    
    # Детальная статистика грядок
    lines.append(f"   ⬜ Пустых: <b>{counts['empty']}</b>")
    lines.append(f"   🌱 Растёт: <b>{counts['growing']}</b>")
    lines.append(f"   ✅ Готово: <b>{counts['ready']}</b>")
    if counts['withered'] > 0:
        lines.append(f"   💀 Завяло: <b>{counts['withered']}</b>")
    lines.append("")
    
    # Детали растущих грядок (если есть)
    if growing_info:
        lines.append("⏳ <b>Созревают:</b>")
        for gi in growing_info[:3]:  # Показываем первые 3
            # Прогресс-бар
            prog_filled = gi['progress'] // 10
            prog_empty = 10 - prog_filled
            prog_bar = "▓" * prog_filled + "░" * prog_empty
            time_str = _fmt_time(gi['remain'])
            lines.append(f"   🌱 #{gi['idx']} {html.escape(gi['name'])}")
            lines.append(f"      [{prog_bar}] {gi['progress']}%")
            lines.append(f"      ⏱ Осталось: {time_str}")
        if len(growing_info) > 3:
            lines.append(f"   <i>...и ещё {len(growing_info) - 3} грядок</i>")
        lines.append("")
    
    # Готовые к сбору
    if ready_info:
        lines.append("🎉 <b>Готово к сбору:</b>")
        for ri in ready_info[:5]:
            lines.append(f"   ✅ #{ri['idx']} {html.escape(ri['name'])}")
        if len(ready_info) > 5:
            lines.append(f"   <i>...и ещё {len(ready_info) - 5} грядок</i>")
        lines.append("")
    
    # Блок инвентаря семян
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    total_seeds = sum(int(getattr(it, 'quantity', 0) or 0) for it in seed_inv)
    lines.append(f"🌱 <b>Семена:</b> {total_seeds} шт.")
    if seed_inv:
        seed_items = []
        for it in seed_inv:
            st = getattr(it, 'seed_type', None)
            name = html.escape(getattr(st, 'name', 'Семена')) if st else 'Семена'
            qty = int(getattr(it, 'quantity', 0) or 0)
            if qty > 0:
                seed_items.append(f"{name}: {qty}")
        if seed_items:
            lines.append(f"   {', '.join(seed_items[:3])}")
            if len(seed_items) > 3:
                lines.append(f"   <i>...и ещё {len(seed_items) - 3} видов</i>")
    else:
        lines.append("   <i>Инвентарь пуст</i>")
    lines.append("")
    
    # Блок удобрений
    total_ferts = sum(int(getattr(it, 'quantity', 0) or 0) for it in fert_inv if getattr(it, 'quantity', 0) and int(getattr(it, 'quantity', 0) or 0) > 0)
    lines.append(f"🧪 <b>Удобрения:</b> {total_ferts} шт.")
    if fert_inv:
        fert_items = []
        for it in fert_inv:
            fz = getattr(it, 'fertilizer', None)
            qty = int(getattr(it, 'quantity', 0) or 0)
            if fz and qty > 0:
                fert_items.append(f"{getattr(fz, 'name', 'Удобрение')}: {qty}")
        if fert_items:
            lines.append(f"   {', '.join(fert_items[:3])}")
            if len(fert_items) > 3:
                lines.append(f"   <i>...и ещё {len(fert_items) - 3} видов</i>")
    else:
        lines.append("   <i>Инвентарь пуст</i>")
    lines.append("")
    
    # Блок фермера
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if farmer:
        level = int(getattr(farmer, 'level', 1) or 1)
        balance = int(getattr(farmer, 'balance_septims', 0) or 0)
        is_enabled = bool(getattr(farmer, 'is_enabled', False))
        status_emoji = "🟢" if is_enabled else "🔴"
        level_icons = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐"}
        
        lines.append(f"👨‍🌾 <b>Селюк-Фермер:</b>")
        lines.append(f"   {level_icons.get(level, '⭐')} Уровень: <b>{level}</b>")
        lines.append(f"   {status_emoji} Статус: <b>{'Активен' if is_enabled else 'Отключен'}</b>")
        lines.append(f"   💵 Баланс: <b>{balance:,} септимов</b>".replace(',', ' '))
        
        # Бонусы по уровню
        if level == 1:
            lines.append("   📋 Автополив (-50💰)")
        elif level == 2:
            lines.append("   📋 Автополив (-45💰) + Автосбор")
        elif level == 3:
            lines.append("   📋 Полный автомат (-45💰)")
        elif level >= 4:
            lines.append("   📋 Полный автомат (-45💰) + Автоудобрение")
    else:
        lines.append("👨‍🌾 <b>Селюк-Фермер:</b> <i>Не куплен</i>")
        lines.append("   <i>Купите в разделе 🌾 Селюки!</i>")
    
    # Кнопки навигации
    keyboard = [
        [
            InlineKeyboardButton("🌾 К грядкам", callback_data='plantation_my_beds'),
            InlineKeyboardButton("🛒 Семена", callback_data='plantation_shop')
        ],
        [
            InlineKeyboardButton("🧪 Удобрения", callback_data='plantation_fertilizers_shop'),
            InlineKeyboardButton("➕ Грядка", callback_data='plantation_buy_bed')
        ],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data='market_plantation')]
    ]
    
    # Добавляем кнопку сбора, если есть готовые
    if counts['ready'] > 0:
        keyboard.insert(0, [InlineKeyboardButton(f"🥕 Собрать урожай ({counts['ready']})", callback_data='plantation_harvest_all')])
    
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# === FERTILIZERS: SHOP, INVENTORY, APPLY ===

def get_fertilizer_category(fertilizer) -> str:
    """Определяет категорию удобрения по его эффекту."""
    effect_type = getattr(fertilizer, 'effect_type', None)
    if effect_type:
        if effect_type in ('growth', 'time', 'growth_quality'):
            return 'growth'
        if effect_type in ('yield', 'mega_yield', 'nutrition'):
            return 'yield'
        if effect_type in ('quality',):
            return 'quality'
        if effect_type in ('complex', 'bio'):
            return 'complex'
        if effect_type in ('resilience',):
            return 'resilience'
        return 'other'

    effect = str(getattr(fertilizer, 'effect', '') or '').lower()
    name = str(getattr(fertilizer, 'name', '') or '').lower()
    if 'стойк' in effect or 'иммун' in effect or 'защит' in effect:
        return 'resilience'
    if 'время' in effect or 'рост' in effect or 'суперрост' in name:
        return 'growth'  # Ускорение роста
    if 'урожай' in effect or 'мегаурожай' in name or 'питание' in effect:
        return 'yield'  # Увеличение урожая
    if 'качество' in effect or 'калийное' in name or 'минерал' in name:
        return 'quality'  # Повышение качества
    if 'всё' in effect or 'био' in effect or 'комплекс' in name:
        return 'complex'  # Комплексные
    return 'other'

def get_category_emoji(category: str) -> str:
    """Возвращает эмодзи для категории."""
    emojis = {
        'growth': '⚡',
        'yield': '🌾',
        'quality': '💎',
        'complex': '🌟',
        'resilience': '🛡️',
        'other': '🧪'
    }
    return emojis.get(category, '🧪')

def get_category_name(category: str) -> str:
    """Возвращает название категории на русском."""
    names = {
        'growth': 'Ускорение роста',
        'yield': 'Увеличение урожая',
        'quality': 'Повышение качества',
        'complex': 'Комплексные',
        'resilience': 'Защита',
        'other': 'Прочие',
        'all': 'Все удобрения'
    }
    return names.get(category, 'Прочие')

async def show_plantation_fertilizers_shop(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_category: str = 'all'):
    """Магазин удобрений с улучшенным интерфейсом."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    
    # Гарантируем наличие дефолтных удобрений (и новых) перед выводом
    try:
        db.ensure_default_fertilizers()
    except Exception:
        pass

    # Получаем удобрения и инвентарь
    try:
        fertilizers = db.list_fertilizers() or []
    except Exception:
        fertilizers = []
    if fertilizers:
        # Hide legacy duplicates with cosmetically different names,
        # e.g. "СуперРост" vs "Супер Рост".
        deduped = {}
        for fz in fertilizers:
            name = str(getattr(fz, 'name', '') or '')
            normalized = ''.join(name.lower().split())
            if not normalized:
                normalized = f"id:{int(getattr(fz, 'id', 0) or 0)}"
            current = deduped.get(normalized)
            if current is None:
                deduped[normalized] = fz
                continue
            cur_name = str(getattr(current, 'name', '') or '')
            new_has_space = (' ' in name)
            cur_has_space = (' ' in cur_name)
            if new_has_space and not cur_has_space:
                deduped[normalized] = fz
            elif new_has_space == cur_has_space:
                if int(getattr(fz, 'id', 0) or 0) < int(getattr(current, 'id', 0) or 0):
                    deduped[normalized] = fz
        fertilizers = sorted(deduped.values(), key=lambda x: int(getattr(x, 'id', 0) or 0))
    
    try:
        inv = db.get_fertilizer_inventory(user.id) or []
        inventory_dict = {}
        for it in inv:
            fz = getattr(it, 'fertilizer', None)
            if fz:
                inventory_dict[fz.id] = int(getattr(it, 'quantity', 0) or 0)
    except Exception:
        inventory_dict = {}

    # Заголовок и баланс
    lines = [f"<b>🧪 Магазин удобрений</b>"]
    lines.append(f"💰 Баланс: <b>{int(getattr(player, 'coins', 0) or 0)}</b> септимов")
    
    # Инвентарь (если есть)
    if inventory_dict:
        lines.append(f"\n📦 <b>В инвентаре:</b>")
        inv_items = []
        for fert in fertilizers:
            qty = inventory_dict.get(fert.id, 0)
            if qty > 0:
                inv_items.append(f"{getattr(fert, 'name', 'Удобрение')}: {qty} шт.")
        if inv_items:
            lines.append(", ".join(inv_items[:5]))  # Показываем до 5 позиций
            if len(inv_items) > 5:
                lines.append(f"... и ещё {len(inv_items) - 5}")
    
    # Фильтры по категориям
    filter_buttons = []
    categories = ['all', 'growth', 'yield', 'quality', 'complex', 'resilience']
    for cat in categories:
        emoji = get_category_emoji(cat) if cat != 'all' else '🌐'
        cat_name = get_category_name(cat)
        # Отметим выбранную категорию
        if cat == filter_category:
            filter_buttons.append(InlineKeyboardButton(f"✅ {cat_name}", callback_data=f'fert_filter_{cat}'))
        else:
            filter_buttons.append(InlineKeyboardButton(f"{emoji} {cat_name}", callback_data=f'fert_filter_{cat}'))
    
    keyboard = []
    # Добавляем фильтры по 2 кнопки в ряд
    keyboard.append(filter_buttons[:3])
    keyboard.append(filter_buttons[3:])
    
    # Фильтруем удобрения по категории
    filtered_fertilizers = []
    if filter_category == 'all':
        filtered_fertilizers = fertilizers
    else:
        for fz in fertilizers:
            if get_fertilizer_category(fz) == filter_category:
                filtered_fertilizers.append(fz)
    
    # Группируем по категориям для красивого отображения
    if filtered_fertilizers:
        lines.append(f"\n<b>📋 Доступно удобрений ({len(filtered_fertilizers)}):</b>")
        
        # Группируем по категориям, если показываем все
        if filter_category == 'all':
            categories_group = {}
            for fz in filtered_fertilizers:
                cat = get_fertilizer_category(fz)
                if cat not in categories_group:
                    categories_group[cat] = []
                categories_group[cat].append(fz)
            
            # Показываем по категориям
            for cat in ['growth', 'yield', 'quality', 'complex', 'resilience', 'other']:
                if cat in categories_group:
                    cat_emoji = get_category_emoji(cat)
                    cat_name = get_category_name(cat)
                    lines.append(f"\n{cat_emoji} <b>{cat_name}:</b>")
                    for fz in categories_group[cat]:
                        name = html.escape(getattr(fz, 'name', 'Удобрение'))
                        desc = html.escape(getattr(fz, 'description', '') or '')
                        price = int(getattr(fz, 'price_coins', 0) or 0)
                        dur_m = int((int(getattr(fz, 'duration_sec', 0) or 0)) / 60)
                        in_inv = inventory_dict.get(fz.id, 0)
                        inv_text = f" | 📦 <i>{in_inv} шт.</i>" if in_inv > 0 else ""
                        lines.append(f"  • <b>{name}</b> — {price}💰{inv_text}")
                        lines.append(f"    <i>{desc}</i> | ⏱ {dur_m} мин")
                        # Кнопки покупки
                        keyboard.append([
                            InlineKeyboardButton("1 шт.", callback_data=f'fert_buy_{fz.id}_1'),
                            InlineKeyboardButton("5 шт.", callback_data=f'fert_buy_{fz.id}_5'),
                            InlineKeyboardButton("10 шт.", callback_data=f'fert_buy_{fz.id}_10'),
                            InlineKeyboardButton("✏️", callback_data=f'fert_buy_custom_{fz.id}'),
                        ])
        else:
            # Показываем только выбранную категорию
            for fz in filtered_fertilizers:
                name = html.escape(getattr(fz, 'name', 'Удобрение'))
                desc = html.escape(getattr(fz, 'description', '') or '')
                price = int(getattr(fz, 'price_coins', 0) or 0)
                dur_m = int((int(getattr(fz, 'duration_sec', 0) or 0)) / 60)
                in_inv = inventory_dict.get(fz.id, 0)
                inv_text = f" | 📦 <i>{in_inv} шт.</i>" if in_inv > 0 else ""
                lines.append(f"\n• <b>{name}</b> — {price}💰{inv_text}")
                lines.append(f"  <i>{desc}</i> | ⏱ {dur_m} мин")
                # Кнопки покупки
                keyboard.append([
                    InlineKeyboardButton("1 шт.", callback_data=f'fert_buy_{fz.id}_1'),
                    InlineKeyboardButton("5 шт.", callback_data=f'fert_buy_{fz.id}_5'),
                    InlineKeyboardButton("10 шт.", callback_data=f'fert_buy_{fz.id}_10'),
                    InlineKeyboardButton("✏️", callback_data=f'fert_buy_custom_{fz.id}'),
                ])
    else:
        lines.append("\n⚠️ Нет удобрений в выбранной категории.")
    
    # Кнопки возврата: если пришли из грядок, даём прямой возврат к ним
    if context.user_data.get('last_plantation_screen') == 'beds':
        keyboard.append([
            InlineKeyboardButton("🔙 Назад в грядки", callback_data='plantation_my_beds'),
            InlineKeyboardButton("🔙 Назад в меню", callback_data='market_plantation')
        ])
    else:
        keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data='market_plantation')])
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

        if context.user_data.get('last_plantation_screen') == 'beds':
            await show_plantation_my_beds(update, context)
        else:
            await show_plantation_fertilizers_shop(update, context)

async def start_fertilizer_custom_buy_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper для извлечения fertilizer_id из callback_data."""
    query = update.callback_query
    try:
        # Извлекаем ID из fert_buy_custom_{fert_id}
        fertilizer_id = int(query.data.split('_')[-1])
        return await start_fertilizer_custom_buy(update, context, fertilizer_id)
    except Exception:
        await query.answer("Ошибка. Попробуйте позже.", show_alert=True)
        return ConversationHandler.END

async def start_fertilizer_custom_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, fertilizer_id: int):
    """Начинает процесс покупки кастомного количества удобрений."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    # Сохраняем ID удобрения в контексте
    context.user_data['fert_custom_buy_id'] = fertilizer_id
    
    # Получаем информацию об удобрении
    try:
        fertilizers = db.list_fertilizers() or []
        fert = None
        for f in fertilizers:
            if f.id == fertilizer_id:
                fert = f
                break
        
        if not fert:
            await query.answer("Удобрение не найдено", show_alert=True)
            return ConversationHandler.END
        
        name = html.escape(getattr(fert, 'name', 'Удобрение'))
        price = int(getattr(fert, 'price_coins', 0) or 0)
        
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        balance = int(getattr(player, 'coins', 0) or 0)
        max_qty = balance // price if price > 0 else 0
        
        text = f"<b>✏️ Покупка удобрения</b>\n\n"
        text += f"<b>{name}</b>\n"
        text += f"💰 Цена: {price} септимов за 1 шт.\n"
        text += f"💰 Ваш баланс: {balance} септимов\n"
        text += f"📦 Максимум: {max_qty} шт.\n\n"
        text += f"<i>Введите количество для покупки (1-{max_qty}):</i>"
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='fert_custom_cancel')]]
        
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
        return FERTILIZER_CUSTOM_QTY
    except Exception:
        await query.answer("Ошибка. Попробуйте позже.", show_alert=True)
        return ConversationHandler.END

async def handle_fertilizer_custom_qty_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод кастомного количества удобрений."""
    msg = update.message
    user = update.effective_user
    
    if not msg or not msg.text:
        await msg.reply_text("Пожалуйста, введите число.")
        return FERTILIZER_CUSTOM_QTY
    
    fertilizer_id = context.user_data.get('fert_custom_buy_id')
    if not fertilizer_id:
        await msg.reply_text("Ошибка: удобрение не выбрано.")
        return ConversationHandler.END
    
    try:
        quantity = int(msg.text.strip())
    except ValueError:
        await msg.reply_text("❌ Неверный формат. Пожалуйста, введите целое число.")
        return FERTILIZER_CUSTOM_QTY
    
    if quantity <= 0:
        await msg.reply_text("❌ Количество должно быть больше 0.")
        return FERTILIZER_CUSTOM_QTY
    
    # Проверяем максимум
    try:
        fertilizers = db.list_fertilizers() or []
        fert = None
        for f in fertilizers:
            if f.id == fertilizer_id:
                fert = f
                break
        
        if not fert:
            await msg.reply_text("❌ Удобрение не найдено.")
            return ConversationHandler.END
        
        price = int(getattr(fert, 'price_coins', 0) or 0)
        total_cost = price * quantity
        
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        balance = int(getattr(player, 'coins', 0) or 0)
        
        if total_cost > balance:
            await msg.reply_text(f"❌ Недостаточно монет!\nНужно: {total_cost} септимов\nУ вас: {balance} септимов")
            return FERTILIZER_CUSTOM_QTY
        
        if quantity > 1000:
            await msg.reply_text("❌ Слишком много! Максимум 1000 шт. за раз.")
            return FERTILIZER_CUSTOM_QTY
        
    except Exception:
        await msg.reply_text("❌ Ошибка при проверке. Попробуйте позже.")
        return ConversationHandler.END
    
    # Выполняем покупку
    lock = _get_lock(f"user:{user.id}:fert_buy")
    if lock.locked():
        await msg.reply_text("⏳ Обработка предыдущей покупки...")
        return FERTILIZER_CUSTOM_QTY
    
    async with lock:
        res = db.purchase_fertilizer(user.id, int(fertilizer_id), int(quantity))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_enough_coins':
                await msg.reply_text('❌ Недостаточно монет')
            elif reason == 'no_such_fertilizer':
                await msg.reply_text('❌ Удобрение не найдено')
            elif reason == 'invalid_quantity':
                await msg.reply_text('❌ Неверное количество')
            else:
                await msg.reply_text('❌ Ошибка. Попробуйте позже.')
        else:
            name = html.escape(getattr(fert, 'name', 'Удобрение'))
            await msg.reply_html(f"✅ <b>Куплено!</b>\n\n{name} x {quantity}\n💰 Баланс: {res.get('coins_left')} септимов")
            
        # Предлагаем вернуться в нужный раздел после покупки
        if context.user_data.get('last_plantation_screen') == 'beds':
            keyboard = [[InlineKeyboardButton("🌾 Мои грядки", callback_data='plantation_my_beds')]]
            await msg.reply_text("Куда вернуться?", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("🧪 Вернуться в магазин", callback_data='plantation_fertilizers_shop')]]
            await msg.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ConversationHandler.END

async def cancel_fertilizer_custom_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет покупку кастомного количества."""
    query = update.callback_query
    if query:
        await query.answer()
        if context.user_data.get('last_plantation_screen') == 'beds':
            await show_plantation_my_beds(update, context)
        else:
            await show_plantation_fertilizers_shop(update, context)
    return ConversationHandler.END

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
        max_fert = max(1, db.get_setting_int('plantation_fertilizer_max_per_bed', PLANTATION_FERTILIZER_MAX_PER_BED))
        res = db.apply_fertilizer(user.id, int(bed_index), int(fertilizer_id))
        if not res.get('ok'):
            reason = res.get('reason')
            if reason == 'not_growing':
                await query.answer('Грядка не в состоянии роста', show_alert=True)
            elif reason == 'not_watered':
                await query.answer('Сначала полейте растение!', show_alert=True)
            elif reason == 'no_fertilizer_in_inventory':
                await query.answer('Нет такого удобрения в инвентаре', show_alert=True)
            elif reason == 'max_fertilizers_reached':
                await query.answer(f'Достигнут лимит удобрений (макс. {max_fert} + 1 защитный слот)', show_alert=True)
            elif reason == 'resilience_slot_occupied':
                await query.answer('Защитный слот уже занят. На грядку доступен только 1 защитный эффект.', show_alert=True)
            else:
                await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        else:
            await query.answer('Удобрение применено! Бонусы суммируются.', show_alert=False)
        await show_plantation_my_beds(update, context)

async def show_fertilizer_pick_for_bed(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    """Выбор удобрения из инвентаря для конкретной грядки."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    max_fert = max(1, db.get_setting_int('plantation_fertilizer_max_per_bed', PLANTATION_FERTILIZER_MAX_PER_BED))
    inv = db.get_fertilizer_inventory(user.id) or []
    beds = db.get_player_beds(user.id) or []
    bed = None
    for b in beds:
        try:
            if int(getattr(b, 'bed_index', 0) or 0) == int(bed_index):
                bed = b
                break
        except Exception:
            continue

    lines = [f"<b>🧪 Выберите удобрение для грядки {bed_index}</b>"]
    if bed is not None:
        try:
            fs = db.get_fertilizer_status(bed)
            info_list = list(fs.get('fertilizers_info', []) or [])
            used = len(info_list)
            total_count = _count_bed_total_fertilizers(bed)
            protection_used = _count_bed_resilience_fertilizers(bed)
            main_used = max(0, total_count - protection_used)
            total_limit = max_fert + 1
            lines.append(f"\n🧪 Сейчас активно: {used} | основные: {main_used}/{max_fert} | 🛡️ защита: {protection_used}/1 | всего {total_count}/{total_limit}")
            if total_count >= total_limit:
                lines.append("⚠️ Лимит удобрений исчерпан до сбора")
            for fi in info_list:
                fn = html.escape(str(fi.get('name') or 'Удобрение'))
                tl = int(fi.get('time_left') or 0)
                lines.append(f"• {fn} — {_fmt_time(tl)}")
        except Exception:
            pass
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
            idx = res.get('new_bed_index')
            await query.answer(f"Грядка куплена! #{idx}. Баланс: {res.get('coins_left')}", show_alert=False)
        await show_plantation_my_beds(update, context)

# Placeholder handlers for buttons
async def show_plantation_join_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)

async def show_plantation_my_contribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)

async def show_plantation_water_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Нечего поливать", show_alert=True)

async def show_plantation_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚧 Функция в разработке", show_alert=True)


def _count_bed_total_fertilizers(bed) -> int:
    total = 0
    try:
        if hasattr(bed, 'active_fertilizers') and bed.active_fertilizers:
            for bf in bed.active_fertilizers:
                if getattr(bf, 'fertilizer', None):
                    total += 1
    except Exception:
        total = 0
    if total == 0:
        try:
            if getattr(bed, 'fertilizer_id', None):
                total = 1
        except Exception:
            pass
    return int(total)


def _count_bed_resilience_fertilizers(bed) -> int:
    total = 0
    try:
        if hasattr(bed, 'active_fertilizers') and bed.active_fertilizers:
            for bf in bed.active_fertilizers:
                fert = getattr(bf, 'fertilizer', None)
                if fert and get_fertilizer_category(fert) == 'resilience':
                    total += 1
    except Exception:
        total = 0
    if total == 0:
        try:
            legacy_fert = getattr(bed, 'fertilizer', None)
            if legacy_fert and getattr(bed, 'fertilizer_id', None) and get_fertilizer_category(legacy_fert) == 'resilience':
                total = 1
        except Exception:
            pass
    return int(total)


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
            # --- FIX: Immediate free watering for everyone ---
            try:
                # Сразу поливаем бесплатно (как будто только что посадили во влажную почву)
                water_res = db.water_bed(user.id, bed_index)
                if water_res.get('ok'):
                    await query.answer('Посажено и полито!', show_alert=False)
                    
                    # Если полили, нужно перепланировать напоминание, так как таймер сбросился
                    # Новое время полива = water_interval
                    player = db.get_or_create_player(user.id, user.username or user.first_name)
                    if getattr(player, 'remind_plantation', False) and context.application and context.application.job_queue:
                        water_interval = int(water_res.get('water_interval_sec', 1800))
                        # Удаляем только что созданное напоминание (которое было на water_interval от посадки)
                        current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user.id}_{bed_index}")
                        for job in current_jobs:
                            job.schedule_removal()
                        
                        context.application.job_queue.run_once(
                            plantation_water_reminder_job,
                            when=water_interval,
                            chat_id=user.id,
                            data={'bed_index': bed_index},
                            name=f"plantation_water_reminder_{user.id}_{bed_index}",
                        )
                else:
                    # Если не удалось полить (странно), просто пишем "Посажено"
                    await query.answer('Посажено!', show_alert=False)
            except Exception as ex:
                logger.warning(f"Ошибка при мгновенном поливе: {ex}")
                await query.answer('Посажено!', show_alert=False)

            # --- OLD FARMER LOGIC (Disabled) ---
            # try:
            #     # Сразу после посадки last_watered_at=0, так что фермер должен полить
            #     auto_res = db.try_farmer_autowater(user.id, bed_index)
            #     if auto_res.get('ok'):
            #         cost = auto_res.get('cost', 50)
            #         try:
            #             await context.bot.send_message(
            #                 chat_id=user.id,
            #                 text=f"👨‍🌾 <b>Селюк фермер сразу полил новую посадку!</b> (−{cost} септимов)",
            #                 parse_mode='HTML'
            #             )
            #             # Если полил, нужно перепланировать напоминание, так как таймер сбросился
            #             # Новое время полива = water_interval
            #             if getattr(player, 'remind_plantation', False) and context.application and context.application.job_queue:
            #                 water_interval = int(auto_res.get('water_interval_sec', 1800))
            #                 # Удаляем только что созданное напоминание (которое было на water_interval от посадки)
            #                 # В принципе, оно было на то же время, но лучше обновить для точности
            #                 current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user.id}_{bed_index}")
            #                 for job in current_jobs:
            #                     job.schedule_removal()
            #                 
            #                 context.application.job_queue.run_once(
            #                     plantation_water_reminder_job,
            #                     when=water_interval,
            #                     chat_id=user.id,
            #                     data={'bed_index': bed_index},
            #                     name=f"plantation_water_reminder_{user.id}_{bed_index}",
            #                 )
            #         except Exception:
            #             pass
            #     else:
            #         # Если не удалось полить, сообщаем причину (если фермер есть)
            #         reason = auto_res.get('reason')
            #         if reason == 'remind_disabled':
            #             await context.bot.send_message(
            #                 chat_id=user.id,
            #                 text="👨‍🌾 Селюк фермер не смог полить: <b>включите напоминания о поливе</b> в настройках!",
            #                 parse_mode='HTML'
            #             )
            #         elif reason == 'no_funds':
            #             await context.bot.send_message(
            #                 chat_id=user.id,
            #                 text="👨‍🌾 Селюк фермер не смог полить: <b>недостаточно средств</b> на балансе селюка!",
            #                 parse_mode='HTML'
            #             )
            #         elif reason == 'selyuk_disabled':
            #             await context.bot.send_message(
            #                 chat_id=user.id,
            #                 text="👨‍🌾 Селюк фермер не смог полить: <b>фермер выключен</b>!",
            #                 parse_mode='HTML'
            #             )
            # except Exception as ex:
            #     logger.warning(f"Ошибка при мгновенном поливе фермером: {ex}")

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

            try:
                db.try_farmer_auto_fertilize(user.id)
            except Exception:
                pass
            
            # Планируем напоминание о следующем поливе, если включено
            player = db.get_or_create_player(user.id, user.username or user.first_name)
            if getattr(player, 'remind_plantation', False) and context.application and context.application.job_queue:
                water_interval = int(res.get('water_interval_sec', 0))
                if water_interval > 0:
                    try:
                        # Удаляем старые напоминания для этой грядки
                        current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user.id}_{bed_index}")
                        for job in current_jobs:
                            job.schedule_removal()
                        
                        # Планируем новое напоминание
                        context.application.job_queue.run_once(
                            plantation_water_reminder_job,
                            when=water_interval,
                            chat_id=user.id,
                            data={'bed_index': bed_index},
                            name=f"plantation_water_reminder_{user.id}_{bed_index}",
                        )
                    except Exception as ex:
                        logger.warning(f"Не удалось запланировать напоминание о поливе: {ex}")
        await show_plantation_my_beds(update, context)


async def handle_plantation_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE, bed_index: int):
    query = update.callback_query
    user = query.from_user
    try:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        lang = getattr(player, 'language', 'ru') or 'ru'
    except Exception:
        lang = 'ru'
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
            rating_added = int(res.get('rating_added') or 0)
            new_rating = res.get('new_rating')

            # Удаляем напоминание о поливе для этой грядки
            if context.application and context.application.job_queue:
                try:
                    current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user.id}_{bed_index}")
                    for job in current_jobs:
                        job.schedule_removal()
                except Exception as ex:
                    logger.warning(f"Не удалось удалить напоминание о поливе при сборе урожая: {ex}")

            # Короткое подтверждение
            if lang == 'en':
                short = f"Collected: {items_added}"
                if rating_added > 0:
                    short += f" | ⭐ +{rating_added}"
                    if new_rating is not None:
                        short += f" (Rating: {int(new_rating)})"
            else:
                short = f"Собрано: {items_added}"
                if rating_added > 0:
                    short += f" | ⭐ +{rating_added}"
                    if new_rating is not None:
                        short += f" (Рейтинг: {int(new_rating)})"
            await query.answer(short, show_alert=False)

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
            if rating_added > 0:
                if lang == 'en':
                    rr = f"⭐ Rating: <b>+{rating_added}</b>"
                    if new_rating is not None:
                        rr += f" (now <b>{int(new_rating)}</b>)"
                else:
                    rr = f"⭐ Рейтинг: <b>+{rating_added}</b>"
                    if new_rating is not None:
                        rr += f" (теперь <b>{int(new_rating)}</b>)"
                lines.append(rr)
            for r in RARITY_ORDER:
                cnt = int((rarity_counts.get(r) or 0))
                if cnt > 0:
                    emoji = COLOR_EMOJIS.get(r, '')
                    lines.append(f"{emoji} {r}: <b>{cnt}</b>")

            # Эффекты (полив, удобрение, негативные статусы, множитель)
            eff = res.get('effects') or {}
            wc = int(eff.get('water_count') or 0)
            fert_active = bool(eff.get('fertilizer_active'))
            fert_names = eff.get('fertilizer_names') or []
            status_raw = (eff.get('status_effect') or '').lower()
            status_lvl = int(eff.get('status_effect_level') or 1)
            yield_mult = float(eff.get('yield_multiplier') or 1.0)
            status_map = {'weeds': 'сорняки', 'pests': 'вредители', 'drought': 'засуха'}
            status_h = status_map.get(status_raw, '—' if not status_raw else status_raw)
            lines.append("")
            lines.append("<i>Эффекты</i>:")
            lines.append(f"• Поливов: {wc}")
            if fert_active and fert_names:
                if len(fert_names) == 1:
                    lines.append(f"• Удобрение: {html.escape(fert_names[0])}")
                else:
                    lines.append(f"• Удобрений активно: {len(fert_names)}")
                    for fname in fert_names:
                        lines.append(f"  - {html.escape(fname)}")
            else:
                lines.append("• Удобрение: нет")
            if status_raw:
                lines.append(f"• Негативный статус: {status_h} (ур.{status_lvl})")
            else:
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
        try:
            player = db.get_or_create_player(user.id, user.username or user.first_name)
            lang = getattr(player, 'language', 'ru') or 'ru'
        except Exception:
            lang = 'ru'
        ready = [b for b in beds if str(getattr(b, 'state', '')) == 'ready']
        if not ready:
            await query.answer('Пока нет готового урожая', show_alert=True)
            return

        total_items = 0
        total_amount = 0
        total_rating_added = 0
        agg_rarity: dict[str, int] = {}
        per_drink: dict[int, dict] = {}

        for b in ready:
            idx = int(getattr(b, 'bed_index', 0) or 0)
            res = db.harvest_bed(user.id, idx)
            if not res.get('ok'):
                continue
            
            # Удаляем напоминание о поливе для этой грядки
            if context.application and context.application.job_queue:
                try:
                    current_jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user.id}_{idx}")
                    for job in current_jobs:
                        job.schedule_removal()
                except Exception as ex:
                    logger.warning(f"Не удалось удалить напоминание о поливе при массовом сборе: {ex}")

            amount = int(res.get('yield') or 0)
            items_added = int(res.get('items_added') or 0)
            drink_id = int(res.get('drink_id') or 0)
            rarity_counts = res.get('rarity_counts') or {}
            eff = res.get('effects') or {}
            try:
                total_rating_added += int(res.get('rating_added') or 0)
            except Exception:
                pass

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
            fert_names = eff.get('fertilizer_names') or []
            status_raw = (eff.get('status_effect') or '').lower()
            status_lvl = int(eff.get('status_effect_level') or 1)
            yield_mult = float(eff.get('yield_multiplier') or 1.0)
            status_map = {'weeds': 'сорняки', 'pests': 'вредители', 'drought': 'засуха'}
            status_h = status_map.get(status_raw, '—' if not status_raw else status_raw)
            lines.append("")
            lines.append("<i>Эффекты</i>:")
            lines.append(f"• Поливов: {wc}")
            if fert_active and fert_names:
                if len(fert_names) == 1:
                    lines.append(f"• Удобрение: {html.escape(fert_names[0])}")
                else:
                    lines.append(f"• Удобрений активно: {len(fert_names)}")
                    for fname in fert_names:
                        lines.append(f"  - {html.escape(fname)}")
            else:
                lines.append("• Удобрение: нет")
            if status_raw:
                lines.append(f"• Негативный статус: {status_h} (ур.{status_lvl})")
            else:
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
                except  Exception:
                    pass

        # Короткое сводное уведомление
        await query.answer(f"Собрано: {total_items}", show_alert=False)

        # Сводный отчёт
        lines = [
            "<b>🥕 Сбор завершён</b>",
            f"Итого собрано: <b>{total_items}</b>" + (f" из {total_amount}" if total_items != total_amount else ""),
        ]
        if total_rating_added > 0:
            if lang == 'en':
                lines.append(f"⭐ Rating gained: <b>+{int(total_rating_added)}</b>")
            else:
                lines.append(f"⭐ Получено рейтинга: <b>+{int(total_rating_added)}</b>")
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
    lang = getattr(player, 'language', 'ru') or 'ru'

    text = (
        "<b>🏙️ КАРТА ГОРОДОВ 🏙️</b>\n\n"
        "🌍 <i>Откройте для себя четыре уникальных города, каждый со своими возможностями!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏰 <b>ХАЙТАУН</b>\n"
        "   <i>Торговый центр мира</i>\n"
        "   ┣ 🏬 Магазин редкостей\n"
        "   ┣ ♻️ Приёмник ресурсов\n"
        "   ┣ 🌱 Плантация грибов\n"
        "   ┗ 🎰 Роскошное казино\n\n"
        "🧵 <b>ГОРОД ШЁЛКА</b>\n"
        "   <i>Империя шёлковых мануфактур</i>\n"
        "   ┣ 🌳 Шёлковые плантации\n"
        "   ┣ 📊 Динамичный рынок\n"
        "   ┗ 💼 Торговля тканями\n\n"
        "🌆 <b>РОСТОВ</b>\n"
        "   <i>Город будущего и элиты</i>\n"
        "   ┣ 💎 Магазин для избранных\n"
        "   ┗ 💱 Валютный обменник\n\n"
        "⚡ <b>ЛИНИИ ЭЛЕКТРОПЕРЕДАЧ</b>\n"
        "   <i>Промышленные пустоши и странные феномены</i>\n"
        "   ┣ 🌀 Сематори\n"
        "   ┣ 🔥 Красные ядра земли\n"
        "   ┣ 🧪 Поле стекловаты\n"
        "   ┗ 🍊 Хурма?\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Ваш баланс:</b> {coins:,} 💎\n"
        "<i>Выберите город для посещения:</i>"
    ).format(coins=player.coins)
    
    keyboard = [
        [InlineKeyboardButton("🏰 Город ХайТаун", callback_data='city_hightown')],
        [InlineKeyboardButton("🧵 Город Шёлка", callback_data='city_silk')],
        [InlineKeyboardButton("🌆 Город Ростов", callback_data='city_rostov')],
        [InlineKeyboardButton("⚡ Линии Электропередач", callback_data='city_powerlines')],
        [InlineKeyboardButton("🔙 В главное меню", callback_data='menu')],
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
    lang = getattr(player, 'language', 'ru') or 'ru'

    text = (
        "🏰 <b>ДОБРО ПОЖАЛОВАТЬ В ХАЙТАУН</b> 🏰\n\n"
        "🌟 <i>Старейший торговый город, где процветает коммерция и азарт!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📍 <b>ДОСТУПНЫЕ ЛОКАЦИИ:</b>\n\n"
        "🏬 <b>Магазин</b>\n"
        "   └ <i>Приобретайте редкие предметы и улучшения</i>\n\n"
        "♻️ <b>Приёмник</b>\n"
        "   └ <i>Сдавайте ресурсы за септимы</i>\n\n"
        "🌱 <b>Плантация</b>\n"
        "   └ <i>Выращивайте грибы и зарабатывайте</i>\n\n"
        "🎰 <b>Казино</b>\n"
        "   └ <i>Испытайте удачу и выиграйте джекпот!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Ваш баланс:</b> {coins:,} 💎\n"
        "<i>Куда направиться?</i>"
    ).format(coins=player.coins)
    
    keyboard = [
        [InlineKeyboardButton("🏬 Магазин", callback_data='market_shop')],
        [InlineKeyboardButton("♻️ Приёмник", callback_data='market_receiver')],
        [InlineKeyboardButton("🌱 Плантация", callback_data='market_plantation')],
        [InlineKeyboardButton("🎰 Казино", callback_data='city_casino')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🏠 В главное меню", callback_data='menu')],
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


async def show_city_rostov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Город Ростов: город с разделами (заглушки)."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = (
        "🌆 <b>ДОБРО ПОЖАЛОВАТЬ В РОСТОВ</b> 🌆\n\n"
        "✨ <i>Футуристический город элиты, где роскошь встречается с инновациями!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📍 <b>ЭКСКЛЮЗИВНЫЕ ЛОКАЦИИ:</b>\n\n"
        "💎 <b>Магазин Элиты</b>\n"
        "   └ <i>Уникальные товары премиум-класса</i>\n"
        "   └ 🚧 <b>В разработке...</b>\n\n"
        "🧬 <b>Хаб</b>\n"
        "   └ <i>Центр работы с селюками</i>\n\n"
        "💱 <b>Обменник</b>\n"
        "   └ <i>Обмен валют и ресурсов по лучшим курсам</i>\n"
        "   └ 🚧 <b>В разработке...</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Ваш баланс:</b> {coins:,} 💎\n"
        "⏳ <i>Город скоро откроет свои двери для вас!</i>"
    ).format(coins=player.coins)
    
    keyboard = [
        [InlineKeyboardButton("💎 Магазин элиты 🚧", callback_data='rostov_elite_shop')],
        [InlineKeyboardButton("🧬 Хаб", callback_data='rostov_hub')],
        [InlineKeyboardButton("💱 Обменник 🚧", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🏠 В главное меню", callback_data='menu')],
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


async def show_city_powerlines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = (
        "⚡ <b>ДОБРО ПОЖАЛОВАТЬ В ЛИНИИ ЭЛЕКТРОПЕРЕДАЧ</b> ⚡\n\n"
        "🌪️ <i>Промышленные пустоши и странные феномены</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📍 <b>ДОСТУПНЫЕ ЛОКАЦИИ:</b>\n\n"
        "🌀 <b>Сематори</b>\n"
        "   └ <i>Таинственные вихри и аномалии</i>\n\n"
        "🔥 <b>Красные ядра земли</b>\n"
        "   └ <i>Живое тепло под ногами</i>\n\n"
        "🧪 <b>Поле стекловаты</b>\n"
        "   └ <i>Хрупкая тишина и резкие грани</i>\n\n"
        "🍊 <b>Хурма?</b>\n"
        "   └ <i>Неожиданные плоды среди линий</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Ваш баланс:</b> {coins:,} 💎\n"
        "<i>Куда направиться?</i>"
    ).format(coins=player.coins)

    keyboard = [
        [InlineKeyboardButton("🌀 Сематори", callback_data='power_sematori')],
        [InlineKeyboardButton("🔥 Красные ядра земли", callback_data='power_red_cores')],
        [InlineKeyboardButton("🧪 Поле стекловаты", callback_data='power_glasswool_field')],
        [InlineKeyboardButton("🍊 Хурма?", callback_data='power_persimmon')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🏠 В главное меню", callback_data='menu')],
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


async def show_power_sematori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🌀 <b>СЕМАТОРИ</b> 🌀\n\n"
        "🌪️ <i>Место, где ветер шепчет формулы</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появятся события и активити.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Линии Электропередач", callback_data='city_powerlines')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


ROSTOV_ELITE_ITEM_PRICES = {
    'search_skip': 2500,
    'bonus_skip': 4000,
    'auto_boost_10_24h': 20000,
    'fragments_pack_3': 6000,
    'luck_coupon_3': 15000,
}


async def show_rostov_elite_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)

    coins = int(getattr(player, 'coins', 0) or 0)
    luck = int(getattr(player, 'luck_coupon_charges', 0) or 0)
    fragments = int(getattr(player, 'selyuk_fragments', 0) or 0)

    try:
        boost_info = db.get_boost_info(user.id)
    except Exception:
        boost_info = {}

    boost_active = bool(boost_info.get('is_active'))
    boost_count = int(boost_info.get('boost_count', 0) or 0)
    boost_remaining = boost_info.get('time_remaining_formatted', '—')

    text_lines = [
        "💠 <b>ЭЛИТНЫЕ ПРЕДМЕТЫ</b> 💠",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 <b>Баланс:</b> {coins:,} 💎",
        f"🧩 <b>Фрагменты Селюка:</b> {fragments}",
        f"🎲 <b>Купон удачи:</b> {luck} заряд(ов)",
        f"🚀 <b>Автопоиск-буст:</b> {'активен' if boost_active else '—'} (+{boost_count}, осталось {boost_remaining})" if boost_active else "🚀 <b>Автопоиск-буст:</b> —",
        "",
        "<b>Товары:</b>",
        "",
        f"⏱ Пропуск кулдауна поиска — <b>{ROSTOV_ELITE_ITEM_PRICES['search_skip']:,}</b> 💎",
        f"🎁 Пропуск кулдауна бонуса — <b>{ROSTOV_ELITE_ITEM_PRICES['bonus_skip']:,}</b> 💎",
        f"🚀 Автопоиск-буст +10 на 24ч — <b>{ROSTOV_ELITE_ITEM_PRICES['auto_boost_10_24h']:,}</b> 💎",
        f"🧩 Фрагменты Селюка +3 — <b>{ROSTOV_ELITE_ITEM_PRICES['fragments_pack_3']:,}</b> 💎",
        f"🎲 Купон удачи (+3 заряда, 50% на 2 дропа) — <b>{ROSTOV_ELITE_ITEM_PRICES['luck_coupon_3']:,}</b> 💎",
    ]

    text = "\n".join(text_lines)

    keyboard = [
        [InlineKeyboardButton(f"Купить ⏱ ({ROSTOV_ELITE_ITEM_PRICES['search_skip']})", callback_data='rostov_elite_buy_search_skip')],
        [InlineKeyboardButton(f"Купить 🎁 ({ROSTOV_ELITE_ITEM_PRICES['bonus_skip']})", callback_data='rostov_elite_buy_bonus_skip')],
        [InlineKeyboardButton(f"Купить 🚀 (+10/24ч) ({ROSTOV_ELITE_ITEM_PRICES['auto_boost_10_24h']})", callback_data='rostov_elite_buy_auto_boost_10_24h')],
        [InlineKeyboardButton(f"Купить 🧩 (+3) ({ROSTOV_ELITE_ITEM_PRICES['fragments_pack_3']})", callback_data='rostov_elite_buy_fragments_pack_3')],
        [InlineKeyboardButton(f"Купить 🎲 (+3) ({ROSTOV_ELITE_ITEM_PRICES['luck_coupon_3']})", callback_data='rostov_elite_buy_luck_coupon_3')],
        [InlineKeyboardButton("🔙 Назад", callback_data='rostov_elite_shop')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
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


async def handle_rostov_elite_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, item_key: str):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lock = _get_lock(f"user:{user.id}:rostov_elite_buy")
    if lock.locked():
        await query.answer("Подождите…", show_alert=True)
        return
    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, 'coins', 0) or 0)

        price = int(ROSTOV_ELITE_ITEM_PRICES.get(item_key, 0) or 0)
        if price <= 0:
            await query.answer("Товар не найден.", show_alert=True)
            return

        if coins < price:
            await query.answer(f"Недостаточно монет: {coins}/{price}", show_alert=True)
            return

        # Списываем монеты
        try:
            db.update_player(user.id, coins=coins - price)
        except Exception:
            await query.answer("Ошибка покупки.", show_alert=True)
            return

        now_ts = int(time.time())

        if item_key == 'search_skip':
            db.update_player(user.id, last_search=0)
            await query.answer("✅ Кулдаун поиска сброшен!", show_alert=True)
        elif item_key == 'bonus_skip':
            db.update_player(user.id, last_bonus_claim=0)
            await query.answer("✅ Кулдаун бонуса сброшен!", show_alert=True)
        elif item_key == 'auto_boost_10_24h':
            try:
                ok = db.add_auto_search_boost(user.id, boost_count=10, days=1)
            except Exception:
                ok = False
            if ok:
                await query.answer("✅ Автопоиск-буст добавлен (+10 на 24ч)", show_alert=True)
            else:
                await query.answer("⚠️ Не удалось применить буст.", show_alert=True)
        elif item_key == 'fragments_pack_3':
            try:
                db.increment_selyuk_fragments(user.id, 3)
            except Exception:
                pass
            await query.answer("✅ Вы получили +3 фрагмента!", show_alert=True)
        elif item_key == 'luck_coupon_3':
            current = int(getattr(player, 'luck_coupon_charges', 0) or 0)
            db.update_player(user.id, luck_coupon_charges=current + 3)
            await query.answer("✅ Купон удачи пополнен (+3 заряда)", show_alert=True)
        else:
            await query.answer("Товар не найден.", show_alert=True)

        # Лёгкий аудит в action_logs
        try:
            db.log_action(
                user_id=user.id,
                username=getattr(player, 'username', None) or (user.username or user.first_name),
                action_type='purchase',
                action_details=f"rostov_elite_item:{item_key}",
                amount=-price,
                success=True
            )
        except Exception:
            pass

    await show_rostov_elite_items(update, context)


async def show_selyuk_farmer_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)

    auto_w = bool(getattr(player, 'farmer_auto_water', True))
    auto_h = bool(getattr(player, 'farmer_auto_harvest', True))
    auto_p = bool(getattr(player, 'farmer_auto_plant', True))
    auto_f = bool(getattr(player, 'farmer_auto_fertilize', True))
    silent = bool(getattr(player, 'farmer_silent', False))
    summ_on = bool(getattr(player, 'farmer_summary_enabled', True))
    interval = int(getattr(player, 'farmer_summary_interval_sec', 3600) or 3600)
    min_bal = int(getattr(player, 'farmer_min_balance', 0) or 0)
    dlim = int(getattr(player, 'farmer_daily_limit', 0) or 0)

    mode = str(getattr(player, 'farmer_seed_mode', 'any') or 'any')
    mode_readable = {'any': 'Любые', 'whitelist': 'Только выбранные', 'blacklist': 'Кроме выбранных'}.get(mode, mode)
    try:
        seed_ids = json.loads(getattr(player, 'farmer_seed_ids', '[]') or '[]')
        seed_cnt = len(seed_ids) if isinstance(seed_ids, list) else 0
    except Exception:
        seed_cnt = 0
    try:
        prio_ids = json.loads(getattr(player, 'farmer_seed_priority', '[]') or '[]')
        prio_cnt = len(prio_ids) if isinstance(prio_ids, list) else 0
    except Exception:
        prio_cnt = 0

    try:
        fert_prio = json.loads(getattr(player, 'farmer_fert_priority', '[]') or '[]')
        fert_prio_cnt = len(fert_prio) if isinstance(fert_prio, list) else 0
    except Exception:
        fert_prio_cnt = 0

    text = (
        "⚙️ <b>Настройки Селюка Фермера</b>\n\n"
        f"💧 Автополив: {'✅' if auto_w else '🚫'}\n"
        f"🥕 Автосбор: {'✅' if auto_h else '🚫'}\n"
        f"🌱 Автопосадка: {'✅' if auto_p else '🚫'}\n"
        f"🧪 Автоудобрение: {'✅' if auto_f else '🚫'}\n\n"
        f"🤫 Тихий режим: {'✅' if silent else '🚫'}\n"
        f"🧾 Сводки: {'✅' if summ_on else '🚫'} (интервал: {int(interval/60)} мин)\n\n"
        f"🛡️ Не опускать баланс ниже: <b>{min_bal}</b> 💎\n"
        f"📆 Дневной лимит расходов: <b>{dlim}</b> 💎\n\n"
        f"🌾 Семена (ур.3): <b>{mode_readable}</b>\n"
        f"• в списке: <b>{seed_cnt}</b>\n"
        f"• приоритет: <b>{prio_cnt}</b>\n\n"
        f"🧪 Удобрения (ур.4): приоритет: <b>{fert_prio_cnt}</b>"
    )

    keyboard = [
        [InlineKeyboardButton(f"💧 Автополив {'✅' if auto_w else '🚫'}", callback_data='selyuk_farmer_set_autow')],
        [InlineKeyboardButton(f"🥕 Автосбор {'✅' if auto_h else '🚫'}", callback_data='selyuk_farmer_set_autoh')],
        [InlineKeyboardButton(f"🌱 Автопосадка {'✅' if auto_p else '🚫'}", callback_data='selyuk_farmer_set_autop')],
        [InlineKeyboardButton(f"🧪 Автоудобрение {'✅' if auto_f else '🚫'}", callback_data='selyuk_farmer_set_autof')],
        [InlineKeyboardButton(f"🤫 Тихий режим {'✅' if silent else '🚫'}", callback_data='selyuk_farmer_set_silent')],
        [InlineKeyboardButton(f"🧾 Сводки {'✅' if summ_on else '🚫'}", callback_data='selyuk_farmer_set_summary')],
        [InlineKeyboardButton("🧾 Сводки (интервал)", callback_data='selyuk_farmer_summary_interval')],
        [InlineKeyboardButton("🛡️ Минимальный остаток", callback_data='selyuk_farmer_min_balance')],
        [InlineKeyboardButton("📆 Дневной лимит", callback_data='selyuk_farmer_daily_limit')],
        [InlineKeyboardButton("🌾 Настройка семян", callback_data='selyuk_farmer_seed_settings')],
        [InlineKeyboardButton("🧪 Приоритет удобрений", callback_data='selyuk_farmer_fert_prio_0')],
        [InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_manage')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def handle_selyuk_farmer_toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, field: str):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    cur = bool(getattr(player, field, False))
    db.update_player(user.id, **{field: (not cur)})
    await show_selyuk_farmer_settings(update, context)


async def show_selyuk_farmer_min_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    cur = int(getattr(player, 'farmer_min_balance', 0) or 0)
    text = f"🛡️ <b>Минимальный остаток</b>\n\nТекущее значение: <b>{cur}</b> 💎\n\nВыбери новое значение:"
    vals = [0, 100, 500, 1000, 5000, 10000]
    keyboard = [[InlineKeyboardButton(str(v), callback_data=f'selyuk_farmer_set_minbal_{v}') for v in vals[:3]],
                [InlineKeyboardButton(str(v), callback_data=f'selyuk_farmer_set_minbal_{v}') for v in vals[3:]],
                [InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_settings')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_selyuk_farmer_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    cur = int(getattr(player, 'farmer_daily_limit', 0) or 0)
    text = f"📆 <b>Дневной лимит расходов</b>\n\nТекущее значение: <b>{cur}</b> 💎\n\nВыбери новое значение:"
    vals = [0, 500, 1000, 5000, 10000, 50000]
    keyboard = [[InlineKeyboardButton(str(v), callback_data=f'selyuk_farmer_set_dlim_{v}') for v in vals[:3]],
                [InlineKeyboardButton(str(v), callback_data=f'selyuk_farmer_set_dlim_{v}') for v in vals[3:]],
                [InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_settings')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_selyuk_farmer_summary_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    cur = int(getattr(player, 'farmer_summary_interval_sec', 3600) or 3600)
    text = f"🧾 <b>Интервал сводок</b>\n\nТекущее значение: <b>{int(cur/60)}</b> мин\n\nВыбери новое значение:"
    vals = [900, 1800, 3600, 7200]
    keyboard = [
        [InlineKeyboardButton("15м", callback_data='selyuk_farmer_set_sumint_900'), InlineKeyboardButton("30м", callback_data='selyuk_farmer_set_sumint_1800')],
        [InlineKeyboardButton("60м", callback_data='selyuk_farmer_set_sumint_3600'), InlineKeyboardButton("120м", callback_data='selyuk_farmer_set_sumint_7200')],
        [InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_settings')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_selyuk_farmer_seed_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    mode = str(getattr(player, 'farmer_seed_mode', 'any') or 'any')
    mode_readable = {'any': 'Любые', 'whitelist': 'Только выбранные', 'blacklist': 'Кроме выбранных'}.get(mode, mode)
    text = (
        "🌾 <b>Семена для автопосадки (ур.3)</b>\n\n"
        f"Режим: <b>{mode_readable}</b>\n"
        "\nНастрой: список семян и приоритет (что сажать в первую очередь)."
    )
    keyboard = [
        [InlineKeyboardButton("Режим: любые", callback_data='selyuk_farmer_seed_mode_any')],
        [InlineKeyboardButton("Режим: whitelist", callback_data='selyuk_farmer_seed_mode_whitelist')],
        [InlineKeyboardButton("Режим: blacklist", callback_data='selyuk_farmer_seed_mode_blacklist')],
        [InlineKeyboardButton("🧾 Список семян", callback_data='selyuk_farmer_seed_list_0')],
        [InlineKeyboardButton("⭐ Приоритет", callback_data='selyuk_farmer_seed_prio_0')],
        [InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_settings')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


def _farmer_seed_lists_from_player(player: Player) -> tuple[list[int], list[int]]:
    try:
        seed_ids = json.loads(getattr(player, 'farmer_seed_ids', '[]') or '[]')
        seed_ids = [int(x) for x in seed_ids] if isinstance(seed_ids, list) else []
    except Exception:
        seed_ids = []
    try:
        prio_ids = json.loads(getattr(player, 'farmer_seed_priority', '[]') or '[]')
        prio_ids = [int(x) for x in prio_ids] if isinstance(prio_ids, list) else []
    except Exception:
        prio_ids = []
    return seed_ids, prio_ids


async def show_selyuk_farmer_seed_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    seed_ids, prio_ids = _farmer_seed_lists_from_player(player)
    mode = str(getattr(player, 'farmer_seed_mode', 'any') or 'any')
    inv = db.get_seed_inventory(user.id) or []
    seeds = [(it.seed_type, int(getattr(it, 'quantity', 0) or 0)) for it in inv if getattr(it, 'seed_type', None)]
    seeds.sort(key=lambda x: x[0].id)

    per_page = 8
    page = max(0, int(page or 0))
    start = page * per_page
    chunk = seeds[start:start+per_page]
    text = f"🧾 <b>Список семян</b> (режим: {mode})\n\nНажимай на семя, чтобы добавить/убрать из списка."
    keyboard = []
    for st, qty in chunk:
        sid = int(getattr(st, 'id', 0) or 0)
        name = html.escape(getattr(st, 'name', 'Семена'))
        in_list = sid in set(seed_ids)
        mark = '✅' if in_list else '⬜️'
        keyboard.append([InlineKeyboardButton(f"{mark} {name} (x{qty})", callback_data=f'selyuk_farmer_seed_tgl_{sid}_{page}')])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f'selyuk_farmer_seed_list_{page-1}'))
    if start + per_page < len(seeds):
        nav.append(InlineKeyboardButton("➡️", callback_data=f'selyuk_farmer_seed_list_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_seed_settings')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_selyuk_farmer_seed_priority(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    seed_ids, prio_ids = _farmer_seed_lists_from_player(player)
    inv = db.get_seed_inventory(user.id) or []
    seeds = [(it.seed_type, int(getattr(it, 'quantity', 0) or 0)) for it in inv if getattr(it, 'seed_type', None)]
    seeds.sort(key=lambda x: x[0].id)

    prio_names = []
    id_to_name = {int(getattr(st, 'id', 0) or 0): html.escape(getattr(st, 'name', 'Семена')) for st, _ in seeds}
    for sid in prio_ids:
        if sid in id_to_name:
            prio_names.append(id_to_name[sid])

    text = "⭐ <b>Приоритет семян</b>\n\n"
    if prio_names:
        text += "Текущий приоритет:\n" + "\n".join([f"{i+1}. {n}" for i, n in enumerate(prio_names[:10])])
    else:
        text += "Пока пусто. Добавь семена в приоритет ниже." 

    per_page = 6
    page = max(0, int(page or 0))
    start = page * per_page
    chunk = seeds[start:start+per_page]
    keyboard = []
    for st, qty in chunk:
        sid = int(getattr(st, 'id', 0) or 0)
        name = html.escape(getattr(st, 'name', 'Семена'))
        in_prio = sid in set(prio_ids)
        if in_prio:
            keyboard.append([InlineKeyboardButton(f"🗑️ Убрать: {name}", callback_data=f'selyuk_farmer_prio_rm_{sid}_{page}')])
        else:
            keyboard.append([InlineKeyboardButton(f"➕ В приоритет: {name} (x{qty})", callback_data=f'selyuk_farmer_prio_add_{sid}_{page}')])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f'selyuk_farmer_seed_prio_{page-1}'))
    if start + per_page < len(seeds):
        nav.append(InlineKeyboardButton("➡️", callback_data=f'selyuk_farmer_seed_prio_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='selyuk_farmer_seed_settings')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_power_red_cores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🔥 <b>КРАСНЫЕ ЯДРА ЗЕМЛИ</b> 🔥\n\n"
        "🌋 <i>Пульсирующее сердце пустошей</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Следите за обновлениями — скоро здесь будет активность.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Линии Электропередач", callback_data='city_powerlines')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_power_glasswool_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🧪 <b>ПОЛЕ СТЕКЛОВАТЫ</b> 🧪\n\n"
        "🫧 <i>Хрупкая тишина и острые грани</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро тут появятся эксперименты и испытания.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Линии Электропередач", callback_data='city_powerlines')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_power_persimmon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🍊 <b>ХУРМА?</b> 🍊\n\n"
        "🍃 <i>Неожиданная сладость среди проводов</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Совсем скоро здесь появится контент.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Линии Электропередач", callback_data='city_powerlines')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_sept_to_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "💱 <b>ОБМЕН СЕПТИМОВ НА ВАЛЮТУ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится обмен септимов на особые валюты.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_sept_to_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "📦 <b>ОБМЕН СЕПТИМОВ НА РЕСУРСЫ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится обмен септимов на ресурсы.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_sept_to_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🧩 <b>ОБМЕН СЕПТИМОВ НА ЧАСТИ БОЕВЫХ КАРТ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится обмен септимов на части боевых карт.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_convert_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🔄 <b>КОНВЕРТАЦИЯ РЕСУРСОВ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится конвертация ресурсов.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_resource_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "📊 <b>КУРСЫ ПО РЕСУРСАМ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появятся курсы конвертации ресурсов.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_daily_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🔥 <b>ПРЕДЛОЖЕНИЯ ДНЯ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появятся специальные предложения дня.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🎁 <b>ВАШИ БОНУСЫ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появятся персональные бонусы Обменника.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🧾 <b>МОЯ ИСТОРИЯ ОПЕРАЦИЙ</b>\n\n"
        "🚧 <b>ЛОКАЦИЯ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится история операций Обменника.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Обменник", callback_data='rostov_exchange')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def show_rostov_elite_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка для Магазина элиты."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = (
        "💎 <b>МАГАЗИН ЭЛИТЫ</b> 💎\n\n"
        "👑 <i>Роскошь для истинных ценителей</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>МАГАЗИН В РАЗРАБОТКЕ</b> 🚧\n\n"
        "🔮 <b>Будет доступно:</b>\n\n"
        "✨ Легендарные предметы\n"
        "🎨 Уникальные кастомизации\n"
        "⚡ Мощные усиления\n"
        "🔰 Эксклюзивные титулы\n"
        "🌟 Редкие коллекционные вещи\n"
        "💫 Специальные эффекты\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ <i>Скоро откроется!\nПриготовьте свои септимы.</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💠 Элитные предметы", callback_data='rostov_elite_items')],
        [InlineKeyboardButton("⚡ Усилители", callback_data='rostov_elite_boosters')],
        [InlineKeyboardButton("🎨 Темы и эмодзи", callback_data='rostov_elite_themes')],
        [InlineKeyboardButton("🔰 Титулы", callback_data='rostov_elite_titles')],
        [InlineKeyboardButton("🌟 Коллекционки", callback_data='rostov_elite_collectibles')],
        [InlineKeyboardButton("🎫 Боевой Пропуск", callback_data='rostov_elite_battlepass')],
        [InlineKeyboardButton("🃏 Карточки", callback_data='rostov_elite_cards')],
        [InlineKeyboardButton("🔙 Вернуться в Ростов", callback_data='city_rostov')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = (
        "🧬 <b>ХАБ РОСТОВА</b> 🧬\n\n"
        "📡 <i>Центр управления селюками и сделками</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📍 <b>ДОСТУПНЫЕ РАЗДЕЛЫ:</b>\n\n"
        "👥 <b>Ваши селюки</b>\n"
        "   └ <i>Просмотр принадлежащих вам селюков</i>\n\n"
        "📦 <b>Селюки на продажу</b>\n"
        "   └ <i>Список доступных селюков на рынке</i>\n\n"
        "💸 <b>Продажа селюка</b>\n"
        "   └ <i>Выставление ваших селюков на продажу</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Ваш баланс:</b> {coins:,} 💎\n"
        "<i>Выберите раздел:</i>"
    ).format(coins=player.coins)

    keyboard = [
        [InlineKeyboardButton("👥 Ваши селюки", callback_data='rostov_hub_my_selyuki')],
        [InlineKeyboardButton("📦 Селюки на продажу", callback_data='rostov_hub_selyuki_on_sale')],
        [InlineKeyboardButton("💸 Продажа селюка", callback_data='rostov_hub_sell_selyuk')],
        [InlineKeyboardButton("🔙 Вернуться в Ростов", callback_data='city_rostov')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
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


async def show_rostov_hub_my_selyuki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    selyuki = db.get_player_selyuki(user.id)

    if not selyuki:
        text = (
            "👥 <b>ВАШИ СЕЛЮКИ</b>\n\n"
            "У тебя пока нет селюков.\n\n"
            "Загляни в раздел \"Селюки на продажу\", чтобы купить первого помощника."
        )
        keyboard = [
            [InlineKeyboardButton("📦 Селюки на продажу", callback_data='rostov_hub_selyuki_on_sale')],
            [InlineKeyboardButton("🔙 Вернуться в Хаб", callback_data='rostov_hub')],
            [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
        ]
    else:
        lines = ["👥 <b>ВАШИ СЕЛЮКИ</b>"]
        keyboard = []

        for s in selyuki:
            stype = str(getattr(s, 'type', '') or '')
            if stype == 'farmer':
                lvl = int(getattr(s, 'level', 1) or 1)
                bal = int(getattr(s, 'balance_septims', 0) or 0)
                enabled = bool(getattr(s, 'is_enabled', False))
                status = "✅ Вкл" if enabled else "🚫 Выкл"
                lines.append(f"\n👨‍🌾 <b>Селюк фермер</b> — ур. {lvl}, баланс: {bal} 💎, статус: {status}")
                keyboard.append([InlineKeyboardButton("👨‍🌾 Управление фермером", callback_data='selyuk_farmer_manage')])

        lines.append("\nВыбери селюка для управления.")
        text = "\n".join(lines)
        keyboard.append([InlineKeyboardButton("🔙 Вернуться в Хаб", callback_data='rostov_hub')])
        keyboard.append([InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_hub_selyuki_on_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "📦 <b>СЕЛЮКИ НА ПРОДАЖУ</b>\n\n"
        "🧬 <i>Выберите тип селюка, которого хотите приобрести</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👨‍🌾 <b>Селюк фермер</b> — заботится о ваших ресурсах\n"
        "🧵 <b>Селюк шёлковод</b> — мастер шёлковых плантаций\n"
        "🧮 <b>Селюк махинаций</b> — отвечает за хитрые схемы\n"
        "🛒 <b>Селюк покупатель</b> — ищет выгодные сделки\n"
        "👑 <b>Босс селюков</b> — управляет всей их командой\n\n"
        "🚧 <b>Функционал рынка в разработке</b> 🚧\n\n"
        "⏳ <i>Сейчас доступен выбор типа, позже появятся подробные офферы.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("👨‍🌾 Селюк фермер", callback_data='selyuk_type_farmer')],
        [InlineKeyboardButton("🧵 Селюк шёлковод", callback_data='selyuk_type_silkmaker')],
        [InlineKeyboardButton("🧮 Селюк махинаций", callback_data='selyuk_type_trickster')],
        [InlineKeyboardButton("🛒 Селюк покупатель", callback_data='selyuk_type_buyer')],
        [InlineKeyboardButton("👑 Босс селюков", callback_data='selyuk_type_boss')],
        [InlineKeyboardButton("🔙 Вернуться в Хаб", callback_data='rostov_hub')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_type_farmer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    farmer = db.get_selyuk_by_type(user.id, 'farmer')

    if farmer:
        lvl = int(getattr(farmer, 'level', 1) or 1)
        bal = int(getattr(farmer, 'balance_septims', 0) or 0)
        enabled = bool(getattr(farmer, 'is_enabled', False))
        status = "✅ Вкл" if enabled else "🚫 Выкл"
        text = (
            "👨‍🌾 <b>СЕЛЮК ФЕРМЕР</b>\n\n"
            "У тебя уже есть селюк фермер.\n\n"
            f"Уровень: {lvl}\n"
            f"Баланс селюка: {bal} 💎\n"
            f"Статус: {status}\n\n"
            "Фермер автоматически поливает обычные плантации энергетиков, "
            "если включены напоминания о поливе.\n"
            f"Стоимость полива: {'45' if lvl >= 2 else '50'} септимов.\n"
            f"{'✅ Автосбор урожая доступен!' if lvl >= 2 else '❌ Автосбор урожая доступен с 2 уровня.'}"
        )
        keyboard = [
            [InlineKeyboardButton("👨‍🌾 Управление фермером", callback_data='selyuk_farmer_manage')],
            [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
            [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
        ]
    else:
        text = (
            "👨‍🌾 <b>СЕЛЮК ФЕРМЕР</b>\n\n"
            "🌾 Трудолюбивый помощник для обычных плантаций энергетиков.\n\n"
            "• Автоматически поливает грядки, как только они готовы к поливу.\n"
            "• За каждый полив списывает 50 септимов с <b>баланса селюка</b>.\n"
            "• Работает только при включённых напоминаниях о поливе.\n\n"
            "<b>Стоимость покупки:</b> 50 000 💎\n"
            "Начальный баланс селюка: 0 💎 (пополняется отдельно)."
        )
        keyboard = [
            [InlineKeyboardButton("💰 Купить за 50 000", callback_data='selyuk_buy_farmer')],
            [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
            [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_farmer_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    farmer = db.get_selyuk_by_type(user.id, 'farmer')

    if not farmer:
        text = (
            "👨‍🌾 <b>СЕЛЮК ФЕРМЕР</b>\n\n"
            "У тебя ещё нет селюка фермера.\n\n"
            "Купи его в разделе \"Селюки на продажу\"."
        )
        keyboard = [
            [InlineKeyboardButton("📦 Селюки на продажу", callback_data='rostov_hub_selyuki_on_sale')],
            [InlineKeyboardButton("🔙 Вернуться в Хаб", callback_data='rostov_hub')],
        ]
    else:
        lvl = int(getattr(farmer, 'level', 1) or 1)
        bal = int(getattr(farmer, 'balance_septims', 0) or 0)
        enabled = bool(getattr(farmer, 'is_enabled', False))
        status = "✅ Включен" if enabled else "🚫 Выключен"
        coins = int(getattr(player, 'coins', 0) or 0)
        water_cost = 45 if lvl >= 2 else 50

        text = (
            "👨‍🌾 <b>СЕЛЮК ФЕРМЕР</b>\n\n"
            f"Уровень: {lvl}\n"
            f"Баланс селюка: {bal} 💎\n"
            f"Статус: {status}\n\n"
            f"Баланс игрока: {coins} 💎\n\n"
            "Фермер автоматически поливает обычные плантации, когда:\n"
            "• грядка готова к поливу;\n"
            "• включены напоминания о поливе;\n"
            f"• на балансе селюка есть ≥ {water_cost} септимов."
        )

        toggle_text = "🚫 Выключить" if enabled else "✅ Включить"
        keyboard = [
            [InlineKeyboardButton(toggle_text, callback_data='selyuk_farmer_toggle')],
            [
                InlineKeyboardButton("💰 +1 000 на баланс", callback_data='selyuk_farmer_topup_1000'),
                InlineKeyboardButton("💰 +10 000", callback_data='selyuk_farmer_topup_10000'),
            ],
            [InlineKeyboardButton("ℹ️ Как работает", callback_data='selyuk_farmer_howto')],
            [InlineKeyboardButton("⚙️ Настройки", callback_data='selyuk_farmer_settings')],
            [InlineKeyboardButton("⬆️ Улучшить селюка", callback_data='selyuk_farmer_upgrade')],
            [InlineKeyboardButton("💸 Продать селюка", callback_data='selyuk_farmer_sell')],
            [InlineKeyboardButton("🔙 К Вашим селюкам", callback_data='rostov_hub_my_selyuki')],
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_selyuk_buy_farmer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    res = db.buy_farmer_selyuk(user.id, price=50000)

    if not res.get('ok'):
        reason = res.get('reason')
        if reason == 'already_have_farmer':
            await query.answer("У тебя уже есть селюк фермер.", show_alert=True)
        elif reason == 'not_enough_coins':
            need = int(res.get('need') or 50000)
            have = int(res.get('have') or getattr(player, 'coins', 0) or 0)
            await query.answer(f"Недостаточно септимов для покупки. Нужно {need}, у тебя {have}.", show_alert=True)
        else:
            await query.answer("Не удалось купить селюка фермера.", show_alert=True)
        await show_selyuk_type_farmer(update, context)
        return

    await query.answer("Селюк фермер куплен!", show_alert=True)
    await show_selyuk_farmer_manage(update, context)


async def handle_selyuk_farmer_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    farmer = db.get_selyuk_by_type(user.id, 'farmer')
    if not farmer:
        await query.answer("Селюк фермер не найден.", show_alert=True)
        await show_rostov_hub_my_selyuki(update, context)
        return

    new_state = not bool(getattr(farmer, 'is_enabled', False))
    dbs = db.SessionLocal()
    try:
        row = (
            dbs.query(db.Selyuk)
            .filter(db.Selyuk.owner_id == int(user.id), db.Selyuk.type == 'farmer')
            .with_for_update(read=False)
            .first()
        )
        if row:
            row.is_enabled = new_state
            try:
                row.updated_at = int(time.time())
            except Exception:
                pass
            dbs.commit()
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
    finally:
        dbs.close()

    await show_selyuk_farmer_manage(update, context)


async def handle_selyuk_farmer_topup(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    res = db.topup_selyuk_balance_from_player(user.id, 'farmer', amount)

    if not res.get('ok'):
        reason = res.get('reason')
        if reason == 'not_enough_coins':
            need = int(res.get('need') or amount)
            have = int(res.get('have') or 0)
            await query.answer(f"Недостаточно септимов. Нужно {need}, у тебя {have}.", show_alert=True)
        elif reason == 'no_selyuk':
            await query.answer("Селюк фермер не найден.", show_alert=True)
        else:
            await query.answer("Не удалось пополнить баланс селюка.", show_alert=True)
    else:
        await query.answer("Баланс селюка пополнен.", show_alert=False)

    await show_selyuk_farmer_manage(update, context)


async def show_selyuk_farmer_howto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    farmer = db.get_selyuk_by_type(user.id, 'farmer')
    lvl = int(getattr(farmer, 'level', 1) or 1) if farmer else 1
    water_cost = 45 if lvl >= 2 else 50
    text = (
        "ℹ️ <b>КАК РАБОТАЕТ СЕЛЮК ФЕРМЕР</b>\n\n"
        "• Работает только с обычными плантациями энергетиков.\n"
        "• Когда грядка готова к поливу, фермер пытается полить её автоматически.\n"
        f"• За каждый полив списывается {water_cost} септимов с баланса селюка.\n"
        "• Для работы фермера должны быть включены напоминания о поливе.\n"
        f"• Если на балансе селюка меньше {water_cost} септимов, он не поливает грядку."
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_farmer_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    farmer = db.get_selyuk_by_type(user.id, 'farmer')
    if not farmer:
        await show_selyuk_farmer_manage(update, context)
        return

    lvl = int(getattr(farmer, 'level', 1) or 1)
    max_fert = max(1, db.get_setting_int('plantation_fertilizer_max_per_bed', PLANTATION_FERTILIZER_MAX_PER_BED))
    
    if lvl >= 4:
        text = (
            "⬆️ <b>УЛУЧШЕНИЕ СЕЛЮКА ФЕРМЕРА</b>\n\n"
            "Ваш селюк уже достиг максимального 4 уровня!\n\n"
            "✅ Стоимость полива снижена до 45 септимов.\n"
            "✅ Автоматический сбор урожая включен.\n"
            "✅ Автоматическая посадка семян включена.\n"
            f"✅ Автоматическое удобрение (до {max_fert} слотов на грядку) включено."
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')]]
    elif lvl == 3:
        text = (
            "⬆️ <b>УЛУЧШЕНИЕ СЕЛЮКА ФЕРМЕРА</b>\n\n"
            "Текущий уровень: 3\n"
            "Следующий уровень: 4\n\n"
            "<b>Бонусы 4 уровня:</b>\n"
            f"🧪 <b>Автоудобрение:</b> селюк поддерживает удобрения на грядках (до {max_fert} слотов).\n"
            "(Выбор удобрений — по приоритету в настройках)\n\n"
            "<b>Стоимость улучшения:</b>\n"
            "💰 250 000 септимов\n"
            "🧩 25 Фрагментов Селюка"
        )
        keyboard = [
            [InlineKeyboardButton("💰 Улучшить (250к + 25 фрагм.)", callback_data='selyuk_farmer_upgrade_action')],
            [InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')],
        ]
    elif lvl == 2:
        text = (
            "⬆️ <b>УЛУЧШЕНИЕ СЕЛЮКА ФЕРМЕРА</b>\n\n"
            "Текущий уровень: 2\n"
            "Следующий уровень: 3\n\n"
            "<b>Бонусы 3 уровня:</b>\n"
            "🌱 <b>Автопосадка:</b> селюк сам посадит семена, если грядка пуста!\n"
            "(Берет первые попавшиеся семена из инвентаря)\n\n"
            "<b>Стоимость улучшения:</b>\n"
            "💰 150 000 септимов\n"
            "🧩 15 Фрагментов Селюка"
        )
        keyboard = [
            [InlineKeyboardButton("💰 Улучшить (150к + 15 фрагм.)", callback_data='selyuk_farmer_upgrade_action')],
            [InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')],
        ]
    else:
        text = (
            "⬆️ <b>УЛУЧШЕНИЕ СЕЛЮКА ФЕРМЕРА</b>\n\n"
            "Текущий уровень: 1\n"
            "Следующий уровень: 2\n\n"
            "<b>Бонусы 2 уровня:</b>\n"
            "📉 Снижение стоимости полива: 50 -> 45 септимов\n"
            "🚜 <b>Автосбор урожая:</b> селюк сам соберет созревшие энергетики!\n\n"
            "<b>Стоимость улучшения:</b> 200 000 септимов"
        )
        keyboard = [
            [InlineKeyboardButton("💰 Улучшить за 200 000", callback_data='selyuk_farmer_upgrade_action')],
            [InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_selyuk_farmer_upgrade_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    res = db.upgrade_selyuk_farmer(user.id)
    
    if not res.get('ok'):
        reason = res.get('reason')
        if reason == 'not_enough_coins':
            await query.answer("Недостаточно монет для улучшения!", show_alert=True)
        elif reason == 'not_enough_fragments':
            await query.answer("Недостаточно Фрагментов Селюка!", show_alert=True)
        elif reason == 'max_level':
            await query.answer("Селюк уже максимального уровня!", show_alert=True)
        else:
            await query.answer("Ошибка при улучшении.", show_alert=True)
        await show_selyuk_farmer_upgrade(update, context)
        return
        
    new_lvl = res.get('new_level', 2)
    await query.answer(f"Селюк успешно улучшен до {new_lvl} уровня!", show_alert=True)
    await show_selyuk_farmer_upgrade(update, context)


async def show_selyuk_farmer_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "💸 <b>ПРОДАЖА СЕЛЮКА ФЕРМЕРА</b>\n\n"
        "Механика продажи селюков пока в разработке."
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к фермеру", callback_data='selyuk_farmer_manage')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_type_silkmaker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🧵 <b>СЕЛЮК ШЁЛКОВОД</b>\n\n"
        "🌳 <i>Специалист по шёлковым плантациям и добыче редкого ресурса.</i>\n\n"
        "🚧 <b>РАЗДЕЛ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро здесь появится его эффективность и цена.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_type_trickster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🧮 <b>СЕЛЮК МАХИНАЦИЙ</b>\n\n"
        "📊 <i>Отвечает за хитрые схемы и рискованные операции.</i>\n\n"
        "🚧 <b>РАЗДЕЛ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Позже тут появятся бонусы и особенности махинаций.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_type_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "🛒 <b>СЕЛЮК ПОКУПАТЕЛЬ</b>\n\n"
        "💰 <i>Ищет выгодные предложения и помогает с покупками.</i>\n\n"
        "🚧 <b>РАЗДЕЛ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Здесь позже появятся его преимущества и стоимость.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_selyuk_type_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "👑 <b>БОСС СЕЛЮКОВ</b>\n\n"
        "🧬 <i>Главный среди селюков, усиливает работу всей команды.</i>\n\n"
        "🚧 <b>РАЗДЕЛ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Позже здесь появятся его уникальные способности и цена.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к селюкам на продажу", callback_data='rostov_hub_selyuki_on_sale')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_hub_sell_selyuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    text = (
        "💸 <b>ПРОДАЖА СЕЛЮКА</b>\n\n"
        "🚧 <b>РАЗДЕЛ В РАЗРАБОТКЕ</b> 🚧\n\n"
        "⏳ <i>Скоро вы сможете выставлять селюков на продажу.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в Хаб", callback_data='rostov_hub')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def show_rostov_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка для Обменника."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    _ = player.language

    text = (
        "💱 <b>ВАЛЮТНЫЙ ОБМЕННИК</b> 💱\n\n"
        "📈 <i>Лучшие курсы обмена в регионе</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 <b>ОБМЕННИК В РАЗРАБОТКЕ</b> 🚧\n\n"
        "🔮 <b>Планируемые функции:</b>\n\n"
        "💰 Обмен септимов на особые валюты\n"
        "🔄 Конвертация ресурсов\n"
        "📊 Динамические курсы обмена\n"
        "💎 Выгодные предложения дня\n"
        "🎁 Бонусы за крупные обмены\n"
        "📈 История операций\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ <i>Готовимся к открытию!\nСкоро начнём работу.</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💱 Обмен Септимов на валюту 🚧", callback_data='rostov_exchange_sept_to_currency')],
        [InlineKeyboardButton("📦 Обмен Септимов на ресурсы 🚧", callback_data='rostov_exchange_sept_to_resources')],
        [InlineKeyboardButton("🧩 Обмен Септимов на части боевых карт 🚧", callback_data='rostov_exchange_sept_to_cards')],
        [InlineKeyboardButton("🔄 Конвертация ресурсов 🚧", callback_data='rostov_exchange_convert_resources')],
        [InlineKeyboardButton("📊 Курсы по ресурсам 🚧", callback_data='rostov_exchange_resource_rates')],
        [InlineKeyboardButton("🔥 Предложения дня 🚧", callback_data='rostov_exchange_daily_deals')],
        [InlineKeyboardButton("🎁 Ваши бонусы 🚧", callback_data='rostov_exchange_bonuses')],
        [InlineKeyboardButton("🧾 Моя история операций 🚧", callback_data='rostov_exchange_history')],
        [InlineKeyboardButton("🔙 Вернуться в Ростов", callback_data='city_rostov')],
        [InlineKeyboardButton("🏙️ К городам", callback_data='cities_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
        if rarity == 'Majestic':
             kb.append([InlineKeyboardButton(f"🚫 {off.offer_index} (Majestic)", callback_data='noop')])
        else:
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
        # Проверка на Majestic перед покупкой
        offers, _ = db.get_or_refresh_shop_offers()
        target_offer = next((o for o in offers if o.offer_index == offer_index), None)
        if target_offer and str(target_offer.rarity) == 'Majestic':
             await query.answer("Покупка Majestic запрещена в этом магазине!", show_alert=True)
             return

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
            price = SHOP_PRICES.get(rr, 0)
            # Логируем покупку
            db.log_action(
                user_id=user.id,
                username=user.username or user.first_name,
                action_type='purchase',
                action_details=f'Магазин: {dn} ({rr}), оффер #{offer_index}',
                amount=-price,
                success=True
            )
            await query.answer(f"Куплено: {dn} ({rr}). Баланс: {coins}", show_alert=True)
 
async def show_market_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран Приёмника: прайс-лист продажи и переход в инвентарь."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'

    # Собираем прайс-лист (выплата за 1 шт. с учётом комиссии и рейтинга)
    rating_value = int(getattr(player, 'rating', 0) or 0)
    rating_bonus = db.get_rating_bonus_percent(rating_value)
    lines = [
        "<b>♻️ Приёмник</b>",
        "Сдавайте лишние энергетики и получайте монеты.",
        f"Комиссия: {int(RECEIVER_COMMISSION*100)}% (выплата = {100-int(RECEIVER_COMMISSION*100)}% от цены)",
        f"Бонус рейтинга: +{rating_bonus:.1f}%",
    ]
    if lang == 'ru':
        lines.extend([
            "💡 <b>Шкала бонусов рейтинга:</b>",
            "50 → +5%, 100 → +7.5%, 150 → +10%, 200 → +12.5%, 250 → +13%",
            "Дальше плавно до +25% при рейтинге 1000.",
        ])
    else:
        lines.extend([
            "💡 <b>Rating bonus scale:</b>",
            "50 → +5%, 100 → +7.5%, 150 → +10%, 200 → +12.5%, 250 → +13%",
            "Then increases smoothly to +25% at rating 1000.",
        ])
    lines.extend([
        "",
        "<b>Прайс-лист (за 1 шт.)</b>",
    ])
    for r in RARITY_ORDER:
        if r in RECEIVER_PRICES:
            payout = int(db.get_receiver_unit_payout_with_rating(r, rating_value) or 0)
            emoji = COLOR_EMOJIS.get(r, '⚫')
            lines.append(f"{emoji} {r}: {payout} монет")
    text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("📦 Открыть инвентарь", callback_data='inventory')],
        [InlineKeyboardButton("📊 По количеству", callback_data='receiver_by_quantity')],
        [InlineKeyboardButton("🗑️ Продать все", callback_data='sell_all_confirm_1')],
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

    # Проверяем наличие активного VIP+
    has_vip_plus = db.is_vip_plus(user.id)
    
    if has_vip_plus:
        # Если есть VIP+, показываем предупреждение вместо кнопок тарифов
        vip_plus_until = db.get_vip_plus_until(user.id)
        until_str = safe_format_timestamp(vip_plus_until) if vip_plus_until else '—'
        
        text = f"<b>{VIP_EMOJI} V.I.P статус</b>\n\n"
        text += f"⚠️ У вас уже есть активный {VIP_PLUS_EMOJI} VIP+ до {until_str}\n\n"
        text += "❌ Покупка обычного VIP недоступна при наличии VIP+.\n\n"
        text += "💡 VIP+ уже включает все преимущества обычного VIP и даже больше!"
        
        keyboard = [
            [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='extra_bonuses')],
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
        ]
    else:
        # Обычное меню VIP
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
    if await abort_if_banned(update, context):
        return
    user = update.effective_user
    # Регистрируем группу, если команда в группе
    try:
        await register_group_if_needed(update)
    except Exception:
        pass
    db.get_or_create_player(user.id, username=getattr(user, 'username', None), display_name=(getattr(user, 'full_name', None) or getattr(user, 'first_name', None)))
    await show_menu(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все нажатия на inline-кнопки."""
    if await abort_if_banned(update, context):
        return
    # Регистрируем группу, если нажатие было в группе
    try:
        await register_group_if_needed(update)
    except Exception:
        pass
    query = update.callback_query
    if not query:
        return

    try:
        u = query.from_user
        if u:
            db.get_or_create_player(u.id, username=getattr(u, 'username', None), display_name=(getattr(u, 'full_name', None) or getattr(u, 'first_name', None)))
    except Exception:
        pass
    
    data = query.data
    
    # Чтобы не падало, если кнопка без данных
    if not data:
        await query.answer()
        return

    # Централизованная проверка прав для админских callback'ов по матрице.
    required_level = get_required_level_for_callback(data)
    if required_level is not None:
        actor = query.from_user
        if not has_admin_level(actor.id, actor.username, required_level):
            msg = "⛔ Доступ только для Создателя." if required_level >= 99 else "⛔ Недостаточный уровень доступа."
            await query.answer(msg, show_alert=True)
            return

    if data == 'menu':
        await show_menu(update, context)
    elif data == 'swaga_shop':
        await swagashop.show_swaga_shop(update, context)
    elif data == 'swaga_cards_inv':
        await swagashop.show_swaga_cards_inv(update, context)
    elif data == 'swaga_chests_inv':
        await swagashop.show_swaga_chests_inv(update, context)
    elif data == 'swaga_tracks_inv':
        await swagashop.show_swaga_tracks_inv(update, context, page=1)
    elif data.startswith('swaga_exchange_'):
        rarity = data.split('swaga_exchange_')[1]
        await swagashop.handle_swaga_exchange(update, context, rarity)
    elif data.startswith('swaga_open_'):
        rarity = data.split('swaga_open_')[1]
        await swagashop.handle_swaga_open_chest(update, context, rarity)
    elif data.startswith('swaga_tracks_page_'):
        page = int(data.split('swaga_tracks_page_')[1])
        await swagashop.show_swaga_tracks_inv(update, context, page=page)
    elif data.startswith('swaga_play_'):
        track_id = int(data.split('swaga_play_')[1])
        await swagashop.handle_swaga_play_track(update, context, track_id)
    elif data == 'promo_enter':
        await promo_button_start(update, context)
    elif data == 'promo_cancel':
        await promo_button_cancel(update, context)
    elif data == 'creator_panel':
        await show_creator_panel(update, context)
    elif data == 'admin_grants_menu':
        await show_admin_grants_menu(update, context)
    elif data == 'creator_wipe':
        await creator_wipe_start(update, context)
    elif data == 'creator_wipe_confirm':
        await creator_wipe_confirm(update, context)
    elif data == 'creator_reset_bonus':
        await creator_reset_bonus_start(update, context)
    elif data == 'creator_give_coins':
        await creator_give_coins_start(update, context)
    elif data == 'creator_user_stats':
        await creator_user_stats_start(update, context)
    elif data == 'creator_admins':
        await show_admins_panel(update, context)
    elif data == 'creator_admin_add':
        await creator_admin_add_start(update, context)
    elif data == 'creator_admin_promote':
        await creator_admin_promote_start(update, context)
    elif data == 'creator_admin_demote':
        await creator_admin_demote_start(update, context)
    elif data == 'creator_admin_remove':
        await creator_admin_remove_start(update, context)
    elif data == 'admin_bot_stats':
        await show_bot_stats(update, context)
    elif data == 'admin_players_menu':
        await show_admin_players_menu(update, context)
    elif data == 'admin_player_search':
        await admin_player_search_start(update, context)
    elif data == 'admin_players_list' or data.startswith('admin_players_list:'):
        await admin_players_list(update, context)
    elif data == 'admin_players_top':
        await admin_players_top(update, context)
    elif data.startswith('admin_player_details:'):
        await show_player_details(update, context)
    elif data.startswith('admin_player_balance:'):
        await admin_player_balance_start(update, context)
    elif data.startswith('admin_player_rating:'):
        await admin_player_rating_start(update, context)
    elif data.startswith('admin_player_vip:'):
        await admin_player_vip_menu(update, context)
    elif data.startswith('admin_player_vip_give:'):
        # Переадресуем на стандартный обработчик VIP с указанием player_id
        parts = data.split(':')
        if len(parts) > 1:
            context.user_data['admin_vip_player_id'] = int(parts[1])
        await admin_vip_give_start(update, context)
    elif data.startswith('admin_player_vip_plus_give:'):
        parts = data.split(':')
        if len(parts) > 1:
            context.user_data['admin_vip_plus_player_id'] = int(parts[1])
        await admin_vip_plus_give_start(update, context)
    elif data.startswith('admin_player_vip_remove:'):
        parts = data.split(':')
        if len(parts) > 1:
            player_id = int(parts[1])
            dbs = SessionLocal()
            try:
                player = dbs.query(Player).filter(Player.user_id == player_id).first()
                if player:
                    db.update_player(player_id, vip_until=0)
                    await query.answer("✅ VIP отозван!", show_alert=False)
                    await show_player_details(update, context, player_id)
                else:
                    await query.answer("❌ Игрок не найден", show_alert=True)
            finally:
                dbs.close()
    elif data.startswith('admin_player_vip_plus_remove:'):
        parts = data.split(':')
        if len(parts) > 1:
            player_id = int(parts[1])
            dbs = SessionLocal()
            try:
                player = dbs.query(Player).filter(Player.user_id == player_id).first()
                if player:
                    db.update_player(player_id, vip_plus_until=0)
                    await query.answer("✅ VIP+ отозван!", show_alert=False)
                    await show_player_details(update, context, player_id)
                else:
                    await query.answer("❌ Игрок не найден", show_alert=True)
            finally:
                dbs.close()
    elif data.startswith('admin_player_logs:'):
        await admin_player_logs_show(update, context)
    elif data.startswith('admin_player_reset_bonus:'):
        await admin_player_reset_bonus_execute(update, context)
    elif data == 'admin_vip_menu':
        await show_admin_vip_menu(update, context)
    elif data == 'admin_stock_menu':
        logger.info(f"[BUTTON_HANDLER] Обработка кнопки admin_stock_menu от пользователя {query.from_user.id}")
        await show_admin_stock_menu(update, context)
    elif data == 'admin_broadcast_menu':
        await show_admin_broadcast_menu(update, context)
    elif data == 'admin_broadcast_start':
        await admin_broadcast_start(update, context)
    elif data == 'admin_vip_give':
        await admin_vip_give_start(update, context)
    elif data == 'admin_vip_plus_give':
        await admin_vip_plus_give_start(update, context)
    elif data == 'admin_vip_remove':
        await admin_vip_remove_start(update, context)
    elif data == 'admin_vip_plus_remove':
        await admin_vip_plus_remove_start(update, context)
    elif data == 'admin_vip_list':
        await admin_vip_list_show(update, context)
    
    # Новые разделы админ панели
    elif data == 'admin_analytics':
        await show_admin_analytics(update, context)
    elif data == 'admin_analytics_export':
        await export_admin_analytics(update, context)
    elif data == 'admin_drinks_menu':
        await show_admin_drinks_menu(update, context)
    elif data == 'admin_promo_menu':
        await show_admin_promo_menu(update, context)
    elif data == 'admin_promo_wizard':
        await admin_promo_wizard_start(update, context)
    elif data == 'admin_settings_menu':
        await show_admin_settings_menu(update, context)
    elif data == 'admin_settings_limits':
        await show_admin_settings_limits(update, context)
    elif data == 'admin_settings_set_fertilizer_max':
        await admin_settings_set_fertilizer_max_start(update, context)
    elif data == 'admin_settings_negative_effects':
        await show_admin_settings_negative_effects(update, context)
    elif data == 'admin_settings_set_neg_interval':
        await admin_settings_set_neg_interval_start(update, context)
    elif data == 'admin_settings_set_neg_chance':
        await admin_settings_set_neg_chance_start(update, context)
    elif data == 'admin_settings_set_neg_max_active':
        await admin_settings_set_neg_max_active_start(update, context)
    elif data == 'admin_settings_set_neg_duration':
        await admin_settings_set_neg_duration_start(update, context)
    elif data == 'admin_settings_cooldowns':
        await show_admin_settings_cooldowns(update, context)
    elif data == 'admin_settings_set_search_cd':
        await admin_settings_set_search_cd_start(update, context)
    elif data == 'admin_settings_set_bonus_cd':
        await admin_settings_set_bonus_cd_start(update, context)
    elif data == 'admin_settings_autosearch':
        await show_admin_settings_autosearch(update, context)
    elif data == 'admin_settings_set_auto_base':
        await admin_settings_set_auto_base_start(update, context)
    elif data == 'admin_settings_set_auto_vip_mult':
        await admin_settings_set_auto_vip_mult_start(update, context)
    elif data == 'admin_settings_set_auto_vip_plus_mult':
        await admin_settings_set_auto_vip_plus_mult_start(update, context)
    elif data == 'admin_settings_casino':
        await show_admin_settings_casino(update, context)
    elif data == 'admin_settings_set_casino_win_prob':
        await admin_settings_set_casino_win_prob_start(update, context)
    elif data == 'admin_settings_set_casino_luck_mult':
        await admin_settings_set_casino_luck_mult_start(update, context)
    elif data == 'admin_settings_casino_reset_prob':
        if not has_creator_panel_access(query.from_user.id, query.from_user.username):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        ok = db.set_setting_float('casino_win_prob', CASINO_WIN_PROB)
        await query.answer("✅ Сброшено" if ok else "❌ Ошибка", show_alert=True)
        await show_admin_settings_casino(update, context)
    elif data == 'admin_settings_casino_reset_luck':
        if not has_creator_panel_access(query.from_user.id, query.from_user.username):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        ok = db.set_setting_float('casino_luck_mult', 1.0)
        await query.answer("✅ Сброшено" if ok else "❌ Ошибка", show_alert=True)
        await show_admin_settings_casino(update, context)
    elif data == 'admin_moderation_menu':
        await show_admin_moderation_menu(update, context)
    elif data == 'admin_mod_ban':
        await admin_mod_ban_start(update, context)
    elif data == 'admin_mod_unban':
        await admin_mod_unban_start(update, context)
    elif data == 'admin_mod_banlist':
        await admin_mod_banlist_show(update, context)
    elif data == 'admin_mod_check':
        await admin_mod_check_start(update, context)
    elif data == 'admin_mod_history':
        await admin_mod_history_show(update, context)
    elif data == 'admin_mod_warnings':
        await admin_mod_warnings_menu(update, context)
    elif data == 'admin_warn_add':
        await admin_warn_add_start(update, context)
    elif data == 'admin_warn_list':
        await admin_warn_list_start(update, context)
    elif data == 'admin_warn_clear':
        await admin_warn_clear_start(update, context)
    elif data == 'admin_logs_menu':
        try:
            await show_admin_logs_menu(update, context)
        except Exception as e:
            logger.error(f"Ошибка при открытии меню логов: {e}", exc_info=True)
            await query.answer("❌ Ошибка при открытии меню логов", show_alert=True)
    elif data == 'admin_economy_menu':
        await show_admin_economy_menu(update, context)
    elif data == 'admin_events_menu':
        await show_admin_events_menu(update, context)
    
    # Управление энергетиками
    elif data == 'admin_drink_add':
        await admin_drink_add_start(update, context)
    elif data == 'admin_drink_edit':
        await admin_drink_edit_start(update, context)
    elif data == 'admin_drink_rename':
        await admin_drink_rename_start(update, context)
    elif data == 'admin_drink_redesc':
        await admin_drink_redesc_start(update, context)
    elif data == 'admin_drink_update_photo':
        await admin_drink_update_photo_start(update, context)
    elif data == 'admin_drink_delete':
        await admin_drink_delete_start(update, context)
    elif data == 'admin_drink_list':
        await admin_drink_list_show_ids(update, context)
    elif data.startswith('admin_drink_list_p'):
        await admin_drink_list_show(update, context)
    elif data == 'admin_drink_search':
        await admin_drink_search_start(update, context)
    elif data == 'drink_confirm_rename' or data == 'drink_cancel_rename':
        user = query.from_user
        if not has_creator_panel_access(user.id, user.username):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        did = context.user_data.get('edit_drink_id')
        new_name = context.user_data.get('pending_rename')
        if data == 'drink_confirm_rename' and did and new_name:
            ok = db.admin_update_drink(int(did), name=new_name)
            text = "✅ Название обновлено" if ok else "❌ Ошибка при обновлении"
        else:
            text = "Отменено"
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        except BadRequest:
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        context.user_data.pop('pending_rename', None)
        context.user_data.pop('edit_drink_id', None)
        context.user_data.pop('awaiting_admin_action', None)
    elif data == 'drink_confirm_redesc' or data == 'drink_cancel_redesc':
        user = query.from_user
        if not has_creator_panel_access(user.id, user.username):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        did = context.user_data.get('edit_drink_id')
        new_desc = context.user_data.get('pending_redesc')
        if data == 'drink_confirm_redesc' and did and new_desc is not None:
            ok = db.admin_update_drink(int(did), description=new_desc)
            text = "✅ Описание обновлено" if ok else "❌ Ошибка при обновлении"
        else:
            text = "Отменено"
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        except BadRequest:
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        context.user_data.pop('pending_redesc', None)
        context.user_data.pop('edit_drink_id', None)
        context.user_data.pop('awaiting_admin_action', None)
    elif data == 'drink_confirm_photo' or data == 'drink_cancel_photo':
        user = query.from_user
        if not has_creator_panel_access(user.id, user.username):
            await query.answer("⛔ Доступ запрещён!", show_alert=True)
            return
        did = context.user_data.get('edit_drink_id')
        image_name = context.user_data.get('pending_photo')
        if data == 'drink_confirm_photo' and did and image_name:
            ok = db.admin_update_drink_image(int(did), image_name)
            text = "✅ Фото обновлено" if ok else "❌ Ошибка при обновлении фото"
        else:
            if image_name:
                try:
                    fp = os.path.join(ENERGY_IMAGES_DIR, image_name)
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass
            text = "Отменено"
        try:
            if getattr(query.message, 'photo', None):
                await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
            else:
                await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        except BadRequest:
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Управление энергетиками", callback_data='admin_drinks_menu')]]))
        context.user_data.pop('pending_photo', None)
        context.user_data.pop('edit_drink_id', None)
        context.user_data.pop('awaiting_admin_action', None)
    
    # Логи системы
    elif data == 'admin_logs_recent':
        await show_admin_logs_recent(update, context)
    elif data == 'admin_logs_transactions':
        await show_admin_logs_transactions(update, context)
    elif data == 'admin_logs_casino':
        await show_admin_logs_casino(update, context)
    elif data == 'admin_logs_purchases':
        await show_admin_logs_purchases(update, context)
    elif data == 'admin_logs_player':
        await show_admin_logs_player_start(update, context)
    elif data == 'admin_logs_errors':
        await show_admin_logs_errors(update, context)
    
    # Заглушки для остальных подразделов (временно возвращают в меню)
    elif data in [
                  'admin_settings_shop', 'admin_settings_notifications',
                  'admin_settings_localization',
                  'admin_econ_shop_prices', 'admin_econ_casino_bets', 'admin_econ_rewards',
                  'admin_econ_inflation', 'admin_econ_vip_prices', 'admin_econ_exchange', 'admin_event_create',
                  'admin_event_list_active', 'admin_event_list_all', 'admin_event_edit', 'admin_event_end',
                  'admin_event_stats']:
        await query.answer("⚙️ Функция в разработке!", show_alert=True)
    elif data == 'admin_promo_create':
        await admin_promo_create_start(update, context)
    elif data == 'admin_promo_deactivate_pick' or data.startswith('admin_promo_deactivate_pick:'):
        await admin_promo_deactivate_pick_show(update, context)
    elif data == 'admin_promo_list_active':
        await admin_promo_list_active_show(update, context)
    elif data == 'admin_promo_list_all':
        await admin_promo_list_all_show(update, context)
    elif data == 'admin_promo_deactivate':
        await admin_promo_deactivate_start(update, context)
    elif data == 'admin_promo_stats':
        await admin_promo_stats_show(update, context)
    elif data == 'promo_wiz_cancel':
        await promo_wiz_cancel(update, context)
    elif data == 'promo_wiz_confirm':
        await promo_wiz_confirm(update, context)
    elif data.startswith('promo_wiz_kind:'):
        await promo_wiz_kind_select(update, context, data.split(':', 1)[1])
    elif data.startswith('promo_wiz_rarity:'):
        await promo_wiz_rarity_select(update, context, data.split(':', 1)[1])
    elif data.startswith('promo_wiz_active:'):
        await promo_wiz_active_select(update, context, data.split(':', 1)[1] == '1')
    elif data.startswith('promo_deact:'):
        try:
            pid = int(data.split(':', 1)[1])
            await admin_promo_deactivate_confirm(update, context, pid)
        except Exception:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('promo_deact_do:'):
        try:
            pid = int(data.split(':', 1)[1])
            await admin_promo_deactivate_do(update, context, pid)
        except Exception:
            await query.answer('Ошибка', show_alert=True)
    
    elif data == 'find_energy':
        await find_energy(update, context)
    elif data == 'claim_bonus':
        await claim_daily_bonus(update, context)
    elif data == 'daily_bonus_info':
        await show_daily_bonus_info(update, context)
    elif data == 'inventory':
        await show_inventory(update, context)
    elif data.startswith('inventory_p'):
        # Пагинация инвентаря
        await show_inventory(update, context)
    elif data == 'inventory_search_start':
        # Начало поиска по инвентарю
        await start_inventory_search(update, context)
    elif data == 'inventory_search_cancel':
        # Отмена поиска и возврат к инвентарю
        await inventory_search_cancel(update, context)
    elif data.startswith('inventory_search_p'):
        # Пагинация результатов поиска
        try:
            page = int(data.removeprefix('inventory_search_p'))
            search_query = context.user_data.get('last_inventory_search', '')
            if search_query:
                await show_inventory_search_results(update, context, search_query, page)
            else:
                await query.answer("Поисковый запрос не найден. Начните новый поиск.", show_alert=True)
        except Exception:
            await query.answer("Ошибка пагинации", show_alert=True)
    elif data.startswith('receiver_qty_p'):
        # Пагинация инвентаря по количеству для Приёмника
        await show_inventory_by_quantity(update, context)
    elif data == 'my_profile':
        await show_my_profile(update, context)
    elif data == 'profile_stats':
        await show_stats(update, context)
    elif data == 'profile_friends':
        await show_profile_friends(update, context)
    elif data == 'profile_favorites':
        await show_profile_favorites_v2(update, context)
    elif data.startswith('fav_slot_'):
        query = update.callback_query
        try:
            slot = int(data.split('_')[-1])
        except Exception:
            slot = 0
        if slot not in (1, 2, 3):
            await query.answer('Ошибка', show_alert=True)
            return

        user_id = query.from_user.id
        lock = _get_lock(f"favorites:{user_id}")
        async with lock:
            await show_favorites_pick_inventory_v2(update, context, slot=slot, page=1)
            return
            player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
            lang = getattr(player, 'language', 'ru') or 'ru'
            item_id = int(getattr(player, f'favorite_drink_{slot}', 0) or 0)

            if item_id > 0:
                res = db.clear_favorite_drink_slot(user_id, slot)
                if not res or not res.get('ok'):
                    await query.answer('Ошибка', show_alert=True)
                    return
                await query.answer('✅ Удалено' if lang == 'ru' else '✅ Removed')
                await show_profile_favorites_v2(update, context)
            else:
                await show_favorites_pick_inventory_v2(update, context, slot=slot, page=1)
    elif data.startswith('fav_clear_'):
        query = update.callback_query
        try:
            slot = int(data.split('_')[-1])
        except Exception:
            slot = 0
        if slot not in (1, 2, 3):
            await query.answer('Ошибка', show_alert=True)
            return
        user_id = query.from_user.id
        lock = _get_lock(f"favorites:{user_id}")
        async with lock:
            player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
            lang = getattr(player, 'language', 'ru') or 'ru'
            res = db.clear_favorite_drink_slot(user_id, slot)
            if not res or not res.get('ok'):
                await query.answer('Ошибка' if lang == 'ru' else 'Error', show_alert=True)
                return
            await query.answer('✅ Слот очищен' if lang == 'ru' else '✅ Slot cleared')
            await show_profile_favorites_v2(update, context)
    elif data.startswith('fav_search_start_'):
        query = update.callback_query
        try:
            slot = int(data.split('_')[-1])
        except Exception:
            slot = 0
        if slot not in (1, 2, 3):
            await query.answer('Ошибка', show_alert=True)
            return
        await start_favorites_search(update, context, slot=slot)
    elif data.startswith('fav_search_page_'):
        query = update.callback_query
        try:
            _, _, _, slot_str, page_str = data.split('_', 4)
            slot = int(slot_str)
            page = int(page_str)
        except Exception:
            await query.answer('Ошибка', show_alert=True)
            return
        search_query = str(context.user_data.get('favorites_last_search_query') or '').strip()
        last_slot = int(context.user_data.get('favorites_last_search_slot') or 0)
        if search_query and slot == last_slot:
            await show_favorites_search_results(update, context, slot=slot, search_query=search_query, page=page)
        else:
            await show_favorites_pick_inventory_v2(update, context, slot=slot, page=1)
    elif data.startswith('fav_pick_page_'):
        query = update.callback_query
        try:
            _, _, _, slot_str, page_str = data.split('_', 4)
            slot = int(slot_str)
            page = int(page_str)
        except Exception:
            await query.answer('Ошибка', show_alert=True)
            return
        await show_favorites_pick_inventory_v2(update, context, slot=slot, page=page)
    elif data.startswith('fav_pick_'):
        query = update.callback_query
        try:
            # fav_pick_{slot}_{item_id}_p{page}
            parts = data.split('_')
            slot = int(parts[2])
            item_id = int(parts[3])
            page_part = parts[4] if len(parts) > 4 else 'p1'
            page = int(str(page_part).lstrip('p') or 1)
        except Exception:
            await query.answer('Ошибка', show_alert=True)
            return

        user_id = query.from_user.id
        lock = _get_lock(f"favorites:{user_id}")
        async with lock:
            player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
            lang = getattr(player, 'language', 'ru') or 'ru'
            res = db.set_favorite_drink_slot(user_id, slot, item_id)
            if not res or not res.get('ok'):
                reason = (res or {}).get('reason')
                if reason == 'forbidden':
                    msg = '❌ Это не ваш предмет.' if lang == 'ru' else "❌ This isn't your item."
                elif reason == 'not_found':
                    msg = '❌ Предмет не найден.' if lang == 'ru' else '❌ Item not found.'
                else:
                    msg = '❌ Ошибка.' if lang == 'ru' else '❌ Error.'
                await query.answer(msg, show_alert=True)
                await show_favorites_pick_inventory_v2(update, context, slot=slot, page=page)
                return

            await query.answer('✅ Сохранено' if lang == 'ru' else '✅ Saved')
            await show_profile_favorites_v2(update, context)
    elif data == 'friends_add_start':
        await friends_add_start(update, context)
    elif data.startswith('friends_add_search:'):
        # Backward-compat: если в старых сообщениях остались кнопки пагинации
        q = context.user_data.get('friends_last_search_query') or ''
        if q:
            await friends_search_results(update, context, str(q), page=0)
        else:
            await friends_add_start(update, context)
    elif data.startswith('friends_add_pick:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if uid:
            await friends_add_pick(update, context, uid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_requests_'):
        try:
            page = int(data.split('_')[-1])
        except Exception:
            page = 0
        await friends_requests_menu(update, context, page=page)
    elif data.startswith('friends_req_open:'):
        try:
            rid = int(data.split(':', 1)[1])
        except Exception:
            rid = 0
        if rid:
            await friends_request_open(update, context, rid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_req_accept:'):
        try:
            rid = int(data.split(':', 1)[1])
        except Exception:
            rid = 0
        if rid:
            await friends_req_accept(update, context, rid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_req_reject:'):
        try:
            rid = int(data.split(':', 1)[1])
        except Exception:
            rid = 0
        if rid:
            await friends_req_reject(update, context, rid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_list_'):
        try:
            page = int(data.split('_')[-1])
        except Exception:
            page = 0
        await friends_list_menu(update, context, page=page)
    elif data.startswith('friends_open:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if uid:
            await friends_open_menu(update, context, uid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_give_coins:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if uid:
            await friends_start_transfer(update, context, 'coins', uid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_give_fragments:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if uid:
            await friends_start_transfer(update, context, 'fragments', uid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_give_rating:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if uid:
            await friends_start_transfer(update, context, 'rating', uid)
        else:
            await query.answer('Ошибка', show_alert=True)
    elif data.startswith('friends_give_vip7:'):
        try:
            uid = int(data.split(':', 1)[1])
        except Exception:
            uid = 0
        if not uid:
            await query.answer('Ошибка', show_alert=True)
        else:
            user = query.from_user
            p = db.get_or_create_player(user.id, user.username or user.first_name)
            lang = p.language
            res = db.gift_vip_7d_to_friend(user.id, uid)
            if not res or not res.get('ok'):
                reason = (res or {}).get('reason')
                if reason == 'sender_not_vip':
                    msg = "❌ Нужно иметь VIP для подарка." if lang == 'ru' else "❌ You need VIP to gift."
                elif reason == 'sender_is_vip_plus':
                    msg = "❌ VIP+ не может дарить VIP." if lang == 'ru' else "❌ VIP+ can't gift VIP."
                elif reason == 'cooldown':
                    msg = "❌ Подарок VIP доступен раз в 2 недели." if lang == 'ru' else "❌ VIP gift is available once per 2 weeks."
                elif reason == 'not_friends':
                    msg = "❌ Этот игрок не у вас в друзьях." if lang == 'ru' else "❌ Not your friend."
                else:
                    msg = "❌ Ошибка. Попробуйте позже." if lang == 'ru' else "❌ Error. Try later."
                await query.answer(msg, show_alert=True)
                await friends_open_menu(update, context, uid)
            else:
                await query.answer("✅ VIP подарен на 7 дней!" if lang == 'ru' else "✅ VIP gifted for 7 days!", show_alert=True)
                try:
                    await context.bot.send_message(chat_id=uid, text="🎁 Вам подарили VIP на 7 дней!" if lang == 'ru' else "🎁 You received VIP for 7 days!")
                except Exception:
                    pass
                await friends_open_menu(update, context, uid)
    elif data == 'profile_boosts':
        await show_profile_boosts(update, context)
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
    elif data == 'city_rostov':
        await show_city_rostov(update, context)
    elif data == 'city_powerlines':
        await show_city_powerlines(update, context)
    elif data == 'rostov_hub':
        await show_rostov_hub(update, context)
    elif data == 'power_sematori':
        await show_power_sematori(update, context)
    elif data == 'power_red_cores':
        await show_power_red_cores(update, context)
    elif data == 'power_glasswool_field':
        await show_power_glasswool_field(update, context)
    elif data == 'power_persimmon':
        await show_power_persimmon(update, context)
    elif data == 'rostov_hub_my_selyuki':
        await show_rostov_hub_my_selyuki(update, context)
    elif data == 'rostov_hub_selyuki_on_sale':
        await show_rostov_hub_selyuki_on_sale(update, context)
    elif data == 'rostov_hub_sell_selyuk':
        await show_rostov_hub_sell_selyuk(update, context)
    elif data == 'selyuk_type_farmer':
        await show_selyuk_type_farmer(update, context)
    elif data == 'selyuk_type_silkmaker':
        await show_selyuk_type_silkmaker(update, context)
    elif data == 'selyuk_type_trickster':
        await show_selyuk_type_trickster(update, context)
    elif data == 'selyuk_type_buyer':
        await show_selyuk_type_buyer(update, context)
    elif data == 'selyuk_type_boss':
        await show_selyuk_type_boss(update, context)
    elif data == 'selyuk_buy_farmer':
        await handle_selyuk_buy_farmer(update, context)
    elif data == 'selyuk_farmer_manage':
        await show_selyuk_farmer_manage(update, context)
    elif data == 'selyuk_farmer_settings':
        await show_selyuk_farmer_settings(update, context)
    elif data == 'selyuk_farmer_set_autow':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_auto_water')
    elif data == 'selyuk_farmer_set_autoh':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_auto_harvest')
    elif data == 'selyuk_farmer_set_autop':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_auto_plant')
    elif data == 'selyuk_farmer_set_autof':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_auto_fertilize')
    elif data == 'selyuk_farmer_set_silent':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_silent')
    elif data == 'selyuk_farmer_set_summary':
        await handle_selyuk_farmer_toggle_setting(update, context, 'farmer_summary_enabled')
    elif data == 'selyuk_farmer_summary_interval':
        await show_selyuk_farmer_summary_interval(update, context)
    elif data.startswith('selyuk_farmer_set_sumint_'):
        try:
            sec = int(data.split('_')[-1])
        except Exception:
            sec = 3600
        db.update_player(query.from_user.id, farmer_summary_interval_sec=max(300, sec))
        await show_selyuk_farmer_settings(update, context)
    elif data == 'selyuk_farmer_min_balance':
        await show_selyuk_farmer_min_balance(update, context)
    elif data.startswith('selyuk_farmer_set_minbal_'):
        try:
            v = int(data.split('_')[-1])
        except Exception:
            v = 0
        db.update_player(query.from_user.id, farmer_min_balance=max(0, v))
        await show_selyuk_farmer_settings(update, context)
    elif data == 'selyuk_farmer_daily_limit':
        await show_selyuk_farmer_daily_limit(update, context)
    elif data.startswith('selyuk_farmer_set_dlim_'):
        try:
            v = int(data.split('_')[-1])
        except Exception:
            v = 0
        db.update_player(query.from_user.id, farmer_daily_limit=max(0, v))
        await show_selyuk_farmer_settings(update, context)
    elif data == 'selyuk_farmer_seed_settings':
        await show_selyuk_farmer_seed_settings(update, context)
    elif data == 'selyuk_farmer_seed_mode_any':
        db.update_player(query.from_user.id, farmer_seed_mode='any')
        await show_selyuk_farmer_seed_settings(update, context)
    elif data == 'selyuk_farmer_seed_mode_whitelist':
        db.update_player(query.from_user.id, farmer_seed_mode='whitelist')
        await show_selyuk_farmer_seed_settings(update, context)
    elif data == 'selyuk_farmer_seed_mode_blacklist':
        db.update_player(query.from_user.id, farmer_seed_mode='blacklist')
        await show_selyuk_farmer_seed_settings(update, context)
    elif data.startswith('selyuk_farmer_seed_list_'):
        try:
            page = int(data.split('_')[-1])
        except Exception:
            page = 0
        await show_selyuk_farmer_seed_list(update, context, page)
    elif data.startswith('selyuk_farmer_seed_prio_'):
        try:
            page = int(data.split('_')[-1])
        except Exception:
            page = 0
        await show_selyuk_farmer_seed_priority(update, context, page)
    elif data.startswith('selyuk_farmer_seed_tgl_'):
        # selyuk_farmer_seed_tgl_{seed_id}_{page}
        parts = data.split('_')
        try:
            seed_id = int(parts[-2])
            page = int(parts[-1])
        except Exception:
            seed_id = 0
            page = 0
        player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
        seed_ids, prio_ids = _farmer_seed_lists_from_player(player)
        if seed_id > 0:
            if seed_id in set(seed_ids):
                seed_ids = [x for x in seed_ids if x != seed_id]
                prio_ids = [x for x in prio_ids if x != seed_id]
            else:
                seed_ids.append(seed_id)
        db.update_player(query.from_user.id, farmer_seed_ids=json.dumps(seed_ids), farmer_seed_priority=json.dumps(prio_ids))
        await show_selyuk_farmer_seed_list(update, context, page)
    elif data.startswith('selyuk_farmer_prio_add_'):
        # selyuk_farmer_prio_add_{seed_id}_{page}
        parts = data.split('_')
        try:
            seed_id = int(parts[-2])
            page = int(parts[-1])
        except Exception:
            seed_id = 0
            page = 0
        player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
        seed_ids, prio_ids = _farmer_seed_lists_from_player(player)
        if seed_id > 0 and seed_id not in set(prio_ids):
            prio_ids.append(seed_id)
        if seed_id > 0 and seed_id not in set(seed_ids):
            seed_ids.append(seed_id)
        db.update_player(query.from_user.id, farmer_seed_ids=json.dumps(seed_ids), farmer_seed_priority=json.dumps(prio_ids))
        await show_selyuk_farmer_seed_priority(update, context, page)
    elif data.startswith('selyuk_farmer_prio_rm_'):
        # selyuk_farmer_prio_rm_{seed_id}_{page}
        parts = data.split('_')
        try:
            seed_id = int(parts[-2])
            page = int(parts[-1])
        except Exception:
            seed_id = 0
            page = 0
        player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
        seed_ids, prio_ids = _farmer_seed_lists_from_player(player)
        if seed_id > 0:
            prio_ids = [x for x in prio_ids if x != seed_id]
        db.update_player(query.from_user.id, farmer_seed_priority=json.dumps(prio_ids))
        await show_selyuk_farmer_seed_priority(update, context, page)
    elif data.startswith('selyuk_farmer_fert_prio_add_'):
        parts = data.split('_')
        try:
            fert_id = int(parts[-2])
            page = int(parts[-1])
        except Exception:
            fert_id = 0
            page = 0
        player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
        prio_ids = _farmer_fert_priority_from_player(player)
        if fert_id > 0 and fert_id not in set(prio_ids):
            prio_ids.append(fert_id)
        db.update_player(query.from_user.id, farmer_fert_priority=json.dumps(prio_ids))
        await show_selyuk_farmer_fert_priority(update, context, page)
    elif data.startswith('selyuk_farmer_fert_prio_rm_'):
        parts = data.split('_')
        try:
            fert_id = int(parts[-2])
            page = int(parts[-1])
        except Exception:
            fert_id = 0
            page = 0
        player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
        prio_ids = _farmer_fert_priority_from_player(player)
        if fert_id > 0:
            prio_ids = [x for x in prio_ids if x != fert_id]
        db.update_player(query.from_user.id, farmer_fert_priority=json.dumps(prio_ids))
        await show_selyuk_farmer_fert_priority(update, context, page)
    elif data.startswith('selyuk_farmer_fert_prio_'):
        try:
            page = int(data.split('_')[-1])
        except Exception:
            page = 0
        await show_selyuk_farmer_fert_priority(update, context, page)
    elif data == 'selyuk_farmer_toggle':
        await handle_selyuk_farmer_toggle(update, context)
    elif data == 'selyuk_farmer_howto':
        await show_selyuk_farmer_howto(update, context)
    elif data == 'selyuk_farmer_upgrade':
        await show_selyuk_farmer_upgrade(update, context)
    elif data == 'selyuk_farmer_sell':
        await show_selyuk_farmer_sell(update, context)
    elif data.startswith('selyuk_farmer_topup_'):
        try:
            amt = int(data.split('_')[-1])
            await handle_selyuk_farmer_topup(update, context, amt)
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'rostov_elite_shop':
        await show_rostov_elite_shop(update, context)
    elif data == 'rostov_elite_items':
        await show_rostov_elite_items(update, context)
    elif data.startswith('rostov_elite_buy_'):
        key = data.replace('rostov_elite_buy_', '', 1)
        await handle_rostov_elite_buy(update, context, key)
    elif data in [
        'rostov_elite_boosters',
        'rostov_elite_themes',
        'rostov_elite_titles',
        'rostov_elite_collectibles',
        'rostov_elite_battlepass',
        'rostov_elite_cards',
    ]:
        await query.answer("⚙️ Раздел Магазина элиты в разработке!", show_alert=True)
    elif data == 'rostov_exchange':
        await show_rostov_exchange(update, context)
    elif data == 'rostov_exchange_sept_to_currency':
        await show_rostov_exchange_sept_to_currency(update, context)
    elif data == 'rostov_exchange_sept_to_resources':
        await show_rostov_exchange_sept_to_resources(update, context)
    elif data == 'rostov_exchange_sept_to_cards':
        await show_rostov_exchange_sept_to_cards(update, context)
    elif data == 'rostov_exchange_convert_resources':
        await show_rostov_exchange_convert_resources(update, context)
    elif data == 'rostov_exchange_resource_rates':
        await show_rostov_exchange_resource_rates(update, context)
    elif data == 'rostov_exchange_daily_deals':
        await show_rostov_exchange_daily_deals(update, context)
    elif data == 'rostov_exchange_bonuses':
        await show_rostov_exchange_bonuses(update, context)
    elif data == 'rostov_exchange_history':
        await show_rostov_exchange_history(update, context)
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
    elif data.startswith('silk_instant_grow_'):
        # silk_instant_grow_{plantation_id} or silk_instant_grow_all
        if data == 'silk_instant_grow_all':
            await silk_ui.handle_silk_instant_grow_all(update, context)
        else:
            try:
                plantation_id = int(data.split('_')[-1])
                await silk_ui.handle_silk_instant_grow(update, context, plantation_id)
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
    elif data == 'plantation_water':
        await show_plantation_water(update, context)
    elif data == 'plantation_stats':
        await show_plantation_stats(update, context)
    elif data == 'plantation_bed_prices':
        await show_plantation_bed_prices(update, context)
    elif data == 'plantation_buy_bed':
        await handle_plantation_buy_bed(update, context)
    elif data == 'plantation_join_project':
        await show_plantation_join_project(update, context)
    elif data == 'plantation_my_contribution':
        await show_plantation_my_contribution(update, context)
    elif data == 'plantation_water_all':
        await show_plantation_water_all(update, context)
    elif data == 'plantation_leaderboard':
        await show_plantation_leaderboard(update, context)
    elif data == 'casino_rules':
        await show_casino_rules(update, context)
    elif data == 'casino_achievements':
        await show_casino_achievements_page(update, context)
    elif data.startswith('casino_game_'):
        # casino_game_{game_type}
        try:
            game_type = data.replace('casino_game_', '')
            # Специальные игры обрабатываются отдельно
            if game_type == 'blackjack':
                await show_blackjack_bet_screen(update, context)
            elif game_type == 'mines':
                await show_mines_settings(update, context)
            elif game_type == 'crash':
                await show_crash_bet_screen(update, context)
            else:
                await show_casino_game(update, context, game_type)
        except Exception as e:
            logger.error(f"Error in casino_game: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('casino_choice_'):
        # casino_choice_{game_type}_{choice}
        try:
            parts = data.replace('casino_choice_', '').split('_', 1)
            game_type = parts[0]
            choice = parts[1]
            # Показываем экран выбора ставки
            player = db.get_or_create_player(update.callback_query.from_user.id, 
                                            update.callback_query.from_user.username or update.callback_query.from_user.first_name)
            coins = int(getattr(player, 'coins', 0) or 0)
            game_info = CASINO_GAMES.get(game_type, CASINO_GAMES['coin_flip'])
            await show_bet_selection_screen(update, context, game_type, game_info, coins, choice)
        except Exception as e:
            logger.error(f"Error in casino_choice: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('casino_bet_'):
        # casino_bet_{game_type}_{choice}_{amount}
        try:
            parts = data.replace('casino_bet_', '').rsplit('_', 1)
            amount = int(parts[1])
            # Разделяем game_type и choice
            game_and_choice = parts[0].rsplit('_', 1)
            if len(game_and_choice) == 2:
                game_type = game_and_choice[0]
                choice = game_and_choice[1]
                # Если choice='none', значит это слоты
                if choice == 'none':
                    choice = None
            else:
                # Для слотов нет choice
                game_type = parts[0]
                choice = None
            await play_casino_game(update, context, game_type, choice, amount)
        except Exception as e:
            logger.error(f"Error in casino_bet: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('casino_play_'):
        # casino_play_{game_type}_{amount} - старый формат для слотов
        try:
            parts = data.replace('casino_play_', '').rsplit('_', 1)
            game_type = parts[0]
            amount = int(parts[1])
            await play_casino_game(update, context, game_type, None, amount)
        except Exception as e:
            logger.error(f"Error in casino_play: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    # --- Блэкджек ---
    elif data == 'casino_game_blackjack':
        await show_blackjack_bet_screen(update, context)
    elif data.startswith('blackjack_bet_'):
        # blackjack_bet_{amount}
        try:
            amount = int(data.replace('blackjack_bet_', ''))
            await start_blackjack_game(update, context, amount)
        except Exception as e:
            logger.error(f"Error in blackjack_bet: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'blackjack_hit':
        await handle_blackjack_hit(update, context)
    elif data == 'blackjack_stand':
        await handle_blackjack_stand(update, context)
    elif data == 'blackjack_double':
        await handle_blackjack_double(update, context)
    elif data == 'blackjack_surrender':
        await handle_blackjack_surrender(update, context)
    # --- Мины ---
    elif data == 'casino_game_mines':
        await show_mines_settings(update, context)
    elif data.startswith('mines_count_'):
        try:
            mines_count = int(data.replace('mines_count_', ''))
            await show_mines_bet_screen(update, context, mines_count)
        except Exception as e:
            logger.error(f"Error in mines_count: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('mines_bet_'):
        # mines_bet_{mines_count}_{amount}
        try:
            parts = data.replace('mines_bet_', '').split('_')
            mines_count = int(parts[0])
            amount = int(parts[1])
            await start_mines_game(update, context, mines_count, amount)
        except Exception as e:
            logger.error(f"Error in mines_bet: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('mines_click_'):
        try:
            cell_idx = int(data.replace('mines_click_', ''))
            await handle_mines_click(update, context, cell_idx)
        except Exception as e:
            logger.error(f"Error in mines_click: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'mines_cashout':
        await handle_mines_cashout(update, context)
    elif data == 'mines_forfeit':
        await handle_mines_forfeit(update, context)
    elif data == 'mines_noop':
        await update.callback_query.answer()
    # --- Краш ---
    elif data == 'casino_game_crash':
        await show_crash_bet_screen(update, context)
    elif data.startswith('crash_bet_'):
        try:
            amount = int(data.replace('crash_bet_', ''))
            await start_crash_game(update, context, amount)
        except Exception as e:
            logger.error(f"Error in crash_bet: {e}")
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data == 'crash_cashout':
        await handle_crash_cashout(update, context)
    elif data.startswith('plantation_buy_'):
        # plantation_buy_{seed_id}_{qty}
        try:
            _, _, sid, qty = data.split('_')
            await handle_plantation_buy(update, context, int(sid), int(qty))
        except Exception:
            await update.callback_query.answer('Ошибка', show_alert=True)
    elif data.startswith('fert_filter_'):
        # fert_filter_{category}
        try:
            category = data.split('_')[-1]
            await show_plantation_fertilizers_shop(update, context, filter_category=category)
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
    elif data == 'vip_plus_menu':
        await show_vip_plus_menu(update, context)
    elif data == 'vip_1d':
        await show_vip_1d(update, context)
    elif data == 'vip_7d':
        await show_vip_7d(update, context)
    elif data == 'vip_30d':
        await show_vip_30d(update, context)
    elif data == 'vip_plus_1d':
        await show_vip_plus_1d(update, context)
    elif data == 'vip_plus_7d':
        await show_vip_plus_7d(update, context)
    elif data == 'vip_plus_30d':
        await show_vip_plus_30d(update, context)
    elif data == 'buy_vip_1d':
        await buy_vip(update, context, '1d')
    elif data == 'buy_vip_7d':
        await buy_vip(update, context, '7d')
    elif data == 'buy_vip_30d':
        await buy_vip(update, context, '30d')
    elif data == 'confirm_vip_plus_1d':
        await confirm_vip_plus_purchase(update, context, '1d')
    elif data == 'confirm_vip_plus_7d':
        await confirm_vip_plus_purchase(update, context, '7d')
    elif data == 'confirm_vip_plus_30d':
        await confirm_vip_plus_purchase(update, context, '30d')
    elif data == 'buy_vip_plus_1d':
        await buy_vip_plus(update, context, '1d')
    elif data == 'buy_vip_plus_7d':
        await buy_vip_plus(update, context, '7d')
    elif data == 'buy_vip_plus_30d':
        await buy_vip_plus(update, context, '30d')
    elif data == 'stars_menu':
        await show_stars_menu(update, context)
    elif data == 'stars_500':
        await show_stars_500(update, context)
    elif data == 'noop':
        # Заглушка для неактивных кнопок (например, пагинации на крайних страницах)
        await query.answer()
    elif data == 'my_receipts':
        await my_receipts_handler(update, context)
    elif data == 'sell_all_confirm_1':
        await receiver_sell_all_confirm_1(update, context)
    elif data == 'sell_all_confirm_2':
        await receiver_sell_all_confirm_2(update, context)
    elif data == 'sell_all_execute':
        await handle_sell_all_inventory(update, context)
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
    elif data == 'sell_absolutely_all_but_one':
        await handle_sell_absolutely_all_but_one(update, context)
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
    elif data == 'settings_plantation_reminder':
        await toggle_plantation_reminder(update, context)
    elif data == 'settings_auto':
        await toggle_auto_search(update, context)
    elif data == 'settings_autosell':
        await show_autosell_menu(update, context)
    elif data.startswith('autosell_toggle_'):
        rarity = data.removeprefix('autosell_toggle_')
        await toggle_autosell_rarity(update, context, rarity)
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
    elif data == 'group_toggle_notify':
        await toggle_group_notifications(update, context)
    elif data == 'group_toggle_delete':
        await toggle_group_auto_delete(update, context)
    elif data.startswith('gift_page_'):
        # Навигация по страницам выбора подарка
        try:
            page = int(data.split('_')[-1])
            await send_gift_selection_menu(
                context, 
                query.from_user.id, 
                page=page, 
                message_id=query.message.message_id
            )
            await query.answer()
        except Exception:
            await query.answer("Ошибка навигации", show_alert=True)
    elif data == 'gift_page_info':
        # Информационная кнопка - ничего не делает
        await query.answer("Текущая страница", show_alert=False)
    elif data == 'gift_search':
        # Начать поиск напитка
        state = GIFT_SELECTION_STATE.get(query.from_user.id)
        if state:
            state['awaiting_search'] = True
            state['search_message_id'] = query.message.message_id
            await query.answer()
            await query.edit_message_text(
                "🔍 <b>Поиск напитка</b>\n\n"
                "Введите название напитка (или его часть):",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отменить поиск", callback_data="gift_cancel_search")]
                ])
            )
        else:
            await query.answer("Сессия истекла", show_alert=True)
    elif data == 'gift_cancel_search':
        # Отменить поиск и вернуться к списку
        state = GIFT_SELECTION_STATE.get(query.from_user.id)
        if state:
            state['awaiting_search'] = False
            await send_gift_selection_menu(
                context, 
                query.from_user.id, 
                page=1, 
                message_id=query.message.message_id
            )
            await query.answer("Поиск отменён")
        else:
            await query.answer("Сессия истекла", show_alert=True)
    elif data == 'gift_cancel':
        # Полностью отменить выбор подарка
        user_id = query.from_user.id
        if user_id in GIFT_SELECTION_STATE:
            del GIFT_SELECTION_STATE[user_id]
        await query.edit_message_text("❌ Выбор подарка отменён.")
        await query.answer()
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
    if len(args) < 3:
        await update.message.reply_text("Использование: /editdrink <drink_id> <name|description> <new_value>")
        return
    m = re.search(r"\d+", str(args[0]))
    if not m:
        await update.message.reply_text("Использование: /editdrink <drink_id> <name|description> <new_value>")
        return
    drink_id = int(m.group(0))
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
    args = context.args or []
    if not args:
        await update.message.reply_text("Использование: /delrequest <drink_id> [причина]")
        return
    m = re.search(r"\d+", str(args[0]))
    if not m:
        await update.message.reply_text("Использование: /delrequest <drink_id> [причина]")
        return
    drink_id = int(m.group(0))
    reason = " ".join(args[1:]).strip() if len(args) > 1 else None
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
    if len(args) < 3:
        await update.message.reply_text("Использование: /inceditdrink <drink_id> <name|description> <new_value>")
        return
    m = re.search(r"\d+", str(args[0]))
    if not m:
        await update.message.reply_text("Использование: /inceditdrink <drink_id> <name|description> <new_value>")
        return
    drink_id = int(m.group(0))
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
    args = context.args or []
    if not args:
        await update.message.reply_text("Использование: /incdelrequest <drink_id> [причина]")
        return
    m = re.search(r"\d+", str(args[0]))
    if not m:
        await update.message.reply_text("Использование: /incdelrequest <drink_id> [причина]")
        return
    drink_id = int(m.group(0))
    reason = " ".join(args[1:]).strip() if len(args) > 1 else None
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
    try:
        skip_ids = context.chat_data.setdefault('_skip_text_message_ids', set())
        skip_ids.add(int(msg.message_id))
    except Exception:
        pass
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


# --- Функции для работы с правами создателя группы ---

async def is_group_creator(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """Проверяет, является ли пользователь создателем группы."""
    try:
        logger.info(f"[GROUPSETTINGS] Checking creator permissions: user_id={user_id} chat_id={chat_id}")
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        is_creator = chat_member.status == 'creator'
        logger.info(f"[GROUPSETTINGS] Permission check result: user_id={user_id} chat_id={chat_id} status={chat_member.status} is_creator={is_creator}")
        return is_creator
    except Exception as e:
        logger.warning(f"[GROUPSETTINGS] Не удалось проверить права создателя для пользователя {user_id} в чате {chat_id}: {e}")
        return False

async def check_group_creator_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет права создателя группы для текущего пользователя и чата.
    Возвращает True если пользователь является создателем группы.
    """
    chat = update.effective_chat
    user = update.effective_user
    
    if not chat or chat.type not in ("group", "supergroup"):
        return False
    
    return await is_group_creator(context, chat.id, user.id)


async def check_bot_admin_rights(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> dict:
    """Проверяет права бота в группе.
    Возвращает словарь с информацией о правах.
    """
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        is_admin = bot_member.status in ('administrator', 'creator')
        can_delete = getattr(bot_member, 'can_delete_messages', False) if is_admin else False
        
        return {
            'is_admin': is_admin,
            'can_delete_messages': can_delete,
            'status': bot_member.status
        }
    except Exception as e:
        logger.warning(f"[BOT_RIGHTS] Failed to check bot rights in chat {chat_id}: {e}")
        return {
            'is_admin': False,
            'can_delete_messages': False,
            'status': 'unknown'
        }


async def notify_creator_about_missing_rights(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Отправляет предупреждение создателю группы о недостающих правах бота."""
    try:
        # Получаем создателя группы
        admins = await context.bot.get_chat_administrators(chat_id)
        creator = None
        for admin in admins:
            if admin.status == 'creator':
                creator = admin.user
                break
        
        if not creator:
            return
        
        warning_text = (
            "⚠️ <b>Внимание!</b>\n\n"
            "Бот не имеет прав администратора в вашей группе.\n"
            "Для корректной работы автоудаления сообщений необходимо:\n\n"
            "1. Сделать бота администратором группы\n"
            "2. Выдать право <b>\"Удаление сообщений\"</b>\n\n"
            "Без этих прав функция автоудаления работать не будет."
        )
        
        # Отправляем предупреждение создателю в личку
        try:
            await context.bot.send_message(
                chat_id=creator.id,
                text=warning_text,
                parse_mode='HTML'
            )
            logger.info(f"[BOT_RIGHTS] Sent warning to creator {creator.id} about missing rights in chat {chat_id}")
        except Exception as e:
            logger.warning(f"[BOT_RIGHTS] Failed to send warning to creator {creator.id}: {e}")
            # Если не можем отправить в личку, попробуем в группе
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning_text,
                    parse_mode='HTML'
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[BOT_RIGHTS] Error notifying creator about missing rights: {e}")


async def send_auto_delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Отправляет сообщение и автоматически планирует его удаление, если включено в настройках группы."""
    try:
        sent_message = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        
        # Проверяем, является ли это групповым чатом и включено ли автоудаление
        settings = db.get_group_settings(chat_id)
        if settings.get('auto_delete_enabled', False):
            delay = settings.get('auto_delete_delay_minutes', 5)
            await schedule_auto_delete_message(context, chat_id, sent_message.message_id, delay)
        
        return sent_message
    except Exception as e:
        logger.error(f"[AUTO_DELETE] Error sending message to {chat_id}: {e}")
        raise


async def reply_auto_delete_message(message, text: str, context: ContextTypes.DEFAULT_TYPE = None, **kwargs):
    """Отвечает на сообщение и автоматически планирует удаление ответа, если включено в настройках группы."""
    try:
        sent_message = await message.reply_text(text, **kwargs)
        
        if context:
            # Проверяем, является ли это групповым чатом и включено ли автоудаление
            chat_id = message.chat_id
            settings = db.get_group_settings(chat_id)
            if settings.get('auto_delete_enabled', False):
                delay = settings.get('auto_delete_delay_minutes', 5)
                await schedule_auto_delete_message(context, chat_id, sent_message.message_id, delay)
        
        return sent_message
    except Exception as e:
        logger.error(f"[AUTO_DELETE] Error replying to message: {e}")
        raise


async def schedule_auto_delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay_minutes: int = 5):
    """Планирует автоудаление сообщения, если в группе включено автоудаление."""
    try:
        # Проверяем, включено ли автоудаление в этой группе
        settings = db.get_group_settings(chat_id)
        if not settings.get('auto_delete_enabled', False):
            return
        
        # Вычисляем время удаления
        delete_at = int(time.time()) + (delay_minutes * 60)
        
        # Сохраняем задачу в БД для восстановления после перезапуска
        scheduled_id = db.save_scheduled_auto_delete(chat_id, message_id, delete_at)
        
        # Планируем задачу удаления
        job_name = f"auto_delete_{chat_id}_{message_id}"
        context.application.job_queue.run_once(
            auto_delete_message_job,
            when=delay_minutes * 60,  # Преобразуем минуты в секунды
            data={'chat_id': chat_id, 'message_id': message_id, 'scheduled_id': scheduled_id},
            name=job_name
        )
        
        # Сохраняем ссылку на сообщение в глобальном словаре
        AUTO_DELETE_MESSAGES[job_name] = {
            'chat_id': chat_id,
            'message_id': message_id,
            'scheduled_at': time.time(),
            'scheduled_id': scheduled_id
        }
        
        logger.info(f"[AUTO_DELETE] Scheduled deletion for message {message_id} in chat {chat_id} in {delay_minutes} minutes (DB ID: {scheduled_id})")
    except Exception as e:
        logger.warning(f"[AUTO_DELETE] Failed to schedule auto-delete for message {message_id} in chat {chat_id}: {e}")


async def auto_delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача для автоудаления сообщения."""
    try:
        job_data = context.job.data
        chat_id = job_data['chat_id']
        message_id = job_data['message_id']
        scheduled_id = job_data.get('scheduled_id')
        
        # Проверяем, что автоудаление всё ещё включено
        settings = db.get_group_settings(chat_id)
        if not settings.get('auto_delete_enabled', False):
            logger.info(f"[AUTO_DELETE] Auto-delete disabled for chat {chat_id}, skipping message {message_id}")
            # Удаляем из БД даже если автоудаление выключено
            if scheduled_id:
                db.delete_scheduled_auto_delete(scheduled_id)
            return
        
        # Пытаемся удалить сообщение
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"[AUTO_DELETE] Successfully deleted message {message_id} from chat {chat_id}")
        except BadRequest as e:
            if "Message to delete not found" in str(e):
                logger.info(f"[AUTO_DELETE] Message {message_id} in chat {chat_id} already deleted")
            else:
                logger.warning(f"[AUTO_DELETE] Failed to delete message {message_id} from chat {chat_id}: {e}")
        except Exception as e:
            logger.warning(f"[AUTO_DELETE] Error deleting message {message_id} from chat {chat_id}: {e}")
        
        # Удаляем запись из БД после выполнения
        if scheduled_id:
            db.delete_scheduled_auto_delete(scheduled_id)
            logger.debug(f"[AUTO_DELETE] Removed scheduled task {scheduled_id} from database")
        
    except Exception as e:
        logger.error(f"[AUTO_DELETE] Error in auto_delete_message_job: {e}")
    finally:
        # Удаляем запись из словаря
        job_name = context.job.name
        if job_name and job_name in AUTO_DELETE_MESSAGES:
            del AUTO_DELETE_MESSAGES[job_name]


async def restore_scheduled_auto_deletes(application):
    """Восстанавливает запланированные задачи автоудаления из БД при запуске бота."""
    try:
        logger.info("[AUTO_DELETE] Restoring scheduled auto-delete tasks from database...")
        
        # Получаем все запланированные задачи
        scheduled_tasks = db.get_all_scheduled_auto_deletes()
        
        if not scheduled_tasks:
            logger.info("[AUTO_DELETE] No scheduled tasks to restore")
            return
        
        current_time = int(time.time())
        restored_count = 0
        expired_count = 0
        
        for scheduled_id, chat_id, message_id, delete_at in scheduled_tasks:
            # Проверяем, не истекло ли время удаления
            if delete_at <= current_time:
                # Время удаления уже прошло - удаляем сразу
                try:
                    await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    logger.info(f"[AUTO_DELETE] Deleted expired message {message_id} from chat {chat_id}")
                except Exception as e:
                    logger.debug(f"[AUTO_DELETE] Could not delete expired message {message_id}: {e}")
                
                # Удаляем из БД
                db.delete_scheduled_auto_delete(scheduled_id)
                expired_count += 1
            else:
                # Задача еще актуальна - восстанавливаем
                delay_seconds = delete_at - current_time
                
                # Проверяем, включено ли автоудаление в группе
                settings = db.get_group_settings(chat_id)
                if not settings.get('auto_delete_enabled', False):
                    # Автоудаление выключено - удаляем задачу
                    db.delete_scheduled_auto_delete(scheduled_id)
                    logger.debug(f"[AUTO_DELETE] Skipped task {scheduled_id} - auto-delete disabled for chat {chat_id}")
                    continue
                
                # Планируем задачу
                job_name = f"auto_delete_{chat_id}_{message_id}"
                application.job_queue.run_once(
                    auto_delete_message_job,
                    when=delay_seconds,
                    data={'chat_id': chat_id, 'message_id': message_id, 'scheduled_id': scheduled_id},
                    name=job_name
                )
                
                AUTO_DELETE_MESSAGES[job_name] = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'scheduled_at': time.time(),
                    'scheduled_id': scheduled_id
                }
                
                restored_count += 1
                logger.debug(f"[AUTO_DELETE] Restored task {scheduled_id} for message {message_id} (delete in {delay_seconds}s)")
        
        logger.info(f"[AUTO_DELETE] Restored {restored_count} tasks, processed {expired_count} expired tasks")
        
        # Очистка устаревших записей (старше 24 часов)
        db.cleanup_old_scheduled_deletes()
        
    except Exception as e:
        logger.error(f"[AUTO_DELETE] Error restoring scheduled tasks: {e}")
        import traceback
        traceback.print_exc()


async def groupsettings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/groupsettings — открывает настройки группы (только для создателей групп)."""
    await register_group_if_needed(update)

    message = update.message
    chat = update.effective_chat
    
    # 1. Проверяем, что это группа
    if not chat or chat.type not in ("group", "supergroup"):
        await message.reply_text(t('ru', 'group_only_command'))
        return

    # 2. Получаем реального пользователя, отправившего команду.
    #    Это работает и для обычных пользователей, и для анонимных админов.
    user_to_check = message.from_user
    if not user_to_check:
        logger.warning("[GROUPSETTINGS] Не удалось определить пользователя из сообщения в чате %s", chat.id)
        return

    # 3. Передаем этого пользователя в функцию отображения настроек
    await show_group_settings(update, context, user_to_check)


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


async def addp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления плантационного энергетика (только для админов)."""
    user = update.effective_user
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав: команда доступна только администраторам.")
        return ConversationHandler.END

    await update.message.reply_text("Введите название плантационного энергетика:")
    context.user_data.clear()
    return ADDP_NAME


async def addp_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("Введите описание плантационного энергетика:")
    return ADDP_DESCRIPTION


async def addp_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text.strip()
    await update.message.reply_text("Пришлите фото плантационного энергетика или отправьте /skip, чтобы пропустить:")
    return ADDP_PHOTO


async def addp_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data['file_id'] = photo_file.file_id
    else:
        context.user_data['file_id'] = None
    return await finalize_addp(update, context)


async def skip_addp_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['file_id'] = None
    return await finalize_addp(update, context)


async def finalize_addp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальный этап: добавление плантационного энергетика (P-серия)."""
    user = update.effective_user
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав: команда доступна только администраторам.")
        return ConversationHandler.END

    data = context.user_data
    name = data.get('name', '').strip()
    
    # Проверка на дубликат названия
    existing = db.get_drink_by_name(name)
    if existing:
        await update.message.reply_text("❌ Энергетик с таким названием уже существует!")
        return ConversationHandler.END
    
    image_path = None
    if data.get('file_id'):
        try:
            file = await context.bot.get_file(data['file_id'])
            os.makedirs(ENERGY_IMAGES_DIR, exist_ok=True)
            image_path = f"{int(time.time())}_{random.randint(1000,9999)}.jpg"
            await file.download_to_drive(os.path.join(ENERGY_IMAGES_DIR, image_path))
        except Exception:
            image_path = None

    drink = db.add_energy_drink(
        name=name,
        description=data.get('description', '').strip(),
        image_path=image_path,
        is_special=False,
        is_plantation=True,
    )

    p_index = getattr(drink, 'plantation_index', None)
    if p_index:
        await update.message.reply_text(f"🌿 Плантационный энергетик успешно добавлен! Его P-ID: P{p_index}")
    else:
        await update.message.reply_text("🌿 Плантационный энергетик успешно добавлен!")

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


async def pid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pid — показать соответствие P-ID -> название плантационного энергетика (только админы, только ЛС)."""
    user = update.effective_user
    chat = update.effective_chat
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return
    if chat.type != 'private':
        await update.message.reply_text("Эта команда доступна только в личных сообщениях боту.")
        return

    drinks = db.get_plantation_drinks()
    if not drinks:
        await update.message.reply_text("В базе данных нет плантационных энергетиков.")
        return

    drinks_sorted = sorted(drinks, key=lambda d: (getattr(d, 'plantation_index', 0) or 0, d.id))
    lines = []
    for d in drinks_sorted:
        p_index = getattr(d, 'plantation_index', None)
        p_id = f"P{p_index}" if p_index else f"P? (id {d.id})"
        lines.append(f"{p_id}: {d.name}")

    header = f"Всего плантационных энергетиков: {len(lines)}\n"
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

    # Разрешение пользователя через единый поиск
    if target_id is None:
        ident = f"@{target_username}" if target_username else None
        res = db.find_player_by_identifier(ident)
        if res.get('reason') == 'multiple':
            lines = ["Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            await update.message.reply_text("\n".join(lines))
            return
        if res.get('ok') and res.get('player'):
            target_id = int(res['player'].user_id)
            if not target_username:
                target_username = getattr(res['player'], 'username', None)
        else:
            await update.message.reply_text("Не удалось определить пользователя по указанному идентификатору/username.")
            return

    new_balance = db.increment_coins(target_id, amount)
    if new_balance is None:
        await update.message.reply_text("Не удалось обновить баланс. Попробуйте позже.")
        return

    # Логируем транзакцию
    try:
        target_player = db.get_or_create_player(target_id, target_username or str(target_id))
        db.log_action(
            user_id=target_id,
            username=getattr(target_player, 'username', None) or target_username or str(target_id),
            action_type='transaction',
            action_details=f'Команда /addcoins: выдано админом @{user.username or user.first_name}',
            amount=amount,
            success=True
        )
    except Exception:
        pass

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

    # Разрешение пользователя через единый поиск
    if target_id is None:
        ident = f"@{target_username}" if target_username else None
        res = db.find_player_by_identifier(ident)
        if res.get('reason') == 'multiple':
            lines = ["Найдено несколько пользователей, уточните запрос:"]
            for c in (res.get('candidates') or []):
                cu = c.get('username')
                lines.append(f"- @{cu} (ID: {c.get('user_id')})" if cu else f"- ID: {c.get('user_id')}")
            await update.message.reply_text("\n".join(lines))
            return
        if res.get('ok') and res.get('player'):
            target_id = int(res['player'].user_id)
            if not target_username:
                target_username = getattr(res['player'], 'username', None)
        else:
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

    # Логируем транзакцию
    try:
        target_player = db.get_or_create_player(target_id, target_username or str(target_id))
        removed_amount = result.get('removed_amount', amount)
        db.log_action(
            user_id=target_id,
            username=getattr(target_player, 'username', None) or target_username or str(target_id),
            action_type='transaction',
            action_details=f'Команда /delmoney: убрано админом @{user.username or user.first_name}',
            amount=-removed_amount,
            success=True
        )
    except Exception:
        pass

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
    plantation_reminder_state = t(lang, 'on') if getattr(player, 'remind_plantation', False) else t(lang, 'off')
    auto_state = t(lang, 'on') if getattr(player, 'auto_search_enabled', False) else t(lang, 'off')
    # Считаем автопродажу включённой, если хотя бы одна редкость включена
    try:
        autosell_settings = db.get_autosell_settings(user_id)
        autosell_enabled = any(bool(v) for v in autosell_settings.values())
    except Exception:
        autosell_enabled = False
    autosell_state = t(lang, 'on') if autosell_enabled else t(lang, 'off')

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
        f"<b>{t(lang, 'settings_title')}</b>\n\n"\
        f"{t(lang, 'current_language')}: {lang_readable}\n"\
        f"{t(lang, 'auto_reminder')}: {reminder_state}\n"\
        f"{t(lang, 'plantation_reminder')}: {plantation_reminder_state}\n"\
        f"{t(lang, 'auto_search')}: {auto_state}\n"\
        f"{t(lang, 'autosell')}: {autosell_state}\n"\
    )

    if reset_info:
        text += reset_info

    keyboard = [
        [InlineKeyboardButton(t(lang, 'btn_change_lang'), callback_data='settings_lang')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_rem'), callback_data='settings_reminder')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_plantation_rem'), callback_data='settings_plantation_reminder')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_auto'), callback_data='settings_auto')],
        [InlineKeyboardButton(t(lang, 'autosell'), callback_data='settings_autosell')],
        [InlineKeyboardButton(t(lang, 'btn_reset'), callback_data='settings_reset')],
        [InlineKeyboardButton(t(lang, 'btn_back'), callback_data='menu')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.message
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        return

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest as e:
        if 'not modified' in str(e).lower():
            try:
                await query.answer()
            except Exception:
                pass
        else:
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
            except Exception:
                pass

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

    await show_settings(update, context)

async def restore_plantation_reminders(application):
    """Восстанавливает напоминания о поливе после рестарта."""
    try:
        active_beds = db.get_all_active_beds_for_reminders()
        count = 0
        now_ts = int(time.time())
        
        for bed in active_beds:
            user_id = bed['user_id']
            bed_index = bed['bed_index']
            next_water_ts = bed['next_water_ts']
            
            # Вычисляем задержку
            delay = next_water_ts - now_ts
            # Если время уже прошло, ставим небольшую задержку, чтобы сработало сразу
            if delay < 0:
                delay = 1
            
            try:
                # Удаляем старые на всякий случай
                jobs = application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user_id}_{bed_index}")
                for j in jobs:
                    j.schedule_removal()
                
                application.job_queue.run_once(
                    plantation_water_reminder_job,
                    when=delay,
                    chat_id=user_id,
                    data={'bed_index': bed_index},
                    name=f"plantation_water_reminder_{user_id}_{bed_index}",
                )
                count += 1
            except Exception as e:
                logger.warning(f"[PLANTATION] Failed to restore reminder for user {user_id} bed {bed_index}: {e}")
                
        if count > 0:
            logger.info(f"[PLANTATION] Restored {count} watering reminders")
            
    except Exception as e:
        logger.error(f"[PLANTATION] Error restoring reminders: {e}")

async def toggle_plantation_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = db.get_or_create_player(query.from_user.id, query.from_user.username or query.from_user.first_name)
    new_state = not getattr(player, 'remind_plantation', False)
    db.update_player(player.user_id, remind_plantation=new_state)
    
    # Smart Toggle Logic
    user_id = player.user_id
    if new_state:
        # Включили: нужно найти все растущие грядки и запланировать напоминания
        try:
            # Получаем активные грядки и фильтруем по текущему пользователю
            active_beds = db.get_all_active_beds_for_reminders()
            my_beds = [b for b in active_beds if b['user_id'] == user_id]
            
            now_ts = int(time.time())
            for bed in my_beds:
                bed_index = bed['bed_index']
                next_water_ts = bed['next_water_ts']
                delay = max(1, next_water_ts - now_ts)
                
                context.application.job_queue.run_once(
                    plantation_water_reminder_job,
                    when=delay,
                    chat_id=user_id,
                    data={'bed_index': bed_index},
                    name=f"plantation_water_reminder_{user_id}_{bed_index}",
                )
            logger.info(f"[PLANTATION] Enabled reminders for user {user_id}, scheduled {len(my_beds)} jobs")
            
        except Exception as e:
            logger.error(f"[PLANTATION] Error scheduling reminders on toggle: {e}")
            
    else:
        # Выключили: найти и удалить все задачи напоминаний для этого юзера
        try:
            # Мы не знаем индексы грядок наверняка без запроса, но можем попробовать удалить по маске имени?
            # job_queue не поддерживает удаление по маске.
            # Придется перебрать возможные индексы (например 1..10)
            for i in range(1, 20):
                jobs = context.application.job_queue.get_jobs_by_name(f"plantation_water_reminder_{user_id}_{i}")
                for j in jobs:
                    j.schedule_removal()
            logger.info(f"[PLANTATION] Disabled reminders for user {user_id}, cancelled jobs")
        except Exception as e:
            logger.error(f"[PLANTATION] Error cancelling reminders on toggle: {e}")

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
        except Exception as e:
            logger.warning(f"[AUTO] Не удалось удалить предыдущие задачи автопоиска для {user_id}: {e}")
        try:
            context.application.job_queue.run_once(
                auto_search_job,
                when=1,
                chat_id=user_id,
                name=f"auto_search_{user_id}",
            )
            logger.debug(f"[AUTO] Автопоиск включён и запланирована задача для {user_id}")
        except Exception as e:
            logger.error(f"[AUTO] Критическая ошибка: не удалось запланировать автопоиск для {user_id}: {e}")
        try:
            current_limit = db.get_auto_search_daily_limit(user_id)
            await context.bot.send_message(chat_id=user_id, text=t(lang, 'auto_enabled').format(limit=current_limit))
        except Exception:
            pass
    else:
        # Выключаем
        
        # Если был включен тихий режим, отправим сводку перед выключением
        if getattr(player, 'auto_search_silent', False):
            await _send_auto_search_summary(user_id, player, context, reason='disabled')

        db.update_player(user_id, auto_search_enabled=False)
        try:
            jobs = context.application.job_queue.get_jobs_by_name(f"auto_search_{user_id}")
            for j in jobs:
                j.schedule_removal()
        except Exception:
            pass
        await query.answer(t(lang, 'auto_disabled'), show_alert=True)
    
    await show_settings(update, context)


async def show_autosell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    player = db.get_or_create_player(user_id, query.from_user.username or query.from_user.first_name)
    lang = player.language

    settings = db.get_autosell_settings(user_id)

    lines = [t(lang, 'autosell_title'), '', t(lang, 'autosell_desc'), '']

    rarities_order = ['Basic', 'Medium', 'Elite', 'Absolute', 'Majestic', 'Special']
    for r in rarities_order:
        emoji = COLOR_EMOJIS.get(r, '⚪')
        state = t(lang, 'on') if settings.get(r, False) else t(lang, 'off')
        lines.append(f"{emoji} {r}: {state}")

    text = "\n".join(lines)

    keyboard_rows = []
    for r in rarities_order:
        emoji = COLOR_EMOJIS.get(r, '⚪')
        state = t(lang, 'on') if settings.get(r, False) else t(lang, 'off')
        btn_text = f"{emoji} {r}: {state}"
        callback = f"autosell_toggle_{r}"
        keyboard_rows.append([InlineKeyboardButton(btn_text, callback_data=callback)])

    keyboard_rows.append([InlineKeyboardButton(t(lang, 'btn_back'), callback_data='settings')])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode='HTML')


async def toggle_autosell_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    current = db.is_autosell_enabled(user_id, rarity)
    db.set_autosell_enabled(user_id, rarity, not current)
    await show_autosell_menu(update, context)

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


# --- Функции для групповых настроек ---

async def show_group_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, user_to_check: User):
    """Отображает меню настроек группы (только для создателей)."""
    query = update.callback_query
    if query:
        await query.answer()
    
    chat = update.effective_chat
    
    # Проверяем права переданного пользователя
    is_creator = await is_group_creator(context, chat.id, user_to_check.id)
    
    logger.info(
        "[SHOW_GROUP_SETTINGS] Creator check for user %s in chat %s. Result: %s",
        user_to_check.id, chat.id, is_creator
    )

    if not is_creator:
        error_msg = t('ru', 'group_access_denied')
        if query:
            # Если это был клик по кнопке, отвечаем на него
            await query.answer(error_msg, show_alert=True)
            # И пытаемся отредактировать сообщение, если возможно
            try:
                await query.edit_message_text(error_msg)
            except BadRequest:
                pass
        else:
            # Если это была команда, отвечаем на сообщение
            await update.message.reply_text(error_msg)
        return
    
    # Получаем настройки группы
    settings = db.get_group_settings(chat.id)
    if not settings.get('exists'):
        db.upsert_group_chat(chat.id, chat.title)
        settings = db.get_group_settings(chat.id)
    
    lang = 'ru'
    
    notify_disabled = settings.get('notify_disabled', False)
    auto_delete_enabled = settings.get('auto_delete_enabled', False)
    
    notify_status = t(lang, 'notifications_disabled') if notify_disabled else t(lang, 'notifications_enabled')
    auto_delete_status = t(lang, 'auto_delete_enabled') if auto_delete_enabled else t(lang, 'auto_delete_disabled')
    
    text = (
        f"<b>{t(lang, 'group_settings_title')}</b>\n\n"
        f"{t(lang, 'group_settings_desc')}\n\n"
        f"{t(lang, 'group_notifications')}: {notify_status}\n"
        f"{t(lang, 'group_auto_delete')}: {auto_delete_status}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton(t(lang, 'btn_toggle_notifications'), callback_data='group_toggle_notify')],
        [InlineKeyboardButton(t(lang, 'btn_toggle_auto_delete'), callback_data='group_toggle_delete')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            # Планируем автоудаление отредактированного сообщения, если включено в настройках группы
            try:
                await schedule_auto_delete_message(context, chat.id, query.message.message_id)
            except Exception:
                pass
        except BadRequest:
            sent_msg = await context.bot.send_message(chat_id=chat.id, text=text, reply_markup=reply_markup, parse_mode='HTML')
            # Планируем автоудаление отправленного сообщения, если включено в настройках группы
            try:
                await schedule_auto_delete_message(context, chat.id, sent_msg.message_id)
            except Exception:
                pass
    else:
        sent_msg = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        # Планируем автоудаление отправленного сообщения, если включено в настройках группы
        try:
            await schedule_auto_delete_message(context, chat.id, sent_msg.message_id)
        except Exception:
            pass

async def toggle_group_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает уведомления для группы."""
    query = update.callback_query
    await query.answer()
    
    chat = update.effective_chat
    
    # Проверяем права создателя
    is_creator = await check_group_creator_permissions(update, context)
    if not is_creator:
        await query.answer(t('ru', 'group_access_denied'), show_alert=True)
        return
    
    # Получаем текущие настройки
    settings = db.get_group_settings(chat.id)
    current_state = settings.get('notify_disabled', False)
    new_state = not current_state
    
    # Обновляем настройки
    if db.update_group_settings(chat.id, notify_disabled=new_state):
        status_msg = 'Уведомления отключены' if new_state else 'Уведомления включены'
        await query.answer(status_msg, show_alert=True)
        await show_group_settings(update, context, update.effective_user)
    else:
        await query.answer('Ошибка при обновлении настроек', show_alert=True)

async def toggle_group_auto_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает автоудаление сообщений для группы."""
    query = update.callback_query
    await query.answer()
    
    chat = update.effective_chat
    
    # Проверяем права создателя
    is_creator = await check_group_creator_permissions(update, context)
    if not is_creator:
        await query.answer(t('ru', 'group_access_denied'), show_alert=True)
        return
    
    # Получаем текущие настройки
    settings = db.get_group_settings(chat.id)
    current_state = settings.get('auto_delete_enabled', False)
    new_state = not current_state
    
    # Если включаем автоудаление, проверяем права бота
    if new_state:
        bot_rights = await check_bot_admin_rights(context, chat.id)
        if not bot_rights['is_admin'] or not bot_rights['can_delete_messages']:
            # Отправляем предупреждение создателю
            await notify_creator_about_missing_rights(context, chat.id)
            await query.answer(
                '⚠️ Бот не имеет прав администратора или права на удаление сообщений. '
                'Автоудаление не будет работать. Проверьте личные сообщения для подробностей.',
                show_alert=True
            )
            # Всё равно включаем настройку, но предупреждаем
    
    # Обновляем настройки
    if db.update_group_settings(chat.id, auto_delete_enabled=new_state):
        status_msg = 'Автоудаление включено' if new_state else 'Автоудаление отключено'
        await query.answer(status_msg, show_alert=True)
        await show_group_settings(update, context, update.effective_user)
    else:
        await query.answer('Ошибка при обновлении настроек', show_alert=True)


async def _format_display_name(context: ContextTypes.DEFAULT_TYPE, update: Update, user_id: int, username: str | None) -> str:
    uname = (str(username).lstrip('@')) if username else ''
    if uname and 3 <= len(uname) <= 32 and all(ch.isalnum() or ch == '_' for ch in uname) and not uname.isdigit() and uname != str(user_id):
        safe_un = uname.replace('<', '&lt;').replace('>', '&gt;')
        return f"@{safe_un}"
    try:
        chat = await context.bot.get_chat(user_id)
        first_name = getattr(chat, 'first_name', None) or ''
        last_name = getattr(chat, 'last_name', None) or ''
        name = (first_name + (' ' if first_name and last_name else '') + last_name).strip()
        if not name:
            un2 = getattr(chat, 'username', None)
            if un2:
                u2 = str(un2).lstrip('@')
                if 3 <= len(u2) <= 32 and all(ch.isalnum() or ch == '_' for ch in u2):
                    safe_un = u2.replace('<', '&lt;').replace('>', '&gt;')
                    return f"@{safe_un}"
        if name:
            safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
            return f'<a href="tg://user?id={user_id}">{safe_name}</a>'
    except Exception:
        pass
    try:
        chat_obj = update.effective_chat
        chat_id = getattr(chat_obj, 'id', None)
        chat_type = getattr(chat_obj, 'type', None)
        if chat_id and chat_type in ('group', 'supergroup'):
            member = await context.bot.get_chat_member(chat_id, user_id)
            u = getattr(member, 'user', None)
            if u:
                first_name = getattr(u, 'first_name', None) or ''
                last_name = getattr(u, 'last_name', None) or ''
                name = (first_name + (' ' if first_name and last_name else '') + last_name).strip()
                if name:
                    safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
                    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'
                un3 = getattr(u, 'username', None)
                if un3:
                    u3 = str(un3).lstrip('@')
                    if 3 <= len(u3) <= 32 and all(ch.isalnum() or ch == '_' for ch in u3):
                        safe_un = u3.replace('<', '&lt;').replace('>', '&gt;')
                        return f"@{safe_un}"
    except Exception:
        pass
    return f'<a href="tg://user?id={user_id}">Игрок</a>'


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает таблицу лидеров."""
    leaderboard_data = db.get_leaderboard()
    
    if not leaderboard_data:
        text = "Еще никто не нашел ни одного энергетика. Будь первым!"
        await update.message.reply_text(text)
        return

    text = "🏆 <b>Таблица лидеров по количеству энергетиков:</b>\n\n"
    
    medals = {0: '🥇', 1: '🥈', 2: '🥉'}
    
    for i, (user_id, username, total_drinks, vip_until, vip_plus_until, rating) in enumerate(leaderboard_data):
        place = i + 1
        medal = medals.get(i, f" {place}.")
        display_name = await _format_display_name(context, update, user_id, username)
        
        # Проверяем VIP статус с приоритетом VIP+
        current_time = int(time.time())
        vip_plus_active = vip_plus_until and current_time < vip_plus_until
        vip_active = vip_until and current_time < vip_until
        
        if vip_plus_active:
            vip_badge = f" {VIP_PLUS_EMOJI}"
        elif vip_active:
            vip_badge = f" {VIP_EMOJI}"
        else:
            vip_badge = ""
            
        rating_value = int(rating or 0)
        text += f"{medal} {display_name}{vip_badge} - <b>{total_drinks} шт.</b> | ⭐ {rating_value}\n"

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
        display_name = await _format_display_name(context, update, user_id, username)
        
        # Проверяем VIP статус
        vip_until = db.get_vip_until(user_id)
        vip_plus_until = db.get_vip_plus_until(user_id)
        current_time = int(time.time())
        vip_plus_active = vip_plus_until and current_time < vip_plus_until
        vip_active = vip_until and current_time < vip_until
        
        if vip_plus_active:
            vip_badge = f" {VIP_PLUS_EMOJI}"
        elif vip_active:
            vip_badge = f" {VIP_EMOJI}"
        else:
            vip_badge = ""
        
        text += f"{medal} {display_name}{vip_badge} - <b>{coins:,} септимов</b>\n"

    await update.message.reply_html(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет справочное сообщение."""
    user = update.effective_user
    player = None
    try:
        player = db.get_or_create_player(user.id, getattr(user, 'username', None) or getattr(user, 'first_name', None))
    except Exception:
        player = None
    lang = getattr(player, 'language', 'ru') or 'ru'
    rating_value = int(getattr(player, 'rating', 0) or 0) if player else 0
    # Динамические кулдауны
    search_minutes = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN) // 60
    bonus_hours = db.get_setting_int('daily_bonus_cooldown', DAILY_BONUS_COOLDOWN) // 3600
    if lang == 'en':
        text = (
            f"👋 Hi, {user.mention_html()}!\n\n"
            "I am a bot for collecting energy drinks. Here is what you can do:\n\n"
            "<b>Main menu:</b>\n"
            f"• 🔎 <b>Find energy</b> — once per {search_minutes} min you can try your luck and find a random drink.\n"
            f"• 🎁 <b>Daily bonus</b> — once per {bonus_hours} h.\n"
            "• 📦 <b>Inventory</b> — all your found drinks (with pages).\n"
            "• 🏙️ <b>Cities</b> — choose a city (HighTown: Shop, Receiver, Plantation).\n"
            "• 👤 <b>My profile</b> — your stats, boosts and promo codes.\n"
            "• ⚙️ <b>Settings</b> — language and reset progress.\n\n"
            "<b>Rating system:</b>\n"
            "• 🌱 Plantation harvest: <b>+3 rating</b> per harvest.\n"
            "• 🧵 Silk plantation harvest: <b>+3 rating</b> per harvest.\n"
            f"• Current rating bonus: search up to <b>+10%</b> (now <b>+{_rating_bonus_percent(rating_value, 0.10) * 100:.2f}%</b>), daily up to <b>+5%</b> (now <b>+{_rating_bonus_percent(rating_value, 0.05) * 100:.2f}%</b>).\n\n"
            "<b>Commands:</b>\n"
            "/start — open main menu.\n"
            "/leaderboard — leaderboard by drinks.\n"
            "/moneyleaderboard — leaderboard by coins.\n"
            "/find — quick find (works in groups too).\n"
            "/myreceipts — your TG Premium receipts.\n"
            "/myboosts — your auto-search boosts history.\n"
            "/help — this message.\n\n"
            "<b>Tips:</b>\n"
            "• You can just type: \"<b>Find energy</b>\" — I will understand.\n"
            "• In groups you can gift drinks: /gift @username (bot will send the menu in DM)."
        )
    else:
        text = (
            f"👋 Привет, {user.mention_html()}!\n\n"
            "Я бот для коллекционирования энергетиков. Вот что доступно:\n\n"
            "<b>Главное меню:</b>\n"
            f"• 🔎 <b>Найти энергетик</b> — раз в {search_minutes} мин. можно испытать удачу и найти случайный энергетик.\n"
            f"• 🎁 <b>Ежедневный бонус</b> — раз в {bonus_hours} ч.\n"
            "• 📦 <b>Инвентарь</b> — все ваши найденные напитки (есть пагинация).\n"
            "• 🏙️ <b>Города</b> — выбор города (ХайТаун: Магазин, Приёмник, Плантация).\n"
            "• 👤 <b>Мой профиль</b> — ваш профиль, статистика, бусты и промокоды.\n"
            "• ⚙️ <b>Настройки</b> — выбор языка и сброс прогресса.\n\n"
            "<b>Система рейтинга:</b>\n"
            "• 🌱 Сбор урожая плантации: <b>+3 рейтинга</b> за каждый сбор.\n"
            "• 🧵 Сбор урожая шёлковой плантации: <b>+3 рейтинга</b> за каждый сбор.\n"
            f"• Бонус рейтинга к шансам: поиск до <b>+10%</b> (сейчас <b>+{_rating_bonus_percent(rating_value, 0.10) * 100:.2f}%</b>), daily до <b>+5%</b> (сейчас <b>+{_rating_bonus_percent(rating_value, 0.05) * 100:.2f}%</b>).\n\n"
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


async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or getattr(chat, 'type', None) != 'private':
        await update.message.reply_text("Активация промокодов доступна только в личных сообщениях бота.")
        return
    context.user_data['awaiting_promo_code'] = True
    await update.message.reply_text("Введите промокод:")


async def promo_button_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    chat = update.effective_chat
    if not chat or getattr(chat, 'type', None) != 'private':
        await query.answer("Только в личных сообщениях бота", show_alert=True)
        return
    context.user_data['awaiting_promo_code'] = True
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data='promo_cancel')],
    ])
    try:
        await query.message.edit_text("Введите промокод:", reply_markup=kb)
    except BadRequest:
        try:
            await query.message.reply_text("Введите промокод:", reply_markup=kb)
        except Exception:
            pass


async def promo_button_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    context.user_data.pop('awaiting_promo_code', None)
    await show_menu(update, context)

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
    if await abort_if_banned(update, context):
        return
    msg = update.effective_message
    if not msg or not getattr(msg, 'text', None):
        return

    try:
        u = update.effective_user
        if u:
            db.get_or_create_player(u.id, username=getattr(u, 'username', None), display_name=(getattr(u, 'full_name', None) or getattr(u, 'first_name', None)))
    except Exception:
        pass
    try:
        skip_ids = context.chat_data.get('_skip_text_message_ids')
        if skip_ids and int(getattr(msg, 'message_id', 0) or 0) in skip_ids:
            try:
                skip_ids.remove(int(msg.message_id))
            except Exception:
                pass
            return
    except Exception:
        pass
    incoming = msg.text or ""
    
    # Проверяем, ждём ли мы ввод для админ панели Создателя
    if context.user_data.get('awaiting_creator_action'):
        await creator_handle_input(update, context)
        return
    
    # Проверяем, ждём ли мы ввод для новых админ функций (энергетики, логи, управление игроками)
    if context.user_data.get('awaiting_admin_action') or context.user_data.get('admin_player_action'):
        await admin_handle_input(update, context)
        return
    
    if context.user_data.get('awaiting_promo_code'):
        context.user_data.pop('awaiting_promo_code', None)
        chat = update.effective_chat
        if not chat or getattr(chat, 'type', None) != 'private':
            await msg.reply_text("Активация промокодов доступна только в личных сообщениях бота.")
            return
        code = incoming.strip()
        if not code:
            await msg.reply_text("Пустой код. Отправьте промокод ещё раз.")
            return
        res = db.redeem_promo(update.effective_user.id, code)
        if not res or not res.get('ok'):
            reason = (res or {}).get('reason')
            if reason == 'expired':
                await msg.reply_text("Срок действия промокода истёк.")
            elif reason == 'max_uses_reached':
                await msg.reply_text("Достигнут общий лимит активаций этого промокода.")
            elif reason == 'per_user_limit_reached':
                await msg.reply_text("Вы уже использовали этот промокод максимальное число раз.")
            elif reason == 'invalid_drink':
                await msg.reply_text("Некорректный приз в промокоде.")
            elif reason == 'unsupported_kind':
                await msg.reply_text("Неподдерживаемый тип промокода.")
            elif reason == 'exception':
                logger.error("[PROMO] Ошибка активации промокода (см. traceback в database.py)")
                await msg.reply_text("Ошибка при активации промокода. Попробуйте позже.")
            else:
                # Диагностика: проверим, есть ли промокод в базе после нормализации ввода
                try:
                    visible = db.find_promos_by_code_debug(code)
                    items = (visible or {}).get('items') or []
                    code_norm = (visible or {}).get('code_norm') or ''
                    if items:
                        p = items[0]
                        active = bool(p.get('active'))
                        exp = p.get('expires_at')
                        exp_str = safe_format_timestamp(exp) if exp else '—'
                        if not active:
                            await msg.reply_html(
                                "Промокод найден, но он не активен.\n"
                                f"Код в базе: <code>{html.escape(str(p.get('code')))}</code>\n"
                                f"Срок: <b>{html.escape(exp_str)}</b>"
                            )
                        else:
                            # Активен, но redeem_promo не применил — чаще всего это несовпадение кода/символов
                            await msg.reply_html(
                                "Промокод с таким вводом не применился.\n"
                                f"Нормализованный ввод: <code>{html.escape(str(code_norm))}</code>\n"
                                f"Код в базе: <code>{html.escape(str(p.get('code')))}</code>\n"
                                "Попробуйте скопировать код из списка промокодов и вставить без пробелов."
                            )
                    else:
                        await msg.reply_text("Промокод не найден или не активен.")
                except Exception:
                    await msg.reply_text("Промокод не найден или не активен.")
            return
        kind = res.get('kind')
        if kind == 'coins':
            await msg.reply_html(f"✅ Начислено: <b>+{res.get('coins_added', 0)}</b> септимов. Теперь у вас: <b>{res.get('coins_total', 0)}</b>.")
            return
        if kind == 'vip':
            until = res.get('vip_until')
            until_str = safe_format_timestamp(until) if until else '—'
            await msg.reply_html(f"✅ VIP продлён до: <b>{until_str}</b>.")
            return
        if kind == 'vip_plus':
            until = res.get('vip_plus_until')
            until_str = safe_format_timestamp(until) if until else '—'
            await msg.reply_html(f"✅ VIP+ продлён до: <b>{until_str}</b>.")
            return
        if kind == 'drink':
            dn = res.get('drink_name', 'Энергетик')
            rarity = res.get('rarity', 'Basic')
            await msg.reply_html(f"✅ Получен энергетик: <b>{dn}</b> [{rarity}].")
            return
        await msg.reply_text("Промокод активирован.")
        return

    # Проверяем, ждём ли мы ввод для поиска подарка
    user_id = update.effective_user.id
    state = GIFT_SELECTION_STATE.get(user_id)
    if state and state.get('awaiting_search'):
        state['awaiting_search'] = False
        search_query = incoming.strip()
        
        if not search_query:
            await msg.reply_text("❌ Пустой запрос. Попробуйте снова.")
            return
        
        # Обновляем меню с результатами поиска
        message_id = state.get('search_message_id')
        try:
            await send_gift_selection_menu(
                context, 
                user_id, 
                page=1, 
                search_query=search_query,
                message_id=message_id
            )
            # Удаляем сообщение пользователя с запросом
            try:
                await msg.delete()
            except Exception:
                pass
        except Exception as e:
            logger.exception("[GIFT_SEARCH] Error: %s", e)
            await msg.reply_text("Ошибка при поиске. Попробуйте снова.")
        return
    
    # Проверяем, ждём ли мы ввод для поиска по инвентарю
    if context.user_data.get('awaiting_favorites_search'):
        context.user_data.pop('awaiting_favorites_search', None)
        slot = int(context.user_data.get('awaiting_favorites_search_slot') or 0)
        context.user_data.pop('awaiting_favorites_search_slot', None)
        search_query = incoming.strip()
        if slot not in (1, 2, 3):
            return
        if not search_query:
            await msg.reply_text("❌ Пустой запрос. Попробуйте снова.")
            return
        await show_favorites_search_results(update, context, slot=slot, search_query=search_query, page=1)
        return

    if context.user_data.get('awaiting_inventory_search'):
        # Очищаем флаг ожидания
        context.user_data.pop('awaiting_inventory_search', None)
        
        # Выполняем поиск с введённым текстом
        search_query = incoming.strip()
        if not search_query:
            await msg.reply_text("❌ Пустой запрос. Попробуйте снова.")
            return
        
        # Показываем результаты поиска
        await show_inventory_search_results(update, context, search_query, page=1)
        return

    # === ДРУЗЬЯ: ввод ника для поиска ===
    if context.user_data.get('awaiting_friend_username_search'):
        context.user_data.pop('awaiting_friend_username_search', None)
        chat = update.effective_chat
        if not chat or getattr(chat, 'type', None) != 'private':
            await msg.reply_text("Добавление друзей доступно только в личных сообщениях бота.")
            return
        search_query = incoming.strip()
        if not search_query:
            await msg.reply_text("❌ Пустой запрос. Попробуйте снова.")
            return
        try:
            context.user_data['friends_last_search_query'] = search_query.lstrip('@').strip()
        except Exception:
            pass
        await friends_search_results(update, context, search_query.lstrip('@').strip(), page=0)
        return

    # === ДРУЗЬЯ: ввод суммы для перевода ===
    transfer_state = context.user_data.get('awaiting_friend_transfer')
    if transfer_state and isinstance(transfer_state, dict):
        chat = update.effective_chat
        if not chat or getattr(chat, 'type', None) != 'private':
            await msg.reply_text("Передачи друзьям доступны только в личных сообщениях бота.")
            return
        kind = str(transfer_state.get('kind') or '')
        to_uid = int(transfer_state.get('to_user_id') or 0)
        try:
            amount = int(incoming.strip())
        except Exception:
            amount = 0
        if amount <= 0:
            await msg.reply_text("❌ Нужно число больше 0.")
            return

        user = update.effective_user
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        lang = player.language

        if kind == 'coins':
            res = db.transfer_coins_to_friend(user.id, to_uid, amount)
            if not res or not res.get('ok'):
                reason = (res or {}).get('reason')
                if reason == 'limit_reached':
                    rem = int((res or {}).get('remaining') or 0)
                    await msg.reply_text(f"❌ Достигнут лимит. Осталось на сегодня: {rem}.")
                elif reason == 'not_enough_coins':
                    have = int((res or {}).get('have') or 0)
                    await msg.reply_text(f"❌ Недостаточно монет. У вас: {have}.")
                elif reason == 'not_friends':
                    await msg.reply_text("❌ Этот игрок не у вас в друзьях.")
                else:
                    await msg.reply_text("❌ Ошибка перевода. Попробуйте позже.")
                return
            context.user_data.pop('awaiting_friend_transfer', None)
            try:
                await context.bot.send_message(chat_id=to_uid, text=f"💰 Вам перевели {amount} монет!" if lang == 'ru' else f"💰 You received {amount} coins!")
            except Exception:
                pass
            await msg.reply_text("✅ Перевод выполнен." if lang == 'ru' else "✅ Transfer complete.")
            await friends_open_menu(update, context, to_uid)
            return

        if kind == 'fragments':
            res = db.transfer_fragments_to_friend(user.id, to_uid, amount)
            if not res or not res.get('ok'):
                reason = (res or {}).get('reason')
                if reason == 'limit_reached':
                    rem = int((res or {}).get('remaining') or 0)
                    await msg.reply_text(f"❌ Достигнут лимит. Осталось на сегодня: {rem}.")
                elif reason == 'not_enough_fragments':
                    have = int((res or {}).get('have') or 0)
                    await msg.reply_text(f"❌ Недостаточно фрагментов. У вас: {have}.")
                elif reason == 'not_friends':
                    await msg.reply_text("❌ Этот игрок не у вас в друзьях.")
                else:
                    await msg.reply_text("❌ Ошибка перевода. Попробуйте позже.")
                return
            context.user_data.pop('awaiting_friend_transfer', None)
            try:
                await context.bot.send_message(chat_id=to_uid, text=f"🧩 Вам перевели {amount} фрагментов!" if lang == 'ru' else f"🧩 You received {amount} fragments!")
            except Exception:
                pass
            await msg.reply_text("✅ Перевод выполнен." if lang == 'ru' else "✅ Transfer complete.")
            await friends_open_menu(update, context, to_uid)
            return

        if kind == 'rating':
            res = db.transfer_rating_to_friend(user.id, to_uid, amount)
            if not res or not res.get('ok'):
                reason = (res or {}).get('reason')
                if reason == 'limit_reached':
                    rem = int((res or {}).get('remaining') or 0)
                    await msg.reply_text(f"❌ Достигнут лимит. Осталось на 48ч: {rem}.")
                elif reason == 'not_enough_rating':
                    have = int((res or {}).get('have') or 0)
                    await msg.reply_text(f"❌ Недостаточно рейтинга. У вас: {have}.")
                elif reason == 'receiver_max_rating':
                    await msg.reply_text("❌ У получателя достигнут максимум рейтинга.")
                elif reason == 'not_friends':
                    await msg.reply_text("❌ Этот игрок не у вас в друзьях.")
                else:
                    await msg.reply_text("❌ Ошибка перевода. Попробуйте позже.")
                return
            context.user_data.pop('awaiting_friend_transfer', None)
            try:
                await context.bot.send_message(chat_id=to_uid, text=f"🏆 Вам перевели {amount} рейтинга!" if lang == 'ru' else f"🏆 You received {amount} rating!")
            except Exception:
                pass
            await msg.reply_text("✅ Перевод выполнен." if lang == 'ru' else "✅ Transfer complete.")
            await friends_open_menu(update, context, to_uid)
            return

        await msg.reply_text("❌ Неизвестный тип передачи.")
        return

    chat = update.effective_chat
    if chat and getattr(chat, 'type', None) == 'private':
        norm_simple = "".join(ch for ch in incoming.lower() if ch.isalnum() or ch.isspace()).strip()
        if norm_simple == 'меню':
            await start_command(update, context)
            return

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
        # Предварительная проверка кулдауна (учёт VIP+/VIP), чтобы не показывать спиннер впустую
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        now_ts = time.time()
        vip_plus_active = db.is_vip_plus(user.id)
        vip_active = db.is_vip(user.id)
        base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
        if vip_plus_active:
            eff_search_cd = base_search_cd / 4
        elif vip_active:
            eff_search_cd = base_search_cd / 2
        else:
            eff_search_cd = base_search_cd
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
            img_paths = result.get("image_paths") or []
            existing = [p for p in img_paths if p and os.path.exists(p)]
            found_count = int(result.get('found_count', 1) or 1)
            if found_count >= 2 and len(existing) >= 2:
                f1 = None
                f2 = None
                try:
                    f1 = open(existing[0], 'rb')
                    f2 = open(existing[1], 'rb')
                    media = [
                        InputMediaPhoto(media=f1, caption=result.get("caption"), parse_mode='HTML'),
                        InputMediaPhoto(media=f2),
                    ]
                    await _send_media_group_long(context.bot.send_media_group, chat_id=msg.chat_id, media=media)
                finally:
                    try:
                        if f1:
                            f1.close()
                    except Exception:
                        pass
                    try:
                        if f2:
                            f2.close()
                    except Exception:
                        pass
            elif existing:
                with open(existing[0], 'rb') as photo:
                    await _send_photo_long(
                        msg.reply_photo,
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


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not getattr(msg, 'photo', None):
        return
    # Обработка фото для обновления изображения энергетика в админ-панели
    user = update.effective_user
    action = context.user_data.get('awaiting_admin_action')
    if action == 'drink_update_photo_wait_file' and has_creator_panel_access(user.id, user.username):
        # Удаляем ранее загруженное ожидание (если было)
        try:
            old_name = context.user_data.get('pending_photo')
            if old_name:
                fp = os.path.join(ENERGY_IMAGES_DIR, old_name)
                if os.path.exists(fp):
                    os.remove(fp)
        except Exception:
            pass
        # Скачиваем новое фото и сохраняем
        photo_file = msg.photo[-1]
        try:
            file = await context.bot.get_file(photo_file.file_id)
            os.makedirs(ENERGY_IMAGES_DIR, exist_ok=True)
            image_name = f"{int(time.time())}_{random.randint(1000,9999)}.jpg"
            await file.download_to_drive(os.path.join(ENERGY_IMAGES_DIR, image_name))
            context.user_data['pending_photo'] = image_name
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data='drink_confirm_photo')],
                [InlineKeyboardButton("❌ Отмена", callback_data='drink_cancel_photo')]
            ])
            # Отправляем предпросмотр
            try:
                with open(os.path.join(ENERGY_IMAGES_DIR, image_name), 'rb') as photo:
                    await msg.reply_photo(photo=photo, caption="Предпросмотр нового фото. Подтвердить?", reply_markup=kb)
            except Exception:
                await msg.reply_text("Фото загружено. Подтвердить обновление?", reply_markup=kb)
        except Exception:
            await msg.reply_text("❌ Не удалось загрузить фото. Попробуйте ещё раз или отправьте другое изображение.")
        return

async def audio_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not getattr(msg, 'audio', None):
        return
    user = update.effective_user
    action = context.user_data.get('awaiting_admin_action')
    # Поддержка рассылки аудио из админ-панели
    if action == 'broadcast' and has_creator_panel_access(user.id, user.username):
        caption = (msg.caption or '').strip()
        try:
            await handle_admin_broadcast_audio(update, context, caption)
        finally:
            context.user_data.pop('awaiting_admin_action', None)

async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /find для поиска энергетика (особенно полезна в группах)."""
    if await abort_if_banned(update, context):
        return
    msg = update.effective_message
    if not msg:
        return
    user = update.effective_user
    chat = update.effective_chat
    
    # Анти-даблклик для команды /find
    lock = _get_lock(f"user:{user.id}:search")
    if lock.locked():
        await reply_auto_delete_message(msg, "Поиск уже выполняется…", context=context)
        return
    async with lock:
        result = await _perform_energy_search(user.id, user.username or user.first_name, context)

    if result['status'] == 'cooldown':
        time_left = result["time_left"]
        await reply_auto_delete_message(
            msg, 
            f"Ещё не время! Подожди немного (⏳ {int(time_left // 60)}:{int(time_left % 60):02d}).",
            context=context
        )
        return

    if result['status'] == 'no_drinks':
        await reply_auto_delete_message(msg, "В базе данных пока нет энергетиков!", context=context)
        return

    if result["status"] == 'ok':
        img_paths = result.get("image_paths") or []
        existing = [p for p in img_paths if p and os.path.exists(p)]
        found_count = int(result.get('found_count', 1) or 1)
        if found_count >= 2 and len(existing) >= 2:
            f1 = None
            f2 = None
            try:
                f1 = open(existing[0], 'rb')
                f2 = open(existing[1], 'rb')
                media = [
                    InputMediaPhoto(media=f1, caption=result.get("caption"), parse_mode='HTML'),
                    InputMediaPhoto(media=f2),
                ]
                sent_messages = await _send_media_group_long(context.bot.send_media_group, chat_id=chat.id, media=media)
                for sm in sent_messages or []:
                    try:
                        await schedule_auto_delete_message(context, chat.id, sm.message_id)
                    except Exception:
                        pass
            finally:
                try:
                    if f1:
                        f1.close()
                except Exception:
                    pass
                try:
                    if f2:
                        f2.close()
                except Exception:
                    pass
        elif existing:
            with open(existing[0], 'rb') as photo:
                sent_msg = await _send_photo_long(
                    msg.reply_photo,
                    photo=photo,
                    caption=result["caption"],
                    reply_markup=result["reply_markup"],
                    parse_mode='HTML'
                )
            # Планируем автоудаление для фото-сообщения
            try:
                await schedule_auto_delete_message(context, chat.id, sent_msg.message_id)
            except Exception:
                pass
        else:
            sent_msg = await msg.reply_html(
                text=result["caption"],
                reply_markup=result["reply_markup"]
            )
            # Планируем автоудаление для текстового сообщения
            try:
                await schedule_auto_delete_message(context, chat.id, sent_msg.message_id)
            except Exception:
                pass


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

    name = drink.get('name') if isinstance(drink, dict) else getattr(drink, 'name', '')
    descr = drink.get('description') if isinstance(drink, dict) else getattr(drink, 'description', '')
    caption = (
        f"<b>{name}</b>\n\n"
        f"<i>{descr}</i>"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='menu')]])

    image_path = drink.get('image_path') if isinstance(drink, dict) else getattr(drink, 'image_path', None)
    image_full_path = os.path.join(ENERGY_IMAGES_DIR, image_path) if image_path else None
    if image_full_path and os.path.exists(image_full_path):
        try:
            with open(image_full_path, 'rb') as photo:
                await _send_photo_long(msg.reply_photo, photo=photo, caption=caption, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            # На случай проблем с файлом — отправим без фото
            await msg.reply_html(text=caption, reply_markup=keyboard)
    else:
        await msg.reply_html(text=caption, reply_markup=keyboard)


def get_rarity_emoji(rarity: str) -> str:
    """Возвращает эмодзи для редкости напитка из constants.COLOR_EMOJIS."""
    from constants import COLOR_EMOJIS
    return COLOR_EMOJIS.get(rarity, '⭐')


def _load_rarity_emoji_overrides_into_constants() -> None:
    try:
        rows = db.list_rarity_emoji_overrides()
    except Exception:
        rows = []
    if not rows:
        return
    try:
        for rarity, emoji in rows:
            try:
                if rarity and emoji:
                    COLOR_EMOJIS[str(rarity)] = str(emoji)
            except Exception:
                pass
    except Exception:
        return


async def send_gift_selection_menu(context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 1, search_query: str = None, message_id: int = None):
    """Отправляет или обновляет меню выбора подарка с пагинацией."""
    state = GIFT_SELECTION_STATE.get(user_id)
    if not state:
        return
    
    inventory_items = state['inventory_items']
    recipient_display = state['recipient_display']
    gifts_sent_today = state['gifts_sent_today']
    
    # Фильтруем по поиску, если есть
    if search_query:
        filtered_items = [
            item for item in inventory_items 
            if search_query.lower() in item.drink.name.lower()
        ]
    else:
        filtered_items = inventory_items
    
    if not filtered_items:
        text = (
            f"🎁 <b>Выбор подарка</b>\n\n"
            f"❌ Ничего не найдено по запросу: <i>{html.escape(search_query)}</i>\n\n"
            f"Получатель: {html.escape(recipient_display)}\n"
            f"Подарков сегодня: {gifts_sent_today}/20"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Новый поиск", callback_data="gift_search")],
            [InlineKeyboardButton("◀️ Показать все", callback_data="gift_page_1")]
        ])
        
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception:
                pass
        return
    
    # Пагинация (6 напитков на страницу, по 2 в ряд)
    items_per_page = 6
    total_items = len(filtered_items)
    total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
    
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_items = filtered_items[start_idx:end_idx]
    
    # Формируем текст
    search_info = f"\n🔍 Поиск: <i>{html.escape(search_query)}</i>\n" if search_query else ""
    text = (
        f"🎁 <b>Выберите напиток для подарка</b>\n\n"
        f"👤 Получатель: {html.escape(recipient_display)}\n"
        f"📊 Подарков сегодня: {gifts_sent_today}/20"
        f"{search_info}\n"
        f"📄 Страница {page}/{total_pages} ({total_items} напитков)"
    )
    
    # Формируем клавиатуру с кнопками напитков (по 2 в ряд)
    keyboard_rows = []
    for i in range(0, len(page_items), 2):
        row = []
        for item in page_items[i:i+2]:
            rarity_emoji = get_rarity_emoji(item.rarity)
            # Ограничиваем длину названия для кнопки
            drink_name = item.drink.name[:15] + "..." if len(item.drink.name) > 15 else item.drink.name
            button_text = f"{rarity_emoji} {drink_name} x{item.quantity}"
            
            token = secrets.token_urlsafe(8)
            GIFT_SELECT_TOKENS[token] = {
                'group_id': state['group_id'],
                'recipient_username': state['recipient_username'],
                'recipient_id': state['recipient_id'],
                'recipient_display': recipient_display,
                'item_id': item.id,
            }
            row.append(InlineKeyboardButton(button_text, callback_data=f"selectgift2_{token}"))
        keyboard_rows.append(row)
    
    # Кнопка поиска
    keyboard_rows.append([InlineKeyboardButton("🔍 Поиск по названию", callback_data="gift_search")])
    
    # Навигация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"gift_page_{page-1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="gift_page_info"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"gift_page_{page+1}"))
    
    if nav_row:
        keyboard_rows.append(nav_row)
    
    # Кнопка отмены
    keyboard_rows.append([InlineKeyboardButton("❌ Отменить", callback_data="gift_cancel")])
    
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    # Отправляем или обновляем сообщение
    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )


async def giftstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/giftstats — показывает статистику подарков пользователя."""
    user_id = update.effective_user.id
    
    try:
        stats = db.get_gift_stats(user_id)
        gifts_sent_today = db.get_user_gifts_sent_today(user_id)
        
        # Проверяем блокировку
        is_blocked, reason = db.is_user_gift_restricted(user_id)
        
        text = (
            f"📊 <b>Статистика подарков</b>\n\n"
            f"🎁 Отправлено всего: <b>{stats['sent']}</b>\n"
            f"🎉 Получено всего: <b>{stats['received']}</b>\n"
            f"📅 Отправлено сегодня: <b>{gifts_sent_today}/20</b>\n\n"
        )
        
        if is_blocked:
            text += f"🚫 <b>Статус:</b> Заблокирован\n<i>Причина: {html.escape(reason)}</i>"
        else:
            text += "✅ <b>Статус:</b> Активен"
        
        await update.message.reply_html(text)
    except Exception as e:
        logger.exception("[GIFTSTATS] Error: %s", e)
        await update.message.reply_text("Ошибка при получении статистики.")


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/gift @username — инициирует дарение энергетика. Работает только в группах."""
    if await abort_if_banned(update, context):
        return
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
            await reply_auto_delete_message(update.message, "Нельзя дарить ботам.", context=context)
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
            await reply_auto_delete_message(
                update.message, 
                "Использование: /gift @username\nЛибо ответьте на сообщение пользователя в группе и отправьте /gift",
                context=context
            )
            return
        recipient_username = args[0].lstrip("@").strip()
        recipient_display = f"@{recipient_username}"
    giver_id = update.effective_user.id

    # 🛡️ Защита от самодарения
    if recipient_id and recipient_id == giver_id:
        await reply_auto_delete_message(update.message, "❌ Вы не можете подарить напиток самому себе!", context=context)
        return

    # 🛡️ Проверка блокировки дарителя
    is_blocked, reason = db.is_user_gift_restricted(giver_id)
    if is_blocked:
        await reply_auto_delete_message(
            update.message,
            f"🚫 Вы не можете дарить подарки.\nПричина: {reason}",
            context=context
        )
        return

    # 🛡️ Проверка блокировки получателя (если известен ID)
    if recipient_id:
        is_recipient_blocked, _ = db.is_user_gift_restricted(recipient_id)
        if is_recipient_blocked:
            await reply_auto_delete_message(
                update.message,
                f"🚫 Получатель не может принимать подарки.",
                context=context
            )
            return

    # 📊 Проверка дневного лимита (20 подарков в день)
    gifts_sent_today = db.get_user_gifts_sent_today(giver_id)
    if gifts_sent_today >= 20:
        await reply_auto_delete_message(
            update.message,
            f"⏳ Вы достигли дневного лимита подарков ({gifts_sent_today}/20).\nПопробуйте завтра!",
            context=context
        )
        return

    # ⏱️ Проверка кулдауна (40 секунд)
    last_gift_time = db.get_user_last_gift_time(giver_id)
    current_time = int(time.time())
    cooldown_seconds = 40
    if last_gift_time and (current_time - last_gift_time) < cooldown_seconds:
        remaining = cooldown_seconds - (current_time - last_gift_time)
        await reply_auto_delete_message(
            update.message,
            f"⏳ Подождите {remaining} сек. перед следующим подарком.",
            context=context
        )
        return

    # Безопасно читаем инвентарь дарителя
    try:
        inventory_items = db.get_player_inventory_with_details(giver_id)
    except Exception:
        logger.exception("[GIFT] Failed to fetch inventory for giver %s", giver_id)
        await reply_auto_delete_message(update.message, "Ошибка при чтении инвентаря. Попробуйте позже.", context=context)
        return
    if not inventory_items:
        await reply_auto_delete_message(update.message, "Ваш инвентарь пуст — нечего дарить.", context=context)
        return

    # Сохраняем состояние выбора подарка
    GIFT_SELECTION_STATE[giver_id] = {
        'group_id': update.effective_chat.id,
        'recipient_username': recipient_username or "",
        'recipient_id': recipient_id,
        'recipient_display': recipient_display,
        'inventory_items': inventory_items,
        'gifts_sent_today': gifts_sent_today
    }

    # Пытаемся написать дарителю в личку. Если бот не может — сообщаем в группе, что нужно нажать Start.
    try:
        # Отправляем красивое меню выбора подарка
        await send_gift_selection_menu(context, giver_id, page=1)
        # Сообщаем в группе, что список отправлен в личку
        try:
            sent_msg = await update.message.reply_text("Отправил список вам в личные сообщения.")
            # Планируем автоудаление подтверждения
            try:
                await schedule_auto_delete_message(context, update.effective_chat.id, sent_msg.message_id)
            except Exception:
                pass
        except Exception:
            pass
    except Forbidden:
        await reply_auto_delete_message(
            update.message,
            "Не могу написать вам в личку. Откройте чат с ботом и нажмите Start, после этого повторите команду.",
            context=context
        )
        return
    except Exception as e:
        logger.exception("[GIFT] Failed to send DM to giver %s: %s", giver_id, e)
        await reply_auto_delete_message(update.message, "Не удалось отправить список в личные сообщения. Попробуйте позже.", context=context)
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

    # 🛡️ Проверка на подозрительную активность (>10 подарков подряд одному человеку)
    if recipient_id and db.check_consecutive_gifts(giver_id, recipient_id, limit=10):
        # Блокируем обоих пользователей
        db.add_gift_restriction(
            giver_id, 
            "Подозрительная активность: более 10 подарков подряд одному пользователю",
            blocked_until=None  # Постоянная блокировка
        )
        db.add_gift_restriction(
            recipient_id,
            "Подозрительная активность: получение более 10 подарков подряд от одного пользователя",
            blocked_until=None
        )
        logger.warning(
            f"[GIFT_SECURITY] Blocked users {giver_id} and {recipient_id} for suspicious gift activity"
        )
        await query.edit_message_text(
            "🚫 <b>Обнаружена подозрительная активность!</b>\n\n"
            "Вы и получатель заблокированы за нарушение правил дарения.\n"
            "Обратитесь к администратору для разблокировки.",
            parse_mode='HTML'
        )
        # Очищаем состояние
        if giver_id in GIFT_SELECTION_STATE:
            del GIFT_SELECTION_STATE[giver_id]
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

    # Сообщение в группу с эмодзи редкости
    recip_text = GIFT_OFFERS[gift_id].get('recipient_display') or (f"@{recipient_username}" if recipient_username else "получателю")
    # Если нет @username, экранируем имя для HTML
    recip_html = recip_text if recip_text.startswith('@') else html.escape(str(recip_text))
    rarity_emoji = get_rarity_emoji(item.rarity)
    caption = (
        f"🎁 <b>Подарок!</b>\n\n"
        f"<b>От:</b> @{GIFT_OFFERS[gift_id]['giver_name']}\n"
        f"<b>Кому:</b> {recip_html}\n"
        f"<b>Напиток:</b> {rarity_emoji} {html.escape(item.drink.name)}\n"
        f"<b>Редкость:</b> {html.escape(item.rarity)}\n\n"
        f"<i>Принять подарок?</i>"
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

    await query.edit_message_text("✅ Подарок предложен! Ожидаем ответ получателя.")
    
    # Очищаем состояние выбора подарка
    if giver_id in GIFT_SELECTION_STATE:
        del GIFT_SELECTION_STATE[giver_id]


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

    # Фикс: сначала фиксируем drink_id
    drink_id = offer.get('drink_id')
    if not drink_id:
        inv_item = db.get_inventory_item(offer['item_id'])
        drink_id = getattr(inv_item, 'drink_id', None) if inv_item else None
    if not drink_id:
        await query.edit_message_text("Не удалось определить напиток для передачи.")
        del GIFT_OFFERS[gift_id]
        return

    recipient_id = query.from_user.id
    
    if not accepted:
        # Отклонено - логируем в БД
        db.log_gift(
            giver_id=offer['giver_id'],
            recipient_id=recipient_id,
            drink_id=drink_id,
            rarity=offer['rarity'],
            status='declined'
        )
        rarity_emoji = get_rarity_emoji(offer['rarity'])
        try:
            await query.edit_message_text(
                f"❌ <b>Подарок отклонён</b>\n\n"
                f"{rarity_emoji} {html.escape(offer['drink_name'])} ({html.escape(offer['rarity'])})",
                parse_mode='HTML'
            )
        except BadRequest:
            pass
        # Уведомление дарителю
        try:
            await context.bot.send_message(
                chat_id=offer['giver_id'],
                text=f"😔 Ваш подарок ({offer['drink_name']}) был отклонён."
            )
        except Exception:
            pass
        del GIFT_OFFERS[gift_id]
        return

    # Принятие: передаём предмет
    success = db.decrement_inventory_item(offer['item_id'])
    if not success:
        await query.edit_message_text("Не удалось передать подарок (предмет исчез).")
        del GIFT_OFFERS[gift_id]
        return

    # Добавляем получателю
    db.add_drink_to_inventory(recipient_id, drink_id, offer['rarity'])
    
    # 📊 Логируем принятый подарок в БД
    db.log_gift(
        giver_id=offer['giver_id'],
        recipient_id=recipient_id,
        drink_id=drink_id,
        rarity=offer['rarity'],
        status='accepted'
    )
    
    # log
    logger.info(
        f"[GIFT] {offer['giver_name']} -> {query.from_user.username or query.from_user.id}: {offer['drink_name']} ({offer['rarity']})"
    )

    rarity_emoji = get_rarity_emoji(offer['rarity'])
    try:
        await query.edit_message_text(
            f"✅ <b>Подарок принят!</b>\n\n"
            f"{rarity_emoji} {html.escape(offer['drink_name'])} ({html.escape(offer['rarity'])})",
            parse_mode='HTML'
        )
    except BadRequest:
        pass

    # Уведомления приватно с деталями
    try:
        await context.bot.send_message(
            chat_id=offer['giver_id'],
            text=(
                f"🎉 <b>Ваш подарок принят!</b>\n\n"
                f"Получатель: {html.escape(offer.get('recipient_display', 'пользователь'))}\n"
                f"Напиток: {rarity_emoji} {html.escape(offer['drink_name'])}\n"
                f"Редкость: {html.escape(offer['rarity'])}"
            ),
            parse_mode='HTML'
        )
    except Exception:
        pass
    
    try:
        await context.bot.send_message(
            chat_id=recipient_id,
            text=(
                f"🎁 <b>Вы получили подарок!</b>\n\n"
                f"От: @{offer['giver_name']}\n"
                f"Напиток: {rarity_emoji} {html.escape(offer['drink_name'])}\n"
                f"Редкость: {html.escape(offer['rarity'])}\n\n"
                f"<i>Напиток добавлен в ваш инвентарь!</i>"
            ),
            parse_mode='HTML'
        )
    except Exception:
        pass
    
    del GIFT_OFFERS[gift_id]


def main():
    """Запускает бота."""
    db.ensure_schema()
    _load_rarity_emoji_overrides_into_constants()
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
    # Обновляем длительность существующих удобрений на новые значения (10-30 мин)
    try:
        updated = db.update_fertilizers_duration()
        if updated > 0:
            logger.info(f"[PLANTATION] Updated duration for {updated} fertilizers")
    except Exception as e:
        logger.warning(f"[PLANTATION] Failed to update fertilizers duration: {e}")
 
    log_existing_drinks()
    try:
        removed = db.unban_protected_users()
        if removed:
            logger.info(f"[BOOT] Removed bans from protected users: {removed}")
    except Exception as e:
        logger.warning(f"[BOOT] Failed to unban protected users: {e}")
 
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=15.0,
        pool_timeout=15.0,
    )
    application = ApplicationBuilder().token(config.TOKEN).request(request).build()
 
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.COMMAND, debug_log_commands), group=2)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("moneyleaderboard", show_money_leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("promo", promo_command))
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
    application.add_handler(CommandHandler("pid", pid_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("addcoins", addcoins_command))
    application.add_handler(CommandHandler("delmoney", delmoney_command))
    application.add_handler(CommandHandler("myreceipts", myreceipts_command))
    application.add_handler(CommandHandler("receipt", receipt_command))
    application.add_handler(CommandHandler("verifyreceipt", verifyreceipt_command))
    # application.add_handler(CommandHandler("addexdrink", addexdrink_command, filters=(filters.TEXT | filters.PHOTO)))

    addex_conv = ConversationHandler(
        entry_points=[CommandHandler("addexdrink", addexdrink_start)],
        states={
            ADDEX_PHOTO: [MessageHandler(filters.PHOTO, addexdrink_photo), CommandHandler("skip", addexdrink_skip)],
        },
        fallbacks=[CommandHandler("cancel", addexdrink_cancel)],
    )
    application.add_handler(addex_conv)
    application.add_handler(CommandHandler("giveexdrink", giveexdrink_command))
    application.add_handler(CommandHandler("tgstock", tgstock_command))
    application.add_handler(CommandHandler("tgadd", tgadd_command))
    application.add_handler(CommandHandler("tgset", tgset_command))
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("stockadd", stockadd_command))
    application.add_handler(CommandHandler("stockset", stockset_command))
    application.add_handler(CommandHandler("setrareemoji", setrareemoji_command))
    application.add_handler(CommandHandler("listrareemoji", listrareemoji_command))
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

    addp_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addp", addp_start)],
        states={
            ADDP_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), addp_name)],
            ADDP_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), addp_description)],
            ADDP_PHOTO: [MessageHandler(filters.PHOTO, addp_photo), CommandHandler("skip", skip_addp_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )
    application.add_handler(addp_conv_handler)
    
    # Conversation handler для пользовательских ставок в казино
    casino_custom_bet_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_bet, pattern='^casino_custom_bet$')],
        states={
            CASINO_CUSTOM_BET: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_custom_bet_input)],
        },
        fallbacks=[CallbackQueryHandler(cancel_custom_bet, pattern='^city_casino$')],
        allow_reentry=True
    )
    application.add_handler(casino_custom_bet_handler)
    
    # Conversation handler для кастомной покупки удобрений
    fertilizer_custom_buy_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_fertilizer_custom_buy_wrapper, pattern='^fert_buy_custom_')],
        states={
            FERTILIZER_CUSTOM_QTY: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_fertilizer_custom_qty_input)],
        },
        fallbacks=[CallbackQueryHandler(cancel_fertilizer_custom_buy, pattern='^fert_custom_cancel$|^plantation_fertilizers_shop$')],
        allow_reentry=True
    )
    application.add_handler(fertilizer_custom_buy_handler)

    seed_custom_buy_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_seed_custom_buy_wrapper, pattern='^seed_buy_custom_')],
        states={
            SEED_CUSTOM_QTY: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), handle_seed_custom_qty_input),
                CallbackQueryHandler(seed_custom_retry, pattern='^seed_custom_retry$'),
                CallbackQueryHandler(seed_custom_buy_max, pattern='^seed_custom_buy_max$'),
                CallbackQueryHandler(cancel_seed_custom_buy, pattern='^seed_custom_cancel$'),
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_seed_custom_buy, pattern='^seed_custom_cancel$|^plantation_shop$')],
        allow_reentry=True
    )
    application.add_handler(seed_custom_buy_handler)
    
    application.add_handler(CallbackQueryHandler(toggle_plantation_reminder, pattern='^toggle_plantation_rem$'))
    application.add_handler(CallbackQueryHandler(snooze_reminder_handler, pattern='^snooze_remind_'))
    application.add_handler(CallbackQueryHandler(toggle_auto_search_silent, pattern='^toggle_silent_mode$'))
    
    application.add_handler(CallbackQueryHandler(handle_selyuk_farmer_upgrade_action, pattern='^selyuk_farmer_upgrade_action$'))
    application.add_handler(CallbackQueryHandler(admin_player_selyuki_show, pattern='^admin_player_selyuki:'))
    application.add_handler(CallbackQueryHandler(button_handler))
    # ВАЖНО: перехватываем ответы на ForceReply с причиной отклонения до общего текстового обработчика
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, handle_reject_reason_reply), group=0)
    # Общий текстовый обработчик — после reply-хендлера
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler), group=1)
    application.add_handler(MessageHandler(filters.PHOTO, photo_message_handler), group=1)
    application.add_handler(MessageHandler(filters.AUDIO, audio_message_handler), group=1)
    # Регистрируем /gift раньше, чтобы исключить перехват другими обработчиками
    application.add_handler(CommandHandler("gift", gift_command))
    application.add_handler(CommandHandler("giftstats", giftstats_command))
    # Тихая регистрация групп по любым групповым сообщениям/командам
    application.add_handler(CommandHandler("find", find_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("groupsettings", groupsettings_command))

    # Свага Команды
    application.add_handler(CommandHandler("swagashop", swagashop.show_swaga_shop))
    application.add_handler(CommandHandler("swagainv", swagashop.show_swaga_shop))
    application.add_handler(swaga_admin.addswaga_conv_handler)
    application.add_handler(CommandHandler("giveswagacards", swaga_admin.giveswagacards_command))
    application.add_handler(CommandHandler("swagaid", swaga_admin.swagaid_command))
    
    # Логируем информацию о боте после старта (диагностика: верный ли бот запущен)
    async def _log_bot_info(context: ContextTypes.DEFAULT_TYPE):
        try:
            me = await context.bot.get_me()
            logger.info("[BOOT] Running as @%s (id=%s)", getattr(me, 'username', None), getattr(me, 'id', None))
        except Exception as e:
            logger.warning("[BOOT] Failed to get bot info: %s", e)

    # Периодическая проверка групп: отправляем не чаще 8 часов (ограничение внутри функции)
    async def notify_groups_job(context: ContextTypes.DEFAULT_TYPE):
        groups = db.get_groups_with_notifications_enabled()  # Новая функция, учитывает notify_disabled
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
                try:
                    err_text = str(e)
                    if "Chat not found" in err_text or "chat not found" in err_text:
                        try:
                            if db.disable_group_chat(g.chat_id):
                                logger.info(f"[NOTIFY] Disabled group {g.chat_id} due to Chat not found")
                        except Exception as db_err:
                            logger.warning(f"[NOTIFY] Failed to disable group {g.chat_id} after Chat not found: {db_err}")
                except Exception:
                    pass
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

        # Мониторинг автосбора урожая фермерами (каждые 10 минут)
        farmer_harvest_interval = 10 * 60  # 10 минут
        farmer_harvest_delay = 60  # начинаем через 1 минуту после старта
        application.job_queue.run_repeating(global_farmer_harvest_job, interval=farmer_harvest_interval, first=farmer_harvest_delay)

        farmer_fertilize_interval = 5 * 60
        farmer_fertilize_delay = 75
        application.job_queue.run_repeating(global_farmer_fertilize_job, interval=farmer_fertilize_interval, first=farmer_fertilize_delay)
        application.job_queue.run_repeating(global_negative_effects_job, interval=60, first=90)

        # Сводки фермера (для тихого режима)
        farmer_summary_interval = 5 * 60
        farmer_summary_delay = 90
        application.job_queue.run_repeating(farmer_summary_job, interval=farmer_summary_interval, first=farmer_summary_delay)

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
                    # Рассчитываем задержку первого запуска с учётом кулдауна (VIP+/VIP)
                    vip_plus_active = db.is_vip_plus(user_id)
                    vip_active = db.is_vip(user_id)
                    
                    base_search_cd = db.get_setting_int('search_cooldown', SEARCH_COOLDOWN)
                    if vip_plus_active:
                        eff_search_cd = base_search_cd / 4
                    elif vip_active:
                        eff_search_cd = base_search_cd / 2
                    else:
                        eff_search_cd = base_search_cd
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

        # --- Восстановление задач автоудаления после рестарта ---
        async def restore_auto_delete_on_startup(context: ContextTypes.DEFAULT_TYPE):
            await restore_scheduled_auto_deletes(context.application)
        
        application.job_queue.run_once(restore_auto_delete_on_startup, when=3)

        # --- Восстановление напоминаний о поливе ---
        async def restore_plantation_reminders_on_startup(context: ContextTypes.DEFAULT_TYPE):
            await restore_plantation_reminders(context.application)
            
        application.job_queue.run_once(restore_plantation_reminders_on_startup, when=5)

    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
