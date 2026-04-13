# file: constants.py
"""
Единый модуль констант для бота.
Хранит настройки, используемые в нескольких файлах.
"""

# --- Кулдауны и директории ---
SEARCH_COOLDOWN = 1200            # 20 минут в секундах
DAILY_BONUS_COOLDOWN = 86400      # 24 часа в секундах
ENERGY_IMAGES_DIR = 'energy_images'
PLANTATION_FERTILIZER_MAX_PER_BED = 5
PLANTATION_NEG_EVENT_INTERVAL_SEC = 900
PLANTATION_NEG_EVENT_CHANCE = 0.15
PLANTATION_NEG_EVENT_MAX_ACTIVE = 0.25
PLANTATION_NEG_EVENT_DURATION_SEC = 3600

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
    'Plant': '🌿',
}
RARITY_ORDER = ['Plant', 'Special', 'Majestic', 'Absolute', 'Elite', 'Medium', 'Basic']
ITEMS_PER_PAGE = 10               # кол-во предметов на страницу инвентаря
FAVORITE_DRINK_WEIGHT_MULT = 3  # множитель веса при поиске для энергетиков из избранного

# --- Свага-карточки ---
SWAGA_RARITIES = {
    'Обычная': 50,
    'Редкая': 25,
    'Ебабельная': 15,
    'Нереальноахуенная': 8,
    'Swaga': 1.9,
    'Мистербист': 0.1,
}

SWAGA_COLOR_EMOJIS = {
    'Обычная': '⚪',
    'Редкая': '🔵',
    'Ебабельная': '🟣',
    'Нереальноахуенная': '🔴',
    'Swaga': '🌟',
    'Мистербист': '👑',
}

SWAGA_RARITY_ORDER = ['Мистербист', 'Swaga', 'Нереальноахуенная', 'Ебабельная', 'Редкая', 'Обычная']

SWAGA_CHEST_DROP_CHANCES = {
    'Обычная': {'Обычная': 80, 'Редкая': 15, 'Ебабельная': 4, 'Нереальноахуенная': 1, 'Swaga': 0, 'Мистербист': 0},
    'Редкая': {'Обычная': 20, 'Редкая': 65, 'Ебабельная': 10, 'Нереальноахуенная': 4, 'Swaga': 1, 'Мистербист': 0},
    'Ебабельная': {'Обычная': 0, 'Редкая': 25, 'Ебабельная': 60, 'Нереальноахуенная': 10, 'Swaga': 4.5, 'Мистербист': 0.5},
    'Нереальноахуенная': {'Обычная': 0, 'Редкая': 0, 'Ебабельная': 20, 'Нереальноахуенная': 65, 'Swaga': 10, 'Мистербист': 5},
    'Swaga': {'Обычная': 0, 'Редкая': 0, 'Ебабельная': 0, 'Нереальноахуенная': 30, 'Swaga': 55, 'Мистербист': 15},
    'Мистербист': {'Обычная': 0, 'Редкая': 0, 'Ебабельная': 0, 'Нереальноахуенная': 0, 'Swaga': 30, 'Мистербист': 70},
}

# --- Daily bonus ---
DAILY_BONUS_RULES = {
    'cycle_length': 7,
    'streak_grace_multiplier': 0.5,
    'grace_min_sec': 5400,
    'grace_max_sec': 43200,
    'vip_grace_multiplier': 1.25,
    'vip_plus_grace_multiplier': 1.5,
    'rating_bonus_cap': 0.05,
    'pity_rare_after_common': 4,
    'pity_epic_after_non_epic': 11,
    'tier_weights': {
        'common': 84.5,
        'rare': 13.5,
        'epic': 1.9,
        'jackpot': 0.1,
    },
    'tier_rating_multipliers': {
        'rare': 1.0,
        'epic': 1.35,
        'jackpot': 1.7,
    },
}

DAILY_BONUS_TIER_ORDER = ['common', 'rare', 'epic', 'jackpot']

DAILY_BONUS_TIER_LABELS = {
    'common': {'ru': 'Обычные', 'en': 'Common'},
    'rare': {'ru': 'Редкие', 'en': 'Rare'},
    'epic': {'ru': 'Эпические', 'en': 'Epic'},
    'jackpot': {'ru': 'Джекпот', 'en': 'Jackpot'},
}

