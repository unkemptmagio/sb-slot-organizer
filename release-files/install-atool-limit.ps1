# Installs the optional AToolSlotLimit UE4SS mod (lifts ATOOL's 1000-slot limit).
# Usage: install-atool-limit.bat   (or: powershell -ExecutionPolicy Bypass -File install-atool-limit.ps1 -Game "D:\Games\StellarBlade")
param([string]$Game, [switch]$Force)
$ErrorActionPreference = "Stop"
try {
    if (-not $Game) { $Game = Read-Host "Path to the StellarBlade folder (the one that contains SB)" }
    $Game = $Game.Trim().Trim('"')
    $root = if (Test-Path -LiteralPath (Join-Path $Game "SB\Binaries")) { Join-Path $Game "SB" } else { $Game }
    $win64 = Join-Path $root "Binaries\Win64"
    $mods = @((Join-Path $win64 "ue4ss\Mods"), (Join-Path $win64 "Mods")) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $mods) { throw "UE4SS Mods folder not found under $win64 - install UE4SS first." }
    # The DLL links to C++ symbols of the UE4SS it was built for; other builds (e.g. Chrisr0 3.1.0-x, SB-UE4SS 3.1.6) cannot load it.
    $known = "E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE"   # RevOG SB-UE4SS 1.3
    $ueDll = Join-Path (Split-Path -Parent $mods) "UE4SS.dll"
    $have = if (Test-Path -LiteralPath $ueDll) { (Get-FileHash -LiteralPath $ueDll -Algorithm SHA256).Hash } else { "" }
    if ($have -ne $known -and -not $Force) {
        Write-Host "Your UE4SS is not the build this mod was made and tested for (RevOG SB-UE4SS 1.3)."
        Write-Host "On other builds the mod is not expected to load (UE4SS should skip it, but this was not tested in game), slots above 1000 will not work, and SlotOrganizer will keep everything within 1..1000."
        $ans = "" + (Read-Host "Install anyway? [y/N]")                  # no console / empty answer = no
        if ($ans.Trim() -notmatch '^(y|yes)$') { throw "cancelled (UE4SS build not verified)" }
    }
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


