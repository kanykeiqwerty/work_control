import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

from app.utils.report_builder import build_report_data, build_telegram_text
from app.utils.data_utils import format_report_date

logger = logging.getLogger(__name__)


def _last_five_days() -> list[date]:
    return [date.today() - timedelta(days=i) for i in range(1, 8)]


def _build_main_keyboard() -> InlineKeyboardMarkup:
    """5 последних дат + кнопка открыть календарь."""
    workdays = _last_five_days()
    buttons = [
        [InlineKeyboardButton(
            text=format_report_date(d),
            callback_data=f"report:{d.isoformat()}",
        )]
        for d in workdays
    ]
    buttons.append([InlineKeyboardButton("📅 Выбрать другую дату", callback_data="open_calendar")])
    return InlineKeyboardMarkup(buttons)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Выберите дату для отчёта:",
        reply_markup=_build_main_keyboard(),
    )


async def callback_open_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переход к календарю."""
    query = update.callback_query
    await query.answer()
    calendar, step = DetailedTelegramCalendar(locale="ru").build()
    await query.edit_message_text(
        f"Выберите {LSTEP[step]}:",
        reply_markup=calendar,
    )


async def callback_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Навигация по календарю и выбор даты."""
    query = update.callback_query

    result, key, step = DetailedTelegramCalendar(locale="ru").process(query.data)

    if not result and key:
        await query.edit_message_text(
            f"Выберите {LSTEP[step]}:",
            reply_markup=key,
        )
    elif result:
        await _send_report(query, result)


async def callback_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие на одну из пяти последних дат."""
    query = update.callback_query
    await query.answer()
    _, date_str = query.data.split(":", 1)
    await _send_report(query, date.fromisoformat(date_str))


async def _send_report(query, target_date: date) -> None:
    """Общая логика получения и отправки отчёта."""
    await query.edit_message_text(f"⏳ Формирую отчёт за {format_report_date(target_date)}…")

    try:
        report_data = build_report_data(target_date)
    except Exception as exc:
        logger.error("Ошибка при формировании отчёта за %s: %s", target_date, exc)
        await query.edit_message_text(f"❌ Ошибка:\n{exc}")
        return

    if report_data is None:
        await query.edit_message_text(
            f"📭 Данные за {format_report_date(target_date)} не найдены.\n"
            f"Таблица посещаемости не заполнена."
        )
        return

    await query.edit_message_text(build_telegram_text(report_data))


def create_bot_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CallbackQueryHandler(callback_open_calendar, pattern=r"^open_calendar$"))
    app.add_handler(CallbackQueryHandler(callback_calendar, pattern=r"^cbcal_"))
    app.add_handler(CallbackQueryHandler(callback_report, pattern=r"^report:"))
    return app