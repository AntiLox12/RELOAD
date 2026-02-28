import os
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaAudio
from telegram.ext import ContextTypes
import database as db
from constants import (
    SWAGA_RARITIES, 
    SWAGA_COLOR_EMOJIS, 
    SWAGA_RARITY_ORDER, 
    SWAGA_CHEST_DROP_CHANCES
)
import logging

logger = logging.getLogger(__name__)

async def show_swaga_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню магазина Сваги."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    text = (
        "🛒 <b>Свага Шоп</b>\n\n"
        "Добро пожаловать в Свага Шоп! Здесь ты можешь обменять накопленные "
        "Свага Карточки на Свага Сундуки, а также открыть их, чтобы получить уникальные треки!\n\n"
        "<i>Курс обмена: 100 карточек = 1 сундук той же редкости.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🎴 Мои Свага Карточки", callback_data="swaga_cards_inv")],
        [InlineKeyboardButton("📦 Мои Свага Сундуки", callback_data="swaga_chests_inv")],
        [InlineKeyboardButton("💿 Мои Свага Треки", callback_data="swaga_tracks_inv")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def show_swaga_cards_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвентарь Свага Карточек и обмен на сундуки."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    try:
        cards = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id).all()
        card_counts = {c.rarity: c.quantity for c in cards}
    finally:
        db_session.close()

    text = "🎴 <b>Мои Свага Карточки</b>\n\nОбменивай 100 карточек на 1 сундук той же редкости.\n\n"
    has_cards = False
    keyboard = []

    for rarity in SWAGA_RARITY_ORDER:
        count = card_counts.get(rarity, 0)
        emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
        if count > 0:
            has_cards = True
            text += f"{emoji} <b>{rarity}</b>: {count} шт.\n"
            if count >= 100:
                keyboard.append([InlineKeyboardButton(f"🔄 Обменять 100 {emoji} {rarity}", callback_data=f"swaga_exchange_{rarity}")])

    if not has_cards:
        text += "<i>У тебя пока нет карточек. Ищи энергетики!</i>\n"

    keyboard.append([InlineKeyboardButton("🔙 Назад в Свага Шоп", callback_data="swaga_shop")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_swaga_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str):
    """Обработчик обмена карточек на сундуки."""
    query = update.callback_query
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    success = False
    try:
        card_inv = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id, rarity=rarity).first()
        if card_inv and card_inv.quantity >= 100:
            card_inv.quantity -= 100
            
            chest_inv = db_session.query(db.SwagaChestInventory).filter_by(user_id=user_id, rarity=rarity).first()
            if chest_inv:
                chest_inv.quantity += 1
            else:
                db_session.add(db.SwagaChestInventory(user_id=user_id, rarity=rarity, quantity=1))
            
            db_session.commit()
            success = True
        else:
            await query.answer("Недостаточно карточек для обмена!", show_alert=True)
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error in swaga exchange: {e}")
        await query.answer("Ошибка обмена!", show_alert=True)
    finally:
        db_session.close()

    if success:
        emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
        await query.answer(f"✅ Ты успешно обменял 100 карточек на 1 {emoji} сундук!", show_alert=True)
        await show_swaga_cards_inv(update, context)


