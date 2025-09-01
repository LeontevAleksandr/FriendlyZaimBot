"""
Обработчики для выбора способов получения средств
"""
import logging
from datetime import datetime
from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import PAYMENT_METHODS
from admin_bot.states.edit_states import PaymentMethodsStates
from admin_bot.keyboards.offer_keyboards import edit_keyboard
from admin_bot.keyboards.payment_keyboards import get_payment_methods_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers, update_offer_timestamp
from admin_bot.utils.formatters import format_offer_info, format_payment_methods
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def handle_payment_method_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора способов получения средств"""
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    current_methods = data.get('current_methods', [])
    action = callback.data.replace("payment_", "")

    if action == "all":
        # Переключение между "все способы" и "никакие способы"
        current_methods = [] if len(current_methods) == len(PAYMENT_METHODS) else list(PAYMENT_METHODS.keys())
    elif action == "reset":
        # Сброс всех выборов
        current_methods = []
    elif action == "done":
        # Сохранение выбранных способов
        offer_id = data.get('offer_id')
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if offer:
            offer['payment_methods'] = current_methods
            offer = update_offer_timestamp(offer)
            offers["microloans"][offer_id] = offer
            save_offers(offers)

            await callback.answer("✅ Способы получения обновлены!")
            await state.clear()

            # Возврат к редактированию оффера
            text = format_offer_info(offer, offer_id)
            await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))
            return
        else:
            await callback.answer("❌ Ошибка: оффер не найден")
            await state.clear()
            return
    elif action in PAYMENT_METHODS:
        # Переключение конкретного способа оплаты
        if action in current_methods:
            current_methods.remove(action)
        else:
            current_methods.append(action)

    # Обновление состояния и клавиатуры
    await state.update_data(current_methods=current_methods)

    text = (
        f"💳 <b>Способы получения средств</b>\n\n"
        f"📊 <b>Выбранные способы:</b>\n{format_payment_methods(current_methods)}\n\n"
        f"🔧 Выберите доступные способы получения:"
    )
    await safe_edit_message(
        callback.message,
        text,
        reply_markup=get_payment_methods_keyboard(current_methods)
    )


def register_payment_methods_handlers(dp):
    """Регистрирует обработчики способов оплаты"""
    dp.callback_query.register(
        handle_payment_method_selection,
        F.data.startswith("payment_"),
        PaymentMethodsStates.selecting
    )