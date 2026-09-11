"""Assistente de ativação/configuração do sistema no terminal (setup wizard).

EN — Interactive terminal wizard shown at startup. Press ENTER to boot with
    the default configuration; type "sim"/"s" to enter activation mode and
    choose the database backend (SQLite/PostgreSQL), OpenTelemetry (auto-
    installing Docker when missing on the detected OS) and the service ports
    (site, PostgreSQL, Grafana). Shows colored output and a progress bar.
PT — Assistente interativo no terminal exibido na inicialização. Aperte ENTER
    para subir com a configuração padrão; digite "sim"/"s" para entrar no
    modo de ativação e escolher o backend de banco (SQLite/PostgreSQL), o
    OpenTelemetry (instala Docker automaticamente quando ausente, conforme o
    SO detectado) e as portas dos serviços (site, PostgreSQL, Grafana). Usa
    texto colorido e barra de progresso.
"""
import os
import re
import shlex
import sys
import time
import platform
import subprocess
import shutil

_TTY = sys.stdout.isatty() and sys.stdin.isatty()

# =============================================================================
# Cores ANSI (terminal)
# =============================================================================
_VERDE = "\033[32m"
_AMARELO = "\033[33m"
_AZUL = "\033[34m"
_VERMELHO = "\033[31m"
_CIANO = "\033[36m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

CORES = {
    "verde": _VERDE, "amarelo": _AMARELO, "azul": _AZUL,
    "vermelho": _VERMELHO, "ciano": _CIANO,
}


def c(texto, cor="verde", negrito=False):
    """Returns the text wrapped in an ANSI color (terminal only)."""
    if not _TTY:
        return texto
    cod = CORES.get(cor, "")
    return f"{_BOLD if negrito else ''}{cod}{texto}{_RESET}"


_VERSAO = "1.0.260908"


def banner():
    """Prints the system banner."""
    print(c("=" * 62, "azul", True))
    print(c(f"  INTRANET MODULAR {_VERSAO} — PRINCE, K.B", "ciano", True))
    print(c("  Assistente de inicialização / ativação", "azul"))
    print(c("=" * 62, "azul", True))


def barra(fracao, rotulo=""):
    """Renders a progress bar in the terminal (40 chars)."""
    if not _TTY:
        return
    fracao = max(0.0, min(1.0, fracao))
    larg = 40
    preenchido = int(fracao * larg)
    bar = "\u2588" * preenchido + "\u2591" * (larg - preenchido)
    sys.stdout.write(
        f"\r{_AZUL}[{bar}]{_RESET} {int(fracao * 100):3d}% "
        f"{_CIANO}{rotulo}{_RESET}")
    sys.stdout.flush()


def fim_barra():
    """Ends the current progress-bar line."""
    if _TTY:
        sys.stdout.write("\n")
        sys.stdout.flush()


def perguntar(texto, padrao="", validos=None, valido_num=False, faixa=None):
    """Asks a question and returns a normalized answer (default if empty).

    `faixa=(min, max)` restringe valores numéricos (ex.: portas 1–65535)."""
    try:
        resp = input(c(f"{texto}: ", "ciano")).strip()
    except (EOFError, KeyboardInterrupt):
        resp = ""
    if not resp:
        return padrao
    if valido_num:
        try:
            n = int(resp)
        except ValueError:
            print(c("Valor inválido — usando padrão.", "amarelo"))
            return padrao
        if faixa is not None and not (faixa[0] <= n <= faixa[1]):
            print(c(f"Valor fora da faixa {faixa[0]}–{faixa[1]} — "
                    "usando padrão.", "amarelo"))
            return padrao
        return str(n)
    if validos:
        r = resp.lower()
        if r in validos:
            return r
        print(c("Opção inválida — usando padrão.", "amarelo"))
        return padrao
    return resp


def _porta_valida(resp, padrao):
    """Normaliza uma porta digitada; vazio/fora da faixa → usa o padrão."""
    try:
        n = int(str(resp or "").strip())
    except ValueError:
        return padrao
    return n if 1 <= n <= 65535 else padrao


# =============================================================================
# Configuração padrão
# =============================================================================

