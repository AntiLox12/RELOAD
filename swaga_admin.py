import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
from constants import ADMIN_USERNAMES, SWAGA_COLOR_EMOJIS, SWAGA_RARITY_ORDER

logger = logging.getLogger(__name__)

# Состояния для добавления Свага Трека
SWAGA_NAME, SWAGA_DESC, SWAGA_PHOTO, SWAGA_AUDIO, SWAGA_RARITY = range(5)

SWAGA_ADMIN_CALLBACK_PREFIX = "swaga_admin_"
SWAGA_ID_CHUNK_LIMIT = 3600

_EDIT_FIELD_ALIASES = {
    "name": "name",
    "title": "name",
    "название": "name",
    "имя": "name",
    "desc": "description",
    "description": "description",
    "описание": "description",
    "rarity": "rarity",
    "rare": "rarity",
    "редкость": "rarity",
    "photo": "photo_file_id",
    "cover": "photo_file_id",
    "обложка": "photo_file_id",
    "фото": "photo_file_id",
    "audio": "audio_file_id",
    "аудио": "audio_file_id",
    "трек": "audio_file_id",
}

_CLEAR_VALUES = {"-", "none", "null", "clear", "delete", "remove", "нет", "очистить", "удалить"}


def _has_swaga_admin_access(user) -> bool:
    if not user:
        return False
    username = getattr(user, "username", None)
    if username in ADMIN_USERNAMES:
        return True
    try:
        return db.get_admin_level(int(user.id)) >= 2
    except Exception:
        return False


