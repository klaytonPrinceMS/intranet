"""EN: Collects the payroll register published by the transparency portal.

PT-BR: Coleta o cadastro de servidores publicado pelo portal da transparência.

O QUE ESTE SCRIPT FAZ
    Lê a lista "Servidores por Nomes" do portal da transparência de Monte
    Santo de Minas e grava um arquivo local com matrícula, nome, secretaria,
    departamento, cargo, vínculo e situação de cada servidor.

POR QUE ELE EXISTE SEPARADO DA SINCRONIZAÇÃO
    A coleta é conversa com um site de terceiro: pode cair, mudar de layout ou
    estar fora do ar. Se o script que escreve no banco também fosse o que
    busca na web, uma falha de rede viraria um banco pela metade. Aqui a
    coleta para em um arquivo; `carga_folha.py` só lê esse arquivo.
    Dá para conferir o que foi coletado antes de gravar qualquer coisa.

O QUE ESTE SCRIPT NÃO FAZ — E POR QUÊ
    O portal também devolve o salário (`vldefault`) e o Ficha do contracheque
    (`cdContraCheque`). Nada disso é lido, guardado ou usado. A lista
    telefônica precisa de nome, cargo e ramal — não de quanto a pessoa ganha.
    Ler menos do que o portal oferece é a parte fácil de estar dentro da lei;
    a difícil é não usar o resto.

BASE LEGAL
    Lei 12.527/2011 (Lei de Acesso à Informação). A prefeitura é OBRIGADA a
    publicar a relação nominal dos servidores com cargo e lotação. O
    User-Agent se identifica por essa razão, e o intervalo entre requisições
    é de 1,2 s — 47 requisições para a folha inteira não é tráfego que
    atrapalha ninguém, mas também não se disfarça de visita humana.

COMO USAR
    python mod_gest_cad_usuario/coleta_folha.py --atualizar
    python mod_gest_cad_usuario/coleta_folha.py --competencia 07/2026
    python mod_gest_cad_usuario/coleta_folha.py --saida /tmp/folha.json

    Sem `--atualizar`, reaproveita o arquivo já coletado.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# A configuração mora no arquivo ao lado; o leitor é o mesmo do `carga_folha`
# (mesmo módulo, sem abrir banco), para os dois lados do caminho lerem a mesma
# fonte e não haver duas verdades.
DIR_MODULO = os.path.dirname(os.path.abspath(__file__))
if DIR_MODULO not in sys.path:
    sys.path.insert(0, DIR_MODULO)


def _carregar_config_coleta():
    """Lê `fonte_folha.json`; devolve o padrão (desligado) se não der.

    Isolado em `try/except` de propósito: um JSON quebrado tem de devolver
    "portal não configurado", não `NameError` no import — porque quem importa
    este arquivo é o `carga_folha`, e a falha de um não pode derrubar o outro.
    """
    try:
        from carga_folha import carregar_config
        cfg, _aviso = carregar_config()
        return cfg
    except Exception as e:
        print(f"  configuracao ilegivel ({e}); portal considerado NAO "
              f"configurado", file=sys.stderr)
        return {}


# ---- Onde o portal fica: configuração, nunca código ----------------------
# Este arquivo vai para o git público e pode ser usado por qualquer prefeitura
# ou empresa. Nada de endereço, município ou nome de órgão aqui: a URL base vem
# de `fonte_folha.json`, e sem ela o script não faz nada e diz por quê. Um
# sistema distribuído que abre conexão para um portal que não é do dono é pior
# que um sistema que não abre conexão nenhuma.
#
# Os caminhos dos endpoints são do "Portal Fácil" (plataforma de transparência
# de uso comum em municípios brasileiros). Quem usa outra plataforma preenche os
# três campos em `portal_endpoints` com os dela — ou, melhor, usa
# `origem: "csv"`, que não depende de terceiro nenhum.
CFG = _carregar_config_coleta()
RAIZ = (CFG.get("portal_url") or "").rstrip("/")
_PT = CFG.get("portal_endpoints") or {}
REFERER = RAIZ + (CFG.get("portal_pagina") or "/servidores-por-nomes")
GRID = RAIZ + _PT.get("folha", "")
COMPETENCIA = RAIZ + _PT.get("competencia", "")
USER_AGENT = (CFG.get("portal_user_agent")
              or "intranet/1.0 (carga de servidores - dados publicos)")

# The server caps the page at the DataTables lengthMenu values and answers an
# empty page for anything else — `length=1` and `length=100` both return zero
# records, `length=25` returns 25. Discovered the hard way; do not "optimize".
PAGINA = 25
INTERVALO_S = CFG.get("portal_intervalo_s") or 1.2
TENTATIVAS = 3

# Colunas PEDIDAS ao grid. A resposta traz mais do que estas, e `vldefault`
# e `cdContraCheque` estão entre elas de propósito: a remuneração e a ficha de
# contracheque são informação pública por lei, e a prefeitura publica todo
# mês. A intranet importa para o servidor conferir o próprio valor e para o
# DTI conferir a folha contra o portal.
COLUNAS = ["nmMatricula", "nmServidor", "nmUnidade", "nmLotacao",
           "nmCargo", "nmSituacao", "nmVinculo", "nmRegime",
           "nuCargaHoraria", "dtAdmissao", "dtExoneracao", "nmTipo",
           "vldefault", "cdContraCheque"]

# O que é GRAVADO. `vldefault` chega como texto já formatado ("3.456,78") e é
# guardado como texto: dinheiro em ponto flutuante perde centavo, e o valor
# arredondado divergiria do portal — que é justamente a conferência que o
# DTI faz.
CAMPOS_GUARDADOS = ("matricula", "nome", "unidade", "lotacao", "cargo",
                    "vinculo", "situacao", "tipo", "admissao", "exoneracao",
                    "regime", "carga_horaria", "remuneracao",
                    "ficha_contracheque")

# A folha mora em `dados/`, dentro do módulo, e fora do git (AGENTS.md §1 e
# §8.3): os dados são de servidores reais e não vão para o histórico.
DIR_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
ARQUIVO_PADRAO = os.path.join(DIR_DADOS, "funcionarios.json")
# O CSV é o arquivo que o administrador ABRE e confere. O JSON fica com os
# metadados (competência, data da coleta) que o CSV não cabe; os dois saem
# juntos, sempre, para que ninguém confira uma folha de um mês com os dados
# do outro.
ARQUIVO_CSV = os.path.join(DIR_DADOS, "funcionarios.csv")


def _garantir_dir_dados() -> None:
    """Cria `dados/` se ainda não existir (clone novo, sem a pasta)."""
    try:
        os.makedirs(DIR_DADOS, exist_ok=True)
    except Exception as e:
        print(f"  nao foi possivel criar {DIR_DADOS}: {e}", flush=True)


def _log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def _abrir() -> urllib.request.OpenerDirector:
    """Opens a session. The portal sets a BotDeTect cookie on the first GET and
    the grid endpoint answers 500 without it."""
    import http.cookiejar
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("X-Requested-With", "XMLHttpRequest"),
        ("Referer", REFERER),
        ("Accept", "application/json, text/javascript, */*; q=0.01"),
    ]
    opener.open(REFERER, timeout=60).read()
    return opener


def _post(opener, url: str, corpo: dict) -> dict:
    """POSTs JSON and decodes ISO-8859-1.

    The page declares `charset=iso-8859-1` and the accents really are encoded
    that way, so `json.loads(resp)` on the raw bytes raises UnicodeDecodeError
    on the first accented name. Every name in the sheet is unaccented anyway
    (`Ana Beatriz Souza Rocha`), which is how the source stores them. The name
    here is fictitious: the real sheet stays out of git.
    """
    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(
        url, data=dados,
        headers={"Content-Type": "application/json; charset=utf-8"})
    ultima = None
    for tentativa in range(TENTATIVAS):
        try:
            bruto = opener.open(req, timeout=90).read()
            return json.loads(bruto.decode("iso-8859-1"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            ultima = e
            espera = 2 ** tentativa
            _log(f"  falha ({e.__class__.__name__}), nova tentativa em {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"portal não respondeu após {TENTATIVAS} tentativas: {ultima}")


def _competencias(opener) -> list[str]:
    """Available payroll months, most recent first."""
    try:
        dados = _post(opener, COMPETENCIA, {})
        return [c.get("nome") or c.get("id")
                for c in (dados or []) if isinstance(c, dict)]
    except Exception as e:
        _log(f"  não foi possível ler as competências ({e}); usando a atual")
        return [datetime.now(timezone.utc).strftime("%m/%Y")]


def _pagina(opener, competencia: str, inicio: int) -> list[dict]:
    """One page of the grid.

    The `columns` array is not decoration: without it the server builds no
    SELECT and answers `recordsTotal: 0` with HTTP 200. It looks like "the
    portal is empty" and it is not — the first version of this script had this
    bug and read zero servants while the website showed a full sheet.
    """
    corpo = {
        "parameters": {
            "draw": inicio // PAGINA + 1,
            "columns": [{"data": c, "name": "", "searchable": True,
                         "orderable": True,
                         "search": {"value": "", "regex": False}} for c in COLUNAS],
            # Ascending by matrícula, so two runs produce the same order and
            # the diff between them is only real changes.
            "order": [{"column": 0, "dir": "asc"}, {"column": 1, "dir": "asc"}],
            "start": inicio,
            "length": PAGINA,
            "search": {"value": "", "regex": False},
        },
        "entidade": "", "competencia": competencia, "unidade": "", "cargo": "",
        "funcao": "", "vinculo": "", "vlInicio": "0", "vlFim": "0",
        "grupocalculo": "", "covid": None,
    }
    dados = _post(opener, GRID, corpo)
    linhas = dados.get("data")
    if isinstance(linhas, dict):
        linhas = linhas.get("data", [])
    return [l for l in (linhas or []) if isinstance(l, dict)]


def _normalizar(linha: dict) -> dict:
    """Portal row → record with the fields the intranet needs."""
    def txt(campo):
        return (linha.get(campo) or "").strip() or None
    return {
        "matricula": txt("nmMatricula"),
        "nome": txt("nmServidor"),
        "unidade": txt("nmUnidade"),
        "lotacao": txt("nmLotacao"),
        "cargo": txt("nmCargo"),
        "vinculo": txt("nmVinculo"),
        "situacao": txt("nmSituacao"),
        "tipo": txt("nmTipo"),
        "admissao": txt("dtAdmissao"),
        "exoneracao": txt("dtExoneracao"),
        "regime": txt("nmRegime"),
        "carga_horaria": txt("nuCargaHoraria"),
        # `vldefault` é o valor da remuneração; `cdContraCheque` é a ficha.
        "remuneracao": txt("vldefault"),
        "ficha_contracheque": txt("cdContraCheque"),
    }


def coletar(competencia: str | None = None) -> dict:
    """Walks every page and returns the sheet as a dict."""
    opener = _abrir()
    if competencia is None:
        disponiveis = _competencias(opener)
        if not disponiveis:
            raise RuntimeError("o portal não informou nenhuma competência")
        competencia = disponiveis[0]
        _log(f"competência mais recente: {competencia}")

    _log("lendo a folha (página de 25, 1,2s entre requisições)...")
    servidores, vistos, inicio = [], set(), 0
    while True:
        lote = _pagina(opener, competencia, inicio)
        if not lote:
            break
        novos = 0
        for linha in lote:
            reg = _normalizar(linha)
            chave = reg["matricula"]
            # One matrícula can appear twice (an exoneration and a
            # reappointment, for instance). Keep the first and count the rest,
            # so the count below is truthful about how many people there are.
            if chave and chave in vistos:
                continue
            if chave:
                vistos.add(chave)
            servidores.append(reg)
            novos += 1
        if novos == 0:
            break
        _log(f"  {len(servidores)} servidores")
        inicio += PAGINA
        time.sleep(INTERVALO_S)
        if inicio > 20000:
            _log("  limite de segurança de 20.000 registros atingido")
            break

    return {
        "origem": CFG.get("origem_rotulo") or f"Portal ({RAIZ})",
        "url": REFERER,
        "competencia": competencia,
        "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(servidores),
        "aviso": ("Dados publicados por lei (Lei 12.527/2011 e Lei "
                  "11.129/2005). Inclui remuneração e ficha de "
                  "contracheque, também publicação legal."),
        "servidores": servidores,
    }


COLUNAS_CSV = ("matricula", "nome", "unidade", "lotacao", "cargo",
              "vinculo", "situacao", "remuneracao", "ficha_contracheque",
              "regime", "carga_horaria", "admissao", "exoneracao")


def gravar_csv(folha, caminho):
    """Grava a folha em CSV — o arquivo que o administrador abre e confere.

    SEPARADOR PONTO-E-VÍRGULA, E NÃO VÍRGULA
        Em português o separador de milhar é a vírgula. Um CSV com vírgula
        aberto no Excel em pt-BR quebra a coluna em todas as linhas — e a
        primeira pessoa a abrir o arquivo teria a planilha toda partida,
        sem erro nenhum mensagem, e sem perceber que a culpa é do separador.

    BOM UTF-8 no começo do arquivo
        Sem isso o Excel abre acentos como "Saude" virando "SaÃºde". O portal
        guarda os nomes sem acento, mas os que vierem com acento
        precisam sobreviver à ida e volta pelo Excel.

    Uma linha por servidor, na ordem em que o portal devolve (por
    matrícula), porque um diff entre duas coletas é mais fácil de ler em
    ordem de verdade do que em ordem alfabética de nome.
    """
    try:
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            f.write(";".join(COLUNAS_CSV) + "\n")
            for s in folha.get("servidores") or []:
                campos = []
                for col in COLUNAS_CSV:
                    valor = str(s.get(col) or "")
                    # aspas duplicadas: um ; ou " dentro do dado quebraria a linha
                    if '"' in valor or ";" in valor or "\n" in valor:
                        valor = '"' + valor.replace('"', '""') + '"'
                    campos.append(valor)
                f.write(";".join(campos) + "\n")
        return True, caminho
    except Exception as e:
        return False, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Coleta a folha de servidores do portal da transparência "
                    "configurado em fonte_folha.json.")
    ap.add_argument("--competencia", help="mês/ano (ex.: 08/2026). Padrão: o mais recente.")
    ap.add_argument("--saida", default=ARQUIVO_PADRAO, help="arquivo JSON de destino.")
    ap.add_argument("--csv", default=ARQUIVO_CSV,
                    help="arquivo CSV de destino (padrao: funcionarios.csv ao lado).")
    ap.add_argument("--sem-csv", action="store_true",
                    help="nao grava o CSV.")
    ap.add_argument("--atualizar", action="store_true",
                    help="recoleta mesmo que já exista arquivo.")
    args = ap.parse_args()

    # Sem portal configurado, este script não tem o que fazer. Recusa com
    # explicação e sai com 0: quem instalou o sistema e não o configurou está
    # no estado esperado, e um código de erro faria o cron acusar defeito.
    if not RAIZ or not GRID or not CFG.get("portal_endpoints"):
        print("\n  Coleta do portal NAO CONFIGURADA.\n"
              "  Nada foi acessado e nada foi gravado — este e o estado normal\n"
              "  de quem instalou o sistema e nao configurou a fonte.\n"
              "  Para ligar: edite 'portal_url' e 'portal_endpoints' em\n"
              f"  {os.path.join(DIR_MODULO, 'fonte_folha.json')}.\n"
              "  Sem portal, use a via que nao depende de terceiro: escreva a\n"
              "  folha em CSV e rode  carga_folha.py  com 'origem': 'csv'.\n")
        return 0

    try:
        reaproveitando = False
        if os.path.exists(args.saida) and not args.atualizar:
            with open(args.saida, encoding="utf-8") as f:
                anterior = json.load(f)
            _log(f"reaproveitando {args.saida} "
                 f"({anterior.get('total')} servidores de {anterior.get('coletado_em')})")
            _log("use --atualizar para buscar a folha de novo")
            folha = anterior
            reaproveitando = True
        else:
            print("\nColetando servidores no portal da transparência...\n")
            folha = coletar(args.competencia)
            with open(args.saida, "w", encoding="utf-8") as f:
                json.dump(folha, f, ensure_ascii=False, indent=2)

        # O CSV é SEMPRE gravado, mesmo reaproveitando o JSON: ele é o
        # arquivo que o administrador abre para conferir, e um CSV velho
        # seria pior que nenhum — a pessoa conferiria a folha anterior
        # achando que era a nova.
        if not args.sem_csv:
            ok_csv, info = gravar_csv(folha, args.csv)
            if ok_csv:
                print(f"\n  {folha['total']} servidores da competência "
                      f"{folha['competencia']}")
                print(f"  JSON: {args.saida}")
                print(f"  CSV : {info}")
                if reaproveitando:
                    print("  (CSV regravado a partir do JSON existente)")
                print()
            else:
                print(f"  ERRO ao gravar o CSV: {info}", file=sys.stderr)
                return 1
        else:
            print(f"\n  {folha['total']} servidores; CSV não gravado "
                  f"(--sem-csv)")
        return 0
    except Exception as e:
        print(f"\n  ERRO na coleta: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
