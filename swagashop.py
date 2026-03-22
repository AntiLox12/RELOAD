import os
import random
from datetime import datetime
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

SWAGA_CHEST_EXCHANGE_COST = 100
SWAGA_UPGRADE_SUPER_RARE_TARGETS = {"Swaga", "Мистербист"}
SWAGA_TRACKS_PER_PAGE = 10


def _swaga_higher_rarity(rarity: str) -> str | None:
    """Вернуть редкость на 1 выше (более редкую) или None."""
    try:
        idx = SWAGA_RARITY_ORDER.index(str(rarity))
    except ValueError:
        return None
    if idx <= 0:
        return None
    return SWAGA_RARITY_ORDER[idx - 1]


def _swaga_upgrade_cost(target_rarity: str) -> int:
    """Сколько карточек нужно для апгрейда в target_rarity."""
    return 20 if str(target_rarity) in SWAGA_UPGRADE_SUPER_RARE_TARGETS else 10


def _swaga_upgrade_options(target_rarity: str) -> list[tuple[int, int]]:
    """Return allowed upgrade bundles as (cost, reward_qty)."""
    base_cost = _swaga_upgrade_cost(target_rarity)
    return [(base_cost, 1), (base_cost * 5, 5), (base_cost * 10, 10)]


def _format_swaga_track_added_at(created_at: int | None) -> str:
    """Форматирует время добавления трека без секунд."""
    try:
        ts = int(created_at or 0)
        if ts <= 0:
            return "Не указано"
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "Не указано"


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
        "<i>Курс обмена: 100 карточек = 1 сундук той же редкости.</i>\n"
        "<i>Upgrade cards: 10 -> 1, 50 -> 5, 100 -> 10 (Swaga/MisterBeast: 20 -> 1, 100 -> 5, 200 -> 10).</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🎴 Мои Свага Карточки", callback_data="swaga_cards_inv")],
        [InlineKeyboardButton("📦 Мои Свага Сундуки", callback_data="swaga_chests_inv")],
        [InlineKeyboardButton("💿 Мои Свага Треки", callback_data="swaga_tracks_inv")],
        [InlineKeyboardButton("🆕 Недавно добавленные треки", callback_data="swaga_recent_tracks")],
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

    text = (
        "🎴 <b>Мои Свага Карточки</b>\n\n"
        "• Обмен на сундук: 100 карточек = 1 сундук той же редкости.\n"
        "* Upgrade: 10 -> 1, 50 -> 5, 100 -> 10 (Swaga/MisterBeast: 20 -> 1, 100 -> 5, 200 -> 10).\n\n"
    )
    has_cards = False
    keyboard = []

    for rarity in SWAGA_RARITY_ORDER:
        count = card_counts.get(rarity, 0)
        emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
        if count > 0:
            has_cards = True
            text += f"{emoji} <b>{rarity}</b>: {count} шт.\n"

            higher = _swaga_higher_rarity(rarity)
            if higher:
                higher_emoji = SWAGA_COLOR_EMOJIS.get(higher, '⚫')
                for upgrade_cost, reward_qty in _swaga_upgrade_options(higher):
                    if count >= upgrade_cost:
                        keyboard.append([InlineKeyboardButton(
                            f"UPGRADE {upgrade_cost} {emoji} {rarity} -> {reward_qty} {higher_emoji} {higher}",
                            callback_data=f"swaga_upgrade_{rarity}_{upgrade_cost}_{reward_qty}"
                        )])

            if count >= SWAGA_CHEST_EXCHANGE_COST:
                keyboard.append([InlineKeyboardButton(
                    f"🔄 Обменять {SWAGA_CHEST_EXCHANGE_COST} {emoji} {rarity} → 1 сундук",
                    callback_data=f"swaga_exchange_{rarity}"
                )])

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
    cost = SWAGA_CHEST_EXCHANGE_COST
    try:
        card_inv = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id, rarity=rarity).first()
        if card_inv and card_inv.quantity >= cost:
            card_inv.quantity -= cost
            
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
        await query.answer(f"✅ Ты успешно обменял {cost} карточек на 1 {emoji} сундук!", show_alert=True)
        await show_swaga_cards_inv(update, context)


