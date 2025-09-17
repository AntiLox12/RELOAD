# file: fullhelp.py

from telegram import Update
from telegram.ext import ContextTypes
import database as db
from constants import (
    SEARCH_COOLDOWN,
    DAILY_BONUS_COOLDOWN,
    RARITY_ORDER,
    COLOR_EMOJIS,
    ITEMS_PER_PAGE,
    ADMIN_USERNAMES,
)

"""Константы импортируются из модуля constants.py"""


async def fullhelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная справка по боту: механики, команды, настройки, модерация, админ-инструменты."""
    user = update.effective_user
    # Доступ только для админов и Создателя
    if not db.is_admin(user.id) and (user.username not in ADMIN_USERNAMES):
        await update.message.reply_text("Нет прав")
        return

    search_minutes = SEARCH_COOLDOWN // 60
    bonus_hours = DAILY_BONUS_COOLDOWN // 3600

    # Разбиваем на секции, чтобы не превышать лимиты длины сообщения
    sections: list[str] = []

    # 1) Общее
    sections.append(
        (
            f"👋 Привет, {user.mention_html()}!\n\n"
            "Это подробная справка о боте для коллекционирования энергетиков.\n"
            "Ниже — как всё устроено и какие команды доступны."
        )
    )

    # 2) Команды для всех
    sections.append(
        (
            "<b>Команды для всех пользователей:</b>\n"
            "/start — открыть главное меню.\n"
            "/find — быстрый поиск энергетика (работает и в группах).\n"
            "/leaderboard — таблица лидеров по энергетикам.\n"
            "/moneyleaderboard — таблица лидеров по деньгам.\n"
            "/myreceipts — список ваших последних чеков TG Premium.\n"
            "/gift @username — начать дарение напитка участнику (бот пришлёт выбор в личку).\n"
            "/help — краткая справка.\n"
            "/fullhelp — полная справка (это сообщение, доступно только админам).\n\n"
            "<b>Текстовые триггеры (вместо /find):</b>\n"
            "• Напишите: \"Найти энергетик\", \"Найди энергетик\" или \"Получить энергетик\" — я пойму и запущу поиск.\n"
        )
    )

    # 3) Игровая механика
    rarity_lines: list[str] = []
    for r in RARITY_ORDER:
        emoji = COLOR_EMOJIS.get(r, '⚫')
        rarity_lines.append(f"{emoji} {r}")
    sections.append(
        (
            "<b>Игровая механика:</b>\n"
            f"• Поиск: раз в {search_minutes} минут.\n"
            f"• Ежедневный бонус: раз в {bonus_hours} часов.\n"
            "• Редкости напитков (от особых к базовым):\n"
            + "\n".join(f"  — {line}" for line in rarity_lines) + "\n"
            "• Изображения напитков берутся из каталога energy_images/."
        )
    )

    # 4) Инвентарь
    sections.append(
        (
            "<b>Инвентарь:</b>\n"
            f"• Пагинация: по {ITEMS_PER_PAGE} предметов на страницу.\n"
            "• Сортировка: по редкости и названию.\n"
            "• Можно открыть карточку предмета и вернуться назад кнопкой."
        )
    )

    # 5) Дарение
    sections.append(
        (
            "<b>Дарение напитков:</b>\n"
            "• В группе выполните: /gift @username — бот пришлёт выбор предмета в личку.\n"
            "• Получатель подтверждает/отклоняет подарок через кнопки."
        )
    )

    # 6) Настройки
    sections.append(
        (
            "<b>Настройки:</b>\n"
            "• Язык интерфейса (RU/EN).\n"
            "• Автонапоминание о завершении кулдауна поиска.\n"
            "• Сброс данных (осторожно: удаляет прогресс)."
        )
    )

    # 7) Группы и уведомления
    sections.append(
        (
            "<b>Группы и уведомления:</b>\n"
            "• Бот тихо регистрирует группу при первом взаимодействии.\n"
            "• Периодические напоминания в группы отправляются примерно раз в 4 часа."
        )
    )

    # 8) Заявки и модерация
    sections.append(
        (
            "<b>Заявки и модерация:</b>\n"
            "• /add — диалоговая заявка на добавление напитка (название → описание → спец? → фото/skip).\n"
            "• /editdrink &lt;drink_id&gt; &lt;name|description&gt; &lt;new_value&gt; — заявка на редактирование (админы ур.1+, только в личке).\n"
            "• /requests — просмотр заявок (добавление/редактирование/удаление) с кнопками одобрения/отклонения (для админов).\n"
            "• /delrequest &lt;drink_id&gt; [reason] — заявка на удаление напитка (для админов)."
        )
    )

    # 9) Администрирование (кратко)
    sections.append(
        (
            "<b>Администрирование:</b>\n"
            "• Роли: обычные админы (ур.1-2) и Главный админ (ур.3); Создатель — особая роль.\n"
            "• /admin add|remove|level — управление правами админов.\n"
            "• /id — список ID напитков (только в личке).\n"
            "• /incadd — создать обычную заявку от имени Создателя для проверки модерации."
            "• /inceditdrink — создать заявку на редактирование от имени Создателя для проверки модерации."
            "• /incdelrequest — создать заявку на удаление от имени Создателя для проверки модерации."
        )
    )

    # 10) Данные и безопасность
    sections.append(
        (
            "<b>Данные и безопасность:</b>\n"
            "• Прогресс и инвентарь хранятся в базе данных.\n"
            "• Никакие приватные данные не публикуются (кроме никнеймов в таблице лидеров)."
        )
    )

    for part in sections:
        try:
            await update.message.reply_html(part, disable_web_page_preview=True)
        except Exception:
            # На случай редких ограничений — пробуем простой текст
            await update.message.reply_text(part, disable_web_page_preview=True)
