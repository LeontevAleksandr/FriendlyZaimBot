"""
Главный файл админского бота для управления офферами МФО
Декомпозированная архитектура для максимальной масштабируемости
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты из модулей
from admin_bot.config.constants import BOT_TOKEN
from admin_bot.handlers.registration import register_all_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


async def main():
    """Главная функция запуска админского бота"""
    try:
        logger.info("🔧 Запуск админского бота...")

        # Регистрируем все обработчики
        await register_all_handlers(dp, bot)

        logger.info("🚀 Админский бот успешно запущен!")
        logger.info("📋 Доступные функции:")
        logger.info("   • ➕ Добавление офферов МФО")
        logger.info("   • 📋 Управление списком офферов")
        logger.info("   • ✏️ Редактирование всех параметров")
        logger.info("   • 🖼️ Загрузка логотипов")
        logger.info("   • 📊 Статистика системы")
        logger.info("   • 🔄 Активация/деактивация офферов")
        logger.info("   • 🗑️ Безопасное удаление")

        # Удаляем устаревшие вебхуки и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}")
        raise
    finally:
        logger.info("🛑 Закрытие сессии бота...")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Админский бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)