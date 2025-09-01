import os

# Получение списка админов из переменных окружения
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '123456789').split(',')]


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS