"""
Клавиатуры для выбора способов получения средств
"""
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..config.constants import PAYMENT_METHODS


def get_payment_methods_keyboard(current: List[str] = None, show_back: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура выбора способов получения средств"""
    if current is None:
        current = []

    buttons = []
    all_selected = len(current) == len(PAYMENT_METHODS)
    buttons.append([InlineKeyboardButton(
        text="✅ Все способы" if all_selected else "⬜ Все способы",
        callback_data="payment_all"
    )])

    for method_id, method_info in PAYMENT_METHODS.items():
        is_selected = method_id in current
        text = f"✅ {method_info['name']}" if is_selected else f"⬜ {method_info['name']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"payment_{method_id}")])

    bottom_buttons = []
    if show_back:
        bottom_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="payment_back"))
    bottom_buttons.append(InlineKeyboardButton(text="🔄 Сбросить", callback_data="payment_reset"))
    bottom_buttons.append(InlineKeyboardButton(text="✅ Готово", callback_data="payment_done"))

    buttons.append(bottom_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)