// Отрисовка карт этажей

class MapRenderer {
    constructor() {
        this.seatsData = null;
        this.selectedSeats = [];
        this.currentFloor = 1;
    }

    setSeatsData(data) {
        this.seatsData = data;
    }

    setSelectedSeats(seats) {
        this.selectedSeats = seats;
    }

    setCurrentFloor(floor) {
        this.currentFloor = floor;
    }

    renderFloor(floor) {
        const floorKey = `floor_${floor}`;
        const svgId = `floor${floor}-svg`;
        const svg = document.getElementById(svgId);
        
        if (!svg || !this.seatsData || !this.seatsData.floors[floorKey]) {
            return;
        }

        // Очищаем SVG
        svg.innerHTML = '';

        // Добавляем премиум градиенты для мест
        this.addGradients(svg);

        const floorData = this.seatsData.floors[floorKey];
        const sections = floorData.sections;

        if (floor === 1) {
            this.renderFloor1(svg, sections);
        } else if (floor === 2) {
            this.renderFloor2(svg, sections);
        }
    }

    // Добавление премиум градиентов для SVG
    addGradients(svg) {
        // Проверяем, есть ли уже defs
        let defs = svg.querySelector('defs');
        if (!defs) {
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            svg.insertBefore(defs, svg.firstChild);
        }

        // Золотой градиент для выбранных мест
        const goldGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        goldGradient.setAttribute('id', 'goldGradient');
        goldGradient.setAttribute('x1', '0%');
        goldGradient.setAttribute('y1', '0%');
        goldGradient.setAttribute('x2', '100%');
        goldGradient.setAttribute('y2', '100%');

        const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop1.setAttribute('offset', '0%');
        stop1.setAttribute('stop-color', '#ffd700');
        stop1.setAttribute('stop-opacity', '1');

        const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop2.setAttribute('offset', '50%');
        stop2.setAttribute('stop-color', '#ffed4e');
        stop2.setAttribute('stop-opacity', '1');

        const stop3 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop3.setAttribute('offset', '100%');
        stop3.setAttribute('stop-color', '#ffa000');
        stop3.setAttribute('stop-opacity', '1');

        goldGradient.appendChild(stop1);
        goldGradient.appendChild(stop2);
        goldGradient.appendChild(stop3);
        defs.appendChild(goldGradient);

        // Радиальный градиент для свечения
        const glowGradient = document.createElementNS('http://www.w3.org/2000/svg', 'radialGradient');
        glowGradient.setAttribute('id', 'goldGlow');
        glowGradient.setAttribute('cx', '50%');
        glowGradient.setAttribute('cy', '50%');
        glowGradient.setAttribute('r', '50%');

        const glowStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        glowStop1.setAttribute('offset', '0%');
        glowStop1.setAttribute('stop-color', '#ffd700');
        glowStop1.setAttribute('stop-opacity', '0.8');

        const glowStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        glowStop2.setAttribute('offset', '100%');
        glowStop2.setAttribute('stop-color', '#ffd700');
        glowStop2.setAttribute('stop-opacity', '0');

        glowGradient.appendChild(glowStop1);
        glowGradient.appendChild(glowStop2);
        defs.appendChild(glowGradient);
    }

    renderFloor1(svg, sections) {
        // ============================================
        // ТОЧНАЯ СХЕМА 1 ЭТАЖА LOONA CLUB
        // ViewBox: 0 0 750 450
        // Без бара и проходов, места сеткой
        // ============================================
        
        // СЦЕНА - вверху по центру, горизонтальный прямоугольник
        this.addRoundedZone(svg, 180, 30, 420, 65, 'СЦЕНА', '#333', 25);
        
        // ТАНЦПОЛ - ниже сцены, большой ВЕРТИКАЛЬНЫЙ прямоугольник
        this.addRoundedZone(svg, 180, 110, 420, 180, 'ТАНЦПОЛ', '#222', 25);
        
        // БАР и ПРОХОДЫ убраны по требованию

        // ============================================
        // VIP СЕКЦИИ - точное клонирование с оригинального плана
        // ============================================
        
        // 1_1 - Правая сторона, верх (5 мест)
        // Верхние 2 места смещены влево, остальные 3 выровнены вертикально
        // Расположена справа от сцены, на уровне сцены
        // Метка "1_1" расположена выше верхнего места
        this.renderSection1_1(svg, sections['1_1'], 620, 50);
        
        // 1_2 - Правая сторона, середина (4 места, вертикально в один столбец)
        // Расположена ниже секции 1_1, в середине справа
        // Метка "1_2" расположена выше верхнего места
        // Танцпол: y=110, height=180, середина = 110 + 90 = 200
        this.renderSection(svg, sections['1_2'], 620, 200, 4, 'vertical', '1_2');
        
        // 1_3 - Правая сторона, низ (4 места, вертикально в один столбец)
        // Расположена ниже секции 1_2, внизу справа
        // Метка "1_3" расположена выше верхнего места
        // Танцпол заканчивается на y=290 (110+180), места начинаются на этом уровне
        this.renderSection(svg, sections['1_3'], 620, 290, 4, 'vertical', '1_3');
        
        // 1_4 - Левая сторона, низ (4 места, вертикально в один столбец)
        // Расположена слева внизу, под проходом слева
        // Метка "1_4" расположена выше верхнего места
        // Проход слева: y=340, height=40, значит заканчивается на y=380
        // Места начинаются сразу под проходом
        this.renderSection(svg, sections['1_4'], 50, 390, 4, 'vertical', '1_4');
    }
    
