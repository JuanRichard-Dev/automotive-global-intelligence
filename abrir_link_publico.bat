@echo off
title Motor Atlas - Servidor Publico
echo ========================================================
echo   Motor Atlas - Automotive Global Intelligence
echo   Iniciando tunel publico para apresentacao...
echo ========================================================
echo.
"%LOCALAPPDATA%\cloudflared.exe" tunnel --url http://127.0.0.1:3100
pause
