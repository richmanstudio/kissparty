# Скрипт для копирования медиа файлов в public/media
Write-Host "Создание структуры папок для медиа файлов..."

# Создаем папку public если её нет
if (-not (Test-Path "public")) {
    New-Item -ItemType Directory -Path "public" | Out-Null
    Write-Host "Папка public создана"
}

# Создаем папку public/media
if (-not (Test-Path "public\media")) {
    New-Item -ItemType Directory -Path "public\media" | Out-Null
    Write-Host "Папка public/media создана"
}

# Копируем медиа файлы
if (Test-Path "media") {
    Copy-Item -Path "media\*" -Destination "public\media\" -Recurse -Force
    Write-Host "Медиа файлы успешно скопированы в public/media"
} else {
    Write-Host "Папка media не найдена"
}