async def show_swaga_chests_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвентарь Свага Сундуков и возможность их открыть."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    try:
        chests = db_session.query(db.SwagaChestInventory).filter_by(user_id=user_id).all()
        chest_counts = {c.rarity: c.quantity for c in chests}
    finally:
        db_session.close()

    text = "📦 <b>Мои Свага Сундуки</b>\n\n"
    has_chests = False
    keyboard = []

    for rarity in SWAGA_RARITY_ORDER:
        count = chest_counts.get(rarity, 0)
        emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
        if count > 0:
            has_chests = True
            text += f"{emoji} <b>{rarity} Сундук</b>: {count} шт.\n"
            keyboard.append([InlineKeyboardButton(f"🔓 Открыть {emoji} {rarity} Сундук", callback_data=f"swaga_open_{rarity}")])

    if not has_chests:
        text += "<i>У тебя пока нет сундуков. Сначала обменяй карточки!</i>\n"

    keyboard.append([InlineKeyboardButton("🔙 Назад в Свага Шоп", callback_data="swaga_shop")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_swaga_open_chest(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str):
    """Открытие сундука."""
    query = update.callback_query
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    chest_success = False
    try:
        chest_inv = db_session.query(db.SwagaChestInventory).filter_by(user_id=user_id, rarity=rarity).first()
        if chest_inv and chest_inv.quantity > 0:
            chest_inv.quantity -= 1
            db_session.commit()
            chest_success = True
        else:
            await query.answer("У тебя нет сундуков этой редкости!", show_alert=True)
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error checking chest: {e}")
        await query.answer("Ошибка при попытке открыть сундук!", show_alert=True)
    finally:
        db_session.close()

    if not chest_success:
        return

    # Логика выпадения трека:
    drop_chances = SWAGA_CHEST_DROP_CHANCES.get(rarity, {})
    
    # Нормализуем шансы (на всякий случай)
    total_chance = sum(drop_chances.values())
    if total_chance <= 0:
        await query.answer("В этом сундуке нет наград!", show_alert=True)
        return
        
    r = random.random() * total_chance
    cumulative = 0.0
    dropped_rarity = None
    for r_name, chance in drop_chances.items():
        cumulative += chance
        if r <= cumulative:
            dropped_rarity = r_name
            break
            
    if not dropped_rarity:
        dropped_rarity = list(drop_chances.keys())[0]

    db_session = db.SessionLocal()
    track_dropped = None
    already_owned = False
    try:
        # Выбираем случайный трек данной выпавшей редкости
        potential_tracks = db_session.query(db.SwagaTrack).filter_by(rarity=dropped_rarity).all()
        if potential_tracks:
            track_dropped = random.choice(potential_tracks)
            
            # Добавляем в инвентарь (или обновляем)
            player_track = db_session.query(db.PlayerSwagaTrack).filter_by(user_id=user_id, track_id=track_dropped.id).first()
            if player_track:
                already_owned = True
            else:
                db_session.add(db.PlayerSwagaTrack(user_id=user_id, track_id=track_dropped.id))
                db_session.commit()
    except Exception as e:
        logger.error(f"Error dropping track: {e}")
    finally:
        db_session.close()

    await query.message.delete()

    emoji = SWAGA_COLOR_EMOJIS.get(dropped_rarity, '⚫')
    if track_dropped:
        text = f"🎉 <b>Ты открыл сундук и получил трек!</b>\n\n"
        text += f"<b>Редкость:</b> {emoji} {dropped_rarity}\n"
        text += f"<b>Название:</b> {track_dropped.name}\n"
        if track_dropped.description and track_dropped.description != '-':
            text += f"<i>{track_dropped.description}</i>\n"
            
        if already_owned:
            text += f"\n<i>(У тебя уже есть этот трек, но ты можешь им наслаждаться!)</i>\n"
        else:
            text += f"\n<i>Новая находка добавлена в коллекцию!</i>\n"
        
        # У нас есть audio_file_id, отправляем аудио с описанием\n
        keyboard = [[InlineKeyboardButton("🔙 Мои сундуки", callback_data="swaga_chests_inv")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            if track_dropped.audio_file_id:
                # Если есть фото: 
                # Telegram не позволяет отправлять Аудио с прикрепленным Фото в одном сообщении (только обложку mp3 если вшита) 
                # Так что отправляем сначала обложку (если есть), затем аудио:
                if track_dropped.photo_file_id:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=track_dropped.photo_file_id,
                        caption=f"Обложка трека: <b>{track_dropped.name}</b>",
                        parse_mode='HTML'
                    )
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=track_dropped.audio_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            elif track_dropped.photo_file_id:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=track_dropped.photo_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Failed to send track media: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text=text + "\n(Ошибка загрузки медиа файла)",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        text = f"😔 В базе данных нет треков редкости {emoji} {dropped_rarity}!\n<i>(Сундук потрачен, добавьте треки в базу!)</i>"
        keyboard = [[InlineKeyboardButton("🔙 Мои сундуки", callback_data="swaga_chests_inv")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


async def show_swaga_tracks_inv(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Инвентарь Свага Треков (пагинация если их много)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    PER_PAGE = 10

    db_session = db.SessionLocal()
    tracks = []
    try:
        # Подгружаем все треки игрока
        user_tracks = db_session.query(db.PlayerSwagaTrack).filter_by(user_id=user_id).all()
        track_ids = [pt.track_id for pt in user_tracks]
        
        if track_ids:
            tracks = db_session.query(db.SwagaTrack).filter(db.SwagaTrack.id.in_(track_ids)).all()
            
            # Сортируем по редкости:
            sorted_tracks = []
            for rarity in SWAGA_RARITY_ORDER:
                for t in tracks:
                    if t.rarity == rarity:
                        sorted_tracks.append(t)
            tracks = sorted_tracks
    finally:
        db_session.close()

    if not tracks:
        text = "💿 <b>Мои Свага Треки</b>\n\nУ тебя пока нет треков. Открывай Свага Сундуки!"
        keyboard = [[InlineKeyboardButton("🔙 Назад в Свага Шоп", callback_data="swaga_shop")]]
        try:
            await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return

    total_pages = max(1, (len(tracks) - 1) // PER_PAGE + 1)
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    page_tracks = tracks[start_idx:end_idx]

    text = f"💿 <b>Мои Свага Треки</b> (Стр {page}/{total_pages})\n\n"
    keyboard = []

    for trk in page_tracks:
        emoji = SWAGA_COLOR_EMOJIS.get(trk.rarity, '⚫')
        keyboard.append([InlineKeyboardButton(f"{emoji} {trk.name}", callback_data=f"swaga_play_{trk.id}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"swaga_tracks_page_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"swaga_tracks_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 Назад в Свага Шоп", callback_data="swaga_shop")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_swaga_play_track(update: Update, context: ContextTypes.DEFAULT_TYPE, track_id: int):
    """Play track from inventory."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    track = None
    try:
        # Убедимся что он есть у пользователя
        player_track = db_session.query(db.PlayerSwagaTrack).filter_by(user_id=user_id, track_id=track_id).first()
        if player_track:
            track = db_session.query(db.SwagaTrack).filter_by(id=track_id).first()
    finally:
        db_session.close()

    if not track:
        await query.answer("Трек не найден или недоступен.", show_alert=True)
        return

    emoji = SWAGA_COLOR_EMOJIS.get(track.rarity, '⚫')
    text = f"💿 <b>{emoji} {track.name}</b>\n\n<i>{track.description}</i>"
    keyboard = [[InlineKeyboardButton("🔙 К списку треков", callback_data="swaga_tracks_page_1")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.delete()
    
    try:
        if track.audio_file_id:
            if track.photo_file_id:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=track.photo_file_id,
                    caption=f"Обложка трека: <b>{track.name}</b>",
                    parse_mode='HTML'
                )
            await context.bot.send_audio(
                chat_id=user_id,
                audio=track.audio_file_id,
                caption=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=text + "\n(Аудиофайл отсутствует)",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to play track: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="Ошибка загрузки трека",
            reply_markup=reply_markup
        )
