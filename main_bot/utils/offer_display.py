import os
import logging
from typing import Dict
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


class OfferDisplay:
    """Класс для отображения офферов с логотипами"""

    @staticmethod
    async def show_single_offer(message: Message, state: FSMContext, offer: Dict, index: int, total: int):
        """Показ одного оффера с возможностью листать"""

        # Формируем текст оффера
        name = offer.get('name', 'Без названия')
        description = offer.get('description', 'Быстрое получение займа')

        # Получаем данные пользователя для показа условий
        user_data = await state.get_data()
        amount_formatted = f"{user_data.get('amount', 0):,}".replace(',', ' ')
        country = user_data.get('country', 'russia')
        currency = "₸" if country == "kazakhstan" else "₽"

        offer_text = (
            f"🏦 <b>{name}</b>\n\n"
            f"{description}\n\n"
            f"💰 <b>Сумма:</b> {amount_formatted}{currency}\n"
            f"📅 <b>Срок:</b> {user_data.get('term', 0)} дней\n"
            f"🆓 <b>Процент:</b> {'0% для новых клиентов' if offer.get('zero_percent') else 'Выгодные условия'}\n\n"
            f"📊 <b>Вариант {index + 1} из {total}</b>"
        )

        # Формируем кнопки
        buttons = []

        # Главная кнопка - получить займ
        buttons.append([
            InlineKeyboardButton(
                text="💰 ПОЛУЧИТЬ ЗАЙМ",
                callback_data=f"get_loan_{offer['id']}"
            )
        ])

        # Кнопки навигации
        nav_buttons = []

        # Кнопка "Назад" если не первый
        if index > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_offer")
            )

        # Кнопка "Далее" если не последний
        if index < total - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️ Еще варианты", callback_data="next_offer")
            )

        if nav_buttons:
            buttons.append(nav_buttons)

        # Кнопка изменения параметров
        buttons.append([
            InlineKeyboardButton(text="🔄 Изменить условия", callback_data="change_params")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Удаляем предыдущее сообщение с оффером всегда, чтобы убрать картинки
        user_data = await state.get_data()
        last_message_id = user_data.get('last_offer_message_id')
        if last_message_id:
            try:
                await message.bot.delete_message(message.chat.id, last_message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить предыдущее сообщение: {e}")

        # Проверяем наличие логотипа и отправляем соответствующим образом
        logo_path = offer.get('logo')
        if logo_path and os.path.exists(f"data/images/logos/{logo_path}"):
            try:
                # Отправляем с фото
                photo = FSInputFile(f"data/images/logos/{logo_path}")
                sent_message = await message.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=offer_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                # Сохраняем ID сообщения для следующего удаления
                await state.update_data(last_offer_message_id=sent_message.message_id)

            except Exception as e:
                logger.error(f"Ошибка отправки фото {logo_path}: {e}")
                # Отправляем без картинки при ошибке
                sent_message = await message.answer(offer_text, reply_markup=keyboard, parse_mode="HTML")
                await state.update_data(last_offer_message_id=sent_message.message_id)
        else:
            # Отправляем без картинки
            sent_message = await message.answer(offer_text, reply_markup=keyboard, parse_mode="HTML")
            await state.update_data(last_offer_message_id=sent_message.message_id)