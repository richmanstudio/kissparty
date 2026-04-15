// Основная логика Mini App

console.log('=== MINI APP INITIALIZATION START ===');
console.log('Script file: app.js loaded');
console.log('Timestamp:', new Date().toISOString());
console.log('Current URL:', window.location.href);
console.log('Full URL:', window.location.href);
console.log('Search params:', window.location.search);
console.log('Hash:', window.location.hash);
console.log('Document ready state:', document.readyState);

const tg = window.Telegram.WebApp;
console.log('Telegram WebApp object:', tg);
console.log('Telegram WebApp version:', tg.version);

tg.ready();
tg.expand();

// Премиум интеграция с Telegram WebApp API
console.log('🎨 Applying Telegram theme colors...');

// Настройка темы Telegram с применением цветов
const applyTelegramTheme = () => {
    const root = document.documentElement;
    
    // Получаем цвета из Telegram WebApp API
    if (tg.themeParams) {
        // Фон
        if (tg.themeParams.bg_color) {
            root.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color);
            root.style.setProperty('--bg-primary', tg.themeParams.bg_color);
        }
        
        // Текст
        if (tg.themeParams.text_color) {
            root.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color);
            root.style.setProperty('--text-primary', tg.themeParams.text_color);
        }
        
        // Подсказки
        if (tg.themeParams.hint_color) {
            root.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color);
            root.style.setProperty('--text-secondary', tg.themeParams.hint_color);
        }
        
        // Ссылки
        if (tg.themeParams.link_color) {
            root.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color);
        }
        
        // Кнопки
        if (tg.themeParams.button_color) {
            root.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color);
        }
        
        if (tg.themeParams.button_text_color) {
            root.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color);
        }
        
        // Вторичный фон
        if (tg.themeParams.secondary_bg_color) {
            root.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color);
            root.style.setProperty('--bg-secondary', tg.themeParams.secondary_bg_color);
        }
        
        console.log('✅ Telegram theme colors applied:', tg.themeParams);
    }
    
    // Определяем тему
    if (tg.colorScheme === 'dark') {
        document.body.classList.add('dark-theme');
        document.body.classList.remove('light-theme');
        console.log('🌙 Dark theme activated');
    } else {
        document.body.classList.add('light-theme');
        document.body.classList.remove('dark-theme');
        console.log('☀️ Light theme activated');
    }
    
    // Устанавливаем цвет статус-бара (только если поддерживается)
    // В версии 6.0 эти методы не поддерживаются, поэтому проверяем версию
    try {
        if (tg.setHeaderColor && typeof tg.setHeaderColor === 'function') {
            tg.setHeaderColor(tg.themeParams?.bg_color || '#0a0a0a');
        }
    } catch (e) {
        console.log('⚠️ setHeaderColor not supported:', e.message);
    }
    
    // Устанавливаем цвет фона (только если поддерживается)
    try {
        if (tg.setBackgroundColor && typeof tg.setBackgroundColor === 'function') {
            tg.setBackgroundColor(tg.themeParams?.bg_color || '#0a0a0a');
        }
    } catch (e) {
        console.log('⚠️ setBackgroundColor not supported:', e.message);
    }
};

// Применяем тему при загрузке
applyTelegramTheme();

// Слушаем изменения темы
if (tg.onEvent) {
    tg.onEvent('themeChanged', applyTelegramTheme);
    tg.onEvent('viewportChanged', () => {
        console.log('📱 Viewport changed');
    });
}

// Получаем параметры из URL
console.log('=== PARSING URL PARAMETERS ===');
const urlParams = new URLSearchParams(window.location.search);
console.log('URLSearchParams object:', urlParams);
console.log('All URL params:', Object.fromEntries(urlParams.entries()));

let userId = urlParams.get('user_id');
console.log('Raw user_id from URL:', userId, 'Type:', typeof userId);

