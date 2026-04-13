import asyncio
import logging
from datetime import date

import uvicorn
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from decouple import config

from app.config.settings import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.api.router import router as report_router
from app.bot.handlers import create_bot_app
from app.services.sheets_archieve_service import save_violations
from app.services.telegram_service import send_message
from app.utils.data_utils import get_target_date, format_report_date
from app.utils.report_builder import build_report_data, build_telegram_text

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI

fastapi_app = FastAPI(title="WorkTimeControl API")
fastapi_app.include_router(report_router)


# Scheduled job 

def scheduled_report() -> None:
    """Запускается планировщиком: формирует и отправляет отчёты в Telegram."""
    targets: list[date] = get_target_date()

    for target in targets:
        report_data = build_report_data(target)

        if report_data is None:
            msg = (
                f"Отчет за {format_report_date(target)} не сформирован\n"
                f"Причина: таблица посещаемости не заполнена"
            )
            logger.warning(msg)
            send_message(msg)
            continue

        text = build_telegram_text(report_data)
        send_message(text)

        all_violations = [
            v
            for emp in report_data["employees"]
            for v in emp["violations_raw"]
        ]
        save_violations(all_violations, target)
        
        logger.info("Отчёт за %s отправлен.", target)






async def main() -> None:
    BOT_TOKEN = config("BOT_TOKEN")
    # report = build_telegram_text(build_report_data(date(2026, 4, 8)))
    # send_message(report)
    # scheduled_report()

    # 1. Telegram bot (polling)
    bot_app = create_bot_app(BOT_TOKEN)
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram polling запущен.")

    # 2. APScheduler (async)
    scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")
    scheduler.add_job(
        scheduled_report,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute=0,
    )
    scheduler.start()
    logger.info("Планировщик запущен — пн–пт в 13:00 (Asia/Bishkek).")

    # 3. FastAPI (uvicorn)
    server_config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    logger.info("FastAPI запущен на http://0.0.0.0:8000")

    try:
        await server.serve()
    finally:
        scheduler.shutdown()
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())