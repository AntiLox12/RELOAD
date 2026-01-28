# file: silk_city.py
"""
Модуль для системы Город Шёлка.
Содержит функции управления шёлковыми плантациями, торговлей и экономикой.
"""

import time
import random
import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import sessionmaker, joinedload
from database import (
    SessionLocal, SilkPlantation, SilkInventory, SilkTransaction, 
    Player, get_or_create_player
)
import database as db
from constants import (
    SILK_INVESTMENT_LEVELS, SILK_TYPES, SILK_QUALITY_RANGE, 
    SILK_WEATHER_RANGE, SILK_VIP_BONUSES, SILK_MAX_PLANTATIONS,
    SILK_MARKET_PRICES, SILK_MAX_YIELD_PER_PLANTATION, 
    SILK_MAX_QUALITY_GRADE, SILK_MIN_QUALITY_GRADE, SILK_MAX_SALE_AMOUNT,
    SILK_PLANTATIONS_ENABLED, SILK_TRADING_ENABLED
)

logger = logging.getLogger(__name__)

# --- Функции безопасности ---

def log_suspicious_activity(user_id: int, activity_type: str, details: Dict):
    """Логирование подозрительной активности."""
    logger.warning(f"[SILK_SECURITY] User {user_id} - {activity_type}: {details}")

def validate_yield_amount(yield_amount: int, plantation_level: str) -> int:
    """Проверка и ограничение количества урожая."""
    max_expected = SILK_INVESTMENT_LEVELS[plantation_level]['max_yield'] * 3  # Макс с бонусами
    return max(0, min(yield_amount, min(max_expected, SILK_MAX_YIELD_PER_PLANTATION)))

def validate_quality_grade(quality_grade: int) -> int:
    """Проверка и ограничение уровня качества."""
    return max(SILK_MIN_QUALITY_GRADE, min(quality_grade, SILK_MAX_QUALITY_GRADE))

# --- Основные функции управления плантациями ---

def get_player_plantations(user_id: int) -> List[SilkPlantation]:
    """Получить все плантации игрока."""
    dbs = SessionLocal()
    try:
        plantations = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.player_id == user_id)
            .order_by(SilkPlantation.id.asc())
            .all()
        )
        return list(plantations)
    finally:
        dbs.close()

