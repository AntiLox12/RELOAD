import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler,
    CallbackQueryHandler
)
import database as db
from constants import SWAGA_RARITY_ORDER, SWAGA_COLOR_EMOJIS, ADMIN_USERNAMES
import logging

logger = logging.getLogger(__name__)

# Состояния для добавления Свага Трека
SWAGA_NAME, SWAGA_DESC, SWAGA_PHOTO, SWAGA_AUDIO, SWAGA_RARITY = range(5)

async def check_admin(update: Update) -> bool:
    user = update.effective_user
    if user.username in ADMIN_USERNAMES:
        return True
    if db.get_admin_level(user.id) >= 2:
        return True
    await update.message.reply_text("У вас нет прав для выполнения этой команды.")
    return False

async def addswagatrack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога добавления трека."""
    if not await check_admin(update):
        return ConversationHandler.END

    await update.message.reply_text(
        "🎧 Добавление нового Свага Трека.\n\nШаг 1: Введите <b>Название</b> трека:",
        parse_mode='HTML'
    )
    return SWAGA_NAME

async def swaga_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['swaga_name'] = update.message.text
    await update.message.reply_text("Шаг 2: Введите <b>Описание</b> трека (или отправьте '-', чтобы пропустить):", parse_mode='HTML')
    return SWAGA_DESC

async def swaga_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['swaga_desc'] = "" if text == '-' else text
    await update.message.reply_text("Шаг 3: Отправьте <b>Обложку (Фото)</b> для трека (или отправьте слово 'скип', чтобы пропустить):", parse_mode='HTML')
    return SWAGA_PHOTO

async def swaga_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['swaga_photo'] = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.lower() == 'скип':
        context.user_data['swaga_photo'] = None
    else:
        await update.message.reply_text("Пожалуйста, отправьте фото или 'скип'.")
        return SWAGA_PHOTO

    await update.message.reply_text("Шаг 4: Отправьте <b>Аудиофайл</b> трека:", parse_mode='HTML')
    return SWAGA_AUDIO

async def swaga_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.audio and not getattr(update.message, 'voice', None):
        await update.message.reply_text("Это не аудиофайл. Пожалуйста, отправьте трек (аудиофайл или войс).")
        return SWAGA_AUDIO

    if update.message.audio:
        context.user_data['swaga_audio'] = update.message.audio.file_id
    else:
        context.user_data['swaga_audio'] = update.message.voice.file_id

    # Подготовка выбора редкости
    text = "Шаг 5: Выберите редкость (введите номер):\n"
    for i, r in enumerate(SWAGA_RARITY_ORDER, 1):
        emoji = SWAGA_COLOR_EMOJIS.get(r, '⚫')
        text += f"{i}. {emoji} {r}\n"

    await update.message.reply_text(text)
    return SWAGA_RARITY

async def swaga_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Введите число от 1 до " + str(len(SWAGA_RARITY_ORDER)))
        return SWAGA_RARITY

    idx = int(text) - 1
    if idx < 0 or idx >= len(SWAGA_RARITY_ORDER):
        await update.message.reply_text("Неверный номер. Выберите из списка.")
        return SWAGA_RARITY

    rarity = SWAGA_RARITY_ORDER[idx]
    name = context.user_data.get('swaga_name')
    desc = context.user_data.get('swaga_desc')
    photo_id = context.user_data.get('swaga_photo')
    audio_id = context.user_data.get('swaga_audio')

    db_session = db.SessionLocal()
    try:
        new_track = db.SwagaTrack(
            name=name,
            description=desc,
            photo_file_id=photo_id,
            audio_file_id=audio_id,
            rarity=rarity
        )
        db_session.add(new_track)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error saving SwagaTrack: {e}")
        await update.message.reply_text("Ошибка при сохранении трека в БД.")
        db_session.close()
        return ConversationHandler.END

    db_session.close()

    emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
    await update.message.reply_text(f"✅ Трек <b>{name}</b> ({emoji} {rarity}) успешно добавлен!", parse_mode='HTML')
    return ConversationHandler.END

async def cancel_addswaga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление трека отменено.")
    return ConversationHandler.END

addswaga_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('addswagatrack', addswagatrack_start)],
    states={
        SWAGA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_name)],
        SWAGA_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_desc)],
        SWAGA_PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, swaga_photo)],
        SWAGA_AUDIO: [MessageHandler((filters.AUDIO | filters.VOICE) & ~filters.COMMAND, swaga_audio)],
        SWAGA_RARITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_rarity)],
    },
    fallbacks=[CommandHandler('cancel', cancel_addswaga)]
)

async def giveswagacards_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /giveswagacards <user_id> <rarity_id> <count>"""
    if not await check_admin(update):
        return

    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Использование: /giveswagacards <user_id> <номер редкости 1-6> <количество>")
        return

    target_str = args[0]
    rarity_idx = args[1]
    count = args[2]

    if not rarity_idx.isdigit() or not count.isdigit():
        await update.message.reply_text("ID редкости и количество должны быть числами.")
        return

    idx = int(rarity_idx) - 1
    if idx < 0 or idx >= len(SWAGA_RARITY_ORDER):
        await update.message.reply_text("Неверный номер редкости. Доступно от 1 до " + str(len(SWAGA_RARITY_ORDER)))
        return

    rarity = SWAGA_RARITY_ORDER[idx]
    count = int(count)

    db_session = db.SessionLocal()
    try:
        if target_str.isdigit():
            target_id = int(target_str)
        else:
            uname = target_str.lstrip('@')
            player = db_session.query(db.Player).filter(db.Player.username.ilike(uname)).first()
            if player:
                target_id = player.user_id
            else:
                await update.message.reply_text(f"Игрок с юзернеймом {target_str} не найден в БД.")
                db_session.close()
                return

        inv = db_session.query(db.SwagaCardInventory).filter_by(user_id=target_id, rarity=rarity).first()
        if inv:
            inv.quantity += count
        else:
            db_session.add(db.SwagaCardInventory(user_id=target_id, rarity=rarity, quantity=count))
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error giving swaga cards: {e}")
        await update.message.reply_text("Ошибка БД.")
        db_session.close()
        return

    db_session.close()
    
    emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
    await update.message.reply_text(f"Успешно выдано {count} карточек {emoji} {rarity} пользователю {target_id}")


async def swagaid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/swagaid — список всех добавленных Свага Треков."""
    if not await check_admin(update):
        return

    db_session = db.SessionLocal()
    try:
        tracks = db_session.query(db.SwagaTrack).all()
    finally:
        db_session.close()

    if not tracks:
        await update.message.reply_text("В базе пока нет Свага Треков.")
        return

    lines = ["📋 <b>Все Свага Треки в БД:</b>\n"]
    for t in tracks:
        emoji = SWAGA_COLOR_EMOJIS.get(t.rarity, '⚫')
        photo = "📷" if t.photo_file_id else "—"
        audio = "🎵" if t.audio_file_id else "—"
        lines.append(f"<b>ID {t.id}</b> | {emoji} {t.rarity} | {t.name} | фото: {photo} аудио: {audio}")

    text = "\n".join(lines)
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')
