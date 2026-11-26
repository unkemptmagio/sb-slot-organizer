# Installs the optional AToolSlotLimit UE4SS mod (lifts ATOOL's 1000-slot limit).
param([string]$Game)
if (-not $Game) { $Game = Read-Host "Path to the StellarBlade\SB folder (contains Binaries and Content)" }
$ue4ss = Join-Path $Game "Binaries\Win64\ue4ss"
if (-not (Test-Path $ue4ss)) { Write-Host "UE4SS not found at $ue4ss - install UE4SS first."; exit 1 }
$dest = Join-Path $ue4ss "Mods\AToolSlotLimit"
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "AToolSlotLimit\*") $dest
Write-Host "Installed to $dest. Edit config.txt (limit=9999) to change the limit. Remove the folder to uninstall."
