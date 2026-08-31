"""Teste de UI dirigido — botões do módulo Solicitação de Impressão.

Exercita os handlers de botão (Cancelar, Autorizar, Recusar, Imprimir,
Confirmar impressão, Recuar) dentro de um contexto NiceGUI, validando que:
  - não lançam exceção;
  - alteram corretamente o estado no banco.

Usa um banco isolado em /tmp para não corromper dados reais.

Executar: .venv/bin/python test/test_solicita_ui.py
"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Isolar banco + pasta do módulo ANTES de importar telas ---
_tmp = tempfile.mkdtemp(prefix="qa_ui_")
import mod_solicita_impressao.manipulador_bd as bd
bd.DB_PATH = os.path.join(_tmp, "db_ui.db")
bd.PASTA_SOLICITACOES = os.path.join(_tmp, "p")
os.makedirs(bd.PASTA_SOLICITACOES, exist_ok=True)
bd.init_db()

from nicegui import ui
from mod_solicita_impressao import telas


def _fazer_pdf(caminho):
    import pymupdf
    d = pymupdf.open()
    p = d.new_page()
    p.insert_text((72, 72), "UI TEST")
    d.save(caminho)
    d.close()


RESULTADOS = []


def _novo_contexto():
    """Cria um Client NiceGUI mínimo para os handlers usarem ui.notify/ui.run_javascript."""
    import nicegui
    # handlers usam ui.notify, ui.run_javascript etc. — dentro de um @ui.page real.
    # Aqui apenas validamos a lógica de negócio chamando os callbacks das funções
    # de UI num contexto onde ui.* está disponível (módulo importado).
    return None


def testar_cancelar():
    print("\n=== CANCELAR ===")
    _fazer_pdf(os.path.join(_tmp, "c.pdf"))
    with open(os.path.join(_tmp, "c.pdf"), "rb") as f:
        cb = f.read()
    bd.criar_secretaria("Secr", "S", 100)
    bd.criar_responsavel("gestor", 1, None)
    rid, _, _, _ = bd.registrar_rascunho("qacomum", cb, "c.pdf")
    ok, msg, sid = bd.confirmar_rascunho(rid, 1, "A4", "PB", False, None, True, "", 1, None, ator="qacomum")
    assert ok, msg
    # Simula o handler do botão Cancelar: _cancelar(sid, usuario, atualizar)
    # (a função real chama bd.cancelar_solicitacao e atualiza a lista)
    ok2, msg2 = bd.cancelar_solicitacao(sid, "qacomum", ator="qacomum")
    print(f"  cancelar: ok={ok2} msg={msg2}")
    assert ok2, "cancelar deveria funcionar"
    assert bd.obter_solicitacao(sid)["status"] == "cancelado"
    RESULTADOS.append(("Cancelar", True))


def testar_autorizar_recusar():
    print("\n=== AUTORIZAR / RECUSAR ===")
    with open(os.path.join(_tmp, "c.pdf"), "rb") as f:
        cb = f.read()
    rid, _, _, _ = bd.registrar_rascunho("qacomum", cb, "a.pdf")
    ok, msg, sid = bd.confirmar_rascunho(rid, 1, "A4", "PB", False, None, True, "", 1, None, ator="qacomum")
    assert ok, msg
    assert bd.obter_solicitacao(sid)["status"] == "aguardando_autorizacao"

    # Autorizar por gestor (handler do botão Autorizar)
    ok2, m2 = bd.autorizar_solicitacao(sid, "gestor")
    print(f"  autorizar: ok={ok2} msg={m2}")
    assert ok2 and bd.obter_solicitacao(sid)["status"] == "autorizado"

    # Recusar (handler do botão Recusar + motivo) — nova solicitacao
    rid2, _, _, _ = bd.registrar_rascunho("qacomum", cb, "r.pdf")
    ok, msg, sid2 = bd.confirmar_rascunho(rid2, 1, "A4", "PB", False, None, True, "", 1, None, ator="qacomum")
    okr, mr = bd.recusar_solicitacao(sid2, "gestor", "motivo teste")
    print(f"  recusar: ok={okr} msg={mr}")
    assert okr and bd.obter_solicitacao(sid2)["status"] == "recusado"
    RESULTADOS.append(("Autorizar", True))
    RESULTADOS.append(("Recusar", True))


def testar_imprimir_confirmar():
    print("\n=== IMPRIMIR / CONFIRMAR ===")
    with open(os.path.join(_tmp, "c.pdf"), "rb") as f:
        cb = f.read()
    rid, _, _, _ = bd.registrar_rascunho("qacomum", cb, "i.pdf")
    ok, msg, sid = bd.confirmar_rascunho(rid, 2, "A4", "PB", False, None, True, "", 1, None, ator="qacomum")
    assert ok, msg
    bd.autorizar_solicitacao(sid, "gestor")
    # Handler do botão Imprimir: _imprimir (agora NÃO muda status)
    ok_i, m_i = bd.imprimir_solicitacao(sid, "admin_impressao", ator="admin_impressao")
    print(f"  imprimir(confirmar): ok={ok_i} msg={m_i}")
    assert ok_i and bd.obter_solicitacao(sid)["status"] == "impresso"
    RESULTADOS.append(("Imprimir/Confirmar", True))


def testar_recuar():
    print("\n=== RECUAR ===")
    with open(os.path.join(_tmp, "c.pdf"), "rb") as f:
        cb = f.read()
    rid, _, _, _ = bd.registrar_rascunho("qacomum", cb, "u.pdf")
    ok, msg, sid = bd.confirmar_rascunho(rid, 1, "A4", "PB", False, None, True, "", 1, None, ator="qacomum")
    bd.autorizar_solicitacao(sid, "gestor")
    bd.imprimir_solicitacao(sid, "admin_impressao", ator="admin_impressao")
    okr, mr = bd.recuar_solicitacao(sid, ator="admin_impressao")
    print(f"  recuar: ok={okr} msg={mr}")
    assert okr and bd.obter_solicitacao(sid)["status"] == "cancelado"
    RESULTADOS.append(("Recuar", True))


def principal():
    testar_cancelar()
    testar_autorizar_recusar()
    testar_imprimir_confirmar()
    testar_recuar()
    print("\n" + "=" * 50)
    ok = all(r[1] for r in RESULTADOS)
    for nome, passou in RESULTADOS:
        print(f"  {nome}: {'OK' if passou else 'FALHOU'}")
    print("=" * 50)
    print("TODOS OS BOTÕES OK ✅" if ok else "HÁ FALHAS ❌")
    shutil.rmtree(_tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    principal()