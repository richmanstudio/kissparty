-- SQL Schema для KISS PARTY PAY BOT
-- База данных: cw998871_kisspar
-- Пароль: P5V8yaRJ

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS `users` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL UNIQUE,
  `username` varchar(255) DEFAULT NULL,
  `first_name` varchar(255) DEFAULT NULL,
  `last_name` varchar(255) DEFAULT NULL,
  `role` enum('user','admin','moderator','promoter') DEFAULT 'user',
  `promo_code` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица бонусов
CREATE TABLE IF NOT EXISTS `bonuses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `bonus_balance` decimal(10,2) DEFAULT 0.00,
  `last_updated` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_order_id` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  KEY `bonus_balance` (`bonus_balance`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица рефералов
CREATE TABLE IF NOT EXISTS `referrals` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `referral_code` varchar(50) NOT NULL,
  `referrer_id` bigint(20) DEFAULT NULL,
  `referrals_count` int(11) DEFAULT 0,
  `referral_earnings` decimal(10,2) DEFAULT 0.00,
  `referral_bonus_paid` tinyint(1) DEFAULT 0,
  `first_purchase_discount_applied` tinyint(1) DEFAULT 0,
  `first_purchase_date` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  UNIQUE KEY `referral_code` (`referral_code`),
  KEY `referrer_id` (`referrer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица промокодов
CREATE TABLE IF NOT EXISTS `promocodes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `type` enum('percentage','fixed') NOT NULL,
  `value` decimal(10,2) NOT NULL,
  `ticket_types` text DEFAULT NULL COMMENT 'JSON array of ticket types',
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `max_uses` int(11) DEFAULT 0 COMMENT '0 = unlimited',
  `used_count` int(11) DEFAULT 0,
  `active` tinyint(1) DEFAULT 1,
  `min_amount` decimal(10,2) DEFAULT 0.00,
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `active` (`active`),
  KEY `start_date` (`start_date`),
  KEY `end_date` (`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица билетов
CREATE TABLE IF NOT EXISTS `tickets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_code` varchar(100) NOT NULL UNIQUE,
  `user_id` bigint(20) NOT NULL,
  `ticket_type` enum('regular','vip','vip_standing','couple') NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `bonus_used` decimal(10,2) DEFAULT 0.00,
  `bonus_earned` decimal(10,2) DEFAULT 0.00,
  `referral_bonus_earned` decimal(10,2) DEFAULT 0.00,
  `promo_code` varchar(50) DEFAULT NULL,
  `order_id` varchar(50) NOT NULL,
  `qr_file_id` varchar(255) DEFAULT NULL,
  `wants_to_meet` enum('yes','no') DEFAULT 'no',
  `status` enum('active','used','cancelled') DEFAULT 'active',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `order_id` (`order_id`),
  KEY `ticket_type` (`ticket_type`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица настроек цен
CREATE TABLE IF NOT EXISTS `price_settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_type` enum('regular','vip','vip_standing','couple') NOT NULL,
  `base_price` decimal(10,2) NOT NULL,
  `discounted_price` decimal(10,2) NOT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ticket_type` (`ticket_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица промо-билетов
CREATE TABLE IF NOT EXISTS `promo_tickets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `ticket_type` enum('regular','vip','vip_standing','couple') NOT NULL,
  `purpose` varchar(255) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `status` enum('active','used','cancelled') DEFAULT 'active',
  `used_by` bigint(20) DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица акций
CREATE TABLE IF NOT EXISTS `promotions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `start_date` datetime DEFAULT NULL,
  `end_date` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `active` (`active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица ограниченных предложений
CREATE TABLE IF NOT EXISTS `limited_offers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `ticket_type` enum('regular','vip','vip_standing','couple') DEFAULT NULL,
  `discount_percent` decimal(5,2) DEFAULT NULL,
  `max_quantity` int(11) DEFAULT NULL,
  `sold_quantity` int(11) DEFAULT 0,
  `start_date` datetime DEFAULT NULL,
  `end_date` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `active` (`active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица логов бонусов
CREATE TABLE IF NOT EXISTS `bonus_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `operation` enum('add','subtract') NOT NULL,
  `bonus_amount` decimal(10,2) NOT NULL,
  `old_balance` decimal(10,2) NOT NULL,
  `new_balance` decimal(10,2) NOT NULL,
  `order_id` varchar(50) DEFAULT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица логов реферальных бонусов
CREATE TABLE IF NOT EXISTS `referral_bonus_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `referrer_id` bigint(20) NOT NULL,
  `referred_user_id` bigint(20) NOT NULL,
  `purchase_amount` decimal(10,2) NOT NULL,
  `referrer_bonus` decimal(10,2) NOT NULL,
  `referred_bonus` decimal(10,2) NOT NULL,
  `referrer_new_balance` decimal(10,2) NOT NULL,
  `referred_new_balance` decimal(10,2) NOT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `referrer_id` (`referrer_id`),
  KEY `referred_user_id` (`referred_user_id`),
  KEY `timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица состояний пользователей (для FSM)
CREATE TABLE IF NOT EXISTS `user_states` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `state` varchar(100) DEFAULT NULL,
  `data` text DEFAULT NULL COMMENT 'JSON data',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Заявки на ручную оплату (переводом на карту)
CREATE TABLE IF NOT EXISTS `payment_requests` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` varchar(64) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `ticket_type` varchar(64) NOT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1,
  `total_price` decimal(10,2) NOT NULL,
  `promo_code` varchar(50) DEFAULT NULL,
  `bonus_used` decimal(10,2) NOT NULL DEFAULT 0.00,
  `status` enum('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `payload` longtext DEFAULT NULL COMMENT 'JSON snapshot of order data',
  `admin_id` bigint(20) DEFAULT NULL,
  `admin_comment` text DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_id` (`order_id`),
  KEY `user_id` (`user_id`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица настроек бота
CREATE TABLE IF NOT EXISTS `bot_settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) NOT NULL,
  `setting_value` text DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Вставка начальных данных цен
INSERT INTO `price_settings` (`ticket_type`, `base_price`, `discounted_price`) VALUES
('regular', 550.00, 550.00),
('vip', 850.00, 850.00),
('vip_standing', 850.00, 850.00),
('couple', 950.00, 950.00)
ON DUPLICATE KEY UPDATE `base_price`=VALUES(`base_price`), `discounted_price`=VALUES(`discounted_price`);

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

