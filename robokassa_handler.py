# -*- coding: utf-8 -*-
"""
Обработчик платежей Robokassa
"""

import logging
import hashlib
from datetime import datetime
from typing import Dict, Any
import database as db
import config
from qr_generator import generate_qr_code
from telegram import Bot
import asyncio

logger = logging.getLogger(__name__)
bot = Bot(token=config.BOT_TOKEN)

def verify_robokassa_signature(out_sum_raw: str, inv_id: str, received_sign: str, shp_params: Dict[str, str]) -> bool:
    """Проверить подпись Robokassa"""
    # Сортируем shp параметры по алфавиту
    sorted_shp = sorted([(k, v) for k, v in shp_params.items() if k.startswith('Shp_')])
    
    # Формируем строку параметров
    shp_string_parts = [f"{k}={v}" for k, v in sorted_shp]
    shp_string = ':'.join(shp_string_parts)
    
    # Формируем строку для подписи
    signature_string = f"{out_sum_raw}:{inv_id}:{config.ROBOKASSA_PASSWORD2}"
    if shp_string:
        signature_string += f":{shp_string}"
    
    calculated_sign = hashlib.md5(signature_string.encode()).hexdigest().upper()
    received_sign = received_sign.upper()
    
    logger.info(f"Signature check: calculated={calculated_sign}, received={received_sign}")
    
    return calculated_sign == received_sign

