"""Central Intranet observability (loguru).

Observabilidade central do Intranet (loguru).

Logs de erro / debug / info gravados em arquivo com:
  - rotação configurável (tempo, ex.: "1 month", ou tamanho, ex.: "50 MB");
  - retenção configurável (padrão "4 months") — arquivos rotacionados são
    compactados em .zip e mantidos até o prazo de retenção;
  - nível configurável (DEBUG/INFO/WARNING/ERROR);
  - opção de limpeza total dos logs.

Todas as opções vivem em tb_config (área de administração do módulo Intranet):
  log_ativo, log_nivel, log_rotacao, log_retencao, log_console
  (auto/sempre/nunca), log_otel_envio, log_otel_nivel.
"""
import os
import sys
import glob

from loguru import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Logs ficam na MESMA pasta do programa (onde main.py ou o executável roda),
# nunca em pasta temporária. Usa o diretório do entrypoint (sys.argv[0]);
# se indisponível, cai no diretório do projeto. Compatível com auto-py-to-exe.
def _pasta_programa():
    try:
        if getattr(sys, "frozen", False):  # PyInstaller / auto-py-to-exe
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        return BASE_DIR


LOG_DIR = os.path.join(_pasta_programa(), "logs")

# Chaves de configuração (tb_config central)
CFG_ATIVO = "log_ativo"
CFG_NIVEL = "log_nivel"
CFG_ROTACAO = "log_rotacao"
CFG_RETENCAO = "log_retencao"
CFG_CONSOLE = "log_console"
CFG_OTEL_ENVIO = "log_otel_envio"
CFG_OTEL_NIVEL = "log_otel_nivel"

DEFAULTS = {
    CFG_ATIVO: "1",
    CFG_NIVEL: "INFO",
    CFG_ROTACAO: "1 month",
    CFG_RETENCAO: "4 months",
    CFG_CONSOLE: "auto",
    CFG_OTEL_ENVIO: "1",
    CFG_OTEL_NIVEL: "DEBUG",
}

_sinks = []

# Módulos com arquivo de log próprio (separação por módulo)
MODULOS = ["gest_cad_usuario", "blog", "edit_pdf",
           "renomear_empenho", "auditoria", "solicita_impressao"]

_FMT = ("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{module}:{function}:{line} | {message}")


def _obter(chave, padrao):
    try:
        from mod_intranet.bd_conexao import get_config
        return get_config(chave, padrao)
    except Exception:
        return padrao


def _console_valido(v):
    """Validates the console mode (auto/sempre/nunca), defaulting to auto.

    Valida o modo do console (auto/sempre/nunca); padrão `auto`."""
    v = (v or "auto").strip().lower()
    return v if v in ("auto", "sempre", "nunca") else "auto"


def _nivel_valido(v):
    v = (v or "INFO").upper()
    return v if v in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO"


