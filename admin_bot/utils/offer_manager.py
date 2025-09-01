"""
Утилиты для работы с офферами в админском боте
"""
import json
import os
from typing import Dict
from datetime import datetime

from ..config.constants import OFFERS_FILE


def load_offers() -> Dict:
    """Загружает офферы из JSON файла"""
    if not os.path.exists(OFFERS_FILE):
        return {"microloans": {}}
    try:
        with open(OFFERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки офферов: {e}")
        return {"microloans": {}}


def save_offers(data: Dict) -> bool:
    """Сохраняет офферы в JSON файл"""
    try:
        with open(OFFERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения офферов: {e}")
        return False


def generate_offer_id() -> str:
    """Генерирует новый уникальный ID для оффера"""
    offers = load_offers()
    existing_ids = list(offers.get('microloans', {}).keys())
    max_num = 0

    for offer_id in existing_ids:
        if offer_id.startswith('offer_'):
            try:
                num = int(offer_id.split('_')[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue

    return f"offer_{max_num + 1:03d}"


def update_offer_timestamp(offer: Dict) -> Dict:
    """Обновляет timestamp последнего изменения оффера"""
    if 'status' not in offer:
        offer['status'] = {}

    offer['status']['updated_at'] = datetime.utcnow().isoformat() + 'Z'

    # Устанавливаем created_at если его нет
    if 'created_at' not in offer['status']:
        offer['status']['created_at'] = offer['status']['updated_at']

    return offer


def create_new_offer_template() -> Dict:
    """Создает шаблон нового оффера с базовыми полями"""
    timestamp = datetime.utcnow().isoformat() + 'Z'

    return {
        "name": "",
        "logo": None,
        "geography": {
            "countries": [],
            "russia_link": "",
            "kazakhstan_link": ""
        },
        "limits": {
            "min_amount": 5000,
            "max_amount": 30000,
            "min_age": 18,
            "max_age": 70
        },
        "loan_terms": {
            "min_days": 7,
            "max_days": 30
        },
        "zero_percent": False,
        "description": "",
        "payment_methods": [],
        "metrics": {
            "cr": 0.0,
            "ar": 0.0,
            "epc": 0.0,
            "epl": 0.0
        },
        "priority": {
            "manual_boost": 5,
            "final_score": 0
        },
        "status": {
            "is_active": True,
            "created_at": timestamp,
            "updated_at": timestamp
        }
    }