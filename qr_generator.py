# -*- coding: utf-8 -*-
"""
Генератор QR-кодов для билетов
"""

import qrcode
import json
import hashlib
import os
import logging
from typing import Dict, Any
import config

logger = logging.getLogger(__name__)

def generate_qr_code(ticket_data: Dict[str, Any]) -> str:
    """Генерирует QR-код для билета"""
    try:
        # Создаем директорию для временных файлов
        if not os.path.exists(config.TEMP_DIR):
            os.makedirs(config.TEMP_DIR)
        
        # Формируем данные для QR-кода
        qr_data = {
            'ticket_code': ticket_data['ticket_code'],
            'user_id': ticket_data['user_id'],
            'amount': ticket_data['amount'],
            'ticket_type': ticket_data['ticket_type'],
            'order_id': ticket_data['order_id'],
            'created_at': ticket_data.get('created_at', ''),
            'bonus_used': ticket_data.get('bonus_used', 0),
            'bonus_earned': ticket_data.get('bonus_earned', 0),
            'promo_code': ticket_data.get('promo_code', ''),
            'signature': hashlib.md5(
                f"{ticket_data['ticket_code']}{ticket_data['user_id']}{config.QR_SECRET}".encode()
            ).hexdigest()[:8]
        }
        
        qr_text = json.dumps(qr_data, ensure_ascii=False)
        
        # Создаем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        # Создаем изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Сохраняем файл
        ticket_code = ticket_data['ticket_code']
        qr_path = os.path.join(config.TEMP_DIR, f"qr_{ticket_code}.png")
        img.save(qr_path)
        
        logger.info(f"QR code generated: {qr_path}")
        return qr_path
        
    except Exception as e:
        logger.error(f"Error generating QR code: {e}", exc_info=True)
        raise

