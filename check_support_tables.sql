-- SQL скрипт для проверки таблиц тикетов поддержки

-- Проверка существования таблицы support_tickets
SELECT 'Проверка таблицы support_tickets:' as info;
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ Таблица support_tickets существует'
        ELSE '❌ Таблица support_tickets НЕ существует'
    END as status
FROM information_schema.tables 
WHERE table_schema = DATABASE() 
AND table_name = 'support_tickets';

-- Показываем структуру таблицы support_tickets
SELECT 'Структура таблицы support_tickets:' as info;
DESCRIBE support_tickets;

-- Проверка существования таблицы support_messages
SELECT 'Проверка таблицы support_messages:' as info;
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ Таблица support_messages существует'
        ELSE '❌ Таблица support_messages НЕ существует'
    END as status
FROM information_schema.tables 
WHERE table_schema = DATABASE() 
AND table_name = 'support_messages';

-- Показываем структуру таблицы support_messages
SELECT 'Структура таблицы support_messages:' as info;
DESCRIBE support_messages;

-- Показываем количество записей
SELECT 'Количество записей:' as info;
SELECT 
    (SELECT COUNT(*) FROM support_tickets) as tickets_count,
    (SELECT COUNT(*) FROM support_messages) as messages_count;

