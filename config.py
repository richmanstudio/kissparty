# -*- coding: utf-8 -*-
"""
Конфигурация бота KISS PARTY PAY BOT
"""

import os

# Telegram Bot Token
BOT_TOKEN = "8444807494:AAH1_NlMCFaxdvPs6IxsbYohbYBE7x5uUiY"

# Robokassa настройки
ROBOKASSA_MERCHANT_LOGIN = "kisspartypay1"
ROBOKASSA_PASSWORD1 = "LdEx8GdI3ZGyvnhkE020"
ROBOKASSA_PASSWORD2 = "p7TdoF7W64incwJgf1xk"
ROBOKASSA_TEST_MODE = False

# Базовый URL сайта
BASE_URL = "https://cw998871.tw1.ru/KISSPARTYPAYMAIN"

# Админы бота
# Чтобы добавить нового админа, добавьте его user_id в этот список
# Как узнать user_id: попросите пользователя написать боту @userinfobot
# Пример: ADMIN_USERS = [875068919, 728776547, 123456789]
ADMIN_USERS = [728776547, 7888551788, 875068919]

# Каналы для проверки подписки
CHANNELS_TO_CHECK = ['@kisssparty']

# Настройки базы данных MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'cw998871_kisspar',
    'password': 'P5V8yaRJ',
    'database': 'cw998871_kisspar',
    'charset': 'utf8mb4',
    'autocommit': True
}

# Лимиты билетов
TICKET_LIMITS = {
    'regular': 600,
    'vip': 80,
    'vip_standing': 20,
    'couple': 50
}

# Процент бонусов от покупки
BONUS_PERCENT = 0.05  # 5%

# Реферальный бонус
REFERRAL_BONUS = 50

# Максимальный процент использования бонусов от стоимости билета
MAX_BONUS_USAGE_PERCENT = 0.5  # 50%

# Скидка за количество билетов (5+ билетов)
QUANTITY_DISCOUNT_PERCENT = 0.1  # 10%
QUANTITY_DISCOUNT_MIN = 5

# Секрет для подписи QR-кодов
QR_SECRET = "KISS_SECRET_2024"

# Путь для временных файлов
TEMP_DIR = os.path.join(os.path.dirname(__file__), "tmp")

# Секрет для доступа к сканеру билетов (можно переопределить через переменную окружения QR_SCANNER_TOKEN)
QR_SCANNER_TOKEN = os.getenv('QR_SCANNER_TOKEN', 'kissscanner_secret')

# Логирование
LOG_FILE = os.path.join(os.path.dirname(__file__), "bot.log")  # Лог в директории проекта
LOG_LEVEL = "INFO"

# Порт для Flask сервера
FLASK_PORT = 5001  # Можно изменить, если порт занят

# Реквизиты для ручной оплаты
PAYMENT_CARD_NUMBER = "2200246125113418"

