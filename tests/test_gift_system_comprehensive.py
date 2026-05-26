# file: test_gift_system_comprehensive.py
"""
Всесторонние тесты для модуля Системы Подарков (gift_system.py).
Используют in-memory базу данных SQLite для изоляции и моки для Telegram API.
"""

import os
import sys
import time
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Добавляем корень проекта в пути поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.database as db
from core.database import Player, InventoryItem, EnergyDrink, GiftRestriction, GiftHistory, ActionLog, BotSetting
from modules.gift.gift_system import GiftFeature



def build_gift_feature(logger=None) -> GiftFeature:
    """Вспомогательная функция для создания тестового GiftFeature."""
    async def _not_banned(*args, **kwargs):
        return False

    async def _async_noop(*args, **kwargs):
        return None

    return GiftFeature(
        logger=logger or SimpleNamespace(exception=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None),
        abort_if_banned=_not_banned,
        register_group_if_needed=_async_noop,
        reply_auto_delete_message=_async_noop,
        schedule_auto_delete_message=_async_noop,
        get_rarity_emoji=lambda rarity: "⭐",
        get_lock=lambda key: asyncio.Lock(),
    )

def setup_test_data(giver_id=111, recipient_id=222):
    """Наполняет тестовую БД пользователями, напитками и инвентарем."""
    dbs = db.SessionLocal()
    
    # Включаем защиту подарков в настройках
    dbs.add(BotSetting(key="gift_autoblock_enabled", value="1"))
    dbs.add(BotSetting(key="gift_autoblock_consecutive_limit", value="3"))
    dbs.add(BotSetting(key="gift_autoblock_duration_sec", value="3600"))
    
    # Добавляем игроков
    giver = Player(user_id=giver_id, username="giver_user", display_name="Даритель", coins=5000)
    recipient = Player(user_id=recipient_id, username="recip_user", display_name="Получатель", coins=100)
    dbs.add_all([giver, recipient])
    
    # Добавляем напитки
    drink1 = EnergyDrink(id=1, name="Cola Energy", description="Вкусная кола")
    drink2 = EnergyDrink(id=2, name="Flash Up", description="Классический энергетик")
    dbs.add_all([drink1, drink2])
    
    # Добавляем предметы в инвентарь гивера
    inv1 = InventoryItem(id=10, player_id=giver_id, drink_id=1, rarity="Basic", quantity=5)
    inv2 = InventoryItem(id=20, player_id=giver_id, drink_id=2, rarity="Epic", quantity=2)
    dbs.add_all([inv1, inv2])
    
    dbs.commit()
    dbs.close()

# --- Тест 1: Базовое управление корзиной (Cart) ---

def test_cart_management():
    setup_test_data()
    feature = build_gift_feature()
    
    giver_id = 111
    
    # Создаем сессию выбора
    feature.selection_state[giver_id] = {
        "created_at": int(time.time()),
        "recipient_id": 222,
        "max_gifts": 10,
        "cart": {},
        "inventory_items": db.get_player_inventory_with_details(giver_id),
    }
    
    state = feature.selection_state[giver_id]
    
    # Добавляем предметы в корзину через утилиты изменения количества
    # item_id 10 (Cola Energy x5)
    # Имитируем вызов изменения количества
    query = SimpleNamespace(from_user=SimpleNamespace(id=giver_id), answer=AsyncMock(), edit_message_text=AsyncMock())
    
    # Добавим 2 шт.
    asyncio.run(feature._change_item_quantity(query, 10, 2))
    assert state["cart"][10] == 2
    assert feature._selected_total(state) == 2
    
    # Добавим еще 2 шт.
    asyncio.run(feature._change_item_quantity(query, 10, 2))
    assert state["cart"][10] == 4
    
    # Попробуем добавить больше доступного (в инвентаре всего 5)
    asyncio.run(feature._change_item_quantity(query, 10, 3))
    assert state["cart"][10] == 5 # Должно ограничиться 5
    
    # Уменьшим на 2
    asyncio.run(feature._change_item_quantity(query, 10, -2))
    assert state["cart"][10] == 3
    
    # Сбросим эту позицию
    asyncio.run(feature._clear_item_quantity(query, 10))
    assert 10 not in state["cart"]

