# -*- coding: utf-8 -*-
"""
Основной файл Telegram бота KISS PARTY PAY BOT
Работает через webhook
"""

import logging
import json
import hashlib
import hmac
import traceback
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, make_response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import database as db
import config
from qr_generator import generate_qr_code

# Настройка логирования
import os
log_dir = os.path.dirname(config.LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except:
        pass

# Создаем логгер с несколькими обработчиками
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Устанавливаем DEBUG для более детального логирования

# Очищаем существующие обработчики
logger.handlers.clear()

# Обработчик для файла
try:
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8', mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except Exception as e:
    # Если не удалось создать файловый обработчик, создаем обработчик для wsgi_error.log
    try:
        wsgi_log = os.path.join(os.path.dirname(__file__), 'wsgi_error.log')
        file_handler = logging.FileHandler(wsgi_log, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - BOT - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        logger.warning(f"Could not create bot.log, using wsgi_error.log instead: {e}")
    except:
        pass

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.info(f"Logging initialized. Log file: {config.LOG_FILE}")

app = Flask(__name__)
telegram_app = Application.builder().token(config.BOT_TOKEN).build()

# Регистрация Blueprint для Mini App API
from miniapp_api import miniapp_bp
app.register_blueprint(miniapp_bp)
bot = telegram_app.bot

# Флаг инициализации Telegram Application
_telegram_app_initialized = False

# Инициализация БД
try:
    db.init_db_pool()
    logger.info("Database initialized")
except Exception as e:
    logger.error(f"Database initialization error: {e}")

async def send_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """Отправить сообщение"""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def send_photo(chat_id, photo_path, caption=None, parse_mode='HTML'):
    """Отправить фото"""
    try:
        with open(photo_path, 'rb') as photo:
            result = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode
            )
            return result.photo[-1].file_id if result.photo else None
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return None

async def notify_admins_new_ticket_message(ticket_id: str, user_id: int, message_text: str):
    """Уведомить админов о новом сообщении в тикете"""
    try:
        ticket = db.get_support_ticket(ticket_id)
        if not ticket:
            return
        
        user = db.get_user(user_id)
        username = user.get('username', 'не указан') if user else 'не указан'
        first_name = user.get('first_name', '') if user else ''
        
        # Обрезаем длинное сообщение
        preview_text = message_text[:200] + '...' if len(message_text) > 200 else message_text
        
        message = f"💬 <b>НОВОЕ СООБЩЕНИЕ В ТИКЕТЕ</b>\n\n"
        message += f"🆔 <b>Тикет:</b> {ticket_id}\n"
        message += f"👤 <b>Пользователь:</b> {first_name} (@{username})\n"
        message += f"🆔 <b>ID:</b> {user_id}\n"
        if ticket.get('subject'):
            message += f"📝 <b>Тема:</b> {ticket.get('subject')}\n"
        message += f"\n💬 <b>Сообщение:</b>\n{preview_text}\n\n"
        message += f"📊 <b>Статус:</b> {ticket.get('status', 'open')}"
        
        # Получаем всех админов
        admin_ids = set(config.ADMIN_USERS)
        try:
            from database import execute_query
            admin_users = execute_query(
                "SELECT user_id FROM users WHERE role = 'admin'",
                fetch=True
            )
            if admin_users:
                for admin in admin_users:
                    admin_ids.add(admin['user_id'])
        except Exception as e:
            logger.error(f"Error getting admins from database: {e}")
        
        # Отправляем уведомления всем админам
        for admin_id in admin_ids:
            try:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 Открыть тикет", callback_data=f'admin_view_ticket_{ticket_id}')
                ]])
                await bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML', reply_markup=keyboard)
                logger.info(f"Support ticket notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error notifying admins about ticket message: {e}", exc_info=True)

async def notify_admins_new_ticket(ticket_id: str, user_id: int):
    """Уведомить админов о новом тикете"""
    try:
        ticket = db.get_support_ticket(ticket_id)
        if not ticket:
            return
        
        user = db.get_user(user_id)
        username = user.get('username', 'не указан') if user else 'не указан'
        first_name = user.get('first_name', '') if user else ''
        
        message = f"🆕 <b>НОВЫЙ ТИКЕТ ПОДДЕРЖКИ</b>\n\n"
        message += f"🆔 <b>Тикет:</b> {ticket_id}\n"
        message += f"👤 <b>Пользователь:</b> {first_name} (@{username})\n"
        message += f"🆔 <b>ID:</b> {user_id}\n"
        if ticket.get('subject'):
            message += f"📝 <b>Тема:</b> {ticket.get('subject')}\n"
        
        # Получаем всех админов
        admin_ids = set(config.ADMIN_USERS)
        try:
            from database import execute_query
            admin_users = execute_query(
                "SELECT user_id FROM users WHERE role = 'admin'",
                fetch=True
            )
            if admin_users:
                for admin in admin_users:
                    admin_ids.add(admin['user_id'])
        except Exception as e:
            logger.error(f"Error getting admins from database: {e}")
        
        # Отправляем уведомления всем админам
        for admin_id in admin_ids:
            try:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 Открыть тикет", callback_data=f'admin_view_ticket_{ticket_id}')
                ]])
                await bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML', reply_markup=keyboard)
                logger.info(f"New ticket notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error notifying admins about new ticket: {e}", exc_info=True)

async def edit_message_safe(query, text, parse_mode='HTML', reply_markup=None):
    """Безопасное редактирование сообщения - определяет, нужно ли редактировать текст или caption"""
    if not text or not text.strip():
        logger.warning("Empty text provided to edit_message_safe, using default")
        text = "❌ Ошибка: пустое сообщение"
    
    try:
        # Проверяем, есть ли фото в сообщении
        if query.message and hasattr(query.message, 'photo') and query.message.photo:
            # Если есть фото, редактируем caption
            try:
                await query.edit_message_caption(
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                logger.debug("Message caption edited successfully")
                return
            except Exception as e:
                logger.warning(f"Could not edit caption: {e}")
                # Пробуем удалить фото и отправить текстовое сообщение
                try:
                    await query.message.delete()
                    await send_message(query.from_user.id, text, parse_mode=parse_mode, reply_markup=reply_markup)
                    logger.info("Deleted photo message and sent new text message")
                    return
                except Exception as delete_error:
                    logger.error(f"Could not delete message: {delete_error}")
                    # Если не получилось удалить, просто отправляем новое сообщение
                    await send_message(query.from_user.id, text, parse_mode=parse_mode, reply_markup=reply_markup)
                    logger.info("Sent new message instead of editing")
                    return
        
        # Если нет фото, редактируем текст
        try:
            await query.edit_message_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            logger.debug("Message text edited successfully")
        except Exception as edit_error:
            logger.warning(f"Could not edit message text: {edit_error}")
            # Если не получилось отредактировать, отправляем новое сообщение
            try:
                await send_message(query.from_user.id, text, parse_mode=parse_mode, reply_markup=reply_markup)
                logger.info("Sent new message instead of editing")
            except Exception as send_error:
                logger.error(f"Error sending new message: {send_error}")
    except Exception as e:
        logger.error(f"Error in edit_message_safe: {e}", exc_info=True)
        # Последняя попытка - отправить новое сообщение
        try:
            await send_message(query.from_user.id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as send_error:
            logger.error(f"Final error sending new message: {send_error}")

def add_cors_headers(response):
    """Добавляет CORS заголовки для API сканера"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response

def verify_qr_signature(ticket_code: str, user_id: int, signature: str) -> bool:
    """Проверить подпись QR-кода"""
    if not ticket_code or not user_id or not signature:
        return False
    expected = hashlib.md5(f"{ticket_code}{user_id}{config.QR_SECRET}".encode()).hexdigest()[:8]
    return signature.lower() == expected.lower()

@app.route('/api/qr/verify', methods=['POST', 'OPTIONS'])
def qr_verify():
    """Проверка билета по QR-коду (используется стаффом на входе)"""
    if request.method == 'OPTIONS':
        return add_cors_headers(jsonify({'ok': True}))
    
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or '').strip()
    if not token or token != config.QR_SCANNER_TOKEN:
        return add_cors_headers(jsonify({'success': False, 'error': 'unauthorized'})), 401
    
    payload = (data.get('payload') or '').strip()
    mark_used = bool(data.get('mark_used', True))
    
    if not payload:
        return add_cors_headers(jsonify({'success': False, 'error': 'empty_payload'})), 400
    
    # Пытаемся распарсить JSON из QR
    qr_data = None
    ticket_code = None
    signature_valid = False
    try:
        qr_data = json.loads(payload)
        ticket_code = qr_data.get('ticket_code')
        user_id_from_qr = int(qr_data.get('user_id', 0))
        signature = qr_data.get('signature', '')
        signature_valid = verify_qr_signature(ticket_code, user_id_from_qr, signature)
        if not signature_valid:
            return add_cors_headers(jsonify({'success': False, 'error': 'invalid_signature'})), 400
    except Exception:
        # Если QR содержит просто код
        ticket_code = payload
    
    if not ticket_code:
        return add_cors_headers(jsonify({'success': False, 'error': 'ticket_code_missing'})), 400
    
    ticket = db.get_ticket_by_code(ticket_code)
    if not ticket:
        return add_cors_headers(jsonify({'success': False, 'error': 'ticket_not_found'})), 404
    
    # Если в QR был user_id – сверяем с базой для защиты от подмены
    if qr_data and qr_data.get('user_id'):
        try:
            if int(ticket.get('user_id')) != int(qr_data.get('user_id')):
                return add_cors_headers(jsonify({'success': False, 'error': 'user_mismatch'})), 400
        except Exception:
            return add_cors_headers(jsonify({'success': False, 'error': 'user_mismatch'})), 400
    
    previous_status = ticket.get('status')
    marked_used = False
    if previous_status == 'active' and mark_used:
        try:
            db.update_ticket_status(ticket_code, 'used')
            ticket['status'] = 'used'
            marked_used = True
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}", exc_info=True)
    
    # Достаем информацию о пользователе
    user_info = db.get_user(ticket.get('user_id'))
    
    response_data = {
        'success': True,
        'ticket': {
            'ticket_code': ticket_code,
            'status': ticket.get('status'),
            'previous_status': previous_status,
            'ticket_type': ticket.get('ticket_type'),
            'amount': float(ticket.get('amount', 0)) if ticket.get('amount') is not None else 0,
            'user_id': ticket.get('user_id'),
            'username': user_info.get('username') if user_info else None,
            'first_name': user_info.get('first_name') if user_info else None,
            'last_name': user_info.get('last_name') if user_info else None,
            'order_id': ticket.get('order_id'),
            'promo_code': ticket.get('promo_code'),
            'bonus_used': float(ticket.get('bonus_used', 0)) if ticket.get('bonus_used') is not None else 0,
            'bonus_earned': float(ticket.get('bonus_earned', 0)) if ticket.get('bonus_earned') is not None else 0,
            'referral_bonus_earned': float(ticket.get('referral_bonus_earned', 0)) if ticket.get('referral_bonus_earned') is not None else 0,
            'created_at': ticket.get('created_at').isoformat() if ticket.get('created_at') and hasattr(ticket.get('created_at'), 'isoformat') else str(ticket.get('created_at'))
        },
        'signature_valid': signature_valid or qr_data is None,  # если QR был просто кодом, не валидируем подпись
        'marked_used': marked_used,
        'checked_at': datetime.utcnow().isoformat() + 'Z'
    }
    
    # Сообщение для фронта
    if ticket['status'] == 'used':
        response_data['message'] = 'Билет уже использован' if not marked_used else 'Билет отмечен как использованный'
    elif ticket['status'] == 'cancelled':
        response_data['message'] = 'Билет отменен'
    else:
        response_data['message'] = 'Билет активен'
    
    return add_cors_headers(jsonify(response_data))

@app.route('/qr-scanner', methods=['GET'])
def qr_scanner_page():
    """Страница простого сканера билетов"""
    scanner_path = os.path.join(os.path.dirname(__file__), 'qr_scanner.html')
    if not os.path.exists(scanner_path):
        return "Scanner page not found", 404
    
    resp = make_response(send_file(scanner_path))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

async def check_channel_subscription(user_id):
    """Проверить подписку на канал"""
    try:
        # Админы всегда имеют доступ
        if is_admin(user_id):
            return True
            
        for channel in config.CHANNELS_TO_CHECK:
            try:
                member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
                # Проверяем статус подписки
                if member.status not in ['member', 'administrator', 'creator']:
                    logger.info(f"User {user_id} is not subscribed to {channel}, status: {member.status}")
                    return False
            except Exception as e:
                # Если бот не является админом канала или канал не найден
                logger.error(f"Error checking subscription to {channel}: {e}")
                # Если это ошибка "Chat not found" или "Not enough rights", считаем что пользователь не подписан
                if "chat not found" in str(e).lower() or "not enough rights" in str(e).lower():
                    logger.warning(f"Bot may not be admin in {channel} or channel not found")
                    return False
                # Для других ошибок разрешаем доступ (чтобы не блокировать пользователей из-за технических проблем)
                return True
        return True
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        # В случае общей ошибки разрешаем доступ, чтобы не блокировать пользователей
        return True

def is_admin(user_id):
    """Проверить является ли пользователь админом"""
    # Проверяем список админов из config
    if user_id in config.ADMIN_USERS:
        return True
    # Проверяем роль в БД
    user = db.get_user(user_id)
    return user and user.get('role') == 'admin'

def is_promoter(user_id):
    """Проверить является ли пользователь промоутером"""
    try:
        user = db.get_user(user_id)
        if user:
            role = user.get('role')
            logger.debug(f"User {user_id} role check: {role} (promoter={role == 'promoter'})")
            return role == 'promoter'
        logger.debug(f"User {user_id} not found in database")
        return False
    except Exception as e:
        logger.error(f"Error checking promoter status for user {user_id}: {e}", exc_info=True)
        return False

def is_moderator(user_id):
    """Проверить является ли пользователь модератором"""
    user = db.get_user(user_id)
    return user and user.get('role') == 'moderator'

def get_main_menu(user_id: int = None):
    """Главное меню с улучшенным UI"""
    keyboard = [
        [InlineKeyboardButton("🎫 Купить билет", callback_data='show_tickets')],
        [InlineKeyboardButton("💎 Мои бонусы", callback_data='my_bonuses')],
        [InlineKeyboardButton("👥 Реферальная программа", callback_data='referral_program')],
        [InlineKeyboardButton("📋 Мои билеты", callback_data='my_tickets')],
        [InlineKeyboardButton("💕 Поиск пары", callback_data='dating_menu')],
        [InlineKeyboardButton("💬 Чат с поддержкой", callback_data='support_chat')]
    ]
    
    # Добавляем кнопки для админов и промоутеров
    if user_id:
        try:
            user = db.get_user(user_id)
            if user:
                role = user.get('role', 'user')
                logger.debug(f"Building main menu for user {user_id} with role: {role}")
                
                if is_admin(user_id):
                    keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin_panel')])
                    logger.debug(f"Added admin panel button for user {user_id}")
                elif is_promoter(user_id):
                    keyboard.append([InlineKeyboardButton("👤 Панель Промоутера", callback_data='promoter_panel')])
                    logger.debug(f"Added promoter panel button for user {user_id}")
                else:
                    logger.debug(f"User {user_id} is regular user (role: {role}), no special panel button")
            else:
                logger.warning(f"User {user_id} not found in database when building menu")
        except Exception as e:
            logger.error(f"Error checking user role for menu: {e}", exc_info=True)
    
    menu = InlineKeyboardMarkup(keyboard)
    # Логируем создание меню для отладки
    logger.debug(f"Main menu created with {len(keyboard)} buttons for user {user_id}")
    for row in keyboard:
        for btn in row:
            logger.debug(f"Button: {btn.text} -> callback_data: {btn.callback_data}")
    return menu

def get_tickets_menu():
    """Меню выбора билетов с улучшенным UI"""
    # Получаем активные категории из БД
    categories = db.get_all_ticket_categories(active_only=True)
    
    keyboard = []
    
    if not categories:
        # Fallback на старые категории, если новых нет
        prices = db.get_prices()
        keyboard = [
            [InlineKeyboardButton(f"🎫 Обычный билет — {prices.get('regular', {}).get('discounted', 0):.0f}₽", callback_data='regular_ticket')],
            [InlineKeyboardButton(f"💎 VIP билет — {prices.get('vip', {}).get('discounted', 0):.0f}₽", callback_data='vip_ticket')],
            [InlineKeyboardButton(f"💎 VIP стоячий — {prices.get('vip_standing', {}).get('discounted', 0):.0f}₽", callback_data='vip_standing_ticket')],
            [InlineKeyboardButton(f"👫 Парный билет — {prices.get('couple', {}).get('discounted', 0):.0f}₽", callback_data='couple_ticket')],
        ]
    else:
        # Используем категории из БД — показываем все активные (распроданные покажем при выборе)
        for cat in categories:
            limit = cat.get('limit') or 0
            sold = cat.get('sold_count') or 0
            available = (limit - sold) if limit > 0 else 999999
            sold_out_label = " (Распродано)" if available <= 0 else ""
            
            # Выбираем эмодзи в зависимости от названия
            emoji = "🎫"
            if 'vip' in (cat.get('code') or '').lower() or 'вип' in (cat.get('name') or '').lower():
                emoji = "💎"
            elif 'couple' in (cat.get('code') or '').lower() or 'парн' in (cat.get('name') or '').lower():
                emoji = "👫"
            elif 'premium' in (cat.get('code') or '').lower() or 'премиум' in (cat.get('name') or '').lower():
                emoji = "⭐"
            
            price = cat.get('discounted_price') or cat.get('base_price') or 0
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {cat.get('name', cat.get('code', ''))} — {price:.0f}₽{sold_out_label}",
                callback_data=f'{cat["code"]}_ticket'
            )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

def get_quantity_menu(ticket_type):
    """Меню выбора количества билетов с улучшенным UI"""
    keyboard = [
        [InlineKeyboardButton("1️⃣ 1 билет", callback_data=f'{ticket_type}_quantity_1')],
        [InlineKeyboardButton("2️⃣ 2 билета", callback_data=f'{ticket_type}_quantity_2')],
        [InlineKeyboardButton("3️⃣ 3 билета", callback_data=f'{ticket_type}_quantity_3')],
        [InlineKeyboardButton("4️⃣ 4 билета", callback_data=f'{ticket_type}_quantity_4')],
        [InlineKeyboardButton("5️⃣ 5 билетов", callback_data=f'{ticket_type}_quantity_5')],
        [InlineKeyboardButton("➕ Другое количество", callback_data=f'{ticket_type}_quantity_custom')],
        [InlineKeyboardButton("◀️ Назад к выбору билетов", callback_data='show_tickets')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_menu(order_id, ticket_type='regular', quantity=1, user_id=None):
    """Меню ручной оплаты с подтверждением пользователем"""
    keyboard = []
    
    # Добавляем кнопку Mini App для VIP билетов
    if ticket_type == 'vip' and user_id:
        miniapp_url = f"https://cw998871.tw1.ru/KISSPARTYPAYMAIN/miniapp/index.html?user_id={user_id}&ticket_type=vip&quantity={quantity}"
        keyboard.append([
            InlineKeyboardButton('🗺️ Выбрать места на карте', web_app=WebAppInfo(url=miniapp_url))
        ])
    
    # Кнопка подтверждения оплаты пользователем
    keyboard.append([InlineKeyboardButton("✅ Я оплатил", callback_data=f'i_paid_{order_id}')])
    keyboard.append([InlineKeyboardButton("❌ Отменить заказ", callback_data=f'cancel_order_{order_id}')])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_payment_check_menu(request_id: int):
    """Кнопки админа для проверки ручной оплаты"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f'approve_payment_{request_id}')],
        [InlineKeyboardButton("❌ Отклонить оплату", callback_data=f'reject_payment_{request_id}')]
    ])

