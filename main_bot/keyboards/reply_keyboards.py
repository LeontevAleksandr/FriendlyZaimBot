from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    """Создает постоянную клавиатуру для максимальной конверсии"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔥 Популярные предложения"),
                KeyboardButton(text="💰 Найти займ")
            ],
            [KeyboardButton(text="⚙️ Настройки профиля")],
            [KeyboardButton(text="🚀 Поделиться ботом")]
        ],
        resize_keyboard=True,
        persistent=True,
        one_time_keyboard=False
    )
    return keyboard