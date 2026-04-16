# file: vip_plus_handlers.py
"""
VIP+ обработчики для бота RELOAD.
Содержит функции для показа меню VIP+ и обработки покупок.
"""

import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
import database as db
from constants import VIP_PLUS_EMOJI, VIP_PLUS_COSTS, VIP_PLUS_DURATIONS_SEC

# Текстовые константы для VIP+
VIP_PLUS_TEXTS = {
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
    'btn_back': {'ru': 'Назад', 'en': 'Back'},
    'on': {'ru': 'Вкл', 'en': 'On'},
    'off': {'ru': 'Выкл', 'en': 'Off'},
    'vip_auto_header': {'ru': '\n<b>🤖 Автопоиск</b>', 'en': '\n<b>🤖 Auto-search</b>'},
    'vip_auto_state': {'ru': 'Состояние: {state}', 'en': 'State: {state}'},
    'vip_auto_today': {'ru': 'Сегодня: {count}/{limit}', 'en': 'Today: {count}/{limit}'},
    'silent_mode_on': {'ru': 'Тихий режим: Вкл 🔕', 'en': 'Silent Mode: On 🔕'},
    'silent_mode_off': {'ru': 'Тихий режим: Выкл 🔔', 'en': 'Silent Mode: Off 🔔'},
    'btn_silent_toggle': {'ru': '🔕/🔔 Тихий режим', 'en': '🔕/🔔 Silent Mode'},
}

def vip_plus_t(lang: str, key: str) -> str:
    """Функция перевода для VIP+ текстов."""
    return VIP_PLUS_TEXTS.get(key, {}).get(lang, VIP_PLUS_TEXTS.get(key, {}).get('ru', key))

async def show_vip_plus_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю V.I.P+ с выбором длительности."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    if False and not access.get('acts_like_vip'):
        await query.answer("РђРІС‚РѕРїРѕРёСЃРє Р±РѕР»СЊС€Рµ РЅРµРґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РІР°С€РµРіРѕ СЃС‚Р°С‚СѓСЃР°.", show_alert=True)
        await show_vip_plus_menu(update, context)
        return
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    if False and not access.get('acts_like_vip'):
        await query.answer("РђРІС‚РѕРїРѕРёСЃРє Р±РѕР»СЊС€Рµ РЅРµРґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РІР°С€РµРіРѕ СЃС‚Р°С‚СѓСЃР°.", show_alert=True)
        await show_vip_plus_menu(update, context)
        return
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    lang = player.language
    if str(access.get('tier') or '') in ('admin', 'admin_plus'):
        tier = "Admin+" if str(access.get('tier') or '') == 'admin_plus' else "Admin"
        text = (
            f"<b>{access.get('emoji', '🛡️')} {tier}</b>\n\n"
            f"Покупка VIP/VIP+ отключена для вашего статуса.\n"
            f"Привилегии уже выше VIP+."
        )
        keyboard = [
            [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='extra_bonuses')],
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

    text = vip_plus_t(lang, 'vip_plus_title')
    # Добавим блок о текущем состоянии автопоиска VIP+
    try:
        auto_state = vip_plus_t(lang, 'on') if getattr(player, 'auto_search_enabled', False) else vip_plus_t(lang, 'off')
        auto_count = int(getattr(player, 'auto_search_count', 0) or 0)
        auto_limit = db.get_auto_search_daily_limit(user.id, username=getattr(user, 'username', None))
        text += vip_plus_t(lang, 'vip_auto_header')
        text += "\n" + vip_plus_t(lang, 'vip_auto_state').format(state=auto_state)
        text += "\n" + vip_plus_t(lang, 'vip_auto_today').format(count=auto_count, limit=auto_limit)
        
        # Статус тихого режима
        is_silent = getattr(player, 'auto_search_silent', False)
        silent_text = vip_plus_t(lang, 'silent_mode_on') if is_silent else vip_plus_t(lang, 'silent_mode_off')
        text += f"\n{silent_text}"
        
        # Показываем статус VIP+
        if str(access.get('tier') or '') == 'vip_plus':
            vip_plus_until = db.get_vip_plus_until(user.id)
            until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_plus_until)) if vip_plus_until else '—'
            text += f"\n\n{VIP_PLUS_EMOJI} VIP+ до: {until_str}"
        else:
            text += f"\n\n{VIP_PLUS_EMOJI} VIP+: нет"
    except Exception:
        pass
    
    keyboard = [
        [InlineKeyboardButton(vip_plus_t(lang, 'vip_plus_1d'), callback_data='vip_plus_1d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'vip_plus_7d'), callback_data='vip_plus_7d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'vip_plus_30d'), callback_data='vip_plus_30d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_silent_toggle'), callback_data='toggle_silent_mode')],
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='extra_bonuses')],
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

