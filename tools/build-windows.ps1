# Build "D200X Manager.exe" on Windows: one file with everything in it (Python, the code, the defaults for a new
# config folder). Run in PowerShell from the project folder:
#   powershell -ExecutionPolicy Bypass -File tools\build-windows.ps1
# Needs Python 3.11 or newer from python.org (with the "py" launcher). The result is dist\D200X Manager.exe:
# put it in a folder of its own (its config.yaml and the rest come next to it) and start it.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Root

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating .venv ...'
    py -3 -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .venv\Scripts\python.exe tools\stage_defaults.py
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller d200x.spec

Write-Host ''
Write-Host "Built: $Root\dist\D200X Manager.exe"
Write-Host 'Put it in a folder of its own, e.g. C:\D200X Manager, and start it; its icon appears in the system tray.'
