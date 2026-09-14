"""Levantamento do Renomear Empenhos — leitura anexada à listagem.

EN: Empenhos inventory — recognition reading (numero/parcela/usuario/date)
    attached to browse/queue listings via `anotar_arquivos`.
PT: Ao reconhecer o PDF o monitor extrai empenho/parcela/ficha/ano/tipo +
    usuário (`tb_levantamento`); `anotar_arquivos` anexa esses campos (com
    override de `tb_empenhos` quando processado e fallback ao nome final) e
    `listar_navegacao`/`listar_pendentes` já retornam anotados — a tela exibe
    Arquivo, Empenho, Parcela, Usuário e Data.

Cobre as validações de sessão (backend 14/09/2026):
- coluna `usuario` existe em `tb_levantamento`;
- enriquecimento via levantamento, override via `tb_empenhos`, fallbacks
  `doc_<cont>_<empenho>_<parcela>.pdf` e `EC|EE|EG|AE_<n>.pdf`.

Escreve APENAS linhas próprias (`qa_anotar_*`) em `tb_levantamento` e UMA
em `tb_empenhos` (removidas no `finally`). Sem servidor.

Execute: .venv/bin/python assets/test/test_empenho_anotar.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

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


print("INICIANDO TESTES — levantamento anexado à listagem de empenhos")

from mod_renomear_empenho import bd_manipulador as bd  # noqa: E402

bd.init_db_empenho()
conn = bd._conn()
try:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tb_levantamento)").fetchall()]
    check("usuario" in cols, "tb_levantamento tem coluna usuario")
    check("numero_empenho" in cols and "parcela" in cols,
          "tb_levantamento tem numero_empenho/parcela")
finally:
    conn.close()

CAM1 = "/tmp/qa_anotar_scan_001.pdf"
CAM2 = "/tmp/qa_anotar_doc_final.pdf"
conn = bd._conn()
eid = None
try:
    conn.execute(
        "INSERT INTO tb_levantamento (nome_arquivo, caminho_atual, presente, status,"
        " numero_empenho, parcela, ficha, ano, tipo_especial, usuario)"
        " VALUES (?, ?, 1, 'detectado', ?, ?, ?, ?, ?, ?)",
        ("qa_scan.pdf", CAM1, "0000459", 3, "0000123", "2026", None, "qamaster"))
    conn.execute(
        "INSERT INTO tb_levantamento (nome_arquivo, caminho_atual, presente, status,"
        " numero_empenho, parcela, usuario)"
        " VALUES (?, ?, 1, 'detectado', ?, ?, ?)",
        ("qa_doc.pdf", CAM2, "0000100", 1, "sistema"))
    eid = conn.execute(
        "INSERT INTO tb_empenhos (nome_arquivo_original, nome_arquivo_final,"
        " numero_empenho, parcela, usuario, caminho_arquivo, status)"
        " VALUES (?, ?, ?, ?, ?, ?, 'ativo')",
        ("qa_doc.pdf", "qa_doc.pdf", 100, 1, "qamaster", CAM2)).lastrowid
    conn.commit()

    pdfs = [{"nome": "qa_scan.pdf", "caminho": CAM1, "status": "pendente"},
            {"nome": "qa_doc.pdf", "caminho": CAM2, "status": "processado"},
            {"nome": "doc_0007_0001234_002.pdf", "caminho": "/tmp/qa_anotar_x.pdf",
             "status": "processado"},
            {"nome": "EC_0024.pdf", "caminho": "/tmp/qa_anotar_y.pdf", "status": "processado"}]
    # Evita que o nome do fallback exista de verdade em tb_empenhos (o override
    # por banco venceria o fallback — comportamento correto, mas não é o caso
    # deste check): troca o dígito final até ser único.
    base_nome, _ext = "doc_0007_000123", ".pdf"
    _suf, _cand = 2, None
    while True:
        _cand = f"{base_nome}{_suf}_00{_suf}{_ext}"
        n = conn.execute("SELECT COUNT(*) FROM tb_empenhos WHERE nome_arquivo_final=?",
                         (_cand,)).fetchone()[0]
        if not n:
            break
        _suf += 1
    pdfs[2]["nome"] = _cand
    _esp_num, _esp_parc = f"000123{_suf}", f"00{_suf}"
    bd.anotar_arquivos(pdfs)
    p1, p2, p3, p4 = pdfs
    check(p1.get("numero_empenho") == "0000459" and p1.get("parcela") == 3
          and p1.get("usuario") == "qamaster",
          "levantamento anexa empenho/parcela/usuario")
    check(p2.get("usuario") == "qamaster" and p2.get("numero_empenho") == 100,
          "tb_empenhos (quem processou) sobrescreve o levantamento")
    check(p3.get("numero_empenho") == _esp_num and str(p3.get("parcela")) == _esp_parc,
          "fallback doc_<cont>_<empenho>_<parcela>.pdf (zeros só na exibição)")
    check(p4.get("numero_empenho") == "0024" or p4.get("numero_empenho") == "24",
          "fallback EC|EE|EG|AE_<n>.pdf")
finally:
    try:
        conn.execute("DELETE FROM tb_levantamento WHERE caminho_atual IN (?, ?)", (CAM1, CAM2))
        if eid:
            conn.execute("DELETE FROM tb_empenhos WHERE id=?", (eid,))
        conn.commit()
    except Exception:
        pass
    conn.close()
conn = bd._conn()
try:
    n = conn.execute("SELECT COUNT(*) FROM tb_levantamento WHERE caminho_atual IN (?, ?)",
                     (CAM1, CAM2)).fetchone()[0]
    check(n == 0, "limpeza: nenhuma linha qa_anotar_* restante")
finally:
    conn.close()

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