def get_promocode_or_bonus_menu(ticket_type, quantity):
    """Меню выбора: промокод или бонусы с улучшенным UI"""
    keyboard = [
        [InlineKeyboardButton("🎁 Использовать промокод", callback_data=f'use_promo_{ticket_type}_{quantity}')],
        [InlineKeyboardButton("💎 Использовать бонусы", callback_data=f'use_bonus_{ticket_type}_{quantity}')],
        [InlineKeyboardButton("➡️ Продолжить без скидок", callback_data=f'no_discount_{ticket_type}_{quantity}')],
        [InlineKeyboardButton("◀️ Назад", callback_data='show_tickets')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_menu():
    """Меню админ-панели"""
    sales_status = "🟢 Открыты" if db.is_sales_enabled() else "🔴 Закрыты"
    keyboard = [
        [InlineKeyboardButton("🎫 Управление билетами", callback_data='admin_tickets')],
        [InlineKeyboardButton("📋 Категории билетов", callback_data='admin_ticket_categories')],
        [InlineKeyboardButton("💰 Управление ценами", callback_data='admin_prices')],
        [InlineKeyboardButton("💎 Управление бонусами", callback_data='admin_bonuses')],
        [InlineKeyboardButton("🎁 Управление промокодами", callback_data='admin_promocodes')],
        [InlineKeyboardButton("👥 Промоутеры", callback_data='admin_promoters')],
        [InlineKeyboardButton("💬 Обращения в поддержку", callback_data='admin_support_tickets')],
        [InlineKeyboardButton("📢 Публикация постов", callback_data='admin_broadcast')],
        [InlineKeyboardButton("👥 Реферальная программа", callback_data='admin_referrals')],
        [InlineKeyboardButton("👤 Управление ролями", callback_data='admin_roles')],
        [InlineKeyboardButton(f"🛒 Управление продажами ({sales_status})", callback_data='admin_sales')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data='admin_settings')],
        [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Обработчик команды /start"""
    try:
        logger.info("=== handle_start called ===")
        user = update.effective_user
        user_id = user.id
        logger.info(f"User ID: {user_id}, Username: {user.username}")
        
        # Проверяем доступ к боту
        try:
            access_enabled = db.is_bot_access_enabled()
            logger.info(f"Bot access enabled: {access_enabled}")
            is_user_admin = is_admin(user_id)
            logger.info(f"Is user admin: {is_user_admin}")
            
            if not access_enabled and not is_user_admin:
                logger.warning(f"Access denied for user {user_id}")
                await send_message(user_id, "❌ <b>Доступ к боту временно закрыт</b>\n\nПопробуйте позже.")
                return
        except Exception as e:
            logger.error(f"Error checking bot access: {e}", exc_info=True)
            # Продолжаем выполнение даже при ошибке проверки доступа
    
        # Обработка реферальной ссылки
        referrer_id = None
        promo_code = None
        promoter_notification_sent = False
        if context.args and len(context.args) > 0:
            ref_code = context.args[0]
            logger.info(f"Start command with args: {ref_code}")
            if ref_code.startswith('ref'):
                ref_code = ref_code[3:]  # Убираем 'ref'
                # Находим пользователя по реферальному коду
                from database import execute_query
                ref_data = execute_query(
                    "SELECT user_id FROM referrals WHERE referral_code = %s",
                    (ref_code,), fetch=True
                )
                if ref_data:
                    referrer_id = ref_data[0]['user_id']
                    logger.info(f"Referrer found: {referrer_id}")
            elif ref_code.startswith('promo'):
                promo_code = ref_code[5:]  # Убираем 'promo'
                logger.info(f"Promo code from link: {promo_code}")
                
                # Проверяем, является ли это промокодом промоутера
                from database import execute_query
                promoter_data = execute_query(
                    "SELECT user_id, username, first_name, promo_code FROM users WHERE promo_code = %s AND role = 'promoter'",
                    (promo_code,), fetch=True
                )
                
                if promoter_data:
                    promoter = promoter_data[0]
                    promoter_id = promoter['user_id']
                    promoter_username = promoter.get('username', '')
                    promoter_name = promoter.get('first_name', 'Промоутер')
                    
                    # Не привязываем чужой промокод, если пользователь уже промоутер
                    existing_user = db.get_user(user_id)
                    if existing_user and existing_user.get('role') == 'promoter':
                        promo_code = None
                        logger.info(f"User {user_id} is already a promoter, not linking to promoter {promoter_id}")
                    else:
                        # Сохраняем промокод промоутера для пользователя
                        try:
                            db.create_user(
                                user_id=user_id,
                                username=user.username,
                                first_name=user.first_name,
                                last_name=user.last_name,
                                promo_code=promo_code
                            )
                            logger.info(f"User {user_id} linked to promoter {promoter_id} with promo code {promo_code}")
                            
                            # Показываем уведомление о переходе от промоутера
                            notification_message = "🎉 <b>Вы перешли от промоутера!</b>\n\n"
                            notification_message += f"👤 <b>Промоутер:</b> {promoter_name}"
                            if promoter_username:
                                notification_message += f" (@{promoter_username})"
                            notification_message += f"\n🎫 <b>Промокод:</b> <code>{promo_code}</code>\n\n"
                            notification_message += "✅ <b>Вы закреплены за промоутером.</b>\n"
                            notification_message += "ℹ️ Код сохраняется для учета статистики.\n"
                            notification_message += "💸 Скидка по рефералке больше не применяется."
                            
                            # Отправляем уведомление после создания пользователя, но до проверки подписки
                            try:
                                await send_message(user_id, notification_message, parse_mode='HTML')
                                promoter_notification_sent = True
                            except Exception as e:
                                logger.error(f"Error sending promoter notification: {e}")
                                promoter_notification_sent = True
                        except Exception as e:
                            logger.error(f"Error creating user with promoter promo code: {e}", exc_info=True)
                else:
                    # Если промокод не найден или не принадлежит промоутеру, не сохраняем его
                    logger.warning(f"Promo code {promo_code} not found or not a promoter code")
                    promo_code = None
        
        # Создаем/обновляем пользователя (если промокод промоутера не был обработан выше)
        if not promoter_notification_sent:
            try:
                db.create_user(
                    user_id=user_id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    promo_code=promo_code
                )
                logger.info("User created/updated in database")
            except Exception as e:
                logger.error(f"Error creating user: {e}", exc_info=True)
        
        # Если есть реферер, создаем реферальную связь
        if referrer_id:
            try:
                ref_code = 'REF' + str(user_id)[-8:]  # Простой код
                db.create_referral(user_id, ref_code, referrer_id)
                logger.info(f"Referral created: {ref_code}")
            except Exception as e:
                logger.error(f"Error creating referral: {e}", exc_info=True)
        
        # Проверяем подписку
        try:
            subscribed = await check_channel_subscription(user_id)
            logger.info(f"Channel subscription check: {subscribed}")
            if not subscribed:
                message = "❌ <b>Для использования бота необходимо подписаться на канал:</b>\n\n"
                for channel in config.CHANNELS_TO_CHECK:
                    # Формируем ссылку на канал
                    channel_username = channel.replace('@', '')
                    channel_url = f"https://t.me/{channel_username}"
                    message += f"📢 <a href='{channel_url}'>{channel}</a>\n\n"
                message += "👇 Нажмите на кнопку ниже, чтобы подписаться:"
                
                # Создаем кнопки для подписки
                keyboard = []
                for channel in config.CHANNELS_TO_CHECK:
                    channel_username = channel.replace('@', '')
                    channel_url = f"https://t.me/{channel_username}"
                    keyboard.append([InlineKeyboardButton(f"📢 Подписаться на {channel}", url=channel_url)])
                keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')])
                
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                return
        except Exception as e:
            logger.error(f"Error checking subscription: {e}", exc_info=True)
            # Продолжаем выполнение даже при ошибке проверки подписки
        
        # Получаем текст и изображение главного меню из БД
        try:
            welcome_message = db.get_main_menu_text()
            if not welcome_message or welcome_message.strip() == '':
                welcome_message = "🎉 <b>Добро пожаловать в KISS PARTY!</b>\n\n🎪 Мы рады приветствовать вас на нашем мероприятии!\n\nВыберите действие:"
            logger.info("Main menu text loaded successfully")
        except Exception as e:
            logger.error(f"Error getting main menu text: {e}", exc_info=True)
            welcome_message = "🎉 <b>Добро пожаловать в KISS PARTY!</b>\n\n🎪 Мы рады приветствовать вас на нашем мероприятии!\n\nВыберите действие:"
        
        try:
            menu_image = db.get_main_menu_image()
            logger.info(f"Main menu image: {menu_image if menu_image else 'None'}")
        except Exception as e:
            logger.error(f"Error getting main menu image: {e}", exc_info=True)
            menu_image = None
        
        # Получаем меню с учетом роли пользователя
        try:
            menu_keyboard = get_main_menu(user_id)
            logger.info(f"Menu keyboard created for user {user_id}")
            # Логируем все callback_data для отладки
            for row in menu_keyboard.inline_keyboard:
                for btn in row:
                    logger.debug(f"Final menu button: {btn.text} -> {btn.callback_data}")
        except Exception as e:
            logger.error(f"Error creating menu keyboard: {e}", exc_info=True)
            menu_keyboard = get_main_menu(user_id)
        
        # Отправляем сообщение с изображением или без
        try:
            if menu_image and menu_image.strip():
                try:
                    logger.info(f"Sending photo with menu to user {user_id}")
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=menu_image,
                        caption=welcome_message,
                        parse_mode='HTML',
                        reply_markup=menu_keyboard
                    )
                    logger.info("Photo sent successfully")
                except Exception as e:
                    logger.error(f"Error sending photo with menu: {e}", exc_info=True)
                    # Если не удалось отправить фото, отправляем текст
                    await send_message(user_id, welcome_message, reply_markup=menu_keyboard)
            else:
                logger.info(f"Sending text message to user {user_id}")
                await send_message(user_id, welcome_message, reply_markup=menu_keyboard)
                logger.info("Message sent successfully")
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"Error in handle_start: {e}", exc_info=True)
        try:
            await send_message(update.effective_user.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    global json
    try:
        query = update.callback_query
        if not query:
            logger.warning("Callback query is None")
            return
        
        user_id = query.from_user.id
        data = query.data
        
        logger.info(f"Callback received from user {user_id}: {data}")
        logger.debug(f"Full callback data: {query.data}, type: {type(query.data)}")
        
        # Отвечаем на callback сразу, чтобы убрать индикатор загрузки
        try:
            await query.answer()
        except Exception as e:
            logger.error(f"Error answering callback: {e}")
        
        # Обрабатываем callback_data
        if not data:
            logger.warning(f"Empty callback_data from user {user_id}")
            await send_message(user_id, "❌ Ошибка: пустой callback_data")
            return
        
        # Проверяем подписку для всех callback'ов, кроме специальных и админских
        # Исключаем: check_subscription (сама проверка), main_menu (переход в главное меню), админские callback'и
        is_admin_callback = data.startswith('admin_') or is_admin(user_id)
        if data not in ['check_subscription', 'main_menu'] and not is_admin_callback:
            try:
                subscribed = await check_channel_subscription(user_id)
                if not subscribed:
                    message = "❌ <b>Для использования бота необходимо подписаться на канал:</b>\n\n"
                    for channel in config.CHANNELS_TO_CHECK:
                        channel_username = channel.replace('@', '')
                        channel_url = f"https://t.me/{channel_username}"
                        message += f"📢 <a href='{channel_url}'>{channel}</a>\n\n"
                    message += "👇 Нажмите на кнопку ниже, чтобы подписаться:"
                    
                    keyboard = []
                    for channel in config.CHANNELS_TO_CHECK:
                        channel_username = channel.replace('@', '')
                        channel_url = f"https://t.me/{channel_username}"
                        keyboard.append([InlineKeyboardButton(f"📢 Подписаться на {channel}", url=channel_url)])
                    keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')])
                    
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                    return
            except Exception as e:
                logger.error(f"Error checking subscription in callback: {e}", exc_info=True)
                # Продолжаем выполнение при ошибке проверки
        
        # Обработка проверки подписки
        if data == 'check_subscription':
            subscribed = await check_channel_subscription(user_id)
            if subscribed:
                message = "✅ <b>Отлично! Вы подписаны на канал.</b>\n\n"
                message += "Теперь вы можете пользоваться ботом!"
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]]
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                message = "❌ <b>Вы еще не подписаны на канал.</b>\n\n"
                message += "Пожалуйста, подпишитесь на канал, чтобы продолжить:\n\n"
                for channel in config.CHANNELS_TO_CHECK:
                    channel_username = channel.replace('@', '')
                    channel_url = f"https://t.me/{channel_username}"
                    message += f"📢 <a href='{channel_url}'>{channel}</a>\n\n"
                message += "👇 Нажмите на кнопку ниже, чтобы подписаться:"
                
                keyboard = []
                for channel in config.CHANNELS_TO_CHECK:
                    channel_username = channel.replace('@', '')
                    channel_url = f"https://t.me/{channel_username}"
                    keyboard.append([InlineKeyboardButton(f"📢 Подписаться на {channel}", url=channel_url)])
                keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')])
                
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'main_menu':
            await handle_start(update, context, query=query)
            return
        
        # Обработка отмены заказа
        if data.startswith('cancel_order_'):
            message = "❌ <b>Заказ отменен</b>\n\n"
            message += "Вы вернулись в главное меню."
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]])
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=keyboard)
            # Очищаем состояние пользователя
            db.clear_user_state(user_id)
            return

        if data.startswith('i_paid_'):
            order_id = data.replace('i_paid_', '', 1)
            state_data = db.get_user_state(user_id)
            if not state_data or state_data.get('state') != 'processing_payment':
                await send_message(user_id, "❌ Не найден активный заказ. Оформите покупку заново.")
                return

            payload = {}
            raw_data = state_data.get('data')
            if raw_data:
                try:
                    payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                except Exception:
                    payload = {}

            payload_order_id = payload.get('order_id')
            if payload_order_id and payload_order_id != order_id:
                # Не блокируем пользователя из-за рассинхрона состояния:
                # используем order_id из нажатой кнопки и текущий payload.
                logger.warning(
                    f"Order mismatch for user {user_id}: payload_order_id={payload_order_id}, button_order_id={order_id}"
                )

            # Не даем отправлять повторно
            exists = db.get_payment_request_by_order(order_id)
            if exists and exists.get('status') == 'pending':
                await send_message(user_id, "⏳ Ваша заявка уже отправлена админам и ожидает проверки.")
                return

            db.create_payment_request(
                order_id=order_id,
                user_id=user_id,
                ticket_type=payload.get('ticket_type', 'regular'),
                quantity=int(payload.get('quantity', 1)),
                total_price=float(payload.get('total_price', 0)),
                promo_code=payload.get('promo_code'),
                bonus_used=float(payload.get('bonus_used', 0) or 0),
                payload=json.dumps(payload, ensure_ascii=False)
            )
            request_row = db.get_payment_request_by_order(order_id)

            await edit_message_safe(
                query,
                "⏳ <b>Заявка на проверку отправлена</b>\n\n"
                "Администратор проверит перевод и подтвердит оплату. "
                "После подтверждения вы автоматически получите QR-билет.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]])
            )

            # Уведомления админам
            username = query.from_user.username
            user_link = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{user_id}</a>"
            admin_text = (
                "🔔 <b>Новая заявка на проверку оплаты</b>\n\n"
                f"👤 Пользователь: {user_link} (<code>{user_id}</code>)\n"
                f"🧾 Заказ: <code>{order_id}</code>\n"
                f"🎫 Тип: <b>{payload.get('ticket_type', '-')}</b>\n"
                f"📦 Кол-во: <b>{payload.get('quantity', 1)}</b>\n"
                f"💰 Сумма: <b>{float(payload.get('total_price', 0)):.2f} руб.</b>\n"
                f"💳 Карта: <code>{config.PAYMENT_CARD_NUMBER}</code>"
            )
            # Собираем всех админов: из конфига + из БД
            payment_admin_ids = set(config.ADMIN_USERS)
            try:
                from database import execute_query as _eq
                db_admins = _eq("SELECT user_id FROM users WHERE role = 'admin'", fetch=True)
                if db_admins:
                    for _a in db_admins:
                        payment_admin_ids.add(_a['user_id'])
            except Exception as e:
                logger.error(f"Error getting admins from DB for payment notify: {e}")
            for admin_id in payment_admin_ids:
                try:
                    await send_message(admin_id, admin_text, reply_markup=get_admin_payment_check_menu(request_row['id']))
                    logger.info(f"Payment request notification sent to admin {admin_id}")
                except Exception as e:
                    logger.error(f"Error sending payment notification to admin {admin_id}: {e}")
            return

        if data.startswith('approve_payment_') or data.startswith('reject_payment_'):
            if not is_admin(user_id):
                await query.answer("Недостаточно прав", show_alert=True)
                return

            is_approve = data.startswith('approve_payment_')
            request_id = int(data.split('_')[-1])
            payment_request = db.get_payment_request(request_id)

            if not payment_request:
                await edit_message_safe(query, "❌ Заявка не найдена")
                return

            if payment_request.get('status') != 'pending':
                await edit_message_safe(
                    query,
                    f"ℹ️ Заявка уже обработана: <b>{payment_request.get('status')}</b>",
                    parse_mode='HTML'
                )
                return

            if is_approve:
                db.update_payment_request_status(request_id, 'approved', admin_id=user_id)
                await finalize_approved_payment(payment_request)
                await edit_message_safe(
                    query,
                    "✅ <b>Оплата подтверждена</b>\n\n"
                    f"🧾 Заказ: <code>{payment_request['order_id']}</code>",
                    parse_mode='HTML'
                )
            else:
                db.update_payment_request_status(request_id, 'rejected', admin_id=user_id)
                await send_message(
                    int(payment_request['user_id']),
                    "❌ <b>Оплата отклонена администратором</b>\n\n"
                    "Проверьте перевод и попробуйте снова."
                )
                db.clear_user_state(int(payment_request['user_id']))
                await edit_message_safe(
                    query,
                    "❌ <b>Заявка отклонена</b>\n\n"
                    f"🧾 Заказ: <code>{payment_request['order_id']}</code>",
                    parse_mode='HTML'
                )
            return
        
        if data == 'show_tickets':
            # Проверяем, открыты ли продажи
            if not db.is_sales_enabled():
                message = "🔧 <b>Техническое обслуживание</b>\n\n"
                message += "⚠️ Бот находится на техническом обслуживании.\n"
                message += "💰 Покупка билетов временно недоступна.\n\n"
                message += "🕐 Мы работаем над улучшением сервиса и скоро вернемся!\n"
                message += "📢 Следите за обновлениями в наших каналах."
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')
                ]])
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=keyboard)
                return
            
            message = "🎫 <b>Выберите тип билета:</b>"
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=get_tickets_menu())
            return
        
        if data.endswith('_ticket') and data not in ['create_support_ticket']:
            ticket_type = data.replace('_ticket', '')
            # Проверяем, открыты ли продажи
            if not db.is_sales_enabled():
                message = "🔧 <b>Техническое обслуживание</b>\n\n"
                message += "⚠️ Бот находится на техническом обслуживании.\n"
                message += "💰 Покупка билетов временно недоступна.\n\n"
                message += "🕐 Мы работаем над улучшением сервиса и скоро вернемся!\n"
                message += "📢 Следите за обновлениями в наших каналах."
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')
                ]])
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=keyboard)
                return
            
            # Получаем информацию о категории из БД
            category = db.get_ticket_category(ticket_type)
            if not category or not category.get('is_active'):
                await edit_message_safe(query, "❌ <b>Категория билетов недоступна</b>",
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='show_tickets')
                                       ]]))
                return
            
            available = category['limit'] - category['sold_count'] if category['limit'] > 0 else 999999
            price = category['discounted_price']
            
            message = f"🎫 <b>{category['name']}</b>\n\n"
            message += f"💰 <b>Цена за билет:</b> {price:.0f}₽\n\n"
            # Количество оставшихся билетов видно только в админ-панели
            if category.get('description'):
                message += f"📝 <b>Описание:</b> {category['description']}\n\n"
            message += f"👇 <b>Выберите количество билетов:</b>"
            db.set_user_state(user_id, f'selecting_quantity_{ticket_type}')
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=get_quantity_menu(ticket_type))
            return
        
        if '_quantity_' in data and data.endswith(('_1', '_2', '_3', '_4', '_5', '_custom')):
            # Обработка количества для любой категории
            parts = data.split('_quantity_')
            if len(parts) != 2:
                return
            ticket_type = parts[0]
            quantity_str = parts[1]
            
            # Проверяем доступность категории
            category = db.get_ticket_category(ticket_type)
            if not category or not category.get('is_active'):
                await edit_message_safe(query, "❌ <b>Категория билетов недоступна</b>",
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='show_tickets')
                                       ]]))
                return
            
            # Проверяем доступность билетов
            available = category['limit'] - category['sold_count'] if category['limit'] > 0 else 999999
            
            if quantity_str == 'custom':
                db.set_user_state(user_id, f'waiting_quantity_{ticket_type}')
                if available <= 0:
                    # Показываем сообщение о закончившихся билетах и предлагаем другие категории
                    message = f"❌ <b>Билеты закончились</b>\n\n"
                    message += f"К сожалению, все билеты категории <b>{category['name']}</b> уже распроданы.\n\n"
                    
                    # Получаем доступные категории
                    all_categories = db.get_all_ticket_categories(active_only=True)
                    available_categories = [cat for cat in all_categories 
                                         if cat['code'] != ticket_type and 
                                         (cat['limit'] == 0 or (cat['limit'] - cat['sold_count']) > 0)]
                    
                    if available_categories:
                        message += "💡 <b>Но вы можете купить билеты других категорий:</b>\n\n"
                        keyboard = []
                        for cat in available_categories[:5]:  # Показываем до 5 категорий
                            emoji = "🎫"
                            if 'vip' in cat['code'].lower() or 'вип' in cat['name'].lower():
                                emoji = "💎"
                            elif 'couple' in cat['code'].lower() or 'парн' in cat['name'].lower():
                                emoji = "👫"
                            message += f"{emoji} <b>{cat['name']}</b> — {cat['discounted_price']:.0f}₽\n"
                            keyboard.append([InlineKeyboardButton(
                                f"{emoji} {cat['name']} — {cat['discounted_price']:.0f}₽",
                                callback_data=f'{cat["code"]}_ticket'
                            )])
                        keyboard.append([InlineKeyboardButton("◀️ Назад к билетам", callback_data='show_tickets')])
                        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        message += "😔 К сожалению, все билеты распроданы."
                        keyboard = [[InlineKeyboardButton("◀️ Назад к билетам", callback_data='show_tickets')]]
                        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await send_message(user_id, "📝 Введите количество билетов (число от 1 до 10):")
                return
            
            quantity = int(quantity_str)
            
            # Проверяем доступность перед оформлением
            if available < quantity:
                message = f"❌ <b>Недостаточно билетов!</b>\n\n"
                message += f"Вы запросили: {quantity} шт.\n\n"
                
                # Получаем доступные категории
                all_categories = db.get_all_ticket_categories(active_only=True)
                available_categories = [cat for cat in all_categories 
                                     if cat['code'] != ticket_type and 
                                     (cat['limit'] == 0 or (cat['limit'] - cat['sold_count']) > 0)]
                
                if available_categories:
                    message += "💡 <b>Вы можете выбрать другую категорию:</b>\n\n"
                    keyboard = []
                    for cat in available_categories[:5]:
                        emoji = "🎫"
                        if 'vip' in cat['code'].lower() or 'вип' in cat['name'].lower():
                            emoji = "💎"
                        elif 'couple' in cat['code'].lower() or 'парн' in cat['name'].lower():
                            emoji = "👫"
                        message += f"{emoji} <b>{cat['name']}</b> — {cat['discounted_price']:.0f}₽\n"
                        keyboard.append([InlineKeyboardButton(
                            f"{emoji} {cat['name']} — {cat['discounted_price']:.0f}₽",
                            callback_data=f'{cat["code"]}_ticket'
                        )])
                    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='show_tickets')])
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='show_tickets')]]
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                return
            
            # Показываем меню выбора: промокод или бонусы (если разрешено)
            if not db.is_bonuses_promocodes_enabled():
                await process_ticket_purchase(user_id, ticket_type, quantity, query, promo_code=None, bonus_used=0)
                return
            message = f"🎫 <b>Оформление заказа</b>\n\n"
            message += f"📦 <b>Тип:</b> {category['name']}\n"
            message += f"📦 <b>Количество:</b> {quantity}\n\n"
            message += "💡 <b>Хотите использовать промокод или бонусы?</b>\n"
            message += "(Можно выбрать только что-то одно)"
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=get_promocode_or_bonus_menu(ticket_type, quantity))
            return
        
        # Обработка выбора промокода или бонусов
        if data.startswith('use_promo_') or data.startswith('use_bonus_') or data.startswith('no_discount_'):
            parts = data.split('_')
            action = parts[1]  # promo, bonus, discount
            ticket_type = parts[2]
            quantity = int(parts[3])
            if not db.is_bonuses_promocodes_enabled():
                action = 'discount'
            if action == 'promo':
                db.set_user_state(user_id, f'waiting_promocode_{ticket_type}_{quantity}')
                await send_message(user_id, "🔑 <b>Введите промокод:</b>")
                return
            elif action == 'bonus':
                await process_ticket_purchase_with_bonus(user_id, ticket_type, quantity, query)
                return
            else:  # no_discount
                await process_ticket_purchase(user_id, ticket_type, quantity, query, promo_code=None, bonus_used=0)
                return
        
        if data == 'my_bonuses':
            balance = db.get_user_bonuses(user_id)
            message = "💎 <b>Мои бонусы</b>\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"💰 <b>Ваш баланс:</b> <b>{balance:.2f}₽</b>\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += "💡 <b>Как получить бонусы?</b>\n"
            message += "• При покупке билетов начисляется 5% от суммы\n"
            message += "• За приглашение друзей по реферальной программе\n"
            message += "• Бонусы можно использовать при оплате (до 50% от стоимости)\n\n"
            message += "🎁 <b>Используйте бонусы при следующей покупке!</b>"
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')
            ]]))
            return
        
        if data == 'referral_program':
            ref_data = db.get_referral_data(user_id)
            if not ref_data.get('referral_code'):
                # Генерируем новый код
                import random
                import string
                code = 'REF' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                db.create_referral(user_id, code)
                ref_data = db.get_referral_data(user_id)
            
            ref_link = f"https://t.me/{bot.username}?start=ref{ref_data['referral_code']}"
            
            message = "👥 <b>Реферальная программа</b>\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += "🔗 <b>Ваша реферальная ссылка:</b>\n"
            message += f"<code>{ref_link}</code>\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += "📊 <b>Ваша статистика:</b>\n"
            message += f"👥 Приглашено друзей: <b>{ref_data.get('referrals_count', 0)}</b>\n"
            message += f"💰 Заработано бонусов: <b>{ref_data.get('referral_earnings', 0):.2f}₽</b>\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += "🎁 <b>Как это работает?</b>\n"
            message += "1️⃣ Поделитесь своей ссылкой с друзьями\n"
            message += "2️⃣ Когда друг совершит первую покупку\n"
            message += "3️⃣ Вы оба получите по <b>50 бонусов</b>! 🎉\n\n"
            message += "💡 <b>Чем больше друзей пригласите, тем больше бонусов!</b>"
            
            keyboard = [
                [InlineKeyboardButton("📋 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}&text=Присоединяйся!")],
                [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
            ]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Чат с поддержкой
        if data == 'support_chat':
            # Проверяем, есть ли открытые тикеты у пользователя
            open_tickets = db.get_user_tickets(user_id, status='open')
            in_progress_tickets = db.get_user_tickets(user_id, status='in_progress')
            waiting_tickets = db.get_user_tickets(user_id, status='waiting')
            
            active_tickets = open_tickets + in_progress_tickets + waiting_tickets
            
            if active_tickets:
                # Показываем список активных тикетов
                message = "💬 <b>Чат с поддержкой</b>\n\n"
                message += "📋 <b>Ваши активные обращения:</b>\n\n"
                
                keyboard = []
                for ticket in active_tickets[:5]:  # Показываем до 5 тикетов
                    ticket_id = ticket['ticket_id']
                    status_emoji = {
                        'open': '🟢',
                        'in_progress': '🟡',
                        'waiting': '⏳',
                        'closed': '🔴'
                    }
                    emoji = status_emoji.get(ticket.get('status', 'open'), '🟢')
                    subject = ticket.get('subject', 'Без темы')
                    if len(subject) > 30:
                        subject = subject[:30] + '...'
                    button_text = f"{emoji} {subject}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=f'view_ticket_{ticket_id}')])
                
                keyboard.append([InlineKeyboardButton("➕ Создать новое обращение", callback_data='create_support_ticket')])
                keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')])
                
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                # Предлагаем создать новый тикет
                message = "💬 <b>Чат с поддержкой</b>\n\n"
                message += "👋 Здравствуйте! Мы готовы помочь вам.\n\n"
                message += "📝 <b>Создайте обращение, и мы ответим в ближайшее время.</b>"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Создать обращение", callback_data='create_support_ticket')],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
                ]
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'create_support_ticket':
            # Создаем новый тикет
            ticket_id = db.create_support_ticket(user_id)
            db.set_user_state(user_id, f'support_ticket_message_{ticket_id}')
            
            # Уведомляем админов о новом тикете
            await notify_admins_new_ticket(ticket_id, user_id)
            
            message = "💬 <b>Создание обращения в поддержку</b>\n\n"
            message += "📝 <b>Опишите вашу проблему или вопрос:</b>\n\n"
            message += "💡 Вы можете отправить текст, фото, видео или голосовое сообщение.\n"
            message += "💡 Для отмены нажмите кнопку ниже."
            
            keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data='support_chat')]]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith('view_ticket_'):
            # Просмотр тикета
            ticket_id = data.replace('view_ticket_', '')
            ticket = db.get_support_ticket(ticket_id)
            
            if not ticket or ticket['user_id'] != user_id:
                await edit_message_safe(query, "❌ Тикет не найден",
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='support_chat')
                                       ]]))
                return
            
            # Получаем сообщения
            messages = db.get_ticket_messages(ticket_id)
            
            status_names = {
                'open': '🟢 Открыт',
                'in_progress': '🟡 В обработке',
                'waiting': '⏳ Ожидает ответа',
                'closed': '🔴 Закрыт'
            }
            
            message = f"💬 <b>Обращение #{ticket_id}</b>\n\n"
            message += f"📋 <b>Статус:</b> {status_names.get(ticket.get('status', 'open'), 'Открыт')}\n"
            if ticket.get('subject'):
                message += f"📝 <b>Тема:</b> {ticket['subject']}\n"
            message += f"\n📨 <b>Сообщения:</b> ({len(messages)})\n\n"
            
            if messages:
                for msg in messages[-10:]:  # Показываем последние 10 сообщений
                    sender = "👤 Поддержка" if msg.get('is_admin') else "👤 Вы"
                    msg_text = msg.get('message_text', '')
                    if len(msg_text) > 100:
                        msg_text = msg_text[:100] + '...'
                    message += f"{sender}: {msg_text}\n"
            else:
                message += "Пока нет сообщений.\n"
            
            keyboard = []
            if ticket.get('status') != 'closed':
                keyboard.append([InlineKeyboardButton("💬 Написать сообщение", callback_data=f'reply_ticket_{ticket_id}')])
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='support_chat')])
            
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith('reply_ticket_'):
            # Ответ в тикет
            ticket_id = data.replace('reply_ticket_', '')
            ticket = db.get_support_ticket(ticket_id)
            
            if not ticket or ticket['user_id'] != user_id:
                await edit_message_safe(query, "❌ Тикет не найден",
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='support_chat')
                                       ]]))
                return
            
            if ticket.get('status') == 'closed':
                await edit_message_safe(query, "❌ Этот тикет закрыт",
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='support_chat')
                                       ]]))
                return
            
            db.set_user_state(user_id, f'support_ticket_message_{ticket_id}')
            
            message = "💬 <b>Написать сообщение в поддержку</b>\n\n"
            message += "📝 <b>Введите ваше сообщение:</b>\n\n"
            message += "💡 Вы можете отправить текст, фото, видео или голосовое сообщение."
            
            keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data=f'view_ticket_{ticket_id}')]]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Админ-панель
        if data == 'admin_panel':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа к админ-панели")
                return
            message = "⚙️ <b>Админ-панель</b>\n\nВыберите раздел:"
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=get_admin_panel_menu())
            return
        
        # Обработка подтверждения публикации (должна быть ПЕРЕД общим обработчиком admin_)
        if data.startswith('admin_confirm_broadcast_'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                return
            
            # Обрабатываем варианты с кнопкой и без
            if data.endswith('_with_button'):
                broadcast_type = data.replace('admin_confirm_broadcast_', '').replace('_with_button', '')
                add_button = True
            elif data.endswith('_no_button'):
                broadcast_type = data.replace('admin_confirm_broadcast_', '').replace('_no_button', '')
                add_button = False
            else:
                broadcast_type = data.replace('admin_confirm_broadcast_', '')
                add_button = False  # По умолчанию без кнопки для обратной совместимости
            
            logger.info(f"Processing broadcast confirmation: type={broadcast_type}, user_id={user_id}, add_button={add_button}")
            
            state_data = db.get_user_state(user_id)
            logger.info(f"State data retrieved: {state_data}")
            
            if not state_data:
                logger.error(f"No state data found for user {user_id}")
                await edit_message_safe(query, "❌ Данные поста не найдены. Начните заново.")
                db.clear_user_state(user_id)
                return
            
            if state_data.get('state') != 'admin_broadcast_ready':
                logger.error(f"Wrong state: expected 'admin_broadcast_ready', got '{state_data.get('state')}'")
                await edit_message_safe(query, f"❌ Неверное состояние: {state_data.get('state')}. Начните заново.")
                db.clear_user_state(user_id)
                return
            
            # Извлекаем данные поста из состояния
            import json
            post_data = {}
            raw_data = state_data.get('data')
            logger.info(f"Raw data from state: {raw_data}, type: {type(raw_data)}")
            
            if raw_data:
                if isinstance(raw_data, str):
                    try:
                        post_data = json.loads(raw_data)
                        logger.info(f"Parsed JSON data: {post_data}")
                    except Exception as e:
                        logger.error(f"Error parsing JSON: {e}")
                        post_data = {}
                else:
                    post_data = raw_data
                    logger.info(f"Using data as dict: {post_data}")
            
            logger.info(f"Final post_data: {post_data}")
            
            if not post_data or not post_data.get('text'):
                logger.error(f"Post data is empty or missing text: {post_data}")
                await edit_message_safe(query, "❌ Ошибка: данные поста пусты или отсутствует текст. Начните заново.")
                db.clear_user_state(user_id)
                return
            
            # Добавляем информацию о кнопке в post_data
            post_data['add_button'] = add_button
            
            # Отправляем всем пользователям
            await edit_message_safe(query, "📤 <b>Отправка поста...</b>\n\n⏳ Пожалуйста, подождите...")
            
            try:
                # Получаем информацию о кнопке из post_data
                add_button = post_data.get('add_button', False)
                sent, failed, details = await send_broadcast_to_all_users(post_data, user_id, add_button=add_button)
            except Exception as e:
                logger.error(f"Error sending broadcast: {e}", exc_info=True)
                await edit_message_safe(query, f"❌ Ошибка при отправке поста: {str(e)}")
                db.clear_user_state(user_id)
                return
            
            # Расширенный отчет
            message = f"✅ <b>Пост успешно отправлен!</b>\n\n"
            message += f"📊 <b>Основная статистика:</b>\n"
            message += f"✅ Успешно отправлено: <b>{sent}</b>\n"
            message += f"❌ Ошибок при отправке: <b>{failed}</b>\n"
            message += f"📈 Всего пользователей: <b>{sent + failed}</b>\n"
            if add_button:
                message += f"🔘 Кнопка 'Купить билет' добавлена\n"
            message += f"\n📋 <b>Детальная статистика:</b>\n"
            message += f"• Пользователей получили: {details.get('received', 0)}\n"
            message += f"• Пользователей не получили: {details.get('not_received', 0)}\n"
            message += f"• Заблокировали бота: {details.get('blocked', 0)}\n"
            message += f"• Другие ошибки: {details.get('other_errors', 0)}\n"
            if details.get('errors_list'):
                message += f"\n⚠️ <b>Примеры ошибок:</b>\n"
                for error in details['errors_list'][:5]:  # Показываем первые 5 ошибок
                    message += f"• {error}\n"
            
            keyboard = [
                [InlineKeyboardButton("◀️ Админ-панель", callback_data='admin_panel')]
            ]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            db.clear_user_state(user_id)
            return
        
        # Обработка админ-панели
        if data.startswith('admin_'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                return
            await handle_admin_callback(query, data, user_id)
            return
        
        # Команда /promoter для промоутеров
        if data == 'promoter_panel':
            if not is_promoter(user_id):
                await send_message(user_id, "❌ У вас нет доступа к панели промоутера")
                return
            await handle_promoter_panel(query, user_id)
            return
        
        if data == 'admin_menu_skip_image':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                return
            await send_message(user_id, "✅ <b>Главное меню обновлено!</b>")
            db.clear_user_state(user_id)
            return
        
        if data == 'my_tickets':
            # Получаем все билеты пользователя (включая использованные)
            from database import execute_query
            query_sql = "SELECT * FROM tickets WHERE user_id = %s ORDER BY created_at DESC LIMIT 50"
            tickets = execute_query(query_sql, (user_id,), fetch=True)
            
            if not tickets:
                message = "🎫 <b>У вас пока нет билетов</b>"
            else:
                message = "🎫 <b>Ваши билеты:</b>\n\n"
                for ticket in tickets:
                    status_icon = "✅" if ticket['status'] == 'active' else "🔴" if ticket['status'] == 'used' else "⚪"
                    status_text = "Активен" if ticket['status'] == 'active' else "Использован" if ticket['status'] == 'used' else ticket['status']
                    message += f"{status_icon} <b>{ticket['ticket_code']}</b> - {ticket['ticket_type']} ({ticket['amount']}₽) [{status_text}]\n"
            
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='main_menu')
            ]]))
            return
        
        # ==================== ОБРАБОТЧИКИ ДЛЯ "ПОИСК ПАРЫ" ====================
        if data == 'dating_menu':
            try:
                profile = db.get_dating_profile(user_id)
            except Exception as e:
                logger.error(f"Error getting dating profile: {e}", exc_info=True)
                # Если таблица не существует, показываем меню регистрации
                profile = None
            
            if not profile:
                # Показываем меню регистрации
                message = "💕 <b>Поиск пары</b>\n\n"
                message += "👋 Добро пожаловать в функцию поиска пары!\n\n"
                message += "📝 Для начала нужно создать свою анкету:\n"
                message += "• Загрузите свое фото\n"
                message += "• Укажите свой пол\n"
                message += "• Выберите, кого вы ищете\n\n"
                message += "✨ После регистрации вы сможете просматривать анкеты других пользователей!"
                keyboard = [
                    [InlineKeyboardButton("📝 Создать анкету", callback_data='dating_create_profile')],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
                ]
                await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                # Показываем меню с анкетой и фото пользователя
                message = "💕 <b>Поиск пары</b>\n\n"
                message += "✅ Ваша анкета активна!\n\n"
                gender_text = "👨 Мужской" if profile['gender'] == 'male' else "👩 Женский"
                looking_for_text = {
                    'male': '👨 Парней',
                    'female': '👩 Девушек',
                    'both': '👥 Всех'
                }.get(profile['looking_for'], profile['looking_for'])
                message += f"👤 <b>Ваш пол:</b> {gender_text}\n"
                message += f"🔍 <b>Ищете:</b> {looking_for_text}\n\n"
                message += "Выберите действие:"
                keyboard = [
                    [InlineKeyboardButton("👀 Смотреть анкеты", callback_data='dating_view_profiles')],
                    [InlineKeyboardButton("💌 Кто меня лайкнул", callback_data='dating_likes_received')],
                    [InlineKeyboardButton("💑 Мои мэтчи", callback_data='dating_my_matches')],
                    [InlineKeyboardButton("👤 Моя анкета", callback_data='dating_my_profile')],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
                ]
                
                # Удаляем предыдущее сообщение, если есть query
                if query:
                    try:
                        await query.message.delete()
                    except:
                        pass
                
                # Отправляем фото пользователя с меню
                try:
                    if profile.get('photo_file_id'):
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=profile['photo_file_id'],
                            caption=message,
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    logger.error(f"Error sending dating menu with photo: {e}")
                    await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_create_profile':
            message = "📸 <b>Создание анкеты</b>\n\n"
            message += "📷 <b>Шаг 1:</b> Отправьте ваше фото\n\n"
            message += "💡 <i>Отправьте одно фото, которое будет отображаться в вашей анкете</i>"
            db.set_user_state(user_id, 'dating_waiting_photo')
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')
            ]]))
            return
        
        if data.startswith('dating_view_liked_user_'):
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            # Показать анкету пользователя, который лайкнул
            target_user_id = int(data.split('_')[4])
            await show_dating_profile_by_id(user_id, target_user_id, None, is_liked=True)
            return
        
        if data == 'dating_my_profile':
            # Показываем полную анкету пользователя
            await show_my_profile(user_id)
            return
        
        if data == 'dating_edit_profile':
            message = "⚙️ <b>Редактирование анкеты</b>\n\n"
            message += "Что вы хотите изменить?\n\n"
            message += "Выберите пункт для редактирования:"
            keyboard = [
                [InlineKeyboardButton("📷 Фото", callback_data='dating_edit_photo')],
                [InlineKeyboardButton("👤 Пол", callback_data='dating_edit_gender')],
                [InlineKeyboardButton("🔍 Кого ищете", callback_data='dating_edit_looking_for')],
                [InlineKeyboardButton("👤 Имя", callback_data='dating_edit_name')],
                [InlineKeyboardButton("🎂 Возраст", callback_data='dating_edit_age')],
                [InlineKeyboardButton("📝 Описание", callback_data='dating_edit_description')],
                [InlineKeyboardButton("🔄 Заполнить заново", callback_data='dating_recreate_profile')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_my_profile')]
            ]
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_edit_photo':
            message = "📷 <b>Редактирование фото</b>\n\n"
            message += "Отправьте новое фото для вашей анкеты:"
            db.set_user_state(user_id, 'dating_waiting_photo_edit')
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')
            ]]))
            return
        
        if data == 'dating_edit_gender':
            message = "👤 <b>Редактирование пола</b>\n\n"
            message += "Выберите ваш пол:"
            keyboard = [
                [InlineKeyboardButton("👨 Мужской", callback_data='dating_save_gender_male')],
                [InlineKeyboardButton("👩 Женский", callback_data='dating_save_gender_female')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')]
            ]
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith('dating_save_gender_'):
            gender = data.split('_')[3]  # male или female
            profile = db.get_dating_profile(user_id)
            if profile:
                # Обновляем только пол
                if db.create_dating_profile(user_id, profile['photo_file_id'], gender, profile['looking_for'], 
                                          profile.get('name'), profile.get('age'), profile.get('description')):
                    await send_message(user_id, "✅ Пол успешно обновлен!")
                    # Возвращаемся к анкете
                    await show_my_profile(user_id)
                else:
                    await send_message(user_id, "❌ Ошибка при обновлении пола.")
            return
        
        if data == 'dating_edit_looking_for':
            profile = db.get_dating_profile(user_id)
            if not profile:
                await send_message(user_id, "❌ Анкета не найдена.")
                return
            
            message = "🔍 <b>Редактирование: Кого вы ищете</b>\n\n"
            message += "Выберите, кого вы хотите найти:"
            keyboard = [
                [InlineKeyboardButton("👨 Парней", callback_data='dating_save_looking_male')],
                [InlineKeyboardButton("👩 Девушек", callback_data='dating_save_looking_female')],
                [InlineKeyboardButton("👥 Всех", callback_data='dating_save_looking_both')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')]
            ]
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith('dating_save_looking_'):
            looking_for = data.split('_')[3]  # male, female или both
            profile = db.get_dating_profile(user_id)
            if profile:
                # Обновляем только "кого ищете"
                if db.create_dating_profile(user_id, profile['photo_file_id'], profile['gender'], looking_for,
                                          profile.get('name'), profile.get('age'), profile.get('description')):
                    await send_message(user_id, "✅ Предпочтения успешно обновлены!")
                    # Возвращаемся к анкете
                    await show_my_profile(user_id)
                else:
                    await send_message(user_id, "❌ Ошибка при обновлении предпочтений.")
            return
        
        if data == 'dating_edit_name':
            message = "👤 <b>Редактирование имени</b>\n\n"
            message += "Введите ваше имя (или как вас называть):"
            db.set_user_state(user_id, 'dating_waiting_name_edit')
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')
            ]]))
            return
        
        if data == 'dating_edit_age':
            message = "🎂 <b>Редактирование возраста</b>\n\n"
            message += "Введите ваш возраст (число от 14 до 100):"
            db.set_user_state(user_id, 'dating_waiting_age_edit')
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')
            ]]))
            return
        
        if data == 'dating_edit_description':
            message = "📝 <b>Редактирование описания</b>\n\n"
            message += "Введите описание о себе:\n\n"
            message += "💡 <i>Расскажите о себе, своих интересах, что вы ищете.</i>\n"
            message += "💡 <i>Можно отправить /skip чтобы удалить описание</i>"
            db.set_user_state(user_id, 'dating_waiting_description_edit')
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_edit_profile')
            ]]))
            return
        
        if data == 'dating_recreate_profile':
            message = "🔄 <b>Заполнить анкету заново</b>\n\n"
            message += "⚠️ Вы уверены, что хотите заполнить анкету заново?\n\n"
            message += "Это удалит все текущие данные и вы начнете с начала."
            keyboard = [
                [InlineKeyboardButton("✅ Да, заполнить заново", callback_data='dating_confirm_recreate')],
                [InlineKeyboardButton("❌ Отмена", callback_data='dating_edit_profile')]
            ]
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_confirm_recreate':
            # Удаляем анкету и начинаем заново
            db.delete_dating_profile(user_id)
            message = "📸 <b>Создание анкеты</b>\n\n"
            message += "📷 <b>Шаг 1:</b> Отправьте ваше фото\n\n"
            message += "💡 <i>Отправьте одно фото, которое будет отображаться в вашей анкете</i>"
            db.set_user_state(user_id, 'dating_waiting_photo')
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')
            ]]))
            return
        
        if data == 'dating_delete_profile':
            message = "🗑️ <b>Удаление анкеты</b>\n\n"
            message += "⚠️ Вы уверены, что хотите удалить свою анкету?\n\n"
            message += "После удаления вы не сможете просматривать анкеты других пользователей."
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить", callback_data='dating_confirm_delete')],
                [InlineKeyboardButton("❌ Отмена", callback_data='dating_my_profile')]
            ]
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_confirm_delete':
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            
            if db.delete_dating_profile(user_id):
                message = "✅ <b>Анкета успешно удалена</b>\n\n"
                message += "Вы можете создать новую анкету в любое время."
            else:
                message = "❌ <b>Ошибка при удалении анкеты</b>\n\n"
                message += "Попробуйте позже."
            keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]]
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_view_profiles':
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            # Показываем первую доступную анкету
            await show_next_dating_profile(user_id, None)
            return
        
        if data.startswith('dating_like_'):
            target_user_id = int(data.split('_')[2])
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await process_dating_like(user_id, target_user_id, 'like', None)
            return
        
        if data.startswith('dating_dislike_'):
            target_user_id = int(data.split('_')[2])
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            await process_dating_like(user_id, target_user_id, 'dislike', None)
            return
        
        if data.startswith('dating_skip_'):
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            # Просто показываем следующую анкету
            await show_next_dating_profile(user_id, None)
            return
        
        if data == 'dating_likes_received':
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            
            # Получаем список тех, кто лайкнул (исключая тех, на кого уже поставлен лайк/дизлайк)
            likes = db.get_likes_received(user_id)
            if not likes:
                message = "💌 <b>Кто меня лайкнул</b>\n\n"
                message += "😔 Пока нет новых лайков\n\n"
                message += "💡 Продолжайте просматривать анкеты, и вы обязательно найдете свою пару!"
                keyboard = [
                    [InlineKeyboardButton("👀 Смотреть анкеты", callback_data='dating_view_profiles')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                # Сохраняем список лайкнувших в состоянии для навигации (только тех, на кого еще не поставлен лайк/дизлайк)
                liked_user_ids = [like['from_user_id'] for like in likes]
                import json
                db.set_user_state(user_id, 'dating_viewing_likes', {'liked_user_ids': liked_user_ids, 'current_index': 0})
                
                # Показываем первую анкету из тех, кто лайкнул
                first_like = likes[0]
                target_user_id = first_like['from_user_id']
                await show_dating_profile_by_id(user_id, target_user_id, None, is_liked=True, remaining_count=len(likes) - 1)
            return
        
        if data == 'dating_my_matches':
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            
            matches = db.get_user_matches(user_id)
            if not matches:
                message = "💑 <b>Мои мэтчи</b>\n\n"
                message += "😔 У вас пока нет мэтчей\n\n"
                message += "💡 Продолжайте просматривать анкеты и ставить лайки!"
            else:
                message = "💑 <b>Мои мэтчи</b>\n\n"
                message += f"✨ <b>У вас {len(matches)} мэтч(ей):</b>\n\n"
                for match in matches:
                    matched_user_id = match['matched_user_id']
                    matched_user = db.get_user(matched_user_id)
                    if matched_user:
                        username = matched_user.get('username', 'не указан')
                        first_name = matched_user.get('first_name', '')
                        name = f"@{username}" if username != 'не указан' else (first_name or f"ID {matched_user_id}")
                        message += f"💕 {name}\n"
                    else:
                        message += f"💕 ID {matched_user_id}\n"
            keyboard = [
                [InlineKeyboardButton("👀 Смотреть анкеты", callback_data='dating_view_profiles')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
            ]
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == 'dating_next_liked_user':
            # Удаляем предыдущее сообщение с фото
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            
            # Показать следующую анкету из списка лайкнувших
            state_data = db.get_user_state(user_id)
            if state_data and state_data.get('state') == 'dating_viewing_likes':
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                # Обновляем список - исключаем тех, на кого уже поставлен лайк/дизлайк
                all_likes = db.get_likes_received(user_id)
                liked_user_ids = [like['from_user_id'] for like in all_likes]
                
                current_index = state_data_dict.get('current_index', 0) + 1
                
                if current_index < len(liked_user_ids):
                    state_data_dict['current_index'] = current_index
                    state_data_dict['liked_user_ids'] = liked_user_ids  # Обновляем список
                    db.set_user_state(user_id, 'dating_viewing_likes', state_data_dict)
                    target_user_id = liked_user_ids[current_index]
                    remaining_count = len(liked_user_ids) - current_index - 1
                    await show_dating_profile_by_id(user_id, target_user_id, None, is_liked=True, remaining_count=remaining_count)
                else:
                    message = "✅ <b>Вы просмотрели всех, кто вас лайкнул!</b>\n\n"
                    message += "💡 Продолжайте просматривать анкеты, и вы обязательно найдете свою пару!"
                    keyboard = [
                        [InlineKeyboardButton("👀 Смотреть анкеты", callback_data='dating_view_profiles')],
                        [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
                    ]
                    db.clear_user_state(user_id)
                    await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith('dating_select_gender_'):
            # Сохраняем пол и переходим к выбору "кого ищет"
            gender = data.split('_')[3]  # male или female
            state_data = db.get_user_state(user_id)
            # Проверяем состояние - может быть после загрузки фото или уже выбран пол
            if state_data:
                import json
                # Парсим data из JSON строки, если это строка
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                photo_file_id = None
                # Если состояние содержит фото
                if state_data.get('state') in ['dating_waiting_photo', 'dating_waiting_photo_edit']:
                    photo_file_id = state_data_dict.get('photo_file_id')
                # Или если уже есть состояние с фото и полом
                elif state_data.get('state', '').startswith('dating_waiting_looking_for_'):
                    photo_file_id = state_data_dict.get('photo_file_id')
                
                if photo_file_id:
                    # Сохраняем пол и переходим к выбору "кого ищет"
                    db.set_user_state(user_id, f'dating_waiting_looking_for_{gender}', {'photo_file_id': photo_file_id, 'gender': gender})
                    message = "🔍 <b>Шаг 3:</b> Кого вы ищете?\n\n"
                    message += "Выберите, кого вы хотите найти:"
                    keyboard = [
                        [InlineKeyboardButton("👨 Парней", callback_data=f'dating_select_looking_male_{gender}')],
                        [InlineKeyboardButton("👩 Девушек", callback_data=f'dating_select_looking_female_{gender}')],
                        [InlineKeyboardButton("👥 Всех", callback_data=f'dating_select_looking_both_{gender}')],
                        [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
                    ]
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await send_message(user_id, "❌ Ошибка: фото не найдено. Начните заново.")
            else:
                await send_message(user_id, "❌ Ошибка: сессия истекла. Начните создание анкеты заново.")
            return
        
        if data.startswith('dating_select_looking_'):
            # Сохраняем "кого ищет" и переходим к вводу имени
            parts = data.split('_')
            looking_for = parts[3]  # male, female или both
            gender = parts[4]  # male или female
            state_data = db.get_user_state(user_id)
            if state_data:
                import json
                # Парсим data из JSON строки, если это строка
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                photo_file_id = state_data_dict.get('photo_file_id')
                if photo_file_id:
                    # Сохраняем данные и переходим к вводу имени
                    state_data_dict.update({
                        'photo_file_id': photo_file_id,
                        'gender': gender,
                        'looking_for': looking_for
                    })
                    db.set_user_state(user_id, 'dating_waiting_name', state_data_dict)
                    message = "📝 <b>Шаг 4:</b> Укажите ваше имя\n\n"
                    message += "💡 <i>Введите ваше имя (или как вас называть)</i>"
                    # Сохраняем информацию для возврата на шаг 3
                    back_callback = f'dating_back_to_looking_{gender}'
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Назад", callback_data=back_callback)
                    ]]))
                else:
                    await send_message(user_id, "❌ Ошибка: фото не найдено. Начните заново.")
            return
        
        # Обработка возврата на шаг 3 (выбор "кого ищет")
        if data.startswith('dating_back_to_looking_'):
            gender = data.replace('dating_back_to_looking_', '')
            state_data = db.get_user_state(user_id)
            if state_data:
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                photo_file_id = state_data_dict.get('photo_file_id')
                if photo_file_id:
                    # Восстанавливаем состояние для шага 3
                    db.set_user_state(user_id, f'dating_waiting_looking_for_{gender}', {'photo_file_id': photo_file_id, 'gender': gender})
                    message = "🔍 <b>Шаг 3:</b> Кого вы ищете?\n\n"
                    message += "Выберите, кого вы хотите найти:"
                    keyboard = [
                        [InlineKeyboardButton("👨 Парней", callback_data=f'dating_select_looking_male_{gender}')],
                        [InlineKeyboardButton("👩 Девушек", callback_data=f'dating_select_looking_female_{gender}')],
                        [InlineKeyboardButton("👥 Всех", callback_data=f'dating_select_looking_both_{gender}')],
                        [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
                    ]
                    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await send_message(user_id, "❌ Ошибка: фото не найдено. Начните заново.")
            return
        
        # Если callback_data не обработан, логируем это
        logger.warning(f"Unhandled callback_data: {data} from user {user_id}")
        try:
            await send_message(user_id, f"❌ Неизвестная команда. Попробуйте /start")
        except:
            pass
        
    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)
        logger.error(f"Callback data that caused error: {data if 'data' in locals() else 'unknown'}")
        try:
            if query:
                await query.answer("❌ Произошла ошибка. Попробуйте позже.")
            if 'user_id' in locals():
                await send_message(user_id, "❌ Ошибка обработки действия. Попробуйте еще раз через 2-3 секунды.")
        except:
            pass

def generate_manual_order_id() -> str:
    """Генерирует ID заказа для ручной оплаты"""
    return f"MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

async def finalize_approved_payment(payment_request: dict):
    """Финализирует подтвержденную админом оплату: создает билеты и отправляет QR"""
    user_id = int(payment_request['user_id'])
    order_id = payment_request['order_id']

    payload = {}
    if payment_request.get('payload'):
        try:
            payload = json.loads(payment_request['payload'])
        except Exception:
            payload = {}

    ticket_type = payload.get('ticket_type', payment_request.get('ticket_type'))
    quantity = int(payload.get('quantity', payment_request.get('quantity', 1)))
    total_price = float(payload.get('total_price', payment_request.get('total_price', 0)))
    bonus_used = float(payload.get('bonus_used', payment_request.get('bonus_used', 0) or 0))
    promo_code = payload.get('promo_code', payment_request.get('promo_code'))
    price_per_ticket = total_price / max(quantity, 1)

    # Начисление/списание бонусов только после подтверждения оплаты
    if bonus_used > 0:
        db.update_user_bonuses(user_id, bonus_used, 'subtract', order_id)
    bonus_earned = round(total_price * config.BONUS_PERCENT)
    new_bonus_balance = db.update_user_bonuses(user_id, bonus_earned, 'add', order_id)

    if promo_code:
        try:
            db.increment_promocode_usage(promo_code)
        except Exception:
            pass

    prefix_map = {
        'vip': 'VIP',
        'vip_standing': 'VPS',
        'couple': 'CPL',
        'regular': 'TKT'
    }
    code_prefix = prefix_map.get(ticket_type, 'TKT')
    code_hash = hashlib.md5(f"{order_id}{user_id}".encode()).hexdigest()[:6].upper()
    base_code = f"{code_prefix}-{datetime.now().strftime('%Y%m%d')}-{code_hash}"

    created_codes = []
    for i in range(1, quantity + 1):
        ticket_code = base_code if quantity == 1 else f"{base_code}-{i}"
        ticket_data = {
            'ticket_code': ticket_code,
            'user_id': user_id,
            'ticket_type': ticket_type,
            'amount': price_per_ticket,
            'bonus_used': bonus_used / quantity if quantity else 0,
            'bonus_earned': bonus_earned / quantity if quantity else 0,
            'referral_bonus_earned': 0,
            'promo_code': promo_code,
            'order_id': order_id,
            'status': 'active'
        }
        db.create_ticket(ticket_data)
        created_codes.append(ticket_code)

        qr_path = generate_qr_code(ticket_data)
        caption = (
            f"🎫 <b>Билет активирован!</b>\n\n"
            f"🎟 <b>Код:</b> <code>{ticket_code}</code>\n"
            f"💰 <b>Оплачено:</b> {price_per_ticket:.2f} руб.\n\n"
            f"<i>Покажите QR-код на входе.</i>"
        )
        qr_file_id = await send_photo(user_id, qr_path, caption=caption)
        if qr_file_id:
            db.execute_query("UPDATE tickets SET qr_file_id = %s WHERE ticket_code = %s", (qr_file_id, ticket_code))

    await send_message(
        user_id,
        f"✅ <b>Оплата подтверждена администратором</b>\n\n"
        f"🎫 Билетов: <b>{quantity}</b>\n"
        f"💎 Начислено бонусов: <b>+{bonus_earned}</b>\n"
        f"🏆 Баланс бонусов: <b>{new_bonus_balance:.2f}</b>\n\n"
        f"QR-коды отправлены выше."
    )
    db.clear_user_state(user_id)

async def process_ticket_purchase(user_id, ticket_type, quantity, query, promo_code=None, bonus_used=0):
    """Обработать покупку билета"""
    if not db.is_bonuses_promocodes_enabled():
        promo_code = None
        bonus_used = 0
    # Лимит: из ticket_categories, если категории нет — из config
    limit = db.get_ticket_limit_from_db(ticket_type)
    if limit is None:
        limit = config.TICKET_LIMITS.get(ticket_type, 0)
    sold = db.count_tickets_by_type(ticket_type)
    available = (limit - sold) if limit > 0 else 999999
    if available < quantity:
        await send_message(user_id, "❌ Недостаточно билетов!")
        return
    
    # Получаем цены
    prices = db.get_prices()
    base_price = prices[ticket_type]['discounted']
    
    # Применяем промокод если есть
    discount_amount = 0
    if promo_code:
        # Сначала проверяем, является ли это промокодом промоутера
        from database import execute_query
        promoter_check = execute_query(
            "SELECT user_id, username, first_name FROM users WHERE promo_code = %s AND role = 'promoter'",
            (promo_code,), fetch=True
        )
        
        if promoter_check:
            # Промокоды промоутеров больше не дают скидку
            logger.info(f"Promoter code {promo_code} used by user {user_id}: no referral discount applied")
        else:
            # Это обычный промокод из таблицы promocodes
            promocode_data = db.get_promocode(promo_code)
            if promocode_data:
                # Проверяем даты действия промокода
                from datetime import datetime, date
                from decimal import Decimal
                today = date.today()
                
                # Проверка start_date
                if promocode_data.get('start_date'):
                    start_date = promocode_data['start_date']
                    try:
                        # Обрабатываем разные форматы даты
                        if isinstance(start_date, str):
                            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                        elif isinstance(start_date, datetime):
                            start_date = start_date.date()
                        elif not isinstance(start_date, date):
                            logger.warning(f"Unexpected start_date type: {type(start_date)} for promocode {promo_code}")
                            start_date = None
                        
                        if start_date and today < start_date:
                            await send_message(user_id, f"❌ Промокод еще не активен. Действует с {start_date.strftime('%d.%m.%Y')}")
                            return
                    except Exception as e:
                        logger.error(f"Error processing start_date for promocode {promo_code}: {e}")
                
                # Проверка end_date
                if promocode_data.get('end_date'):
                    end_date = promocode_data['end_date']
                    try:
                        # Обрабатываем разные форматы даты
                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                        elif isinstance(end_date, datetime):
                            end_date = end_date.date()
                        elif not isinstance(end_date, date):
                            logger.warning(f"Unexpected end_date type: {type(end_date)} for promocode {promo_code}")
                            end_date = None
                        
                        if end_date and today > end_date:
                            await send_message(user_id, f"❌ Промокод истек. Действовал до {end_date.strftime('%d.%m.%Y')}")
                            return
                    except Exception as e:
                        logger.error(f"Error processing end_date for promocode {promo_code}: {e}")
                
                # Проверяем, что промокод активен
                if not promocode_data.get('active', True):
                    await send_message(user_id, "❌ Промокод неактивен")
                    return
                
                # Проверяем категории билетов: если у промокода заданы категории — текущий тип должен входить в список
                allowed_types = promocode_data.get('ticket_types')
                if allowed_types is not None:
                    if isinstance(allowed_types, str):
                        try:
                            import json
                            allowed_types = json.loads(allowed_types)
                        except Exception:
                            allowed_types = None
                    if allowed_types and len(allowed_types) > 0 and ticket_type not in allowed_types:
                        await send_message(user_id, f"❌ Этот промокод не действует для выбранной категории билетов.")
                        return
                
                # Проверяем минимальную сумму заказа
                min_amount = promocode_data.get('min_amount', 0) or 0
                if min_amount:
                    if isinstance(min_amount, Decimal):
                        min_amount = float(min_amount)
                    if base_price * quantity < min_amount:
                        await send_message(user_id, f"❌ Промокод действует только для заказов от {min_amount:.2f} руб.")
                        return
                
                # Применяем скидку (конвертируем Decimal в float)
                promo_value = promocode_data.get('value', 0)
                if promo_value is None:
                    logger.error(f"Promocode {promo_code} has no value")
                    await send_message(user_id, "❌ Ошибка: промокод не имеет значения скидки")
                    return
                    
                if isinstance(promo_value, Decimal):
                    promo_value = float(promo_value)
                elif not isinstance(promo_value, (int, float)):
                    logger.error(f"Promocode {promo_code} has invalid value type: {type(promo_value)}")
                    await send_message(user_id, "❌ Ошибка: неверное значение промокода")
                    return
                
                promo_type = promocode_data.get('type', 'fixed')
                if promo_type == 'percentage':
                    discount_amount = float(base_price) * (promo_value / 100)
                else:  # fixed
                    discount_amount = float(promo_value)
                base_price = max(0, float(base_price) - discount_amount)
            else:
                await send_message(user_id, "❌ Промокод не найден или недействителен")
                return
    
    # Применяем скидку за количество
    if quantity >= config.QUANTITY_DISCOUNT_MIN:
        base_price = base_price * (1 - config.QUANTITY_DISCOUNT_PERCENT)
    
    total_price = base_price * quantity
    
    # Вычитаем бонусы если используются
    if bonus_used > 0:
        total_price = max(0, total_price - bonus_used)
    
    message = f"🎫 <b>Оформление заказа</b>\n\n"
    message += f"📦 <b>Тип:</b> {ticket_type.replace('_', ' ').title()}\n"
    message += f"📦 <b>Количество:</b> {quantity}\n"
    if promo_code:
        # Проверяем, является ли это промокодом промоутера
        from database import execute_query
        promoter_check = execute_query(
            "SELECT user_id FROM users WHERE promo_code = %s AND role = 'promoter'",
            (promo_code,), fetch=True
        )
        if promoter_check:
            message += f"👥 <b>Код промоутера:</b> <code>{promo_code}</code> (без скидки)\n"
        else:
            message += f"🎁 <b>Промокод:</b> {promo_code}\n"
            if discount_amount > 0:
                message += f"💸 <b>Скидка:</b> {discount_amount:.2f} руб.\n"
    if bonus_used > 0:
        message += f"💎 <b>Использовано бонусов:</b> {bonus_used:.2f} руб.\n"
    message += f"💰 <b>Итого к оплате:</b> {total_price:.2f} руб.\n\n"
    message += "⚠️ <b>Временные проблемы с оплатой</b>\n\n"
    message += "Все кто хотят купить билет — пишите менеджеру: @kissmngr"
    
    # Сохраняем данные заказа
    order_id = generate_manual_order_id()
    order_data = {
        'order_id': order_id,
        'ticket_type': ticket_type,
        'quantity': quantity,
        'price_per_ticket': base_price,
        'total_price': total_price,
        'promo_code': promo_code,
        'bonus_used': bonus_used
    }
    db.set_user_state(user_id, 'processing_payment', order_data)
    
    if query:
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=get_payment_menu(order_id, ticket_type, quantity, user_id))
    else:
        await send_message(user_id, message, reply_markup=get_payment_menu(order_id, ticket_type, quantity, user_id))

async def process_ticket_purchase_with_bonus(user_id, ticket_type, quantity, query):
    """Обработать покупку билета с использованием бонусов"""
    if not db.is_bonuses_promocodes_enabled():
        await process_ticket_purchase(user_id, ticket_type, quantity, query, promo_code=None, bonus_used=0)
        return
    limit = db.get_ticket_limit_from_db(ticket_type)
    if limit is None:
        limit = config.TICKET_LIMITS.get(ticket_type, 0)
    sold = db.count_tickets_by_type(ticket_type)
    available = (limit - sold) if limit > 0 else 999999
    if available < quantity:
        await send_message(user_id, "❌ Недостаточно билетов!")
        return
    
    # Получаем цены
    prices = db.get_prices()
    base_price = prices[ticket_type]['discounted']
    
    # Применяем скидку за количество
    if quantity >= config.QUANTITY_DISCOUNT_MIN:
        base_price = base_price * (1 - config.QUANTITY_DISCOUNT_PERCENT)
    
    total_price = base_price * quantity
    
    # Проверяем бонусы
    bonus_balance = db.get_user_bonuses(user_id)
    max_bonus_usage = total_price * config.MAX_BONUS_USAGE_PERCENT
    available_bonus = min(bonus_balance, max_bonus_usage)
    
    if available_bonus <= 0:
        await send_message(user_id, "❌ У вас недостаточно бонусов для использования")
        return
    
    message = f"💎 <b>Использование бонусов</b>\n\n"
    message += f"💰 <b>Сумма заказа:</b> {total_price:.2f} руб.\n"
    message += f"💎 <b>Доступно бонусов:</b> {available_bonus:.2f} руб.\n"
    message += f"💎 <b>Максимум можно использовать:</b> {max_bonus_usage:.2f} руб. (50% от суммы)\n\n"
    message += "📝 <b>Введите сумму бонусов для использования:</b>"
    
    db.set_user_state(user_id, f'waiting_bonus_{ticket_type}_{quantity}')
    await edit_message_safe(query, message, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    user_id = user.id
    text = update.message.text
    
    # Проверяем состояние пользователя
    state_data = db.get_user_state(user_id)
    if state_data:
        state = state_data.get('state')
        
        if state.startswith('waiting_promocode_'):
            # Обработка промокода при покупке
            try:
                parts = state.split('_')
                ticket_type = parts[2]
                quantity = int(parts[3])
                if not db.is_bonuses_promocodes_enabled():
                    await process_ticket_purchase(user_id, ticket_type, quantity, None, promo_code=None, bonus_used=0)
                    db.clear_user_state(user_id)
                    return
                
                # Импортируем execute_query для проверки промокодов промоутеров
                from database import execute_query
                
                promo_code_upper = text.strip().upper()
                logger.info(f"Processing promocode: {promo_code_upper} for user {user_id}, ticket_type: {ticket_type}, quantity: {quantity}")
                
                # Проверяем, не пытается ли пользователь использовать промокод промоутера вручную
                promoter_check = execute_query(
                    "SELECT user_id FROM users WHERE promo_code = %s AND role = 'promoter'",
                    (promo_code_upper,), fetch=True
                )
                
                if promoter_check:
                    await send_message(user_id,
                        "ℹ️ <b>Это код промоутера.</b>\n\n"
                        "По рефералке скидка больше не применяется.\n"
                        "Используйте обычный промокод для скидки.",
                        parse_mode='HTML')
                    db.clear_user_state(user_id)
                    return
                
                promocode = db.get_promocode(promo_code_upper)
                if promocode:
                    logger.info(f"Promocode found: {promocode}")
                    # Проверяем, можно ли использовать промокод
                    # Обрабатываем NULL значения для max_uses (0 или None = бесконечные использования)
                    max_uses = promocode.get('max_uses') or 0
                    used_count = promocode.get('used_count') or 0
                    if max_uses > 0 and used_count >= max_uses:
                        await send_message(user_id, "❌ Промокод исчерпал лимит использований")
                        db.clear_user_state(user_id)
                        return
                    
                    # Применяем промокод (внутри функции будут дополнительные проверки)
                    await process_ticket_purchase(user_id, ticket_type, quantity, None, promo_code=promo_code_upper, bonus_used=0)
                    # Увеличиваем счетчик только если покупка прошла успешно
                    # (счетчик будет увеличен после успешной оплаты в robokassa_handler)
                    # НЕ очищаем состояние — process_ticket_purchase установила 'processing_payment'
                else:
                    logger.warning(f"Promocode not found: {promo_code_upper}")
                    await send_message(user_id, "❌ Промокод не найден или недействителен")
                    db.clear_user_state(user_id)
            except Exception as e:
                logger.error(f"Error processing promocode '{promo_code_upper}' for user {user_id}: {e}", exc_info=True)
                logger.error(f"Promocode data: {promocode if 'promocode' in locals() else 'Not found'}")
                await send_message(user_id, "❌ Произошла ошибка при обработке промокода. Попробуйте еще раз.")
                db.clear_user_state(user_id)
            return
        
        if state.startswith('waiting_bonus_'):
            # Обработка ввода суммы бонусов
            parts = state.split('_')
            ticket_type = parts[2]
            quantity = int(parts[3])
            if not db.is_bonuses_promocodes_enabled():
                await process_ticket_purchase(user_id, ticket_type, quantity, None, promo_code=None, bonus_used=0)
                db.clear_user_state(user_id)
                return
            try:
                bonus_amount = float(text)
                bonus_balance = db.get_user_bonuses(user_id)
                prices = db.get_prices()
                base_price = prices[ticket_type]['discounted']
                
                if quantity >= config.QUANTITY_DISCOUNT_MIN:
                    base_price = base_price * (1 - config.QUANTITY_DISCOUNT_PERCENT)
                
                total_price = base_price * quantity
                max_bonus_usage = total_price * config.MAX_BONUS_USAGE_PERCENT
                
                if bonus_amount <= 0:
                    await send_message(user_id, "❌ Сумма должна быть больше 0")
                    return
                if bonus_amount > bonus_balance:
                    await send_message(user_id, f"❌ У вас недостаточно бонусов. Доступно: {bonus_balance:.2f} руб.")
                    return
                if bonus_amount > max_bonus_usage:
                    await send_message(user_id, f"❌ Можно использовать максимум {max_bonus_usage:.2f} руб. (50% от суммы)")
                    return
                
                await process_ticket_purchase(user_id, ticket_type, quantity, None, promo_code=None, bonus_used=bonus_amount)
                # НЕ очищаем состояние — process_ticket_purchase установила 'processing_payment'
            except ValueError:
                await send_message(user_id, "❌ Введите корректную сумму (число)")
                return
            return
        
        # Обработка ввода данных для анкеты "Поиск пары"
        if state == 'dating_waiting_name':
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            name = text.strip()
            if len(name) > 255:
                await send_message(user_id, "❌ Имя слишком длинное (максимум 255 символов). Попробуйте еще раз.")
                return
            
            state_data_dict['name'] = name
            db.set_user_state(user_id, 'dating_waiting_age', state_data_dict)
            await send_message(user_id, "🎂 <b>Шаг 5:</b> Укажите ваш возраст\n\n💡 <i>Введите ваш возраст (число от 14 до 100)</i>")
            return
        
        if state == 'dating_waiting_age':
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            try:
                age = int(text.strip())
                if age < 14 or age > 100:
                    await send_message(user_id, "❌ Возраст должен быть от 14 до 100 лет. Попробуйте еще раз.")
                    return
                
                state_data_dict['age'] = age
                db.set_user_state(user_id, 'dating_waiting_description', state_data_dict)
                await send_message(user_id, "📝 <b>Шаг 6:</b> Напишите описание о себе\n\n💡 <i>Расскажите о себе, своих интересах, что вы ищете. Это поможет другим лучше узнать вас!</i>\n\n💡 <i>Можно пропустить этот шаг, отправив /skip</i>")
            except ValueError:
                await send_message(user_id, "❌ Пожалуйста, введите число (возраст).")
            return
        
        if state == 'dating_waiting_description':
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            description = text.strip() if text.strip().lower() != '/skip' else None
            
            # Создаем анкету
            photo_file_id = state_data_dict.get('photo_file_id')
            gender = state_data_dict.get('gender')
            looking_for = state_data_dict.get('looking_for')
            name = state_data_dict.get('name')
            age = state_data_dict.get('age')
            
            if photo_file_id and gender and looking_for:
                if db.create_dating_profile(user_id, photo_file_id, gender, looking_for, name, age, description):
                    message = "✅ <b>Анкета успешно создана!</b>\n\n"
                    message += "🎉 Теперь вы можете просматривать анкеты других пользователей и найти свою пару!"
                    keyboard = [
                        [InlineKeyboardButton("👀 Смотреть анкеты", callback_data='dating_view_profiles')],
                        [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
                    ]
                    db.clear_user_state(user_id)
                    await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await send_message(user_id, "❌ Ошибка при создании анкеты. Попробуйте позже.")
            else:
                await send_message(user_id, "❌ Ошибка: данные анкеты не найдены. Начните заново.")
                db.clear_user_state(user_id)
            return
        
        if state.startswith('waiting_quantity_'):
            try:
                quantity = int(text)
                if 1 <= quantity <= 10:
                    ticket_type = state.replace('waiting_quantity_', '')
                    
                    # Проверяем доступность категории
                    category = db.get_ticket_category(ticket_type)
                    if not category or not category.get('is_active'):
                        await send_message(user_id, "❌ <b>Категория билетов недоступна</b>", 
                                         reply_markup=InlineKeyboardMarkup([[
                                             InlineKeyboardButton("◀️ Назад к билетам", callback_data='show_tickets')
                                         ]]))
                        db.clear_user_state(user_id)
                        return
                    
                    # Проверяем доступность билетов
                    available = category['limit'] - category['sold_count'] if category['limit'] > 0 else 999999
                    
                    if available < quantity:
                        message = f"❌ <b>Недостаточно билетов!</b>\n\n"
                        message += f"Вы запросили: {quantity} шт.\n\n"
                        
                        # Получаем доступные категории
                        all_categories = db.get_all_ticket_categories(active_only=True)
                        available_categories = [cat for cat in all_categories 
                                             if cat['code'] != ticket_type and 
                                             (cat['limit'] == 0 or (cat['limit'] - cat['sold_count']) > 0)]
                        
                        keyboard = []
                        if available_categories:
                            message += "💡 <b>Вы можете выбрать другую категорию:</b>\n\n"
                            for cat in available_categories[:5]:
                                emoji = "🎫"
                                if 'vip' in cat['code'].lower() or 'вип' in cat['name'].lower():
                                    emoji = "💎"
                                elif 'couple' in cat['code'].lower() or 'парн' in cat['name'].lower():
                                    emoji = "👫"
                                message += f"{emoji} <b>{cat['name']}</b> — {cat['discounted_price']:.0f}₽\n"
                                keyboard.append([InlineKeyboardButton(
                                    f"{emoji} {cat['name']} — {cat['discounted_price']:.0f}₽",
                                    callback_data=f'{cat["code"]}_ticket'
                                )])
                        keyboard.append([InlineKeyboardButton("◀️ Назад к билетам", callback_data='show_tickets')])
                        await send_message(user_id, message, reply_markup=InlineKeyboardMarkup(keyboard))
                        db.clear_user_state(user_id)
                        return
                    
                    # Показываем меню выбора: промокод или бонусы (если разрешено)
                    if not db.is_bonuses_promocodes_enabled():
                        await process_ticket_purchase(user_id, ticket_type, quantity, None, promo_code=None, bonus_used=0)
                    else:
                        message = f"🎫 <b>Оформление заказа</b>\n\n"
                        message += f"📦 <b>Тип:</b> {category['name']}\n"
                        message += f"📦 <b>Количество:</b> {quantity}\n\n"
                        message += "💡 <b>Хотите использовать промокод или бонусы?</b>\n"
                        message += "(Можно выбрать только что-то одно)"
                        await send_message(user_id, message, reply_markup=get_promocode_or_bonus_menu(ticket_type, quantity))
                    db.clear_user_state(user_id)
                else:
                    await send_message(user_id, "❌ Количество должно быть от 1 до 10")
            except ValueError:
                await send_message(user_id, "❌ Введите число от 1 до 10")
            return
        
        if state.startswith('support_ticket_message_'):
            # Обработка сообщений в тикет поддержки
            ticket_id = state.replace('support_ticket_message_', '')
            ticket = db.get_support_ticket(ticket_id)
            
            if not ticket:
                await send_message(user_id, "❌ Тикет не найден")
                db.clear_user_state(user_id)
                return
            
            if ticket['user_id'] != user_id:
                await send_message(user_id, "❌ У вас нет доступа к этому тикету")
                db.clear_user_state(user_id)
                return
            
            # Добавляем сообщение в тикет
            db.add_support_message(ticket_id, user_id, text, 'text')
            
            # Отправляем подтверждение пользователю
            await send_message(user_id, "✅ <b>Сообщение отправлено в поддержку!</b>\n\nМы ответим вам в ближайшее время.",
                             reply_markup=InlineKeyboardMarkup([[
                                 InlineKeyboardButton("◀️ К тикету", callback_data=f'view_ticket_{ticket_id}')
                             ]]))
            
            # Уведомляем админов
            await notify_admins_new_ticket_message(ticket_id, user_id, text)
            
            db.clear_user_state(user_id)
            return
        
        if state.startswith('admin_support_reply_'):
            # Обработка ответа админа в тикет
            ticket_id = state.replace('admin_support_reply_', '')
            ticket = db.get_support_ticket(ticket_id)
            
            if not ticket:
                await send_message(user_id, "❌ Тикет не найден")
                db.clear_user_state(user_id)
                return
            
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Добавляем сообщение от админа
            db.add_support_message(ticket_id, user_id, text, 'text', is_admin=True)
            
            # Отправляем сообщение пользователю
            user = db.get_user(ticket['user_id'])
            if user:
                try:
                    await bot.send_message(
                        chat_id=ticket['user_id'],
                        text=f"💬 <b>Ответ от поддержки</b>\n\n{text}",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("💬 Открыть тикет", callback_data=f'view_ticket_{ticket_id}')
                        ]])
                    )
                except Exception as e:
                    logger.error(f"Error sending message to user {ticket['user_id']}: {e}")
            
            await send_message(user_id, "✅ <b>Ответ отправлен пользователю!</b>",
                             reply_markup=InlineKeyboardMarkup([[
                                 InlineKeyboardButton("◀️ К тикету", callback_data=f'admin_view_ticket_{ticket_id}')
                             ]]))
            
            db.clear_user_state(user_id)
            return
        
        if state == 'admin_editing_menu_text':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Сохраняем новый текст (убеждаемся, что эмодзи сохраняются правильно)
            try:
                # Проверяем, что текст правильно закодирован
                text_encoded = text.encode('utf-8').decode('utf-8')
                db.set_bot_setting('main_menu_text', text_encoded)
                logger.info(f"Main menu text updated, length: {len(text_encoded)}")
            except Exception as e:
                logger.error(f"Error saving main menu text: {e}", exc_info=True)
                await send_message(user_id, "❌ Ошибка при сохранении текста. Попробуйте еще раз.")
                return
            await send_message(user_id, "✅ <b>Текст главного меню обновлен!</b>\n\n"
                              "📷 <b>Хотите добавить изображение?</b> Отправьте фото или нажмите 'Пропустить'",
                              reply_markup=InlineKeyboardMarkup([[
                                  InlineKeyboardButton("⏭️ Пропустить", callback_data='admin_menu_skip_image')
                              ]]))
            db.set_user_state(user_id, 'admin_editing_menu_image')
            return
        
        if state == 'admin_editing_menu_image':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            # Это обрабатывается в handle_photo
            return
        
        # ============================================
        # ОБРАБОТКА РЕДАКТИРОВАНИЯ ЦЕН БИЛЕТОВ
        # ============================================
        if state.startswith('admin_editing_price_base_'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            ticket_type = state.replace('admin_editing_price_base_', '')
            
            try:
                base_price = float(text.strip())
                if base_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                # Сохраняем базовую цену и переходим к цене со скидкой
                import json
                price_data = {'base': base_price, 'ticket_type': ticket_type}
                db.set_user_state(user_id, f'admin_editing_price_discounted_{ticket_type}', price_data)
                
                type_names = {
                    'regular': 'Обычный билет',
                    'vip': 'VIP билет',
                    'vip_standing': 'VIP стоячий',
                    'couple': 'Парный билет'
                }
                
                message = f"✅ <b>Базовая цена сохранена:</b> {base_price:.0f}₽\n\n"
                message += f"📝 <b>Введите цену со скидкой:</b>\n"
                message += f"💡 <i>Обычно это та же цена или меньше (например: {base_price:.0f})</i>"
                
                keyboard = [
                    [InlineKeyboardButton("❌ Отменить", callback_data='admin_prices')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 850)")
            return
        
        if state.startswith('admin_editing_price_discounted_'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            ticket_type = state.replace('admin_editing_price_discounted_', '')
            
            try:
                discounted_price = float(text.strip())
                if discounted_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                # Получаем базовую цену из состояния
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                base_price = state_data_dict.get('base', discounted_price)
                
                # Пытаемся обновить категорию в БД
                category = db.get_ticket_category(ticket_type)
                if category:
                    # Обновляем категорию в БД
                    if db.update_ticket_category(ticket_type, base_price=base_price, discounted_price=discounted_price):
                        category_name = category['name']
                    else:
                        await send_message(user_id, "❌ Ошибка при обновлении цен")
                        db.clear_user_state(user_id)
                        return
                else:
                    # Обновляем старую таблицу price_settings
                    db.execute_query(
                        """UPDATE price_settings 
                           SET base_price = %s, discounted_price = %s 
                           WHERE ticket_type = %s""",
                        (base_price, discounted_price, ticket_type)
                    )
                    type_names = {
                        'regular': 'Обычный билет',
                        'vip': 'VIP билет',
                        'vip_standing': 'VIP стоячий',
                        'couple': 'Парный билет'
                    }
                    category_name = type_names.get(ticket_type, ticket_type)
                
                message = f"✅ <b>Цены успешно обновлены!</b>\n\n"
                message += f"🎫 <b>{category_name}</b>\n"
                message += f"💰 Базовая цена: {base_price:.0f}₽\n"
                message += f"💎 Цена со скидкой: {discounted_price:.0f}₽\n\n"
                message += "💡 <b>Изменения вступят в силу сразу!</b>"
                
                keyboard = [
                    [InlineKeyboardButton("◀️ Назад к ценам", callback_data='admin_prices')],
                    [InlineKeyboardButton("🏠 Админ-панель", callback_data='admin_panel')]
                ]
                
                db.clear_user_state(user_id)
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 850)")
            return
        
        # ============================================
        # ОБРАБОТКА УПРАВЛЕНИЯ РОЛЯМИ
        # ============================================
        if state == 'admin_searching_promoter_id':
            # Поиск промоутера по ID
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                search_id = int(text.strip())
                # Проверяем, является ли пользователь промоутером
                user = db.get_user(search_id)
                if not user:
                    await send_message(user_id, 
                        f"❌ <b>Пользователь не найден</b>\n\n"
                        f"Пользователь с ID <code>{search_id}</code> не найден в базе данных.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                        ]]))
                    db.clear_user_state(user_id)
                    return
                
                if user.get('role') != 'promoter':
                    await send_message(user_id,
                        f"❌ <b>Пользователь не является промоутером</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{search_id}</code>\n"
                        f"👤 <b>Username:</b> @{user.get('username', 'Нет username')}\n"
                        f"👤 <b>Имя:</b> {user.get('first_name', 'Без имени')}\n"
                        f"👤 <b>Роль:</b> {user.get('role', 'user')}\n\n"
                        f"💡 Этот пользователь не является промоутером.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                        ]]))
                    db.clear_user_state(user_id)
                    return
                
                # Пользователь является промоутером - показываем детальную информацию
                stats = db.get_promoter_detailed_stats(search_id)
                if not stats:
                    await send_message(user_id,
                        f"❌ <b>Ошибка получения статистики</b>\n\n"
                        f"Не удалось получить статистику для промоутера {search_id}.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                        ]]))
                    db.clear_user_state(user_id)
                    return
                
                # Проверяем статус активности
                is_active = db.is_promoter_active(search_id)
                
                # Формируем сообщение с детальной информацией (используем тот же формат, что и в callback)
                message = "👤 <b>Детальная информация о промоутере</b>\n\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                # Основная информация
                message += "📋 <b>Основная информация:</b>\n"
                message += f"🆔 <b>ID:</b> <code>{stats['user_id']}</code>\n"
                if stats.get('username'):
                    message += f"👤 <b>Username:</b> @{stats['username']}\n"
                if stats.get('first_name'):
                    message += f"👤 <b>Имя:</b> {stats['first_name']}"
                    if stats.get('last_name'):
                        message += f" {stats['last_name']}"
                    message += "\n"
                message += f"🎫 <b>Промокод:</b> <code>{stats.get('promo_code', 'Нет кода')}</code>\n"
                message += f"⭐ <b>Статус:</b> {'✅ Активный' if is_active else '❌ Неактивный'}\n"
                if stats.get('created_at'):
                    created = stats['created_at']
                    if isinstance(created, str):
                        try:
                            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        except:
                            try:
                                created = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                            except:
                                created = None
                    if created and hasattr(created, 'strftime'):
                        message += f"📅 <b>Дата регистрации:</b> {created.strftime('%d.%m.%Y %H:%M')}\n"
                message += "\n"
                
                # Статистика
                message += "📊 <b>Статистика:</b>\n"
                message += f"👥 <b>Приглашено пользователей:</b> {stats.get('invited_users', 0)}\n"
                message += f"🛒 <b>Количество покупок:</b> {stats.get('purchases_count', 0)}\n"
                message += f"💰 <b>Выручка:</b> {stats.get('revenue', 0.0):.2f}₽\n"
                message += f"🎟️ <b>Использовано билетов:</b> {stats.get('used_tickets', 0)}\n"
                
                # Статистика по типам билетов
                tickets_by_type = stats.get('tickets_by_type', {})
                if tickets_by_type:
                    message += "\n📦 <b>По типам билетов:</b>\n"
                    type_names = {
                        'regular': 'Обычный',
                        'vip': 'VIP',
                        'vip_standing': 'VIP стоячий',
                        'couple': 'Парный'
                    }
                    for ticket_type, data in tickets_by_type.items():
                        type_name = type_names.get(ticket_type, ticket_type)
                        message += f"  • {type_name}: {data['count']} шт. ({data['revenue']:.2f}₽)\n"
                
                # Даты покупок
                if stats.get('first_purchase'):
                    first = stats['first_purchase']
                    if isinstance(first, str):
                        try:
                            first = datetime.fromisoformat(first.replace('Z', '+00:00'))
                        except:
                            try:
                                first = datetime.strptime(first, '%Y-%m-%d %H:%M:%S')
                            except:
                                first = None
                    if first and hasattr(first, 'strftime'):
                        message += f"\n📅 <b>Первая покупка:</b> {first.strftime('%d.%m.%Y %H:%M')}\n"
                if stats.get('last_purchase'):
                    last = stats['last_purchase']
                    if isinstance(last, str):
                        try:
                            last = datetime.fromisoformat(last.replace('Z', '+00:00'))
                        except:
                            try:
                                last = datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
                            except:
                                last = None
                    if last and hasattr(last, 'strftime'):
                        message += f"📅 <b>Последняя покупка:</b> {last.strftime('%d.%m.%Y %H:%M')}\n"
                
                # Последние покупки
                recent_purchases = stats.get('recent_purchases', [])
                if recent_purchases:
                    message += "\n🛒 <b>Последние покупки:</b>\n"
                    for purchase in recent_purchases[:5]:
                        username = purchase.get('username', 'Нет username')
                        amount = purchase.get('amount', 0)
                        created = purchase.get('created_at')
                        if isinstance(created, str):
                            try:
                                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                created_str = created_dt.strftime('%d.%m %H:%M')
                            except:
                                try:
                                    created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                                    created_str = created_dt.strftime('%d.%m %H:%M')
                                except:
                                    created_str = str(created)
                        elif created and hasattr(created, 'strftime'):
                            created_str = created.strftime('%d.%m %H:%M')
                        else:
                            created_str = str(created)
                        message += f"  • @{username}: {amount:.2f}₽ ({created_str})\n"
                
                keyboard = [
                    [InlineKeyboardButton(
                        "⭐ Отметить активным" if not is_active else "❌ Отметить неактивным",
                        callback_data=f'admin_toggle_promoter_active_{search_id}'
                    )],
                    [InlineKeyboardButton("🔄 Обновить", callback_data=f'admin_promoter_{search_id}')],
                    [InlineKeyboardButton("❌ Удалить промоутера", callback_data=f'admin_remove_promoter_{search_id}')],
                    [InlineKeyboardButton("◀️ Назад к списку", callback_data='admin_promoters')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                db.clear_user_state(user_id)
                
            except ValueError:
                await send_message(user_id,
                    "❌ <b>Неверный формат ID</b>\n\n"
                    "💡 ID должен быть числом (например: 123456789)\n\n"
                    "Попробуйте еще раз:",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ Отменить", callback_data='admin_promoters')
                    ]]))
            return
        
        if state == 'admin_setting_role':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                target_user_id = int(text.strip())
                
                # Проверяем, существует ли пользователь
                target_user_db = db.get_user(target_user_id)
                if not target_user_db:
                    # Пытаемся получить информацию о пользователе через API
                    try:
                        target_user = await bot.get_chat(target_user_id)
                        # Создаем пользователя, если его нет в БД
                        db.create_user(
                            user_id=target_user_id,
                            username=target_user.username,
                            first_name=target_user.first_name,
                            last_name=target_user.last_name
                        )
                    except Exception as e:
                        await send_message(user_id, f"❌ Пользователь с ID {target_user_id} не найден.\n\nПроверьте правильность ID.")
                        return
                
                # Получаем информацию о пользователе
                try:
                    target_user = await bot.get_chat(target_user_id)
                    username = target_user.username or 'N/A'
                    first_name = target_user.first_name or 'N/A'
                    current_role = target_user_db.get('role', 'user') if target_user_db else 'user'
                except:
                    username = 'N/A'
                    first_name = 'N/A'
                    current_role = target_user_db.get('role', 'user') if target_user_db else 'user'
                
                role_names = {
                    'admin': 'Администратор',
                    'moderator': 'Модератор',
                    'promoter': 'Промоутер',
                    'user': 'Пользователь'
                }
                
                message = f"👤 <b>Назначение роли</b>\n\n"
                message += f"🆔 <b>ID пользователя:</b> <code>{target_user_id}</code>\n"
                message += f"👤 <b>Имя:</b> {first_name}\n"
                message += f"📝 <b>Username:</b> @{username}\n"
                message += f"👤 <b>Текущая роль:</b> {role_names.get(current_role, current_role)}\n\n"
                message += "Выберите роль для назначения:"
                
                keyboard = [
                    [InlineKeyboardButton("👑 Администратор", callback_data=f'admin_set_role_{target_user_id}_admin')],
                    [InlineKeyboardButton("🛡️ Модератор", callback_data=f'admin_set_role_{target_user_id}_moderator')],
                    [InlineKeyboardButton("👤 Промоутер", callback_data=f'admin_set_role_{target_user_id}_promoter')],
                    [InlineKeyboardButton("👥 Пользователь", callback_data=f'admin_set_role_{target_user_id}_user')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_roles')]
                ]
                
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                db.clear_user_state(user_id)
            except ValueError:
                await send_message(user_id, "❌ Введите корректный ID пользователя (число, например: 123456789)")
            return
        
        # ============================================
        # ОБРАБОТКА СОЗДАНИЯ ПОСТОВ (РАССЫЛОК)
        # ============================================
        if state == 'admin_broadcasting_text':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Сохраняем текст поста и entities для сохранения форматирования
            import json
            from telegram import MessageEntity
            
            # Получаем entities из сообщения
            entities = []
            if update.message and update.message.entities:
                for entity in update.message.entities:
                    entity_dict = {
                        'type': entity.type,
                        'offset': entity.offset,
                        'length': entity.length
                    }
                    # Добавляем дополнительные поля, если они есть
                    if entity.url:
                        entity_dict['url'] = entity.url
                    if entity.user:
                        entity_dict['user'] = {
                            'id': entity.user.id,
                            'is_bot': entity.user.is_bot,
                            'first_name': entity.user.first_name
                        }
                    if entity.language:
                        entity_dict['language'] = entity.language
                    entities.append(entity_dict)
            
            post_data = {
                'text': text, 
                'type': 'text',
                'entities': entities if entities else None
            }
            logger.info(f"Saving post data for user {user_id}: text length={len(text)}, entities count={len(entities)}")
            db.set_user_state(user_id, 'admin_broadcast_ready', post_data)
            logger.info(f"Post data saved, state set to 'admin_broadcast_ready'")
            
            # Проверяем, что данные сохранились
            check_state = db.get_user_state(user_id)
            logger.info(f"Verification: state after save = {check_state}")
            
            await send_message(user_id,
                f"📝 <b>Предпросмотр поста:</b>\n\n{text}\n\n"
                "🔘 <b>Добавить кнопку 'Купить билет'?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Да, добавить кнопку", callback_data='admin_confirm_broadcast_text_with_button')],
                    [InlineKeyboardButton("❌ Нет, без кнопки", callback_data='admin_confirm_broadcast_text_no_button')],
                    [InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')]
                ]))
            return
        
        if state.startswith('admin_broadcasting_photo'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Сохраняем текст для фото (фото будет отправлено отдельно) и entities
            import json
            from telegram import MessageEntity
            
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            # Получаем entities из сообщения
            entities = []
            if update.message and update.message.entities:
                for entity in update.message.entities:
                    entity_dict = {
                        'type': entity.type,
                        'offset': entity.offset,
                        'length': entity.length
                    }
                    if entity.url:
                        entity_dict['url'] = entity.url
                    if entity.user:
                        entity_dict['user'] = {
                            'id': entity.user.id,
                            'is_bot': entity.user.is_bot,
                            'first_name': entity.user.first_name
                        }
                    if entity.language:
                        entity_dict['language'] = entity.language
                    entities.append(entity_dict)
            
            state_data_dict['text'] = text
            state_data_dict['entities'] = entities if entities else None
            db.set_user_state(user_id, 'admin_broadcast_text_photo', state_data_dict)
            
            await send_message(user_id,
                f"📝 <b>Текст сохранен:</b>\n\n{text}\n\n"
                "🖼️ <b>Теперь отправьте фото</b> (можно с подписью):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')
                ]]))
            return
        
        if state.startswith('admin_broadcasting_video'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Сохраняем текст для видео (видео будет отправлено отдельно) и entities
            import json
            from telegram import MessageEntity
            
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            # Получаем entities из сообщения
            entities = []
            if update.message and update.message.entities:
                for entity in update.message.entities:
                    entity_dict = {
                        'type': entity.type,
                        'offset': entity.offset,
                        'length': entity.length
                    }
                    if entity.url:
                        entity_dict['url'] = entity.url
                    if entity.user:
                        entity_dict['user'] = {
                            'id': entity.user.id,
                            'is_bot': entity.user.is_bot,
                            'first_name': entity.user.first_name
                        }
                    if entity.language:
                        entity_dict['language'] = entity.language
                    entities.append(entity_dict)
            
            state_data_dict['text'] = text
            state_data_dict['entities'] = entities if entities else None
            db.set_user_state(user_id, 'admin_broadcast_text_video', state_data_dict)
            
            await send_message(user_id,
                f"📝 <b>Текст сохранен:</b>\n\n{text}\n\n"
                "🎥 <b>Теперь отправьте видео</b> (можно с подписью):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')
                ]]))
            return
        
        if state.startswith('admin_broadcasting_document'):
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            # Сохраняем текст для документа (документ будет отправлен отдельно) и entities
            import json
            from telegram import MessageEntity
            
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            # Получаем entities из сообщения
            entities = []
            if update.message and update.message.entities:
                for entity in update.message.entities:
                    entity_dict = {
                        'type': entity.type,
                        'offset': entity.offset,
                        'length': entity.length
                    }
                    if entity.url:
                        entity_dict['url'] = entity.url
                    if entity.user:
                        entity_dict['user'] = {
                            'id': entity.user.id,
                            'is_bot': entity.user.is_bot,
                            'first_name': entity.user.first_name
                        }
                    if entity.language:
                        entity_dict['language'] = entity.language
                    entities.append(entity_dict)
            
            state_data_dict['text'] = text
            state_data_dict['entities'] = entities if entities else None
            db.set_user_state(user_id, 'admin_broadcast_text_document', state_data_dict)
            
            await send_message(user_id,
                f"📝 <b>Текст сохранен:</b>\n\n{text}\n\n"
                "📄 <b>Теперь отправьте документ</b> (можно с подписью):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')
                ]]))
            return
        
        # ============================================
        # ОБРАБОТКА СОЗДАНИЯ ПРОМОКОДА
        # ============================================
        if state == 'admin_creating_promo_step1':
            # Шаг 1: Код промокода
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            code = text.strip().upper()
            if not code or len(code) < 3:
                await send_message(user_id, "❌ Код должен содержать минимум 3 символа")
                return
            
            # Проверяем уникальность
            existing = db.get_promocode(code)
            if existing:
                await send_message(user_id, "❌ Промокод с таким кодом уже существует")
                return
            
            # Сохраняем код и переходим к следующему шагу
            import json
            promo_data = {'code': code}
            db.set_user_state(user_id, 'admin_creating_promo_step2', promo_data)
            message = "🎁 <b>Создание промокода</b>\n\n"
            message += f"✅ <b>Код:</b> {code}\n\n"
            message += "📝 <b>Шаг 2/7:</b> Введите название промокода (например: Летняя скидка)"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_promo_step2':
            # Шаг 2: Название
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            name = text.strip()
            state_data_dict['name'] = name
            # Сохраняем данные и переходим к выбору типа через кнопки
            db.set_user_state(user_id, 'admin_creating_promo_step3', state_data_dict)
            message = "🎁 <b>Создание промокода</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {name}\n\n"
            message += "📝 <b>Шаг 3/7:</b> Выберите тип скидки:\n\n"
            keyboard = [
                [InlineKeyboardButton("📊 Процентная (%)", callback_data='admin_promo_type_percentage')],
                [InlineKeyboardButton("💰 Фиксированная (₽)", callback_data='admin_promo_type_fixed')],
                [InlineKeyboardButton("❌ Отменить", callback_data='admin_promocodes')]
            ]
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if state.startswith('admin_creating_promo_step3_'):
            # Шаг 3: Значение скидки (после выбора типа)
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                value = float(text)
                if value <= 0:
                    await send_message(user_id, "❌ Значение должно быть больше 0")
                    return
                
                promo_type = state.replace('admin_creating_promo_step3_', '')
                if promo_type == 'percentage' and value > 100:
                    await send_message(user_id, "❌ Процент не может быть больше 100")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['type'] = promo_type
                state_data_dict['value'] = value
                state_data_dict['ticket_types'] = state_data_dict.get('ticket_types') or []
                db.set_user_state(user_id, 'admin_creating_promo_categories', state_data_dict)
                # Показываем выбор категорий билетов (кнопками)
                categories = db.get_all_ticket_categories(active_only=True)
                message = "🎁 <b>Создание промокода</b>\n\n"
                message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"✅ <b>Тип:</b> {promo_type}\n"
                message += f"✅ <b>Значение:</b> {value}{'%' if promo_type == 'percentage' else '₽'}\n\n"
                message += "📝 <b>Шаг 4/7:</b> Выберите категории билетов, для которых действует промокод (нажимайте несколько раз для выбора нескольких). Затем нажмите <b>Готово</b>:"
                keyboard = []
                for cat in categories:
                    keyboard.append([InlineKeyboardButton(
                        f"🎫 {cat.get('name', cat['code'])} ({cat['code']})",
                        callback_data=f"admin_promo_cat_{cat['code']}"
                    )])
                keyboard.append([InlineKeyboardButton("✅ Все категории", callback_data='admin_promo_cat_all')])
                keyboard.append([InlineKeyboardButton("➡️ Готово", callback_data='admin_promo_cat_done')])
                keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data='admin_promocodes')])
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число")
            return
        
        if state == 'admin_creating_promo_step4':
            # Шаг 4: Максимальное количество использований
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                max_uses = int(text)
                if max_uses < 0:
                    await send_message(user_id, "❌ Количество не может быть отрицательным")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['max_uses'] = max_uses
                db.set_user_state(user_id, 'admin_creating_promo_step5', state_data_dict)
                message = "🎁 <b>Создание промокода</b>\n\n"
                message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"✅ <b>Тип:</b> {state_data_dict.get('type')}\n"
                message += f"✅ <b>Значение:</b> {state_data_dict.get('value')}{'%' if state_data_dict.get('type') == 'percentage' else '₽'}\n"
                message += f"✅ <b>Макс. использований:</b> {max_uses if max_uses > 0 else '∞'}\n\n"
                message += "📝 <b>Шаг 5/7:</b> Введите дату окончания действия (ДД.ММ.ГГГГ) или 'бессрочно':"
                await send_message(user_id, message, parse_mode='HTML')
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число")
            return
        
        if state == 'admin_creating_promo_step5':
            # Шаг 5: Дата окончания
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            from datetime import datetime
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            end_date = None
            if text.strip().lower() not in ['бессрочно', 'бессрочная', 'нет']:
                try:
                    # Парсим дату в формате ДД.ММ.ГГГГ
                    end_date = datetime.strptime(text.strip(), '%d.%m.%Y').date().strftime('%Y-%m-%d')
                except ValueError:
                    await send_message(user_id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 31.12.2024)")
                    return
            
            state_data_dict['end_date'] = end_date
            db.set_user_state(user_id, 'admin_creating_promo_step6', state_data_dict)
            message = "🎁 <b>Создание промокода</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
            message += f"✅ <b>Тип:</b> {state_data_dict.get('type')}\n"
            message += f"✅ <b>Значение:</b> {state_data_dict.get('value')}{'%' if state_data_dict.get('type') == 'percentage' else '₽'}\n"
            message += f"✅ <b>Макс. использований:</b> {state_data_dict.get('max_uses') if state_data_dict.get('max_uses') > 0 else '∞'}\n"
            message += f"✅ <b>Действует до:</b> {end_date if end_date else 'Бессрочно'}\n\n"
            message += "📝 <b>Шаг 6/7:</b> Введите примечания (необязательно, можно отправить 'нет'):"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_promo_step6':
            # Шаг 6: Примечания и создание промокода
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            notes = text.strip() if text.strip().lower() not in ['нет', 'н', ''] else None
            
            try:
                ticket_types = state_data_dict.get('ticket_types')
                if ticket_types is not None and not isinstance(ticket_types, list):
                    ticket_types = [ticket_types] if ticket_types else None
                # Создаем промокод
                db.create_promocode(
                    code=state_data_dict.get('code'),
                    name=state_data_dict.get('name'),
                    type=state_data_dict.get('type'),
                    value=float(state_data_dict.get('value')),
                    ticket_types=ticket_types if ticket_types else None,
                    start_date=None,
                    end_date=state_data_dict.get('end_date'),
                    max_uses=int(state_data_dict.get('max_uses', 0)),
                    min_amount=0.0,
                    notes=notes
                )
                
                cats_display = state_data_dict.get('ticket_types')
                if not cats_display:
                    cats_display = "все категории"
                elif isinstance(cats_display, list):
                    cats_display = ", ".join(cats_display)
                else:
                    cats_display = str(cats_display) if cats_display else "все категории"
                message = "✅ <b>Промокод успешно создан!</b>\n\n"
                message += f"🎁 <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"📝 <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"🎫 <b>Категории:</b> {cats_display}\n"
                message += f"💰 <b>Скидка:</b> {state_data_dict.get('value')}{'%' if state_data_dict.get('type') == 'percentage' else '₽'}\n"
                message += f"📊 <b>Использований:</b> {state_data_dict.get('max_uses') if state_data_dict.get('max_uses') > 0 else '∞'}\n"
                message += f"📅 <b>Действует до:</b> {state_data_dict.get('end_date') if state_data_dict.get('end_date') else 'Бессрочно'}\n"
                
                keyboard = [
                    [InlineKeyboardButton("◀️ Назад к промокодам", callback_data='admin_promocodes')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                db.clear_user_state(user_id)
            except Exception as e:
                logger.error(f"Error creating promocode: {e}", exc_info=True)
                await send_message(user_id, f"❌ Ошибка при создании промокода: {e}")
                db.clear_user_state(user_id)
            return
        
        # ============================================
        # ОБРАБОТКА СОЗДАНИЯ ПРОХОДКИ
        # ============================================
        if state.startswith('admin_creating_pass_step2_'):
            # Шаг 2: Количество проходок
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                quantity = int(text)
                if quantity <= 0:
                    await send_message(user_id, "❌ Количество должно быть больше 0")
                    return
                if quantity > 1000:
                    await send_message(user_id, "❌ Количество не может быть больше 1000")
                    return
                
                ticket_type = state.replace('admin_creating_pass_step2_', '')
                import json
                pass_data = {'ticket_type': ticket_type, 'quantity': quantity}
                db.set_user_state(user_id, 'admin_creating_pass_step3', pass_data)
                message = "🎫 <b>Создание проходки</b>\n\n"
                message += f"✅ <b>Категория:</b> {ticket_type.upper()}\n"
                message += f"✅ <b>Количество:</b> {quantity}\n\n"
                message += "📝 <b>Шаг 3/5:</b> Выберите срок действия:\n\n"
                keyboard = [
                    [InlineKeyboardButton("♾️ Бессрочная", callback_data='admin_pass_unlimited_yes')],
                    [InlineKeyboardButton("📅 С датой окончания", callback_data='admin_pass_unlimited_no')],
                    [InlineKeyboardButton("❌ Отменить", callback_data='admin_promocodes')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число")
            return
        
        if state == 'admin_creating_pass_step3_date':
            # Шаг 3: Дата окончания (если не бессрочная)
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            from datetime import datetime
            try:
                # Парсим дату в формате ДД.ММ.ГГГГ
                expires_at = datetime.strptime(text.strip(), '%d.%m.%Y').date().strftime('%Y-%m-%d')
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['expires_at'] = expires_at
                state_data_dict['is_unlimited'] = False
                db.set_user_state(user_id, 'admin_creating_pass_step4', state_data_dict)
                message = "🎫 <b>Создание проходки</b>\n\n"
                message += f"✅ <b>Категория:</b> {state_data_dict.get('ticket_type', '').upper()}\n"
                message += f"✅ <b>Количество:</b> {state_data_dict.get('quantity')}\n"
                message += f"✅ <b>Действует до:</b> {expires_at}\n\n"
                message += "📝 <b>Шаг 4/5:</b> Введите код проходки (например: GUEST2024):"
                await send_message(user_id, message, parse_mode='HTML')
            except ValueError:
                await send_message(user_id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 31.12.2024)")
            return
        
        if state == 'admin_creating_pass_step4':
            # Шаг 4: Код проходки
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            code = text.strip().upper()
            if not code or len(code) < 3:
                await send_message(user_id, "❌ Код должен содержать минимум 3 символа")
                return
            
            # Проверяем уникальность
            existing = db.get_guest_pass(code)
            if existing:
                await send_message(user_id, "❌ Проходка с таким кодом уже существует")
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            state_data_dict['code'] = code
            db.set_user_state(user_id, 'admin_creating_pass_step5', state_data_dict)
            message = "🎫 <b>Создание проходки</b>\n\n"
            message += f"✅ <b>Категория:</b> {state_data_dict.get('ticket_type', '').upper()}\n"
            message += f"✅ <b>Количество:</b> {state_data_dict.get('quantity')}\n"
            message += f"✅ <b>Действует до:</b> {state_data_dict.get('expires_at') if not state_data_dict.get('is_unlimited') else 'Бессрочно'}\n"
            message += f"✅ <b>Код:</b> {code}\n\n"
            message += "📝 <b>Шаг 5/5:</b> Введите примечания (необязательно, можно отправить 'нет'):"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_pass_step5':
            # Шаг 5: Примечания и создание проходки
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            notes = text.strip() if text.strip().lower() not in ['нет', 'н', ''] else None
            
            try:
                # Создаем проходку
                db.create_guest_pass(
                    code=state_data_dict.get('code'),
                    ticket_type=state_data_dict.get('ticket_type'),
                    quantity=int(state_data_dict.get('quantity')),
                    is_unlimited=state_data_dict.get('is_unlimited', False),
                    expires_at=state_data_dict.get('expires_at'),
                    created_by=user_id,
                    notes=notes
                )
                
                message = "✅ <b>Проходка успешно создана!</b>\n\n"
                message += f"🎫 <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"📝 <b>Категория:</b> {state_data_dict.get('ticket_type', '').upper()}\n"
                message += f"📊 <b>Количество:</b> {state_data_dict.get('quantity')}\n"
                message += f"📅 <b>Действует до:</b> {state_data_dict.get('expires_at') if not state_data_dict.get('is_unlimited') else 'Бессрочно'}\n"
                
                keyboard = [
                    [InlineKeyboardButton("◀️ Назад к промокодам", callback_data='admin_promocodes')]
                ]
                await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                db.clear_user_state(user_id)
            except Exception as e:
                logger.error(f"Error creating guest pass: {e}", exc_info=True)
                await send_message(user_id, f"❌ Ошибка при создании проходки: {e}")
                db.clear_user_state(user_id)
            return
        
        # ============================================
        # ОБРАБОТКА СОЗДАНИЯ И РЕДАКТИРОВАНИЯ КАТЕГОРИЙ БИЛЕТОВ
        # ============================================
        if state == 'admin_creating_category_step1':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            code = text.strip().lower().replace(' ', '_')
            if not code or len(code) < 2:
                await send_message(user_id, "❌ Код должен содержать минимум 2 символа")
                return
            
            # Проверяем уникальность
            existing = db.get_ticket_category(code)
            if existing:
                await send_message(user_id, "❌ Категория с таким кодом уже существует")
                return
            
            import json
            category_data = {'code': code}
            db.set_user_state(user_id, 'admin_creating_category_step2', category_data)
            message = "➕ <b>Создание категории</b>\n\n"
            message += f"✅ <b>Код:</b> {code}\n\n"
            message += "📝 <b>Шаг 2/7:</b> Введите название категории:\n\n"
            message += "💡 <b>Пример:</b> Обычный билет, VIP билет, Парный билет"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_category_step2':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            state_data_dict['name'] = text.strip()
            db.set_user_state(user_id, 'admin_creating_category_step3', state_data_dict)
            message = "➕ <b>Создание категории</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n\n"
            message += "💰 <b>Шаг 3/7:</b> Введите базовую цену:\n\n"
            message += "💡 <b>Пример:</b> 550"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_category_step3':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                base_price = float(text.strip())
                if base_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['base_price'] = base_price
                db.set_user_state(user_id, 'admin_creating_category_step4', state_data_dict)
                message = "➕ <b>Создание категории</b>\n\n"
                message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"✅ <b>Базовая цена:</b> {base_price:.0f}₽\n\n"
                message += "💰 <b>Шаг 4/7:</b> Введите цену со скидкой:\n\n"
                message += f"💡 <b>Обычно это та же цена или меньше (например: {base_price:.0f})</b>"
                await send_message(user_id, message, parse_mode='HTML')
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 550)")
            return
        
        if state == 'admin_creating_category_step4':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                discounted_price = float(text.strip())
                if discounted_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['discounted_price'] = discounted_price
                db.set_user_state(user_id, 'admin_creating_category_step5', state_data_dict)
                message = "➕ <b>Создание категории</b>\n\n"
                message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"✅ <b>Базовая цена:</b> {state_data_dict.get('base_price'):.0f}₽\n"
                message += f"✅ <b>Цена со скидкой:</b> {discounted_price:.0f}₽\n\n"
                message += "📦 <b>Шаг 5/7:</b> Введите лимит билетов:\n\n"
                message += "💡 <b>Введите число (0 = безлимит, например: 100)</b>"
                await send_message(user_id, message, parse_mode='HTML')
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 550)")
            return
        
        if state == 'admin_creating_category_step5':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            try:
                limit = int(text.strip())
                if limit < 0:
                    await send_message(user_id, "❌ Лимит не может быть отрицательным")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                state_data_dict['limit'] = limit
                db.set_user_state(user_id, 'admin_creating_category_step6', state_data_dict)
                message = "➕ <b>Создание категории</b>\n\n"
                message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
                message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
                message += f"✅ <b>Цена:</b> {state_data_dict.get('discounted_price'):.0f}₽\n"
                message += f"✅ <b>Лимит:</b> {limit if limit > 0 else 'Безлимит'}\n\n"
                message += "📄 <b>Шаг 6/7:</b> Введите описание (необязательно, можно отправить 'нет'):\n\n"
                message += "💡 <b>Пример:</b> Стандартный билет на мероприятие"
                await send_message(user_id, message, parse_mode='HTML')
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 100)")
            return
        
        if state == 'admin_creating_category_step6':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            description = text.strip() if text.strip().lower() not in ['нет', 'н', ''] else None
            state_data_dict['description'] = description
            db.set_user_state(user_id, 'admin_creating_category_step7', state_data_dict)
            message = "➕ <b>Создание категории</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
            message += f"✅ <b>Цена:</b> {state_data_dict.get('discounted_price'):.0f}₽\n"
            message += f"✅ <b>Лимит:</b> {state_data_dict.get('limit') if state_data_dict.get('limit') > 0 else 'Безлимит'}\n"
            if description:
                message += f"✅ <b>Описание:</b> {description[:50]}...\n"
            message += "\n🪑 <b>Шаг 7/7:</b> Разрешить выбор мест для этой категории?\n\n"
            message += "💡 <b>Отправьте:</b> да/yes - разрешить, нет/no - запретить"
            await send_message(user_id, message, parse_mode='HTML')
            return
        
        if state == 'admin_creating_category_step7':
            if not is_admin(user_id):
                await send_message(user_id, "❌ У вас нет доступа")
                db.clear_user_state(user_id)
                return
            
            import json
            state_data_dict = {}
            if state_data.get('data'):
                if isinstance(state_data.get('data'), str):
                    try:
                        state_data_dict = json.loads(state_data.get('data'))
                    except:
                        state_data_dict = {}
                else:
                    state_data_dict = state_data.get('data', {})
            
            allows_seats = text.strip().lower() in ['да', 'yes', 'д', 'y']
            
            # Создаем категорию
            try:
                # Получаем максимальный sort_order
                categories = db.get_all_ticket_categories()
                max_sort = max([c.get('sort_order', 0) for c in categories] + [0])
                
                if db.create_ticket_category(
                    code=state_data_dict.get('code'),
                    name=state_data_dict.get('name'),
                    base_price=state_data_dict.get('base_price'),
                    discounted_price=state_data_dict.get('discounted_price'),
                    limit=state_data_dict.get('limit', 0),
                    description=state_data_dict.get('description'),
                    allows_seat_selection=allows_seats,
                    sort_order=max_sort + 1
                ):
                    message = "✅ <b>Категория успешно создана!</b>\n\n"
                    message += f"📋 <b>Код:</b> {state_data_dict.get('code')}\n"
                    message += f"📝 <b>Название:</b> {state_data_dict.get('name')}\n"
                    message += f"💰 <b>Цена:</b> {state_data_dict.get('discounted_price'):.0f}₽\n"
                    message += f"📦 <b>Лимит:</b> {state_data_dict.get('limit') if state_data_dict.get('limit') > 0 else 'Безлимит'}\n"
                    message += f"🪑 <b>Выбор мест:</b> {'Разрешен' if allows_seats else 'Запрещен'}\n"
                    
                    keyboard = [
                        [InlineKeyboardButton("◀️ Назад к категориям", callback_data='admin_ticket_categories')]
                    ]
                    await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                    db.clear_user_state(user_id)
                else:
                    await send_message(user_id, "❌ Ошибка при создании категории")
            except Exception as e:
                logger.error(f"Error creating category: {e}", exc_info=True)
                await send_message(user_id, f"❌ Ошибка при создании категории: {str(e)}")
                db.clear_user_state(user_id)
            return
        
        # Редактирование категорий
        if state.startswith('admin_editing_category_name_'):
            category_code = state.replace('admin_editing_category_name_', '')
            if db.update_ticket_category(category_code, name=text.strip()):
                await send_message(user_id, f"✅ <b>Название обновлено!</b>",
                                 reply_markup=InlineKeyboardMarkup([[
                                     InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                                 ]]))
            else:
                await send_message(user_id, "❌ Ошибка при обновлении названия")
            db.clear_user_state(user_id)
            return
        
        if state.startswith('admin_editing_category_price_base_'):
            category_code = state.replace('admin_editing_category_price_base_', '')
            try:
                base_price = float(text.strip())
                if base_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                import json
                price_data = {'base': base_price, 'category_code': category_code}
                db.set_user_state(user_id, f'admin_editing_category_price_discounted_{category_code}', price_data)
                await send_message(user_id,
                    f"✅ <b>Базовая цена сохранена:</b> {base_price:.0f}₽\n\n"
                    f"💰 <b>Введите цену со скидкой:</b>\n"
                    f"💡 <i>Обычно это та же цена или меньше (например: {base_price:.0f})</i>",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')
                    ]]))
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 850)")
            return
        
        if state.startswith('admin_editing_category_price_discounted_'):
            category_code = state.replace('admin_editing_category_price_discounted_', '')
            try:
                discounted_price = float(text.strip())
                if discounted_price <= 0:
                    await send_message(user_id, "❌ Цена должна быть больше 0")
                    return
                
                import json
                state_data_dict = {}
                if state_data.get('data'):
                    if isinstance(state_data.get('data'), str):
                        try:
                            state_data_dict = json.loads(state_data.get('data'))
                        except:
                            state_data_dict = {}
                    else:
                        state_data_dict = state_data.get('data', {})
                
                base_price = state_data_dict.get('base', discounted_price)
                
                if db.update_ticket_category(category_code, base_price=base_price, discounted_price=discounted_price):
                    await send_message(user_id,
                        f"✅ <b>Цены успешно обновлены!</b>\n\n"
                        f"💰 Базовая цена: {base_price:.0f}₽\n"
                        f"💎 Цена со скидкой: {discounted_price:.0f}₽",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                        ]]))
                else:
                    await send_message(user_id, "❌ Ошибка при обновлении цен")
                db.clear_user_state(user_id)
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 850)")
            return
        
        if state.startswith('admin_editing_category_limit_'):
            category_code = state.replace('admin_editing_category_limit_', '')
            try:
                limit = int(text.strip())
                if limit < 0:
                    await send_message(user_id, "❌ Лимит не может быть отрицательным")
                    return
                
                if db.update_ticket_category(category_code, limit=limit):
                    limit_text = f"{limit}" if limit > 0 else "Безлимит"
                    await send_message(user_id, f"✅ <b>Лимит обновлен: {limit_text}</b>",
                                     reply_markup=InlineKeyboardMarkup([[
                                         InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                                     ]]))
                else:
                    await send_message(user_id, "❌ Ошибка при обновлении лимита")
                db.clear_user_state(user_id)
            except ValueError:
                await send_message(user_id, "❌ Введите корректное число (например: 100)")
            return
        
        if state.startswith('admin_editing_category_desc_'):
            category_code = state.replace('admin_editing_category_desc_', '')
            description = text.strip() if text.strip().lower() not in ['нет', 'н', ''] else None
            if db.update_ticket_category(category_code, description=description):
                await send_message(user_id, f"✅ <b>Описание {'обновлено' if description else 'удалено'}!</b>",
                                 reply_markup=InlineKeyboardMarkup([[
                                     InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                                 ]]))
            else:
                await send_message(user_id, "❌ Ошибка при обновлении описания")
            db.clear_user_state(user_id)
            return
    
    # Если нет состояния, показываем главное меню
    await handle_start(update, context)

async def handle_admin_callback(query, data, user_id):
    """Обработчик callback админ-панели"""
    if data == 'admin_tickets':
        tickets = db.get_all_tickets(limit=10)
        message = "🎫 <b>Последние билеты:</b>\n\n"
        for ticket in tickets[:5]:
            message += f"• {ticket['ticket_code']} - {ticket['ticket_type']} ({ticket['amount']}₽)\n"
        message += "\n📊 <b>Управление билетами</b>"
        keyboard = [
            [InlineKeyboardButton("📋 Все билеты", callback_data='admin_tickets_all')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_bonuses':
        bonuses = db.get_all_bonuses(limit=10)
        message = "💎 <b>Топ пользователей по бонусам:</b>\n\n"
        for bonus in bonuses[:5]:
            username = bonus.get('username', 'N/A')
            message += f"• @{username}: {bonus['bonus_balance']:.2f}₽\n"
        message += "\n⚙️ <b>Управление бонусами</b>"
        keyboard = [
            [InlineKeyboardButton("➕ Добавить бонусы", callback_data='admin_bonus_add')],
            [InlineKeyboardButton("➖ Списать бонусы", callback_data='admin_bonus_subtract')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_promocodes':
        promocodes = db.get_all_promocodes(active_only=True)
        message = "🎁 <b>Активные промокоды:</b>\n\n"
        for promo in promocodes[:5]:
            usage = f"{promo['used_count']}/{promo['max_uses']}" if promo['max_uses'] > 0 else f"{promo['used_count']}/∞"
            message += f"• {promo['code']} - {promo['name']} ({usage})\n"
        message += "\n⚙️ <b>Управление промокодами и проходками</b>"
        keyboard = [
            [InlineKeyboardButton("➕ Создать промокод", callback_data='admin_promo_create')],
            [InlineKeyboardButton("🎫 Создать проходку", callback_data='admin_pass_create')],
            [InlineKeyboardButton("📋 Все промокоды", callback_data='admin_promo_all')],
            [InlineKeyboardButton("📋 Все проходки", callback_data='admin_pass_all')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Обработчик создания промокода
    if data == 'admin_promo_create':
        db.set_user_state(user_id, 'admin_creating_promo_step1')
        message = "🎁 <b>Создание промокода</b>\n\n"
        message += "📝 <b>Шаг 1/7:</b> Введите код промокода (например: SUMMER2024)\n\n"
        message += "💡 Код должен быть уникальным и содержать только буквы и цифры"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    # Обработчик просмотра всех промокодов
    if data == 'admin_promo_all':
        promocodes = db.get_all_promocodes(active_only=False)
        message = "📋 <b>Все промокоды:</b>\n\n"
        if not promocodes:
            message += "Промокодов пока нет"
        else:
            for promo in promocodes[:20]:
                status = "✅" if promo['active'] else "❌"
                usage = f"{promo['used_count']}/{promo['max_uses']}" if promo['max_uses'] > 0 else f"{promo['used_count']}/∞"
                message += f"{status} <b>{promo['code']}</b> - {promo['name']} ({usage})\n"
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_promocodes')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Обработчик создания проходки
    if data == 'admin_pass_create':
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            return
        db.set_user_state(user_id, 'admin_creating_pass_step1')
        message = "🎫 <b>Создание проходки</b>\n\n"
        message += "📝 <b>Шаг 1/5:</b> Выберите категорию билетов для проходки:\n\n"
        keyboard = [
            [InlineKeyboardButton("🎫 Regular", callback_data='admin_pass_type_regular')],
            [InlineKeyboardButton("⭐ VIP", callback_data='admin_pass_type_vip')],
            [InlineKeyboardButton("💃 VIP Standing", callback_data='admin_pass_type_vip_standing')],
            [InlineKeyboardButton("💑 Couple", callback_data='admin_pass_type_couple')],
            [InlineKeyboardButton("❌ Отменить", callback_data='admin_promocodes')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Обработчик выбора бессрочности проходки
    if data == 'admin_pass_unlimited_yes':
        import json
        state_data = db.get_user_state(user_id)
        state_data_dict = {}
        if state_data and state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                except:
                    state_data_dict = {}
            else:
                state_data_dict = state_data.get('data', {})
        
        state_data_dict['is_unlimited'] = True
        state_data_dict['expires_at'] = None
        db.set_user_state(user_id, 'admin_creating_pass_step4', state_data_dict)
        message = "🎫 <b>Создание проходки</b>\n\n"
        message += f"✅ <b>Категория:</b> {state_data_dict.get('ticket_type', '').upper()}\n"
        message += f"✅ <b>Количество:</b> {state_data_dict.get('quantity')}\n"
        message += f"✅ <b>Действует:</b> Бессрочно\n\n"
        message += "📝 <b>Шаг 4/5:</b> Введите код проходки (например: GUEST2024):"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    if data == 'admin_pass_unlimited_no':
        import json
        state_data = db.get_user_state(user_id)
        state_data_dict = {}
        if state_data and state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                except:
                    state_data_dict = {}
            else:
                state_data_dict = state_data.get('data', {})
        
        db.set_user_state(user_id, 'admin_creating_pass_step3_date', state_data_dict)
        message = "🎫 <b>Создание проходки</b>\n\n"
        message += f"✅ <b>Категория:</b> {state_data_dict.get('ticket_type', '').upper()}\n"
        message += f"✅ <b>Количество:</b> {state_data_dict.get('quantity')}\n\n"
        message += "📝 <b>Шаг 3/5:</b> Введите дату окончания действия (ДД.ММ.ГГГГ, например: 31.12.2024):"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    # Обработчик выбора типа скидки для промокода
    if data.startswith('admin_promo_type_'):
        promo_type = data.replace('admin_promo_type_', '')
        import json
        state_data = db.get_user_state(user_id)
        state_data_dict = {}
        if state_data and state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                except:
                    state_data_dict = {}
            else:
                state_data_dict = state_data.get('data', {})
        
        # Сохраняем тип и переходим к вводу значения
        state_data_dict['type'] = promo_type
        db.set_user_state(user_id, f'admin_creating_promo_step3_{promo_type}', state_data_dict)
        message = "🎁 <b>Создание промокода</b>\n\n"
        message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
        message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
        message += f"✅ <b>Тип:</b> {promo_type}\n\n"
        message += f"📝 <b>Шаг 3/7:</b> Введите значение скидки ({'процент (0-100)' if promo_type == 'percentage' else 'сумма в рублях'}):"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    # Обработчик выбора категорий билетов для промокода
    if data.startswith('admin_promo_cat_'):
        state_data = db.get_user_state(user_id)
        if not state_data or state_data.get('state') != 'admin_creating_promo_categories':
            await edit_message_safe(query, "❌ Сессия создания промокода устарела. Начните заново из раздела промокодов.")
            return
        import json
        state_data_dict = {}
        if state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                except Exception:
                    state_data_dict = {}
            else:
                state_data_dict = state_data.get('data', {})
        suffix = data.replace('admin_promo_cat_', '')
        if suffix == 'all':
            state_data_dict['ticket_types'] = None
            db.set_user_state(user_id, 'admin_creating_promo_step4', state_data_dict)
            message = "🎁 <b>Создание промокода</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
            message += f"✅ <b>Категории:</b> Все категории\n\n"
            message += "📝 <b>Шаг 5/7:</b> Введите максимальное количество использований (0 = без ограничений):"
            await edit_message_safe(query, message, parse_mode='HTML')
            return
        if suffix == 'done':
            ticket_types = state_data_dict.get('ticket_types') or []
            state_data_dict['ticket_types'] = ticket_types if ticket_types else None
            db.set_user_state(user_id, 'admin_creating_promo_step4', state_data_dict)
            cats_text = ", ".join(ticket_types) if ticket_types else "не выбрано (будет все)"
            message = "🎁 <b>Создание промокода</b>\n\n"
            message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
            message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
            message += f"✅ <b>Категории:</b> {cats_text}\n\n"
            message += "📝 <b>Шаг 5/7:</b> Введите максимальное количество использований (0 = без ограничений):"
            await edit_message_safe(query, message, parse_mode='HTML')
            return
        # Добавляем категорию в список (или убираем при повторном нажатии)
        ticket_types = state_data_dict.get('ticket_types') or []
        if not isinstance(ticket_types, list):
            ticket_types = [ticket_types] if ticket_types else []
        if suffix in ticket_types:
            ticket_types = [c for c in ticket_types if c != suffix]
        else:
            ticket_types = list(ticket_types) + [suffix]
        state_data_dict['ticket_types'] = ticket_types
        db.set_user_state(user_id, 'admin_creating_promo_categories', state_data_dict)
        categories = db.get_all_ticket_categories(active_only=True)
        message = "🎁 <b>Создание промокода</b>\n\n"
        message += f"✅ <b>Код:</b> {state_data_dict.get('code')}\n"
        message += f"✅ <b>Название:</b> {state_data_dict.get('name')}\n"
        message += f"✅ <b>Выбрано категорий:</b> {', '.join(ticket_types) if ticket_types else 'пока нет'}\n\n"
        message += "📝 <b>Шаг 4/7:</b> Выберите категории билетов (повторное нажатие убирает категорию). Затем нажмите <b>Готово</b>:"
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(
                f"{'✅ ' if cat['code'] in ticket_types else '🎫 '}{cat.get('name', cat['code'])} ({cat['code']})",
                callback_data=f"admin_promo_cat_{cat['code']}"
            )])
        keyboard.append([InlineKeyboardButton("✅ Все категории", callback_data='admin_promo_cat_all')])
        keyboard.append([InlineKeyboardButton("➡️ Готово", callback_data='admin_promo_cat_done')])
        keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data='admin_promocodes')])
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Обработчик выбора типа билета для проходки
    if data.startswith('admin_pass_type_'):
        ticket_type = data.replace('admin_pass_type_', '')
        db.set_user_state(user_id, f'admin_creating_pass_step2_{ticket_type}')
        message = f"🎫 <b>Создание проходки</b>\n\n"
        message += f"✅ <b>Категория:</b> {ticket_type.upper()}\n\n"
        message += "📝 <b>Шаг 2/5:</b> Введите количество проходок (число):\n\n"
        message += "💡 Например: 10"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    # Обработчик просмотра всех проходок
    if data == 'admin_pass_all':
        passes = db.get_all_guest_passes()
        message = "📋 <b>Все проходки:</b>\n\n"
        if not passes:
            message += "Проходок пока нет"
        else:
            for p in passes[:20]:
                status = "✅" if p['active'] else "❌"
                expires = "Бессрочная" if p['is_unlimited'] else (p['expires_at'] or "Не указана")
                message += f"{status} <b>{p['code']}</b> - {p['ticket_type']} ({p['used_count']}/{p['quantity']}) до {expires}\n"
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_promocodes')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_referrals':
        message = "👥 <b>Реферальная программа</b>\n\n"
        message += "📊 Статистика по рефералам"
        keyboard = [
            [InlineKeyboardButton("📋 Топ рефереров", callback_data='admin_ref_top')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_roles':
        message = "👤 <b>Управление ролями пользователей</b>\n\n"
        message += "Назначьте роль пользователю по его ID.\n\n"
        message += "📝 <b>Доступные роли:</b>\n"
        message += "• <b>admin</b> — полный доступ к админ-панели\n"
        message += "• <b>moderator</b> — модератор (в разработке)\n"
        message += "• <b>promoter</b> — промоутер (доступ к панели промоутера)\n"
        message += "• <b>user</b> — обычный пользователь\n\n"
        message += "Введите ID пользователя для назначения роли:"
        
        db.set_user_state(user_id, 'admin_setting_role', {})
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_set_role_'):
        # Формат: admin_set_role_<user_id>_<role>
        parts = data.split('_')
        if len(parts) >= 5:
            target_user_id = int(parts[3])
            role = '_'.join(parts[4:])  # На случай, если роль состоит из нескольких частей
            
            logger.info(f"Setting role for user {target_user_id} to '{role}'")
            
            # Проверяем текущую роль перед обновлением
            user_before = db.get_user(target_user_id)
            old_role = user_before.get('role', 'user') if user_before else None
            logger.info(f"User {target_user_id} current role: {old_role}")
            
            # Обновляем роль
            try:
                db.update_user_role(target_user_id, role)
                logger.info(f"Role update called for user {target_user_id}")
                # При назначении промоутера присваиваем свой уникальный промокод (если был чужой — заменим)
                if role == 'promoter':
                    db.ensure_promoter_own_code(target_user_id)
            except Exception as e:
                logger.error(f"Error updating role: {e}", exc_info=True)
                await edit_message_safe(query, f"❌ <b>Ошибка при обновлении роли:</b>\n\n{str(e)}", 
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='admin_roles')
                                       ]]))
                return
            
            # Проверяем, что роль действительно обновилась
            user_after = db.get_user(target_user_id)
            new_role = user_after.get('role', 'user') if user_after else None
            logger.info(f"User {target_user_id} new role: {new_role}")
            
            if new_role != role:
                logger.error(f"Role mismatch! Expected '{role}', got '{new_role}'")
                await edit_message_safe(query, f"⚠️ <b>Предупреждение:</b> Роль может быть не обновлена.\n\nОжидалось: {role}\nПолучено: {new_role}\n\nПроверьте базу данных.", 
                                       reply_markup=InlineKeyboardMarkup([[
                                           InlineKeyboardButton("◀️ Назад", callback_data='admin_roles')
                                       ]]))
                return
            
            # Получаем информацию о пользователе
            try:
                target_user = await bot.get_chat(target_user_id)
                username = target_user.username or 'N/A'
                first_name = target_user.first_name or 'N/A'
            except Exception as e:
                logger.warning(f"Could not get user info: {e}")
                username = 'N/A'
                first_name = 'N/A'
            
            role_names = {
                'admin': 'Администратор',
                'moderator': 'Модератор',
                'promoter': 'Промоутер',
                'user': 'Пользователь'
            }
            
            message = f"✅ <b>Роль успешно назначена!</b>\n\n"
            message += f"👤 <b>Пользователь:</b> {first_name} (@{username})\n"
            message += f"🆔 <b>ID:</b> <code>{target_user_id}</code>\n"
            message += f"👤 <b>Роль:</b> {role_names.get(role, role)}\n\n"
            
            if role == 'promoter':
                message += "📌 <b>Что произошло:</b>\n"
                message += "• Пользователь получил доступ к панели промоутера\n"
                message += "• Ему будет показана кнопка 'Панель Промоутера' в главном меню\n"
                message += "• При первом входе в панель будет сгенерирован промо-код\n"
                message += "• Пользователь сможет видеть статистику по своим приглашениям\n"
            
            keyboard = [
                [InlineKeyboardButton("◀️ Назад", callback_data='admin_roles')]
            ]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
    
    if data == 'admin_stats':
        stats = db.get_bot_statistics()
        message = "📊 <b>Статистика бота</b>\n\n"
        message += f"👥 <b>Всего пользователей:</b> {stats['total_users']}\n"
        message += f"👥 <b>Активных (30 дней):</b> {stats['active_users_30d']}\n"
        message += f"🎫 <b>Всего билетов:</b> {stats['total_tickets']}\n"
        message += f"✅ <b>Активных билетов:</b> {stats.get('active_tickets', 0)}\n"
        message += f"🔴 <b>Использованных билетов:</b> {stats.get('used_tickets', 0)}\n"
        message += f"💰 <b>Общая выручка:</b> {stats['total_revenue']:.2f}₽\n"
        message += f"💎 <b>Всего бонусов:</b> {stats['total_bonuses']:.2f}₽\n"
        message += f"👥 <b>Рефереров:</b> {stats['total_referrers']}\n"
        message += f"🎁 <b>Активных промокодов:</b> {stats['active_promocodes']}\n\n"
        message += "<b>Билеты по типам (всего):</b>\n"
        for ttype, count in stats['tickets_by_type'].items():
            message += f"• {ttype}: {count}\n"
        keyboard = [
            [InlineKeyboardButton("📈 Расширенная статистика", callback_data='admin_stats_extended')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_stats_extended':
        try:
            stats = db.get_extended_statistics()
            message = "📈 <b>Расширенная статистика</b>\n\n"
            message += "<b>Продажи за последние 7 дней:</b>\n"
            if stats.get('sales_by_day'):
                for day in stats['sales_by_day'][:7]:
                    date = day.get('date', 'N/A')
                    count = day.get('count', 0)
                    revenue = day.get('revenue', 0) or 0  # Если None, используем 0
                    message += f"• {date}: {count} билетов ({float(revenue):.2f}₽)\n"
            else:
                message += "• Нет данных за последние 7 дней\n"
            
            message += "\n<b>Топ пользователей:</b>\n"
            if stats.get('top_users'):
                for user in stats['top_users'][:5]:
                    username = user.get('username', 'N/A')
                    tickets_count = user.get('tickets_count', 0) or 0
                    total_spent = user.get('total_spent', 0) or 0
                    message += f"• @{username}: {tickets_count} билетов ({float(total_spent):.2f}₽)\n"
            else:
                message += "• Нет данных\n"
            
            # Добавляем топ промоутеров
            message += "\n<b>Топ промоутеров:</b>\n"
            promoters = db.get_all_promoters()
            if promoters:
                # Сортируем по продажам (revenue)
                sorted_promoters = []
                for promoter in promoters:
                    promoter_stats = db.get_promoter_statistics(promoter['user_id'])
                    promoter['revenue'] = promoter_stats.get('revenue', 0.0)
                    promoter['purchases_count'] = promoter_stats.get('purchases_count', 0)
                    sorted_promoters.append(promoter)
                
                sorted_promoters.sort(key=lambda x: x['revenue'], reverse=True)
                
                for idx, promoter in enumerate(sorted_promoters[:5], 1):
                    username = promoter.get('username', 'N/A')
                    revenue = promoter.get('revenue', 0.0)
                    purchases = promoter.get('purchases_count', 0)
                    display = f"@{username}" if username != 'N/A' else f"ID:{promoter['user_id']}"
                    message += f"{idx}. {display}: {purchases} продаж ({revenue:.2f}₽)\n"
            else:
                message += "• Промоутеров пока нет\n"
            
            keyboard = [
                [InlineKeyboardButton("◀️ Назад", callback_data='admin_stats')]
            ]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error in admin_stats_extended: {e}")
            await edit_message_safe(query, 
                f"❌ <b>Ошибка при получении статистики</b>\n\n<code>{str(e)}</code>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data='admin_stats')
                ]]))
        return
    
    if data == 'admin_sales':
        sales_enabled = db.is_sales_enabled()
        message = "💰 <b>Управление продажами</b>\n\n"
        message += f"📊 <b>Статус продаж:</b> {'🟢 Открыты' if sales_enabled else '🔴 Закрыты'}\n\n"
        if not sales_enabled:
            message += "⚠️ <b>Продажи закрыты</b>\n"
            message += "Пользователи не смогут покупать билеты.\n"
            message += "Им будет показано сообщение о техническом обслуживании.\n\n"
        message += "Выберите действие:"
        keyboard = [
            [InlineKeyboardButton("🔴 Закрыть продажи" if sales_enabled else "🟢 Открыть продажи", 
                                callback_data='admin_toggle_sales')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_prices':
        # Получаем категории из БД
        categories = db.get_all_ticket_categories()
        prices = db.get_prices()
        
        message = "💰 <b>Управление ценами билетов</b>\n\n"
        message += "📊 <b>Текущие цены:</b>\n\n"
        
        keyboard = []
        
        if categories:
            # Используем категории из БД
            for cat in categories:
                status = "✅" if cat['is_active'] else "❌"
                base_price = cat['base_price']
                discounted_price = cat['discounted_price']
                sold_count = cat['sold_count']
                limit = cat['limit']
                available = limit - sold_count if limit > 0 else "∞"
                
                message += f"{status} <b>{cat['name']}</b> ({cat['code']})\n"
                message += f"   💰 Базовая цена: {base_price:.0f}₽\n"
                message += f"   💎 Со скидкой: {discounted_price:.0f}₽\n"
                if limit > 0:
                    message += f"   📦 Продано: {sold_count}/{limit} (осталось: {available})\n\n"
                else:
                    message += f"   📦 Продано: {sold_count} (безлимит)\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{status} {cat['name']}",
                    callback_data=f'admin_edit_price_{cat["code"]}'
                )])
        else:
            # Fallback на старые категории
            type_names = {
                'regular': 'Обычный билет',
                'vip': 'VIP билет',
                'vip_standing': 'VIP стоячий',
                'couple': 'Парный билет'
            }
            
            for ticket_type, price_data in prices.items():
                type_name = type_names.get(ticket_type, ticket_type)
                base_price = price_data['base']
                discounted_price = price_data['discounted']
                sold_count = db.count_tickets_by_type(ticket_type)
                limit = config.TICKET_LIMITS.get(ticket_type, 0)
                available = limit - sold_count
                
                message += f"🎫 <b>{type_name}</b>\n"
                message += f"   💰 Базовая цена: {base_price:.0f}₽\n"
                message += f"   💎 Со скидкой: {discounted_price:.0f}₽\n"
                message += f"   📦 Продано: {sold_count}/{limit} (осталось: {available})\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🎫 Обычный билет", callback_data='admin_edit_price_regular')],
                [InlineKeyboardButton("💎 VIP билет", callback_data='admin_edit_price_vip')],
                [InlineKeyboardButton("💎 VIP стоячий", callback_data='admin_edit_price_vip_standing')],
                [InlineKeyboardButton("💑 Парный билет", callback_data='admin_edit_price_couple')],
            ]
        
        message += "💡 <b>Выберите категорию для редактирования:</b>"
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')])
        
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_edit_price_'):
        ticket_type = data.replace('admin_edit_price_', '')
        
        # Пытаемся получить категорию из БД
        category = db.get_ticket_category(ticket_type)
        if category:
            # Используем категорию из БД
            current_base = category['base_price']
            current_discounted = category['discounted_price']
            category_name = category['name']
        else:
            # Fallback на старую систему
            prices = db.get_prices()
            price_data = prices.get(ticket_type, {})
            current_base = price_data.get('base', 0)
            current_discounted = price_data.get('discounted', 0)
            type_names = {
                'regular': 'Обычный билет',
                'vip': 'VIP билет',
                'vip_standing': 'VIP стоячий',
                'couple': 'Парный билет'
            }
            category_name = type_names.get(ticket_type, ticket_type)
        
        message = f"✏️ <b>Редактирование цены: {category_name}</b>\n\n"
        message += f"💰 <b>Текущая базовая цена:</b> {current_base:.0f}₽\n"
        message += f"💎 <b>Текущая цена со скидкой:</b> {current_discounted:.0f}₽\n\n"
        message += "📝 <b>Введите новую базовую цену:</b>\n"
        message += "💡 <i>Введите число (например: 850)</i>"
        
        db.set_user_state(user_id, f'admin_editing_price_base_{ticket_type}')
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data='admin_prices')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_toggle_sales':
        current_status = db.is_sales_enabled()
        db.set_bot_setting('sales_enabled', '0' if current_status else '1')
        new_status = db.is_sales_enabled()
        message = f"✅ <b>Продажи {'открыты' if new_status else 'закрыты'}</b>\n\n"
        if not new_status:
            message += "⚠️ Пользователи не смогут покупать билеты до открытия продаж."
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_sales')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ==================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ БИЛЕТОВ ====================
    if data == 'admin_ticket_categories':
        db.ensure_standard_ticket_categories()
        categories = db.get_all_ticket_categories()
        message = "📋 <b>Категории билетов</b>\n\n"
        
        if not categories:
            message += "📭 Категорий пока нет\n\n"
        else:
            for cat in categories:
                status = "✅" if cat['is_active'] else "❌"
                available = cat['limit'] - cat['sold_count'] if cat['limit'] > 0 else "∞"
                limit_text = f"{cat['sold_count']}/{cat['limit']}" if cat['limit'] > 0 else f"{cat['sold_count']}/∞"
                message += f"{status} <b>{cat['name']}</b> ({cat['code']})\n"
                message += f"   💰 Цена: {cat['discounted_price']:.0f}₽\n"
                message += f"   📦 Продано: {limit_text} (осталось: {available})\n"
                if cat.get('description'):
                    desc = cat['description'][:50] + "..." if len(cat.get('description', '')) > 50 else cat.get('description', '')
                    message += f"   📝 {desc}\n"
                message += "\n"
        
        keyboard = []
        if categories:
            # Добавляем кнопки для редактирования каждой категории
            for cat in categories[:10]:  # Максимум 10 категорий в меню
                keyboard.append([InlineKeyboardButton(
                    f"{'✅' if cat['is_active'] else '❌'} {cat['name']}",
                    callback_data=f'admin_edit_category_{cat["code"]}'
                )])
        
        keyboard.append([InlineKeyboardButton("➕ Создать категорию", callback_data='admin_create_category')])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')])
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_create_category':
        db.set_user_state(user_id, 'admin_creating_category_step1')
        message = "➕ <b>Создание новой категории билетов</b>\n\n"
        message += "📝 <b>Шаг 1/7:</b> Введите код категории (латинскими буквами, без пробелов):\n\n"
        message += "💡 <b>Примеры:</b> regular, vip, premium, student\n"
        message += "⚠️ <b>Код должен быть уникальным!</b>"
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data='admin_ticket_categories')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_edit_category_'):
        category_code = data.replace('admin_edit_category_', '')
        db.ensure_standard_ticket_categories()
        category = db.get_ticket_category(category_code)
        if not category:
            await edit_message_safe(query, "❌ Категория не найдена")
            return
        
        message = f"✏️ <b>Редактирование категории: {category['name']}</b>\n\n"
        message += f"📋 <b>Код:</b> {category['code']}\n"
        message += f"📝 <b>Название:</b> {category['name']}\n"
        message += f"💰 <b>Цена:</b> {category['discounted_price']:.0f}₽\n"
        message += f"📦 <b>Лимит:</b> {category['limit'] if category['limit'] > 0 else 'Безлимит'}\n"
        message += f"📊 <b>Продано:</b> {category['sold_count']}\n"
        message += f"✅ <b>Статус:</b> {'Активна' if category['is_active'] else 'Неактивна'}\n\n"
        message += "💡 <b>Выберите, что хотите изменить:</b>"
        
        keyboard = [
            [InlineKeyboardButton("📝 Название", callback_data=f'admin_edit_category_name_{category_code}')],
            [InlineKeyboardButton("💰 Цена", callback_data=f'admin_edit_category_price_{category_code}')],
            [InlineKeyboardButton("📦 Лимит", callback_data=f'admin_edit_category_limit_{category_code}')],
            [InlineKeyboardButton("📄 Описание", callback_data=f'admin_edit_category_desc_{category_code}')],
            [InlineKeyboardButton("🪑 Выбор мест", callback_data=f'admin_toggle_category_seats_{category_code}')],
            [InlineKeyboardButton("✅/❌ Активировать/Деактивировать", callback_data=f'admin_toggle_category_active_{category_code}')],
            [InlineKeyboardButton("🗑️ Удалить категорию", callback_data=f'admin_delete_category_{category_code}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_ticket_categories')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_delete_category_'):
        category_code = data.replace('admin_delete_category_', '')
        category = db.get_ticket_category(category_code)
        if not category:
            await edit_message_safe(query, "❌ Категория не найдена")
            return
        
        sold_count = db.count_tickets_by_type(category_code)
        if sold_count > 0:
            message = f"⚠️ <b>Невозможно удалить категорию!</b>\n\n"
            message += f"📊 Уже продано билетов: {sold_count}\n\n"
            message += "💡 Можно только деактивировать категорию."
            keyboard = [
                [InlineKeyboardButton("❌ Деактивировать", callback_data=f'admin_toggle_category_active_{category_code}')],
                [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')]
            ]
        else:
            message = f"🗑️ <b>Удаление категории: {category['name']}</b>\n\n"
            message += "⚠️ <b>Это действие необратимо!</b>\n\n"
            message += "Вы уверены, что хотите удалить эту категорию?"
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить", callback_data=f'admin_confirm_delete_category_{category_code}')],
                [InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')]
            ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_confirm_delete_category_'):
        category_code = data.replace('admin_confirm_delete_category_', '')
        if db.delete_ticket_category(category_code):
            await edit_message_safe(query, f"✅ <b>Категория успешно удалена!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад к категориям", callback_data='admin_ticket_categories')
                                   ]]))
        else:
            await edit_message_safe(query, "❌ Ошибка при удалении категории",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_ticket_categories')
                                   ]]))
        return
    
    if data.startswith('admin_toggle_category_active_'):
        category_code = data.replace('admin_toggle_category_active_', '')
        category = db.get_ticket_category(category_code)
        if category:
            new_status = not category['is_active']
            db.update_ticket_category(category_code, is_active=new_status)
            status_text = "активирована" if new_status else "деактивирована"
            await edit_message_safe(query, f"✅ <b>Категория {status_text}!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                                   ]]))
        return
    
    if data.startswith('admin_toggle_category_seats_'):
        category_code = data.replace('admin_toggle_category_seats_', '')
        category = db.get_ticket_category(category_code)
        if category:
            new_status = not category.get('allows_seat_selection', False)
            db.update_ticket_category(category_code, allows_seat_selection=new_status)
            status_text = "разрешен" if new_status else "запрещен"
            await edit_message_safe(query, f"✅ <b>Выбор мест {status_text}!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_category_{category_code}')
                                   ]]))
        return
    
    if data.startswith('admin_edit_category_name_'):
        category_code = data.replace('admin_edit_category_name_', '')
        db.set_user_state(user_id, f'admin_editing_category_name_{category_code}')
        message = f"✏️ <b>Редактирование названия категории</b>\n\n"
        message += "📝 <b>Введите новое название:</b>"
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_edit_category_price_'):
        category_code = data.replace('admin_edit_category_price_', '')
        db.set_user_state(user_id, f'admin_editing_category_price_base_{category_code}')
        message = f"✏️ <b>Редактирование цены категории</b>\n\n"
        message += "💰 <b>Введите новую базовую цену:</b>\n"
        message += "💡 <i>Введите число (например: 850)</i>"
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_edit_category_limit_'):
        category_code = data.replace('admin_edit_category_limit_', '')
        db.set_user_state(user_id, f'admin_editing_category_limit_{category_code}')
        message = f"✏️ <b>Редактирование лимита категории</b>\n\n"
        message += "📦 <b>Введите новый лимит билетов:</b>\n"
        message += "💡 <i>Введите число (0 = безлимит, например: 100)</i>"
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_edit_category_desc_'):
        category_code = data.replace('admin_edit_category_desc_', '')
        db.set_user_state(user_id, f'admin_editing_category_desc_{category_code}')
        message = f"✏️ <b>Редактирование описания категории</b>\n\n"
        message += "📄 <b>Введите новое описание:</b>\n"
        message += "💡 <i>Можно отправить 'нет' для удаления описания</i>"
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data=f'admin_edit_category_{category_code}')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_broadcast':
        message = "📢 <b>Публикация постов</b>\n\n"
        message += "Выберите тип поста для публикации:\n\n"
        message += "💡 <b>Пост будет отправлен всем пользователям бота</b>"
        keyboard = [
            [InlineKeyboardButton("📝 Текстовый пост", callback_data='admin_broadcast_text')],
            [InlineKeyboardButton("🖼️ Текст + Фото", callback_data='admin_broadcast_photo')],
            [InlineKeyboardButton("🎥 Текст + Видео", callback_data='admin_broadcast_video')],
            [InlineKeyboardButton("🎤 Голосовое сообщение", callback_data='admin_broadcast_voice')],
            [InlineKeyboardButton("📄 Документ", callback_data='admin_broadcast_document')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_broadcast_'):
        broadcast_type = data.replace('admin_broadcast_', '')
        db.set_user_state(user_id, f'admin_broadcasting_{broadcast_type}')
        type_names = {
            'text': 'текстовый',
            'photo': 'текст + фото',
            'video': 'текст + видео',
            'voice': 'голосовое',
            'document': 'документ'
        }
        message = f"📢 <b>Создание {type_names.get(broadcast_type, 'поста')}</b>\n\n"
        if broadcast_type == 'text':
            message += "📝 <b>Отправьте текст поста:</b>"
        elif broadcast_type in ['photo', 'video']:
            message += f"📝 <b>Отправьте текст поста</b> (можно отправить сразу с {type_names[broadcast_type].split(' + ')[1]}):"
        elif broadcast_type == 'voice':
            message += "🎤 <b>Отправьте голосовое сообщение:</b>"
        elif broadcast_type == 'document':
            message += "📄 <b>Отправьте документ:</b>"
        await edit_message_safe(query, message, parse_mode='HTML')
        return
    
    if data == 'admin_promoters':
        # Список всех промоутеров
        promoters = db.get_all_promoters()
        
        if not promoters:
            message = "👥 <b>Управление промоутерами</b>\n\n"
            message += "❌ Промоутеры не найдены."
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]]
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        message = "👥 <b>Управление промоутерами</b>\n\n"
        message += f"📊 <b>Всего промоутеров:</b> {len(promoters)}\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Подготавливаем список промоутеров со статистикой для сортировки
        promoters_with_stats = []
        for promoter in promoters:
            user_id = promoter['user_id']
            username = promoter.get('username', 'Нет username')
            first_name = promoter.get('first_name', 'Без имени')
            promo_code = promoter.get('promo_code', 'Нет кода')
            is_active = bool(promoter.get('promoter_active', 0))
            
            # Получаем краткую статистику
            stats = db.get_promoter_statistics(user_id)
            invited = stats.get('invited_users', 0)
            purchases = stats.get('purchases_count', 0)
            revenue = stats.get('revenue', 0.0)
            
            promoters_with_stats.append({
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'promo_code': promo_code,
                'is_active': is_active,
                'revenue': revenue,
                'purchases': purchases
            })
        
        # Сортируем: сначала по активности, затем по количеству продаж
        promoters_with_stats.sort(key=lambda x: (not x['is_active'], -x['revenue']))
        
        keyboard = []
        for promoter in promoters_with_stats:
            user_id = promoter['user_id']
            username = promoter['username']
            revenue = promoter['revenue']
            is_active = promoter['is_active']
            
            # Формируем текст кнопки с звездой для активных
            display_name = f"@{username}" if username != 'Нет username' else f"ID: {user_id}"
            star = "⭐ " if is_active else ""
            button_text = f"{star}👤 {display_name} | 💰 {revenue:.0f}₽"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f'admin_promoter_{user_id}'
            )])
        
        keyboard.append([InlineKeyboardButton("🔍 Поиск по ID", callback_data='admin_search_promoter')])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')])
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_search_promoter':
        # Запрос ID для поиска
        db.set_user_state(user_id, 'admin_searching_promoter_id')
        message = "🔍 <b>Поиск промоутера по ID</b>\n\n"
        message += "📝 <b>Введите ID пользователя:</b>\n\n"
        message += "💡 <i>ID должен быть числом (например: 123456789)</i>"
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data='admin_promoters')]]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_promoter_'):
        # Детальная информация о промоутере
        try:
            promoter_id = int(data.replace('admin_promoter_', ''))
        except ValueError:
            await edit_message_safe(query, "❌ Ошибка: неверный ID промоутера",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                                   ]]))
            return
        
        stats = db.get_promoter_detailed_stats(promoter_id)
        if not stats:
            await edit_message_safe(query, "❌ Промоутер не найден",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                                   ]]))
            return
        
        message = "👤 <b>Детальная информация о промоутере</b>\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Проверяем статус активности
        is_active = db.is_promoter_active(promoter_id)
        
        # Основная информация
        message += "📋 <b>Основная информация:</b>\n"
        message += f"🆔 <b>ID:</b> <code>{stats['user_id']}</code>\n"
        if stats.get('username'):
            message += f"👤 <b>Username:</b> @{stats['username']}\n"
        if stats.get('first_name'):
            message += f"👤 <b>Имя:</b> {stats['first_name']}"
            if stats.get('last_name'):
                message += f" {stats['last_name']}"
            message += "\n"
        message += f"🎫 <b>Промокод:</b> <code>{stats.get('promo_code', 'Нет кода')}</code>\n"
        message += f"⭐ <b>Статус:</b> {'✅ Активный' if is_active else '❌ Неактивный'}\n"
        if stats.get('created_at'):
            created = stats['created_at']
            if isinstance(created, str):
                try:
                    # Пробуем разные форматы дат
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                except:
                    try:
                        # Формат MySQL: YYYY-MM-DD HH:MM:SS
                        created = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                    except:
                        created = None
            if created and hasattr(created, 'strftime'):
                message += f"📅 <b>Дата регистрации:</b> {created.strftime('%d.%m.%Y %H:%M')}\n"
        message += "\n"
        
        # Статистика
        message += "📊 <b>Статистика:</b>\n"
        message += f"👥 <b>Приглашено пользователей:</b> {stats.get('invited_users', 0)}\n"
        message += f"🛒 <b>Количество покупок:</b> {stats.get('purchases_count', 0)}\n"
        message += f"💰 <b>Выручка:</b> {stats.get('revenue', 0.0):.2f}₽\n"
        message += f"🎟️ <b>Использовано билетов:</b> {stats.get('used_tickets', 0)}\n"
        
        # Статистика по типам билетов
        tickets_by_type = stats.get('tickets_by_type', {})
        if tickets_by_type:
            message += "\n📦 <b>По типам билетов:</b>\n"
            type_names = {
                'regular': 'Обычный',
                'vip': 'VIP',
                'vip_standing': 'VIP стоячий',
                'couple': 'Парный'
            }
            for ticket_type, data in tickets_by_type.items():
                type_name = type_names.get(ticket_type, ticket_type)
                message += f"  • {type_name}: {data['count']} шт. ({data['revenue']:.2f}₽)\n"
        
        # Даты покупок
        if stats.get('first_purchase'):
            first = stats['first_purchase']
            if isinstance(first, str):
                try:
                    first = datetime.fromisoformat(first.replace('Z', '+00:00'))
                except:
                    try:
                        first = datetime.strptime(first, '%Y-%m-%d %H:%M:%S')
                    except:
                        first = None
            if first and hasattr(first, 'strftime'):
                message += f"\n📅 <b>Первая покупка:</b> {first.strftime('%d.%m.%Y %H:%M')}\n"
        if stats.get('last_purchase'):
            last = stats['last_purchase']
            if isinstance(last, str):
                try:
                    last = datetime.fromisoformat(last.replace('Z', '+00:00'))
                except:
                    try:
                        last = datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
                    except:
                        last = None
            if last and hasattr(last, 'strftime'):
                message += f"📅 <b>Последняя покупка:</b> {last.strftime('%d.%m.%Y %H:%M')}\n"
        
        # Последние покупки
        recent_purchases = stats.get('recent_purchases', [])
        if recent_purchases:
            message += "\n🛒 <b>Последние покупки:</b>\n"
            for purchase in recent_purchases[:5]:
                username = purchase.get('username', 'Нет username')
                amount = purchase.get('amount', 0)
                created = purchase.get('created_at')
                if isinstance(created, str):
                    try:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        created_str = created_dt.strftime('%d.%m %H:%M')
                    except:
                        try:
                            created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                            created_str = created_dt.strftime('%d.%m %H:%M')
                        except:
                            created_str = str(created)
                elif created and hasattr(created, 'strftime'):
                    created_str = created.strftime('%d.%m %H:%M')
                else:
                    created_str = str(created)
                message += f"  • @{username}: {amount:.2f}₽ ({created_str})\n"
        
        keyboard = [
            [InlineKeyboardButton(
                "⭐ Отметить активным" if not is_active else "❌ Отметить неактивным",
                callback_data=f'admin_toggle_promoter_active_{promoter_id}'
            )],
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'admin_promoter_{promoter_id}')],
            [InlineKeyboardButton("❌ Удалить промоутера", callback_data=f'admin_remove_promoter_{promoter_id}')],
            [InlineKeyboardButton("◀️ Назад к списку", callback_data='admin_promoters')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_toggle_promoter_active_'):
        # Переключение статуса активности промоутера
        try:
            promoter_id = int(data.replace('admin_toggle_promoter_active_', ''))
        except ValueError:
            await edit_message_safe(query, "❌ Ошибка: неверный ID промоутера",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                                   ]]))
            return
        
        # Получаем текущий статус
        current_status = db.is_promoter_active(promoter_id)
        new_status = not current_status
        
        # Обновляем статус
        if db.set_promoter_active(promoter_id, new_status):
            status_text = "активным" if new_status else "неактивным"
            await edit_message_safe(query, f"✅ <b>Промоутер отмечен как {status_text}!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад к промоутеру", callback_data=f'admin_promoter_{promoter_id}')
                                   ]]))
        else:
            await edit_message_safe(query, "❌ Ошибка при обновлении статуса",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                                   ]]))
        return
    
    if data.startswith('admin_remove_promoter_'):
        # Удаление промоутера (смена роли на 'user')
        try:
            promoter_id = int(data.replace('admin_remove_promoter_', ''))
        except ValueError:
            await edit_message_safe(query, "❌ Ошибка: неверный ID промоутера",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_promoters')
                                   ]]))
            return
        
        # Меняем роль на 'user', но сохраняем промокод для истории
        db.update_user_role(promoter_id, 'user')
        logger.info(f"Admin {user_id} removed promoter role from user {promoter_id}")
        
        await edit_message_safe(query, "✅ <b>Промоутер удален</b>\n\nРоль изменена на обычного пользователя.",
                               reply_markup=InlineKeyboardMarkup([[
                                   InlineKeyboardButton("◀️ Назад к списку", callback_data='admin_promoters')
                               ]]))
        return
    
    if data == 'admin_support_tickets':
        try:
            # Список тикетов поддержки для админов
            stats = db.get_ticket_stats() or {}
            tickets = db.get_all_support_tickets(limit=20) or []
            
            message = "💬 <b>Обращения в поддержку</b>\n\n"
            message += "📊 <b>Статистика:</b>\n"
            message += f"🆕 Новых: {stats.get('open', 0)}\n"
            message += f"🟡 В обработке: {stats.get('in_progress', 0)}\n"
            message += f"⏳ Ожидают ответа: {stats.get('waiting', 0)}\n"
            message += f"🔴 Закрытых: {stats.get('closed', 0)}\n"
            message += f"📋 Всего: {stats.get('total', 0)}\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            keyboard = []
            
            if not tickets or len(tickets) == 0:
                message += "📭 Нет обращений"
            else:
                status_emoji = {
                    'open': '🆕',
                    'in_progress': '🟡',
                    'waiting': '⏳',
                    'closed': '🔴'
                }
                
                for ticket in tickets[:15]:  # Показываем до 15 тикетов
                    if not ticket:
                        continue
                        
                    ticket_id = ticket.get('ticket_id', '')
                    if not ticket_id:
                        continue
                    
                    status = ticket.get('status', 'open')
                    emoji = status_emoji.get(status, '🆕')
                    subject = ticket.get('subject') or 'Без темы'
                    
                    # Обрезаем длинную тему (защита от None)
                    if subject and len(subject) > 35:
                        subject = subject[:35] + '...'
                    
                    # Получаем информацию о пользователе
                    user_id = ticket.get('user_id')
                    if user_id:
                        user = db.get_user(user_id)
                        username = user.get('username', 'нет username') if user else 'нет username'
                    else:
                        username = 'нет username'
                    
                    button_text = f"{emoji} {subject} (@{username})"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=f'admin_view_ticket_{ticket_id}')])
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')])
            
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error in admin_support_tickets: {e}")
            await edit_message_safe(query, 
                f"❌ <b>Ошибка при получении тикетов</b>\n\n"
                f"<code>{str(e)}</code>\n\n"
                f"💡 Убедитесь, что таблицы support_tickets и support_messages созданы в базе данных.\n"
                f"Запустите SQL скрипт support_tickets_schema.sql",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')
                ]]))
        return
    
    if data.startswith('admin_view_ticket_'):
        # Просмотр тикета админом
        ticket_id = data.replace('admin_view_ticket_', '')
        ticket = db.get_support_ticket(ticket_id)
        
        if not ticket:
            await edit_message_safe(query, "❌ Тикет не найден",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_support_tickets')
                                   ]]))
            return
        
        # Получаем сообщения
        messages = db.get_ticket_messages(ticket_id)
        
        # Получаем информацию о пользователе
        user = db.get_user(ticket['user_id'])
        username = user.get('username', 'не указан') if user else 'не указан'
        first_name = user.get('first_name', '') if user else ''
        
        status_names = {
            'open': '🆕 Открыт',
            'in_progress': '🟡 В обработке',
            'waiting': '⏳ Ожидает ответа',
            'closed': '🔴 Закрыт'
        }
        
        message = f"💬 <b>Обращение #{ticket_id}</b>\n\n"
        message += f"👤 <b>Пользователь:</b> {first_name} (@{username})\n"
        message += f"🆔 <b>ID:</b> {ticket['user_id']}\n"
        message += f"📋 <b>Статус:</b> {status_names.get(ticket.get('status', 'open'), 'Открыт')}\n"
        if ticket.get('subject'):
            message += f"📝 <b>Тема:</b> {ticket['subject']}\n"
        if ticket.get('admin_id'):
            admin_user = db.get_user(ticket['admin_id'])
            admin_name = admin_user.get('first_name', 'Админ') if admin_user else 'Админ'
            message += f"👨‍💼 <b>Обрабатывает:</b> {admin_name}\n"
        message += f"\n📨 <b>Сообщения:</b> ({len(messages)})\n\n"
        
        if messages:
            for msg in messages[-10:]:  # Показываем последние 10 сообщений
                sender = "👨‍💼 Поддержка" if msg.get('is_admin') else f"👤 {first_name}"
                msg_text = msg.get('message_text', '')
                if len(msg_text) > 150:
                    msg_text = msg_text[:150] + '...'
                message += f"{sender}: {msg_text}\n"
        else:
            message += "Пока нет сообщений.\n"
        
        keyboard = []
        if ticket.get('status') != 'closed':
            keyboard.append([InlineKeyboardButton("💬 Ответить", callback_data=f'admin_reply_ticket_{ticket_id}')])
            if ticket.get('status') == 'open':
                keyboard.append([InlineKeyboardButton("🟡 Взять в обработку", callback_data=f'admin_take_ticket_{ticket_id}')])
            keyboard.append([InlineKeyboardButton("🔴 Закрыть тикет", callback_data=f'admin_close_ticket_{ticket_id}')])
        else:
            keyboard.append([InlineKeyboardButton("🟢 Открыть тикет", callback_data=f'admin_reopen_ticket_{ticket_id}')])
        keyboard.append([InlineKeyboardButton("◀️ Назад к списку", callback_data='admin_support_tickets')])
        
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_reply_ticket_'):
        # Ответ админа в тикет
        ticket_id = data.replace('admin_reply_ticket_', '')
        ticket = db.get_support_ticket(ticket_id)
        
        if not ticket:
            await edit_message_safe(query, "❌ Тикет не найден",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_support_tickets')
                                   ]]))
            return
        
        if ticket.get('status') == 'closed':
            await edit_message_safe(query, "❌ Этот тикет закрыт",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data=f'admin_view_ticket_{ticket_id}')
                                   ]]))
            return
        
        db.set_user_state(user_id, f'admin_support_reply_{ticket_id}')
        
        message = "💬 <b>Ответить в тикет</b>\n\n"
        message += "📝 <b>Введите ваш ответ:</b>\n\n"
        message += "💡 Сообщение будет отправлено пользователю."
        
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data=f'admin_view_ticket_{ticket_id}')]]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data.startswith('admin_take_ticket_'):
        # Взять тикет в обработку
        ticket_id = data.replace('admin_take_ticket_', '')
        if db.update_ticket_status(ticket_id, 'in_progress', user_id):
            await edit_message_safe(query, "✅ <b>Тикет взят в обработку!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ К тикету", callback_data=f'admin_view_ticket_{ticket_id}')
                                   ]]))
        else:
            await edit_message_safe(query, "❌ Ошибка при обновлении статуса",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_support_tickets')
                                   ]]))
        return
    
    if data.startswith('admin_close_ticket_'):
        # Закрыть тикет
        ticket_id = data.replace('admin_close_ticket_', '')
        if db.update_ticket_status(ticket_id, 'closed', user_id):
            # Уведомляем пользователя
            ticket = db.get_support_ticket(ticket_id)
            if ticket:
                try:
                    await bot.send_message(
                        chat_id=ticket['user_id'],
                        text="🔴 <b>Ваше обращение закрыто</b>\n\nЕсли у вас возникнут новые вопросы, создайте новое обращение.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("💬 Чат с поддержкой", callback_data='support_chat')
                        ]])
                    )
                except Exception as e:
                    logger.error(f"Error notifying user about closed ticket: {e}")
            
            await edit_message_safe(query, "✅ <b>Тикет закрыт!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ К тикету", callback_data=f'admin_view_ticket_{ticket_id}')
                                   ]]))
        else:
            await edit_message_safe(query, "❌ Ошибка при закрытии тикета",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_support_tickets')
                                   ]]))
        return
    
    if data.startswith('admin_reopen_ticket_'):
        # Открыть закрытый тикет
        ticket_id = data.replace('admin_reopen_ticket_', '')
        if db.update_ticket_status(ticket_id, 'open', user_id):
            await edit_message_safe(query, "✅ <b>Тикет открыт!</b>",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ К тикету", callback_data=f'admin_view_ticket_{ticket_id}')
                                   ]]))
        else:
            await edit_message_safe(query, "❌ Ошибка при открытии тикета",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("◀️ Назад", callback_data='admin_support_tickets')
                                   ]]))
        return
    
    if data == 'admin_settings':
        access_enabled = db.is_bot_access_enabled()
        sales_enabled = db.is_sales_enabled()
        bonuses_promocodes_enabled = db.is_bonuses_promocodes_enabled()
        message = "⚙️ <b>Настройки бота</b>\n\n"
        message += f"🔒 <b>Доступ к боту:</b> {'✅ Открыт' if access_enabled else '❌ Закрыт'}\n"
        message += f"💰 <b>Продажи:</b> {'🟢 Открыты' if sales_enabled else '🔴 Закрыты'}\n"
        message += f"🎁 <b>Бонусы и промокоды при оплате:</b> {'✅ Разрешены' if bonuses_promocodes_enabled else '❌ Отключены'}\n\n"
        message += "Выберите действие:"
        keyboard = [
            [InlineKeyboardButton("🔒 Закрыть доступ" if access_enabled else "🔓 Открыть доступ", 
                                callback_data='admin_toggle_access')],
            [InlineKeyboardButton("🎁 Выкл. бонусы/промокоды" if bonuses_promocodes_enabled else "🎁 Вкл. бонусы/промокоды",
                                callback_data='admin_toggle_bonuses_promocodes')],
            [InlineKeyboardButton("✏️ Редактировать главное меню", callback_data='admin_edit_menu')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_panel')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_toggle_bonuses_promocodes':
        current_status = db.is_bonuses_promocodes_enabled()
        db.set_bot_setting('bonuses_promocodes_enabled', '0' if current_status else '1')
        new_status = db.is_bonuses_promocodes_enabled()
        status_text = "разрешены" if new_status else "отключены"
        message = f"✅ <b>Оплата бонусами и промокодами {status_text}</b>\n\n"
        message += "При отключении пользователи смогут оплачивать билеты только полной стоимостью."
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_settings')]]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_toggle_access':
        current_status = db.is_bot_access_enabled()
        db.set_bot_setting('bot_access_enabled', '0' if current_status else '1')
        new_status = db.is_bot_access_enabled()
        message = f"✅ <b>Доступ к боту {'открыт' if new_status else 'закрыт'}</b>"
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_settings')]
        ]
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_edit_menu':
        try:
            current_text = db.get_main_menu_text()
        except:
            current_text = "Ошибка загрузки текста"
        message = f"✏️ <b>Редактирование главного меню</b>\n\n"
        message += f"<b>Текущий текст:</b>\n{current_text}\n\n"
        message += "📝 <b>Отправьте новый текст для главного меню:</b>\n\n"
        message += "💡 <b>Или нажмите кнопку для сброса к значениям по умолчанию:</b>"
        keyboard = [
            [InlineKeyboardButton("🔄 Сбросить к умолчанию", callback_data='admin_reset_menu')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_settings')]
        ]
        db.set_user_state(user_id, 'admin_editing_menu_text')
        await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == 'admin_reset_menu':
        default_text = """🎉 <b>Добро пожаловать в KISS PARTY!</b>

🎪 Мы рады приветствовать вас на нашем мероприятии!

Выберите действие:"""
        db.set_bot_setting('main_menu_text', default_text)
        db.set_bot_setting('main_menu_image', None)
        await edit_message_safe(query, "✅ <b>Главное меню сброшено к значениям по умолчанию!</b>",
                                     reply_markup=InlineKeyboardMarkup([[
                                         InlineKeyboardButton("◀️ Назад", callback_data='admin_settings')
                                     ]]))
        return

async def handle_promoter_panel(query, user_id):
    """Обработчик панели промоутера"""
    # Проверяем промокод напрямую из базы данных
    promo_code = db.get_promoter_code(user_id)
    
    if not promo_code:
        # Генерируем код промоутера только если его еще нет
        import random
        import string
        promo_code = 'PROMO' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Обновляем только promo_code, сохраняя существующую роль
        user = db.get_user(user_id)
        if user:
            db.create_user(
                user_id=user_id,
                username=user.get('username'),
                first_name=user.get('first_name'),
                last_name=user.get('last_name'),
                role=user.get('role', 'user'),  # Сохраняем существующую роль
                promo_code=promo_code
            )
        else:
            db.create_user(user_id=user_id, promo_code=promo_code)
        logger.info(f"Generated new promo code for promoter {user_id}: {promo_code}")
    else:
        logger.info(f"Using existing promo code for promoter {user_id}: {promo_code}")
    
    # Получаем статистику после проверки/создания промокода
    stats = db.get_promoter_statistics(user_id)
    
    bot_username = bot.username
    promo_link = f"https://t.me/{bot_username}?start=promo{promo_code}"
    
    message = "👤 <b>Панель промоутера</b>\n\n"
    message += f"🎫 <b>Ваш промокод:</b> <code>{promo_code}</code>\n\n"
    message += f"🔗 <b>Ваша промо-ссылка:</b>\n{promo_link}\n\n"
    message += f"📊 <b>Статистика:</b>\n"
    message += f"• Приглашено пользователей: {stats.get('invited_users', 0)}\n"
    message += f"• Покупок от приглашенных: {stats.get('purchases_count', 0)}\n"
    message += f"• Выручка: {stats.get('revenue', 0):.2f}₽\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Поделиться ссылкой", url=f"https://t.me/share/url?url={promo_link}&text=Присоединяйся!")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
    ]
    await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin для быстрого доступа к админ-панели"""
    try:
        user_id = update.effective_user.id
        logger.info(f"Handle /admin command from user {user_id}")
        
        # Проверяем доступ к боту
        if not db.is_bot_access_enabled() and not is_admin(user_id):
            await send_message(user_id, "❌ <b>Доступ к боту временно закрыт</b>\n\nПопробуйте позже.")
            return
        
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа к админ-панели")
            return
        
        message = "⚙️ <b>Админ-панель</b>\n\nВыберите раздел:"
        await send_message(user_id, message, parse_mode='HTML', reply_markup=get_admin_panel_menu())
    except Exception as e:
        logger.error(f"Error in handle_admin_command: {e}", exc_info=True)
        try:
            await send_message(update.effective_user.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

async def handle_setadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /setadmin для установки админа"""
    user_id = update.effective_user.id
    
    # Проверяем, что пользователь в списке админов из config или уже админ
    if user_id not in config.ADMIN_USERS and not is_admin(user_id):
        await send_message(user_id, "❌ У вас нет прав для выполнения этой команды")
        return
    
    # Если есть аргумент - устанавливаем админа по user_id
    if context.args and len(context.args) > 0:
        try:
            target_user_id = int(context.args[0])
            db.update_user_role(target_user_id, 'admin')
            target_user = await bot.get_chat(target_user_id)
            await send_message(user_id, f"✅ Пользователь @{target_user.username or target_user.first_name} (ID: {target_user_id}) назначен админом")
            await send_message(target_user_id, "🎉 <b>Вам предоставлены права администратора!</b>\n\nИспользуйте /start для доступа к админ-панели.")
        except ValueError:
            await send_message(user_id, "❌ Неверный формат. Используйте: /setadmin <user_id>")
        except Exception as e:
            await send_message(user_id, f"❌ Ошибка: {e}")
    else:
        # Показываем инструкцию
        message = "👤 <b>Установка администратора</b>\n\n"
        message += "Использование:\n"
        message += "<code>/setadmin &lt;user_id&gt;</code>\n\n"
        message += "Пример:\n"
        message += "<code>/setadmin 123456789</code>\n\n"
        message += "💡 <b>Как узнать user_id?</b>\n"
        message += "1. Попросите пользователя написать боту @userinfobot\n"
        message += "2. Или используйте SQL запрос в БД\n\n"
        message += "📝 <b>Альтернативный способ через SQL:</b>\n"
        message += "<code>UPDATE users SET role = 'admin' WHERE user_id = &lt;user_id&gt;;</code>"
        await send_message(user_id, message, parse_mode='HTML')

async def handle_promoter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /promoter"""
    user_id = update.effective_user.id
    
    if not is_promoter(user_id):
        await send_message(user_id, "❌ У вас нет доступа к панели промоутера")
        return
    
    # Проверяем промокод напрямую из базы данных
    promo_code = db.get_promoter_code(user_id)
    
    if not promo_code:
        # Генерируем код промоутера только если его еще нет
        import random
        import string
        promo_code = 'PROMO' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Обновляем только promo_code, сохраняя существующую роль
        user = db.get_user(user_id)
        if user:
            db.create_user(
                user_id=user_id,
                username=user.get('username'),
                first_name=user.get('first_name'),
                last_name=user.get('last_name'),
                role=user.get('role', 'user'),  # Сохраняем существующую роль
                promo_code=promo_code
            )
        else:
            db.create_user(user_id=user_id, promo_code=promo_code)
        logger.info(f"Generated new promo code for promoter {user_id}: {promo_code}")
    else:
        logger.info(f"Using existing promo code for promoter {user_id}: {promo_code}")
    
    # Получаем статистику после проверки/создания промокода
    stats = db.get_promoter_statistics(user_id)
    
    bot_username = bot.username
    promo_link = f"https://t.me/{bot_username}?start=promo{promo_code}"
    
    message = "👤 <b>Панель промоутера</b>\n\n"
    message += f"🎫 <b>Ваш промокод:</b> <code>{promo_code}</code>\n\n"
    message += f"🔗 <b>Ваша промо-ссылка:</b>\n{promo_link}\n\n"
    message += f"📊 <b>Статистика:</b>\n"
    message += f"• Приглашено пользователей: {stats.get('invited_users', 0)}\n"
    message += f"• Покупок от приглашенных: {stats.get('purchases_count', 0)}\n"
    message += f"• Выручка: {stats.get('revenue', 0):.2f}₽\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Поделиться ссылкой", url=f"https://t.me/share/url?url={promo_link}&text=Присоединяйся!")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data='main_menu')]
    ]
    await send_message(user_id, message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    state_data = db.get_user_state(user_id)
    
    # Обработка фото для анкеты "Поиск пары"
    if state_data and state_data.get('state') in ['dating_waiting_photo', 'dating_waiting_photo_edit']:
        photo = update.message.photo[-1]  # Берем самое большое фото
        file_id = photo.file_id
        
        if state_data.get('state') == 'dating_waiting_photo_edit':
            # Редактирование фото - обновляем только фото
            profile = db.get_dating_profile(user_id)
            if profile:
                if db.create_dating_profile(user_id, file_id, profile['gender'], profile['looking_for'],
                                          profile.get('name'), profile.get('age'), profile.get('description')):
                    await send_message(user_id, "✅ Фото успешно обновлено!")
                    db.clear_user_state(user_id)
                    await show_my_profile(user_id)
                else:
                    await send_message(user_id, "❌ Ошибка при обновлении фото.")
            else:
                await send_message(user_id, "❌ Анкета не найдена.")
                db.clear_user_state(user_id)
            return
        
        # Создание новой анкеты - сохраняем file_id в состоянии
        db.set_user_state(user_id, state_data.get('state'), {'photo_file_id': file_id})
        
        # Переходим к выбору пола
        message = "👤 <b>Шаг 2:</b> Укажите ваш пол\n\n"
        message += "Выберите ваш пол:"
        keyboard = [
            [InlineKeyboardButton("👨 Мужской", callback_data='dating_select_gender_male')],
            [InlineKeyboardButton("👩 Женский", callback_data='dating_select_gender_female')],
            [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
        ]
        await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state_data and state_data.get('state') == 'admin_editing_menu_image':
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            db.clear_user_state(user_id)
            return
        
        photo = update.message.photo[-1]  # Берем самое большое фото
        file_id = photo.file_id
        db.set_bot_setting('main_menu_image', file_id)
        await send_message(user_id, "✅ <b>Изображение главного меню обновлено!</b>")
        db.clear_user_state(user_id)
        return
    
    # Обработка публикации поста с фото
    if state_data and (state_data.get('state') == 'admin_broadcast_text_photo' or state_data.get('state', '').startswith('admin_broadcast_text_photo')):
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            db.clear_user_state(user_id)
            return
        
        logger.info(f"Processing photo for broadcast, state: {state_data.get('state')}, user_id: {user_id}")
        
        photo = update.message.photo[-1]
        file_id = photo.file_id
        caption = update.message.caption or ""
        
        # Получаем сохраненный текст и entities
        state_text = ""
        saved_entities = None
        if state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                import json
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                    state_text = state_data_dict.get('text', '')
                    saved_entities = state_data_dict.get('entities')
                except:
                    state_text = ""
            else:
                state_data_dict = state_data.get('data', {})
                state_text = state_data_dict.get('text', '')
                saved_entities = state_data_dict.get('entities')
        
        # Если есть caption с entities, используем их, иначе используем сохраненные
        final_text = caption if caption else state_text
        final_entities = None
        
        # Если есть caption с entities, используем их
        if caption and update.message.caption_entities:
            from telegram import MessageEntity
            final_entities = []
            for entity in update.message.caption_entities:
                entity_dict = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length
                }
                if entity.url:
                    entity_dict['url'] = entity.url
                if entity.user:
                    entity_dict['user'] = {
                        'id': entity.user.id,
                        'is_bot': entity.user.is_bot,
                        'first_name': entity.user.first_name
                    }
                if entity.language:
                    entity_dict['language'] = entity.language
                final_entities.append(entity_dict)
        elif saved_entities:
            # Используем сохраненные entities, но нужно скорректировать offset если есть caption
            if caption:
                # Если есть caption, entities должны быть применены к caption, а не к сохраненному тексту
                final_entities = None  # Используем entities из caption
            else:
                final_entities = saved_entities
        
        logger.info(f"Photo received: file_id={file_id}, caption={caption}, state_text={state_text}, final_text={final_text}, entities={final_entities}")
        
        # Сохраняем данные поста
        import json
        post_data = {
            'text': final_text, 
            'file_id': file_id, 
            'type': 'photo',
            'entities': final_entities
        }
        db.set_user_state(user_id, 'admin_broadcast_ready', post_data)
        
        await send_message(user_id,
            f"📝 <b>Предпросмотр поста:</b>\n\n{final_text}\n\n"
            "🖼️ <b>С фото</b>\n\n"
            "🔘 <b>Добавить кнопку 'Купить билет'?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, добавить кнопку", callback_data='admin_confirm_broadcast_photo_with_button')],
                [InlineKeyboardButton("❌ Нет, без кнопки", callback_data='admin_confirm_broadcast_photo_no_button')],
                [InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')]
            ]))
        return

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик видео"""
    user_id = update.effective_user.id
    state_data = db.get_user_state(user_id)
    
    if state_data and state_data.get('state', '').startswith('admin_broadcast_text_video'):
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            db.clear_user_state(user_id)
            return
        
        video = update.message.video
        file_id = video.file_id
        caption = update.message.caption or ""
        
        # Получаем сохраненный текст и entities
        state_text = ""
        saved_entities = None
        if state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                import json
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                    state_text = state_data_dict.get('text', '')
                    saved_entities = state_data_dict.get('entities')
                except:
                    state_text = ""
            else:
                state_data_dict = state_data.get('data', {})
                state_text = state_data_dict.get('text', '')
                saved_entities = state_data_dict.get('entities')
        
        # Если есть caption с entities, используем их, иначе используем сохраненные
        final_text = caption if caption else state_text
        final_entities = None
        
        # Если есть caption с entities, используем их
        if caption and update.message.caption_entities:
            from telegram import MessageEntity
            final_entities = []
            for entity in update.message.caption_entities:
                entity_dict = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length
                }
                if entity.url:
                    entity_dict['url'] = entity.url
                if entity.user:
                    entity_dict['user'] = {
                        'id': entity.user.id,
                        'is_bot': entity.user.is_bot,
                        'first_name': entity.user.first_name
                    }
                if entity.language:
                    entity_dict['language'] = entity.language
                final_entities.append(entity_dict)
        elif saved_entities:
            final_entities = saved_entities
        
        import json
        post_data = {
            'text': final_text, 
            'file_id': file_id, 
            'type': 'video',
            'entities': final_entities
        }
        db.set_user_state(user_id, 'admin_broadcast_ready', post_data)
        
        await send_message(user_id,
            f"📝 <b>Предпросмотр поста:</b>\n\n{final_text}\n\n"
            "🎥 <b>С видео</b>\n\n"
            "🔘 <b>Добавить кнопку 'Купить билет'?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, добавить кнопку", callback_data='admin_confirm_broadcast_video_with_button')],
                [InlineKeyboardButton("❌ Нет, без кнопки", callback_data='admin_confirm_broadcast_video_no_button')],
                [InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')]
            ]))
        return

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    user_id = update.effective_user.id
    state_data = db.get_user_state(user_id)
    
    if state_data and state_data.get('state') == 'admin_broadcasting_voice':
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            db.clear_user_state(user_id)
            return
        
        voice = update.message.voice
        file_id = voice.file_id
        
        import json
        post_data = {'file_id': file_id, 'type': 'voice'}
        db.set_user_state(user_id, 'admin_broadcast_ready', post_data)
        
        await send_message(user_id,
            "🎤 <b>Голосовое сообщение получено</b>\n\n"
            "✅ <b>Отправить всем пользователям?</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Отправить", callback_data='admin_confirm_broadcast_voice'),
                InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')
            ]]))
        return

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов"""
    user_id = update.effective_user.id
    state_data = db.get_user_state(user_id)
    
    if state_data and state_data.get('state', '').startswith('admin_broadcast_text_document'):
        if not is_admin(user_id):
            await send_message(user_id, "❌ У вас нет доступа")
            db.clear_user_state(user_id)
            return
        
        document = update.message.document
        file_id = document.file_id
        caption = update.message.caption or ""
        
        # Получаем сохраненный текст и entities
        state_text = ""
        saved_entities = None
        if state_data.get('data'):
            if isinstance(state_data.get('data'), str):
                import json
                try:
                    state_data_dict = json.loads(state_data.get('data'))
                    state_text = state_data_dict.get('text', '')
                    saved_entities = state_data_dict.get('entities')
                except:
                    state_text = ""
            else:
                state_data_dict = state_data.get('data', {})
                state_text = state_data_dict.get('text', '')
                saved_entities = state_data_dict.get('entities')
        
        # Если есть caption с entities, используем их, иначе используем сохраненные
        final_text = caption if caption else state_text
        final_entities = None
        
        # Если есть caption с entities, используем их
        if caption and update.message.caption_entities:
            from telegram import MessageEntity
            final_entities = []
            for entity in update.message.caption_entities:
                entity_dict = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length
                }
                if entity.url:
                    entity_dict['url'] = entity.url
                if entity.user:
                    entity_dict['user'] = {
                        'id': entity.user.id,
                        'is_bot': entity.user.is_bot,
                        'first_name': entity.user.first_name
                    }
                if entity.language:
                    entity_dict['language'] = entity.language
                final_entities.append(entity_dict)
        elif saved_entities:
            final_entities = saved_entities
        
        import json
        post_data = {
            'text': final_text, 
            'file_id': file_id, 
            'type': 'document',
            'entities': final_entities
        }
        db.set_user_state(user_id, 'admin_broadcast_ready', post_data)
        
        await send_message(user_id,
            f"📝 <b>Предпросмотр поста:</b>\n\n{final_text}\n\n"
            "📄 <b>С документом</b>\n\n"
            "🔘 <b>Добавить кнопку 'Купить билет'?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, добавить кнопку", callback_data='admin_confirm_broadcast_document_with_button')],
                [InlineKeyboardButton("❌ Нет, без кнопки", callback_data='admin_confirm_broadcast_document_no_button')],
                [InlineKeyboardButton("❌ Отменить", callback_data='admin_panel')]
            ]))
        return

