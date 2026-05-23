from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from casino_logic import parse_casino_game_choice
from constants import CASINO_GAMES
from reload_bot.runtime import BotRuntime


CALLBACK_EXACT = {
    "city_casino",
    "casino_rules",
    "casino_achievements",
    "blackjack_hit",
    "blackjack_stand",
    "blackjack_double",
    "blackjack_surrender",
    "mines_cashout",
    "mines_forfeit",
    "mines_noop",
    "crash_cashout",
}

CALLBACK_PREFIXES = (
    "casino_game_",
    "casino_choice_",
    "casino_bet_",
    "casino_repeat|",
    "casino_play_",
    "blackjack_bet_",
    "mines_count_",
    "mines_bet_",
    "mines_click_",
    "crash_bet_",
)


def can_handle_callback(data: str | None) -> bool:
    if not data:
        return False
    return data in CALLBACK_EXACT or data.startswith(CALLBACK_PREFIXES)


async def _answer_error(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("Ошибка", show_alert=True)


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str | None,
    runtime: BotRuntime,
) -> bool:
    query = update.callback_query
    data = data or (query.data if query else "")
    if not query or not can_handle_callback(data):
        return False

    handlers = runtime.handlers

    if data == "city_casino":
        await handlers["show_city_casino"](update, context)
    elif data == "casino_rules":
        await handlers["show_casino_rules"](update, context)
    elif data == "casino_achievements":
        await handlers["show_casino_achievements_page"](update, context)
    elif data.startswith("casino_game_"):
        try:
            game_type = data.replace("casino_game_", "", 1)
            if game_type == "blackjack":
                await handlers["show_blackjack_bet_screen"](update, context)
            elif game_type == "mines":
                await handlers["show_mines_settings"](update, context)
            elif game_type == "crash":
                await handlers["show_crash_bet_screen"](update, context)
            else:
                await handlers["show_casino_game"](update, context, game_type)
        except Exception as e:
            runtime.logger.error("Error in casino_game: %s", e)
            await _answer_error(update)
    elif data.startswith("casino_choice_"):
        try:
            payload = data.replace("casino_choice_", "", 1)
            game_type, choice = parse_casino_game_choice(payload, CASINO_GAMES)
            if not game_type or choice is None:
                raise ValueError("bad casino_choice payload")
            player = runtime.db.get_or_create_player(
                query.from_user.id,
                query.from_user.username or query.from_user.first_name,
            )
            coins = int(getattr(player, "coins", 0) or 0)
            game_info = CASINO_GAMES.get(game_type, CASINO_GAMES["coin_flip"])
            await handlers["show_bet_selection_screen"](update, context, game_type, game_info, coins, choice)
        except Exception as e:
            runtime.logger.error("Error in casino_choice: %s", e)
            await _answer_error(update)
    elif data.startswith("casino_bet_"):
        try:
            parts = data.replace("casino_bet_", "", 1).rsplit("_", 1)
            amount = int(parts[1])
            game_type, choice = parse_casino_game_choice(parts[0], CASINO_GAMES)
            if not game_type:
                raise ValueError("bad casino_bet payload")
            if choice == "none":
                choice = None
            await handlers["play_casino_game"](update, context, game_type, choice, amount)
        except Exception as e:
            runtime.logger.error("Error in casino_bet: %s", e)
            await _answer_error(update)
    elif data.startswith("casino_repeat|"):
        try:
            _, game_type, raw_choice, raw_amount = data.split("|", 3)
            amount = int(raw_amount)
            choice = None if raw_choice == "-" else raw_choice
            await handlers["play_casino_game"](update, context, game_type, choice, amount)
        except Exception as e:
            runtime.logger.error("Error in casino_repeat: %s", e)
            await _answer_error(update)
    elif data.startswith("casino_play_"):
        try:
            parts = data.replace("casino_play_", "", 1).rsplit("_", 1)
            game_type = parts[0]
            amount = int(parts[1])
            await handlers["play_casino_game"](update, context, game_type, None, amount)
        except Exception as e:
            runtime.logger.error("Error in casino_play: %s", e)
            await _answer_error(update)
    elif data.startswith("blackjack_bet_"):
        try:
            amount = int(data.replace("blackjack_bet_", "", 1))
            await handlers["start_blackjack_game"](update, context, amount)
        except Exception as e:
            runtime.logger.error("Error in blackjack_bet: %s", e)
            await _answer_error(update)
    elif data == "blackjack_hit":
        await handlers["handle_blackjack_hit"](update, context)
    elif data == "blackjack_stand":
        await handlers["handle_blackjack_stand"](update, context)
    elif data == "blackjack_double":
        await handlers["handle_blackjack_double"](update, context)
    elif data == "blackjack_surrender":
        await handlers["handle_blackjack_surrender"](update, context)
    elif data.startswith("mines_count_"):
        try:
            mines_count = int(data.replace("mines_count_", "", 1))
            await handlers["show_mines_bet_screen"](update, context, mines_count)
        except Exception as e:
            runtime.logger.error("Error in mines_count: %s", e)
            await _answer_error(update)
    elif data.startswith("mines_bet_"):
        try:
            parts = data.replace("mines_bet_", "", 1).split("_")
            mines_count = int(parts[0])
            amount = int(parts[1])
            await handlers["start_mines_game"](update, context, mines_count, amount)
        except Exception as e:
            runtime.logger.error("Error in mines_bet: %s", e)
            await _answer_error(update)
    elif data.startswith("mines_click_"):
        try:
            cell_idx = int(data.replace("mines_click_", "", 1))
            await handlers["handle_mines_click"](update, context, cell_idx)
        except Exception as e:
            runtime.logger.error("Error in mines_click: %s", e)
            await _answer_error(update)
    elif data == "mines_cashout":
        await handlers["handle_mines_cashout"](update, context)
    elif data == "mines_forfeit":
        await handlers["handle_mines_forfeit"](update, context)
    elif data == "mines_noop":
        await query.answer()
    elif data.startswith("crash_bet_"):
        try:
            amount = int(data.replace("crash_bet_", "", 1))
            await handlers["start_crash_game"](update, context, amount)
        except Exception as e:
            runtime.logger.error("Error in crash_bet: %s", e)
            await _answer_error(update)
    elif data == "crash_cashout":
        await handlers["handle_crash_cashout"](update, context)
    return True
