# Builds dist\SlotOrganizer.exe and release\SlotOrganizer-<version>.zip. Fails closed: any problem throws, no stale zip is left behind.
param([string]$Game = $(if ($env:SB_GAME) { $env:SB_GAME } else { "E:\SteamLibrary\steamapps\common\StellarBlade\SB" }))
function Run($what, [scriptblock]$cmd) { & $cmd; if ($LASTEXITCODE) { throw "$what failed (exit $LASTEXITCODE)" } }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found on PATH" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found on PATH" }
if (git status --porcelain) { throw "uncommitted changes: commit first so the zip matches the repository" }
Run "slots_test" { python tests\slots_test.py }
Run "iostore_test" { python tests\iostore_test.py }
Run "PyInstaller" { python -m PyInstaller --onefile --name SlotOrganizer --distpath dist --workpath build --specpath build slots.py 2>$null | Out-Null }
$ver = (python slots.py --version).Split(" ")[1]
if ((& .\dist\SlotOrganizer.exe --version) -ne "SlotOrganizer $ver") { throw "built exe reports the wrong version" }
$dll = Join-Path $Game "Binaries\Win64\ue4ss\Mods\AToolSlotLimit\dlls\main.dll"
if (-not (Test-Path -LiteralPath $dll)) { throw "AToolSlotLimit main.dll not found at $dll (pass -Game <SB folder>)" }
# the packaged DLL must be exactly the tested build (RevOG SB-UE4SS 1.3); rebuilding the mod means re-testing it and updating this pin
$pinned = "F9FF1CFE1DF2F38C73D7E39A75FD77777B6DEBB3C93A913F81FAB657DA4AFAE7"
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $pinned) { throw "main.dll at $dll is not the tested build ($pinned)" }
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
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$stageFull = (Resolve-Path $stage).Path; $zipFull = Join-Path (Get-Location).Path $zip
# one top-level folder and forward-slash entry names; CreateFromDirectory writes backslashes on Windows PowerShell 5.1, so the entries are written by hand
$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Stop"
$fs = [IO.File]::Create($zipFull); $za = New-Object IO.Compression.ZipArchive($fs, [IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $stageFull -Recurse -File | ForEach-Object {
        $entry = $za.CreateEntry("SlotOrganizer-$ver/" + $_.FullName.Substring($stageFull.Length + 1).Replace('\', '/'), [IO.Compression.CompressionLevel]::Optimal)
        $es = $entry.Open(); $in = [IO.File]::OpenRead($_.FullName); try { $in.CopyTo($es) } finally { $in.Dispose(); $es.Dispose() }
    }
} finally { if ($za) { $za.Dispose() }; if ($fs) { $fs.Dispose() }; $ErrorActionPreference = $prevEap }
if (-not (Test-Path $zip)) { throw "zip was not created" }
$zf = [IO.Compression.ZipFile]::OpenRead($zipFull); $names = $zf.Entries | ForEach-Object { $_.FullName }; $zf.Dispose()
if ($names | Where-Object { $_ -match '\\' }) { throw "zip entry names contain backslashes" }
$top = "SlotOrganizer-$ver/"
if ($names | Where-Object { -not $_.StartsWith($top) }) { throw "zip has entries outside $top" }
foreach ($need in "SlotOrganizer.exe", "README-USER.txt", "Undo-last-run.bat", "install-atool-limit.bat", "install-atool-limit.ps1", "LICENSE", "NOTICE.txt", "AToolSlotLimit/dlls/main.dll", "AToolSlotLimit/README.txt", "AToolSlotLimit/config.txt", "AToolSlotLimit/enabled.txt") { if (-not ($names | Where-Object { $_ -eq "$top$need" })) { throw "zip is missing $need" } }
"AToolSlotLimit main.dll sha256 (RevOG SB-UE4SS 1.3 build): " + (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
Get-FileHash $zip -Algorithm SHA256 | Format-List
