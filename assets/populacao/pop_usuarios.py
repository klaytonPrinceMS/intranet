"""POPULA OS SERVIDORES DA PREFEITURA NOS BANCOS DO SISTEMA.

*** ESTE ARQUIVO NÃO DEVE SER DOCUMENTADO. ***

Ele é uma ferramenta, não parte do produto: fica em `assets/populacao/` e não
entra no MkDocs, no `nav` nem em manual nenhum. Quem instala a intranet não
quer 60 servidores na lista telefônica — quem quiser, roda o script. Os
**dados** que ele grava moram nos bancos, que já são ignorados pelo Git, e é
isso que evita vazar informação: nada de dado de servidor versionado, só o
código que popula.

O que ele faz
-------------
1. Lê a árvore de unidades da Lista Telefônica (secretaria/setor/subsetor).
2. Distribui os telefones da faixa **35 3591-5101 a 35 3591-5199** (99 números):
   um por secretaria, um por setor, e o que sobrar nos subsetores.
3. Cria um servidor por número, com:
   - nome de usuário = **matrícula**
   - nome completo (o cadastro guarda o nome inteiro)
   - senha provisória **123456**, com **troca obrigatória no 1º acesso**
     (isso é o `criar_usuario`, que já marca `forcar_troca`; o servidor troca a
     senha antes de usar qualquer coisa)
   - cargo/unidade/lotação
4. Grava o telefone como **da empresa** e cria o contato na lista telefônica.

Nome na lista x nome no cadastro
--------------------------------
Na **lista telefônica** o contato aparece como *primeiro + último nome*
("Ana Souza"), que é o padrão de diretório. No **cadastro de usuário** fica o
nome completo, como manda a identificação funcional.

Sobre os nomes: o padrão é gente **fictícia**, gerada aqui. Para usar os nomes
reais do portal da transparência, exporte o CSV no formato indicado por
`--csv` e passe `--csv ARQUIVO.csv`. A escolha é conscious de propósito: um
script que arrasta nome de pessoa real de site de terceiro e já cria login
para ela é decisão do responsável, com a LGPD e o portal sob sua
responsabilidade — não algo que um script de populate faça sozinho e em
silêncio.

Uso
---
    python assets/populacao/pop_usuarios.py                 # ensaio (nada grava)
    python assets/populacao/pop_usuarios.py --aplicar        # grava de verdade
    python assets/populacao/pop_usuarios.py --csv x.csv --aplicar

    # o que ele faria, sem gravar:
    python assets/populacao/pop_usuarios.py --aplicar --somente secretaria

EN: OPT-IN script that seeds the city hall staff into the phone list and the
user database. NOT part of the product and NOT documented on purpose.
Username is the functional registration (matricula); the initial password is
123456 with a forced change on first login. The directory shows the first +
last name only. Fictitious people by default; pass --csv to supply real data.
"""

import argparse
import csv
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# A faixa de telefones pedida. 5101..5199 = 99 números.
FAIXA_INICIO = 5101
FAIXA_FIM = 5199
DDD = "35"
SENHA_PROVISORIA = "123456"
MATRICULA_INICIO = 1001

# Nomes fictícios. Sobrenhos e prenomes comuns, para a lista ficar com cara de
# diretório de prefeitura sem ser cópia de ninguém.
PRENOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elaine", "Fábio", "Gabriela", "Heitor",
    "Isabela", "João", "Karina", "Lucas", "Mariana", "Nelson", "Olívia",
    "Paulo", "Queila", "Rafael", "Sabrina", "Thiago", "Ursula", "Vinícius",
    "Wanda", "Yara", "Zilda", "André", "Bianca", "Cláudio", "Denise",
    "Eduardo", "Fernanda", "Gustavo", "Helena", "Ivan", "Juliana",
    "Leonardo", "Márcia", "Nilton", "Patrícia", "Renato", "Sérgio",
    "Tatiane", "Valéria", "Wesley",
]
SOBRENOMES = [
    "Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Ferreira", "Gomes",
    "Henriques", "Inácio", "Jardim", "Klein", "Lima", "Martins", "Nunes",
    "Oliveira", "Pereira", "Queiroz", "Ribeiro", "Santos", "Teixeira",
    "Uchoa", "Vasconcelos", "Werneck", "Xavier", "Zanetti", "Araújo",
    "Bittencourt", "Carvalho", "Fonseca", "Moreira", "Rocha", "Siqueira",
]
# Cargos públicos de prefeitura. O cargo é campo de texto livre no cadastro —
# aqui é só a lista de exemplo, para o directory parecer real.
CARGOS = [
    "Diretor", "Diretora", "Secretário", "Secretária", "Coordenador",
    "Coordenadora", "Gerente", "Analista", "Técnico", "Técnica",
    "Assistente Administrativo", "Auxiliar Administrativo", "Recepcionista",
]
LOTACOES = [
    "Gabinete", "Divisão", "Departamento", "Núcleo", "Comissão", "Copa",
]