def create_plantation(user_id: int, username: str, investment_level: str, plantation_name: str = None) -> Dict:
    """
    Создать новую шёлковую плантацию.
    
    Returns:
        dict: {ok: bool, reason?: str, plantation_id?: int, coins_left?: int}
    """
    # Проверить, разрешено ли создание новых плантаций
    if not SILK_PLANTATIONS_ENABLED:
        return {"ok": False, "reason": "plantations_disabled"}
    
    if investment_level not in SILK_INVESTMENT_LEVELS:
        return {"ok": False, "reason": "invalid_level"}
    
    dbs = SessionLocal()
    try:
        # Проверить количество существующих плантаций
        existing_count = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.player_id == user_id)
            .filter(SilkPlantation.status.in_(['growing', 'ready', 'harvesting']))
            .count()
        )
        
        if existing_count >= SILK_MAX_PLANTATIONS:
            return {"ok": False, "reason": "max_plantations"}
        
        # Получить игрока и проверить баланс
        player = get_or_create_player(user_id, username)
        level_config = SILK_INVESTMENT_LEVELS[investment_level]
        cost = level_config['cost']
        
        if player.coins < cost:
            return {"ok": False, "reason": "insufficient_coins", "required": cost, "available": player.coins}
        
        # Списать монеты
        dbs.query(Player).filter(Player.user_id == user_id).update({
            Player.coins: Player.coins - cost
        })
        
        # Создать плантацию
        current_time = int(time.time())
        is_vip = db.is_vip(user_id)
        
        # Применить VIP бонус к времени роста
        grow_time = level_config['grow_time']
        if is_vip:
            grow_time = int(grow_time * SILK_VIP_BONUSES['growth_speedup'])
        
        # Генерировать модификаторы качества и погоды
        quality_mod = random.randint(*SILK_QUALITY_RANGE)
        weather_mod = random.randint(*SILK_WEATHER_RANGE)
        
        # VIP бонус к качеству
        if is_vip:
            quality_mod = min(120, quality_mod + SILK_VIP_BONUSES['quality_bonus'])
        
        # Рассчитать ожидаемый урожай
        base_yield = random.randint(level_config['min_yield'], level_config['max_yield'])
        expected_yield = int(base_yield * (quality_mod / 100) * (weather_mod / 100))
        
        if is_vip:
            expected_yield = int(expected_yield * SILK_VIP_BONUSES['yield_multiplier'])
        
        # Генерировать название если не задано
        if not plantation_name:
            plantation_names = [
                "Изумрудная долина", "Золотые поля", "Серебряный сад",
                "Лунная роща", "Утренняя роса", "Вечерний бриз",
                "Шёлковый рай", "Нефритовая плантация", "Янтарные деревья"
            ]
            plantation_name = random.choice(plantation_names)
        
        plantation = SilkPlantation(
            player_id=user_id,
            plantation_name=plantation_name,
            silk_trees_count=level_config['trees'],
            planted_at=current_time,
            harvest_ready_at=current_time + grow_time,
            status='growing',
            investment_cost=cost,
            expected_yield=expected_yield,
            investment_level=investment_level,
            quality_modifier=quality_mod,
            weather_modifier=weather_mod
        )
        
        dbs.add(plantation)
        dbs.commit()
        dbs.refresh(plantation)
        
        # Получить новый баланс
        updated_player = dbs.query(Player).filter(Player.user_id == user_id).first()
        
        logger.info(f"[SILK] User {username} ({user_id}) created plantation: {investment_level}, cost: {cost}, expected: {expected_yield}")
        
        return {
            "ok": True,
            "plantation_id": plantation.id,
            "coins_left": updated_player.coins,
            "expected_yield": expected_yield,
            "harvest_time": grow_time
        }
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error creating plantation for user {user_id}: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def harvest_plantation(user_id: int, plantation_id: int) -> Dict:
    """
    Собрать урожай с плантации.
    
    Returns:
        dict: {ok: bool, reason?: str, silk_gained?: Dict, coins_gained?: int}
    """
    dbs = SessionLocal()
    try:
        plantation = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.id == plantation_id, SilkPlantation.player_id == user_id)
            .first()
        )
        
        if not plantation:
            return {"ok": False, "reason": "plantation_not_found"}
        
        if plantation.status != 'ready':
            current_time = int(time.time())
            if plantation.status == 'growing' and current_time >= plantation.harvest_ready_at:
                # Автоматически обновить статус
                plantation.status = 'ready'
                dbs.commit()
            else:
                return {"ok": False, "reason": "not_ready"}
        
        # Обновить статус плантации
        plantation.status = 'completed'
        
        # Рассчитать количество и тип получаемого шёлка
        silk_gained = calculate_silk_harvest(plantation)
        
        # Добавить шёлк в инвентарь
        for silk_type, quantity in silk_gained.items():
            if quantity > 0:
                add_silk_to_inventory(user_id, silk_type, quantity)
        
        # Рассчитать бонусные монеты (небольшая награда за успешный сбор)
        bonus_coins = random.randint(50, 150)
        is_vip = db.is_vip(user_id)
        if is_vip:
            bonus_coins = int(bonus_coins * 1.5)
        
        # Добавить монеты игроку
        dbs.query(Player).filter(Player.user_id == user_id).update({
            Player.coins: Player.coins + bonus_coins
        })
        
        dbs.commit()

        rating_added = 3
        new_rating = db.increment_rating(user_id, rating_added)
        
        logger.info(f"[SILK] User {user_id} harvested plantation {plantation_id}: {silk_gained}, +{bonus_coins} coins")
        
        return {
            "ok": True,
            "silk_gained": silk_gained,
            "coins_gained": bonus_coins,
            "rating_added": int(rating_added),
            "new_rating": int(new_rating) if new_rating is not None else None,
        }
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error harvesting plantation {plantation_id} for user {user_id}: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def calculate_silk_harvest(plantation: SilkPlantation) -> Dict[str, int]:
    """Рассчитать количество и тип шёлка от урожая."""
    total_yield = max(0, min(plantation.expected_yield, 10000))  # Ограничиваем максимальный урожай
    silk_distribution = {}
    
    # Распределяем урожай по типам шёлка согласно вероятностям
    allocated_yield = 0
    
    for silk_type, config in SILK_TYPES.items():
        probability = config['probability'] / 100.0
        # Фиксируем баг с отрицательным remaining_yield
        base_amount = int(total_yield * probability)
        variance = random.uniform(0.8, 1.2)
        type_yield = int(base_amount * variance)
        
        # Убеждаемся, что не превышаем общий урожай
        type_yield = max(0, min(type_yield, total_yield - allocated_yield))
        
        if type_yield > 0:
            silk_distribution[silk_type] = type_yield
            allocated_yield += type_yield
    
    # Остаток распределяем в сырой шёлк
    remaining = total_yield - allocated_yield
    if remaining > 0:
        silk_distribution['raw'] = silk_distribution.get('raw', 0) + remaining
    
    return silk_distribution