async def send_broadcast_to_all_users(post_data, admin_id, add_button=False):
    """Отправить пост всем пользователям"""
    from database import execute_query
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
    users = execute_query("SELECT user_id FROM users", fetch=True) or []
    sent = 0
    failed = 0
    received = 0
    not_received = 0
    blocked = 0
    other_errors = 0
    errors_list = []
    
    # Создаем клавиатуру с кнопкой, если нужно
    reply_markup = None
    if add_button:
        # Получаем username бота
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            start_url = f"https://t.me/{bot_username}?start=menu"
        except:
            # Если не удалось получить username, используем просто /start
            start_url = "https://t.me/kissspartypaybot?start=menu"
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎫 Купить билет", url=start_url)
        ]])
    
    # Преобразуем entities из словарей в объекты MessageEntity, если они есть
    entities = None
    if post_data.get('entities'):
        entities = []
        for entity_dict in post_data['entities']:
            try:
                entity_type = entity_dict.get('type')
                offset = entity_dict.get('offset', 0)
                length = entity_dict.get('length', 0)
                
                # Создаем MessageEntity в зависимости от типа
                if entity_type == 'text_link':
                    entity = MessageEntity(
                        type=entity_type, 
                        offset=offset, 
                        length=length, 
                        url=entity_dict.get('url')
                    )
                elif entity_type == 'text_mention':
                    from telegram import User
                    user_dict = entity_dict.get('user', {})
                    if user_dict:
                        user = User(
                            id=user_dict.get('id'),
                            is_bot=user_dict.get('is_bot', False),
                            first_name=user_dict.get('first_name', '')
                        )
                        entity = MessageEntity(
                            type=entity_type, 
                            offset=offset, 
                            length=length, 
                            user=user
                        )
                    else:
                        # Если нет данных о пользователе, создаем без user
                        entity = MessageEntity(type=entity_type, offset=offset, length=length)
                elif entity_type == 'pre':
                    entity = MessageEntity(
                        type=entity_type, 
                        offset=offset, 
                        length=length, 
                        language=entity_dict.get('language')
                    )
                else:
                    # Для всех остальных типов (bold, italic, code, etc.)
                    entity = MessageEntity(type=entity_type, offset=offset, length=length)
                entities.append(entity)
            except Exception as e:
                logger.error(f"Error creating MessageEntity from dict: {e}, dict: {entity_dict}")
                # Пропускаем проблемный entity, но продолжаем обработку
                continue
    
    # Определяем, использовать ли entities или parse_mode
    use_entities = entities is not None and len(entities) > 0
    parse_mode = None if use_entities else 'HTML'
    
    for user in users:
        try:
            user_id = user['user_id']
            if post_data['type'] == 'text':
                if use_entities:
                    await bot.send_message(chat_id=user_id, text=post_data['text'], 
                                         entities=entities, reply_markup=reply_markup)
                else:
                    await bot.send_message(chat_id=user_id, text=post_data['text'], 
                                         parse_mode=parse_mode, reply_markup=reply_markup)
            elif post_data['type'] == 'photo':
                if use_entities:
                    await bot.send_photo(chat_id=user_id, photo=post_data['file_id'], 
                                       caption=post_data.get('text', ''), caption_entities=entities,
                                       reply_markup=reply_markup)
                else:
                    await bot.send_photo(chat_id=user_id, photo=post_data['file_id'], 
                                       caption=post_data.get('text', ''), parse_mode=parse_mode,
                                       reply_markup=reply_markup)
            elif post_data['type'] == 'video':
                if use_entities:
                    await bot.send_video(chat_id=user_id, video=post_data['file_id'],
                                       caption=post_data.get('text', ''), caption_entities=entities,
                                       reply_markup=reply_markup)
                else:
                    await bot.send_video(chat_id=user_id, video=post_data['file_id'],
                                       caption=post_data.get('text', ''), parse_mode=parse_mode,
                                       reply_markup=reply_markup)
            elif post_data['type'] == 'voice':
                await bot.send_voice(chat_id=user_id, voice=post_data['file_id'],
                                    reply_markup=reply_markup)
            elif post_data['type'] == 'document':
                if use_entities:
                    await bot.send_document(chat_id=user_id, document=post_data['file_id'],
                                           caption=post_data.get('text', ''), caption_entities=entities,
                                           reply_markup=reply_markup)
                else:
                    await bot.send_document(chat_id=user_id, document=post_data['file_id'],
                                           caption=post_data.get('text', ''), parse_mode=parse_mode,
                                           reply_markup=reply_markup)
            sent += 1
            received += 1
        except Exception as e:
            failed += 1
            error_msg = str(e).lower()
            if 'blocked' in error_msg or 'bot was blocked' in error_msg:
                blocked += 1
            elif 'chat not found' in error_msg or 'user not found' in error_msg:
                not_received += 1
            else:
                other_errors += 1
                if len(errors_list) < 10:  # Сохраняем до 10 примеров ошибок
                    errors_list.append(f"User {user.get('user_id')}: {str(e)[:50]}")
            logger.error(f"Error sending broadcast to {user.get('user_id')}: {e}")
    
    # Сохраняем статистику
    from database import execute_query
    import json
    execute_query(
        """INSERT INTO broadcasts (admin_id, message_type, text, file_id, sent_count, failed_count, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'completed')""",
        (admin_id, post_data['type'], post_data.get('text'), post_data.get('file_id'), sent, failed)
    )
    
    details = {
        'received': received,
        'not_received': not_received,
        'blocked': blocked,
        'other_errors': other_errors,
        'errors_list': errors_list
    }
    
    return sent, failed, details

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ "ПОИСК ПАРЫ" ====================

