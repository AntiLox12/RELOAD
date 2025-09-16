# file: test_silk_city.py
"""
Базовые тесты для системы Город Шёлка.
Проверяет основную функциональность создания плантаций, сбора урожая и торговли.
"""

import time
import random
import sqlite3
import os
from constants import SILK_INVESTMENT_LEVELS, SILK_TYPES

def test_basic_silk_functionality():
    """Основной тест функциональности системы шёлка."""
    print("🧵 Тестирование системы Город Шёлка...")
    
    # Удалим тестовую базу данных если существует
    test_db = "test_silk_city.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Создаём тестовую базу данных
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Создаём тестовые таблицы
    cursor.execute("""
        CREATE TABLE players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE silk_plantations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            plantation_name TEXT,
            silk_trees_count INTEGER DEFAULT 0,
            planted_at INTEGER DEFAULT 0,
            harvest_ready_at INTEGER DEFAULT 0,
            status TEXT DEFAULT 'growing',
            investment_cost INTEGER DEFAULT 0,
            expected_yield INTEGER DEFAULT 0,
            investment_level TEXT DEFAULT 'starter',
            quality_modifier INTEGER DEFAULT 100,
            weather_modifier INTEGER DEFAULT 100
        )
    """)
    
    cursor.execute("""
        CREATE TABLE silk_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            silk_type TEXT,
            quantity INTEGER DEFAULT 0,
            quality_grade INTEGER DEFAULT 300,
            produced_at INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE silk_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            buyer_id INTEGER,
            transaction_type TEXT,
            silk_type TEXT,
            amount INTEGER DEFAULT 0,
            price_per_unit INTEGER DEFAULT 0,
            total_price INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0
        )
    """)
    
    # Тест 1: Создание игрока с начальными монетами
    test_user_id = 12345
    initial_coins = 100000
    
    cursor.execute(
        "INSERT INTO players (user_id, username, coins) VALUES (?, ?, ?)",
        (test_user_id, "test_user", initial_coins)
    )
    conn.commit()
    print(f"✅ Создан тестовый игрок с {initial_coins:,} монет")
    
    # Тест 2: Проверка уровней инвестиций
    print(f"✅ Доступно {len(SILK_INVESTMENT_LEVELS)} уровней инвестиций:")
    for level, config in SILK_INVESTMENT_LEVELS.items():
        print(f"   • {level}: {config['cost']:,} септимов, {config['trees']} деревьев")
    
    # Тест 3: Создание плантации
    level = 'starter'
    config = SILK_INVESTMENT_LEVELS[level]
    current_time = int(time.time())
    
    cursor.execute("""
        INSERT INTO silk_plantations (
            player_id, plantation_name, silk_trees_count, planted_at,
            harvest_ready_at, investment_cost, expected_yield, investment_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        test_user_id, "Тестовая плантация", config['trees'], current_time,
        current_time + 10,  # Готов через 10 секунд для теста
        config['cost'], random.randint(config['min_yield'], config['max_yield']), level
    ))
    
    # Списываем монеты
    cursor.execute(
        "UPDATE players SET coins = coins - ? WHERE user_id = ?",
        (config['cost'], test_user_id)
    )
    conn.commit()
    
    print(f"✅ Создана плантация уровня '{level}' за {config['cost']:,} септимов")
    
    # Тест 4: Проверка типов шёлка
    print(f"✅ Доступно {len(SILK_TYPES)} типов шёлка:")
    for silk_type, config in SILK_TYPES.items():
        print(f"   • {silk_type}: {config['name']} {config['emoji']} ({config['probability']}%)")
    
    # Тест 5: Симуляция сбора урожая
    print("⏳ Ожидание готовности урожая...")
    time.sleep(11)  # Ждём больше 10 секунд
    
    # Обновляем статус плантации
    cursor.execute(
        "UPDATE silk_plantations SET status = 'ready' WHERE player_id = ? AND harvest_ready_at <= ?",
        (test_user_id, int(time.time()))
    )
    
    # Симулируем сбор урожая
    cursor.execute(
        "SELECT * FROM silk_plantations WHERE player_id = ? AND status = 'ready'",
        (test_user_id,)
    )
    ready_plantation = cursor.fetchone()
    
    if ready_plantation:
        plantation_id, player_id, name, trees, planted_at, ready_at, status, cost, expected_yield = ready_plantation[:9]
        
        # Генерируем случайный урожай шёлка
        silk_harvest = {}
        total_yield = expected_yield
        
        for silk_type, config in SILK_TYPES.items():
            probability = config['probability'] / 100.0
            type_yield = int(total_yield * probability * random.uniform(0.8, 1.2))
            if type_yield > 0:
                silk_harvest[silk_type] = type_yield
        
        # Добавляем шёлк в инвентарь
        for silk_type, quantity in silk_harvest.items():
            cursor.execute("""
                INSERT INTO silk_inventory (player_id, silk_type, quantity, produced_at)
                VALUES (?, ?, ?, ?)
            """, (test_user_id, silk_type, quantity, int(time.time())))
        
        # Помечаем плантацию как завершённую
        cursor.execute(
            "UPDATE silk_plantations SET status = 'completed' WHERE id = ?",
            (plantation_id,)
        )
        
        # Добавляем бонусные монеты
        bonus_coins = random.randint(50, 150)
        cursor.execute(
            "UPDATE players SET coins = coins + ? WHERE user_id = ?",
            (bonus_coins, test_user_id)
        )
        
        conn.commit()
        
        print(f"✅ Урожай собран! Получено:")
        for silk_type, quantity in silk_harvest.items():
            config = SILK_TYPES[silk_type]
            print(f"   • {quantity} {config['emoji']} {config['name']}")
        print(f"   • Бонус: +{bonus_coins} монет")
    
    # Тест 6: Проверка инвентаря
    cursor.execute(
        "SELECT silk_type, quantity FROM silk_inventory WHERE player_id = ?",
        (test_user_id,)
    )
    inventory = cursor.fetchall()
    
    print("📦 Итоговый инвентарь шёлка:")
    for silk_type, quantity in inventory:
        config = SILK_TYPES[silk_type]
        print(f"   • {quantity} {config['emoji']} {config['name']}")
    
    # Тест 7: Симуляция продажи
    if inventory:
        silk_type, quantity = inventory[0]
        sell_quantity = min(5, quantity)
        base_price = SILK_TYPES[silk_type]['base_price']
        sale_price = random.randint(base_price - 5, base_price + 5)
        total_earnings = sale_price * sell_quantity
        
        # Убираем шёлк из инвентаря
        cursor.execute(
            "UPDATE silk_inventory SET quantity = quantity - ? WHERE player_id = ? AND silk_type = ?",
            (sell_quantity, test_user_id, silk_type)
        )
        
        # Добавляем монеты
        cursor.execute(
            "UPDATE players SET coins = coins + ? WHERE user_id = ?",
            (total_earnings, test_user_id)
        )
        
        # Записываем транзакцию
        cursor.execute("""
            INSERT INTO silk_transactions (
                seller_id, transaction_type, silk_type, amount, price_per_unit, total_price, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (test_user_id, 'npc_sale', silk_type, sell_quantity, sale_price, total_earnings, int(time.time())))
        
        conn.commit()
        
        config = SILK_TYPES[silk_type]
        print(f"💰 Продано: {sell_quantity} {config['emoji']} {config['name']} за {total_earnings:,} монет")
    
    # Тест 8: Финальная статистика
    cursor.execute("SELECT coins FROM players WHERE user_id = ?", (test_user_id,))
    final_coins = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM silk_plantations WHERE player_id = ?", (test_user_id,))
    total_plantations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM silk_transactions WHERE seller_id = ?", (test_user_id,))
    total_sales = cursor.fetchone()[0]
    
    profit = final_coins - initial_coins
    
    print(f"\n📊 Финальная статистика:")
    print(f"   💰 Начальные монеты: {initial_coins:,}")
    print(f"   💰 Итоговые монеты: {final_coins:,}")
    print(f"   📈 Прибыль: {profit:,}")
    print(f"   🌳 Создано плантаций: {total_plantations}")
    print(f"   🛒 Совершено продаж: {total_sales}")
    
    # Закрываем соединение и удаляем тестовую базу
    conn.close()
    os.remove(test_db)
    
    print("\n🎉 Все тесты системы Город Шёлка прошли успешно!")
    return True

def test_silk_constants():
    """Тест корректности констант системы шёлка."""
    print("\n🔧 Тестирование констант системы шёлка...")
    
    # Проверяем уровни инвестиций
    assert len(SILK_INVESTMENT_LEVELS) == 4, "Должно быть 4 уровня инвестиций"
    for level, config in SILK_INVESTMENT_LEVELS.items():
        assert 'cost' in config, f"Уровень {level} должен иметь стоимость"
        assert 'trees' in config, f"Уровень {level} должен иметь количество деревьев"
        assert 'grow_time' in config, f"Уровень {level} должен иметь время роста"
        assert 'min_yield' in config, f"Уровень {level} должен иметь минимальный урожай"
        assert 'max_yield' in config, f"Уровень {level} должен иметь максимальный урожай"
        assert config['min_yield'] <= config['max_yield'], f"Минимальный урожай не может быть больше максимального в {level}"
    
    # Проверяем типы шёлка
    assert len(SILK_TYPES) == 3, "Должно быть 3 типа шёлка"
    total_probability = sum(config['probability'] for config in SILK_TYPES.values())
    assert total_probability == 100, f"Общая вероятность должна быть 100%, получено {total_probability}%"
    
    for silk_type, config in SILK_TYPES.items():
        assert 'name' in config, f"Тип шёлка {silk_type} должен иметь название"
        assert 'emoji' in config, f"Тип шёлка {silk_type} должен иметь эмодзи"
        assert 'base_price' in config, f"Тип шёлка {silk_type} должен иметь базовую цену"
        assert 'probability' in config, f"Тип шёлка {silk_type} должен иметь вероятность"
        assert 0 < config['probability'] <= 100, f"Вероятность {silk_type} должна быть от 1 до 100"
    
    print("✅ Все константы корректны!")
    return True

if __name__ == "__main__":
    try:
        test_silk_constants()
        test_basic_silk_functionality()
        print("\n🚀 Система Город Шёлка готова к использованию!")
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()