-- SQL Schema для функции "Поиск пары"
-- Добавьте эти таблицы в базу данных

-- Таблица анкет пользователей
CREATE TABLE IF NOT EXISTS `dating_profiles` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `photo_file_id` varchar(255) NOT NULL,
  `gender` enum('male','female') NOT NULL COMMENT 'Пол пользователя',
  `looking_for` enum('male','female','both') NOT NULL COMMENT 'Кого ищет: парня, девушку, оба',
  `active` tinyint(1) DEFAULT 1 COMMENT 'Активна ли анкета',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  KEY `active` (`active`),
  KEY `gender` (`gender`),
  KEY `looking_for` (`looking_for`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица лайков/дизлайков
CREATE TABLE IF NOT EXISTS `dating_likes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `from_user_id` bigint(20) NOT NULL COMMENT 'Кто поставил лайк/дизлайк',
  `to_user_id` bigint(20) NOT NULL COMMENT 'Кому поставили лайк/дизлайк',
  `action` enum('like','dislike') NOT NULL COMMENT 'Лайк или дизлайк',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_like` (`from_user_id`, `to_user_id`),
  KEY `from_user_id` (`from_user_id`),
  KEY `to_user_id` (`to_user_id`),
  KEY `action` (`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица мэтчей
CREATE TABLE IF NOT EXISTS `dating_matches` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user1_id` bigint(20) NOT NULL,
  `user2_id` bigint(20) NOT NULL,
  `matched_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `notified_user1` tinyint(1) DEFAULT 0 COMMENT 'Уведомлен ли первый пользователь',
  `notified_user2` tinyint(1) DEFAULT 0 COMMENT 'Уведомлен ли второй пользователь',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_match` (`user1_id`, `user2_id`),
  KEY `user1_id` (`user1_id`),
  KEY `user2_id` (`user2_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

