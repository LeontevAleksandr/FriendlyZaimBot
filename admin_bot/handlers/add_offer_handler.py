"""
Обработчики для добавления новых офферов
"""
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from admin_bot.config.auth import is_admin
from admin_bot.states.add_offer_states import AddOfferStates
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.keyboards.payment_keyboards import get_payment_methods_keyboard
from admin_bot.utils.validators import parse_metrics
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def add_offer_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса добавления нового оффера"""
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AddOfferStates.name)

    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
    ])

    await safe_edit_message(
        callback.message,
        "➕ <b>Добавление оффера</b>\n\n"
        "Шаг 1/9: Введите название МФО:",
        reply_markup=cancel_keyboard
    )


async def cancel_add_offer(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления оффера"""
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    await safe_edit_message(
        callback.message,
        "❌ Добавление оффера отменено",
        reply_markup=main_keyboard()
    )


async def add_offer_name(message: Message, state: FSMContext):
    """Обработка названия МФО"""
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(name=name)
    await state.set_state(AddOfferStates.countries)

    await message.answer(
        f"✅ Название: {name}\n\n🌍 Шаг 2/9: Выберите страны:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
            [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")],
            [InlineKeyboardButton(text="🌍 Обе", callback_data="country_both")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
        ])
    )


async def add_offer_countries(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора стран"""
    choice = callback.data.replace("country_", "")
    countries_map = {
        "russia": ["russia"],
        "kazakhstan": ["kazakhstan"],
        "both": ["russia", "kazakhstan"]
    }
    countries = countries_map[choice]

    await state.update_data(countries=countries)
    await state.set_state(AddOfferStates.amounts)

    countries_text = {"russia": "🇷🇺 Россия", "kazakhstan": "🇰🇿 Казахстан", "both": "🌍 Россия и Казахстан"}[choice]

    await safe_edit_message(
        callback.message,
        f"✅ Страны: {countries_text}\n\n"
        f"💰 Шаг 3/9: Введите лимиты по сумме займа\n\n"
        f"Формат: мин макс\nПример: 1000 30000\n\n"
        f"Отправьте 'отмена' для прекращения"
    )


async def add_offer_amounts(message: Message, state: FSMContext):
    """Обработка лимитов по сумме"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно ровно 2 числа")

        min_amount, max_amount = int(parts[0]), int(parts[1])
        if min_amount <= 0 or max_amount <= 0:
            raise ValueError("Суммы должны быть больше нуля")
        if min_amount >= max_amount:
            raise ValueError("Минимальная сумма должна быть меньше максимальной")

        await state.update_data(min_amount=min_amount, max_amount=max_amount)
        await state.set_state(AddOfferStates.age)

        await message.answer(
            f"✅ Суммы: {min_amount:,} - {max_amount:,} ₽\n\n"
            f"👤 Шаг 4/9: Введите возрастные ограничения\n\n"
            f"Формат: мин макс\nПример: 18 70\n\n"
            f"Отправьте 'отмена' для прекращения"
        )

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")


async def add_offer_age(message: Message, state: FSMContext):
    """Обработка возрастных ограничений"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно ровно 2 числа")

        min_age, max_age = int(parts[0]), int(parts[1])
        if min_age < 18 or max_age > 100:
            raise ValueError("Возраст должен быть от 18 до 100 лет")
        if min_age >= max_age:
            raise ValueError("Минимальный возраст должен быть меньше максимального")

        await state.update_data(min_age=min_age, max_age=max_age)
        await state.set_state(AddOfferStates.loan_terms)

        await message.answer(
            f"✅ Возраст: {min_age} - {max_age} лет\n\n"
            f"📅 Шаг 5/9: Введите сроки займа в днях\n\n"
            f"Формат: мин макс\nПример: 5 30\n\n"
            f"Отправьте 'отмена' для прекращения"
        )

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")


async def add_offer_loan_terms(message: Message, state: FSMContext):
    """Обработка сроков займа"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно ровно 2 числа")

        min_days, max_days = int(parts[0]), int(parts[1])
        if min_days <= 0 or max_days <= 0:
            raise ValueError("Дни должны быть больше 0")
        if min_days > max_days:
            raise ValueError("Минимальный срок не может быть больше максимального")

        await state.update_data(min_days=min_days, max_days=max_days)
        await state.set_state(AddOfferStates.zero_percent)

        await message.answer(
            f"✅ Сроки: {min_days} - {max_days} дней\n\n"
            f"🎯 Шаг 6/9: Есть ли 0% для новых клиентов?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="zero_yes")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="zero_no")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
            ])
        )

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")


async def add_offer_zero(callback: CallbackQuery, state: FSMContext):
    """Обработка 0% предложений"""
    zero_percent = callback.data == "zero_yes"
    await state.update_data(zero_percent=zero_percent)
    await state.set_state(AddOfferStates.description)

    zero_text = "✅ Есть 0%" if zero_percent else "❌ Нет 0%"

    await safe_edit_message(
        callback.message,
        f"{zero_text}\n\n"
        f"📝 Шаг 7/9: Введите описание оффера\n\n"
        f"Кратко опишите особенности займа\n\n"
        f"Отправьте 'отмена' для прекращения"
    )


