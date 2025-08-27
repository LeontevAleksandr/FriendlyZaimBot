import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any

from main_bot.config.settings import DB_FILE

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Обновленный трекер для работы с существующей структурой БД"""

    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file

    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_file)

    async def track_user_start(self, user_id: int, username: str = None, first_name: str = None):
        """Регистрация нового пользователя или обновление активности"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET last_activity = CURRENT_TIMESTAMP, username = ?, first_name = ?
                WHERE telegram_id = ?
            """, (username, first_name, user_id))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_activity)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, username, first_name))
                logger.info(f"Новый пользователь: {user_id} ({username})")

            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка трекинга пользователя: {e}")
        finally:
            conn.close()

    async def track_session_start(self, user_id: int, age: int, country: str) -> Optional[int]:
        """Начало новой сессии поиска займа"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if not user_row:
                return None

            db_user_id = user_row[0]

            cursor.execute("""
                INSERT INTO sessions (user_id, age, country, session_start)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (db_user_id, age, country))

            session_id = cursor.lastrowid

            cursor.execute("""
                UPDATE users SET total_sessions = total_sessions + 1, last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (db_user_id,))

            conn.commit()
            logger.info(f"Новая сессия: user={user_id}, session={session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return None
        finally:
            conn.close()

    async def track_offers_shown(self, session_id: int, offer_ids: List[str]):
        """Сохранение показанных офферов"""
        if not session_id:
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            offers_json = json.dumps(offer_ids)
            cursor.execute("UPDATE sessions SET shown_offers = ? WHERE id = ?", (offers_json, session_id))
            conn.commit()
            logger.info(f"Показаны офферы в сессии {session_id}: {offer_ids}")
        except Exception as e:
            logger.error(f"Ошибка сохранения показанных офферов: {e}")
        finally:
            conn.close()

    async def track_session_parameters(self, session_id: int, amount: int):
        """Сохранение параметров сессии (сумма запроса)"""
        if not session_id:
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET amount_requested = ? WHERE id = ?", (amount, session_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения параметров сессии: {e}")
        finally:
            conn.close()

    async def track_link_click(self, user_id: int, session_id: int, offer_id: str, country: str):
        """ГЛАВНАЯ МЕТРИКА: Клик по партнерской ссылке"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if not user_row:
                return

            db_user_id = user_row[0]

            cursor.execute("""
                INSERT INTO link_clicks (user_id, session_id, offer_id, country, clicked_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (db_user_id, session_id, offer_id, country))

            cursor.execute("""
                UPDATE users SET total_link_clicks = total_link_clicks + 1, last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (db_user_id,))

            if session_id:
                cursor.execute("""
                    UPDATE sessions SET completed = TRUE, clicked_offer_id = ?, session_end = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (offer_id, session_id))

            conn.commit()
            logger.info(f"🎯 КЛИК ПО ССЫЛКЕ: user={user_id}, offer={offer_id}, country={country}")

        except Exception as e:
            logger.error(f"Ошибка трекинга клика: {e}")
        finally:
            conn.close()

    async def get_analytics_summary(self, days: int = 7) -> Dict[str, Any]:
        """Получение сводной аналитики за период"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            stats = {}

            cursor.execute(f"""
                SELECT 
                    COUNT(DISTINCT u.telegram_id) as total_users,
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(DISTINCT lc.id) as total_clicks,
                    COALESCE(AVG(CASE WHEN s.completed = 1 THEN 1.0 ELSE 0.0 END) * 100, 0) as completion_rate
                FROM users u
                LEFT JOIN sessions s ON u.id = s.user_id AND s.session_start >= datetime('now', '-{days} days')
                LEFT JOIN link_clicks lc ON u.id = lc.user_id AND lc.clicked_at >= datetime('now', '-{days} days')
                WHERE u.created_at >= datetime('now', '-{days} days') OR u.last_activity >= datetime('now', '-{days} days')
            """)

            row = cursor.fetchone()
            if row:
                stats.update({
                    'total_users': row[0],
                    'total_sessions': row[1],
                    'total_clicks': row[2],
                    'session_completion_rate': round(row[3], 2),
                    'click_through_rate': round((row[2] / row[1] * 100) if row[1] > 0 else 0, 2)
                })

            # Топ офферы и страны
            cursor.execute(
                f"SELECT offer_id, COUNT(*) FROM link_clicks WHERE clicked_at >= datetime('now', '-{days} days') GROUP BY offer_id ORDER BY COUNT(*) DESC LIMIT 5")
            stats['top_offers'] = [{'offer_id': r[0], 'clicks': r[1]} for r in cursor.fetchall()]

            cursor.execute(
                f"SELECT country, COUNT(*) FROM link_clicks WHERE clicked_at >= datetime('now', '-{days} days') GROUP BY country ORDER BY COUNT(*) DESC")
            stats['country_distribution'] = [{'country': r[0], 'clicks': r[1]} for r in cursor.fetchall()]

            return stats
        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {e}")
            return {}
        finally:
            conn.close()