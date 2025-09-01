import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """Модель профиля пользователя (адаптирована под существующую БД)"""
    telegram_id: int
    username: str = None
    first_name: str = None
    age: int = None
    country: str = None
    created_at: datetime = None
    last_activity: datetime = None
    total_sessions: int = 0
    total_link_clicks: int = 0


class UserProfileManager:
    """Менеджер для работы с профилями пользователей (адаптирован под существующую БД)"""

    def __init__(self, db_file: str = "data/analytics.db"):
        self.db_file = db_file
        # Не создаем таблицы - они уже существуют

    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_file)

    async def get_or_create_profile(self, telegram_id: int, username: str = None,
                                    first_name: str = None) -> UserProfile:
        """Получение или создание профиля пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Пытаемся найти существующий профиль
            cursor.execute("""
                SELECT telegram_id, username, first_name, age, country,
                       created_at, last_activity, total_sessions, total_link_clicks
                FROM users 
                WHERE telegram_id = ?
            """, (telegram_id,))

            row = cursor.fetchone()

            if row:
                # Обновляем активность и контактные данные
                cursor.execute("""
                    UPDATE users 
                    SET username = ?, first_name = ?, 
                        last_activity = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (username, first_name, telegram_id))

                conn.commit()

                # Возвращаем профиль
                return UserProfile(
                    telegram_id=row[0],
                    username=row[1] or username,
                    first_name=row[2] or first_name,
                    age=row[3],
                    country=row[4],
                    created_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    last_activity=datetime.fromisoformat(row[6]) if row[6] else None,
                    total_sessions=row[7] or 0,
                    total_link_clicks=row[8] or 0
                )
            else:
                # Создаем новый профиль
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_activity)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (telegram_id, username, first_name))

                conn.commit()

                logger.info(f"Создан новый профиль: {telegram_id} ({username})")

                return UserProfile(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name
                )

        except Exception as e:
            logger.error(f"Ошибка работы с профилем {telegram_id}: {e}")
            # Возвращаем базовый профиль при ошибке
            return UserProfile(telegram_id=telegram_id, username=username, first_name=first_name)
        finally:
            conn.close()

    async def update_profile_preferences(self, telegram_id: int, country: str = None, age: int = None):
        """Обновление предпочтений пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            updates = []
            params = []

            if country:
                updates.append("country = ?")
                params.append(country)

            if age:
                updates.append("age = ?")
                params.append(age)

            if updates:
                updates.append("last_activity = CURRENT_TIMESTAMP")
                params.append(telegram_id)

                query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?"
                cursor.execute(query, params)
                conn.commit()

                logger.info(f"Обновлены предпочтения пользователя {telegram_id}: country={country}, age={age}")

        except Exception as e:
            logger.error(f"Ошибка обновления предпочтений {telegram_id}: {e}")
        finally:
            conn.close()

    async def increment_sessions(self, telegram_id: int):
        """Увеличение счетчика сессий"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users 
                SET total_sessions = total_sessions + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка увеличения счетчика сессий {telegram_id}: {e}")
        finally:
            conn.close()

    async def increment_clicks(self, telegram_id: int):
        """Увеличение счетчика кликов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users 
                SET total_link_clicks = total_link_clicks + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка увеличения счетчика кликов {telegram_id}: {e}")
        finally:
            conn.close()

    async def get_user_stats(self, telegram_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT total_sessions, total_link_clicks, created_at, last_activity
                FROM users
                WHERE telegram_id = ?
            """, (telegram_id,))

            row = cursor.fetchone()
            if row:
                total_sessions = row[0] or 0
                total_clicks = row[1] or 0

                return {
                    'total_sessions': total_sessions,
                    'total_link_clicks': total_clicks,
                    'conversion_rate': (total_clicks / total_sessions * 100) if total_sessions > 0 else 0,
                    'created_at': row[2],
                    'last_activity': row[3]
                }
            return {}

        except Exception as e:
            logger.error(f"Ошибка получения статистики {telegram_id}: {e}")
            return {}
        finally:
            conn.close()

    async def check_if_returning_user(self, telegram_id: int) -> bool:
        """Проверка, возвращающийся ли пользователь (есть ли сохраненные страна и возраст)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE telegram_id = ? AND country IS NOT NULL AND age IS NOT NULL
            """, (telegram_id,))

            count = cursor.fetchone()[0]
            return count > 0

        except Exception as e:
            logger.error(f"Ошибка проверки пользователя {telegram_id}: {e}")
            return False
        finally:
            conn.close()

    async def clear_profile(self, telegram_id: int):
        """Очистка профиля пользователя - сброс страны и возраста"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Обнуляем только настройки профиля, оставляя статистику
            cursor.execute("""
                UPDATE users 
                SET country = NULL, 
                    age = NULL, 
                    last_activity = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))

            conn.commit()
            logger.info(f"Профиль пользователя {telegram_id} очищен (country, age)")

        except Exception as e:
            logger.error(f"Ошибка очистки профиля {telegram_id}: {e}")
            raise  # Пробрасываем исключение для обработки в вызывающем коде
        finally:
            conn.close()

    async def get_recent_user_activity(self, days: int = 7) -> Dict[str, int]:
        """Получение статистики активности за последние дни"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Новые пользователи
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE created_at >= datetime('now', '-{} days')
            """.format(days))
            new_users = cursor.fetchone()[0]

            # Активные пользователи
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE last_activity >= datetime('now', '-{} days')
            """.format(days))
            active_users = cursor.fetchone()[0]

            # Пользователи с кликами
            cursor.execute("""
                SELECT COUNT(DISTINCT u.telegram_id) FROM users u
                JOIN link_clicks lc ON u.id = lc.user_id
                WHERE lc.clicked_at >= datetime('now', '-{} days')
            """.format(days))
            converting_users = cursor.fetchone()[0]

            return {
                'new_users': new_users,
                'active_users': active_users,
                'converting_users': converting_users,
                'conversion_rate': (converting_users / active_users * 100) if active_users > 0 else 0
            }

        except Exception as e:
            logger.error(f"Ошибка получения активности: {e}")
            return {}
        finally:
            conn.close()