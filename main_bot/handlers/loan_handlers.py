import logging
from aiogram import Bot, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from main_bot.states.loan_flow import LoanFlow
from main_bot.keyboards.inline_keyboards import get_popular_offers_keyboard
from main_bot.utils.analytics import AnalyticsTracker
from shared.offer_manager import OfferManager
from shared.user_profile_manager import UserProfileManager

logger = logging.getLogger(__name__)


class LoanHandlers:
    """Обработчики поиска займов"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.offer_manager = OfferManager()
        self.analytics = AnalyticsTracker()
        self.profile_manager = UserProfileManager()

    def register_handlers(self, dp):
        """Регистрация обработчиков"""
        dp.message.register(self.handle_popular_offers_button, F.text == "🔥 Популярные предложения")
        dp.message.register(self.handle_find_loan_button, F.text == "💰 Найти займ")

    async def handle_popular_offers_button(self, message: Message):
        """Обработчик кнопки популярных предложений - МАКСИМАЛЬНАЯ КОНВЕРСИЯ"""
        popular_text = (
            "🔥 <b>ПОПУЛЯРНЫЕ ЗАЙМЫ</b>\n\n"
            "Выберите подходящий вариант для быстрого получения денег:"
        )

        keyboard = get_popular_offers_keyboard()
        await message.answer(popular_text, reply_markup=keyboard, parse_mode="HTML")

    async def handle_find_loan_button(self, message: Message, state: FSMContext):
        """Обработчик кнопки поиска займа"""
        # Получаем профиль пользователя
        profile = await self.profile_manager.get_or_create_profile(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        await state.update_data(user_profile=profile.__dict__)

        # Проверяем, есть ли сохраненные данные профиля
        if profile.country and profile.age:
            # ВОЗВРАЩАЮЩИЙСЯ ПОЛЬЗОВАТЕЛЬ - быстрый поиск
            country_name = "🇷🇺 России" if profile.country == "russia" else "🇰🇿 Казахстане"

            welcome_text = (
                f"💰 <b>Найдем займ с вашими настройками!</b>\n\n"
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
            # НОВЫЙ ПОЛЬЗОВАТЕЛЬ - настройка профиля
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

        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")