def configurar():
    """(Re)configura os sinks do loguru conforme tb_config.

    - Arquivo core (intranet_*.log) para logs do sistema sem módulo explícito.
    - Um arquivo por módulo (ex.: solicita_impressao_*.log) para separação.
    - Console (terminal) conforme `log_console`: `auto` (só via python,
      nunca no executável congelado), `sempre` ou `nunca` (só arquivo).
    - Bridge loguru→OTel (Loki) conforme `log_otel_envio`/`log_otel_nivel`.
    """
    global _sinks, _sink_otel_loguru
    try:
        logger.remove()  # remove tudo (inclusive o stderr padrão do loguru)
        _sinks = []
        _sink_otel_loguru = None
        if _obter(CFG_ATIVO, "1") != "1":
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        nivel = _nivel_valido(_obter(CFG_NIVEL, "INFO"))
        rotacao = _obter(CFG_ROTACAO, "1 month") or "1 month"
        retencao = _obter(CFG_RETENCAO, "4 months") or "4 months"

        def _add(nome_arquivo, filtro):
            sid = logger.add(
                os.path.join(LOG_DIR, nome_arquivo),
                level=nivel,
                rotation=rotacao,
                retention=retencao,
                compression="zip",
                encoding="utf-8",
                enqueue=True,
                backtrace=True,
                diagnose=True,
                format=_FMT,
                filter=filtro,
            )
            _sinks.append(sid)

        # Core: logs sem módulo marcado (sistema/núcleo)
        _add("intranet_{time:YYYY-MM-DD}.log",
             lambda r: not r["extra"].get("modulo"))
        # Um arquivo dedicado por módulo
        for m in MODULOS:
            _add(f"{m}_{{time:YYYY-MM-DD}}.log",
                 (lambda r, m=m: r["extra"].get("modulo") == m))

        # Console: auto = só via terminal (nunca no executável congelado);
        # sempre/nunca forçam com/sem console (só arquivo quando nunca).
        modo_console = _console_valido(_obter(CFG_CONSOLE, "auto"))
        console = "nao"
        if modo_console == "sempre" or (
                modo_console == "auto" and not getattr(sys, "frozen", False)):
            logger.add(sys.stderr, level=nivel, format=_FMT, filter=lambda r: True)
            console = "sim"

        # Bridge: roteia logs do loguru para o OpenTelemetry (→ Loki via collector).
        # loguru aceita instâncias de logging.Handler como sink: cada record é
        # convertido e enviado ao LoggerProvider OTel. Sem isso, logs via loguru()
        # (o que o app usa) NUNCA chegam ao Loki — ficam presos no arquivo/console.
        # `log_otel_envio=0` mantém o log só local; `log_otel_nivel` filtra o envio.
        envio_otel = _obter(CFG_OTEL_ENVIO, "1") == "1"
        nivel_otel = _nivel_valido(_obter(CFG_OTEL_NIVEL, "DEBUG"))
        if envio_otel and _sink_otel_loguru is None:
            try:
                from mod_intranet.otel_integracao import (
                    OTEL_AVAILABLE, obter_handler_log,
                )
                _h = obter_handler_log()
                if OTEL_AVAILABLE and _h:
                    logger.add(_h, level=nivel_otel)
                    _sink_otel_loguru = _h
            except Exception as e:
                print(f"[observabilidade] falha ao bridge OTel loguru: {e}")

        logger.info(f"Observabilidade ativa | nivel={nivel} rotacao={rotacao} "
                    f"retencao={retencao} | console={console} "
                    f"otel_envio={'sim' if envio_otel else 'nao'} "
                    f"otel_nivel={nivel_otel}")
    except Exception as e:
        # Nunca deixar o log quebrar o boot do sistema
        print(f"[observabilidade] falha ao configurar logger: {e}")


def limpar_todos():
    """Remove TODOS os arquivos de log (ativos e compactados em .zip)."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        removidos = 0
        for pad in ("*.log", "*.log.zip", "*.log.*.zip"):
            for f in glob.glob(os.path.join(LOG_DIR, pad)):
                try:
                    os.remove(f)
                    removidos += 1
                except OSError:
                    pass
        return True, f"{removidos} arquivo(s) de log removido(s)"
    except Exception as e:
        return False, str(e)


def gerar_logs_teste_niveis():
    """Emits one log per level (DEBUG/INFO/WARNING/ERROR) for admin verification.

    Emite um registro de log em cada um dos 4 níveis do loguru com a descrição
    "Gestão de nível de logs". Serve ao administrador que acabou de salvar as
    configurações de observabilidade: no terminal/console aparecem os níveis
    permitidos, e no ARQUIVO apenas os eventos do NÍVEL MÍNIMO para cima são
    gravados — provando que o filtro de nível está ativo e que a cadeia
    arquivo/rotação/retenção está funcionando."""
    try:
        logger.debug("Gestão de nível de logs — teste de nível DEBUG")
        logger.info("Gestão de nível de logs — teste de nível INFO")
        logger.warning("Gestão de nível de logs — teste de nível WARNING")
        logger.error("Gestão de nível de logs — teste de nível ERROR")
    except Exception as e:
        # Última saída caso o loguru falhe (sink quebrado, disco etc.): print
        # no terminal garante que algo foi gravado.
        print(f"[observabilidade] falha ao gerar logs de teste por nível: {e}")


def instalar_excepthook():
    """Captura exceções não tratadas (thread principal e loop assíncrono)."""
    def hook(tipo, valor, tb):
        logger.opt(exception=(tipo, valor, tb)).error("Exceção não tratada")
    sys.excepthook = hook
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.set_exception_handler(
                lambda lp, ctx: logger.opt(exception=ctx.get("exception")).error(
                    f"Exceção em loop assíncrono: {ctx.get('message')}"))
    except Exception:
        pass


def get_logger(modulo=None):
    """Retorna o logger. Se `modulo` for informado, o registro é marcado para
    ir também ao arquivo dedicado daquele módulo (ex.: solicita_impressao_*.log)."""
    if modulo:
        return logger.bind(modulo=modulo)
    return logger
