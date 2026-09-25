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

# Lista TODOS os IPs acessiveis da maquina. Em WSL2 o `localhost` do navegador
# Windows NAO alcança o processo que roda dentro do distro: é preciso usar o IP
# do WSL. O servidor escuta em 0.0.0.0, entao qualquer um destes enderecos
# funciona — imprimimos todos para nao ter que adivinhar.
mostrar_ips() {
    local rotulo="$1" porta="$2"
    local ips
    # IPs de interfaces globais (o `scope global` exclui loopback e/docker).
    ips=$(ip -4 -o addr show scope global 2>/dev/null \
          | awk '{split($4, a, "/"); print a[1]}')
    # Fallback: `hostname -I` quando `ip` não existe (macOS, contêiner).
    [ -z "$ips" ] && ips=$(hostname -I 2>/dev/null)
    if [ -z "$ips" ]; then
        echo "  $rotulo: http://localhost:$porta  (nenhum IP de rede detectado)"
        return
    fi
    local ip
    for ip in $ips; do
        echo "  $rotulo: http://$ip:$porta"
    done
    echo "  $rotulo: http://localhost:$porta  (somente de dentro desta maquina)"
}

mostrar_ips "Servidor" 8080
mostrar_ips "Docs    " 8001

# Em WSL2 o IP do host Windows (gateway / nameserver do resolv.conf) é
# informativo: o servidor não atende nele, mas ajuda a diagnosticar rede.
if grep -qi microsoft /proc/version 2>/dev/null; then
    HOST_WIN=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf 2>/dev/null)
    echo "  (WSL2 detectado. No navegador do Windows use o IP do WSL acima,"
    echo "   'localhost' nao atravessa. Host Windows: ${HOST_WIN:-desconhecido})"
fi
echo "Logs: logs/console.log"
if [ -x ".venv/bin/python" ]; then
    PYBIN=".venv/bin/python"
else
    PYBIN="python3"
fi
nohup "$PYBIN" main.py >> "logs/console.log" 2>&1 &
disown
echo "Intranet lancada em segundo plano (PID $!). Pode fechar este terminal."
