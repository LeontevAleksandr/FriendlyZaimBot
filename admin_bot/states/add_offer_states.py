"""
FSM состояния для добавления нового оффера
"""
from aiogram.fsm.state import State, StatesGroup


class AddOfferStates(StatesGroup):
    """Состояния для процесса добавления нового оффера"""
    name = State()                  # Название МФО
    countries = State()             # Выбор стран (РФ/КЗ)
    amounts = State()               # Лимиты по сумме займа
    age = State()                   # Возрастные ограничения
    loan_terms = State()            # Сроки займа (min/max дни)
    zero_percent = State()          # Наличие 0% для новых клиентов
    description = State()           # Описание оффера
    russia_link = State()           # Партнерская ссылка для России
    kazakhstan_link = State()       # Партнерская ссылка для Казахстана
    metrics = State()               # CPA метрики (CR, AR, EPC, EPL)
    priority = State()              # Ручной приоритет (множитель)
    payment_methods = State()       # Способы получения средств
    logo = State()                  # Загрузка логотипа МФО