DAILY_BONUS_REWARD_CATALOG = {
    'coins_75': {
        'kind': 'coins',
        'amount': 75,
        'label_ru': '💰 75 септимов',
        'label_en': '💰 75 coins',
    },
    'coins_100': {
        'kind': 'coins',
        'amount': 100,
        'label_ru': '💰 100 септимов',
        'label_en': '💰 100 coins',
    },
    'coins_125': {
        'kind': 'coins',
        'amount': 125,
        'label_ru': '💰 125 септимов',
        'label_en': '💰 125 coins',
    },
    'coins_200': {
        'kind': 'coins',
        'amount': 200,
        'label_ru': '💰 200 септимов',
        'label_en': '💰 200 coins',
    },
    'coins_250': {
        'kind': 'coins',
        'amount': 250,
        'tier': 'common',
        'label_ru': '💰 250 септимов',
        'label_en': '💰 250 coins',
    },
    'coins_400': {
        'kind': 'coins',
        'amount': 400,
        'tier': 'common',
        'label_ru': '💰 400 септимов',
        'label_en': '💰 400 coins',
    },
    'coins_700': {
        'kind': 'coins',
        'amount': 700,
        'tier': 'rare',
        'label_ru': '💰 700 септимов',
        'label_en': '💰 700 coins',
    },
    'selyuk_fragment_1': {
        'kind': 'selyuk_fragment',
        'amount': 1,
        'tier': 'common',
        'label_ru': '🧩 Фрагмент Селюка x1',
        'label_en': '🧩 Selyuk fragment x1',
    },
    'selyuk_fragment_2': {
        'kind': 'selyuk_fragment',
        'amount': 2,
        'tier': 'rare',
        'label_ru': '🧩 Фрагменты Селюка x2',
        'label_en': '🧩 Selyuk fragments x2',
    },
    'luck_coupon_1': {
        'kind': 'luck_coupon',
        'amount': 1,
        'tier': 'common',
        'label_ru': '🎲 Купон удачи x1',
        'label_en': '🎲 Luck coupon x1',
    },
    'seed_coupon_1': {
        'kind': 'seed_coupon',
        'amount': 1,
        'tier': 'common',
        'label_ru': '🎟 Купон семян x1',
        'label_en': '🎟 Seed coupon x1',
    },
    'auto_search_boost_2_24h': {
        'kind': 'auto_search_boost',
        'boost_count': 2,
        'days': 1,
        'label_ru': '🚀 Автопоиск +2 на 24ч',
        'label_en': '🚀 Auto-search +2 for 24h',
    },
    'auto_search_boost_5_24h': {
        'kind': 'auto_search_boost',
        'boost_count': 5,
        'days': 1,
        'tier': 'rare',
        'label_ru': '🚀 Автопоиск +5 на 24ч',
        'label_en': '🚀 Auto-search +5 for 24h',
    },
    'absolute_drink': {
        'kind': 'absolute_drink',
        'tier': 'rare',
        'label_ru': '🟣 Энергетик Absolute',
        'label_en': '🟣 Absolute energy drink',
    },
    'vip_3d': {
        'kind': 'vip',
        'seconds': 3 * 24 * 60 * 60,
        'tier': 'epic',
        'label_ru': '👑 VIP на 3 дня',
        'label_en': '👑 VIP for 3 days',
    },
    'vip_combo_14': {
        'kind': 'vip_combo',
        'vip_seconds': 3 * 24 * 60 * 60,
        'vip_plus_seconds_if_active': 1 * 24 * 60 * 60,
        'label_ru': '👑 VIP на 3 дня или 💎 VIP+ +1 день',
        'label_en': '👑 VIP for 3 days or 💎 VIP+ +1 day',
    },
    'vip_plus_1d': {
        'kind': 'vip_plus',
        'seconds': 1 * 24 * 60 * 60,
        'tier': 'epic',
        'label_ru': '💎 VIP+ на 1 день',
        'label_en': '💎 VIP+ for 1 day',
    },
    'vip_plus_7d': {
        'kind': 'vip_plus',
        'seconds': 7 * 24 * 60 * 60,
        'tier': 'jackpot',
        'label_ru': '💎 VIP+ на 7 дней',
        'label_en': '💎 VIP+ for 7 days',
    },
    'vip_plus_30d': {
        'kind': 'vip_plus',
        'seconds': 30 * 24 * 60 * 60,
        'tier': 'jackpot',
        'label_ru': '🎊 VIP+ на 30 дней',
        'label_en': '🎊 VIP+ for 30 days',
    },
}

DAILY_BONUS_ROULETTE_TABLE = {
    'common': [
        {'reward_id': 'coins_250', 'weight': 42},
        {'reward_id': 'coins_400', 'weight': 28},
        {'reward_id': 'selyuk_fragment_1', 'weight': 15},
        {'reward_id': 'luck_coupon_1', 'weight': 13},
        {'reward_id': 'seed_coupon_1', 'weight': 2},
    ],
    'rare': [
        {'reward_id': 'coins_700', 'weight': 28},
        {'reward_id': 'selyuk_fragment_2', 'weight': 22},
        {'reward_id': 'auto_search_boost_5_24h', 'weight': 25},
        {'reward_id': 'absolute_drink', 'weight': 25},
    ],
    'epic': [
        {'reward_id': 'vip_3d', 'weight': 85},
        {'reward_id': 'vip_plus_1d', 'weight': 15},
    ],
    'jackpot': [
        {'reward_id': 'vip_plus_7d', 'weight': 91},
        {'reward_id': 'vip_plus_30d', 'weight': 9},
    ],
}

