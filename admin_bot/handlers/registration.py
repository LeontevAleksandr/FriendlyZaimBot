"""
Центральная система регистрации всех обработчиков админского бота
"""
import logging
from aiogram import Bot

# Импорты всех модулей обработчиков
from admin_bot.handlers.start_handler import register_start_handlers
from admin_bot.handlers.list_handlers import register_list_handlers
from admin_bot.handlers.edit_field_handler import register_edit_field_handlers
from admin_bot.handlers.payment_methods_handler import register_payment_methods_handlers
from admin_bot.handlers.logo_upload_handler import register_logo_upload_handlers
from admin_bot.handlers.edit_value_handler import register_edit_value_handlers
from admin_bot.handlers.toggle_handler import register_toggle_handlers
from admin_bot.handlers.delete_handler import register_delete_handlers
from admin_bot.handlers.stats_handler import register_stats_handlers
from admin_bot.handlers.add_offer_handler import register_add_offer_handlers
from admin_bot.handlers.add_payment_methods_handler import register_add_payment_methods_handlers

logger = logging.getLogger(__name__)


async def register_all_handlers(dp, bot: Bot):
    """
    Регистрирует все обработчики админского бота
    Порядок регистрации важен - более специфичные фильтры должны идти первыми
    """
    try:
        # 1. Обработчики команд и главного меню
        register_start_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики команд")

        # 2. Обработчики просмотра и управления списком
        register_list_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики списка офферов")

        # 3. Обработчики редактирования полей
        register_edit_field_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики редактирования полей")

        # 4. Обработчики способов оплаты (при редактировании)
        register_payment_methods_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики способов оплаты")

        # 5. Обработчики редактирования значений
        register_edit_value_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики редактирования значений")

        # 6. Обработчики переключения статуса
        register_toggle_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики переключения статуса")

        # 7. Обработчики удаления офферов
        register_delete_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики удаления")

        # 8. Обработчики статистики
        register_stats_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики статистики")

        # 9. Обработчики добавления новых офферов
        register_add_offer_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики добавления офферов")

        # 10. Обработчики способов оплаты (при добавлении)
        register_add_payment_methods_handlers(dp)
        logger.info("✅ Зарегистрированы обработчики способов оплаты для новых офферов")

        # 11. Обработчик загрузки логотипов (требует bot instance)
        await register_logo_handlers_with_bot(dp, bot)
        logger.info("✅ Зарегистрированы обработчики загрузки логотипов")

        logger.info("🚀 Все обработчики админского бота успешно зарегистрированы!")

    except Exception as e:
        logger.error(f"❌ Ошибка регистрации обработчиков: {e}")
        raise


async def register_logo_handlers_with_bot(dp, bot: Bot):
    """Регистрирует обработчики загрузки логотипов с передачей bot instance"""
    from aiogram import F
    from ..handlers.logo_upload_handler import handle_photo_upload

    # Создаем обработчик с замыканием для передачи bot
    async def photo_handler_wrapper(message, state):
        await handle_photo_upload(message, state, bot)

    dp.message.register(photo_handler_wrapper, F.photo)