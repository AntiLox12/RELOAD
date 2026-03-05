import random


def casino_adjusted_prob(base_prob: float, luck_mult: float) -> float:
    base = max(0.0, min(1.0, float(base_prob)))
    adj = base * max(0.1, min(5.0, float(luck_mult)))
    return max(0.0, min(0.95, adj))


def casino_roll_win(base_prob: float, luck_mult: float) -> bool:
    return random.random() < casino_adjusted_prob(base_prob, luck_mult)


def casino_extra_win_chance(base_prob: float, luck_mult: float) -> float:
    base = max(0.0, min(1.0, float(base_prob)))
    adj = casino_adjusted_prob(base, luck_mult)
    return max(0.0, adj - base)


def casino_game_type_from_info(game_info: dict, casino_games: dict) -> str:
    for game_type, info in casino_games.items():
        if info is game_info:
            return game_type
    for game_type, info in casino_games.items():
        if info == game_info:
            return game_type
    return "coin_flip"


def parse_casino_game_choice(payload: str, casino_games: dict) -> tuple[str | None, str | None]:
    for game_type in sorted(casino_games.keys(), key=len, reverse=True):
        prefix = f"{game_type}_"
        if payload == game_type:
            return game_type, None
        if payload.startswith(prefix):
            return game_type, payload[len(prefix):]
    return None, None


def build_casino_repeat_callback(game_type: str, choice: str | None, bet_amount: int) -> str:
    safe_choice = choice if choice is not None else "-"
    return f"casino_repeat|{game_type}|{safe_choice}|{int(bet_amount)}"


def play_coin_flip(player_choice: str, luck_mult: float):
    win = casino_roll_win(0.5, luck_mult)
    result = player_choice if win else ("tails" if player_choice == "heads" else "heads")

    result_emoji = "🦅 Орёл" if result == "heads" else "🪙 Решка"
    choice_emoji = "🦅 Орёл" if player_choice == "heads" else "🪙 Решка"

    result_text = (
        f"🎲 Ваш выбор: <b>{choice_emoji}</b>\n"
        f"🪙 Выпало: <b>{result_emoji}</b>\n"
        f"{'✅ Совпадение!' if win else '❌ Не угадали'}"
    )
    return win, result_text


def play_dice(game_info: dict, player_choice: str, luck_mult: float):
    player_number = int(player_choice)
    win = casino_roll_win(1 / 6, luck_mult)
    if win:
        dice_result = player_number
    else:
        other = [n for n in range(1, 7) if n != player_number]
        dice_result = random.choice(other)

    result_text = (
        f"🎯 Ваше число: <b>{player_number}</b>\n"
        f"🎲 Выпало: <b>{dice_result}</b>\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали'}"
    )
    return win, result_text, game_info["multiplier"]


def play_high_low(player_choice: str, luck_mult: float):
    win = casino_roll_win(0.49, luck_mult)
    if player_choice == "high":
        number = random.randint(51, 100) if win else random.randint(1, 50)
    else:
        number = random.randint(1, 49) if win else random.randint(50, 100)

    is_higher = number > 50
    choice_text = "📈 Больше 50" if player_choice == "high" else "📉 Меньше 50"
    actual_text = "📈 Больше 50" if is_higher else "📉 Меньше 50"
    result_text = (
        f"🎯 Ваш выбор: <b>{choice_text}</b>\n"
        f"📊 Выпало: <b>{number}</b> ({actual_text})\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали'}"
    )
    return win, result_text


def play_roulette_color(player_choice: str, luck_mult: float):
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
    win = casino_roll_win(18 / 37, luck_mult)
    if win:
        if player_choice == "red":
            number = random.choice(red_numbers)
            color_code = "red"
            color = "🔴 Красное"
        else:
            number = random.choice(black_numbers)
            color_code = "black"
            color = "⚫ Чёрное"
    else:
        if random.random() < 0.15:
            number = 0
            color_code = "green"
            color = "🟢 Зелёное"
        elif player_choice == "red":
            number = random.choice(black_numbers)
            color_code = "black"
            color = "⚫ Чёрное"
        else:
            number = random.choice(red_numbers)
            color_code = "red"
            color = "🔴 Красное"

    choice_text = "🔴 Красное" if player_choice == "red" else "⚫ Чёрное"
    result_text = (
        f"🎯 Ваш выбор: <b>{choice_text}</b>\n"
        f"🎡 Выпало: <b>{number}</b> ({color})\n"
        f"{'✅ Угадали!' if win else '❌ Не угадали' if color_code != 'green' else '❌ Выпал зелёный 0'}"
    )
    return win, result_text


def play_roulette_number(game_info: dict, player_choice: str, luck_mult: float):
    player_number = int(player_choice)
    win = casino_roll_win(1 / 37, luck_mult)
    if win:
        number = player_number
    else:
        other = [n for n in range(0, 37) if n != player_number]
        number = random.choice(other)

    result_text = (
        f"🎯 Ваше число: <b>{player_number}</b>\n"
        f"🎡 Выпало: <b>{number}</b>\n"
        f"{'✅ Точное попадание!' if win else '❌ Не угадали'}"
    )
    return win, result_text, game_info["multiplier"]


def play_slots(slot_symbols: list[str], slot_payouts: dict, slots_win_prob: float, luck_mult: float):
    win = casino_roll_win(slots_win_prob, luck_mult)
    if win:
        combination = random.choice(list(slot_payouts.keys()))
        slot1, slot2, slot3 = combination[0], combination[1], combination[2]
        multiplier = slot_payouts.get(combination, 3.0)
    else:
        while True:
            slot1 = random.choice(slot_symbols)
            slot2 = random.choice(slot_symbols)
            slot3 = random.choice(slot_symbols)
            if not (slot1 == slot2 == slot3):
                break
        multiplier = 0

    if win:
        result_text = (
            f"🎰 Результат:\n"
            f"┏━━━━━━━━━━━━━┓\n"
            f"┃  <b>{slot1} {slot2} {slot3}</b>  ┃\n"
            f"┗━━━━━━━━━━━━━┛\n"
            f"💫 Множитель: <b>x{int(multiplier)}</b>"
        )
    else:
        result_text = (
            f"🎰 Результат:\n"
            f"┏━━━━━━━━━━━━━┓\n"
            f"┃  <b>{slot1} {slot2} {slot3}</b>  ┃\n"
            f"┗━━━━━━━━━━━━━┛"
        )

    return win, result_text, multiplier
