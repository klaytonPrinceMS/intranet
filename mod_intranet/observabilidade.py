"""Observabilidade central do Intranet (loguru).

Logs de erro / debug / info gravados em arquivo com:
  - rotação configurável (tempo, ex.: "1 month", ou tamanho, ex.: "50 MB");
  - retenção configurável (padrão "4 months") — arquivos rotacionados são
    compactados em .zip e mantidos até o prazo de retenção;
  - nível configurável (DEBUG/INFO/WARNING/ERROR);
  - opção de limpeza total dos logs.

Todas as opções vivem em tb_config (área de administração do módulo Intranet):
  log_ativo, log_nivel, log_rotacao, log_retencao.
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

DEFAULTS = {
    CFG_ATIVO: "1",
    CFG_NIVEL: "INFO",
    CFG_ROTACAO: "1 month",
    CFG_RETENCAO: "4 months",
}

_sinks = []

# Módulos com arquivo de log próprio (separação por módulo)
MODULOS = ["gest_cad_usuario", "blog", "edit_pdf",
           "renomear_empenho", "auditoria", "solicita_impressao"]

_FMT = ("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{module}:{function}:{line} | {message}")


def _obter(chave, padrao):
    try:
        from mod_intranet.conexao_bd import get_config
        return get_config(chave, padrao)
    except Exception:
        return padrao


def _nivel_valido(v):
    v = (v or "INFO").upper()
    return v if v in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO"


def configurar():
    """(Re)configura os sinks do loguru conforme tb_config.

    - Arquivo core (intranet_*.log) para logs do sistema sem módulo explícito.
    - Um arquivo por módulo (ex.: solicita_impressao_*.log) para separação.
    - Console (terminal) SOMENTE quando rodando via python (não congelado);
      no executável (.exe / auto-py-to-exe) os logs ficam apenas no arquivo.
    """
    global _sinks
    try:
        logger.remove()  # remove tudo (inclusive o stderr padrão do loguru)
        _sinks = []
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

        # Console: só em execução via terminal (não em executável congelado)
        console = "nao"
        if not getattr(sys, "frozen", False):
            logger.add(sys.stderr, level=nivel, format=_FMT, filter=lambda r: True)
            console = "sim"

        logger.info(f"Observabilidade ativa | nivel={nivel} rotacao={rotacao} "
                     f"retencao={retencao} | console={console}")
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
