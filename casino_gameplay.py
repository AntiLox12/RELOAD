import asyncio
import logging

import database as db
import casino_handlers
from casino_logic import (
    casino_roll_win,
    casino_extra_win_chance,
    play_coin_flip,
    play_dice,
    play_high_low,
    play_roulette_color,
    play_roulette_number,
    play_slots,
)
from constants import CASINO_GAMES, CASINO_ACHIEVEMENTS, CASINO_MAX_BET, CASINO_MIN_BET, SLOT_PAYOUTS, SLOT_SYMBOLS


logger = logging.getLogger(__name__)


def casino_take_bet(user_id: int, amount: int) -> int | None:
    res = db.decrement_coins(user_id, int(amount))
    if not res.get("ok"):
        return None
    return int(res.get("new_balance", 0) or 0)


def casino_record_result(user_id: int, win: bool) -> None:
    if win:
        db.add_casino_stats(user_id, wins_delta=1)
    else:
        db.add_casino_stats(user_id, losses_delta=1)


def check_casino_achievements(user_id, player):
    casino_wins = int(getattr(player, "casino_wins", 0) or 0)
    unlocked_achievements = getattr(player, "casino_achievements", "") or ""

    bonus = 0
    new_achievement = None
    for ach_id, ach_data in CASINO_ACHIEVEMENTS.items():
        if ach_id not in unlocked_achievements and casino_wins >= ach_data["wins"]:
            unlocked_achievements += f"{ach_id},"
            db.update_player_stats(user_id, casino_achievements=unlocked_achievements)
            bonus = ach_data["reward"]
            new_achievement = ach_data
            db.increment_coins(user_id, bonus)
            break

    return {"bonus": bonus, "achievement": new_achievement} if new_achievement else None


async def play_casino_game_native(update, context, game_type: str, bet_amount: int, player_choice: str = None, *, luck_mult_getter):
    query = update.callback_query
    user = query.from_user
    chat_id = user.id

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    current_coins = int(getattr(player, "coins", 0) or 0)
    if current_coins < bet_amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return

    if casino_take_bet(user.id, bet_amount) is None:
        await query.answer("Недостаточно средств!", show_alert=True)
        return

    emoji = CASINO_GAMES[game_type]["emoji"]
    dice_msg = await context.bot.send_dice(chat_id=chat_id, emoji=emoji)
    value = dice_msg.dice.value

    async def delete_dice_later(msg, delay):
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except Exception:
            pass

    asyncio.create_task(delete_dice_later(dice_msg, 8))
    await asyncio.sleep(4)

    win = False
    multiplier = 0.0
    result_text = ""
    base_prob = 0.0
    luck_mult = luck_mult_getter()

    if game_type == "dice":
        target = int(player_choice)
        win = value == target
        base_prob = 1 / 6
        multiplier = CASINO_GAMES["dice"]["multiplier"]
        result_text = f"🎲 Выпало: <b>{value}</b> (Ваш выбор: {target})"
    elif game_type == "slots":
        base_prob = 4 / 64
        if value == 64:
            win = True
            multiplier = 10.0
            result_text = "🎰 <b>ДЖЕКПОТ! (777)</b>"
        elif value == 43:
            win = True
            multiplier = 5.0
            result_text = "🍇 <b>Виноград!</b>"
        elif value == 22:
            win = True
            multiplier = 3.0
            result_text = "🍋 <b>Лимон!</b>"
        elif value == 1:
            win = True
            multiplier = 2.0
            result_text = "🍫 <b>BAR!</b>"
        else:
            result_text = "🎰 Попробуйте ещё раз!"
    elif game_type == "basketball":
        win = value in [4, 5]
        multiplier = CASINO_GAMES["basketball"]["multiplier"] if win else 0.0
        result_text = "🏀 <b>Попадание!</b>" if win else "🏀 Промах..."
        base_prob = 2 / 6
    elif game_type == "football":
        win = value in [3, 4, 5]
        multiplier = CASINO_GAMES["football"]["multiplier"] if win else 0.0
        result_text = "⚽ <b>ГОООЛ!</b>" if win else "⚽ Мимо ворот..."
        base_prob = 3 / 6
    elif game_type == "bowling":
        win = value == 6
        multiplier = CASINO_GAMES["bowling"]["multiplier"] if win else 0.0
        result_text = "🎳 <b>СТРАЙК!</b>" if win else f"🎳 Сбито кеглей: {value}"
        base_prob = 1 / 6
    elif game_type == "darts":
        win = value == 6
        multiplier = CASINO_GAMES["darts"]["multiplier"] if win else 0.0
        result_text = "🎯 <b>В ЯБЛОЧКО!</b>" if win else "🎯 Мимо центра..."
        base_prob = 1 / 6

    if not win and base_prob > 0:
        extra = casino_extra_win_chance(base_prob, luck_mult)
        if extra > 0 and casino_roll_win(extra, 1.0):
            win = True
            if multiplier <= 0:
                multiplier = CASINO_GAMES.get(game_type, {}).get("multiplier", 2.0)
            result_text += "\n🍀 Удача сработала!"

    winnings = 0
    if win:
        winnings = int(bet_amount * multiplier)
        db.increment_coins(user.id, winnings)
        casino_record_result(user.id, True)
    else:
        casino_record_result(user.id, False)

    player = db.get_or_create_player(user.id, user.username or user.first_name)
    achievement_bonus = check_casino_achievements(user.id, player)
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    new_balance = int(getattr(player, "coins", 0) or 0)
    game_info = CASINO_GAMES[game_type]

    await casino_handlers.show_game_result_message(
        query,
        user,
        game_info,
        bet_amount,
        win,
        winnings,
        new_balance,
        result_text,
        achievement_bonus,
        context,
        game_type,
        player_choice,
    )


