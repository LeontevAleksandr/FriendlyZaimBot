from aiogram.fsm.state import State, StatesGroup


class LoanFlow(StatesGroup):
    """Состояния FSM для максимально простого флоу поиска займов"""

    choosing_country = State()  # Выбор страны (РФ/КЗ)
    choosing_age = State()  # Возраст (18-25, 26-35, 36-50, 51+)
    choosing_amount = State()  # Сумма займа
    choosing_term = State()  # Срок займа (7, 14, 21, 30 дней)
    choosing_payment = State()  # Способ получения
    choosing_zero_percent = State()  # 0% или любые варианты
    viewing_offers = State()  # Просмотр офферов