# Install D200X Manager on Windows: a Python environment (.venv) in the project folder, the packages, and
# "D200X Manager" in the Start menu (the tray app). Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File tools\windows\install.ps1
# Needs Python 3.11 or newer from python.org (with the "py" launcher).
$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $Project

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating .venv ...'
    py -3 -m venv .venv
}
Write-Host 'Installing packages ...'
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host 'Making the icon and the Start menu shortcut ...'
$Icon = Join-Path $Project '.cache\D200X Manager.ico'
New-Item -ItemType Directory -Force -Path (Split-Path $Icon) | Out-Null
& .venv\Scripts\python.exe tools\app_icon.py $Icon

$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'D200X Manager.lnk'
$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut($Shortcut)
$Link.TargetPath = Join-Path $Project '.venv\Scripts\pythonw.exe'
$Link.Arguments = '"' + (Join-Path $Project 'tools\windows\tray.py') + '"'
$Link.WorkingDirectory = $Project
$Link.IconLocation = $Icon
$Link.Description = 'Ulanzi D200X Manager'
$Link.Save()

Write-Host ''
Write-Host "Done. Start 'D200X Manager' from the Start menu; its icon appears in the system tray."