async def play_casino_game(update, context, game_type: str, player_choice: str, bet_amount: int, *, get_lock, luck_mult_getter):
    if game_type in ["dice", "slots", "basketball", "football", "bowling", "darts"]:
        await play_casino_game_native(update, context, game_type, bet_amount, player_choice, luck_mult_getter=luck_mult_getter)
        return

    query = update.callback_query
    user = query.from_user

    if bet_amount < CASINO_MIN_BET or bet_amount > CASINO_MAX_BET:
        await query.answer(f"Ставка должна быть от {CASINO_MIN_BET} до {CASINO_MAX_BET}", show_alert=True)
        return

    lock = get_lock(f"user:{user.id}:casino")
    if lock.locked():
        await query.answer("Игра уже обрабатывается...", show_alert=True)
        return

    async with lock:
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        coins = int(getattr(player, "coins", 0) or 0)
        if coins < bet_amount:
            await query.answer("Недостаточно септимов", show_alert=True)
            return

        if casino_take_bet(user.id, bet_amount) is None:
            await query.answer("Недостаточно септимов", show_alert=True)
            return

        game_info = CASINO_GAMES.get(game_type, CASINO_GAMES["coin_flip"])
        win = False
        result_text = ""
        multiplier = game_info["multiplier"]
        luck_mult = luck_mult_getter()

        if game_type == "coin_flip":
            win, result_text = play_coin_flip(player_choice, luck_mult)
        elif game_type == "dice":
            win, result_text, multiplier = play_dice(game_info, player_choice, luck_mult)
        elif game_type == "high_low":
            win, result_text = play_high_low(player_choice, luck_mult)
        elif game_type == "roulette_color":
            win, result_text = play_roulette_color(player_choice, luck_mult)
        elif game_type == "roulette_number":
            win, result_text, multiplier = play_roulette_number(game_info, player_choice, luck_mult)
        elif game_type == "slots":
            win, result_text, multiplier = play_slots(SLOT_SYMBOLS, SLOT_PAYOUTS, CASINO_GAMES["slots"]["win_prob"], luck_mult)
        else:
            win = casino_roll_win(game_info["win_prob"], luck_mult)
            result_text = "🎲 Результат определён"

        winnings = 0
        if win:
            winnings = int(bet_amount * multiplier)
            db.increment_coins(user.id, winnings)
            casino_record_result(user.id, True)
            db.log_action(
                user_id=user.id,
                username=user.username or user.first_name,
                action_type="casino",
                action_details=f"{game_type}: ставка {bet_amount}, выигрыш {winnings}",
                amount=winnings,
                success=True,
            )
        else:
            casino_record_result(user.id, False)
            db.log_action(
                user_id=user.id,
                username=user.username or user.first_name,
                action_type="casino",
                action_details=f"{game_type}: ставка {bet_amount}, проигрыш",
                amount=-bet_amount,
                success=False,
            )

        achievement_bonus = check_casino_achievements(user.id, player)
        player = db.get_or_create_player(user.id, user.username or user.first_name)
        new_balance = int(getattr(player, "coins", 0) or 0)

        logger.info(f"Casino game result - Type: {game_type}, Win: {win}, Result text: {result_text[:50]}...")
        await casino_handlers.show_game_result_message(
            query,
            user,
            game_info,
            bet_amount,
            win,
            winnings,
            new_balance,
            result_text,
            achievement_bonus,
            context,
            game_type,
            player_choice,
        )