def _config_padrao():
    """Default configuration — boot simples, sem assistente.

    Subir SEM configurações = SQLite apenas, SEM Postgres e SEM OpenTelemetry
    (boot rápido e autossuficiente). Postgres/OTel só são trazidos quando o
    usuário entra no modo de ativação/configuração."""
    return {
        "modo": "padrao",
        "banco_tipo": "sqlite",
        "postgres_url": ("postgresql+psycopg2://intranet:intranet"
                         "@localhost:5432/intranet"),
        "otel_ativo": False,
        "subir_postgres": False,
        "porta_site": 8080,
        "porta_postgres": 5432,
        "porta_grafana": 3000,
    }


# =============================================================================
# Persistência do seletor de banco (antes do inicializar_bancos)
# =============================================================================

def _garantir_tb_config():
    """Creates the central SQLite file + tb_config if missing (pre-boot)."""
    try:
        from mod_intranet.repositorio import DB_PATH
        if not os.path.exists(DB_PATH):
            conn = __import__("sqlite3").connect(DB_PATH)
            conn.execute("CREATE TABLE IF NOT EXISTS tb_config ("
                         "chave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
            conn.commit()
            conn.close()
        return True
    except Exception:
        return False


def aplicar_banco(cfg):
    """Persists the backend selector (banco_tipo/postgres_url) pre-boot."""
    try:
        _garantir_tb_config()
        from mod_intranet import banco_conexao as bc
        bc.definir_banco_tipo(cfg.get("banco_tipo", "sqlite"))
        bc.definir_postgres_url(cfg.get(
            "postgres_url",
            "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"))
    except Exception as e:
        print(c(f"[setup] aviso ao aplicar banco: {e}", "amarelo"))


# =============================================================================
# Portas — edição best-effort dos compose
# =============================================================================

def _trocar_porta_compose(caminho, mapeamentos):
    """Best-effort: replaces `orig:cont` port mappings in a compose file."""
    try:
        if not os.path.exists(caminho):
            return False
        with open(caminho, "r", encoding="utf-8") as f:
            txt = f.read()
        for origem, destino in mapeamentos.items():
            txt = txt.replace(f'"{origem}:', f'"{destino}:')
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(txt)
        return True
    except Exception:
        return False


def aplicar_portas(cfg):
    """Applies the configured ports to the docker compose files (best-effort)."""
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "docker")
    _trocar_porta_compose(
        os.path.join(base, "compose.yml"),
        {"3000": str(cfg.get("porta_grafana", 3000))})
    pg = os.path.join(base, "postgres", "docker-compose.yml")
    if os.path.exists(pg):
        try:
            with open(pg, "r", encoding="utf-8") as f:
                txt = f.read()
            txt = re.sub(r'"\d+:5432"',
                         f'"{cfg.get("porta_postgres", 5432)}:5432"', txt)
            with open(pg, "w", encoding="utf-8") as f:
                f.write(txt)
        except Exception:
            pass


# =============================================================================
# Docker — detecção, instalação e stack OTel
# =============================================================================

def docker_instalado():
    """True if the Docker CLI is available."""
    return shutil.which("docker") is not None


def _tem_operador_shell(comando):
    """True if the string needs a shell (&&, ||, ;, pipes, redirections)."""
    return bool(re.search(r"&&|\|\||[;|><()]|`|\$\(", comando))


