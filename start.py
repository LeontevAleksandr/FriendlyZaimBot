import os
import sys
import subprocess
import sqlite3
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

def create_directories():
    """Создает необходимые директории"""
    directories = ['data', 'data/images', 'data/images/logos']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def init_database():
    """Инициализирует базу данных SQLite"""
    db_path = 'data/analytics.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(50),
            first_name VARCHAR(100),
            age INTEGER,
            country VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP,
            total_sessions INTEGER DEFAULT 0,
            total_link_clicks INTEGER DEFAULT 0
        )
    ''')

    # Таблица сессий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_end TIMESTAMP,
            age INTEGER,
            country VARCHAR(20),
            amount_requested INTEGER,
            shown_offers TEXT,
            clicked_offer_id VARCHAR(50),
            completed BOOLEAN DEFAULT FALSE
        )
    ''')

    # Таблица кликов по ссылкам
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_clicks (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            session_id INTEGER REFERENCES sessions(id),
            offer_id VARCHAR(50) NOT NULL,
            country VARCHAR(20),
            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(45),
            user_agent TEXT
        )
    ''')

    conn.commit()
    conn.close()


def init_offers_file():
    """Создает файл офферов с тестовыми данными"""
    offers_path = 'data/offers.json'
    if not os.path.exists(offers_path):
        test_offers = {
            "microloans": {
                "offer_001": {
                    "id": "offer_001",
                    "name": "МФО Быстроденьги",
                    "logo": "fastmoney_logo.jpg",
                    "geography": {
                        "countries": ["russia"],
                        "russia_link": "https://example.com/russia?ref={user_id}",
                        "kazakhstan_link": None
                    },
                    "limits": {
                        "min_amount": 1000,
                        "max_amount": 50000,
                        "min_age": 18,
                        "max_age": 70
                    },
                    "zero_percent": True,
                    "description": "Деньги на карту за 5 минут, без справок и поручителей",
                    "metrics": {
                        "cr": 25.5,
                        "ar": 12.3,
                        "epc": 180.50,
                        "epl": 708.22
                    },
                    "priority": {
                        "manual_boost": 8,
                        "final_score": 90.5
                    },
                    "status": {
                        "is_active": True,
                        "created_at": "2025-08-05T14:00:00.000000",
                        "updated_at": "2025-08-05T14:00:00.000000"
                    }
                },
                "offer_002": {
                    "id": "offer_002",
                    "name": "Займ Экспресс",
                    "logo": "express_logo.jpg",
                    "geography": {
                        "countries": ["russia", "kazakhstan"],
                        "russia_link": "https://example.com/russia?ref={user_id}",
                        "kazakhstan_link": "https://example.com/kz?ref={user_id}"
                    },
                    "limits": {
                        "min_amount": 3000,
                        "max_amount": 30000,
                        "min_age": 21,
                        "max_age": 65
                    },
                    "zero_percent": False,
                    "description": "Быстрое одобрение, деньги через 10 минут",
                    "metrics": {
                        "cr": 18.2,
                        "ar": 15.7,
                        "epc": 220.30,
                        "epl": 1211.54
                    },
                    "priority": {
                        "manual_boost": 6,
                        "final_score": 75.8
                    },
                    "status": {
                        "is_active": True,
                        "created_at": "2025-08-05T14:00:00.000000",
                        "updated_at": "2025-08-05T14:00:00.000000"
                    }
                },
                "offer_003": {
                    "id": "offer_003",
                    "name": "Мгновенные займы",
                    "logo": None,
                    "geography": {
                        "countries": ["russia"],
                        "russia_link": "https://example.com/instant?ref={user_id}",
                        "kazakhstan_link": None
                    },
                    "limits": {
                        "min_amount": 500,
                        "max_amount": 25000,
                        "min_age": 18,
                        "max_age": 75
                    },
                    "zero_percent": True,
                    "description": "0% первый займ, решение за 3 минуты",
                    "metrics": {
                        "cr": 30.1,
                        "ar": 8.9,
                        "epc": 195.75,
                        "epl": 650.45
                    },
                    "priority": {
                        "manual_boost": 9,
                        "final_score": 85.2
                    },
                    "status": {
                        "is_active": True,
                        "created_at": "2025-08-05T14:00:00.000000",
                        "updated_at": "2025-08-05T14:00:00.000000"
                    }
                }
            },
            "metadata": {
                "created_at": "2025-08-05T14:00:00Z",
                "updated_at": "2025-08-05T14:00:00Z",
                "version": "1.0"
            }
        }

        with open(offers_path, 'w', encoding='utf-8') as f:
            json.dump(test_offers, f, ensure_ascii=False, indent=2)


def create_env_file():
    """Создает шаблон .env файла"""
    if not os.path.exists('.env'):
        env_template = """# Токены ботов (получите у @BotFather)
MAIN_BOT_TOKEN=YOUR_MAIN_BOT_TOKEN_HERE
ADMIN_BOT_TOKEN=YOUR_ADMIN_BOT_TOKEN_HERE

# ID администраторов (узнайте у @userinfobot)
ADMIN_IDS=123456789,987654321

# Режим отладки
DEBUG=True
"""
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_template)
        return False
    return True


def check_env_file():
    """Проверяет правильность .env файла"""
    if not create_env_file():
        print("❌ Создан шаблон .env файла - заполните его и перезапустите")
        return False

    load_dotenv()
    main_token = os.getenv('MAIN_BOT_TOKEN')

    if not main_token or main_token == 'YOUR_MAIN_BOT_TOKEN_HERE':
        print("❌ Настройте токены в .env файле")
        return False

    return True


def install_requirements():
    """Устанавливает зависимости"""
    requirements_content = """aiogram==3.4.1
python-dotenv==1.0.0
aiofiles==23.2.1
"""

    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w') as f:
            f.write(requirements_content)

    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        print("❌ Ошибка установки зависимостей")
        return False


async def run_both_bots():
    """Запускает оба бота одновременно"""
    print("🚀 Запускаем систему займов...")
    print("🤖 Основной бот + 🔧 Админ-бот")
    print("⏹️  Для остановки нажмите Ctrl+C")
    print("=" * 50)

    try:
        load_dotenv()

        # Импорт и создание ботов
        from main_bot import LoanBot

        main_token = os.getenv('MAIN_BOT_TOKEN')
        main_bot = LoanBot(main_token)

        # Запуск основного бота
        task_main = asyncio.create_task(main_bot.start_polling())

        # Если есть админ-бот, запускаем его в отдельном процессе
        admin_process = None
        if os.path.exists('admin_bot.py'):
            admin_process = subprocess.Popen([sys.executable, 'admin_bot.py'])
            print("✅ Админ-бот запущен")

        print("✅ Основной бот запущен")

        # Ждем завершения основного бота
        await task_main

        # Останавливаем админ-бот если он был запущен
        if admin_process:
            admin_process.terminate()

    except KeyboardInterrupt:
        print("\n⏹️ Боты остановлены")
        if 'admin_process' in locals() and admin_process:
            admin_process.terminate()
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def main():
    """Основная функция запуска"""
    print("🔧 Инициализация...")

    # Проверки и инициализация
    if not check_env_file():
        return

    if not install_requirements():
        return

    if not os.path.exists('main_bot.py'):
        print("❌ Файл main_bot.py не найден!")
        return

    # Создание структуры
    create_directories()
    init_database()
    init_offers_file()

    print("✅ Система готова!")

    # Запуск ботов
    asyncio.run(run_both_bots())


if __name__ == "__main__":
    main()