DAILY_BONUS_CYCLE_REWARDS = [
    {'day': 1, 'reward_id': 'coins_75'},
    {'day': 2, 'reward_id': 'coins_100'},
    {'day': 3, 'reward_id': 'luck_coupon_1'},
    {'day': 4, 'reward_id': 'coins_125'},
    {'day': 5, 'reward_id': 'selyuk_fragment_1'},
    {'day': 6, 'reward_id': 'auto_search_boost_2_24h'},
    {'day': 7, 'reward_id': 'coins_200'},
]

DAILY_BONUS_MILESTONES = [
    {'streak': 7, 'reward_id': 'selyuk_fragment_1'},
    {'streak': 14, 'reward_id': 'vip_combo_14'},
    {'every': 30, 'start': 30, 'reward_id': 'vip_plus_1d'},
]

# Legacy alias for older imports.
DAILY_BONUS_REWARDS = DAILY_BONUS_REWARD_CATALOG

# --- Казино ---
CASINO_WIN_PROB = 0.35  # Вероятность выигрыша в казино (меньше — чаще проигрыши)
CASINO_MAX_BET = 50000  # Максимальная ставка в казино
CASINO_MIN_BET = 1      # Минимальная ставка в казино

# --- Улучшенное Казино ---
# Типы игр в казино с разными коэффициентами и вероятностями
CASINO_GAMES = {
    'coin_flip': {
        'name': '🪙 Монетка',
        'description': 'Орёл или Решка',
        'win_prob': 0.50,  # 50% шанс (честная монета)
        'multiplier': 2.0,  # x2 при выигрыше
        'emoji': '🪙',
    },
    'dice': {
        'name': '🎲 Кости',
        'description': 'Угадай число (1-6)',
        'win_prob': 0.167,  # ~16.7% шанс (1 из 6)
        'multiplier': 5.5,  # x5.5 при выигрыше
        'emoji': '🎲',
    },
    'roulette_color': {
        'name': '🎡 Рулетка (цвет)',
        'description': 'Красное или Чёрное',
        'win_prob': 0.486,  # 48.6% шанс (18/37, есть зелёный 0)
        'multiplier': 2.0,  # x2 при выигрыше
        'emoji': '🎡',
    },
    'roulette_number': {
        'name': '🎯 Рулетка (число)',
        'description': 'Угадай число (0-36)',
        'win_prob': 0.027,  # ~2.7% шанс (1 из 37)
        'multiplier': 35.0,  # x35 при выигрыше
        'emoji': '🎯',
    },
    'slots': {
        'name': '🎰 Слоты',
        'description': 'Три в ряд',
        'win_prob': 0.15,  # 15% шанс любого выигрыша
        'multiplier': 3.0,  # среднее x3
        'emoji': '🎰',
    },
    'high_low': {
        'name': '📊 Больше/Меньше',
        'description': 'Больше или меньше 50',
        'win_prob': 0.49,  # 49% шанс (число 50 не считается)
        'multiplier': 1.95,  # x1.95 при выигрыше
        'emoji': '📊',
    },
    'basketball': {
        'name': '🏀 Баскетбол',
        'description': 'Забросьте мяч в корзину!',
        'win_prob': 0.4,
        'multiplier': 2.5,
        'emoji': '🏀',
    },
    'football': {
        'name': '⚽ Футбол',
        'description': 'Забейте гол!',
        'win_prob': 0.6,
        'multiplier': 1.6,
        'emoji': '⚽',
    },
    'bowling': {
        'name': '🎳 Боулинг',
        'description': 'Сбейте все кегли!',
        'win_prob': 0.166,
        'multiplier': 6.0,
        'emoji': '🎳',
    },
    'darts': {
        'name': '🎯 Дартс',
        'description': 'Попадите в яблочко!',
        'win_prob': 0.166,
        'multiplier': 6.0,
        'emoji': '🎯',
    },
}

# Эмодзи для слотов
SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
SLOT_PAYOUTS = {
    '💎💎💎': 20,    # Джекпот - три бриллианта
    '7️⃣7️⃣7️⃣': 15,   # Три семерки
    '🔔🔔🔔': 10,    # Три колокола
    '🍇🍇🍇': 7,     # Три винограда
    '🍊🍊🍊': 5,     # Три апельсина
    '🍋🍋🍋': 4,     # Три лимона
    '🍒🍒🍒': 3,     # Три вишни
}

