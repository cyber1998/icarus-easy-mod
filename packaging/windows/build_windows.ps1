# Builds the Windows portable zip and (if Inno Setup is installed) the installer.
# Run from the project root:  powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$venv = ".venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating build venv at $venv ..."
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv $venv
    } else {
        throw "Python 3.10+ was not found. Install it from https://www.python.org/downloads/ (check 'Add to PATH')."
    }
}
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt pyinstaller

& "$venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath packaging/dist --workpath packaging/build packaging/app.spec

$binary = "packaging\dist\IcarusEasyMod\IcarusEasyMod.exe"
& "$venv\Scripts\python.exe" packaging\smoke_test.py $binary --port 8613
& $binary --self-check

$version = (& "$venv\Scripts\python.exe" -c "import icarus_manager; print(icarus_manager.__version__)").Trim()

$zip = "packaging\dist\IcarusEasyMod-$version-windows-x64.zip"
Compress-Archive -Path "packaging\dist\IcarusEasyMod" -DestinationPath $zip -Force
Write-Host "Portable zip: $zip"

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    & $iscc "/DMyAppVersion=$version" "packaging\windows\installer.iss"
    Write-Host "Installer: packaging\dist\installer\IcarusEasyModSetup-$version.exe"
} else {
    Write-Host ""
    Write-Host "Inno Setup not found; skipping installer build." -ForegroundColor Yellow
    Write-Host "Install it with:  winget install -e --id JRSoftware.InnoSetup" -ForegroundColor Yellow
    Write-Host "Then re-run this script to produce the installer." -ForegroundColor Yellow
}
