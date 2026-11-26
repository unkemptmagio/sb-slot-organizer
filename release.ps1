# Builds dist\SlotOrganizer.exe and release\SlotOrganizer-<version>.zip
param([string]$Game = "E:\SteamLibrary\steamapps\common\StellarBlade\SB")
python tests\slots_test.py; if ($LASTEXITCODE) { throw "slots_test failed" }
python tests\iostore_test.py; if ($LASTEXITCODE) { throw "iostore_test failed" }
python -m PyInstaller --onefile --name SlotOrganizer --distpath dist --workpath build --specpath build slots.py 2>$null | Out-Null; if ($LASTEXITCODE) { throw "PyInstaller failed" }
$ver = (python slots.py --version).Split(" ")[1]
$stage = "release\SlotOrganizer-$ver"; Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage\AToolSlotLimit\dlls" | Out-Null
Copy-Item dist\SlotOrganizer.exe, release-files\README-USER.txt, release-files\install-atool-limit.ps1 $stage
$mod = Join-Path $Game "Binaries\Win64\ue4ss\Mods\AToolSlotLimit"
if (Test-Path "$mod\dlls\main.dll") { Copy-Item "$mod\dlls\main.dll" "$stage\AToolSlotLimit\dlls"; Copy-Item "$mod\enabled.txt", "$mod\config.txt" "$stage\AToolSlotLimit" }
else { Write-Warning "AToolSlotLimit not installed at ${mod} - zip has no limit mod" }
Compress-Archive -Force -Path "$stage\*" -DestinationPath "release\SlotOrganizer-$ver.zip"
Get-FileHash "release\SlotOrganizer-$ver.zip" -Algorithm SHA256 | Format-List


