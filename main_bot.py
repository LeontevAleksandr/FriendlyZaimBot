import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, \
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from user_profile_manager import UserProfileManager

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация бота из переменных окружения
BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")
OFFERS_FILE = "data/offers.json"
DB_FILE = "data/analytics.db"

if not BOT_TOKEN or BOT_TOKEN == "YOUR_MAIN_BOT_TOKEN_HERE":
    logger.error("❌ Токен основного бота не найден в .env файле!")
    logger.error("💡 Добавьте MAIN_BOT_TOKEN в файл .env")
    exit(1)


# Состояния FSM для максимально простого флоу
class LoanFlow(StatesGroup):
    choosing_country = State()
    choosing_age = State()
    choosing_amount = State()
    choosing_term = State()
    choosing_payment = State()
    choosing_zero_percent = State()
    viewing_offers = State()


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
            # Пытаемся обновить существующего пользователя
            cursor.execute("""
                UPDATE users 
                SET last_activity = CURRENT_TIMESTAMP,
                    username = ?,
                    first_name = ?
                WHERE telegram_id = ?
            """, (username, first_name, user_id))

            # Если пользователя не было, создаем нового
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
            # Получаем ID пользователя из таблицы users
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if not user_row:
                logger.error(f"Пользователь {user_id} не найден в БД")
                return None

            db_user_id = user_row[0]

            # Создаем новую сессию (используем вашу структуру)
            cursor.execute("""
                INSERT INTO sessions (user_id, age, country, session_start)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (db_user_id, age, country))

            session_id = cursor.lastrowid

            # Увеличиваем счетчик сессий пользователя
            cursor.execute("""
                UPDATE users 
                SET total_sessions = total_sessions + 1,
                    last_activity = CURRENT_TIMESTAMP
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
        cursor = conn.cursor()

        try:
            offers_json = json.dumps(offer_ids)
            cursor.execute("""
                UPDATE sessions 
                SET shown_offers = ?
                WHERE id = ?
            """, (offers_json, session_id))

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
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE sessions 
                SET amount_requested = ?
                WHERE id = ?
            """, (amount, session_id))

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
            # Получаем ID пользователя из таблицы users
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if not user_row:
                logger.error(f"Пользователь {user_id} не найден в БД")
                return

            db_user_id = user_row[0]

            # Записываем клик (используем вашу структуру)
            cursor.execute("""
                INSERT INTO link_clicks (user_id, session_id, offer_id, country, clicked_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (db_user_id, session_id, offer_id, country))

            # Обновляем статистику пользователя
            cursor.execute("""
                UPDATE users 
                SET total_link_clicks = total_link_clicks + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (db_user_id,))

            # Отмечаем сессию как завершенную
            if session_id:
                cursor.execute("""
                    UPDATE sessions 
                    SET completed = TRUE,
                        clicked_offer_id = ?,
                        session_end = CURRENT_TIMESTAMP
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
        cursor = conn.cursor()

        try:
            stats = {}

            # Общие показатели за период
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT u.telegram_id) as total_users,
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(DISTINCT lc.id) as total_clicks,
                    COALESCE(AVG(CASE WHEN s.completed = 1 THEN 1.0 ELSE 0.0 END) * 100, 0) as session_completion_rate
                FROM users u
                LEFT JOIN sessions s ON u.id = s.user_id 
                    AND s.session_start >= datetime('now', '-{} days')
                LEFT JOIN link_clicks lc ON u.id = lc.user_id 
                    AND lc.clicked_at >= datetime('now', '-{} days')
                WHERE u.created_at >= datetime('now', '-{} days') 
                   OR u.last_activity >= datetime('now', '-{} days')
            """.format(days, days, days, days))

            row = cursor.fetchone()
            if row:
                stats['total_users'] = row[0]
                stats['total_sessions'] = row[1]
                stats['total_clicks'] = row[2]
                stats['session_completion_rate'] = round(row[3], 2)
                stats['click_through_rate'] = round((row[2] / row[1] * 100) if row[1] > 0 else 0, 2)

            # Топ офферы по кликам
            cursor.execute("""
                SELECT offer_id, COUNT(*) as clicks
                FROM link_clicks 
                WHERE clicked_at >= datetime('now', '-{} days')
                GROUP BY offer_id 
                ORDER BY clicks DESC 
                LIMIT 5
            """.format(days))

            stats['top_offers'] = [{'offer_id': row[0], 'clicks': row[1]} for row in cursor.fetchall()]

            # Распределение по странам
            cursor.execute("""
                SELECT country, COUNT(*) as clicks
                FROM link_clicks 
                WHERE clicked_at >= datetime('now', '-{} days')
                GROUP BY country 
                ORDER BY clicks DESC
            """.format(days))

            stats['country_distribution'] = [{'country': row[0], 'clicks': row[1]} for row in cursor.fetchall()]

            return stats

        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {e}")
            return {}
        finally:
            conn.close()


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
        except FileNotFoundError:
            logger.warning(f"Файл {self.offers_file} не найден, создаем пустую базу")
            self.offers_data = {"microloans": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            self.offers_data = {"microloans": {}}

    def get_filtered_offers(self, user_criteria: Dict[str, Any]) -> List[Dict]:
        """Получение и ранжирование офферов по критериям пользователя"""
        offers = []

        for offer_id, offer in self.offers_data.get('microloans', {}).items():
            # Проверяем активность оффера
            if not offer.get('status', {}).get('is_active', False):
                continue

            # Проверяем ручной приоритет (0 = исключить)
            manual_boost = offer.get('priority', {}).get('manual_boost', 1)
            if manual_boost == 0:
                continue

            # Проверяем доступность для страны
            countries = offer.get('geography', {}).get('countries', [])
            if user_criteria['country'] not in countries:
                continue

            # Проверяем возрастные ограничения
            limits = offer.get('limits', {})
            min_age = limits.get('min_age', 18)
            max_age = limits.get('max_age', 70)
            user_age = user_criteria['age']

            if not (min_age <= user_age <= max_age):
                continue

            # Проверяем лимиты по сумме
            min_amount = limits.get('min_amount', 0)
            max_amount = limits.get('max_amount', 999999)
            requested_amount = user_criteria.get('amount', 0)

            if not (min_amount <= requested_amount <= max_amount):
                continue

            # Проверяем требование 0% если нужно
            if user_criteria.get('zero_percent_only', False):
                if not offer.get('zero_percent', False):
                    continue

            # Рассчитываем приоритет
            priority_score = self.calculate_priority(offer, user_criteria)
            offer_copy = offer.copy()
            offer_copy['calculated_priority'] = priority_score

            offers.append(offer_copy)

        # Сортируем по приоритету (больше = лучше)
        offers.sort(key=lambda x: x['calculated_priority'], reverse=True)

        return offers[:10]  # Возвращаем топ-10 для листания

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


class LoanBot:
    """Основной класс бота для микрозаймов"""

    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.offer_manager = OfferManager()
        self.analytics = AnalyticsTracker()
        self.profile_manager = UserProfileManager()

        self.register_handlers()

    async def setup_bot_commands(self):
        """Настройка меню команд бота"""
        commands = [
            BotCommand(command="start", description="🚀 Начать поиск займов"),
            BotCommand(command="restart", description="🔄 Перезапустить бот"),
            BotCommand(command="clear_profile", description="🗑️ Очистить профиль"),
            BotCommand(command="help", description="ℹ️ Помощь и команды")
        ]

        await self.bot.set_my_commands(commands)
        logger.info("Команды бота настроены")

    def get_settings_keyboard(self):
        """Создает постоянную клавиатуру для изменения настроек профиля и популярных предложений"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔥 Популярные предложения")],
                [KeyboardButton(text="⚙️ Настройки профиля")],
                [KeyboardButton(text="🚀 Поделиться ботом")]
            ],
            resize_keyboard=True,
            persistent=True,
            one_time_keyboard=False
        )
        return keyboard

    def register_handlers(self):
        """Регистрация всех обработчиков"""
        self.dp.message.register(self.cmd_start, CommandStart())
        self.dp.message.register(self.cmd_restart, Command("restart"))
        self.dp.message.register(self.cmd_clear_profile, Command("clear_profile"))
        self.dp.message.register(self.cmd_help, Command("help"))
        self.dp.message.register(self.handle_settings_button, F.text == "⚙️ Настройки профиля")
        self.dp.message.register(self.handle_popular_offers_button, F.text == "🔥 Популярные предложения")
        self.dp.message.register(self.handle_share_button, F.text == "🚀 Поделиться ботом")

        self.dp.callback_query.register(self.popular_offer_callback, F.data.startswith("popular_"))
        self.dp.callback_query.register(self.back_to_popular_callback, F.data == "back_to_popular")
        self.dp.callback_query.register(self.quick_search_callback, F.data.startswith("quick_search_"))
        self.dp.callback_query.register(self.change_profile_settings_callback, F.data == "change_profile_settings")
        self.dp.callback_query.register(self.edit_country_callback, F.data == "edit_country")
        self.dp.callback_query.register(self.edit_age_callback, F.data == "edit_age")
        self.dp.callback_query.register(self.back_to_main_callback, F.data == "back_to_main")
        self.dp.callback_query.register(self.country_callback, F.data.startswith("country_"))
        self.dp.callback_query.register(self.age_callback, F.data.startswith("age_"))
        self.dp.callback_query.register(self.amount_callback, F.data.startswith("amount_"))
        self.dp.callback_query.register(self.term_callback, F.data.startswith("term_"))
        self.dp.callback_query.register(self.payment_callback, F.data.startswith("payment_"))
        self.dp.callback_query.register(self.zero_percent_callback, F.data.startswith("zero_"))
        self.dp.callback_query.register(self.get_loan_callback, F.data.startswith("get_loan_"))
        self.dp.callback_query.register(self.next_offer_callback, F.data == "next_offer")
        self.dp.callback_query.register(self.prev_offer_callback, F.data == "prev_offer")
        self.dp.callback_query.register(self.back_to_offers_callback, F.data == "back_to_offers")
        self.dp.callback_query.register(self.change_params_callback, F.data == "change_params")
        self.dp.callback_query.register(self.confirm_clear_profile_callback, F.data == "confirm_clear_profile")
        self.dp.callback_query.register(self.share_bot_callback, F.data == "share_bot")

    async def handle_settings_button(self, message: Message, state: FSMContext):
        """Обработчик кнопки настроек профиля"""
        profile = await self.profile_manager.get_or_create_profile(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        settings_text = (
            "⚙️ <b>Настройки вашего профиля</b>\n\n"
            f"👤 Имя: {profile.first_name or 'Не указано'}\n"
            f"🌍 Страна: {'🇷🇺 Россия' if profile.country == 'russia' else '🇰🇿 Казахстан' if profile.country == 'kazakhstan' else 'Не выбрана'}\n"
            f"🎂 Возраст: {profile.age or 'Не указан'} лет\n\n"
            "Что хотите изменить?"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Изменить страну", callback_data="edit_country")],
            [InlineKeyboardButton(text="🎂 Изменить возраст", callback_data="edit_age")],
            [InlineKeyboardButton(text="🔙 Закрыть", callback_data="back_to_main")]
        ])

        await message.answer(settings_text, reply_markup=keyboard, parse_mode="HTML")

    async def send_message_with_keyboard(self, chat_id: int, text: str, inline_keyboard: InlineKeyboardMarkup = None,
                                         parse_mode: str = "HTML"):
        """Отправляет сообщение с inline клавиатурой и устанавливает постоянную reply клавиатуру"""
        # Отправляем сообщение с inline клавиатурой И постоянной reply клавиатурой одновременно
        settings_keyboard = self.get_settings_keyboard()

        message = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=inline_keyboard,
            parse_mode=parse_mode
        )

        # Устанавливаем постоянную reply клавиатуру отдельным техническим сообщением
        tech_message = await self.bot.send_message(
            chat_id=chat_id,
            text=".",  # Минимальное сообщение
            reply_markup=settings_keyboard
        )

        # Сразу удаляем техническое сообщение
        try:
            await tech_message.delete()
        except:
            pass

        return message

    async def popular_offer_callback(self, callback: CallbackQuery, state: FSMContext):
        """Обработчик популярных предложений с предустановленными критериями"""

        offer_type = callback.data.split("_", 1)[1]

        # Получаем или создаем профиль пользователя
        profile = await self.profile_manager.get_or_create_profile(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name
        )

        # Предустановленные критерии для разных типов популярных предложений
        if offer_type == "zero_percent":
            # 0% займы
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 15000 if (profile.country or 'russia') == 'russia' else 150000,
                'zero_percent_only': True,
                'term': 14,
                'payment_method': 'card'
            }
            search_text = "🆓 <b>ЗАЙМЫ БЕЗ ПЕРЕПЛАТ (0%)</b>"

        elif offer_type == "instant":
            # Быстрые займы на карту
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 10000 if (profile.country or 'russia') == 'russia' else 100000,
                'zero_percent_only': False,
                'term': 7,
                'payment_method': 'card'
            }
            search_text = "💳 <b>ДЕНЬГИ НА КАРТУ ЗА 5 МИНУТ</b>"

        elif offer_type == "cash":
            # Наличные
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 20000 if (profile.country or 'russia') == 'russia' else 200000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'cash'
            }
            search_text = "💵 <b>НАЛИЧНЫЕ В РУКИ</b>"

        elif offer_type == "big_amount":
            # Большие суммы
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 50000 if (profile.country or 'russia') == 'russia' else 500000,
                'zero_percent_only': False,
                'term': 30,
                'payment_method': 'card'
            }
            search_text = "🚀 <b>БОЛЬШИЕ СУММЫ (до 500К)</b>"

        elif offer_type == "no_docs":
            # Без документов
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 15000 if (profile.country or 'russia') == 'russia' else 150000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            }
            search_text = "⚡ <b>БЕЗ СПРАВОК И ПОРУЧИТЕЛЕЙ</b>"

        elif offer_type == "bad_credit":
            # Плохая КИ
            search_criteria = {
                'country': profile.country or 'russia',
                'age': profile.age or 30,
                'amount': 10000 if (profile.country or 'russia') == 'russia' else 100000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            }
            search_text = "🛡️ <b>ПЛОХАЯ КИ? НЕ ПРОБЛЕМА!</b>"

        elif offer_type == "russia":
            # Для России
            search_criteria = {
                'country': 'russia',
                'age': profile.age or 30,
                'amount': 25000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            }
            search_text = "🇷🇺 <b>ЗАЙМЫ ДЛЯ РОССИИ</b>"

        elif offer_type == "kazakhstan":
            # Для Казахстана
            search_criteria = {
                'country': 'kazakhstan',
                'age': profile.age or 30,
                'amount': 250000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            }
            search_text = "🇰🇿 <b>ЗАЙМЫ ДЛЯ КАЗАХСТАНА</b>"

        else:
            await callback.answer("❌ Неизвестный тип предложения", show_alert=True)
            return

        # Создаем сессию для аналитики
        session_id = await self.analytics.track_session_start(
            callback.from_user.id,
            search_criteria['age'],
            search_criteria['country']
        )

        # Сохраняем критерии в состоянии
        await state.update_data(**search_criteria, session_id=session_id)

        # Ищем офферы по критериям
        offers = self.offer_manager.get_filtered_offers(search_criteria)

        if not offers:
            # Если нет подходящих офферов
            no_offers_text = (
                f"{search_text}\n\n"
                "😔 <b>Пока нет доступных предложений</b>\n\n"
                "Попробуйте другие варианты или настройте поиск вручную:"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔥 Другие популярные", callback_data="back_to_popular")],
                [InlineKeyboardButton(text="🔄 Настроить вручную", callback_data="back_to_main")]
            ])

            await callback.message.edit_text(no_offers_text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()
            return

        # Удаляем сообщение с популярными предложениями
        try:
            await callback.message.delete()
            logger.info(f"Удалено сообщение с популярными предложениями: {callback.message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с популярными: {e}")

        # Сохраняем найденные офферы
        await state.update_data(
            found_offers=offers,
            current_offer_index=0
        )

        # Трекинг показанного оффера
        if session_id:
            await self.analytics.track_offers_shown(session_id, [offers[0]['id']])

        # Показываем первый оффер
        await self.show_single_offer(callback.message, state, offers[0], 0, len(offers))
        await state.set_state(LoanFlow.viewing_offers)

        await callback.answer(f"🔥 Найдено {len(offers)} популярных предложений!")

    async def back_to_popular_callback(self, callback: CallbackQuery, state: FSMContext):
        """Возврат к популярным предложениям"""
        popular_text = (
            "🔥 <b>ПОПУЛЯРНЫЕ ПРЕДЛОЖЕНИЯ</b>\n\n"
            "💰 <b>Топ займы с максимальным одобрением!</b>\n"
            "⚡ Деньги на карту за 5 минут\n"
            "✅ Одобряем 95% заявок\n"
            "🆓 0% для новых клиентов\n\n"
            "🎯 <b>Выберите что вас интересует:</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 ЗАЙМЫ 0% (БЕЗ ПЕРЕПЛАТ)", callback_data="popular_zero_percent"),
            ],
            [
                InlineKeyboardButton(text="💳 НА КАРТУ ЗА 5 МИНУТ", callback_data="popular_instant"),
                InlineKeyboardButton(text="💵 НАЛИЧНЫМИ В РУКИ", callback_data="popular_cash")
            ],
            [
                InlineKeyboardButton(text="🚀 БОЛЬШИЕ СУММЫ (до 500К)", callback_data="popular_big_amount"),
                InlineKeyboardButton(text="⚡ БЕЗ СПРАВОК И ПОРУЧИТЕЛЕЙ", callback_data="popular_no_docs")
            ],
            [
                InlineKeyboardButton(text="🛡️ ПЛОХАЯ КИ? НЕ ПРОБЛЕМА!", callback_data="popular_bad_credit"),
            ],
            [
                InlineKeyboardButton(text="🇷🇺 Для России", callback_data="popular_russia"),
                InlineKeyboardButton(text="🇰🇿 Для Казахстана", callback_data="popular_kazakhstan")
            ]
        ])

        # Используем edit_text вместо вызова handle_popular_offers_button
        await callback.message.edit_text(popular_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def handle_popular_offers_button(self, message: Message, state: FSMContext):
        """ИСПРАВЛЕННЫЙ обработчик кнопки популярных предложений - сразу показываем меню выбора"""

        popular_text = (
            "🔥 <b>ПОПУЛЯРНЫЕ ПРЕДЛОЖЕНИЯ</b>\n\n"
            "💰 <b>Топ займы с максимальным одобрением!</b>\n"
            "⚡ Деньги на карту за 5 минут\n"
            "✅ Одобряем 95% заявок\n"
            "🆓 0% для новых клиентов\n\n"
            "🎯 <b>Выберите что вас интересует:</b>"
        )

        # Самые конвертящие кнопки для максимального привлечения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 ЗАЙМЫ 0% (БЕЗ ПЕРЕПЛАТ)", callback_data="popular_zero_percent"),
            ],
            [
                InlineKeyboardButton(text="💳 НА КАРТУ ЗА 5 МИНУТ", callback_data="popular_instant"),
                InlineKeyboardButton(text="💵 НАЛИЧНЫМИ В РУКИ", callback_data="popular_cash")
            ],
            [
                InlineKeyboardButton(text="🚀 БОЛЬШИЕ СУММЫ (до 500К)", callback_data="popular_big_amount"),
                InlineKeyboardButton(text="⚡ БЕЗ СПРАВОК И ПОРУЧИТЕЛЕЙ", callback_data="popular_no_docs")
            ],
            [
                InlineKeyboardButton(text="🛡️ ПЛОХАЯ КИ? НЕ ПРОБЛЕМА!", callback_data="popular_bad_credit"),
            ],
            [
                InlineKeyboardButton(text="🇷🇺 Для России", callback_data="popular_russia"),
                InlineKeyboardButton(text="🇰🇿 Для Казахстана", callback_data="popular_kazakhstan")
            ]
        ])

        # ИСПРАВЛЕНИЕ: Отправляем ТОЛЬКО меню выбора, без промежуточного сообщения
        await message.answer(popular_text, reply_markup=keyboard, parse_mode="HTML")

    async def handle_share_button(self, message: Message, state: FSMContext):
        """Обработчик кнопки поделиться ботом"""

        bot_username = (await self.bot.get_me()).username
        share_url = f"https://t.me/{bot_username}"

        share_text = (
            "🚀 <b>Поделитесь ботом с друзьями!</b>\n\n"
            "💰 Этот бот поможет найти выгодные займы:\n"
            "✅ До 500,000₸ / 50,000₽ на карту\n"
            "⚡ Одобрение за 5 минут\n"
            "🆓 0% для новых клиентов\n"
            "🛡️ Работает даже с плохой КИ\n\n"
            f"🔗 <b>Ссылка на бота:</b>\n<code>{share_url}</code>\n\n"
            "👆 Нажмите на ссылку чтобы скопировать"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Поделиться в Telegram",
                                  url=f"https://t.me/share/url?url={share_url}&text=💰 Найди выгодный займ за 30 секунд! До 500К на карту за 5 минут.")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])

        await message.answer(share_text, reply_markup=keyboard, parse_mode="HTML")

    async def edit_message_with_keyboard(self, message: Message, text: str,
                                         inline_keyboard: InlineKeyboardMarkup = None, parse_mode: str = "HTML"):
        """Редактирует сообщение с inline клавиатурой, постоянная reply клавиатура остается"""
        try:
            if message.photo:
                await message.edit_caption(
                    caption=text,
                    reply_markup=inline_keyboard,
                    parse_mode=parse_mode
                )
            else:
                await message.edit_text(
                    text=text,
                    reply_markup=inline_keyboard,
                    parse_mode=parse_mode
                )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            # Если не можем редактировать - отправляем новое
            await message.answer(text, reply_markup=inline_keyboard, parse_mode=parse_mode)

    async def cmd_start(self, message: Message, state: FSMContext):
        """Стартовое сообщение с проверкой существующего профиля"""

        # ДОБАВЛЯЕМ: Трекинг пользователя
        await self.analytics.track_user_start(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        profile = await self.profile_manager.get_or_create_profile(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        # Сохраняем профиль в состоянии для быстрого доступа
        await state.update_data(user_profile=profile.__dict__)

        # Проверяем, есть ли сохраненные предпочтения
        if profile.country and profile.age:
            # ВОЗВРАЩАЮЩИЙСЯ ПОЛЬЗОВАТЕЛЬ с сохраненными настройками
            country_name = "🇷🇺 России" if profile.country == "russia" else "🇰🇿 Казахстане"

            welcome_text = (
                f"👋 <b>С возвращением, {profile.first_name}!</b>\n\n"
                f"📍 Ваши настройки:\n"
                f"🌍 Страна: {country_name}\n"
                f"👤 Возраст: {profile.age} лет\n"
                f"💡 Используйте кнопку ниже для настройки профиля\n\n"
                f"💰 Найти займы с этими настройками?"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ДА, НАЙТИ ЗАЙМЫ!",
                                      callback_data=f"quick_search_{profile.country}_{profile.age}")],
                [InlineKeyboardButton(text="⚙️ Изменить настройки", callback_data="change_profile_settings")]
            ])

        else:
            # НОВЫЙ ПОЛЬЗОВАТЕЛЬ
            welcome_text = (
                "🚀 <b>Найдем выгодный займ за 30 секунд!</b>\n\n"
                "💰 Займы до 500,000₸ / 50,000₽ на карту за 5 минут\n"
                "✅ Одобряем даже с плохой КИ\n"
                "🆓 0% для новых клиентов\n"
                "⚡ Без справок и поручителей\n\n"
                "Сначала настроим ваш профиль:"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

            await state.set_state(LoanFlow.choosing_country)

        # ИСПРАВЛЯЕМ: Используем простую отправку сообщения
        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

        # Устанавливаем постоянную клавиатуру отдельно
        settings_keyboard = self.get_settings_keyboard()
        await message.answer("⬇️ Используйте кнопки ниже:", reply_markup=settings_keyboard)

    async def quick_search_callback(self, callback: CallbackQuery, state: FSMContext):
        """Быстрый поиск для возвращающихся пользователей"""
        # Парсим данные из callback
        parts = callback.data.split("_")
        country = parts[2]
        age = int(parts[3])

        # Устанавливаем базовые данные
        await state.update_data(country=country, age=age)

        # Увеличиваем счетчик сессий
        await self.profile_manager.increment_sessions(callback.from_user.id)

        # Переходим сразу к выбору суммы
        text = "💰 <b>Выберите СУММУ займа</b>"

        if country == "kazakhstan":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="50,000₸ и менее", callback_data="amount_50000"),
                    InlineKeyboardButton(text="100,000₸", callback_data="amount_100000")
                ],
                [
                    InlineKeyboardButton(text="150,000₸", callback_data="amount_150000"),
                    InlineKeyboardButton(text="250,000₸", callback_data="amount_250000")
                ],
                [
                    InlineKeyboardButton(text="500,000₸ и более", callback_data="amount_500000")
                ]
            ])
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="5,000₽ и менее", callback_data="amount_5000"),
                    InlineKeyboardButton(text="10,000₽", callback_data="amount_10000")
                ],
                [
                    InlineKeyboardButton(text="15,000₽", callback_data="amount_15000"),
                    InlineKeyboardButton(text="25,000₽", callback_data="amount_25000")
                ],
                [
                    InlineKeyboardButton(text="50,000₽ и более", callback_data="amount_50000")
                ]
            ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_amount)
        await callback.answer("⚡ Ускоряем поиск для вас!")

    async def change_profile_settings_callback(self, callback: CallbackQuery, state: FSMContext):
        """Изменение настроек профиля"""
        user_data = await state.get_data()
        profile = user_data.get('user_profile', {})

        settings_text = (
            "⚙️ <b>Настройки вашего профиля</b>\n\n"
            f"👤 Имя: {profile.get('first_name', 'Не указано')}\n"
            f"🌍 Страна: {'🇷🇺 Россия' if profile.get('country') == 'russia' else '🇰🇿 Казахстан' if profile.get('country') == 'kazakhstan' else 'Не выбрана'}\n"
            f"🎂 Возраст: {profile.get('age', 'Не указан')} лет\n\n"
            "Что хотите изменить?"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Изменить страну", callback_data="edit_country")],
            [InlineKeyboardButton(text="🎂 Изменить возраст", callback_data="edit_age")],
            [InlineKeyboardButton(text="🔙 Вернуться назад", callback_data="back_to_main")]
        ])

        await self.edit_message_with_keyboard(callback.message, settings_text, keyboard)
        await callback.answer()

    async def edit_country_callback(self, callback: CallbackQuery, state: FSMContext):
        """Редактирование страны в профиле"""
        text = "🌍 <b>Выберите вашу страну:</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
            [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")],
            [InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="change_profile_settings")]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await callback.answer()

    async def edit_age_callback(self, callback: CallbackQuery, state: FSMContext):
        """Редактирование возраста в профиле"""
        text = "🎂 <b>Выберите ваш возраст:</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="18-25 лет", callback_data="age_22")],
            [InlineKeyboardButton(text="26-35 лет", callback_data="age_30")],
            [InlineKeyboardButton(text="36-50 лет", callback_data="age_43")],
            [InlineKeyboardButton(text="51+ лет", callback_data="age_60")],
            [InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="change_profile_settings")]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await callback.answer()

    async def back_to_main_callback(self, callback: CallbackQuery, state: FSMContext):
        """Возврат к главному меню"""
        profile = await self.profile_manager.get_or_create_profile(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name
        )

        await state.update_data(user_profile=profile.__dict__)

        if profile.country and profile.age:
            country_name = "🇷🇺 России" if profile.country == "russia" else "🇰🇿 Казахстане"

            welcome_text = (
                f"👋 <b>С возвращением, {profile.first_name}!</b>\n\n"
                f"📍 Ваши настройки:\n"
                f"🌍 Страна: {country_name}\n"
                f"👤 Возраст: {profile.age} лет\n\n"
                f"💰 Найти займы с этими настройками?"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ДА, НАЙТИ ЗАЙМЫ!",
                                      callback_data=f"quick_search_{profile.country}_{profile.age}")],
                [InlineKeyboardButton(text="⚙️ Изменить настройки", callback_data="change_profile_settings")]
            ])
        else:
            welcome_text = (
                "🚀 <b>Найдем выгодный займ за 30 секунд!</b>\n\n"
                "💰 Займы до 500,000₸ / 50,000₽ на карту за 5 минут\n"
                "✅ Одобряем даже с плохой КИ\n"
                "🆓 0% для новых клиентов\n"
                "⚡ Без справок и поручителей\n\n"
                "Сначала настроим ваш профиль:"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

        await self.edit_message_with_keyboard(callback.message, welcome_text, keyboard)
        await callback.answer()

    async def country_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор страны"""
        country = callback.data.split("_")[1]
        await state.update_data(country=country)

        await self.profile_manager.update_profile_preferences(
            callback.from_user.id,
            country=country
        )

        # Проверяем, откуда пришел пользователь (редактирование профиля или обычный флоу)
        user_data = await state.get_data()
        if user_data.get('user_profile'):
            # Это редактирование профиля - показываем уведомление и возвращаем к настройкам
            success_text = (
                f"✅ <b>Страна обновлена!</b>\n\n"
                f"🌍 Новая страна: {'🇷🇺 Россия' if country == 'russia' else '🇰🇿 Казахстан'}\n\n"
                "Настройки сохранены в вашем профиле."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ К настройкам профиля", callback_data="change_profile_settings")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
            ])

            await self.edit_message_with_keyboard(callback.message, success_text, keyboard)
            await callback.answer("🌍 Страна обновлена!")
            return

        # Обычный флоу - продолжаем к выбору возраста
        country_name = "🇷🇺 России" if country == "russia" else "🇰🇿 Казахстане"

        text = f"Отлично! Подбираем займы в {country_name}\n\n👤 Укажите ваш возраст:"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="18-25 лет", callback_data="age_22")],
            [InlineKeyboardButton(text="26-35 лет", callback_data="age_30")],
            [InlineKeyboardButton(text="36-50 лет", callback_data="age_43")],
            [InlineKeyboardButton(text="51+ лет", callback_data="age_60")]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_age)
        await callback.answer()

    async def age_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор возраста"""
        age = int(callback.data.split("_")[1])
        await state.update_data(age=age)

        await self.profile_manager.update_profile_preferences(
            callback.from_user.id,
            age=age
        )

        # Проверяем, откуда пришел пользователь (редактирование профиля или обычный флоу)
        user_data = await state.get_data()
        if user_data.get('user_profile') and not user_data.get('session_id'):
            # Это редактирование профиля - показываем уведомление и возвращаем к настройкам
            success_text = (
                f"✅ <b>Возраст обновлен!</b>\n\n"
                f"🎂 Новый возраст: {age} лет\n\n"
                "Настройки сохранены в вашем профиле."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ К настройкам профиля", callback_data="change_profile_settings")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
            ])

            await self.edit_message_with_keyboard(callback.message, success_text, keyboard)
            await callback.answer("🎂 Возраст обновлен!")
            return

        # Обычный флоу - создаем сессию в аналитике и продолжаем
        session_id = await self.analytics.track_session_start(
            callback.from_user.id,
            age,
            user_data['country']
        )
        await state.update_data(session_id=session_id)

        text = "💰 <b>Выберите СУММУ займа</b>"

        # Определяем валюту и суммы в зависимости от страны
        country = user_data.get('country')
        if country == "kazakhstan":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="50,000₸ и менее", callback_data="amount_50000"),
                    InlineKeyboardButton(text="100,000₸", callback_data="amount_100000")
                ],
                [
                    InlineKeyboardButton(text="150,000₸", callback_data="amount_150000"),
                    InlineKeyboardButton(text="250,000₸", callback_data="amount_250000")
                ],
                [
                    InlineKeyboardButton(text="500,000₸ и более", callback_data="amount_500000")
                ]
            ])
        else:  # russia
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="5,000₽ и менее", callback_data="amount_5000"),
                    InlineKeyboardButton(text="10,000₽", callback_data="amount_10000")
                ],
                [
                    InlineKeyboardButton(text="15,000₽", callback_data="amount_15000"),
                    InlineKeyboardButton(text="25,000₽", callback_data="amount_25000")
                ],
                [
                    InlineKeyboardButton(text="50,000₽ и более", callback_data="amount_50000")
                ]
            ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_amount)
        await callback.answer()

    async def amount_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор суммы"""
        amount = int(callback.data.split("_")[1])
        await state.update_data(amount=amount)

        # Сохраняем параметры в сессию
        user_data = await state.get_data()
        session_id = user_data.get('session_id')
        if session_id:
            await self.analytics.track_session_parameters(session_id, amount)

        text = "📅 <b>Выбери СРОК займа</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="7 дней", callback_data="term_7"),
                InlineKeyboardButton(text="14 дней", callback_data="term_14")
            ],
            [
                InlineKeyboardButton(text="21 день", callback_data="term_21"),
                InlineKeyboardButton(text="30 дней", callback_data="term_30")
            ]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_term)
        await callback.answer()

    async def term_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор срока"""
        term = int(callback.data.split("_")[1])
        await state.update_data(term=term)

        text = (
            "💳 <b>Как хотите получить деньги?</b>\n\n"
            "Выберите удобный способ получения займа:"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 На банковскую карту", callback_data="payment_card")],
            [InlineKeyboardButton(text="📱 QIWI кошелек", callback_data="payment_qiwi")],
            [InlineKeyboardButton(text="🟡 Яндекс.Деньги", callback_data="payment_yandex")],
            [InlineKeyboardButton(text="🏦 На счет в банке", callback_data="payment_bank")],
            [InlineKeyboardButton(text="💵 Наличные", callback_data="payment_cash")],
            [InlineKeyboardButton(text="📞 Через систему контакт", callback_data="payment_contact")]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_payment)
        await callback.answer()

    async def payment_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор способа получения"""
        payment_method = callback.data.split("_")[1]
        await state.update_data(payment_method=payment_method)

        text = "💳 <b>Выбери ПРОЦЕНТ займа</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Только 0%", callback_data="zero_true")],
            [InlineKeyboardButton(text="💰 Любые варианты", callback_data="zero_false")]
        ])

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_zero_percent)
        await callback.answer()

    async def zero_percent_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор 0% или любые варианты с удалением сообщения о проценте"""
        zero_only = callback.data.split("_")[1] == "true"
        await state.update_data(zero_percent_only=zero_only)

        # Получаем критерии пользователя
        user_data = await state.get_data()

        # Ищем подходящие офферы
        offers = self.offer_manager.get_filtered_offers(user_data)

        if not offers:
            # Если нет подходящих офферов
            text = (
                "😔 К сожалению, по вашим критериям нет доступных предложений.\n\n"
                "Попробуйте изменить параметры поиска:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Изменить параметры", callback_data="change_params")]
            ])

            await self.edit_message_with_keyboard(callback.message, text, keyboard)
            await callback.answer()
            return

        # ИСПРАВЛЕНИЕ: Удаляем сообщение "Выбери ПРОЦЕНТ займа" перед показом офферов
        try:
            await callback.message.delete()
            logger.info(f"Удалено сообщение с выбором процента: {callback.message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с выбором процента: {e}")

        # Сохраняем найденные офферы и начинаем с первого
        await state.update_data(
            found_offers=offers,
            current_offer_index=0
        )

        # Трекинг показанного оффера
        session_id = user_data.get('session_id')
        if session_id:
            await self.analytics.track_offers_shown(session_id, [offers[0]['id']])

        # Показываем первый оффер (новое сообщение)
        await self.show_single_offer(callback.message, state, offers[0], 0, len(offers))
        await state.set_state(LoanFlow.viewing_offers)
        await callback.answer()

    async def show_single_offer(self, message: Message, state: FSMContext, offer: Dict, index: int, total: int):
        """Показ одного оффера с возможностью листать"""

        # Формируем текст оффера
        name = offer.get('name', 'Без названия')
        description = offer.get('description', 'Быстрое получение займа')

        # Получаем данные пользователя для показа условий
        user_data = await state.get_data()
        amount_formatted = f"{user_data.get('amount', 0):,}".replace(',', ' ')
        country = user_data.get('country', 'russia')
        currency = "₸" if country == "kazakhstan" else "₽"

        offer_text = (
            f"🏦 <b>{name}</b>\n\n"
            f"{description}\n\n"
            f"💰 <b>Сумма:</b> {amount_formatted}{currency}\n"
            f"📅 <b>Срок:</b> {user_data.get('term', 0)} дней\n"
            f"🆓 <b>Процент:</b> {'0% для новых клиентов' if offer.get('zero_percent') else 'Выгодные условия'}\n\n"
            f"📊 <b>Вариант {index + 1} из {total}</b>"
        )

        # Формируем кнопки
        buttons = []

        # Главная кнопка - получить займ
        buttons.append([
            InlineKeyboardButton(
                text="💰 ПОЛУЧИТЬ ЗАЙМ",
                callback_data=f"get_loan_{offer['id']}"
            )
        ])

        # Кнопки навигации
        nav_buttons = []

        # Кнопка "Назад" если не первый
        if index > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_offer")
            )

        # Кнопка "Далее" если не последний
        if index < total - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️ Еще варианты", callback_data="next_offer")
            )

        if nav_buttons:
            buttons.append(nav_buttons)

        # Кнопка изменения параметров
        buttons.append([
            InlineKeyboardButton(text="🔄 Изменить условия", callback_data="change_params")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Удаляем предыдущее сообщение с оффером ВСЕГДА, чтобы убрать картинки
        user_data = await state.get_data()
        last_message_id = user_data.get('last_offer_message_id')
        if last_message_id:
            try:
                await message.bot.delete_message(message.chat.id, last_message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить предыдущее сообщение: {e}")

        # Проверяем наличие логотипа и отправляем соответствующим образом
        logo_path = offer.get('logo')
        if logo_path and os.path.exists(f"data/images/logos/{logo_path}"):
            try:
                # Отправляем с фото
                photo = FSInputFile(f"data/images/logos/{logo_path}")
                sent_message = await message.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=offer_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                # Сохраняем ID сообщения для следующего удаления
                await state.update_data(last_offer_message_id=sent_message.message_id)

            except Exception as e:
                logger.error(f"Ошибка отправки фото {logo_path}: {e}")
                # Отправляем без картинки при ошибке
                sent_message = await message.answer(offer_text, reply_markup=keyboard, parse_mode="HTML")
                await state.update_data(last_offer_message_id=sent_message.message_id)
        else:
            # Отправляем без картинки
            sent_message = await message.answer(offer_text, reply_markup=keyboard, parse_mode="HTML")
            await state.update_data(last_offer_message_id=sent_message.message_id)

    async def next_offer_callback(self, callback: CallbackQuery, state: FSMContext):
        """Показать следующий оффер"""
        user_data = await state.get_data()
        offers = user_data.get('found_offers', [])
        current_index = user_data.get('current_offer_index', 0)

        # Переходим к следующему офферу
        new_index = min(current_index + 1, len(offers) - 1)
        await state.update_data(current_offer_index=new_index)

        # Трекинг просмотра нового оффера
        session_id = user_data.get('session_id')
        if session_id:
            await self.analytics.track_offers_shown(session_id, [offers[new_index]['id']])

        await self.show_single_offer(callback.message, state, offers[new_index], new_index, len(offers))
        await callback.answer()

    async def prev_offer_callback(self, callback: CallbackQuery, state: FSMContext):
        """Показать предыдущий оффер"""
        user_data = await state.get_data()
        offers = user_data.get('found_offers', [])
        current_index = user_data.get('current_offer_index', 0)

        # Переходим к предыдущему офферу
        new_index = max(current_index - 1, 0)
        await state.update_data(current_offer_index=new_index)

        await self.show_single_offer(callback.message, state, offers[new_index], new_index, len(offers))
        await callback.answer()

    async def back_to_offers_callback(self, callback: CallbackQuery, state: FSMContext):
        """Возврат к просмотру офферов"""
        user_data = await state.get_data()
        offers = user_data.get('found_offers', [])
        current_index = user_data.get('current_offer_index', 0)

        if not offers:
            await callback.answer("❌ Нет офферов для показа", show_alert=True)
            return

        await self.show_single_offer(callback.message, state, offers[current_index], current_index, len(offers))
        await callback.answer()

    async def get_loan_callback(self, callback: CallbackQuery, state: FSMContext):
        """ГЛАВНАЯ МЕТРИКА: Прямой переход по партнерской ссылке БЕЗ промежуточных сообщений"""
        offer_id = callback.data.split("_", 2)[2]
        user_data = await state.get_data()
        country = user_data.get('country', 'russia')

        # Находим оффер
        offers = user_data.get('found_offers', [])
        selected_offer = None

        for offer in offers:
            if offer['id'] == offer_id:
                selected_offer = offer
                break

        if not selected_offer:
            await callback.answer("❌ Оффер не найден", show_alert=True)
            return

        # Получаем ссылку для страны
        geography = selected_offer.get('geography', {})
        link_key = f"{country}_link"
        partner_link = geography.get(link_key)

        if not partner_link:
            await callback.answer("❌ Ссылка недоступна", show_alert=True)
            return

        # Персонализируем ссылку
        user_id = callback.from_user.id
        personalized_link = partner_link.replace('{user_id}', str(user_id))

        # Трекинг клика по ссылке - ГЛАВНАЯ МЕТРИКА!
        session_id = user_data.get('session_id')
        await self.analytics.track_link_click(user_id, session_id, offer_id, country)

        # Увеличиваем счетчик кликов в профиле
        await self.profile_manager.increment_clicks(callback.from_user.id)

        # ПРЯМОЙ РЕДИРЕКТ - пользователь сразу попадает на сайт МФО
        try:
            # Создаем кнопку с прямой ссылкой - МАКСИМАЛЬНАЯ КОНВЕРСИЯ
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 ПОЛУЧИТЬ ДЕНЬГИ СЕЙЧАС!", url=personalized_link)],
                [InlineKeyboardButton(text="🔙 Посмотреть другие варианты", callback_data="back_to_offers")],
                [InlineKeyboardButton(text="🚀 Поделиться ботом", callback_data="share_bot")]
            ])

            # Простое сообщение об успешном выборе - БЕЗ лишних деталей
            user_data = await state.get_data()
            country = user_data.get('country', 'russia')
            currency = "₸" if country == "kazakhstan" else "₽"

            success_text = (
                f"✅ <b>Отличный выбор!</b>\n\n"
                f"🏦 {selected_offer.get('name')}\n"
                f"💰 {user_data.get('amount', 0):,}{currency} на {user_data.get('term', 0)} дней\n\n"
                f"👆 <b>Нажмите кнопку для оформления займа</b>"
            )

            await self.edit_message_with_keyboard(callback.message, success_text, keyboard)

            # Логируем клик
            logger.info(f"🎯 КЛИК ПО ССЫЛКЕ: user_id={user_id}, offer_id={offer_id}, country={country}")

            await callback.answer("🚀 Переходим к оформлению займа!")

        except Exception as e:
            logger.error(f"Ошибка создания ссылки: {e}")
            await callback.answer("❌ Ошибка перехода", show_alert=True)

    async def change_params_callback(self, callback: CallbackQuery, state: FSMContext):
        """ИСПРАВЛЕННАЯ ЛОГИКА: Изменение условий займа с полной очисткой всех сообщений с офферами"""
        user_data = await state.get_data()

        # ИСПРАВЛЕНИЕ БАГА: Удаляем предыдущее сообщение с логотипом оффера
        last_message_id = user_data.get('last_offer_message_id')
        if last_message_id:
            try:
                await callback.message.bot.delete_message(callback.message.chat.id, last_message_id)
                logger.info(f"Удалено предыдущее сообщение с офером: {last_message_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить предыдущее сообщение с офером: {e}")

        # ДОПОЛНИТЕЛЬНОЕ ИСПРАВЛЕНИЕ: Удаляем текущее сообщение с оффером
        try:
            await callback.message.delete()
            logger.info(f"Удалено текущее сообщение с офером: {callback.message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить текущее сообщение с офером: {e}")

        # Очищаем ID последнего сообщения из состояния
        await state.update_data(last_offer_message_id=None)

        # Получаем сохраненный профиль пользователя
        profile = await self.profile_manager.get_or_create_profile(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name
        )

        # Если у пользователя есть сохраненные страна и возраст - используем их
        if profile.country and profile.age:
            await state.update_data(
                country=profile.country,
                age=profile.age
            )

            # Создаем новую сессию
            session_id = await self.analytics.track_session_start(
                callback.from_user.id,
                profile.age,
                profile.country
            )
            await state.update_data(session_id=session_id)

            # Сразу переходим к выбору суммы
            text = "🔄 <b>Изменяем условия займа</b>\n\n💰 <b>Выберите СУММУ займа</b>"

            if profile.country == "kazakhstan":
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="50,000₸ и менее", callback_data="amount_50000"),
                        InlineKeyboardButton(text="100,000₸", callback_data="amount_100000")
                    ],
                    [
                        InlineKeyboardButton(text="150,000₸", callback_data="amount_150000"),
                        InlineKeyboardButton(text="250,000₸", callback_data="amount_250000")
                    ],
                    [
                        InlineKeyboardButton(text="500,000₸ и более", callback_data="amount_500000")
                    ]
                ])
            else:  # russia
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="5,000₽ и менее", callback_data="amount_5000"),
                        InlineKeyboardButton(text="10,000₽", callback_data="amount_10000")
                    ],
                    [
                        InlineKeyboardButton(text="15,000₽", callback_data="amount_15000"),
                        InlineKeyboardButton(text="25,000₽", callback_data="amount_25000")
                    ],
                    [
                        InlineKeyboardButton(text="50,000₽ и более", callback_data="amount_50000")
                    ]
                ])

            await state.set_state(LoanFlow.choosing_amount)

        else:
            # Если нет сохраненных данных - стандартный флоу
            await state.clear()
            welcome_text = (
                "🔄 <b>Изменяем параметры поиска</b>\n\n"
                "💰 Деньги на карту за 5 минут\n"
                "✅ Одобряем 9 из 10 заявок\n"
                "🆓 0% для новых клиентов"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

            await state.set_state(LoanFlow.choosing_country)
            text = welcome_text

        # ИСПРАВЛЕНИЕ: Отправляем НОВОЕ сообщение (так как удалили предыдущие)
        new_message = await callback.message.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await callback.answer("🔄 Изменяем условия поиска!")

    async def cmd_restart(self, message: Message, state: FSMContext):
        """Команда для полного рестарта бота"""
        await state.clear()

        restart_text = (
            "🔄 <b>Бот перезапущен!</b>\n\n"
            "Все данные сессии очищены.\n"
            "Ваш профиль остался сохранен.\n\n"
            "Начнем заново?"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 НАЧАТЬ ПОИСК ЗАЙМОВ", callback_data="back_to_main")]
        ])

        await message.answer(restart_text, reply_markup=keyboard, parse_mode="HTML")

    async def cmd_clear_profile(self, message: Message, state: FSMContext):
        """Команда для очистки профиля пользователя"""
        try:
            await self.profile_manager.clear_profile(message.from_user.id)
            await state.clear()

            clear_text = (
                "🗑️ <b>Профиль очищен!</b>\n\n"
                "✅ Все ваши данные удалены\n"
                "✅ Настройки сброшены\n"
                "✅ Статистика сохранена\n\n"
                "Настроим профиль заново?"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

            await message.answer(clear_text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(LoanFlow.choosing_country)

        except Exception as e:
            logger.error(f"Ошибка очистки профиля: {e}")
            await message.answer("❌ Ошибка очистки профиля. Попробуйте позже.")

    async def cmd_my_stats(self, message: Message, state: FSMContext):
        """Команда заглушка - статистика отключена для клиентов"""
        await message.answer(
            "📊 <b>Статистика временно недоступна</b>\n\n"
            "Используйте другие команды для управления ботом:",
            parse_mode="HTML"
        )

    async def cmd_help(self, message: Message, state: FSMContext):
        """Команда помощи с доступными командами"""
        help_text = (
            "ℹ️ <b>Доступные команды:</b>\n\n"
            "🚀 /start - Начать работу с ботом\n"
            "🔄 /restart - Перезапустить бот\n"
            "🗑️ /clear_profile - Очистить профиль\n"
            "ℹ️ /help - Эта справка\n\n"
            "📱 <b>Кнопки:</b>\n"
            "🔥 Популярные предложения - Быстрый поиск\n"
            "⚙️ Настройки профиля - Управление данными\n\n"
            "💡 <b>Совет:</b> Сохраните настройки профиля для быстрого поиска займов!"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 НАЙТИ ЗАЙМЫ", callback_data="back_to_main")]
        ])

        await message.answer(help_text, reply_markup=keyboard, parse_mode="HTML")

    async def confirm_clear_profile_callback(self, callback: CallbackQuery, state: FSMContext):
        """Подтверждение очистки профиля через inline кнопку"""
        confirm_text = (
            "⚠️ <b>Подтверждение очистки</b>\n\n"
            "Вы действительно хотите удалить:\n"
            "• Сохраненную страну\n"
            "• Возраст\n"
            "• Все настройки профиля\n\n"
            "❗ Статистика поиска сохранится"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="execute_clear_profile"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")
            ]
        ])

        await callback.message.edit_text(confirm_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def execute_clear_profile_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выполнение очистки профиля после подтверждения"""
        try:
            await self.profile_manager.clear_profile(callback.from_user.id)
            await state.clear()

            success_text = (
                "✅ <b>Профиль успешно очищен!</b>\n\n"
                "🔄 Все настройки сброшены\n"
                "📊 Статистика сохранена\n\n"
                "Настроим профиль заново?"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

            await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(LoanFlow.choosing_country)
            await callback.answer("✅ Профиль очищен!")

        except Exception as e:
            logger.error(f"Ошибка очистки профиля: {e}")
            await callback.answer("❌ Ошибка очистки профиля", show_alert=True)

    async def share_bot_callback(self, callback: CallbackQuery, state: FSMContext):
        """Callback для кнопки поделиться ботом"""

        bot_username = (await self.bot.get_me()).username
        share_url = f"https://t.me/{bot_username}"

        share_text = (
            "🚀 <b>Поделитесь ботом с друзьями!</b>\n\n"
            "💰 Этот бот поможет найти выгодные займы:\n"
            "✅ До 500,000₸ / 50,000₽ на карту\n"
            "⚡ Одобрение за 5 минут\n"
            "🆓 0% для новых клиентов\n"
            "🛡️ Работает даже с плохой КИ\n\n"
            f"🔗 <b>Ссылка на бота:</b>\n<code>{share_url}</code>\n\n"
            "👆 Нажмите на ссылку чтобы скопировать"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Поделиться в Telegram",
                                  url=f"https://t.me/share/url?url={share_url}&text=💰 Найди выгодный займ за 30 секунд! До 500К на карту за 5 минут.")],
            [InlineKeyboardButton(text="🔙 Назад к займу", callback_data="back_to_offers")]
        ])

        await callback.message.edit_text(share_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def start_polling(self):
        """Запуск бота"""
        # Настраиваем меню команд при запуске
        await self.setup_bot_commands()

        logger.info("🚀 Бот запущен!")
        await self.dp.start_polling(self.bot)


# Точка входа
async def main():
    """Главная функция запуска"""
    bot = LoanBot(BOT_TOKEN)
    await bot.start_polling()


if __name__ == "__main__":
    asyncio.run(main())