import time
import logging
import asyncio
import re
import database as db
from typing import Dict

logger = logging.getLogger(__name__)

_LOCKS: Dict[str, asyncio.Lock] = {}

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
