"""
Обработчики команд запуска и главного меню
"""
import os
import sys
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from admin_bot.config.auth import is_admin
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def cmd_start(message: Message):
    """Команда /start - главное меню админ-панели"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    await message.answer(
        "🔧 <b>Админ-панель займов</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    if not is_admin(callback.from_user.id):
        return

    await safe_edit_message(
        callback.message,
        "🔧 <b>Админ-панель займов</b>",
        reply_markup=main_keyboard()
    )


async def restart_bot(callback: CallbackQuery):
    """Перезапуск бота"""
    if not is_admin(callback.from_user.id):
        return

    await callback.answer("🔄 Перезапуск бота...")
    await safe_edit_message(
        callback.message,
        "🔄 <b>Бот перезапускается...</b>\n\nПодождите несколько секунд и нажмите /start"
    )

    # Закрываем текущую сессию
    try:
        from admin_bot import bot
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка закрытия сессии: {e}")

    # Перезапускаем процесс
    os.execv(sys.executable, ['python'] + sys.argv)


def register_start_handlers(dp):
    """Регистрирует обработчики команд запуска"""
    dp.message.register(cmd_start, Command("start"))
    dp.callback_query.register(back_to_main, F.data == "main_menu")
    dp.callback_query.register(restart_bot, F.data == "restart_bot")