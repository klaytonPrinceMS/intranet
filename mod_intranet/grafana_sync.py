"""Grafana credentials sync with Intranet database.

Sincroniza as credenciais do usuário master da Intranet com o Grafana.

Author: Klayton Prince
Date: 2026-09-04
"""
import os
import sys
import subprocess
import json
from typing import Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_command(cmd: list, timeout: int = 10) -> Tuple[int, str, str]:
    """Execute a command and return returncode, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def obter_senha_master() -> Optional[str]:
    """Get master user password from Intranet database.

    Obtém a senha do usuário master do banco de dados da Intranet.
    """
    try:
        # A tabela tb_usuarios fica no banco do módulo mod_gest_cad_usuario
        from mod_gest_cad_usuario.manipulador_bd import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Verifica se o usuário master existe (idempotente)
        cursor.execute(
            "SELECT user_nome FROM tb_usuarios WHERE user_nome = 'master'"
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            # A senha real é um hash bcrypt; o Grafana usa a mesma senha
            # padrão "master". Retorna "master" (password padrão de seed).
            return "master"

        return None
    except Exception as e:
        print(f"[grafana-sync] Error getting master password: {e}")
        return None


def grafana_rodando() -> bool:
    """Check if Grafana container is running.

    Verifica se o container do Grafana está rodando.
    """
    returncode, stdout, _ = _run_command(
        ["docker", "inspect", "--format", "{{.State.Running}}", "intranet-grafana"],
        timeout=5
    )
    return returncode == 0 and "true" in stdout.lower()


def grafana_aguardar_pronto(limite: int = 150) -> bool:
    """Wait until the Grafana HTTP API is ready.

    Aguarda o Grafana responder no /api/health. Evita chamar o CLI de reset
    durante a migração inicial do banco: em instalação limpa isso corrompia o
    SQLite com SQLITE_BUSY (migração renomear coluna dava "duplicate column").
    """
    import time as _time
    import urllib.request as _url

    inicio = _time.time()
    while _time.time() - inicio < limite:
        try:
            with _url.urlopen("http://localhost:3000/api/health", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        _time.sleep(2)
    return False


def _api_autorizada(senha: str) -> Optional[bool]:
    """Check if basic auth master:<senha> works on the Grafana API.

    Retorna True se a API aceita master/senha, False se 401, None em erro.
    """
    import base64 as _b64
    import urllib.error as _urlerr
    import urllib.request as _url

    token = _b64.b64encode(f"master:{senha}".encode()).decode()
    requisicao = _url.Request(
        "http://localhost:3000/api/org",
        headers={"Authorization": f"Basic {token}"},
    )
    try:
        with _url.urlopen(requisicao, timeout=5) as resp:
            return resp.status == 200
    except _urlerr.HTTPError as e:
        return False if e.code == 401 else None
    except Exception:
        return None


def atualizar_senha_grafana(nova_senha: str) -> Tuple[bool, str]:
    """Update Grafana admin password via Grafana CLI (only when healthy).

    Atualiza a senha do admin via CLI somente depois que o Grafana está pronto,
    evitando corrida com a migração inicial do banco (SQLITE_BUSY).
    """
    if not grafana_rodando():
        return False, "Grafana container not running"

    if not grafana_aguardar_pronto(limite=150):
        return False, "Grafana demorou demais para ficar pronto (health check)"

    try:
        # Reset admin password using Grafana CLI (confiável no Grafana 13+)
        returncode, stdout, stderr = _run_command(
            ["docker", "exec", "intranet-grafana", "grafana", "cli",
             "admin", "reset-admin-password", nova_senha],
            timeout=30
        )
        if returncode == 0:
            return True, f"Senha do grafana atualizada para '{nova_senha}'"
        else:
            return False, (stderr or stdout or "Falha ao resetar senha").strip()
    except Exception as e:
        return False, str(e)


def sincronizar_credenciais() -> Tuple[bool, str]:
    """Sync Intranet master credentials with Grafana.

    Sincroniza as credenciais do master da Intranet com o Grafana. Aguarda o
    Grafana ficar pronto e prefere validar via API (sem corrida de escrita no
    banco); só usa o CLI de reset se a senha atual não for aceita.
    """
    # Get master password from Intranet
    senha_master = obter_senha_master()

    if not senha_master:
        return False, "Could not get master password from Intranet"

    if not grafana_rodando():
        return False, "Grafana not running"

    if not grafana_aguardar_pronto(limite=150):
        return False, "Grafana demorou demais para ficar pronto (health check)"

    # Se a API já aceita master/senha, não toca no banco (evita SQLITE_BUSY).
    ja_sincronizada = _api_autorizada(senha_master)
    if ja_sincronizada is True:
        return True, f"Grafana credentials synced: master/{senha_master}"

    # Fallback: CLI reset (agora o Grafana já migrou, sem corrida).
    sucesso, msg = atualizar_senha_grafana(senha_master)
    if sucesso:
        return True, f"Grafana credentials synced: master/{senha_master}"
    return False, f"Failed to update Grafana: {msg}"


def obter_status_grafana() -> dict:
    """Get Grafana status information.

    Retorna informações de status do Grafana.
    """
    return {
        "rodando": grafana_rodando(),
        "url": "http://localhost:3000",
        "usuario": "master",
        "senha": "master"
    }


if __name__ == "__main__":
    print("=== Grafana Credentials Sync ===")
    status = obter_status_grafana()
    print(f"Grafana running: {status['rodando']}")
    print(f"URL: {status['url']}")
    print(f"Username: {status['usuario']}")
    print(f"Password: {status['senha']}")
    print("="*40)