async def show_my_profile(user_id: int):
    """Показать анкету пользователя"""
    profile = db.get_dating_profile(user_id)
    if not profile:
        await send_message(user_id, "❌ Анкета не найдена.")
        return
    
    user = db.get_user(user_id)
    username = user.get('username', 'не указан') if user else 'не указан'
    
    message = "👤 <b>Моя анкета</b>\n\n"
    
    # Имя
    profile_name = profile.get('name')
    if profile_name:
        message += f"👤 <b>Имя:</b> {profile_name}\n"
    elif user:
        first_name = user.get('first_name', '')
        if first_name:
            message += f"👤 <b>Имя:</b> {first_name}\n"
    
    # Возраст
    if profile.get('age'):
        message += f"🎂 <b>Возраст:</b> {profile.get('age')}\n"
    
    # Username
    if username != 'не указан':
        message += f"🔗 <b>Username:</b> @{username}\n"
    
    # Пол
    gender_text = "👨 Мужской" if profile['gender'] == 'male' else "👩 Женский"
    message += f"👤 <b>Пол:</b> {gender_text}\n"
    
    # Ищете
    looking_for_text = {
        'male': '👨 Парней',
        'female': '👩 Девушек',
        'both': '👥 Всех'
    }.get(profile['looking_for'], profile['looking_for'])
    message += f"🔍 <b>Ищете:</b> {looking_for_text}\n"
    
    # Описание
    if profile.get('description'):
        message += f"\n📝 <b>О себе:</b>\n{profile.get('description')}\n"
    else:
        message += f"\n📝 <b>О себе:</b> не указано\n"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Редактировать анкету", callback_data='dating_edit_profile')],
        [InlineKeyboardButton("🗑️ Удалить анкету", callback_data='dating_delete_profile')],
        [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
    ]
    
    try:
        if profile.get('photo_file_id'):
            await bot.send_photo(
                chat_id=user_id,
                photo=profile['photo_file_id'],
                caption=message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error showing my profile: {e}")
        await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_dating_profile_by_id(user_id: int, target_user_id: int, query=None, is_liked=False, remaining_count=0):
    """Показать анкету конкретного пользователя"""
    profile = db.get_dating_profile(target_user_id)
    if not profile:
        await send_message(user_id, "❌ Анкета не найдена или деактивирована.")
        return
    
    target_user = db.get_user(target_user_id)
    username = target_user.get('username', 'не указан') if target_user else 'не указан'
    
    message = f"💕 <b>Анкета</b>\n\n"
    
    # Имя
    profile_name = profile.get('name')
    if profile_name:
        message += f"👤 <b>Имя:</b> {profile_name}\n"
    elif target_user:
        first_name = target_user.get('first_name', '')
        if first_name:
            message += f"👤 <b>Имя:</b> {first_name}\n"
    
    # Возраст
    if profile.get('age'):
        message += f"🎂 <b>Возраст:</b> {profile.get('age')}\n"
    
    # Username скрыт до мэтча
    # if username != 'не указан':
    #     message += f"🔗 <b>Username:</b> @{username}\n"
    
    # Пол
    gender_text = "👨 Мужской" if profile['gender'] == 'male' else "👩 Женский"
    message += f"👤 <b>Пол:</b> {gender_text}\n"
    
    # Описание
    if profile.get('description'):
        message += f"\n📝 <b>О себе:</b>\n{profile.get('description')}\n"
    
    if is_liked:
        message += f"\n💌 <b>Этот человек вас лайкнул!</b>"
        if remaining_count > 0:
            message += f"\n\n📊 Еще {remaining_count} человек(а) вас лайкнули"
    
    message += "\n\n💡 Что вы думаете об этой анкете?"
    
    keyboard = [
        [
            InlineKeyboardButton("❤️ Лайк", callback_data=f'dating_like_{target_user_id}'),
            InlineKeyboardButton("👎 Дизлайк", callback_data=f'dating_dislike_{target_user_id}')
        ]
    ]
    
    if is_liked and remaining_count > 0:
        keyboard.append([InlineKeyboardButton("➡️ Следующий", callback_data='dating_next_liked_user')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')])
    
    try:
        # Удаляем предыдущее сообщение, если есть query
        if query:
            try:
                await query.message.delete()
            except:
                pass
        
        # Отправляем фото с анкетой
        await bot.send_photo(
            chat_id=user_id,
            photo=profile['photo_file_id'],
            caption=message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error showing profile by id: {e}")
        # Если не удалось отправить фото, отправляем текстовое сообщение
        message += f"\n\n⚠️ Фото временно недоступно"
        if query:
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_next_dating_profile(user_id: int, query=None):
    """Показать следующую доступную анкету"""
    profiles = db.get_available_profiles(user_id, limit=1)
    
    if not profiles:
        message = "😔 <b>Анкеты закончились</b>\n\n"
        message += "💡 Пока нет новых анкет для просмотра.\n"
        message += "Попробуйте позже или проверьте, кто вас лайкнул!"
        keyboard = [
            [InlineKeyboardButton("💌 Кто меня лайкнул", callback_data='dating_likes_received')],
            [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
        ]
        if query:
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    profile = profiles[0]
    target_user_id = profile['user_id']
    target_user = db.get_user(target_user_id)
    username = profile.get('username', 'не указан')
    
    message = f"💕 <b>Новая анкета</b>\n\n"
    
    # Имя из анкеты или из профиля пользователя
    profile_name = profile.get('name')
    if profile_name:
        message += f"👤 <b>Имя:</b> {profile_name}\n"
    elif target_user:
        first_name = target_user.get('first_name', '')
        if first_name:
            message += f"👤 <b>Имя:</b> {first_name}\n"
    
    # Возраст
    if profile.get('age'):
        message += f"🎂 <b>Возраст:</b> {profile.get('age')}\n"
    
    # Username скрыт до мэтча
    # if username != 'не указан':
    #     message += f"🔗 <b>Username:</b> @{username}\n"
    
    # Пол
    gender_text = "👨 Мужской" if profile['gender'] == 'male' else "👩 Женский"
    message += f"👤 <b>Пол:</b> {gender_text}\n"
    
    # Описание
    if profile.get('description'):
        message += f"\n📝 <b>О себе:</b>\n{profile.get('description')}\n"
    
    message += "\n💡 Что вы думаете об этой анкете?"
    
    keyboard = [
        [
            InlineKeyboardButton("❤️ Лайк", callback_data=f'dating_like_{target_user_id}'),
            InlineKeyboardButton("👎 Дизлайк", callback_data=f'dating_dislike_{target_user_id}')
        ],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data='dating_skip_0')],
        [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
    ]
    
    try:
        # Удаляем предыдущее сообщение, если есть query
        if query:
            try:
                await query.message.delete()
            except:
                pass
        
        # Отправляем фото с анкетой
        await bot.send_photo(
            chat_id=user_id,
            photo=profile['photo_file_id'],
            caption=message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error showing profile: {e}")
        # Если не удалось отправить фото, отправляем текстовое сообщение
        message += f"\n\n⚠️ Фото временно недоступно"
        if query:
            await edit_message_safe(query, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await send_message(user_id, message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def process_dating_like(from_user_id: int, to_user_id: int, action: str, query=None):
    """Обработать лайк или дизлайк"""
    # Сохраняем лайк/дизлайк
    db.add_dating_like(from_user_id, to_user_id, action)
    
    if action == 'like':
        # Проверяем, есть ли взаимный лайк (мэтч)
        is_match = db.check_match(from_user_id, to_user_id)
        logger.info(f"Dating like from {from_user_id} to {to_user_id}. Match: {is_match}")
        
        if is_match:
            # Создаем мэтч
            db.create_match(from_user_id, to_user_id)
            logger.info(f"Match created between {from_user_id} and {to_user_id}")
            
            # Получаем информацию о пользователях
            from_user = db.get_user(from_user_id)
            to_user = db.get_user(to_user_id)
            
            from_username = from_user.get('username', 'не указан') if from_user else 'не указан'
            to_username = to_user.get('username', 'не указан') if to_user else 'не указан'
            
            # Получаем профили для более информативного уведомления
            from_profile = db.get_dating_profile(from_user_id)
            to_profile = db.get_dating_profile(to_user_id)
            
            # Формируем уведомления с подробной информацией
            match_message_from = f"🎉 <b>У ВАС МЭТЧ!</b>\n\n"
            match_message_from += f"💕 Вы нашли друг друга!\n\n"
            match_message_from += f"━━━━━━━━━━━━━━━━━━━━\n"
            match_message_from += f"👤 <b>Информация о мэтче:</b>\n\n"
            
            if to_profile:
                to_name = to_profile.get('name') or to_user.get('first_name', '') or (f"@{to_username}" if to_username != 'не указан' else f"ID {to_user_id}")
                match_message_from += f"👤 <b>Имя:</b> {to_name}\n"
                if to_profile.get('age'):
                    match_message_from += f"🎂 <b>Возраст:</b> {to_profile.get('age')}\n"
                if to_profile.get('description'):
                    desc = to_profile.get('description', '')[:150]
                    match_message_from += f"📝 <b>О себе:</b> {desc}...\n"
            
            match_message_from += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            if to_username != 'не указан':
                match_message_from += f"💬 <b>Напишите:</b> @{to_username}\n"
            else:
                match_message_from += f"💬 <b>ID:</b> {to_user_id}\n"
            match_message_from += f"\n🎯 <b>Начните общение!</b>"
            
            match_message_to = f"🎉 <b>У ВАС МЭТЧ!</b>\n\n"
            match_message_to += f"💕 Вы нашли друг друга!\n\n"
            match_message_to += f"━━━━━━━━━━━━━━━━━━━━\n"
            match_message_to += f"👤 <b>Информация о мэтче:</b>\n\n"
            
            if from_profile:
                from_name = from_profile.get('name') or from_user.get('first_name', '') or (f"@{from_username}" if from_username != 'не указан' else f"ID {from_user_id}")
                match_message_to += f"👤 <b>Имя:</b> {from_name}\n"
                if from_profile.get('age'):
                    match_message_to += f"🎂 <b>Возраст:</b> {from_profile.get('age')}\n"
                if from_profile.get('description'):
                    desc = from_profile.get('description', '')[:150]
                    match_message_to += f"📝 <b>О себе:</b> {desc}...\n"
            
            match_message_to += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            if from_username != 'не указан':
                match_message_to += f"💬 <b>Напишите:</b> @{from_username}\n"
            else:
                match_message_to += f"💬 <b>ID:</b> {from_user_id}\n"
            match_message_to += f"\n🎯 <b>Начните общение!</b>"
            
            # Кнопки для быстрого доступа
            keyboard_from = [
                [InlineKeyboardButton("👀 Посмотреть анкету", callback_data=f'dating_view_liked_user_{to_user_id}')],
                [InlineKeyboardButton("💌 Мои мэтчи", callback_data='dating_my_matches')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
            ]
            
            keyboard_to = [
                [InlineKeyboardButton("👀 Посмотреть анкету", callback_data=f'dating_view_liked_user_{from_user_id}')],
                [InlineKeyboardButton("💌 Мои мэтчи", callback_data='dating_my_matches')],
                [InlineKeyboardButton("◀️ Назад", callback_data='dating_menu')]
            ]
            
            # Отправляем уведомление первому пользователю (независимо)
            try:
                if to_profile and to_profile.get('photo_file_id'):
                    try:
                        await bot.send_photo(
                            chat_id=from_user_id,
                            photo=to_profile['photo_file_id'],
                            caption=match_message_from,
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup(keyboard_from)
                        )
                        logger.info(f"Match notification with photo sent to user {from_user_id}")
                    except Exception as photo_error:
                        # Если не удалось отправить фото, отправляем текстом
                        logger.warning(f"Failed to send photo to user {from_user_id}, sending text: {photo_error}")
                        await send_message(from_user_id, match_message_from, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard_from))
                else:
                    await send_message(from_user_id, match_message_from, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard_from))
                    logger.info(f"Match notification sent to user {from_user_id}")
            except Exception as e:
                logger.error(f"CRITICAL: Failed to send match notification to user {from_user_id}: {e}")
                logger.error(traceback.format_exc())
            
            # Отправляем уведомление второму пользователю (независимо)
            try:
                if from_profile and from_profile.get('photo_file_id'):
                    try:
                        await bot.send_photo(
                            chat_id=to_user_id,
                            photo=from_profile['photo_file_id'],
                            caption=match_message_to,
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup(keyboard_to)
                        )
                        logger.info(f"Match notification with photo sent to user {to_user_id}")
                    except Exception as photo_error:
                        # Если не удалось отправить фото, отправляем текстом
                        logger.warning(f"Failed to send photo to user {to_user_id}, sending text: {photo_error}")
                        await send_message(to_user_id, match_message_to, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard_to))
                else:
                    await send_message(to_user_id, match_message_to, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard_to))
                    logger.info(f"Match notification sent to user {to_user_id}")
            except Exception as e:
                logger.error(f"CRITICAL: Failed to send match notification to user {to_user_id}: {e}")
                logger.error(traceback.format_exc())
        else:
            # Отправляем уведомление пользователю, что его лайкнули с кнопками
            from_user_profile = db.get_dating_profile(from_user_id)
            from_user = db.get_user(from_user_id)
            from_username = from_user.get('username', 'не указан') if from_user else 'не указан'
            from_first_name = from_user.get('first_name', '') if from_user else ''
            
            like_message = f"💌 <b>Вас лайкнули!</b>\n\n"
            if from_user_profile:
                # Username скрыт до мэтча - используем только имя
                profile_name = from_user_profile.get('name') or from_first_name or f"Пользователь"
                like_message += f"❤️ Вас лайкнул(а): {profile_name}\n\n"
                if from_user_profile.get('age'):
                    like_message += f"🎂 Возраст: {from_user_profile.get('age')}\n"
                if from_user_profile.get('description'):
                    desc = from_user_profile.get('description', '')[:200]
                    like_message += f"📝 {desc}\n\n"
            else:
                # Username скрыт до мэтча
                if from_first_name:
                    like_message += f"❤️ Вас лайкнул(а): {from_first_name}\n\n"
                else:
                    like_message += f"❤️ Вас лайкнул(а) пользователь\n\n"
            
            like_message += "💡 Хотите посмотреть анкету и ответить?"
            
            keyboard = [
                [
                    InlineKeyboardButton("❤️ Лайкнуть в ответ", callback_data=f'dating_like_{from_user_id}'),
                    InlineKeyboardButton("👎 Дизлайк", callback_data=f'dating_dislike_{from_user_id}')
                ],
                [InlineKeyboardButton("👀 Посмотреть анкету", callback_data=f'dating_view_liked_user_{from_user_id}')],
                [InlineKeyboardButton("◀️ Пропустить", callback_data='dating_menu')]
            ]
            
            # Отправляем уведомление о лайке с fallback механизмом
            try:
                if from_user_profile and from_user_profile.get('photo_file_id'):
                    try:
                        # Пытаемся отправить с фото
                        await bot.send_photo(
                            chat_id=to_user_id,
                            photo=from_user_profile['photo_file_id'],
                            caption=like_message,
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        logger.info(f"Like notification with photo sent from {from_user_id} to {to_user_id}")
                    except Exception as photo_error:
                        # Если не удалось отправить фото, отправляем текстом
                        logger.warning(f"Failed to send photo in like notification to user {to_user_id}, sending text: {photo_error}")
                        await send_message(to_user_id, like_message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                        logger.info(f"Like notification (text) sent from {from_user_id} to {to_user_id}")
                else:
                    await send_message(to_user_id, like_message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                    logger.info(f"Like notification sent from {from_user_id} to {to_user_id}")
            except Exception as e:
                logger.error(f"CRITICAL: Failed to send like notification from {from_user_id} to {to_user_id}: {e}")
                logger.error(traceback.format_exc())
    
    # Показываем следующую анкету
    await show_next_dating_profile(from_user_id, query)

# Регистрация обработчиков
# Регистрация обработчиков команд
telegram_app.add_handler(CommandHandler('start', handle_start))
telegram_app.add_handler(CommandHandler('admin', handle_admin_command))
telegram_app.add_handler(CommandHandler('promoter', handle_promoter_command))
telegram_app.add_handler(CommandHandler('setadmin', handle_setadmin_command))

# Регистрация обработчиков callback
telegram_app.add_handler(CallbackQueryHandler(handle_callback))

# Регистрация обработчиков сообщений (важно: порядок имеет значение!)
# Сначала текстовые сообщения
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
# Затем медиа файлы
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
telegram_app.add_handler(MessageHandler(filters.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.VOICE, handle_voice))
# Для документов используем правильный фильтр (для версии 20+ используем filters.Document.ALL)
try:
    # В python-telegram-bot 20+ используется filters.Document.ALL
    telegram_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    logger.info("Document handler registered with filters.Document.ALL")
except AttributeError:
    # Если Document.ALL недоступен, пробуем альтернативные варианты
    try:
        # Для старых версий может быть filters.DOCUMENT
        telegram_app.add_handler(MessageHandler(filters.DOCUMENT, handle_document))
        logger.info("Document handler registered with filters.DOCUMENT")
    except AttributeError:
        logger.warning("Document filter not available, documents will be handled in handle_message")
except Exception as e:
    logger.error(f"Error setting up document handler: {e}")
    # Продолжаем без обработчика документов - документы будут обрабатываться в handle_message

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Webhook endpoint для Telegram"""
    if request.method == 'POST':
        try:
            import asyncio
            global _telegram_app_initialized
            
            async def process_update_async():
                """Обработка обновления с инициализацией"""
                global _telegram_app_initialized
                
                try:
                    # Инициализируем приложение, если еще не инициализировано
                    if not _telegram_app_initialized:
                        await telegram_app.initialize()
                        _telegram_app_initialized = True
                        logger.info("Telegram Application initialized")
                    
                    # Получаем обновление
                    update_dict = request.get_json(force=True)
                    logger.info(f"Received update type: {update_dict.get('message', {}).get('text', 'callback' if 'callback_query' in update_dict else 'unknown')}")
                    logger.debug(f"Full update: {update_dict}")
                    update = Update.de_json(update_dict, telegram_app.bot)
                    
                    # Логируем команды
                    if update.message and update.message.text:
                        logger.info(f"Message from {update.message.from_user.id}: {update.message.text}")
                    if update.callback_query:
                        logger.info(f"Callback from {update.callback_query.from_user.id}: {update.callback_query.data}")
                    
                    # Обрабатываем обновление
                    await telegram_app.process_update(update)
                    logger.info("Update processed successfully")
                except Exception as e:
                    logger.error(f"Error in process_update_async: {e}", exc_info=True)
                    # Также пишем в wsgi_error.log для надежности
                    try:
                        error_log = os.path.join(os.path.dirname(__file__), 'wsgi_error.log')
                        with open(error_log, 'a', encoding='utf-8') as f:
                            from datetime import datetime
                            f.write(f"\n=== Bot Error at {datetime.now()} ===\n")
                            f.write(f"Error: {str(e)}\n")
                            f.write(f"Traceback:\n{traceback.format_exc()}\n\n")
                    except:
                        pass
                    raise
            
            # Запускаем обработку
            asyncio.run(process_update_async())
            
            return jsonify({'ok': True})
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return jsonify({'ok': False, 'error': str(e)}), 500
    else:
        # GET запрос для проверки работы
        return jsonify({'ok': True, 'status': 'webhook endpoint is working'})

@app.route('/robokassa', methods=['POST', 'GET'])
def robokassa_callback():
    """Старый endpoint Robokassa (отключен)"""
    return jsonify({
        'ok': False,
        'message': 'Robokassa flow disabled. Manual card transfer flow is active.'
    }), 410

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установить webhook"""
    import asyncio
    webhook_url = f"{config.BASE_URL}/webhook"
    
    async def _set_webhook():
        result = await bot.set_webhook(webhook_url)
        return result
    
    result = asyncio.run(_set_webhook())
    return jsonify({'ok': result, 'url': webhook_url})

# Для WSGI на виртуальном хостинге
application = app

if __name__ == '__main__':
    import asyncio
    
    # Устанавливаем webhook при запуске
    async def setup_webhook():
        webhook_url = f"{config.BASE_URL}/webhook"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    
    asyncio.run(setup_webhook())
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=config.FLASK_PORT, debug=False)

