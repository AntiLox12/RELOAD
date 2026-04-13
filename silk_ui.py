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
    SILK_MAX_PLANTATIONS, SILK_PLANTATIONS_ENABLED, SILK_TRADING_ENABLED,
    ADMIN_USERNAMES
)

# --- Основные функции интерфейса ---

async def show_city_silk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню Города Шёлка."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'
    
    # Получить статистику игрока
    stats = silk_city.get_silk_city_stats(user.id)
    plantations = silk_city.get_player_plantations(user.id)
    active_plantations = len([p for p in plantations if p.status in ['growing', 'ready']])
    
    # Получить общее количество шёлка
    silk_inventory = silk_city.get_silk_inventory(user.id)
    total_silk = sum(item.quantity for item in silk_inventory)
    
    # VIP статус
    if lang == 'en':
        access = db.get_access_profile(user.id, username=getattr(user, 'username', None))
        vip_status = "🔥 V.I.P active" if access.get('acts_like_vip') else ""
    else:
        access = db.get_access_profile(user.id, username=getattr(user, 'username', None))
        vip_status = "🔥 V.I.P активен" if access.get('acts_like_vip') else ""
    vip_line = f"   {vip_status}\n" if vip_status else ""
    
    if lang == 'en':
        text = (
            f"🧵 <b>WELCOME TO SILK CITY</b> 🧵\n\n"
            f"🏛️ <i>The center of silk production and trading!</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>YOUR STATS:</b>\n\n"
            f"{SILK_EMOJIS['plantation']} Active plantations: <b>{active_plantations}</b>\n"
            f"{SILK_EMOJIS['inventory']} Silk in inventory: <b>{total_silk}</b> units\n"
            f"{SILK_EMOJIS['coins']} Coins available: <b>{player.coins:,}</b> 💎\n"
            f"{vip_line}"
            f"\n⭐ Each silk harvest gives <b>+3 rating</b>.\n"
            f"\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>LOCATIONS:</b>\n\n"
            f"🌳 <b>Plantations</b> - create and manage\n"
            f"📊 <b>Market</b> - sell at the best prices\n"
            f"💼 <b>Inventory</b> - view your stock\n"
            f"📈 <b>Statistics</b> - track progress\n\n"
            f"<i>Choose a section:</i>"
        )
    else:
        text = (
            f"🧵 <b>ДОБРО ПОЖАЛОВАТЬ В ГОРОД ШЁЛКА</b> 🧵\n\n"
            f"🏛️ <i>Центр шёлкового производства и торговли тканями!</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>ВАША СТАТИСТИКА:</b>\n\n"
            f"{SILK_EMOJIS['plantation']} Активных плантаций: <b>{active_plantations}</b>\n"
            f"{SILK_EMOJIS['inventory']} Шёлка в инвентаре: <b>{total_silk}</b> единиц\n"
            f"{SILK_EMOJIS['coins']} Доступно септимов: <b>{player.coins:,}</b> 💎\n"
            f"{vip_line}"
            f"\n⭐ Каждый сбор шёлка даёт <b>+3 рейтинга</b>.\n"
            f"\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>ДОСТУПНЫЕ ЛОКАЦИИ:</b>\n\n"
            f"🌳 <b>Плантации</b> - создавайте и управляйте\n"
            f"📊 <b>Рынок</b> - продавайте по лучшим ценам\n"
            f"💼 <b>Инвентарь</b> - просматривайте запасы\n"
            f"📈 <b>Статистика</b> - отслеживайте прогресс\n\n"
            f"<i>Выберите раздел:</i>"
        )
    
    keyboard = [
        [InlineKeyboardButton(f"{SILK_EMOJIS['plantation']} Мои плантации", callback_data='silk_plantations')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['market']} Шёлковый рынок", callback_data='silk_market')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['inventory']} Инвентарь шёлка", callback_data='silk_inventory')],
        [InlineKeyboardButton(f"{SILK_EMOJIS['stats']} Статистика", callback_data='silk_stats')],
        [InlineKeyboardButton("🔙 К городам", callback_data='cities_menu')],
        [InlineKeyboardButton("🏠 В главное меню", callback_data='menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await _edit_or_send_message(query, text, reply_markup)

async def show_silk_plantations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать плантации игрока."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'
    plantations = silk_city.get_player_plantations(user.id)
    
    # Обновить статусы плантаций
    silk_city.update_plantation_statuses()
    plantations = silk_city.get_player_plantations(user.id)  # Обновить после проверки
    
    active_plantations = [p for p in plantations if p.status in ['growing', 'ready']]
    
    if lang == 'en':
        text = f"{SILK_EMOJIS['plantation']} <b>MY PLANTATIONS</b>\n\n⭐ Each harvest gives <b>+3 rating</b>.\n\n"
    else:
        text = f"{SILK_EMOJIS['plantation']} <b>МОИ ПЛАНТАЦИИ</b>\n\n⭐ Каждый сбор даёт <b>+3 рейтинга</b>.\n\n"
    
    if not active_plantations:
        if lang == 'en':
            text += "You don't have any active plantations yet.\nCreate your first plantation!"
        else:
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
    
    # Кнопки для создателя
    is_creator = (user.username in ADMIN_USERNAMES)
    if is_creator:
        growing_plantations = [p for p in active_plantations if p.status == 'growing']
        if growing_plantations:
            if len(growing_plantations) == 1:
                plantation = growing_plantations[0]
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚡ Вырастить сразу: {plantation.plantation_name}",
                        callback_data=f'silk_instant_grow_{plantation.id}'
                    )
                ])
            else:
                # Если несколько растущих плантаций - добавляем кнопку "вырастить все"
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚡ Вырастить все ({len(growing_plantations)} шт.)",
                        callback_data='silk_instant_grow_all'
                    )
                ])
                # И отдельные кнопки для каждой плантации
                for plantation in growing_plantations[:3]:  # Ограничиваем до 3 кнопок
                    keyboard.append([
                        InlineKeyboardButton(
                            f"⚡ Вырастить: {plantation.plantation_name}",
                            callback_data=f'silk_instant_grow_{plantation.id}'
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

    # Проверить, разрешено ли создание плантаций
    if not SILK_PLANTATIONS_ENABLED:
        text = f"{SILK_EMOJIS['investment']} **СОЗДАНИЕ ПЛАНТАЦИЙ**\n\n"
        text += "🚫 **Создание новых плантаций временно отключено**\n\n"
        text += "Пожалуйста, завершите свои текущие плантации и соберите урожай.\n"
        text += "Новые инвестиции будут доступны поле."
        
        keyboard = [[InlineKeyboardButton("🔙 Мои плантации", callback_data='silk_plantations')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await _edit_or_send_message(query, text, reply_markup)
        return

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    access = db.get_access_profile(user.id, username=getattr(user, 'username', None), player=player)
    is_vip = bool(access.get('acts_like_vip'))
    
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
    
    # Проверить, разрешена ли торговля
    if not SILK_TRADING_ENABLED:
        text += "🚫 **Торговля шёлком временно отключена**\n\n"
        text += "Ожидайте восстановления рынка для продажи.\n\n"
    
    text += "📊 **Текущие цены:**\n"
    
    for silk_type, price in current_prices.items():
        config = SILK_TYPES[silk_type]
        emoji = config['emoji']
        name = config['name']
        text += f"{emoji} {name}: **{price}** 🪙/шт\n"
    
    text += "\n💼 **Ваш инвентарь:**\n"
    
    keyboard = []
    
    if silk_inventory and SILK_TRADING_ENABLED:
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
    elif silk_inventory and not SILK_TRADING_ENABLED:
        # Показать инвентарь без кнопок продажи
        for item in silk_inventory:
            config = SILK_TYPES[item.silk_type]
            emoji = config['emoji']
            name = config['name']
            price = current_prices[item.silk_type]
            total_value = price * item.quantity
            
            text += f"{emoji} {name}: {item.quantity} шт. (потенциал: {total_value:,} 🪙)\n"
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
        elif reason == "plantations_disabled":
            await query.answer(
                "🚫 Создание новых плантаций временно отключено. Завершите свои текущие плантации.",
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
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    lang = getattr(player, 'language', 'ru') or 'ru'
    
    result = silk_city.harvest_plantation(user.id, plantation_id)
    
    if result["ok"]:
        silk_gained = result["silk_gained"]
        coins_gained = result["coins_gained"]
        rating_added = int(result.get('rating_added') or 0)
        new_rating = result.get('new_rating')
        
        # Формируем сообщение о полученном шёлке
        silk_text = []
        for silk_type, quantity in silk_gained.items():
            if quantity > 0:
                config = SILK_TYPES[silk_type]
                emoji = config['emoji']
                name = config['name']
                silk_text.append(f"{emoji} {name}: {quantity}")
        
        silk_summary = ", ".join(silk_text) if silk_text else "шёлка нет"

        if lang == 'en':
            msg = f"Harvest collected! Received: {silk_summary}. Bonus: +{coins_gained} 🪙"
            if rating_added > 0:
                msg += f" | ⭐ +{rating_added}"
                if new_rating is not None:
                    msg += f" (Rating: {int(new_rating)})"
        else:
            msg = f"Урожай собран! Получено: {silk_summary}. Бонус: +{coins_gained} 🪙"
            if rating_added > 0:
                msg += f" | ⭐ +{rating_added}"
                if new_rating is not None:
                    msg += f" (Рейтинг: {int(new_rating)})"

        await query.answer(msg, show_alert=True)
    else:
        reason = result.get("reason")
        if reason == "not_ready":
            await query.answer("Harvest is not ready yet!" if lang == 'en' else "Урожай ещё не готов!", show_alert=True)
        elif reason == "plantation_not_found":
            await query.answer("Plantation not found." if lang == 'en' else "Плантация не найдена.", show_alert=True)
        else:
            await query.answer("Harvest error. Try again later." if lang == 'en' else "Ошибка сбора урожая. Попробуйте позже.", show_alert=True)
    
    # Вернуться к списку плантаций
    await show_silk_plantations(update, context)

async def handle_silk_sell(update: Update, context: ContextTypes.DEFAULT_TYPE, silk_type: str, quantity_str: str):
    """Обработать продажу шёлка."""
    query = update.callback_query
    user = query.from_user
    
    # Проверить, разрешена ли торговля шёлком
    if not SILK_TRADING_ENABLED:
        await query.answer(
            "🚫 Продажа шёлка временно отключена. Ожидайте восстановления рынка.",
            show_alert=True
        )
        return
    
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
        elif reason == "trading_disabled":
            await query.answer(
                "🚫 Продажа шёлка временно отключена. Ожидайте восстановления рынка.",
                show_alert=True
            )
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
        await query.get_bot().send_message(
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
        except BadRequest as e:
            # Игнорируем ошибку "сообщение не изменено" — это нормальная ситуация
            if "Message is not modified" in str(e):
                return
            # Для других BadRequest ошибок — отправляем новое сообщение
            await query.get_bot().send_message(
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

# --- Обработчики для создателя ---

async def handle_silk_instant_grow(update: Update, context: ContextTypes.DEFAULT_TYPE, plantation_id: int):
    """Обработать мгновенное выращивание одной плантации."""
    query = update.callback_query
    user = query.from_user
    
    # Проверка прав создателя
    if user.username not in ADMIN_USERNAMES:
        await query.answer("Нет прав: функция доступна только создателю", show_alert=True)
        return
    
    result = silk_city.instant_grow_plantation(user.id, plantation_id)
    
    if result["ok"]:
        plantation_name = result["plantation_name"]
        await query.answer(
            f"⚡ Плантация '{plantation_name}' мгновенно выросла! Можно собирать урожай.",
            show_alert=True
        )
    else:
        reason = result.get("reason")
        if reason == "plantation_not_found":
            await query.answer("Плантация не найдена", show_alert=True)
        elif reason == "not_growing":
            current_status = result.get("current_status", "неизвестный")
            await query.answer(
                f"Плантация не растёт. Текущий статус: {current_status}",
                show_alert=True
            )
        else:
            await query.answer("Ошибка при выращивании плантации", show_alert=True)
    
    # Вернуться к списку плантаций
    await show_silk_plantations(update, context)

async def handle_silk_instant_grow_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать мгновенное выращивание всех плантаций."""
    query = update.callback_query
    user = query.from_user
    
    # Проверка прав создателя
    if user.username not in ADMIN_USERNAMES:
        await query.answer("Нет прав: функция доступна только создателю", show_alert=True)
        return
    
    result = silk_city.instant_grow_all_plantations(user.id)
    
    if result["ok"]:
        count = result["count"]
        plantations = result["plantations"]
        if count == 1:
            await query.answer(
                f"⚡ 1 плантация мгновенно выросла! Можно собирать урожай.",
                show_alert=True
            )
        else:
            await query.answer(
                f"⚡ {count} плантаций мгновенно выросли! Можно собирать урожай.",
                show_alert=True
            )
    else:
        reason = result.get("reason")
        if reason == "no_growing_plantations":
            await query.answer("Нет растущих плантаций для выращивания", show_alert=True)
        else:
            await query.answer("Ошибка при выращивании плантаций", show_alert=True)
    
    # Вернуться к списку плантаций
    await show_silk_plantations(update, context)