async def show_vip_plus_1d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали VIP+ на 1 день."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    lang = player.language
    if str(access.get('tier') or '') in ('admin', 'admin_plus'):
        await show_vip_plus_menu(update, context)
        return

    cost = VIP_PLUS_COSTS['1d']
    vip_plus_until = db.get_vip_plus_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_plus_until)) if vip_plus_until else None
    text = vip_plus_t(lang, 'vip_plus_details_1d')
    text += f"\n{vip_plus_t(lang, 'vip_plus_price').format(cost=cost)}"
    if until_str:
        text += f"\n{vip_plus_t(lang, 'vip_plus_until').format(dt=until_str)}"
    
    # Проверяем наличие активного обычного VIP
    has_vip = db.is_vip(user.id) and not db.is_vip_plus(user.id)
    if has_vip:
        vip_until = db.get_vip_until(user.id)
        if vip_until and vip_until > time.time():
            remaining_seconds = int(vip_until - time.time())
            remaining_days = remaining_seconds / (24 * 3600)
            text += f"\n\n⚠️ <b>Внимание!</b>\n"
            text += f"У вас активен обычный VIP (осталось ~{remaining_days:.1f} дней).\n"
            text += f"При покупке VIP+:\n"
            text += f"• 25% времени VIP перенесётся на VIP+\n"
            text += f"• 75% времени VIP сгорит\n"
    
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{vip_plus_t(lang, 'vip_plus_insufficient').format(coins=current_coins, cost=cost)}"
    
    keyboard = [
        [InlineKeyboardButton(f"{vip_plus_t(lang, 'vip_plus_buy')} — {cost}", callback_data='confirm_vip_plus_1d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='vip_plus_menu')],
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

async def show_vip_plus_7d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали VIP+ на 7 дней."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    lang = player.language
    if str(access.get('tier') or '') in ('admin', 'admin_plus'):
        await show_vip_plus_menu(update, context)
        return

    cost = VIP_PLUS_COSTS['7d']
    vip_plus_until = db.get_vip_plus_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_plus_until)) if vip_plus_until else None
    text = vip_plus_t(lang, 'vip_plus_details_7d')
    text += f"\n{vip_plus_t(lang, 'vip_plus_price').format(cost=cost)}"
    if until_str:
        text += f"\n{vip_plus_t(lang, 'vip_plus_until').format(dt=until_str)}"
    
    # Проверяем наличие активного обычного VIP
    has_vip = db.is_vip(user.id) and not db.is_vip_plus(user.id)
    if has_vip:
        vip_until = db.get_vip_until(user.id)
        if vip_until and vip_until > time.time():
            remaining_seconds = int(vip_until - time.time())
            remaining_days = remaining_seconds / (24 * 3600)
            text += f"\n\n⚠️ <b>Внимание!</b>\n"
            text += f"У вас активен обычный VIP (осталось ~{remaining_days:.1f} дней).\n"
            text += f"При покупке VIP+:\n"
            text += f"• 25% времени VIP перенесётся на VIP+\n"
            text += f"• 75% времени VIP сгорит\n"
    
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{vip_plus_t(lang, 'vip_plus_insufficient').format(coins=current_coins, cost=cost)}"
    
    keyboard = [
        [InlineKeyboardButton(f"{vip_plus_t(lang, 'vip_plus_buy')} — {cost}", callback_data='confirm_vip_plus_7d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='vip_plus_menu')],
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

async def show_vip_plus_30d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали VIP+ на 30 дней."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    lang = player.language
    if str(access.get('tier') or '') in ('admin', 'admin_plus'):
        await show_vip_plus_menu(update, context)
        return

    cost = VIP_PLUS_COSTS['30d']
    vip_plus_until = db.get_vip_plus_until(user.id)
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(vip_plus_until)) if vip_plus_until else None
    text = vip_plus_t(lang, 'vip_plus_details_30d')
    text += f"\n{vip_plus_t(lang, 'vip_plus_price').format(cost=cost)}"
    if until_str:
        text += f"\n{vip_plus_t(lang, 'vip_plus_until').format(dt=until_str)}"
    
    # Проверяем наличие активного обычного VIP
    has_vip = db.is_vip(user.id) and not db.is_vip_plus(user.id)
    if has_vip:
        vip_until = db.get_vip_until(user.id)
        if vip_until and vip_until > time.time():
            remaining_seconds = int(vip_until - time.time())
            remaining_days = remaining_seconds / (24 * 3600)
            text += f"\n\n⚠️ <b>Внимание!</b>\n"
            text += f"У вас активен обычный VIP (осталось ~{remaining_days:.1f} дней).\n"
            text += f"При покупке VIP+:\n"
            text += f"• 25% времени VIP перенесётся на VIP+\n"
            text += f"• 75% времени VIP сгорит\n"
    
    current_coins = int(player.coins or 0)
    if current_coins < cost:
        text += f"\n{vip_plus_t(lang, 'vip_plus_insufficient').format(coins=current_coins, cost=cost)}"
    
    keyboard = [
        [InlineKeyboardButton(f"{vip_plus_t(lang, 'vip_plus_buy')} — {cost}", callback_data='confirm_vip_plus_30d')],
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='vip_plus_menu')],
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

async def confirm_vip_plus_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_key: str):
    """Показывает окно подтверждения покупки VIP+ с предупреждением о переносе VIP времени."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    lang = player.language
    if str(access.get('tier') or '') in ('admin', 'admin_plus'):
        await query.answer("Покупка VIP+ недоступна для админ-статуса.", show_alert=True)
        await show_vip_plus_menu(update, context)
        return

    if plan_key not in VIP_PLUS_COSTS or plan_key not in VIP_PLUS_DURATIONS_SEC:
        await query.answer("Ошибка плана", show_alert=True)
        return

    cost = VIP_PLUS_COSTS[plan_key]
    
    # Проверяем наличие обычного VIP
    has_vip = db.is_vip(user.id) and not db.is_vip_plus(user.id)
    
    if has_vip:
        # Показываем предупреждение с подробностями переноса времени
        vip_until = db.get_vip_until(user.id)
        if vip_until and vip_until > time.time():
            remaining_seconds = int(vip_until - time.time())
            remaining_days = remaining_seconds / (24 * 3600)
            transferred_seconds = int(remaining_seconds * 0.25)
            transferred_days = transferred_seconds / (24 * 3600)
            burned_seconds = int(remaining_seconds * 0.75)
            burned_days = burned_seconds / (24 * 3600)
            
            plan_names = {'1d': '1 день', '7d': '7 дней', '30d': '30 дней'}
            plan_name = plan_names.get(plan_key, plan_key)
            
            text = f"<b>⚠️ Подтверждение покупки VIP+</b>\n\n"
            text += f"Вы покупаете: <b>VIP+ на {plan_name}</b>\n"
            text += f"Стоимость: <b>{cost}</b> септимов\n\n"
            text += f"<b>📊 Информация о переносе времени:</b>\n"
            text += f"• Текущий VIP: ~{remaining_days:.1f} дней (~{remaining_seconds//3600} часов)\n"
            text += f"• Перенесётся на VIP+: ~{transferred_days:.1f} дней (~{transferred_seconds//3600} часов)\n"
            text += f"• Сгорит: ~{burned_days:.1f} дней (~{burned_seconds//3600} часов)\n\n"
            text += f"⚠️ <i>75% времени VIP будет потеряно!</i>"
    else:
        # Обычное подтверждение без предупреждения
        plan_names = {'1d': '1 день', '7d': '7 дней', '30d': '30 дней'}
        plan_name = plan_names.get(plan_key, plan_key)
        
        text = f"<b>Подтверждение покупки VIP+</b>\n\n"
        text += f"Вы покупаете: <b>VIP+ на {plan_name}</b>\n"
        text += f"Стоимость: <b>{cost}</b> септимов\n\n"
        text += f"Подтвердите покупку."
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить покупку VIP+", callback_data=f'buy_vip_plus_{plan_key}')],
        [InlineKeyboardButton("❌ Отмена", callback_data=f'vip_plus_{plan_key}')],
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

async def buy_vip_plus(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_key: str):
    """Покупка VIP+ на указанный срок (plan_key: '1d'|'7d'|'30d')."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = player.language

    if plan_key not in VIP_PLUS_COSTS or plan_key not in VIP_PLUS_DURATIONS_SEC:
        await query.answer("Ошибка плана", show_alert=True)
        return

    cost = VIP_PLUS_COSTS[plan_key]
    duration = VIP_PLUS_DURATIONS_SEC[plan_key]
    res = db.purchase_vip_plus(user.id, cost, duration)
    if not res.get('ok'):
        reason = res.get('reason')
        if reason == 'admin_blocked':
            tier = "Admin+" if str(res.get('tier') or '') == 'admin_plus' else "Admin"
            await query.answer(f"Покупка VIP+ недоступна для статуса {tier}.", show_alert=True)
            await show_vip_plus_menu(update, context)
        elif reason == 'not_enough_coins':
            await query.answer(vip_plus_t(lang, 'vip_plus_not_enough'), show_alert=True)
        else:
            await query.answer('Ошибка. Попробуйте позже.', show_alert=True)
        return

    vip_plus_until_ts = res.get('vip_plus_until') or db.get_vip_plus_until(user.id)
    coins_left = res.get('coins_left')
    until_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(int(vip_plus_until_ts))) if vip_plus_until_ts else '—'
    
    # Добавляем информацию о переносе времени, если было
    transferred_time = res.get('vip_time_transferred', 0)
    text = vip_plus_t(lang, 'vip_plus_bought').format(emoji=VIP_PLUS_EMOJI, dt=until_str, coins=coins_left)
    
    if transferred_time > 0:
        transferred_days = transferred_time / (24 * 3600)
        text += f"\n\n✅ Перенесено {transferred_days:.1f} дней с VIP на VIP+"
    
    keyboard = [
        [InlineKeyboardButton(vip_plus_t(lang, 'btn_back'), callback_data='vip_plus_menu')],
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

async def toggle_auto_search_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает тихий режим автопоиска."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    
    # Переключаем
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    if not access.get('acts_like_vip'):
        await query.answer("РђРІС‚РѕРїРѕРёСЃРє Р±РѕР»СЊС€Рµ РЅРµРґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РІР°С€РµРіРѕ СЃС‚Р°С‚СѓСЃР°.", show_alert=True)
        await show_vip_plus_menu(update, context)
        return
    current = getattr(player, 'auto_search_silent', False)
    db.update_player(user.id, auto_search_silent=not current)
    
    # Обновляем меню
    await show_vip_plus_menu(update, context)
