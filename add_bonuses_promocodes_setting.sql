-- Добавление настройки оплаты бонусами и промокодами
-- Выполните в БД для включения функции переключения

INSERT INTO `bot_settings` (`setting_key`, `setting_value`) VALUES
('bonuses_promocodes_enabled', '1')
ON DUPLICATE KEY UPDATE `setting_value`=VALUES(`setting_value`);
