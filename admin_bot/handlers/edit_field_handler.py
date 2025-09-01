"""
Обработчики для редактирования полей офферов
"""
import logging
from datetime import datetime
from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.states.edit_states import EditStates, PaymentMethodsStates
from admin_bot.keyboards.offer_keyboards import back_to_offer_keyboard
from admin_bot.keyboards.payment_keyboards import get_payment_methods_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers, update_offer_timestamp
from admin_bot.utils.formatters import format_payment_methods, escape_html
from admin_bot.utils.message_utils import safe_edit_message
from admin_bot.handlers.list_handlers import view_offer

logger = logging.getLogger(__name__)


async def edit_field(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование поля оффера"""
    if not is_admin(callback.from_user.id):
        return

    try:
        data_part = callback.data.replace("field_", "")

        # Парсим тип поля и ID оффера
        if data_part.endswith("_ru_link"):
            offer_id, field = data_part.replace("_ru_link", ""), "ru_link"
        elif data_part.endswith("_kz_link"):
            offer_id, field = data_part.replace("_kz_link", ""), "kz_link"
        elif data_part.endswith("_payment_methods"):
            offer_id, field = data_part.replace("_payment_methods", ""), "payment_methods"
        elif data_part.endswith("_loan_terms"):
            offer_id, field = data_part.replace("_loan_terms", ""), "loan_terms"
        else:
            parts = data_part.rsplit("_", 1)
            if len(parts) != 2:
                await callback.answer("❌ Ошибка формата")
                return
            offer_id, field = parts

        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)
        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        # Обработка переключения 0% предложений
        if field == "zero":
            current_zero = offer.get('zero_percent', False)
            offer['zero_percent'] = not current_zero
            offer = update_offer_timestamp(offer)
            offers["microloans"][offer_id] = offer
            save_offers(offers)

            await callback.answer(f"0% {'включен' if not current_zero else 'отключен'}")
            await view_offer(callback)
            return

        # Обработка выбора способов оплаты
        if field == "payment_methods":
            current_methods = offer.get('payment_methods', [])
            await state.set_state(PaymentMethodsStates.selecting)
            await state.update_data(offer_id=offer_id, current_methods=current_methods)

            text = (
                f"💳 <b>Способы получения средств</b>\n\n"
                f"📊 <b>Текущие способы:</b>\n{format_payment_methods(current_methods)}\n\n"
                f"🔧 Выберите доступные способы получения:"
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_payment_methods_keyboard(current_methods)
            )
            return

        # Обработка загрузки логотипа
        if field == "logo":
            logo_status = f"✅ {escape_html(offer.get('logo'))}" if offer.get('logo') else "❌ Не загружен"
            await state.set_state(EditStates.waiting_value)
            await state.update_data(offer_id=offer_id, field=field)

            text = (
                f"🖼️ <b>Редактирование логотипа</b>\n\n"
                f"📊 <b>Текущий логотип:</b> {logo_status}\n\n"
                f"📎 Отправьте новое изображение или:\n"
                f"• '-' чтобы удалить текущий логотип\n"
                f"• 'отмена' чтобы вернуться назад"
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=back_to_offer_keyboard(offer_id)
            )
            return

        # Обработка остальных полей
        await state.set_state(EditStates.waiting_value)
        await state.update_data(offer_id=offer_id, field=field)

        # Получаем текущие значения полей
        current_values = {
            "name": escape_html(offer.get('name', 'Не указано')),
            "desc": escape_html(offer.get('description', 'Не указано')),
            "amounts": f"{offer['limits']['min_amount']} {offer['limits']['max_amount']}",
            "age": f"{offer['limits']['min_age']} {offer['limits']['max_age']}",
            "loan_terms": (
                f"{offer.get('loan_terms', {}).get('min_days', 'Не указано')} "
                f"{offer.get('loan_terms', {}).get('max_days', 'Не указано')}"
                if offer.get('loan_terms') else "Не указаны"
            ),
            "ru_link": escape_html(offer.get('geography', {}).get('russia_link', 'Не указана')),
            "kz_link": escape_html(offer.get('geography', {}).get('kazakhstan_link') or 'Не указана'),
            "priority": str(offer.get('priority', {}).get('manual_boost', 0)),
            "metrics": (
                f"CR: {offer.get('metrics', {}).get('cr', 0)}%, "
                f"AR: {offer.get('metrics', {}).get('ar', 0)}%, "
                f"EPC: {offer.get('metrics', {}).get('epc', 0)}, "
                f"EPL: {offer.get('metrics', {}).get('epl', 0)}"
            )
        }

        # Промпты для редактирования полей
        field_prompts = {
            "name": f"📝 <b>Текущее название:</b> <i>{current_values['name']}</i>\n\nВведите новое название:",
            "desc": f"📝 <b>Текущее описание:</b> <i>{current_values['desc']}</i>\n\nВведите новое описание:",
            "amounts": f"💰 <b>Текущие суммы:</b> <i>{current_values['amounts']}</i>\n\nВведите новые суммы (формат: мин макс):",
            "age": f"👤 <b>Текущий возраст:</b> <i>{current_values['age']}</i>\n\nВведите новый возраст (формат: мин макс):",
            "loan_terms": f"📅 <b>Текущие сроки займа:</b> <i>{current_values['loan_terms']}</i>\n\nВведите новые сроки в днях (формат: мин макс):\nНапример: 5 30",
            "ru_link": f"🔗 <b>Текущая ссылка РФ:</b>\n<i>{current_values['ru_link']}</i>\n\nВведите новую ссылку для России:",
            "kz_link": f"🔗 <b>Текущая ссылка КЗ:</b>\n<i>{current_values['kz_link']}</i>\n\nВведите новую ссылку для Казахстана (или '-'):",
            "priority": f"⭐ <b>Текущий приоритет:</b> <i>{current_values['priority']}</i>\n\nВведите новый приоритет (0-10):",
            "metrics": (
                f"📈 <b>Текущие метрики:</b>\n<i>{current_values['metrics']}</i>\n\n"
                f"📈 <b>Введите новые CPA метрики одним из способов:</b>\n\n"
                f"<b>Способ 1 - через пробел:</b>\n"
                f"<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n"
                f"<b>Способ 2 - скопировать с сайта:</b>\n"
                f"<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>"
            )
        }

        prompt_text = field_prompts.get(field, f"Введите новое значение:")
        await safe_edit_message(
            callback.message,
            prompt_text,
            reply_markup=back_to_offer_keyboard(offer_id)
        )

    except Exception as e:
        logger.error(f"Ошибка в edit_field: {e}")
        await callback.answer("❌ Ошибка редактирования поля")


def register_edit_field_handlers(dp):
    """Регистрирует обработчики редактирования полей"""
    dp.callback_query.register(edit_field, F.data.startswith("field_"))