def process_payment_callback(data: Dict[str, Any]) -> str:
    """Обработать callback от Robokassa"""
    try:
        logger.info(f"Payment callback received: {data}")
        
        # Получаем данные
        out_sum_raw = data.get('OutSum', '0')
        out_sum = float(out_sum_raw)
        inv_id = data.get('InvId', '')
        received_sign = data.get('SignatureValue', '')
        
        # Собираем shp параметры
        shp_params = {k: v for k, v in data.items() if k.startswith('Shp_')}
        
        user_id = int(shp_params.get('Shp_user_id', 0))
        ticket_type = shp_params.get('Shp_ticket_type', '')
        bonus_used = float(shp_params.get('Shp_bonus_used', 0))
        promo_code = shp_params.get('Shp_promo_code', '')
        ticket_quantity = int(shp_params.get('Shp_ticket_quantity', 1))
        
        # Проверяем обязательные поля
        if not all([out_sum, inv_id, received_sign, user_id]):
            raise ValueError("Missing required parameters")
        
        # Проверяем, не обработан ли уже заказ
        existing_ticket = db.execute_query(
            "SELECT * FROM tickets WHERE order_id = %s LIMIT 1",
            (inv_id,),
            fetch=True
        )
        if existing_ticket:
            logger.info(f"Order {inv_id} already processed")
            return f"OK{inv_id}"
        
        # Проверяем подпись
        if not verify_robokassa_signature(out_sum_raw, inv_id, received_sign, shp_params):
            raise ValueError("Invalid signature")
        
        logger.info(f"Payment verified for user {user_id}, order {inv_id}")
        
        # Начисляем бонусы (5% от суммы)
        bonus_earned = round(out_sum * config.BONUS_PERCENT)
        new_bonus_balance = db.update_user_bonuses(user_id, bonus_earned, 'add', inv_id)
        
        # Обрабатываем реферальные бонусы
        referral_bonus_earned = process_referral_bonus(user_id, out_sum)
        
        # Увеличиваем счетчик использования промокода
        if promo_code:
            db.increment_promocode_usage(promo_code)
        
        # Генерируем базовый код
        date_str = datetime.now().strftime('%Y%m%d')
        code_hash = hashlib.md5(f"{inv_id}{user_id}".encode()).hexdigest()[:6].upper()
        
        if ticket_type == 'vip':
            base_code = f"VIP-{date_str}-{code_hash}"
        elif ticket_type == 'vip_standing':
            base_code = f"VPS-{date_str}-{code_hash}"
        elif ticket_type == 'couple':
            base_code = f"CPL-{date_str}-{code_hash}"
        else:
            base_code = f"TKT-{date_str}-{code_hash}"
        
        # Создаем билеты
        price_per_ticket = out_sum / ticket_quantity
        all_tickets = []
        
        # Загружаем выбранные места для VIP билетов
        selected_seats = None
        if ticket_type == 'vip':
            selection = db.get_user_seat_selection(user_id)
            if selection:
                import json
                selected_seats = json.loads(selection['selected_seats'])
        
        for i in range(1, ticket_quantity + 1):
            ticket_code = base_code if ticket_quantity == 1 else f"{base_code}-{i}"
            
            ticket_data = {
                'ticket_code': ticket_code,
                'user_id': user_id,
                'ticket_type': ticket_type,
                'amount': price_per_ticket,
                'bonus_used': bonus_used / ticket_quantity,
                'bonus_earned': bonus_earned / ticket_quantity,
                'referral_bonus_earned': referral_bonus_earned / ticket_quantity,
                'promo_code': promo_code,
                'order_id': inv_id,
                'status': 'active'
            }
            
            db.create_ticket(ticket_data)
            all_tickets.append(ticket_data)
            
            # Назначаем место билету, если есть выбранные места
            if selected_seats and i <= len(selected_seats):
                seat_index = (i - 1) % len(selected_seats)
                selected_seat = selected_seats[seat_index]
                
                # Обновляем билет с информацией о месте
                db.execute_query(
                    """UPDATE tickets 
                       SET seat_floor = %s, seat_section = %s, seat_number = %s, seat_row = %s
                       WHERE ticket_code = %s""",
                    (
                        selected_seat['floor'],
                        selected_seat['section'],
                        selected_seat['seat_number'],
                        selected_seat.get('row'),
                        ticket_code
                    )
                )
        
        # Удаляем временную запись после обработки всех билетов
        if selected_seats:
            db.delete_user_seat_selection(user_id)
        
        # Увеличиваем счетчик проданных билетов в категории
        try:
            db.increment_ticket_category_sold(ticket_type, ticket_quantity)
        except Exception as e:
            logger.error(f"Error incrementing category sold count: {e}")
        
        # Отправляем QR-коды пользователю
        send_tickets_to_user(user_id, all_tickets, out_sum, bonus_used, bonus_earned, 
                           referral_bonus_earned, new_bonus_balance, promo_code, ticket_type, ticket_quantity)
        
        # Уведомляем админов
        notify_admins(user_id, ticket_type, ticket_quantity, out_sum, inv_id, promo_code)
        
        return f"OK{inv_id}"
        
    except Exception as e:
        logger.error(f"Error processing payment: {e}", exc_info=True)
        # Уведомляем админов об ошибке
        error_message = f"❌ ОШИБКА ОБРАБОТКИ ПЛАТЕЖА\n\nЗаказ: {data.get('InvId', 'неизвестен')}\nОшибка: {str(e)}"
        async def send_error_notifications():
            for admin_id in config.ADMIN_USERS:
                try:
                    await bot.send_message(chat_id=admin_id, text=error_message, parse_mode='HTML')
                except:
                    pass
        asyncio.run(send_error_notifications())
        raise

