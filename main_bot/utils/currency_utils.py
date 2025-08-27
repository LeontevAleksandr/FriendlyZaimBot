"""Валютные утилиты для мультивалютной поддержки"""


def get_currency_symbol(country: str) -> str:
    """Получение символа валюты по стране"""
    return "₸" if country == "kazakhstan" else "₽"


def get_country_name(country: str) -> str:
    """Получение названия страны"""
    return "Казахстан" if country == "kazakhstan" else "Россия"


def get_country_flag(country: str) -> str:
    """Получение флага страны"""
    return "🇰🇿" if country == "kazakhstan" else "🇷🇺"


def format_amount(amount: int, country: str) -> str:
    """Форматирование суммы с валютой"""
    currency = get_currency_symbol(country)
    formatted = f"{amount:,}".replace(',', ' ')
    return f"{formatted}{currency}"


def get_default_amounts(country: str) -> list:
    """Получение стандартных сумм для страны"""
    if country == "kazakhstan":
        return [50000, 100000, 150000, 250000, 500000]
    else:
        return [5000, 10000, 15000, 25000, 50000]


def get_amount_limits(country: str) -> dict:
    """Получение лимитов сумм для страны"""
    if country == "kazakhstan":
        return {"min": 10000, "max": 500000}
    else:
        return {"min": 1000, "max": 50000}