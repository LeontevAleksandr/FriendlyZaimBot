"""
Валидаторы для данных админского бота
"""
import re
from typing import Dict, Tuple, List


def parse_metrics(text: str) -> Tuple[bool, Dict]:
    """
    Парсит метрики из текста в двух форматах:
    1. Числа через пробел: "55.4 4.5 110.89 200.76"
    2. С метками: "CR: 55.4% AR: 4.5% EPC: 110.89 EPL: 200.76"
    """
    text = text.strip()

    # Формат: числа через пробел
    space_match = re.match(r'^(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)$', text)
    if space_match:
        try:
            cr, ar, epc, epl = map(float, space_match.groups())
            return True, {"cr": cr, "ar": ar, "epc": epc, "epl": epl}
        except ValueError:
            pass

    # Формат: из сайта с метками
    patterns = {
        "cr": r'CR:?\s*(\d+\.?\d*)%?',
        "ar": r'AR:?\s*(\d+\.?\d*)%?',
        "epc": r'EPC:?\s*(\d+\.?\d*)',
        "epl": r'EPL:?\s*(\d+\.?\d*)'
    }

    metrics = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                metrics[name] = float(match.group(1))
            except ValueError:
                continue

    return len(metrics) == 4, metrics


def validate_age_range(text: str) -> Tuple[bool, Dict]:
    """Валидирует возрастной диапазон"""
    text = text.strip()

    # Формат: "18-70" или "18 70"
    age_match = re.match(r'^(\d+)[-\s]+(\d+)$', text)
    if age_match:
        try:
            min_age, max_age = map(int, age_match.groups())
            if 18 <= min_age <= max_age <= 99:
                return True, {"min_age": min_age, "max_age": max_age}
        except ValueError:
            pass

    return False, {}


def validate_amount_range(text: str) -> Tuple[bool, Dict]:
    """Валидирует диапазон сумм займа"""
    text = text.strip().replace(' ', '').replace(',', '')

    # Формат: "5000-50000" или "5000 50000"
    amount_match = re.match(r'^(\d+)[-\s]*(\d+)$', text.replace(' ', ''))
    if amount_match:
        try:
            min_amount, max_amount = map(int, amount_match.groups())
            if 1000 <= min_amount <= max_amount <= 1000000:
                return True, {"min_amount": min_amount, "max_amount": max_amount}
        except ValueError:
            pass

    return False, {}


def validate_loan_terms(text: str) -> Tuple[bool, Dict]:
    """Валидирует сроки займа в днях"""
    text = text.strip()

    # Формат: "7-30" или "7 30"
    terms_match = re.match(r'^(\d+)[-\s]+(\d+)$', text)
    if terms_match:
        try:
            min_days, max_days = map(int, terms_match.groups())
            if 1 <= min_days <= max_days <= 365:
                return True, {"min_days": min_days, "max_days": max_days}
        except ValueError:
            pass

    return False, {}


def validate_priority(text: str) -> Tuple[bool, int]:
    """Валидирует приоритет (1-10)"""
    try:
        priority = int(text.strip())
        if 1 <= priority <= 10:
            return True, priority
    except ValueError:
        pass

    return False, 0


def validate_url(url: str) -> bool:
    """Простая валидация URL"""
    if not url or not url.strip():
        return False

    url = url.strip()
    return url.startswith(('http://', 'https://')) and len(url) > 10