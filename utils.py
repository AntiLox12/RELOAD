import time
import logging
import asyncio
import re
import html as _html
import weakref
import database as db
from typing import Dict


def esc(text) -> str:
    """Экранирует HTML-спецсимволы для безопасной вставки в parse_mode=HTML сообщения.
    
    Использование: f"Привет, <b>{esc(username)}</b>!"
    Безопасно для None — вернёт пустую строку.
    """
    if text is None:
        return ""
    return _html.escape(str(text))

logger = logging.getLogger(__name__)

# WeakValueDictionary автоматически удаляет Lock когда на него
# не остаётся ссылок, предотвращая утечку памяти при большом
# количестве уникальных ключей (user_id:action).
_LOCKS: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

def _get_lock(key: str) -> asyncio.Lock:
    lock = _LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[key] = lock
    return lock

def safe_format_timestamp(timestamp, format_str='%d.%m.%Y %H:%M'):
    """Безопасное форматирование временной метки."""
    if not timestamp:
        return None
    try:
        # Проверяем что таймстамп в разумных пределах
        if timestamp < 0 or timestamp > 4102444800:  # максимум до 2100 года
            return None
        return time.strftime(format_str, time.localtime(timestamp))
    except (OSError, ValueError, OverflowError) as e:
        logger.warning(f"Invalid timestamp {timestamp}: {e}")
        return None

def create_progress_bar(percent: float, length: int = 10, filled: str = '█', empty: str = '░') -> str:
    """Создает визуальный прогресс-бар."""
    if percent < 0:
        percent = 0
    elif percent > 100:
        percent = 100
    
    filled_length = int(length * percent / 100)
    empty_length = length - filled_length
    
    return filled * filled_length + empty * empty_length

def _parse_duration_to_seconds(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip().lower()
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        try:
            val = int(s)
            return val if val > 0 else None
        except Exception:
            return None
    num = int(m.group(1))
    unit = m.group(2)
    mult = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(unit, 1)
    return num * mult

def _resolve_user_identifier(text: str) -> int | None:
    t = (text or '').strip()
    if not t:
        return None
    res = db.find_player_by_identifier(t)
    if res.get('ok') and res.get('player'):
        return int(getattr(res['player'], 'user_id', 0) or 0) or None
    try:
        return int(t)
    except Exception:
        return None


def _format_duration_compact(seconds_value: int | float) -> str:
    """Форматирует секунды в компактную строку вида '7d 2h 30m'."""
    total = max(0, int(seconds_value or 0))
    if total == 0:
        return "0s"
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not days:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


def _format_player_label(user_id: int, username: str | None = None, display_name: str | None = None) -> str:
    """Возвращает человекочитаемую метку игрока для админ-панели."""
    parts: list[str] = []
    if display_name:
        parts.append(str(display_name))
    if username:
        parts.append(f"@{username}")
    parts.append(f"[{user_id}]")
    return " ".join(parts)
