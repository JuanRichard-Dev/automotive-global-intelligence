@echo off
title Motor Atlas - Servidor Publico
cls
echo ========================================================
echo   Motor Atlas - Automotive Global Intelligence
echo   Iniciando tunel publico para apresentacao...
echo ========================================================
echo.
echo ATENCAO: Mantenha esta janela aberta durante a apresentacao!
echo.
"%LOCALAPPDATA%\cloudflared.exe" tunnel --url http://127.0.0.1:3100
pause
