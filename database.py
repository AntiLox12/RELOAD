# file: database.py

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, BigInteger, Index, and_, or_
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload
import re
from sqlalchemy import text, func
import time
import random
from constants import RARITIES, RECEIVER_PRICES, RECEIVER_COMMISSION, SHOP_PRICES, ADMIN_USERNAMES

# --- Настройка базы данных ---
DATABASE_FILE = "bot_data.db"
engine = create_engine(f"sqlite:///{DATABASE_FILE}", connect_args={"check_same_thread": False})
# Важно: отключаем expire_on_commit, чтобы возвращаемые объекты не теряли значения полей после commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()

# --- Описание таблиц в базе данных ---

class Player(Base):
    __tablename__ = 'players'
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String)
    coins = Column(Integer, default=0)
    last_search = Column(Integer, default=0)
    last_bonus_claim = Column(Integer, default=0)
    last_add = Column(Integer, default=0)
    language = Column(String, default='ru')
    remind = Column(Boolean, default=False)
    remind_plantation = Column(Boolean, default=False)
    vip_until = Column(Integer, default=0)
    vip_plus_until = Column(Integer, default=0)  # VIP+ статус
    tg_premium_until = Column(Integer, default=0)
    # --- VIP автопоиск ---
    auto_search_enabled = Column(Boolean, default=False)
    auto_search_count = Column(Integer, default=0)
    auto_search_reset_ts = Column(Integer, default=0)
    # --- Автопоиск буст ---
    auto_search_boost_count = Column(Integer, default=0)  # дополнительные поиски за день
    auto_search_boost_until = Column(Integer, default=0)  # время истечения буста
    # --- Тихий режим автопоиска ---
    auto_search_silent = Column(Boolean, default=False)
    auto_search_session_stats = Column(String, default='{}')  # JSON со статистикой текущей сессии
    # --- Статистика казино ---
    casino_wins = Column(Integer, default=0)  # количество побед в казино
    casino_losses = Column(Integer, default=0)  # количество поражений в казино
    casino_achievements = Column(String, default='')  # разблокированные достижения (через запятую)
    selyuk_fragments = Column(Integer, default=0)  # Фрагменты Селюка
    inventory = relationship("InventoryItem", back_populates="owner", cascade="all, delete-orphan")


class Selyuk(Base):
    __tablename__ = 'selyuki'
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey('players.user_id'), index=True)
    type = Column(String, index=True)
    level = Column(Integer, default=1)
    balance_septims = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True, index=True)
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()))

    owner = relationship('Player')

    __table_args__ = (
        Index('idx_selyuk_owner_type', 'owner_id', 'type', unique=True),
    )

class EnergyDrink(Base):
    __tablename__ = 'energy_drinks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    image_path = Column(String, nullable=True)
    is_special = Column(Boolean, default=False)
    is_plantation = Column(Boolean, default=False)
    plantation_index = Column(Integer, nullable=True)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey('players.user_id'))
    drink_id = Column(Integer, ForeignKey('energy_drinks.id'))
    rarity = Column(String)
    quantity = Column(Integer, default=1)
    owner = relationship("Player", back_populates="inventory")
    drink = relationship("EnergyDrink")

    __table_args__ = (
        Index('idx_inventory_player', 'player_id'),
        Index('idx_inventory_drink', 'drink_id'),
        Index('idx_inventory_rarity', 'rarity'),
    )


class AutoSellSetting(Base):
    __tablename__ = 'autosell_settings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)
    rarity = Column(String, index=True)
    enabled = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_autosell_user_rarity', 'user_id', 'rarity', unique=True),
    )

# --- Магазинные офферы (персистентны, обновляются раз в 4 часа) ---

class ShopOffer(Base):
    __tablename__ = 'shop_offers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_index = Column(Integer, index=True)  # 1..50
    drink_id = Column(Integer, ForeignKey('energy_drinks.id'), index=True)
    rarity = Column(String, index=True)
    batch_ts = Column(Integer, index=True)  # метка времени генерации пакета офферов

    drink = relationship('EnergyDrink')

# --- Роли админов ---

class AdminUser(Base):
    __tablename__ = 'admin_users'
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String)
    level = Column(Integer, default=1)  # 1=Младший модератор, 2=Старший модератор, 3=Главный админ
    created_at = Column(Integer, default=lambda: int(time.time()))

# --- Заявки на добавление энергетиков ---

class PendingAddition(Base):
    __tablename__ = 'pending_additions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    proposer_id = Column(BigInteger, index=True)
    name = Column(String)
    description = Column(String)
    is_special = Column(Boolean, default=False)
    file_id = Column(String, nullable=True)
    status = Column(String, default='pending', index=True)  # pending/approved/rejected
    created_at = Column(Integer, default=lambda: int(time.time()))
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(Integer, nullable=True)
    review_reason = Column(String, nullable=True)

# --- Заявки на удаление энергетиков ---

class PendingDeletion(Base):
    __tablename__ = 'pending_deletions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    proposer_id = Column(BigInteger, index=True)
    drink_id = Column(Integer, index=True)
    reason = Column(String, nullable=True)
    status = Column(String, default='pending', index=True)  # pending/approved/rejected
    created_at = Column(Integer, default=lambda: int(time.time()))
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(Integer, nullable=True)
    review_reason = Column(String, nullable=True)

# --- Заявки на редактирование энергетиков ---

class PendingEdit(Base):
    __tablename__ = 'pending_edits'
    id = Column(Integer, primary_key=True, autoincrement=True)
    proposer_id = Column(BigInteger, index=True)
    drink_id = Column(Integer, index=True)
    field = Column(String)  # 'name' | 'description'
    new_value = Column(String)
    status = Column(String, default='pending', index=True)  # pending/approved/rejected
    created_at = Column(Integer, default=lambda: int(time.time()))
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(Integer, nullable=True)
    review_reason = Column(String, nullable=True)

# --- Аудит-лог модерации и админ-действий ---

class ModerationLog(Base):
    __tablename__ = 'moderation_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Integer, default=lambda: int(time.time()), index=True)
    actor_id = Column(BigInteger, index=True)
    action = Column(String, index=True)  # e.g., approve_add, reject_add, approve_delete, reject_delete, admin_add, admin_remove, admin_level_change
    request_id = Column(Integer, nullable=True)
    target_id = Column(BigInteger, nullable=True)
    details = Column(String, nullable=True)

# --- Баны и предупреждения ---

class UserBan(Base):
    __tablename__ = 'user_bans'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, index=True)
    reason = Column(String, nullable=True)
    banned_at = Column(Integer, default=lambda: int(time.time()), index=True)
    banned_until = Column(Integer, nullable=True, index=True)
    banned_by = Column(BigInteger, nullable=True)

class UserWarning(Base):
    __tablename__ = 'user_warnings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)
    reason = Column(String, nullable=True)
    issued_at = Column(Integer, default=lambda: int(time.time()), index=True)
    issued_by = Column(BigInteger, nullable=True)

# --- Логи действий пользователей ---

class ActionLog(Base):
    __tablename__ = 'action_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, default=lambda: int(time.time()), index=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String, nullable=True)
    action_type = Column(String, index=True)  # transaction, casino, purchase, search, admin_action, etc.
    action_details = Column(String, nullable=True)  # JSON или текст с деталями
    amount = Column(Integer, nullable=True)  # для транзакций
    success = Column(Boolean, default=True)

# --- Группы для рассылок ---

class GroupChat(Base):
    __tablename__ = 'group_chats'
    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=True)
    is_enabled = Column(Boolean, default=True, index=True)
    last_notified = Column(Integer, default=0)
    # Новые настройки для создателей групп
    notify_disabled = Column(Boolean, default=False, index=True)  # Отключение notify_groups_job
    auto_delete_enabled = Column(Boolean, default=False, index=True)  # Включение автоудаления
    auto_delete_delay_minutes = Column(Integer, default=5)  # Задержка перед удалением в минутах

# --- Запланированные задачи автоудаления ---

class ScheduledAutoDelete(Base):
    __tablename__ = 'scheduled_auto_deletes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, index=True, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    delete_at = Column(Integer, index=True, nullable=False)  # Unix timestamp когда нужно удалить
    created_at = Column(Integer, default=lambda: int(time.time()))

# --- Промокоды ---

class Promo(Base):
    __tablename__ = 'promos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, index=True)
    kind = Column(String, index=True)  # coins | vip | vip_plus | drink | custom
    value = Column(Integer, default=0)  # сумма монет, дни VIP, id напитка и т.п. (для custom — соглашение на уровне приложения)
    rarity = Column(String, nullable=True)
    max_uses = Column(Integer, default=0)  # 0 = без лимита
    per_user_limit = Column(Integer, default=1)  # 0 = без лимита на пользователя
    expires_at = Column(Integer, nullable=True, index=True)  # None = без срока
    active = Column(Boolean, default=True, index=True)
    created_at = Column(Integer, default=lambda: int(time.time()), index=True)

class PromoUsage(Base):
    __tablename__ = 'promo_usages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    promo_id = Column(Integer, ForeignKey('promos.id'), index=True)
    user_id = Column(BigInteger, index=True)
    used_at = Column(Integer, default=lambda: int(time.time()), index=True)

class BotSetting(Base):
    __tablename__ = 'bot_settings'
    key = Column(String, primary_key=True)
    value = Column(String)

# --- Склад для TG Premium ---

class TgPremiumStock(Base):
    __tablename__ = 'tg_premium_stock'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock = Column(Integer, default=0)

# --- Чеки покупок ---

class PurchaseReceipt(Base):
    __tablename__ = 'purchase_receipts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)
    kind = Column(String, index=True)  # e.g., 'tg_premium'
    amount_coins = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    purchased_at = Column(Integer, default=lambda: int(time.time()), index=True)
    valid_until = Column(Integer, default=0)
    status = Column(String, default='completed', index=True)  # completed | verified | canceled
    verified_by = Column(BigInteger, nullable=True)
    verified_at = Column(Integer, nullable=True)
    extra = Column(String, nullable=True)

# --- Универсальный склад бонусов ---

class BonusStock(Base):
    __tablename__ = 'bonus_stock'
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String, unique=True, index=True)  # уникальный вид бонуса, например 'tg_premium'
    stock = Column(Integer, default=0)

# --- История бустов автопоиска ---

class BoostHistory(Base):
    __tablename__ = 'boost_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String, nullable=True)
    action = Column(String, index=True)  # 'granted' | 'removed' | 'expired'
    boost_count = Column(Integer, default=0)  # количество добавленных/убранных поисков
    boost_days = Column(Integer, default=0)  # количество дней (только для granted)
    granted_by = Column(BigInteger, nullable=True)  # ID админа, выдавшего буст
    granted_by_username = Column(String, nullable=True)  # username админа
    timestamp = Column(Integer, default=lambda: int(time.time()), index=True)
    details = Column(String, nullable=True)  # дополнительная информация
    
    __table_args__ = (
        Index('idx_boost_history_user', 'user_id'),
        Index('idx_boost_history_action', 'action'),
        Index('idx_boost_history_timestamp', 'timestamp'),
    )


# --- Модели для Города Шёлка ---

class SilkPlantation(Base):
    __tablename__ = 'silk_plantations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey('players.user_id'), index=True)
    plantation_name = Column(String, nullable=True)  # Название плантации (задается игроком)
    silk_trees_count = Column(Integer, default=0)  # Количество шёлковых деревьев
    planted_at = Column(Integer, default=0)  # Дата посадки (timestamp)
    harvest_ready_at = Column(Integer, default=0)  # Дата готовности урожая (timestamp)
    status = Column(String, default='growing', index=True)  # growing | ready | harvesting | completed
    investment_cost = Column(Integer, default=0)  # Стоимость инвестиции в септимах
    expected_yield = Column(Integer, default=0)  # Ожидаемый урожай
    investment_level = Column(String, default='starter', index=True)  # starter | standard | premium | master
    quality_modifier = Column(Integer, default=100)  # Модификатор качества (в процентах, 80-120)
    weather_modifier = Column(Integer, default=100)  # Модификатор погоды (в процентах, 90-110)
    
    player = relationship('Player')
    
    __table_args__ = (
        Index('idx_silk_plantation_player', 'player_id'),
        Index('idx_silk_plantation_status', 'status'),
        Index('idx_silk_plantation_harvest_time', 'harvest_ready_at'),
    )

class SilkInventory(Base):
    __tablename__ = 'silk_inventory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey('players.user_id'), index=True)
    silk_type = Column(String, index=True)  # raw | refined | premium
    quantity = Column(Integer, default=0)
    quality_grade = Column(Integer, default=300)  # Оценка качества (100-500, где 300 - среднее)
    produced_at = Column(Integer, default=lambda: int(time.time()))  # Дата производства
    
    player = relationship('Player')
    
    __table_args__ = (
        Index('idx_silk_inventory_player', 'player_id'),
        Index('idx_silk_inventory_type', 'silk_type'),
    )

class SilkTransaction(Base):
    __tablename__ = 'silk_transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(BigInteger, ForeignKey('players.user_id'), nullable=True)  # ID продавца (может быть NPC)
    buyer_id = Column(BigInteger, ForeignKey('players.user_id'), index=True)  # ID покупателя
    transaction_type = Column(String, index=True)  # buy | sell | trade | npc_sale
    silk_type = Column(String)  # raw | refined | premium
    amount = Column(Integer, default=0)  # Количество товара
    price_per_unit = Column(Integer, default=0)  # Цена за единицу в септимах
    total_price = Column(Integer, default=0)  # Общая стоимость сделки
    created_at = Column(Integer, default=lambda: int(time.time()), index=True)  # Дата транзакции
    
    seller = relationship('Player', foreign_keys=[seller_id])
    buyer = relationship('Player', foreign_keys=[buyer_id])
    
    __table_args__ = (
        Index('idx_silk_transaction_seller', 'seller_id'),
        Index('idx_silk_transaction_buyer', 'buyer_id'),
        Index('idx_silk_transaction_type', 'transaction_type'),
        Index('idx_silk_transaction_date', 'created_at'),
    )

# --- Плантация: модели ---

class Fertilizer(Base):
    __tablename__ = 'fertilizers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    effect = Column(String, nullable=True)  # произвольное описание эффекта/модификаторов
    duration_sec = Column(Integer, default=7200)  # длительность действия в секундах
    price_coins = Column(Integer, default=0)

class SeedType(Base):
    __tablename__ = 'seed_types'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    drink_id = Column(Integer, ForeignKey('energy_drinks.id'), index=True)
    price_coins = Column(Integer, default=0)
    grow_time_sec = Column(Integer, default=3600)
    water_interval_sec = Column(Integer, default=1800)
    yield_min = Column(Integer, default=1)
    yield_max = Column(Integer, default=1)
    drink = relationship('EnergyDrink')


class SeedInventory(Base):
    __tablename__ = 'seed_inventory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey('players.user_id'))
    seed_type_id = Column(Integer, ForeignKey('seed_types.id'))
    quantity = Column(Integer, default=0)
    player = relationship('Player')
    seed_type = relationship('SeedType')

    __table_args__ = (
        Index('idx_seed_inventory_player', 'player_id'),
        Index('idx_seed_inventory_seed', 'seed_type_id'),
    )


class FertilizerInventory(Base):
    __tablename__ = 'fertilizer_inventory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey('players.user_id'))
    fertilizer_id = Column(Integer, ForeignKey('fertilizers.id'))
    quantity = Column(Integer, default=0)
    player = relationship('Player')
    fertilizer = relationship('Fertilizer')

    __table_args__ = (
        Index('idx_fertilizer_inventory_player', 'player_id'),
        Index('idx_fertilizer_inventory_fertilizer', 'fertilizer_id'),
    )

class PlantationBed(Base):
    __tablename__ = 'plantation_beds'
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey('players.user_id'), index=True)
    bed_index = Column(Integer, default=1)  # Порядковый номер грядки у игрока
    state = Column(String, default='empty', index=True)  # empty | growing | ready | withered
    seed_type_id = Column(Integer, ForeignKey('seed_types.id'), nullable=True)
    planted_at = Column(Integer, default=0)
    last_watered_at = Column(Integer, default=0)
    water_count = Column(Integer, default=0)
    fertilizer_id = Column(Integer, ForeignKey('fertilizers.id'), nullable=True)
    fertilizer_applied_at = Column(Integer, default=0)
    status_effect = Column(String, nullable=True)  # e.g. 'weeds' | 'pests' | 'drought'

    owner = relationship('Player')
    seed_type = relationship('SeedType')
    fertilizer = relationship('Fertilizer')
    active_fertilizers = relationship('BedFertilizer', back_populates='bed', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_plantation_owner', 'owner_id'),
        Index('idx_plantation_owner_bed', 'owner_id', 'bed_index'),
        Index('idx_plantation_fertilizer', 'fertilizer_id'),
    )


class BedFertilizer(Base):
    """Таблица для хранения множественных активных удобрений на грядке."""
    __tablename__ = 'bed_fertilizers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    bed_id = Column(Integer, ForeignKey('plantation_beds.id'), index=True)
    fertilizer_id = Column(Integer, ForeignKey('fertilizers.id'))
    applied_at = Column(Integer, default=0)
    
    bed = relationship('PlantationBed', back_populates='active_fertilizers')
    fertilizer = relationship('Fertilizer')
    
    __table_args__ = (
        Index('idx_bed_fertilizer_bed', 'bed_id'),
        Index('idx_bed_fertilizer_fertilizer', 'fertilizer_id'),
    )


class CommunityPlantation(Base):
    __tablename__ = 'community_plantations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)
    description = Column(String, nullable=True)
    created_at = Column(Integer, default=lambda: int(time.time()))
    created_by = Column(BigInteger, nullable=True)

class CommunityProjectState(Base):
    __tablename__ = 'community_project_state'
    project_id = Column(Integer, ForeignKey('community_plantations.id'), primary_key=True)
    goal_amount = Column(Integer, default=1000)
    progress_amount = Column(Integer, default=0, index=True)
    status = Column(String, default='active', index=True)  # active | completed
    reward_total_coins = Column(Integer, default=250)

class CommunityParticipant(Base):
    __tablename__ = 'community_participants'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('community_plantations.id'), index=True)
    user_id = Column(BigInteger, index=True)
    joined_at = Column(Integer, default=lambda: int(time.time()))
    contributed_amount = Column(Integer, default=0)
    reward_claimed = Column(Boolean, default=False, index=True)
    __table_args__ = (
        Index('idx_comm_part_proj_user', 'project_id', 'user_id', unique=True),
    )

class CommunityContributionLog(Base):
    __tablename__ = 'community_contrib_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('community_plantations.id'), index=True)
    user_id = Column(BigInteger, index=True)
    amount = Column(Integer, default=0)
    ts = Column(Integer, default=lambda: int(time.time()), index=True)

# --- Статистика находок напитков (система "горячих" и "холодных" напитков) ---

class DrinkDiscoveryStats(Base):
    """Таблица для отслеживания частоты находок напитков.
    Используется для системы "горячих" и "холодных" напитков."""
    __tablename__ = 'drink_discovery_stats'
    id = Column(Integer, primary_key=True, autoincrement=True)
    drink_id = Column(Integer, ForeignKey('energy_drinks.id'), unique=True, index=True)
    total_discoveries = Column(Integer, default=0)  # Всего раз найден
    last_discovered_at = Column(Integer, default=0, index=True)  # Последняя находка (timestamp)
    global_discoveries_today = Column(Integer, default=0)  # Находок сегодня (глобально)
    last_reset_date = Column(Integer, default=0)  # Дата последнего сброса дневного счетчика
    
    drink = relationship('EnergyDrink')
    
    __table_args__ = (
        Index('idx_drink_stats_drink', 'drink_id'),
        Index('idx_drink_stats_last_discovered', 'last_discovered_at'),
    )


# --- Система подарков ---

class GiftHistory(Base):
    """Таблица для хранения истории всех подарков."""
    __tablename__ = 'gift_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    giver_id = Column(BigInteger, index=True)  # ID дарителя
    recipient_id = Column(BigInteger, index=True)  # ID получателя
    drink_id = Column(Integer, ForeignKey('energy_drinks.id'))
    rarity = Column(String)
    status = Column(String, index=True)  # 'accepted' | 'declined'
    created_at = Column(Integer, default=lambda: int(time.time()), index=True)
    
    drink = relationship('EnergyDrink')
    
    __table_args__ = (
        Index('idx_gift_history_giver', 'giver_id'),
        Index('idx_gift_history_recipient', 'recipient_id'),
        Index('idx_gift_history_timestamp', 'created_at'),
        Index('idx_gift_history_giver_recipient', 'giver_id', 'recipient_id'),
    )


class GiftRestriction(Base):
    """Таблица для хранения блокировок на дарение подарков."""
    __tablename__ = 'gift_restrictions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, index=True)  # ID заблокированного пользователя
    reason = Column(String)  # Причина блокировки
    blocked_at = Column(Integer, default=lambda: int(time.time()), index=True)
    blocked_until = Column(Integer, nullable=True, index=True)  # NULL = навсегда, иначе timestamp
    blocked_by = Column(BigInteger, nullable=True)  # ID админа или системы (None = автоматическая)
    
    __table_args__ = (
        Index('idx_gift_restriction_user', 'user_id'),
        Index('idx_gift_restriction_until', 'blocked_until'),
    )


# --- Функции для взаимодействия с базой данных ---

def create_db_and_tables():
    """Создает файл базы данных и все таблицы, если их нет."""
    Base.metadata.create_all(bind=engine)
    print("База данных и таблицы успешно созданы.")

def _ensure_player_has_autosearch_columns():
    """Гарантирует наличие колонок для тихого автопоиска в таблице players."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(players)")).fetchall()
            cols = [row[1] for row in res]
            if 'auto_search_silent' not in cols:
                conn.execute(text("ALTER TABLE players ADD COLUMN auto_search_silent BOOLEAN DEFAULT 0"))
            if 'auto_search_session_stats' not in cols:
                conn.execute(text("ALTER TABLE players ADD COLUMN auto_search_session_stats VARCHAR DEFAULT '{}'"))
            conn.commit()
    except Exception as e:
        print(f"Error checking/adding auto_search columns: {e}")

def _ensure_promos_has_rarity_column():
    """Гарантирует наличие колонки rarity в таблице promos (SQLite)."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(promos)")).fetchall()
            cols = [row[1] for row in res]
            if 'rarity' not in cols:
                conn.execute(text("ALTER TABLE promos ADD COLUMN rarity VARCHAR"))
    except Exception:
        pass

