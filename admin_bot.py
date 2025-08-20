import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, Tuple, List
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', 'YOUR_ADMIN_BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '123456789').split(',')]
DATA_DIR = 'data'
OFFERS_FILE = os.path.join(DATA_DIR, 'offers.json')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'logos')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

PAYMENT_METHODS = {
    "bank_card": {"name": "💳 Карта банка", "emoji": "💳"},
    "bank_account": {"name": "🏦 Счет в банке", "emoji": "🏦"},
    "yandex_money": {"name": "🟡 Яндекс.Деньги", "emoji": "🟡"},
    "qiwi": {"name": "🥝 QIWI", "emoji": "🥝"},
    "contact": {"name": "📞 Контакт", "emoji": "📞"},
    "cash": {"name": "💵 Наличные", "emoji": "💵"}
}


class AddOfferStates(StatesGroup):
    name = State()
    countries = State()
    amounts = State()
    age = State()
    loan_terms = State()  # Новое состояние для сроков займа
    zero_percent = State()
    description = State()
    russia_link = State()
    kazakhstan_link = State()
    metrics = State()
    priority = State()
    payment_methods = State()
    logo = State()


class EditStates(StatesGroup):
    waiting_value = State()


class PaymentMethodsStates(StatesGroup):
    selecting = State()


def load_offers() -> Dict:
    if not os.path.exists(OFFERS_FILE):
        return {"microloans": {}}
    try:
        with open(OFFERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"microloans": {}}


def save_offers(data: Dict):
    with open(OFFERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_offer_id() -> str:
    offers = load_offers()
    existing_ids = list(offers.get('microloans', {}).keys())
    max_num = 0
    for offer_id in existing_ids:
        if offer_id.startswith('offer_'):
            try:
                max_num = max(max_num, int(offer_id.split('_')[1]))
            except:
                continue
    return f"offer_{max_num + 1:03d}"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def parse_metrics(text: str) -> Tuple[bool, Dict]:
    text = text.strip()

    # Формат: числа через пробел
    space_match = re.match(r'^(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)$', text)
    if space_match:
        try:
            cr, ar, epc, epl = map(float, space_match.groups())
            return True, {"cr": cr, "ar": ar, "epc": epc, "epl": epl}
        except:
            pass

    # Формат: из сайта с метками
    patterns = {"cr": r'CR:?\s*(\d+\.?\d*)%?', "ar": r'AR:?\s*(\d+\.?\d*)%?',
                "epc": r'EPC:?\s*(\d+\.?\d*)', "epl": r'EPL:?\s*(\d+\.?\d*)'}
    metrics = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                metrics[name] = float(match.group(1))
            except:
                continue

    return len(metrics) == 4, metrics


def escape_html(text: str) -> str:
    """Экранирует специальные HTML символы"""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def format_payment_methods(methods: List[str]) -> str:
    if not methods:
        return "❌ Не указаны"
    if len(methods) == len(PAYMENT_METHODS):
        return "✅ Все способы доступны"
    return "\n".join(f"   • {PAYMENT_METHODS[m]['name']}" for m in methods if m in PAYMENT_METHODS)


def get_payment_methods_keyboard(current: List[str] = None, show_back: bool = True) -> InlineKeyboardMarkup:
    if current is None:
        current = []

    buttons = []
    all_selected = len(current) == len(PAYMENT_METHODS)
    buttons.append([InlineKeyboardButton(text="✅ Все способы" if all_selected else "⬜ Все способы",
                                         callback_data="payment_all")])

    for method_id, method_info in PAYMENT_METHODS.items():
        is_selected = method_id in current
        text = f"✅ {method_info['name']}" if is_selected else f"⬜ {method_info['name']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"payment_{method_id}")])

    bottom_buttons = []
    if show_back:
        bottom_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="payment_back"))
    bottom_buttons.append(InlineKeyboardButton(text="🔄 Сбросить", callback_data="payment_reset"))
    bottom_buttons.append(InlineKeyboardButton(text="✅ Готово", callback_data="payment_done"))

    buttons.append(bottom_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_offer_info(offer: Dict, offer_id: str) -> str:
    """Форматирует информацию об оффере с защитой от HTML"""
    status = "✅ Активен" if offer.get('status', {}).get('is_active', True) else "❌ Неактивен"
    countries = offer.get('geography', {}).get('countries', [])
    countries_text = ", ".join(countries)
    zero_text = "✅ Есть" if offer.get('zero_percent', False) else "❌ Нет"

    metrics = offer.get('metrics', {})
    cr, ar, epc, epl = metrics.get('cr', 0), metrics.get('ar', 0), metrics.get('epc', 0), metrics.get('epl', 0)

    geography = offer.get('geography', {})
    ru_link = geography.get('russia_link', 'Не указана')
    kz_link = geography.get('kazakhstan_link') or 'Не указана'

    # Определяем валюты на основе стран
    has_russia = 'russia' in countries
    has_kazakhstan = 'kazakhstan' in countries

    if has_russia and has_kazakhstan:
        currency_text = f"{offer['limits']['min_amount']:,} - {offer['limits']['max_amount']:,} ₽/₸"
    elif has_kazakhstan:
        currency_text = f"{offer['limits']['min_amount']:,} - {offer['limits']['max_amount']:,} ₸"
    else:
        currency_text = f"{offer['limits']['min_amount']:,} - {offer['limits']['max_amount']:,} ₽"

    # Валюта для метрик - показываем обе если есть обе страны
    if has_russia and has_kazakhstan:
        epc_currency = "₽/₸"
        epl_currency = "₽/₸"
    elif has_kazakhstan:
        epc_currency = "₸"
        epl_currency = "₸"
    else:
        epc_currency = "₽"
        epl_currency = "₽"

    # Безопасное сокращение ссылок
    ru_link_short = escape_html((ru_link[:50] + '...') if ru_link and len(ru_link) > 50 else ru_link)
    kz_link_short = escape_html((kz_link[:50] + '...') if kz_link != 'Не указана' and len(kz_link) > 50 else kz_link)

    logo = offer.get('logo')
    logo_status = f"✅ {escape_html(logo)}" if logo else "❌ Не загружен"
    payment_methods_text = format_payment_methods(offer.get('payment_methods', []))

    # Форматирование сроков займа
    loan_terms = offer.get('loan_terms', {})
    if loan_terms:
        loan_terms_text = f"{loan_terms.get('min_days', 'Не указано')} - {loan_terms.get('max_days', 'Не указано')} дней"
    else:
        loan_terms_text = "Не указаны"

    created = offer.get('status', {}).get('created_at', 'Неизвестно')
    updated = offer.get('status', {}).get('updated_at', 'Неизвестно')

    for dt_str in [created, updated]:
        if dt_str != 'Неизвестно':
            try:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                if dt_str == created:
                    created = dt.strftime('%d.%m.%Y %H:%M')
                else:
                    updated = dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass

    # Безопасное экранирование всех текстовых полей
    offer_name = escape_html(offer.get('name', 'Без названия'))
    description = escape_html(offer.get('description', 'Не указано'))

    return (
        f"✏️ <b>Оффер {escape_html(offer_id)}</b>\n\n"
        f"📝 <b>Название:</b> {offer_name}\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"🌍 <b>Страны:</b> {countries_text}\n\n"
        f"💰 <b>Лимиты:</b>\n   • Сумма: {currency_text}\n"
        f"   • Возраст: {offer['limits']['min_age']} - {offer['limits']['max_age']} лет\n"
        f"   • Срок займа: {loan_terms_text}\n\n"
        f"🎯 <b>Условия:</b>\n   • 0% для новых: {zero_text}\n   • Описание: {description}\n\n"
        f"💳 <b>Способы получения:</b>\n{payment_methods_text}\n\n"
        f"📈 <b>CPA Метрики:</b>\n   • CR: {cr}%\n   • AR: {ar}%\n   • EPC: {epc} {epc_currency}\n   • EPL: {epl} {epl_currency}\n\n"
        f"⭐ <b>Приоритет:</b> {offer['priority']['manual_boost']}/10\n"
        f"🖼️ <b>Логотип:</b> {logo_status}\n\n"
        f"🔗 <b>Ссылки:</b>\n   • РФ: {ru_link_short}\n   • КЗ: {kz_link_short}\n\n"
        f"📅 <b>Создан:</b> {created}\n📅 <b>Обновлен:</b> {updated}"
    )


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить оффер", callback_data="add_offer")],
        [InlineKeyboardButton(text="📋 Список офферов", callback_data="list_offers")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")]
    ])