def nome_para_exibicao(nome_completo: str) -> str:
    """Nome como aparece na LISTA TELEFÔNICA: primeiro + último.

    "Ana Beatriz Souza Rocha" vira "Ana Rocha". A lista é um diretório, não um
    prontuário; o nome inteiro fica no cadastro, que é onde ele é útil."""
    partes = [p for p in (nome_completo or "").split() if p]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[-1]}"


def telefone_legivel(numero: str) -> str:
    """`(35) 3591-5101` a partir de `3535915101` — o formato que a lista usa."""
    d = "".join(c for c in (numero or "") if c.isdigit())
    if len(d) == 11 and d.startswith("55"):
        d = d[2:]
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return f"({DDD}) {numero}" if numero else ""


def faixa_telefones():
    """Os números da faixa, como string, em ordem."""
    return [f"{DDD}3591{n}" for n in range(FAIXA_INICIO, FAIXA_FIM + 1)]


def ler_csv(caminho: str):
    """Lê o CSV de dados reais. Colunas obrigatórias:

        matricula;nome_completo;unidade;cargo;lotacao;telefone

    Devolve a lista de dicts. Falha com mensagem clara, porque o arquivo é
    digitado à mão e o erro de digitação é comum."""
    with open(caminho, newline="", encoding="utf-8-sig") as fh:
        linhas = list(csv.DictReader(fh, delimiter=";"))
    if not linhas:
        raise SystemExit("O CSV está vazio.")
    exigidas = ("matricula", "nome_completo", "unidade", "cargo", "telefone")
    faltando = [c for c in exigidas if c not in linhas[0]]
    if faltando:
        raise SystemExit(
            f"Faltam colunas no CSV: {', '.join(faltando)}. "
            f"Esperado: {';'.join(exigidas)}[;lotacao]")
    return linhas


def pessoas_ficticias(quantidade: int, semente: int = 20260927):
    """Gera `quantidade` pessoas fictícias, com nomes varietyados.

    Semente fixa de propósito: rodar o script duas vezes produz o MESMO
    resultado, e quem revisa o_diff sabe que o texto mudou é a escolha da
    pessoa, não a sorte."""
    sorteio = random.Random(semente)
    pessoas = []
    usados = set()
    for _ in range(quantidade):
        while True:
            prenome = sorteio.choice(PRENOMES)
            sobrenome = sorteio.choice(SOBRENOMES)
            completo = f"{prenome} {sorteio.choice(PRENOMES)} {sobrenome}"
            if completo not in usados:
                usados.add(completo)
                break
        pessoas.append({
            "nome_completo": completo,
            "cargo": sorteio.choice(CARGOS),
            "lotacao": sorteio.choice(LOTACOES),
        })
    return pessoas


