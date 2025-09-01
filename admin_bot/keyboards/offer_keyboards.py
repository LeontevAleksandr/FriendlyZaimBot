"""
Клавиатуры для управления офферами
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def edit_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    """Клавиатура редактирования оффера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"field_{offer_id}_name")],
        [InlineKeyboardButton(text="🎯 0% предложение", callback_data=f"field_{offer_id}_zero")],
        [InlineKeyboardButton(text="💰 Суммы", callback_data=f"field_{offer_id}_amounts")],
        [InlineKeyboardButton(text="👤 Возраст", callback_data=f"field_{offer_id}_age")],
        [InlineKeyboardButton(text="📅 Сроки займа", callback_data=f"field_{offer_id}_loan_terms")],
        [InlineKeyboardButton(text="📝 Описание", callback_data=f"field_{offer_id}_desc")],
        [InlineKeyboardButton(text="💳 Способы получения", callback_data=f"field_{offer_id}_payment_methods")],
        [InlineKeyboardButton(text="📈 CPA метрики", callback_data=f"field_{offer_id}_metrics")],
        [InlineKeyboardButton(text="🔗 Ссылка РФ", callback_data=f"field_{offer_id}_ru_link")],
        [InlineKeyboardButton(text="🔗 Ссылка КЗ", callback_data=f"field_{offer_id}_kz_link")],
        [InlineKeyboardButton(text="🖼️ Логотип", callback_data=f"field_{offer_id}_logo")],
        [InlineKeyboardButton(text="⭐ Приоритет", callback_data=f"field_{offer_id}_priority")],
        [InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=f"toggle_{offer_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{offer_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="list_offers")]
    ])


def back_to_offer_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    """Клавиатура возврата к редактированию оффера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_offer_{offer_id}")]
    ])


def confirm_delete_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{offer_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_to_offer_{offer_id}")
        ]
    ])