def update_plantation_statuses():
    """Обновить статусы всех плантаций (вызывается периодически)."""
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        
        # Найти плантации, которые готовы к сбору
        ready_plantations = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.status == 'growing')
            .filter(SilkPlantation.harvest_ready_at <= current_time)
            .all()
        )
        
        for plantation in ready_plantations:
            plantation.status = 'ready'
        
        if ready_plantations:
            dbs.commit()
            logger.info(f"[SILK] Updated {len(ready_plantations)} plantations to ready status")
        
        return len(ready_plantations)
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error updating plantation statuses: {e}")
        return 0
    finally:
        dbs.close()

# --- Функции управления инвентарём шёлка ---

def get_silk_inventory(user_id: int) -> List[SilkInventory]:
    """Получить инвентарь шёлка игрока."""
    dbs = SessionLocal()
    try:
        inventory = (
            dbs.query(SilkInventory)
            .filter(SilkInventory.player_id == user_id)
            .filter(SilkInventory.quantity > 0)
            .order_by(SilkInventory.silk_type.asc())
            .all()
        )
        return list(inventory)
    finally:
        dbs.close()

def add_silk_to_inventory(user_id: int, silk_type: str, quantity: int) -> bool:
    """Добавить шёлк в инвентарь игрока."""
    if silk_type not in SILK_TYPES or quantity <= 0:
        return False
    
    dbs = SessionLocal()
    try:
        # Найти существующую запись
        existing = (
            dbs.query(SilkInventory)
            .filter(SilkInventory.player_id == user_id, SilkInventory.silk_type == silk_type)
            .first()
        )
        
        if existing:
            existing.quantity += quantity
        else:
            new_item = SilkInventory(
                player_id=user_id,
                silk_type=silk_type,
                quantity=quantity,
                quality_grade=random.randint(250, 350)  # случайное качество
            )
            dbs.add(new_item)
        
        dbs.commit()
        return True
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error adding silk to inventory for user {user_id}: {e}")
        return False
    finally:
        dbs.close()

# --- Функции торговли ---