def main():
    ap = argparse.ArgumentParser(
        description="Popula servidores na lista telefônica e no cadastro de "
                    "usuários. Ensaio por padrão; --aplicar grava de verdade.")
    ap.add_argument("--aplicar", action="store_true",
                    help="Grava de verdade. Sem esta flag, é só ensaio.")
    ap.add_argument("--csv", help="CSV de dados reais (matricula;nome_completo;"
                                  "unidade;cargo;telefone). Sem ela, nomes fictícios.")
    ap.add_argument("--somente", help="Filtra a unidade pelo nome (ex.: 'Saúde').")
    ap.add_argument("--limite", type=int, help="Popula no máximo N servidores.")
    args = ap.parse_args()

    from mod_lista_telefonica import bd_manipulador as lista
    from mod_gest_cad_usuario import bd_manipulador as cadastro

    arvore = lista.listar_arvore_contatos()
    if not arvore:
        raise SystemExit("Nenhuma unidade encontrada. Rode o sistema uma vez "
                         "antes, para o organograma existir.")

    if args.somente:
        alvo = (args.somente or "").casefold()

        def filtrar(nos):
            out = []
            for no in nos:
                copia = dict(no)
                copia["filhos"] = filtrar(no["filhos"])
                if alvo in (no["nome"] or "").casefold() or copia["filhos"]:
                    out.append(copia)
            return out
        arvore = filtrar(arvore)
        if not arvore:
            raise SystemExit(f"Nenhuma unidade casa com {args.somente!r}.")

    # Achata a árvore, guardando o caminho (o folder da lista telefônica).
    unidades = []

    def descer(nos, caminho):
        for no in nos:
            atual = caminho + [no["nome"]]
            unidades.append((no, list(atual)))
            descer(no["filhos"], atual)
    descer(arvore, [])

    # Um telefone por secretaria, um por setor, o resto nos subsetores.
    # A regra é por TIPO, na ordem em que a árvore já vem (alfabética), e não
    # por posição na lista — assim o telefone de uma secretaria é sempre o
    # mesmo, mesmo que outra secretaria ganhe servidor depois.
    telefones = iter(faixa_telefones())
    usados_por_unidade = {}
    for no, _caminho in unidades:
        if no["tipo"] in ("secretaria", "setor", "subsetor"):
            try:
                usados_por_unidade[no["id"]] = next(telefones)
            except StopIteration:
                pass
    restante = list(telefones)  # o que sobrou da faixa

    if args.csv:
        pessoas = ler_csv(args.csv)
        fonte = f"CSV {args.csv}"
    else:
        pessoas = pessoas_ficticias(len(unidades) or 1)
        fonte = "nomes fictícios"

    print(f"  unidades na árvore : {len(unidades)}")
    print(f"  faixa de telefones : {len(faixa_telefones())} "
          f"({DDD} 3591-{FAIXA_INICIO} a {DDD} 3591-{FAIXA_FIM})")
    print(f"  telefones usados   : {len(usados_por_unidade)}")
    print(f"  servidores         : {len(pessoas)}  (fonte: {fonte})")
    print()

    if not args.aplicar:
        print("  ENSAIO — nada foi gravado. Use --aplicar para gravar.")
        for i, (no, caminho) in enumerate(unidades[:8]):
            p = pessoas[i % len(pessoas)]
            tel = usados_por_unidade.get(no["id"], "")
            print(f"    {' / '.join(caminho):46} "
                  f"{nome_para_exibicao(p['nome_completo']):22} {telefone_legivel(tel)}")
        if len(unidades) > 8:
            print(f"    ... mais {len(unidades) - 8}")
        return 0

    print("  APLICANDO — grava em tb_usuarios, tb_telefone_usuario e tb_contato.")
    criados = contatos = ignorados = 0
    for i, (no, caminho) in enumerate(unidades):
        if args.limite and criados >= args.limite:
            break
        p = pessoas[i % len(pessoas)]
        matricula = str(MATRICULA_INICIO + i)
        nome_exibicao = nome_para_exibicao(p["nome_completo"])
        tel = usados_por_unidade.get(no["id"]) or (restante.pop(0) if restante else "")
        if not tel:
            break

        existente = cadastro.obter_usuario(matricula)
        if existente:
            ignorados += 1
            continue

        ok, msg = cadastro.criar_usuario(
            "sistema", matricula, SENHA_PROVISORIA, fone=telefone_legivel(tel),
            perfil="comum", nome_completo=p["nome_completo"])
        if not ok:
            print(f"    [falha] {matricula} — {msg}")
            continue
        criados += 1

        cadastro.adicionar_telefone("sistema", matricula, telefone_legivel(tel),
                                    papel="empresa", tipo="fixo", principal=True)
        cadastro.definir_dados_funcionais(
            "sistema", matricula, unidade=caminho[0] if caminho else "",
            lotacao=p.get("lotacao", ""), cargo=p.get("cargo", ""))

        lista.criar_contato(no["id"], nome_exibicao, telefone_legivel(tel),
                            user_nome=matricula, ator="sistema")
        contatos += 1

    print()
    print(f"  usuários criados    : {criados}  (já existentes: {ignorados})")
    print(f"  contatos na lista   : {contatos}")
    print(f"  total de contatos   : {lista.contar_contatos()}")
    print("  Todos com senha provisória 123456 e TROCA OBRIGATÓRIA no 1º acesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
