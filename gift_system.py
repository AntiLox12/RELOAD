import html
import logging
import random
import time
from collections import defaultdict
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import database as db


class GiftFeature:
    MAX_BUNDLE_SIZE = 10
    DAILY_LIMIT = 20
    COOLDOWN_SECONDS = 40
    ITEMS_PER_PAGE = 6
    OFFER_EXPIRY_SECONDS = 600  # 10 минут на ответ получателя
    MAX_PENDING_OFFERS = 500   # Максимум незавершённых предложений
    COMMAND_RATE_LIMIT_SEC = 5  # IMP-4: минимальный интервал между /gift командами от одного пользователя

    def __init__(
        self,
        *,
        logger: logging.Logger,
        abort_if_banned,
        register_group_if_needed,
        reply_auto_delete_message,
        schedule_auto_delete_message,
        get_rarity_emoji,
        get_lock,
    ) -> None:
        self.logger = logger
        self.abort_if_banned = abort_if_banned
        self.register_group_if_needed = register_group_if_needed
        self.reply_auto_delete_message = reply_auto_delete_message
        self.schedule_auto_delete_message = schedule_auto_delete_message
        self.get_rarity_emoji = get_rarity_emoji
        self.get_lock = get_lock
        self.gift_offers: dict[int, dict[str, Any]] = {}
        self.next_gift_id = int(time.time()) * 1000  # Устойчив к рестартам
        self.selection_state: dict[int, dict[str, Any]] = {}
        self._gift_command_timestamps: dict[int, float] = defaultdict(float)  # IMP-4: rate limiter

    def _cleanup_stale(self) -> None:
        """Удаляет просроченные offer'ы и selection_state."""
        now = int(time.time())
        expired_ids = [
            gid for gid, offer in self.gift_offers.items()
            if now - offer.get("created_at", 0) > self.OFFER_EXPIRY_SECONDS
        ]
        for gid in expired_ids:
            self.gift_offers.pop(gid, None)

        stale_users = [
            uid for uid, state in self.selection_state.items()
            if now - state.get("created_at", 0) > self.OFFER_EXPIRY_SECONDS
        ]
        for uid in stale_users:
            self.selection_state.pop(uid, None)

    def _format_timestamp(self, timestamp: int | None) -> str:
        if not timestamp:
            return "—"
        try:
            return time.strftime("%d.%m.%Y %H:%M", time.localtime(int(timestamp)))
        except Exception:
            return "—"

    def _build_user_display(self, user_id: int | None, username: str | None = None, display_name: str | None = None) -> str:
        if username:
            return f"@{username}"
        if display_name:
            return str(display_name)
        if user_id:
            return str(user_id)
        return "пользователь"

    def _resolve_username_recipient(self, username: str | None) -> tuple[int | None, str]:
        uname = (username or "").lstrip("@").strip()
        if not uname:
            return (None, "")
        player = db.get_player_by_username(uname)
        if not player:
            return (None, f"@{uname}")
        return (
            int(player.user_id),
            self._build_user_display(
                int(player.user_id),
                getattr(player, "username", None),
                getattr(player, "display_name", None),
            ),
        )

    def _format_restriction_message(self, restriction: dict | None) -> str:
        if not restriction:
            return "Ограничение на подарки активно."
        text = html.escape(restriction.get("reason") or "Нарушение правил дарения")
        blocked_until = restriction.get("blocked_until")
        if blocked_until:
            text += f"\nДо: {self._format_timestamp(blocked_until)}"
        return text

    def _build_gift_flow_snapshot(self, giver_id: int, recipient_id: int | None) -> dict:
        settings = db.get_gift_autoblock_settings()
        gifts_sent_today = db.get_user_gifts_sent_today(giver_id)
        remaining_daily = max(self.DAILY_LIMIT - gifts_sent_today, 0)
        recipient_stats = None
        recipient_warning = None
        if settings["enabled"]:
            if recipient_id:
                recipient_stats = db.get_consecutive_gift_stats(
                    giver_id,
                    recipient_id,
                    limit=settings["consecutive_limit"],
                    planned_gifts=0,
                )
            else:
                recipient_warning = (
                    "Точный лимит подряд доступен, если получатель известен по ID. "
                    "Используйте reply на сообщение пользователя или дождитесь, пока он появится в базе."
                )
        return {
            "settings": settings,
            "gifts_sent_today": gifts_sent_today,
            "remaining_daily": remaining_daily,
            "recipient_stats": recipient_stats,
            "recipient_warning": recipient_warning,
        }

    def _refresh_selection_snapshot(self, state: dict[str, Any], giver_id: int) -> dict:
        snapshot = self._build_gift_flow_snapshot(giver_id, state.get("recipient_id"))
        state["gifts_sent_today"] = snapshot["gifts_sent_today"]
        state["max_gifts"] = min(self.MAX_BUNDLE_SIZE, snapshot["remaining_daily"])
        state["gift_snapshot"] = snapshot
        return snapshot

    def _project_recipient_stats(self, snapshot: dict, planned_gifts: int) -> dict | None:
        stats = snapshot.get("recipient_stats")
        if not stats:
            return None
        planned_gifts = max(0, int(planned_gifts or 0))
        projected_streak = int(stats["current_streak"]) + planned_gifts
        limit = int(stats["limit"])
        return {
            "current_streak": int(stats["current_streak"]),
            "remaining_before_block": int(stats["remaining_before_block"]),
            "projected_streak": projected_streak,
            "would_trigger": projected_streak > limit,
            "limit": limit,
        }

    def _render_gift_limit_block(self, snapshot: dict, planned_gifts: int = 0) -> str:
        lines = [
            f"📊 Сегодня отправлено: <b>{snapshot['gifts_sent_today']}/{self.DAILY_LIMIT}</b>",
            f"🎯 Осталось на сегодня: <b>{snapshot['remaining_daily']}</b>",
        ]
        settings = snapshot["settings"]
        if not settings["enabled"]:
            lines.append("🛡️ Gift-защита: <b>выключена</b>")
            return "\n".join(lines)

        stats = snapshot.get("recipient_stats")
        if stats:
            projected = self._project_recipient_stats(snapshot, planned_gifts)
            lines.append(
                f"🧱 Серия этому получателю: <b>{stats['current_streak']}/{stats['limit']}</b>"
            )
            lines.append(
                f"⚠️ Ещё можно подряд без блока: <b>{stats['remaining_before_block']}</b>"
            )
            if planned_gifts > 0 and projected:
                lines.append(
                    f"📦 С учётом корзины будет: <b>{projected['projected_streak']}/{projected['limit']}</b>"
                )
                if projected["would_trigger"]:
                    lines.append("🚫 Эта корзина вызовет автоблокировку.")
                elif projected["limit"] - projected["projected_streak"] <= 1:
                    lines.append("⚠️ Лимит почти достигнут.")
        elif snapshot.get("recipient_warning"):
            lines.append(f"ℹ️ {snapshot['recipient_warning']}")
        return "\n".join(lines)

    def _build_autoblock_reasons(self, limit: int) -> tuple[str, str]:
        return (
            f"Подозрительная активность: более {limit} подарков подряд одному пользователю",
            f"Подозрительная активность: получение более {limit} подарков подряд от одного пользователя",
        )

    def _apply_gift_autoblock(
        self,
        giver_id: int,
        recipient_id: int | None,
        *,
        limit: int,
        duration_sec: int,
        blocked_by: int | None = None,
    ) -> int:
        blocked_until = int(time.time()) + int(duration_sec)
        giver_reason, recipient_reason = self._build_autoblock_reasons(limit)
        db.add_gift_restriction(giver_id, giver_reason, blocked_until=blocked_until, blocked_by=blocked_by)
        if recipient_id:
            db.add_gift_restriction(recipient_id, recipient_reason, blocked_until=blocked_until, blocked_by=blocked_by)
        return blocked_until

    def _autoblock_text(self, blocked_until: int) -> str:
        until_text = self._format_timestamp(blocked_until)
        return (
            "🚫 <b>Обнаружена подозрительная активность!</b>\n\n"
            "Даритель и получатель получили временную gift-блокировку.\n"
            f"Срок окончания: <b>{until_text}</b>\n\n"
            "Обратитесь к администратору, если это ошибка."
        )

    async def giftstats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            stats = db.get_gift_stats(user_id)
            gifts_sent_today = db.get_user_gifts_sent_today(user_id)
            restriction = db.get_gift_restriction_info(user_id)
            text = (
                "📊 <b>Статистика подарков</b>\n\n"
                f"🎁 Отправлено всего: <b>{stats['sent']}</b>\n"
                f"🎉 Получено всего: <b>{stats['received']}</b>\n"
                f"📅 Отправлено сегодня: <b>{gifts_sent_today}/{self.DAILY_LIMIT}</b>\n\n"
            )
            if restriction:
                text += (
                    "🚫 <b>Статус:</b> Заблокирован\n"
                    f"<i>Причина: {html.escape(restriction['reason'])}</i>\n"
                    f"<i>До: {self._format_timestamp(restriction.get('blocked_until'))}</i>"
                )
            else:
                text += "✅ <b>Статус:</b> Активен"
            await update.message.reply_html(text)
        except Exception as exc:
            self.logger.exception("[GIFTSTATS] Error: %s", exc)
            await update.message.reply_text("Ошибка при получении статистики.")

    async def gift_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self.abort_if_banned(update, context):
            return
        await self.register_group_if_needed(update)
        if update.message.chat.type not in ("group", "supergroup"):
            await update.message.reply_text("Этой командой можно пользоваться только в группах.")
            return

        # IMP-4: In-memory rate limiter — защита от спама командой /gift
        giver_uid = update.effective_user.id
        now = time.time()
        if now - self._gift_command_timestamps[giver_uid] < self.COMMAND_RATE_LIMIT_SEC:
            return
        self._gift_command_timestamps[giver_uid] = now

        recipient_id = None
        recipient_username = None
        recipient_display = None
        reply = getattr(update.message, "reply_to_message", None)
        if reply and getattr(reply, "from_user", None):
            ruser = reply.from_user
            if getattr(ruser, "is_bot", False):
                await self.reply_auto_delete_message(update.message, "Нельзя дарить ботам.", context=context)
                return
            recipient_id = ruser.id
            recipient_username = ruser.username or None
            display = getattr(ruser, "full_name", None) or " ".join(
                [part for part in [ruser.first_name, ruser.last_name] if part]
            )
            recipient_display = f"@{recipient_username}" if recipient_username else (display or str(recipient_id))
        else:
            args = context.args if hasattr(context, "args") else []
            if not args:
                raw = (getattr(update.message, "text", None) or "").strip()
                parts = raw.split(maxsplit=1)
                if len(parts) > 1:
                    args = [parts[1]]
            if not args:
                await self.reply_auto_delete_message(
                    update.message,
                    "Использование: /gift @username\nЛибо ответьте на сообщение пользователя в группе и отправьте /gift",
                    context=context,
                )
                return
            recipient_username = args[0].lstrip("@").strip()
            recipient_id, recipient_display = self._resolve_username_recipient(recipient_username)

        giver_id = update.effective_user.id
        if recipient_id and recipient_id == giver_id:
            await self.reply_auto_delete_message(
                update.message,
                "❌ Вы не можете подарить напиток самому себе!",
                context=context,
            )
            return

        giver_restriction = db.get_gift_restriction_info(giver_id)
        if giver_restriction:
            await self.reply_auto_delete_message(
                update.message,
                f"🚫 Вы не можете дарить подарки.\n{self._format_restriction_message(giver_restriction)}",
                context=context,
            )
            return

        if recipient_id:
            recipient_restriction = db.get_gift_restriction_info(recipient_id)
            if recipient_restriction:
                await self.reply_auto_delete_message(
                    update.message,
                    f"🚫 Получатель временно не может принимать подарки.\n{self._format_restriction_message(recipient_restriction)}",
                    context=context,
                )
                return

        gifts_sent_today = db.get_user_gifts_sent_today(giver_id)
        remaining_daily = self.DAILY_LIMIT - gifts_sent_today
        if remaining_daily <= 0:
            await self.reply_auto_delete_message(
                update.message,
                f"⏳ Вы достигли дневного лимита подарков ({gifts_sent_today}/{self.DAILY_LIMIT}).\nПопробуйте завтра!",
                context=context,
            )
            return

        last_gift_time = db.get_user_last_gift_time(giver_id)
        current_time = int(time.time())
        if last_gift_time and (current_time - last_gift_time) < self.COOLDOWN_SECONDS:
            remaining = self.COOLDOWN_SECONDS - (current_time - last_gift_time)
            await self.reply_auto_delete_message(
                update.message,
                f"⏳ Подождите {remaining} сек. перед следующим подарком.",
                context=context,
            )
            return

        try:
            inventory_items = db.get_player_inventory_with_details(giver_id)
        except Exception:
            self.logger.exception("[GIFT] Failed to fetch inventory for giver %s", giver_id)
            await self.reply_auto_delete_message(
                update.message,
                "Ошибка при чтении инвентаря. Попробуйте позже.",
                context=context,
            )
            return

        if not inventory_items:
            await self.reply_auto_delete_message(update.message, "Ваш инвентарь пуст — нечего дарить.", context=context)
            return

        # Отменяем предыдущую сессию выбора, если была (BUG-5)
        old_state = self.selection_state.get(giver_id)
        if old_state and old_state.get("search_message_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=giver_id,
                    message_id=old_state["search_message_id"],
                    text="❌ Предыдущий выбор подарка отменён.",
                )
            except Exception:
                pass

        # Очистка просроченных записей
        self._cleanup_stale()

        self.selection_state[giver_id] = {
            "created_at": int(time.time()),
            "group_id": update.effective_chat.id,
            "recipient_username": recipient_username or "",
            "recipient_id": recipient_id,
            "recipient_display": recipient_display or f"@{recipient_username}",
            "inventory_items": inventory_items,
            "gifts_sent_today": gifts_sent_today,
            "max_gifts": min(self.MAX_BUNDLE_SIZE, remaining_daily),
            "cart": {},
            "current_page": 1,
            "search_query": None,
            "awaiting_search": False,
            "search_message_id": None,
            "gift_snapshot": self._build_gift_flow_snapshot(giver_id, recipient_id),
        }

        try:
            await self.send_gift_selection_menu(context, giver_id, page=1)
            try:
                sent_msg = await update.message.reply_text("Отправил список вам в личные сообщения.")
                try:
                    await self.schedule_auto_delete_message(context, update.effective_chat.id, sent_msg.message_id)
                except Exception:
                    pass
            except Exception:
                pass
        except Forbidden:
            await self.reply_auto_delete_message(
                update.message,
                "Не могу написать вам в личку. Откройте чат с ботом и нажмите Start, после этого повторите команду.",
                context=context,
            )
        except Exception as exc:
            self.logger.exception("[GIFT] Failed to send DM to giver %s: %s", giver_id, exc)
            await self.reply_auto_delete_message(
                update.message,
                "Не удалось отправить список в личные сообщения. Попробуйте позже.",
                context=context,
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        query = update.callback_query
        data = query.data or ""
        if not self._is_gift_callback(data):
            return False

        try:
            if data.startswith("gift_page_"):
                page = int(data.split("_")[-1])
                await self.send_gift_selection_menu(
                    context,
                    query.from_user.id,
                    page=page,
                    message_id=query.message.message_id,
                )
                await query.answer()
            elif data == "gift_page_info":
                await query.answer("Текущая страница")
            elif data == "gift_search":
                await self._start_search(query)
            elif data == "gift_cancel_search":
                await self._cancel_search(context, query)
            elif data == "gift_cancel":
                await self._cancel_selection(query)
            elif data == "gift_back":
                state = self.selection_state.get(query.from_user.id)
                if not state:
                    await query.answer("Сессия истекла", show_alert=True)
                else:
                    await self.send_gift_selection_menu(
                        context,
                        query.from_user.id,
                        page=state.get("current_page", 1),
                        search_query=state.get("search_query"),
                        message_id=query.message.message_id,
                    )
                    await query.answer()
            elif data.startswith("gift_item_"):
                item_id = int(data.split("_")[-1])
                await self._show_item_quantity_menu(query, item_id)
            elif data.startswith("gift_qty_add_"):
                _, _, _, item_id, amount = data.split("_")
                await self._change_item_quantity(query, int(item_id), int(amount))
            elif data.startswith("gift_qty_remove_"):
                _, _, _, item_id, amount = data.split("_")
                await self._change_item_quantity(query, int(item_id), -int(amount))
            elif data.startswith("gift_qty_clear_"):
                item_id = int(data.split("_")[-1])
                await self._clear_item_quantity(query, item_id)
            elif data == "gift_clear_cart":
                await self._clear_cart(context, query)
            elif data == "gift_send":
                await self._send_bundle_offer(update, context)
            elif data.startswith("giftresp_"):
                _, gid, resp = data.split("_", 2)
                await self.handle_gift_response(update, context, int(gid), resp == "yes")
            else:
                await query.answer("Неизвестное действие", show_alert=True)
        except Exception as exc:
            self.logger.exception("[GIFT] Callback error [%s]: %s", data, exc)
            try:
                await query.answer("Ошибка", show_alert=True)
            except Exception:
                pass
        return True

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not update.effective_user:
            return False
        user_id = update.effective_user.id
        state = self.selection_state.get(user_id)
        if not state or not state.get("awaiting_search"):
            return False

        msg = update.message
        incoming = (getattr(msg, "text", None) or "").strip()
        state["awaiting_search"] = False
        if not incoming:
            await msg.reply_text("❌ Пустой запрос. Попробуйте снова.")
            return True

        try:
            await self.send_gift_selection_menu(
                context,
                user_id,
                page=1,
                search_query=incoming,
                message_id=state.get("search_message_id"),
            )
            try:
                await msg.delete()
            except Exception:
                pass
        except Exception as exc:
            self.logger.exception("[GIFT_SEARCH] Error: %s", exc)
            await msg.reply_text("Ошибка при поиске. Попробуйте снова.")
        return True

    async def send_gift_selection_menu(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        page: int = 1,
        search_query: str | None = None,
        message_id: int | None = None,
    ):
        state = self.selection_state.get(user_id)
        if not state:
            return

        self._refresh_inventory(state, user_id)
        snapshot = self._refresh_selection_snapshot(state, user_id)
        if search_query is not None:
            state["search_query"] = search_query
        search_query = state.get("search_query")
        state["current_page"] = page

        inventory_items = state["inventory_items"]
        if search_query:
            filtered_items = [
                item for item in inventory_items if search_query.lower() in (item.drink.name or "").lower()
            ]
        else:
            filtered_items = inventory_items

        selected_total = self._selected_total(state)
        max_gifts = state["max_gifts"]
        summary = self._cart_summary(state)
        limits_block = self._render_gift_limit_block(snapshot, planned_gifts=selected_total)

        if not filtered_items:
            text = (
                "🎁 <b>Подарки пачкой</b>\n\n"
                f"❌ Ничего не найдено по запросу: <i>{html.escape(search_query or '')}</i>\n\n"
                f"👤 Получатель: {html.escape(state['recipient_display'])}\n"
                f"🧺 В корзине: <b>{selected_total}/{max_gifts}</b>\n"
                f"{limits_block}\n\n"
                f"{summary}"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔍 Новый поиск", callback_data="gift_search")],
                    [InlineKeyboardButton("◀️ Показать все", callback_data="gift_page_1")],
                    [InlineKeyboardButton("❌ Отменить", callback_data="gift_cancel")],
                ]
            )
            await self._edit_or_send(context, user_id, text, keyboard, message_id)
            return

        total_items = len(filtered_items)
        total_pages = max(1, (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        page = max(1, min(page, total_pages))
        state["current_page"] = page
        start_idx = (page - 1) * self.ITEMS_PER_PAGE
        page_items = filtered_items[start_idx:start_idx + self.ITEMS_PER_PAGE]

        search_info = f"\n🔍 Поиск: <i>{html.escape(search_query)}</i>" if search_query else ""
        text = (
            "🎁 <b>Подарки пачкой</b>\n\n"
            f"👤 Получатель: {html.escape(state['recipient_display'])}\n"
            f"🧺 В корзине: <b>{selected_total}/{max_gifts}</b>{search_info}\n"
            f"{limits_block}\n"
            f"📄 Страница {page}/{total_pages} ({total_items} поз.)\n\n"
            f"{summary}"
        )

        keyboard_rows = []
        for item in page_items:
            rarity_emoji = self.get_rarity_emoji(item.rarity)
            drink_name = item.drink.name[:18] + "..." if len(item.drink.name) > 18 else item.drink.name
            selected = int(state["cart"].get(item.id, 0) or 0)
            selected_text = f" • {selected}" if selected else ""
            button_text = f"{rarity_emoji} {drink_name} x{item.quantity}{selected_text}"
            keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=f"gift_item_{item.id}")])

        action_row = []
        if selected_total > 0:
            action_row.append(InlineKeyboardButton(f"🎁 Отправить ({selected_total})", callback_data="gift_send"))
            action_row.append(InlineKeyboardButton("🧹 Очистить", callback_data="gift_clear_cart"))
        if action_row:
            keyboard_rows.append(action_row)

        keyboard_rows.append([InlineKeyboardButton("🔍 Поиск по названию", callback_data="gift_search")])

        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"gift_page_{page - 1}"))
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="gift_page_info"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"gift_page_{page + 1}"))
        if nav_row:
            keyboard_rows.append(nav_row)

        keyboard_rows.append([InlineKeyboardButton("❌ Отменить", callback_data="gift_cancel")])
        await self._edit_or_send(
            context,
            user_id,
            text,
            InlineKeyboardMarkup(keyboard_rows),
            message_id,
        )

    async def handle_gift_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        gift_id: int,
        accepted: bool,
    ):
        query = update.callback_query
        lock = self.get_lock(f"gift:{gift_id}")
        if lock.locked():
            await query.answer("Этот подарок уже обрабатывается…", show_alert=True)
            return

        await query.answer()
        async with lock:
            offer = self.gift_offers.get(gift_id)
            if not offer:
                try:
                    await query.edit_message_text("⏰ Предложение подарка истекло. Попросите отправить заново.")
                except Exception:
                    pass
                return

            rec_id = offer.get("recipient_id")
            rec_un = (offer.get("recipient_username") or "").lower()

            # CRIT-3: Строгая проверка — подарок должен иметь идентификатор получателя
            if not rec_id and not rec_un:
                self.gift_offers.pop(gift_id, None)
                try:
                    await query.edit_message_text("❌ Ошибка: получатель не определён.")
                except Exception:
                    pass
                return

            if rec_id:
                if query.from_user.id != rec_id:
                    await query.answer("Это не вам предназначалось!", show_alert=True)
                    return
            elif rec_un:
                if not query.from_user.username or query.from_user.username.lower() != rec_un:
                    await query.answer("Это не вам предназначалось!", show_alert=True)
                    return

            recipient_id = query.from_user.id
            offer["recipient_id"] = recipient_id
            offer["recipient_display"] = self._build_user_display(
                recipient_id,
                getattr(query.from_user, "username", None),
                getattr(query.from_user, "full_name", None) or getattr(query.from_user, "first_name", None),
            )
            if not accepted:
                db.log_gift_bundle(offer["giver_id"], recipient_id, offer["items"], "declined")
                try:
                    await query.edit_message_text(
                        "❌ <b>Подарок отклонён</b>\n\n"
                        f"{self._bundle_lines(offer['items'])}\n\n"
                        f"Всего: <b>{offer['total_quantity']}</b>",
                        parse_mode="HTML",
                    )
                except BadRequest:
                    pass
                try:
                    await context.bot.send_message(
                        chat_id=offer["giver_id"],
                        text="😔 Ваш подарок был отклонён.",
                    )
                except Exception:
                    pass
                self.gift_offers.pop(gift_id, None)
                # IMP-5: Audit log для отклонённого подарка
                try:
                    db.log_action(
                        user_id=offer["giver_id"],
                        username=offer.get("giver_name"),
                        action_type="gift_declined",
                        action_details=f"by={recipient_id}, total={offer['total_quantity']}",
                        amount=offer["total_quantity"],
                        success=True,
                    )
                except Exception:
                    pass
                # IMP-1: Отменяем expire job
                try:
                    jobs = context.job_queue.get_jobs_by_name(f"gift_expire_{gift_id}")
                    for job in jobs:
                        job.schedule_removal()
                except Exception:
                    pass
                return

            giver_restriction = db.get_gift_restriction_info(offer["giver_id"])
            if giver_restriction:
                self.gift_offers.pop(gift_id, None)
                await query.edit_message_text(
                    f"🚫 Даритель сейчас не может отправлять подарки.\n\n{self._format_restriction_message(giver_restriction)}",
                    parse_mode="HTML",
                )
                return

            recipient_restriction = db.get_gift_restriction_info(recipient_id)
            if recipient_restriction:
                self.gift_offers.pop(gift_id, None)
                await query.edit_message_text(
                    f"🚫 Вы сейчас не можете принимать подарки.\n\n{self._format_restriction_message(recipient_restriction)}",
                    parse_mode="HTML",
                )
                return

            settings = db.get_gift_autoblock_settings()
            if settings["enabled"]:
                streak_stats = db.get_consecutive_gift_stats(
                    offer["giver_id"],
                    recipient_id,
                    limit=settings["consecutive_limit"],
                    planned_gifts=offer["total_quantity"],
                )
                if streak_stats["would_trigger"]:
                    blocked_until = self._apply_gift_autoblock(
                        offer["giver_id"],
                        recipient_id,
                        limit=settings["consecutive_limit"],
                        duration_sec=settings["duration_sec"],
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=offer["giver_id"],
                            text=(
                                "🚫 <b>Подарок не был передан.</b>\n\n"
                                "Сработала защита от подозрительной серии подарков.\n"
                                f"Срок gift-блокировки: <b>до {self._format_timestamp(blocked_until)}</b>"
                            ),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    self.gift_offers.pop(gift_id, None)
                    await query.edit_message_text(
                        self._autoblock_text(blocked_until),
                        parse_mode="HTML",
                    )
                    return

            # CRIT-1: Атомарная передача — списание и начисление в одной DB-транзакции
            giver_lock = self.get_lock(f"gift-transfer:{offer['giver_id']}")
            async with giver_lock:
                result = db.transfer_gift_bundle_atomic(
                    giver_id=offer["giver_id"],
                    recipient_id=recipient_id,
                    items=offer["items"],
                )
                if not result["ok"]:
                    await query.edit_message_text("Не удалось передать подарок: часть напитков уже исчезла из инвентаря.")
                    self.gift_offers.pop(gift_id, None)
                    return

            db.log_gift_bundle(offer["giver_id"], recipient_id, offer["items"], "accepted")
            self.logger.info(
                "[GIFT] %s -> %s: %s",
                offer["giver_name"],
                query.from_user.username or query.from_user.id,
                ", ".join(f"{item['drink_name']} x{item['quantity']}" for item in offer["items"]),
            )

            # IMP-5: Audit log для принятого подарка
            try:
                db.log_action(
                    user_id=offer["giver_id"],
                    username=offer.get("giver_name"),
                    action_type="gift_accepted",
                    action_details=f"to={recipient_id}, items={len(offer['items'])}, total={offer['total_quantity']}",
                    amount=offer["total_quantity"],
                    success=True,
                )
            except Exception:
                pass

            try:
                await query.edit_message_text(
                    "✅ <b>Подарок принят!</b>\n\n"
                    f"{self._bundle_lines(offer['items'])}\n\n"
                    f"Всего: <b>{offer['total_quantity']}</b>",
                    parse_mode="HTML",
                )
            except BadRequest:
                pass

            try:
                await context.bot.send_message(
                    chat_id=offer["giver_id"],
                    text=(
                        "🎉 <b>Ваш подарок принят!</b>\n\n"
                        f"Получатель: {html.escape(offer.get('recipient_display', 'пользователь'))}\n"
                        f"{self._bundle_lines(offer['items'])}\n\n"
                        f"Всего: <b>{offer['total_quantity']}</b>"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

            # IMP-2: Уведомление получателю с кнопкой «Посмотреть инвентарь»
            try:
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=(
                        "🎁 <b>Вы получили подарок!</b>\n\n"
                        f"От: @{html.escape(offer['giver_name'])}\n"
                        f"{self._bundle_lines(offer['items'])}\n\n"
                        f"Всего: <b>{offer['total_quantity']}</b>\n"
                        "<i>Напитки добавлены в ваш инвентарь.</i>"
                    ),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📦 Мой инвентарь", callback_data="inventory")]]
                    ),
                )
            except Exception:
                pass

            self.gift_offers.pop(gift_id, None)

            # IMP-1: Отменяем запланированную задачу истечения, т.к. offer обработан
            try:
                jobs = context.job_queue.get_jobs_by_name(f"gift_expire_{gift_id}")
                for job in jobs:
                    job.schedule_removal()
            except Exception:
                pass

    def _is_gift_callback(self, data: str) -> bool:
        prefixes = (
            "gift_page_",
            "gift_item_",
            "gift_qty_add_",
            "gift_qty_remove_",
            "gift_qty_clear_",
            "giftresp_",
        )
        exact = {
            "gift_page_info",
            "gift_search",
            "gift_cancel_search",
            "gift_cancel",
            "gift_back",
            "gift_clear_cart",
            "gift_send",
        }
        return data in exact or any(data.startswith(prefix) for prefix in prefixes)

    def _refresh_inventory(self, state: dict[str, Any], user_id: int) -> None:
        state["inventory_items"] = db.get_player_inventory_with_details(user_id)
        inventory_ids = {item.id for item in state["inventory_items"]}
        stale_ids = [item_id for item_id in state["cart"] if item_id not in inventory_ids]
        for item_id in stale_ids:
            state["cart"].pop(item_id, None)
        for item in state["inventory_items"]:
            selected = int(state["cart"].get(item.id, 0) or 0)
            if selected > int(item.quantity):
                state["cart"][item.id] = int(item.quantity)

    def _selected_total(self, state: dict[str, Any]) -> int:
        return sum(int(qty or 0) for qty in state.get("cart", {}).values())

    def _cart_summary(self, state: dict[str, Any]) -> str:
        # IMP-3: Показываем все позиции корзины (MAX_BUNDLE_SIZE максимум 10)
        if not state["cart"]:
            return "Корзина пуста. Нажмите на напиток и выберите количество."
        lines = []
        inventory_map = {item.id: item for item in state["inventory_items"]}
        for item_id, qty in state["cart"].items():
            item = inventory_map.get(item_id)
            if not item or qty <= 0:
                continue
            lines.append(
                f"• {self.get_rarity_emoji(item.rarity)} {html.escape(item.drink.name)} x{qty}"
            )
        return "Сейчас выбрано:\n" + "\n".join(lines)

    def _find_item(self, state: dict[str, Any], item_id: int):
        for item in state["inventory_items"]:
            if int(item.id) == int(item_id):
                return item
        return None

    async def _start_search(self, query) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        state["awaiting_search"] = True
        state["search_message_id"] = query.message.message_id
        await query.answer()
        await query.edit_message_text(
            "🔍 <b>Поиск напитка</b>\n\nВведите название напитка (или его часть):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Отменить поиск", callback_data="gift_cancel_search")]]
            ),
        )

    async def _cancel_search(self, context: ContextTypes.DEFAULT_TYPE, query) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        state["awaiting_search"] = False
        await self.send_gift_selection_menu(
            context,
            query.from_user.id,
            page=state.get("current_page", 1),
            search_query=state.get("search_query"),
            message_id=query.message.message_id,
        )
        await query.answer("Поиск отменён")

    async def _cancel_selection(self, query) -> None:
        self.selection_state.pop(query.from_user.id, None)
        await query.edit_message_text("❌ Выбор подарка отменён.")
        await query.answer()

    async def _show_item_quantity_menu(self, query, item_id: int) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        self._refresh_inventory(state, query.from_user.id)
        snapshot = self._refresh_selection_snapshot(state, query.from_user.id)
        item = self._find_item(state, item_id)
        if not item or int(item.quantity or 0) <= 0:
            state["cart"].pop(item_id, None)
            await query.answer("Этот напиток больше недоступен.", show_alert=True)
            return

        selected = int(state["cart"].get(item_id, 0) or 0)
        remaining_slots = state["max_gifts"] - self._selected_total(state)
        available_to_add = max(0, min(int(item.quantity) - selected, remaining_slots))
        rarity_emoji = self.get_rarity_emoji(item.rarity)
        limits_block = self._render_gift_limit_block(snapshot, planned_gifts=self._selected_total(state))
        text = (
            "🎁 <b>Настройка подарка</b>\n\n"
            f"{rarity_emoji} <b>{html.escape(item.drink.name)}</b>\n"
            f"Редкость: <b>{html.escape(item.rarity)}</b>\n"
            f"В инвентаре: <b>{item.quantity}</b>\n"
            f"В корзине: <b>{selected}</b>\n"
            f"Можно добавить ещё: <b>{available_to_add}</b>\n\n"
            f"{limits_block}\n\n"
            f"{self._cart_summary(state)}"
        )

        add_amounts = [1, 3, 5, 10]
        rows = []
        add_row = [
            InlineKeyboardButton(f"+{amount}", callback_data=f"gift_qty_add_{item_id}_{amount}")
            for amount in add_amounts
            if available_to_add >= amount
        ]
        if add_row:
            rows.append(add_row)

        remove_row = []
        if selected >= 1:
            remove_row.append(InlineKeyboardButton("-1", callback_data=f"gift_qty_remove_{item_id}_1"))
        if selected >= 3:
            remove_row.append(InlineKeyboardButton("-3", callback_data=f"gift_qty_remove_{item_id}_3"))
        if selected > 0:
            remove_row.append(InlineKeyboardButton("Сбросить", callback_data=f"gift_qty_clear_{item_id}"))
        if remove_row:
            rows.append(remove_row)

        action_row = [InlineKeyboardButton("◀️ К списку", callback_data="gift_back")]
        if self._selected_total(state) > 0:
            action_row.append(
                InlineKeyboardButton(f"🎁 Отправить ({self._selected_total(state)})", callback_data="gift_send")
            )
        rows.append(action_row)

        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="HTML",
        )
        await query.answer()

    async def _change_item_quantity(self, query, item_id: int, delta: int) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        self._refresh_inventory(state, query.from_user.id)
        item = self._find_item(state, item_id)
        if not item:
            state["cart"].pop(item_id, None)
            await query.answer("Этот напиток больше недоступен.", show_alert=True)
            return

        selected = int(state["cart"].get(item_id, 0) or 0)
        total_before = self._selected_total(state)
        if delta > 0:
            remaining_slots = state["max_gifts"] - total_before
            delta = min(delta, remaining_slots, int(item.quantity) - selected)
        else:
            delta = -min(abs(delta), selected)

        new_value = max(0, selected + delta)
        if new_value > 0:
            state["cart"][item_id] = new_value
        else:
            state["cart"].pop(item_id, None)
        await self._show_item_quantity_menu(query, item_id)

    async def _clear_item_quantity(self, query, item_id: int) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        state["cart"].pop(item_id, None)
        await self._show_item_quantity_menu(query, item_id)

    async def _clear_cart(self, context: ContextTypes.DEFAULT_TYPE, query) -> None:
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        state["cart"] = {}
        await query.answer("Корзина очищена")
        await self.send_gift_selection_menu(
            context,
            query.from_user.id,
            page=state.get("current_page", 1),
            search_query=state.get("search_query"),
            message_id=query.message.message_id,
        )

    async def _send_bundle_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        state = self.selection_state.get(query.from_user.id)
        if not state:
            await query.answer("Сессия истекла", show_alert=True)
            return
        self._refresh_inventory(state, query.from_user.id)
        snapshot = self._refresh_selection_snapshot(state, query.from_user.id)

        total_selected = self._selected_total(state)
        if total_selected <= 0:
            await query.answer("Корзина пуста.", show_alert=True)
            return

        giver_restriction = db.get_gift_restriction_info(query.from_user.id)
        if giver_restriction:
            self.selection_state.pop(query.from_user.id, None)
            await query.edit_message_text(
                f"🚫 Дарение недоступно.\n\n{self._format_restriction_message(giver_restriction)}",
                parse_mode="HTML",
            )
            return

        current_sent = snapshot["gifts_sent_today"]
        remaining_daily = snapshot["remaining_daily"]
        if total_selected > remaining_daily:
            state["gifts_sent_today"] = current_sent
            state["max_gifts"] = min(self.MAX_BUNDLE_SIZE, max(0, remaining_daily))
            await self.send_gift_selection_menu(
                context,
                query.from_user.id,
                page=state.get("current_page", 1),
                search_query=state.get("search_query"),
                message_id=query.message.message_id,
            )
            await query.answer("Дневной лимит изменился. Корзину пришлось пересчитать.", show_alert=True)
            return

        last_gift_time = db.get_user_last_gift_time(query.from_user.id)
        current_time = int(time.time())
        if last_gift_time and (current_time - last_gift_time) < self.COOLDOWN_SECONDS:
            remaining = self.COOLDOWN_SECONDS - (current_time - last_gift_time)
            await query.answer(f"Подождите {remaining} сек.", show_alert=True)
            return

        recipient_id = state.get("recipient_id")
        if recipient_id:
            recipient_restriction = db.get_gift_restriction_info(recipient_id)
            if recipient_restriction:
                self.selection_state.pop(query.from_user.id, None)
                await query.edit_message_text(
                    f"🚫 Получатель не может принять подарок.\n\n{self._format_restriction_message(recipient_restriction)}",
                    parse_mode="HTML",
                )
                return

        settings = snapshot["settings"]
        if recipient_id and settings["enabled"]:
            streak_stats = db.get_consecutive_gift_stats(
                query.from_user.id,
                recipient_id,
                limit=settings["consecutive_limit"],
                planned_gifts=total_selected,
            )
            if streak_stats["would_trigger"]:
                blocked_until = self._apply_gift_autoblock(
                    query.from_user.id,
                    recipient_id,
                    limit=settings["consecutive_limit"],
                    duration_sec=settings["duration_sec"],
                )
                self.selection_state.pop(query.from_user.id, None)
                await query.edit_message_text(
                    self._autoblock_text(blocked_until),
                    parse_mode="HTML",
                )
                return

        inventory_map = {item.id: item for item in state["inventory_items"]}
        bundle_items = []
        for item_id, quantity in state["cart"].items():
            item = inventory_map.get(item_id)
            if not item or int(item.quantity or 0) < int(quantity):
                await query.answer("Один из напитков уже закончился. Обновите корзину.", show_alert=True)
                await self.send_gift_selection_menu(
                    context,
                    query.from_user.id,
                    page=state.get("current_page", 1),
                    search_query=state.get("search_query"),
                    message_id=query.message.message_id,
                )
                return
            bundle_items.append(
                {
                    "item_id": int(item.id),
                    "drink_id": int(item.drink.id),
                    "drink_name": item.drink.name,
                    "rarity": item.rarity,
                    "quantity": int(quantity),
                }
            )

        # Очистка просроченных предложений перед созданием нового
        self._cleanup_stale()

        gift_id = self.next_gift_id
        self.next_gift_id += 1
        giver_name = query.from_user.username or query.from_user.first_name
        offer = {
            "created_at": int(time.time()),
            "giver_id": query.from_user.id,
            "giver_name": giver_name,
            "recipient_username": state.get("recipient_username"),
            "recipient_id": recipient_id,
            "recipient_display": state.get("recipient_display"),
            "group_id": state.get("group_id"),
            "items": bundle_items,
            "total_quantity": total_selected,
        }
        self.gift_offers[gift_id] = offer

        recip_text = offer.get("recipient_display") or (
            f"@{offer.get('recipient_username')}" if offer.get("recipient_username") else "получателю"
        )
        recip_html = recip_text if str(recip_text).startswith("@") else html.escape(str(recip_text))
        caption = (
            "🎁 <b>Подарок!</b>\n\n"
            f"<b>От:</b> @{html.escape(giver_name)}\n"
            f"<b>Кому:</b> {recip_html}\n"
            f"{self._bundle_lines(bundle_items)}\n\n"
            f"<b>Всего:</b> {total_selected}\n\n"
            "<i>Принять подарок?</i>"
        )
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Да", callback_data=f"giftresp_{gift_id}_yes"),
                InlineKeyboardButton("❌ Нет", callback_data=f"giftresp_{gift_id}_no"),
            ]]
        )
        await context.bot.send_message(
            chat_id=offer["group_id"],
            text=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await query.edit_message_text(
            "✅ Подарок предложен! Ожидаем ответ получателя.\n\n"
            f"{self._bundle_lines(bundle_items)}\n\n"
            f"Всего: <b>{total_selected}</b>",
            parse_mode="HTML",
        )
        self.selection_state.pop(query.from_user.id, None)

        # IMP-1: Запланировать автоматическое истечение предложения через JobQueue
        try:
            context.job_queue.run_once(
                self._expire_offer_job,
                when=self.OFFER_EXPIRY_SECONDS,
                data=gift_id,
                name=f"gift_expire_{gift_id}",
            )
        except Exception:
            pass

        # IMP-5: Audit log для создания предложения
        try:
            db.log_action(
                user_id=query.from_user.id,
                username=giver_name,
                action_type="gift_offered",
                action_details=f"to={recipient_id or offer.get('recipient_username','?')}, items={len(bundle_items)}, total={total_selected}",
                amount=total_selected,
                success=True,
            )
        except Exception:
            pass

    def _bundle_lines(self, bundle_items: list[dict[str, Any]]) -> str:
        lines = []
        for item in bundle_items:
            lines.append(
                f"• {self.get_rarity_emoji(item['rarity'])} {html.escape(item['drink_name'])} x{item['quantity']}"
            )
        return "\n".join(lines)

    def _log_bundle(self, offer: dict[str, Any], recipient_id: int, status: str) -> None:
        for item in offer["items"]:
            for _ in range(int(item["quantity"])):
                db.log_gift(
                    giver_id=offer["giver_id"],
                    recipient_id=recipient_id,
                    drink_id=item["drink_id"],
                    rarity=item["rarity"],
                    status=status,
                )

    # IMP-1: Автоматическое истечение предложения подарка через JobQueue
    async def _expire_offer_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        gift_id = context.job.data
        offer = self.gift_offers.pop(gift_id, None)
        if not offer:
            return
        # Уведомляем дарителя
        try:
            await context.bot.send_message(
                chat_id=offer["giver_id"],
                text=(
                    "⏰ <b>Подарок не был принят</b>\n\n"
                    f"{self._bundle_lines(offer['items'])}\n\n"
                    f"Всего: <b>{offer['total_quantity']}</b>\n"
                    "<i>Предложение истекло через 10 минут.</i>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        # IMP-5: Audit log для истечения
        try:
            db.log_action(
                user_id=offer["giver_id"],
                username=offer.get("giver_name"),
                action_type="gift_expired",
                action_details=f"to={offer.get('recipient_id') or offer.get('recipient_username','?')}, total={offer['total_quantity']}",
                amount=offer["total_quantity"],
                success=True,
            )
        except Exception:
            pass

    def _bundle_available(self, bundle_items: list[dict[str, Any]], giver_id: int) -> bool:
        for item in bundle_items:
            inv_item = db.get_inventory_item(item["item_id"])
            if not inv_item:
                return False
            if int(inv_item.player_id) != int(giver_id):
                return False
            if int(inv_item.quantity or 0) < int(item["quantity"]):
                return False
        return True

    async def _edit_or_send(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        text: str,
        keyboard: InlineKeyboardMarkup,
        message_id: int | None,
    ) -> None:
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