def _ensure_player_has_selyuk_fragments_column():
    """Гарантирует наличие колонки selyuk_fragments в таблице players."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(players)")).fetchall()
            cols = [row[1] for row in res]
            if 'selyuk_fragments' not in cols:
                conn.execute(text("ALTER TABLE players ADD COLUMN selyuk_fragments INTEGER DEFAULT 0"))
    except Exception as e:
        print(f"Error checking/adding selyuk_fragments column: {e}")

def get_or_create_player(user_id, username):
    """Возвращает игрока по ID. Если его нет, создает нового."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        # Нормализуем username: только валидные @username (буквы/цифры/подчёркивания 3-32)
        new_uname = None
        try:
            if username:
                uname = str(username).lstrip('@')
                if re.fullmatch(r"[A-Za-z0-9_]{3,32}", uname or ""):
                    new_uname = uname
        except Exception:
            new_uname = None
        if not player:
            # Создаём игрока; заполняем username только если он валиден
            player = Player(user_id=user_id, username=new_uname)
            db.add(player)
            db.commit()
            db.refresh(player)
            print(f"Создан новый игрок: {new_uname or user_id} ({user_id})")
        else:
            # Автообновляем username, если пришёл валидный и отличается от сохранённого
            if new_uname and new_uname != getattr(player, 'username', None):
                try:
                    player.username = new_uname
                    db.commit()
                except Exception:
                    db.rollback()
        return player
    finally:
        db.close()

def get_active_ban(user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        try:
            if is_protected_user(int(user_id)):
                try:
                    recp = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
                    if recp:
                        db.delete(recp)
                        db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                return None
        except Exception:
            pass
        now_ts = int(time.time())
        rec = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
        if not rec:
            return None
        until = getattr(rec, 'banned_until', None)
        if until is None or int(until) > now_ts:
            return {
                'user_id': int(rec.user_id),
                'reason': rec.reason,
                'banned_at': int(rec.banned_at or 0),
                'banned_until': int(rec.banned_until or 0) if rec.banned_until else None,
                'banned_by': int(rec.banned_by or 0) if rec.banned_by else None,
            }
        return None
    finally:
        db.close()

def create_promo(code: str, kind: str, value: int, max_uses: int, per_user_limit: int, expires_at: int | None, active: bool = True, rarity: str | None = None) -> dict:
    db = SessionLocal()
    try:
        _ensure_promos_has_rarity_column()
        existing = db.query(Promo).filter(Promo.code == code).first()
        if existing:
            return {"ok": False, "reason": "exists"}
        row = Promo(
            code=code.strip(),
            kind=kind.strip(),
            value=int(value),
            max_uses=int(max_uses or 0),
            per_user_limit=int(per_user_limit or 0),
            expires_at=int(expires_at) if expires_at else None,
            active=bool(active),
            rarity=(str(rarity).strip() if rarity else None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "id": int(row.id)}
    except Exception:
        db.rollback()
        return {"ok": False, "reason": "exception"}
    finally:
        db.close()

def list_promos(active_only: bool = False) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(Promo).order_by(Promo.created_at.desc())
        if active_only:
            now_ts = int(time.time())
            q = q.filter(Promo.active == True, ((Promo.expires_at == None) | (Promo.expires_at > now_ts)))
        rows = q.all()
        out = []
        for r in rows:
            used = db.query(func.count(PromoUsage.id)).filter(PromoUsage.promo_id == r.id).scalar() or 0
            out.append({
                'id': int(r.id),
                'code': r.code,
                'kind': r.kind,
                'value': int(r.value or 0),
                'rarity': r.rarity,
                'max_uses': int(r.max_uses or 0),
                'per_user_limit': int(r.per_user_limit or 0),
                'expires_at': int(r.expires_at or 0) if r.expires_at else None,
                'active': bool(r.active),
                'used': int(used),
            })
        return out
    except Exception:
        return []
    finally:
        db.close()

def deactivate_promo_by_id(promo_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Promo).filter(Promo.id == int(promo_id)).first()
        if not row:
            return False
        row.active = False
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def deactivate_promo_by_code(code: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Promo).filter(Promo.code == code.strip()).first()
        if not row:
            return False
        row.active = False
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def get_promo_usage_total() -> int:
    db = SessionLocal()
    try:
        return int(db.query(func.count(PromoUsage.id)).scalar() or 0)
    except Exception:
        return 0
    finally:
        db.close()

# Пользовательская активация промокодов

def redeem_promo(user_id: int, code: str) -> dict:
    db = SessionLocal()
    try:
        create_db_and_tables()
        _ensure_promos_has_rarity_column()
        _ensure_player_has_autosearch_columns()
        _ensure_player_has_casino_stats()
        code_s = (code or '').strip()
        if not code_s:
            return {"ok": False, "reason": "not_found_or_inactive"}

        row = db.query(Promo).filter(func.lower(Promo.code) == code_s.lower()).first()
        if not row or not bool(row.active):
            return {"ok": False, "reason": "not_found_or_inactive"}

        now_ts = int(time.time())
        if getattr(row, 'expires_at', None):
            try:
                exp = int(row.expires_at)
            except Exception:
                exp = None
            if exp and now_ts >= exp:
                return {"ok": False, "reason": "expired"}

        # Общий лимит
        used_total = int(db.query(func.count(PromoUsage.id)).filter(PromoUsage.promo_id == row.id).scalar() or 0)
        if int(row.max_uses or 0) > 0 and used_total >= int(row.max_uses):
            return {"ok": False, "reason": "max_uses_reached"}

        # Лимит на пользователя
        used_by_user = int(
            db.query(func.count(PromoUsage.id))
            .filter(PromoUsage.promo_id == row.id, PromoUsage.user_id == int(user_id))
            .scalar() or 0
        )
        if int(row.per_user_limit or 0) > 0 and used_by_user >= int(row.per_user_limit):
            return {"ok": False, "reason": "per_user_limit_reached"}

        # Гарантируем наличие игрока
        player = db.query(Player).filter(Player.user_id == int(user_id)).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=int(user_id), username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)

        kind = str(row.kind or '').strip().lower()
        value = int(row.value or 0)
        


        result: dict = {"ok": True, "kind": kind, "value": value}

        if kind == 'coins':
            add = max(0, value)
            current = int(player.coins or 0)
            player.coins = current + add
            db.add(PromoUsage(promo_id=int(row.id), user_id=int(user_id)))
            db.commit()
            result.update({"coins_added": add, "coins_total": int(player.coins)})
            try:
                log_action(int(user_id), getattr(player, 'username', None), 'promo_redeem', f'coins:+{add}', success=True)
            except Exception:
                pass
            return result

        elif kind == 'vip':
            # value — дни VIP
            add_sec = max(0, int(value)) * 86400
            now_ts = int(time.time())
            base_ts = int(getattr(player, 'vip_until', 0) or 0)
            start_ts = base_ts if base_ts > now_ts else now_ts
            player.vip_until = start_ts + add_sec
            db.add(PromoUsage(promo_id=int(row.id), user_id=int(user_id)))
            db.commit()
            result.update({"vip_until": int(player.vip_until)})
            try:
                log_action(int(user_id), getattr(player, 'username', None), 'promo_redeem', f'vip:+{add_sec}s', success=True)
            except Exception:
                pass
            return result

        elif kind == 'vip_plus':
            # value — дни VIP+
            add_sec = max(0, int(value)) * 86400
            now_ts = int(time.time())
            base_ts = int(getattr(player, 'vip_plus_until', 0) or 0)
            start_ts = base_ts if base_ts > now_ts else now_ts
            player.vip_plus_until = start_ts + add_sec
            db.add(PromoUsage(promo_id=int(row.id), user_id=int(user_id)))
            db.commit()
            result.update({"vip_plus_until": int(player.vip_plus_until)})
            try:
                log_action(int(user_id), getattr(player, 'username', None), 'promo_redeem', f'vip_plus:+{add_sec}s', success=True)
            except Exception:
                pass
            return result

        elif kind == 'drink':
            # value — drink_id, редкость из колонки rarity (или Basic по умолчанию)
            drink = db.query(EnergyDrink).filter(EnergyDrink.id == int(value)).first()
            if not drink:
                return {"ok": False, "reason": "invalid_drink"}
            rarity = str(getattr(row, 'rarity', '') or '').strip() or 'Basic'
            # Добавляем в инвентарь в рамках одной сессии
            item = db.query(InventoryItem).filter_by(player_id=int(user_id), drink_id=int(drink.id), rarity=rarity).first()
            if item:
                item.quantity = int(item.quantity or 0) + 1
            else:
                db.add(InventoryItem(player_id=int(user_id), drink_id=int(drink.id), rarity=rarity, quantity=1))
            db.add(PromoUsage(promo_id=int(row.id), user_id=int(user_id)))
            db.commit()
            result.update({"drink_name": getattr(drink, 'name', 'Энергетик'), "rarity": rarity})
            try:
                log_action(int(user_id), getattr(player, 'username', None), 'promo_redeem', f'drink:{getattr(drink, "name", "?")}/{rarity}', success=True)
            except Exception:
                pass
            return result

        else:
            return {"ok": False, "reason": "unsupported_kind"}

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        db.close()

def get_all_active_beds_for_reminders() -> list[dict]:
    """
    Возвращает список всех грядок, которые растут, для восстановления напоминаний.
    Возвращает: [{user_id, bed_index, next_water_ts, water_interval_sec}, ...]
    """
    db = SessionLocal()
    try:
        # Получаем грядки:
        # 1. Статус growing
        # 2. Есть seed_type (чтобы знать интервал полива)
        # 3. Владелец включил напоминания (remind_plantation = True)
        
        results = (
            db.query(PlantationBed, SeedType.water_interval_sec, Player.user_id)
            .join(SeedType, PlantationBed.seed_type_id == SeedType.id)
            .join(Player, PlantationBed.owner_id == Player.user_id)
            .filter(PlantationBed.state == 'growing')
            .filter(Player.remind_plantation == True)
            .all()
        )
        
        out = []
        for bed, interval, uid in results:
            # Вычисляем время следующего полива
            last_watered = bed.last_watered_at or bed.planted_at
            next_water_ts = last_watered + interval
            
            # Если уже пора поливать или время прошло - всё равно добавляем, 
            # job_queue запустит сразу (when=0 или отрицательное)
            
            out.append({
                'user_id': uid,
                'bed_index': bed.bed_index,
                'next_water_ts': next_water_ts,
                'water_interval_sec': interval
            })
        return out
    except Exception as e:
        print(f"Error getting active beds for reminders: {e}")
        return []
    finally:
        db.close()

def get_setting_str(key: str, default_value: str | None = None) -> str | None:
    db = SessionLocal()
    try:
        row = db.query(BotSetting).filter(BotSetting.key == key).first()
        if not row or row.value is None:
            return default_value
        return str(row.value)
    finally:
        db.close()

def set_setting_str(key: str, value: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(BotSetting).filter(BotSetting.key == key).first()
        if not row:
            row = BotSetting(key=key, value=str(value))
            db.add(row)
        else:
            row.value = str(value)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        db.close()

def get_setting_int(key: str, default_value: int) -> int:
    s = get_setting_str(key, None)
    try:
        return int(s) if s is not None else int(default_value)
    except Exception:
        return int(default_value)

def set_setting_int(key: str, value: int) -> bool:
    return set_setting_str(key, str(int(value)))

def get_setting_float(key: str, default_value: float) -> float:
    s = get_setting_str(key, None)
    try:
        return float(s) if s is not None else float(default_value)
    except Exception:
        return float(default_value)

def set_setting_float(key: str, value: float) -> bool:
    return set_setting_str(key, str(float(value)))

def get_setting_bool(key: str, default_value: bool) -> bool:
    s = get_setting_str(key, None)
    if s is None:
        return bool(default_value)
    s_lower = s.strip().lower()
    if s_lower in ("1", "true", "yes", "on", "y", "t"):
        return True
    if s_lower in ("0", "false", "no", "off", "n", "f"):
        return False
    return bool(default_value)

def set_setting_bool(key: str, value: bool) -> bool:
    return set_setting_str(key, "1" if value else "0")

# --- Магазин: офферы и покупки ---

SHOP_REFRESH_SEC = 4 * 60 * 60  # 4 часа

def get_or_refresh_shop_offers() -> tuple[list[ShopOffer], int]:
    """Возвращает текущие 50 офферов магазина и их batch_ts.
    Если последняя генерация была более 4 часов назад или офферов меньше 50, сгенерировать новый пакет.
    """
    dbs = SessionLocal()
    try:
        now_ts = int(time.time())
        # Найдём последний batch_ts
        last = (
            dbs.query(ShopOffer.batch_ts)
            .order_by(ShopOffer.batch_ts.desc())
            .first()
        )
        need_refresh = False
        last_ts = 0
        if last:
            last_ts = int(last[0] or 0)
            if now_ts - last_ts >= SHOP_REFRESH_SEC:
                need_refresh = True
        else:
            need_refresh = True

        offers_count = dbs.query(ShopOffer).count()
        if offers_count != 50:
            need_refresh = True

        if need_refresh:
            # полная регенерация
            dbs.query(ShopOffer).delete(synchronize_session=False)
            drinks = dbs.query(EnergyDrink).filter(EnergyDrink.is_special == False).all() or []
            if not drinks:
                dbs.commit()
                return ([], 0)
            rarities = list(RARITIES.keys())
            weights = [int(RARITIES[r]) for r in rarities]
            new_ts = now_ts
            for i in range(50):
                d = random.choice(drinks)
                rrt = random.choices(rarities, weights=weights, k=1)[0]
                row = ShopOffer(offer_index=i + 1, drink_id=int(d.id), rarity=rrt, batch_ts=new_ts)
                dbs.add(row)
            dbs.commit()
            last_ts = new_ts

        # Выгружаем офферы с напитками
        rows = (
            dbs.query(ShopOffer)
            .options(joinedload(ShopOffer.drink))
            .order_by(ShopOffer.offer_index.asc())
            .all()
        )
        return (list(rows), last_ts)
    finally:
        dbs.close()


def get_autosell_settings(user_id: int) -> dict:
    """Возвращает словарь настроек автопродажи по редкостям для указанного пользователя.

    Формат: { 'Basic': bool, 'Medium': bool, ... }
    Отсутствующие записи трактуются как выключенные (False).
    """
    dbs = SessionLocal()
    try:
        rows = (
            dbs.query(AutoSellSetting)
            .filter(AutoSellSetting.user_id == int(user_id))
            .all()
        )
        settings: dict[str, bool] = {}
        for row in rows:
            try:
                if row.rarity:
                    settings[str(row.rarity)] = bool(row.enabled)
            except Exception:
                continue
        return settings
    finally:
        dbs.close()


def is_autosell_enabled(user_id: int, rarity: str) -> bool:
    """Проверяет, включена ли автопродажа для указанной редкости у пользователя."""
    if not rarity:
        return False
    dbs = SessionLocal()
    try:
        row = (
            dbs.query(AutoSellSetting)
            .filter(
                AutoSellSetting.user_id == int(user_id),
                AutoSellSetting.rarity == str(rarity),
            )
            .first()
        )
        if not row:
            return False
        return bool(row.enabled)
    finally:
        dbs.close()


def set_autosell_enabled(user_id: int, rarity: str, enabled: bool) -> bool:
    """Устанавливает режим автопродажи для указанной редкости пользователя.

    Возвращает True при успешном сохранении.
    """
    if not rarity:
        return False
    dbs = SessionLocal()
    try:
        row = (
            dbs.query(AutoSellSetting)
            .filter(
                AutoSellSetting.user_id == int(user_id),
                AutoSellSetting.rarity == str(rarity),
            )
            .first()
        )
        if not row:
            row = AutoSellSetting(
                user_id=int(user_id),
                rarity=str(rarity),
                enabled=bool(enabled),
            )
            dbs.add(row)
        else:
            row.enabled = bool(enabled)
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()


def has_inventory_item(user_id: int, drink_id: int, rarity: str) -> bool:
    """Проверяет, есть ли у пользователя в инвентаре хотя бы 1 энергетик указанного drink_id и редкости."""
    if not drink_id or not rarity:
        return False
    dbs = SessionLocal()
    try:
        item = (
            dbs.query(InventoryItem)
            .filter(
                InventoryItem.player_id == int(user_id),
                InventoryItem.drink_id == int(drink_id),
                InventoryItem.rarity == str(rarity),
                InventoryItem.quantity > 0,
            )
            .first()
        )
        return item is not None
    except Exception:
        return False
    finally:
        dbs.close()


def purchase_next_bed(user_id: int) -> dict:
    """Покупка следующей грядки до максимум 5. Цены: 2-я — 1000, затем x2 (2000, 4000, 8000)."""
    dbs = SessionLocal()
    try:
        beds = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == user_id)
            .order_by(PlantationBed.bed_index.asc())
            .with_for_update(read=False)
            .all()
        )
        owned = len(beds)
        if owned >= 5:
            return {"ok": False, "reason": "max_reached", "owned": owned}
        next_index = owned + 1
        if next_index <= 1:
            # Ничего покупать не нужно — базовая грядка создаётся ensure_player_beds
            return {"ok": True, "owned": owned}
        # Расчёт цены: 2 -> 1000, 3 -> 2000, 4 -> 4000, 5 -> 8000
        price = 1000 * (2 ** (next_index - 2))
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id), coins=0)
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        if int(player.coins or 0) < price:
            return {"ok": False, "reason": "not_enough_coins", "price": price, "coins": int(player.coins or 0)}
        # Списываем, создаём грядку
        player.coins = int(player.coins or 0) - price
        b = PlantationBed(owner_id=user_id, bed_index=next_index, state='empty', seed_type_id=None, planted_at=0, last_watered_at=0, water_count=0)
        dbs.add(b)
        dbs.commit()
        dbs.refresh(b)
        return {"ok": True, "new_bed_index": next_index, "coins_left": int(player.coins)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def purchase_shop_offer(user_id: int, offer_index: int) -> dict:
    """Покупка оффера магазина по индексу (1..50).
    Возвращает dict: {ok, reason?, coins_left?, drink_name?, rarity?}
    Возможные reason: no_offer, not_enough_coins, exception
    """
    dbs = SessionLocal()
    try:
        # Получаем оффер и игрока в транзакции
        off = (
            dbs.query(ShopOffer)
            .options(joinedload(ShopOffer.drink))
            .filter(ShopOffer.offer_index == int(offer_index))
            .first()
        )
        if not off or not off.drink:
            return {"ok": False, "reason": "no_offer"}

        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        rarity = str(off.rarity)
        price = int(SHOP_PRICES.get(rarity, 0))
        if price <= 0:
            return {"ok": False, "reason": "no_offer"}

        coins = int(player.coins or 0)
        if coins < price:
            return {"ok": False, "reason": "not_enough_coins", "coins_left": coins}

        # списываем, добавляем предмет
        player.coins = coins - price
        # добавить в инвентарь
        item = dbs.query(InventoryItem).filter_by(player_id=user_id, drink_id=off.drink_id, rarity=rarity).first()
        if item:
            item.quantity = int(item.quantity or 0) + 1
        else:
            dbs.add(InventoryItem(player_id=user_id, drink_id=off.drink_id, rarity=rarity, quantity=1))
        dbs.commit()
        return {
            "ok": True,
            "coins_left": int(player.coins or 0),
            "drink_name": off.drink.name,
            "rarity": rarity,
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


 


# --- Плантация: CRUD и хелперы ---

def list_seed_types() -> list[SeedType]:
    dbs = SessionLocal()
    try:
        return list(dbs.query(SeedType).order_by(SeedType.id.asc()).all())
    finally:
        dbs.close()


def get_seed_type_by_id(seed_type_id: int) -> SeedType | None:
    dbs = SessionLocal()
    try:
        return dbs.query(SeedType).filter(SeedType.id == seed_type_id).first()
    finally:
        dbs.close()


def get_seed_price_by_rarity(rarity: str) -> int:
    """Возвращает цену семян в зависимости от редкости напитка.
    Basic -> 50, Medium -> 120, Elite/Absolute/Majestic -> 250
    """
    rarity = str(rarity).strip()
    if rarity == 'Basic':
        return 50
    elif rarity == 'Medium':
        return 120
    else:  # Elite, Absolute, Majestic, Special и т.д.
        return 250


def ensure_default_seed_types() -> int:
    """Создаёт базовые типы семян, если их нет. Возвращает количество добавленных записей.
    Логика: берём первые 3 энергетика и делаем по семени на каждый.
    Если энергетиков мало, создаём столько, сколько есть.
    """
    dbs = SessionLocal()
    try:
        # Миграция: обновляем цены и параметры всех существующих семян на основе редкости связанного напитка
        try:
            all_seeds = dbs.query(SeedType).options(joinedload(SeedType.drink)).all()
            updated = 0
            for seed in all_seeds:
                if seed.drink:
                    # Получаем правильные параметры по редкости напитка
                    correct_price = get_seed_price_by_rarity(getattr(seed.drink, 'rarity', 'Basic'))
                    
                    # Определяем параметры по цене
                    if correct_price == 50:  # Basic
                        grow_time, water_int, ymin, ymax = 7200, 1800, 1, 2
                    elif correct_price == 120:  # Medium
                        grow_time, water_int, ymin, ymax = 10800, 2400, 1, 2
                    else:  # 250 - Elite+
                        grow_time, water_int, ymin, ymax = 14400, 3600, 1, 3
                    
                    # Обновляем все параметры
                    changed = False
                    if seed.price_coins != correct_price:
                        seed.price_coins = correct_price
                        changed = True
                    if seed.grow_time_sec != grow_time:
                        seed.grow_time_sec = grow_time
                        changed = True
                    if seed.water_interval_sec != water_int:
                        seed.water_interval_sec = water_int
                        changed = True
                    if seed.yield_min != ymin:
                        seed.yield_min = ymin
                        changed = True
                    if seed.yield_max != ymax:
                        seed.yield_max = ymax
                        changed = True
                    
                    if changed:
                        updated += 1
            
            if updated > 0:
                dbs.commit()
        except Exception:
            try:
                dbs.rollback()
            except Exception:
                pass

        existing = dbs.query(SeedType).count()
        if existing > 0:
            return 0
        drinks = dbs.query(EnergyDrink).order_by(EnergyDrink.id.asc()).limit(3).all()
        if not drinks:
            return 0
        added = 0
        for drink in drinks:
            # Определяем цену и параметры по редкости напитка
            price = get_seed_price_by_rarity(getattr(drink, 'rarity', 'Basic'))
            # Параметры также зависят от редкости
            if price == 50:  # Basic
                grow_time, water_int, ymin, ymax = 7200, 1800, 1, 2
            elif price == 120:  # Medium
                grow_time, water_int, ymin, ymax = 10800, 2400, 1, 2
            else:  # 250 - Elite+
                grow_time, water_int, ymin, ymax = 14400, 3600, 1, 3
            
            st = SeedType(
                name=f"Семена {drink.name}",
                description=f"Семена для выращивания напитка '{drink.name}'.",
                drink_id=drink.id,
                price_coins=price,
                grow_time_sec=grow_time,
                water_interval_sec=water_int,
                yield_min=ymin,
                yield_max=ymax,
            )
            dbs.add(st)
            added += 1
        dbs.commit()
        return added
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return 0
    finally:
        dbs.close()


def get_or_create_seed_type_for_drink(drink_id: int) -> SeedType | None:
    """Возвращает SeedType для указанного энергетика или создаёт его с дефолтными параметрами.
    Возвращает объект SeedType или None, если энергетик не найден.
    """
    dbs = SessionLocal()
    try:
        drink = dbs.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return None
        # Пытаемся найти по drink_id
        st = (
            dbs.query(SeedType)
            .filter(SeedType.drink_id == drink_id)
            .order_by(SeedType.id.asc())
            .first()
        )
        if st:
            return st
        # Пытаемся найти по имени (на случай существующих записей по уникальному имени)
        expected_name = f"Семена {drink.name}"
        st_by_name = (
            dbs.query(SeedType)
            .filter(SeedType.name == expected_name)
            .order_by(SeedType.id.asc())
            .first()
        )
        if st_by_name:
            # Заполним связь drink_id, если не задана
            if not getattr(st_by_name, 'drink_id', None):
                try:
                    st_by_name.drink_id = drink.id
                    dbs.commit()
                except Exception:
                    try:
                        dbs.rollback()
                    except Exception:
                        pass
            return st_by_name
        # Создаём новый тип семян с параметрами по редкости напитка
        price = get_seed_price_by_rarity(getattr(drink, 'rarity', 'Basic'))
        # Параметры зависят от редкости
        if price == 50:  # Basic
            grow_time, water_int, ymin, ymax = 7200, 1800, 1, 2
        elif price == 120:  # Medium
            grow_time, water_int, ymin, ymax = 10800, 2400, 1, 2
        else:  # 250 - Elite+
            grow_time, water_int, ymin, ymax = 14400, 3600, 1, 3
        
        st_new = SeedType(
            name=expected_name,
            description=f"Семена для выращивания напитка '{drink.name}'.",
            drink_id=drink.id,
            price_coins=price,
            grow_time_sec=grow_time,
            water_interval_sec=water_int,
            yield_min=ymin,
            yield_max=ymax,
        )
        dbs.add(st_new)
        try:
            dbs.commit()
            dbs.refresh(st_new)
            return st_new
        except Exception:
            try:
                dbs.rollback()
            except Exception:
                pass
            # Повторно ищем (вдруг была гонка или конфликт по имени)
            st_retry = (
                dbs.query(SeedType)
                .filter(SeedType.name == expected_name)
                .order_by(SeedType.id.asc())
                .first()
            )
            return st_retry
    finally:
        dbs.close()


def ensure_seed_types_for_drinks(drink_ids: list[int]) -> list[SeedType]:
    """Гарантирует наличие типов семян для списка энергетиков. Возвращает список SeedType."""
    result: list[SeedType] = []
    for did in drink_ids or []:
        st = get_or_create_seed_type_for_drink(int(did))
        if st:
            result.append(st)
    return result


def get_seed_inventory(user_id: int) -> list[SeedInventory]:
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(SeedInventory)
            .options(joinedload(SeedInventory.seed_type))
            .filter(SeedInventory.player_id == user_id)
            .order_by(SeedInventory.id.asc())
            .all()
        )
    finally:
        dbs.close()


def get_seed_inventory_item(user_id: int, seed_type_id: int) -> SeedInventory | None:
    dbs = SessionLocal()
    try:
        return (
            dbs.query(SeedInventory)
            .filter(SeedInventory.player_id == user_id, SeedInventory.seed_type_id == seed_type_id)
            .first()
        )
    finally:
        dbs.close()


def change_seed_inventory(user_id: int, seed_type_id: int, delta: int) -> int:
    """Изменяет количество семян у игрока на delta. Возвращает новое кол-во (не ниже 0)."""
    dbs = SessionLocal()
    try:
        row = (
            dbs.query(SeedInventory)
            .filter(SeedInventory.player_id == user_id, SeedInventory.seed_type_id == seed_type_id)
            .with_for_update(read=False)
            .first()
        )
        if not row:
            row = SeedInventory(player_id=user_id, seed_type_id=seed_type_id, quantity=0)
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
        row.quantity = max(0, int(row.quantity or 0) + int(delta))
        dbs.commit()
        return int(row.quantity)
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        # Возвращаем текущее значение при ошибке
        try:
            row2 = (
                dbs.query(SeedInventory)
                .filter(SeedInventory.player_id == user_id, SeedInventory.seed_type_id == seed_type_id)
                .first()
            )
            return int(getattr(row2, 'quantity', 0) or 0) if row2 else 0
        except Exception:
            return 0
    finally:
        dbs.close()


def purchase_seeds(user_id: int, seed_type_id: int, quantity: int) -> dict:
    """Покупка семян. Возвращает dict: {ok, reason?, coins_left?, inventory_qty?}"""
    if quantity <= 0:
        return {"ok": False, "reason": "invalid_quantity"}
    dbs = SessionLocal()
    try:
        seed_type = dbs.query(SeedType).filter(SeedType.id == seed_type_id).first()
        if not seed_type:
            return {"ok": False, "reason": "no_such_seed"}
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        cost = int(seed_type.price_coins or 0) * int(quantity)
        if int(player.coins or 0) < cost:
            return {"ok": False, "reason": "not_enough_coins"}
        # списываем и увеличиваем инвентарь семян
        player.coins = int(player.coins or 0) - cost
        row = (
            dbs.query(SeedInventory)
            .filter(SeedInventory.player_id == user_id, SeedInventory.seed_type_id == seed_type_id)
            .with_for_update(read=False)
            .first()
        )
        if not row:
            row = SeedInventory(player_id=user_id, seed_type_id=seed_type_id, quantity=0)
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
        row.quantity = max(0, int(row.quantity or 0) + int(quantity))
        dbs.commit()
        return {"ok": True, "coins_left": int(player.coins), "inventory_qty": int(row.quantity)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


# --- Удобрения: CRUD и хелперы ---

def ensure_default_fertilizers() -> int:
    """Создаёт 10 дефолтных удобрений, если их нет. Возвращает количество добавленных записей."""
    dbs = SessionLocal()
    try:
        existing = dbs.query(Fertilizer).count()
        if existing > 0:
            return 0
        data = [
            {"name": "Азотное",       "description": "Ускоряет вегетацию",           "effect": "+рост",       "duration_sec": 1500,  "price_coins": 75},   # 25 мин
            {"name": "Фосфорное",     "description": "Усиливает образование плодов", "effect": "+урожай",     "duration_sec": 1800,  "price_coins": 90},   # 30 мин
            {"name": "Калийное",      "description": "Повышает устойчивость",        "effect": "+качество",   "duration_sec": 2250,  "price_coins": 110},  # 37.5 мин
            {"name": "Комплексное",   "description": "Сбалансированная смесь",       "effect": "+всё",        "duration_sec": 2700,  "price_coins": 180},  # 45 мин
            {"name": "Биоактив",      "description": "Органический стимулятор",      "effect": "+био",        "duration_sec": 1800,  "price_coins": 130},  # 30 мин
            {"name": "Стимул-Х",      "description": "Мощный стимулятор роста",       "effect": "+рост+кач",   "duration_sec": 2250,  "price_coins": 200},  # 37.5 мин
            {"name": "Минерал+",      "description": "Минеральный комплекс",         "effect": "+качество",   "duration_sec": 1800,  "price_coins": 150},  # 30 мин
            {"name": "Гумат",         "description": "Гуминовый концентрат",          "effect": "+питание",    "duration_sec": 1500,  "price_coins": 120},  # 25 мин
            {"name": "СуперРост",     "description": "Сокращает время роста",         "effect": "-время",      "duration_sec": 1050,  "price_coins": 250},  # 17.5 мин
            {"name": "МегаУрожай",    "description": "Повышает выход урожая",         "effect": "+урожай++",   "duration_sec": 2700,  "price_coins": 300},  # 45 мин
        ]
        created = 0
        for d in data:
            try:
                dbs.add(Fertilizer(
                    name=d["name"],
                    description=d.get("description"),
                    effect=d.get("effect"),
                    duration_sec=int(d.get("duration_sec", 7200) or 7200),
                    price_coins=int(d.get("price_coins", 0) or 0),
                ))
                created += 1
            except Exception:
                pass
        dbs.commit()
        return int(created)
    finally:
        dbs.close()


def update_fertilizers_duration() -> int:
    """Обновляет duration_sec для существующих удобрений на новые значения (17.5-45 мин).
    Возвращает количество обновленных записей."""
    dbs = SessionLocal()
    try:
        duration_map = {
            "Азотное": 1500,     # 25 мин
            "Фосфорное": 1800,   # 30 мин
            "Калийное": 2250,    # 37.5 мин
            "Комплексное": 2700, # 45 мин
            "Биоактив": 1800,    # 30 мин
            "Стимул-Х": 2250,    # 37.5 мин
            "Минерал+": 1800,    # 30 мин
            "Гумат": 1500,       # 25 мин
            "СуперРост": 1050,   # 17.5 мин
            "МегаУрожай": 2700,  # 45 мин
        }
        
        updated = 0
        for name, duration in duration_map.items():
            try:
                fert = dbs.query(Fertilizer).filter(Fertilizer.name == name).first()
                if fert:
                    fert.duration_sec = duration
                    updated += 1
            except Exception:
                pass
        
        dbs.commit()
        return updated
    finally:
        dbs.close()


def list_fertilizers() -> list[Fertilizer]:
    dbs = SessionLocal()
    try:
        return list(dbs.query(Fertilizer).order_by(Fertilizer.id.asc()).all())
    finally:
        dbs.close()


def get_fertilizer_inventory(user_id: int) -> list[FertilizerInventory]:
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(FertilizerInventory)
            .options(joinedload(FertilizerInventory.fertilizer))
            .filter(FertilizerInventory.player_id == user_id)
            .order_by(FertilizerInventory.id.asc())
            .all()
        )
    finally:
        dbs.close()


def purchase_fertilizer(user_id: int, fertilizer_id: int, quantity: int) -> dict:
    """Покупка удобрений. Возвращает dict: {ok, reason?, coins_left?, inventory_qty?}"""
    if quantity <= 0:
        return {"ok": False, "reason": "invalid_quantity"}
    dbs = SessionLocal()
    try:
        fert = dbs.query(Fertilizer).filter(Fertilizer.id == fertilizer_id).first()
        if not fert:
            return {"ok": False, "reason": "no_such_fertilizer"}
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        cost = int(fert.price_coins or 0) * int(quantity)
        if int(player.coins or 0) < cost:
            return {"ok": False, "reason": "not_enough_coins"}
        # списываем и увеличиваем инвентарь удобрений
        player.coins = int(player.coins or 0) - cost
        row = (
            dbs.query(FertilizerInventory)
            .filter(FertilizerInventory.player_id == user_id, FertilizerInventory.fertilizer_id == fertilizer_id)
            .with_for_update(read=False)
            .first()
        )
        if not row:
            row = FertilizerInventory(player_id=user_id, fertilizer_id=fertilizer_id, quantity=0)
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
        row.quantity = max(0, int(row.quantity or 0) + int(quantity))
        dbs.commit()
        return {"ok": True, "coins_left": int(player.coins), "inventory_qty": int(row.quantity)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def apply_fertilizer(user_id: int, bed_index: int, fertilizer_id: int) -> dict:
    """Применяет удобрение к грядке. Возвращает dict: {ok, reason?, bed_state?}
    Возможные reason: no_such_bed, not_growing, not_watered, no_such_fertilizer, no_fertilizer_in_inventory, max_fertilizers_reached
    Теперь поддерживает накопление нескольких удобрений на одной грядке (максимум 3).
    Требует, чтобы растение было полито хотя бы один раз (water_count > 0).
    """
    dbs = SessionLocal()
    try:
        fert = dbs.query(Fertilizer).filter(Fertilizer.id == fertilizer_id).first()
        if not fert:
            return {"ok": False, "reason": "no_such_fertilizer"}

        bed = (
            dbs.query(PlantationBed)
            .options(
                joinedload(PlantationBed.fertilizer), 
                joinedload(PlantationBed.seed_type),
                joinedload(PlantationBed.active_fertilizers).joinedload(BedFertilizer.fertilizer)
            )
            .filter(PlantationBed.owner_id == user_id, PlantationBed.bed_index == bed_index)
            .with_for_update(read=False)
            .first()
        )
        if not bed:
            return {"ok": False, "reason": "no_such_bed"}
        if bed.state != 'growing' or not bed.seed_type:
            # автообновление готовности, если уже созрело
            _update_bed_ready_if_due(dbs, bed)
            return {"ok": False, "reason": "not_growing", "bed_state": bed.state}

        # Проверяем, что растение было полито хотя бы раз
        if int(bed.water_count or 0) <= 0:
            return {"ok": False, "reason": "not_watered", "bed_state": bed.state}

        # Проверяем количество активных удобрений (максимум 3)
        # Используем check_duration=True, чтобы считать только удобрения с активным временем действия
        now_ts = int(time.time())
        fert_status = get_fertilizer_status(bed, check_duration=True)
        active_count = len(fert_status.get('fertilizers_info', []))
        
        if active_count >= 3:
            return {"ok": False, "reason": "max_fertilizers_reached", "bed_state": bed.state}

        inv = (
            dbs.query(FertilizerInventory)
            .filter(FertilizerInventory.player_id == user_id, FertilizerInventory.fertilizer_id == fertilizer_id)
            .with_for_update(read=False)
            .first()
        )
        if not inv or int(inv.quantity or 0) <= 0:
            return {"ok": False, "reason": "no_fertilizer_in_inventory"}

        # Применяем: добавляем в список активных удобрений
        bed_fert = BedFertilizer(
            bed_id=bed.id,
            fertilizer_id=fertilizer_id,
            applied_at=now_ts
        )
        dbs.add(bed_fert)
        
        # Также обновляем старые поля для обратной совместимости
        bed.fertilizer_id = fertilizer_id
        bed.fertilizer_applied_at = now_ts
        
        inv.quantity = int(inv.quantity or 0) - 1
        dbs.commit()
        return {"ok": True, "bed_state": bed.state}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def ensure_player_beds(user_id: int, total_beds: int = 1) -> list[PlantationBed]:
    """Гарантирует наличие total_beds грядок у игрока и возвращает их список."""
    dbs = SessionLocal()
    try:
        beds = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == user_id)
            .order_by(PlantationBed.bed_index.asc())
            .all()
        )
        if len(beds) >= total_beds:
            return list(beds)
        # создаём недостающие грядки
        existing_indices = {b.bed_index for b in beds}
        created = []
        for i in range(1, total_beds + 1):
            if i not in existing_indices:
                b = PlantationBed(owner_id=user_id, bed_index=i, state='empty', seed_type_id=None, planted_at=0, last_watered_at=0, water_count=0)
                dbs.add(b)
                created.append(b)
        dbs.commit()
        if created:
            for b in created:
                dbs.refresh(b)
        beds = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == user_id)
            .order_by(PlantationBed.bed_index.asc())
            .all()
        )
        return list(beds)
    finally:
        dbs.close()


