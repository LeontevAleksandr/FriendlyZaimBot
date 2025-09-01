"""
Обработчики выбора способов оплаты при добавлении нового оффера
"""
import logging
from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import PAYMENT_METHODS
from admin_bot.states.add_offer_states import AddOfferStates
from admin_bot.keyboards.payment_keyboards import get_payment_methods_keyboard
from admin_bot.utils.formatters import format_payment_methods
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def handle_add_offer_payment_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора способов оплаты при создании оффера"""
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    current_methods = data.get('payment_methods', [])
    action = callback.data.replace("payment_", "")

    if action == "all":
        # Переключение между "все способы" и "никакие способы"
        current_methods = [] if len(current_methods) == len(PAYMENT_METHODS) else list(PAYMENT_METHODS.keys())
    elif action == "reset":
        # Сброс всех выборов
        current_methods = []
    elif action == "done":
        # Завершение выбора способов оплаты
        if not current_methods:
            await callback.answer("❌ Выберите хотя бы один способ получения")
            return

        await state.update_data(payment_methods=current_methods)
        await state.set_state(AddOfferStates.logo)

        methods_text = format_payment_methods(current_methods)

        await safe_edit_message(
            callback.message,
            f"✅ <b>Способы получения выбраны:</b>\n{methods_text}\n\n"
            f"🖼️ <b>Финальный шаг:</b> Загрузите логотип МФО\n\n"
            f"📎 Отправьте изображение в чат\n"
            f"• Поддерживаемые форматы: JPG, PNG\n"
            f"• Рекомендуемый размер: до 2MB\n\n"
            f"💡 <i>После загрузки логотипа оффер будет создан автоматически</i>",
            parse_mode="HTML"
        )
        return
    elif action in PAYMENT_METHODS:
        # Переключение конкретного способа оплаты
        if action in current_methods:
            current_methods.remove(action)
        else:
            current_methods.append(action)

    # Обновление состояния и клавиатуры
    await state.update_data(payment_methods=current_methods)

    text = (
        f"💳 <b>Способы получения средств</b>\n\n"
        f"📊 <b>Выбранные способы:</b>\n{format_payment_methods(current_methods)}\n\n"
        f"🔧 Выберите все доступные способы получения:"
    )

    await safe_edit_message(
        callback.message,
        text,
        reply_markup=get_payment_methods_keyboard(current_methods, show_back=False)
    )


def register_add_payment_methods_handlers(dp):
    """Регистрирует обработчики способов оплаты для создания оффера"""
    dp.callback_query.register(
        handle_add_offer_payment_selection,
        F.data.startswith("payment_"),
        AddOfferStates.payment_methods
    )