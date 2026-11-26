# Builds dist\SlotOrganizer.exe and release\SlotOrganizer-<version>.zip. Fails closed: any problem throws, no stale zip is left behind.
param([string]$Game = $(if ($env:SB_GAME) { $env:SB_GAME } else { "E:\SteamLibrary\steamapps\common\StellarBlade\SB" }))
function Run($what, [scriptblock]$cmd) { & $cmd; if ($LASTEXITCODE) { throw "$what failed (exit $LASTEXITCODE)" } }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found on PATH" }
Run "slots_test" { python tests\slots_test.py }
Run "iostore_test" { python tests\iostore_test.py }
Run "PyInstaller" { python -m PyInstaller --onefile --name SlotOrganizer --distpath dist --workpath build --specpath build slots.py 2>$null | Out-Null }
$ver = (python slots.py --version).Split(" ")[1]
if ((& .\dist\SlotOrganizer.exe --version) -ne "SlotOrganizer $ver") { throw "built exe reports the wrong version" }
$dll = Join-Path $Game "Binaries\Win64\ue4ss\Mods\AToolSlotLimit\dlls\main.dll"
if (-not (Test-Path -LiteralPath $dll)) { throw "AToolSlotLimit main.dll not found at $dll (pass -Game <SB folder>)" }
# the packaged DLL must be the RevOG-line build (the only tested one): it imports CppUserModBase::on_cpp_mods_loaded
$dumpbin = Get-ChildItem "C:\Program Files*\Microsoft Visual Studio\2022\*\VC\Tools\MSVC\*\bin\Hostx64\x64\dumpbin.exe" | Select-Object -Last 1 -ExpandProperty FullName
if (-not $dumpbin) { throw "dumpbin not found (Visual Studio C++ build tools)" }
if (-not ((& $dumpbin /nologo /imports $dll) -match "on_cpp_mods_loaded")) { throw "main.dll does not import on_cpp_mods_loaded: wrong file at $dll (the mod must be the RevOG SB-UE4SS 1.3 build)" }
# smoke test the built exe: a read-only scan of the real install with its data folder redirected to a scratch location
$oldLocal = $env:LOCALAPPDATA; $env:LOCALAPPDATA = Join-Path $env:TEMP "so_release_smoke"
try { & .\dist\SlotOrganizer.exe scan --game $Game | Out-Null; if ($LASTEXITCODE -ge 2) { throw "built exe failed a scan (exit $LASTEXITCODE)" } } finally { $env:LOCALAPPDATA = $oldLocal }
$stage = "release\SlotOrganizer-$ver"; $zip = "release\SlotOrganizer-$ver.zip"
Remove-Item -Recurse -Force $stage, $zip -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage\AToolSlotLimit\dlls" | Out-Null
foreach ($f in "dist\SlotOrganizer.exe", "release-files\README-USER.txt", "release-files\install-atool-limit.ps1", "release-files\install-atool-limit.bat", "release-files\Undo-last-run.bat", "release-files\LICENSE", "release-files\NOTICE.txt") { Copy-Item -LiteralPath $f -Destination $stage -ErrorAction Stop }
Copy-Item -LiteralPath $dll -Destination "$stage\AToolSlotLimit\dlls\main.dll" -ErrorAction Stop
Copy-Item -LiteralPath "release-files\AToolSlotLimit-README.txt" -Destination "$stage\AToolSlotLimit\README.txt" -ErrorAction Stop
Set-Content "$stage\AToolSlotLimit\enabled.txt" "1" -Encoding ascii            # canonical defaults, not whatever the author's install holds
Set-Content "$stage\AToolSlotLimit\config.txt" "limit=9999" -Encoding ascii
Compress-Archive -Force -Path "$stage\*" -DestinationPath $zip -ErrorAction Stop
if (-not (Test-Path $zip)) { throw "zip was not created" }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$names = [IO.Compression.ZipFile]::OpenRead((Resolve-Path $zip)).Entries | ForEach-Object { $_.FullName -replace '\\', '/' }
foreach ($need in "SlotOrganizer.exe", "README-USER.txt", "Undo-last-run.bat", "install-atool-limit.bat", "LICENSE", "NOTICE.txt", "AToolSlotLimit/dlls/main.dll", "AToolSlotLimit/README.txt") { if (-not ($names | Where-Object { $_ -eq $need })) { throw "zip is missing $need" } }
"AToolSlotLimit main.dll sha256 (RevOG SB-UE4SS 1.3 build): " + (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
Get-FileHash $zip -Algorithm SHA256 | Format-List
