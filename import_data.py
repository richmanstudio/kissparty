#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для импорта данных из txt файлов в MySQL базу данных
"""

import json
import os
import sys
from pathlib import Path

def parse_json_lines(file_path):
    """Парсит файл с JSON объектами, разделенными переносами строк"""
    data = []
    if not os.path.exists(file_path):
        return data
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Разделяем по строкам
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Пытаемся найти все JSON объекты в строке
            start = 0
            while start < len(line):
                if line[start] == '{':
                    depth = 0
                    end = start
                    for i in range(start, len(line)):
                        if line[i] == '{':
                            depth += 1
                        elif line[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    if end > start:
                        try:
                            obj = json.loads(line[start:end])
                            data.append(obj)
                        except:
                            pass
                        start = end
                    else:
                        break
                else:
                    start += 1
    return data

def escape_sql(value):
    """Экранирует значение для SQL"""
    if value is None:
        return 'NULL'
    if isinstance(value, str):
        return "'" + value.replace("'", "''").replace("\\", "\\\\") + "'"
    return str(value)

def generate_sql_inserts():
    """Генерирует SQL INSERT запросы из txt файлов"""
    
    base_path = Path(__file__).parent.parent / 'data'
    sql_lines = []
    
    sql_lines.append("-- SQL дамп данных для импорта в MySQL")
    sql_lines.append("-- Использование: импортируйте этот файл в phpMyAdmin")
    sql_lines.append("")
    sql_lines.append("SET FOREIGN_KEY_CHECKS=0;")
    sql_lines.append("")
    
    # Импорт бонусов
    bonuses_file = base_path / 'bonuses.txt'
    if bonuses_file.exists():
        bonuses = parse_json_lines(bonuses_file)
        if bonuses:
            sql_lines.append("-- Импорт бонусов")
            for bonus in bonuses:
                user_id = bonus.get('user_id', 0)
                balance = bonus.get('bonus_balance', 0)
                last_updated = bonus.get('last_updated', 'CURRENT_TIMESTAMP')
                last_order_id = bonus.get('last_order_id')
                
                sql = f"INSERT INTO `bonuses` (`user_id`, `bonus_balance`, `last_updated`, `last_order_id`) VALUES ({user_id}, {balance}, {escape_sql(last_updated)}, {escape_sql(last_order_id)}) ON DUPLICATE KEY UPDATE `bonus_balance`=VALUES(`bonus_balance`), `last_updated`=VALUES(`last_updated`), `last_order_id`=VALUES(`last_order_id`);"
                sql_lines.append(sql)
            sql_lines.append("")
    
    # Импорт рефералов
    referrals_file = base_path / 'referrals.txt'
    if referrals_file.exists():
        referrals = parse_json_lines(referrals_file)
        if referrals:
            sql_lines.append("-- Импорт рефералов")
            seen = set()
            for ref in referrals:
                user_id = ref.get('user_id', 0)
                if user_id == 0 or user_id in seen:
                    continue
                seen.add(user_id)
                
                referral_code = ref.get('referral_code', '')
                referrer_id = ref.get('referrer_id', '')
                referrals_count = ref.get('referrals_count', 0)
                referral_earnings = ref.get('referral_earnings', 0)
                referral_bonus_paid = 1 if ref.get('referral_bonus_paid', False) else 0
                first_purchase_discount_applied = 1 if ref.get('first_purchase_discount_applied', False) else 0
                first_purchase_date = ref.get('first_purchase_date')
                created_at = ref.get('created_at', 'CURRENT_TIMESTAMP')
                
                referrer_id_sql = 'NULL' if not referrer_id or referrer_id == '' else str(referrer_id)
                
                sql = f"INSERT INTO `referrals` (`user_id`, `referral_code`, `referrer_id`, `referrals_count`, `referral_earnings`, `referral_bonus_paid`, `first_purchase_discount_applied`, `first_purchase_date`, `created_at`) VALUES ({user_id}, {escape_sql(referral_code)}, {referrer_id_sql}, {referrals_count}, {referral_earnings}, {referral_bonus_paid}, {first_purchase_discount_applied}, {escape_sql(first_purchase_date)}, {escape_sql(created_at)}) ON DUPLICATE KEY UPDATE `referral_code`=VALUES(`referral_code`), `referrer_id`=VALUES(`referrer_id`), `referrals_count`=VALUES(`referrals_count`), `referral_earnings`=VALUES(`referral_earnings`);"
                sql_lines.append(sql)
            sql_lines.append("")
    
    # Импорт промокодов
    promocodes_file = base_path / 'promocodes.txt'
    if promocodes_file.exists():
        promocodes = parse_json_lines(promocodes_file)
        if promocodes:
            sql_lines.append("-- Импорт промокодов")
            for promo in promocodes:
                code = promo.get('code', '')
                name = promo.get('name', '')
                promo_type = promo.get('type', 'percentage')
                value = promo.get('value', 0)
                ticket_types = promo.get('ticket_types', [])
                start_date = promo.get('start_date')
                end_date = promo.get('end_date')
                max_uses = promo.get('max_uses', 0)
                used_count = promo.get('used_count', 0)
                active = 1 if promo.get('active', True) else 0
                min_amount = promo.get('min_amount', 0)
                notes = promo.get('notes', '')
                created_at = promo.get('created_at', 'CURRENT_TIMESTAMP')
                
                ticket_types_json = json.dumps(ticket_types, ensure_ascii=False)
                
                sql = f"INSERT INTO `promocodes` (`code`, `name`, `type`, `value`, `ticket_types`, `start_date`, `end_date`, `max_uses`, `used_count`, `active`, `min_amount`, `notes`, `created_at`) VALUES ({escape_sql(code)}, {escape_sql(name)}, {escape_sql(promo_type)}, {value}, {escape_sql(ticket_types_json)}, {escape_sql(start_date)}, {escape_sql(end_date)}, {max_uses}, {used_count}, {active}, {min_amount}, {escape_sql(notes)}, {escape_sql(created_at)}) ON DUPLICATE KEY UPDATE `name`=VALUES(`name`), `type`=VALUES(`type`), `value`=VALUES(`value`), `ticket_types`=VALUES(`ticket_types`), `start_date`=VALUES(`start_date`), `end_date`=VALUES(`end_date`), `max_uses`=VALUES(`max_uses`), `used_count`=VALUES(`used_count`), `active`=VALUES(`active`), `min_amount`=VALUES(`min_amount`), `notes`=VALUES(`notes`);"
                sql_lines.append(sql)
            sql_lines.append("")
    
    # Импорт ролей
    roles_file = base_path / 'roles.txt'
    if roles_file.exists():
        roles = parse_json_lines(roles_file)
        if roles:
            sql_lines.append("-- Импорт пользователей и ролей")
            for role_data in roles:
                user_id = role_data.get('user_id', 0)
                if user_id == 0:
                    continue
                
                role = role_data.get('role', 'user')
                promo_code = role_data.get('promo_code', '')
                created_at = role_data.get('created_at', 'CURRENT_TIMESTAMP')
                updated_at = role_data.get('updated_at', 'CURRENT_TIMESTAMP')
                
                sql = f"INSERT INTO `users` (`user_id`, `role`, `promo_code`, `created_at`, `updated_at`) VALUES ({user_id}, {escape_sql(role)}, {escape_sql(promo_code)}, {escape_sql(created_at)}, {escape_sql(updated_at)}) ON DUPLICATE KEY UPDATE `role`=VALUES(`role`), `promo_code`=VALUES(`promo_code`), `updated_at`=VALUES(`updated_at`);"
                sql_lines.append(sql)
            sql_lines.append("")
    
    # Импорт промо-билетов
    promo_tickets_file = base_path / 'promo_tickets.txt'
    if promo_tickets_file.exists():
        promo_tickets = parse_json_lines(promo_tickets_file)
        if promo_tickets:
            sql_lines.append("-- Импорт промо-билетов")
            for pt in promo_tickets:
                code = pt.get('code', '')
                ticket_type = pt.get('ticket_type', 'regular')
                purpose = pt.get('purpose', '')
                notes = pt.get('notes', '')
                status = pt.get('status', 'active')
                used_by = pt.get('used_by')
                used_at = pt.get('used_at')
                created_at = pt.get('created_at', 'CURRENT_TIMESTAMP')
                
                used_by_sql = 'NULL' if used_by is None else str(used_by)
                
                sql = f"INSERT INTO `promo_tickets` (`code`, `ticket_type`, `purpose`, `notes`, `status`, `used_by`, `used_at`, `created_at`) VALUES ({escape_sql(code)}, {escape_sql(ticket_type)}, {escape_sql(purpose)}, {escape_sql(notes)}, {escape_sql(status)}, {used_by_sql}, {escape_sql(used_at)}, {escape_sql(created_at)}) ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `used_by`=VALUES(`used_by`), `used_at`=VALUES(`used_at`);"
                sql_lines.append(sql)
            sql_lines.append("")
    
    # Импорт настроек цен
    price_settings_file = base_path / 'price_settings.txt'
    if price_settings_file.exists():
        try:
            with open(price_settings_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    prices = json.loads(content)
                    sql_lines.append("-- Импорт настроек цен")
                    for ticket_type, price_data in prices.items():
                        base_price = price_data.get('base', 0)
                        discounted_price = price_data.get('discounted', 0)
                        sql = f"INSERT INTO `price_settings` (`ticket_type`, `base_price`, `discounted_price`) VALUES ({escape_sql(ticket_type)}, {base_price}, {discounted_price}) ON DUPLICATE KEY UPDATE `base_price`=VALUES(`base_price`), `discounted_price`=VALUES(`discounted_price`);"
                        sql_lines.append(sql)
                    sql_lines.append("")
        except:
            pass
    
    sql_lines.append("SET FOREIGN_KEY_CHECKS=1;")
    
    # Сохраняем в файл
    output_file = Path(__file__).parent / 'data_import.sql'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_lines))
    
    print(f"SQL дамп создан: {output_file}")
    print(f"Всего строк SQL: {len(sql_lines)}")

if __name__ == '__main__':
    generate_sql_inserts()