    // Специальная отрисовка секции 1_1 с особым расположением (верхние 2 места смещены влево)
    renderSection1_1(svg, sectionData, x, y) {
        if (!sectionData) return;
        
        const occupied = sectionData.occupied || [];
        const floor = this.currentFloor;
        
        // Метка секции "1_1" - расположена ВЫШЕ верхнего места (как на плане)
        // x позиция: по центру между смещенными и обычными местами
        // y позиция: выше первого места (y - 20px)
        this.addText(svg, x - 12, y - 20, '1_1', 'section-label');
        
        // Верхние 2 места смещены влево (согласно точному плану)
        // Смещение: 30px влево от основной позиции
        // Расстояние между местами: 50px по вертикали (как на 2 этаже)
        for (let i = 0; i < 2; i++) {
            const seatNum = i + 1;
            const seatX = x - 30; // Смещение влево на 30px
            const seatY = y + i * 50; // Расстояние 50px между местами
            this.addSeatWithFloor(svg, seatX, seatY, '1_1', seatNum, occupied.includes(seatNum), floor);
        }
        
        // Остальные 3 места в обычной позиции (выровнены вертикально по правому краю)
        // Начинаются сразу после верхних 2 мест, идут вертикально
        // Расстояние между местами: 50px (как на 2 этаже)
        for (let i = 2; i < 5; i++) {
            const seatNum = i + 1;
            const seatX = x; // Основная позиция по правому краю
            // Продолжаем вертикальную линию: 2 места * 50px = 100px от начала
            const seatY = y + 100 + (i - 2) * 50; // 100px от начала + смещение для остальных
            this.addSeatWithFloor(svg, seatX, seatY, '1_1', seatNum, occupied.includes(seatNum), floor);
        }
    }
    
    // Добавление зоны с закругленными углами (премиум стиль с золотой обводкой)
    addRoundedZone(svg, x, y, width, height, label, fill, radius = 10) {
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', width);
        rect.setAttribute('height', height);
        rect.setAttribute('rx', radius);
        rect.setAttribute('ry', radius);
        rect.setAttribute('fill', fill);
        rect.setAttribute('stroke', '#ffd700'); // Золотая обводка как на плане
        rect.setAttribute('stroke-width', '2');
        rect.setAttribute('opacity', '0.8');
        svg.appendChild(rect);

        if (label) {
            // Текст по центру зоны
            this.addText(svg, x + width / 2, y + height / 2, label, 'zone-label');
        }
    }

    renderFloor2(svg, sections) {
        // Центральные зоны
        this.addZone(svg, 200, 50, 400, 80, 'СЦЕНА', '#333');
        this.addZone(svg, 200, 140, 400, 200, 'ТАНЦ ПОЛ', '#222');

        // Секции мест вокруг сцены и танцпола
        // 21 - Верхний правый (6 мест, 3 ряда × 2)
        this.renderSection(svg, sections['21'], 650, 100, 6, 'grid', '21', 3, 2);
        
        // 22 - Правый верхний (6 мест, 3 ряда × 2)
        this.renderSection(svg, sections['22'], 650, 250, 6, 'grid', '22', 3, 2);
        
        // 23 - Правый средний (2 места)
        this.renderSection(svg, sections['23'], 650, 400, 2, 'horizontal', '23');
        
        // 24 - Правый средний нижний (2 места)
        this.renderSection(svg, sections['24'], 650, 480, 2, 'horizontal', '24');
        
        // 25 - Правый нижний (2 места)
        this.renderSection(svg, sections['25'], 650, 560, 2, 'horizontal', '25');
        
        // 26 - Нижний центральный (2 места)
        this.renderSection(svg, sections['26'], 350, 600, 2, 'horizontal', '26');
        
        // 27 - Нижний левый (7 мест, 4 + 3)
        this.renderSection(svg, sections['27'], 50, 600, 7, 'mixed', '27', 2, [4, 3]);
        
        // 28 - Левый нижний (3 места: 2 рядом, 1 ниже слева)
        this.renderSection(svg, sections['28'], 50, 480, 3, 'mixed', '28', 2, [2, 1]);
        
        // 29 - Левый верхний (6 мест, 3 ряда × 2)
        this.renderSection(svg, sections['29'], 50, 100, 6, 'grid', '29', 3, 2);
    }

