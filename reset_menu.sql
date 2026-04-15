-- Сброс главного меню к значениям по умолчанию
-- Выполните этот SQL запрос, если главное меню вызывает ошибки

UPDATE `bot_settings` 
SET `setting_value` = '🎉 <b>Добро пожаловать в KISS PARTY!</b>

🎪 Мы рады приветствовать вас на нашем мероприятии!

Выберите действие:'
WHERE `setting_key` = 'main_menu_text';

UPDATE `bot_settings` 
SET `setting_value` = NULL
WHERE `setting_key` = 'main_menu_image';

