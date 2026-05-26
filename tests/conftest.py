# file: conftest.py
"""
Глобальная конфигурация pytest для проекта RELOAD.
Перехватывает SQLAlchemy SessionLocal и перенаправляет все запросы в единую
изолированную in-memory базу данных SQLite для всего тестового запуска.
"""

import os
import sys
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Добавляем корень проекта в пути поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.database as db

# Создаем единый Engine для in-memory SQLite с StaticPool
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Создаем единый sessionmaker
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def global_setup_db():
    """Настраивает глобальную тестовую базу данных в начале запуска тестов."""
    # Создаем все таблицы
    db.Base.metadata.create_all(bind=test_engine)
    
    # Подменяем SessionLocal и engine в core.database
    db.SessionLocal = TestSessionLocal
    db.engine = test_engine
    
    # Также перехватываем во всех уже импортированных или импортируемых модулях
    for module_name, module in list(sys.modules.items()):
        if "modules" in module_name or "reload_bot" in module_name:
            if hasattr(module, "SessionLocal"):
                setattr(module, "SessionLocal", TestSessionLocal)
                
    yield test_engine
    
    # Дропаем таблицы в конце сессии
    db.Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(autouse=True)
def clean_database_tables():
    """Очищает все таблицы перед каждым тестом для достижения полной изоляции."""
    connection = test_engine.connect()
    transaction = connection.begin()
    
    # Отключаем внешние ключи на время очистки
    connection.execute(text("PRAGMA foreign_keys = OFF;"))
    
    # Очищаем каждую таблицу
    for table in reversed(db.Base.metadata.sorted_tables):
        connection.execute(table.delete())
        
    connection.execute(text("PRAGMA foreign_keys = ON;"))
    transaction.commit()
    connection.close()