def get_player_beds(user_id: int) -> list[PlantationBed]:
    dbs = SessionLocal()
    try:
        beds = list(
            dbs.query(PlantationBed)
            .options(
                joinedload(PlantationBed.seed_type), 
                joinedload(PlantationBed.fertilizer),
                joinedload(PlantationBed.active_fertilizers).joinedload(BedFertilizer.fertilizer)
            )
            .filter(PlantationBed.owner_id == user_id)
            .order_by(PlantationBed.bed_index.asc())
            .all()
        )
        
        # Обновляем состояние грядок (ленивая проверка)
        updated = False
        for bed in beds:
            if _update_bed_ready_if_due(dbs, bed):
                updated = True
        
        if updated:
            dbs.commit()
            # Refresh beds to ensure we return updated state
            for bed in beds:
                dbs.refresh(bed)
                
        return beds
    finally:
        dbs.close()


def get_fertilizer_status(bed: PlantationBed, check_duration: bool = True) -> dict:
    """Возвращает информацию о статусе удобрений на грядке.
    Returns: {active: bool, fertilizer_names: list, total_multiplier: float, fertilizers_info: list}
    Теперь поддерживает множественные удобрения с суммированием множителей.
    
    Args:
        bed: Грядка для проверки
        check_duration: Если True - учитывать только удобрения с активным временем действия (для проверки слотов).
                       Если False - учитывать ВСЕ примененные удобрения (для расчета множителя при сборе).
    """
    result = {
        'active': False,
        'fertilizer_names': [],
        'total_multiplier': 1.0,
        'fertilizers_info': []  # Список словарей: {name, multiplier, time_left, effect_type}
    }
    
    try:
        if not hasattr(bed, 'active_fertilizers'):
            return result
        
        now_ts = int(time.time())
        active_fertilizers = []
        total_bonus = 0.0  # Сумма бонусов (без базового 1.0)
        
        # Проходим по всем активным удобрениям
        for bed_fert in bed.active_fertilizers:
            if not bed_fert.fertilizer:
                continue
                
            fert = bed_fert.fertilizer
            f_dur = int(getattr(fert, 'duration_sec', 0) or 0)
            f_appl = int(getattr(bed_fert, 'applied_at', 0) or 0)
            
            if f_dur > 0 and f_appl > 0:
                time_left = max(0, f_dur - (now_ts - f_appl))
                
                # Если check_duration=True, проверяем время (для слотов)
                # Если check_duration=False, берем все удобрения (для множителя при harvest)
                if not check_duration or time_left > 0:
                    fert_name = getattr(fert, 'name', 'Удобрение')
                    effect = getattr(fert, 'effect', '') or ''
                    
                    # Определяем множитель для этого удобрения
                    multiplier = 1.0
                    effect_type = 'basic'
                    
                    if 'урожай++' in effect:
                        multiplier = 1.4
                        effect_type = 'mega_yield'
                    elif 'урожай' in effect:
                        multiplier = 1.25
                        effect_type = 'yield'
                    elif 'качество' in effect:
                        multiplier = 1.15
                        effect_type = 'quality'
                    elif 'всё' in effect:
                        multiplier = 1.3
                        effect_type = 'complex'
                    elif 'рост+кач' in effect:
                        multiplier = 1.35
                        effect_type = 'growth_quality'
                    elif 'время' in effect:
                        multiplier = 1.25
                        effect_type = 'time'
                    elif 'рост' in effect:
                        multiplier = 1.2
                        effect_type = 'growth'
                    elif 'питание' in effect:
                        multiplier = 1.3
                        effect_type = 'nutrition'
                    elif 'био' in effect:
                        multiplier = 1.28
                        effect_type = 'bio'
                    else:
                        multiplier = 1.15
                        effect_type = 'basic'
                    
                    # Добавляем бонус (без базового 1.0) к общей сумме
                    total_bonus += (multiplier - 1.0)
                    
                    active_fertilizers.append({
                        'name': fert_name,
                        'multiplier': multiplier,
                        'time_left': time_left,
                        'effect_type': effect_type
                    })
        
        if active_fertilizers:
            result['active'] = True
            result['fertilizer_names'] = [f['name'] for f in active_fertilizers]
            result['total_multiplier'] = 1.0 + total_bonus  # Базовый 1.0 + сумма бонусов
            result['fertilizers_info'] = active_fertilizers
                
    except Exception:
        pass
        
    return result


def get_actual_grow_time(bed: PlantationBed) -> int:
    """Возвращает фактическое время роста с учетом примененного удобрения.
    Если удобрение было применено, ускорение сохраняется до конца роста.
    """
    if not bed or not bed.seed_type:
        return 0
    
    base_grow_time = int(bed.seed_type.grow_time_sec or 0)
    
    # Если удобрение применено, рассчитываем ускоренное время
    if bed.fertilizer_id and bed.fertilizer:
        effect = getattr(bed.fertilizer, 'effect', '') or ''
        # Удобрения на ускорение роста
        if 'время' in effect:  # СуперРост (-время)
            return int(base_grow_time * 0.4)  # Сокращение на 60%
        elif 'рост+кач' in effect:  # Стимул-Х
            return int(base_grow_time * 0.7)  # Сокращение на 30%
        elif 'всё' in effect:  # Комплексное
            return int(base_grow_time * 0.7)  # Сокращение на 30%
        elif 'рост' in effect:  # Азотное (+рост)
            return int(base_grow_time * 0.75)  # Сокращение на 25%
    
    return base_grow_time


def _update_bed_ready_if_due(dbs, bed: PlantationBed) -> bool:
    """Внутренняя: переводит грядку в состояние 'ready', если прошло время роста. Возвращает True, если обновлено.
    Учитывает эффекты удобрений на скорость роста.
    ВАЖНО: Если удобрение было применено, ускорение сохраняется до конца роста (даже если duration истек).
    """
    try:
        if bed and bed.state == 'growing' and bed.seed_type and bed.planted_at:
            now_ts = int(time.time())
            actual_grow_time = get_actual_grow_time(bed)
            
            if now_ts - int(bed.planted_at) >= actual_grow_time:
                bed.state = 'ready'
                dbs.commit()
                return True
        return False
    except Exception:
        return False