    renderSection(svg, sectionData, x, y, totalSeats, layout, sectionId, rows = 1, seatsPerRow = null) {
        if (!sectionData) return;

        const occupied = sectionData.occupied || [];
        // Метка секции ВЫШЕ первого места (как на плане)
        const sectionLabel = this.addText(svg, x, y - 20, sectionId, 'section-label');

        let seatX = x;
        let seatY = y;
        let seatIndex = 1;

        if (layout === 'vertical') {
            // Вертикальное расположение - точное клонирование с оригинального плана
            // Все места в один столбец, равномерное расстояние
            for (let i = 0; i < totalSeats; i++) {
                this.addSeat(svg, seatX, seatY, sectionId, seatIndex, occupied.includes(seatIndex));
                seatY += 45; // Расстояние 45px между местами (как на оригинальном плане)
                seatIndex++;
            }
        } else if (layout === 'horizontal') {
            // Горизонтальное расположение
            for (let i = 0; i < totalSeats; i++) {
                this.addSeat(svg, seatX, seatY, sectionId, seatIndex, occupied.includes(seatIndex));
                seatX += 50;
                seatIndex++;
            }
        } else if (layout === 'grid') {
            // Сетка (rows × seatsPerRow)
            const actualRows = rows || 3;
            const actualSeatsPerRow = seatsPerRow || 2;
            for (let row = 0; row < actualRows; row++) {
                for (let col = 0; col < actualSeatsPerRow; col++) {
                    this.addSeat(svg, seatX + col * 50, seatY + row * 50, sectionId, seatIndex, occupied.includes(seatIndex));
                    seatIndex++;
                }
            }
        } else if (layout === 'mixed') {
            // Смешанное расположение (для секции 27)
            if (Array.isArray(seatsPerRow)) {
                let currentY = seatY;
                seatsPerRow.forEach((seatsInRow, rowIndex) => {
                    let currentX = seatX;
                    for (let i = 0; i < seatsInRow; i++) {
                        this.addSeat(svg, currentX, currentY, sectionId, seatIndex, occupied.includes(seatIndex));
                        currentX += 50;
                        seatIndex++;
                    }
                    currentY += 50;
                });
            }
        }
    }

    // Вспомогательная функция для добавления места с указанием этажа
    addSeatWithFloor(svg, x, y, section, seatNumber, isOccupied, floor) {
        const seatId = `${section}-${seatNumber}`;
        const isSelected = this.selectedSeats.some(s => 
            s.section === section && s.seat_number === seatNumber && s.floor === floor
        );

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        // Адаптивный размер радиуса в зависимости от экрана
        const isMobile = window.innerWidth <= 480;
        const radius = isMobile ? 14 : 16;
        circle.setAttribute('r', radius);
        circle.setAttribute('class', `seat ${isOccupied ? 'occupied' : isSelected ? 'selected' : 'free'}`);
        circle.setAttribute('data-section', section);
        circle.setAttribute('data-seat', seatNumber);
        circle.setAttribute('data-floor', floor);
        
        if (!isOccupied) {
            circle.setAttribute('data-selectable', 'true');
        }

        svg.appendChild(circle);

        // Номер места
        const text = this.addText(svg, x, y + 5, seatNumber.toString(), 'seat-number');
        text.setAttribute('font-size', '11');
        text.setAttribute('fill', isOccupied ? '#fff' : '#000');
    }

    addSeat(svg, x, y, section, seatNumber, isOccupied) {
        // Используем вспомогательную функцию с текущим этажом
        this.addSeatWithFloor(svg, x, y, section, seatNumber, isOccupied, this.currentFloor);
    }

    addZone(svg, x, y, width, height, label, fill) {
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', width);
        rect.setAttribute('height', height);
        rect.setAttribute('fill', fill);
        rect.setAttribute('stroke', '#555');
        rect.setAttribute('stroke-width', '2');
        svg.appendChild(rect);

        if (label) {
            this.addText(svg, x + width / 2, y + height / 2, label, 'zone-label');
        }
    }

    addText(svg, x, y, text, className) {
        const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textEl.setAttribute('x', x);
        textEl.setAttribute('y', y);
        textEl.setAttribute('class', className);
        textEl.textContent = text;
        svg.appendChild(textEl);
        return textEl;
    }
}

