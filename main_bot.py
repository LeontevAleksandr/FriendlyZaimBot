import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from main_bot.handlers.start_handler import StartHandler
from main_bot.handlers.loan_handlers import LoanHandlers
from main_bot.handlers.callback_handlers import CallbackHandlers
from main_bot.config.settings import setup_logging
from shared.database import init_database

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

# Конфигурация бота из переменных окружения
BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_MAIN_BOT_TOKEN_HERE":
    logger.error("❌ Токен основного бота не найден в .env файле!")
    logger.error("💡 Добавьте MAIN_BOT_TOKEN в файл .env")
    exit(1)


class LoanBot:
    """Основной класс бота для микрозаймов - точка входа"""

    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())

        # Инициализация обработчиков
        self.start_handler = StartHandler(self.bot)
        self.loan_handlers = LoanHandlers(self.bot)
        self.callback_handlers = CallbackHandlers(self.bot)

        self.register_handlers()

    def register_handlers(self):
        """Регистрация всех обработчиков"""
        self.start_handler.register_handlers(self.dp)
        self.loan_handlers.register_handlers(self.dp)
        self.callback_handlers.register_handlers(self.dp)

    async def setup_bot_commands(self):
        """Настройка меню команд бота"""
        await self.start_handler.setup_bot_commands()

    async def start_polling(self):
        """Запуск бота"""
        logger.info("🚀 Запуск основного бота для поиска микрозаймов")

        # Инициализация БД
        await init_database()

        # Настройка команд
        await self.setup_bot_commands()

        logger.info("✅ Бот успешно запущен и готов к работе!")

        # Запуск polling
        await self.dp.start_polling(self.bot)


async def main():
    """Главная функция запуска"""
    bot = LoanBot(BOT_TOKEN)

    try:
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("❌ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка бота: {e}")
    finally:
        await bot.bot.session.close()
        logger.info("🔄 Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())