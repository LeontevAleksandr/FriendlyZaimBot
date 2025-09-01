"""
Главные клавиатуры админского бота
"""
from typing import Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..utils.formatters import escape_html, format_currency_icon


def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админского бота"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить оффер", callback_data="add_offer")],
        [InlineKeyboardButton(text="📋 Список офферов", callback_data="list_offers")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")]
    ])


def offers_keyboard(offers: Dict) -> InlineKeyboardMarkup:
    """Клавиатура со списком офферов для управления"""
    buttons = []
    sorted_offers = sorted(
        offers.get('microloans', {}).items(),
        key=lambda x: (
            x[1].get('priority', {}).get('manual_boost', 0),
            x[1].get('metrics', {}).get('cr', 0)
        ),
        reverse=True
    )

    for offer_id, offer in sorted_offers:
        status = "✅" if offer.get('status', {}).get('is_active', True) else "❌"
        priority = offer.get('priority', {}).get('manual_boost', 5)
        cr = offer.get('metrics', {}).get('cr', 0)

        # Определяем валюту на основе стран
        countries = offer.get('geography', {}).get('countries', [])
        currency_icon = format_currency_icon(countries)

        # Экранируем имя оффера для безопасного отображения
        safe_name = escape_html(offer.get('name', 'Без названия'))[:25]  # Ограничиваем для места валюты
        text = f"{status} {safe_name} {currency_icon} (P:{priority}, CR:{cr}%)"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"edit_{offer_id}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)