from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


AsyncHandler = Callable[..., Awaitable[Any]]
SyncHelper = Callable[..., Any]


@dataclass(slots=True)
class BotRuntime:
    db: Any
    logger: Any
    t: Callable[[str, str], str]
    has_creator_panel_access: Callable[..., bool]
    has_admin_level: Callable[..., bool]
    safe_format_timestamp: Callable[..., Any]
    parse_duration_to_seconds: SyncHelper
    format_duration_compact: SyncHelper
    resolve_user_identifier: SyncHelper
    format_player_label: SyncHelper
    promo_kind_options: list[tuple[str, str]]
    donate_options: list[dict[str, Any]]
    rarities: dict[str, Any]
    rarity_order: list[str]
    color_emojis: dict[str, str]
    promo_announcement_chat: Any
    promo_announcement_link: Any
    search_cooldown_default: int
    daily_bonus_cooldown_default: int
    auto_search_daily_limit_default: int
    casino_win_prob_default: float
    plantation_fertilizer_max_per_bed_default: int
    plantation_neg_event_interval_sec_default: int
    plantation_neg_event_chance_default: float
    plantation_neg_event_max_active_default: float
    plantation_neg_event_duration_sec_default: int
    handlers: dict[str, AsyncHandler] = field(default_factory=dict)
    helpers: dict[str, SyncHelper] = field(default_factory=dict)
