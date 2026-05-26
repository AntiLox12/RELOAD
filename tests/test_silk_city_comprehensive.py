# file: test_silk_city_comprehensive.py
"""
Всесторонние тесты для модуля Город Шёлка (silk_city.py).
Используют in-memory базу данных SQLite для полной изоляции.
"""

import os
import sys
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем корень проекта в пути поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.database as db
from core.database import Player, SilkPlantation, SilkInventory, SilkTransaction
from core.constants import SILK_INVESTMENT_LEVELS, SILK_TYPES
import modules.plantation.silk_city as silk_city



def create_test_player(user_id=123, username="test_player", coins=100000, vip_until=0):
    """Вспомогательная функция для создания тестового игрока."""
    dbs = db.SessionLocal()
    player = Player(
        user_id=user_id,
        username=username,
        display_name="Тестовый Игрок",
        coins=coins,
        vip_until=vip_until,
        rating=0
    )
    dbs.add(player)
    dbs.commit()
    dbs.close()
    return user_id

def test_create_plantation_success():
    """Тест успешного создания плантации."""
    user_id = create_test_player(coins=10000)
    
    # Пробуем создать плантацию уровня starter
    res = silk_city.create_plantation(user_id, "test_player", "starter", "Моя грядка")
    
    assert res["ok"] is True
    assert "plantation_id" in res
    assert res["coins_left"] == 10000 - SILK_INVESTMENT_LEVELS["starter"]["cost"]
    
    # Проверяем запись в БД
    dbs = db.SessionLocal()
    plantation = dbs.query(SilkPlantation).filter(SilkPlantation.id == res["plantation_id"]).first()
    assert plantation is not None
    assert plantation.player_id == user_id
    assert plantation.plantation_name == "Моя грядка"
    assert plantation.investment_level == "starter"
    assert plantation.status == "growing"
    assert plantation.silk_trees_count == SILK_INVESTMENT_LEVELS["starter"]["trees"]
    dbs.close()

def test_create_plantation_insufficient_coins():
    """Тест создания плантации при нехватке монет."""
    user_id = create_test_player(coins=10) # Слишком мало монет
    
    res = silk_city.create_plantation(user_id, "test_player", "starter")
    
    assert res["ok"] is False
    assert res["reason"] == "insufficient_coins"
    assert res["required"] == SILK_INVESTMENT_LEVELS["starter"]["cost"]
    assert res["available"] == 10

def test_create_plantation_max_limit():
    """Тест ограничения на максимальное количество плантаций."""
    user_id = create_test_player(coins=100000)
    
    # Забиваем лимит плантаций
    dbs = db.SessionLocal()
    for i in range(silk_city.SILK_MAX_PLANTATIONS):
        plantation = SilkPlantation(
            player_id=user_id,
            plantation_name=f"Плантация {i}",
            status="growing"
        )
        dbs.add(plantation)
    dbs.commit()
    dbs.close()
    
    # Пробуем создать ещё одну плантацию поверх лимита
    res = silk_city.create_plantation(user_id, "test_player", "starter")
    
    assert res["ok"] is False
    assert res["reason"] == "max_plantations"

def test_create_plantation_disabled(monkeypatch):
    """Тест создания плантации при выключенной системной настройке."""
    user_id = create_test_player(coins=10000)
    
    # Отключаем плантации
    monkeypatch.setattr(silk_city, "SILK_PLANTATIONS_ENABLED", False)
    
    res = silk_city.create_plantation(user_id, "test_player", "starter")
    
    assert res["ok"] is False
    assert res["reason"] == "plantations_disabled"

def test_create_plantation_invalid_level():
    """Тест создания плантации с некорректным уровнем инвестиций."""
    user_id = create_test_player()
    
    res = silk_city.create_plantation(user_id, "test_player", "super_duper_level")
    
    assert res["ok"] is False
    assert res["reason"] == "invalid_level"

