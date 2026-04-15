# Скрипт для копирования шрифтов в public/fonts
Write-Host "Создание структуры папок для шрифтов..."

# Создаем папку public если её нет
if (-not (Test-Path "public")) {
    New-Item -ItemType Directory -Path "public" | Out-Null
    Write-Host "Папка public создана"
}

# Создаем папку public/fonts
if (-not (Test-Path "public\fonts")) {
    New-Item -ItemType Directory -Path "public\fonts" | Out-Null
    Write-Host "Папка public/fonts создана"
}

# Копируем шрифты
Write-Host "Копирование шрифтов..."
if (Test-Path "PLANK___.TTF") {
    Copy-Item -Path "PLANK___.TTF" -Destination "public\fonts\" -Force
    Write-Host "  - PLANK___.TTF скопирован"
}
if (Test-Path "BormusSPDemo-Bold.otf") {
    Copy-Item -Path "BormusSPDemo-Bold.otf" -Destination "public\fonts\" -Force
    Write-Host "  - BormusSPDemo-Bold.otf скопирован"
}
if (Test-Path "Dikoe_disco.ttf") {
    Copy-Item -Path "Dikoe_disco.ttf" -Destination "public\fonts\" -Force
    Write-Host "  - Dikoe_disco.ttf скопирован"
}

Write-Host "`nШрифты успешно скопированы в public/fonts"