def sell_silk_to_npc(user_id: int, silk_type: str, quantity: int) -> Dict:
    """
    Продать шёлк NPC торговцу.
    
    Returns:
        dict: {ok: bool, reason?: str, coins_earned?: int, price_per_unit?: int}
    """
    # Проверить, разрешена ли торговля шёлком
    if not SILK_TRADING_ENABLED:
        return {"ok": False, "reason": "trading_disabled"}
    
    if silk_type not in SILK_TYPES or quantity <= 0:
        return {"ok": False, "reason": "invalid_parameters"}
    
    dbs = SessionLocal()
    try:
        # Найти шёлк в инвентаре
        inventory_item = (
            dbs.query(SilkInventory)
            .filter(SilkInventory.player_id == user_id, SilkInventory.silk_type == silk_type)
            .filter(SilkInventory.quantity >= quantity)
            .first()
        )
        
        if not inventory_item:
            return {"ok": False, "reason": "insufficient_silk"}
        
        # Рассчитать цену с учётом рыночной динамики
        base_price = SILK_TYPES[silk_type]['base_price']
        market_range = SILK_MARKET_PRICES[silk_type]
        current_price = random.randint(market_range['min'], market_range['max'])
        
        # Учесть качество шёлка с безопасными ограничениями
        validated_quality = validate_quality_grade(inventory_item.quality_grade)
        quality_bonus = (validated_quality - 300) / 300.0 * 0.2  # ±20% от качества
        quality_bonus = max(-0.3, min(quality_bonus, 0.5))  # Ограничиваем бонус -30% до +50%
        final_price = max(1, int(current_price * (1 + quality_bonus)))  # Минимум 1 монета
        
        # Ограничиваем максимальную сумму продажи
        max_total_earnings = SILK_MAX_SALE_AMOUNT  # Максимум за одну продажу
        total_earnings = min(final_price * quantity, max_total_earnings)
        
        # Логируем подозрительные продажи
        if total_earnings > 50000:
            log_suspicious_activity(user_id, "high_silk_sale", {
                "silk_type": silk_type,
                "quantity": quantity,
                "final_price": final_price,
                "total_earnings": total_earnings,
                "quality_grade": inventory_item.quality_grade
            })
        
        # Убрать шёлк из инвентаря
        inventory_item.quantity -= quantity
        if inventory_item.quantity <= 0:
            dbs.delete(inventory_item)
        
        # Добавить монеты игроку
        dbs.query(Player).filter(Player.user_id == user_id).update({
            Player.coins: Player.coins + total_earnings
        })
        
        # Записать транзакцию
        transaction = SilkTransaction(
            seller_id=user_id,
            buyer_id=None,  # NPC покупка
            transaction_type='npc_sale',
            silk_type=silk_type,
            amount=quantity,
            price_per_unit=final_price,
            total_price=total_earnings
        )
        dbs.add(transaction)
        
        dbs.commit()
        
        logger.info(f"[SILK] User {user_id} sold {quantity} {silk_type} silk for {total_earnings} coins")
        
        return {
            "ok": True,
            "coins_earned": total_earnings,
            "price_per_unit": final_price
        }
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error selling silk for user {user_id}: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def get_current_silk_prices() -> Dict[str, int]:
    """Получить текущие рыночные цены на шёлк."""
    prices = {}
    for silk_type, market_range in SILK_MARKET_PRICES.items():
        # Имитируем рыночную динамику
        prices[silk_type] = random.randint(market_range['min'], market_range['max'])
    return prices

# --- Статистические функции ---

def get_silk_city_stats(user_id: int) -> Dict:
    """Получить статистику игрока по Городу Шёлка."""
    dbs = SessionLocal()
    try:
        # Статистика плантаций
        plantations = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.player_id == user_id)
            .all()
        )
        
        active_plantations = len([p for p in plantations if p.status in ['growing', 'ready']])
        completed_plantations = len([p for p in plantations if p.status == 'completed'])
        total_invested = sum(p.investment_cost for p in plantations)
        
        # Статистика инвентаря
        silk_inventory = get_silk_inventory(user_id)
        total_silk = sum(item.quantity for item in silk_inventory)
        
        # Статистика транзакций
        transactions = (
            dbs.query(SilkTransaction)
            .filter(SilkTransaction.seller_id == user_id)
            .all()
        )
        
        total_sales = len(transactions)
        total_earnings = sum(t.total_price for t in transactions)
        
        return {
            "active_plantations": active_plantations,
            "completed_plantations": completed_plantations,
            "total_invested": total_invested,
            "total_silk": total_silk,
            "silk_by_type": {item.silk_type: item.quantity for item in silk_inventory},
            "total_sales": total_sales,
            "total_earnings": total_earnings,
            "profit": total_earnings - total_invested
        }
        
    except Exception as e:
        logger.error(f"[SILK] Error getting stats for user {user_id}: {e}")
        return {}
    finally:
        dbs.close()

