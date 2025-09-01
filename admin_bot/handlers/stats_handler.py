"""
Обработчики для отображения статистики системы
"""
import logging
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from admin_bot.config.auth import is_admin
from admin_bot.config.constants import PAYMENT_METHODS
from admin_bot.utils.offer_manager import load_offers
from admin_bot.utils.formatters import escape_html
from admin_bot.utils.message_utils import safe_edit_message

logger = logging.getLogger(__name__)


async def show_stats(callback: CallbackQuery):
    """Показать статистику системы"""
    if not is_admin(callback.from_user.id):
        return

    try:
        offers = load_offers()
        microloans = offers.get("microloans", {})

        # Базовая статистика
        total_offers = len(microloans)
        active_offers = sum(1 for offer in microloans.values()
                            if offer.get('status', {}).get('is_active', True))
        inactive_offers = total_offers - active_offers

        # Средние метрики
        if total_offers > 0:
            avg_cr = sum(offer.get('metrics', {}).get('cr', 0) for offer in microloans.values()) / total_offers
            avg_ar = sum(offer.get('metrics', {}).get('ar', 0) for offer in microloans.values()) / total_offers
            avg_epc = sum(offer.get('metrics', {}).get('epc', 0) for offer in microloans.values()) / total_offers
            avg_epl = sum(offer.get('metrics', {}).get('epl', 0) for offer in microloans.values()) / total_offers
        else:
            avg_cr = avg_ar = avg_epc = avg_epl = 0

        # ТОП офферы по CR
        top_offers = sorted(
            [(offer_id, offer) for offer_id, offer in microloans.items()],
            key=lambda x: x[1].get('metrics', {}).get('cr', 0),
            reverse=True
        )[:3]

        if top_offers:
            top_text = "\n".join(
                f"{i}. {escape_html(offer['name'])}: {offer.get('metrics', {}).get('cr', 0)}%"
                for i, (_, offer) in enumerate(top_offers, 1)
            )
        else:
            top_text = "Нет данных"

        # Статистика способов получения
        payment_stats = {}
        for offer in microloans.values():
            for method in offer.get('payment_methods', []):
                if method in PAYMENT_METHODS:
                    payment_stats[method] = payment_stats.get(method, 0) + 1

        if payment_stats:
            payment_stats_text = "\n".join(
                f"{PAYMENT_METHODS[method_id]['emoji']} "
                f"{PAYMENT_METHODS[method_id]['name'].replace(PAYMENT_METHODS[method_id]['emoji'] + ' ', '')}: {count}"
                for method_id, count in sorted(payment_stats.items(), key=lambda x: x[1], reverse=True)
            )
        else:
            payment_stats_text = "Нет данных"

        # Статистика стран
        country_stats = {"russia": 0, "kazakhstan": 0, "both": 0}
        for offer in microloans.values():
            countries = offer.get('geography', {}).get('countries', [])
            if 'russia' in countries and 'kazakhstan' in countries:
                country_stats["both"] += 1
            elif 'russia' in countries:
                country_stats["russia"] += 1
            elif 'kazakhstan' in countries:
                country_stats["kazakhstan"] += 1

        # Статистика 0% предложений
        zero_percent_count = sum(1 for offer in microloans.values()
                                 if offer.get('zero_percent', False))

        # Статистика логотипов
        with_logo_count = sum(1 for offer in microloans.values()
                              if offer.get('logo'))

        text = (
            f"📊 <b>Статистика системы</b>\n\n"
            f"📋 <b>Офферы:</b>\n"
            f"   • Всего: {total_offers}\n"
            f"   • Активных: {active_offers}\n"
            f"   • Неактивных: {inactive_offers}\n\n"
            f"🌍 <b>География:</b>\n"
            f"   • 🇷🇺 Только Россия: {country_stats['russia']}\n"
            f"   • 🇰🇿 Только Казахстан: {country_stats['kazakhstan']}\n"
            f"   • 🌍 Обе страны: {country_stats['both']}\n\n"
            f"📈 <b>Средние метрики:</b>\n"
            f"   • CR: {avg_cr:.1f}%\n"
            f"   • AR: {avg_ar:.1f}%\n"
            f"   • EPC: {avg_epc:.1f} ₽\n"
            f"   • EPL: {avg_epl:.1f} ₽\n\n"
            f"🏆 <b>ТОП по CR:</b>\n{top_text}\n\n"
            f"🎯 <b>Дополнительно:</b>\n"
            f"   • 0% предложений: {zero_percent_count}\n"
            f"   • С логотипами: {with_logo_count}\n\n"
            f"💳 <b>Способы получения:</b>\n{payment_stats_text}"
        )

        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])

        await safe_edit_message(callback.message, text, reply_markup=back_keyboard)

    except Exception as e:
        logger.error(f"Ошибка в show_stats: {e}")
        await callback.answer("❌ Ошибка загрузки статистики")


def register_stats_handlers(dp):
    """Регистрирует обработчики статистики"""
    dp.callback_query.register(show_stats, F.data == "stats")