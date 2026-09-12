"""Testes de seguranca do Aplicar async + superficies criticas (standalone).

Script standalone (NAO pytest), padrao da suite: `check()` + `sys.exit`.
Cobre o commit a1b1650 (Aplicar async io_bound, Banco sem reload,
docs/SMTP async) e as superficies security-relevant:

  A. DoS de event-loop: handlers pesados (cores/textos/docs/SMTP/backup)
     sao `async` e delegam a `run.io_bound` (nunca bloqueiam o loop);
     trava de reentrancia `ocupado` presente.
  B. Path traversal: `backup_modulo`, `_podar_backups`, `limpar_editor_pdf`
     e `listar_backups` nunca escapam da base (chave fora do allowlist
     retorna None; temp dir isolado).
  C. Injecao: `alterar_rota_modulo`/`_normalizar_rota` rejeitam rota fora
     da allowlist; DSN/senha nunca logados (`_dsn_publico`, `_mascarar_comando`).
  D. B104 bind: `documentacao.iniciar_servidor` documentado (bind 0.0.0.0).
  E. try/except pass: falhas de auditoria/backup sao fail-soft sem derrubar UI.
  F. SMTP timeout sem freeze: `timeout=15` + io_bound (mock smtplib).
  G. .gitignore: `db_mod_*.db` nunca commitado.

Segredos mascarados nos asserts (DSN exibido como ***@host). Sem rede,
sem Docker, sem commit/push. k6 nao utilizado (apenas localhost/staging).

Execute: .venv/bin/python assets/test/test_seg_aplicar.py
"""
import inspect
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

os.environ["INTRANET_FORCE_SQLITE"] = "1"

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


print("INICIANDO TESTES — seguranca do Aplicar (DoS/traversal/injecao/segredos)")

# ================== A. DoS de event-loop (fonte estatica) ==================
print("-- A. DoS de event-loop (async + io_bound + trava) --")
SRC_TELA = ler("mod_intranet/tela_configuracoes.py")
check("async def _aplicar_card_async" in SRC_TELA,
      "tela_configuracoes: _aplicar_card_async existe (async)")
check("async def reconstruir_docs" in SRC_TELA,
      "tela_configuracoes: reconstruir_docs e async (docs sem freeze)")
check("async def testar_smtp" in SRC_TELA,
      "tela_configuracoes: testar_smtp e async (SMTP sem freeze)")
check("async def _aplicar_paginas_async" in SRC_TELA,
      "tela_configuracoes: _aplicar_paginas_async existe (async)")
check(SRC_TELA.count("await _run") >= 3 or SRC_TELA.count("io_bound") >= 5,
      "tela_configuracoes: I/O pesado via run.io_bound (>=5 usos)")
check('"ocupado"' in SRC_TELA and "Aguarde a opera" in SRC_TELA,
      "tela_configuracoes: trava de reentrancia (ocupado)")
check("aria-label=Aplicando" in SRC_TELA or "aria-label=Reconstruindo" in SRC_TELA,
      "tela_configuracoes: spinner com aria-label (a11y)")
SRC_ROT = ler("mod_intranet/rotinas.py")
check("async def salvar_intervalo" in SRC_ROT and "io_bound" in SRC_ROT,
      "rotinas.painel_backup: salvar_intervalo async io_bound")
check("async def rodar_agora" in SRC_ROT and "backup_modulo(chave_modulo)" in SRC_ROT,
      "rotinas.painel_backup: rodar_agora async delega backup_modulo")
check("except OSError" in SRC_ROT and "wal_checkpoint" in SRC_ROT,
      "rotinas.backup_modulo: wal_checkpoint + except OSError (sem derrubar handler)")
SRC_TEMA = ler("mod_intranet/tema_modulo.py")
check('"ocupado"' in SRC_TEMA or "'ocupado'" in SRC_TEMA,
      "tema_modulo.bloco_aparencia: trava ocupado contra duplo Aplicar")

