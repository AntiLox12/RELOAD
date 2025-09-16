# file: constants.py
"""
Единый модуль констант для бота.
Хранит настройки, используемые в нескольких файлах.
"""

# --- Кулдауны и директории ---
SEARCH_COOLDOWN = 300             # 5 минут в секундах
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

# --- TG Premium ---
TG_PREMIUM_COST = 600000
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
        'min_yield': 1200,
        'max_yield': 1400,
    },
    'standard': {
        'cost': 5000,
        'trees': 50,
        'grow_time': 48 * 60 * 60,  # 48 часов
        'min_yield': 6500,
        'max_yield': 7500,
    },
    'premium': {
        'cost': 15000,
        'trees': 150,
        'grow_time': 72 * 60 * 60,  # 72 часа
        'min_yield': 20000,
        'max_yield': 25000,
    },
    'master': {
        'cost': 50000,
        'trees': 500,
        'grow_time': 96 * 60 * 60,  # 96 часов
        'min_yield': 70000,
        'max_yield': 90000,
    },
}

# Типы шёлка и их базовые цены
SILK_TYPES = {
    'raw': {
        'name': 'Сырой шёлк',
        'emoji': '🧵',
        'base_price': 50,
        'probability': 70,  # вероятность получения в %
    },
    'refined': {
        'name': 'Рафинированный шёлк',
        'emoji': '🪡',
        'base_price': 65,  # +30% к базовой стоимости
        'probability': 25,
    },
    'premium': {
        'name': 'Премиум шёлк',
        'emoji': '✨',
        'base_price': 80,  # +60% к базовой стоимости
        'probability': 5,
    },
}

# Модификаторы качества и погоды
SILK_QUALITY_RANGE = (80, 120)  # диапазон модификатора качества семян в %
SILK_WEATHER_RANGE = (90, 110)  # диапазон модификатора погодных условий в %

# VIP бонусы для системы шёлка
SILK_VIP_BONUSES = {
    'yield_multiplier': 1.2,  # +20% к урожаю
    'quality_bonus': 10,      # +10% к модификатору качества
    'growth_speedup': 0.9,    # ускорение роста на 10%
}

# Максимальное количество плантаций у одного игрока
SILK_MAX_PLANTATIONS = 5

# Время уведомления до готовности урожая (в минутах)
SILK_NOTIFICATION_TIME = 30

# Рыночные цены на шёлк (базовая стоимость может колебаться)
SILK_MARKET_PRICES = {
    'raw': {'min': 45, 'max': 55},
    'refined': {'min': 60, 'max': 70},
    'premium': {'min': 75, 'max': 85},
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
