import logging

# Пути к файлам данных
OFFERS_FILE = "data/offers.json"
DB_FILE = "data/analytics.db"


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )