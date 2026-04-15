# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных MySQL
"""

import mysql.connector
from mysql.connector import Error, pooling
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import logging
import random
import string
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# Пул соединений
connection_pool = None

def init_db_pool():
    """Инициализация пула соединений с БД"""
    global connection_pool
    try:
        # Убеждаемся, что используется utf8mb4 для поддержки эмодзи
        db_config = DB_CONFIG.copy()
        if 'charset' not in db_config or db_config['charset'] != 'utf8mb4':
            db_config['charset'] = 'utf8mb4'
            db_config['use_unicode'] = True
        
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="kissparty_pool",
            pool_size=5,
            pool_reset_session=True,
            **db_config
        )
        logger.info("Database connection pool created successfully with utf8mb4 charset")
    except Error as e:
        logger.error(f"Error creating connection pool: {e}")
        raise

@contextmanager
def get_db_connection():
    """Контекстный менеджер для получения соединения с БД"""
    global connection_pool
    if connection_pool is None:
        init_db_pool()
    
    conn = None
    try:
        conn = connection_pool.get_connection()
        # Устанавливаем кодировку для поддержки эмодзи
        try:
            conn.cmd_query("SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'")
            conn.cmd_query("SET CHARACTER SET utf8mb4")
        except:
            pass
        yield conn
    except Error as e:
        logger.error(f"Error getting database connection: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()

def execute_query(query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Выполняет SQL запрос"""
    with get_db_connection() as conn:
        # Убеждаемся, что соединение использует правильную кодировку
        try:
            conn.set_charset_collation('utf8mb4', 'utf8mb4_unicode_ci')
        except:
            pass
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            if fetch:
                result = cursor.fetchall()
                # Убеждаемся, что строковые значения правильно декодированы
                if result:
                    for row in result:
                        for key, value in row.items():
                            if isinstance(value, bytes):
                                try:
                                    row[key] = value.decode('utf-8')
                                except:
                                    row[key] = value.decode('utf-8', errors='ignore')
                return result
            conn.commit()
            return None
        except Error as e:
            logger.error(f"Error executing query: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

def execute_many(query: str, params_list: List[tuple]) -> None:
    """Выполняет массовую вставку"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
        except Error as e:
            logger.error(f"Error executing many: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

# Функции для работы с пользователями
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить пользователя по ID"""
    # Используем COALESCE для обработки NULL значений promoter_active (если поле еще не добавлено)
    query = """SELECT *, COALESCE(promoter_active, 0) as promoter_active 
               FROM users WHERE user_id = %s"""
    result = execute_query(query, (user_id,), fetch=True)
    return result[0] if result else None

def create_user(user_id: int, username: str = None, first_name: str = None, 
                last_name: str = None, role: str = None, promo_code: str = None) -> None:
    """Создать или обновить пользователя
    
    Важно: 
    - Если role=None, при обновлении существующего пользователя роль сохраняется.
    - Если promo_code=None, при обновлении существующего пользователя promo_code сохраняется.
    Если role или promo_code указаны явно, они будут обновлены.
    """
    # Проверяем, существует ли пользователь
    existing_user = get_user(user_id)
    
    # Сохраняем оригинальное значение promo_code для проверки (до того, как мы его изменим)
    original_promo_code = promo_code
    
    # Если пользователь существует и роль не указана явно - сохраняем текущую роль
    if existing_user and role is None:
        role = existing_user.get('role', 'user')
        logger.info(f"Preserving existing role '{role}' for user {user_id} (user already exists)")
    elif role is None:
        # Для нового пользователя используем роль по умолчанию
        role = 'user'
        logger.info(f"Creating new user {user_id} with default role 'user'")
    else:
        logger.info(f"Updating user {user_id} with explicit role '{role}'")
    
    # Если пользователь существует и promo_code не указан явно - сохраняем текущий promo_code
    if existing_user and original_promo_code is None:
        promo_code = existing_user.get('promo_code')
        logger.info(f"Preserving existing promo_code '{promo_code}' for user {user_id} (user already exists, promo_code not provided)")
    elif original_promo_code is None:
        # Для нового пользователя promo_code остается NULL
        promo_code = None
        logger.info(f"Creating new user {user_id} without promo_code")
    else:
        logger.info(f"Updating user {user_id} with explicit promo_code '{promo_code}'")
    
    # Формируем запрос - всегда используем VALUES для promo_code
    # Если original_promo_code был None и пользователь существует, мы уже установили promo_code = existing_user.get('promo_code'),
    # так что существующий промокод сохранится
    query = """INSERT INTO users (user_id, username, first_name, last_name, role, promo_code)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE 
               username=VALUES(username), 
               first_name=VALUES(first_name),
               last_name=VALUES(last_name), 
               role=VALUES(role), 
               promo_code=VALUES(promo_code)"""
    logger.debug(f"Executing create_user query for user {user_id} with role '{role}' and promo_code '{promo_code}'")
    execute_query(query, (user_id, username, first_name, last_name, role, promo_code))
    
    # Проверяем результат
    verify_user = get_user(user_id)
    if verify_user:
        actual_role = verify_user.get('role')
        logger.info(f"User {user_id} role after create_user: '{actual_role}'")
        if existing_user and existing_user.get('role') != actual_role and role is None:
            logger.warning(f"Role changed unexpectedly for user {user_id}: was '{existing_user.get('role')}', now '{actual_role}'")

def update_user_role(user_id: int, role: str) -> None:
    """Обновить роль пользователя"""
    query = "UPDATE users SET role = %s WHERE user_id = %s"
    logger.info(f"Updating user role: user_id={user_id}, role={role}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (role, user_id))
            affected_rows = cursor.rowcount
            logger.info(f"UPDATE executed. Affected rows: {affected_rows}")
            
            # Проверяем, что роль действительно обновилась ПЕРЕД commit
            verify_query = "SELECT role FROM users WHERE user_id = %s"
            cursor.execute(verify_query, (user_id,))
            result = cursor.fetchone()
            
            if result:
                actual_role = result['role']
                logger.info(f"Verification before commit: user {user_id} has role '{actual_role}'")
                
                # Делаем commit
                conn.commit()
                logger.info(f"Commit successful. Role updated to '{actual_role}'")
                
                # Проверяем еще раз после commit
                cursor.execute(verify_query, (user_id,))
                result_after = cursor.fetchone()
                if result_after:
                    logger.info(f"Verification after commit: user {user_id} has role '{result_after['role']}'")
                    if result_after['role'] != role:
                        logger.error(f"Role mismatch! Expected '{role}', got '{result_after['role']}'")
            else:
                logger.warning(f"Verification failed: user {user_id} not found in database")
                conn.rollback()
                raise ValueError(f"User {user_id} not found in database")
            
            cursor.close()
    except Exception as e:
        logger.error(f"Error updating user role: {e}", exc_info=True)
        raise

def ensure_promoter_own_code(user_id: int) -> Optional[str]:
    """
    Убедиться, что у промоутера свой уникальный промокод.
    Если у пользователя роль promoter, но promo_code чужой (пригласившего) или пустой —
    генерирует и сохраняет новый уникальный код.
    Возвращает текущий или новый промокод промоутера, иначе None.
    """
    user = get_user(user_id)
    if not user or user.get('role') != 'promoter':
        return None
    current_code = user.get('promo_code')
    # Проверяем: есть ли другой пользователь (не мы) с таким же promo_code и ролью promoter
    if current_code:
        other = execute_query(
            "SELECT user_id FROM users WHERE promo_code = %s AND role = 'promoter' AND user_id != %s LIMIT 1",
            (current_code, user_id), fetch=True
        )
        if not other:
            return current_code  # наш код, ничего не меняем
    # Нужен новый уникальный код
    for _ in range(50):
        new_code = 'PROMO' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        exists = execute_query(
            "SELECT user_id FROM users WHERE promo_code = %s LIMIT 1",
            (new_code,), fetch=True
        )
        if not exists:
            execute_query("UPDATE users SET promo_code = %s WHERE user_id = %s", (new_code, user_id))
            logger.info(f"Assigned own promo code {new_code} to promoter {user_id}")
            return new_code
    logger.error(f"Could not generate unique promo code for promoter {user_id}")
    return None

# Функции для работы с бонусами
def get_user_bonuses(user_id: int) -> float:
    """Получить баланс бонусов пользователя"""
    query = "SELECT bonus_balance FROM bonuses WHERE user_id = %s"
    result = execute_query(query, (user_id,), fetch=True)
    if result:
        return float(result[0]['bonus_balance'])
    # Создаем запись если нет
    query = "INSERT INTO bonuses (user_id, bonus_balance) VALUES (%s, 0)"
    execute_query(query, (user_id,))
    return 0.0

def update_user_bonuses(user_id: int, bonus_amount: float, operation: str, order_id: str = None) -> float:
    """Обновить бонусы пользователя"""
    current_balance = get_user_bonuses(user_id)
    
    if operation == 'add':
        new_balance = current_balance + bonus_amount
    elif operation == 'subtract':
        new_balance = max(0, current_balance - bonus_amount)
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    query = """INSERT INTO bonuses (user_id, bonus_balance, last_order_id)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE bonus_balance=VALUES(bonus_balance), 
               last_order_id=VALUES(last_order_id), last_updated=NOW()"""
    execute_query(query, (user_id, new_balance, order_id))
    
    # Логируем операцию
    log_query = """INSERT INTO bonus_logs (user_id, operation, bonus_amount, old_balance, new_balance, order_id)
                   VALUES (%s, %s, %s, %s, %s, %s)"""
    execute_query(log_query, (user_id, operation, bonus_amount, current_balance, new_balance, order_id))
    
    return new_balance

# Функции для работы с рефералами
def get_referral_data(user_id: int) -> Dict[str, Any]:
    """Получить данные реферала"""
    query = "SELECT * FROM referrals WHERE user_id = %s"
    result = execute_query(query, (user_id,), fetch=True)
    if result:
        return result[0]
    return {
        'referral_code': '',
        'referrer_id': None,
        'referrals_count': 0,
        'referral_earnings': 0.0,
        'referral_bonus_paid': False,
        'first_purchase_discount_applied': False
    }

def create_referral(user_id: int, referral_code: str, referrer_id: int = None) -> None:
    """Создать реферальную запись"""
    query = """INSERT INTO referrals (user_id, referral_code, referrer_id)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE referral_code=VALUES(referral_code), referrer_id=VALUES(referrer_id)"""
    execute_query(query, (user_id, referral_code, referrer_id))

def update_referral_stats(user_id: int, **kwargs) -> None:
    """Обновить статистику реферала"""
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key}=%s")
        values.append(value)
    values.append(user_id)
    
    query = f"UPDATE referrals SET {', '.join(updates)} WHERE user_id = %s"
    execute_query(query, tuple(values))

# Функции для работы с промокодами
def get_promocode(code: str) -> Optional[Dict[str, Any]]:
    """Получить промокод"""
    query = "SELECT * FROM promocodes WHERE code = %s AND active = 1"
    result = execute_query(query, (code.upper(),), fetch=True)
    return result[0] if result else None

def increment_promocode_usage(code: str) -> None:
    """Увеличить счетчик использования промокода"""
    query = "UPDATE promocodes SET used_count = used_count + 1 WHERE code = %s"
    execute_query(query, (code.upper(),))

# Функции для работы с билетами
def create_ticket(ticket_data: Dict[str, Any]) -> int:
    """Создать билет"""
    query = """INSERT INTO tickets (ticket_code, user_id, ticket_type, amount, bonus_used, 
               bonus_earned, referral_bonus_earned, promo_code, order_id, qr_file_id, wants_to_meet, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    params = (
        ticket_data['ticket_code'],
        ticket_data['user_id'],
        ticket_data['ticket_type'],
        ticket_data['amount'],
        ticket_data.get('bonus_used', 0),
        ticket_data.get('bonus_earned', 0),
        ticket_data.get('referral_bonus_earned', 0),
        ticket_data.get('promo_code'),
        ticket_data['order_id'],
        ticket_data.get('qr_file_id'),
        ticket_data.get('wants_to_meet', 'no'),
        ticket_data.get('status', 'active')
    )
    execute_query(query, params)
    return 1

def get_ticket_by_code(ticket_code: str) -> Optional[Dict[str, Any]]:
    """Получить билет по коду"""
    query = "SELECT * FROM tickets WHERE ticket_code = %s"
    result = execute_query(query, (ticket_code,), fetch=True)
    return result[0] if result else None

def count_tickets_by_type(ticket_type: str) -> int:
    """Подсчитать количество проданных билетов по типу"""
    query = "SELECT COUNT(*) as count FROM tickets WHERE ticket_type = %s AND status = 'active'"
    result = execute_query(query, (ticket_type,), fetch=True)
    return int(result[0]['count']) if result else 0

# Функции для работы с ценами
def get_prices() -> Dict[str, Dict[str, float]]:
    """Получить настройки цен (использует категории из БД, fallback на старую таблицу)"""
    # Сначала пытаемся получить из категорий
    try:
        categories = get_all_ticket_categories(active_only=True)
        prices = {}
        
        if categories:
            for cat in categories:
                prices[cat['code']] = {
                    'base': float(cat['base_price']),
                    'discounted': float(cat['discounted_price'])
                }
        
        # Если категорий нет, используем старую таблицу
        if not prices:
            query = "SELECT ticket_type, base_price, discounted_price FROM price_settings"
            result = execute_query(query, fetch=True)
            for row in result:
                prices[row['ticket_type']] = {
                    'base': float(row['base_price']),
                    'discounted': float(row['discounted_price'])
                }
        
        return prices
    except Exception as e:
        logger.error(f"Error getting prices: {e}")
        # Fallback на старую таблицу
        query = "SELECT ticket_type, base_price, discounted_price FROM price_settings"
        result = execute_query(query, fetch=True)
        prices = {}
        for row in result:
            prices[row['ticket_type']] = {
                'base': float(row['base_price']),
                'discounted': float(row['discounted_price'])
            }
        return prices

# Функции для работы с состояниями пользователей
def get_user_state(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить состояние пользователя"""
    query = "SELECT * FROM user_states WHERE user_id = %s"
    result = execute_query(query, (user_id,), fetch=True)
    return result[0] if result else None

def set_user_state(user_id: int, state: str, data: Dict[str, Any] = None) -> None:
    """Установить состояние пользователя"""
    import json
    data_json = json.dumps(data) if data else None
    query = """INSERT INTO user_states (user_id, state, data)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE state=VALUES(state), data=VALUES(data), updated_at=NOW()"""
    execute_query(query, (user_id, state, data_json))

def clear_user_state(user_id: int) -> None:
    """Очистить состояние пользователя"""
    query = "DELETE FROM user_states WHERE user_id = %s"
    execute_query(query, (user_id,))

# Функции для ручных заявок на оплату
def ensure_payment_requests_table() -> None:
    """Гарантирует наличие таблицы заявок на ручную оплату."""
    query = """CREATE TABLE IF NOT EXISTS payment_requests (
               id INT NOT NULL AUTO_INCREMENT,
               order_id VARCHAR(64) NOT NULL,
               user_id BIGINT NOT NULL,
               ticket_type VARCHAR(64) NOT NULL,
               quantity INT NOT NULL DEFAULT 1,
               total_price DECIMAL(10,2) NOT NULL,
               promo_code VARCHAR(50) DEFAULT NULL,
               bonus_used DECIMAL(10,2) NOT NULL DEFAULT 0.00,
               status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
               payload LONGTEXT DEFAULT NULL,
               admin_id BIGINT DEFAULT NULL,
               admin_comment TEXT DEFAULT NULL,
               created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
               updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
               PRIMARY KEY (id),
               UNIQUE KEY order_id (order_id),
               KEY user_id (user_id),
               KEY status (status)
               ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
    execute_query(query)

def create_payment_request(order_id: str, user_id: int, ticket_type: str, quantity: int,
                           total_price: float, promo_code: str = None, bonus_used: float = 0.0,
                           payload: str = None) -> None:
    """Создать заявку на ручную оплату"""
    ensure_payment_requests_table()
    query = """INSERT INTO payment_requests
               (order_id, user_id, ticket_type, quantity, total_price, promo_code, bonus_used, status, payload)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)
               ON DUPLICATE KEY UPDATE
               ticket_type=VALUES(ticket_type),
               quantity=VALUES(quantity),
               total_price=VALUES(total_price),
               promo_code=VALUES(promo_code),
               bonus_used=VALUES(bonus_used),
               payload=VALUES(payload),
               status='pending'"""
    execute_query(query, (order_id, user_id, ticket_type, quantity, total_price, promo_code, bonus_used, payload))

def get_payment_request_by_order(order_id: str) -> Optional[Dict[str, Any]]:
    """Получить заявку по order_id"""
    ensure_payment_requests_table()
    query = "SELECT * FROM payment_requests WHERE order_id = %s LIMIT 1"
    result = execute_query(query, (order_id,), fetch=True)
    return result[0] if result else None

def get_payment_request(request_id: int) -> Optional[Dict[str, Any]]:
    """Получить заявку по ID"""
    ensure_payment_requests_table()
    query = "SELECT * FROM payment_requests WHERE id = %s LIMIT 1"
    result = execute_query(query, (request_id,), fetch=True)
    return result[0] if result else None

def update_payment_request_status(request_id: int, status: str, admin_id: int = None,
                                  admin_comment: str = None) -> None:
    """Обновить статус заявки на оплату"""
    ensure_payment_requests_table()
    query = """UPDATE payment_requests
               SET status = %s, admin_id = %s, admin_comment = %s
               WHERE id = %s"""
    execute_query(query, (status, admin_id, admin_comment, request_id))

# Функции для работы с настройками бота
def get_bot_setting(key: str, default: str = None) -> Optional[str]:
    """Получить настройку бота"""
    query = "SELECT setting_value FROM bot_settings WHERE setting_key = %s"
    result = execute_query(query, (key,), fetch=True)
    if result and result[0]['setting_value']:
        value = result[0]['setting_value']
        # Убеждаемся, что значение правильно декодировано
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8')
            except UnicodeDecodeError:
                # Пробуем другие кодировки
                try:
                    value = value.decode('utf-8', errors='replace')
                except:
                    value = value.decode('latin-1', errors='replace')
        elif isinstance(value, str):
            # Уже строка, проверяем что она корректная UTF-8
            try:
                # Пробуем перекодировать для проверки
                value.encode('utf-8')
            except UnicodeEncodeError:
                # Если есть проблемы, пробуем исправить
                try:
                    value = value.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
                except:
                    pass
        return value
    return default

def set_bot_setting(key: str, value: str) -> None:
    """Установить настройку бота"""
    # Убеждаемся, что значение правильно закодировано
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    elif not isinstance(value, str):
        value = str(value)
    
    # Убеждаемся, что значение в UTF-8
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        # Если есть проблемы с кодировкой, пробуем исправить
        value = value.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
    
    query = """INSERT INTO bot_settings (setting_key, setting_value)
               VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_at=NOW()"""
    execute_query(query, (key, value))

def is_bot_access_enabled() -> bool:
    """Проверить, открыт ли доступ к боту"""
    value = get_bot_setting('bot_access_enabled', '1')
    return value == '1' or value == 1

def is_sales_enabled() -> bool:
    """Проверить, открыты ли продажи билетов"""
    value = get_bot_setting('sales_enabled', '1')
    return value == '1' or value == 1

def is_bonuses_promocodes_enabled() -> bool:
    """Проверить, разрешена ли оплата бонусами и промокодами"""
    value = get_bot_setting('bonuses_promocodes_enabled', '1')
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    normalized = str(value).strip().lower()
    return normalized in ('1', 'true', 'yes', 'on')

def get_main_menu_text() -> str:
    """Получить текст главного меню"""
    default_text = """🎉 <b>Добро пожаловать в KISS PARTY!</b>

