# file: silk_ui.py
"""
Модуль пользовательского интерфейса для системы Город Шёлка.
Содержит функции отображения меню, обработки кнопок и взаимодействия с пользователем.
"""

import time
import html
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import database as db
import silk_city
from constants import (
    SILK_INVESTMENT_LEVELS, SILK_TYPES, SILK_EMOJIS, 
    SILK_MAX_PLANTATIONS
)

# --- Основные функции интерфейса ---

async def show_city_silk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню Города Шёлка."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    
    # Получить статистику игрока
    stats = silk_city.get_silk_city_stats(user.id)
    plantations = silk_city.get_player_plantations(user.id)
    active_plantations = len([p for p in plantations if p.status in ['growing', 'ready']])
    
    # Получить общее количество шёлка
    silk_inventory = silk_city.get_silk_inventory(user.id)
    total_silk = sum(item.quantity for item in silk_inventory)
    
    # VIP статус
    vip_status = "🔥 V.I.P активен" if db.is_vip(user.id) else ""
    vip_line = f"\n{vip_status}" if vip_status else ""
    
    text = (
        f"{SILK_EMOJIS['city']} **ГОРОД ШЁЛКА** {SILK_EMOJIS['city']}\n\n"
        f"{SILK_EMOJIS['plantation']} Ваши плантации: {active_plantations} активных\n"
        f"{SILK_EMOJIS['inventory']} Шёлковый инвентарь: {total_silk} единиц\n"
        f"{SILK_EMOJIS['coins']} Доступно септимов: {player.coins:,}\n"
        f"{vip_line}"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"{SILK_EMOJIS['plantation']} Мои плантации", callback_data='silk_plantations')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['market']} Шёлковый рынок", callback_data='silk_market')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['inventory']} Инвентарь шёлка", callback_data='silk_inventory')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['stats']} Статистика", callback_data='silk_stats')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_plantations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать плантации игрока."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    plantations = silk_city.get_player_plantations(user.id)
    
    # Обновить статусы плантаций
    silk_city.update_plantation_statuses()
    plantations = silk_city.get_player_plantations(user.id)  # Обновить после проверки
    
    active_plantations = [p for p in plantations if p.status in ['growing', 'ready']]
    
    text = f"{SILK_EMOJIS['plantation']} **МОИ ПЛАНТАЦИИ**\n\n"
    
    if not active_plantations:
        text += "У вас пока нет активных плантаций.\nСоздайте свою первую плантацию!"
    else:
        for i, plantation in enumerate(active_plantations, 1):
            status_emoji = _get_status_emoji(plantation.status)
            progress_bar = _get_progress_bar(plantation)
            
            time_remaining = ""
            if plantation.status == 'growing':
                time_remaining = silk_city.format_time_remaining(plantation.harvest_ready_at)
            elif plantation.status == 'ready':
                time_remaining = "Готов к сбору!"
            
            text += (
                f"{i}. **{plantation.plantation_name}**\n"
                f"   {status_emoji} Статус: {_get_status_text(plantation.status)}\n"
                f"   {SILK_EMOJIS['timer']} {time_remaining}\n"
                f"   {SILK_EMOJIS['investment']} Уровень: {plantation.investment_level.title()}\n"
                f"   {progress_bar}\n\n"
            )
    
    keyboard = []
    
    # Кнопки для готовых плантаций
    ready_plantations = [p for p in active_plantations if p.status == 'ready']
    if ready_plantations:
        for plantation in ready_plantations:
            keyboard.append([
                InlineKeyboardButton(
                    f"{SILK_EMOJIS['harvest']} Собрать урожай: {plantation.plantation_name}",
                    callback_data=f'silk_harvest_{plantation.id}'
                )
            ])
    
    # Кнопка создания новой плантации
    if len(active_plantations) < SILK_MAX_PLANTATIONS:
        keyboard.append([
            InlineKeyboardButton(
                f"➕ Создать плантацию ({len(active_plantations)}/{SILK_MAX_PLANTATIONS})",
                callback_data='silk_create_plantation'
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Город Шёлка", callback_data='city_silk')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_create_plantation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню создания плантации."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    is_vip = db.is_vip(user.id)
    
    text = f"{SILK_EMOJIS['investment']} **СОЗДАНИЕ ПЛАНТАЦИИ**\n\n"
    text += f"Доступно септимов: **{player.coins:,}**\n"
    if is_vip:
        text += "🔥 VIP бонусы: +20% урожай, +10% качество, -10% время роста\n"
    text += "\nВыберите уровень инвестиций:\n\n"
    
    keyboard = []
    
    for level, config in SILK_INVESTMENT_LEVELS.items():
        cost = config['cost']
        trees = config['trees']
        grow_time_hours = config['grow_time'] // 3600
        
        # Применить VIP бонус к времени
        if is_vip:
            grow_time_hours = int(grow_time_hours * 0.9)
        
        min_yield = config['min_yield']
        max_yield = config['max_yield']
        
        # Применить VIP бонус к урожаю
        if is_vip:
            min_yield = int(min_yield * 1.2)
            max_yield = int(max_yield * 1.2)
        
        affordable = "✅" if player.coins >= cost else "❌"
        
        text += (
            f"**{level.title()}** {affordable}\n"
            f"💰 Стоимость: {cost:,} септимов\n"
            f"🌳 Деревьев: {trees}\n"
            f"⏱️ Время роста: {grow_time_hours} часов\n"
            f"📈 Ожидаемый доход: {min_yield:,}-{max_yield:,}\n\n"
        )
        
        if player.coins >= cost:
            keyboard.append([
                InlineKeyboardButton(
                    f"Создать {level.title()} ({cost:,} 🪙)",
                    callback_data=f'silk_plant_{level}'
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Мои плантации", callback_data='silk_plantations')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать шёлковый рынок."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    current_prices = silk_city.get_current_silk_prices()
    silk_inventory = silk_city.get_silk_inventory(user.id)
    
    text = f"{SILK_EMOJIS['market']} **ШЁЛКОВЫЙ РЫНОК**\n\n"
    text += "📊 **Текущие цены:**\n"
    
    for silk_type, price in current_prices.items():
        config = SILK_TYPES[silk_type]
        emoji = config['emoji']
        name = config['name']
        text += f"{emoji} {name}: **{price}** 🪙/шт\n"
    
    text += "\n💼 **Ваш инвентарь:**\n"
    
    keyboard = []
    
    if silk_inventory:
        for item in silk_inventory:
            config = SILK_TYPES[item.silk_type]
            emoji = config['emoji']
            name = config['name']
            price = current_prices[item.silk_type]
            total_value = price * item.quantity
            
            text += f"{emoji} {name}: {item.quantity} шт. (стоимость: {total_value:,} 🪙)\n"
            
            # Кнопки продажи
            if item.quantity >= 1:
                keyboard.append([
                    InlineKeyboardButton(
                        f"Продать 1 {emoji} (+{price} 🪙)",
                        callback_data=f'silk_sell_{item.silk_type}_1'
                    )
                ])
            
            if item.quantity >= 5:
                earn_5 = price * 5
                keyboard.append([
                    InlineKeyboardButton(
                        f"Продать 5 {emoji} (+{earn_5} 🪙)",
                        callback_data=f'silk_sell_{item.silk_type}_5'
                    )
                ])
            
            if item.quantity >= 10:
                earn_all = price * item.quantity
                keyboard.append([
                    InlineKeyboardButton(
                        f"Продать всё {emoji} (+{earn_all} 🪙)",
                        callback_data=f'silk_sell_{item.silk_type}_all'
                    )
                ])
    else:
        text += "Инвентарь пуст. Соберите урожай с плантаций!"
    
    keyboard.append([InlineKeyboardButton("🔙 Город Шёлка", callback_data='city_silk')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать инвентарь шёлка."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    silk_inventory = silk_city.get_silk_inventory(user.id)
    
    text = f"{SILK_EMOJIS['inventory']} **ИНВЕНТАРЬ ШЁЛКА**\n\n"
    
    if not silk_inventory:
        text += "Ваш инвентарь шёлка пуст.\nСоберите урожай с плантаций или купите шёлк на рынке!"
    else:
        total_items = sum(item.quantity for item in silk_inventory)
        text += f"Всего предметов: **{total_items}**\n\n"
        
        for item in silk_inventory:
            config = SILK_TYPES[item.silk_type]
            emoji = config['emoji']
            name = config['name']
            quality = _get_quality_description(item.quality_grade)
            
            text += (
                f"{emoji} **{name}**\n"
                f"   Количество: {item.quantity} шт.\n"
                f"   Качество: {quality}\n"
                f"   Произведено: {_format_date(item.produced_at)}\n\n"
            )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Город Шёлка", callback_data='city_silk')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику Города Шёлка."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    stats = silk_city.get_silk_city_stats(user.id)
    
    text = f"{SILK_EMOJIS['stats']} **СТАТИСТИКА ГОРОДА ШЁЛКА**\n\n"
    
    if not stats:
        text += "Статистика пуста. Начните создавать плантации!"
    else:
        text += (
            f"🌱 **Плантации:**\n"
            f"   Активных: {stats.get('active_plantations', 0)}\n"
            f"   Завершённых: {stats.get('completed_plantations', 0)}\n"
            f"   Инвестировано: {stats.get('total_invested', 0):,} 🪙\n\n"
            
            f"🧵 **Шёлк в инвентаре:**\n"
            f"   Всего единиц: {stats.get('total_silk', 0)}\n"
        )
        
        silk_by_type = stats.get('silk_by_type', {})
        for silk_type, quantity in silk_by_type.items():
            if quantity > 0:
                config = SILK_TYPES[silk_type]
                emoji = config['emoji']
                name = config['name']
                text += f"   {emoji} {name}: {quantity}\n"
        
        text += (
            f"\n💰 **Торговля:**\n"
            f"   Продаж: {stats.get('total_sales', 0)}\n"
            f"   Заработано: {stats.get('total_earnings', 0):,} 🪙\n"
            f"   Прибыль: {stats.get('profit', 0):,} 🪙\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Город Шёлка", callback_data='city_silk')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

# --- Обработчики действий ---

async def handle_silk_plant(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str):
    """Обработать создание плантации."""
    query = update.callback_query
    user = query.from_user
    
    result = silk_city.create_plantation(
        user.id, 
        user.username or user.first_name, 
        level
    )
    
    if result["ok"]:
        expected_yield = result["expected_yield"]
        coins_left = result["coins_left"]
        harvest_time_hours = result["harvest_time"] // 3600
        
        await query.answer(
            f"Плантация создана! Ожидаемый доход: {expected_yield:,} 🪙. "
            f"Готова через {harvest_time_hours} ч. Баланс: {coins_left:,}",
            show_alert=True
        )
    else:
        reason = result.get("reason")
        if reason == "insufficient_coins":
            required = result.get("required", 0)
            available = result.get("available", 0)
            await query.answer(
                f"Недостаточно септимов. Нужно: {required:,}, доступно: {available:,}",
                show_alert=True
            )
        elif reason == "max_plantations":
            await query.answer(
                f"Достигнут лимит плантаций ({SILK_MAX_PLANTATIONS}). Завершите существующие.",
                show_alert=True
            )
        else:
            await query.answer("Ошибка создания плантации. Попробуйте позже.", show_alert=True)
    
    # Вернуться к списку плантаций
    await show_silk_plantations(update, context)

async def handle_silk_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE, plantation_id: int):
    """Обработать сбор урожая."""
    query = update.callback_query
    user = query.from_user
    
    result = silk_city.harvest_plantation(user.id, plantation_id)
    
    if result["ok"]:
        silk_gained = result["silk_gained"]
        coins_gained = result["coins_gained"]
        
        # Формируем сообщение о полученном шёлке
        silk_text = []
        for silk_type, quantity in silk_gained.items():
            if quantity > 0:
                config = SILK_TYPES[silk_type]
                emoji = config['emoji']
                name = config['name']
                silk_text.append(f"{emoji} {name}: {quantity}")
        
        silk_summary = ", ".join(silk_text) if silk_text else "шёлка нет"
        
        await query.answer(
            f"Урожай собран! Получено: {silk_summary}. Бонус: +{coins_gained} 🪙",
            show_alert=True
        )
    else:
        reason = result.get("reason")
        if reason == "not_ready":
            await query.answer("Урожай ещё не готов!", show_alert=True)
        elif reason == "plantation_not_found":
            await query.answer("Плантация не найдена.", show_alert=True)
        else:
            await query.answer("Ошибка сбора урожая. Попробуйте позже.", show_alert=True)
    
    # Вернуться к списку плантаций
    await show_silk_plantations(update, context)

async def handle_silk_sell(update: Update, context: ContextTypes.DEFAULT_TYPE, silk_type: str, quantity_str: str):
    """Обработать продажу шёлка."""
    query = update.callback_query
    user = query.from_user
    
    # Определить количество
    if quantity_str == "all":
        # Получить весь доступный шёлк этого типа
        silk_inventory = silk_city.get_silk_inventory(user.id)
        item = next((item for item in silk_inventory if item.silk_type == silk_type), None)
        if not item:
            await query.answer("Шёлк не найден в инвентаре.", show_alert=True)
            return
        quantity = item.quantity
    else:
        try:
            quantity = int(quantity_str)
        except ValueError:
            await query.answer("Некорректное количество.", show_alert=True)
            return
    
    result = silk_city.sell_silk_to_npc(user.id, silk_type, quantity)
    
    if result["ok"]:
        coins_earned = result["coins_earned"]
        price_per_unit = result["price_per_unit"]
        
        config = SILK_TYPES[silk_type]
        emoji = config['emoji']
        name = config['name']
        
        await query.answer(
            f"Продано: {quantity} {emoji} {name} за {coins_earned:,} 🪙 "
            f"({price_per_unit} 🪙/шт)",
            show_alert=True
        )
    else:
        reason = result.get("reason")
        if reason == "insufficient_silk":
            await query.answer("Недостаточно шёлка в инвентаре.", show_alert=True)
        else:
            await query.answer("Ошибка продажи. Попробуйте позже.", show_alert=True)
    
    # Вернуться к рынку
    await show_silk_market(update, context)

# --- Вспомогательные функции ---

async def _edit_or_send_message(query, text: str, reply_markup: InlineKeyboardMarkup):
    """Универсальная функция для редактирования или отправки сообщения."""
    message = query.message
    
    # Если сообщение содержит медиа, удаляем и отправляем новое
    if getattr(message, 'photo', None) or getattr(message, 'document', None) or getattr(message, 'video', None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await query.bot.send_message(
            chat_id=message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        try:
            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except BadRequest:
            await query.bot.send_message(
                chat_id=message.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

def _get_status_emoji(status: str) -> str:
    """Получить эмодзи для статуса плантации."""
    status_emojis = {
        'growing': SILK_EMOJIS['growing'],
        'ready': SILK_EMOJIS['ready'],
        'harvesting': '🔄',
        'completed': '✅'
    }
    return status_emojis.get(status, '❓')

def _get_status_text(status: str) -> str:
    """Получить текст для статуса плантации."""
    status_texts = {
        'growing': 'Растёт',
        'ready': 'Готов к сбору',
        'harvesting': 'Сбор урожая',
        'completed': 'Завершён'
    }
    return status_texts.get(status, 'Неизвестно')

def _get_progress_bar(plantation) -> str:
    """Получить прогресс-бар для плантации."""
    progress = silk_city.calculate_plantation_progress(plantation)
    filled_blocks = progress // 10
    empty_blocks = 10 - filled_blocks
    
    bar = '█' * filled_blocks + '░' * empty_blocks
    return f"🔄 Прогресс: {bar} {progress}%"

def _get_quality_description(quality_grade: int) -> str:
    """Получить описание качества шёлка."""
    if quality_grade >= 400:
        return "🏆 Превосходное"
    elif quality_grade >= 350:
        return "💎 Отличное"
    elif quality_grade >= 300:
        return "⭐ Хорошее"
    elif quality_grade >= 250:
        return "✅ Среднее"
    else:
        return "⚠️ Низкое"

def _format_date(timestamp: int) -> str:
    """Отформатировать дату."""
    try:
        return time.strftime('%d.%m.%Y %H:%M', time.localtime(timestamp))
    except:
        return "Неизвестно"