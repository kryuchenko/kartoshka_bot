#!/bin/bash

# Скрипт для автоматического создания systemd службы для Kartoshka Bot

# Функция для отображения сообщений об ошибках
function error_exit {
    echo "$1" 1>&2
    exit 1
}

# Проверка, выполняется ли скрипт с правами root
if [ "$EUID" -ne 0 ]; then
    error_exit "Пожалуйста, запустите скрипт с правами суперпользователя (sudo)."
fi

# Получение текущего пользователя (предполагается, что это владелец проекта)
USER=$(logname)
GROUP=$USER

# Путь к домашней директории пользователя
HOME_DIR=$(eval echo "~$USER")

# Параметры проекта
PROJECT_DIR="$HOME_DIR/projects/kartoshka_bot"
SERVICE_NAME="kartoshka_bot.service"

# Проверка существования директории проекта
if [ ! -d "$PROJECT_DIR" ]; then
    error_exit "Директория проекта не найдена: $PROJECT_DIR"
fi

# Проверка существования виртуального окружения
VENV_DIR="$PROJECT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    error_exit "Виртуальное окружение не найдено: $VENV_DIR"
fi

# Проверка существования файла бота
BOT_SCRIPT="$PROJECT_DIR/kartoshka_bot.py"
if [ ! -f "$BOT_SCRIPT" ]; then
    error_exit "Файл бота не найден: $BOT_SCRIPT"
fi

# Проверка существования файла .env
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    error_exit "Файл переменных окружения не найден: $ENV_FILE"
fi

# Путь к интерпретатору Python в виртуальном окружении
PYTHON_EXEC="$VENV_DIR/bin/python3"
if [ ! -f "$PYTHON_EXEC" ]; then
    error_exit "Интерпретатор Python не найден в виртуальном окружении: $PYTHON_EXEC"
fi

# Путь к файлу службы systemd
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

# Генерация содержимого службы
SERVICE_CONTENT="[Unit]
Description=Kartoshka Bot Telegram Service
After=network.target

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$PYTHON_EXEC $BOT_SCRIPT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"

# Создание файла службы
echo "$SERVICE_CONTENT" > /tmp/$SERVICE_NAME

# Установка правильных прав доступа
chmod 644 /tmp/$SERVICE_NAME

# Перемещение файла службы в директорию systemd
mv /tmp/$SERVICE_NAME "$SERVICE_FILE" || error_exit "Не удалось переместить файл службы в $SERVICE_FILE"

echo "Файл службы $SERVICE_NAME успешно создан."

# Перезагрузка конфигурации systemd
systemctl daemon-reload || error_exit "Не удалось перезагрузить конфигурацию systemd."

# Включение службы для автозапуска при старте системы
systemctl enable "$SERVICE_NAME" || error_exit "Не удалось включить службу $SERVICE_NAME."

# Запуск службы
systemctl start "$SERVICE_NAME" || error_exit "Не удалось запустить службу $SERVICE_NAME."

echo "Служба $SERVICE_NAME успешно запущена и включена для автозапуска."

# Вывод статуса службы
systemctl status "$SERVICE_NAME" --no-pager