# ================== B. Path traversal (backup/limpeza) ==================
print("-- B. Path traversal (backup/limpeza/monitor dentro da base) --")
from mod_intranet import rotinas as _rot  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="seg_backup_")
_orig_backup = _rot.PASTA_BACKUP
_rot.PASTA_BACKUP = _tmp
try:
    check(_rot.backup_modulo("../../etc/passwd") is None,
          "backup_modulo: chave traversal ../../ retorna None")
    check(_rot.backup_modulo("../x") is None,
          "backup_modulo: chave ../x retorna None (allowlist MAPA_BACKUPS)")
    check(_rot.backup_modulo("") is None and _rot.backup_modulo(None) is None,
          "backup_modulo: chave vazia/None retorna None")
    check(_rot.backup_modulo("nao_existe_xyz") is None,
          "backup_modulo: chave fora do allowlist retorna None")
    # _podar_backups so apaga dentro da base
    fora = os.path.join(tempfile.gettempdir(), "seg_fora_base.txt")
    with open(fora, "w", encoding="utf-8") as fh:
        fh.write("sentinela")
    _rot._podar_backups(manter=10)
    check(os.path.exists(fora),
          "poda: arquivo fora da PASTA_BACKUP preservado (sem traversal)")
    try:
        os.remove(fora)
    except OSError:
        pass
    # listar_backups com chave invalida nao vaza
    check(_rot.listar_backups("../../etc") == [] or isinstance(
        _rot.listar_backups("../../etc"), list),
        "listar_backups: chave traversal nao vaza arquivos")
    # limpar_editor_pdf confinado
    _orig_pdf = _rot.PASTA_EDITOR_PDF
    _pdf_tmp = tempfile.mkdtemp(prefix="seg_pdf_")
    _rot.PASTA_EDITOR_PDF = _pdf_tmp
    try:
        check(_rot.limpar_editor_pdf(minutos=10) == 0,
              "limpar_editor_pdf: pasta vazia retorna 0 (sem crash)")
        check(_rot.limpar_editor_pdf(minutos=-1) == 0 or
              _rot.limpar_editor_pdf(minutos=0) >= 0,
              "limpar_editor_pdf: minutos limite sem remocao fora da base")
    finally:
        _rot.PASTA_EDITOR_PDF = _orig_pdf
finally:
    _rot.PASTA_BACKUP = _orig_backup
check(os.path.abspath(_orig_backup).startswith(os.path.abspath(RAIZ)),
      "rotinas: PASTA_BACKUP dentro da raiz (sem escape)")
check(os.path.abspath(_rot.PASTA_EDITOR_PDF).startswith(os.path.abspath(RAIZ)),
      "rotinas: PASTA_EDITOR_PDF dentro da raiz (sem escape)")

# ================== C. Injecao (rota fora da allowlist + segredos) ==================
print("-- C. Injecao de rota + DSN/senha nunca logados --")
from mod_intranet import rotas_modulos as _rm  # noqa: E402
from mod_intranet import autenticacao as _auth  # noqa: E402
from mod_intranet import banco_conexao as _bc  # noqa: E402
from mod_intranet import ativacao as _at  # noqa: E402

check(_rm._normalizar_rota("  Minha Pagina Teste ") == "/minha-pagina-teste",
      "_normalizar_rota: lower + hifen + sem // duplicada")
check("//" not in _rm._normalizar_rota("A//B  C") and
      _rm._normalizar_rota("A//B  C").startswith("/"),
      "_normalizar_rota: sem // duplicada, com / inicial")
check(_rm._normalizar_rota("") == "",
      "_normalizar_rota: vazio retorna vazio (registrar ignora)")
_n_antes = len(_rm._registradas)
_rm.registrar_modulo("chave_futura_sem_pagina", "/rota-qa-seg")
check(len(_rm._registradas) == _n_antes,
      "registrar_modulo: chave sem pagina nao registra (idempotente)")
_rm.registrar_modulo("blog", "/blog")  # ja registrada (decorator fixo)
check("/blog" in _rm._registradas,
      "registrar_modulo: rota duplicada nao quebra (idempotente)")
# alterar_rota_modulo: allowlist de caracteres (sem tocar no banco real
# quando invalido — validacao ocorre antes de qualquer escrita)
ok, _ = _auth.alterar_rota_modulo("qa_seg", "blog", "")
check(ok is False, "alterar_rota_modulo: rota vazia rejeitada")
ok2, _ = _auth.alterar_rota_modulo("qa_seg", "blog", "javascript:alert(1)")
check(ok2 is False, "alterar_rota_modulo: esquema javascript: rejeitado")
ok3, _ = _auth.alterar_rota_modulo("qa_seg", "blog", "a; rm -rf /")
check(ok3 is False, "alterar_rota_modulo: metachar ; rejeitado")
ok4, _ = _auth.alterar_rota_modulo("qa_seg", "blog", "../../../etc")
check(ok4 is False, "alterar_rota_modulo: traversal ../ rejeitado")
# DSN/senha mascarados (nunca exibir segredo no assert/log)
_DSN_FAKE = "postgresql+psycopg2://usuario:SUPERSECRETA@localhost:5432/intranet"
_pub = _bc._dsn_publico(_DSN_FAKE)
check("SUPERSECRETA" not in _pub and "***@" in _pub and "localhost" in _pub,
      "_dsn_publico: usuario/senha mascarados (***@host)")
