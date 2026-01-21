@echo off
setlocal
title NOTE BOT

echo ========================================
echo        NOTE BOT: RESTARTING...
echo ========================================

:: 1. Принудительно закрываем ВСЕ процессы Python
echo [1/3] Cleaning up ALL old processes...
powershell -Command "$p = Get-Process python -ErrorAction SilentlyContinue; $c = 0; if ($p) { $c = $p.Count; $p | Stop-Process -Force }; Write-Host \"ЗАКРЫТО ДУБЛИКАТОВ: $c\" -ForegroundColor Red"

:: 2. Удаляем старые лог-файлы, чтобы начать с чистого листа
if exist bot.log del bot.log

:: 3. Небольшая пауза
timeout /t 2 /nobreak >nul

:: 3. Launch the bot using conhost (for icon support)
echo [2/3] Starting Note Bot...
start "NOTE BOT" conhost.exe "%~dp0.venv\Scripts\python.exe" "%~dp0bot.py"

echo [3/3] Done! 
echo.
echo ✅ Bot is now running in a separate window.
echo This launcher will close in 5 seconds.
timeout /t 5 >nul
exit
