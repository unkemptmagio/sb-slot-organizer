# Installs the optional AToolSlotLimit UE4SS mod (lifts ATOOL's 1000-slot limit).
# Usage: install-atool-limit.bat   (or: powershell -ExecutionPolicy Bypass -File install-atool-limit.ps1 -Game "D:\Games\StellarBlade")
param([string]$Game)
$ErrorActionPreference = "Stop"
try {
    if (-not $Game) { $Game = Read-Host "Path to the StellarBlade folder (the one that contains SB)" }
    $Game = $Game.Trim().Trim('"')
    $root = if (Test-Path -LiteralPath (Join-Path $Game "SB\Binaries")) { Join-Path $Game "SB" } else { $Game }
    $win64 = Join-Path $root "Binaries\Win64"
    $mods = @((Join-Path $win64 "ue4ss\Mods"), (Join-Path $win64 "Mods")) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $mods) { throw "UE4SS Mods folder not found under $win64 - install UE4SS first." }
    $src = Join-Path $PSScriptRoot "AToolSlotLimit"
    if (-not (Test-Path -LiteralPath (Join-Path $src "dlls\main.dll"))) { throw "AToolSlotLimit\dlls\main.dll is missing from this package." }
    $dest = Join-Path $mods "AToolSlotLimit"
    New-Item -ItemType Directory -Force (Join-Path $dest "dlls") | Out-Null
    Copy-Item -LiteralPath (Join-Path $src "dlls\main.dll") -Force -Destination (Join-Path $dest "dlls\main.dll")
    foreach ($f in "enabled.txt", "config.txt") {                      # never overwrite the user's own settings
        if (-not (Test-Path -LiteralPath (Join-Path $dest $f))) { Copy-Item -LiteralPath (Join-Path $src $f) -Destination (Join-Path $dest $f) }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dest "dlls\main.dll"))) { throw "copy failed" }
    Write-Host "Installed to $dest"
    Write-Host "Settings: config.txt (limit=9999), enabled.txt (1 = on, 0 = off). Delete the folder to uninstall."
    Write-Host "This DLL is built against one UE4SS build; if the game crashes at launch, delete the folder."
} catch {
    Write-Host "Not installed: $($_.Exception.Message)  (close the game first if a file is locked)"
    exit 1
}