def test_create_plantation_vip_bonuses():
    """Тест применения VIP-бонусов при создании плантации."""
    # Создаем VIP игрока (vip_until в будущем)
    future_time = int(time.time()) + 86400
    user_id = create_test_player(coins=100000, vip_until=future_time)
    
    res = silk_city.create_plantation(user_id, "test_player", "standard")
    
    assert res["ok"] is True
    
    # Проверяем, что время роста уменьшилось на VIP коэффициент
    expected_grow_time = int(SILK_INVESTMENT_LEVELS["standard"]["grow_time"] * silk_city.SILK_VIP_BONUSES['growth_speedup'])
    assert res["harvest_time"] == expected_grow_time

def test_harvest_plantation_success():
    """Тест успешного сбора урожая."""
    user_id = create_test_player(coins=0)
    
    # Создаем готовую к сбору плантацию
    dbs = db.SessionLocal()
    plantation = SilkPlantation(
        player_id=user_id,
        plantation_name="Тестовая спелая",
        investment_level="starter",
        expected_yield=100,
        status="ready"
    )
    dbs.add(plantation)
    dbs.commit()
    plantation_id = plantation.id
    dbs.close()
    
    # Собираем урожай
    res = silk_city.harvest_plantation(user_id, plantation_id)
    
    assert res["ok"] is True
    assert "silk_gained" in res
    assert res["coins_gained"] >= 50
    assert res["coins_gained"] <= 150
    assert res["rating_added"] == 3
    assert res["new_rating"] == 3
    
    # Проверяем статус плантации в БД
    dbs = db.SessionLocal()
    updated_plantation = dbs.query(SilkPlantation).filter(SilkPlantation.id == plantation_id).first()
    assert updated_plantation.status == "completed"
    
    # Проверяем, что шёлк добавлен в инвентарь
    inventory_items = dbs.query(SilkInventory).filter(SilkInventory.player_id == user_id).all()
    assert len(inventory_items) > 0
    total_quantity = sum(item.quantity for item in inventory_items)
    assert total_quantity > 0
    
    # Баланс игрока увеличился
    player = dbs.query(Player).filter(Player.user_id == user_id).first()
    assert player.coins == res["coins_gained"]
    dbs.close()

def test_harvest_plantation_not_ready():
    """Тест попытки собрать недозревший урожай."""
    user_id = create_test_player()
    
    # Создаем растущую плантацию со временем готовности в будущем
    dbs = db.SessionLocal()
    plantation = SilkPlantation(
        player_id=user_id,
        plantation_name="Растущая",
        status="growing",
        harvest_ready_at=int(time.time()) + 3600
    )
    dbs.add(plantation)
    dbs.commit()
    plantation_id = plantation.id
    dbs.close()
    
    res = silk_city.harvest_plantation(user_id, plantation_id)
    
    assert res["ok"] is False
    assert res["reason"] == "not_ready"

def test_harvest_plantation_auto_ready():
    """Тест сбора урожая, который созрел во время роста."""
    user_id = create_test_player()
    
    # Создаем плантацию, которая "выросла" (время готовности в прошлом)
    dbs = db.SessionLocal()
    plantation = SilkPlantation(
        player_id=user_id,
        plantation_name="Созревшая в прошлом",
        status="growing",
        harvest_ready_at=int(time.time()) - 100,
        expected_yield=50,
        investment_level="starter"
    )
    dbs.add(plantation)
    dbs.commit()
    plantation_id = plantation.id
    dbs.close()
    
    res = silk_city.harvest_plantation(user_id, plantation_id)
    
    assert res["ok"] is True
    assert res["coins_gained"] > 0

def test_harvest_plantation_not_found():
    """Тест сбора урожая с несуществующей плантации."""
    user_id = create_test_player()
    
    res = silk_city.harvest_plantation(user_id, 9999) # Неверный id
    
    assert res["ok"] is False
    assert res["reason"] == "plantation_not_found"