def offers_keyboard(offers: Dict) -> InlineKeyboardMarkup:
    buttons = []
    sorted_offers = sorted(offers.get('microloans', {}).items(),
                           key=lambda x: (x[1].get('priority', {}).get('manual_boost', 0),
                                          x[1].get('metrics', {}).get('cr', 0)), reverse=True)

    for offer_id, offer in sorted_offers:
        status = "✅" if offer.get('status', {}).get('is_active', True) else "❌"
        priority = offer.get('priority', {}).get('manual_boost', 5)
        cr = offer.get('metrics', {}).get('cr', 0)

        # Определяем валюту на основе стран
        countries = offer.get('geography', {}).get('countries', [])
        if 'russia' in countries and 'kazakhstan' in countries:
            currency_icon = "₽/₸"
        elif 'kazakhstan' in countries:
            currency_icon = "₸"
        else:
            currency_icon = "₽"

        # Экранируем имя оффера для безопасного отображения
        safe_name = escape_html(offer.get('name', 'Без названия'))[:25]  # Ограичиваем для места валюты
        text = f"{status} {safe_name} {currency_icon} (P:{priority}, CR:{cr}%)"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"edit_{offer_id}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"field_{offer_id}_name")],
        [InlineKeyboardButton(text="🎯 0% предложение", callback_data=f"field_{offer_id}_zero")],
        [InlineKeyboardButton(text="💰 Суммы", callback_data=f"field_{offer_id}_amounts")],
        [InlineKeyboardButton(text="👤 Возраст", callback_data=f"field_{offer_id}_age")],
        [InlineKeyboardButton(text="📅 Сроки займа", callback_data=f"field_{offer_id}_loan_terms")],
        [InlineKeyboardButton(text="📝 Описание", callback_data=f"field_{offer_id}_desc")],
        [InlineKeyboardButton(text="💳 Способы получения", callback_data=f"field_{offer_id}_payment_methods")],
        [InlineKeyboardButton(text="📈 CPA метрики", callback_data=f"field_{offer_id}_metrics")],
        [InlineKeyboardButton(text="🔗 Ссылка РФ", callback_data=f"field_{offer_id}_ru_link")],
        [InlineKeyboardButton(text="🔗 Ссылка КЗ", callback_data=f"field_{offer_id}_kz_link")],
        [InlineKeyboardButton(text="🖼️ Логотип", callback_data=f"field_{offer_id}_logo")],
        [InlineKeyboardButton(text="⭐ Приоритет", callback_data=f"field_{offer_id}_priority")],
        [InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=f"toggle_{offer_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{offer_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="list_offers")]
    ])


