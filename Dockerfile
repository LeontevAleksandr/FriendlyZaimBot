# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда запуска будет определяться через docker-compose
