@echo off
REM Lançador padrão da Intranet (Windows) — sobe com SQLite e sem OTel,
REM sem depender de Docker/Postgres/Grafana. Ponte até o executável único.
cd /d "%~dp0"
set INTRANET_FORCE_SQLITE=1
set INTRANET_SEM_OTEL=1
echo Iniciando Intranet (modo padrao: SQLite, sem OTel)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
pause
