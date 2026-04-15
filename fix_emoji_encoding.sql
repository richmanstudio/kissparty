-- Исправление кодировки для поддержки эмодзи
-- Выполните этот SQL скрипт в вашей базе данных

-- Убеждаемся, что таблица использует utf8mb4
ALTER TABLE `bot_settings` 
CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Обновляем существующие данные с эмодзи (если они были сохранены неправильно)
-- Замените на правильный текст с эмодзи
UPDATE `bot_settings` 
SET `setting_value` = '🎉 <b>Добро пожаловать в KISS PARTY!</b>

🎪 Мы рады приветствовать вас на нашем мероприятии!

Выберите действие:'
WHERE `setting_key` = 'main_menu_text';

-- Проверяем кодировку таблицы
SHOW CREATE TABLE `bot_settings`;

