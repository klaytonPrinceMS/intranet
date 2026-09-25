@echo off
REM Lançador padrão da Intranet (Windows) — sobe com SQLite e sem OTel,
REM sem depender de Docker/Postgres/Grafana. Ponte até o executável único.
REM Processo DESTACADO (start sem /wait): sobrevive ao fechar este terminal.
REM (rodar python main.py direto em foreground derruba o servidor ao fechar
REM  o terminal — mesmo problema em qualquer sistema operacional).
cd /d "%~dp0"
set INTRANET_FORCE_SQLITE=1
set INTRANET_SEM_OTEL=1
if not exist "logs" mkdir "logs"
echo Iniciando Intranet (modo padrao: SQLite, sem OTel)...
echo Servidor: http://localhost:8080  Docs: http://localhost:8001
echo Logs: logs\console.log
if exist ".venv\Scripts\python.exe" (
    set "PYBIN=.venv\Scripts\python.exe"
) else (
    set "PYBIN=python"
)
start "Intranet" /min cmd /c ""%PYBIN%" main.py >> "logs\console.log" 2>&1"
echo Intranet lancada em segundo plano. Pode fechar esta janela.
pause
