@echo off
REM Lancador do servidor de desenvolvimento (recorte de iniciar.bat).
REM Sobe o main.py em foreground,writing to logs\console.log. Use via
REM "schtasks /Run" ou manualmente; manter o terminal aberto.
cd /d D:\Documents\git\intranet
set INTRANET_FORCE_SQLITE=1
set INTRANET_SEM_OTEL=1
if not exist "logs" mkdir "logs"
D:\Documents\git\intranet\.venv\Scripts\python.exe main.py >> "logs\console.log" 2>> "logs\console.err.log"