def test_sell_silk_to_npc_success():
    """Тест успешной продажи шёлка NPC."""
    user_id = create_test_player(coins=0)
    
    # Добавляем премиум шёлк в инвентарь
    dbs = db.SessionLocal()
    item = SilkInventory(
        player_id=user_id,
        silk_type="premium",
        quantity=5,
        quality_grade=400 # Высокое качество
    )
    dbs.add(item)
    dbs.commit()
    dbs.close()
    
    # Продаем 3 единицы шёлка
    res = silk_city.sell_silk_to_npc(user_id, "premium", 3)
    
    assert res["ok"] is True
    assert res["coins_earned"] > 0
    assert res["price_per_unit"] > 0
    
    # Проверяем остаток в инвентаре
    dbs = db.SessionLocal()
    remaining_item = dbs.query(SilkInventory).filter(SilkInventory.player_id == user_id, SilkInventory.silk_type == "premium").first()
    assert remaining_item.quantity == 2
    
    # Проверяем создание транзакции
    transaction = dbs.query(SilkTransaction).filter(SilkTransaction.seller_id == user_id).first()
    assert transaction is not None
    assert transaction.amount == 3
    assert transaction.silk_type == "premium"
    assert transaction.transaction_type == "npc_sale"
    assert transaction.total_price == res["coins_earned"]
    dbs.close()

def test_sell_silk_to_npc_insufficient_silk():
    """Тест продажи шёлка при его нехватке."""
    user_id = create_test_player()
    
    # Пробуем продать шёлк, которого нет в инвентаре
    res = silk_city.sell_silk_to_npc(user_id, "raw", 1)
    
    assert res["ok"] is False
    assert res["reason"] == "insufficient_silk"

def test_sell_silk_to_npc_disabled(monkeypatch):
    """Тест продажи шёлка при отключенном рынке."""
    user_id = create_test_player()
    
    monkeypatch.setattr(silk_city, "SILK_TRADING_ENABLED", False)
    
    res = silk_city.sell_silk_to_npc(user_id, "raw", 1)
    
    assert res["ok"] is False
    assert res["reason"] == "trading_disabled"

def test_sell_silk_to_npc_invalid_parameters():
    """Тест продажи шёлка с неверными параметрами."""
    user_id = create_test_player()
    
    # Неверный тип шёлка
    res1 = silk_city.sell_silk_to_npc(user_id, "unknown_silk", 1)
    assert res1["ok"] is False
    assert res1["reason"] == "invalid_parameters"
    
    # Отрицательное количество
    res2 = silk_city.sell_silk_to_npc(user_id, "raw", -5)
    assert res2["ok"] is False
    assert res2["reason"] == "invalid_parameters"

def test_update_plantation_statuses():
    """Тест автоматического обновления статусов плантаций."""
    user_id = create_test_player()
    current_time = int(time.time())
    
    dbs = db.SessionLocal()
    # Плантация, которая должна созреть
    p1 = SilkPlantation(player_id=user_id, status="growing", harvest_ready_at=current_time - 10)
    # Плантация, которая ещё не должна созреть
    p2 = SilkPlantation(player_id=user_id, status="growing", harvest_ready_at=current_time + 100)
    
    dbs.add_all([p1, p2])
    dbs.commit()
    p1_id, p2_id = p1.id, p2.id
    dbs.close()
    
    count = silk_city.update_plantation_statuses()
    
    assert count == 1
    
    dbs = db.SessionLocal()
    assert dbs.query(SilkPlantation).filter(SilkPlantation.id == p1_id).first().status == "ready"
    assert dbs.query(SilkPlantation).filter(SilkPlantation.id == p2_id).first().status == "growing"
    dbs.close()