def plant_seed(user_id: int, bed_index: int, seed_type_id: int) -> dict:
    """Сажает семя в указанную грядку.
    Возвращает dict: {ok, reason?, bed_state?}
    Возможные reason: no_such_bed, bed_not_empty, no_such_seed, no_seeds
    """
    dbs = SessionLocal()
    try:
        bed = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == user_id, PlantationBed.bed_index == bed_index)
            .with_for_update(read=False)
            .first()
        )
        if not bed:
            return {"ok": False, "reason": "no_such_bed"}
        if bed.state not in ('empty', 'withered'):
            return {"ok": False, "reason": "bed_not_empty"}
        seed_type = dbs.query(SeedType).filter(SeedType.id == seed_type_id).first()
        if not seed_type:
            return {"ok": False, "reason": "no_such_seed"}
        inv = (
            dbs.query(SeedInventory)
            .filter(SeedInventory.player_id == user_id, SeedInventory.seed_type_id == seed_type_id)
            .with_for_update(read=False)
            .first()
        )
        if not inv or int(inv.quantity or 0) <= 0:
            return {"ok": False, "reason": "no_seeds"}
        # Посадка
        now_ts = int(time.time())
        bed.state = 'growing'
        bed.seed_type_id = seed_type_id
        bed.planted_at = now_ts
        bed.last_watered_at = 0
        bed.water_count = 0
        inv.quantity = int(inv.quantity or 0) - 1
        water_interval = int(seed_type.water_interval_sec or 0)
        dbs.commit()
        return {"ok": True, "bed_state": bed.state, "water_interval_sec": water_interval}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def water_bed(user_id: int, bed_index: int) -> dict:
    """Полив грядки. Возвращает dict: {ok, reason?, next_water_in?, bed_state?}
    Возможные reason: no_such_bed, not_growing, too_early_to_water
    Если грядка дозрела, состояние обновляется на 'ready'.
    """
    dbs = SessionLocal()
    try:
        bed = (
            dbs.query(PlantationBed)
            .options(joinedload(PlantationBed.seed_type))
            .filter(PlantationBed.owner_id == user_id, PlantationBed.bed_index == bed_index)
            .with_for_update(read=False)
            .first()
        )
        if not bed:
            return {"ok": False, "reason": "no_such_bed"}
        if bed.state != 'growing' or not bed.seed_type:
            # Попробуем автообновить, если уже готово
            _update_bed_ready_if_due(dbs, bed)
            return {"ok": False, "reason": "not_growing", "bed_state": bed.state}
        # Проверка интервала полива
        now_ts = int(time.time())
        last = int(bed.last_watered_at or 0)
        interval = int(bed.seed_type.water_interval_sec or 0)
        if last and interval and (now_ts - last) < interval:
            return {"ok": False, "reason": "too_early_to_water", "next_water_in": interval - (now_ts - last), "bed_state": bed.state}
        bed.last_watered_at = now_ts
        bed.water_count = int(bed.water_count or 0) + 1
        # Обновим готовность, если срок истёк
        _update_bed_ready_if_due(dbs, bed)
        dbs.commit()
        return {"ok": True, "bed_state": bed.state, "water_interval_sec": interval}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def harvest_bed(user_id: int, bed_index: int) -> dict:
    """Сбор урожая. Возвращает dict: {ok, reason?, yield?, drink_id?, items_added?}
    Возможные reason: no_such_bed, not_ready, no_seed
    Урожай добавляется в инвентарь как энергетик с редкостью 'Basic'.
    """
    dbs = SessionLocal()
    try:
        bed = (
            dbs.query(PlantationBed)
            .options(
                joinedload(PlantationBed.seed_type).joinedload(SeedType.drink),
                joinedload(PlantationBed.active_fertilizers).joinedload(BedFertilizer.fertilizer)
            )
            .filter(PlantationBed.owner_id == user_id, PlantationBed.bed_index == bed_index)
            .with_for_update(read=False)
            .first()
        )
        if not bed:
            return {"ok": False, "reason": "no_such_bed"}
        if not bed.seed_type:
            return {"ok": False, "reason": "no_seed"}
        # Обновим состояние, если дозрело
        _update_bed_ready_if_due(dbs, bed)
        if bed.state != 'ready':
            return {"ok": False, "reason": "not_ready", "bed_state": bed.state}
        st = bed.seed_type
        # Рассчитываем урожай с учётом полива/удобрений/негативных статусов
        ymin = int(st.yield_min or 0)
        ymax = int(st.yield_max or 0)
        if ymax < ymin:
            ymax = ymin
        base_amount = random.randint(ymin, ymax) if ymax > 0 else 0

        # Множители урожайности
        now_ts = int(time.time())
        yield_mult = 1.0
        # Бонус за полив: до +10% (по 2% за полив, максимум 5)
        wc = int(bed.water_count or 0)
        if wc > 0:
            yield_mult *= (1.0 + min(wc, 5) * 0.02)
        # Бонус от удобрений - теперь суммируем множители всех активных удобрений
        fert_applied = False
        fertilizer_names = []
        fert_effect_types = []
        fert_multiplier = 1.0
        try:
            # Используем check_duration=False, чтобы учесть ВСЕ примененные удобрения
            # независимо от истечения их времени действия (множитель сохраняется до сбора)
            fert_status = get_fertilizer_status(bed, check_duration=False)
            if fert_status['active']:
                fert_applied = True
                fertilizer_names = fert_status['fertilizer_names']
                fert_multiplier = fert_status['total_multiplier']
                # Собираем типы эффектов для определения влияния на редкость
                fert_effect_types = [f['effect_type'] for f in fert_status['fertilizers_info']]
        except Exception:
            fert_applied = False
        
        if fert_applied:
            yield_mult *= fert_multiplier
        # Штрафы от негативных статусов
        try:
            se = (bed.status_effect or '').strip().lower()
        except Exception:
            se = ''
        if se:
            penalty_map = {
                'weeds': 0.9,
                'pests': 0.8,
                'drought': 0.85,
            }
            yield_mult *= penalty_map.get(se, 0.95)

        amount = max(0, int(round(base_amount * yield_mult)))
        if base_amount > 0 and amount == 0:
            amount = 1

        # Добавляем предметы в инвентарь игрока с редкостью на основе скорректированных весов
        items_added = 0
        rarity_counts = {}
        if amount > 0 and st.drink_id:
            try:
                # Базовые веса редкостей
                rarity_weights = {k: float(v) for k, v in RARITIES.items()}
                # Смещения весов от удобрений и полива - улучшенные эффекты
                if fert_applied and fert_effect_types:
                    # Применяем эффекты от каждого активного удобрения
                    for fert_effect_type in fert_effect_types:
                        # Различные эффекты в зависимости от типа удобрения
                        if fert_effect_type in ('quality', 'complex', 'growth_quality'):
                            # Усиливаем высокие редкости, снижаем Basic
                            if 'Basic' in rarity_weights:
                                rarity_weights['Basic'] *= 0.5  # Сильнее снижаем Basic
                            if 'Medium' in rarity_weights:
                                rarity_weights['Medium'] *= 2.5  # Усиливаем Medium
                            if 'Elite' in rarity_weights:
                                rarity_weights['Elite'] *= 4.0  # Значительно усиливаем Elite
                            if 'Absolute' in rarity_weights:
                                rarity_weights['Absolute'] *= 6.0  # Сильно усиливаем Absolute
                            if 'Majestic' in rarity_weights:
                                rarity_weights['Majestic'] *= 8.0  # Максимально усиливаем Majestic
                        elif fert_effect_type in ('yield', 'mega_yield', 'time'):
                            # Средний эффект на редкость
                            if 'Basic' in rarity_weights:
                                rarity_weights['Basic'] *= 0.7
                            if 'Medium' in rarity_weights:
                                rarity_weights['Medium'] *= 1.8
                            if 'Elite' in rarity_weights:
                                rarity_weights['Elite'] *= 2.5
                            if 'Absolute' in rarity_weights:
                                rarity_weights['Absolute'] *= 3.0
                            if 'Majestic' in rarity_weights:
                                rarity_weights['Majestic'] *= 4.0
                        else:
                            # Базовые удобрения - умеренный эффект
                            if 'Basic' in rarity_weights:
                                rarity_weights['Basic'] *= 0.8
                            if 'Medium' in rarity_weights:
                                rarity_weights['Medium'] *= 1.5
                            if 'Elite' in rarity_weights:
                                rarity_weights['Elite'] *= 2.0
                if wc > 0:
                    # Полив чуть усиливает Medium/Elite
                    if 'Medium' in rarity_weights:
                        rarity_weights['Medium'] *= (1.0 + min(wc, 5) * 0.03)
                    if 'Elite' in rarity_weights:
                        rarity_weights['Elite'] *= (1.0 + min(wc, 5) * 0.02)
                if se:
                    # Негативные статусы ухудшают качество
                    if 'Basic' in rarity_weights:
                        rarity_weights['Basic'] *= 1.15
                    for rk in ('Medium', 'Elite', 'Absolute', 'Majestic'):
                        if rk in rarity_weights:
                            rarity_weights[rk] *= 0.85

                # Страховка: если все веса некорректны — откат к Basic
                total_w = sum(w for w in rarity_weights.values() if w > 0)
                if not total_w:
                    rarity_weights = {'Basic': 1.0}

                # Выбираем редкость для каждого предмета
                rarities = list(rarity_weights.keys())
                weights = list(rarity_weights.values())
                chosen = random.choices(rarities, weights=weights, k=amount)
                for rrt in chosen:
                    try:
                        add_drink_to_inventory(user_id, st.drink_id, rrt)
                        items_added += 1
                        rarity_counts[rrt] = int(rarity_counts.get(rrt, 0) or 0) + 1
                    except Exception:
                        pass
            except Exception:
                # Фоллбек: добавляем все как Basic
                for _ in range(amount):
                    try:
                        add_drink_to_inventory(user_id, st.drink_id, 'Basic')
                        items_added += 1
                        rarity_counts['Basic'] = int(rarity_counts.get('Basic', 0) or 0) + 1
                    except Exception:
                        pass
        # Сбрасываем грядку
        bed.state = 'empty'
        bed.seed_type_id = None
        bed.planted_at = 0
        bed.last_watered_at = 0
        bed.water_count = 0
        # Сбрасываем новые поля удобрений и статуса
        try:
            bed.fertilizer_id = None
        except Exception:
            pass
        try:
            bed.fertilizer_applied_at = 0
        except Exception:
            pass
        try:
            bed.status_effect = None
        except Exception:
            pass
        # Удаляем все активные удобрения (благодаря cascade='all, delete-orphan' они удалятся автоматически)
        try:
            if hasattr(bed, 'active_fertilizers'):
                for bf in list(bed.active_fertilizers):
                    dbs.delete(bf)
        except Exception:
            pass
        # Получаем название напитка для уведомлений
        drink_name = "Неизвестный"
        if st.drink and st.drink.name:
            drink_name = st.drink.name

        dbs.commit()
        return {
            "ok": True,
            "yield": amount,
            "drink_id": st.drink_id,
            "drink_name": drink_name,
            "items_added": items_added,
            "rarity_counts": rarity_counts,
            "effects": {
                "fertilizers": fertilizer_names,  # Keep for backward compatibility if needed
                "fertilizer_names": fertilizer_names,
                "fertilizer_active": fert_applied,
                "yield_multiplier": yield_multiplier,  # Note: variable name in code is yield_mult
                "status_effect": se,
                "water_count": wc,
            },
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def get_player_selyuki(user_id: int) -> list[Selyuk]:
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id))
            .order_by(Selyuk.id.asc())
            .all()
        )
    finally:
        dbs.close()


def get_selyuk_by_type(user_id: int, selyuk_type: str) -> Selyuk | None:
    dbs = SessionLocal()
    try:
        return (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == str(selyuk_type))
            .first()
        )
    finally:
        dbs.close()


def buy_farmer_selyuk(user_id: int, price: int = 50000) -> dict:
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == int(user_id)).with_for_update(read=False).first()
        if not player:
            return {"ok": False, "reason": "no_player"}

        existing = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == 'farmer')
            .with_for_update(read=False)
            .first()
        )
        if existing:
            return {"ok": False, "reason": "already_have_farmer"}

        coins = int(getattr(player, 'coins', 0) or 0)
        price_i = int(price or 0)
        if coins < price_i:
            return {"ok": False, "reason": "not_enough_coins", "need": price_i, "have": coins}

        player.coins = coins - price_i
        now_ts = int(time.time())
        farmer = Selyuk(
            owner_id=int(user_id),
            type='farmer',
            level=1,
            balance_septims=0,
            is_enabled=True,
            created_at=now_ts,
            updated_at=now_ts,
        )
        dbs.add(farmer)
        dbs.commit()
        dbs.refresh(farmer)
        return {"ok": True, "selyuk_id": int(farmer.id), "coins_left": int(player.coins or 0)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def topup_selyuk_balance_from_player(user_id: int, selyuk_type: str, amount: int) -> dict:
    dbs = SessionLocal()
    try:
        amt = int(amount or 0)
        if amt <= 0:
            return {"ok": False, "reason": "invalid_amount"}

        player = dbs.query(Player).filter(Player.user_id == int(user_id)).with_for_update(read=False).first()
        if not player:
            return {"ok": False, "reason": "no_player"}

        selyuk = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == str(selyuk_type))
            .with_for_update(read=False)
            .first()
        )
        if not selyuk:
            return {"ok": False, "reason": "no_selyuk"}

        coins = int(getattr(player, 'coins', 0) or 0)
        if coins < amt:
            return {"ok": False, "reason": "not_enough_coins", "need": amt, "have": coins}

        player.coins = coins - amt
        selyuk.balance_septims = int(getattr(selyuk, 'balance_septims', 0) or 0) + amt
        try:
            selyuk.updated_at = int(time.time())
        except Exception:
            pass
        dbs.commit()
        return {
            "ok": True,
            "new_balance": int(selyuk.balance_septims or 0),
            "coins_left": int(player.coins or 0),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def try_farmer_autowater(user_id: int, bed_index: int) -> dict:
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == int(user_id)).first()
        if not player:
            return {"ok": False, "reason": "no_player"}

        if not bool(getattr(player, 'remind_plantation', False)):
            return {"ok": False, "reason": "remind_disabled"}

        selyuk = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == 'farmer')
            .with_for_update(read=False)
            .first()
        )
        if not selyuk:
            return {"ok": False, "reason": "no_selyuk"}

        if not bool(getattr(selyuk, 'is_enabled', False)):
            return {"ok": False, "reason": "selyuk_disabled"}

        # Определяем стоимость полива в зависимости от уровня
        level = int(getattr(selyuk, 'level', 1) or 1)
        cost = 45 if level >= 2 else 50

        balance = int(getattr(selyuk, 'balance_septims', 0) or 0)
        if balance < cost:
            return {"ok": False, "reason": "not_enough_balance"}

        bed = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == int(user_id), PlantationBed.bed_index == int(bed_index))
            .with_for_update(read=False)
            .first()
        )
        if not bed:
            return {"ok": False, "reason": "no_bed"}
        
        # Проверяем, нужно ли поливать
        seed_type = bed.seed_type
        if not seed_type:
             return {"ok": False, "reason": "no_seed"}

        # Логика проверки времени полива (аналогично water_bed, но упрощенно)
        # Если state != growing -> не поливаем
        if str(getattr(bed, 'state', '')) != 'growing':
             return {"ok": False, "reason": "not_growing"}
             
        now_ts = int(time.time())
        water_interval = int(seed_type.water_interval_sec or 0)
        last_water = int(bed.last_watered_at or 0)
        planted_at = int(bed.planted_at or 0)
        
        # Если ни разу не поливали (last_water == 0), разрешаем полив сразу
        if last_water > 0:
             reference_time = last_water
             if now_ts - reference_time < water_interval:
                  return {"ok": False, "reason": "too_early"}
        # else: last_water == 0 -> allow immediate water

        bed.last_watered_at = now_ts
        bed.water_count = int(bed.water_count or 0) + 1
        _update_bed_ready_if_due(dbs, bed)

        selyuk.balance_septims = balance - cost
        try:
            selyuk.updated_at = now_ts
        except Exception:
            pass

        dbs.commit()
        return {"ok": True, "bed_state": bed.state, "water_interval_sec": water_interval, "cost": cost}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def upgrade_selyuk_farmer(user_id: int) -> dict:
    """Повышает уровень Селюка Фермера до 2 за 200 000 монет."""
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == int(user_id)).with_for_update(read=False).first()
        if not player:
            return {"ok": False, "reason": "no_player"}

        selyuk = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == 'farmer')
            .with_for_update(read=False)
            .first()
        )
        if not selyuk:
            return {"ok": False, "reason": "no_selyuk"}
        
        current_level = int(getattr(selyuk, 'level', 1) or 1)
        
        if current_level == 1:
            # Upgrade to Level 2
            cost = 200000
            if int(player.coins or 0) < cost:
                return {"ok": False, "reason": "not_enough_coins", "need": cost, "have": int(player.coins or 0)}
                
            player.coins = int(player.coins or 0) - cost
            selyuk.level = 2
            new_lvl = 2
        elif current_level == 2:
            # Upgrade to Level 3
            cost_coins = 150000
            cost_fragments = 15
            
            if int(player.coins or 0) < cost_coins:
                return {"ok": False, "reason": "not_enough_coins", "need": cost_coins, "have": int(player.coins or 0)}
            
            fragments = int(getattr(player, 'selyuk_fragments', 0) or 0)
            if fragments < cost_fragments:
                return {"ok": False, "reason": "not_enough_fragments", "need": cost_fragments, "have": fragments}
                
            player.coins = int(player.coins or 0) - cost_coins
            player.selyuk_fragments = fragments - cost_fragments
            selyuk.level = 3
            new_lvl = 3
        else:
            return {"ok": False, "reason": "max_level"}

        try:
            selyuk.updated_at = int(time.time())
        except Exception:
            pass
            
        dbs.commit()
        return {"ok": True, "new_level": new_lvl, "coins_left": int(player.coins)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def try_farmer_auto_harvest(user_id: int) -> dict:
    """
    Автоматический сбор урожая для Селюка Фермера 2 уровня.
    Проверяет все грядки, если готовы - собирает.
    Возвращает список собранных предметов.
    """
    dbs = SessionLocal()
    try:
        # 1. Проверяем селюка
        selyuk = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == 'farmer')
            .first()
        )
        if not selyuk:
            return {"ok": False, "reason": "no_selyuk"}
            
        level = int(getattr(selyuk, 'level', 1) or 1)
        if level < 2:
            return {"ok": False, "reason": "low_level"}
            
        if not bool(getattr(selyuk, 'is_enabled', False)):
            return {"ok": False, "reason": "disabled"}
    finally:
        dbs.close()
        
    # Вызываем сбор для каждой готовой грядки отдельными транзакциями
    harvested_items = []
    
    # Helper для проверки готовности без транзакции (или с короткой)
    ready_indices = []
    dbs2 = SessionLocal()
    try:
        beds = dbs2.query(PlantationBed).filter(PlantationBed.owner_id == int(user_id)).all()
        for bed in beds:
            # Обновляем статус если пришло время
            _update_bed_ready_if_due(dbs2, bed)
            if str(getattr(bed, 'state', '')) == 'ready':
                ready_indices.append(int(bed.bed_index))
    finally:
        dbs2.close()
        
    if not ready_indices:
        return {"ok": True, "harvested": []}
        
    for idx in ready_indices:
        res = harvest_bed(user_id, idx)
        if res.get('ok'):
            harvested_items.append({
                'bed_index': idx,
                'drink_id': res.get('drink_id'),
                'drink_name': res.get('drink_name'),
                'yield': res.get('yield'),
                'items_added': res.get('items_added')
            })
            
    return {"ok": True, "harvested": harvested_items}


def try_farmer_auto_plant(user_id: int) -> dict:
    """
    Автоматическая посадка семян для Селюка Фермера 3 уровня.
    Ищет пустые грядки и сажает первые попавшиеся семена из инвентаря.
    """
    dbs = SessionLocal()
    try:
        # 1. Проверяем селюка
        selyuk = (
            dbs.query(Selyuk)
            .filter(Selyuk.owner_id == int(user_id), Selyuk.type == 'farmer')
            .first()
        )
        if not selyuk:
            return {"ok": False, "reason": "no_selyuk"}
            
        level = int(getattr(selyuk, 'level', 1) or 1)
        if level < 3:
            return {"ok": False, "reason": "low_level"}
            
        if not bool(getattr(selyuk, 'is_enabled', False)):
            return {"ok": False, "reason": "disabled"}
            
        # 2. Ищем пустые грядки
        empty_beds = (
            dbs.query(PlantationBed)
            .filter(PlantationBed.owner_id == int(user_id), PlantationBed.state == 'empty')
            .all()
        )
        
        if not empty_beds:
            return {"ok": True, "planted": [], "reason": "no_empty_beds"}
            
        planted_items = []
        
        # 3. Ищем семена в инвентаре (SeedInventory)
        inventory_items = (
            dbs.query(SeedInventory)
            .filter(SeedInventory.player_id == int(user_id), SeedInventory.quantity > 0)
            .order_by(SeedInventory.quantity.desc())
            .all()
        )
        
        if not inventory_items:
             return {"ok": True, "planted": [], "reason": "no_seeds"}
             
        # Преобразуем в список для удобства работы
        current_seed_idx = 0
        
        for bed in empty_beds:
            if current_seed_idx >= len(inventory_items):
                break # Кончились типы семян
                
            seed_item = inventory_items[current_seed_idx]
            
            # Списываем семя
            seed_item.quantity -= 1
            if seed_item.quantity <= 0:
                # Если 0, можно удалить или оставить 0. Обычно удаляем или оставляем.
                # В SeedInventory часто оставляют 0 или удаляют. Проверим логику бота.
                # Для надежности просто уменьшаем. Если станет 0, потом почистится или будет игнорироваться.
                pass
                
            if seed_item.quantity == 0:
                 current_seed_idx += 1
            
            # Обновляем грядку
            bed.state = 'growing'
            bed.seed_type_id = seed_item.seed_type_id
            bed.planted_at = int(time.time())
            bed.last_watered_at = 0
            bed.water_count = 0
            
            planted_items.append({
                'bed_index': bed.bed_index,
                'seed_name': seed_item.seed_type.name if seed_item.seed_type else 'Unknown'
            })
            
        dbs.commit()
        return {"ok": True, "planted": planted_items}
        
    except Exception as e:
        try:
            dbs.rollback()
        except Exception:
            pass
        print(f"Error in try_farmer_auto_plant: {e}")
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def get_players_with_auto_search_enabled() -> list[Player]:
    """
    Возвращает список игроков, у которых включён автопоиск (auto_search_enabled = True).
    Используется для восстановления задач JobQueue после рестарта бота.
    """
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(Player)
            .filter(Player.auto_search_enabled == True)  # noqa: E712 - сравнение с True корректно для SQLAlchemy
            .all()
        )
    finally:
        dbs.close()

def get_auto_search_daily_limit(user_id: int) -> int:
    """
    Возвращает дневной лимит автопоиска для пользователя.
    Базовый лимит + VIP+ удвоение + активный буст (если не истёк).
    """
    from constants import AUTO_SEARCH_DAILY_LIMIT
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return int(AUTO_SEARCH_DAILY_LIMIT)
        
        base_limit = int(AUTO_SEARCH_DAILY_LIMIT)
        
        # Проверяем VIP+ статус (удваивает базовый лимит)
        if is_vip_plus(user_id):
            base_limit *= 2
        
        boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
        boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
        
        # Проверяем, активен ли буст
        import time
        if boost_until > int(time.time()):
            return base_limit + boost_count
        else:
            return base_limit
    finally:
        dbs.close()

def add_auto_search_boost(user_id: int, boost_count: int, days: int) -> bool:
    """
    Добавляет буст автопоиска пользователю.
    Если буст уже активен, продлевает его и добавляет к количеству.
    """
    import time
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        now_ts = int(time.time())
        current_boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
        current_boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
        
        # Если буст ещё активен, продлеваем от текущего времени окончания
        if current_boost_until > now_ts:
            start_time = current_boost_until
            new_boost_count = current_boost_count + boost_count
        else:
            start_time = now_ts
            new_boost_count = boost_count
        
        new_boost_until = start_time + (days * 24 * 60 * 60)
        
        player.auto_search_boost_count = new_boost_count
        player.auto_search_boost_until = new_boost_until
        dbs.commit()
        
        # Добавляем запись в историю
        try:
            add_boost_history_record(
                user_id=user_id,
                username=player.username,
                action='granted',
                boost_count=boost_count,
                boost_days=days,
                details=f"Новый лимит: {get_auto_search_daily_limit(user_id)}"
            )
        except Exception:
            # Не прерываем основную операцию из-за ошибки с историей
            pass
            
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

