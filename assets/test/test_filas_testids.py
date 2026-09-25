"""QA do FLUXO FILAS — testids, CSV, rotas e papel do ator (kbp-qa).

Cobre as lacunas que as seções D–D8 de `test_seg_novos_modulos.py` não cobrem:

  A. `data-testid` dos fluxos críticos em `mod_filas/telas.py` (Playwright):
     criar/campos do cadastro, chamar próximo, avançar, próximo da etapa,
     transferir, acesso, mídia+fundo, controle da TV, excluir (uma/todas).
  B. Conversão CSV → tags (`csv_para_tags`) + importação fim a fim.
  C. Rotas em `main.py`: /filas, /tv, /tv/{fila_id}, /tv?grupo=&etapa=,
     /admin/{chave_modulo} com ramo `filas`.
  D. Papel do ator antes da escrita: `_pode_acessar` barra quem não tem
     acesso ao módulo; fonte gateia Excluir/Editar/Acesso e o escopo do
     "excluir todas" (dono vs admin).

Padrão standalone: `check()` + sys.exit (como test_seg_novos_modulos.py).
Execute: .venv/bin/python assets/test/test_filas_testids.py
"""

import os
import re as _re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
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


print("INICIANDO TESTES — QA fluxo filas (testids + CSV + rotas + papel)")

# ========== A. data-testid dos fluxos críticos ==========
print("\n-- A. data-testid em mod_filas/telas.py --")
FONTE_TELAS = ler("mod_filas/telas.py")
IDS_CRITICOS = [
    # cadastro/criação
    "filas-cadastro", "filas-campo-nome", "filas-campo-tv-grupo",
    "filas-campo-ordem-fala", "filas-campo-etapas", "filas-campo-lista",
    "filas-criar", "filas-salvar-edicao", "filas-cancelar-edicao",
    "filas-tv-recem-criada",
    # operação por fila
    "filas-card-abrir-tv", "filas-card-tv-grupo", "filas-chamar-proximo",
    "filas-avancar", "filas-etapa-proximo", "filas-etapa-enviar", "filas-excluir", "filas-editar",
    # lista/nomes + transferência mesma TV
    "filas-importar-texto", "filas-importar-submit", "filas-transferir-todos",
    # acesso liberado
    "filas-acesso-abrir", "filas-acesso-buscar", "filas-acesso-chamar",
    # mídia por fila + fundo + volume + mutar vídeo
    "filas-midia-salvar", "filas-midia-fundo", "filas-midia-som",
    # controle da TV (claim de voz)
    "filas-tv-pausar", "filas-tv-retomar", "filas-tv-retornar",
    "filas-tv-avancar",
    # exclusão em lote
    "filas-excluir-todas", "filas-confirmar-exclusao",
]
for tid in IDS_CRITICOS:
    check(f"data-testid={tid}" in FONTE_TELAS, f"testid {tid} presente")
check("data-testid" in FONTE_TELAS and ".props('data-testid=" in FONTE_TELAS,
      "testids via .props('data-testid=...') (padrão kbp-qa)")
# cada testid aparece exatamente 1x (strict-mode do Playwright não tolera duplicado)
dus = [t for t in IDS_CRITICOS
       if len(_re.findall(rf"data-testid={t}(?![\w-])", FONTE_TELAS)) != 1]
check(not dus, f"testids únicos (sem duplicados): {dus if dus else 'ok'}")

# ========== B. CSV → tags + importação fim a fim ==========
print("\n-- B. csv_para_tags + importar fim a fim --")
from mod_filas import bd_manipulador as filas  # noqa: E402

check(filas.csv_para_tags("Maria\nJoão") is None,
      "texto puro sem delimitador não é CSV (None)")
csv_pv = filas.csv_para_tags("nome;grupo;cor;etapa\nMaria;gestante;vermelho;Recepção")
check(csv_pv == "Maria #gestante #vermelho #Recepção",
      f"CSV com ; e cabeçalho vira tags: {csv_pv!r}")
csv_vg = filas.csv_para_tags("nome,grupo,cor,etapa\nJoão,idoso,azul,Triagem")
check(csv_vg == "João #idoso #azul #Triagem",
      f"CSV com , e cabeçalho vira tags: {csv_vg!r}")
csv_sc = filas.csv_para_tags("Ana,comum,,Recepção")
check(csv_sc == "Ana #comum #Recepção",
      f"CSV sem cabeçalho usa ordem nome,grupo,cor,etapa: {csv_sc!r}")