def process_referral_bonus(referred_user_id: int, purchase_amount: float) -> float:
    """Обработать реферальный бонус"""
    ref_data = db.get_referral_data(referred_user_id)
    
    if not ref_data.get('referrer_id') or ref_data.get('referral_bonus_paid'):
        return 0.0
    
    referrer_id = ref_data['referrer_id']
    referral_bonus = config.REFERRAL_BONUS
    
    # Начисляем бонусы рефереру
    referrer_new_balance = db.update_user_bonuses(referrer_id, referral_bonus, 'add', f'ref_{referred_user_id}')
    
    # Начисляем бонусы рефералу
    referred_new_balance = db.update_user_bonuses(referred_user_id, referral_bonus, 'add', 'ref_bonus_first_purchase')
    
    # Обновляем статистику
    referrer_ref_data = db.get_referral_data(referrer_id)
    db.update_referral_stats(
        referrer_id,
        referrals_count=referrer_ref_data.get('referrals_count', 0) + 1,
        referral_earnings=referrer_ref_data.get('referral_earnings', 0) + referral_bonus
    )
    
    # Отмечаем что бонусы начислены
    db.update_referral_stats(
        referred_user_id,
        referral_bonus_paid=True,
        first_purchase_discount_applied=True,
        first_purchase_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    # Отправляем уведомления
    async def send_notifications():
        try:
            referrer_notification = f"""🎉 <b>Ваш реферал совершил покупку!</b>

👤 Реферал: ID {referred_user_id}
💰 Сумма покупки: {purchase_amount} руб.
💎 <b>Вам начислено {referral_bonus} бонусов!</b>

🏆 Ваш баланс бонусов: {referrer_new_balance}"""
            await bot.send_message(chat_id=referrer_id, text=referrer_notification, parse_mode='HTML')
            
            referred_notification = f"""🎉 <b>Реферальный бонус!</b>

✅ Вы совершили первую покупку по реферальной ссылке!
💎 <b>Вам начислено {referral_bonus} бонусов!</b>

🏆 Ваш баланс бонусов: {referred_new_balance}"""
            await bot.send_message(chat_id=referred_user_id, text=referred_notification, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error sending referral notifications: {e}")
    
    asyncio.run(send_notifications())
    
    return referral_bonus

async def send_tickets_to_user_async(user_id: int, tickets: list, total_amount: float, bonus_used: float,
                        bonus_earned: float, referral_bonus: float, new_balance: float,
                        promo_code: str, ticket_type: str, quantity: int):
    """Отправить билеты пользователю (async)"""
    import os
    import asyncio
    
    ticket_type_names = {
        'vip': 'VIP БИЛЕТ',
        'vip_standing': 'VIP (СТОЯЧИЙ)',
        'couple': 'ПАРНЫЙ БИЛЕТ',
        'regular': 'ОБЫЧНЫЙ БИЛЕТ'
    }
    
    ticket_name = ticket_type_names.get(ticket_type, 'БИЛЕТ')
    
    for i, ticket_data in enumerate(tickets):
        ticket_num = i + 1
        
        # Генерируем QR-код
        qr_path = generate_qr_code(ticket_data)
        
        # Формируем сообщение
        caption = f"🎫 <b>{ticket_name} {ticket_num} из {quantity} АКТИВИРОВАН!</b>\n\n"
        
        if ticket_num == 1:
            caption += f"✅ <b>Платеж подтвержден</b>\n"
            caption += f"💰 <b>Сумма:</b> {total_amount} руб.\n"
            if bonus_used > 0:
                caption += f"🎁 <b>Использовано бонусов:</b> {bonus_used} руб.\n"
            caption += f"💎 <b>Начислено бонусов:</b> +{bonus_earned} (5% от платежа)\n"
            if referral_bonus > 0:
                caption += f"👥 <b>Реферальный бонус:</b> +{referral_bonus}\n"
            caption += f"🏆 <b>Баланс бонусов:</b> {new_balance}\n\n"
            if promo_code:
                caption += f"🔑 <b>Промокод:</b> {promo_code}\n\n"
        
        caption += f"🎫 <b>Код билета:</b> <code>{ticket_data['ticket_code']}</code>\n\n"
        caption += f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        caption += "<i>Сохраните этот QR-код для входа!</i>"
        
        # Отправляем фото
        if qr_path and os.path.exists(qr_path):
            try:
                with open(qr_path, 'rb') as photo:
                    result = await bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    # Сохраняем file_id
                    if result.photo:
                        qr_file_id = result.photo[-1].file_id
                        db.execute_query(
                            "UPDATE tickets SET qr_file_id = %s WHERE ticket_code = %s",
                            (qr_file_id, ticket_data['ticket_code'])
                        )
                os.remove(qr_path)
                await asyncio.sleep(0.5)  # Задержка между отправками
            except Exception as e:
                logger.error(f"Error sending ticket {ticket_num}: {e}")
                await bot.send_message(chat_id=user_id, text=caption + "\n\n⚠️ QR-код не удалось отправить, но билет активен.", parse_mode='HTML')
        else:
            await bot.send_message(chat_id=user_id, text=caption + "\n\n⚠️ QR-код не удалось сгенерировать, но билет активен.", parse_mode='HTML')
    
    # Финальное сообщение
    final_message = f"""✅ <b>Платеж успешно завершен!</b>

🎫 <b>Все {quantity} билетов активировано</b>
💰 <b>Сумма:</b> {total_amount} руб.
💎 <b>Начислено бонусов:</b> +{bonus_earned}
🏆 <b>Баланс бонусов:</b> {new_balance}

📞 <b>По вопросам:</b> @kissmngr

<i>QR-коды билетов отправлены выше. Сохраните их для входа!</i>"""
    
    await bot.send_message(chat_id=user_id, text=final_message, parse_mode='HTML')

def send_tickets_to_user(user_id: int, tickets: list, total_amount: float, bonus_used: float,
                        bonus_earned: float, referral_bonus: float, new_balance: float,
                        promo_code: str, ticket_type: str, quantity: int):
    """Отправить билеты пользователю (sync wrapper)"""
    asyncio.run(send_tickets_to_user_async(user_id, tickets, total_amount, bonus_used,
                                          bonus_earned, referral_bonus, new_balance,
                                          promo_code, ticket_type, quantity))

def notify_admins(user_id: int, ticket_type: str, quantity: int, amount: float, 
                 order_id: str, promo_code: str = None):
    """Уведомить админов о новом заказе"""
    ticket_type_names = {
        'vip': 'VIP',
        'vip_standing': 'VIP (Стоячий)',
        'couple': 'Парный',
        'regular': 'Обычный'
    }
    
    try:
        user = db.get_user(user_id)
        username = user.get('username', 'не указан') if user else 'не указан'
        first_name = user.get('first_name', '') if user else ''
        last_name = user.get('last_name', '') if user else ''
        full_name = f"{first_name} {last_name}".strip() if (first_name or last_name) else 'не указано'
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        username = 'не указан'
        full_name = 'не указано'
    
    # Получаем информацию о билетах
    try:
        tickets = db.execute_query(
            "SELECT ticket_code FROM tickets WHERE order_id = %s ORDER BY ticket_code",
            (order_id,),
            fetch=True
        )
        ticket_codes = [t['ticket_code'] for t in tickets] if tickets else []
    except Exception as e:
        logger.error(f"Error getting ticket codes: {e}")
        ticket_codes = []
    
    message = f"""🎉 <b>НОВЫЙ ЗАКАЗ БИЛЕТОВ!</b>

👤 <b>Пользователь:</b> ID {user_id}
📛 <b>Имя:</b> {full_name}
🔗 <b>Username:</b> @{username}
💎 <b>Тип билета:</b> {ticket_type_names.get(ticket_type, ticket_type)}
📦 <b>Количество:</b> {quantity} билетов
💰 <b>Сумма:</b> {amount:.2f} руб.
🔖 <b>Номер заказа:</b> {order_id}"""
    
    if promo_code:
        message += f"\n🔑 <b>Промокод:</b> {promo_code}"
    
    if ticket_codes:
        codes_text = ', '.join(ticket_codes[:5])  # Показываем первые 5 кодов
        if len(ticket_codes) > 5:
            codes_text += f" ... (всего {len(ticket_codes)})"
        message += f"\n🎫 <b>Коды билетов:</b> {codes_text}"
    
    message += "\n\n✅ <b>Все билеты созданы и отправлены пользователю</b>"
    
    async def send_admin_notifications():
        # Получаем всех админов (из config и из базы данных)
        admin_ids = set(config.ADMIN_USERS)
        
        # Добавляем админов из базы данных
        try:
            admin_users = db.execute_query(
                "SELECT user_id FROM users WHERE role = 'admin'",
                fetch=True
            )
            if admin_users:
                for admin in admin_users:
                    admin_ids.add(admin['user_id'])
        except Exception as e:
            logger.error(f"Error getting admins from database: {e}")
        
        # Отправляем уведомления всем админам
        sent_count = 0
        for admin_id in admin_ids:
            try:
                await bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML')
                sent_count += 1
                logger.info(f"Notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
        
        logger.info(f"Sent purchase notifications to {sent_count} admins")
    
    asyncio.run(send_admin_notifications())

