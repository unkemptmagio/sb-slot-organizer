# Installs the optional AToolSlotLimit UE4SS mod (lifts ATOOL's 1000-slot limit), choosing the DLL that matches your UE4SS build.
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
    # The DLL links to C++ symbols of the UE4SS it was built for, so there is one DLL per UE4SS line (UE4SS.dll SHA-256 -> build folder).
    $builds = @{
        "E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE" = "revog-1.3"        # RevOG SB-UE4SS 1.3 (tested in game)
        "2E7B3E7E8760263B99AD45FD3EE3C35930E43D8C38D15B7E41685E8A3C26E2C4" = "chrisr0-3.1.0"     # Chrisr0/RE-UE4SS 3.1.0-4
        "458839B77D05255F228045210270B01597D47FC83004CD47937126B2409A26EE" = "chrisr0-3.1.0"     # Chrisr0/RE-UE4SS 3.1.0-5
        "F3F0229E8D046824C6D71DB256F1C9BBBDA9652A193643C28FA4E6C329E17670" = "chrisr0-3.1.0"     # Chrisr0/RE-UE4SS 3.1.0-6 = SB-UE4SS 3.1.6
    }
    $ueDll = Join-Path (Split-Path -Parent $mods) "UE4SS.dll"
    $have = if (Test-Path -LiteralPath $ueDll) { (Get-FileHash -LiteralPath $ueDll -Algorithm SHA256).Hash } else { "" }
    $build = $builds[$have]
    if (-not $build) {
        Write-Host "Your UE4SS is not a build this mod was made for (RevOG SB-UE4SS 1.3, Chrisr0 RE-UE4SS 3.1.0-4/5/6)."
        Write-Host "The mod is not expected to load on it (UE4SS should skip it, but this was not tested in game); slots above 1000 will not work and SlotOrganizer keeps everything within 1..1000."
        if (-not $Force) { $ans = "" + (Read-Host "Install the RevOG build anyway? [y/N]"); if ($ans.Trim() -notmatch '^(y|yes)$') { throw "cancelled (UE4SS build not supported)" } }
        $build = "revog-1.3"
    } elseif ($build -ne "revog-1.3" -and -not $Force) {
        Write-Host "Your UE4SS is a Chrisr0 / SB-UE4SS 3.1.x build. The mod was built against that source and every symbol it needs resolves,"
        Write-Host "but it has NOT been tested in game yet. SlotOrganizer keeps slots within 1..1000 on this build until it is verified."
        $ans = "" + (Read-Host "Install it anyway? [y/N]"); if ($ans.Trim() -notmatch '^(y|yes)$') { throw "cancelled (build not tested in game)" }
    }
    $src = Join-Path $PSScriptRoot "AToolSlotLimit"
    $dll = Join-Path $src "builds\$build\main.dll"
    if (-not (Test-Path -LiteralPath $dll)) { throw "$dll is missing from this package." }
    $dest = Join-Path $mods "AToolSlotLimit"
    New-Item -ItemType Directory -Force (Join-Path $dest "dlls") | Out-Null
    Copy-Item -LiteralPath $dll -Force -Destination (Join-Path $dest "dlls\main.dll")
    foreach ($f in "enabled.txt", "config.txt") {                      # never overwrite the user's own settings
        if (-not (Test-Path -LiteralPath (Join-Path $dest $f))) { Copy-Item -LiteralPath (Join-Path $src $f) -Destination (Join-Path $dest $f) }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dest "dlls\main.dll"))) { throw "copy failed" }
    Write-Host "Installed the '$build' build to $dest"
    Write-Host "Settings: config.txt (limit=9999), enabled.txt (1 = on, 0 = off). Delete the folder to uninstall."
    Write-Host "If the game crashes at launch after this, delete the folder."
} catch {
    Write-Host "Not installed: $($_.Exception.Message)  (close the game first if a file is locked)"
    exit 1
}
