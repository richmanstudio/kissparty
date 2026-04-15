-- SQL Schema для Mini App выбора мест
-- База данных: cw998871_kisspar

-- Таблица временного хранения выбранных мест
CREATE TABLE IF NOT EXISTS `seat_selections` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `ticket_type` enum('regular','vip','vip_standing','couple') NOT NULL,
  `quantity` int(11) NOT NULL,
  `selected_seats` text NOT NULL COMMENT 'JSON array of selected seats',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  KEY `expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Обновление таблицы tickets - добавление полей для мест
-- Проверяем существование колонок перед добавлением
SET @dbname = DATABASE();
SET @tablename = 'tickets';
SET @columnname1 = 'seat_floor';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname1)
  ) > 0,
  "SELECT 'Column seat_floor already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname1, " tinyint(1) DEFAULT NULL COMMENT 'Этаж места (1 или 2)'")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @columnname2 = 'seat_section';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname2)
  ) > 0,
  "SELECT 'Column seat_section already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname2, " varchar(10) DEFAULT NULL COMMENT 'Секция места'")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @columnname3 = 'seat_number';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname3)
  ) > 0,
  "SELECT 'Column seat_number already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname3, " int(11) DEFAULT NULL COMMENT 'Номер места'")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @columnname4 = 'seat_row';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname4)
  ) > 0,
  "SELECT 'Column seat_row already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname4, " int(11) DEFAULT NULL COMMENT 'Ряд места'")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Добавление индекса для быстрого поиска мест
SET @indexname = 'seat_location';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (index_name = @indexname)
  ) > 0,
  "SELECT 'Index seat_location already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD KEY ", @indexname, " (`seat_floor`, `seat_section`, `seat_number`)")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

