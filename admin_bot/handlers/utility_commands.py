"""
Утилитарные команды для диагностики и миграции системы
"""
import logging
from datetime import datetime
from aiogram import F
from aiogram.types import Message
from aiogram.filters import Command

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import PAYMENT_METHODS
from admin_bot.keyboards.main_keyboards import main_keyboard
from admin_bot.utils.offer_manager import load_offers, save_offers
from admin_bot.utils.formatters import escape_html

logger = logging.getLogger(__name__)


async def check_all_offers(message: Message):
    """Команда /check_offers - проверка состояния всех офферов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    offers = load_offers()
    microloans = offers.get("microloans", {})

    if not microloans:
        await message.answer("📋 <b>Нет офферов в базе</b>", parse_mode="HTML")
        return

    result = f"📊 <b>Состояние всех офферов ({len(microloans)}):</b>\n\n"

    sorted_offers = sorted(
        microloans.items(),
        key=lambda x: x[1].get('priority', {}).get('manual_boost', 0),
        reverse=True
    )
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

    # Разбиваем длинные сообщения на части
    if len(result) > 4096:
        chunks = [result[i:i + 4000] for i in range(0, len(result), 4000)]
        for i, chunk in enumerate(chunks):
            await message.answer(
                chunk if i == 0 else f"<b>Продолжение {i + 1}:</b>\n{chunk}",
                parse_mode="HTML"
            )
    else:
        await message.answer(result, parse_mode="HTML")


async def fix_inactive_offers(message: Message):
    """Команда /fix_inactive_offers - активация всех офферов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
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
            f"✅ <b>Исправление завершено!</b>\n\n"
            f"📊 Активировано офферов: {fixed_count}\n"
            f"ℹ️ Теперь все офферы активны независимо от приоритета",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "ℹ️ <b>Исправление не требуется</b>\n\nВсе офферы уже активны",
            parse_mode="HTML"
        )


async def migrate_offers_structure(message: Message):
    """Команда /migrate_offers - миграция структуры старых офферов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
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

        # Проверка структуры статуса
        if "status" not in offer:
            offer["status"] = {
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            updated = True

        if updated:
            offer["status"]["updated_at"] = datetime.now().isoformat()
            migrated_count += 1

    if migrated_count > 0:
        save_offers(offers)
        await message.answer(
            f"✅ <b>Миграция завершена!</b>\n\n"
            f"📊 Обновлено офферов: {migrated_count}\n"
            f"💳 Добавлены способы получения и сроки займа",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "ℹ️ <b>Миграция не требуется</b>\n\nВсе офферы уже имеют актуальную структуру",
            parse_mode="HTML"
        )


async def unknown_message(message: Message):
    """Обработчик неизвестных сообщений"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    await message.answer(
        "❓ Неизвестная команда. Используйте /start",
        reply_markup=main_keyboard()
    )


def register_utility_handlers(dp):
    """Регистрирует утилитарные команды"""
    dp.message.register(check_all_offers, Command("check_offers"))
    dp.message.register(fix_inactive_offers, Command("fix_inactive_offers"))
    dp.message.register(migrate_offers_structure, Command("migrate_offers"))
    dp.message.register(unknown_message)  # Должен быть последним