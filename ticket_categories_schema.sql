-- Таблица категорий билетов
CREATE TABLE IF NOT EXISTS `ticket_categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL COMMENT 'Уникальный код категории (например: regular, vip)',
  `name` varchar(255) NOT NULL COMMENT 'Название категории для отображения',
  `description` text DEFAULT NULL COMMENT 'Описание категории',
  `base_price` decimal(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Базовая цена',
  `discounted_price` decimal(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Цена со скидкой',
  `limit` int(11) DEFAULT 0 COMMENT 'Лимит билетов (0 = безлимит)',
  `sold_count` int(11) DEFAULT 0 COMMENT 'Количество проданных билетов',
  `allows_seat_selection` tinyint(1) DEFAULT 0 COMMENT 'Разрешен ли выбор мест (для VIP)',
  `is_active` tinyint(1) DEFAULT 1 COMMENT 'Активна ли категория',
  `sort_order` int(11) DEFAULT 0 COMMENT 'Порядок сортировки',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `is_active` (`is_active`),
  KEY `sort_order` (`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Вставка существующих категорий
INSERT INTO `ticket_categories` (`code`, `name`, `description`, `base_price`, `discounted_price`, `limit`, `allows_seat_selection`, `sort_order`) VALUES
('regular', 'Обычный билет', 'Стандартный билет на мероприятие', 550.00, 550.00, 600, 0, 1),
('vip', 'VIP билет', 'VIP билет с выбором места', 850.00, 850.00, 80, 1, 2),
('vip_standing', 'VIP стоячий', 'VIP билет без места', 850.00, 850.00, 20, 0, 3),
('couple', 'Парный билет', 'Билет для пары', 990.00, 990.00, 50, 0, 4)
ON DUPLICATE KEY UPDATE 
  `name`=VALUES(`name`),
  `base_price`=VALUES(`base_price`),
  `discounted_price`=VALUES(`discounted_price`),
  `limit`=VALUES(`limit`);

