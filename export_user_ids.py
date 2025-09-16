#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт всех user_id из базы данных в файл.

По умолчанию сохраняет в CSV-файл user_ids.csv в текущей директории.

Пример запуска:
    python export_user_ids.py --output user_ids.csv --format csv --sort
    python export_user_ids.py --output out/user_ids.txt --format txt --dedup

Важно: запускать из директории проекта (где лежит database.py), чтобы импорт сработал.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Iterable, List

try:
    # Ожидаем, что файл database.py лежит рядом со скриптом
    import database as db
    from database import SessionLocal, Player  # type: ignore
except Exception as e:
    print("[ERROR] Не удалось импортировать модуль database.py. Запустите скрипт из директории проекта.")
    raise


def _ensure_schema_if_available() -> None:
    """Пробуем вызвать ensure_schema(), если она есть в database.py."""
    try:
        if hasattr(db, 'ensure_schema') and callable(getattr(db, 'ensure_schema')):
            db.ensure_schema()
    except Exception:
        # Не критично для экспорта, продолжим
        pass


def fetch_all_user_ids() -> List[int]:
    """Возвращает список всех user_id из таблицы игроков."""
    _ensure_schema_if_available()
    session = SessionLocal()
    try:
        rows = session.query(Player.user_id).distinct().all()  # [(user_id,), ...]
        ids = [int(r[0]) for r in rows if r and r[0] is not None]
        return ids
    finally:
        session.close()


def write_txt(ids: Iterable[int], path: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for uid in ids:
            f.write(f"{uid}\n")


def write_csv(ids: Iterable[int], path: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["user_id"])  # header
        for uid in ids:
            writer.writerow([uid])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Экспорт всех user_id из базы данных в файл")
    parser.add_argument('--output', '-o', default='user_ids.csv', help='Путь к выходному файлу (по умолчанию user_ids.csv)')
    parser.add_argument('--format', '-f', choices=['csv', 'txt'], default='csv', help='Формат файла: csv или txt (по умолчанию csv)')
    parser.add_argument('--sort', action='store_true', help='Сортировать user_id по возрастанию')
    parser.add_argument('--dedup', action='store_true', help='Убрать дубликаты (на всякий случай)')

    args = parser.parse_args(argv)

    ids = fetch_all_user_ids()
    if args.dedup:
        ids = list(set(ids))
    if args.sort:
        ids.sort()

    if args.format == 'csv':
        write_csv(ids, args.output)
    else:
        write_txt(ids, args.output)

    print(f"[OK] Экспортировано {len(ids)} user_id в файл: {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