def _mascarar_comando(comando):
    """Mascara credenciais no comando exibido (a senha nunca aparece)."""
    txt = comando if isinstance(comando, str) else " ".join(comando)
    txt = re.sub(
        r"([^\s|&;<>]+):([^\s|&;<>]+)(\s*\|\s*chpasswd\b)",
        r"\1:***\3", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(-p\s+)\S+", r"\1***", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(password=)\S+", r"\1***", txt, flags=re.IGNORECASE)
    txt = re.sub(r":senha\S*", ":***", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\b(PASSWORD|SENHA)\b(?!\s*=)", "***", txt)
    return txt


def _cmd(comando, timeout=600, entrada=None):
    """Runs a command, streaming output to the terminal.

    Aceita uma lista de argumentos (shell=False, sem interpolação) ou uma
    string: sem operadores de shell roda via `shlex.split` como lista; com
    operadores mantém o comportamento legado (comandos estáticos, sem entrada
    do usuário — nunca interpolamos entrada do usuário em shell). Credenciais
    são mascaradas no print; `entrada` é enviada por stdin (a senha nunca vai
    no argv). Retorna True se o retorno for 0."""
    usar_shell = False
    if isinstance(comando, str):
        if _tem_operador_shell(comando):
            usar_shell = True
        else:
            comando = shlex.split(comando)
    print(c(f"\n$ {_mascarar_comando(comando)}", "azul"))
    try:
        r = subprocess.run(
            comando, shell=usar_shell, timeout=timeout,
            input=(entrada.encode() if isinstance(entrada, str) else entrada))
        return r.returncode == 0
    except Exception as e:
        print(c(f"  falha ao executar: {e}", "vermelho"))
        return False


def instalar_docker():
    """Installs Docker on the detected OS (needs sudo/admin on most cases)."""
    so = platform.system()
    print(c(f"Sistema operacional detectado: {so}", "ciano", True))
    if not docker_instalado():
        barra(0.25, "Instalando Docker...")
        if so == "Linux":
            if shutil.which("apt-get"):
                _cmd("sudo apt-get update && sudo apt-get install -y docker.io")
            elif shutil.which("dnf"):
                _cmd("sudo dnf install -y docker")
            elif shutil.which("yum"):
                _cmd("sudo yum install -y docker")
            else:
                print(c("Gestor de pacotes não identificado — instale o Docker "
                        "manualmente (https://docs.docker.com/engine/install/).",
                        "amarelo"))
            _cmd("sudo systemctl enable --now docker")
        elif so == "Darwin":
            _cmd("brew install --cask docker")
        elif so == "Windows":
            _cmd("winget install -e --id Docker.DockerDesktop")
        else:
            print(c("SO não suportado para instalação automática — instale o "
                    "Docker manualmente.", "amarelo"))
        barra(0.6, "Docker instalado")
    else:
        barra(0.6, "Docker já disponível")
    # garante o serviço em execução
    if so == "Linux":
        _cmd("sudo systemctl start docker || true")
    barra(0.8, "Verificando Docker")
    if docker_instalado():
        ok = _cmd("docker info >/dev/null 2>&1 || "
                  "(sudo systemctl start docker >/dev/null 2>&1; docker info >/dev/null 2>&1)")
        barra(1.0, "Docker pronto")
        return ok
    print(c("Docker não ficou disponível — siga as instruções de instalação "
            "e rode novamente.", "vermelho"))
    return False


def _dir_docker():
    """Returns the absolute path of `assets/docker`."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "docker")


def _compose_cmd():
    """Returns the available docker compose command (plugin v2 or v1) or None."""
    if shutil.which("docker"):
        try:
            r = subprocess.run(["docker", "compose", "version"],
                               capture_output=True, timeout=10)
            if r.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None


def instalar_docker_compose():
    """Installs the Docker Compose plugin when missing (best-effort, sudo)."""
    if _compose_cmd():
        return True
    so = platform.system()
    print(c("Docker Compose ausente — instalando...", "amarelo", True))
    if so == "Linux":
        if shutil.which("apt-get"):
            _cmd("sudo apt-get update && "
                 "sudo apt-get install -y docker-compose-plugin "
                 "docker-compose-v2 || sudo apt-get install -y docker-compose")
        elif shutil.which("dnf"):
            _cmd("sudo dnf install -y docker-compose-plugin")
        elif shutil.which("yum"):
            _cmd("sudo yum install -y docker-compose-plugin")
        else:
            print(c("Instale o Docker Compose manualmente: "
                    "https://docs.docker.com/compose/install/", "amarelo"))
            return False
    elif so == "Darwin":
        _cmd("brew install docker-compose")
    elif so == "Windows":
        _cmd("winget install -e --id Docker.DockerDesktop")  # Desktop inclui compose
    return _compose_cmd() is not None


def _porta_livre(porta):
    """True if the TCP port is free on localhost (not in use)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", int(porta))) != 0
    except Exception:
        return False  # erro/porta inválida → assume ocupada (nunca "livre")


def _verificar_postgres(dsn):
    """True if the PostgreSQL DSN is reachable (psycopg2 connect).

    Remove o sufixo `+psycopg2` do esquema (SQLAlchemy) porque o psycopg2
    só entende `postgresql://` — era a causa de nunca confirmar a conexão."""
    try:
        import psycopg2
        d = (dsn or "").replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(d)
        conn.close()
        return True
    except Exception:
        return False


def _servicos_otel_online(porta_grafana=3000):
    """True if the Grafana health endpoint answers (stack OTel online)."""
    try:
        import urllib.request
        r = urllib.request.urlopen(
            f"http://localhost:{porta_grafana}/api/health", timeout=3)
        return r.status == 200
    except Exception:
        return False


def _terminal_disponivel():
    """Returns a command template that opens a new terminal running `{cmd}`
    (Linux: gnome-terminal (sintaxe `-- bash -c`), konsole/xfce4-terminal/
    xterm; Win: PowerShell; Mac: Terminal.app)."""
    so = platform.system()
    if so == "Linux":
        if shutil.which("gnome-terminal"):
            return "gnome-terminal -- bash -c '{cmd}; exec bash'"
        for t, tmpl in {
            "konsole": "konsole -e bash -c '{cmd}; exec bash'",
            "xfce4-terminal": "xfce4-terminal -e bash -c '{cmd}; exec bash'",
            "x-terminal-emulator": "x-terminal-emulator -e bash -c '{cmd}; exec bash'",
            "xterm": "xterm -e bash -c '{cmd}; exec bash'",
        }.items():
            if shutil.which(t):
                return tmpl
    elif so == "Darwin":
        return ('osascript -e \'tell app "Terminal" '
                'to do script "{cmd}"\'')
    elif so == "Windows":
        return 'start powershell -NoExit -Command "{cmd}"'
    return None


def abrir_terminal(comando):
    """Opens a new terminal window running `comando` (best-effort)."""
    t = _terminal_disponivel()
    if not t:
        return False
    _cmd(t.format(cmd=comando))
    return True


def _status_docker(prefixo=""):
    """Prints the running docker containers (live status during setup)."""
    if not docker_instalado():
        return 0
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}: {{.Status}}"],
            capture_output=True, text=True, timeout=10)
        linhas = [l for l in r.stdout.splitlines() if l.strip()]
        if linhas:
            print(c("  Containers Docker:", "ciano"))
            for l in linhas:
                visivel = (not prefixo) or (prefixo in l)
                print(("   " + c(l, "verde")) if visivel else "   " + l)
        return len(linhas)
    except Exception:
        return 0


