@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 goto end
python threads_irent.py --login --max-posts 30
if errorlevel 1 goto end
if exist output\results.docx start "" "output\results.docx"
:end
pause
