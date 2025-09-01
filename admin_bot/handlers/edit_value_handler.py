"""
Обработчики для редактирования значений полей офферов
"""
import os
import logging
from datetime import datetime
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from admin_bot.config.constants import IMAGES_DIR
from admin_bot.states.edit_states import EditStates
from admin_bot.keyboards.offer_keyboards import edit_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers, update_offer_timestamp
from admin_bot.utils.validators import parse_metrics, validate_age_range, validate_amount_range, validate_loan_terms, \
    validate_priority
from admin_bot.utils.formatters import escape_html

logger = logging.getLogger(__name__)


async def process_edit_value(message: Message, state: FSMContext):
    """Обработка введенного значения для редактирования поля"""
    data = await state.get_data()
    offer_id = data.get("offer_id")
    field = data.get("field")
    new_value = message.text.strip() if message.text else ""

    # Проверка на отмену
    if new_value.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=edit_keyboard(offer_id))
        return

    # Загрузка оффера
    offers = load_offers()
    offer = offers.get("microloans", {}).get(offer_id)
    if not offer:
        await message.answer("❌ Оффер не найден")
        await state.clear()
        return

    try:
        success = await process_field_update(offer, field, new_value, message)

        if success:
            # Обновляем timestamp и сохраняем
            offer = update_offer_timestamp(offer)
            offers["microloans"][offer_id] = offer
            save_offers(offers)

            # Возвращаем к редактированию
            await message.answer("🔧 Возврат к редактированию:", reply_markup=edit_keyboard(offer_id))

    except ValueError as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка обновления поля {field}: {e}")
        await message.answer("❌ <b>Ошибка обновления</b>", parse_mode="HTML")

    await state.clear()


async def process_field_update(offer: dict, field: str, new_value: str, message: Message) -> bool:
    """Обрабатывает обновление конкретного поля оффера"""

    if field == "logo":
        return await process_logo_field(offer, new_value, message)
    elif field == "name":
        offer["name"] = new_value
        await message.answer("✅ <b>Название обновлено!</b>", parse_mode="HTML")
    elif field == "desc":
        offer["description"] = new_value
        await message.answer("✅ <b>Описание обновлено!</b>", parse_mode="HTML")
    elif field == "ru_link":
        offer["geography"]["russia_link"] = new_value
        await message.answer("✅ <b>Ссылка для России обновлена!</b>", parse_mode="HTML")
    elif field == "kz_link":
        offer["geography"]["kazakhstan_link"] = new_value if new_value != "-" else None
        await message.answer("✅ <b>Ссылка для Казахстана обновлена!</b>", parse_mode="HTML")
    elif field == "priority":
        return await process_priority_field(offer, new_value, message)
    elif field == "amounts":
        return await process_amounts_field(offer, new_value, message)
    elif field == "age":
        return await process_age_field(offer, new_value, message)
    elif field == "loan_terms":
        return await process_loan_terms_field(offer, new_value, message)
    elif field == "metrics":
        return await process_metrics_field(offer, new_value, message)
    else:
        raise ValueError(f"Неизвестное поле: {field}")

    return True


async def process_logo_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля логотипа"""
    if new_value == "-":
        # Удаление текущего логотипа
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                os.remove(logo_path)
        offer['logo'] = None
        await message.answer("🗑️ <b>Логотип удален</b>", parse_mode="HTML")
        return True
    else:
        # Запрос на загрузку нового изображения
        await message.answer(
            "🖼️ <b>Для загрузки нового логотипа отправьте изображение</b>\n\n"
            "• Поддерживаемые форматы: JPG, PNG\n"
            "• Или отправьте '-' чтобы удалить текущий логотип\n"
            "• Или 'отмена' чтобы вернуться назад",
            parse_mode="HTML"
        )
        return False


async def process_priority_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля приоритета"""
    is_valid, priority = validate_priority(new_value)
    if not is_valid:
        raise ValueError("Приоритет должен быть числом от 1 до 10")

    offer["priority"]["manual_boost"] = priority
    offer["priority"]["final_score"] = priority * 10
    await message.answer(f"✅ <b>Приоритет обновлен:</b> {priority}/10", parse_mode="HTML")
    return True


async def process_amounts_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля лимитов по сумме"""
    is_valid, amounts = validate_amount_range(new_value)
    if not is_valid:
        raise ValueError("Формат: мин макс (например: 5000 50000)")

    offer["limits"]["min_amount"] = amounts["min_amount"]
    offer["limits"]["max_amount"] = amounts["max_amount"]

    await message.answer(
        f"✅ <b>Лимиты сумм обновлены!</b>\n\n"
        f"💰 Минимум: {amounts['min_amount']:,} ₽\n"
        f"💰 Максимум: {amounts['max_amount']:,} ₽",
        parse_mode="HTML"
    )
    return True


async def process_age_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля возрастных ограничений"""
    is_valid, ages = validate_age_range(new_value)
    if not is_valid:
        raise ValueError("Формат: мин макс (например: 18 70)")

    offer["limits"]["min_age"] = ages["min_age"]
    offer["limits"]["max_age"] = ages["max_age"]

    await message.answer(
        f"✅ <b>Возрастные ограничения обновлены!</b>\n\n"
        f"👤 Минимум: {ages['min_age']} лет\n"
        f"👤 Максимум: {ages['max_age']} лет",
        parse_mode="HTML"
    )
    return True


async def process_loan_terms_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля сроков займа"""
    is_valid, terms = validate_loan_terms(new_value)
    if not is_valid:
        raise ValueError("Формат: мин макс (например: 7 30). Значения должны быть больше 0")

    if "loan_terms" not in offer:
        offer["loan_terms"] = {}

    offer["loan_terms"]["min_days"] = terms["min_days"]
    offer["loan_terms"]["max_days"] = terms["max_days"]

    await message.answer(
        f"✅ <b>Сроки займа обновлены!</b>\n\n"
        f"📅 Минимум: {terms['min_days']} дней\n"
        f"📅 Максимум: {terms['max_days']} дней",
        parse_mode="HTML"
    )
    return True


async def process_metrics_field(offer: dict, new_value: str, message: Message) -> bool:
    """Обработка поля CPA метрик"""
    success, metrics = parse_metrics(new_value)
    if not success:
        raise ValueError(
            "Неверный формат метрик.\n"
            "Используйте:\n"
            "• Через пробел: 54.9 4.2 102.01 185.98\n"
            "• Или скопируйте с сайта: CR: 54.9% AR: 4.2% ..."
        )

    if "metrics" not in offer:
        offer["metrics"] = {}

    offer["metrics"].update(metrics)

    await message.answer(
        f"✅ <b>Метрики обновлены!</b>\n\n"
        f"📈 CR: {metrics['cr']}%\n"
        f"📈 AR: {metrics['ar']}%\n"
        f"💰 EPC: {metrics['epc']} ₽\n"
        f"💰 EPL: {metrics['epl']} ₽",
        parse_mode="HTML"
    )
    return True


def register_edit_value_handlers(dp):
    """Регистрирует обработчики редактирования значений"""
    dp.message.register(process_edit_value, EditStates.waiting_value)