def _wsl_distros():
    """Lists installed WSL distributions (Windows)."""
    try:
        r = subprocess.run(["wsl", "--list", "--quiet"],
                           capture_output=True, text=True, timeout=20)
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _validar_senha(senha):
    """True if the password has no shell metacharacters (safe on stdin)."""
    return not re.search(r"[;|&\n$'\"\\ ]", str(senha or ""))


def configurar_docker_windows(cfg=None):
    """Guides Windows: installs WSL (light distro preferred), asks the WSL
    user/password and installs Docker Desktop for the containers.

    Segurança: a distro é revalidada contra a whitelist {debian, ubuntu,
    alpine}; o usuário segue o regex Linux `^[a-z_][a-z0-9_-]{0,31}$`; a senha
    é validada contra metacharacteres de shell e NUNCA vai no argv do comando
    — é enviada por stdin ao `chpasswd` e mascarada no print do `_cmd`."""
    print(c("Configuração do Docker no Windows...", "amarelo", True))
    distros = _wsl_distros()
    if not distros:
        print(c("WSL não configurado — instalando uma distro leve dedicada...",
                "amarelo"))
        escolha = perguntar(
            "Distro WSL dedicada [debian/ubuntu/alpine] (padrão debian — "
            "leve)", "debian", validos={"debian", "ubuntu", "alpine"})
        if escolha not in {"debian", "ubuntu", "alpine"}:
            escolha = "debian"  # revalidação da whitelist antes do comando
        _cmd(["wsl", "--install", "-d", escolha])
    distros = _wsl_distros()
    if distros:
        distro = distros[0]
        usuario = "intranet"
        while True:
            usuario = perguntar(f"Usuário do WSL ({distro}) (padrão intranet)",
                                "intranet")
            if re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", usuario):
                break
            print(c("Usuário inválido — use minúsculas, números, '_' ou '-' "
                    "(máx. 32). Tente novamente.", "amarelo"))
        senha = "intranet"
        while True:
            senha = perguntar(f"Senha do WSL ({distro}) (padrão intranet)",
                              "intranet")
            if _validar_senha(senha):
                break
            print(c("Senha inválida — evite espaços e caracteres de shell "
                    "(; | & $ ' \" \\). Tente novamente.", "amarelo"))
        # cria o usuário na distro e o define como padrão; a senha vai por
        # stdin (nunca interpolada no argv nem no shell local)
        script_usuario = (
            f"useradd -m -s /bin/bash {usuario} && "
            f"echo '{usuario} ALL=(ALL) NOPASSWD:ALL' >> "
            f"/etc/sudoers.d/{usuario} && "
            "read -r linha && echo \"$linha\" | chpasswd")
        if not _cmd(["wsl", "-d", distro, "-u", "root", "--", "sh", "-c",
                     script_usuario], entrada=f"{usuario}:{senha}\n"):
            print(c("  Falha ao criar o usuário WSL — verifique manualmente "
                    "(WSL integrado ao Docker Desktop).", "vermelho"))
        _cmd(["wsl", "--set-default-user", distro, usuario])
    # Docker Desktop (inclui o engine + compose)
    if not docker_instalado():
        print(c("Instalando o Docker Desktop...", "amarelo"))
        _cmd("winget install -e --id Docker.DockerDesktop")
    print(c("Abra o Docker Desktop e ative a integração com o WSL "
            "(Settings → Resources → WSL integration) antes de continuar.",
            "amarelo"))


