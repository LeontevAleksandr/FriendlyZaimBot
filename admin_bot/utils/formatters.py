"""
Форматтеры для отображения данных в админском боте
"""
from typing import Dict, List
from datetime import datetime

from ..config.constants import PAYMENT_METHODS


def escape_html(text: str) -> str:
    """Экранирует специальные HTML символы"""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def format_payment_methods(methods: List[str]) -> str:
    """Форматирует список способов получения средств"""
    if not methods:
        return "❌ Не указаны"
    if len(methods) == len(PAYMENT_METHODS):
        return "✅ Все способы доступны"
    return "\n".join(f"   • {PAYMENT_METHODS[m]['name']}" for m in methods if m in PAYMENT_METHODS)


def format_offer_info(offer: Dict, offer_id: str) -> str:
    """Форматирует полную информацию об оффере с защитой от HTML"""
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
        epc_currency = "₽/₸"
        epl_currency = "₽/₸"
    elif has_kazakhstan:
        currency_text = f"{offer['limits']['min_amount']:,} - {offer['limits']['max_amount']:,} ₸"
        epc_currency = "₸"
        epl_currency = "₸"
    else:
        currency_text = f"{offer['limits']['min_amount']:,} - {offer['limits']['max_amount']:,} ₽"
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

    # Форматирование дат
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
            except Exception:
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


def format_currency_icon(countries: List[str]) -> str:
    """Возвращает иконку валюты на основе списка стран"""
    if 'russia' in countries and 'kazakhstan' in countries:
        return "₽/₸"
    elif 'kazakhstan' in countries:
        return "₸"
    else:
        return "₽"