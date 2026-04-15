# Script for creating folder structure and copying all files
Write-Host "Creating folder structure..."

# Create public folder if it doesn't exist
if (-not (Test-Path "public")) {
    New-Item -ItemType Directory -Path "public" | Out-Null
    Write-Host "Folder public created"
}

# Create public/fonts folder
if (-not (Test-Path "public\fonts")) {
    New-Item -ItemType Directory -Path "public\fonts" | Out-Null
    Write-Host "Folder public/fonts created"
}

# Create public/media folder
if (-not (Test-Path "public\media")) {
    New-Item -ItemType Directory -Path "public\media" | Out-Null
    Write-Host "Folder public/media created"
}

# Copy fonts
Write-Host "Copying fonts..."
if (Test-Path "PLANK___.TTF") {
    Copy-Item -Path "PLANK___.TTF" -Destination "public\fonts\" -Force
    Write-Host "  - PLANK___.TTF copied"
}
if (Test-Path "BormusSPDemo-Bold.otf") {
    Copy-Item -Path "BormusSPDemo-Bold.otf" -Destination "public\fonts\" -Force
    Write-Host "  - BormusSPDemo-Bold.otf copied"
}
if (Test-Path "Dikoe_disco.ttf") {
    Copy-Item -Path "Dikoe_disco.ttf" -Destination "public\fonts\" -Force
    Write-Host "  - Dikoe_disco.ttf copied"
}

# Copy media files
Write-Host "Copying media files..."
if (Test-Path "media") {
    Copy-Item -Path "media\*" -Destination "public\media\" -Recurse -Force
    Write-Host "  - Media files copied"
}

Write-Host ""
Write-Host "Done! All files copied to public folder"
Write-Host "Now you can run: npm run dev"