def add_auto_search_boost_to_all(boost_count: int, days: int) -> int:
    """
    Добавляет буст автопоиска всем пользователям.
    Возвращает количество обновлённых пользователей.
    """
    import time
    dbs = SessionLocal()
    try:
        now_ts = int(time.time())
        players = dbs.query(Player).all()
        updated_count = 0
        
        for player in players:
            current_boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
            current_boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
            
            # Если буст ещё активен, продлеваем от текущего времени окончания
            if current_boost_until > now_ts:
                start_time = current_boost_until
                new_boost_count = current_boost_count + boost_count
            else:
                start_time = now_ts
                new_boost_count = boost_count
            
            new_boost_until = start_time + (days * 24 * 60 * 60)
            
            player.auto_search_boost_count = new_boost_count
            player.auto_search_boost_until = new_boost_until
            updated_count += 1
        
        dbs.commit()
        return updated_count
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return 0
    finally:
        dbs.close()

# --- TG Premium helpers ---

def get_tg_premium_until(user_id: int) -> int:
    """Возвращает Unix-время истечения TG Premium (или 0)."""
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        return int(getattr(player, 'tg_premium_until', 0) or 0) if player else 0
    finally:
        dbs.close()

# --- Универсальные функции управления складом бонусов ---

def get_bonus_stock(kind: str) -> int:
    """Возвращает текущий склад для указанного вида бонуса."""
    dbs = SessionLocal()
    try:
        row = dbs.query(BonusStock).filter(BonusStock.kind == str(kind)).first()
        if row is not None:
            return int(row.stock or 0)
        # Fallback для обратной совместимости: если запрошен tg_premium — читаем старую таблицу
        if str(kind) == 'tg_premium':
            legacy = dbs.query(TgPremiumStock).order_by(TgPremiumStock.id.asc()).first()
            return int(legacy.stock) if legacy else 0
        return 0
    finally:
        dbs.close()

def add_bonus_stock(kind: str, delta: int) -> int:
    """Увеличивает/уменьшает склад указанного бонуса на delta. Возвращает новое значение."""
    dbs = SessionLocal()
    try:
        row = dbs.query(BonusStock).filter(BonusStock.kind == str(kind)).with_for_update(read=False).first()
        if not row:
            row = BonusStock(kind=str(kind), stock=0)
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
        row.stock = max(0, int(row.stock or 0) + int(delta))
        dbs.commit()
        return int(row.stock)
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return get_bonus_stock(kind)
    finally:
        dbs.close()

def set_bonus_stock(kind: str, value: int) -> int:
    """Устанавливает склад указанного бонуса в значение value (не ниже 0). Возвращает новое значение."""
    dbs = SessionLocal()
    try:
        row = dbs.query(BonusStock).filter(BonusStock.kind == str(kind)).with_for_update(read=False).first()
        if not row:
            row = BonusStock(kind=str(kind), stock=0)
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
        row.stock = max(0, int(value))
        dbs.commit()
        return int(row.stock)
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return get_bonus_stock(kind)
    finally:
        dbs.close()

def purchase_generic_bonus(user_id: int, cost_coins: int, kind: str, extra: str | None = None) -> dict:
    """
    Универсальная покупка бонуса без срока действия и без склада.
    Списывает монеты и создаёт чек в таблице purchase_receipts с указанным kind.
    Возвращает dict: {ok: bool, reason?: str, coins_left?: int, receipt_id?: int}
    Возможные reason: 'not_enough_coins', 'exception'
    """
    dbs = SessionLocal()
    try:
        # Блокируем запись игрока
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        current_coins = int(player.coins or 0)
        if current_coins < int(cost_coins):
            return {"ok": False, "reason": "not_enough_coins"}

        player.coins = current_coins - int(cost_coins)

        # Создаём чек
        receipt = PurchaseReceipt(
            user_id=user_id,
            kind=str(kind),
            amount_coins=int(cost_coins),
            duration_seconds=0,
            purchased_at=int(time.time()),
            valid_until=0,
            status='completed',
            extra=extra,
        )
        dbs.add(receipt)

        dbs.commit()
        return {
            "ok": True,
            "coins_left": int(player.coins),
            "receipt_id": int(getattr(receipt, 'id', 0) or 0),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def purchase_bonus_with_stock(
    user_id: int,
    kind: str,
    cost_coins: int,
    duration_seconds: int = 0,
    extra: str | None = None,
) -> dict:
    """
    Универсальная покупка бонуса со складом BonusStock(kind).
    - Проверяет и уменьшает склад (на 1).
    - Списывает монеты у игрока.
    - Создает чек в purchase_receipts с valid_until (если duration_seconds > 0).

    Важно: не изменяет спец-поля игрока (например, tg_premium_until) — для таких случаев
    используйте специализированные функции (как purchase_tg_premium).

    Возвращает dict: {ok: bool, reason?: str, coins_left?: int, receipt_id?: int, valid_until?: int}
    Возможные reason: 'out_of_stock', 'not_enough_coins', 'exception'
    """
    dbs = SessionLocal()
    try:
        # Блокируем игрока
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        # Блокируем склад по виду бонуса
        stock_row = (
            dbs.query(BonusStock)
            .filter(BonusStock.kind == str(kind))
            .with_for_update(read=False)
            .first()
        )
        if not stock_row:
            # Создаём запись склада по требованию
            stock_row = BonusStock(kind=str(kind), stock=0)
            dbs.add(stock_row)
            dbs.commit()
            dbs.refresh(stock_row)

        if int(stock_row.stock or 0) <= 0:
            return {"ok": False, "reason": "out_of_stock"}

        current_coins = int(player.coins or 0)
        if current_coins < int(cost_coins):
            return {"ok": False, "reason": "not_enough_coins"}

        # Расчёт срока действия (если есть)
        now_ts = int(time.time())
        valid_until = now_ts + int(duration_seconds) if int(duration_seconds) > 0 else 0

        # Применяем изменения
        player.coins = current_coins - int(cost_coins)
        stock_row.stock = max(0, int(stock_row.stock or 0) - 1)

        # Создаём чек
        receipt = PurchaseReceipt(
            user_id=user_id,
            kind=str(kind),
            amount_coins=int(cost_coins),
            duration_seconds=int(duration_seconds or 0),
            purchased_at=now_ts,
            valid_until=int(valid_until),
            status='completed',
            extra=extra,
        )
        dbs.add(receipt)

        dbs.commit()
        return {
            "ok": True,
            "coins_left": int(player.coins),
            "receipt_id": int(getattr(receipt, 'id', 0) or 0),
            "valid_until": int(valid_until),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def get_tg_premium_stock() -> int:
    """Возвращает текущий склад TG Premium (шт.). Использует универсальный склад."""
    return get_bonus_stock('tg_premium')

def add_tg_premium_stock(delta: int) -> int:
    """Увеличивает склад TG Premium на delta (может быть отрицательным)."""
    return add_bonus_stock('tg_premium', delta)

def set_tg_premium_stock(value: int) -> int:
    """Устанавливает склад TG Premium (не ниже 0)."""
    return set_bonus_stock('tg_premium', value)

def purchase_tg_premium(user_id: int, cost_coins: int, duration_seconds: int) -> dict:
    """
    Списывает монеты, уменьшает универсальный склад бонуса 'tg_premium' и устанавливает/продлевает TG Premium пользователю.
    Возвращает dict: {ok: bool, reason?: str, tg_premium_until?: int, coins_left?: int, receipt_id?: int}
    Возможные reason: 'not_enough_coins', 'out_of_stock', 'exception'
    """
    dbs = SessionLocal()
    try:
        # Блокируем запись игрока и склад TG Premium
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        stock_row = (
            dbs.query(BonusStock)
            .filter(BonusStock.kind == 'tg_premium')
            .with_for_update(read=False)
            .first()
        )
        if not stock_row:
            # Попробуем подтянуть остаток из легаси-таблицы при первом обращении
            legacy = dbs.query(TgPremiumStock).order_by(TgPremiumStock.id.asc()).with_for_update(read=False).first()
            stock_init = int(legacy.stock) if legacy else 0
            stock_row = BonusStock(kind='tg_premium', stock=stock_init)
            dbs.add(stock_row)
            dbs.commit()
            dbs.refresh(stock_row)

        if int(stock_row.stock or 0) <= 0:
            return {"ok": False, "reason": "out_of_stock"}

        current_coins = int(player.coins or 0)
        if current_coins < int(cost_coins):
            return {"ok": False, "reason": "not_enough_coins"}

        now_ts = int(time.time())
        base_ts = int(getattr(player, 'tg_premium_until', 0) or 0)
        start_ts = base_ts if base_ts and base_ts > now_ts else now_ts
        new_until = start_ts + int(duration_seconds)

        player.coins = current_coins - int(cost_coins)
        try:
            player.tg_premium_until = new_until
        except Exception:
            pass

        stock_row.stock = max(0, int(stock_row.stock or 0) - 1)

        receipt = PurchaseReceipt(
            user_id=user_id,
            kind='tg_premium',
            amount_coins=int(cost_coins),
            duration_seconds=int(duration_seconds),
            purchased_at=int(time.time()),
            valid_until=int(new_until),
            status='completed',
        )
        dbs.add(receipt)

        dbs.commit()
        return {
            "ok": True,
            "tg_premium_until": new_until,
            "coins_left": int(player.coins),
            "receipt_id": int(getattr(receipt, 'id', 0) or 0),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def get_player_by_username(username: str) -> Player | None:
    """Возвращает игрока по username (поиск без учета регистра) или None."""
    db = SessionLocal()
    try:
        if not username:
            return None
        return db.query(Player).filter(func.lower(Player.username) == username.lower()).first()
    finally:
        db.close()

def increment_coins(user_id: int, amount: int) -> int | None:
    """Увеличивает баланс монет игрока на amount и возвращает новый баланс. Создаёт игрока при отсутствии."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)
        current = int(player.coins or 0)
        player.coins = current + int(amount)
        db.commit()
        return int(player.coins)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
    finally:
        db.close()

def decrement_coins(user_id: int, amount: int) -> dict:
    """Уменьшает баланс монет игрока на amount. Не позволяет балансу стать отрицательным.
    Возвращает dict: {ok: bool, reason?: str, new_balance?: int, insufficient?: bool}
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id), coins=0)
            db.add(player)
            db.commit()
            db.refresh(player)
        
        current = int(player.coins or 0)
        amount_to_remove = int(amount)
        
        if current < amount_to_remove:
            return {
                "ok": False,
                "reason": "insufficient_funds",
                "current_balance": current,
                "requested_amount": amount_to_remove,
                "insufficient": True
            }
        
        player.coins = current - amount_to_remove
        db.commit()
        return {
            "ok": True,
            "new_balance": int(player.coins),
            "removed_amount": amount_to_remove
        }
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "ok": False,
            "reason": "exception"
        }
    finally:
        db.close()

def get_all_drinks():
    """Возвращает список всех существующих энергетиков."""
    db = SessionLocal()
    try:
        return db.query(EnergyDrink).all()
    finally:
        db.close()


def get_plantation_drinks() -> list[EnergyDrink]:
    """Возвращает список всех плантационных энергетиков (is_plantation = True)."""
    db = SessionLocal()
    try:
        return (
            db.query(EnergyDrink)
            .filter(EnergyDrink.is_plantation == True)  # noqa: E712
            .order_by(EnergyDrink.id.asc())
            .all()
        )
    finally:
        db.close()

def get_drink_by_id(drink_id: int) -> EnergyDrink | None:
    """Возвращает энергетик по его ID или None, если не найден."""
    db = SessionLocal()
    try:
        return db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
    finally:
        db.close()

def add_drink_to_inventory(user_id, drink_id, rarity):
    """Добавляет энергетик в инвентарь игрока."""
    db = SessionLocal()
    try:
        item = db.query(InventoryItem).filter_by(player_id=user_id, drink_id=drink_id, rarity=rarity).first()
        if item:
            item.quantity += 1
        else:
            new_item = InventoryItem(player_id=user_id, drink_id=drink_id, rarity=rarity, quantity=1)
            db.add(new_item)
        db.commit()
    finally:
        db.close()


# --- Функции для системы "горячих" и "холодных" напитков ---

def record_drink_discovery(drink_id: int):
    """Записывает находку напитка для статистики."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        current_date = int(current_time // 86400)  # День с начала эпохи
        
        stats = db.query(DrinkDiscoveryStats).filter_by(drink_id=drink_id).first()
        if stats:
            # Обновляем существующую статистику
            stats.total_discoveries += 1
            stats.last_discovered_at = current_time
            
            # Проверяем, нужно ли сбросить дневной счетчик
            if stats.last_reset_date != current_date:
                stats.global_discoveries_today = 1
                stats.last_reset_date = current_date
            else:
                stats.global_discoveries_today += 1
        else:
            # Создаем новую запись
            stats = DrinkDiscoveryStats(
                drink_id=drink_id,
                total_discoveries=1,
                last_discovered_at=current_time,
                global_discoveries_today=1,
                last_reset_date=current_date
            )
            db.add(stats)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Ошибка при записи статистики находки: {e}")
    finally:
        db.close()


def get_drink_temperature(drink_id: int) -> str:
    """Определяет 'температуру' напитка на основе статистики.
    Возвращает: 'hot' (горячий), 'cold' (холодный) или 'neutral' (нейтральный)
    Напитки без статистики (никогда не находили) считаются 'hot' (редкими).
    """
    db = SessionLocal()
    try:
        current_time = int(time.time())
        stats = db.query(DrinkDiscoveryStats).filter_by(drink_id=drink_id).first()
        
        if not stats:
            return 'hot'  # Новые/редкие напитки считаются горячими
        
        time_since_discovery = current_time - stats.last_discovered_at
        
        # Холодный: нашли в последние 6 часов (21600 сек)
        if time_since_discovery < 21600:
            return 'cold'
        
        # Горячий: не находили более 48 часов (172800 сек)
        if time_since_discovery > 172800:
            return 'hot'
        
        # Нейтральный: между 6 и 48 часов
        return 'neutral'
    finally:
        db.close()


def get_weighted_drinks_list():
    """Возвращает список напитков с весами на основе их 'температуры'.
    Холодные напитки имеют вес 0.5x, горячие 2x, нейтральные 1x.
    """
    db = SessionLocal()
    try:
        all_drinks = db.query(EnergyDrink).all()
        weighted_list = []
        
        for drink in all_drinks:
            # Плантационные энергетики не участвуют в обычном поиске
            if getattr(drink, 'is_plantation', False):
                continue
            temp = get_drink_temperature(drink.id)
            
            # Определяем вес
            if temp == 'cold':
                weight = 0.5
            elif temp == 'hot':
                weight = 2.0
            else:  # neutral
                weight = 1.0
            
            # Добавляем напиток в список с учетом веса
            # Для упрощения выбора, добавляем напиток несколько раз
            count = max(1, int(weight * 10))  # Минимум 1 раз
            weighted_list.extend([drink] * count)
        
        return weighted_list
    finally:
        db.close()


def get_all_drinks_with_temperature():
    """Возвращает список всех напитков с информацией о их температуре.
    Полезно для отладки и статистики.
    """
    db = SessionLocal()
    try:
        all_drinks = db.query(EnergyDrink).all()
        result = []
        
        for drink in all_drinks:
            temp = get_drink_temperature(drink.id)
            stats = db.query(DrinkDiscoveryStats).filter_by(drink_id=drink.id).first()
            
            result.append({
                'drink': drink,
                'temperature': temp,
                'total_discoveries': stats.total_discoveries if stats else 0,
                'last_discovered_at': stats.last_discovered_at if stats else 0,
            })
        
        return result
    finally:
        db.close()

def get_player_inventory_with_details(user_id):
    """Возвращает полный инвентарь игрока с деталями о каждом напитке."""
    db = SessionLocal()
    try:
        # Используем joinedload для эффективной загрузки связанных данных
        inventory = db.query(InventoryItem).options(joinedload(InventoryItem.drink)).filter(InventoryItem.player_id == user_id).order_by(InventoryItem.id).all()
        return inventory
    finally:
        db.close()

def update_player(user_id, **kwargs):
    """Обновляет поля игрока (например, монеты или время поиска)."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if player:
            for key, value in kwargs.items():
                setattr(player, key, value)
            db.commit()
    finally:
        db.close()

def get_inventory_item(item_id):
    """Возвращает элемент инвентаря по его ID вместе с данными о напитке."""
    db = SessionLocal()
    try:
        return db.query(InventoryItem).options(joinedload(InventoryItem.drink)).filter(InventoryItem.id == item_id).first()
    finally:
        db.close()

def add_energy_drink(name: str, description: str, image_path: str | None = None, is_special: bool = False, is_plantation: bool = False):
    """Создаёт новый энергетик в базе и возвращает объект.

    Если is_plantation=True, энергетик помечается как плантационный и получает
    последовательный plantation_index (P1, P2, ...).
    """
    db = SessionLocal()
    try:
        drink = EnergyDrink(
            name=name,
            description=description,
            image_path=image_path,
            is_special=is_special,
        )
        # Безопасно проставляем флаг плантационного энергетика, если колонка присутствует
        try:
            drink.is_plantation = bool(is_plantation)
        except Exception:
            pass

        # Для плантационных энергетиков выдаём следующий plantation_index
        if getattr(drink, 'is_plantation', False):
            try:
                max_idx = db.query(func.max(EnergyDrink.plantation_index)).scalar() or 0
                drink.plantation_index = int(max_idx) + 1
            except Exception:
                # При ошибке просто оставляем plantation_index пустым
                pass

        db.add(drink)
        db.commit()
        db.refresh(drink)
        return drink
    finally:
        db.close()

def get_leaderboard(limit: int = 10):
    """Возвращает топ игроков по количеству энергетиков в инвентаре."""
    db = SessionLocal()
    try:
        now_ts = int(time.time())
        leaderboard_data = (
            db.query(
                Player.user_id,
                Player.username,
                func.sum(InventoryItem.quantity).label('total_drinks'),
                Player.vip_until,
                Player.vip_plus_until,
            )
            .join(InventoryItem, Player.user_id == InventoryItem.player_id)
            .outerjoin(
                UserBan,
                and_(
                    UserBan.user_id == Player.user_id,
                    or_(UserBan.banned_until == None, UserBan.banned_until > now_ts)
                )
            )
            .filter(UserBan.user_id == None)
            .group_by(Player.user_id)
            .order_by(func.sum(InventoryItem.quantity).desc())
            .limit(limit)
            .all()
        )
        return leaderboard_data
    finally:
        db.close()

def delete_energy_drink(drink_id: int) -> bool:
    """Полностью удаляет энергетик и все связанные элементы инвентаря. Возвращает True, если удалено."""
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return False
        # Удаляем связанные предметы инвентаря
        db.query(InventoryItem).filter(InventoryItem.drink_id == drink_id).delete(synchronize_session=False)
        # Удаляем сам напиток
        db.delete(drink)
        db.commit()
        return True
    finally:
        db.close()

def update_energy_drink_field(drink_id: int, field: str, new_value: str) -> bool:
    """Обновляет поле энергетика (name или description). Возвращает True при успехе."""
    if field not in ("name", "description"):
        return False
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return False
        setattr(drink, field, new_value)
        try:
            db.commit()
        except Exception:
            db.rollback()
            return False
        return True
    finally:
        db.close()