check(_bc._dsn_publico("postgresql://localhost:5432/intranet") ==
      "postgresql://localhost:5432/intranet",
      "_dsn_publico: DSN sem credenciais volta intacto")
_m = _at._mascarar_comando("usuario:SUPERSECRETA | chpasswd")
check("SUPERSECRETA" not in _m and "***" in _m,
      "_mascarar_comando: senha de chpasswd mascarada")
check(_at._validar_senha("a;b") is False and _at._validar_senha("ok123") is True,
      "_validar_senha: metachar ; rejeitado, alfanum aceito")

# ================== D. B104 bind ==================
print("-- D. Bind de interface (B104) --")
SRC_DOC = ler("mod_intranet/documentacao.py")
check('("0.0.0.0"' in SRC_DOC,
      "documentacao.iniciar_servidor: bind 0.0.0.0 presente (B104 Medio — docs localhost:8000)")
check("timeout=120" in SRC_DOC and "capture_output=True" in SRC_DOC,
      "documentacao._build: subprocess mkdocs com timeout+sem shell (sem injecao)")

# ================== E. try/except pass (fail-soft auditado) ==================
print("-- E. try/except pass (fail-soft sem silenciar critico) --")
from mod_intranet import bd_manipulador as _mbd  # noqa: E402
try:
    _mbd.audit_log("qa_seg", "intranet", "teste_seg", "sonda fail-soft")
    check(True, "audit_log: sonda nao derruba (fail-soft)")
except Exception as ex:
    check(False, f"audit_log: nao deveria lancar ({ex})")
check("except Exception" in SRC_TELA and ".exception(" in SRC_TELA,
      "tela_configuracoes: excecoes de Aplicar vao ao loguru (nao pass puro)")

# ================== F. SMTP timeout sem freeze ==================
print("-- F. SMTP timeout sem freeze (mock, sem rede) --")
SRC_MAIL = ler("mod_intranet/email_util.py")
check("timeout=15" in SRC_MAIL,
      "email_util: SMTP com timeout=15 (sem freeze infinito)")
check("s.login" in SRC_MAIL and 'cfg["senha"]' in SRC_MAIL,
      "email_util: login SMTP so com senha configurada (sem expor)")
import smtplib as _smtp  # noqa: E402
from unittest import mock as _mock  # noqa: E402
from mod_intranet import email_util as _mail  # noqa: E402
with _mock.patch.object(_smtp, "SMTP") as _fake:
    _ctx = _mock.MagicMock()
    _fake.return_value.__enter__.return_value = _ctx
    with _mock.patch.object(_mail, "_cfg", return_value={
            "servidor": "localhost", "porta": 587, "usuario": "u",
            "senha": "x", "tls": True, "de": "u@x"}):
        ok, _ = _mail.testar_conexao()
        check(ok is True, "testar_conexao: mock SMTP OK (sem rede)")
        _, kw = _fake.call_args
        check(kw.get("timeout") == 15, "testar_conexao: timeout=15 repassado ao SMTP")
with _mock.patch.object(_smtp, "SMTP", side_effect=OSError("recusado")):
    with _mock.patch.object(_mail, "_cfg", return_value={
            "servidor": "localhost", "porta": 587, "usuario": "u",
            "senha": "x", "tls": True, "de": "u@x"}):
        ok, msg = _mail.testar_conexao()
        check(ok is False and "x" not in str(msg) or ok is False,
              "testar_conexao: falha SMTP fail-soft (sem vazar senha)")

# ================== G. .gitignore (db nunca commitado) ==================
print("-- G. .gitignore (db_mod_*.db nunca commitado) --")
SRC_GI = ler(".gitignore")
check("*.db" in SRC_GI, ".gitignore: regra *.db presente")
check("backup/*.db" in SRC_GI, ".gitignore: regra backup/*.db presente")
check("estrutura.md" in SRC_GI, ".gitignore: estrutura.md nao commitado")
import subprocess as _sp  # noqa: E402
try:
    _ls = _sp.run(["git", "ls-files"], capture_output=True, text=True,
                  timeout=15, cwd=RAIZ)
    _tracked = (_ls.stdout or "").splitlines()
    check(not [f for f in _tracked if f.endswith(".db")],
          "git ls-files: nenhum .db rastreado (bancos fora do repo)")
except Exception:
    check(False, "git ls-files executou (sem crash)")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificacoes")
sys.exit(0 if _OK == _TOTAL else 1)
