# -*- coding: utf-8 -*-
"""
Модуль для работы с платежами Robokassa
"""

import hashlib
import logging
from typing import Tuple
import config

logger = logging.getLogger(__name__)

def generate_payment_link(user_id: int, amount: float, ticket_type: str, quantity: int,
                         bonus_used: float = 0, promo_code: str = None) -> Tuple[str, str]:
    """Генерирует ссылку на оплату через Robokassa"""
    import random
    
    # Генерируем номер заказа
    inv_id = str(random.randint(10000, 99999))
    
    # Формируем подпись
    signature_string = f"{config.ROBOKASSA_MERCHANT_LOGIN}:{amount}:{inv_id}:{config.ROBOKASSA_PASSWORD1}"
    
    # Добавляем shp параметры
    shp_params = {
        'Shp_user_id': str(user_id),
        'Shp_ticket_type': ticket_type,
        'Shp_bonus_used': str(bonus_used),
        'Shp_ticket_quantity': str(quantity)
    }
    
    if promo_code:
        shp_params['Shp_promo_code'] = promo_code
    
    # Сортируем параметры
    sorted_shp = sorted(shp_params.items())
    shp_string_parts = [f"{k}={v}" for k, v in sorted_shp]
    
    if shp_string_parts:
        signature_string += f":{':'.join(shp_string_parts)}"
    
    signature = hashlib.md5(signature_string.encode()).hexdigest()
    
    # Формируем URL
    base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
    params = {
        'MerchantLogin': config.ROBOKASSA_MERCHANT_LOGIN,
        'OutSum': str(amount),
        'InvId': inv_id,
        'Description': f'KISS PARTY - {ticket_type} x{quantity}',
        'SignatureValue': signature
    }
    
    # Добавляем shp параметры
    for key, value in sorted_shp:
        params[key] = value
    
    # Формируем финальный URL
    param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    payment_url = f"{base_url}?{param_string}"
    
    logger.info(f"Payment link generated: order_id={inv_id}, amount={amount}, user_id={user_id}")
    
    return payment_url, inv_id

