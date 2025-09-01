import os
from dotenv import load_dotenv

load_dotenv()

# Токены и настройки бота
BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', 'YOUR_ADMIN_BOT_TOKEN')

# Пути к файлам и директориям
DATA_DIR = 'data'
OFFERS_FILE = os.path.join(DATA_DIR, 'offers.json')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'logos')

# Способы получения средств
PAYMENT_METHODS = {
    "bank_card": {"name": "💳 Карта банка", "emoji": "💳"},
    "bank_account": {"name": "🏦 Счет в банке", "emoji": "🏦"},
    "yandex_money": {"name": "🟡 Яндекс.Деньги", "emoji": "🟡"},
    "qiwi": {"name": "🥝 QIWI", "emoji": "🥝"},
    "contact": {"name": "📞 Контакт", "emoji": "📞"},
    "cash": {"name": "💵 Наличные", "emoji": "💵"}
}

# Создание необходимых директорий
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)