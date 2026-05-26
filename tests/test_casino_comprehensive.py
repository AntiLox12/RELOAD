# file: test_casino_comprehensive.py
"""
Всесторонние тесты для модуля Казино (casino_logic.py, casino_gameplay.py).
Используют in-memory базу данных SQLite для изоляции.
"""

import os
import sys
import time
import pytest
from unittest.mock import MagicMock

# Добавляем корень проекта в пути поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.database as db
from core.database import Player
import modules.casino.casino_logic as logic
import modules.casino.casino_gameplay as gameplay
from core.constants import CASINO_GAMES, CASINO_ACHIEVEMENTS

def create_test_player(user_id=777, username="gambler", coins=10000):
    """Вспомогательная функция для создания тестового игрока."""
    dbs = db.SessionLocal()
    player = Player(
        user_id=user_id,
        username=username,
        display_name="Заядлый Игрок",
        coins=coins,
        casino_wins=0,
        casino_losses=0,
        casino_achievements=""
    )
    dbs.add(player)
    dbs.commit()
    dbs.close()
    return user_id

# ==========================================
# 1. ТЕСТЫ ДЛЯ КАЗИНО LOGIC (ВЕРОЯТНОСТЬ И УТИЛИТЫ)
# ==========================================

def test_casino_probability_adjustments():
    """Тестирование корректности модификации вероятностей удачи."""
    # Базовые случаи
    assert logic.casino_adjusted_prob(0.5, 1.0) == 0.5
    assert logic.casino_adjusted_prob(0.5, 2.0) == 0.95  # Зажато в max 0.95
    assert logic.casino_adjusted_prob(0.5, 0.1) == 0.05
    
    # Граничные значения вероятности
    assert logic.casino_adjusted_prob(-0.1, 1.0) == 0.0
    assert logic.casino_adjusted_prob(1.5, 1.0) == 0.95 # Ограничение до 0.95
    
    # Граничные значения удачи
    assert logic.casino_adjusted_prob(0.2, 10.0) == 0.95 # Удача зажимается в [0.1, 5.0], 0.2 * 5.0 = 1.0 -> max 0.95
    assert abs(logic.casino_adjusted_prob(0.2, -1.0) - 0.02) < 1e-6 # Минимальный множитель удачи 0.1, 0.2 * 0.1 = 0.02

def test_casino_extra_win_chance():
    """Тестирование шанса на дополнительную победу."""
    # Базовая вероятность 0.1, удача 2.0 -> Скорректированная 0.2. Дополнительный шанс = 0.2 - 0.1 = 0.1
    assert abs(logic.casino_extra_win_chance(0.1, 2.0) - 0.1) < 1e-6
    
    # Без удачи (1.0) -> дополнительный шанс 0.0
    assert logic.casino_extra_win_chance(0.3, 1.0) == 0.0
    
    # При плохой удаче (0.5) -> скорректированная меньше базовой -> дополнительный шанс зажат до 0.0
    assert logic.casino_extra_win_chance(0.3, 0.5) == 0.0

def test_casino_game_type_from_info():
    """Тест определения типа игры по словарю конфигурации."""
    games_config = {
        "flip": {"id": 1, "multiplier": 2.0},
        "dice_game": {"id": 2, "multiplier": 6.0}
    }
    
    assert logic.casino_game_type_from_info(games_config["flip"], games_config) == "flip"
    assert logic.casino_game_type_from_info(games_config["dice_game"], games_config) == "dice_game"
    
    # Неизвестная игра
    unknown_config = {"id": 999}
    assert logic.casino_game_type_from_info(unknown_config, games_config) == "coin_flip"

def test_parse_casino_game_choice():
    """Тестирование парсинга команд выбора игр."""
    games_config = {
        "coin_flip": {},
        "roulette_color": {},
        "dice": {}
    }
    
    # Точное совпадение
    assert logic.parse_casino_game_choice("coin_flip", games_config) == ("coin_flip", None)
    
    # С аргументом выбора (через подчёркивание)
    assert logic.parse_casino_game_choice("roulette_color_red", games_config) == ("roulette_color", "red")
    assert logic.parse_casino_game_choice("dice_5", games_config) == ("dice", "5")
    
    # Неверные форматы
    assert logic.parse_casino_game_choice("unknown_game", games_config) == (None, None)

def test_build_casino_repeat_callback():
    """Тест создания Callback строки для повтора ставки."""
    assert logic.build_casino_repeat_callback("coin_flip", "heads", 500) == "casino_repeat|coin_flip|heads|500"
    assert logic.build_casino_repeat_callback("slots", None, 1000) == "casino_repeat|slots|-|1000"

# ==========================================
# 2. ТЕСТЫ ЭМУЛЯЦИИ ИГРОВЫХ МОДУЛЕЙ
# ==========================================

def test_play_coin_flip():
    """Тест игры Орёл/Решка."""
    # Запустим несколько раз, чтобы поймать результаты
    wins = 0
    losses = 0
    for _ in range(50):
        win, text = logic.play_coin_flip("heads", 5.0)
        assert "Орёл" in text or "Решка" in text
        assert "Орёл" in text # Ваш выбор: Орёл всегда отображается при heads
        if win:
            wins += 1
            assert "Совпадение" in text
        else:
            losses += 1
            assert "Не угадали" in text
            
    assert wins > 0

