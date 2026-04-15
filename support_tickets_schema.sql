-- SQL скрипт для создания таблицы тикетов поддержки

CREATE TABLE IF NOT EXISTS `support_tickets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_id` varchar(50) NOT NULL COMMENT 'Уникальный ID тикета',
  `user_id` bigint(20) NOT NULL COMMENT 'ID пользователя, создавшего тикет',
  `admin_id` bigint(20) DEFAULT NULL COMMENT 'ID админа, обрабатывающего тикет',
  `subject` varchar(255) DEFAULT NULL COMMENT 'Тема тикета',
  `status` enum('open','in_progress','closed','waiting') DEFAULT 'open' COMMENT 'Статус тикета',
  `priority` enum('low','medium','high','urgent') DEFAULT 'medium' COMMENT 'Приоритет тикета',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `closed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ticket_id` (`ticket_id`),
  KEY `user_id` (`user_id`),
  KEY `admin_id` (`admin_id`),
  KEY `status` (`status`),
  KEY `created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица сообщений в тикетах
CREATE TABLE IF NOT EXISTS `support_messages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_id` varchar(50) NOT NULL COMMENT 'ID тикета',
  `user_id` bigint(20) NOT NULL COMMENT 'ID отправителя',
  `message_text` text NOT NULL COMMENT 'Текст сообщения',
  `message_type` enum('text','photo','video','document','voice') DEFAULT 'text',
  `file_id` varchar(255) DEFAULT NULL COMMENT 'File ID для медиа файлов',
  `is_admin` tinyint(1) DEFAULT 0 COMMENT '1 если сообщение от админа, 0 если от пользователя',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ticket_id` (`ticket_id`),
  KEY `user_id` (`user_id`),
  KEY `created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