def _garantir_docker_compose():
    """Ensures Docker + Docker Compose are available (installing if needed)."""
    if not docker_instalado():
        if not instalar_docker():
            return None
    if _compose_cmd():
        return _compose_cmd()
    if platform.system() == "Windows":
        configurar_docker_windows()
    else:
        instalar_docker_compose()
    return _compose_cmd()


def _pre_pull(imagens):
    """Pulls Docker images explicitly so failures (ex.: no internet/air-gapped)
    are visible and clearly reported before `up -d`."""
    for img in imagens:
        print(c(f"  Baixando imagem {img}...", "amarelo"))
        ok = _cmd(["docker", "pull", img])
        if not ok:
            print(c(f"    Falha ao baixar {img}. Sem acesso à internet? "
                    "Carregue a imagem offline (docker load -i imagem.tar) "
                    "ou use imagens já presentes localmente.", "vermelho"))


def iniciar_postgres(cfg):
    """Starts PostgreSQL (installs Docker/Compose if needed), opens a terminal
    with the compose logs/status, waits until the service is online and
    confirms connectivity before booting."""
    compose = os.path.join(_dir_docker(), "postgres", "docker-compose.yml")
    if not os.path.exists(compose):
        return False
    if not _porta_livre(cfg.get("porta_postgres", 5432)):
        return False  # porta ocupada — o wizard pede outra porta
    cmd = _garantir_docker_compose()
    if not cmd:
        return False
    _pre_pull(["postgres:16-alpine"])
    # `down` primeiro: recriação limpa quando a porta mudou (evita
    # "'ContainerConfig'" do docker-compose v1 ao reescrever o compose).
    _cmd(cmd + ["-f", compose, "down"])
    comando_up = cmd + ["-f", compose, "up", "-d"]
    _cmd(comando_up)
    abrir_terminal(" ".join(cmd + ["-f", compose, "ps"]))
    porta = cfg.get("porta_postgres", 5432)
    dsn = cfg.get("postgres_url", "")
    for i in range(30):
        barra(0.5 + i * 0.015, f"Aguardando PostgreSQL online (porta {porta})...")
        if _verificar_postgres(dsn):
            barra(1.0, "PostgreSQL online")
            fim_barra()
            return True
        time.sleep(1)
    fim_barra()
    return _verificar_postgres(dsn)


def _garantir_sdk_otel():
    """Garante o SDK OpenTelemetry instalado (instala via pip se ausente).

    Se `import opentelemetry` (api/sdk/exporter OTLP gRPC) falhar, instala os
    pacotes no interpretador atual e devolve True/False (fail-soft)."""
    try:
        import opentelemetry  # noqa: F401
        import opentelemetry.sdk  # noqa: F401
        import opentelemetry.exporter.otlp.proto.grpc  # noqa: F401
        return True
    except Exception:
        pass
    return _cmd([sys.executable, "-m", "pip", "install",
                 "opentelemetry-api", "opentelemetry-sdk",
                 "opentelemetry-exporter-otlp-proto-grpc"])


