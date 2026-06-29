@echo off
cd /d "%~dp0"
echo Iniciando SuKo Worker...
python -m bot.worker
pause