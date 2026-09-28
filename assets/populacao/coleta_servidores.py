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
    coleta para em um arquivo; `sincroniza_servidores.py` só lê esse arquivo.
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
    python assets/populacao/coleta_servidores.py --atualizar
    python assets/populacao/coleta_servidores.py --competencia 07/2026
    python assets/populacao/coleta_servidores.py --saida /tmp/folha.json

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

# -----------------------------------------------------------------identified
RAIZ = "https://transparencia.montesantodeminas.mg.gov.br"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) intranet-montesanto/1.0 "
              "(dados publicos - Lei 12.527/2011)")
REFERER = RAIZ + "/servidores-por-nomes"
GRID = RAIZ + "/transparencia/servidor/tpc_servidor_data.ashx?metodo=ServidorGetNomeGrid"
COMPETENCIA = RAIZ + "/transparencia/servidor/tpc_servidor_data.ashx?metodo=ServidorGetCompetencia&entidade="

# The server caps the page at the DataTables lengthMenu values and answers an
# empty page for anything else — `length=1` and `length=100` both return zero
# records, `length=25` returns 25. Discovered the hard way; do not "optimize".
PAGINA = 25
INTERVALO_S = 1.2
TENTATIVAS = 3

# Only these are read. The response also carries `vldefault` (remuneration),
# `cdContraCheque` (internal payroll id) and `dtExoneracao` — deliberately
# absent from this list, so the collector cannot read them by accident.
COLUNAS = ["nmMatricula", "nmServidor", "nmUnidade", "nmLotacao",
           "nmCargo", "nmVinculo", "vldefault"]
CAMPOS_GUARDADOS = ("matricula", "nome", "unidade", "lotacao", "cargo",
                    "vinculo", "situacao", "tipo", "admissao")

ARQUIVO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "servidores_coletados.json")


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
    """Portal row → record with only the fields the intranet needs."""
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
        "origem": "Portal da Transparência de Monte Santo de Minas",
        "url": REFERER,
        "competencia": competencia,
        "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(servidores),
        "aviso": ("Dados publicados por lei (Lei 12.527/2011). O portal também "
                  "publica remuneração e ficha de contracheque; esses campos "
                  "foram deliberadamente ignorados."),
        "servidores": servidores,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Coleta a folha de servidores do portal da transparência.")
    ap.add_argument("--competencia", help="mês/ano (ex.: 08/2026). Padrão: o mais recente.")
    ap.add_argument("--saida", default=ARQUIVO_PADRAO, help="arquivo JSON de destino.")
    ap.add_argument("--atualizar", action="store_true",
                    help="recoleta mesmo que já exista arquivo.")
    args = ap.parse_args()

    try:
        if os.path.exists(args.saida) and not args.atualizar:
            with open(args.saida, encoding="utf-8") as f:
                anterior = json.load(f)
            _log(f"reaproveitando {args.saida} "
                 f"({anterior.get('total')} servidores de {anterior.get('coletado_em')})")
            _log("use --atualizar para buscar a folha de novo")
            return 0

        print("\nColetando servidores no portal da transparência...\n")
        folha = coletar(args.competencia)
        with open(args.saida, "w", encoding="utf-8") as f:
            json.dump(folha, f, ensure_ascii=False, indent=2)
        print(f"\n  {folha['total']} servidores da competência "
              f"{folha['competencia']}")
        print(f"  gravado em {args.saida}\n")
        return 0
    except Exception as e:
        print(f"\n  ERRO na coleta: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
