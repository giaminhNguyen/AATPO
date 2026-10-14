# Builds dist\AATPO\AATPO.exe (onedir) and runs its built-in self-check. Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q pyinstaller
& $py -m PyInstaller packaging\aatpo.spec --noconfirm --distpath dist --workpath build
$home_dir = Join-Path $env:TEMP "aatpo_build_check"
Remove-Item -Recurse -Force $home_dir -ErrorAction SilentlyContinue
$env:AATPO_HOME = $home_dir
$report = Join-Path $env:TEMP "aatpo_build_check.json"
$p = Start-Process -FilePath ".\dist\AATPO\AATPO.exe" -ArgumentList "--smoke-test", $report -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Self-check failed (exit $($p.ExitCode)); see $report" }
Get-Content $report
Write-Host "OK: dist\AATPO\AATPO.exe"
