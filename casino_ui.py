from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_city_casino_view(coins: int, casino_wins: int, casino_losses: int) -> tuple[str, InlineKeyboardMarkup]:
    casino_total = int(casino_wins or 0) + int(casino_losses or 0)
    win_rate = (int(casino_wins or 0) / casino_total * 100) if casino_total > 0 else 0

    text = (
        "<b>🎰 Казино ХайТаун</b>\n\n"
        f"💰 Ваш баланс: <b>{int(coins or 0)}</b> септимов\n"
        f"📊 Статистика: {int(casino_wins or 0)}✅ / {int(casino_losses or 0)}❌ ({win_rate:.1f}%)\n\n"
        "🎮 <b>Выберите игру:</b>\n"
    )

    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data="casino_game_coin_flip")],
        [InlineKeyboardButton("🎲 Кости", callback_data="casino_game_dice"),
         InlineKeyboardButton("📊 Больше/Меньше", callback_data="casino_game_high_low")],
        [InlineKeyboardButton("🎡 Рулетка (цвет)", callback_data="casino_game_roulette_color"),
         InlineKeyboardButton("🎯 Рулетка (число)", callback_data="casino_game_roulette_number")],
        [InlineKeyboardButton("🎰 Слоты", callback_data="casino_game_slots")],
        [InlineKeyboardButton("🃏 Блэкджек", callback_data="casino_game_blackjack")],
        [InlineKeyboardButton("💣 Мины", callback_data="casino_game_mines"),
         InlineKeyboardButton("📈 Краш", callback_data="casino_game_crash")],
        [InlineKeyboardButton("🏀 Баскетбол", callback_data="casino_game_basketball"),
         InlineKeyboardButton("⚽ Футбол", callback_data="casino_game_football")],
        [InlineKeyboardButton("🎳 Боулинг", callback_data="casino_game_bowling"),
         InlineKeyboardButton("🎯 Дартс", callback_data="casino_game_darts")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="casino_achievements"),
         InlineKeyboardButton("📜 Правила", callback_data="casino_rules")],
        [InlineKeyboardButton("🔙 Назад", callback_data="city_hightown")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_casino_rules_view(min_bet: int, max_bet: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "<b>📜 Правила Казино ХайТаун</b>\n\n"
        "🎮 <b>Доступные игры:</b>\n\n"
        "🪙 <b>Монетка</b>\n"
        "├ Выберите Орёл или Решка\n"
        "├ Шанс: 50%\n"
        "└ Выплата: x2\n\n"
        "🎲 <b>Кости</b>\n"
        "├ Выберите число от 1 до 6\n"
        "├ Шанс: ~17%\n"
        "└ Выплата: x5.5\n\n"
        "📊 <b>Больше/Меньше</b>\n"
        "├ Выберите больше или меньше 50\n"
        "├ Шанс: 49%\n"
        "└ Выплата: x1.95\n\n"
        "🎡 <b>Рулетка (цвет)</b>\n"
        "├ Выберите Красное или Чёрное\n"
        "├ Шанс: ~49%\n"
        "└ Выплата: x2\n\n"
        "🎯 <b>Рулетка (число)</b>\n"
        "├ Угадай число 0-36\n"
        "├ Шанс: ~3%\n"
        "└ Выплата: x35\n\n"
        "🎰 <b>Слоты</b>\n"
        "├ Три символа в ряд\n"
        "├ Шанс: 15%\n"
        "└ Выплата: до x20\n\n"
        f"⚙️ <b>Лимиты:</b>\n"
        f"• Мин. ставка: {int(min_bet)} септимов\n"
        f"• Макс. ставка: {int(max_bet)} септимов\n\n"
        "🏆 <b>Достижения:</b>\n"
        "Получайте награды за победы!\n\n"
        "⚠️ Играйте ответственно!"
    )
    keyboard = [
        [InlineKeyboardButton("🔙 В Казино", callback_data="city_casino")],
        [InlineKeyboardButton("🔙 Назад", callback_data="city_hightown")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_game_choice_view(game_type: str, game_info: dict, coins: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"📋 {game_info['description']}\n"
        f"🎯 Шанс выигрыша: {int(game_info['win_prob'] * 100)}%\n"
        f"💰 Множитель: x{game_info['multiplier']}\n\n"
        f"💵 Ваш баланс: <b>{int(coins or 0)}</b> септимов\n\n"
    )

    keyboard: list[list[InlineKeyboardButton]] = []
    if game_type == "coin_flip":
        text += "Выберите на что ставите:"
        keyboard = [
            [InlineKeyboardButton("🦅 Орёл", callback_data=f"casino_choice_{game_type}_heads"),
             InlineKeyboardButton("🪙 Решка", callback_data=f"casino_choice_{game_type}_tails")],
            [InlineKeyboardButton("🔙 Назад", callback_data="city_casino")],
        ]
    elif game_type == "dice":
        text += "Выберите число от 1 до 6:"
        keyboard = [
            [InlineKeyboardButton("1️⃣", callback_data=f"casino_choice_{game_type}_1"),
             InlineKeyboardButton("2️⃣", callback_data=f"casino_choice_{game_type}_2"),
             InlineKeyboardButton("3️⃣", callback_data=f"casino_choice_{game_type}_3")],
            [InlineKeyboardButton("4️⃣", callback_data=f"casino_choice_{game_type}_4"),
             InlineKeyboardButton("5️⃣", callback_data=f"casino_choice_{game_type}_5"),
             InlineKeyboardButton("6️⃣", callback_data=f"casino_choice_{game_type}_6")],
            [InlineKeyboardButton("🔙 Назад", callback_data="city_casino")],
        ]
    elif game_type == "high_low":
        text += "Число будет больше или меньше 50?"
        keyboard = [
            [InlineKeyboardButton("📈 Больше 50", callback_data=f"casino_choice_{game_type}_high"),
             InlineKeyboardButton("📉 Меньше 50", callback_data=f"casino_choice_{game_type}_low")],
            [InlineKeyboardButton("🔙 Назад", callback_data="city_casino")],
        ]
    elif game_type == "roulette_color":
        text += "Выберите цвет:"
        keyboard = [
            [InlineKeyboardButton("🔴 Красное", callback_data=f"casino_choice_{game_type}_red"),
             InlineKeyboardButton("⚫ Чёрное", callback_data=f"casino_choice_{game_type}_black")],
            [InlineKeyboardButton("🔙 Назад", callback_data="city_casino")],
        ]
    elif game_type == "roulette_number":
        text += "Выберите число от 0 до 36:"
        for i in range(0, 37, 6):
            row = []
            for num in range(i, min(i + 6, 37)):
                row.append(InlineKeyboardButton(str(num), callback_data=f"casino_choice_{game_type}_{num}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="city_casino")])

    return text, InlineKeyboardMarkup(keyboard)


def build_bet_selection_view(game_type: str, game_info: dict, coins: int, choice: str | None) -> tuple[str, InlineKeyboardMarkup]:
    choice_text = ""
    if choice:
        if game_type == "coin_flip":
            choice_text = f"Ваш выбор: <b>{'🦅 Орёл' if choice == 'heads' else '🪙 Решка'}</b>\n"
        elif game_type == "dice":
            choice_text = f"Ваше число: <b>{choice}</b>\n"
        elif game_type == "high_low":
            choice_text = f"Ваш выбор: <b>{'📈 Больше 50' if choice == 'high' else '📉 Меньше 50'}</b>\n"
        elif game_type == "roulette_color":
            choice_text = f"Ваш цвет: <b>{'🔴 Красное' if choice == 'red' else '⚫ Чёрное'}</b>\n"
        elif game_type == "roulette_number":
            choice_text = f"Ваше число: <b>{choice}</b>\n"

    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"{choice_text}"
        f"🎯 Шанс выигрыша: {int(game_info['win_prob'] * 100)}%\n"
        f"💰 Множитель: до x{game_info['multiplier'] if game_type != 'slots' else '10'}\n\n"
        f"💵 Ваш баланс: <b>{int(coins or 0)}</b> септимов\n\n"
        "Выберите ставку:"
    )

    if choice:
        bet_callback = f"casino_bet_{game_type}_{choice}"
        change_button = [InlineKeyboardButton("🔙 Изменить выбор", callback_data=f"casino_game_{game_type}")]
    else:
        bet_callback = f"casino_bet_{game_type}_none"
        change_button = []

    keyboard = [
        [InlineKeyboardButton("💵 100", callback_data=f"{bet_callback}_100"),
         InlineKeyboardButton("💵 500", callback_data=f"{bet_callback}_500")],
        [InlineKeyboardButton("💵 1,000", callback_data=f"{bet_callback}_1000"),
         InlineKeyboardButton("💵 5,000", callback_data=f"{bet_callback}_5000")],
        [InlineKeyboardButton("💵 10,000", callback_data=f"{bet_callback}_10000"),
         InlineKeyboardButton("💵 25,000", callback_data=f"{bet_callback}_25000")],
    ]
    if change_button:
        keyboard.append(change_button)
    keyboard.append([InlineKeyboardButton("🔙 Назад в казино", callback_data="city_casino")])
    return text, InlineKeyboardMarkup(keyboard)
