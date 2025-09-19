# file: database.py

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, BigInteger, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload
import re
from sqlalchemy import text, func
import time
import random
from constants import RARITIES, RECEIVER_PRICES, RECEIVER_COMMISSION, SHOP_PRICES

# --- Настройка базы данных ---
DATABASE_FILE = "bot_data.db"
engine = create_engine(f"sqlite:///{DATABASE_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    inventory = relationship("InventoryItem", back_populates="owner", cascade="all, delete-orphan")

class EnergyDrink(Base):
    __tablename__ = 'energy_drinks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    image_path = Column(String, nullable=True)
    is_special = Column(Boolean, default=False)

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

# --- Группы для рассылок ---

class GroupChat(Base):
    __tablename__ = 'group_chats'
    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=True)
    is_enabled = Column(Boolean, default=True, index=True)
    last_notified = Column(Integer, default=0)

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

    __table_args__ = (
        Index('idx_plantation_owner', 'owner_id'),
        Index('idx_plantation_owner_bed', 'owner_id', 'bed_index'),
        Index('idx_plantation_fertilizer', 'fertilizer_id'),
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


# --- Функции для взаимодействия с базой данных ---

def create_db_and_tables():
    """Создает файл базы данных и все таблицы, если их нет."""
    Base.metadata.create_all(bind=engine)
    print("База данных и таблицы успешно созданы.")

def get_or_create_player(user_id, username):
    """Возвращает игрока по ID. Если его нет, создает нового."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            player = Player(user_id=user_id, username=username)
            db.add(player)
            db.commit()
            db.refresh(player)
            print(f"Создан новый игрок: {username} ({user_id})")
        return player
    finally:
        db.close()


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
            drinks = dbs.query(EnergyDrink).all() or []
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


def ensure_default_seed_types() -> int:
    """Создаёт базовые типы семян, если их нет. Возвращает количество добавленных записей.
    Логика: берём первые 3 энергетика и делаем по семени на каждый.
    Если энергетиков мало, создаём столько, сколько есть.
    """
    dbs = SessionLocal()
    try:
        # Миграция: обновляем старую цену 400 -> 15 для уже существующих типов семян
        try:
            updated = (
                dbs.query(SeedType)
                .filter(SeedType.price_coins == 400)
                .update({SeedType.price_coins: 15}, synchronize_session=False)
            )
            if updated:
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
        defaults = [
            {"price": 15, "grow": 3600, "water": 1200, "ymin": 1, "ymax": 2},
            {"price": 30, "grow": 5400, "water": 1200, "ymin": 1, "ymax": 3},
            {"price": 60, "grow": 7200, "water": 1800, "ymin": 2, "ymax": 4},
        ]
        for i, drink in enumerate(drinks):
            cfg = defaults[min(i, len(defaults) - 1)]
            st = SeedType(
                name=f"Семена {drink.name}",
                description=f"Семена для выращивания напитка '{drink.name}'.",
                drink_id=drink.id,
                price_coins=cfg["price"],
                grow_time_sec=cfg["grow"],
                water_interval_sec=cfg["water"],
                yield_min=cfg["ymin"],
                yield_max=cfg["ymax"],
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
        # Создаём новый тип семян с базовыми параметрами
        st_new = SeedType(
            name=expected_name,
            description=f"Семена для выращивания напитка '{drink.name}'.",
            drink_id=drink.id,
            price_coins=15,
            grow_time_sec=5400,
            water_interval_sec=1200,
            yield_min=1,
            yield_max=3,
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


def list_community_plantations(limit: int = 20) -> list[CommunityPlantation]:
    dbs = SessionLocal()
    try:
        return list(
            dbs.query(CommunityPlantation)
            .order_by(CommunityPlantation.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        dbs.close()


def get_community_plantation_by_id(pid: int) -> CommunityPlantation | None:
    dbs = SessionLocal()
    try:
        return dbs.query(CommunityPlantation).filter(CommunityPlantation.id == pid).first()
    finally:
        dbs.close()


def create_community_plantation(title: str, description: str | None, created_by: int | None, goal_amount: int | None = None, reward_total_coins: int | None = None) -> CommunityPlantation | None:
    dbs = SessionLocal()
    try:
        cp = CommunityPlantation(title=title, description=description, created_by=created_by)
        dbs.add(cp)
        dbs.commit()
        dbs.refresh(cp)
        # создаём состояние проекта по умолчанию
        try:
            st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == cp.id).first()
            if not st:
                st = CommunityProjectState(
                    project_id=cp.id,
                    goal_amount=int(goal_amount) if goal_amount is not None else 1000,
                    progress_amount=0,
                    status='active',
                    reward_total_coins=int(reward_total_coins) if reward_total_coins is not None else 250,
                )
                dbs.add(st)
                dbs.commit()
        except Exception:
            try:
                dbs.rollback()
            except Exception:
                pass
        return cp
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return None
    finally:
        dbs.close()


def ensure_community_project_state(project_id: int, default_goal: int = 1000, default_reward_total: int = 250) -> CommunityProjectState | None:
    dbs = SessionLocal()
    try:
        st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).first()
        if st:
            return st
        # убеждаемся, что проект существует
        proj = dbs.query(CommunityPlantation).filter(CommunityPlantation.id == project_id).first()
        if not proj:
            return None
        st = CommunityProjectState(project_id=project_id, goal_amount=int(default_goal), progress_amount=0, status='active', reward_total_coins=int(default_reward_total))
        dbs.add(st)
        dbs.commit()
        return st
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return None
    finally:
        dbs.close()


def get_community_project_state(project_id: int) -> CommunityProjectState | None:
    dbs = SessionLocal()
    try:
        return dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).first()
    finally:
        dbs.close()


def get_community_participant(project_id: int, user_id: int) -> CommunityParticipant | None:
    dbs = SessionLocal()
    try:
        return (
            dbs.query(CommunityParticipant)
            .filter(CommunityParticipant.project_id == project_id, CommunityParticipant.user_id == user_id)
            .first()
        )
    finally:
        dbs.close()


def join_community_project(project_id: int, user_id: int) -> dict:
    """Вступление в проект. Возвращает {ok, reason?}."""
    dbs = SessionLocal()
    try:
        proj = dbs.query(CommunityPlantation).filter(CommunityPlantation.id == project_id).first()
        if not proj:
            return {"ok": False, "reason": "no_project"}
        # ensure state
        st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).first()
        if not st:
            st = CommunityProjectState(project_id=project_id, goal_amount=1000, progress_amount=0, status='active', reward_total_coins=250)
            dbs.add(st)
            dbs.commit()
        # ensure player exists
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id))
            dbs.add(player)
            dbs.commit()
        # create participant if not exists
        row = (
            dbs.query(CommunityParticipant)
            .filter(CommunityParticipant.project_id == project_id, CommunityParticipant.user_id == user_id)
            .first()
        )
        if row:
            return {"ok": True}
        row = CommunityParticipant(project_id=project_id, user_id=user_id)
        dbs.add(row)
        dbs.commit()
        return {"ok": True}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def contribute_to_community_project(project_id: int, user_id: int, amount: int) -> dict:
    """Взнос в проект (в септимах). Возвращает {ok, reason?, coins_left?, progress?, goal?, status?}."""
    if int(amount) <= 0:
        return {"ok": False, "reason": "invalid_amount"}
    dbs = SessionLocal()
    try:
        st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).with_for_update(read=False).first()
        if not st:
            # автоинициализация
            st = CommunityProjectState(project_id=project_id, goal_amount=1000, progress_amount=0, status='active', reward_total_coins=250)
            dbs.add(st)
            dbs.commit()
            dbs.refresh(st)
        if st.status == 'completed':
            return {"ok": False, "reason": "completed"}
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id), coins=0)
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        current = int(player.coins or 0)
        if current < int(amount):
            return {"ok": False, "reason": "not_enough_coins"}
        # списываем у игрока
        player.coins = current - int(amount)
        # участник
        part = (
            dbs.query(CommunityParticipant)
            .filter(CommunityParticipant.project_id == project_id, CommunityParticipant.user_id == user_id)
            .with_for_update(read=False)
            .first()
        )
        if not part:
            part = CommunityParticipant(project_id=project_id, user_id=user_id, contributed_amount=0, reward_claimed=False)
            dbs.add(part)
            dbs.commit()
            dbs.refresh(part)
        part.contributed_amount = int(part.contributed_amount or 0) + int(amount)
        # прогресс проекта
        st.progress_amount = int(st.progress_amount or 0) + int(amount)
        if int(st.progress_amount) >= int(st.goal_amount or 0) and st.status != 'completed':
            st.status = 'completed'
        # лог
        try:
            log = CommunityContributionLog(project_id=project_id, user_id=user_id, amount=int(amount))
            dbs.add(log)
        except Exception:
            pass
        dbs.commit()
        return {
            "ok": True,
            "coins_left": int(player.coins),
            "progress": int(st.progress_amount),
            "goal": int(st.goal_amount or 0),
            "status": st.status,
        }
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()


def get_community_stats(project_id: int) -> dict:
    """Статистика проекта: {goal, progress, participants, status}."""
    dbs = SessionLocal()
    try:
        st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).first()
        goal = int(getattr(st, 'goal_amount', 0) or 0) if st else 0
        progress = int(getattr(st, 'progress_amount', 0) or 0) if st else 0
        status = getattr(st, 'status', 'active') if st else 'active'
        participants = (
            dbs.query(CommunityParticipant)
            .filter(CommunityParticipant.project_id == project_id)
            .count()
        )
        return {"goal": goal, "progress": progress, "participants": int(participants), "status": status}
    finally:
        dbs.close()


def claim_community_reward(project_id: int, user_id: int) -> dict:
    """Выдача награды участнику. Пропорционально его взносу. Возвращает {ok, reason?, claimed_coins?, coins_after?}."""
    dbs = SessionLocal()
    try:
        st = dbs.query(CommunityProjectState).filter(CommunityProjectState.project_id == project_id).with_for_update(read=False).first()
        if not st:
            return {"ok": False, "reason": "no_state"}
        if st.status != 'completed':
            return {"ok": False, "reason": "not_completed"}
        part = (
            dbs.query(CommunityParticipant)
            .filter(CommunityParticipant.project_id == project_id, CommunityParticipant.user_id == user_id)
            .with_for_update(read=False)
            .first()
        )
        if not part:
            return {"ok": False, "reason": "not_participant"}
        if bool(getattr(part, 'reward_claimed', False)):
            return {"ok": False, "reason": "already_claimed"}
        total = int(getattr(st, 'progress_amount', 0) or 0)
        if total <= 0:
            return {"ok": False, "reason": "no_progress"}
        user_contrib = int(getattr(part, 'contributed_amount', 0) or 0)
        if user_contrib <= 0:
            return {"ok": False, "reason": "no_contribution"}
        pool = int(getattr(st, 'reward_total_coins', 0) or 0)
        # Удельная доля
        share = int((pool * user_contrib) // total)
        if share <= 0:
            share = 0
        # выдаём монеты
        player = dbs.query(Player).filter(Player.user_id == user_id).with_for_update(read=False).first()
        if not player:
            player = Player(user_id=user_id, username=str(user_id), coins=0)
            dbs.add(player)
            dbs.commit()
            dbs.refresh(player)
        player.coins = int(player.coins or 0) + int(share)
        part.reward_claimed = True
        dbs.commit()
        return {"ok": True, "claimed_coins": int(share), "coins_after": int(player.coins)}
    except Exception:
        try:
            dbs.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    finally:
        dbs.close()

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
            {"name": "Азотное",       "description": "Ускоряет вегетацию",           "effect": "+рост",       "duration_sec": 21600,  "price_coins": 30},  # 6 часов, +40%
            {"name": "Фосфорное",     "description": "Усиливает образование плодов", "effect": "+урожай",     "duration_sec": 21600,  "price_coins": 35},  # 6 часов, +50%
            {"name": "Калийное",      "description": "Повышает устойчивость",        "effect": "+качество",   "duration_sec": 25200,  "price_coins": 40},  # 7 часов, +редкость
            {"name": "Комплексное",   "description": "Сбалансированная смесь",       "effect": "+всё",        "duration_sec": 28800, "price_coins": 60},  # 8 часов, +40% урожай +редкость
            {"name": "Биоактив",      "description": "Органический стимулятор",      "effect": "+био",        "duration_sec": 21600,  "price_coins": 50},  # 6 часов, +45%
            {"name": "Стимул-Х",      "description": "Мощный стимулятор роста",       "effect": "+рост+кач",   "duration_sec": 25200,  "price_coins": 70},  # 7 часов, +55%
            {"name": "Минерал+",      "description": "Минеральный комплекс",         "effect": "+качество",   "duration_sec": 25200,  "price_coins": 55},  # 7 часов, +редкость
            {"name": "Гумат",         "description": "Гуминовый концентрат",          "effect": "+питание",    "duration_sec": 21600,  "price_coins": 45},  # 6 часов, +40%
            {"name": "СуперРост",     "description": "Сокращает время роста",         "effect": "-время",      "duration_sec": 32400,  "price_coins": 80},  # 9 часов, +60%
            {"name": "МегаУрожай",    "description": "Повышает выход урожая",         "effect": "+урожай++",   "duration_sec": 43200, "price_coins": 100}, # 12 часов, +60%
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
    Возможные reason: no_such_bed, not_growing, no_such_fertilizer, no_fertilizer_in_inventory, fertilizer_active
    """
    dbs = SessionLocal()
    try:
        fert = dbs.query(Fertilizer).filter(Fertilizer.id == fertilizer_id).first()
        if not fert:
            return {"ok": False, "reason": "no_such_fertilizer"}

        bed = (
            dbs.query(PlantationBed)
            .options(joinedload(PlantationBed.fertilizer), joinedload(PlantationBed.seed_type))
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

        # Проверяем активное удобрение
        now_ts = int(time.time())
        if bed.fertilizer_id and bed.fertilizer:
            dur = int(getattr(bed.fertilizer, 'duration_sec', 0) or 0)
            appl = int(getattr(bed, 'fertilizer_applied_at', 0) or 0)
            if dur > 0 and appl > 0 and (now_ts - appl) <= dur:
                return {"ok": False, "reason": "fertilizer_active", "bed_state": bed.state}

        inv = (
            dbs.query(FertilizerInventory)
            .filter(FertilizerInventory.player_id == user_id, FertilizerInventory.fertilizer_id == fertilizer_id)
            .with_for_update(read=False)
            .first()
        )
        if not inv or int(inv.quantity or 0) <= 0:
            return {"ok": False, "reason": "no_fertilizer_in_inventory"}

        # Применяем
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
        return list(
            dbs.query(PlantationBed)
            .options(joinedload(PlantationBed.seed_type), joinedload(PlantationBed.fertilizer))
            .filter(PlantationBed.owner_id == user_id)
            .order_by(PlantationBed.bed_index.asc())
            .all()
        )
    finally:
        dbs.close()


def get_fertilizer_status(bed: PlantationBed) -> dict:
    """Возвращает информацию о статусе удобрения на грядке.
    Returns: {active: bool, fertilizer_name: str, time_left: int, multiplier: float, effect_type: str}
    """
    result = {
        'active': False,
        'fertilizer_name': None,
        'time_left': 0,
        'multiplier': 1.0,
        'effect_type': 'none'
    }
    
    try:
        if not bed.fertilizer_id or not bed.fertilizer:
            return result
            
        now_ts = int(time.time())
        f_dur = int(getattr(bed.fertilizer, 'duration_sec', 0) or 0)
        f_appl = int(getattr(bed, 'fertilizer_applied_at', 0) or 0)
        
        if f_dur > 0 and f_appl > 0:
            time_left = max(0, f_dur - (now_ts - f_appl))
            if time_left > 0:
                result['active'] = True
                result['fertilizer_name'] = getattr(bed.fertilizer, 'name', 'Удобрение')
                result['time_left'] = time_left
                
                # Определяем тип эффекта по названию удобрения
                fert_name = result['fertilizer_name'].lower()
                effect = getattr(bed.fertilizer, 'effect', '') or ''
                
                if 'урожай++' in effect:
                    result['multiplier'] = 1.6  # +60%
                    result['effect_type'] = 'mega_yield'
                elif 'урожай' in effect:
                    result['multiplier'] = 1.5  # +50%
                    result['effect_type'] = 'yield'
                elif 'качество' in effect:
                    result['multiplier'] = 1.0  # не влияет на количество, но улучшает редкость
                    result['effect_type'] = 'quality'
                elif 'всё' in effect:
                    result['multiplier'] = 1.4  # +40%
                    result['effect_type'] = 'complex'
                elif 'рост+кач' in effect:
                    result['multiplier'] = 1.55  # +55%
                    result['effect_type'] = 'growth_quality'
                elif 'время' in effect:
                    result['multiplier'] = 1.6  # +60%
                    result['effect_type'] = 'time'
                else:
                    result['multiplier'] = 1.4  # +40% базовые удобрения
                    result['effect_type'] = 'basic'
                
    except Exception:
        pass
        
    return result


def _update_bed_ready_if_due(dbs, bed: PlantationBed) -> bool:
    """Внутренняя: переводит грядку в состояние 'ready', если прошло время роста. Возвращает True, если обновлено."""
    try:
        if bed and bed.state == 'growing' and bed.seed_type and bed.planted_at:
            now_ts = int(time.time())
            if now_ts - int(bed.planted_at) >= int(bed.seed_type.grow_time_sec or 0):
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
        return {"ok": True, "bed_state": bed.state}
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
            .options(joinedload(PlantationBed.seed_type))
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
        # Бонус за полив: до +25% (по 5% за полив, максимум 5)
        wc = int(bed.water_count or 0)
        if wc > 0:
            yield_mult *= (1.0 + min(wc, 5) * 0.05)
        # Бонус от удобрения, если активно
        fert_active = False
        fertilizer_name = None
        fert_effect_type = 'none'
        fert_multiplier = 1.0
        try:
            if bed.fertilizer_id and bed.fertilizer:
                fert_status = get_fertilizer_status(bed)
                fert_active = fert_status['active']
                fertilizer_name = fert_status['fertilizer_name']
                fert_effect_type = fert_status['effect_type']
                fert_multiplier = fert_status['multiplier']
        except Exception:
            fert_active = False
        
        if fert_active:
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
                # Смещения весов от удобрения и полива
                if fert_active:
                    # Различные эффекты в зависимости от типа удобрения
                    if fert_effect_type in ('quality', 'complex', 'growth_quality'):
                        # Усиливаем высокие редкости, снижаем Basic
                        if 'Basic' in rarity_weights:
                            rarity_weights['Basic'] *= 0.7
                        for rk in ('Medium', 'Elite', 'Absolute', 'Majestic'):
                            if rk in rarity_weights:
                                multiplier = 1.5 if rk == 'Medium' else 2.0 if rk == 'Elite' else 2.5
                                rarity_weights[rk] *= multiplier
                    elif fert_effect_type in ('yield', 'mega_yield', 'time'):
                        # Меньше влияние на редкость, больше на количество
                        if 'Basic' in rarity_weights:
                            rarity_weights['Basic'] *= 0.9
                        for rk in ('Medium', 'Elite'):
                            if rk in rarity_weights:
                                rarity_weights[rk] *= 1.2
                    else:
                        # Базовые удобрения
                        if 'Basic' in rarity_weights:
                            rarity_weights['Basic'] *= 0.8
                        for rk in ('Medium', 'Elite'):
                            if rk in rarity_weights:
                                rarity_weights[rk] *= 1.3
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
        dbs.commit()
        return {
            "ok": True,
            "yield": amount,
            "drink_id": st.drink_id,
            "items_added": items_added,
            "rarity_counts": rarity_counts,
            "effects": {
                "water_count": int(wc),
                "fertilizer_active": bool(fert_active),
                "fertilizer_name": fertilizer_name,
                "status_effect": (se or None),
                "yield_multiplier": float(yield_mult),
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

def add_energy_drink(name: str, description: str, image_path: str | None = None, is_special: bool = False):
    """Создаёт новый энергетик в базе и возвращает объект."""
    db = SessionLocal()
    try:
        drink = EnergyDrink(name=name, description=description, image_path=image_path, is_special=is_special)
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
        leaderboard_data = (
            db.query(
                Player.user_id,
                Player.username,
                func.sum(InventoryItem.quantity).label('total_drinks'),
                Player.vip_until,
                Player.vip_plus_until,
            )
            .join(InventoryItem, Player.user_id == InventoryItem.player_id)
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
    Возвращает dict: {ok: bool, reason?: str, vip_plus_until?: int, coins_left?: int}
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
        base_ts = int(player.vip_plus_until or 0)
        start_ts = base_ts if base_ts and base_ts > now_ts else now_ts
        new_vip_plus_until = start_ts + int(duration_seconds)

        player.coins = current_coins - int(cost_coins)
        try:
            player.vip_plus_until = new_vip_plus_until
        except Exception:
            # На случай старой схемы без столбца
            pass
        db.commit()
        return {"ok": True, "vip_plus_until": new_vip_plus_until, "coins_left": int(player.coins)}
    except Exception as ex:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
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
        players = (
            dbs.query(Player)
            .filter(Player.coins > 0)
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