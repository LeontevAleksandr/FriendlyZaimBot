import logging
from typing import Dict
from aiogram import Bot, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from main_bot.states.loan_flow import LoanFlow
from main_bot.keyboards.inline_keyboards import get_popular_offers_keyboard
from main_bot.utils.analytics import AnalyticsTracker
from main_bot.utils.offer_display import OfferDisplay
from shared.offer_manager import OfferManager
from user_profile_manager import UserProfileManager

logger = logging.getLogger(__name__)


class CallbackHandlers:
    """Обработчики всех коллбеков для максимальной конверсии"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.offer_manager = OfferManager()
        self.analytics = AnalyticsTracker()
        self.profile_manager = UserProfileManager()
        self.offer_display = OfferDisplay()

    def register_handlers(self, dp):
        """Регистрация обработчиков коллбеков"""
        # Популярные предложения
        dp.callback_query.register(self.popular_offer_callback, F.data.startswith("popular_"))
        dp.callback_query.register(self.back_to_popular_callback, F.data == "back_to_popular")

        # Быстрый поиск
        dp.callback_query.register(self.quick_search_callback, F.data.startswith("quick_search_"))

        # FSM флоу выбора параметров
        dp.callback_query.register(self.country_callback, F.data.startswith("country_"))
        dp.callback_query.register(self.age_callback, F.data.startswith("age_"))
        dp.callback_query.register(self.amount_callback, F.data.startswith("amount_"))
        dp.callback_query.register(self.term_callback, F.data.startswith("term_"))
        dp.callback_query.register(self.payment_callback, F.data.startswith("payment_"))
        dp.callback_query.register(self.zero_percent_callback, F.data.startswith("zero_"))

        # Просмотр офферов
        dp.callback_query.register(self.get_loan_callback, F.data.startswith("get_loan_"))
        dp.callback_query.register(self.next_offer_callback, F.data == "next_offer")
        dp.callback_query.register(self.prev_offer_callback, F.data == "prev_offer")
        dp.callback_query.register(self.back_to_offers_callback, F.data == "back_to_offers")
        dp.callback_query.register(self.change_params_callback, F.data == "change_params")

        # Дополнительные коллбеки
        dp.callback_query.register(self.share_bot_from_offer_callback, F.data == "share_bot")

        # Настройки профиля
        dp.callback_query.register(self.change_profile_settings_callback, F.data == "change_profile_settings")
        dp.callback_query.register(self.edit_country_callback, F.data == "edit_country")
        dp.callback_query.register(self.edit_age_callback, F.data == "edit_age")
        dp.callback_query.register(self.back_to_main_callback, F.data == "back_to_main")

    async def edit_message_with_keyboard(self, message, text: str,
                                         inline_keyboard: InlineKeyboardMarkup = None, parse_mode: str = "HTML"):
        """Безопасное редактирование сообщения с inline клавиатурой"""
        try:
            if message.photo:
                await message.edit_caption(caption=text, reply_markup=inline_keyboard, parse_mode=parse_mode)
            else:
                await message.edit_text(text=text, reply_markup=inline_keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            await message.answer(text, reply_markup=inline_keyboard, parse_mode=parse_mode)

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

        keyboard = get_popular_offers_keyboard()
        await callback.message.edit_text(popular_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

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
        search_criteria = self._get_popular_offer_criteria(offer_type, profile)
        search_text = self._get_popular_offer_text(offer_type)

        if not search_criteria:
            await callback.answer("Неизвестный тип предложения", show_alert=True)
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

        await callback.answer(f"Найдено {len(offers)} популярных предложений!")

    async def quick_search_callback(self, callback: CallbackQuery, state: FSMContext):
        """Быстрый поиск для возвращающихся пользователей"""
        parts = callback.data.split("_")
        country = parts[2]
        age = int(parts[3])

        await state.update_data(country=country, age=age)
        await self.profile_manager.increment_sessions(callback.from_user.id)

        # Переходим сразу к выбору суммы
        text = "💰 <b>Выберите СУММУ займа</b>"
        keyboard = self._get_amount_keyboard(country)

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_amount)
        await callback.answer("Ускоряем поиск для вас!")

    async def country_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор страны"""
        country = callback.data.split("_")[1]
        await state.update_data(country=country)

        await self.profile_manager.update_profile_preferences(
            callback.from_user.id,
            country=country
        )

        # Проверяем, откуда пришел пользователь
        user_data = await state.get_data()
        if user_data.get('user_profile'):
            # Это редактирование профиля
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
            await callback.answer("Страна обновлена!")
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

        # Проверяем, откуда пришел пользователь
        user_data = await state.get_data()
        if user_data.get('user_profile') and not user_data.get('session_id'):
            # Это редактирование профиля
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
            await callback.answer("Возраст обновлен!")
            return

        # Обычный флоу - создаем сессию и продолжаем
        session_id = await self.analytics.track_session_start(
            callback.from_user.id,
            age,
            user_data['country']
        )
        await state.update_data(session_id=session_id)

        text = "💰 <b>Выберите СУММУ займа</b>"
        keyboard = self._get_amount_keyboard(user_data.get('country'))

        await self.edit_message_with_keyboard(callback.message, text, keyboard)
        await state.set_state(LoanFlow.choosing_amount)
        await callback.answer()

    async def amount_callback(self, callback: CallbackQuery, state: FSMContext):
        """Выбор суммы займа"""
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
        """Выбор срока займа"""
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
        """Выбор 0% или любые варианты с показом результатов"""
        zero_only = callback.data.split("_")[1] == "true"
        await state.update_data(zero_percent_only=zero_only)

        # Получаем критерии пользователя
        user_data = await state.get_data()

        # Ищем подходящие офферы
        offers = self.offer_manager.get_filtered_offers(user_data)

        if not offers:
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

        # Удаляем сообщение "Выбери ПРОЦЕНТ займа" перед показом офферов
        try:
            await callback.message.delete()
            logger.info(f"Удалено сообщение с выбором процента: {callback.message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с выбором процента: {e}")

        # Сохраняем найденные офферы
        await state.update_data(
            found_offers=offers,
            current_offer_index=0
        )

        # Трекинг показанных офферов
        session_id = user_data.get('session_id')
        if session_id:
            await self.analytics.track_offers_shown(session_id, [offers[0]['id']])

        # Показываем первый оффер
        await self.show_single_offer(callback.message, state, offers[0], 0, len(offers))
        await state.set_state(LoanFlow.viewing_offers)
        await callback.answer()

    async def show_single_offer(self, message, state: FSMContext, offer: Dict, index: int, total: int):
        """Показ одного оффера с логотипом"""
        await self.offer_display.show_single_offer(message, state, offer, index, total)

    async def get_loan_callback(self, callback: CallbackQuery, state: FSMContext):
        """ГЛАВНАЯ МЕТРИКА: Прямой переход по партнерской ссылке"""
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
            await callback.answer("Оффер не найден", show_alert=True)
            return

        # Получаем ссылку для страны
        geography = selected_offer.get('geography', {})
        link_key = f"{country}_link"
        partner_link = geography.get(link_key)

        if not partner_link:
            await callback.answer("Ссылка недоступна", show_alert=True)
            return

        # Персонализируем ссылку
        user_id = callback.from_user.id
        personalized_link = partner_link.replace('{user_id}', str(user_id))

        # Трекинг клика по ссылке - ГЛАВНАЯ МЕТРИКА!
        session_id = user_data.get('session_id')
        await self.analytics.track_link_click(user_id, session_id, offer_id, country)

        # Увеличиваем счетчик кликов в профиле
        await self.profile_manager.increment_clicks(callback.from_user.id)

        # Создаем кнопку с прямой ссылкой
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 ПОЛУЧИТЬ ДЕНЬГИ СЕЙЧАС!", url=personalized_link)],
                [InlineKeyboardButton(text="🔙 Посмотреть другие варианты", callback_data="back_to_offers")],
                [InlineKeyboardButton(text="🚀 Поделиться ботом", callback_data="share_bot")]
            ])

            # Простое сообщение об успешном выборе
            currency = "₸" if country == "kazakhstan" else "₽"

            success_text = (
                f"✅ <b>Отличный выбор!</b>\n\n"
                f"🏦 {selected_offer.get('name')}\n"
                f"💰 {user_data.get('amount', 0):,}{currency} на {user_data.get('term', 0)} дней\n\n"
                f"👆 <b>Нажмите кнопку для оформления займа</b>"
            )

            await self.edit_message_with_keyboard(callback.message, success_text, keyboard)

            # Логируем клик
            logger.info(f"КЛИК ПО ССЫЛКЕ: user_id={user_id}, offer_id={offer_id}, country={country}")

            await callback.answer("Переходим к оформлению займа!")

        except Exception as e:
            logger.error(f"Ошибка создания ссылки: {e}")
            await callback.answer("Ошибка перехода", show_alert=True)

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
            await callback.answer("Нет офферов для показа", show_alert=True)
            return

        await self.show_single_offer(callback.message, state, offers[current_index], current_index, len(offers))
        await callback.answer()

    async def change_params_callback(self, callback: CallbackQuery, state: FSMContext):
        """Изменение условий займа с полной очисткой всех сообщений с офферами"""
        user_data = await state.get_data()

        # Удаляем предыдущее сообщение с логотипом оффера
        last_message_id = user_data.get('last_offer_message_id')
        if last_message_id:
            try:
                await callback.message.bot.delete_message(callback.message.chat.id, last_message_id)
                logger.info(f"Удалено предыдущее сообщение с офером: {last_message_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить предыдущее сообщение с офером: {e}")

        # Удаляем текущее сообщение с оффером
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
            keyboard = self._get_amount_keyboard(profile.country)
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

        # Отправляем новое сообщение (так как удалили предыдущие)
        new_message = await callback.message.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await callback.answer("Изменяем условия поиска!")

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

    # Вспомогательные методы
    def _get_popular_offer_criteria(self, offer_type: str, profile) -> dict:
        """Получение критериев для популярных предложений"""
        base_country = profile.country or 'russia'
        base_age = profile.age or 30

        criteria_map = {
            "zero_percent": {
                'country': base_country,
                'age': base_age,
                'amount': 15000 if base_country == 'russia' else 150000,
                'zero_percent_only': True,
                'term': 14,
                'payment_method': 'card'
            },
            "instant": {
                'country': base_country,
                'age': base_age,
                'amount': 10000 if base_country == 'russia' else 100000,
                'zero_percent_only': False,
                'term': 7,
                'payment_method': 'card'
            },
            "cash": {
                'country': base_country,
                'age': base_age,
                'amount': 20000 if base_country == 'russia' else 200000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'cash'
            },
            "big_amount": {
                'country': base_country,
                'age': base_age,
                'amount': 50000 if base_country == 'russia' else 500000,
                'zero_percent_only': False,
                'term': 30,
                'payment_method': 'card'
            },
            "no_docs": {
                'country': base_country,
                'age': base_age,
                'amount': 15000 if base_country == 'russia' else 150000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            },
            "bad_credit": {
                'country': base_country,
                'age': base_age,
                'amount': 10000 if base_country == 'russia' else 100000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            },
            "russia": {
                'country': 'russia',
                'age': base_age,
                'amount': 25000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            },
            "kazakhstan": {
                'country': 'kazakhstan',
                'age': base_age,
                'amount': 250000,
                'zero_percent_only': False,
                'term': 14,
                'payment_method': 'card'
            }
        }

        return criteria_map.get(offer_type)

    def _get_popular_offer_text(self, offer_type: str) -> str:
        """Получение текста для популярных предложений"""
        text_map = {
            "zero_percent": "🆓 <b>ЗАЙМЫ БЕЗ ПЕРЕПЛАТ (0%)</b>",
            "instant": "💳 <b>ДЕНЬГИ НА КАРТУ ЗА 5 МИНУТ</b>",
            "cash": "💵 <b>НАЛИЧНЫЕ В РУКИ</b>",
            "big_amount": "🚀 <b>СУММЫ до 500К</b>",
            "no_docs": "⚡ <b>БЕЗ СПРАВОК И ПОРУЧИТЕЛЕЙ</b>",
            "bad_credit": "🛡️ <b>ПЛОХАЯ КИ? НЕ ПРОБЛЕМА!</b>",
            "russia": "🇷🇺 <b>ЗАЙМЫ ДЛЯ РОССИИ</b>",
            "kazakhstan": "🇰🇿 <b>ЗАЙМЫ ДЛЯ КАЗАХСТАНА</b>"
        }

        return text_map.get(offer_type, "💰 <b>ПОПУЛЯРНЫЕ ЗАЙМЫ</b>")

    def _get_amount_keyboard(self, country: str) -> InlineKeyboardMarkup:
        """Получение клавиатуры выбора суммы в зависимости от страны"""
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

        return keyboard

    async def share_bot_from_offer_callback(self, callback: CallbackQuery, state: FSMContext):
        """Callback для поделиться ботом из контекста оффера"""
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
            [InlineKeyboardButton(text="🔙 Назад к предложениям", callback_data="back_to_offers")]
        ])

        await self.edit_message_with_keyboard(callback.message, share_text, keyboard)
        await callback.answer()