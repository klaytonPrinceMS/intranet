#!/bin/bash
# Lançador padrão da Intranet (Linux) — SQLite + sem OTel,
# sem depender de Docker/Postgres/Grafana. Ponte até o executável único.
cd "$(dirname "$0")"
export INTRANET_FORCE_SQLITE=1
export INTRANET_SEM_OTEL=1
echo "Iniciando Intranet (modo padrao: SQLite, sem OTel)..."
if [ -x ".venv/bin/python" ]; then
    .venv/bin/python main.py
else
    python3 main.py
fi
