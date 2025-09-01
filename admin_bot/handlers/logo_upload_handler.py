"""
Обработчики для загрузки и управления логотипами
"""
import os
import logging
from datetime import datetime
from typing import Dict
from aiogram import F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import IMAGES_DIR
from admin_bot.states.edit_states import EditStates
from admin_bot.states.add_offer_states import AddOfferStates
from admin_bot.keyboards.offer_keyboards import edit_keyboard
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers, generate_offer_id, update_offer_timestamp
from admin_bot.utils.formatters import escape_html, format_payment_methods
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def handle_photo_upload(message: Message, state: FSMContext, bot):
    """Обработка загрузки фотографий для логотипов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    current_state = await state.get_state()
    data = await state.get_data()

    # Загрузка логотипа при редактировании существующего оффера
    if current_state == EditStates.waiting_value.state and data.get('field') == 'logo':
        await handle_edit_logo_upload(message, state, bot)
    # Загрузка логотипа при создании нового оффера
    elif current_state == AddOfferStates.logo.state:
        await handle_add_offer_logo(message, state, bot)
    else:
        await message.answer(
            "🖼️ <b>Загрузка изображений</b>\n\n"
            "Для загрузки логотипа:\n"
            "📋 Перейдите в список офферов → выберите оффер → нажмите '🖼️ Логотип'",
            parse_mode="HTML"
        )


async def handle_edit_logo_upload(message: Message, state: FSMContext, bot):
    """Обработка загрузки логотипа при редактировании оффера"""
    data = await state.get_data()
    offer_id = data.get('offer_id')

    if not offer_id:
        await message.answer("❌ Ошибка: ID оффера не найден")
        await state.clear()
        return

    try:
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)
        if not offer:
            await message.answer("❌ Оффер не найден")
            await state.clear()
            return

        # Удаляем старый логотип если есть
        if offer.get('logo'):
            old_logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(old_logo_path):
                os.remove(old_logo_path)

        # Сохраняем новый логотип
        logo_filename = await save_logo_file(message, bot, offer_id)

        # Обновляем оффер
        offer['logo'] = logo_filename
        offer = update_offer_timestamp(offer)
        offers["microloans"][offer_id] = offer
        save_offers(offers)

        await message.answer(
            f"✅ <b>Логотип обновлен!</b>\n\n📁 <b>Файл:</b> {escape_html(logo_filename)}",
            parse_mode="HTML"
        )
        await message.answer("🔧 Возврат к редактированию:", reply_markup=edit_keyboard(offer_id))
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при сохранении логотипа: {e}")
        await message.answer("❌ <b>Ошибка при сохранении логотипа</b>", parse_mode="HTML")
        await state.clear()


async def handle_add_offer_logo(message: Message, state: FSMContext, bot):
    """Обработка загрузки логотипа при создании нового оффера"""
    try:
        data = await state.get_data()
        offer_id = generate_offer_id()

        # Сохраняем логотип
        logo_filename = await save_logo_file(message, bot, offer_id)

        # Создаем оффер с загруженным логотипом
        await create_offer_with_data(data, offer_id, logo_filename, message, state)

    except Exception as e:
        logger.error(f"Ошибка при загрузке логотипа: {e}")
        await message.answer("❌ <b>Ошибка при загрузке логотипа</b>", parse_mode="HTML")
        await state.clear()


async def save_logo_file(message: Message, bot, offer_id: str) -> str:
    """Сохраняет файл логотипа и возвращает имя файла"""
    photo = message.photo[-1]  # Берем фото наивысшего качества
    file_info = await bot.get_file(photo.file_id)

    # Определяем расширение файла
    file_extension = 'jpg'  # По умолчанию
    if file_info.file_path and '.' in file_info.file_path:
        file_extension = file_info.file_path.split('.')[-1]

    # Создаем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logo_filename = f"{offer_id}_{timestamp}.{file_extension}"
    logo_path = os.path.join(IMAGES_DIR, logo_filename)

    # Скачиваем и сохраняем файл
    await bot.download_file(file_info.file_path, logo_path)

    return logo_filename


async def create_offer_with_data(data: Dict, offer_id: str, logo_filename: str, message: Message, state: FSMContext):
    """Создает новый оффер с полученными данными"""
    now = datetime.now().isoformat()

    offer = {
        "id": offer_id,
        "name": data["name"],
        "logo": logo_filename,
        "geography": {
            "countries": data["countries"],
            "russia_link": data["russia_link"],
            "kazakhstan_link": data.get("kazakhstan_link")
        },
        "limits": {
            "min_amount": data["min_amount"],
            "max_amount": data["max_amount"],
            "min_age": data["min_age"],
            "max_age": data["max_age"]
        },
        "loan_terms": {
            "min_days": data.get("min_days", 5),
            "max_days": data.get("max_days", 30)
        },
        "zero_percent": data["zero_percent"],
        "description": data["description"],
        "payment_methods": data.get("payment_methods", []),
        "metrics": data["metrics"],
        "priority": {
            "manual_boost": data["priority"],
            "final_score": data["priority"] * 10
        },
        "status": {
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
    }

    # Сохраняем оффер
    offers = load_offers()
    offers["microloans"][offer_id] = offer
    save_offers(offers)

    # Подготавливаем информацию для уведомления
    metrics = data["metrics"]
    logo_status = f"✅ {escape_html(logo_filename)}" if logo_filename else "❌ Не загружен"
    payment_methods_text = format_payment_methods(data.get("payment_methods", []))
    safe_name = escape_html(data['name'])

    # Определяем валюту для отображения
    countries = data.get("countries", [])
    if 'kazakhstan' in countries and 'russia' not in countries:
        epc_currency = "₸"
    elif 'russia' in countries and 'kazakhstan' in countries:
        epc_currency = "₽/₸"
    else:
        epc_currency = "₽"

    # Уведомление о создании оффера
    await message.answer(
        f"✅ <b>Оффер создан!</b>\n\n"
        f"🏷️ <b>ID:</b> {offer_id}\n"
        f"📝 <b>Название:</b> {safe_name}\n"
        f"⭐ <b>Приоритет:</b> {data['priority']}\n"
        f"📈 <b>CR:</b> {metrics['cr']}%\n"
        f"💰 <b>EPC:</b> {metrics['epc']} {epc_currency}\n"
        f"🖼️ <b>Логотип:</b> {logo_status}\n"
        f"💳 <b>Способы получения:</b>\n{payment_methods_text}",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()


def register_logo_upload_handlers(dp):
    """Регистрирует обработчики загрузки логотипов"""
    # Обработчик будет зарегистрирован в главном файле с передачей bot
    pass