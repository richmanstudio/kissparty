-- Таблица проходок (guest passes)
CREATE TABLE IF NOT EXISTS `guest_passes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `ticket_type` enum('regular','vip','vip_standing','couple') NOT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1 COMMENT 'Количество проходок',
  `used_count` int(11) DEFAULT 0 COMMENT 'Количество использованных проходок',
  `is_unlimited` tinyint(1) DEFAULT 0 COMMENT 'Бессрочная проходка (1) или с датой окончания (0)',
  `expires_at` date DEFAULT NULL COMMENT 'Дата окончания действия (если не бессрочная)',
  `created_by` bigint(20) DEFAULT NULL COMMENT 'ID админа, создавшего проходку',
  `notes` text DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `ticket_type` (`ticket_type`),
  KEY `active` (`active`),
  KEY `expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица использования проходок
CREATE TABLE IF NOT EXISTS `guest_pass_usage` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `guest_pass_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `ticket_id` int(11) DEFAULT NULL COMMENT 'ID созданного билета',
  `used_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `guest_pass_id` (`guest_pass_id`),
  KEY `user_id` (`user_id`),
  KEY `ticket_id` (`ticket_id`),
  FOREIGN KEY (`guest_pass_id`) REFERENCES `guest_passes`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