async def check_admin(update: Update) -> bool:
    user = update.effective_user
    if _has_swaga_admin_access(user):
        return True

    query = update.callback_query
    if query:
        await query.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("У вас нет прав для выполнения этой команды.")
    return False


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _resolve_rarity(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(SWAGA_RARITY_ORDER):
            return SWAGA_RARITY_ORDER[idx]
        return None
    lowered = raw.casefold()
    for rarity in SWAGA_RARITY_ORDER:
        if rarity.casefold() == lowered:
            return rarity
    return None


def _format_track_line(track: db.SwagaTrack) -> str:
    emoji = SWAGA_COLOR_EMOJIS.get(track.rarity, "⚫")
    photo = "📷" if track.photo_file_id else "—"
    audio = "🎵" if track.audio_file_id else "—"
    return (
        f"<b>ID {int(track.id)}</b> | {emoji} {_esc(track.rarity)} | "
        f"{_esc(track.name)} | фото: {photo} аудио: {audio}"
    )


def _swaga_track_usage() -> str:
    rarity_lines = "\n".join(
        f"{idx}. {SWAGA_COLOR_EMOJIS.get(rarity, '⚫')} {html.escape(rarity)}"
        for idx, rarity in enumerate(SWAGA_RARITY_ORDER, 1)
    )
    return (
        "Команды управления Свага Треками:\n"
        "/swagaid — список треков с ID\n"
        "/swagaedit <id> name <новое название>\n"
        "/swagaedit <id> desc <новое описание или ->\n"
        "/swagaedit <id> rarity <номер или название редкости>\n"
        "/swagaedit <id> photo <file_id или ->, либо reply на фото\n"
        "/swagaedit <id> audio <file_id или ->, либо reply на аудио/войс\n"
        "/swagadel <id> — удалить трек с подтверждением\n"
        "/swagadel <id> confirm — удалить сразу\n\n"
        f"Редкости:\n{rarity_lines}"
    )


def _message_chunks(lines: list[str], limit: int = SWAGA_ID_CHUNK_LIMIT) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        extra_len = len(line) + 1
        if current and current_len + extra_len > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = extra_len
        else:
            current.append(line)
            current_len += extra_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def _delete_swaga_track(db_session, track_id: int) -> tuple[bool, str, int, int]:
    track = db_session.query(db.SwagaTrack).filter_by(id=int(track_id)).first()
    if not track:
        return False, "", 0, 0

    track_name = str(track.name or "")
    owned_deleted = (
        db_session.query(db.PlayerSwagaTrack)
        .filter_by(track_id=int(track_id))
        .delete(synchronize_session=False)
    )
    favorites_cleared = (
        db_session.query(db.Player)
        .filter(db.Player.favorite_swaga_track_id == int(track_id))
        .update({db.Player.favorite_swaga_track_id: 0}, synchronize_session=False)
    )
    db_session.delete(track)
    return True, track_name, int(owned_deleted or 0), int(favorites_cleared or 0)


async def addswagatrack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога добавления трека."""
    if not await check_admin(update):
        return ConversationHandler.END

    await update.message.reply_text(
        "🎧 Добавление нового Свага Трека.\n\nШаг 1: Введите <b>Название</b> трека:",
        parse_mode="HTML",
    )
    return SWAGA_NAME


async def swaga_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["swaga_name"] = update.message.text
    await update.message.reply_text(
        "Шаг 2: Введите <b>Описание</b> трека (или отправьте '-', чтобы пропустить):",
        parse_mode="HTML",
    )
    return SWAGA_DESC


async def swaga_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["swaga_desc"] = "" if text == "-" else text
    await update.message.reply_text(
        "Шаг 3: Отправьте <b>Обложку (Фото)</b> для трека "
        "(или отправьте слово 'скип', чтобы пропустить):",
        parse_mode="HTML",
    )
    return SWAGA_PHOTO


async def swaga_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["swaga_photo"] = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.lower() == "скип":
        context.user_data["swaga_photo"] = None
    else:
        await update.message.reply_text("Пожалуйста, отправьте фото или 'скип'.")
        return SWAGA_PHOTO

    await update.message.reply_text("Шаг 4: Отправьте <b>Аудиофайл</b> трека:", parse_mode="HTML")
    return SWAGA_AUDIO


async def swaga_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.audio and not getattr(update.message, "voice", None):
        await update.message.reply_text(
            "Это не аудиофайл. Пожалуйста, отправьте трек (аудиофайл или войс)."
        )
        return SWAGA_AUDIO

    if update.message.audio:
        context.user_data["swaga_audio"] = update.message.audio.file_id
    else:
        context.user_data["swaga_audio"] = update.message.voice.file_id

    text = "Шаг 5: Выберите редкость (введите номер):\n"
    for i, rarity in enumerate(SWAGA_RARITY_ORDER, 1):
        emoji = SWAGA_COLOR_EMOJIS.get(rarity, "⚫")
        text += f"{i}. {emoji} {rarity}\n"

    await update.message.reply_text(text)
    return SWAGA_RARITY


async def swaga_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    rarity = _resolve_rarity(text)
    if not rarity:
        await update.message.reply_text("Введите число от 1 до " + str(len(SWAGA_RARITY_ORDER)))
        return SWAGA_RARITY

    name = context.user_data.get("swaga_name")
    desc = context.user_data.get("swaga_desc")
    photo_id = context.user_data.get("swaga_photo")
    audio_id = context.user_data.get("swaga_audio")

    db_session = db.SessionLocal()
    try:
        new_track = db.SwagaTrack(
            name=name,
            description=desc,
            photo_file_id=photo_id,
            audio_file_id=audio_id,
            rarity=rarity,
        )
        db_session.add(new_track)
        db_session.commit()
        track_id = int(new_track.id)
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error saving SwagaTrack: {e}")
        await update.message.reply_text("Ошибка при сохранении трека в БД.")
        return ConversationHandler.END
    finally:
        db_session.close()

    emoji = SWAGA_COLOR_EMOJIS.get(rarity, "⚫")
    await update.message.reply_text(
        f"✅ Трек <b>{_esc(name)}</b> ({emoji} {_esc(rarity)}) успешно добавлен!\n"
        f"ID трека: <b>{track_id}</b>",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cancel_addswaga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление трека отменено.")
    return ConversationHandler.END


addswaga_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("addswagatrack", addswagatrack_start)],
    states={
        SWAGA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_name)],
        SWAGA_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_desc)],
        SWAGA_PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, swaga_photo)],
        SWAGA_AUDIO: [MessageHandler((filters.AUDIO | filters.VOICE) & ~filters.COMMAND, swaga_audio)],
        SWAGA_RARITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, swaga_rarity)],
    },
    fallbacks=[CommandHandler("cancel", cancel_addswaga)],
)


async def giveswagacards_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /giveswagacards <user_id> <rarity_id> <count>."""
    if not await check_admin(update):
        return

    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "Использование: /giveswagacards <user_id> <номер редкости 1-6> <количество>"
        )
        return

    target_str = args[0]
    rarity_idx = args[1]
    count = args[2]

    if not rarity_idx.isdigit() or not count.isdigit():
        await update.message.reply_text("ID редкости и количество должны быть числами.")
        return

    idx = int(rarity_idx) - 1
    if idx < 0 or idx >= len(SWAGA_RARITY_ORDER):
        await update.message.reply_text(
            "Неверный номер редкости. Доступно от 1 до " + str(len(SWAGA_RARITY_ORDER))
        )
        return

    rarity = SWAGA_RARITY_ORDER[idx]
    count = int(count)

    db_session = db.SessionLocal()
    try:
        if target_str.isdigit():
            target_id = int(target_str)
        else:
            uname = target_str.lstrip("@")
            player = db_session.query(db.Player).filter(db.Player.username.ilike(uname)).first()
            if player:
                target_id = player.user_id
            else:
                await update.message.reply_text(f"Игрок с юзернеймом {target_str} не найден в БД.")
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
        return
    finally:
        db_session.close()

    emoji = SWAGA_COLOR_EMOJIS.get(rarity, "⚫")
    await update.message.reply_text(
        f"Успешно выдано {count} карточек {emoji} {rarity} пользователю {target_id}"
    )