def get_plantation_details(plantation_id: int, user_id: int) -> Optional[SilkPlantation]:
    """Получить детали конкретной плантации."""
    dbs = SessionLocal()
    try:
        plantation = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.id == plantation_id, SilkPlantation.player_id == user_id)
            .first()
        )
        return plantation
    finally:
        dbs.close()

def get_ready_plantations_for_notification(user_id: int) -> List[SilkPlantation]:
    """Получить плантации готовые к уведомлению о сборе урожая."""
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        plantations = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.player_id == user_id)
            .filter(SilkPlantation.status == 'ready')
            .all()
        )
        return list(plantations)
    finally:
        dbs.close()

def instant_grow_plantation(user_id: int, plantation_id: int) -> Dict:
    """
    Мгновенно вырастить плантацию (функция для создателя).
    
    Returns:
        dict: {ok: bool, reason?: str, plantation_name?: str}
    """
    dbs = SessionLocal()
    try:
        plantation = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.id == plantation_id, SilkPlantation.player_id == user_id)
            .first()
        )
        
        if not plantation:
            return {"ok": False, "reason": "plantation_not_found"}
        
        if plantation.status != 'growing':
            return {"ok": False, "reason": "not_growing", "current_status": plantation.status}
        
        # Мгновенно завершить рост
        current_time = int(time.time())
        plantation.harvest_ready_at = current_time
        plantation.status = 'ready'
        
        dbs.commit()
        
        logger.info(f"[SILK] Instant grow: User {user_id} plantation {plantation_id} ({plantation.plantation_name})")
        
        return {
            "ok": True,
            "plantation_name": plantation.plantation_name
        }
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error instant growing plantation {plantation_id} for user {user_id}: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def instant_grow_all_plantations(user_id: int) -> Dict:
    """
    Мгновенно вырастить все растущие плантации игрока (функция для создателя).
    
    Returns:
        dict: {ok: bool, count?: int, plantations?: List[str]}
    """
    dbs = SessionLocal()
    try:
        growing_plantations = (
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.player_id == user_id)
            .filter(SilkPlantation.status == 'growing')
            .all()
        )
        
        if not growing_plantations:
            return {"ok": False, "reason": "no_growing_plantations"}
        
        # Мгновенно завершить рост для всех плантаций
        current_time = int(time.time())
        plantation_names = []
        
        for plantation in growing_plantations:
            plantation.harvest_ready_at = current_time
            plantation.status = 'ready'
            plantation_names.append(plantation.plantation_name)
        
        dbs.commit()
        
        logger.info(f"[SILK] Instant grow all: User {user_id} grew {len(growing_plantations)} plantations")
        
        return {
            "ok": True,
            "count": len(growing_plantations),
            "plantations": plantation_names
        }
        
    except Exception as e:
        try:
            dbs.rollback()
        except:
            pass
        logger.error(f"[SILK] Error instant growing all plantations for user {user_id}: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

# --- Утилиты ---

def format_time_remaining(timestamp: int) -> str:
    """Отформатировать оставшееся время до события."""
    current_time = int(time.time())
    if timestamp <= current_time:
        return "Готово!"
    
    remaining = timestamp - current_time
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours} ч {minutes} мин"
    elif minutes > 0:
        return f"{minutes} мин {seconds} сек"
    else:
        return f"{seconds} сек"

def calculate_plantation_progress(plantation: SilkPlantation) -> int:
    """Рассчитать прогресс роста плантации в процентах."""
    if plantation.status == 'completed':
        return 100
    
    current_time = int(time.time())
    total_time = plantation.harvest_ready_at - plantation.planted_at
    elapsed_time = current_time - plantation.planted_at
    
    if total_time <= 0:
        return 100
    
    progress = int((elapsed_time / total_time) * 100)
    return min(100, max(0, progress))