#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для установки webhook Telegram бота
Используйте этот скрипт для установки webhook отдельно от основного приложения
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

import config
from telegram.ext import Application

async def setup_webhook():
    """Установить webhook для бота"""
    application = Application.builder().token(config.BOT_TOKEN).build()
    bot = application.bot
    
    webhook_url = f"{config.BASE_URL}/webhook"
    print(f"Устанавливаю webhook: {webhook_url}")
    
    result = await bot.set_webhook(webhook_url)
    
    if result:
        print(f"✅ Webhook успешно установлен: {webhook_url}")
    else:
        print(f"❌ Ошибка при установке webhook")
    
    return result

if __name__ == '__main__':
    asyncio.run(setup_webhook())