# --- Тест 2: Очистка старых данных (Cleanup Stale) ---

def test_cleanup_stale():
    feature = build_gift_feature()
    now = int(time.time())
    
    # Создаем старое предложение (истекло более 10 минут назад)
    feature.gift_offers[999] = {
        "created_at": now - 700, # 11 минут назад
        "giver_id": 111
    }
    
    # Создаем свежее предложение
    feature.gift_offers[888] = {
        "created_at": now - 100, # 1.5 минуты назад
        "giver_id": 111
    }
    
    # Создаем старую сессию выбора
    feature.selection_state[111] = {
        "created_at": now - 800,
        "cart": {}
    }
    
    # Создаем свежую сессию выбора
    feature.selection_state[222] = {
        "created_at": now - 50,
        "cart": {}
    }
    
    feature._cleanup_stale()
    
    assert 999 not in feature.gift_offers
    assert 888 in feature.gift_offers
    assert 111 not in feature.selection_state
    assert 222 in feature.selection_state

# --- Тест 3: Команда /giftstats ---

def test_giftstats_command():
    setup_test_data(giver_id=111, recipient_id=222)
    feature = build_gift_feature()
    
    # Mock update & message
    reply_mock = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=111),
        message=SimpleNamespace(reply_html=reply_mock)
    )
    
    # Запускаем команду giftstats
    asyncio.run(feature.giftstats_command(update, None))
    
    # Проверяем, что reply_html был вызван и вывел статистику
    reply_mock.assert_awaited_once()
    args, kwargs = reply_mock.call_args
    message_text = args[0]
    assert "Отправлено всего" in message_text
    assert "Получено всего" in message_text
    assert "Статус:" in message_text

# --- Тест 4: Проверка лимитов дарения и ограничений ---

def test_gift_limits_and_restrictions():
    setup_test_data(giver_id=111, recipient_id=222)
    feature = build_gift_feature()
    
    # Блокируем получателя в БД
    dbs = db.SessionLocal()
    dbs.add(GiftRestriction(user_id=222, reason="Нарушение правил", blocked_until=int(time.time()) + 1000))
    dbs.commit()
    dbs.close()
    
    # Мокаем сообщение от гивера
    reply_mock = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=111),
        effective_chat=SimpleNamespace(id=777),
        message=SimpleNamespace(
            chat=SimpleNamespace(type="group"),
            reply_to_message=SimpleNamespace(
                from_user=SimpleNamespace(id=222, is_bot=False, username="recip_user", first_name="Recip", last_name=None)
            )
        )
    )
    
    # Запускаем /gift
    asyncio.run(feature.gift_command(update, MagicMock()))
    
    # Проверяем, что сработала блокировка получателя (abort с автоудалением)
    assert len(feature.selection_state) == 0

# --- Тест 5: Полноценный цикл: Отправка предложения, Принятие, Транзакция инвентаря ---