🎪 Мы рады приветствовать вас на нашем мероприятии!

Выберите действие:"""
    try:
        text = get_bot_setting('main_menu_text', default_text)
        if text and isinstance(text, str):
            return text
        return default_text
    except Exception as e:
        logger.error(f"Error getting main menu text: {e}")
        return default_text

def get_main_menu_image() -> Optional[str]:
    """Получить изображение главного меню (file_id)"""
    try:
        image = get_bot_setting('main_menu_image', None)
        if image and isinstance(image, str) and image.strip():
            return image
        return None
    except Exception as e:
        logger.error(f"Error getting main menu image: {e}")
        return None

# Функции для статистики
def get_bot_statistics() -> Dict[str, Any]:
    """Получить статистику бота"""
    stats = {}
    
    # Общее количество пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = execute_query(query, fetch=True)
    stats['total_users'] = int(result[0]['count']) if result else 0
    
    # Количество активных пользователей (за последние 30 дней)
    query = "SELECT COUNT(DISTINCT user_id) as count FROM tickets WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
    result = execute_query(query, fetch=True)
    stats['active_users_30d'] = int(result[0]['count']) if result else 0
    
    # Общее количество билетов (включая использованные)
    query = "SELECT COUNT(*) as count FROM tickets"
    result = execute_query(query, fetch=True)
    stats['total_tickets'] = int(result[0]['count']) if result else 0
    
    # Количество активных билетов
    query = "SELECT COUNT(*) as count FROM tickets WHERE status = 'active'"
    result = execute_query(query, fetch=True)
    stats['active_tickets'] = int(result[0]['count']) if result else 0
    
    # Количество использованных билетов
    query = "SELECT COUNT(*) as count FROM tickets WHERE status = 'used'"
    result = execute_query(query, fetch=True)
    stats['used_tickets'] = int(result[0]['count']) if result else 0
    
    # Общая сумма продаж (все билеты, включая использованные)
    query = "SELECT SUM(amount) as total FROM tickets"
    result = execute_query(query, fetch=True)
    stats['total_revenue'] = float(result[0]['total']) if result and result[0]['total'] else 0.0
    
    # Билеты по типам (все, включая использованные)
    stats['tickets_by_type'] = {}
    for ticket_type in ['regular', 'vip', 'vip_standing', 'couple']:
        query = "SELECT COUNT(*) as count FROM tickets WHERE ticket_type = %s"
        result = execute_query(query, (ticket_type,), fetch=True)
        stats['tickets_by_type'][ticket_type] = int(result[0]['count']) if result else 0
    
    # Общий баланс бонусов
    query = "SELECT SUM(bonus_balance) as total FROM bonuses"
    result = execute_query(query, fetch=True)
    stats['total_bonuses'] = float(result[0]['total']) if result and result[0]['total'] else 0.0
    
    # Количество рефералов
    query = "SELECT COUNT(*) as count FROM referrals WHERE referrals_count > 0"
    result = execute_query(query, fetch=True)
    stats['total_referrers'] = int(result[0]['count']) if result else 0
    
    # Активные промокоды
    query = "SELECT COUNT(*) as count FROM promocodes WHERE active = 1"
    result = execute_query(query, fetch=True)
    stats['active_promocodes'] = int(result[0]['count']) if result else 0
    
    return stats

def get_extended_statistics() -> Dict[str, Any]:
    """Получить расширенную статистику"""
    try:
        stats = get_bot_statistics()
        
        # Продажи по дням (последние 30 дней)
        query = """SELECT DATE(created_at) as date, COUNT(*) as count, COALESCE(SUM(amount), 0) as revenue
                   FROM tickets 
                   WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) AND status = 'active'
                   GROUP BY DATE(created_at)
                   ORDER BY date DESC"""
        result = execute_query(query, fetch=True)
        stats['sales_by_day'] = result if result else []
        
        # Топ пользователей по покупкам
        query = """SELECT u.user_id, u.first_name, u.username, COUNT(t.id) as tickets_count, COALESCE(SUM(t.amount), 0) as total_spent
                   FROM users u
                   LEFT JOIN tickets t ON u.user_id = t.user_id AND t.status = 'active'
                   GROUP BY u.user_id
                   ORDER BY total_spent DESC
                   LIMIT 10"""
        result = execute_query(query, fetch=True)
        stats['top_users'] = result if result else []
    except Exception as e:
        logger.error(f"Error in get_extended_statistics: {e}")
        stats = {
            'sales_by_day': [],
            'top_users': []
        }
    
    # Статистика по промокодам
    query = """SELECT code, name, used_count, max_uses, 
               CASE WHEN max_uses > 0 THEN (used_count * 100.0 / max_uses) ELSE 0 END as usage_percent
               FROM promocodes
               WHERE active = 1
               ORDER BY used_count DESC
               LIMIT 10"""
    result = execute_query(query, fetch=True)
    stats['promocodes_stats'] = result if result else []
    
    return stats

# Функции для работы с промоутерами
def get_promoter_code(user_id: int) -> Optional[str]:
    """Получить код промоутера пользователя"""
    user = get_user(user_id)
    return user.get('promo_code') if user else None

def get_promoter_statistics(user_id: int) -> Dict[str, Any]:
    """Получить статистику промоутера.
    - Приглашённые: по users.promo_code (кто перешёл по ссылке и имеет этот промокод).
    - Покупки/выручка: по tickets.promo_code (чтобы не терять продажи при смене роли у покупателя).
    """
    promo_code = get_promoter_code(user_id)
    if not promo_code:
        return {}
    
    # Приглашённые = пользователи, у которых в профиле записан этот промокод (перешли по ссылке)
    query = """SELECT COUNT(*) as count FROM users 
               WHERE promo_code = %s AND (role IS NULL OR role != 'promoter')"""
    result = execute_query(query, (promo_code,), fetch=True)
    invited_count = int(result[0]['count']) if result else 0
    
    # Покупки и выручка — по билетам (не по users), чтобы не терять при смене промокода у покупателя
    query = """SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as revenue
               FROM tickets WHERE promo_code = %s AND status = 'active'"""
    result = execute_query(query, (promo_code,), fetch=True)
    purchases_count = int(result[0]['count']) if result else 0
    revenue = float(result[0]['revenue']) if result and result[0]['revenue'] is not None else 0.0
    
    # Использованные билеты (пройденные на входе)
    query = """SELECT COUNT(*) as count FROM tickets WHERE promo_code = %s AND status = 'used'"""
    result = execute_query(query, (promo_code,), fetch=True)
    used_tickets = int(result[0]['count']) if result else 0
    
    return {
        'promo_code': promo_code,
        'invited_users': invited_count,
        'purchases_count': purchases_count,
        'revenue': revenue,
        'used_tickets': used_tickets
    }

def get_all_promoters() -> List[Dict[str, Any]]:
    """Получить список всех промоутеров"""
    try:
        # Используем COALESCE для обработки NULL значений promoter_active
        query = """SELECT user_id, username, first_name, last_name, promo_code, created_at,
                          COALESCE(promoter_active, 0) as promoter_active
                   FROM users 
                   WHERE role = 'promoter' AND promo_code IS NOT NULL
                   ORDER BY promoter_active DESC, created_at DESC"""
        result = execute_query(query, fetch=True)
        return result if result else []
    except Exception as e:
        logger.error(f"Error in get_all_promoters: {e}")
        return []

def set_promoter_active(user_id: int, active: bool) -> bool:
    """Установить статус активности промоутера"""
    try:
        # Проверяем, что пользователь является промоутером
        user = get_user(user_id)
        if not user or user.get('role') != 'promoter':
            return False
        
        # Пытаемся обновить статус активности
        # Если поле не существует, MySQL выдаст ошибку, но мы обработаем её
        try:
            query = """UPDATE users SET promoter_active = %s WHERE user_id = %s"""
            execute_query(query, (1 if active else 0, user_id))
        except Exception as e:
            # Если поле не существует, пытаемся его добавить
            if 'promoter_active' in str(e).lower() or 'unknown column' in str(e).lower():
                logger.info(f"Field promoter_active doesn't exist, trying to add it")
                try:
                    # Добавляем поле
                    alter_query = """ALTER TABLE users 
                                    ADD COLUMN promoter_active TINYINT(1) DEFAULT 0 
                                    COMMENT 'Статус активности промоутера'"""
                    execute_query(alter_query)
                    # Теперь обновляем статус
                    query = """UPDATE users SET promoter_active = %s WHERE user_id = %s"""
                    execute_query(query, (1 if active else 0, user_id))
                except Exception as alter_error:
                    logger.error(f"Error adding promoter_active field: {alter_error}", exc_info=True)
                    return False
            else:
                raise
        
        return True
    except Exception as e:
        logger.error(f"Error setting promoter active status: {e}", exc_info=True)
        return False

def is_promoter_active(user_id: int) -> bool:
    """Проверить, активен ли промоутер"""
    user = get_user(user_id)
    if not user or user.get('role') != 'promoter':
        return False
    # Проверяем поле promoter_active, если его нет - возвращаем False
    promoter_active = user.get('promoter_active')
    return bool(promoter_active) if promoter_active is not None else False

def get_promoter_detailed_stats(user_id: int) -> Dict[str, Any]:
    """Получить детальную статистику промоутера для админ-панели"""
    user = get_user(user_id)
    if not user or user.get('role') != 'promoter':
        return {}
    
    promo_code = user.get('promo_code')
    if not promo_code:
        return {}
    
    stats = get_promoter_statistics(user_id)
    
    # Дополнительная статистика: последние покупки (по promo_code в билете)
    query = """SELECT t.id, t.user_id, t.amount, t.created_at, u.username, u.first_name
               FROM tickets t
               LEFT JOIN users u ON t.user_id = u.user_id
               WHERE t.promo_code = %s
               ORDER BY t.created_at DESC
               LIMIT 10"""
    result = execute_query(query, (promo_code,), fetch=True)
    recent_purchases = result if result else []
    
    # Статистика по типам билетов
    query = """SELECT t.ticket_type, COUNT(*) as count, COALESCE(SUM(t.amount), 0) as revenue
               FROM tickets t
               WHERE t.promo_code = %s AND t.status = 'active'
               GROUP BY t.ticket_type"""
    result = execute_query(query, (promo_code,), fetch=True)
    tickets_by_type = {row['ticket_type']: {'count': row['count'], 'revenue': row['revenue']} 
                       for row in result} if result else {}
    
    # Дата первой покупки
    query = """SELECT MIN(created_at) as first_purchase FROM tickets WHERE promo_code = %s"""
    result = execute_query(query, (promo_code,), fetch=True)
    first_purchase = result[0]['first_purchase'] if result and result[0]['first_purchase'] else None
    
    # Дата последней покупки
    query = """SELECT MAX(created_at) as last_purchase FROM tickets WHERE promo_code = %s"""
    result = execute_query(query, (promo_code,), fetch=True)
    last_purchase = result[0]['last_purchase'] if result and result[0]['last_purchase'] else None
    
    stats.update({
        'user_id': user_id,
        'username': user.get('username'),
        'first_name': user.get('first_name'),
        'last_name': user.get('last_name'),
        'created_at': user.get('created_at'),
        'recent_purchases': recent_purchases,
        'tickets_by_type': tickets_by_type,
        'first_purchase': first_purchase,
        'last_purchase': last_purchase
    })
    
    return stats

# Функции для работы с промокодами (расширенные)
def get_all_promocodes(active_only: bool = False) -> List[Dict[str, Any]]:
    """Получить все промокоды"""
    if active_only:
        query = "SELECT * FROM promocodes WHERE active = 1 ORDER BY created_at DESC"
    else:
        query = "SELECT * FROM promocodes ORDER BY created_at DESC"
    return execute_query(query, fetch=True) or []

def create_promocode(code: str, name: str, type: str, value: float, 
                    ticket_types: List[str] = None, start_date: str = None,
                    end_date: str = None, max_uses: int = 0, min_amount: float = 0.0,
                    notes: str = None) -> None:
    """Создать промокод"""
    import json
    ticket_types_json = json.dumps(ticket_types) if ticket_types else None
    query = """INSERT INTO promocodes (code, name, type, value, ticket_types, start_date, 
               end_date, max_uses, min_amount, notes, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)"""
    execute_query(query, (code.upper(), name, type, value, ticket_types_json, 
                          start_date, end_date, max_uses, min_amount, notes))

def update_promocode(code: str, **kwargs) -> None:
    """Обновить промокод"""
    updates = []
    values = []
    for key, value in kwargs.items():
        if key == 'ticket_types' and isinstance(value, list):
            import json
            value = json.dumps(value)
        updates.append(f"{key}=%s")
        values.append(value)
    values.append(code.upper())
    
    query = f"UPDATE promocodes SET {', '.join(updates)} WHERE code = %s"
    execute_query(query, tuple(values))

def delete_promocode(code: str) -> None:
    """Удалить промокод (деактивировать)"""
    query = "UPDATE promocodes SET active = 0 WHERE code = %s"
    execute_query(query, (code.upper(),))

# ============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОХОДКАМИ (GUEST PASSES)
# ============================================

def create_guest_pass(code: str, ticket_type: str, quantity: int, 
                      is_unlimited: bool = False, expires_at: str = None,
                      created_by: int = None, notes: str = None) -> None:
    """Создать проходку"""
    query = """INSERT INTO guest_passes (code, ticket_type, quantity, is_unlimited, 
               expires_at, created_by, notes, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)"""
    execute_query(query, (code.upper(), ticket_type, quantity, 
                         1 if is_unlimited else 0, expires_at, created_by, notes))

def get_guest_pass(code: str) -> Optional[Dict[str, Any]]:
    """Получить проходку по коду"""
    query = """SELECT * FROM guest_passes WHERE code = %s AND active = 1"""
    result = execute_query(query, (code.upper(),), fetch=True)
    return result[0] if result else None

def get_all_guest_passes(active_only: bool = False) -> List[Dict[str, Any]]:
    """Получить все проходки"""
    if active_only:
        query = """SELECT * FROM guest_passes WHERE active = 1 
                  ORDER BY created_at DESC"""
    else:
        query = """SELECT * FROM guest_passes ORDER BY created_at DESC"""
    return execute_query(query, fetch=True) or []

def use_guest_pass(code: str, user_id: int, ticket_id: int = None) -> bool:
    """Использовать проходку"""
    pass_data = get_guest_pass(code)
    if not pass_data:
        return False
    
    # Проверяем срок действия
    if not pass_data['is_unlimited']:
        if pass_data['expires_at']:
            from datetime import datetime
            expires = datetime.strptime(pass_data['expires_at'], '%Y-%m-%d').date()
            if datetime.now().date() > expires:
                return False
    
    # Проверяем количество
    if pass_data['used_count'] >= pass_data['quantity']:
        return False
    
    # Увеличиваем счетчик использований
    query = "UPDATE guest_passes SET used_count = used_count + 1 WHERE id = %s"
    execute_query(query, (pass_data['id'],))
    
    # Записываем использование
    query = """INSERT INTO guest_pass_usage (guest_pass_id, user_id, ticket_id)
               VALUES (%s, %s, %s)"""
    execute_query(query, (pass_data['id'], user_id, ticket_id))
    
    return True

def update_guest_pass(code: str, **kwargs) -> None:
    """Обновить проходку"""
    updates = []
    values = []
    for key, value in kwargs.items():
        if key == 'is_unlimited':
            value = 1 if value else 0
        updates.append(f"{key}=%s")
        values.append(value)
    values.append(code.upper())
    
    query = f"UPDATE guest_passes SET {', '.join(updates)} WHERE code = %s"
    execute_query(query, tuple(values))

def delete_guest_pass(code: str) -> None:
    """Удалить проходку (деактивировать)"""
    query = "UPDATE guest_passes SET active = 0 WHERE code = %s"
    execute_query(query, (code.upper(),))

# Функции для управления билетами
def get_all_tickets(limit: int = 100, offset: int = 0, status: str = None) -> List[Dict[str, Any]]:
    """Получить все билеты"""
    if status:
        query = """SELECT t.*, u.first_name, u.username 
                  FROM tickets t
                  JOIN users u ON t.user_id = u.user_id
                  WHERE t.status = %s
                  ORDER BY t.created_at DESC
                  LIMIT %s OFFSET %s"""
        return execute_query(query, (status, limit, offset), fetch=True) or []
    else:
        query = """SELECT t.*, u.first_name, u.username 
                  FROM tickets t
                  JOIN users u ON t.user_id = u.user_id
                  ORDER BY t.created_at DESC
                  LIMIT %s OFFSET %s"""
        return execute_query(query, (limit, offset), fetch=True) or []

def update_ticket_status(ticket_code: str, status: str) -> None:
    """Обновить статус билета"""
    query = "UPDATE tickets SET status = %s WHERE ticket_code = %s"
    execute_query(query, (status, ticket_code))

# Функции для управления бонусами
def get_all_bonuses(limit: int = 100) -> List[Dict[str, Any]]:
    """Получить все балансы бонусов"""
    query = """SELECT b.*, u.first_name, u.username 
              FROM bonuses b
              JOIN users u ON b.user_id = u.user_id
              ORDER BY b.bonus_balance DESC
              LIMIT %s"""
    return execute_query(query, (limit,), fetch=True) or []

def add_bonuses_manually(user_id: int, amount: float, reason: str = None) -> None:
    """Добавить бонусы вручную (админ)"""
    update_user_bonuses(user_id, amount, 'add', order_id=f"admin_{reason}" if reason else None)

def subtract_bonuses_manually(user_id: int, amount: float, reason: str = None) -> None:
    """Списать бонусы вручную (админ)"""
    update_user_bonuses(user_id, amount, 'subtract', order_id=f"admin_{reason}" if reason else None)

# ==================== ФУНКЦИИ ДЛЯ "ПОИСК ПАРЫ" ====================

def create_dating_profile(user_id: int, photo_file_id: str, gender: str, looking_for: str, 
                          name: str = None, age: int = None, description: str = None) -> bool:
    """Создать или обновить анкету пользователя"""
    query = """INSERT INTO dating_profiles (user_id, photo_file_id, gender, looking_for, name, age, description, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
               ON DUPLICATE KEY UPDATE 
               photo_file_id = VALUES(photo_file_id),
               gender = VALUES(gender),
               looking_for = VALUES(looking_for),
               name = VALUES(name),
               age = VALUES(age),
               description = VALUES(description),
               active = 1,
               updated_at = CURRENT_TIMESTAMP"""
    try:
        execute_query(query, (user_id, photo_file_id, gender, looking_for, name, age, description))
        return True
    except Exception as e:
        logger.error(f"Error creating dating profile: {e}")
        return False

def get_dating_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить анкету пользователя"""
    try:
        query = "SELECT * FROM dating_profiles WHERE user_id = %s AND active = 1"
        result = execute_query(query, (user_id,), fetch=True)
        return result[0] if result else None
    except Exception as e:
        # Если таблица не существует, возвращаем None
        logger.error(f"Error getting dating profile (table may not exist): {e}")
        return None

def delete_dating_profile(user_id: int) -> bool:
    """Удалить анкету пользователя (деактивировать)"""
    query = "UPDATE dating_profiles SET active = 0 WHERE user_id = %s"
    try:
        execute_query(query, (user_id,))
        return True
    except Exception as e:
        logger.error(f"Error deleting dating profile: {e}")
        return False

def get_available_profiles(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получить доступные анкеты для пользователя (исключая уже просмотренные)"""
    try:
        # Получаем анкету текущего пользователя
        user_profile = get_dating_profile(user_id)
        if not user_profile:
            return []
    except Exception as e:
        logger.error(f"Error in get_available_profiles: {e}")
        return []
    
    user_gender = user_profile['gender']
    user_looking_for = user_profile['looking_for']
    
    # Определяем, какие анкеты показывать
    # Если пользователь ищет "both", показываем всех
    # Если ищет "male" или "female", показываем только соответствующий пол
    # Также проверяем, что другой пользователь ищет нас или "both"
    
    gender_condition = ""
    if user_looking_for == 'male':
        gender_condition = "AND p.gender = 'male'"
    elif user_looking_for == 'female':
        gender_condition = "AND p.gender = 'female'"
    # Если "both", то gender_condition пустой - показываем всех
    
    try:
        # Получаем ID пользователей, которым мы уже поставили лайк/дизлайк
        viewed_users_query = "SELECT DISTINCT to_user_id FROM dating_likes WHERE from_user_id = %s"
        viewed_users = execute_query(viewed_users_query, (user_id,), fetch=True)
        viewed_user_ids = [v['to_user_id'] for v in viewed_users] if viewed_users else []
        viewed_user_ids.append(user_id)  # Исключаем себя
        
        # Формируем условие для исключения просмотренных
        exclude_condition = ""
        if viewed_user_ids:
            placeholders = ','.join(['%s'] * len(viewed_user_ids))
            exclude_condition = f"AND p.user_id NOT IN ({placeholders})"
        
        # Проверяем, что другой пользователь ищет нас или "both"
        looking_for_condition = f"AND (p.looking_for = 'both' OR p.looking_for = '{user_gender}')"
        
        query = f"""SELECT p.*, u.username, u.first_name, u.last_name
                    FROM dating_profiles p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.active = 1
                    {gender_condition}
                    {looking_for_condition}
                    {exclude_condition}
                    ORDER BY p.created_at DESC
                    LIMIT %s"""
        
        params = []
        if viewed_user_ids:
            params.extend(viewed_user_ids)
        params.append(limit)
        
        return execute_query(query, tuple(params), fetch=True) or []
    except Exception as e:
        logger.error(f"Error in get_available_profiles query: {e}")
        return []

def add_dating_like(from_user_id: int, to_user_id: int, action: str) -> bool:
    """Добавить лайк или дизлайк"""
    query = """INSERT INTO dating_likes (from_user_id, to_user_id, action)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE action = VALUES(action), created_at = CURRENT_TIMESTAMP"""
    try:
        execute_query(query, (from_user_id, to_user_id, action))
        return True
    except Exception as e:
        logger.error(f"Error adding dating like: {e}")
        return False

def check_match(user1_id: int, user2_id: int) -> bool:
    """Проверить, есть ли взаимный лайк (мэтч)"""
    query = """SELECT COUNT(*) as count FROM dating_likes
               WHERE ((from_user_id = %s AND to_user_id = %s) OR (from_user_id = %s AND to_user_id = %s))
               AND action = 'like'"""
    result = execute_query(query, (user1_id, user2_id, user2_id, user1_id), fetch=True)
    return result[0]['count'] == 2 if result else False

def create_match(user1_id: int, user2_id: int) -> bool:
    """Создать мэтч между двумя пользователями"""
    # Убеждаемся, что user1_id < user2_id для уникальности
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    query = """INSERT INTO dating_matches (user1_id, user2_id)
               VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE matched_at = CURRENT_TIMESTAMP"""
    try:
        execute_query(query, (user1_id, user2_id))
        return True
    except Exception as e:
        logger.error(f"Error creating match: {e}")
        return False

def get_match(user1_id: int, user2_id: int) -> Optional[Dict[str, Any]]:
    """Получить информацию о мэтче"""
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    query = "SELECT * FROM dating_matches WHERE user1_id = %s AND user2_id = %s"
    result = execute_query(query, (user1_id, user2_id), fetch=True)
    return result[0] if result else None

def get_user_matches(user_id: int) -> List[Dict[str, Any]]:
    """Получить все мэтчи пользователя"""
    try:
        query = """SELECT m.*, 
                          CASE WHEN m.user1_id = %s THEN m.user2_id ELSE m.user1_id END as matched_user_id
                   FROM dating_matches m
                   WHERE m.user1_id = %s OR m.user2_id = %s
                   ORDER BY m.matched_at DESC"""
        return execute_query(query, (user_id, user_id, user_id), fetch=True) or []
    except Exception as e:
        logger.error(f"Error getting user matches: {e}")
        return []

def get_likes_received(user_id: int) -> List[Dict[str, Any]]:
    """Получить список пользователей, которые поставили лайк текущему пользователю (исключая тех, на кого уже поставлен лайк/дизлайк)"""
    try:
        query = """SELECT l.from_user_id, l.created_at, u.username, u.first_name, u.last_name
                   FROM dating_likes l
                   JOIN users u ON l.from_user_id = u.user_id
                   WHERE l.to_user_id = %s AND l.action = 'like'
                   AND NOT EXISTS (
                       SELECT 1 FROM dating_likes l2 
                       WHERE l2.from_user_id = %s AND l2.to_user_id = l.from_user_id
                   )
                   ORDER BY l.created_at DESC"""
        return execute_query(query, (user_id, user_id), fetch=True) or []
    except Exception as e:
        logger.error(f"Error getting likes received: {e}")
        return []

def mark_match_notified(user1_id: int, user2_id: int, user_id: int) -> bool:
    """Отметить, что пользователь получил уведомление о мэтче"""
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    field = 'notified_user1' if user_id == user1_id else 'notified_user2'
    query = f"UPDATE dating_matches SET {field} = 1 WHERE user1_id = %s AND user2_id = %s"
    try:
        execute_query(query, (user1_id, user2_id))
        return True
    except Exception as e:
        logger.error(f"Error marking match as notified: {e}")
        return False

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С МЕСТАМИ (MINI APP) ====================

def get_occupied_seats() -> Dict[str, Dict[str, List[int]]]:
    """Получить все занятые места из базы данных"""
    query = """SELECT seat_floor, seat_section, seat_number 
               FROM tickets 
               WHERE status = 'active' 
                 AND seat_floor IS NOT NULL 
                 AND seat_section IS NOT NULL 
                 AND seat_number IS NOT NULL"""
    
    result = execute_query(query, fetch=True)
    
    occupied = {
        'floor_1': {},
        'floor_2': {}
    }
    
    for row in result or []:
        floor_key = f"floor_{row['seat_floor']}"
        section = row['seat_section']
        seat_num = row['seat_number']
        
        if section not in occupied[floor_key]:
            occupied[floor_key][section] = []
        
        if seat_num not in occupied[floor_key][section]:
            occupied[floor_key][section].append(seat_num)
    
    # Сортируем номера мест
    for floor_key in occupied:
        for section in occupied[floor_key]:
            occupied[floor_key][section].sort()
    
    return occupied

def get_user_seat_selection(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить выбранные места пользователя"""
    query = """SELECT * FROM seat_selections 
               WHERE user_id = %s AND expires_at > NOW()"""
    result = execute_query(query, (user_id,), fetch=True)
    return result[0] if result else None

def save_user_seat_selection(user_id: int, ticket_type: str, quantity: int, 
                             selected_seats: List[Dict[str, Any]]) -> None:
    """Сохранить выбранные места пользователя"""
    import json
    from datetime import datetime, timedelta
    
    seats_json = json.dumps(selected_seats, ensure_ascii=False)
    expires_at = datetime.now() + timedelta(minutes=30)
    
    query = """INSERT INTO seat_selections (user_id, ticket_type, quantity, selected_seats, expires_at)
               VALUES (%s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE 
               ticket_type = VALUES(ticket_type),
               quantity = VALUES(quantity),
               selected_seats = VALUES(selected_seats),
               expires_at = VALUES(expires_at),
               created_at = CURRENT_TIMESTAMP"""
    
    execute_query(query, (user_id, ticket_type, quantity, seats_json, expires_at))

def delete_user_seat_selection(user_id: int) -> None:
    """Удалить выбранные места пользователя"""
    query = "DELETE FROM seat_selections WHERE user_id = %s"
    execute_query(query, (user_id,))

def cleanup_expired_selections() -> int:
    """Очистить просроченные выборы мест"""
    # Сначала получаем количество записей для удаления
    count_query = "SELECT COUNT(*) as count FROM seat_selections WHERE expires_at < NOW()"
    result = execute_query(count_query, fetch=True)
    count = result[0]['count'] if result else 0
    
    # Удаляем просроченные записи
    query = "DELETE FROM seat_selections WHERE expires_at < NOW()"
    execute_query(query)
    
    return count

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С КАТЕГОРИЯМИ БИЛЕТОВ ====================

def get_all_ticket_categories(active_only: bool = False) -> List[Dict[str, Any]]:
    """Получить все категории билетов"""
    if active_only:
        query = "SELECT * FROM ticket_categories WHERE is_active = 1 ORDER BY sort_order ASC, name ASC"
    else:
        query = "SELECT * FROM ticket_categories ORDER BY sort_order ASC, name ASC"
    return execute_query(query, fetch=True) or []

def get_ticket_category(code: str) -> Optional[Dict[str, Any]]:
    """Получить категорию билета по коду"""
    query = "SELECT * FROM ticket_categories WHERE code = %s"
    result = execute_query(query, (code,), fetch=True)
    return result[0] if result else None

def get_ticket_limit_from_db(ticket_type: str) -> Optional[int]:
    """Получить лимит билетов по типу из ticket_categories. None если категории нет."""
    cat = get_ticket_category(ticket_type)
    if not cat:
        return None
    limit = cat.get('limit')
    if limit is None:
        return None
    return int(limit)

def ensure_standard_ticket_categories() -> None:
    """Создать стандартные категории (regular, vip, vip_standing, couple), если их ещё нет в БД."""
    defaults = [
        ('regular', 'Обычный билет', 550.00, 550.00, 600, 0, 1),
        ('vip', 'VIP билет', 850.00, 850.00, 80, 1, 2),
        ('vip_standing', 'VIP стоячий', 850.00, 850.00, 20, 0, 3),
        ('couple', 'Парный билет', 990.00, 990.00, 50, 0, 4),
    ]
    for code, name, base_price, discounted_price, limit, allows_seat, sort_order in defaults:
        if get_ticket_category(code) is None:
            try:
                create_ticket_category(
                    code=code, name=name, base_price=base_price, discounted_price=discounted_price,
                    limit=limit, allows_seat_selection=bool(allows_seat), sort_order=sort_order
                )
                logger.info(f"Created standard ticket category: {code}")
            except Exception as e:
                logger.error(f"Error creating category {code}: {e}")

def create_ticket_category(code: str, name: str, base_price: float, discounted_price: float,
                          limit: int = 0, description: str = None, allows_seat_selection: bool = False,
                          sort_order: int = 0) -> bool:
    """Создать новую категорию билетов"""
    try:
        query = """INSERT INTO ticket_categories 
                   (code, name, description, base_price, discounted_price, `limit`, allows_seat_selection, sort_order, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)"""
        execute_query(query, (code, name, description, base_price, discounted_price, limit, 
                             1 if allows_seat_selection else 0, sort_order))
        return True
    except Exception as e:
        logger.error(f"Error creating ticket category: {e}")
        return False

def update_ticket_category(code: str, **kwargs) -> bool:
    """Обновить категорию билетов. Возвращает False, если категория не найдена."""
    try:
        if get_ticket_category(code) is None:
            return False
        updates = []
        values = []
        for key, value in kwargs.items():
            if key == 'allows_seat_selection':
                value = 1 if value else 0
            elif key == 'is_active':
                value = 1 if value else 0
            updates.append(f"`{key}`=%s")
            values.append(value)
        values.append(code)
        
        query = f"UPDATE ticket_categories SET {', '.join(updates)}, updated_at = NOW() WHERE code = %s"
        execute_query(query, tuple(values))
        return True
    except Exception as e:
        logger.error(f"Error updating ticket category: {e}")
        return False

def delete_ticket_category(code: str) -> bool:
    """Удалить категорию билетов (деактивировать)"""
    try:
        # Проверяем, есть ли проданные билеты этой категории
        sold_count = count_tickets_by_type(code)
        if sold_count > 0:
            # Деактивируем вместо удаления
            query = "UPDATE ticket_categories SET is_active = 0 WHERE code = %s"
        else:
            # Можно удалить, если нет проданных билетов
            query = "DELETE FROM ticket_categories WHERE code = %s"
        execute_query(query, (code,))
        return True
    except Exception as e:
        logger.error(f"Error deleting ticket category: {e}")
        return False

def increment_ticket_category_sold(code: str, count: int = 1) -> None:
    """Увеличить счетчик проданных билетов категории"""
    query = "UPDATE ticket_categories SET sold_count = sold_count + %s WHERE code = %s"
    execute_query(query, (count, code))

def check_user_seat_selection(user_id: int, required_quantity: int) -> Dict[str, Any]:
    """Проверить выбранные места пользователя"""
    query = """SELECT * FROM seat_selections 
               WHERE user_id = %s AND expires_at > NOW()"""
    result = execute_query(query, (user_id,), fetch=True)
    
    if not result:
        return {'has_selection': False, 'message': 'Места не выбраны'}
    
    selection = result[0]
    import json
    selected_seats = json.loads(selection['selected_seats'])
    
    # Проверяем количество
    if len(selected_seats) != required_quantity:
        return {
            'has_selection': False,
            'message': f"Выбрано мест: {len(selected_seats)}, требуется: {required_quantity}"
        }
    
    # Проверяем, что места все еще свободны
    occupied_seats = get_occupied_seats()
    for seat in selected_seats:
        floor_key = f"floor_{seat['floor']}"
        section = seat['section']
        seat_num = seat['seat_number']
        
        if seat_num in (occupied_seats.get(floor_key, {}).get(section, [])):
            return {
                'has_selection': False,
                'message': f"Место {section}-{seat_num} уже занято"
            }
    
    return {'has_selection': True, 'selection': selection}

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ТИКЕТАМИ ПОДДЕРЖКИ ====================

def create_support_ticket(user_id: int, subject: str = None) -> str:
    """Создать новый тикет поддержки"""
    try:
        import uuid
        import time
        ticket_id = f"TICKET-{int(time.time())}-{str(uuid.uuid4())[:8].upper()}"
        
        query = """INSERT INTO support_tickets (ticket_id, user_id, subject, status, priority)
                   VALUES (%s, %s, %s, 'open', 'medium')"""
        execute_query(query, (ticket_id, user_id, subject))
        logger.info(f"Created support ticket {ticket_id} for user {user_id}")
        return ticket_id
    except Exception as e:
        logger.error(f"Error creating support ticket: {e}")
        return None

def get_support_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Получить тикет по ID"""
    try:
        if not ticket_id:
            return None
        query = "SELECT * FROM support_tickets WHERE ticket_id = %s"
        result = execute_query(query, (ticket_id,), fetch=True)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting support ticket {ticket_id}: {e}")
        return None

def get_user_tickets(user_id: int, status: str = None) -> List[Dict[str, Any]]:
    """Получить все тикеты пользователя"""
    try:
        if status:
            query = """SELECT * FROM support_tickets 
                       WHERE user_id = %s AND status = %s 
                       ORDER BY created_at DESC"""
            result = execute_query(query, (user_id, status), fetch=True)
        else:
            query = """SELECT * FROM support_tickets 
                       WHERE user_id = %s 
                       ORDER BY created_at DESC"""
            result = execute_query(query, (user_id,), fetch=True)
        return result if result else []
    except Exception as e:
        logger.error(f"Error getting user tickets for {user_id}: {e}")
        return []

def get_all_support_tickets(status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Получить все тикеты (для админов)"""
    try:
        if status:
            query = """SELECT * FROM support_tickets 
                       WHERE status = %s 
                       ORDER BY created_at DESC 
                       LIMIT %s"""
            result = execute_query(query, (status, limit), fetch=True)
        else:
            query = """SELECT * FROM support_tickets 
                       ORDER BY created_at DESC 
                       LIMIT %s"""
            result = execute_query(query, (limit,), fetch=True)
        return result if result else []
    except Exception as e:
        logger.error(f"Error in get_all_support_tickets: {e}")
        return []

def update_ticket_status(ticket_id: str, status: str, admin_id: int = None) -> bool:
    """Обновить статус тикета"""
    try:
        if status == 'closed':
            query = """UPDATE support_tickets 
                      SET status = %s, admin_id = %s, closed_at = NOW() 
                      WHERE ticket_id = %s"""
            execute_query(query, (status, admin_id, ticket_id))
        elif status == 'in_progress' and admin_id:
            query = """UPDATE support_tickets 
                      SET status = %s, admin_id = %s 
                      WHERE ticket_id = %s"""
            execute_query(query, (status, admin_id, ticket_id))
        else:
            query = """UPDATE support_tickets 
                      SET status = %s 
                      WHERE ticket_id = %s"""
            execute_query(query, (status, ticket_id))
        logger.info(f"Updated ticket {ticket_id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating ticket status: {e}", exc_info=True)
        return False

def add_support_message(ticket_id: str, user_id: int, message_text: str, 
                        message_type: str = 'text', file_id: str = None, is_admin: bool = False) -> int:
    """Добавить сообщение в тикет"""
    query = """INSERT INTO support_messages 
               (ticket_id, user_id, message_text, message_type, file_id, is_admin)
               VALUES (%s, %s, %s, %s, %s, %s)"""
    execute_query(query, (ticket_id, user_id, message_text, message_type, file_id, 1 if is_admin else 0))
    
    # Обновляем время последнего обновления тикета
    if is_admin:
        update_ticket_status(ticket_id, 'in_progress', user_id)
    else:
        update_ticket_status(ticket_id, 'waiting')
    
    # Получаем ID вставленного сообщения
    result = execute_query("SELECT LAST_INSERT_ID() as id", fetch=True)
    return result[0]['id'] if result else 0

def get_ticket_messages(ticket_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Получить все сообщения тикета"""
    query = """SELECT * FROM support_messages 
               WHERE ticket_id = %s 
               ORDER BY created_at ASC 
               LIMIT %s"""
    result = execute_query(query, (ticket_id, limit), fetch=True)
    return result if result else []

def get_ticket_stats() -> Dict[str, Any]:
    """Получить статистику по тикетам"""
    try:
        stats = {}
        
        # Всего тикетов
        query = "SELECT COUNT(*) as count FROM support_tickets"
        result = execute_query(query, fetch=True)
        stats['total'] = result[0]['count'] if result else 0
        
        # Открытых
        query = "SELECT COUNT(*) as count FROM support_tickets WHERE status = 'open'"
        result = execute_query(query, fetch=True)
        stats['open'] = result[0]['count'] if result else 0
        
        # В обработке
        query = "SELECT COUNT(*) as count FROM support_tickets WHERE status = 'in_progress'"
        result = execute_query(query, fetch=True)
        stats['in_progress'] = result[0]['count'] if result else 0
        
        # Ожидающих ответа
        query = "SELECT COUNT(*) as count FROM support_tickets WHERE status = 'waiting'"
        result = execute_query(query, fetch=True)
        stats['waiting'] = result[0]['count'] if result else 0
        
        # Закрытых
        query = "SELECT COUNT(*) as count FROM support_tickets WHERE status = 'closed'"
        result = execute_query(query, fetch=True)
        stats['closed'] = result[0]['count'] if result else 0
        
        return stats
    except Exception as e:
        logger.error(f"Error in get_ticket_stats: {e}")
        return {
            'total': 0,
            'open': 0,
            'in_progress': 0,
            'waiting': 0,
            'closed': 0
        }

