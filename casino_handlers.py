import logging

from telegram.error import BadRequest

import database as db
from constants import CASINO_GAMES, CASINO_MAX_BET, CASINO_MIN_BET
from casino_logic import build_casino_repeat_callback, casino_game_type_from_info
from casino_ui import (
    build_bet_selection_view,
    build_casino_rules_view,
    build_city_casino_view,
    build_game_choice_view,
)


logger = logging.getLogger(__name__)


async def show_city_casino_screen(update, context):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, "coins", 0) or 0)
    casino_wins = int(getattr(player, "casino_wins", 0) or 0)
    casino_losses = int(getattr(player, "casino_losses", 0) or 0)
    text, reply_markup = build_city_casino_view(coins, casino_wins, casino_losses)

    message = query.message
    if getattr(message, "photo", None) or getattr(message, "document", None) or getattr(message, "video", None):
        try:
            await message.delete()
        except BadRequest:
            pass
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except BadRequest:
            await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def show_casino_rules_screen(update, context):
    query = update.callback_query
    await query.answer()
    text, reply_markup = build_casino_rules_view(CASINO_MIN_BET, CASINO_MAX_BET)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def show_casino_game_screen(update, context, game_type: str):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = db.get_or_create_player(user.id, user.username or user.first_name)
    coins = int(getattr(player, "coins", 0) or 0)
    game_info = CASINO_GAMES.get(game_type, CASINO_GAMES["coin_flip"])

    if game_type in ["coin_flip", "dice", "high_low", "roulette_color", "roulette_number"]:
        await show_game_choice_screen(update, context, game_type, game_info, coins)
    else:
        await show_bet_selection_screen(update, context, game_type, game_info, coins, None)


async def show_game_choice_screen(update, context, game_type: str, game_info: dict, coins: int):
    query = update.callback_query
    user = query.from_user
    text, reply_markup = build_game_choice_view(game_type, game_info, coins)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def show_bet_selection_screen(update, context, game_type: str, game_info: dict, coins: int, choice):
    query = update.callback_query
    user = query.from_user
    text, reply_markup = build_bet_selection_view(game_type, game_info, coins, choice)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def show_game_result_message(
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
    game_type: str | None = None,
    player_choice: str | None = None,
):
    if win:
        profit = winnings - bet_amount
        result_line = f"🎉 <b>ПОБЕДА!</b> 🎉\n💰 Выигрыш: +{profit} септимов"
    else:
        result_line = f"💥 <b>Поражение</b>\n💸 Потеряно: {bet_amount} септимов"

    achievement_text = ""
    if achievement_bonus:
        ach = achievement_bonus["achievement"]
        achievement_text = (
            f"\n\n🏆 <b>Достижение разблокировано!</b>\n{ach['name']}: {ach['desc']}\n"
            f"💰 Бонус: +{achievement_bonus['bonus']} септимов"
        )

    text = (
        f"<b>{game_info['emoji']} {game_info['name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{result_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{result_line}\n"
        f"💵 Баланс: <b>{new_balance}</b> септимов"
        f"{achievement_text}"
    )

    logger.info(f"Showing casino result, text length: {len(text)}, has result_text: {bool(result_text)}")

    resolved_game_type = game_type or casino_game_type_from_info(game_info, CASINO_GAMES)
    keyboard = []
    if resolved_game_type:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard.append([InlineKeyboardButton("🔄 Играть ещё", callback_data=f"casino_game_{resolved_game_type}")])
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚡ Повторить ставку",
                    callback_data=build_casino_repeat_callback(resolved_game_type, player_choice, bet_amount),
                )
            ]
        )
        keyboard.append([InlineKeyboardButton("🎮 Другая игра", callback_data="city_casino")])
        keyboard.append([InlineKeyboardButton("🔙 Выход", callback_data="city_hightown")])
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = None

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=reply_markup, parse_mode="HTML")