if (userId) {
    const userIdParsed = parseInt(userId);
    console.log('Parsed user_id:', userIdParsed, 'Is NaN?', isNaN(userIdParsed));
    if (isNaN(userIdParsed)) {
        console.error('❌ Invalid user_id:', userId, 'Cannot parse to integer');
        userId = null;
    } else {
        userId = userIdParsed;
        console.log('✅ Valid user_id:', userId);
    }
} else {
    console.error('❌ user_id parameter is missing from URL');
    console.log('Available params:', Array.from(urlParams.keys()));
    userId = null;
}

const ticketType = urlParams.get('ticket_type') || 'vip';
console.log('ticket_type:', ticketType);

let quantity = urlParams.get('quantity');
console.log('Raw quantity from URL:', quantity, 'Type:', typeof quantity);
if (quantity) {
    const quantityParsed = parseInt(quantity);
    console.log('Parsed quantity:', quantityParsed, 'Is NaN?', isNaN(quantityParsed));
    if (isNaN(quantityParsed)) {
        console.warn('⚠️ Invalid quantity, using default: 1');
        quantity = 1;
    } else {
        quantity = quantityParsed;
        console.log('✅ Valid quantity:', quantity);
    }
} else {
    console.log('No quantity param, using default: 1');
    quantity = 1;
}

console.log('=== FINAL PARSED PARAMETERS ===');
console.log('userId:', userId, 'Type:', typeof userId);
console.log('ticketType:', ticketType, 'Type:', typeof ticketType);
console.log('quantity:', quantity, 'Type:', typeof quantity);

// Проверка обязательных параметров
if (!userId) {
    console.error('❌❌❌ CRITICAL ERROR: Cannot initialize - user_id is required ❌❌❌');
    console.error('Full URL breakdown:');
    console.error('  Protocol:', window.location.protocol);
    console.error('  Host:', window.location.host);
    console.error('  Pathname:', window.location.pathname);
    console.error('  Search:', window.location.search);
    console.error('  Hash:', window.location.hash);
    
    // Инициализируем Telegram WebApp для закрытия
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.ready();
        tg.expand();
    }
    
    document.body.innerHTML = `
        <div style="padding: 40px 20px; text-align: center; color: #fff; background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; flex-direction: column; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin-bottom: 30px; box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M2 17L12 22L22 17" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M2 12L12 17L22 12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>
            <h2 style="color: #fff; font-size: 24px; font-weight: 600; margin-bottom: 15px; line-height: 1.3;">Выбор VIP мест</h2>
            <p style="color: #b0b0b0; font-size: 16px; line-height: 1.6; max-width: 300px; margin-bottom: 30px;">
                Это приложение предназначено только для выбора мест при покупке VIP билетов.
            </p>
            <p style="color: #888; font-size: 14px; line-height: 1.5; max-width: 300px; margin-bottom: 40px;">
                Чтобы использовать приложение, начните покупку VIP билета в боте и нажмите кнопку "🗺️ Выбрать места на карте".
            </p>
            <button onclick="window.Telegram?.WebApp?.close()" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 32px; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); transition: transform 0.2s, box-shadow 0.2s;" onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 6px 20px rgba(102, 126, 234, 0.5)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(102, 126, 234, 0.4)';">
                Закрыть
            </button>
        </div>
    `;
}

// Инициализация
const mapRenderer = new MapRenderer();
let seatsData = null;
let selectedSeats = [];
let currentFloor = 1;

// Элементы DOM
const loadingEl = document.getElementById('loading');
const selectedCountEl = document.getElementById('selected-count');
const totalCountEl = document.getElementById('total-count');
const selectedListEl = document.getElementById('selected-list');
const saveBtn = document.getElementById('save-btn');
const clearBtn = document.getElementById('clear-btn');
const floorButtons = document.querySelectorAll('.floor-btn');
const progressFillEl = document.getElementById('progress-fill');
const selectedCountBadgeEl = document.getElementById('selected-count-badge');
const emptyStateEl = document.getElementById('empty-state');
const toastEl = document.getElementById('toast');
const headerIconEl = document.getElementById('header-icon');
const selectedSeatsIconEl = document.getElementById('selected-seats-icon');
const saveIconEl = document.getElementById('save-icon');
const clearIconEl = document.getElementById('clear-icon');
const floorIcon1El = document.getElementById('floor-icon-1');
const floorIcon2El = document.getElementById('floor-icon-2');