async def safe_edit_message(message, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасно редактирует сообщение с обработкой ошибок"""
    try:
        # Ограничиваем длину текста
        if len(text) > 4096:
            text = text[:4000] + "\n\n... (текст сокращен)"

        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        # Пробуем отправить новое сообщение вместо редактирования
        try:
            await message.delete()
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e2:
            logger.error(f"Ошибка отправки сообщения: {e2}")
            # В крайнем случае отправляем простое сообщение
            await message.answer("❌ Произошла ошибка при отображении информации", reply_markup=reply_markup)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    await message.answer("🔧 <b>Админ-панель займов</b>", reply_markup=main_keyboard(), parse_mode="HTML")


@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await safe_edit_message(callback.message, "🔧 <b>Админ-панель займов</b>", reply_markup=main_keyboard())


@dp.callback_query(F.data == "restart_bot")
async def restart_bot(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    await callback.answer("🔄 Перезапуск бота...")
    await safe_edit_message(callback.message,
                            "🔄 <b>Бот перезапускается...</b>\n\nПодождите несколько секунд и нажмите /start")

    # Закрываем текущую сессию
    await bot.session.close()

    # Перезапускаем процесс
    os.execv(sys.executable, ['python'] + sys.argv)


@dp.callback_query(F.data == "list_offers")
async def list_offers(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        offers = load_offers()
        if not offers.get("microloans"):
            await safe_edit_message(callback.message, "📋 Список пуст", reply_markup=main_keyboard())
            return

        text = f"📋 <b>Офферы ({len(offers['microloans'])})</b>"
        await safe_edit_message(callback.message, text, reply_markup=offers_keyboard(offers))

    except Exception as e:
        logger.error(f"Ошибка в list_offers: {e}")
        await callback.answer("❌ Ошибка загрузки офферов")


@dp.callback_query(F.data.startswith("edit_"))
async def view_offer(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        offer_id = callback.data.replace("edit_", "")
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        text = format_offer_info(offer, offer_id)

        # Если есть логотип, пробуем отправить его вместе с информацией
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                try:
                    photo = FSInputFile(logo_path)
                    await callback.message.delete()
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=edit_keyboard(offer_id),
                        parse_mode="HTML"
                    )
                    return
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения: {e}")

        await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))

    except Exception as e:
        logger.error(f"Ошибка в view_offer: {e}")
        await callback.answer("❌ Ошибка загрузки оффера")


@dp.callback_query(F.data.startswith("field_"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    try:
        data_part = callback.data.replace("field_", "")

        if data_part.endswith("_ru_link"):
            offer_id, field = data_part.replace("_ru_link", ""), "ru_link"
        elif data_part.endswith("_kz_link"):
            offer_id, field = data_part.replace("_kz_link", ""), "kz_link"
        elif data_part.endswith("_payment_methods"):
            offer_id, field = data_part.replace("_payment_methods", ""), "payment_methods"
        elif data_part.endswith("_loan_terms"):
            offer_id, field = data_part.replace("_loan_terms", ""), "loan_terms"
        else:
            parts = data_part.rsplit("_", 1)
            if len(parts) != 2:
                await callback.answer("❌ Ошибка формата")
                return
            offer_id, field = parts

        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)
        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        if field == "zero":
            current_zero = offer.get('zero_percent', False)
            offer['zero_percent'] = not current_zero
            offer['status']['updated_at'] = datetime.now().isoformat()
            save_offers(offers)
            await callback.answer(f"0% {'включен' if not current_zero else 'отключен'}")
            await view_offer(callback)
            return

        if field == "payment_methods":
            current_methods = offer.get('payment_methods', [])
            await state.set_state(PaymentMethodsStates.selecting)
            await state.update_data(offer_id=offer_id, current_methods=current_methods)

            text = f"💳 <b>Способы получения средств</b>\n\n📊 <b>Текущие способы:</b>\n{format_payment_methods(current_methods)}\n\n🔧 Выберите доступные способы получения:"
            await safe_edit_message(callback.message, text, reply_markup=get_payment_methods_keyboard(current_methods))
            return

        if field == "logo":
            logo_status = f"✅ {escape_html(offer.get('logo'))}" if offer.get('logo') else "❌ Не загружен"
            await state.set_state(EditStates.waiting_value)
            await state.update_data(offer_id=offer_id, field=field)

            # Создаем клавиатуру с кнопкой назад
            back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_offer_{offer_id}")]
            ])

            text = f"🖼️ <b>Редактирование логотипа</b>\n\n📊 <b>Текущий логотип:</b> {logo_status}\n\n📎 Отправьте новое изображение или:\n• '-' чтобы удалить текущий логотип\n• 'отмена' чтобы вернуться назад"
            await safe_edit_message(callback.message, text, reply_markup=back_keyboard)
            return

        await state.set_state(EditStates.waiting_value)
        await state.update_data(offer_id=offer_id, field=field)

        current_values = {
            "name": escape_html(offer.get('name', 'Не указано')),
            "desc": escape_html(offer.get('description', 'Не указано')),
            "amounts": f"{offer['limits']['min_amount']} {offer['limits']['max_amount']}",
            "age": f"{offer['limits']['min_age']} {offer['limits']['max_age']}",
            "loan_terms": f"{offer.get('loan_terms', {}).get('min_days', 'Не указано')} {offer.get('loan_terms', {}).get('max_days', 'Не указано')}" if offer.get(
                'loan_terms') else "Не указаны",
            "ru_link": escape_html(offer.get('geography', {}).get('russia_link', 'Не указана')),
            "kz_link": escape_html(offer.get('geography', {}).get('kazakhstan_link') or 'Не указана'),
            "priority": str(offer.get('priority', {}).get('manual_boost', 0)),
            "metrics": f"CR: {offer.get('metrics', {}).get('cr', 0)}%, AR: {offer.get('metrics', {}).get('ar', 0)}%, EPC: {offer.get('metrics', {}).get('epc', 0)}, EPL: {offer.get('metrics', {}).get('epl', 0)}"
        }

        field_prompts = {
            "name": f"📝 <b>Текущее название:</b> <i>{current_values['name']}</i>\n\nВведите новое название:",
            "desc": f"📝 <b>Текущее описание:</b> <i>{current_values['desc']}</i>\n\nВведите новое описание:",
            "amounts": f"💰 <b>Текущие суммы:</b> <i>{current_values['amounts']}</i>\n\nВведите новые суммы (формат: мин макс):",
            "age": f"👤 <b>Текущий возраст:</b> <i>{current_values['age']}</i>\n\nВведите новый возраст (формат: мин макс):",
            "loan_terms": f"📅 <b>Текущие сроки займа:</b> <i>{current_values['loan_terms']}</i>\n\nВведите новые сроки в днях (формат: мин макс):\nНапример: 5 30",
            "ru_link": f"🔗 <b>Текущая ссылка РФ:</b>\n<i>{current_values['ru_link']}</i>\n\nВведите новую ссылку для России:",
            "kz_link": f"🔗 <b>Текущая ссылка КЗ:</b>\n<i>{current_values['kz_link']}</i>\n\nВведите новую ссылку для Казахстана (или '-'):",
            "priority": f"⭐ <b>Текущий приоритет:</b> <i>{current_values['priority']}</i>\n\nВведите новый приоритет (0-10):",
            "metrics": f"📈 <b>Текущие метрики:</b>\n<i>{current_values['metrics']}</i>\n\n📈 <b>Введите новые CPA метрики одним из способов:</b>\n\n<b>Способ 1 - через пробел:</b>\n<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n<b>Способ 2 - скопировать с сайта:</b>\n<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>"
        }

        # Создаем клавиатуру с кнопкой назад
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_offer_{offer_id}")]
        ])

        prompt_text = field_prompts.get(field, f"Введите новое значение:")
        await safe_edit_message(callback.message, prompt_text, reply_markup=back_keyboard)

    except Exception as e:
        logger.error(f"Ошибка в edit_field: {e}")
        await callback.answer("❌ Ошибка редактирования поля")


@dp.callback_query(F.data.startswith("back_to_offer_"))
async def back_to_offer(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    offer_id = callback.data.replace("back_to_offer_", "")

    # Создаем новый объект callback с нужными данными для view_offer
    try:
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if not offer:
            await callback.answer("❌ Оффер не найден")
            return

        text = format_offer_info(offer, offer_id)

        # Если есть логотип, пробуем отправить его вместе с информацией
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                try:
                    photo = FSInputFile(logo_path)
                    await callback.message.delete()
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=edit_keyboard(offer_id),
                        parse_mode="HTML"
                    )
                    return
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения: {e}")

        await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))

    except Exception as e:
        logger.error(f"Ошибка в back_to_offer: {e}")
        await callback.answer("❌ Ошибка возврата к офферу")


@dp.callback_query(F.data == "payment_back", PaymentMethodsStates.selecting)
async def payment_method_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    offer_id = data.get('offer_id')
    await state.clear()

    if offer_id:
        # Безопасное возвращение к редактированию оффера
        try:
            offers = load_offers()
            offer = offers.get("microloans", {}).get(offer_id)

            if not offer:
                await callback.answer("❌ Оффер не найден")
                return

            text = format_offer_info(offer, offer_id)

            # Если есть логотип, пробуем отправить его вместе с информацией
            if offer.get('logo'):
                logo_path = os.path.join(IMAGES_DIR, offer['logo'])
                if os.path.exists(logo_path):
                    try:
                        photo = FSInputFile(logo_path)
                        await callback.message.delete()
                        await callback.message.answer_photo(
                            photo=photo,
                            caption=text,
                            reply_markup=edit_keyboard(offer_id),
                            parse_mode="HTML"
                        )
                        return
                    except Exception as e:
                        logger.error(f"Ошибка при отправке изображения: {e}")

            await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))

        except Exception as e:
            logger.error(f"Ошибка в payment_method_back: {e}")
            await callback.answer("❌ Ошибка возврата к офферу")
    else:
        await back_to_main(callback)


@dp.callback_query(F.data.startswith("payment_"), PaymentMethodsStates.selecting)
async def handle_payment_method_selection(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    current_methods = data.get('current_methods', [])
    action = callback.data.replace("payment_", "")

    if action == "all":
        current_methods = [] if len(current_methods) == len(PAYMENT_METHODS) else list(PAYMENT_METHODS.keys())
    elif action == "reset":
        current_methods = []
    elif action == "done":
        offer_id = data.get('offer_id')
        offers = load_offers()
        offer = offers.get("microloans", {}).get(offer_id)

        if offer:
            offer['payment_methods'] = current_methods
            offer['status']['updated_at'] = datetime.now().isoformat()
            save_offers(offers)
            await callback.answer("✅ Способы получения обновлены!")
            await state.clear()

            # Безопасное возвращение к редактированию оффера
            text = format_offer_info(offer, offer_id)
            await safe_edit_message(callback.message, text, reply_markup=edit_keyboard(offer_id))
            return
        else:
            await callback.answer("❌ Ошибка: оффер не найден")
            await state.clear()
            return
    elif action in PAYMENT_METHODS:
        if action in current_methods:
            current_methods.remove(action)
        else:
            current_methods.append(action)

    await state.update_data(current_methods=current_methods)

    text = f"💳 <b>Способы получения средств</b>\n\n📊 <b>Выбранные способы:</b>\n{format_payment_methods(current_methods)}\n\n🔧 Выберите доступные способы получения:"
    await safe_edit_message(callback.message, text, reply_markup=get_payment_methods_keyboard(current_methods))


@dp.message(F.photo)
async def handle_photo_upload(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    current_state = await state.get_state()
    data = await state.get_data()

    if current_state == EditStates.waiting_value.state and data.get('field') == 'logo':
        offer_id = data.get('offer_id')
        if not offer_id:
            await message.answer("❌ Ошибка: ID оффера не найден")
            await state.clear()
            return

        try:
            offers = load_offers()
            offer = offers.get("microloans", {}).get(offer_id)
            if not offer:
                await message.answer("❌ Оффер не найден")
                await state.clear()
                return

            if offer.get('logo'):
                old_logo_path = os.path.join(IMAGES_DIR, offer['logo'])
                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)

            photo = message.photo[-1]
            file_info = await bot.get_file(photo.file_id)
            file_extension = file_info.file_path.split('.')[
                -1] if file_info.file_path and '.' in file_info.file_path else 'jpg'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logo_filename = f"{offer_id}_{timestamp}.{file_extension}"
            logo_path = os.path.join(IMAGES_DIR, logo_filename)

            await bot.download_file(file_info.file_path, logo_path)

            offer['logo'] = logo_filename
            offer['status']['updated_at'] = datetime.now().isoformat()
            save_offers(offers)

            await message.answer(f"✅ <b>Логотип обновлен!</b>\n\n📁 <b>Файл:</b> {escape_html(logo_filename)}",
                                 parse_mode="HTML")
            await message.answer("🔧 Возврат к редактированию:", reply_markup=edit_keyboard(offer_id))
            await state.clear()

        except Exception as e:
            logger.error(f"Ошибка при сохранении логотипа: {e}")
            await message.answer("❌ <b>Ошибка при сохранении логотипа</b>", parse_mode="HTML")
            await state.clear()

    elif current_state == AddOfferStates.logo.state:
        await handle_add_offer_logo(message, state)
    else:
        await message.answer(
            "🖼️ <b>Загрузка изображений</b>\n\nДля загрузки логотипа:\n📋 Перейдите в список офферов → выберите оффер → нажмите '🖼️ Логотип'",
            parse_mode="HTML")


@dp.message(EditStates.waiting_value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    offer_id = data.get("offer_id")
    field = data.get("field")
    new_value = message.text.strip() if message.text else ""

    if new_value.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=edit_keyboard(offer_id))
        return

    offers = load_offers()
    offer = offers.get("microloans", {}).get(offer_id)
    if not offer:
        await message.answer("❌ Оффер не найден")
        await state.clear()
        return

    try:
        if field == "logo":
            if new_value == "-":
                if offer.get('logo'):
                    logo_path = os.path.join(IMAGES_DIR, offer['logo'])
                    if os.path.exists(logo_path):
                        os.remove(logo_path)
                offer['logo'] = None
                await message.answer("🗑️ <b>Логотип удален</b>", parse_mode="HTML")
                offer["status"]["updated_at"] = datetime.now().isoformat()
                save_offers(offers)
                await message.answer("🔧 Возврат к редактированию:", reply_markup=edit_keyboard(offer_id))
                await state.clear()
                return
            else:
                await message.answer(
                    "🖼️ <b>Для загрузки нового логотипа отправьте изображение</b>\n\n• Поддерживаемые форматы: JPG, PNG\n• Или отправьте '-' чтобы удалить текущий логотип\n• Или 'отмена' чтобы вернуться назад",
                    parse_mode="HTML")
                return

        elif field == "name":
            offer["name"] = new_value
        elif field == "desc":
            offer["description"] = new_value
        elif field == "ru_link":
            offer["geography"]["russia_link"] = new_value
        elif field == "kz_link":
            offer["geography"]["kazakhstan_link"] = new_value if new_value != "-" else None
        elif field == "priority":
            priority = int(new_value)
            if not 0 <= priority <= 10:
                raise ValueError("Приоритет должен быть 0-10")
            offer["priority"]["manual_boost"] = priority
            offer["priority"]["final_score"] = priority * 10
        elif field == "amounts":
            parts = new_value.split()
            if len(parts) != 2:
                raise ValueError("Формат: мин макс")
            offer["limits"]["min_amount"], offer["limits"]["max_amount"] = int(parts[0]), int(parts[1])
        elif field == "age":
            parts = new_value.split()
            if len(parts) != 2:
                raise ValueError("Формат: мин макс")
            offer["limits"]["min_age"], offer["limits"]["max_age"] = int(parts[0]), int(parts[1])
        elif field == "loan_terms":
            parts = new_value.split()
            if len(parts) != 2:
                raise ValueError("Формат: мин макс")
            min_days, max_days = int(parts[0]), int(parts[1])
            if min_days <= 0 or max_days <= 0:
                raise ValueError("Дни должны быть больше 0")
            if min_days > max_days:
                raise ValueError("Минимальный срок не может быть больше максимального")

            if "loan_terms" not in offer:
                offer["loan_terms"] = {}
            offer["loan_terms"]["min_days"] = min_days
            offer["loan_terms"]["max_days"] = max_days

            await message.answer(
                f"✅ <b>Сроки займа обновлены!</b>\n\n📅 Минимум: {min_days} дней\n📅 Максимум: {max_days} дней",
                parse_mode="HTML")
        elif field == "metrics":
            success, metrics = parse_metrics(new_value)
            if not success:
                raise ValueError(
                    "Неверный формат метрик.\nИспользуйте:\n• Через пробел: 54.9 4.2 102.01 185.98\n• Или скопируйте с сайта: CR: 54.9% ...")

            if "metrics" not in offer:
                offer["metrics"] = {}
            offer["metrics"].update(metrics)

            await message.answer(
                f"✅ <b>Метрики обновлены!</b>\n\n📈 CR: {metrics['cr']}%\n📈 AR: {metrics['ar']}%\n💰 EPC: {metrics['epc']} ₽\n💰 EPL: {metrics['epl']} ₽",
                parse_mode="HTML")

        offer["status"]["updated_at"] = datetime.now().isoformat()
        save_offers(offers)

        if field not in ["metrics", "logo", "loan_terms"]:
            await message.answer("✅ <b>Обновлено!</b>", parse_mode="HTML")

        await message.answer("🔧 Возврат к редактированию:", reply_markup=edit_keyboard(offer_id))

    except ValueError as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")
        await message.answer("❌ <b>Ошибка обновления</b>", parse_mode="HTML")

    await state.clear()


async def handle_add_offer_logo(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        offer_id = generate_offer_id()

        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_extension = file_info.file_path.split('.')[
            -1] if file_info.file_path and '.' in file_info.file_path else 'jpg'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logo_filename = f"{offer_id}_{timestamp}.{file_extension}"
        logo_path = os.path.join(IMAGES_DIR, logo_filename)

        await bot.download_file(file_info.file_path, logo_path)
        await create_offer_with_data(data, offer_id, logo_filename, message, state)

    except Exception as e:
        logger.error(f"Ошибка при загрузке логотипа: {e}")
        await message.answer("❌ <b>Ошибка при загрузке логотипа</b>", parse_mode="HTML")
        await state.clear()


async def create_offer_with_data(data: Dict, offer_id: str, logo_filename: str, message: Message, state: FSMContext):
    now = datetime.now().isoformat()

    offer = {
        "id": offer_id, "name": data["name"], "logo": logo_filename,
        "geography": {"countries": data["countries"], "russia_link": data["russia_link"],
                      "kazakhstan_link": data.get("kazakhstan_link")},
        "limits": {"min_amount": data["min_amount"], "max_amount": data["max_amount"], "min_age": data["min_age"],
                   "max_age": data["max_age"]},
        "loan_terms": {"min_days": data.get("min_days", 5), "max_days": data.get("max_days", 30)},
        "zero_percent": data["zero_percent"], "description": data["description"],
        "payment_methods": data.get("payment_methods", []),
        "metrics": data["metrics"],
        "priority": {"manual_boost": data["priority"], "final_score": data["priority"] * 10},
        "status": {"is_active": True, "created_at": now, "updated_at": now}
    }

    offers = load_offers()
    offers["microloans"][offer_id] = offer
    save_offers(offers)

    metrics = data["metrics"]
    logo_status = f"✅ {escape_html(logo_filename)}" if logo_filename else "❌ Не загружен"
    payment_methods_text = format_payment_methods(data.get("payment_methods", []))
    safe_name = escape_html(data['name'])

    # Определяем валюту для EPC на основе стран
    countries = data.get("countries", [])
    if 'kazakhstan' in countries and 'russia' not in countries:
        epc_currency = "₸"
    elif 'russia' in countries and 'kazakhstan' in countries:
        epc_currency = "₽/₸"
    else:
        epc_currency = "₽"

    await message.answer(
        f"✅ <b>Оффер создан!</b>\n\n🏷️ <b>ID:</b> {offer_id}\n📝 <b>Название:</b> {safe_name}\n⭐ <b>Приоритет:</b> {data['priority']}\n📈 <b>CR:</b> {metrics['cr']}%\n💰 <b>EPC:</b> {metrics['epc']} {epc_currency}\n🖼️ <b>Логотип:</b> {logo_status}\n💳 <b>Способы получения:</b>\n{payment_methods_text}",
        reply_markup=main_keyboard(), parse_mode="HTML")
    await state.clear()


@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_offer(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("toggle_", "")
    offers = load_offers()
    offer = offers.get("microloans", {}).get(offer_id)

    if not offer:
        await callback.answer("❌ Оффер не найден")
        return

    current_status = offer.get('status', {}).get('is_active', True)
    new_status = not current_status

    offer['status']['is_active'] = new_status
    offer['status']['updated_at'] = datetime.now().isoformat()

    if not new_status:
        offer['priority']['manual_boost'] = 0
        offer['priority']['final_score'] = 0
    else:
        if offer['priority']['manual_boost'] == 0:
            offer['priority']['manual_boost'] = 1
            offer['priority']['final_score'] = 10

    save_offers(offers)
    await callback.answer(f"{'✅ Включен' if new_status else '❌ Отключен'}")
    await view_offer(callback)


@dp.callback_query(F.data.startswith("delete_"))
async def delete_offer(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("delete_", "")

    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{offer_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_{offer_id}")
        ]
    ])

    await safe_edit_message(callback.message,
                            f"❗ <b>Подтверждение удаления</b>\n\nВы уверены, что хотите удалить оффер?",
                            reply_markup=confirm_keyboard)


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_offer(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    offer_id = callback.data.replace("confirm_delete_", "")
    offers = load_offers()

    if offer_id in offers.get("microloans", {}):
        offer = offers["microloans"][offer_id]
        if offer.get('logo'):
            logo_path = os.path.join(IMAGES_DIR, offer['logo'])
            if os.path.exists(logo_path):
                os.remove(logo_path)

        del offers["microloans"][offer_id]
        save_offers(offers)
        await callback.answer("🗑️ Удален")
        await safe_edit_message(callback.message, "🗑️ Оффер удален", reply_markup=main_keyboard())
    else:
        await callback.answer("❌ Оффер не найден")


@dp.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        offers = load_offers()
        microloans = offers.get("microloans", {})

        active_offers = sum(1 for offer in microloans.values() if offer.get('status', {}).get('is_active', True))
        total_offers = len(microloans)

        if total_offers > 0:
            avg_cr = sum(offer.get('metrics', {}).get('cr', 0) for offer in microloans.values()) / total_offers
            avg_ar = sum(offer.get('metrics', {}).get('ar', 0) for offer in microloans.values()) / total_offers
            avg_epc = sum(offer.get('metrics', {}).get('epc', 0) for offer in microloans.values()) / total_offers
        else:
            avg_cr = avg_ar = avg_epc = 0

        top_offers = sorted([(offer_id, offer) for offer_id, offer in microloans.items()],
                            key=lambda x: x[1].get('metrics', {}).get('cr', 0), reverse=True)[:3]
        top_text = "\n".join(f"{i}. {escape_html(offer['name'])}: {offer.get('metrics', {}).get('cr', 0)}%"
                             for i, (_, offer) in enumerate(top_offers, 1)) or "Нет данных"

        payment_stats = {}
        for offer in microloans.values():
            for method in offer.get('payment_methods', []):
                if method in PAYMENT_METHODS:
                    payment_stats[method] = payment_stats.get(method, 0) + 1

        payment_stats_text = "\n".join(
            f"{PAYMENT_METHODS[method_id]['emoji']} {PAYMENT_METHODS[method_id]['name'].replace(PAYMENT_METHODS[method_id]['emoji'] + ' ', '')}: {count}"
            for method_id, count in sorted(payment_stats.items(), key=lambda x: x[1], reverse=True)) or "Нет данных"

        text = (
            f"📊 <b>Статистика системы</b>\n\n📋 <b>Офферы:</b>\n   • Всего: {total_offers}\n   • Активных: {active_offers}\n   • Неактивных: {total_offers - active_offers}\n\n"
            f"📈 <b>Средние метрики:</b>\n   • CR: {avg_cr:.1f}%\n   • AR: {avg_ar:.1f}%\n   • EPC: {avg_epc:.1f} ₽\n\n"
            f"🏆 <b>ТОП по CR:</b>\n{top_text}\n\n💳 <b>Способы получения:</b>\n{payment_stats_text}")

        await safe_edit_message(callback.message, text,
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]]))
    except Exception as e:
        logger.error(f"Ошибка в show_stats: {e}")
        await callback.answer("❌ Ошибка загрузки статистики")


@dp.callback_query(F.data == "add_offer")
async def add_offer_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddOfferStates.name)

    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
    ])

    await safe_edit_message(callback.message,
                            "➕ <b>Добавление оффера</b>\n\nВведите название МФО:",
                            reply_markup=cancel_keyboard)


@dp.callback_query(F.data == "cancel_add_offer")
async def cancel_add_offer(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    await safe_edit_message(callback.message, "❌ Добавление оффера отменено", reply_markup=main_keyboard())


@dp.message(AddOfferStates.name)
async def add_offer_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddOfferStates.countries)
    await message.answer("🌍 Выберите страны:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_russia")],
        [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")],
        [InlineKeyboardButton(text="🌍 Обе", callback_data="country_both")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
    ]))


@dp.callback_query(F.data.startswith("country_"))
async def add_offer_countries(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.replace("country_", "")
    countries = {"russia": ["russia"], "kazakhstan": ["kazakhstan"], "both": ["russia", "kazakhstan"]}[choice]
    await state.update_data(countries=countries)
    await state.set_state(AddOfferStates.amounts)
    await safe_edit_message(callback.message,
                            "💰 Введите суммы (формат: мин макс):\nНапример: 1000 30000\n\nОтправьте 'отмена' для прекращения создания")


@dp.message(AddOfferStates.amounts)
async def add_offer_amounts(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно 2 числа")
        await state.update_data(min_amount=int(parts[0]), max_amount=int(parts[1]))
        await state.set_state(AddOfferStates.age)
        await message.answer(
            "👤 Введите возраст (формат: мин макс):\nНапример: 18 70\n\nОтправьте 'отмена' для прекращения создания")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите два числа через пробел")


@dp.message(AddOfferStates.age)
async def add_offer_age(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно 2 числа")
        await state.update_data(min_age=int(parts[0]), max_age=int(parts[1]))
        await state.set_state(AddOfferStates.loan_terms)
        await message.answer(
            "📅 Введите сроки займа в днях (формат: мин макс):\nНапример: 5 30\n\nОтправьте 'отмена' для прекращения создания")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите два числа через пробел")


@dp.message(AddOfferStates.loan_terms)
async def add_offer_loan_terms(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Нужно 2 числа")
        min_days, max_days = int(parts[0]), int(parts[1])
        if min_days <= 0 or max_days <= 0:
            raise ValueError("Дни должны быть больше 0")
        if min_days > max_days:
            raise ValueError("Минимальный срок не может быть больше максимального")

        await state.update_data(min_days=min_days, max_days=max_days)
        await state.set_state(AddOfferStates.zero_percent)
        await message.answer("🎯 Есть ли 0% для новых клиентов?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="zero_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="zero_no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_offer")]
        ]))
    except ValueError as e:
        await message.answer(f"❌ Неверный формат: {e}")


@dp.callback_query(F.data.startswith("zero_"))
async def add_offer_zero(callback: CallbackQuery, state: FSMContext):
    await state.update_data(zero_percent=callback.data == "zero_yes")
    await state.set_state(AddOfferStates.description)
    await safe_edit_message(callback.message,
                            "📝 Введите описание оффера:\n\nОтправьте 'отмена' для прекращения создания")


@dp.message(AddOfferStates.description)
async def add_offer_description(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(AddOfferStates.russia_link)
    await message.answer("🔗 Введите партнерскую ссылку для России:\n\nОтправьте 'отмена' для прекращения создания")


@dp.message(AddOfferStates.russia_link)
async def add_offer_russia_link(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    await state.update_data(russia_link=message.text.strip())
    data = await state.get_data()

    if "kazakhstan" in data.get("countries", []):
        await state.set_state(AddOfferStates.kazakhstan_link)
        await message.answer(
            "🔗 Введите ссылку для Казахстана (или '-'):\n\nОтправьте 'отмена' для прекращения создания")
    else:
        await state.set_state(AddOfferStates.metrics)
        await message.answer(
            "📈 <b>Введите CPA метрики одним из способов:</b>\n\n<b>Способ 1 - через пробел:</b>\n<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n<b>Способ 2 - скопировать с сайта:</b>\n<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>\n\nОтправьте 'отмена' для прекращения создания",
            parse_mode="HTML")


@dp.message(AddOfferStates.kazakhstan_link)
async def add_offer_kazakhstan_link(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    await state.update_data(kazakhstan_link=message.text.strip() if message.text.strip() != "-" else None)
    await state.set_state(AddOfferStates.metrics)
    await message.answer(
        "📈 <b>Введите CPA метрики одним из способов:</b>\n\n<b>Способ 1 - через пробел:</b>\n<code>54.9 4.2 102.01 185.98</code>\n(CR AR EPC EPL)\n\n<b>Способ 2 - скопировать с сайта:</b>\n<code>CR: 54.9%\nAR: 4.2%\nEPC: 102.01\nEPL: 185.98</code>\n\nОтправьте 'отмена' для прекращения создания",
        parse_mode="HTML")


@dp.message(AddOfferStates.metrics)
async def add_offer_metrics(message: Message, state: FSMContext):
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    try:
        success, metrics = parse_metrics(message.text)
        if not success:
            raise ValueError(
                "Неверный формат метрик.\nИспользуйте:\n• Через пробел: 54.9 4.2 102.01 185.98\n• Или скопируйте с сайта: CR: 54.9% ...")

        await state.update_data(metrics=metrics)
        await state.set_state(AddOfferStates.priority)
        await message.answer(
            f"✅ <b>Метрики приняты:</b>\n📈 CR: {metrics['cr']}%\n📈 AR: {metrics['ar']}%\n💰 EPC: {metrics['epc']} ₽\n💰 EPL: {metrics['epl']} ₽\n\n⭐ Теперь введите приоритет (1-10):\n\nОтправьте 'отмена' для прекращения создания",
            parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(AddOfferStates.priority)
async def add_offer_priority(message: Message, state: FSMContext):
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
            "💳 <b>Способы получения средств</b>\n\n🔧 Выберите доступные способы получения для этого оффера:",
            reply_markup=get_payment_methods_keyboard([], show_back=False), parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.callback_query(F.data.startswith("payment_"), AddOfferStates.payment_methods)
async def handle_add_offer_payment_methods(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    current_methods = data.get('payment_methods_temp', [])
    action = callback.data.replace("payment_", "")

    if action == "all":
        current_methods = [] if len(current_methods) == len(PAYMENT_METHODS) else list(PAYMENT_METHODS.keys())
    elif action == "reset":
        current_methods = []
    elif action == "done":
        await state.update_data(payment_methods=current_methods)
        await state.set_state(AddOfferStates.logo)
        await safe_edit_message(callback.message,
                                f"✅ <b>Способы получения выбраны:</b>\n{format_payment_methods(current_methods)}\n\n🖼️ <b>Загрузка логотипа</b>\n\n📎 Отправьте изображение логотипа МФО или '-' чтобы пропустить\n\n• Поддерживаемые форматы: JPG, PNG\n• Рекомендуемый размер: не более 1 МБ\n\nОтправьте 'отмена' для прекращения создания")
        return
    elif action in PAYMENT_METHODS:
        if action in current_methods:
            current_methods.remove(action)
        else:
            current_methods.append(action)

    await state.update_data(payment_methods_temp=current_methods)
    text = f"💳 <b>Способы получения средств</b>\n\n📊 <b>Выбранные способы:</b>\n{format_payment_methods(current_methods)}\n\n🔧 Выберите доступные способы получения:"
    await safe_edit_message(callback.message, text,
                            reply_markup=get_payment_methods_keyboard(current_methods, show_back=False))


@dp.message(AddOfferStates.logo)
async def add_offer_logo(message: Message, state: FSMContext):
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление оффера отменено", reply_markup=main_keyboard())
        return

    if message.text and message.text.strip() == "-":
        data = await state.get_data()
        offer_id = generate_offer_id()
        await create_offer_with_data(data, offer_id, None, message, state)
    else:
        await message.answer(
            "🖼️ <b>Для загрузки логотипа отправьте изображение</b>\n\n• Или отправьте '-' чтобы пропустить загрузку логотипа\n• Или 'отмена' для прекращения создания",
            parse_mode="HTML")


@dp.message(Command("check_offers"))
async def check_all_offers(message: Message):
    if not is_admin(message.from_user.id):
        return

    offers = load_offers()
    microloans = offers.get("microloans", {})

    if not microloans:
        await message.answer("📋 <b>Нет офферов в базе</b>", parse_mode="HTML")
        return

    result = f"📊 <b>Состояние всех офферов ({len(microloans)}):</b>\n\n"

    sorted_offers = sorted(microloans.items(), key=lambda x: x[1].get('priority', {}).get('manual_boost', 0),
                           reverse=True)
    active_count = inactive_count = 0

    for offer_id, offer in sorted_offers:
        status = offer.get('status', {}).get('is_active', True)
        priority = offer.get('priority', {}).get('manual_boost', 0)
        cr = offer.get('metrics', {}).get('cr', 0)
        safe_name = escape_html(offer.get('name', 'Без названия'))

        if status:
            active_count += 1
            status_emoji = "✅"
        else:
            inactive_count += 1
            status_emoji = "❌"

        result += f"{status_emoji} <b>{safe_name}</b>\n   P: {priority}/10, CR: {cr}%\n   ID: {offer_id}\n\n"

    result += f"📈 <b>Итого:</b>\n   • Активных: {active_count}\n   • Неактивных: {inactive_count}\n   • Всего: {len(microloans)}"

    if len(result) > 4096:
        chunks = [result[i:i + 4000] for i in range(0, len(result), 4000)]
        for i, chunk in enumerate(chunks):
            await message.answer(chunk if i == 0 else f"<b>Продолжение {i + 1}:</b>\n{chunk}", parse_mode="HTML")
    else:
        await message.answer(result, parse_mode="HTML")


@dp.message(Command("fix_inactive_offers"))
async def fix_inactive_offers(message: Message):
    if not is_admin(message.from_user.id):
        return

    offers = load_offers()
    fixed_count = 0

    for offer_id, offer in offers.get("microloans", {}).items():
        if not offer.get('status', {}).get('is_active', True):
            offer['status']['is_active'] = True
            offer['status']['updated_at'] = datetime.now().isoformat()
            fixed_count += 1

    if fixed_count > 0:
        save_offers(offers)
        await message.answer(
            f"✅ <b>Исправление завершено!</b>\n\n📊 Активировано офферов: {fixed_count}\nℹ️ Теперь все офферы активны независимо от приоритета",
            parse_mode="HTML")
    else:
        await message.answer("ℹ️ <b>Исправление не требуется</b>\n\nВсе офферы уже активны", parse_mode="HTML")


@dp.message(Command("migrate_offers"))
async def migrate_offers_structure(message: Message):
    if not is_admin(message.from_user.id):
        return

    offers = load_offers()
    migrated_count = 0

    for offer_id, offer in offers.get("microloans", {}).items():
        updated = False

        # Миграция способов оплаты
        if "payment_methods" not in offer:
            offer["payment_methods"] = list(PAYMENT_METHODS.keys())
            updated = True

        # Миграция сроков займа
        if "loan_terms" not in offer:
            offer["loan_terms"] = {"min_days": 5, "max_days": 30}
            updated = True

        if updated:
            offer["status"]["updated_at"] = datetime.now().isoformat()
            migrated_count += 1

    if migrated_count > 0:
        save_offers(offers)
        await message.answer(
            f"✅ <b>Миграция завершена!</b>\n\n📊 Обновлено офферов: {migrated_count}\n💳 Добавлены способы получения и сроки займа",
            parse_mode="HTML")
    else:
        await message.answer("ℹ️ <b>Миграция не требуется</b>\n\nВсе офферы уже имеют актуальную структуру",
                             parse_mode="HTML")


@dp.message()
async def unknown_message(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    await message.answer("❓ Неизвестная команда. Используйте /start", reply_markup=main_keyboard())


async def main():
    if not os.path.exists(OFFERS_FILE):
        save_offers({"microloans": {}})

    logger.info("🚀 Улучшенный админ-бот запущен")
    logger.info("📈 Поддержка: CR, AR, EPC, EPL")
    logger.info("🖼️ Поддержка изображений с просмотром")
    logger.info("💳 Поддержка способов получения средств")
    logger.info("📅 Поддержка сроков займа")
    logger.info("⬅️ Кнопки назад на всех этапах")
    logger.info("🔄 Возможность перезапуска бота")
    logger.info("🔧 Команды: /start, /check_offers, /fix_inactive_offers, /migrate_offers")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка бота")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Принудительная остановка")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        print("🔚 Завершено")