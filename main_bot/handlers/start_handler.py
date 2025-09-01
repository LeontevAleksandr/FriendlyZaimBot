import logging
from aiogram import Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from main_bot.states.loan_flow import LoanFlow
from main_bot.keyboards.reply_keyboards import get_main_keyboard
from main_bot.utils.analytics import AnalyticsTracker
from shared.user_profile_manager import UserProfileManager

logger = logging.getLogger(__name__)


class StartHandler:
    """Обработчик команд запуска и настроек"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.analytics = AnalyticsTracker()
        self.profile_manager = UserProfileManager()

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

    def register_handlers(self, dp):
        """Регистрация обработчиков команд"""
        dp.message.register(self.cmd_start, CommandStart())
        dp.message.register(self.cmd_restart, Command("restart"))
        dp.message.register(self.cmd_clear_profile, Command("clear_profile"))
        dp.message.register(self.cmd_help, Command("help"))
        dp.message.register(self.handle_settings_button, F.text == "⚙️ Настройки профиля")
        dp.message.register(self.handle_share_button, F.text == "🚀 Поделиться ботом")

        # Коллбеки для настроек профиля
        dp.callback_query.register(self.confirm_clear_profile_callback, F.data == "confirm_clear_profile")
        dp.callback_query.register(self.execute_clear_profile_callback, F.data == "execute_clear_profile")
        dp.callback_query.register(self.share_bot_callback, F.data == "share_bot")
        dp.callback_query.register(self.back_to_main_callback, F.data == "back_to_main")

        # Базовые коллбеки для начального флоу (если CallbackHandlers не подхватил)
        dp.callback_query.register(self.country_callback, F.data.startswith("country_"))
        dp.callback_query.register(self.age_callback, F.data.startswith("age_"))

    async def cmd_start(self, message: Message, state: FSMContext):
        """Команда /start - максимальная конверсия с первой секунды"""
        await state.clear()

        # Трекинг пользователя
        await self.analytics.track_user_start(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        # Получаем профиль пользователя
        profile = await self.profile_manager.get_or_create_profile(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        # Сохраняем профиль в состоянии
        await state.update_data(user_profile=profile.__dict__)

        # Проверяем, есть ли сохраненные предпочтения
        if profile.country and profile.age:
            # ВОЗВРАЩАЮЩИЙСЯ ПОЛЬЗОВАТЕЛЬ с сохраненными настройками
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
            # НОВЫЙ ПОЛЬЗОВАТЕЛЬ
            welcome_text = (
                f"🎉 <b>Добро пожаловать, {message.from_user.first_name or 'друг'}!</b>\n\n"
                "💰 Найдём вам <b>займ до 500 000 ₽</b> за 5 минут!\n\n"
                "✅ Без отказов и справок\n"
                "✅ Плохая КИ? Не проблема!\n"
                "✅ Деньги на карту или наличными\n\n"
                "Сначала настроим ваш профиль:"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
                [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")]
            ])

            await state.set_state(LoanFlow.choosing_country)

        # Отправляем основное сообщение с inline клавиатурой
        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

        # Устанавливаем постоянную клавиатуру через незаметное сообщение
        await message.answer("​", reply_markup=get_main_keyboard())

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
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear_profile")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
        ])

        await message.answer(
            "🗑️ <b>Очистка профиля</b>\n\n"
            "Вы уверены, что хотите удалить все сохранённые данные?\n"
            "(возраст, страна, предпочтения)",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def cmd_help(self, message: Message):
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

    async def handle_settings_button(self, message: Message):
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

    async def handle_share_button(self, message: Message):
        """Обработчик кнопки поделиться ботом"""
        share_text = (
            "🚀 <b>Поделитесь ботом с друзьями!</b>\n\n"
            "Расскажите знакомым о быстрых займах:\n"
            "✅ До 500К без отказов\n"
            "✅ За 5 минут на карту\n"
            "✅ Даже с плохой КИ\n\n"
            "Просто перешлите это сообщение 👇"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share_bot")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])

        await message.answer(share_text, reply_markup=keyboard, parse_mode="HTML")

    async def back_to_main_callback(self, callback: CallbackQuery):
        """Возврат к главному меню"""
        await callback.message.delete()
        await callback.answer()

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
                "Используйте кнопки ниже для поиска займов"
            )

            # Удаляем inline клавиатуру, показываем только сообщение
            await callback.message.edit_text(success_text, parse_mode="HTML")
            await callback.answer("Профиль очищен!")

        except Exception as e:
            logger.error(f"Ошибка очистки профиля: {e}")
            await callback.answer("Ошибка очистки профиля", show_alert=True)

    async def share_bot_callback(self, callback: CallbackQuery):
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
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])

        await callback.message.edit_text(share_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def country_callback(self, callback: CallbackQuery, state: FSMContext):
        """Базовый обработчик выбора страны для начального флоу"""
        country = callback.data.split("_")[1]
        await state.update_data(country=country)

        # Сохраняем в профиле
        await self.profile_manager.update_profile_preferences(
            callback.from_user.id,
            country=country
        )

        country_name = "🇷🇺 России" if country == "russia" else "🇰🇿 Казахстане"
        text = f"Отлично! Подбираем займы в {country_name}\n\n👤 Укажите ваш возраст:"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="18-25 лет", callback_data="age_22")],
            [InlineKeyboardButton(text="26-35 лет", callback_data="age_30")],
            [InlineKeyboardButton(text="36-50 лет", callback_data="age_43")],
            [InlineKeyboardButton(text="51+ лет", callback_data="age_60")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(LoanFlow.choosing_age)
        await callback.answer()

    async def age_callback(self, callback: CallbackQuery, state: FSMContext):
        """Базовый обработчик выбора возраста для начального флоу"""
        age = int(callback.data.split("_")[1])
        await state.update_data(age=age)

        # Сохраняем в профиле
        await self.profile_manager.update_profile_preferences(
            callback.from_user.id,
            age=age
        )

        # После выбора возраста переходим к основному функционалу
        success_text = (
            f"✅ <b>Профиль настроен!</b>\n\n"
            f"🌍 Страна: {'🇷🇺 Россия' if (await state.get_data()).get('country') == 'russia' else '🇰🇿 Казахстан'}\n"
            f"🎂 Возраст: {age} лет\n\n"
            "Теперь можно искать займы!"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 НАЙТИ ЗАЙМЫ",
                                  callback_data=f"quick_search_{(await state.get_data()).get('country')}_{age}")],
            [InlineKeyboardButton(text="🔥 Популярные предложения", callback_data="back_to_popular")]
        ])

        await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("Профиль настроен!")