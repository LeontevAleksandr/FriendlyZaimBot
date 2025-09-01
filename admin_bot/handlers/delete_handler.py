"""
Обработчики для удаления офферов
"""
import os
import logging
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import IMAGES_DIR
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def delete_offer(callback: CallbackQuery):
    """Запрос подтверждения удаления оффера"""
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("delete_", "")

    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{offer_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_{offer_id}")
        ]
    ])

    await safe_edit_message(
        callback.message,
        "❗ <b>Подтверждение удаления</b>\n\nВы уверены, что хотите удалить оффер?\n\n"
        "⚠️ Это действие необратимо!\n• Будет удален файл логотипа\n• Все данные оффера будут потеряны",
        reply_markup=confirm_keyboard
    )


async def confirm_delete_offer(callback: CallbackQuery):
    """Подтвержденное удаление оффера"""
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("confirm_delete_", "")
    offers = load_offers()

    if offer_id not in offers.get("microloans", {}):
        await callback.answer("❌ Оффер не найден")
        return

    try:
        offer = offers["microloans"][offer_id]

        # Удаляем файл логотипа если существует
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                try:
                    os.remove(logo_path)
                    logger.info(f"Удален логотип: {logo_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления логотипа {logo_path}: {e}")

        # Удаляем оффер из базы
        offer_name = offer.get('name', offer_id)
        del offers["microloans"][offer_id]

        # Сохраняем изменения
        if save_offers(offers):
            await callback.answer("🗑️ Оффер удален")
            await safe_edit_message(
                callback.message,
                f"🗑️ <b>Оффер удален</b>\n\n📝 <b>Название:</b> {offer_name}\n🏷️ <b>ID:</b> {offer_id}\n\n✅ Логотип также удален с диска",
                reply_markup=main_keyboard()
            )
            logger.info(f"Оффер {offer_id} ({offer_name}) успешно удален")
        else:
            await callback.answer("❌ Ошибка сохранения")
            logger.error(f"Ошибка сохранения после удаления оффера {offer_id}")

    except Exception as e:
        logger.error(f"Ошибка удаления оффера {offer_id}: {e}")
        await callback.answer("❌ Ошибка удаления")


def register_delete_handlers(dp):
    """Регистрирует обработчики удаления"""
    dp.callback_query.register(delete_offer, F.data.startswith("delete_"))
    dp.callback_query.register(confirm_delete_offer, F.data.startswith("confirm_delete_"))