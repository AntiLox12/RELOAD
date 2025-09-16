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
