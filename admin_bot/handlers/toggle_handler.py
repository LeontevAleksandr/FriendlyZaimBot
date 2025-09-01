"""
Обработчики для включения/выключения офферов
"""
import logging
from datetime import datetime
from aiogram import F
from aiogram.types import CallbackQuery

from admin_bot.config.auth import is_admin
from admin_bot.utils.offer_manager import load_offers, save_offers, update_offer_timestamp
from admin_bot.handlers.list_handlers import view_offer

logger = logging.getLogger(__name__)


async def toggle_offer(callback: CallbackQuery):
    """Включение/выключение оффера"""
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("toggle_", "")
    offers = load_offers()
    offer = offers.get("microloans", {}).get(offer_id)

    if not offer:
        await callback.answer("❌ Оффер не найден")
        return

    try:
        current_status = offer.get('status', {}).get('is_active', True)
        new_status = not current_status

        # Обновляем статус
        offer['status']['is_active'] = new_status
        offer = update_offer_timestamp(offer)

        # При отключении обнуляем приоритет
        if not new_status:
            offer['priority']['manual_boost'] = 0
            offer['priority']['final_score'] = 0
        else:
            # При включении устанавливаем минимальный приоритет если был 0
            if offer['priority']['manual_boost'] == 0:
                offer['priority']['manual_boost'] = 1
                offer['priority']['final_score'] = 10

        # Сохраняем изменения
        offers["microloans"][offer_id] = offer
        save_offers(offers)

        # Уведомляем и обновляем интерфейс
        status_text = "✅ Включен" if new_status else "❌ Отключен"
        await callback.answer(status_text)

        # Обновляем callback data для view_offer
        callback.data = f"edit_{offer_id}"
        await view_offer(callback)

    except Exception as e:
        logger.error(f"Ошибка переключения статуса оффера {offer_id}: {e}")
        await callback.answer("❌ Ошибка изменения статуса")


def register_toggle_handlers(dp):
    """Регистрирует обработчики переключения статуса"""
    dp.callback_query.register(toggle_offer, F.data.startswith("toggle_"))