def test_instant_grow_plantation():
    """Тест функции мгновенного выращивания одной плантации."""
    user_id = create_test_player()
    
    dbs = db.SessionLocal()
    p = SilkPlantation(player_id=user_id, plantation_name="Медленная", status="growing", harvest_ready_at=int(time.time()) + 1000)
    dbs.add(p)
    dbs.commit()
    plantation_id = p.id
    dbs.close()
    
    res = silk_city.instant_grow_plantation(user_id, plantation_id)
    
    assert res["ok"] is True
    assert res["plantation_name"] == "Медленная"
    
    dbs = db.SessionLocal()
    updated_p = dbs.query(SilkPlantation).filter(SilkPlantation.id == plantation_id).first()
    assert updated_p.status == "ready"
    assert updated_p.harvest_ready_at <= int(time.time())
    dbs.close()

def test_instant_grow_all_plantations():
    """Тест функции мгновенного выращивания всех плантаций."""
    user_id = create_test_player()
    
    dbs = db.SessionLocal()
    p1 = SilkPlantation(player_id=user_id, plantation_name="Плантация 1", status="growing", harvest_ready_at=int(time.time()) + 1000)
    p2 = SilkPlantation(player_id=user_id, plantation_name="Плантация 2", status="growing", harvest_ready_at=int(time.time()) + 2000)
    p3 = SilkPlantation(player_id=user_id, plantation_name="Плантация 3", status="completed") # Уже завершена
    
    dbs.add_all([p1, p2, p3])
    dbs.commit()
    p1_id, p2_id, p3_id = p1.id, p2.id, p3.id
    dbs.close()
    
    res = silk_city.instant_grow_all_plantations(user_id)
    
    assert res["ok"] is True
    assert res["count"] == 2
    assert "Плантация 1" in res["plantations"]
    assert "Плантация 2" in res["plantations"]
    
    dbs = db.SessionLocal()
    assert dbs.query(SilkPlantation).filter(SilkPlantation.id == p1_id).first().status == "ready"
    assert dbs.query(SilkPlantation).filter(SilkPlantation.id == p2_id).first().status == "ready"
    assert dbs.query(SilkPlantation).filter(SilkPlantation.id == p3_id).first().status == "completed"
    dbs.close()

def test_get_silk_city_stats():
    """Тест получения корректной статистики игрока по Городу Шёлка."""
    user_id = create_test_player()
    
    dbs = db.SessionLocal()
    # Активная плантация
    dbs.add(SilkPlantation(player_id=user_id, status="growing", investment_cost=1000))
    # Завершённая плантация
    dbs.add(SilkPlantation(player_id=user_id, status="completed", investment_cost=2000))
    # Шёлк в инвентаре
    dbs.add(SilkInventory(player_id=user_id, silk_type="raw", quantity=10))
    dbs.add(SilkInventory(player_id=user_id, silk_type="refined", quantity=5))
    # Продажи NPC
    dbs.add(SilkTransaction(seller_id=user_id, transaction_type="npc_sale", total_price=5000))
    dbs.commit()
    dbs.close()
    
    stats = silk_city.get_silk_city_stats(user_id)
    
    assert stats["active_plantations"] == 1
    assert stats["completed_plantations"] == 1
    assert stats["total_invested"] == 3000
    assert stats["total_silk"] == 15
    assert stats["silk_by_type"]["raw"] == 10
    assert stats["silk_by_type"]["refined"] == 5
    assert stats["total_sales"] == 1
    assert stats["total_earnings"] == 5000
    assert stats["profit"] == 2000 # 5000 - 3000

def test_format_time_remaining():
    """Тест форматирования оставшегося времени."""
    current_time = int(time.time())
    
    # Готово
    assert silk_city.format_time_remaining(current_time - 10) == "Готово!"
    
    # Секунды
    assert silk_city.format_time_remaining(current_time + 45) == "45 сек"
    
    # Минуты
    assert silk_city.format_time_remaining(current_time + 150) == "2 мин 30 сек"
    
    # Часы
    assert silk_city.format_time_remaining(current_time + 7500) == "2 ч 5 мин"
