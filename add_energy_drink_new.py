# file: add_energy_drink_new.py

import os
import shutil
from tkinter import Tk, filedialog
import database as db

ENERGY_IMAGES_DIR = 'energy_images'

if not os.path.exists(ENERGY_IMAGES_DIR):
    os.makedirs(ENERGY_IMAGES_DIR)

def prompt_yes_no(prompt):
    while True:
        choice = input(prompt + " (Да/Нет): ").strip().lower()
        if choice in ['да', 'д', 'yes', 'y']:
            return True
        elif choice in ['нет', 'н', 'no', 'n']:
            return False
        else:
            print("Пожалуйста, введите 'Да' или 'Нет'.")

def select_image_file():
    Tk().withdraw()
    file_path = filedialog.askopenfilename(
        title="Выберите изображение",
        filetypes=[("Изображения", "*.png;*.jpg;*.jpeg")]
    )
    return file_path

def main():
    print("=== Скрипт для добавления энергетиков в базу данных ===")
    
    session = db.SessionLocal()
    
    while True:
        name = input("\nВведите название энергетика (или 'выход' для завершения): ").strip()
        if name.lower() in ['выход', 'exit', 'quit']:
            break
        if not name:
            print("Название не может быть пустым.")
            continue
            
        existing_drink = session.query(db.EnergyDrink).filter_by(name=name).first()
        if existing_drink:
            print(f"Энергетик '{name}' уже существует. Обновляем информацию.")
            drink_to_update = existing_drink
        else:
            print(f"Добавляем новый энергетик '{name}'.")
            drink_to_update = db.EnergyDrink(name=name)

        drink_to_update.description = input("Введите описание: ").strip()
        drink_to_update.is_special = prompt_yes_no("Это 'Особенный' энергетик?")
        
        if prompt_yes_no("Хотите добавить/изменить изображение?"):
            image_path = select_image_file()
            if image_path:
                filename = os.path.basename(image_path)
                new_path = os.path.join(ENERGY_IMAGES_DIR, filename)
                shutil.copy(image_path, new_path)
                drink_to_update.image_path = filename
                print(f"Изображение сохранено как {filename}")
        
        if not existing_drink:
            session.add(drink_to_update)
            
        session.commit()
        print(f"✅ Данные для '{name}' успешно сохранены в базе.")
        
    session.close()
    print("\nСкрипт завершён.")


if __name__ == '__main__':
    db.create_db_and_tables() # На всякий случай
    main()