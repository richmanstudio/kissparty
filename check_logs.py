#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки логов и диагностики проблем
"""

import os
import sys

print("=" * 60)
print("Проверка логов и диагностика")
print("=" * 60)

# Проверяем bot.log
bot_log = os.path.join(os.path.dirname(__file__), "bot.log")
print(f"\n1. Проверка bot.log:")
print(f"   Путь: {bot_log}")
if os.path.exists(bot_log):
    print(f"   ✅ Файл существует")
    size = os.path.getsize(bot_log)
    print(f"   Размер: {size} байт")
    if size > 0:
        print(f"   Последние 20 строк:")
        with open(bot_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(f"   {line.rstrip()}")
    else:
        print(f"   ⚠️ Файл пуст")
else:
    print(f"   ❌ Файл не существует")

# Проверяем wsgi_error.log
wsgi_log = os.path.join(os.path.dirname(__file__), "wsgi_error.log")
print(f"\n2. Проверка wsgi_error.log:")
print(f"   Путь: {wsgi_log}")
if os.path.exists(wsgi_log):
    print(f"   ✅ Файл существует")
    size = os.path.getsize(wsgi_log)
    print(f"   Размер: {size} байт")
    if size > 0:
        print(f"   Последние 20 строк:")
        with open(wsgi_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(f"   {line.rstrip()}")
    else:
        print(f"   ⚠️ Файл пуст")
else:
    print(f"   ❌ Файл не существует")

# Проверяем права доступа
print(f"\n3. Проверка прав доступа:")
current_dir = os.path.dirname(__file__)
print(f"   Текущая директория: {current_dir}")
print(f"   Права на директорию: {oct(os.stat(current_dir).st_mode)[-3:]}")
if os.path.exists(bot_log):
    print(f"   Права на bot.log: {oct(os.stat(bot_log).st_mode)[-3:]}")
if os.path.exists(wsgi_log):
    print(f"   Права на wsgi_error.log: {oct(os.stat(wsgi_log).st_mode)[-3:]}")

# Проверяем конфигурацию
print(f"\n4. Проверка конфигурации:")
try:
    import config
    print(f"   LOG_FILE: {config.LOG_FILE}")
    print(f"   LOG_FILE существует: {os.path.exists(config.LOG_FILE)}")
except Exception as e:
    print(f"   ❌ Ошибка импорта config: {e}")

print("\n" + "=" * 60)
print("Для просмотра логов в реальном времени используйте:")
print(f"  tail -f {bot_log}")
print(f"  tail -f {wsgi_log}")
print("=" * 60)

