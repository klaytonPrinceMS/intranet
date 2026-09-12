"""Teste unitário de e-mail, documentação e observabilidade (sem I/O real).

Cobre funções sem cobertura direta na suíte:
- `email_util.enviar_email` (sem config, com mock SMTP ok/falha, anexo
  inexistente ignorado) e `testar_conexao` (sem servidor, mock ok/falha);
- `documentacao.reconstruir` (build ok/falha com mocks — sem rodar mkdocs
  nem abrir porta), `porta_documentacao`, `montar` sem site/;
- `observabilidade._console_valido`, `_nivel_valido`, `get_logger`,
  `configurar` (em LOG_DIR isolado) e `limpar_todos`.

AUTOCONTIDO: snapshot/restore das chaves smtp_*/log_*; SMTP e build com
mocks; LOG_DIR redirecionado para /tmp.

Execute: .venv/bin/python assets/test/test_email_docs_obs.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from mod_intranet.bd_conexao import get_config, set_config, init_db  # noqa: E402
from mod_intranet import email_util, documentacao, observabilidade  # noqa: E402

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


print("INICIANDO TESTES — email_util + documentacao + observabilidade")
init_db()

CHAVES = ["smtp_servidor", "smtp_porta", "smtp_usuario", "smtp_senha",
          "smtp_tls", "smtp_de", "log_ativo", "log_nivel", "log_console",
          "log_otel_envio", "log_otel_nivel"]
ORIG = {k: get_config(k, None) for k in CHAVES}
TMP = tempfile.mkdtemp(prefix="qa_maildocs_")
LOG_ORIG = observabilidade.LOG_DIR

try:
    # ================== EMAIL ==================
    print("-- email_util --")
    set_config("smtp_servidor", "")
    set_config("smtp_usuario", "")
    ok, msg = email_util.enviar_email("a@b.c", "Assunto", "Corpo")
    check(ok is False and "configurado" in msg,
          "enviar sem SMTP configurado recusa com mensagem clara")
    ok, msg = email_util.testar_conexao()
    check(ok is False and "Servidor" in msg,
          "testar_conexao sem servidor recusa sem abrir socket")

    set_config("smtp_servidor", "smtp.qa.local")
    set_config("smtp_porta", "587")
    set_config("smtp_usuario", "qa@local")
    set_config("smtp_senha", "segredo")
    set_config("smtp_tls", "1")
    cfg = email_util._cfg()
    check(cfg["servidor"] == "smtp.qa.local" and cfg["porta"] == 587
          and cfg["tls"] is True and cfg["de"] == "qa@local",
          "_cfg lê as 6 chaves smtp_* (de herda usuario)")

    import smtplib as _smtplib
    _smtp_orig = _smtplib.SMTP
    eventos = []

    class _SMTPOk:
        def __init__(self, *a, **k):
            eventos.append(("conectar", a))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            eventos.append(("tls",))

        def login(self, u, s):
            eventos.append(("login", u))

        def sendmail(self, de, para, corpo):
            eventos.append(("enviar", de, para))

    _smtplib.SMTP = _SMTPOk
    try:
        ok, msg = email_util.testar_conexao()
        check(ok is True and "OK" in msg,
              "testar_conexao com mock SMTP devolve OK")
        check(any(e[0] == "tls" for e in eventos),
              "TLS acionado quando smtp_tls=1")
        eventos.clear()
        ok, msg = email_util.enviar_email(
            "dest@x.y", "Oi", "<b>html</b>", html=True,
            anexos=["/caminho/que/nao/existe.pdf"])
        check(ok is True and any(e[0] == "enviar" for e in eventos),
              "enviar com mock SMTP entrega (anexo inexistente ignorado)")
    finally:
        _smtplib.SMTP = _smtp_orig

    class _SMTPFalha(_SMTPOk):
        def __init__(self, *a, **k):
            raise ConnectionRefusedError("porta fechada (simulada)")

    _smtplib.SMTP = _SMTPFalha
    try:
        ok, msg = email_util.testar_conexao()
        check(ok is False and "porta fechada" in msg,
              "falha de conexão vira (False, msg) sem exceção")
        ok, _ = email_util.enviar_email("d@x.y", "A", "B")
        check(ok is False, "falha de envio vira False sem exceção")
    finally:
        _smtplib.SMTP = _smtp_orig

    # ================== DOCUMENTAÇÃO ==================
    print("-- documentacao --")
    check(documentacao.porta_documentacao() == 8000,
          "porta_documentacao default 8000")
    _build_orig = documentacao._build
    _montar_orig = documentacao.montar
    _srv_orig = documentacao.iniciar_servidor
    documentacao.iniciar_servidor = lambda *a, **k: True
    try:
        documentacao._build = lambda: (False, "mkdocs quebrou (simulado)")
        ok, msg = documentacao.reconstruir()
        check(ok is False and "mkdocs quebrou" in msg,
              "reconstruir com build falho devolve erro sem exceção")
        documentacao._build = lambda: (True, "")
        documentacao.montar = lambda: True
        ok, msg = documentacao.reconstruir()
        check(ok is True and "localhost" in msg,
              "reconstruir com build ok devolve URL da documentação")
        documentacao.montar = lambda: False
        ok, msg = documentacao.reconstruir()
        check(ok is True and "regenerados" in msg,
              "reconstruir sem montar ainda devolve sucesso parcial")
    finally:
        documentacao._build = _build_orig
        documentacao.montar = _montar_orig
        documentacao.iniciar_servidor = _srv_orig
    check(documentacao.montar() is True
          and documentacao.montar() is True,
          "montar com site/ gerado monta e é idempotente (não derruba)")
    ok, erro = documentacao._build if False else (None, None)
    check(callable(documentacao.construir_e_montar_documentacao),
          "construir_e_montar_documentacao exposta (build+monta+serve)")

    # ================== OBSERVABILIDADE ==================
    print("-- observabilidade --")
    check(observabilidade._console_valido("sempre") == "sempre"
          and observabilidade._console_valido("bogus") == "auto",
          "_console_valido aceita auto/sempre/nunca, resto vira auto")
    check(observabilidade._nivel_valido("DEBUG") == "DEBUG"
          and observabilidade._nivel_valido("BOGUS") == "INFO",
          "_nivel_valido aceita níveis válidos, resto vira INFO")
    lg = observabilidade.get_logger("qa_teste")
    check(lg is not None, "get_logger devolve logger do módulo")
    lg.info("linha de teste qa (isolada)")
    check(True, "log em nível info não levanta exceção")

    observabilidade.LOG_DIR = os.path.join(TMP, "logs")
    set_config("log_ativo", "1")
    set_config("log_nivel", "INFO")
    set_config("log_console", "nunca")
    set_config("log_otel_envio", "0")
    observabilidade.configurar()
    gerados = [f for f in os.listdir(observabilidade.LOG_DIR)
               if f.endswith(".log")]
    check(len(gerados) >= 1,
          f"configurar cria arquivos de log no LOG_DIR ({len(gerados)})")
    ok, msg = observabilidade.limpar_todos()
    restantes = [f for f in os.listdir(observabilidade.LOG_DIR)
                 if ".log" in f]
    check(ok is True and not restantes,
          "limpar_todos remove os logs do LOG_DIR isolado")
finally:
    observabilidade.LOG_DIR = LOG_ORIG
    try:
        observabilidade.configurar()
    except Exception:
        pass
    for k, v in ORIG.items():
        try:
            if v is None:
                from mod_intranet.bd_conexao import get_connection
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM tb_config WHERE chave=?", (k,))
                    conn.commit()
                finally:
                    conn.close()
            else:
                set_config(k, v)
        except Exception:
            pass
    import shutil as _sh
    _sh.rmtree(TMP, ignore_errors=True)

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