filas.init_db()
NOME_QA = f"QA-TID-{os.getpid()}"
ok_inv, msg_inv = filas.criar_fila(NOME_QA + "-inv", ator="qa_tid", tv_grupo="!!!")
check(not ok_inv, f"criar_fila rejeita tv_grupo inválido: {msg_inv}")
check(filas.obter_fila_por_nome(NOME_QA + "-inv") is None,
      "grupo inválido não escreve nada no banco")
ok_c, fid_c = filas.criar_fila(NOME_QA, ator="qa_tid", tv_grupo="qa-tid-grupo",
                               etapas=[("Recepção", "01"), ("Triagem", "02")])
check(ok_c, f"criar fila com slug + etapas: {fid_c}")
if ok_c:
    fila = filas.obter_fila(fid_c)
    check(fila[12] == "qa-tid-grupo", "tv_grupo salvo como slug")
    check([e[3] for e in filas.listar_etapas(fid_c)] == ["Recepção", "Triagem"],
          "etapas na sequência informada")
    ok_i, msg_i = filas.importar_nomes(fid_c, csv_pv, ator="qa_tid")
    check(ok_i, f"importar texto convertido do CSV: {msg_i}")
    nomes = {r[1]: (r[4], r[5], r[6]) for r in filas.listar_nomes(fid_c)}
    check(nomes.get("Maria") == ("gestante", "vermelho", "Recepção"),
          f"Maria com grupo+cor+etapa: {nomes.get('Maria')}")
    ok_s, nova = filas.gerar_senha(fid_c, ator="qa_tid")
    check(ok_s, f"gerar senha consome a lista: {nova}")
    ult = filas.ultima_chamada(fid_c)
    check(ult is not None and ult[4] == "Maria" and ult[5] == "Recepção",
          "chamada vinculada a Maria na Recepção")
    ok_px, _ = filas.proximo_da_etapa(fid_c, "Triagem", ator="qa_tid")
    check(not ok_px, "Triagem sem ninguém atribuído recusa (não puxa de outra etapa)")
    filas.excluir_fila(fid_c, ator="qa_tid")
    check(filas.obter_fila_por_nome(NOME_QA) is None, "fila QA excluída (limpeza)")
else:
    check(False, "fila QA não criada — demais passos pulados")

# ========== C. Rotas ==========
print("\n-- C. rotas /filas /tv /admin/filas em main.py --")
FONTE_MAIN = ler("main.py")
check('@ui.page("/filas")' in FONTE_MAIN, "rota /filas registrada")
check('@ui.page("/tv")' in FONTE_MAIN, "rota /tv registrada")
check('@ui.page("/tv/{fila_id}")' in FONTE_MAIN, "rota /tv/{fila_id} registrada")
check('query_params.get("grupo")' in FONTE_MAIN, "/tv lê ?grupo= (TV compartilhada)")
check('query_params.get("etapa")' in FONTE_MAIN, "/tv e /tv/{id} leem ?etapa= (TV por sala)")
check('@ui.page("/admin/{chave_modulo}")' in FONTE_MAIN, "rota /admin/{chave} registrada")
check('elif chave_modulo == "filas":' in FONTE_MAIN, "ramo filas → /admin/filas")
check("from mod_filas.telas_administracao import mostrar_administracao" in FONTE_MAIN,
      "/admin/filas usa telas_administracao do módulo")

# ========== D. Papel do ator antes da escrita ==========
print("\n-- D. papel do ator (_pode_acessar + gates na fonte) --")
from mod_filas import telas as telas_filas  # noqa: E402
from mod_intranet import autenticacao  # noqa: E402

_orig = autenticacao.validar_acesso_modulo
try:
    autenticacao.validar_acesso_modulo = lambda u, m: False
    check(telas_filas._pode_acessar("ze", "administrador_geral") is True,
          "administrador_geral passa mesmo sem acesso explícito")
    check(telas_filas._pode_acessar("ze", "comum") is False,
          "comum sem acesso ao módulo é barrado antes de qualquer escrita")
    autenticacao.validar_acesso_modulo = lambda u, m: (u, m) == ("lia", "filas")
    check(telas_filas._pode_acessar("lia", "comum") is True,
          "comum com acesso liberado entra")
    check(telas_filas._pode_acessar("ze", "comum") is False,
          "comum de outro módulo continua barrado")
finally:
    autenticacao.validar_acesso_modulo = _orig
check("if not _pode_acessar(user_nome, perfil_global):" in FONTE_TELAS,
      "mostrar_tela retorna cedo sem acesso (nada renderiza, nada escreve)")
check("if eh_admin or criado_por == user_nome:" in FONTE_TELAS,
      "Excluir só dono/admin (papel antes da escrita)")
check("somente_do_criador" in FONTE_TELAS and "eh_admin=eh_admin" in FONTE_TELAS,
      "excluir-todas respeita escopo (minhas vs todas)")

print(f"\nRESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
