@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 goto end
python threads_irent.py --login
if exist output\results.html start "" "output\results.html"
:end
pause
