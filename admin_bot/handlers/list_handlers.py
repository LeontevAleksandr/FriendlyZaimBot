"""
Обработчики для просмотра и управления списком офферов
"""
import os
import logging
from datetime import datetime
from aiogram import F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import IMAGES_DIR
from admin_bot.states.edit_states import EditStates, PaymentMethodsStates
from admin_bot.keyboards.main_keyboards import offers_keyboard
from admin_bot.keyboards.offer_keyboards import edit_keyboard, back_to_offer_keyboard
from admin_bot.keyboards.payment_keyboards import get_payment_methods_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers, update_offer_timestamp
from admin_bot.utils.formatters import format_offer_info, format_payment_methods, escape_html
from admin_bot.utils.message_utils import safe_edit_message, safe_send_photo

logger = logging.getLogger(__name__)


async def list_offers(callback: CallbackQuery):
    """Показать список всех офферов"""
    if not is_admin(callback.from_user.id):
        return

    try:
        offers = load_offers()
        if not offers.get("microloans"):
            await safe_edit_message(callback.message, "📋 Список пуст", reply_markup=main_keyboard())
            return

        text = f"📋 <b>Офферы ({len(offers['microloans'])})</b>"
        await safe_edit_message(callback.message, text, reply_markup=offers_keyboard(offers))

    except Exception as e:
        logger.error(f"Ошибка в list_offers: {e}")
        await callback.answer("❌ Ошибка загрузки офферов")


async def view_offer(callback: CallbackQuery):
    """Просмотр детальной информации об оффере"""
    if not is_admin(callback.from_user.id):
        return

    try:
        offer_id = callback.data.replace("edit_", "")
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        text = format_offer_info(offer, offer_id)

        # Если есть логотип, пробуем отправить его вместе с информацией
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                photo = FSInputFile(logo_path)
                if await safe_send_photo(callback.message, photo, text, edit_keyboard(offer_id)):
                    return

        await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))

    except Exception as e:
        logger.error(f"Ошибка в view_offer: {e}")
        await callback.answer("❌ Ошибка загрузки оффера")


async def back_to_offer(callback: CallbackQuery, state: FSMContext):
    """Возврат к просмотру оффера из режима редактирования"""
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    offer_id = callback.data.replace("back_to_offer_", "")

    try:
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        text = format_offer_info(offer, offer_id)

        # Если есть логотип, пробуем отправить его вместе с информацией
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                photo = FSInputFile(logo_path)
                if await safe_send_photo(callback.message, photo, text, edit_keyboard(offer_id)):
                    return

        await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))

    except Exception as e:
        logger.error(f"Ошибка в back_to_offer: {e}")
        await callback.answer("❌ Ошибка возврата к офферу")


async def payment_method_back(callback: CallbackQuery, state: FSMContext):
    """Возврат из режима выбора способов оплаты"""
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    offer_id = data.get('offer_id')
    await state.clear()

    if offer_id:
        # Создаем callback с нужными данными для back_to_offer
        callback.data = f"back_to_offer_{offer_id}"
        await back_to_offer(callback, state)
    else:
        from ..handlers.start_handler import back_to_main
        await back_to_main(callback)


def register_list_handlers(dp):
    """Регистрирует обработчики списка офферов"""
    dp.callback_query.register(list_offers, F.data == "list_offers")
    dp.callback_query.register(view_offer, F.data.startswith("edit_"))
    dp.callback_query.register(back_to_offer, F.data.startswith("back_to_offer_"))
    dp.callback_query.register(payment_method_back, F.data == "payment_back", PaymentMethodsStates.selecting)