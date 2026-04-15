-- Обновление базы данных для модернизации бота
-- Выполните этот файл в вашей БД для добавления новых таблиц и функций

-- Таблица настроек бота
CREATE TABLE IF NOT EXISTS `bot_settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) NOT NULL,
  `setting_value` text DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Вставка начальных настроек бота
INSERT INTO `bot_settings` (`setting_key`, `setting_value`) VALUES
('bot_access_enabled', '1'),
('sales_enabled', '1'),
('bonuses_promocodes_enabled', '1'),
('main_menu_text', '🎉 <b>Добро пожаловать в KISS PARTY!</b>\n\n🎪 Мы рады приветствовать вас на нашем мероприятии!\n\nВыберите действие:'),
('main_menu_image', NULL)
ON DUPLICATE KEY UPDATE `setting_value`=VALUES(`setting_value`);

-- Таблица для публикаций (постов)
CREATE TABLE IF NOT EXISTS `broadcasts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `admin_id` bigint(20) NOT NULL,
  `message_type` enum('text','photo','video','voice','document') NOT NULL DEFAULT 'text',
  `text` text DEFAULT NULL,
  `file_id` varchar(255) DEFAULT NULL,
  `sent_count` int(11) DEFAULT 0,
  `failed_count` int(11) DEFAULT 0,
  `status` enum('pending','sending','completed','failed') DEFAULT 'pending',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `admin_id` (`admin_id`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

