# -*- coding: utf-8 -*-
"""
API endpoints для Mini App выбора мест
"""

from flask import Blueprint, request, jsonify
import database as db
import json
import logging

logger = logging.getLogger(__name__)

miniapp_bp = Blueprint('miniapp', __name__)

# Структура зала на основе планов этажей
FLOOR_STRUCTURE = {
    'floor_1': {
        '1_1': {'total_seats': 5, 'layout': 'vertical', 'rows': 1},
        '1_2': {'total_seats': 4, 'layout': 'vertical', 'rows': 1},
        '1_3': {'total_seats': 4, 'layout': 'vertical', 'rows': 1},
        '1_4': {'total_seats': 4, 'layout': 'vertical', 'rows': 1}
    },
    'floor_2': {
        '21': {'total_seats': 6, 'layout': 'grid', 'rows': 3, 'seats_per_row': 2},
        '22': {'total_seats': 6, 'layout': 'grid', 'rows': 3, 'seats_per_row': 2},
        '23': {'total_seats': 2, 'layout': 'horizontal', 'rows': 1},
        '24': {'total_seats': 2, 'layout': 'horizontal', 'rows': 1},
        '25': {'total_seats': 2, 'layout': 'horizontal', 'rows': 1},
        '26': {'total_seats': 2, 'layout': 'horizontal', 'rows': 1},
        '27': {'total_seats': 7, 'layout': 'mixed', 'rows': 2, 'seats_per_row': [4, 3]},
        '28': {'total_seats': 3, 'layout': 'mixed', 'rows': 2, 'seats_per_row': [2, 1]},
        '29': {'total_seats': 6, 'layout': 'grid', 'rows': 3, 'seats_per_row': 2}
    }
}

@miniapp_bp.route('/api/miniapp/seats', methods=['GET', 'POST', 'OPTIONS'])
def seats_api():
    """API для работы с местами"""
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response
    
    user_id = request.args.get('user_id') or (request.json and request.json.get('user_id'))
    
    if not user_id:
        response = jsonify({'success': False, 'error': 'user_id required'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        response = jsonify({'success': False, 'error': 'Invalid user_id'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    if request.method == 'GET':
        # Получение данных о местах
        floor = request.args.get('floor')
        ticket_type = request.args.get('ticket_type', 'vip')
        
        occupied_seats = db.get_occupied_seats()
        
        result = {
            'success': True,
            'floors': {}
        }
        
        for floor_key in ['floor_1', 'floor_2']:
            if floor and floor_key != f"floor_{floor}":
                continue
            
            result['floors'][floor_key] = {'sections': {}}
            
            for section, config in FLOOR_STRUCTURE[floor_key].items():
                occupied = occupied_seats.get(floor_key, {}).get(section, [])
                section_data = {
                    'total_seats': config['total_seats'],
                    'occupied': occupied,
                    'layout': config['layout'],
                    'rows': config.get('rows', 1)
                }
                
                if 'seats_per_row' in config:
                    section_data['seats_per_row'] = config['seats_per_row']
                
                result['floors'][floor_key]['sections'][section] = section_data
        
        # Загружаем выбранные места пользователя (если есть)
        selection = db.get_user_seat_selection(user_id)
        if selection:
            result['user_selection'] = {
                'user_id': selection['user_id'],
                'ticket_type': selection['ticket_type'],
                'quantity': selection['quantity'],
                'selected_seats': json.loads(selection['selected_seats']),
                'created_at': selection['created_at'].isoformat() if hasattr(selection['created_at'], 'isoformat') else str(selection['created_at']),
                'expires_at': selection['expires_at'].isoformat() if hasattr(selection['expires_at'], 'isoformat') else str(selection['expires_at'])
            }
        
        response = jsonify(result)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    elif request.method == 'POST':
        # Сохранение выбранных мест
        data = request.json
        if not data:
            response = jsonify({'success': False, 'error': 'No data provided'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        ticket_type = data.get('ticket_type', 'vip')
        quantity = int(data.get('quantity', 1))
        selected_seats = data.get('selected_seats', [])
        
        if len(selected_seats) != quantity:
            response = jsonify({
                'success': False,
                'error': f'Необходимо выбрать {quantity} мест(а)'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # Проверяем, что места свободны
        occupied_seats = db.get_occupied_seats()
        for seat in selected_seats:
            floor_key = f"floor_{seat['floor']}"
            section = seat['section']
            seat_num = seat['seat_number']
            
            if seat_num in occupied_seats.get(floor_key, {}).get(section, []):
                response = jsonify({
                    'success': False,
                    'error': f"Место {section}-{seat_num} уже занято"
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 400
        
        # Сохраняем выбор
        try:
            db.save_user_seat_selection(user_id, ticket_type, quantity, selected_seats)
            selection = db.get_user_seat_selection(user_id)
            
            response = jsonify({
                'success': True,
                'message': 'Места успешно сохранены',
                'expires_at': selection['expires_at'].isoformat() if hasattr(selection['expires_at'], 'isoformat') else str(selection['expires_at'])
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        except Exception as e:
            logger.error(f"Error saving seat selection: {e}", exc_info=True)
            response = jsonify({
                'success': False,
                'error': f'Ошибка при сохранении: {str(e)}'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500

@miniapp_bp.route('/api/miniapp/user_selection', methods=['GET', 'DELETE', 'OPTIONS'])
def user_selection_api():
    """API для работы с выбранными местами пользователя"""
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, DELETE, OPTIONS')
        return response
    
    user_id = request.args.get('user_id')
    
    if not user_id:
        response = jsonify({'success': False, 'error': 'user_id required'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        response = jsonify({'success': False, 'error': 'Invalid user_id'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    if request.method == 'GET':
        selection = db.get_user_seat_selection(user_id)
        if not selection:
            response = jsonify({'success': False, 'error': 'Selection not found'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        response = jsonify({
            'success': True,
            'selection': {
                'user_id': selection['user_id'],
                'ticket_type': selection['ticket_type'],
                'quantity': selection['quantity'],
                'selected_seats': json.loads(selection['selected_seats']),
                'created_at': selection['created_at'].isoformat() if hasattr(selection['created_at'], 'isoformat') else str(selection['created_at']),
                'expires_at': selection['expires_at'].isoformat() if hasattr(selection['expires_at'], 'isoformat') else str(selection['expires_at'])
            }
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    elif request.method == 'DELETE':
        db.delete_user_seat_selection(user_id)
        response = jsonify({'success': True, 'message': 'Selection deleted'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