def create_pending_deletion(proposer_id: int, drink_id: int, reason: str | None = None) -> PendingDeletion:
    db = SessionLocal()
    try:
        pending = PendingDeletion(
            proposer_id=proposer_id,
            drink_id=drink_id,
            reason=reason or None,
            status='pending',
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        return pending
    finally:
        db.close()

def get_pending_deletions(limit: int = 20) -> list[PendingDeletion]:
    db = SessionLocal()
    try:
        return (
            db.query(PendingDeletion)
            .filter(PendingDeletion.status == 'pending')
            .order_by(PendingDeletion.created_at.asc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()

def get_pending_deletion_by_id(request_id: int) -> PendingDeletion | None:
    db = SessionLocal()
    try:
        return db.query(PendingDeletion).filter(PendingDeletion.id == request_id).first()
    finally:
        db.close()

def mark_pending_deletion_approved(request_id: int, reviewer_id: int):
    db = SessionLocal()
    try:
        rec = db.query(PendingDeletion).filter(PendingDeletion.id == request_id).first()
        if not rec:
            return False
        rec.status = 'approved'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        db.commit()
        return True
    finally:
        db.close()

def mark_pending_deletion_rejected(request_id: int, reviewer_id: int, reason: str | None = None):
    db = SessionLocal()
    try:
        rec = db.query(PendingDeletion).filter(PendingDeletion.id == request_id).first()
        if not rec:
            return False
        rec.status = 'rejected'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        rec.review_reason = reason
        db.commit()
        return True
    finally:
        db.close()

# --- Модерация редактирований ---

def create_pending_edit(proposer_id: int, drink_id: int, field: str, new_value: str) -> PendingEdit:
    db = SessionLocal()
    try:
        pending = PendingEdit(
            proposer_id=proposer_id,
            drink_id=drink_id,
            field=field,
            new_value=new_value,
            status='pending',
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        return pending
    finally:
        db.close()

def get_pending_edits(limit: int = 20) -> list[PendingEdit]:
    db = SessionLocal()
    try:
        return (
            db.query(PendingEdit)
            .filter(PendingEdit.status == 'pending')
            .order_by(PendingEdit.created_at.asc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()

def get_pending_edit_by_id(request_id: int) -> PendingEdit | None:
    db = SessionLocal()
    try:
        return db.query(PendingEdit).filter(PendingEdit.id == request_id).first()
    finally:
        db.close()

def mark_pending_edit_approved(request_id: int, reviewer_id: int):
    db = SessionLocal()
    try:
        rec = db.query(PendingEdit).filter(PendingEdit.id == request_id).first()
        if not rec:
            return False
        rec.status = 'approved'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        db.commit()
        return True
    finally:
        db.close()

def mark_pending_edit_rejected(request_id: int, reviewer_id: int, reason: str | None = None):
    db = SessionLocal()
    try:
        rec = db.query(PendingEdit).filter(PendingEdit.id == request_id).first()
        if not rec:
            return False
        rec.status = 'rejected'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        rec.review_reason = reason
        db.commit()
        return True
    finally:
        db.close()

# --- Дополнительные функции для схемы и пользователей ---

def ensure_schema():
    """Проверяет наличие новых столбцов и добавляет их, если необходимо (SQLite ALTER TABLE)."""
    # Создаём новые таблицы, если их нет
    Base.metadata.create_all(bind=engine)
    # Важно: использовать транзакцию с автокоммитом, чтобы ALTER TABLE применялись (SQLAlchemy 2.x)
    with engine.begin() as conn:
        # Получаем текущие столбцы таблицы players
        res = conn.exec_driver_sql("PRAGMA table_info(players)")
        cols = [row[1] for row in res]

        if 'language' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN language TEXT DEFAULT 'ru'")
        if 'remind' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN remind INTEGER DEFAULT 0")
        if 'last_bonus_claim' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN last_bonus_claim INTEGER DEFAULT 0")
        if 'last_add' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN last_add INTEGER DEFAULT 0")
        if 'vip_until' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN vip_until INTEGER DEFAULT 0")
        if 'vip_plus_until' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN vip_plus_until INTEGER DEFAULT 0")
        if 'tg_premium_until' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN tg_premium_until INTEGER DEFAULT 0")
        # Автопоиск VIP
        if 'auto_search_enabled' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN auto_search_enabled INTEGER DEFAULT 0")
        if 'auto_search_count' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN auto_search_count INTEGER DEFAULT 0")
        if 'auto_search_reset_ts' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN auto_search_reset_ts INTEGER DEFAULT 0")
        # Автопоиск буст
        if 'auto_search_boost_count' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN auto_search_boost_count INTEGER DEFAULT 0")
        if 'auto_search_boost_until' not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN auto_search_boost_until INTEGER DEFAULT 0")

        # Обновления для energy_drinks (плантационные энергетики)
        res_drinks = conn.exec_driver_sql("PRAGMA table_info(energy_drinks)")
        cols_drinks = [row[1] for row in res_drinks]
        if 'is_plantation' not in cols_drinks:
            conn.exec_driver_sql("ALTER TABLE energy_drinks ADD COLUMN is_plantation INTEGER DEFAULT 0")
        if 'plantation_index' not in cols_drinks:
            conn.exec_driver_sql("ALTER TABLE energy_drinks ADD COLUMN plantation_index INTEGER")

        # Обновления для admin_users
        res_adm = conn.exec_driver_sql("PRAGMA table_info(admin_users)")
        cols_adm = [row[1] for row in res_adm]
        if 'level' not in cols_adm:
            conn.exec_driver_sql("ALTER TABLE admin_users ADD COLUMN level INTEGER DEFAULT 1")
        # Бэкофилл NULL значений уровня на 1
        try:
            conn.exec_driver_sql("UPDATE admin_users SET level = 1 WHERE level IS NULL")
        except Exception:
            pass

        # Проверяем существование таблицы boost_history
        try:
            conn.exec_driver_sql("SELECT COUNT(*) FROM boost_history LIMIT 1")
        except Exception:
            # Таблица boost_history не существует, создаём её
            try:
                conn.exec_driver_sql("""
                    CREATE TABLE boost_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id BIGINT,
                        username TEXT,
                        action TEXT,
                        boost_count INTEGER DEFAULT 0,
                        boost_days INTEGER DEFAULT 0,
                        granted_by BIGINT,
                        granted_by_username TEXT,
                        timestamp INTEGER DEFAULT 0,
                        details TEXT
                    )
                """)
                # Создаём индексы
                conn.exec_driver_sql("CREATE INDEX idx_boost_history_user ON boost_history(user_id)")
                conn.exec_driver_sql("CREATE INDEX idx_boost_history_action ON boost_history(action)")
                conn.exec_driver_sql("CREATE INDEX idx_boost_history_timestamp ON boost_history(timestamp)")
            except Exception as e:
                # Таблица может уже существовать или ошибка создания - это не критично
                pass

        # Инициализация складов: legacy TG Premium и миграция в универсальный склад
        try:
            # Убедимся, что есть запись в tg_premium_stock (legacy)
            res_stock = conn.exec_driver_sql("SELECT COUNT(*) FROM tg_premium_stock")
            cnt = list(res_stock)[0][0] if res_stock else 0
            if cnt == 0:
                conn.exec_driver_sql("INSERT INTO tg_premium_stock (stock) VALUES (0)")
        except Exception:
            pass

        # Миграция значения склада TG Premium в bonus_stock(kind='tg_premium')
        try:
            # Проверим, есть ли уже запись в bonus_stock для tg_premium
            res_b = conn.exec_driver_sql("SELECT stock FROM bonus_stock WHERE kind = 'tg_premium'")
            row_b = list(res_b)
            if not row_b:
                # Берём legacy-остаток (если таблица существует)
                legacy_stock = 0
                try:
                    res_l = conn.exec_driver_sql("SELECT stock FROM tg_premium_stock ORDER BY id ASC LIMIT 1")
                    rows_l = list(res_l)
                    if rows_l:
                        legacy_stock = int(rows_l[0][0] or 0)
                except Exception:
                    legacy_stock = 0
                conn.exec_driver_sql("INSERT INTO bonus_stock (kind, stock) VALUES ('tg_premium', ?)", (legacy_stock,))
        except Exception:
            # Если таблицы bonus_stock ещё нет (первая инициализация) — не критично, она создастся выше
            pass

        # --- Плантация: новые поля и индексы ---
        try:
            res_beds = conn.exec_driver_sql("PRAGMA table_info(plantation_beds)")
            cols_beds = [row[1] for row in res_beds]
            if 'fertilizer_id' not in cols_beds:
                conn.exec_driver_sql("ALTER TABLE plantation_beds ADD COLUMN fertilizer_id INTEGER")
            if 'fertilizer_applied_at' not in cols_beds:
                conn.exec_driver_sql("ALTER TABLE plantation_beds ADD COLUMN fertilizer_applied_at INTEGER DEFAULT 0")
            if 'status_effect' not in cols_beds:
                conn.exec_driver_sql("ALTER TABLE plantation_beds ADD COLUMN status_effect TEXT")
            # Индекс для ускорения выборок по удобрениям
            try:
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_plantation_fertilizer ON plantation_beds(fertilizer_id)")
            except Exception:
                pass
        except Exception:
            # Если таблицы plantation_beds ещё нет — она будет создана выше через Base.metadata.create_all
            pass

def get_receipt_by_id(receipt_id: int) -> PurchaseReceipt | None:
    dbs = SessionLocal()
    try:
        return dbs.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()
    finally:
        dbs.close()

def get_receipts_by_user(user_id: int, limit: int = 20) -> list[PurchaseReceipt]:
    dbs = SessionLocal()
    try:
        return (
            dbs.query(PurchaseReceipt)
            .filter(PurchaseReceipt.user_id == user_id)
            .order_by(PurchaseReceipt.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        dbs.close()

def verify_receipt(receipt_id: int, admin_user_id: int) -> bool:
    dbs = SessionLocal()
    try:
        rec = dbs.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()
        if not rec:
            return False
        rec.status = 'verified'
        rec.verified_by = admin_user_id
        rec.verified_at = int(time.time())
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

# --- Админ функции ---

def add_admin_user(user_id: int, username: str | None = None, level: int | None = None) -> bool:
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
        if existing:
            if username and existing.username != username:
                existing.username = username
            if level is not None and getattr(existing, 'level', None) != level:
                try:
                    existing.level = level
                except Exception:
                    pass
            db.commit()
            return False
        admin = AdminUser(user_id=user_id, username=username, level=(level if level is not None else 1))
        db.add(admin)
        db.commit()
        return True
    finally:
        db.close()

def remove_admin_user(user_id: int) -> bool:
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
        if not existing:
            return False
        db.delete(existing)
        db.commit()
        return True
    finally:
        db.close()

def is_admin(user_id: int) -> bool:
    db = SessionLocal()
    try:
        return db.query(AdminUser).filter(AdminUser.user_id == user_id).first() is not None
    finally:
        db.close()

def get_admin_user_ids() -> list[int]:
    db = SessionLocal()
    try:
        return [row.user_id for row in db.query(AdminUser).all()]
    finally:
        db.close()

def get_admin_users() -> list[AdminUser]:
    db = SessionLocal()
    try:
        return list(db.query(AdminUser).all())
    finally:
        db.close()

def get_admin_level(user_id: int) -> int:
    """Возвращает уровень админа (1..3). Если не админ — 0."""
    db = SessionLocal()
    try:
        rec = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
        if not rec:
            return 0
        lvl = getattr(rec, 'level', None)
        return int(lvl) if isinstance(lvl, int) and 1 <= lvl <= 3 else 1
    finally:
        db.close()

def is_creator(user_id: int) -> bool:
    db = SessionLocal()
    try:
        p = db.query(Player).filter(Player.user_id == int(user_id)).first()
        if not p:
            return False
        uname = getattr(p, 'username', None)
        try:
            if uname:
                return uname in ADMIN_USERNAMES
        except Exception:
            return False
        return False
    finally:
        db.close()

def is_protected_user(user_id: int) -> bool:
    try:
        if is_admin(int(user_id)):
            return True
    except Exception:
        pass
    try:
        if is_creator(int(user_id)):
            return True
    except Exception:
        pass
    return False

# --- VIP helpers ---

def get_vip_until(user_id: int) -> int:
    """Возвращает Unix-время истечения VIP (или 0/None)."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        return int(getattr(player, 'vip_until', 0) or 0) if player else 0
    finally:
        db.close()

def get_vip_plus_until(user_id: int) -> int:
    """Возвращает Unix-время истечения VIP+ (или 0/None)."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        return int(getattr(player, 'vip_plus_until', 0) or 0) if player else 0
    finally:
        db.close()

def is_vip(user_id: int) -> bool:
    """Возвращает True, если VIP или VIP+ активен на текущий момент."""
    try:
        vip_ts = get_vip_until(user_id)
        vip_plus_ts = get_vip_plus_until(user_id)
        import time
        current_time = int(time.time())
        return bool((vip_ts and current_time < int(vip_ts)) or (vip_plus_ts and current_time < int(vip_plus_ts)))
    except Exception:
        return False

def is_vip_plus(user_id: int) -> bool:
    """Возвращает True, если VIP+ активен на текущий момент."""
    try:
        vip_plus_ts = get_vip_plus_until(user_id)
        import time
        return bool(vip_plus_ts and int(time.time()) < int(vip_plus_ts))
    except Exception:
        return False

def purchase_vip(user_id: int, cost_coins: int, duration_seconds: int) -> dict:
    """
    Списывает монеты и устанавливает/продлевает VIP.
    Возвращает dict: {ok: bool, reason?: str, vip_until?: int, coins_left?: int}
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            # Автосоздание игрока при редком коллизии
            player = Player(user_id=user_id, username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)

        current_coins = int(player.coins or 0)
        if current_coins < cost_coins:
            return {"ok": False, "reason": "not_enough_coins"}

        now_ts = int(time.time())
        base_ts = int(player.vip_until or 0)
        start_ts = base_ts if base_ts and base_ts > now_ts else now_ts
        new_vip_until = start_ts + int(duration_seconds)

        player.coins = current_coins - int(cost_coins)
        try:
            player.vip_until = new_vip_until
        except Exception:
            # На случай старой схемы без столбца — не должен произойти, т.к. ensure_schema()
            pass
        db.commit()
        return {"ok": True, "vip_until": new_vip_until, "coins_left": int(player.coins)}
    except Exception as ex:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        db.close()

def purchase_vip_plus(user_id: int, cost_coins: int, duration_seconds: int) -> dict:
    """
    Списывает монеты и устанавливает/продлевает VIP+.
    Если у пользователя есть активный обычный VIP, 25% оставшегося времени переносится на VIP+.
    Возвращает dict: {ok: bool, reason?: str, vip_plus_until?: int, coins_left?: int, vip_time_transferred?: int}
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            # Автосоздание игрока при редком коллизии
            player = Player(user_id=user_id, username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)

        current_coins = int(player.coins or 0)
        if current_coins < cost_coins:
            return {"ok": False, "reason": "not_enough_coins"}

        now_ts = int(time.time())
        
        # Проверяем наличие активного обычного VIP
        vip_until = int(player.vip_until or 0)
        vip_plus_until = int(player.vip_plus_until or 0)
        vip_time_transferred = 0
        
        # Если есть активный VIP (но не VIP+), переносим 25% времени
        if vip_until > now_ts and vip_plus_until <= now_ts:
            remaining_vip_time = vip_until - now_ts
            vip_time_transferred = int(remaining_vip_time * 0.25)
            # Обнуляем обычный VIP после переноса
            player.vip_until = 0
        
        # Рассчитываем новое время VIP+
        base_ts = vip_plus_until if vip_plus_until and vip_plus_until > now_ts else now_ts
        new_vip_plus_until = base_ts + int(duration_seconds) + vip_time_transferred

        player.coins = current_coins - int(cost_coins)
        try:
            player.vip_plus_until = new_vip_plus_until
        except Exception:
            # На случай старой схемы без столбца
            pass
        db.commit()
        return {
            "ok": True, 
            "vip_plus_until": new_vip_plus_until, 
            "coins_left": int(player.coins),
            "vip_time_transferred": vip_time_transferred
        }
    except Exception as ex:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        db.close()

def extend_vip(user_id: int, duration_seconds: int) -> int:
    """
    Продлевает VIP на указанное количество секунд без списания монет.
    Используется для наград (например, рулетка ежедневного бонуса).
    Возвращает новый Unix-timestamp окончания VIP.
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            # Автосоздание игрока
            player = Player(user_id=user_id, username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)

        now_ts = int(time.time())
        base_ts = int(player.vip_until or 0)
        start_ts = base_ts if base_ts and base_ts > now_ts else now_ts
        new_vip_until = start_ts + int(duration_seconds)

        player.vip_until = new_vip_until
        db.commit()
        return new_vip_until
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def extend_vip_plus(user_id: int, duration_seconds: int) -> int:
    """
    Продлевает VIP+ на указанное количество секунд без списания монет.
    Используется для наград (например, рулетка ежедневного бонуса).
    Возвращает новый Unix-timestamp окончания VIP+.
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            # Автосоздание игрока
            player = Player(user_id=user_id, username=str(user_id))
            db.add(player)
            db.commit()
            db.refresh(player)

        now_ts = int(time.time())
        base_ts = int(player.vip_plus_until or 0)
        start_ts = base_ts if base_ts and base_ts > now_ts else now_ts
        new_vip_plus_until = start_ts + int(duration_seconds)

        player.vip_plus_until = new_vip_plus_until
        db.commit()
        return new_vip_plus_until
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def set_admin_level(user_id: int, level: int) -> bool:
    """Устанавливает уровень админа (1..3). Возвращает True, если успешно."""
    if level not in (1, 2, 3):
        return False
    db = SessionLocal()
    try:
        rec = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
        if not rec:
            return False
        rec.level = level
        db.commit()
        return True
    finally:
        db.close()

def reset_all_daily_bonus() -> int:
    """Сбрасывает ежедневный бонус для всех пользователей. Возвращает количество обновленных записей."""
    db = SessionLocal()
    try:
        count = db.query(Player).update({Player.last_bonus_claim: 0})
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def insert_moderation_log(actor_id: int, action: str, request_id: int | None = None, target_id: int | None = None, details: str | None = None) -> None:
    """Записывает событие модерации/администрирования в аудит-лог."""
    db = SessionLocal()
    try:
        rec = ModerationLog(actor_id=actor_id, action=action, request_id=request_id, target_id=target_id, details=details)
        db.add(rec)
        db.commit()
    except Exception:
        # Аудит не должен ломать основной поток
        db.rollback()
    finally:
        db.close()

# --- Модерация добавлений ---

def create_pending_addition(proposer_id: int, name: str, description: str, is_special: bool, file_id: str | None) -> PendingAddition:
    db = SessionLocal()
    try:
        pending = PendingAddition(
            proposer_id=proposer_id,
            name=name,
            description=description,
            is_special=is_special,
            file_id=file_id,
            status='pending',
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        return pending
    finally:
        db.close()

def get_pending_additions(limit: int = 20) -> list[PendingAddition]:
    db = SessionLocal()
    try:
        return (
            db.query(PendingAddition)
            .filter(PendingAddition.status == 'pending')
            .order_by(PendingAddition.created_at.asc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()

def get_pending_by_id(request_id: int) -> PendingAddition | None:
    db = SessionLocal()
    try:
        return db.query(PendingAddition).filter(PendingAddition.id == request_id).first()
    finally:
        db.close()

def mark_pending_as_approved(request_id: int, reviewer_id: int):
    db = SessionLocal()
    try:
        rec = db.query(PendingAddition).filter(PendingAddition.id == request_id).first()
        if not rec:
            return False
        rec.status = 'approved'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        db.commit()
        return True
    finally:
        db.close()

def mark_pending_as_rejected(request_id: int, reviewer_id: int, reason: str | None = None):
    db = SessionLocal()
    try:
        rec = db.query(PendingAddition).filter(PendingAddition.id == request_id).first()
        if not rec:
            return False
        rec.status = 'rejected'
        rec.reviewed_by = reviewer_id
        rec.reviewed_at = int(time.time())
        rec.review_reason = reason
        db.commit()
        return True
    finally:
        db.close()

# --- Работа с группами ---

def upsert_group_chat(chat_id: int, title: str | None):
    db = SessionLocal()
    try:
        grp = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if grp:
            # Обновим title, если изменился
            if title and grp.title != title:
                grp.title = title
                db.commit()
            return False
        db.add(GroupChat(chat_id=chat_id, title=title or None, is_enabled=True))
        db.commit()
        return True
    finally:
        db.close()

def get_enabled_group_chats() -> list[GroupChat]:
    db = SessionLocal()
    try:
        return db.query(GroupChat).filter(GroupChat.is_enabled == True).all()
    finally:
        db.close()

def update_group_last_notified(chat_id: int):
    db = SessionLocal()
    try:
        grp = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not grp:
            return False
        grp.last_notified = int(time.time())
        db.commit()
        return True
    finally:
        db.close()

def disable_group_chat(chat_id: int) -> bool:
    db = SessionLocal()
    try:
        grp = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not grp:
            return False
        grp.is_enabled = False
        db.commit()
        return True
    finally:
        db.close()

def delete_player(user_id):
    """Удаляет игрока и все связанные записи."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if player:
            db.delete(player)
            db.commit()
            return True
        return False
    finally:
        db.close()

# --- Инвентарь: дополнительные операции ---

def decrement_inventory_item(item_id: int) -> bool:
    """Уменьшает количество предмета в инвентаре на 1 или удаляет запись, если осталось 0. Возвращает True, если успешно."""
    db = SessionLocal()
    try:
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            return False
        if item.quantity <= 1:
            db.delete(item)
        else:
            item.quantity -= 1
        db.commit()
        return True
    finally:
        db.close()

def get_receiver_unit_payout(rarity: str) -> int:
    """Возвращает выплату за 1 шт. указанной редкости с учётом комиссии (int(base * (1 - commission)))."""
    try:
        base = int(RECEIVER_PRICES.get(rarity, 0) or 0)
        commission = float(RECEIVER_COMMISSION)
        payout = int(base * (1.0 - commission))
        return max(0, payout)
    except Exception:
        return 0

def sell_inventory_item(user_id: int, item_id: int, quantity: int) -> dict:
    """Продажа предметов из инвентаря в Приёмник.
    - Уменьшает количество/удаляет предмет, начисляет монеты.
    Возвращает dict: {ok, reason?, unit_payout, quantity_sold, total_payout, coins_after, item_left_qty}
    """
    dbs = SessionLocal()
    try:
        item = (
            dbs.query(InventoryItem)
            .filter(InventoryItem.id == item_id)
            .first()
        )
        if not item:
            return {"ok": False, "reason": "not_found"}
        if int(item.player_id) != int(user_id):
            return {"ok": False, "reason": "forbidden"}

        # Нормализуем количество
        qty_available = int(item.quantity or 0)
        qty_req = int(quantity or 0)
        if qty_req < 1:
            return {"ok": False, "reason": "bad_quantity"}
        qty_to_sell = min(qty_req, qty_available)
        if qty_to_sell <= 0:
            return {"ok": False, "reason": "empty"}

        unit_payout = get_receiver_unit_payout(item.rarity)
        if unit_payout <= 0:
            return {"ok": False, "reason": "unsupported_rarity"}

        total_payout = int(unit_payout) * int(qty_to_sell)

        # Начисляем монеты
        player = (
            dbs.query(Player)
            .filter(Player.user_id == user_id)
            .with_for_update(read=False)
            .first()
        )
        if not player:
            # Создаём игрока, если внезапно отсутствует
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        player.coins = int(player.coins or 0) + int(total_payout)

        # Списываем из инвентаря
        left = int(item.quantity or 0) - int(qty_to_sell)
        if left <= 0:
            dbs.delete(item)
            item_left_qty = 0
        else:
            item.quantity = left
            item_left_qty = left

        dbs.commit()
        return {
            "ok": True,
            "unit_payout": int(unit_payout),
            "quantity_sold": int(qty_to_sell),
            "total_payout": int(total_payout),
            "coins_after": int(player.coins),
            "item_left_qty": int(item_left_qty),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def sell_all_but_one(user_id: int, item_id: int) -> dict:
    """Продажа всех предметов из инвентаря кроме одного через Приёмник.
    - Уменьшает количество до 1, начисляет монеты.
    Возвращает dict: {ok, reason?, unit_payout, quantity_sold, total_payout, coins_after, item_left_qty}
    """
    dbs = SessionLocal()
    try:
        item = (
            dbs.query(InventoryItem)
            .filter(InventoryItem.id == item_id)
            .first()
        )
        if not item:
            return {"ok": False, "reason": "not_found"}
        if int(item.player_id) != int(user_id):
            return {"ok": False, "reason": "forbidden"}

        # Проверяем количество - должно быть больше 1
        qty_available = int(item.quantity or 0)
        if qty_available <= 1:
            return {"ok": False, "reason": "not_enough_items"}
        
        qty_to_sell = qty_available - 1  # Продаём все кроме одного

        unit_payout = get_receiver_unit_payout(item.rarity)
        if unit_payout <= 0:
            return {"ok": False, "reason": "unsupported_rarity"}

        total_payout = int(unit_payout) * int(qty_to_sell)

        # Начисляем монеты
        player = (
            dbs.query(Player)
            .filter(Player.user_id == user_id)
            .with_for_update(read=False)
            .first()
        )
        if not player:
            # Создаём игрока, если внезапно отсутствует
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)

        player.coins = int(player.coins or 0) + int(total_payout)

        # Списываем из инвентаря (оставляем только 1)
        item.quantity = 1
        item_left_qty = 1

        dbs.commit()
        return {
            "ok": True,
            "unit_payout": int(unit_payout),
            "quantity_sold": int(qty_to_sell),
            "total_payout": int(total_payout),
            "coins_after": int(player.coins),
            "item_left_qty": int(item_left_qty),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

def sell_absolutely_all_but_one(user_id: int) -> dict:
    """Продажа АБСОЛЮТНО всех энергетиков кроме одного экземпляра каждого типа.
    Возвращает dict: {ok, total_items_sold, total_earned, items_processed, coins_after}
    """
    dbs = SessionLocal()
    try:
        # Получаем все предметы пользователя
        user_items = (
            dbs.query(InventoryItem)
            .filter(InventoryItem.player_id == user_id)
            .all()
        )
        
        if not user_items:
            return {"ok": False, "reason": "no_items"}
        
        # Получаем игрока для обновления баланса
        player = (
            dbs.query(Player)
            .filter(Player.user_id == user_id)
            .with_for_update(read=False)
            .first()
        )
        if not player:
            # Создаём игрока, если внезапно отсутствует
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        
        total_items_sold = 0
        total_earned = 0
        items_processed = 0
        
        # Обрабатываем каждый предмет
        for item in user_items:
            qty_available = int(item.quantity or 0)
            
            # Пропускаем предметы с количеством 1 или меньше
            if qty_available <= 1:
                continue
                
            # Получаем выплату за предмет
            unit_payout = get_receiver_unit_payout(item.rarity)
            if unit_payout <= 0:
                continue  # Пропускаем неподдерживаемые редкости
            
            # Продаём все кроме одного
            qty_to_sell = qty_available - 1
            item_payout = int(unit_payout) * int(qty_to_sell)
            
            total_items_sold += qty_to_sell
            total_earned += item_payout
            items_processed += 1
            
            # Обновляем количество предмета (оставляем 1)
            item.quantity = 1
        
        # Если ничего не продали
        if total_items_sold == 0:
            return {"ok": False, "reason": "nothing_to_sell"}
        
        # Начисляем заработанные монеты
        player.coins = int(player.coins or 0) + int(total_earned)
        
        dbs.commit()
        return {
            "ok": True,
            "total_items_sold": int(total_items_sold),
            "total_earned": int(total_earned),
            "items_processed": int(items_processed),
            "coins_after": int(player.coins),
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

# --- Автопоиск буст: расширенные функции ---

def get_players_with_active_boosts() -> list[Player]:
    """Возвращает список игроков с активными автопоиск бустами."""
    import time
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        return list(
            dbs.query(Player)
            .filter(
                Player.auto_search_boost_until > current_time,
                Player.auto_search_boost_count > 0
            )
            .all()
        )
    finally:
        dbs.close()

def get_expiring_boosts(hours_ahead: int = 24) -> list[Player]:
    """Возвращает список игроков, у которых буст истекает в ближайшие hours_ahead часов."""
    import time
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        expiration_threshold = current_time + (hours_ahead * 60 * 60)
        return list(
            dbs.query(Player)
            .filter(
                Player.auto_search_boost_until > current_time,
                Player.auto_search_boost_until <= expiration_threshold,
                Player.auto_search_boost_count > 0
            )
            .all()
        )
    finally:
        dbs.close()

def remove_auto_search_boost(user_id: int, removed_by: int | None = None, removed_by_username: str | None = None) -> bool:
    """Убирает активный буст автопоиска у пользователя."""
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        # Сохраняем информацию о бусте для истории
        boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
        
        player.auto_search_boost_count = 0
        player.auto_search_boost_until = 0
        dbs.commit()
        
        # Добавляем запись в историю, если был активный буст
        if boost_count > 0:
            try:
                add_boost_history_record(
                    user_id=user_id,
                    username=player.username,
                    action='removed',
                    boost_count=boost_count,
                    granted_by=removed_by,
                    granted_by_username=removed_by_username,
                    details=f"Новый лимит: {get_auto_search_daily_limit(user_id)}"
                )
            except Exception:
                # Не прерываем основную операцию из-за ошибки с историей
                pass
        
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

def get_boost_statistics() -> dict:
    """Возвращает статистику по бустам автопоиска."""
    import time
    dbs = SessionLocal()
    try:
        current_time = int(time.time())
        
        # Всего игроков с активными бустами
        active_boosts = dbs.query(Player).filter(
            Player.auto_search_boost_until > current_time,
            Player.auto_search_boost_count > 0
        ).count()
        
        # Всего истёкших бустов (имеют count > 0 но until <= current_time)
        expired_boosts = dbs.query(Player).filter(
            Player.auto_search_boost_until <= current_time,
            Player.auto_search_boost_count > 0
        ).count()
        
        # Топ пользователей по количеству бустов
        top_users = dbs.query(Player).filter(
            Player.auto_search_boost_until > current_time,
            Player.auto_search_boost_count > 0
        ).order_by(Player.auto_search_boost_count.desc()).limit(5).all()
        
        # Среднее количество бустов
        avg_result = dbs.query(Player.auto_search_boost_count).filter(
            Player.auto_search_boost_until > current_time,
            Player.auto_search_boost_count > 0
        ).all()
        
        avg_boost_count = 0
        if avg_result:
            total = sum(row[0] for row in avg_result)
            avg_boost_count = round(total / len(avg_result), 1)
        
        return {
            "active_boosts": active_boosts,
            "expired_boosts": expired_boosts,
            "top_users": [{
                "user_id": user.user_id,
                "username": user.username,
                "boost_count": user.auto_search_boost_count,
                "boost_until": user.auto_search_boost_until
            } for user in top_users],
            "average_boost_count": avg_boost_count
        }
    finally:
        dbs.close()

def get_user_boost_history(user_id: int, limit: int = 10) -> list[dict]:
    """Возвращает историю бустов пользователя."""
    dbs = SessionLocal()
    try:
        records = dbs.query(BoostHistory).filter(
            BoostHistory.user_id == user_id
        ).order_by(BoostHistory.timestamp.desc()).limit(limit).all()
        
        history = []
        for record in records:
            from datetime import datetime
            formatted_date = datetime.fromtimestamp(record.timestamp).strftime('%d.%m.%Y %H:%M')
            
            # Определяем описание действия
            if record.action == 'granted':
                action_text = f"🎉 Получен буст: +{record.boost_count} поисков на {record.boost_days} дн."
                if record.granted_by_username:
                    action_text += f" (от @{record.granted_by_username})"
            elif record.action == 'removed':
                action_text = f"🚫 Убран буст: -{record.boost_count} поисков"
                if record.granted_by_username:
                    action_text += f" (админ @{record.granted_by_username})"
            elif record.action == 'expired':
                action_text = f"⏰ Истёк буст: -{record.boost_count} поисков"
            else:
                action_text = f"🔄 {record.action}: {record.boost_count} поисков"
                
            history.append({
                'timestamp': record.timestamp,
                'formatted_date': formatted_date,
                'action': record.action,
                'action_text': action_text,
                'boost_count': record.boost_count,
                'boost_days': record.boost_days,
                'granted_by': record.granted_by,
                'granted_by_username': record.granted_by_username,
                'details': record.details
            })
            
        return history
    finally:
        dbs.close()

def add_boost_history_record(user_id: int, username: str | None, action: str, boost_count: int, 
                           boost_days: int = 0, granted_by: int | None = None, 
                           granted_by_username: str | None = None, details: str | None = None) -> bool:
    """Добавляет запись в историю бустов."""
    dbs = SessionLocal()
    try:
        record = BoostHistory(
            user_id=user_id,
            username=username,
            action=action,
            boost_count=boost_count,
            boost_days=boost_days,
            granted_by=granted_by,
            granted_by_username=granted_by_username,
            timestamp=int(time.time()),
            details=details
        )
        dbs.add(record)
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

def get_boost_info(user_id: int) -> dict:
    """Возвращает полную информацию о бусте пользователя."""
    import time
    from datetime import datetime
    
    dbs = SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return {
                "has_boost": False,
                "boost_count": 0,
                "boost_until": 0,
                "time_remaining": 0,
                "is_active": False
            }
        
        boost_count = int(getattr(player, 'auto_search_boost_count', 0) or 0)
        boost_until = int(getattr(player, 'auto_search_boost_until', 0) or 0)
        current_time = int(time.time())
        
        is_active = boost_until > current_time and boost_count > 0
        time_remaining = max(0, boost_until - current_time) if is_active else 0
        
        return {
            "has_boost": boost_count > 0,
            "boost_count": boost_count,
            "boost_until": boost_until,
            "boost_until_formatted": datetime.fromtimestamp(boost_until).strftime('%d.%m.%Y %H:%M') if boost_until > 0 else "",
            "time_remaining": time_remaining,
            "time_remaining_formatted": format_time_remaining(time_remaining) if time_remaining > 0 else "",
            "is_active": is_active
        }
    finally:
        dbs.close()

def format_time_remaining(seconds: int) -> str:
    """Форматирует оставшееся время в удобочитаемом виде."""
    if seconds <= 0:
        return "Истёк"
    
    days = seconds // (24 * 60 * 60)
    hours = (seconds % (24 * 60 * 60)) // (60 * 60)
    minutes = (seconds % (60 * 60)) // 60
    
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    elif hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"

# --- Функции для системы шёлка ---

def get_silk_plantation(plantation_id: int, user_id: int = None) -> SilkPlantation | None:
    """Получить плантацию по ID. Опционально проверить владельца."""
    dbs = SessionLocal()
    try:
        query = dbs.query(SilkPlantation).filter(SilkPlantation.id == plantation_id)
        if user_id is not None:
            query = query.filter(SilkPlantation.player_id == user_id)
        return query.first()
    finally:
        dbs.close()

def get_player_silk_plantations(user_id: int, status: str = None) -> list[SilkPlantation]:
    """Получить все плантации игрока. Опционально фильтр по статусу."""
    dbs = SessionLocal()
    try:
        query = dbs.query(SilkPlantation).filter(SilkPlantation.player_id == user_id)
        if status:
            query = query.filter(SilkPlantation.status == status)
        return list(query.order_by(SilkPlantation.id.asc()).all())
    finally:
        dbs.close()

def get_player_silk_inventory(user_id: int) -> list[SilkInventory]:
    """Получить инвентарь шёлка игрока."""
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(SilkInventory)
            .filter(SilkInventory.player_id == user_id)
            .filter(SilkInventory.quantity > 0)
            .order_by(SilkInventory.silk_type.asc())
            .all()
        )
    finally:
        dbs.close()

def update_silk_plantation_status(plantation_id: int, status: str, **kwargs) -> bool:
    """Обновить статус плантации."""
    dbs = SessionLocal()
    try:
        plantation = dbs.query(SilkPlantation).filter(SilkPlantation.id == plantation_id).first()
        if not plantation:
            return False
        
        plantation.status = status
        for key, value in kwargs.items():
            if hasattr(plantation, key):
                setattr(plantation, key, value)
        
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

def add_silk_to_player_inventory(user_id: int, silk_type: str, quantity: int, quality_grade: int = None) -> bool:
    """Добавить шёлк в инвентарь игрока."""
    if quantity <= 0:
        return False
    
    dbs = SessionLocal()
    try:
        # Поиск существующей записи
        existing = (
            dbs.query(SilkInventory)
            .filter(SilkInventory.player_id == user_id, SilkInventory.silk_type == silk_type)
            .first()
        )
        
        if existing:
            existing.quantity += quantity
            # Обновить качество средним взвешенным
            if quality_grade is not None:
                total_old = existing.quantity - quantity
                if total_old > 0:
                    existing.quality_grade = int((existing.quality_grade * total_old + quality_grade * quantity) / existing.quantity)
                else:
                    existing.quality_grade = quality_grade
        else:
            new_item = SilkInventory(
                player_id=user_id,
                silk_type=silk_type,
                quantity=quantity,
                quality_grade=quality_grade or 300
            )
            dbs.add(new_item)
        
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()

def get_ready_silk_plantations() -> list[SilkPlantation]:
    """Получить все готовые к сбору шёлковые плантации для уведомлений."""
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(SilkPlantation)
            .filter(SilkPlantation.status == 'ready')
            .all()
        )
    finally:
        dbs.close()

def get_money_leaderboard(limit: int = 10) -> list[dict]:
    """Получить топ игроков по количеству денег.
    
    Args:
        limit: Количество игроков в топе (по умолчанию 10)
        
    Returns:
        Список словарей с данными игроков: {'user_id', 'username', 'coins', 'position'}
    """
    dbs = SessionLocal()
    try:
        now_ts = int(time.time())
        players = (
            dbs.query(Player)
            .filter(Player.coins > 0)
            .outerjoin(
                UserBan,
                and_(
                    UserBan.user_id == Player.user_id,
                    or_(UserBan.banned_until == None, UserBan.banned_until > now_ts)
                )
            )
            .filter(UserBan.user_id == None)
            .order_by(Player.coins.desc())
            .limit(limit)
            .all()
        )
        
        result = []
        for position, player in enumerate(players, 1):
            result.append({
                'user_id': player.user_id,
                'username': player.username or 'Неизвестный игрок',
                'coins': player.coins,
                'position': position
            })
        
        return result
    except Exception:
        return []
    finally:
        dbs.close()

# --- Функции для управления групповыми настройками ---

def get_group_settings(chat_id: int) -> dict:
    """Получение настроек группы."""
    db = SessionLocal()
    try:
        group = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not group:
            return {'exists': False}
        return {
            'exists': True,
            'title': group.title,
            'is_enabled': group.is_enabled,
            'notify_disabled': getattr(group, 'notify_disabled', False),
            'auto_delete_enabled': getattr(group, 'auto_delete_enabled', False),
            'auto_delete_delay_minutes': getattr(group, 'auto_delete_delay_minutes', 5)
        }
    finally:
        db.close()

def update_group_settings(chat_id: int, notify_disabled: bool = None, auto_delete_enabled: bool = None) -> bool:
    """Обновление настроек группы. Возвращает True если успешно."""
    db = SessionLocal()
    try:
        group = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not group:
            return False
        
        if notify_disabled is not None:
            group.notify_disabled = notify_disabled
        if auto_delete_enabled is not None:
            group.auto_delete_enabled = auto_delete_enabled
        
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        db.close()

def get_groups_with_notifications_enabled() -> list[GroupChat]:
    """Получение всех групп, где уведомления не отключены (для notify_groups_job)."""
    db = SessionLocal()
    try:
        return db.query(GroupChat).filter(
            GroupChat.is_enabled == True,
            GroupChat.notify_disabled != True  # Включаем группы где поле не установлено или False
        ).all()
    finally:
        db.close()

def migrate_group_settings():
    """Миграция базы для добавления новых полей в таблицу group_chats."""
    db = SessionLocal()
    try:
        # Проверяем, существуют ли новые колонки
        try:
            db.execute(text("SELECT notify_disabled FROM group_chats LIMIT 1"))
            print("[MIGRATION] Group settings columns already exist")
            return
        except Exception:
            # Колонки не существуют, создаём
            pass
        
        print("[MIGRATION] Adding group settings columns...")
        
        # Добавляем новые колонки
        try:
            db.execute(text("ALTER TABLE group_chats ADD COLUMN notify_disabled BOOLEAN DEFAULT FALSE"))
            db.execute(text("ALTER TABLE group_chats ADD COLUMN auto_delete_enabled BOOLEAN DEFAULT FALSE"))
            db.commit()
            print("[MIGRATION] Successfully added group settings columns")
        except Exception as e:
            print(f"[MIGRATION] Error adding columns: {e}")
            db.rollback()
            
    except Exception as e:
        print(f"[MIGRATION] Migration failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


# --- Функции для работы с запланированными задачами автоудаления ---

def save_scheduled_auto_delete(chat_id: int, message_id: int, delete_at: int):
    """Сохраняет запланированную задачу автоудаления в БД."""
    db = SessionLocal()
    try:
        scheduled = ScheduledAutoDelete(
            chat_id=chat_id,
            message_id=message_id,
            delete_at=delete_at
        )
        db.add(scheduled)
        db.commit()
        return scheduled.id
    except Exception as e:
        print(f"[AUTO_DELETE_DB] Error saving scheduled delete: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_all_scheduled_auto_deletes():
    """Получает все запланированные задачи автоудаления."""
    db = SessionLocal()
    try:
        scheduled_list = db.query(ScheduledAutoDelete).all()
        return [(s.id, s.chat_id, s.message_id, s.delete_at) for s in scheduled_list]
    finally:
        db.close()


def delete_scheduled_auto_delete(scheduled_id: int):
    """Удаляет задачу автоудаления из БД по ID."""
    db = SessionLocal()
    try:
        db.query(ScheduledAutoDelete).filter(ScheduledAutoDelete.id == scheduled_id).delete()
        db.commit()
    except Exception as e:
        print(f"[AUTO_DELETE_DB] Error deleting scheduled task {scheduled_id}: {e}")
        db.rollback()
    finally:
        db.close()


def delete_scheduled_auto_delete_by_message(chat_id: int, message_id: int):
    """Удаляет задачу автоудаления из БД по chat_id и message_id."""
    db = SessionLocal()
    try:
        db.query(ScheduledAutoDelete).filter(
            ScheduledAutoDelete.chat_id == chat_id,
            ScheduledAutoDelete.message_id == message_id
        ).delete()
        db.commit()
    except Exception as e:
        print(f"[AUTO_DELETE_DB] Error deleting scheduled task for message {message_id}: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_old_scheduled_deletes():
    """Удаляет устаревшие записи (старше 24 часов от времени удаления)."""
    db = SessionLocal()
    try:
        cutoff = int(time.time()) - 24 * 60 * 60
        deleted = db.query(ScheduledAutoDelete).filter(ScheduledAutoDelete.delete_at < cutoff).delete()
        db.commit()
        if deleted > 0:
            print(f"[AUTO_DELETE_DB] Cleaned up {deleted} old scheduled tasks")
        return deleted
    except Exception as e:
        print(f"[AUTO_DELETE_DB] Error cleaning up old tasks: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


# --- Функции для работы с системой подарков ---

def log_gift(giver_id: int, recipient_id: int, drink_id: int, rarity: str, status: str):
    """Логирует подарок в историю."""
    db = SessionLocal()
    try:
        gift = GiftHistory(
            giver_id=giver_id,
            recipient_id=recipient_id,
            drink_id=drink_id,
            rarity=rarity,
            status=status
        )
        db.add(gift)
        db.commit()
        return gift.id
    except Exception as e:
        print(f"[GIFT_DB] Error logging gift: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_user_gifts_sent_today(user_id: int) -> int:
    """Возвращает количество подарков, отправленных пользователем сегодня."""
    db = SessionLocal()
    try:
        today_start = int(time.time()) - (int(time.time()) % 86400)  # начало текущего дня UTC
        count = db.query(GiftHistory).filter(
            GiftHistory.giver_id == user_id,
            GiftHistory.created_at >= today_start
        ).count()
        return count
    finally:
        db.close()


def get_user_last_gift_time(user_id: int) -> int:
    """Возвращает timestamp последнего подарка пользователя или 0."""
    db = SessionLocal()
    try:
        last_gift = db.query(GiftHistory).filter(
            GiftHistory.giver_id == user_id
        ).order_by(GiftHistory.created_at.desc()).first()
        return last_gift.created_at if last_gift else 0
    finally:
        db.close()


def check_consecutive_gifts(giver_id: int, recipient_id: int, limit: int = 10) -> bool:
    """
    Проверяет, дарил ли giver_id последние N раз подряд recipient_id.
    Возвращает True если превышен лимит (нужна блокировка).
    """
    db = SessionLocal()
    try:
        # Берем последние 'limit' подарков от дарителя
        recent_gifts = db.query(GiftHistory).filter(
            GiftHistory.giver_id == giver_id
        ).order_by(GiftHistory.created_at.desc()).limit(limit).all()
        
        if len(recent_gifts) < limit:
            return False  # Недостаточно подарков для проверки
        
        # Проверяем, все ли они были одному получателю
        return all(g.recipient_id == recipient_id for g in recent_gifts)
    finally:
        db.close()


def add_gift_restriction(user_id: int, reason: str, blocked_until: int = None, blocked_by: int = None):
    """Добавляет блокировку на дарение подарков."""
    db = SessionLocal()
    try:
        # Проверяем, нет ли уже блокировки
        existing = db.query(GiftRestriction).filter(GiftRestriction.user_id == user_id).first()
        if existing:
            # Обновляем существующую
            existing.reason = reason
            existing.blocked_at = int(time.time())
            existing.blocked_until = blocked_until
            existing.blocked_by = blocked_by
        else:
            # Создаем новую
            restriction = GiftRestriction(
                user_id=user_id,
                reason=reason,
                blocked_until=blocked_until,
                blocked_by=blocked_by
            )
            db.add(restriction)
        db.commit()
        return True
    except Exception as e:
        print(f"[GIFT_DB] Error adding restriction: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def is_user_gift_restricted(user_id: int) -> tuple[bool, str]:
    """
    Проверяет, заблокирован ли пользователь для дарения.
    Возвращает (True/False, причина).
    """
    db = SessionLocal()
    try:
        restriction = db.query(GiftRestriction).filter(GiftRestriction.user_id == user_id).first()
        if not restriction:
            return (False, "")
        
        # Проверяем, не истекла ли блокировка
        if restriction.blocked_until is not None:
            if int(time.time()) > restriction.blocked_until:
                # Блокировка истекла, удаляем её
                db.delete(restriction)
                db.commit()
                return (False, "")
        
        return (True, restriction.reason or "Нарушение правил дарения")
    except Exception as e:
        print(f"[GIFT_DB] Error checking restriction: {e}")
        return (False, "")
    finally:
        db.close()


def remove_gift_restriction(user_id: int):
    """Снимает блокировку с пользователя."""
    db = SessionLocal()
    try:
        db.query(GiftRestriction).filter(GiftRestriction.user_id == user_id).delete()
        db.commit()
        return True
    except Exception as e:
        print(f"[GIFT_DB] Error removing restriction: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_gift_stats(user_id: int) -> dict:
    """Возвращает статистику подарков пользователя."""
    db = SessionLocal()
    try:
        sent = db.query(GiftHistory).filter(GiftHistory.giver_id == user_id).count()
        received = db.query(GiftHistory).filter(
            GiftHistory.recipient_id == user_id,
            GiftHistory.status == 'accepted'
        ).count()
        return {
            'sent': sent,
            'received': received
        }
    finally:
        db.close()


def update_player_stats(user_id: int, **kwargs):
    """Обновляет статистику игрока (для казино и других систем)."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        # Обновляем только переданные поля
        for key, value in kwargs.items():
            if hasattr(player, key):
                setattr(player, key, value)
        
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error updating player stats: {e}")
        db.rollback()
        return False
    finally:
        db.close()


# --- Функции статистики для админ панели ---

def get_total_users_count() -> int:
    """Возвращает общее количество пользователей."""
    db = SessionLocal()
    try:
        return db.query(Player).count()
    except Exception:
        return 0
    finally:
        db.close()


def get_active_vip_count() -> int:
    """Возвращает количество пользователей с активным VIP."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        return db.query(Player).filter(Player.vip_until > current_time).count()
    except Exception:
        return 0
    finally:
        db.close()


def get_active_vip_plus_count() -> int:
    """Возвращает количество пользователей с активным VIP+."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        return db.query(Player).filter(Player.vip_plus_until > current_time).count()
    except Exception:
        return 0
    finally:
        db.close()


def count_all_drinks() -> int:
    """Возвращает общее количество уникальных напитков в базе данных."""
    db = SessionLocal()
    try:
        return db.query(EnergyDrink).count()
    except Exception as e:
        print(f"[DB] Error counting drinks: {e}")
        return 0
    finally:
        db.close()


def get_total_collection_points() -> int:
    """
    Возвращает общее количество очков коллекции (100% прогресса).
    Логика:
      - Special напитки: 1 очко (считаются как 1 уникальный предмет)
      - Остальные (Basic, Medium, Elite, Absolute, Majestic): 5 очков (по 1 за каждую редкость)
    """
    db = SessionLocal()
    try:
        # Получаем все напитки
        drinks = db.query(EnergyDrink).all()
        total_points = 0
        for drink in drinks:
            if drink.is_special:
                total_points += 1
            else:
                total_points += 5
        return total_points
    except Exception:
        return 0
    finally:
        db.close()


def get_total_drinks_count() -> int:
    """Возвращает общее количество напитков в базе."""
    return count_all_drinks()


def get_total_inventory_items() -> int:
    """Возвращает общее количество предметов в инвентарях всех игроков."""
    db = SessionLocal()
    try:
        return db.query(func.sum(InventoryItem.quantity)).scalar() or 0
    except Exception:
        return 0
    finally:
        db.close()


def get_active_users_today() -> int:
    """Возвращает количество активных пользователей за последние 24 часа."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        one_day_ago = current_time - 86400
        return db.query(Player).filter(Player.last_search > one_day_ago).count()
    except Exception:
        return 0
    finally:
        db.close()


def get_active_users_week() -> int:
    """Возвращает количество активных пользователей за последнюю неделю."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        one_week_ago = current_time - 604800
        return db.query(Player).filter(Player.last_search > one_week_ago).count()
    except Exception:
        return 0
    finally:
        db.close()


def get_total_coins_in_system() -> int:
    """Возвращает общее количество монет в системе."""
    db = SessionLocal()
    try:
        return db.query(func.sum(Player.coins)).scalar() or 0
    except Exception:
        return 0
    finally:
        db.close()


def get_active_promo_count() -> int:
    """Возвращает количество активных промокодов."""
    db = SessionLocal()
    try:
        now_ts = int(time.time())
        return db.query(Promo).filter(
            Promo.active == True,
            ((Promo.expires_at == None) | (Promo.expires_at > now_ts))
        ).count()
    except Exception:
        return 0
    finally:
        db.close()

def get_group_settings(chat_id: int) -> dict:
    """Возвращает настройки группы. Если записи нет — возвращает значения по умолчанию."""
    db = SessionLocal()
    try:
        row = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not row:
            return {
                'notify_disabled': False,
                'auto_delete_enabled': False,
                'auto_delete_delay_minutes': 5,
                'title': None,
            }
        return {
            'notify_disabled': bool(row.notify_disabled),
            'auto_delete_enabled': bool(row.auto_delete_enabled),
            'auto_delete_delay_minutes': int(row.auto_delete_delay_minutes or 5),
            'title': row.title,
        }
    finally:
        db.close()

def set_group_settings(chat_id: int, **kwargs) -> bool:
    """Создаёт/обновляет запись настроек для группы."""
    db = SessionLocal()
    try:
        row = db.query(GroupChat).filter(GroupChat.chat_id == chat_id).first()
        if not row:
            row = GroupChat(chat_id=chat_id)
            db.add(row)
        # Обновляем поддерживаемые поля
        for key in ('title', 'notify_disabled', 'auto_delete_enabled', 'auto_delete_delay_minutes', 'is_enabled'):
            if key in kwargs:
                setattr(row, key, kwargs[key])
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def save_scheduled_auto_delete(chat_id: int, message_id: int, delete_at: int) -> int:
    """Сохраняет задачу автоудаления и возвращает её ID."""
    db = SessionLocal()
    try:
        rec = ScheduledAutoDelete(chat_id=chat_id, message_id=message_id, delete_at=delete_at)
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return int(rec.id)
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()

def delete_scheduled_auto_delete(scheduled_id: int) -> bool:
    """Удаляет сохранённую задачу автоудаления по её ID."""
    db = SessionLocal()
    try:
        db.query(ScheduledAutoDelete).filter(ScheduledAutoDelete.id == int(scheduled_id)).delete()
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_banned_users_count() -> int:
    """Возвращает количество забаненных пользователей."""
    db = SessionLocal()
    try:
        now_ts = int(time.time())
        return db.query(UserBan).filter((UserBan.banned_until == None) | (UserBan.banned_until > now_ts)).count()
    except Exception:
        return 0
    finally:
        db.close()

def is_user_banned(user_id: int) -> bool:
    db = SessionLocal()
    try:
        try:
            if is_protected_user(int(user_id)):
                try:
                    recp = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
                    if recp:
                        db.delete(recp)
                        db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                return False
        except Exception:
            pass
        now_ts = int(time.time())
        rec = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
        if not rec:
            return False
        until = getattr(rec, 'banned_until', None)
        return True if (until is None or int(until) > now_ts) else False
    finally:
        db.close()

def ban_user(user_id: int, banned_by: int | None = None, reason: str | None = None, duration_seconds: int | None = None) -> bool:
    db = SessionLocal()
    try:
        if is_protected_user(int(user_id)):
            return False
        rec = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
        now_ts = int(time.time())
        until = None
        if duration_seconds and int(duration_seconds) > 0:
            until = now_ts + int(duration_seconds)
        if rec:
            rec.reason = reason
            rec.banned_at = now_ts
            rec.banned_until = until
            rec.banned_by = banned_by
        else:
            rec = UserBan(user_id=int(user_id), reason=reason, banned_at=now_ts, banned_until=until, banned_by=banned_by)
            db.add(rec)
        db.commit()
        try:
            insert_moderation_log(actor_id=int(banned_by or 0), action='ban_user', request_id=None, target_id=int(user_id), details=reason)
        except Exception:
            pass
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def unban_user(user_id: int, unbanned_by: int | None = None) -> bool:
    db = SessionLocal()
    try:
        rec = db.query(UserBan).filter(UserBan.user_id == int(user_id)).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        try:
            insert_moderation_log(actor_id=int(unbanned_by or 0), action='unban_user', request_id=None, target_id=int(user_id), details=None)
        except Exception:
            pass
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def list_active_bans(limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        now_ts = int(time.time())
        rows = (
            db.query(UserBan)
            .filter((UserBan.banned_until == None) | (UserBan.banned_until > now_ts))
            .order_by(UserBan.banned_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                'user_id': int(row.user_id),
                'reason': row.reason,
                'banned_at': int(row.banned_at or 0),
                'banned_until': int(row.banned_until or 0) if row.banned_until else None,
                'banned_by': int(row.banned_by or 0) if row.banned_by else None,
            }
            for row in rows
        ]
    except Exception:
        return []
    finally:
        db.close()

def unban_protected_users() -> int:
    dbs = SessionLocal()
    try:
        protected_ids = set()
        for r in dbs.query(AdminUser).all():
            try:
                protected_ids.add(int(getattr(r, 'user_id', 0) or 0))
            except Exception:
                continue
        try:
            names = [u.lower() for u in ADMIN_USERNAMES] if ADMIN_USERNAMES else []
        except Exception:
            names = []
        if names:
            creators = dbs.query(Player).filter(func.lower(Player.username).in_(names)).all()
            for p in creators:
                try:
                    protected_ids.add(int(getattr(p, 'user_id', 0) or 0))
                except Exception:
                    continue
        removed = 0
        for uid in protected_ids:
            if not uid:
                continue
            rec = dbs.query(UserBan).filter(UserBan.user_id == int(uid)).first()
            if rec:
                dbs.delete(rec)
                removed += 1
        if removed:
            dbs.commit()
        return removed
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return 0
    finally:
        dbs.close()

def add_warning(user_id: int, issued_by: int | None = None, reason: str | None = None) -> bool:
    db = SessionLocal()
    try:
        row = UserWarning(user_id=int(user_id), reason=reason, issued_by=issued_by)
        db.add(row)
        db.commit()
        try:
            insert_moderation_log(actor_id=int(issued_by or 0), action='warn_user', request_id=None, target_id=int(user_id), details=reason)
        except Exception:
            pass
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def get_warnings(user_id: int, limit: int = 20) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(UserWarning)
            .filter(UserWarning.user_id == int(user_id))
            .order_by(UserWarning.issued_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                'id': int(row.id),
                'user_id': int(row.user_id),
                'reason': row.reason,
                'issued_at': int(row.issued_at or 0),
                'issued_by': int(row.issued_by or 0) if row.issued_by else None,
            }
            for row in rows
        ]
    except Exception:
        return []
    finally:
        db.close()

def clear_warnings(user_id: int) -> int:
    db = SessionLocal()
    try:
        deleted = db.query(UserWarning).filter(UserWarning.user_id == int(user_id)).delete()
        db.commit()
        return int(deleted or 0)
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()

def get_player(user_id: int) -> Player | None:
    db = SessionLocal()
    try:
        return db.query(Player).filter(Player.user_id == int(user_id)).first()
    finally:
        db.close()

def get_moderation_logs(limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(ModerationLog).order_by(ModerationLog.ts.desc()).limit(limit).all()
        return [
            {
                'id': int(r.id),
                'ts': int(r.ts or 0),
                'actor_id': int(r.actor_id or 0),
                'action': r.action,
                'request_id': int(r.request_id or 0) if r.request_id else None,
                'target_id': int(r.target_id or 0) if r.target_id else None,
                'details': r.details,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        db.close()

def get_moderation_logs_by_user(target_id: int, limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ModerationLog)
            .filter(ModerationLog.target_id == int(target_id))
            .order_by(ModerationLog.ts.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                'id': int(r.id),
                'ts': int(r.ts or 0),
                'actor_id': int(r.actor_id or 0),
                'action': r.action,
                'request_id': int(r.request_id or 0) if r.request_id else None,
                'target_id': int(r.target_id or 0) if r.target_id else None,
                'details': r.details,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        db.close()


def get_active_events_count() -> int:
    """Возвращает количество активных событий."""
    # TODO: Реализовать после создания таблицы событий
    return 0


def get_bot_statistics() -> dict:
    """Возвращает детальную статистику бота."""
    db = SessionLocal()
    try:
        current_time = int(time.time())
        one_day_ago = current_time - 86400
        one_week_ago = current_time - 604800
        
        # Общая статистика
        total_users = db.query(Player).count()
        total_drinks = db.query(EnergyDrink).count()
        total_inventory_items = db.query(func.sum(InventoryItem.quantity)).scalar() or 0
        total_coins = db.query(func.sum(Player.coins)).scalar() or 0
        
        # VIP статистика
        active_vip = db.query(Player).filter(Player.vip_until > current_time).count()
        active_vip_plus = db.query(Player).filter(Player.vip_plus_until > current_time).count()
        
        # Активность
        active_today = db.query(Player).filter(Player.last_search > one_day_ago).count()
        active_week = db.query(Player).filter(Player.last_search > one_week_ago).count()
        
        # Покупки
        total_purchases = db.query(PurchaseReceipt).count()
        purchases_today = db.query(PurchaseReceipt).filter(PurchaseReceipt.purchased_at > one_day_ago).count()
        
        # Топ игроков по монетам
        top_coins = db.query(Player).order_by(Player.coins.desc()).limit(10).all()
        
        # Топ игроков по количеству напитков
        top_drinks = (
            db.query(
                Player.user_id,
                Player.username,
                func.sum(InventoryItem.quantity).label('total_drinks')
            )
            .join(InventoryItem, Player.user_id == InventoryItem.player_id)
            .group_by(Player.user_id, Player.username)
            .order_by(func.sum(InventoryItem.quantity).desc())
            .limit(10)
            .all()
        )
        
        return {
            'total_users': total_users,
            'total_drinks': total_drinks,
            'total_inventory_items': int(total_inventory_items),
            'total_coins': int(total_coins),
            'active_vip': active_vip,
            'active_vip_plus': active_vip_plus,
            'active_today': active_today,
            'active_week': active_week,
            'total_purchases': total_purchases,
            'purchases_today': purchases_today,
            'top_coins': [(p.user_id, p.username, p.coins) for p in top_coins],
            'top_drinks': [(user_id, username, int(total)) for user_id, username, total in top_drinks]
        }
    except Exception as e:
        print(f"[DB] Error getting bot statistics: {e}")
        return {}
    finally:
        db.close()


def get_all_users_for_broadcast(limit: int = None) -> list[int]:
    """Возвращает список всех user_id для рассылки."""
    db = SessionLocal()
    try:
        query = db.query(Player.user_id)
        if limit:
            query = query.limit(limit)
        return [row.user_id for row in query.all()]
    except Exception:
        return []
    finally:
        db.close()


def wipe_all_except_drinks() -> bool:
    dbs = SessionLocal()
    try:
        dbs.query(InventoryItem).delete()
        dbs.query(ShopOffer).delete()
        dbs.query(PendingAddition).delete()
        dbs.query(PendingDeletion).delete()
        dbs.query(PendingEdit).delete()
        dbs.query(ModerationLog).delete()
        dbs.query(UserWarning).delete()
        dbs.query(UserBan).delete()
        dbs.query(ActionLog).delete()
        dbs.query(PromoUsage).delete()
        dbs.query(Promo).delete()
        dbs.query(BotSetting).delete()
        dbs.query(TgPremiumStock).delete()
        dbs.query(PurchaseReceipt).delete()
        dbs.query(BonusStock).delete()
        dbs.query(BoostHistory).delete()
        dbs.query(SilkInventory).delete()
        dbs.query(SilkTransaction).delete()
        dbs.query(SilkPlantation).delete()
        dbs.query(BedFertilizer).delete()
        dbs.query(PlantationBed).delete()
        dbs.query(FertilizerInventory).delete()
        dbs.query(SeedInventory).delete()
        dbs.query(SeedType).delete()
        dbs.query(Fertilizer).delete()
        dbs.query(CommunityParticipant).delete()
        dbs.query(CommunityContributionLog).delete()
        dbs.query(CommunityProjectState).delete()
        dbs.query(CommunityPlantation).delete()
        dbs.query(DrinkDiscoveryStats).delete()
        dbs.query(GiftHistory).delete()
        dbs.query(GiftRestriction).delete()
        dbs.query(ScheduledAutoDelete).delete()
        dbs.query(GroupChat).delete()
        dbs.query(AdminUser).delete()
        dbs.query(Player).delete()
        dbs.commit()
        return True
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return False
    finally:
        dbs.close()


def set_vip_for_user(user_id: int, duration_seconds: int) -> bool:
    """Устанавливает или продлевает VIP статус пользователю."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        current_time = int(time.time())
        current_vip = int(getattr(player, 'vip_until', 0) or 0)
        
        # Если VIP активен, продлеваем, иначе устанавливаем новый
        if current_vip > current_time:
            player.vip_until = current_vip + duration_seconds
        else:
            player.vip_until = current_time + duration_seconds
        
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error setting VIP: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def set_vip_plus_for_user(user_id: int, duration_seconds: int) -> bool:
    """Устанавливает или продлевает VIP+ статус пользователю."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        current_time = int(time.time())
        current_vip_plus = int(getattr(player, 'vip_plus_until', 0) or 0)
        
        # Если VIP+ активен, продлеваем, иначе устанавливаем новый
        if current_vip_plus > current_time:
            player.vip_plus_until = current_vip_plus + duration_seconds
        else:
            player.vip_plus_until = current_time + duration_seconds
        
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error setting VIP+: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def remove_vip_from_user(user_id: int) -> bool:
    """Удаляет VIP статус у пользователя."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        player.vip_until = 0
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error removing VIP: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def remove_vip_plus_from_user(user_id: int) -> bool:
    """Удаляет VIP+ статус у пользователя."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            return False
        
        player.vip_plus_until = 0
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error removing VIP+: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_stock_info() -> dict:
    """Возвращает информацию о складе всех бонусов."""
    db = SessionLocal()
    try:
        stocks = db.query(BonusStock).all()
        return {stock.kind: int(stock.stock or 0) for stock in stocks}
    except Exception as e:
        print(f"[DB] Error getting stock info: {e}")
        import traceback
        traceback.print_exc()
        return {}


# --- Функции для работы с логами ---

def log_action(user_id: int, username: str | None, action_type: str, action_details: str | None = None, amount: int | None = None, success: bool = True):
    """Записывает действие в лог."""
    db = SessionLocal()
    try:
        log_entry = ActionLog(
            user_id=user_id,
            username=username,
            action_type=action_type,
            action_details=action_details,
            amount=amount,
            success=success
        )
        db.add(log_entry)
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error logging action: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_recent_logs(limit: int = 50):
    """Возвращает последние N записей логов."""
    db = SessionLocal()
    try:
        logs = db.query(ActionLog).order_by(ActionLog.timestamp.desc()).limit(limit).all()
        return [
            {
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'username': log.username or 'Unknown',
                'action_type': log.action_type,
                'action_details': log.action_details,
                'amount': log.amount,
                'success': log.success
            }
            for log in logs
        ]
    except Exception as e:
        print(f"[DB] Error getting recent logs: {e}")
        return []
    finally:
        db.close()


def get_logs_by_type(action_type: str, limit: int = 50):
    """Возвращает логи определенного типа."""
    db = SessionLocal()
    try:
        logs = db.query(ActionLog).filter(ActionLog.action_type == action_type).order_by(ActionLog.timestamp.desc()).limit(limit).all()
        return [
            {
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'username': log.username or 'Unknown',
                'action_type': log.action_type,
                'action_details': log.action_details,
                'amount': log.amount,
                'success': log.success
            }
            for log in logs
        ]
    except Exception as e:
        print(f"[DB] Error getting logs by type: {e}")
        return []
    finally:
        db.close()


def get_user_logs(user_id: int, limit: int = 50):
    """Возвращает логи конкретного пользователя."""
    db = SessionLocal()
    try:
        logs = db.query(ActionLog).filter(ActionLog.user_id == user_id).order_by(ActionLog.timestamp.desc()).limit(limit).all()
        return [
            {
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'username': log.username or 'Unknown',
                'action_type': log.action_type,
                'action_details': log.action_details,
                'amount': log.amount,
                'success': log.success
            }
            for log in logs
        ]
    except Exception as e:
        print(f"[DB] Error getting user logs: {e}")
        return []
    finally:
        db.close()


def get_error_logs(limit: int = 50):
    """Возвращает логи с ошибками."""
    db = SessionLocal()
    try:
        logs = db.query(ActionLog).filter(ActionLog.success == False).order_by(ActionLog.timestamp.desc()).limit(limit).all()
        return [
            {
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'username': log.username or 'Unknown',
                'action_type': log.action_type,
                'action_details': log.action_details,
                'amount': log.amount,
                'success': log.success
            }
            for log in logs
        ]
    except Exception as e:
        print(f"[DB] Error getting error logs: {e}")
        return []
    finally:
        db.close()


# --- Функции для управления энергетиками ---

def get_all_drinks_paginated(page: int = 1, page_size: int = 20):
    """Возвращает список всех напитков с пагинацией."""
    db = SessionLocal()
    try:
        offset = (page - 1) * page_size
        drinks = db.query(EnergyDrink).order_by(EnergyDrink.name).offset(offset).limit(page_size).all()
        total = db.query(EnergyDrink).count()
        
        return {
            'drinks': [
                {
                    'id': drink.id,
                    'name': drink.name,
                    'description': drink.description,
                    'is_special': drink.is_special,
                    'has_image': bool(drink.image_path)
                }
                for drink in drinks
            ],
            'total': total,
            'page': page,
            'total_pages': (total + page_size - 1) // page_size
        }
    except Exception as e:
        print(f"[DB] Error getting drinks: {e}")
        return {'drinks': [], 'total': 0, 'page': 1, 'total_pages': 0}
    finally:
        db.close()


def search_drinks_by_name(search_query: str):
    """Ищет напитки по названию."""
    db = SessionLocal()
    try:
        drinks = db.query(EnergyDrink).filter(EnergyDrink.name.ilike(f'%{search_query}%')).order_by(EnergyDrink.name).limit(50).all()
        return [
            {
                'id': drink.id,
                'name': drink.name,
                'description': drink.description,
                'is_special': drink.is_special,
                'has_image': bool(drink.image_path)
            }
            for drink in drinks
        ]
    except Exception as e:
        print(f"[DB] Error searching drinks: {e}")
        return []
    finally:
        db.close()


def get_drink_by_id(drink_id: int):
    """Получает напиток по ID."""
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if drink:
            return {
                'id': drink.id,
                'name': drink.name,
                'description': drink.description,
                'is_special': drink.is_special,
                'image_path': drink.image_path,
                'has_image': bool(drink.image_path)
            }
        return None
    except Exception as e:
        print(f"[DB] Error getting drink by id: {e}")
        return None
    finally:
        db.close()


def admin_add_drink(name: str, description: str, is_special: bool = False, image_path: str | None = None) -> bool:
    """Админ добавляет напиток напрямую."""
    db = SessionLocal()
    try:
        # Проверяем, не существует ли уже
        existing = db.query(EnergyDrink).filter(EnergyDrink.name == name).first()
        if existing:
            return False
        
        drink = EnergyDrink(name=name, description=description, is_special=is_special, image_path=image_path)
        db.add(drink)
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error adding drink: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def admin_update_drink(drink_id: int, name: str | None = None, description: str | None = None, is_special: bool | None = None) -> bool:
    """Админ обновляет информацию о напитке."""
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return False
        
        if name is not None:
            drink.name = name
        if description is not None:
            drink.description = description
        if is_special is not None:
            drink.is_special = is_special
        
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error updating drink: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def admin_update_drink_image(drink_id: int, image_path: str) -> bool:
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return False
        drink.image_path = image_path
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error updating drink image: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def admin_delete_drink(drink_id: int) -> bool:
    """Админ удаляет напиток."""
    db = SessionLocal()
    try:
        drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
        if not drink:
            return False
        
        # Удаляем все записи из инвентаря с этим напитком
        db.query(InventoryItem).filter(InventoryItem.drink_id == drink_id).delete()
        
        # Удаляем напиток
        db.delete(drink)
        db.commit()
        return True
    except Exception as e:
        print(f"[DB] Error deleting drink: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_users_with_level2_farmers() -> list[int]:
    """Возвращает список ID пользователей, у которых есть Селюк Фермер 2 уровня (или выше) и он включен."""
    dbs = SessionLocal()
    try:
        # Ищем селюков типа 'farmer', уровень >= 2, is_enabled = True
        # Возвращаем список owner_id
        rows = (
            dbs.query(Selyuk.owner_id)
            .filter(Selyuk.type == 'farmer')
            .filter(Selyuk.level >= 2)
            .filter(Selyuk.is_enabled == True)
            .all()
        )
        return [r[0] for r in rows]
    except Exception as e:
        print(f"[DB] Error getting users with level 2 farmers: {e}")
        return []
    finally:
        dbs.close()


def increment_selyuk_fragments(user_id: int, amount: int = 1) -> int:
    """Начисляет фрагменты Селюка пользователю. Возвращает новое количество."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if player:
            current = int(getattr(player, 'selyuk_fragments', 0) or 0)
            player.selyuk_fragments = current + amount
            db.commit()
            db.refresh(player)
            return player.selyuk_fragments
        return 0
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()