// Инициализация иконок
function initIcons() {
    if (headerIconEl) headerIconEl.innerHTML = getIcon('map', 'icon');
    if (selectedSeatsIconEl) selectedSeatsIconEl.innerHTML = getIcon('seat', 'icon');
    if (saveIconEl) saveIconEl.innerHTML = getIcon('save', 'icon');
    if (clearIconEl) clearIconEl.innerHTML = getIcon('clear', 'icon');
    if (floorIcon1El) floorIcon1El.innerHTML = getIcon('floor', 'icon');
    if (floorIcon2El) floorIcon2El.innerHTML = getIcon('floor', 'icon');
}

// Функция показа toast (определяем раньше, чтобы была доступна в init)
function showToast(message, type = 'success') {
    if (!toastEl) {
        // Fallback на console если toast еще не готов
        console.log(`[${type.toUpperCase()}] ${message}`);
        return;
    }
    
    toastEl.textContent = message;
    toastEl.className = `toast ${type}`;
    toastEl.classList.add('show');
    
    setTimeout(() => {
        toastEl.classList.remove('show');
    }, 3000);
}

// Инициализация
async function init() {
    console.log('=== INIT FUNCTION CALLED ===');
    console.log('userId check:', userId, 'Is valid?', userId && !isNaN(userId));
    
    if (!userId || isNaN(userId)) {
        console.error('❌ INIT BLOCKED: Invalid userId');
        showToast('Ошибка: не указан user_id', 'error');
        hideLoading(); // Важно: скрываем loading при ошибке
        return;
    }
    
    console.log('✅ INIT PROCEEDING with userId:', userId);
    initIcons();
    showLoading();
    
    try {
        console.log('=== CALLING fetchSeatsData ===');
        console.log('Parameters being passed:');
        console.log('  userId:', userId, 'Type:', typeof userId, 'Is NaN?', isNaN(userId));
        console.log('  ticketType:', ticketType, 'Type:', typeof ticketType);
        console.log('  quantity:', quantity, 'Type:', typeof quantity);
        
        // Загружаем данные о местах
        console.log('📡 Making API call to fetch seats data...');
        seatsData = await fetchSeatsData(userId, ticketType);
        console.log('✅ Successfully received seats data:', seatsData);
        
        // Проверяем, все ли места заняты
        let allSeatsOccupied = true;
        let totalSeats = 0;
        let occupiedSeats = 0;
        
        if (seatsData && seatsData.floors) {
            for (const floorKey in seatsData.floors) {
                const floor = seatsData.floors[floorKey];
                if (floor.sections) {
                    for (const sectionKey in floor.sections) {
                        const section = floor.sections[sectionKey];
                        totalSeats += section.total_seats || 0;
                        occupiedSeats += (section.occupied || []).length;
                        if ((section.occupied || []).length < section.total_seats) {
                            allSeatsOccupied = false;
                        }
                    }
                }
            }
        }
        
        // Если все места заняты, показываем сообщение
        if (allSeatsOccupied && totalSeats > 0) {
            console.log('⚠️ All seats are occupied, showing message');
            hideLoading();
            const tg = window.Telegram?.WebApp;
            if (tg) {
                tg.ready();
                tg.expand();
            }
            
            document.body.innerHTML = `
                <div style="padding: 40px 20px; text-align: center; color: #fff; background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; flex-direction: column; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin-bottom: 30px; box-shadow: 0 10px 30px rgba(245, 158, 11, 0.3);">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            <path d="M2 17L12 22L22 17" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            <path d="M2 12L12 17L22 12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </div>
                    <h2 style="color: #fff; font-size: 24px; font-weight: 600; margin-bottom: 15px; line-height: 1.3;">Все места раскуплены</h2>
                    <p style="color: #b0b0b0; font-size: 16px; line-height: 1.6; max-width: 300px; margin-bottom: 15px;">
                        К сожалению, все места для выбора уже заняты.
                    </p>
                    <p style="color: #f59e0b; font-size: 16px; line-height: 1.6; max-width: 300px; margin-bottom: 30px; font-weight: 600;">
                        Но вы всё ещё можете купить VIP билет без выбора конкретного места!
                    </p>
                    <button onclick="window.Telegram?.WebApp?.close()" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 32px; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); transition: transform 0.2s, box-shadow 0.2s;" onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 6px 20px rgba(102, 126, 234, 0.5)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(102, 126, 234, 0.4)';">
                        Закрыть и продолжить покупку
                    </button>
                </div>
            `;
            return;
        }
        
        mapRenderer.setSeatsData(seatsData);
        
        // Загружаем сохраненный выбор пользователя
        console.log('=== LOADING USER SELECTION ===');
        console.log('Calling getUserSelection with userId:', userId);
        const userSelection = await getUserSelection(userId);
        console.log('User selection result:', userSelection);
        
        if (userSelection && userSelection.selected_seats) {
            console.log('✅ Found saved selection:', userSelection.selected_seats);
            selectedSeats = userSelection.selected_seats;
            mapRenderer.setSelectedSeats(selectedSeats);
            updateSelectedCount();
            renderSelectedList();
        } else {
            console.log('ℹ️ No saved selection found');
        }
        
        // Устанавливаем количество мест
        console.log('Setting quantity display:', quantity);
        totalCountEl.textContent = quantity;
        
        // Рендерим карты
        console.log('=== RENDERING MAPS ===');
        renderMaps();
        
        // Устанавливаем обработчики событий
        console.log('=== SETTING UP EVENT LISTENERS ===');
        setupEventListeners();
        
        console.log('✅ INITIALIZATION COMPLETE');
        clearTimeout(loadingTimeout); // Отменяем таймаут
        hideLoading();
    } catch (error) {
        console.error('❌❌❌ INITIALIZATION ERROR ❌❌❌');
        console.error('Error type:', error.constructor.name);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        console.error('Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack
        });
        clearTimeout(loadingTimeout); // Отменяем таймаут
        showToast(`Ошибка загрузки: ${error.message}`, 'error');
        hideLoading();
    }
    
    console.log('=== MINI APP INITIALIZATION END ===');
}

