"""EN: Checks the first-load-of-the-staff-sheet standard (30/09/2026).

Covers the four things that decide whether a fresh install comes up with the
staff register already populated: the `dados/` directory bug, the
"is this the first load?" trigger, the boot step in the initializer, and the
config that turns the source on. Every check is offline — no portal call —
because a test that needs the internet is a test that fails for the wrong
reason.

PT-BR: Confere o padrão da primeira carga da folha de servidores (30/09/2026).

Cobre as quatro coisas que decidem se uma instalação nova sobe com o cadastro
de servidores já populado: o bug da pasta `dados/`, o gatilho de "é a
primeira carga?", o passo de boot no inicializador, e a configuração que liga
a fonte. Todo o teste é offline — nenhuma chamada ao portal — porque teste
que depende de internet é teste que falha pelo motivo errado.

Execute:
    .venv/bin/python assets/test/test_carga_folha_primeira.py
"""
import ast
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

MOD_CFG = os.path.join(RAIZ, "mod_gest_cad_usuario", "fonte_folha.json")
MOD_CARGA = os.path.join(RAIZ, "mod_gest_cad_usuario", "carga_folha.py")
MOD_COLETA = os.path.join(RAIZ, "mod_gest_cad_usuario", "coleta_folha.py")
MOD_INIT = os.path.join(RAIZ, "mod_intranet", "bd_criador.py")
MOD_CONEXAO = os.path.join(RAIZ, "mod_intranet", "bd_conexao.py")

_ok = 0
_falhas = []


def check(cond, msg):
    """Conta um OK ou uma falha e imprime o veredito."""
    global _ok
    if cond:
        _ok += 1
        print(f"  OK    {msg}")
    else:
        _falhas.append(msg)
        print(f"  FALHA {msg}")


