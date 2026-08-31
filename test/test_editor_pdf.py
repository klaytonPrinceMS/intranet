"""Teste do módulo Editor de PDF (Fase 5.6) — rodar manualmente:
    python test/test_editor_pdf.py
Gera PDFs sintéticos, exercita o motor completo e valida hashes na auditoria.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mod_edit_pdf import manipulador_bd as m
from mod_intranet.conexao_bd import get_connection

PASS = []
FAIL = []


def check(nome, condicao):
    (PASS if condicao else FAIL).append(nome)
    print(f"  [{'OK' if condicao else 'FALHOU'}] {nome}")


def pdf_sintetico(caminho, paginas=6, pesado=False):
    import pymupdf
    doc = pymupdf.open()
    for i in range(paginas):
        pg = doc.new_page()
        if pesado:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 800))
            pix.set_rect(pix.irect, (120 + i, 60, 200))
            pg.insert_image(pg.rect, pixmap=pix)
        else:
            pg.insert_text((72, 72), f"Pagina {i + 1}")
    doc.save(caminho)
    doc.close()


def n_paginas(caminho):
    import pymupdf
    d = pymupdf.open(caminho)
    n = len(d)
    d.close()
    return n


def main():
    base = m.pasta_usuario("zzz_teste_56")
    src = os.path.join(base, "origem.pdf")
    pdf_sintetico(src, paginas=6, pesado=True)

    print("\n== hash ==")
    h1 = m.hash_sha256(src)
    h2 = m.hash_sha256(src)
    check("sha256 deterministico", len(h1) == 64 and h1 == h2)

    print("\n== reduzir LEVE ==")
    for bib in ("auto", "pymupdf", "pikepdf", "pypdf"):
        out = os.path.join(base, f"leve_{bib}.pdf")
        ok, msg = m.op_reduzir(src, out, qualidade=50, modo="leve", biblioteca=bib)
        check(f"leve/{bib} -> {msg[:40]}", ok and os.path.exists(out) and n_paginas(out) == 6)

    print("\n== reduzir AGRESSIVO ==")
    out_a = os.path.join(base, "agressivo.pdf")
    ok, msg = m.op_reduzir(src, out_a, qualidade=30, dpi=72, modo="agressivo")
    tam_orig = os.path.getsize(src)
    tam_agr = os.path.getsize(out_a) if os.path.exists(out_a) else -1
    check(f"agressivo 72dpi q30 ({tam_orig}B -> {tam_agr}B)",
          ok and os.path.exists(out_a) and n_paginas(out_a) == 6 and tam_agr < tam_orig)

    print("\n== juntar ==")
    outs3 = [os.path.join(base, f"parte{i}.pdf") for i in range(3)]
    for p in outs3:
        pdf_sintetico(p, paginas=2)
    out_j = os.path.join(base, "junto.pdf")
    ok, msg = m.op_juntar(outs3, out_j)
    check("juntar 3x2pag = 6pag", ok and n_paginas(out_j) == 6)

    # juntar ignorando lixo na seleção (ZIP + corrompido)
    lixo_zip = os.path.join(base, "selecao.zip")
    with open(lixo_zip, "wb") as f:
        f.write(b"PK\x03\x04 nao e um pdf")
    ruim2 = os.path.join(base, "ruim2.pdf")
    with open(ruim2, "wb") as f:
        f.write(b"%PDF-1.7 quebrado")
    out_j2 = os.path.join(base, "junto2.pdf")
    ok, msg = m.op_juntar(outs3 + [lixo_zip, ruim2], out_j2)
    check("juntar ignora zip/corrompido e une os validos",
          ok and n_paginas(out_j2) == 6 and "IGNORADOS" in msg)
    ok, msg = m.op_juntar([lixo_zip], out_j2)
    check("juntar sem nenhum PDF valido falha explicando", not ok and "não é PDF" in msg)

    print("\n== cortar ==")
    for filtro, esperado in (("pares", 3), ("impares", 3), ("2-4", 3), ("99", None)):
        out_c = os.path.join(base, f"corte_{filtro.replace('-', '_')}.pdf")
        ok, res = m.op_cortar(src, filtro, base, f"corte_{filtro}")
        if esperado is None:
            check(f"cortar '{filtro}' recusado", not ok)
        else:
            check(f"cortar '{filtro}' = {esperado} pag",
                  ok and os.path.exists(res) and n_paginas(res) == esperado)

    print("\n== dividir ==")
    ok, res = m.op_dividir(src, "1-3", base, "div_teste")
    check("dividir 1-3 = 3 arquivos", ok and len(res) == 3)
    ok, res = m.op_dividir(src, "99", base, "div_vazio")
    check("dividir '99' vazio avisado", ok and len(res) == 0)

    print("\n== dividir_partes (novos modos) ==")
    # pares × ímpares: duas partes complementares
    ok, dados, aviso = m.op_dividir_partes(src, "parimpar", "", base,
                                           "dv_pi")
    p_pares = os.path.join(base, "dv_pi_pares.pdf") if ok else ""
    p_impar = os.path.join(base, "dv_pi_impares.pdf") if ok else ""
    check("parimpar gera 2 partes",
          ok and len(dados) == 2 and n_paginas(p_pares) == 3
          and n_paginas(p_impar) == 3 and not aviso)

    # cortes múltiplos: '5' → parte1=1..5, parte2=6..fim ; '2,4' → 2/2/2
    ok, dados, aviso = m.op_dividir_partes(src, "cortes", "5", base, "dv_c5")
    tams = [n_paginas(c) for c, _s in dados] if ok else []
    check("cortes '5' = [5,1]", ok and tams == [5, 1])
    ok, dados, aviso = m.op_dividir_partes(src, "cortes", "2,4", base, "dv_c24")
    tams = [n_paginas(c) for c, _s in dados] if ok else []
    check("cortes '2,4' = [2,2,2]", ok and tams == [2, 2, 2])
    ok, dados, aviso = m.op_dividir_partes(src, "cortes", "9", base, "dv_c9")
    check("corte fora do range recusado", not ok)

    # intervalos: '1-2,5-6' → grupo1=2pag, grupo2=2pag (pulo preservado)
    ok, dados, aviso = m.op_dividir_partes(src, "intervalos", "1-2,5-6",
                                           base, "dv_iv")
    tams = [n_paginas(c) for c, _s in dados] if ok else []
    check("intervalos '1-2,5-6' = [2,2]", ok and tams == [2, 2])

    # página a página via novo motor + biblioteca alternativas no corte
    ok, dados, aviso = m.op_dividir_partes(src, "pagina", "1,3", base,
                                           "dv_pg")
    check("pagina '1,3' = 2 arquivos via op_dividir_partes",
          ok and len(dados) == 2)
    for bib in ("pikepdf", "pypdf"):
        out_cb = os.path.join(base, f"corte_bib_{bib}.pdf")
        okb, resb = m.op_cortar(src, "1-2", base, f"corte_bib_{bib}",
                                biblioteca=bib)
        check(f"cortar via {bib} = 2 pag",
              okb and os.path.exists(resb) and n_paginas(resb) == 2)
    okb, resb = m.op_cortar(src, "1-2", base, "corte_bib_auto",
                            biblioteca="auto")
    check("cortar via auto = 2 pag", okb and n_paginas(resb) == 2)
    okb, dados_b, _av = m.op_dividir_partes(src, "parimpar", "", base,
                                            "dv_pi_py", biblioteca="pypdf")
    check("parimpar via pypdf = 2 partes", okb and len(dados_b) == 2)

    print("\n== verificar ==")
    ok, msg = m.op_verificar(src)
    check("verificar integro", ok and ("ntegro" in msg))
    ruim = os.path.join(base, "ruim.pdf")
    with open(ruim, "wb") as f:
        f.write(b"%PDF-1.7 quebrado nao e pdf de verdade")
    ok, msg = m.op_verificar(ruim)
    check("verificar corrompido detectado", not ok)

    print("\n== cota / uso global ==")
    uso = m.uso_global_bytes()
    check("uso_global_bytes > 0", uso > 0)
    okq, _msgq = m.verificar_quota("zzz_ninguem", 1024)
    check("quota disponivel p/ usuario novo", okq)

    print("\n== auditoria com hash (tb_auditoria central) ==")
    from mod_intranet.manipulador_bd import audit_log
    audit_log("zzz_teste_56", "edit-pdf", "teste_hash",
              f"sha256 origem=[{h1}]", hash_arquivo=h1)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT descricao, hash_arquivo FROM tb_auditoria
                   WHERE usuario='zzz_teste_56' AND acao='teste_hash'
                   ORDER BY id DESC LIMIT 1""")
    linha = cur.fetchone()
    conn.close()
    check("hash completo persistido na tb_auditoria",
          h1 in linha[0] and linha[1] == h1)

    print("\n== expirar_antigos ==")
    velho = os.path.join(base, "velho.pdf")
    pdf_sintetico(velho, paginas=1)
    novo = os.path.join(base, "novo.pdf")
    pdf_sintetico(novo, paginas=1)
    t = time.time()
    os.utime(velho, (t - 700, t - 700))
    conn = m._conn()
    conn.execute("INSERT INTO tb_arquivos (nome_arquivo, usuario, tamanho_bytes, operacao) "
                 "VALUES ('velho.pdf','zzz_teste_56',100,'upload')")
    conn.execute("INSERT INTO tb_arquivos (nome_arquivo, usuario, tamanho_bytes, operacao) "
                 "VALUES ('novo.pdf','zzz_teste_56',100,'upload')")
    conn.commit()
    conn.close()
    removidos = m.expirar_antigos(minutos=10)
    conn = m._conn()
    ativo_velho = conn.execute(
        "SELECT ativo FROM tb_arquivos WHERE nome_arquivo='velho.pdf' AND usuario='zzz_teste_56'"
    ).fetchone()[0]
    ativo_novo = conn.execute(
        "SELECT ativo FROM tb_arquivos WHERE nome_arquivo='novo.pdf' AND usuario='zzz_teste_56'"
    ).fetchone()[0]
    conn.close()
    check("arquivo antigo removido do disco", not os.path.exists(velho))
    check("registro antigo inativado no banco",
          removidos >= 1 and ativo_velho == 0 and ativo_novo == 1)

    # ---- limpeza ----
    conn = m._conn()
    conn.execute("DELETE FROM tb_arquivos WHERE usuario='zzz_teste_56'")
    conn.execute("DELETE FROM tb_cota_disco WHERE usuario='zzz_teste_56'")
    conn.commit()
    conn.close()
    for f in os.listdir(base):
        try:
            os.remove(os.path.join(base, f))
        except OSError:
            pass
    os.rmdir(base)

    print(f"\n==== RESULTADO: {len(PASS)} OK, {len(FAIL)} falha(s) ====")
    if FAIL:
        print("Falhas:", *FAIL, sep="\n  - ")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
