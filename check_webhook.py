#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки webhook и бота
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import config
from telegram.ext import Application

async def check_bot():
    """Проверка работы бота"""
    print("=== Проверка бота ===\n")
    
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()
    bot = application.bot
    
    # Проверяем информацию о боте
    try:
        bot_info = await bot.get_me()
        print(f"✓ Бот подключен")
        print(f"  Имя: {bot_info.first_name}")
        print(f"  Username: @{bot_info.username}")
        print(f"  ID: {bot_info.id}")
    except Exception as e:
        print(f"✗ Ошибка подключения к боту: {e}")
        return False
    
    # Проверяем webhook
    print(f"\n=== Проверка webhook ===")
    try:
        webhook_info = await bot.get_webhook_info()
        print(f"Webhook URL: {webhook_info.url or 'не установлен'}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
        
        if webhook_info.url:
            expected_url = f"{config.BASE_URL}/webhook"
            if webhook_info.url == expected_url:
                print(f"✓ Webhook установлен правильно: {expected_url}")
            else:
                print(f"⚠ Webhook установлен на другой URL:")
                print(f"  Текущий: {webhook_info.url}")
                print(f"  Ожидаемый: {expected_url}")
        else:
            print(f"✗ Webhook не установлен!")
            print(f"  Запустите: python3 setup_webhook.py")
    except Exception as e:
        print(f"✗ Ошибка проверки webhook: {e}")
    
    print("\n=== Конец проверки ===")
    return True

if __name__ == '__main__':
    asyncio.run(check_bot())

