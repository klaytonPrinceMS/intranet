"""Guarda estrutural do isolamento modular (AST, sem importar nada).

Structural guard for module isolation (AST-only, zero imports executed).

Verifica, por análise estática (stdlib `ast` — sem executar código, sem
banco, sem rede):
  A. Nenhum módulo de negócio importa outro (`mod_a -> mod_b`, A,B !=
     `mod_intranet`): cada módulo só acessa o PRÓPRIO banco; comunicação
     entre módulos passa pela API pública do núcleo (`mod_intranet`).
  B. Sem ciclos de import em nível de topo (top-level) entre `mod_*` e
     `main.py`. Imports lazy (dentro de função) que fechem ciclo são
     reportados como AVISO, não falha.
  C. Todo `mod_*` tem `bd_manipulador.py` (nunca `db_manipulador.py`).

Execute: .venv/bin/python assets/test/check_integridade.py
"""
import ast
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_OK = 0
_TOTAL = 0
_FALHAS = []


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        _FALHAS.append(msg)
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


def _modulo_de(path_rel):
    """mod_x do arquivo, 'main' para main.py, None para o resto."""
    partes = path_rel.replace("\\", "/").split("/")
    if partes[0] == "main.py":
        return "main"
    if partes[0].startswith("mod_"):
        return partes[0]
    return None


def _alvo_top(modulo_importado):
    """mod_x / main do dotted name importado (None se stdlib/terceiro)."""
    if not modulo_importado:
        return None
    primeiro = modulo_importado.split(".")[0]
    if primeiro == "main":
        return "main"
    if primeiro.startswith("mod_"):
        return primeiro
    return None


def _imports_de(caminho, pacote):
    """(top_level, lazy): conjuntos de módulos-alvo importados."""
    try:
        with open(caminho, encoding="utf-8") as f:
            arvore = ast.parse(f.read())
    except (SyntaxError, UnicodeDecodeError, OSError):
        return set(), set()
    topo, lazy = set(), set()

    def _visitar(no, dentro_funcao):
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _visitar(filho, True)
            elif isinstance(filho, (ast.Import, ast.ImportFrom)):
                destino = lazy if dentro_funcao else topo
                if isinstance(filho, ast.Import):
                    for a in filho.names:
                        t = _alvo_top(a.name)
                        if t:
                            destino.add(t)
                else:
                    if filho.level and filho.level > 0:
                        base = pacote.split(".")
                        prefixo = ".".join(base[:len(base) - filho.level + 1])
                        mod = (prefixo + "." + (filho.module or "")).strip(".")
                    else:
                        mod = filho.module or ""
                    t = _alvo_top(mod)
                    if t:
                        destino.add(t)
                    else:
                        for a in filho.names:
                            t2 = _alvo_top(a.name)
                            if t2:
                                destino.add(t2)
            else:
                _visitar(filho, dentro_funcao)

    _visitar(arvore, False)
    return topo, lazy


def _arquivos_py():
    alvos = []
    for base in [RAIZ]:
        for raiz, _dirs, arqs in os.walk(base):
            for a in arqs:
                if not a.endswith(".py"):
                    continue
                cheio = os.path.join(raiz, a)
                rel = os.path.relpath(cheio, RAIZ)
                mod = _modulo_de(rel)
                if mod is None:
                    continue
                partes = rel.replace("\\", "/").split("/")[:-1]
                pacote = ".".join(partes) if partes else ""
                alvos.append((mod, rel, cheio, pacote))
    return alvos


print("INICIANDO TESTES — integridade estrutural (isolamento modular)")

arestas_topo = {}   # (origem, destino) -> [arquivos]
arestas_lazy = {}
for mod, rel, cheio, pacote in _arquivos_py():
    topo, lazy = _imports_de(cheio, pacote)
    for d in topo:
        if d != mod:
            arestas_topo.setdefault((mod, d), []).append(rel)
    for d in lazy:
        if d != mod:
            arestas_lazy.setdefault((mod, d), []).append(rel)