# Анимация для казино
CASINO_ANIMATIONS = {
    'coin_flip': ['🪙', '💫', '🌟', '✨'],
    'dice': ['🎲', '🎯', '⚡', '✨'],
    'roulette': ['🎡', '🔴', '⚫', '🟢', '✨'],
    'slots': ['🎰', '💫', '⭐', '✨'],
}

# Достижения казино
CASINO_ACHIEVEMENTS = {
    'beginner': {'wins': 5, 'reward': 500, 'name': '🎯 Новичок', 'desc': '5 побед'},
    'player': {'wins': 25, 'reward': 2500, 'name': '🎲 Игрок', 'desc': '25 побед'},
    'gambler': {'wins': 100, 'reward': 10000, 'name': '🎰 Азартный', 'desc': '100 побед'},
    'master': {'wins': 500, 'reward': 50000, 'name': '👑 Мастер', 'desc': '500 побед'},
}

# --- Блэкджек ---
BLACKJACK_SUITS = ['♠️', '♥️', '♦️', '♣️']
BLACKJACK_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
BLACKJACK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11  # Туз считается как 11, но может быть 1
}
BLACKJACK_MULTIPLIER = 2.0       # Обычный выигрыш x2
BLACKJACK_BJ_MULTIPLIER = 2.5    # Блэкджек (21 на первых 2 картах) x2.5

# --- Мины (Mines) ---
MINES_GRID_SIZE = 5              # Поле 5x5
MINES_MIN_COUNT = 1              # Минимум мин
MINES_MAX_COUNT = 24             # Максимум мин (25-1)
MINES_DEFAULT_COUNT = 5          # Кол-во мин по умолчанию

# --- Краш (Crash) ---
CRASH_UPDATE_INTERVAL = 0.8      # Интервал обновления множителя (секунды)
CRASH_GROWTH_RATE = 0.15         # Скорость роста множителя за шаг
CRASH_MAX_MULTIPLIER = 100.0     # Максимальный множитель

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
    '1d': 7500,
    '7d': 45000,
    '30d': 150000,
}
VIP_PLUS_DURATIONS_SEC = {
    '1d': 24 * 60 * 60,
    '7d': 7 * 24 * 60 * 60,
    '30d': 30 * 24 * 60 * 60,
}
ADMIN_EMOJI = '🛡️'
ADMIN_PLUS_EMOJI = '🛡️✨'

PROMO_ANNOUNCEMENT_CHAT = '@energobot_support'
PROMO_ANNOUNCEMENT_LINK = 'https://t.me/energobot_support'

# --- TG Premium ---
TG_PREMIUM_COST = 1000000 
TG_PREMIUM_DURATION_SEC = 90 * 24 * 60 * 60  # ~90 дней

# --- Администрирование (bootstrap) ---
ADMIN_USERNAMES = {'aAntiLoxX'}  # username Создателя(ей) для fallback-проверок

# --- Автопоиск VIP ---
# Максимум автопоисков в сутки
AUTO_SEARCH_DAILY_LIMIT = 40

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
    'Plant': 400,
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
        'cost': 4000,
        'trees': 50,
        'grow_time': 40 * 60 * 60,  # 40 часов
        'min_yield': 140,
        'max_yield': 165,
    },
    'premium': {
        'cost': 10000,
        'trees': 150,
        'grow_time': 44 * 60 * 60,  # 44 часов
        'min_yield': 420,
        'max_yield': 480,
    },
        'master': {
        'cost': 40000,
        'trees': 500,
        'grow_time': 48 * 60 * 60,  # 48 часов
        'min_yield': 1700,
        'max_yield': 1800,
    },
}

# Типы шёлка и их базовые цены
SILK_TYPES = {
    'raw': {
        'name': 'Сырой шёлк',
        'emoji': '🧵',
        'base_price': 32,
        'probability': 70,
    },
    'refined': {
        'name': 'Рафинированный шёлк',
        'emoji': '🪡',
        'base_price': 37,
        'probability': 25,
    },
    'premium': {
        'name': 'Премиум шёлк',
        'emoji': '✨',
        'base_price': 45,
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
SILK_PLANTATIONS_ENABLED = True # Временно отключить создание новых плантаций
SILK_TRADING_ENABLED = True      # Временно отключить продажу шёлка

# Рыночные цены на шёлк (базовая стоимость может колебаться)
SILK_MARKET_PRICES = {
    'raw': {'min': 20, 'max': 25}, 
    'refined': {'min': 24, 'max': 28},
    'premium': {'min': 28, 'max': 38},
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