async def handle_swaga_upgrade(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    rarity: str,
    cost: int | None = None,
    reward_qty: int | None = None,
):
    """Upgrade cards: rarity -> one tier higher."""
    query = update.callback_query
    user_id = query.from_user.id

    higher = _swaga_higher_rarity(rarity)
    if not higher:
        await query.answer("This rarity cannot be upgraded.", show_alert=True)
        return

    allowed_options = set(_swaga_upgrade_options(higher))
    if cost is None or reward_qty is None:
        cost, reward_qty = _swaga_upgrade_cost(higher), 1

    try:
        cost = int(cost)
        reward_qty = int(reward_qty)
    except (TypeError, ValueError):
        await query.answer("Invalid upgrade format.", show_alert=True)
        return

    if (cost, reward_qty) not in allowed_options:
        await query.answer("Upgrade option is not allowed.", show_alert=True)
        return

    db_session = db.SessionLocal()
    success = False
    try:
        cur = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id, rarity=rarity).first()
        if not cur or int(cur.quantity or 0) < int(cost):
            await query.answer("Not enough cards for upgrade!", show_alert=True)
            return

        cur.quantity -= cost
        up = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id, rarity=higher).first()
        if up:
            up.quantity += reward_qty
        else:
            db_session.add(db.SwagaCardInventory(user_id=user_id, rarity=higher, quantity=reward_qty))

        db_session.commit()
        success = True
    except Exception as e:
        try:
            db_session.rollback()
        except Exception:
            pass
        logger.error(f"Error in swaga upgrade: {e}")
        await query.answer("Upgrade error!", show_alert=True)
    finally:
        db_session.close()

    if success:
        e_from = SWAGA_COLOR_EMOJIS.get(rarity, '?')
        e_to = SWAGA_COLOR_EMOJIS.get(higher, '?')
        await query.answer(
            f"Upgrade: {cost} {e_from} {rarity} -> {reward_qty} {e_to} {higher}",
            show_alert=True,
        )
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
    compensation_qty = 0
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

            # Компенсация за повторный дроп трека: возвращаем часть карточек редкости сундука
            if already_owned:
                compensation_qty = max(1, SWAGA_CHEST_EXCHANGE_COST // 2)
                inv = db_session.query(db.SwagaCardInventory).filter_by(user_id=user_id, rarity=rarity).first()
                if inv:
                    inv.quantity += compensation_qty
                else:
                    db_session.add(db.SwagaCardInventory(user_id=user_id, rarity=rarity, quantity=compensation_qty))

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
            text += f"\n<i>(У тебя уже есть этот трек.)</i>\n"
            if compensation_qty > 0:
                chest_emoji = SWAGA_COLOR_EMOJIS.get(rarity, '⚫')
                text += f"🎁 <b>Компенсация:</b> +{compensation_qty} {chest_emoji} {rarity} карточек\n"
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

    total_pages = max(1, (len(tracks) - 1) // SWAGA_TRACKS_PER_PAGE + 1)
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * SWAGA_TRACKS_PER_PAGE
    end_idx = start_idx + SWAGA_TRACKS_PER_PAGE
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


async def show_recent_swaga_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Список недавно добавленных свага-треков с пагинацией."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    db_session = db.SessionLocal()
    tracks = []
    try:
        tracks = (
            db_session.query(db.SwagaTrack)
            .order_by(db.SwagaTrack.created_at.desc(), db.SwagaTrack.id.desc())
            .all()
        )
    finally:
        db_session.close()

    if not tracks:
        text = "🆕 <b>Недавно добавленные Свага Треки</b>\n\nВ базе пока нет добавленных треков."
        keyboard = [[InlineKeyboardButton("🔙 Назад в Свага Шоп", callback_data="swaga_shop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
        return

    total_pages = max(1, (len(tracks) - 1) // SWAGA_TRACKS_PER_PAGE + 1)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * SWAGA_TRACKS_PER_PAGE
    end_idx = start_idx + SWAGA_TRACKS_PER_PAGE
    page_tracks = tracks[start_idx:end_idx]

    lines = [f"🆕 <b>Недавно добавленные Свага Треки</b> (Стр {page}/{total_pages})", ""]
    for idx, trk in enumerate(page_tracks, start=start_idx + 1):
        emoji = SWAGA_COLOR_EMOJIS.get(trk.rarity, '⚫')
        added_at = _format_swaga_track_added_at(getattr(trk, 'created_at', 0))
        lines.append(
            f"{idx}. <b>{trk.name}</b>\n"
            f"Редкость: {emoji} {trk.rarity}\n"
            f"Добавлен: {added_at}"
        )

    lines.extend([
        "",
        "ℹ️ <i>Редкость трека указывает администратор при добавлении. Это его личная субъективная оценка, с которой игроки могут не соглашаться.</i>",
    ])
    text = "\n\n".join(lines)

    keyboard = []
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"swaga_recent_tracks_page_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"swaga_recent_tracks_page_{page+1}"))
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
