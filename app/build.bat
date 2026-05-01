@echo off
chcp 65001 > nul
echo.
echo  ██████╗ ██████╗ ██╗  ██╗ ██████╗ ██████╗ ██████╗
echo  ██╔══██╗██╔══██╗╚██╗██╔╝██╔═══██╗██╔══██╗╚════██╗
echo  ██║  ██║██████╔╝ ╚███╔╝ ██║   ██║██║  ██║ █████╔╝
echo  ██║  ██║██╔══██╗ ██╔██╗ ██║   ██║██║  ██║██╔═══╝
echo  ██████╔╝██████╔╝██╔╝ ██╗╚██████╔╝██████╔╝███████╗
echo  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
echo.
echo  [BUILD] 0bx0d? v1.0 — PyInstaller
echo  ─────────────────────────────────────────────────
echo.

:: Check PyInstaller
python -m PyInstaller --version > nul 2>&1
if errorlevel 1 (
    echo  [!] PyInstaller not found. Installing...
    pip install pyinstaller
)

:: Build
python -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name "0bx0d" ^
  --manifest manifest.xml ^
  --version-file version_info.txt ^
  --add-data "bin/goodbyedpi.exe;bin" ^
  --add-data "bin/WinDivert.dll;bin" ^
  --add-data "bin/WinDivert64.sys;bin" ^
  --hidden-import PySide6.QtCore ^
  --hidden-import PySide6.QtGui ^
  --hidden-import PySide6.QtWidgets ^
  --hidden-import psutil ^
  main.py

if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo  [OK] Build complete! → dist\0bx0d.exe
echo.

:: Create release zip
echo  [ZIP] Packing release...
if exist "..\release" rmdir /s /q "..\release"
mkdir "..\release\0bx0d"
copy "dist\0bx0d.exe" "..\release\0bx0d\"

powershell -Command "Compress-Archive -Path '..\release\0bx0d' -DestinationPath '..\release\0bx0d.zip' -Force"
echo  [OK] Release zip: release\0bx0d.zip
echo.
echo  Upload 0bx0d.zip to GitHub Releases!
echo.
pause
