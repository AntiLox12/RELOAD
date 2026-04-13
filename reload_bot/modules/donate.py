from __future__ import annotations

from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, PreCheckoutQueryHandler, filters

from reload_bot.runtime import BotRuntime


async def show_donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    player = runtime.db.get_or_create_player(
        user.id,
        username=getattr(user, "username", None),
        display_name=(getattr(user, "full_name", None) or getattr(user, "first_name", None)),
    )
    lang = getattr(player, "language", "ru") or "ru"

    keyboard = [
        [InlineKeyboardButton(option["label"], callback_data=f"donate_pay:{option['stars']}")]
        for option in runtime.donate_options
    ]
    keyboard.append([InlineKeyboardButton("🔙 Назад" if lang == "ru" else "🔙 Back", callback_data="menu")])

    await query.message.edit_text(
        text=runtime.t(lang, "donate_title"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def donate_send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    try:
        stars_amount = int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    if stars_amount not in {option["stars"] for option in runtime.donate_options}:
        return

    user = query.from_user
    player = runtime.db.get_or_create_player(
        user.id,
        username=getattr(user, "username", None),
        display_name=(getattr(user, "full_name", None) or getattr(user, "first_name", None)),
    )
    lang = getattr(player, "language", "ru") or "ru"

    title = "Поддержка автора" if lang == "ru" else "Support the author"
    description = (
        f"Донат {stars_amount} ⭐ для поддержки разработчика бота"
        if lang == "ru"
        else f"Donate {stars_amount} ⭐ to support the bot developer"
    )

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=title,
        description=description,
        payload=f"donate_{stars_amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(title, stars_amount)],
    )


async def donate_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    payload = str(query.invoice_payload or "")
    if payload.startswith("donate_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Неизвестный платёж")


async def donate_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    payment = getattr(update.message, "successful_payment", None)
    if not payment:
        return
    payload = str(payment.invoice_payload or "")
    if not payload.startswith("donate_"):
        return

    user = update.effective_user
    amount = int(payment.total_amount or 0)
    charge_id = str(payment.telegram_payment_charge_id or "")
    runtime.logger.info("[DONATE] user_id=%s donated %s stars (charge_id=%s)", user.id, amount, charge_id)

    player = runtime.db.get_or_create_player(
        user.id,
        username=getattr(user, "username", None),
        display_name=(getattr(user, "full_name", None) or getattr(user, "first_name", None)),
    )
    lang = getattr(player, "language", "ru") or "ru"

    thank_text = runtime.t(lang, "donate_thanks").format(amount=amount)
    await update.message.reply_text(thank_text, parse_mode="HTML")


async def _donate_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE, runtime: BotRuntime) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    if data == "donate_menu":
        await show_donate_menu(update, context, runtime)
    elif data.startswith("donate_pay:"):
        await donate_send_invoice(update, context, runtime)


def register_handlers(application, runtime: BotRuntime) -> None:
    application.add_handler(
        CallbackQueryHandler(
            partial(_donate_callback_router, runtime=runtime),
            pattern=r"^(donate_menu|donate_pay:)",
        )
    )
    application.add_handler(PreCheckoutQueryHandler(partial(donate_pre_checkout, runtime=runtime)))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, partial(donate_successful_payment, runtime=runtime)))
