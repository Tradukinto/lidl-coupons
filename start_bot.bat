@echo off
chcp 65001 > nul
title Lidl Coupons Telegram Bot
echo ========================================================
echo   Lidl Пафос Telegram Bot (Long Polling Daemon)
echo   Мгновенный отклик на команды и Радар акций
echo ========================================================
python "%~dp0telegram_notifier.py" --daemon
pause