function renderMaps() {
    mapRenderer.setCurrentFloor(1);
    mapRenderer.renderFloor(1);
    
    mapRenderer.setCurrentFloor(2);
    mapRenderer.renderFloor(2);
    
    // Устанавливаем обработчики для мест
    setupSeatListeners();
}

function setupSeatListeners() {
    const seats = document.querySelectorAll('.seat[data-selectable="true"]');
    seats.forEach(seat => {
        seat.addEventListener('click', handleSeatClick);
    });
}

function handleSeatClick(event) {
    const seat = event.currentTarget;
    const section = seat.getAttribute('data-section');
    const seatNumber = parseInt(seat.getAttribute('data-seat'));
    const floor = parseInt(seat.getAttribute('data-floor'));
    
    // Проверяем, не занято ли место
    if (seat.classList.contains('occupied')) {
        showToast('Это место уже занято', 'error');
        // Анимация тряски
        seat.style.animation = 'none';
        setTimeout(() => {
            seat.style.animation = 'shake 0.5s';
        }, 10);
        return;
    }
    
    // Проверяем, выбрано ли уже это место
    const existingIndex = selectedSeats.findIndex(s => 
        s.section === section && s.seat_number === seatNumber && s.floor === floor
    );
    
    if (existingIndex !== -1) {
        // Удаляем место из выбранных
        selectedSeats.splice(existingIndex, 1);
        seat.classList.remove('selected');
        seat.classList.add('free');
        showToast('Место удалено из выбора', 'success');
    } else {
        // Проверяем лимит
        if (selectedSeats.length >= quantity) {
            showToast(`Можно выбрать только ${quantity} мест(а)`, 'error');
            // Анимация тряски кнопки сохранения
            saveBtn.style.animation = 'none';
            setTimeout(() => {
                saveBtn.style.animation = 'shake 0.5s';
            }, 10);
            return;
        }
        
        // Добавляем место
        selectedSeats.push({
            floor: floor,
            section: section,
            seat_number: seatNumber,
            row: 1 // По умолчанию
        });
        
        seat.classList.remove('free');
        seat.classList.add('selected');
        showToast(`Место ${section}-${seatNumber} выбрано`, 'success');
        
        // Анимация появления
        seat.style.transform = 'scale(1.2)';
        setTimeout(() => {
            seat.style.transform = 'scale(1)';
        }, 200);
    }
    
    // Обновляем отображение
    mapRenderer.setSelectedSeats(selectedSeats);
    updateSelectedCount();
    renderSelectedList();
    updateSaveButton();
}

