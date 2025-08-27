from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_popular_offers_keyboard():
    """Клавиатура популярных предложений для максимальной конверсии"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 ЗАЙМЫ 0% (БЕЗ ПЕРЕПЛАТ)", callback_data="popular_zero_percent")],
        [InlineKeyboardButton(text="💳 НА КАРТУ ЗА 5 МИНУТ", callback_data="popular_instant")],
        [InlineKeyboardButton(text="💵 НАЛИЧНЫМИ В РУКИ", callback_data="popular_cash")],
        [InlineKeyboardButton(text="🚀 БОЛЬШИЕ СУММЫ (до 500К)", callback_data="popular_big_amount")],
        [InlineKeyboardButton(text="⚡ БЕЗ СПРАВОК И ПОРУЧИТЕЛЕЙ", callback_data="popular_no_docs")],
        [InlineKeyboardButton(text="🛡️ ПЛОХАЯ КИ? НЕ ПРОБЛЕМА!", callback_data="popular_bad_credit")],
        [
            InlineKeyboardButton(text="🇷🇺 Для России", callback_data="popular_russia"),
            InlineKeyboardButton(text="🇰🇿 Для Казахстана", callback_data="popular_kazakhstan")
        ]
    ])
    return keyboard


def get_country_keyboard():
    """Клавиатура выбора страны"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
        [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
    ])
    return keyboard


def get_age_keyboard():
    """Клавиатура выбора возраста"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="18-25 лет", callback_data="age_18_25"),
            InlineKeyboardButton(text="26-35 лет", callback_data="age_26_35")
        ],
        [
            InlineKeyboardButton(text="36-50 лет", callback_data="age_36_50"),
            InlineKeyboardButton(text="51+ лет", callback_data="age_51_plus")
        ]
    ])
    return keyboard


def get_offer_navigation_keyboard(current_index: int, total_offers: int, offer_id: str):
    """Клавиатура навигации по офферам"""
    buttons = []

    # Навигация
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_offer"))
    if current_index < total_offers - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Еще варианты", callback_data="next_offer"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Главная кнопка - ПОЛУЧИТЬ ЗАЙМ
    buttons.append([InlineKeyboardButton(text="💰 ПОЛУЧИТЬ ЗАЙМ", callback_data=f"get_loan_{offer_id}")])

    # Дополнительные действия
    buttons.append([
        InlineKeyboardButton(text="🔄 Изменить условия", callback_data="change_params"),
        InlineKeyboardButton(text="🔙 К популярным", callback_data="back_to_popular")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)