def test_gift_offer_and_acceptance():
    setup_test_data(giver_id=111, recipient_id=222)
    feature = build_gift_feature()
    
    giver_id = 111
    recipient_id = 222
    
    # Создаем сессию выбора у дарителя
    feature.selection_state[giver_id] = {
        "created_at": int(time.time()),
        "group_id": -999,
        "recipient_id": recipient_id,
        "recipient_username": "recip_user",
        "recipient_display": "@recip_user",
        "inventory_items": db.get_player_inventory_with_details(giver_id),
        "max_gifts": 10,
        "cart": {10: 2}, # Кладем 2 штуки Cola Energy
        "gifts_sent_today": 0,
        "search_query": None,
        "awaiting_search": False,
        "search_message_id": None,
        "gift_snapshot": feature._build_gift_flow_snapshot(giver_id, recipient_id),
    }
    
    # Моки Telegram бота
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()
    
    query_mock = AsyncMock()
    query_mock.from_user = SimpleNamespace(id=giver_id, username="giver_user", first_name="Giver", last_name=None)
    query_mock.message = SimpleNamespace(message_id=555)
    query_mock.edit_message_text = AsyncMock()
    
    update = SimpleNamespace(callback_query=query_mock)
    context = SimpleNamespace(bot=bot_mock, job_queue=MagicMock())
    
    # 1. Отправляем корзину (создаем предложение)
    asyncio.run(feature._send_bundle_offer(update, context))
    
    # Проверяем, что создано предложение в памяти
    assert len(feature.gift_offers) == 1
    gift_id = list(feature.gift_offers.keys())[0]
    offer = feature.gift_offers[gift_id]
    assert offer["total_quantity"] == 2
    assert offer["items"][0]["drink_name"] == "Cola Energy"
    
    # Проверяем, что в группу ушло сообщение с кнопками дарения
    bot_mock.send_message.assert_called_once()
    
    # 2. Имитируем принятие подарка получателем
    query_recip_mock = AsyncMock()
    query_recip_mock.from_user = SimpleNamespace(id=recipient_id, username="recip_user", first_name="Recip", last_name=None)
    query_recip_mock.message = SimpleNamespace(message_id=666)
    query_recip_mock.answer = AsyncMock()
    query_recip_mock.edit_message_text = AsyncMock()
    
    update_recip = SimpleNamespace(callback_query=query_recip_mock)
    
    # Принимаем подарок
    asyncio.run(feature.handle_gift_response(update_recip, context, gift_id, accepted=True))
    
    # Проверяем, что предложение удалено из активных после принятия
    assert len(feature.gift_offers) == 0
    
    # Проверяем состояние БД после атомарной транзакции переноса!
    dbs = db.SessionLocal()
    
    # У дарителя осталось 3 колы (было 5)
    giver_item = dbs.query(InventoryItem).filter(InventoryItem.player_id == giver_id, InventoryItem.drink_id == 1).first()
    assert giver_item.quantity == 3
    
    # У получателя появилось 2 колы (было 0)
    recip_item = dbs.query(InventoryItem).filter(InventoryItem.player_id == recipient_id, InventoryItem.drink_id == 1).first()
    assert recip_item is not None
    assert recip_item.quantity == 2
    
    # Проверим лог действий (ActionLog)
    action = dbs.query(ActionLog).filter(ActionLog.user_id == giver_id, ActionLog.action_type == "gift_accepted").first()
    assert action is not None
    assert action.amount == 2
    
    # Проверим историю подарков (GiftHistory)
    history = dbs.query(GiftHistory).filter(GiftHistory.giver_id == giver_id, GiftHistory.recipient_id == recipient_id).first()
    assert history is not None
    assert history.drink_id == 1
    assert history.status == "accepted"
    
    dbs.close()

# --- Тест 6: Срабатывание Автоблокировки (Autoblock) ---

