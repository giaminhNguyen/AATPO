# Creates a "AATPO - Văn phòng AI" shortcut (default: on the Desktop) that opens the packaged app by double-click.
#   powershell -ExecutionPolicy Bypass -File packaging\make_shortcut.ps1 [-Folder C:\some\folder]
param([string]$Folder = [Environment]::GetFolderPath("Desktop"))
$exe = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\dist\AATPO")).Path "AATPO.exe"
if (-not (Test-Path $exe)) { throw "Chưa có $exe. Hãy chạy packaging\build.ps1 trước." }
$lnk = Join-Path $Folder "AATPO - Van phong AI.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $exe
$s.WorkingDirectory = Split-Path $exe
$s.IconLocation = $exe
$s.Description = "AATPO - Van phong AI"
$s.Save()
Write-Host $lnk
