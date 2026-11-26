# Installs the optional AToolSlotLimit UE4SS mod (lifts ATOOL's 1000-slot limit).
# TESTED ONLY WITH: RevOG SB-UE4SS 1.3 (ue4ss\UE4SS.dll SHA-256 E0CC51CE...DABE). Any other UE4SS is refused.
# Usage: install-atool-limit.bat   (or: powershell -ExecutionPolicy Bypass -File install-atool-limit.ps1 -Game "D:\Games\StellarBlade")
# -InstallUnverified installs on an unsupported UE4SS anyway (it can crash the game at launch).
param([string]$Game, [switch]$InstallUnverified)
$ErrorActionPreference = "Stop"
try {
    if (-not $Game) { $Game = "" + (Read-Host "Path to the StellarBlade folder (the one that contains SB)") }
    $Game = $Game.Trim().Trim('"')
    if (-not $Game) { throw "no game folder given (run with -Game <path to StellarBlade>)" }
    $root = if (Test-Path -LiteralPath (Join-Path $Game "SB\Binaries")) { Join-Path $Game "SB" } else { $Game }
    $win64 = Join-Path $root "Binaries\Win64"
    $mods = @((Join-Path $win64 "ue4ss\Mods"), (Join-Path $win64 "Mods")) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $mods) { throw "UE4SS Mods folder not found under $win64 - install UE4SS first." }
    $known = "E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE"   # RevOG SB-UE4SS 1.3, the only build this mod was tested with
    $ueDll = Join-Path (Split-Path -Parent $mods) "UE4SS.dll"
    $have = if (Test-Path -LiteralPath $ueDll) { (Get-FileHash -LiteralPath $ueDll -Algorithm SHA256).Hash } else { "" }
    if ($have -ne $known) {
        Write-Host "This mod was tested ONLY with RevOG SB-UE4SS 1.3 (ue4ss\UE4SS.dll SHA-256 $known)."
        if ($have) { Write-Host "Your UE4SS.dll is different, so the mod is unsupported on it and may crash the game at launch (a test on Chrisr0/RE-UE4SS 3.1.0-5 crashed). Slots above 1000 will not work and SlotOrganizer keeps everything within 1..1000." }
        else { Write-Host "No UE4SS.dll was found at $ueDll, so the mod cannot be checked and is unsupported here." }
        if (-not $InstallUnverified) { throw "refused: unsupported UE4SS build (-InstallUnverified installs it anyway, at your own risk)" }
    }
    $src = Join-Path $PSScriptRoot "AToolSlotLimit"
    $dll = Join-Path $src "dlls\main.dll"
    if (-not (Test-Path -LiteralPath $dll)) { throw "$dll is missing from this package." }
    $dest = Join-Path $mods "AToolSlotLimit"
    New-Item -ItemType Directory -Force (Join-Path $dest "dlls") | Out-Null
    Copy-Item -LiteralPath $dll -Force -Destination (Join-Path $dest "dlls\main.dll")
    foreach ($f in "enabled.txt", "config.txt") {                      # never overwrite the user's own settings
        if (-not (Test-Path -LiteralPath (Join-Path $dest $f))) { Copy-Item -LiteralPath (Join-Path $src $f) -Destination (Join-Path $dest $f) }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dest "dlls\main.dll"))) { throw "copy failed" }
    if ($have -eq $known) { Write-Host "Installed to $dest (your UE4SS is RevOG SB-UE4SS 1.3, the tested one)" }
    else { Write-Host "Installed to $dest ON AN UNSUPPORTED UE4SS (-InstallUnverified): it may crash the game at launch - delete the folder if it does." }
    if ((Test-Path -LiteralPath (Join-Path $dest "enabled.txt")) -and ((Get-Content -LiteralPath (Join-Path $dest "enabled.txt") -Raw).Trim() -eq "0")) { Write-Host "Note: enabled.txt is 0, so the mod stays OFF until you set it to 1." }
    Write-Host "Settings: config.txt (limit=NNNN; the default package says 9999), enabled.txt (1 = on, 0 = off). Delete the folder to uninstall."
    Write-Host "If the game crashes at launch after this, delete the folder."
} catch {
    $hint = if ($_.Exception -is [System.IO.IOException] -or $_.Exception -is [System.UnauthorizedAccessException]) { "  (close the game first if a file is locked)" } else { "" }
    Write-Host "Not installed: $($_.Exception.Message)$hint"
    exit 1
}