def test_gift_autoblock_trigger():
    setup_test_data(giver_id=111, recipient_id=222)
    feature = build_gift_feature()
    
    giver_id = 111
    recipient_id = 222
    
    # В истории уже лежат 2 подарка получателю 222 от дарителя 111 (более 100 секунд назад, чтобы обойти cooldown)
    dbs = db.SessionLocal()
    past_time = int(time.time()) - 100
    dbs.add(GiftHistory(giver_id=giver_id, recipient_id=recipient_id, drink_id=1, rarity="Basic", status="accepted", created_at=past_time))
    dbs.add(GiftHistory(giver_id=giver_id, recipient_id=recipient_id, drink_id=1, rarity="Basic", status="accepted", created_at=past_time))
    dbs.commit()
    dbs.close()
    
    # Создаем предложение на ещё 2 подарка (серия превысит лимит в 3 подарка)
    feature.selection_state[giver_id] = {
        "created_at": int(time.time()),
        "group_id": -999,
        "recipient_id": recipient_id,
        "recipient_username": "recip_user",
        "recipient_display": "@recip_user",
        "inventory_items": db.get_player_inventory_with_details(giver_id),
        "max_gifts": 10,
        "cart": {10: 2},
        "gifts_sent_today": 2,
        "search_query": None,
        "awaiting_search": False,
        "search_message_id": None,
        "gift_snapshot": feature._build_gift_flow_snapshot(giver_id, recipient_id),
    }
    
    # Имитируем отправку предложения
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()
    query_mock = AsyncMock()
    query_mock.from_user = SimpleNamespace(id=giver_id, username="giver_user", first_name="Giver", last_name=None)
    query_mock.message = SimpleNamespace(message_id=555)
    query_mock.edit_message_text = AsyncMock()
    query_mock.answer = AsyncMock()
    update = SimpleNamespace(callback_query=query_mock)
    context = SimpleNamespace(bot=bot_mock, job_queue=MagicMock())
    
    asyncio.run(feature._send_bundle_offer(update, context))
    
    # Так как серия превысила лимит, предложение подарка не должно быть создано
    assert len(feature.gift_offers) == 0
    
    # Проверяем, что наложены автоблокировки в БД
    dbs = db.SessionLocal()
    giver_restriction = dbs.query(GiftRestriction).filter(GiftRestriction.user_id == giver_id).first()
    recipient_restriction = dbs.query(GiftRestriction).filter(GiftRestriction.user_id == recipient_id).first()
    
    assert giver_restriction is not None
    assert "Подозрительная активность" in giver_restriction.reason
    assert recipient_restriction is not None
    assert "Подозрительная активность" in recipient_restriction.reason
    
    # Проверяем, что инвентарь остался прежним
    giver_item = dbs.query(InventoryItem).filter(InventoryItem.player_id == giver_id, InventoryItem.drink_id == 1).first()
    assert giver_item.quantity == 5
    
    dbs.close()

# --- Тест 7: Отклонение подарка (Rejection) ---

def test_gift_rejection():
    setup_test_data(giver_id=111, recipient_id=222)
    feature = build_gift_feature()
    
    giver_id = 111
    recipient_id = 222
    
    # Создаем предложение
    gift_id = 9999
    feature.gift_offers[gift_id] = {
        "created_at": int(time.time()),
        "giver_id": giver_id,
        "giver_name": "giver_user",
        "recipient_id": recipient_id,
        "recipient_username": "recip_user",
        "recipient_display": "@recip_user",
        "group_id": -999,
        "items": [{"item_id": 10, "drink_id": 1, "drink_name": "Cola Energy", "rarity": "Basic", "quantity": 1}],
        "total_quantity": 1,
    }
    
    # Имитируем отклонение
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()
    query_recip_mock = AsyncMock()
    query_recip_mock.from_user = SimpleNamespace(id=recipient_id, username="recip_user", first_name="Recip", last_name=None)
    query_recip_mock.message = SimpleNamespace(message_id=666)
    query_recip_mock.answer = AsyncMock()
    query_recip_mock.edit_message_text = AsyncMock()
    update_recip = SimpleNamespace(callback_query=query_recip_mock)
    context = SimpleNamespace(bot=bot_mock, job_queue=MagicMock())
    
    asyncio.run(feature.handle_gift_response(update_recip, context, gift_id, accepted=False))
    
    # Проверяем, что предложение удалено
    assert gift_id not in feature.gift_offers
    
    # Проверяем, что в БД записался отклонённый лог
    dbs = db.SessionLocal()
    history = dbs.query(GiftHistory).filter(GiftHistory.giver_id == giver_id, GiftHistory.status == "declined").first()
    assert history is not None
    assert history.drink_id == 1
    dbs.close()
