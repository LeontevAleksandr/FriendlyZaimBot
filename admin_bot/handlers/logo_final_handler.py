"""
Обработчик финального шага создания оффера - загрузки логотипа
"""
import logging
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.states.add_offer_states import AddOfferStates
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.utils.offer_manager import generate_offer_id
from admin_bot.handlers.logo_upload_handler import create_offer_with_data

logger = logging.getLogger(__name__)


async def add_offer_logo(message: Message, state: FSMContext):
    """Обработка финального шага - логотип или пропуск"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    # Проверка на отмену
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    # Пропуск загрузки логотипа
    if message.text and message.text.strip() == "-":
        data = await state.get_data()
        offer_id = generate_offer_id()
        await create_offer_with_data(data, offer_id, None, message, state)
        return

    # Если это не команда пропуска, просим загрузить изображение
    if message.text:
        await message.answer(
            "🖼️ <b>Для загрузки логотипа отправьте изображение</b>\n\n"
            "• Или отправьте '-' чтобы пропустить загрузку логотипа\n"
            "• Или 'отмена' для прекращения создания",
            parse_mode="HTML"
        )


def register_logo_final_handlers(dp):
    """Регистрирует обработчик финального шага создания оффера"""
    dp.message.register(add_offer_logo, AddOfferStates.logo)