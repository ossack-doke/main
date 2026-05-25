@echo off
REM Build single-file GUI exe (Windows). Run from this folder.
cd /d "%~dp0"

py -m pip install --upgrade pip
py -m pip install pyinstaller requests

py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name PanelApiProbeGUI ^
  --add-data "endpoints_manifest.json;." ^
  --hidden-import panel_api_probe ^
  panel_probe_gui.py

echo.
echo Output: dist\PanelApiProbeGUI.exe
pause
