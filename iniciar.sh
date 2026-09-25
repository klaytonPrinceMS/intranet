#!/bin/bash
# Lançador padrão da Intranet (Linux) — SQLite + sem OTel,
# sem depender de Docker/Postgres/Grafana. Ponte até o executável único.
# Processo DESTACADO (nohup + & + disown): sobrevive ao fechar o terminal.
# (rodar python main.py direto em foreground derruba o servidor ao fechar
#  o terminal — mesmo problema em qualquer sistema operacional).
cd "$(dirname "$0")"
export INTRANET_FORCE_SQLITE=1
export INTRANET_SEM_OTEL=1
mkdir -p logs
echo "Iniciando Intranet (modo padrao: SQLite, sem OTel)..."
echo "Servidor: http://localhost:8080  Docs: http://localhost:8001"
echo "Logs: logs/console.log"
if [ -x ".venv/bin/python" ]; then
    PYBIN=".venv/bin/python"
else
    PYBIN="python3"
fi
nohup "$PYBIN" main.py >> "logs/console.log" 2>&1 &
disown
echo "Intranet lancada em segundo plano (PID $!). Pode fechar este terminal."