async def swagaid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/swagaid — список всех добавленных Свага Треков."""
    if not await check_admin(update):
        return

    db_session = db.SessionLocal()
    try:
        tracks = db_session.query(db.SwagaTrack).order_by(db.SwagaTrack.id.asc()).all()
    finally:
        db_session.close()

    if not tracks:
        await update.message.reply_text("В базе пока нет Свага Треков.")
        return

    lines = [
        "📋 <b>Все Свага Треки в БД:</b>",
        "",
        "✏️ Редактировать: <code>/swagaedit &lt;id&gt; &lt;field&gt; &lt;value&gt;</code>",
        "🗑 Удалить: <code>/swagadel &lt;id&gt;</code>",
        "",
    ]
    lines.extend(_format_track_line(track) for track in tracks)

    for chunk in _message_chunks(lines):
        await update.message.reply_text(chunk, parse_mode="HTML")


async def swagaedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/swagaedit <id> <field> <value> — редактирование Свага Трека."""
    if not await check_admin(update):
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(_swaga_track_usage())
        return

    try:
        track_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID трека должен быть числом.")
        return

    field_key = str(args[1]).strip().casefold()
    column = _EDIT_FIELD_ALIASES.get(field_key)
    if not column:
        await update.message.reply_text(_swaga_track_usage())
        return

    reply = update.message.reply_to_message
    raw_value = " ".join(args[2:]).strip() if len(args) > 2 else ""
    value = None

    if column == "name":
        value = raw_value
        if not value:
            await update.message.reply_text("Новое название не может быть пустым.")
            return
    elif column == "description":
        value = "" if raw_value.casefold() in _CLEAR_VALUES else raw_value
        if not raw_value:
            await update.message.reply_text("Пришлите новое описание или '-' для очистки.")
            return
    elif column == "rarity":
        value = _resolve_rarity(raw_value)
        if not value:
            await update.message.reply_text(_swaga_track_usage())
            return
    elif column == "photo_file_id":
        if reply and reply.photo:
            value = reply.photo[-1].file_id
        elif raw_value:
            value = None if raw_value.casefold() in _CLEAR_VALUES else raw_value
        else:
            await update.message.reply_text("Ответьте командой на фото или укажите file_id / '-' для очистки.")
            return
    elif column == "audio_file_id":
        if reply and reply.audio:
            value = reply.audio.file_id
        elif reply and getattr(reply, "voice", None):
            value = reply.voice.file_id
        elif raw_value:
            value = None if raw_value.casefold() in _CLEAR_VALUES else raw_value
        else:
            await update.message.reply_text(
                "Ответьте командой на аудио/войс или укажите file_id / '-' для очистки."
            )
            return

    db_session = db.SessionLocal()
    try:
        track = db_session.query(db.SwagaTrack).filter_by(id=track_id).first()
        if not track:
            await update.message.reply_text(f"Трек с ID {track_id} не найден.")
            return

        old_value = getattr(track, column)
        setattr(track, column, value)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error editing SwagaTrack {track_id}: {e}")
        await update.message.reply_text("Ошибка БД при редактировании трека.")
        return
    finally:
        db_session.close()

    try:
        db.insert_moderation_log(
            actor_id=int(update.effective_user.id),
            action="swaga_track_edit",
            target_id=track_id,
            details=f"{column}: {old_value!r} -> {value!r}",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Трек <b>ID {track_id}</b> обновлён.\n"
        f"Поле: <code>{html.escape(column)}</code>\n"
        f"Было: <code>{_esc(old_value) or '—'}</code>\n"
        f"Стало: <code>{_esc(value) or '—'}</code>",
        parse_mode="HTML",
    )