def iniciar_stack_otel(cfg=None):
    """Starts the OTel LGTM stack (installs Docker/Compose if needed), opens a
    terminal with the compose status and waits until Grafana is online."""
    if not _garantir_sdk_otel():
        print(c("  SDK OpenTelemetry indisponível — seguindo sem telemetria "
                "(o sistema roda normalmente).", "amarelo"))
        return False
    compose = os.path.join(_dir_docker(), "compose.yml")
    if not os.path.exists(compose):
        return False
    cmd = _garantir_docker_compose()
    if not cmd:
        return False
    _pre_pull(["grafana/grafana", "grafana/loki", "grafana/tempo",
               "grafana/mimir", "otel/opentelemetry-collector-contrib"])
    _cmd(cmd + ["-f", compose, "up", "-d"])
    abrir_terminal(" ".join(cmd + ["-f", compose, "ps"]))
    porta_grafana = (cfg or {}).get("porta_grafana", 3000)
    for i in range(40):
        barra(0.5 + i * 0.012, "Aguardando stack OTel online (Grafana)...")
        if _servicos_otel_online(porta_grafana):
            barra(1.0, "Stack OTel online")
            fim_barra()
            return True
        time.sleep(2)
    fim_barra()
    return _servicos_otel_online(porta_grafana)


# =============================================================================
# Assistente principal
# =============================================================================

