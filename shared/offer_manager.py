import json
import logging
from typing import Dict, List, Any

from main_bot.config.settings import OFFERS_FILE

logger = logging.getLogger(__name__)


class OfferManager:
    """Управление офферами и их ранжирование"""

    def __init__(self, offers_file: str = OFFERS_FILE):
        self.offers_file = offers_file
        self.offers_data = {}
        self.load_offers()

    def load_offers(self):
        """Загрузка офферов из JSON файла"""
        try:
            with open(self.offers_file, 'r', encoding='utf-8') as f:
                self.offers_data = json.load(f)
            logger.info(f"Загружено {len(self.offers_data.get('microloans', {}))} офферов")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Ошибка загрузки офферов: {e}")
            self.offers_data = {"microloans": {}}

    def get_filtered_offers(self, user_criteria: Dict[str, Any]) -> List[Dict]:
        """Получение и ранжирование офферов по критериям пользователя"""
        offers = []

        for offer_id, offer in self.offers_data.get('microloans', {}).items():
            # Базовые проверки
            if (not offer.get('status', {}).get('is_active', False) or
                    offer.get('priority', {}).get('manual_boost', 1) == 0 or
                    user_criteria['country'] not in offer.get('geography', {}).get('countries', [])):
                continue

            # Проверки лимитов
            limits = offer.get('limits', {})
            if not (limits.get('min_age', 18) <= user_criteria['age'] <= limits.get('max_age', 70)):
                continue

            requested_amount = user_criteria.get('amount', 0)
            if not (limits.get('min_amount', 0) <= requested_amount <= limits.get('max_amount', 999999)):
                continue

            # Проверка 0%
            if user_criteria.get('zero_percent_only', False) and not offer.get('zero_percent', False):
                continue

            # Добавляем с приоритетом
            offer_copy = offer.copy()
            offer_copy['calculated_priority'] = self.calculate_priority(offer, user_criteria)
            offers.append(offer_copy)

        return sorted(offers, key=lambda x: x['calculated_priority'], reverse=True)[:10]

    def calculate_priority(self, offer: Dict, user_criteria: Dict) -> float:
        """Расчет приоритета оффера для пользователя"""
        # Базовые метрики из CPA
        metrics = offer.get('metrics', {})
        cr = metrics.get('cr', 0)  # Conversion Rate
        epc = metrics.get('epc', 0)  # Earnings Per Click

        # Базовый скор
        base_score = cr * 2.0 + epc / 50

        # Ручной множитель админа
        manual_boost = offer.get('priority', {}).get('manual_boost', 1)

        # Бонусы за соответствие
        relevance_bonus = 0

        # Бонус за 0% если нужен
        if user_criteria.get('zero_percent_only') and offer.get('zero_percent'):
            relevance_bonus += 25

        # Итоговый скор
        final_score = (base_score * manual_boost) + relevance_bonus

        return round(final_score, 2)