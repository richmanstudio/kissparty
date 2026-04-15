-- SQL скрипт для добавления поля promoter_active в таблицу users
-- Это поле используется для отметки активных промоутеров

-- Проверяем существование колонки и добавляем её, если её нет
SET @dbname = DATABASE();
SET @tablename = 'users';
SET @columnname = 'promoter_active';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1', -- Колонка уже существует
  CONCAT('ALTER TABLE `', @tablename, '` ADD COLUMN `', @columnname, '` TINYINT(1) DEFAULT 0 COMMENT ''Статус активности промоутера (1 = активный, 0 = неактивный)''')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Создаем индекс для быстрого поиска активных промоутеров (если его еще нет)
SET @indexname = 'idx_promoter_active';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (index_name = @indexname)
  ) > 0,
  'SELECT 1', -- Индекс уже существует
  CONCAT('CREATE INDEX `', @indexname, '` ON `', @tablename, '` (`promoter_active`)')
));
PREPARE createIndexIfNotExists FROM @preparedStatement;
EXECUTE createIndexIfNotExists;
DEALLOCATE PREPARE createIndexIfNotExists;

