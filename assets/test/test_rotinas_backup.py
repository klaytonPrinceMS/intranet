"""Teste unitário/integração das rotinas de backup (mod_intranet/rotinas.py).

Cobre o delta do commit a1b1650 (checkpoint WAL + OSError->None em
`backup_modulo`, handlers async) e as funções sem cobertura direta:
`intervalo_backup`, `intervalo_monitor_empenho`, `reagendar_backup`,
`reagendar_monitor_empenho`, `backup_bancos`, `backup_modulo`,
`_podar_backups`, `listar_backups` e `limpar_editor_pdf`.

AUTOCONTIDO: redireciona PASTA_BACKUP/PASTA_EDITOR_PDF/BASE_DIR para /tmp
via monkeypatch (não toca em backup/ nem no banco de produção); faz
snapshot/restore das chaves tb_config tocadas.

Execute: .venv/bin/python assets/test/test_rotinas_backup.py
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from mod_intranet.bd_conexao import get_config, set_config, init_db  # noqa: E402
from mod_intranet import rotinas  # noqa: E402

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


print("INICIANDO TESTES — rotinas de backup (mod_intranet/rotinas.py)")
init_db()

CHAVES = ["backup_horas:blog", "empenhos_monitor_intervalo_seg"]
ORIG = {k: get_config(k, None) for k in CHAVES}

TMP = tempfile.mkdtemp(prefix="qa_rotinas_")
PASTA_BKP_ORIG = rotinas.PASTA_BACKUP
BASE_ORIG = rotinas.BASE_DIR
PASTA_PDF_ORIG = rotinas.PASTA_EDITOR_PDF
rotinas.PASTA_BACKUP = os.path.join(TMP, "backup")
os.makedirs(rotinas.PASTA_BACKUP, exist_ok=True)

try:
    # ---------- intervalos ----------
    print("-- intervalos --")
    for k in CHAVES:
        conn = None
        try:
            from mod_intranet.bd_conexao import get_connection
            conn = get_connection()
            conn.execute("DELETE FROM tb_config WHERE chave=?", (k,))
            conn.commit()
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    check(rotinas.intervalo_backup("blog") == 12,
          "intervalo_backup default 12h sem config")
    check(rotinas.intervalo_monitor_empenho() == 60,
          "intervalo_monitor_empenho default 60s sem config")
    set_config("backup_horas:blog", "5")
    check(rotinas.intervalo_backup("blog") == 5,
          "intervalo_backup lê tb_config (5h)")
    set_config("backup_horas:blog", "lixo")
    check(rotinas.intervalo_backup("blog") == 12,
          "intervalo_backup inválido cai no default (fail-soft)")
    set_config("backup_horas:blog", "0")
    check(rotinas.intervalo_backup("blog") == 1,
          "intervalo_backup mínimo é 1h (clamp)")

    # ---------- reagendamento sem agendador ----------
    print("-- reagendamento --")
    rotinas._agendador = None
    check(rotinas.reagendar_backup("blog", 7) is False,
          "reagendar_backup sem agendador devolve False (não quebra)")
    check(rotinas.reagendar_monitor_empenho(30) is False,
          "reagendar_monitor_empenho sem agendador devolve False")

    # ---------- backup_modulo: chaves inválidas ----------
    print("-- backup_modulo (casos de borda) --")
    check(rotinas.backup_modulo("modulo_inexistente") is None,
          "backup_modulo de chave fora do MAPA devolve None")
    rotinas.MAPA_BACKUPS["qa_fantasma"] = ("db_qa_fantasma_que_nao_existe.db",
                                           "Fantasma QA")
    try:
        check(rotinas.backup_modulo("qa_fantasma") is None,
              "backup_modulo sem arquivo de origem devolve None")
    finally:
        del rotinas.MAPA_BACKUPS["qa_fantasma"]

    # ---------- backup_modulo real (checkpoint WAL + cópia) ----------
    print("-- backup_modulo (cópia real com checkpoint) --")
    gerado = rotinas.backup_modulo("intranet")
    check(isinstance(gerado, str) and gerado.endswith("db_mod_intranet.db"),
          f"backup_modulo gera cópia com timestamp ({gerado})")
    if gerado:
        check(os.path.exists(os.path.join(rotinas.PASTA_BACKUP, gerado)),
              "arquivo de backup existe na pasta isolada")
    lista = rotinas.listar_backups("intranet")
    check(any(l[0] == gerado for l in lista),
          "listar_backups filtra pelo banco do módulo")
    check(rotinas.listar_backups("blog") == [],
          "listar_backups vazio para módulo sem cópia")
    check(all(len(l) == 3 and l[1] >= 1 for l in lista),
          "listar_backups devolve (arquivo, tamanho_kb>=1, data_hora)")

    # ---------- OSError nunca derruba o handler (a1b1650) ----------
    print("-- backup_modulo (falha de I/O) --")
    _copy2_orig = shutil.copy2

    def _quebrar(*a, **k):
        raise OSError("disco cheio (simulado)")

    shutil.copy2 = _quebrar
    try:
        check(rotinas.backup_modulo("intranet") is None,
              "OSError no copy2 devolve None (falha nunca derruba handler)")
    finally:
        shutil.copy2 = _copy2_orig

    # ---------- poda retém os N mais recentes ----------
    print("-- poda de backups --")
    base = "20990101_000000_db_mod_blog.db"
    for i in range(12):
        p = os.path.join(rotinas.PASTA_BACKUP, f"2099010{i // 10}_{i:06d}_{base}")
        with open(p, "wb") as fh:
            fh.write(b"x")
    rotinas._podar_backups(manter=10)
    restantes = [f for f in os.listdir(rotinas.PASTA_BACKUP) if f.endswith(base)]
    check(len(restantes) == 10,
          f"_podar_backups retém 10 mais recentes ({len(restantes)})")

    # ---------- backup_bancos em BASE isolada ----------
    print("-- backup_bancos --")
    base_iso = os.path.join(TMP, "base")
    os.makedirs(base_iso, exist_ok=True)
    for nome in ("db_mod_blog.db", "db_mod_x.db", "nao_banco.txt"):
        with open(os.path.join(base_iso, nome), "wb") as fh:
            fh.write(b"dados")
    rotinas.BASE_DIR = base_iso
    try:
        copiados = rotinas.backup_bancos()
    finally:
        rotinas.BASE_DIR = BASE_ORIG
    check("db_mod_blog.db" in copiados and "nao_banco.txt" not in copiados,
          "backup_bancos copia só db_*.db da BASE isolada")

    # ---------- limpar_editor_pdf ----------
    print("-- limpar_editor_pdf --")
    pasta_pdf = os.path.join(TMP, "editorPDF")
    os.makedirs(pasta_pdf, exist_ok=True)
    velho = os.path.join(pasta_pdf, "velho.pdf")
    novo = os.path.join(pasta_pdf, "novo.pdf")
    for p in (velho, novo):
        with open(p, "wb") as fh:
            fh.write(b"pdf")
    antigo = time.time() - 20 * 60
    os.utime(velho, (antigo, antigo))
    rotinas.PASTA_EDITOR_PDF = pasta_pdf
    try:
        removidos = rotinas.limpar_editor_pdf(minutos=10)
    finally:
        rotinas.PASTA_EDITOR_PDF = PASTA_PDF_ORIG
    check(removidos == 1 and not os.path.exists(velho)
          and os.path.exists(novo),
          "limpar_editor_pdf remove só arquivos além do limite")
    rotinas.PASTA_EDITOR_PDF = os.path.join(TMP, "pasta_que_nao_existe")
    try:
        check(rotinas.limpar_editor_pdf() == 0,
              "limpar_editor_pdf sem pasta devolve 0")
    finally:
        rotinas.PASTA_EDITOR_PDF = PASTA_PDF_ORIG
finally:
    rotinas.PASTA_BACKUP = PASTA_BKP_ORIG
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
    shutil.rmtree(TMP, ignore_errors=True)

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
