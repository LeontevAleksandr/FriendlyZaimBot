"""
FSM состояния для редактирования офферов
"""
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    """Состояния для редактирования существующих офферов"""
    waiting_value = State()         # Ожидание нового значения для поля


class PaymentMethodsStates(StatesGroup):
    """Состояния для выбора способов получения средств"""
    selecting = State()             # Процесс выбора способов оплаты