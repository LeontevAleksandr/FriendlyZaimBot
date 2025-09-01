"""
Утилиты для безопасной работы с сообщениями
"""
import logging

logger = logging.getLogger(__name__)


async def safe_edit_message(message, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасно редактирует сообщение с обработкой ошибок"""
    try:
        # Ограничиваем длину текста
        if len(text) > 4096:
            text = text[:4000] + "\n\n... (текст сокращен)"

        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        # Пробуем отправить новое сообщение вместо редактирования
        try:
            await message.delete()
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e2:
            logger.error(f"Ошибка отправки сообщения: {e2}")
            # В крайнем случае отправляем простое сообщение
            await message.answer(
                "❌ Произошла ошибка при отображении информации",
                reply_markup=reply_markup
            )


async def safe_send_photo(message, photo, caption: str, reply_markup=None, parse_mode="HTML"):
    """Безопасно отправляет фото с подписью"""
    try:
        if len(caption) > 1024:
            caption = caption[:1000] + "\n\n... (текст сокращен)"

        await message.delete()
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке изображения: {e}")
        return False