function updateSelectedCount() {
    const count = selectedSeats.length;
    selectedCountEl.textContent = count;
    if (selectedCountBadgeEl) {
        selectedCountBadgeEl.textContent = count;
        selectedCountBadgeEl.style.display = count > 0 ? 'block' : 'none';
    }
    updateProgress();
    updateEmptyState();
}

function updateProgress() {
    const progress = quantity > 0 ? (selectedSeats.length / quantity) * 100 : 0;
    if (progressFillEl) {
        progressFillEl.style.width = `${progress}%`;
    }
}

function updateEmptyState() {
    if (emptyStateEl) {
        if (selectedSeats.length === 0) {
            emptyStateEl.classList.add('active');
            selectedListEl.style.display = 'none';
        } else {
            emptyStateEl.classList.remove('active');
            selectedListEl.style.display = 'flex';
        }
    }
}

// showToast определена выше в коде

function renderSelectedList() {
    selectedListEl.innerHTML = '';
    
    selectedSeats.forEach((seat, index) => {
        const badge = document.createElement('div');
        badge.className = 'seat-badge';
        badge.innerHTML = `
            <span>${seat.section}-${seat.seat_number}</span>
            <span class="floor-indicator">${seat.floor} эт.</span>
            <span class="remove" data-index="${index}">${getIcon('close', 'icon')}</span>
        `;
        
        badge.querySelector('.remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removeSeat(index);
        });
        
        selectedListEl.appendChild(badge);
    });
}

function removeSeat(index) {
    const seat = selectedSeats[index];
    selectedSeats.splice(index, 1);
    
    // Обновляем визуальное состояние места на карте
    const seatEl = document.querySelector(
        `.seat[data-section="${seat.section}"][data-seat="${seat.seat_number}"][data-floor="${seat.floor}"]`
    );
    if (seatEl) {
        seatEl.classList.remove('selected');
        seatEl.classList.add('free');
    }
    
    mapRenderer.setSelectedSeats(selectedSeats);
    updateSelectedCount();
    renderSelectedList();
    updateSaveButton();
}

function updateSaveButton() {
    saveBtn.disabled = selectedSeats.length !== quantity;
}

function setupEventListeners() {
    // Переключение этажей
    floorButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const floor = parseInt(btn.getAttribute('data-floor'));
            switchFloor(floor);
        });
    });
    
    // Кнопка сохранения
    saveBtn.addEventListener('click', handleSave);
    
    // Кнопка очистки
    clearBtn.addEventListener('click', handleClear);
}