def iniciar():
    """Main entry: shows the banner + initial prompt, returns the config dict.

    ENTER (ou não-TTY) → configuração padrão: SQLite apenas, sem Postgres e
    sem OpenTelemetry (boot simples e autossuficiente). 'sim'/'s' → modo de
    ativação, onde o usuário pode optar por subir PostgreSQL e/ou OTel."""
    banner()
    if not _TTY:
        print(c("Terminal não interativo — usando SQLite (configuração "
                "padrão, sem Postgres/OTel).", "amarelo"))
        return _config_padrao()
    try:
        resp = input(c("\nPressione ENTER para rodar com a configuração padrão,\n"
                       "ou digite 'sim' para entrar no modo de ativação.\n> ",
                       "ciano")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return _config_padrao()
    if resp in ("", "n", "nao", "não", "no", "default", "padrao"):
        return _config_padrao()

    print(c("\n===== MODO DE ATIVAÇÃO / CONFIGURAÇÃO =====", "ciano", True))
    cfg = _config_padrao()
    cfg["modo"] = "ativacao"
    print(c("Tudo será instalado e configurado automaticamente (Docker, "
            "PostgreSQL, OpenTelemetry).", "verde"))
    print(c("Responda as perguntas ou pressione ENTER para o padrão.", "verde"))

    # 1) Banco de dados (configuração da aplicação)
    bt = perguntar("Backend de banco [sqlite/postgres] (padrão sqlite)",
                   "sqlite", validos={"sqlite", "postgres"})
    cfg["banco_tipo"] = bt

    # 2) Serviços — pergunta PRIMEIRO se ativa; só então a porta (se sim)
    print(c("\nAtivação dos serviços (independentes entre si):", "ciano", True))
    subir_pg = perguntar(
        "Subir/ativar o PostgreSQL (container)? [sim/nao] (padrão "
        + ("sim" if bt == "postgres" else "nao") + ")",
        "sim" if bt == "postgres" else "nao",
        validos={"sim", "s", "nao", "não", "n"})
    cfg["subir_postgres"] = subir_pg in ("sim", "s")
    if cfg["subir_postgres"]:
        resp_porta_pg = perguntar(
            "  Porta do PostgreSQL (padrão 5432)", "5432", valido_num=True,
            faixa=(1, 65535))
        cfg["porta_postgres"] = _porta_valida(resp_porta_pg, 5432)
        cfg["postgres_url"] = (
            f"postgresql+psycopg2://intranet:intranet"
            f"@localhost:{cfg['porta_postgres']}/intranet")
    subir_otel = perguntar(
        "Subir/ativar o OpenTelemetry (Grafana+Loki+Tempo+Mimir)? "
        "[sim/nao] (padrão sim)",
        "sim", validos={"sim", "s", "nao", "não", "n"})
    cfg["otel_ativo"] = subir_otel in ("sim", "s")
    if cfg["otel_ativo"]:
        resp_porta_grafana = perguntar(
            "  Porta do Grafana (painel da telemetria) (padrão 3000)",
            "3000", valido_num=True, faixa=(1, 65535))
        cfg["porta_grafana"] = _porta_valida(resp_porta_grafana, 3000)

    # 3) Porta do SITE — sempre necessária
    cfg["porta_site"] = _porta_valida(perguntar(
        "Porta do SITE (aplicação — documentação em /documentacao, "
        "mesma porta) (padrão 8080)", "8080", valido_num=True,
        faixa=(1, 65535)), 8080)

    # 4) Execução — sobe os serviços escolhidos e aguarda ficarem online
    try:
        if cfg["subir_postgres"]:
            print(c("\nSubindo PostgreSQL...", "amarelo", True))
            ok_pg = False
            tentativas = 0
            if not _porta_livre(cfg["porta_postgres"]):
                resp = perguntar(
                    f"  A porta {cfg['porta_postgres']} já está em uso "
                    "(Postgres nativo ou outro serviço). Informar OUTRA "
                    "porta, ou ENTER para usar SQLite: ", "", valido_num=True,
                    faixa=(1, 65535))
                if not resp:
                    ok_pg = False
                else:
                    cfg["porta_postgres"] = _porta_valida(
                        resp, cfg["porta_postgres"])
                    cfg["postgres_url"] = (
                        f"postgresql+psycopg2://intranet:intranet"
                        f"@localhost:{cfg['porta_postgres']}/intranet")
                    aplicar_portas(cfg)
            while not ok_pg and tentativas < 5:
                ok_pg = iniciar_postgres(cfg)
                if not ok_pg:
                    resp = perguntar(
                        f"  PostgreSQL não subiu na porta {cfg['porta_postgres']}. "
                        "Informar OUTRA porta, ou ENTER para usar SQLite: ",
                        "", valido_num=True, faixa=(1, 65535))
                    if not resp:
                        break
                    cfg["porta_postgres"] = _porta_valida(
                        resp, cfg["porta_postgres"])
                    cfg["postgres_url"] = (
                        f"postgresql+psycopg2://intranet:intranet"
                        f"@localhost:{cfg['porta_postgres']}/intranet")
                    aplicar_portas(cfg)
                tentativas += 1
            if not ok_pg:
                print(c("  PostgreSQL não ficou acessível — usando SQLite como "
                        "fallback.", "vermelho", True))
                cfg["banco_tipo"] = "sqlite"
                cfg["subir_postgres"] = False
        elif bt == "postgres":
            if not _verificar_postgres(cfg["postgres_url"]):
                print(c("  Sem PostgreSQL acessível (container não iniciado) — "
                        "usando SQLite como fallback.", "vermelho", True))
                cfg["banco_tipo"] = "sqlite"
        if cfg["otel_ativo"]:
            print(c("\nSubindo OpenTelemetry...", "amarelo", True))
            iniciar_stack_otel(cfg)
    except KeyboardInterrupt:
        print(c("\nInterrompido pelo usuário — continuando com SQLite e sem "
                "telemetria.", "amarelo", True))
        cfg["banco_tipo"] = "sqlite"
        cfg["subir_postgres"] = False
        cfg["otel_ativo"] = False

    # 5) Persiste e aplica portas
    aplicar_banco(cfg)
    aplicar_portas(cfg)
    # Persiste a escolha do OTel — a opção "nao" sobrevive ao restart
    # (o main.py consulta get_config("otel_ativo", "1") == "1").
    try:
        from mod_intranet.bd_conexao import set_config
        set_config("otel_ativo", "1" if cfg.get("otel_ativo") else "0")
    except Exception as e:
        print(c(f"[setup] aviso ao persistir otel_ativo: {e}", "amarelo"))
    print(c("\nResumo:", "ciano", True))
    print(f"  Banco:            {cfg['banco_tipo']}")
    print(f"  Subir PostgreSQL: {'sim' if cfg.get('subir_postgres') else 'não'}")
    if cfg.get("subir_postgres"):
        print(f"  Porta PostgreSQL: {cfg['porta_postgres']}")
    print(f"  OpenTelemetry:    {'sim' if cfg['otel_ativo'] else 'não'}")
    if cfg.get("otel_ativo"):
        print(f"  Porta Grafana:    {cfg['porta_grafana']}")
    print(f"  Porta do site:    {cfg['porta_site']}")
    print(c("\nServiços prontos — inicializando os bancos de dados e subindo "
            "o sistema (pode levar alguns minutos na primeira vez)...",
            "amarelo", True))
    return cfg


def progresso_boot(passos):
    """Runs a list of (nome, callable) boot steps with a progress bar."""
    total = len(passos)
    for i, (nome, fn) in enumerate(passos, start=1):
        barra(i / total, nome)
        try:
            fn()
        except Exception as e:
            fim_barra()
            print(c(f"  [boot] falha em '{nome}': {e}", "vermelho"))
    fim_barra()