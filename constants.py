# file: constants.py
"""
Единый модуль констант для бота.
Хранит настройки, используемые в нескольких файлах.
"""

# --- Кулдауны и директории ---
SEARCH_COOLDOWN = 1200            # 20 минут в секундах
DAILY_BONUS_COOLDOWN = 86400      # 24 часа в секундах
ENERGY_IMAGES_DIR = 'energy_images'

# --- Игровые константы ---
RARITIES = {
    'Basic': 50,
    'Medium': 30,
    'Elite': 15,
    'Absolute': 4,
    'Majestic': 1,
}
COLOR_EMOJIS = {
    'Basic': '⚪',
    'Medium': '🟢',
    'Elite': '🔵',
    'Absolute': '🟣',
    'Majestic': '🟠',
    'Special': '⭐',
}
RARITY_ORDER = ['Special', 'Majestic', 'Absolute', 'Elite', 'Medium', 'Basic']
ITEMS_PER_PAGE = 10               # кол-во предметов на страницу инвентаря

# --- Казино ---
CASINO_WIN_PROB = 0.35  # Вероятность выигрыша в казино (меньше — чаще проигрыши)

# --- VIP настройки ---
VIP_EMOJI = '👑'
VIP_COSTS = {
    '1d': 500,
    '7d': 3000,
    '30d': 10000,
}
VIP_DURATIONS_SEC = {
    '1d': 24 * 60 * 60,
    '7d': 7 * 24 * 60 * 60,
    '30d': 30 * 24 * 60 * 60,
}

# --- VIP+ настройки ---
VIP_PLUS_EMOJI = '💎'
VIP_PLUS_COSTS = {
    '1d': 1000,
    '7d': 6000,
    '30d': 20000,
}
VIP_PLUS_DURATIONS_SEC = {
    '1d': 24 * 60 * 60,
    '7d': 7 * 24 * 60 * 60,
    '30d': 30 * 24 * 60 * 60,
}

# --- TG Premium ---
TG_PREMIUM_COST = 1000000 
TG_PREMIUM_DURATION_SEC = 90 * 24 * 60 * 60  # ~90 дней

# --- Администрирование (bootstrap) ---
ADMIN_USERNAMES = {'aAntiLoxX'}  # username Создателя(ей) для fallback-проверок

# --- Автопоиск VIP ---
# Максимум автопоисков в сутки
AUTO_SEARCH_DAILY_LIMIT = 60

# --- Приёмник (продажа энергетиков) ---
# Комиссия 30% означает, что игрок получает 70% от базовой цены продажи
# Пример: базовая цена 10 -> выплатится int(10 * 0.7) = 7
RECEIVER_COMMISSION = 0.30
RECEIVER_PRICES = {
    'Basic': 10,
    'Medium': 20,
    'Elite': 50,
    'Absolute': 120,
    'Majestic': 750,
    'Special': 300,
}

# --- Магазин (покупка энергетиков) ---
# Множитель цены покупки относительно базовой цены приёмника.
# Например, при множителе 3: Basic продаётся игроку за 30 монет, если базовая цена 10.
SHOP_PRICE_MULTIPLIER = 3
SHOP_PRICES = {k: int(v * SHOP_PRICE_MULTIPLIER) for k, v in RECEIVER_PRICES.items()}

# --- Город Шёлка ---
# Уровни инвестиций в шёлковые плантации
SILK_INVESTMENT_LEVELS = {
    'starter': {
        'cost': 1000,
        'trees': 10,
        'grow_time': 24 * 60 * 60,  # 24 часа
        'min_yield': 30,
        'max_yield': 38,
    },
    'standard': {
        'cost': 5000,
        'trees': 50,
        'grow_time': 48 * 60 * 60,  # 48 часов
        'min_yield': 140,
        'max_yield': 165,
    },
    'premium': {
        'cost': 15000,
        'trees': 150,
        'grow_time': 48 * 60 * 60,  # 48 часов (уменьшено с 72)
        'min_yield': 420,
        'max_yield': 480,
    },
        'master': {
        'cost': 50000,
        'trees': 500,
        'grow_time': 60 * 60 * 60,  # 60 часов (уменьшено с 96)
        'min_yield': 1300,
        'max_yield': 1500,
    },
}

# Типы шёлка и их базовые цены
SILK_TYPES = {
    'raw': {
        'name': 'Сырой шёлк',
        'emoji': '🧵',
        'base_price': 25,
        'probability': 70,  # вероятность получения в %
    },
    'refined': {
        'name': 'Рафинированный шёлк',
        'emoji': '🪡',
        'base_price': 32,  # было 40
        'probability': 25,
    },
    'premium': {
        'name': 'Премиум шёлк',
        'emoji': '✨',
        'base_price': 40,  # было 50
        'probability': 5,
    },
}

# Модификаторы качества и погоды
SILK_QUALITY_RANGE = (80, 120)  # диапазон модификатора качества семян в %
SILK_WEATHER_RANGE = (90, 110)  # диапазон модификатора погодных условий в %

# Максимальные ограничения для безопасности системы
SILK_MAX_YIELD_PER_PLANTATION = 10000  # максимальный урожай с одной плантации
SILK_MAX_QUALITY_GRADE = 500  # максимальный уровень качества
SILK_MIN_QUALITY_GRADE = 100  # минимальный уровень качества
SILK_MAX_SALE_AMOUNT = 100000  # максимальная сумма продажи за раз

# VIP бонусы для системы шёлка
SILK_VIP_BONUSES = {
    'yield_multiplier': 1.2,  # +20% к урожаю
    'quality_bonus': 10,      # +10% к модификатору качества
    'growth_speedup': 0.9,    # ускорение роста на 10%
}

# Максимальное количество плантаций у одного игрока
SILK_MAX_PLANTATIONS = 2

# Время уведомления до готовности урожая (в минутах)
SILK_NOTIFICATION_TIME = 30

# Флаги временного отключения функций
SILK_PLANTATIONS_ENABLED = False  # Временно отключить создание новых плантаций
SILK_TRADING_ENABLED = False      # Временно отключить продажу шёлка

# Рыночные цены на шёлк (базовая стоимость может колебаться)
SILK_MARKET_PRICES = {
    'raw': {'min': 18, 'max': 24},      # было 22-28
    'refined': {'min': 22, 'max': 28},  # было 28-36
    'premium': {'min': 28, 'max': 36},  # было 36-44
}

# Эмодзи для системы шёлка
SILK_EMOJIS = {
    'city': '🧵',
    'plantation': '🌳',
    'harvest': '🌾',
    'market': '🏪',
    'inventory': '📦',
    'stats': '📊',
    'coins': '🪙',
    'timer': '⏱️',
    'ready': '✅',
    'growing': '🌱',
    'investment': '💰',
}
