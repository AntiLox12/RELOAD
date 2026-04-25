import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

from telegram import Bot

import config


DB_PATH = Path(__file__).with_name("bot_data.db")


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def load_groups(include_disabled: bool) -> list[dict]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT
                chat_id,
                title,
                is_enabled,
                notify_disabled,
                auto_delete_enabled,
                auto_delete_delay_minutes,
                last_notified
            FROM group_chats
        """
        params: tuple = ()
        if not include_disabled:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY is_enabled DESC, title COLLATE NOCASE, chat_id"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def verify_groups(groups: list[dict]) -> list[dict]:
    bot = Bot(token=config.TOKEN)
    verified: list[dict] = []

    for group in groups:
        result = dict(group)
        try:
            chat = await bot.get_chat(group["chat_id"])
            result["api_ok"] = True
            result["api_title"] = getattr(chat, "title", None)
            result["api_type"] = getattr(chat, "type", None)
        except Exception as exc:
            result["api_ok"] = False
            result["api_error"] = str(exc)
        verified.append(result)

    return verified


def format_group_line(index: int, group: dict, show_extra: bool) -> str:
    title = group.get("title") or "(без названия)"
    status = "enabled" if group.get("is_enabled") else "disabled"
    parts = [f"{index}. {title}", f"chat_id={group['chat_id']}", f"status={status}"]

    if show_extra:
        parts.append(f"notify_disabled={int(bool(group.get('notify_disabled')))}")
        parts.append(f"auto_delete={int(bool(group.get('auto_delete_enabled')))}")

    if "api_ok" in group:
        if group["api_ok"]:
            api_title = group.get("api_title")
            api_type = group.get("api_type")
            parts.append("api=ok")
            if api_type:
                parts.append(f"type={api_type}")
            if api_title and api_title != title:
                parts.append(f"api_title={api_title}")
        else:
            parts.append(f"api_error={group.get('api_error', 'unknown error')}")

    return " | ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Показывает группы, в которых бот уже был зарегистрирован в локальной БД."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Показывать и активные, и отключенные группы.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Дополнительно проверить группы через Telegram Bot API.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Показывать дополнительные поля из базы.",
    )
    args = parser.parse_args()

    configure_stdout()
    groups = load_groups(include_disabled=args.all)

    if args.verify and groups:
        groups = asyncio.run(verify_groups(groups))

    if not groups:
        print("Группы не найдены.")
        return

    print(
        "Важно: Telegram Bot API не умеет отдавать полный список всех групп бота. "
        "Этот скрипт показывает группы, которые бот уже сохранил в таблице group_chats."
    )
    print(f"Найдено групп: {len(groups)}")
    print()

    for index, group in enumerate(groups, start=1):
        print(format_group_line(index, group, args.details))


if __name__ == "__main__":
    main()
