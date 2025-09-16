# file: migrate_data.py

import json
import os
import re
import database as db

ENERGY_DRINKS_FILE = 'energy_drinks.json'
PLAYER_DATA_FILE = 'player_data.json'

def run_migration():
    print("Начинаем миграцию данных из JSON в базу данных SQLite...")
    
    # 1. Создаем таблицы в БД
    db.create_db_and_tables()
    
    session = db.SessionLocal()
    
    # 2. Миграция энергетиков
    print(f"\n--- Миграция из {ENERGY_DRINKS_FILE} ---")
    if not os.path.exists(ENERGY_DRINKS_FILE):
        print(f"Файл {ENERGY_DRINKS_FILE} не найден. Пропускаем.")
        return

    with open(ENERGY_DRINKS_FILE, 'r', encoding='utf-8') as f:
        energy_drinks_data = json.load(f)
    
    drink_name_to_id = {}
    for drink_data in energy_drinks_data:
        # Проверяем, нет ли уже такого напитка
        existing = session.query(db.EnergyDrink).filter_by(name=drink_data['name']).first()
        if not existing:
            new_drink = db.EnergyDrink(
                name=drink_data['name'],
                description=drink_data['description'],
                image_path=os.path.basename(drink_data.get('image_path', '')),
                is_special=drink_data.get('is_special', False)
            )
            session.add(new_drink)
            print(f"Добавлен энергетик: {new_drink.name}")
    
    session.commit()
    
    # Сохраняем ID всех напитков для удобства
    all_drinks = session.query(db.EnergyDrink).all()
    for drink in all_drinks:
        drink_name_to_id[drink.name] = drink.id
        
    print("Миграция энергетиков завершена.")

    # 3. Миграция данных игроков
    print(f"\n--- Миграция из {PLAYER_DATA_FILE} ---")
    if not os.path.exists(PLAYER_DATA_FILE):
        print(f"Файл {PLAYER_DATA_FILE} не найден. Пропускаем.")
        session.close()
        return

    with open(PLAYER_DATA_FILE, 'r', encoding='utf-8') as f:
        players_data = json.load(f)
        
    for user_id, data in players_data.items():
        if not user_id.isdigit():
            print(f"Пропущен неверный ID: {user_id}")
            continue

        # Проверяем, нет ли уже такого игрока
        existing_player = session.query(db.Player).filter_by(user_id=int(user_id)).first()
        if not existing_player:
            new_player = db.Player(
                user_id=int(user_id),
                username=data.get('username', 'Unknown'),
                coins=data.get('coins', 0),
                last_search=data.get('last_search', 0)
            )
            session.add(new_player)
            print(f"Добавлен игрок: {new_player.username} ({new_player.user_id})")
            
            # Миграция инвентаря игрока
            inventory = data.get('energy_drinks', {})
            for item_key, quantity in inventory.items():
                # Парсим ключ "Название (Редкость)"
                match = re.match(r'^(.*?)\s*\((.*?)\)$', item_key)
                if match:
                    name, rarity = match.groups()
                    name = name.strip()
                    rarity = rarity.strip()
                    
                    drink_id = drink_name_to_id.get(name)
                    if drink_id:
                        inv_item = db.InventoryItem(
                            player_id=new_player.user_id,
                            drink_id=drink_id,
                            rarity=rarity,
                            quantity=quantity
                        )
                        session.add(inv_item)
                        print(f"  - Добавлен предмет в инвентарь: {name} ({rarity}) x{quantity}")
                    else:
                        print(f"  - [ОШИБКА] Энергетик '{name}' не найден в справочнике.")
                else:
                    print(f"  - [ОШИБКА] Не удалось распознать ключ инвентаря: '{item_key}'")

    session.commit()
    print("Миграция данных игроков завершена.")
    
    session.close()
    print("\n✅ Миграция успешно завершена!")

if __name__ == '__main__':
    run_migration()