async def add_offer_description(message: Message, state: FSMContext):
    """Обработка описания"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    description = message.text.strip()
    if not description:
        await message.answer("❌ Описание не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(description=description)
    await state.set_state(AddOfferStates.russia_link)

    await message.answer(
        f"✅ Описание сохранено\n\n"
        f"🔗 Шаг 8/9: Введите партнерскую ссылку для России\n\n"
        f"Полная ссылка с вашим партнерским ID\n\n"
        f"Отправьте 'отмена' для прекращения"
    )


async def add_offer_russia_link(message: Message, state: FSMContext):
    """Обработка ссылки для России"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    russia_link = message.text.strip()
    if not russia_link:
        await message.answer("❌ Ссылка не может быть пустой. Попробуйте еще раз:")
        return

    await state.update_data(russia_link=russia_link)
    data = await state.get_data()

    # Если есть Казахстан, запрашиваем ссылку для него
    if "kazakhstan" in data.get("countries", []):
        await state.set_state(AddOfferStates.kazakhstan_link)
        await message.answer(
            f"✅ Ссылка для России сохранена\n\n"
            f"🔗 Введите ссылку для Казахстана\n\n"
            f"Или отправьте '-' если одинаковая ссылка\n\n"
            f"Отправьте 'отмена' для прекращения"
        )
    else:
        # Переходим к метрикам
        await state.set_state(AddOfferStates.metrics)
        await message.answer(
            "✅ Ссылка сохранена\n\n"
            "📈 Шаг 9/9: Введите CPA метрики\n\n"
            "<b>Способ 1 - через пробел:</b>\n"
            "<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n"
            "<b>Способ 2 - скопировать с сайта:</b>\n"
            "<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>\n\n"
            "Отправьте 'отмена' для прекращения",
            parse_mode="HTML"
        )


async def add_offer_kazakhstan_link(message: Message, state: FSMContext):
    """Обработка ссылки для Казахстана"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    kz_link = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(kazakhstan_link=kz_link)
    await state.set_state(AddOfferStates.metrics)

    await message.answer(
        "✅ Ссылка для Казахстана сохранена\n\n"
        "📈 Шаг 9/9: Введите CPA метрики\n\n"
        "<b>Способ 1 - через пробел:</b>\n"
        "<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n"
        "<b>Способ 2 - скопировать с сайта:</b>\n"
        "<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>\n\n"
        "Отправьте 'отмена' для прекращения",
        parse_mode="HTML"
    )


async def add_offer_metrics(message: Message, state: FSMContext):
    """Обработка CPA метрик"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        success, metrics = parse_metrics(message.text)
        if not success:
            raise ValueError(
                "Неверный формат метрик.\n"
                "Используйте:\n"
                "• Через пробел: 54.9 4.2 102.01 185.98\n"
                "• Или скопируйте с сайта: CR: 54.9% AR: 4.2% ..."
            )

        await state.update_data(metrics=metrics)
        await state.set_state(AddOfferStates.priority)

        await message.answer(
            f"✅ <b>Метрики приняты:</b>\n"
            f"📈 CR: {metrics['cr']}%\n"
            f"📈 AR: {metrics['ar']}%\n"
            f"💰 EPC: {metrics['epc']} ₽\n"
            f"💰 EPL: {metrics['epl']} ₽\n\n"
            f"⭐ Введите приоритет (1-10):\n"
            f"1 = низкий, 10 = максимальный\n\n"
            f"Отправьте 'отмена' для прекращения",
            parse_mode="HTML"
        )

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")


async def add_offer_priority(message: Message, state: FSMContext):
    """Обработка приоритета"""
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        priority = int(message.text.strip())
        if not 1 <= priority <= 10:
            raise ValueError("Должно быть от 1 до 10")

        await state.update_data(priority=priority)
        await state.set_state(AddOfferStates.payment_methods)

        await message.answer(
            f"✅ Приоритет: {priority}/10\n\n"
            f"💳 Выберите способы получения средств\n\n"
            f"🔧 Выберите все доступные способы:",
            reply_markup=get_payment_methods_keyboard([], show_back=False),
            parse_mode="HTML"
        )

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")


def register_add_offer_handlers(dp):
    """Регистрирует обработчики добавления офферов"""
    dp.callback_query.register(add_offer_start, F.data == "add_offer")
    dp.callback_query.register(cancel_add_offer, F.data == "cancel_add_offer")
    dp.callback_query.register(add_offer_countries, F.data.startswith("country_"))
    dp.callback_query.register(add_offer_zero, F.data.startswith("zero_"))

    dp.message.register(add_offer_name, AddOfferStates.name)
    dp.message.register(add_offer_amounts, AddOfferStates.amounts)
    dp.message.register(add_offer_age, AddOfferStates.age)
    dp.message.register(add_offer_loan_terms, AddOfferStates.loan_terms)
    dp.message.register(add_offer_description, AddOfferStates.description)
    dp.message.register(add_offer_russia_link, AddOfferStates.russia_link)
    dp.message.register(add_offer_kazakhstan_link, AddOfferStates.kazakhstan_link)
    dp.message.register(add_offer_metrics, AddOfferStates.metrics)
    dp.message.register(add_offer_priority, AddOfferStates.priority)