# --- A) isolamento: negócio NUNCA importa negócio ---
# Exceção documentada e revisada: cascata LGPD. Quando um usuário é
# excluído/renomeado, `mod_gest_cad_usuario` chama a API PÚBLICA de
# limpeza do próprio banco de cada módulo (remover/renomear/anonimizar).
# Cada módulo toca SÓ o seu banco — nunca há cross-query. Qualquer outro
# par negócio→negócio é violação.
CASCATA_LGPD = {("mod_gest_cad_usuario", "mod_blog"),
                ("mod_gest_cad_usuario", "mod_edit_pdf"),
                ("mod_gest_cad_usuario", "mod_renomear_empenho")}
print("-- A) isolamento entre módulos de negócio --")
violacoes = [((o, d), arqs) for (o, d), arqs in
             list(arestas_topo.items()) + list(arestas_lazy.items())
             if o != "mod_intranet" and d != "mod_intranet"
             and o != "main" and d != "main"
             and o.startswith("mod_") and d.startswith("mod_")
             and (o, d) not in CASCATA_LGPD]
vistos = set()
for (o, d), arqs in sorted(violacoes):
    if (o, d) in vistos:
        continue
    vistos.add((o, d))
    check(False, f"{o} -> {d} ({', '.join(sorted(set(arqs))[:3])})")
if not vistos:
    check(True, "nenhum import entre módulos de negócio (só cascata LGPD)")

# --- B) ciclos em nível de topo ---
print("-- B) ciclos de import (top-level) --")
mods = set([o for o, _d in arestas_topo] + [d for _o, d in arestas_topo])


def _tem_ciclo(grafo):
    BRANCO, CINZA, PRETO = 0, 1, 2
    cor = {m: BRANCO for m in grafo}
    for m in list(grafo):
        for n in grafo.get(m, ()):
            cor.setdefault(n, BRANCO)
    ciclos = []

    def _dfs(no, caminho):
        cor[no] = CINZA
        caminho.append(no)
        for viz in sorted(grafo.get(no, ())):
            if cor.get(viz) == CINZA:
                ciclos.append(caminho[caminho.index(viz):] + [viz])
            elif cor.get(viz) == BRANCO:
                _dfs(viz, caminho)
        caminho.pop()
        cor[no] = PRETO

    for m in sorted(cor):
        if cor[m] == BRANCO:
            _dfs(m, [])
    return ciclos


grafo_topo = {}
for (o, d) in arestas_topo:
    grafo_topo.setdefault(o, set()).add(d)
ciclos = _tem_ciclo(grafo_topo)
for c in ciclos:
    check(False, "ciclo top-level: " + " -> ".join(c))
if not ciclos:
    check(True, "sem ciclos de import em nível de topo")

grafo_lazy = {}
for (o, d), _arqs in list(arestas_topo.items()) + list(arestas_lazy.items()):
    grafo_lazy.setdefault(o, set()).add(d)
for c in _tem_ciclo(grafo_lazy):
    print(f"  AVISO ciclo apenas-lazy (runtime ok): {' -> '.join(c)}")

# --- C) nomenclatura do manipulador ---
print("-- C) bd_manipulador.py em todo mod_* --")
for entrada in sorted(os.listdir(RAIZ)):
    if not entrada.startswith("mod_"):
        continue
    if not os.path.isdir(os.path.join(RAIZ, entrada)):
        continue
    tem_bd = os.path.exists(os.path.join(RAIZ, entrada, "bd_manipulador.py"))
    tem_db = os.path.exists(os.path.join(RAIZ, entrada, "db_manipulador.py"))
    check(tem_bd and not tem_db, f"{entrada}/bd_manipulador.py padronizado")

if _FALHAS:
    print(f"\n{len(_FALHAS)} FALHA(S) de {_TOTAL} verificações")
    sys.exit(1)
print(f"\nTODOS OS TESTES PASSARAM — {_OK} verificações")
