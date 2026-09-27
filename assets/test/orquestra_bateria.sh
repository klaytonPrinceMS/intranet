#!/bin/bash
# Orquestra a bateria combinada: k6 (40 VUs) + 20 navegadores reais + guarda.
#
# POR QUE ESTE SCRIPT EXISTE: na primeira tentativa de rodar a bateria na mão,
# usei `pgrep -f carga_uso_navegador` para descobrir o PID. `pgrep -f` casa a
# linha de comando INTEIRA — e a linha do meu próprio bash continha essas
# strings, porque o comando que executava o navegador era o próprio comando.
# Resultado: o processo "vigiado" era o meu shell, o guarda o matou, e a
# bateria morreu antes de escrever uma linha de log.
#
# Aqui os PIDs vêm de `$!`, direto do `&` do lançamento. Sem `pgrep -f`.

set -u
cd /home/klayton/git/intranet
RAIZ="$PWD"
mkdir -p logs /tmp

MAX_VU="${MAX_VU:-40}"
NAV_MIN="${NAV_MIN:-12}"

# garante que não sobrou nada da execucao anterior
for p in $(pgrep -x k6 2>/dev/null); do kill -TERM "$p" 2>/dev/null; done
pkill -f "assets/test/carga_uso_navegador.py" 2>/dev/null
pkill -f "assets/test/guarda_recursos.py" 2>/dev/null
sleep 3

echo "  === configuracao ==="
echo "  k6: MAX_VU=$MAX_VU | navegadores: $NAV_MIN min"
.venv/bin/python assets/test/valida_cronometragem.py | tail -4

# 1) k6
env K6_MAX_VU="$MAX_VU" k6 run --quiet assets/k6/carga_uso.js > /tmp/k6_comb.log 2>&1 &
PID_K6=$!
# 2) 20 navegadores reais, em paralelo
.venv/bin/python assets/test/carga_uso_navegador.py --usuarios 20 \
    --minutos "$NAV_MIN" > /tmp/navegadores.log 2>&1 &
PID_NAV=$!
sleep 12

# 3) o guarda, com os PIDs REAIS
.venv/bin/python assets/test/guarda_recursos.py \
    --por-cento 90 --por-cento-cpu 98 \
    --k6-pid "$PID_K6" --py-pid "$PID_NAV" \
    --json /tmp/serie_comb.json --log /tmp/guarda_comb.log \
    > /tmp/guarda_comb.out 2>&1 &
PID_GUARDA=$!

echo "  === PIDs (de \$!, sem pgrep -f) ==="
echo "  k6         = $PID_K6"
echo "  navegadores= $PID_NAV"
echo "  guarda     = $PID_GUARDA"

# confere que cada PID e mesmo o processo esperado
for par in "k6:$PID_K6" "nav:$PID_NAV" "guarda:$PID_GUARDA"; do
    nome="${par%%:*}"; pid="${par##*:}"
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "  [ERRO] $nome (PID $pid) ja morreu no lançamento"
        exit 1
    fi
done
echo "  os 3 PIDs conferem com processos vivos"

# espera a bateria (k6 e o mais longo)
wait "$PID_K6" 2>/dev/null
echo "  k6 terminou"
wait "$PID_NAV" 2>/dev/null
echo "  navegadores terminaram"
wait "$PID_GUARDA" 2>/dev/null
echo "  guarda terminou"
echo "  === fim ==="