async def swagadel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/swagadel <id> — удаление Свага Трека."""
    if not await check_admin(update):
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("Использование: /swagadel <id> [confirm]")
        return

    try:
        track_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID трека должен быть числом.")
        return

    force = len(args) > 1 and str(args[1]).casefold() in {"confirm", "yes", "да", "force"}

    db_session = db.SessionLocal()
    try:
        track = db_session.query(db.SwagaTrack).filter_by(id=track_id).first()
        if not track:
            await update.message.reply_text(f"Трек с ID {track_id} не найден.")
            return

        if not force:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🗑 Да, удалить",
                            callback_data=f"{SWAGA_ADMIN_CALLBACK_PREFIX}del_confirm:{track_id}",
                        ),
                        InlineKeyboardButton(
                            "Отмена",
                            callback_data=f"{SWAGA_ADMIN_CALLBACK_PREFIX}del_cancel:{track_id}",
                        ),
                    ]
                ]
            )
            await update.message.reply_text(
                "Удалить этот Свага Трек?\n\n"
                f"{_format_track_line(track)}\n\n"
                "Это также удалит трек из коллекций игроков и сбросит его как любимый трек.",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return

        ok, track_name, owned_deleted, favorites_cleared = _delete_swaga_track(db_session, track_id)
        if not ok:
            await update.message.reply_text(f"Трек с ID {track_id} не найден.")
            return
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting SwagaTrack {track_id}: {e}")
        await update.message.reply_text("Ошибка БД при удалении трека.")
        return
    finally:
        db_session.close()

    try:
        db.insert_moderation_log(
            actor_id=int(update.effective_user.id),
            action="swaga_track_delete",
            target_id=track_id,
            details=f"name={track_name!r}; owned_deleted={owned_deleted}; favorites_cleared={favorites_cleared}",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Свага Трек <b>ID {track_id}</b> удалён: {_esc(track_name)}\n"
        f"Удалено из коллекций: {owned_deleted}\n"
        f"Сброшено любимых треков: {favorites_cleared}",
        parse_mode="HTML",
    )


async def handle_swaga_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    if not data.startswith(SWAGA_ADMIN_CALLBACK_PREFIX):
        return
    if not await check_admin(update):
        return

    if data.startswith(f"{SWAGA_ADMIN_CALLBACK_PREFIX}del_cancel:"):
        await query.answer("Удаление отменено.")
        try:
            await query.edit_message_text("Удаление Свага Трека отменено.")
        except Exception:
            pass
        return

    if not data.startswith(f"{SWAGA_ADMIN_CALLBACK_PREFIX}del_confirm:"):
        await query.answer()
        return

    try:
        track_id = int(data.rsplit(":", 1)[1])
    except ValueError:
        await query.answer("Некорректный ID трека.", show_alert=True)
        return

    db_session = db.SessionLocal()
    try:
        ok, track_name, owned_deleted, favorites_cleared = _delete_swaga_track(db_session, track_id)
        if not ok:
            await query.answer("Трек уже удалён или не найден.", show_alert=True)
            return
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting SwagaTrack {track_id}: {e}")
        await query.answer("Ошибка БД при удалении трека.", show_alert=True)
        return
    finally:
        db_session.close()

    try:
        db.insert_moderation_log(
            actor_id=int(query.from_user.id),
            action="swaga_track_delete",
            target_id=track_id,
            details=f"name={track_name!r}; owned_deleted={owned_deleted}; favorites_cleared={favorites_cleared}",
        )
    except Exception:
        pass

    await query.answer("Трек удалён.")
    await query.edit_message_text(
        f"✅ Свага Трек <b>ID {track_id}</b> удалён: {_esc(track_name)}\n"
        f"Удалено из коллекций: {owned_deleted}\n"
        f"Сброшено любимых треков: {favorites_cleared}",
        parse_mode="HTML",
    )
