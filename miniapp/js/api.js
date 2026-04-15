// API для работы с сервером

// ВАЖНО: Базовый URL должен включать /KISSPARTYPAYMAIN
const API_BASE = 'https://cw998871.tw1.ru/KISSPARTYPAYMAIN';

console.log('=== API MODULE LOADED ===');
console.log('API_BASE:', API_BASE);
console.log('API_BASE verification:', API_BASE === 'https://cw998871.tw1.ru/KISSPARTYPAYMAIN' ? '✅ CORRECT' : '❌ WRONG!');
console.log('Current page URL:', window.location.href);
console.log('Expected API path should contain: /KISSPARTYPAYMAIN/api/miniapp/');

async function fetchSeatsData(userId, ticketType = 'vip', floor = null) {
    console.log('=== fetchSeatsData CALLED ===');
    console.log('Function parameters received:');
    console.log('  userId:', userId, 'Type:', typeof userId, 'Is NaN?', isNaN(userId));
    console.log('  ticketType:', ticketType, 'Type:', typeof ticketType);
    console.log('  floor:', floor, 'Type:', typeof floor);
    
    if (!userId || isNaN(userId)) {
        console.error('❌ VALIDATION FAILED: Invalid user_id');
        console.error('  userId value:', userId);
        console.error('  userId type:', typeof userId);
        console.error('  isNaN(userId):', isNaN(userId));
        throw new Error(`Invalid user_id: ${userId} (type: ${typeof userId})`);
    }
    
    console.log('✅ Validation passed, building URL...');
    
    // Строим URL с проверкой
    let url = `${API_BASE}/api/miniapp/seats?user_id=${userId}&ticket_type=${ticketType}`;
    if (floor) {
        url += `&floor=${floor}`;
    }
    
    // КРИТИЧЕСКАЯ ПРОВЕРКА URL
    if (!url.includes('/KISSPARTYPAYMAIN/')) {
        console.error('❌❌❌ CRITICAL ERROR: URL does not contain /KISSPARTYPAYMAIN/ ❌❌❌');
        console.error('Built URL:', url);
        console.error('API_BASE value:', API_BASE);
        throw new Error('URL construction error: missing /KISSPARTYPAYMAIN/ in path');
    }
    
    if (url.includes('user_id=NaN')) {
        console.error('❌❌❌ CRITICAL ERROR: user_id is NaN in URL ❌❌❌');
        console.error('userId value:', userId);
        console.error('userId type:', typeof userId);
        throw new Error('URL construction error: user_id is NaN');
    }
    
    console.log('=== API REQUEST DETAILS ===');
    console.log('Full URL:', url);
    console.log('URL verification:', url.includes('/KISSPARTYPAYMAIN/') ? '✅ Contains /KISSPARTYPAYMAIN/' : '❌ Missing /KISSPARTYPAYMAIN/');
    console.log('URL verification:', !url.includes('NaN') ? '✅ No NaN in URL' : '❌ NaN found in URL!');
    console.log('URL components:');
    console.log('  Base:', API_BASE);
    console.log('  Endpoint: /api/miniapp/seats');
    console.log('  Query params:');
    console.log('    user_id:', userId, '(type:', typeof userId, ')');
    console.log('    ticket_type:', ticketType, '(type:', typeof ticketType, ')');
    if (floor) console.log('    floor:', floor, '(type:', typeof floor, ')');
    
    console.log('📡 Sending fetch request...');
    const startTime = Date.now();
    
    try {
        const response = await fetch(url);
        const duration = Date.now() - startTime;
        
        console.log('=== API RESPONSE RECEIVED ===');
        console.log('Status:', response.status, response.statusText);
        console.log('Response time:', duration + 'ms');
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ API ERROR RESPONSE:');
            console.error('  Status:', response.status);
            console.error('  Status Text:', response.statusText);
            console.error('  Response Body:', errorText);
            console.error('  Request URL:', url);
            throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('✅ API SUCCESS:');
        console.log('  Response data:', data);
        return data;
    } catch (error) {
        console.error('❌ FETCH ERROR:');
        console.error('  Error type:', error.constructor.name);
        console.error('  Error message:', error.message);
        console.error('  Error stack:', error.stack);
        console.error('  Request URL:', url);
        throw error;
    }
}

async function saveSeatSelection(userId, ticketType, quantity, selectedSeats) {
    if (!userId || isNaN(userId)) {
        throw new Error('Invalid user_id');
    }
    
    const url = `${API_BASE}/api/miniapp/seats`;
    console.log('Saving seat selection to:', url);
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: userId,
            ticket_type: ticketType,
            quantity: quantity,
            selected_seats: selectedSeats
        })
    });
    
    if (!response.ok) {
        const errorText = await response.text();
        console.error('API Error:', response.status, errorText);
        let error;
        try {
            error = await response.json();
        } catch {
            error = { error: errorText || 'Ошибка при сохранении' };
        }
        throw new Error(error.error || 'Ошибка при сохранении');
    }
    
    return await response.json();
}

async function getUserSelection(userId) {
    if (!userId || isNaN(userId)) {
        return null;
    }
    
    const url = `${API_BASE}/api/miniapp/user_selection?user_id=${userId}`;
    console.log('Getting user selection from:', url);
    
    const response = await fetch(url);
    if (!response.ok) {
        if (response.status === 404) {
            return null; // Выбор не найден - это нормально
        }
        console.error('API Error:', response.status);
        return null;
    }
    const data = await response.json();
    return data.selection;
}

async function deleteUserSelection(userId) {
    if (!userId || isNaN(userId)) {
        return;
    }
    
    const url = `${API_BASE}/api/miniapp/user_selection?user_id=${userId}`;
    console.log('Deleting user selection from:', url);
    
    const response = await fetch(url, {
        method: 'DELETE'
    });
    if (response.ok) {
        return await response.json();
    }
    return null;
}