function switchFloor(floor) {
    if (currentFloor === floor) return;
    
    const oldFloor = currentFloor;
    currentFloor = floor;
    
    // Обновляем кнопки с анимацией
    floorButtons.forEach(btn => {
        if (parseInt(btn.getAttribute('data-floor')) === floor) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Плавное переключение карт
    const oldMap = document.getElementById(`map-floor-${oldFloor}`);
    const newMap = document.getElementById(`map-floor-${floor}`);
    
    if (oldMap && newMap) {
        oldMap.style.opacity = '0';
        oldMap.style.transform = 'translateX(-20px)';
        
        setTimeout(() => {
            oldMap.classList.remove('active');
            newMap.classList.add('active');
            newMap.style.opacity = '0';
            newMap.style.transform = 'translateX(20px)';
            
            setTimeout(() => {
                newMap.style.transition = 'opacity 0.3s, transform 0.3s';
                newMap.style.opacity = '1';
                newMap.style.transform = 'translateX(0)';
            }, 50);
        }, 200);
    }
    
    mapRenderer.setCurrentFloor(floor);
    
    setTimeout(() => {
        setupSeatListeners();
    }, 300);
}

async function handleSave() {
    if (selectedSeats.length !== quantity) {
        showToast(`Необходимо выбрать ${quantity} мест(а)`, 'error');
        return;
    }
    
    showLoading();
    
    try {
        await saveSeatSelection(userId, ticketType, quantity, selectedSeats);
        showToast('Места успешно сохранены!', 'success');
        
        // Анимация успеха
        saveBtn.style.background = 'linear-gradient(135deg, #4caf50 0%, #66bb6a 100%)';
        setTimeout(() => {
            tg.close();
        }, 1500);
    } catch (error) {
        console.error('Error saving seats:', error);
        showToast(`Ошибка при сохранении: ${error.message}`, 'error');
        hideLoading();
    }
}

function handleClear() {
    if (selectedSeats.length === 0) {
        return;
    }
    
    // Анимация очистки
    const badges = document.querySelectorAll('.seat-badge');
    badges.forEach((badge, index) => {
        setTimeout(() => {
            badge.style.animation = 'badgeDisappear 0.3s ease-out';
            setTimeout(() => {
                badge.remove();
            }, 300);
        }, index * 50);
    });
    
    // Очищаем визуально все места
    document.querySelectorAll('.seat.selected').forEach((seat, index) => {
        setTimeout(() => {
            seat.classList.remove('selected');
            seat.classList.add('free');
            seat.style.transform = 'scale(0.8)';
            setTimeout(() => {
                seat.style.transform = 'scale(1)';
            }, 200);
        }, index * 30);
    });
    
    selectedSeats = [];
    mapRenderer.setSelectedSeats(selectedSeats);
    
    setTimeout(() => {
        updateSelectedCount();
        renderSelectedList();
        updateSaveButton();
        showToast('Выбор очищен', 'success');
    }, badges.length * 50 + 300);
}

function showLoading() {
    if (loadingEl) {
        loadingEl.style.display = 'flex';
        loadingEl.classList.add('active');
    }
}

function hideLoading() {
    if (loadingEl) {
        loadingEl.classList.remove('active');
        // Небольшая задержка перед скрытием для плавности
        setTimeout(() => {
            if (loadingEl) {
                loadingEl.style.display = 'none';
            }
        }, 300);
    }
}

// Запускаем приложение
console.log('=== STARTING APP ===');
console.log('Calling init() function...');

// Оборачиваем в try-catch для обработки ошибок инициализации
try {
    init().catch(error => {
        console.error('❌ Unhandled error in init():', error);
        hideLoading();
        showToast('Ошибка инициализации приложения', 'error');
    });
} catch (error) {
    console.error('❌ Error calling init():', error);
    hideLoading();
    showToast('Ошибка запуска приложения', 'error');
}

console.log('init() function called (may be async)');

