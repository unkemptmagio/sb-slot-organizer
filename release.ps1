# Builds dist\SlotOrganizer.exe and release\SlotOrganizer-<version>.zip
param([string]$Game = $(if ($env:SB_GAME) { $env:SB_GAME } else { "E:\SteamLibrary\steamapps\common\StellarBlade\SB" }))
python tests\slots_test.py; if ($LASTEXITCODE) { throw "slots_test failed" }
python tests\iostore_test.py; if ($LASTEXITCODE) { throw "iostore_test failed" }
python -m PyInstaller --onefile --name SlotOrganizer --distpath dist --workpath build --specpath build slots.py 2>$null | Out-Null; if ($LASTEXITCODE) { throw "PyInstaller failed" }
$ver = (python slots.py --version).Split(" ")[1]
$exeVer = (& .\dist\SlotOrganizer.exe --version); if ($exeVer -ne "SlotOrganizer $ver") { throw "built exe reports '$exeVer', expected 'SlotOrganizer $ver'" }
$dll = Join-Path $Game "Binaries\Win64\ue4ss\Mods\AToolSlotLimit\dlls\main.dll"
if (-not (Test-Path $dll)) { throw "AToolSlotLimit main.dll not found at $dll (pass -Game <SB folder>)" }
$stage = "release\SlotOrganizer-$ver"; Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage\AToolSlotLimit\dlls" | Out-Null
Copy-Item dist\SlotOrganizer.exe, release-files\README-USER.txt, release-files\install-atool-limit.ps1, release-files\install-atool-limit.bat $stage
Copy-Item $dll "$stage\AToolSlotLimit\dlls"
Set-Content "$stage\AToolSlotLimit\enabled.txt" "1" -Encoding ascii            # canonical defaults, not whatever the author's install holds
Set-Content "$stage\AToolSlotLimit\config.txt" "limit=9999" -Encoding ascii
Compress-Archive -Force -Path "$stage\*" -DestinationPath "release\SlotOrganizer-$ver.zip"
"main.dll sha256: " + (Get-FileHash $dll -Algorithm SHA256).Hash
Get-FileHash "release\SlotOrganizer-$ver.zip" -Algorithm SHA256 | Format-List
