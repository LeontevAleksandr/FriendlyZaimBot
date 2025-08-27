import sqlite3
import logging
import os
from main_bot.config.settings import DB_FILE

logger = logging.getLogger(__name__)


async def init_database():
    """Проверка и инициализация базы данных при необходимости"""
    try:
        # Создаем директорию data если её нет
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

        # Проверяем, существует ли БД и корректна ли её структура
        if os.path.exists(DB_FILE):
            # Проверяем структуру существующей БД
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Проверяем наличие основных таблиц
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('users', 'sessions', 'link_clicks')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]

            if len(existing_tables) == 3:
                logger.info(f"✅ База данных уже существует и корректна: {DB_FILE}")
                conn.close()
                return

            conn.close()

        # Если БД нет или структура неполная, создаём/дополняем
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Выполняем создание таблиц (IF NOT EXISTS защитит от дублирования)
        sql_commands = [
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                total_sessions INTEGER DEFAULT 0,
                total_link_clicks INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",

            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                age INTEGER,
                country TEXT,
                amount_requested INTEGER,
                shown_offers TEXT,
                completed BOOLEAN DEFAULT FALSE,
                clicked_offer_id TEXT,
                session_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_end DATETIME,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )""",

            """CREATE TABLE IF NOT EXISTS link_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER,
                offer_id TEXT NOT NULL,
                country TEXT,
                clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE SET NULL
            )""",

            # Индексы
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions (session_start)",
            "CREATE INDEX IF NOT EXISTS idx_link_clicks_user_id ON link_clicks (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_link_clicks_offer_id ON link_clicks (offer_id)",
            "CREATE INDEX IF NOT EXISTS idx_link_clicks_clicked_at ON link_clicks (clicked_at)",
            "CREATE INDEX IF NOT EXISTS idx_link_clicks_country ON link_clicks (country)"
        ]

        for sql_command in sql_commands:
            cursor.execute(sql_command)

        conn.commit()
        logger.info(f"✅ База данных проверена/создана: {DB_FILE}")

    except Exception as e:
        logger.error(f"❌ Ошибка работы с БД: {e}")
        raise
    finally:
        if conn:
            conn.close()