def _fonte(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    print("\n== 1. A pasta dados/ e criada antes de gravar ==")

    # O bug: `dados/` e gitignored, entao NUNCA existe num clone novo, e a
    # coleta abria `args.saida` para escrita direto. Resultado: `[Errno 2]`
    # depois de ~100 s de coleta, e a folha sumia.
    arvore = ast.parse(_fonte(MOD_COLETA))
    main_fn = next((n for n in arvore.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    check(main_fn is not None, "coleta_folha.main() existe")

    if main_fn is not None:
        # `n.func` e `ast.Name` numa chamada simples de funcao e `ast.Attribute`
        # numa de metodo. Filtrar so por `attr` perderia a chamada justamente
        # que este teste existe para achar.
        chamadas = []
        for n in ast.walk(main_fn):
            if not isinstance(n, ast.Call):
                continue
            if isinstance(n.func, ast.Attribute):
                chamadas.append(n.func.attr)
            elif isinstance(n.func, ast.Name):
                chamadas.append(n.func.id)
        check("_garantir_dir_dados" in chamadas,
              "main() chama _garantir_dir_dados() antes de gravar")
        # `_garantir_dir_dados` precisa vir ANTES do primeiro `open` de escrita.
        if "_garantir_dir_dados" in chamadas:
            fonte_coleta = _fonte(MOD_COLETA)
            i_garantir = fonte_coleta.find("_garantir_dir_dados()",
                                          fonte_coleta.find("def main("))
            i_abre = fonte_coleta.find('open(args.saida, "w"',
                                       fonte_coleta.find("def main("))
            check(0 < i_garantir < i_abre,
                  "_garantir_dir_dados() vem antes do open de escrita")

    # A funcao existe e cria o diretorio de verdade.
    try:
        sys.path.insert(0, os.path.dirname(MOD_COLETA))
        from carga_folha import DIR_DADOS  # noqa: F401
        import coleta_folha as cf
        check(callable(getattr(cf, "_garantir_dir_dados", None)),
              "_garantir_dir_dados() e chamavel")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            alvo = os.path.join(tmp, "sub", "dados")
            original = cf.DIR_DADOS
            try:
                cf.DIR_DADOS = alvo
                cf._garantir_dir_dados()
                check(os.path.isdir(alvo), "_garantir_dir_dados() cria o diretorio")
            finally:
                cf.DIR_DADOS = original
    except Exception as exc:
        check(False, f"import de coleta_folha/carga_folha: {exc}")

    print("\n== 2. O gatilho de primeira carga ==")

    try:
        from mod_gest_cad_usuario.carga_folha import (
            carga_automatica, primeira_carga_pendente, servidores_no_cadastro,
        )
        check(callable(carga_automatica), "carga_automatica e importavel")
        check(callable(primeira_carga_pendente),
              "primeira_carga_pendente() e importavel")
        check(callable(servidores_no_cadastro),
              "servidores_no_cadastro() e importavel")

        total = servidores_no_cadastro()
        check(isinstance(total, int) and total >= 0,
              f"servidores_no_cadastro() devolve inteiro ({total})")

        # Coerencia: "primeira carga pendente" e "zero servidores" sao a
        # mesma pergunta. Divergir entre as duas e o defeito.
        check(primeira_carga_pendente() == (total == 0),
              "primeira_carga_pendente() concorda com a contagem")

        # A contagem nao pode depender de lista de contas de fabrica: essa
        # lista mudaria a cada renomeacao. O criterio tem que ser a coluna que
        # a folha preenche (`vinculo`) e que o seed NAO preenche.
        fonte_carga = _fonte(MOD_CARGA)
        trecho = fonte_carga[fonte_carga.find("def servidores_no_cadastro"):
                             fonte_carga.find("def primeira_carga_pendente")]
        check("vinculo" in trecho,
              "a contagem usa a coluna vinculo (preenchida pela folha)")
        for nome in ("master", "qacomum", "qamaster", "klayton"):
            check(f'"{nome}"' not in trecho,
                  f"a contagem nao depende da conta de fabrica {nome}")
    except Exception as exc:
        check(False, f"gatilho de primeira carga: {exc}")

    print("\n== 3. A carga esta no inicializador de bancos ==")

    fonte_init = _fonte(MOD_INIT)
    check("carga_automatica" in fonte_init,
          "bd_criador chama carga_automatica")
    check("primeira_carga_pendente" in fonte_init,
          "bd_criador consulta primeira_carga_pendente antes")
    # Ordem: a folha escreve em tb_usuarios, que so existe depois do
    # init_users(). A carga antes dele seria um cadastro vazio sem erro visivel.
    i_users = fonte_init.find("init_users()")
    i_folha = fonte_init.find("primeira_carga_pendente()")
    check(0 < i_users < i_folha,
          "a carga vem DEPOIS do init_users() (a tabela precisa existir)")
    # Fail-soft: o boot nao pode cair por causa da folha.
    i_try = fonte_init.find("try:", max(0, i_folha - 400))
    check(i_try >= 0, "a carga do boot esta dentro de try/except (fail-soft)")

    print("\n== 4. A configuracao liga a fonte ==")

    try:
        with open(MOD_CFG, encoding="utf-8") as fh:
            cfg = json.load(fh)
        check(cfg.get("ativo") is True,
              "fonte_folha.json tem ativo=true (esta instalacao popula a folha)")
        check(cfg.get("origem") == "portal",
              "fonte_folha.json usa origem=portal")
        check(bool(cfg.get("portal_url")),
              "fonte_folha.json tem portal_url preenchido")
        endpoints = cfg.get("portal_endpoints") or {}
        check(bool(endpoints.get("folha")),
              "portal_endpoints.folha preenchido")
        check(bool(endpoints.get("competencia")),
              "portal_endpoints.competencia preenchido")
        # O arquivo e documentado dentro de si: quem abre no editor entende.
        leia_me = " ".join(cfg.get("_leia_me") or [])
        check("ATIVACAO" in leia_me.upper() or "ATENCAO" in leia_me.upper(),
              "o _leia_me avisa que isto e fase de desenvolvimento")
        check("removido" in leia_me.lower() or "remov" in leia_me.lower(),
              "o _leia_me diz que a mudanca sera removida depois")
    except Exception as exc:
        check(False, f"leitura da configuracao: {exc}")

    print("\n== 5. O padrao de versionamento do modulo (AGENTS.md 4.2) ==")

    fonte_conexao = _fonte(MOD_CONEXAO)
    marcador = "migracao_versao_usuarios_260930_carga_folha"
    # Escrito literal, e nao em f-string: e o que o teste de versionamento
    # procura por leitura estatica.
    check(marcador in fonte_conexao,
          f"marcador {marcador} escrito literal em bd_conexao.py")
    check("versao_modulo:usuarios" in fonte_conexao,
          "o bump escreve versao_modulo:usuarios")

    print("\n== 6. Sintaxe e JSON ==")

    for caminho, nome in ((MOD_CARGA, "carga_folha.py"),
                          (MOD_COLETA, "coleta_folha.py"),
                          (MOD_INIT, "bd_criador.py"),
                          (MOD_CONEXAO, "bd_conexao.py")):
        try:
            ast.parse(_fonte(caminho), filename=nome)
            check(True, f"{nome} compila")
        except SyntaxError as exc:
            check(False, f"{nome} tem erro de sintaxe: {exc}")

    print("\n" + "=" * 66)
    if _falhas:
        print(f"FALHOU: {len(_falhas)} de {_ok + len(_falhas)} verificacoes")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"OK: {_ok} verificacoes, todas passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())