def test_play_dice():
    """Тест игры в кости (выбор числа)."""
    game_info = {"multiplier": 6.0}
    win, text, mult = logic.play_dice(game_info, "4", 5.0)
    assert mult == 6.0
    assert "Ваше число" in text
    assert "4" in text
    if win:
        assert "Угадали" in text
    else:
        assert "Не угадали" in text

def test_play_high_low():
    """Тест игры Больше/Меньше 50."""
    # Выбор high (больше 50)
    win, text = logic.play_high_low("high", 1.0)
    assert "Ваш выбор" in text
    assert "Больше 50" in text
    if win:
        assert "Угадали" in text
    else:
        assert "Не угадали" in text

    # Выбор low (меньше 50)
    win, text = logic.play_high_low("low", 1.0)
    assert "Ваш выбор" in text
    assert "Меньше 50" in text

def test_play_roulette_color():
    """Тест игры Рулетка (Цвет)."""
    win, text = logic.play_roulette_color("red", 1.0)
    assert "Ваш выбор" in text
    assert "Красное" in text
    if win:
        assert "Угадали" in text
    else:
        assert "Чёрное" in text or "Зелёное" in text

def test_play_roulette_number():
    """Тест игры Рулетка (Число)."""
    game_info = {"multiplier": 35.0}
    win, text, mult = logic.play_roulette_number(game_info, "17", 1.0)
    assert mult == 35.0
    assert "Ваше число" in text
    assert "17" in text
    if win:
        assert "Точное попадание" in text
    else:
        assert "Не угадали" in text

def test_play_slots():
    """Тест игры в Слоты."""
    symbols = ["🍒", "🍋", "🍇", "💎"]
    payouts = {
        ("🍒", "🍒", "🍒"): 3.0,
        ("🍋", "🍋", "🍋"): 5.0,
        ("🍇", "🍇", "🍇"): 8.0,
        ("💎", "💎", "💎"): 25.0
    }
    
    win_slots = 0
    lose_slots = 0
    for _ in range(100):
        win, text, mult = logic.play_slots(symbols, payouts, 0.3, 1.0)
        if win:
            win_slots += 1
            assert mult > 0
            assert "Множитель" in text
        else:
            lose_slots += 1
            assert mult == 0
            assert "Множитель" not in text
            
    assert win_slots > 0 or lose_slots > 0

# ==========================================
# 3. ТЕСТЫ ИНТЕГРАЦИИ С БАЗОЙ ДАННЫХ
# ==========================================

def test_casino_take_bet():
    """Тестирование списания монет для ставки."""
    user_id = create_test_player(user_id=888, coins=5000)
    
    # Успешная ставка
    new_bal = gameplay.casino_take_bet(user_id, 1000)
    assert new_bal == 4000
    
    # Проверяем в БД
    dbs = db.SessionLocal()
    player = dbs.query(Player).filter(Player.user_id == user_id).first()
    assert player.coins == 4000
    dbs.close()
    
    # Ставка больше баланса -> None (недостаточно средств)
    fail_bet = gameplay.casino_take_bet(user_id, 10000)
    assert fail_bet is None

def test_casino_record_result():
    """Тестирование накопления статистики побед и поражений."""
    user_id = create_test_player(user_id=889)
    
    # Записываем победу
    gameplay.casino_record_result(user_id, win=True)
    # Записываем ещё победу
    gameplay.casino_record_result(user_id, win=True)
    # Записываем поражение
    gameplay.casino_record_result(user_id, win=False)
    
    # Проверяем в БД
    dbs = db.SessionLocal()
    player = dbs.query(Player).filter(Player.user_id == user_id).first()
    assert player.casino_wins == 2
    assert player.casino_losses == 1
    dbs.close()

def test_check_casino_achievements():
    """Тестирование разблокировки ачивок казино."""
    user_id = create_test_player(user_id=890, coins=100)
    
    # Имитируем игрока в БД
    dbs = db.SessionLocal()
    player = dbs.query(Player).filter(Player.user_id == user_id).first()
    
    # Проверяем на 0 побед -> ачивок нет
    res = gameplay.check_casino_achievements(user_id, player)
    assert res is None
    
    # Имитируем 100 побед (чтобы гарантированно покрыть любые достижения из CASINO_ACHIEVEMENTS)
    player.casino_wins = 100
    dbs.commit()
    
    # Запускаем проверку ачивок
    res2 = gameplay.check_casino_achievements(user_id, player)
    
    # Должна разблокироваться как минимум первая ачивка
    assert res2 is not None
    assert res2["bonus"] > 0
    assert "achievement" in res2
    
    # Синхронизируем сессию с реальным состоянием БД перед проверкой баланса
    dbs.expire_all()
    
    # Проверяем, что монеты зачислились на баланс в БД
    player_updated = dbs.query(Player).filter(Player.user_id == user_id).first()
    assert player_updated.coins == 100 + res2["bonus"]
    assert len(player_updated.casino_achievements) > 0
    
    dbs.close()
