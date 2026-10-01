"""EN: Syncs the collected server sheet into the user register.

PT-BR: Sincroniza a folha de servidores coletada no cadastro de usuários.

O QUE ESTE SCRIPT FAZ
    Lê o arquivo produzido por `coleta_folha.py` e grava cada servidor em
    `mod_gest_cad_usuario`, criando o que é novo e atualizando o que mudou.
    Pode rodar quantas vezes quiser: rodar duas vezes não duplica ninguém.

A MATRÍCULA É O NOME DE USUÁRIO
    A prefeitura já tem um identificador único e público para cada servidor,
    e ele é o login. Não há senha inventada a memorizar, não há colisão de
    nome entre homônimos (que no interior do Brasil não é raro) e o servidor
    reconhece o próprio número de matrícula na tela de login.

O QUE NÃO ENTRA NO BANCO
    Telefone. O portal não publica ramal — e esta escolha é do usuário que
    pediu, não um limite técnico. Todo servidor nasce com `telefone_pendente`
    ligado: no primeiro acesso, depois de trocar a senha, o sistema pergunta
    celular particular, celular da prefeitura e fixo da prefeitura, cada
    um com a sua caixa de "pode aparecer na lista telefônica?". O fixo da
    prefeitura publica sozinho, porque linha institucional existe para ser
    achada; o celular é escolha de cada pessoa.

QUEM NASCE BLOQUEADO
    Pensionista, Inativo e Eleito entram no cadastro — o registro é obrigatório
    e o histórico importa — mas bloqueados: não podem entrar no sistema. O
    mesmo vale para quem está com situação "Demitido". Bloquear é reversível
    pelo administrador; apagar não seria.

COMO USAR
    python mod_gest_cad_usuario/carga_folha.py            # ensaia
    python mod_gest_cad_usuario/carga_folha.py --aplicar   # grava
    python mod_gest_cad_usuario/carga_folha.py --aplicar --competencia 07/2026

    Sem `--aplicar` nada é escrito: o script só mostra o que faria.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

# A raiz do repositório é UM nível acima do módulo. Dois `..` subiam um nível
# demais e faziam `caminho_csv` relativo resolver para fora do repositório —
# o "arquivo não encontrado" apontava para um caminho que não existe e não
# deixava pista de onde veio o erro.
RAIZ_REPO = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, RAIZ_REPO)

# A folha mora em `dados/`, dentro do módulo, e fora do git (AGENTS.md §1 e
# §8.3): os dados são de servidores reais e não vão para o histórico.
DIR_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
ARQUIVO_PADRAO = os.path.join(DIR_DADOS, "funcionarios.json")
SENHA_PROVISORIA = "123456"
# Competencia da folha em sincronizacao: carimba a remuneracao, para que
# o historico diga de que mes e o valor. A folha traz o campo por servidor;
# esta e a reserva para quando vier vazio.
COMPETENCIA_FOLHA = ""
ATOR = "carga_folha"

# Vínculos que continuam no cadastro (o registro é obrigatório) mas não podem
# entrar no sistema: quem não está mais vinculado não tem por que logar.
VINCULOS_BLOQUEADOS = {"pensionista", "inativo", "eleito", "exonerado"}
SITUACOES_BLOQUEADAS = {"demitido", "exonerado", "afastado"}


def _log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "")
                   if not unicodedata.combining(c)).lower().strip()


def _bonito(texto: str) -> str:
    """`Secretaria Municipal De Educacao Publica` -> `Secretaria Municipal de Educacao Publica`.

    O portal guarda TUDO em caixa alta e sem acento, porque é assim que vai
    para o banco municipal. Mostrar "DE EDUCACAO" na lista telefônica da
    própria prefeitura é feio; mas inventar o acento (`EDUCAÇÃO`) é pior,
    porque passa a ser um dado que a fonte não disse. Aqui só se mexe na
    caixa — as minúsculas viram minúsculas, os acentos ficam como estão.
    """
    limpo = (texto or "").strip()
    if not limpo:
        return ""
    # "De Educacao" -> "de Educacao": preposições e artigos em minúscula
    minusculas = {"de", "da", "do", "das", "dos", "e", "a", "o"}
    partes = limpo.split()
    saida = []
    for i, p in enumerate(partes):
        if i > 0 and _sem_acento(p) in minusculas:
            saida.append(p.lower())
        else:
            saida.append(p)
    return " ".join(saida)


def _bloqueado(reg: dict) -> tuple[bool, str]:
    """Diz se o servidor entra bloqueado, e por quê."""
    vinculo = _sem_acento(reg.get("vinculo"))
    situacao = _sem_acento(reg.get("situacao"))
    if vinculo in VINCULOS_BLOQUEADOS:
        return True, f"vínculo {reg.get('vinculo')}"
    if situacao in SITUACOES_BLOQUEADAS:
        return True, f"situação {reg.get('situacao')}"
    return False, ""


def _matricula(reg: dict) -> str:
    """The login. Digits only — a matrícula with punctuation would be a
    different login depending on how the user typed it."""
    return "".join(c for c in str(reg.get("matricula") or "") if c.isdigit())


def _arvore_real(folha: dict) -> dict:
    """Monta a estrutura secretaria -> departamento a partir da folha.

    O portal dá DUAS coisas: `unidade` (a secretaria) e `lotacao` (o
    departamento dentro dela). Quando as duas são iguais, o servidor está
    ligado direto na secretaria e não há departamento a criar."""
    arvore, ordem = {}, {}
    for reg in folha.get("servidores") or []:
        sec = _bonito(reg.get("unidade"))
        if not sec:
            continue
        arvore.setdefault(sec, set())
        if sec not in ordem:
            ordem[sec] = len(ordem) + 1
        lot = _bonito(reg.get("lotacao"))
        if lot and _sem_acento(lot) != _sem_acento(sec):
            arvore[sec].add(lot)
    return {"secretarias": {k: sorted(v) for k, v in arvore.items()},
            "ordem": ordem}


def sincronizar_unidades(folha: dict, aplicar: bool = False) -> dict:
    """Monta o organograma que a folha conhece e pede para grava-lo.

    ESTE MÓDULO NÃO FALA COM A LISTA TELEFÔNICA
        A folha é do módulo de cadastro; o organograma gravado é do módulo da
        lista telefônica, que tem banco próprio. Módulo de negócio não importa
        módulo de negócio — nem para ler, muito menos para escrever
        (AGENTS.md §2, e `check_integridade.py` reprova a aresta). Por isso
        este arquivo só monta o PLANO e chama a fachada do núcleo, que costura
        com `mod_lista_telefonica.bd_manipulador.sincronizar_organograma`.

    POR QUE DESATIVAR E NÃO APAGAR
        O banco pode vir com um organograma de demonstração (12 secretarias
        fictícias, semeado por uma instalação anterior). Diante da folha real,
        elas viram pastas vazias na lista telefônica de uma prefeitura de
        verdade — confusão pura. Mas apagar é definitivo, e pasta vazia tem
        vez: o administrador pode estar montando um organograma que a folha
        ainda não publica. Então: `ativo=0`, que some da lista e pode voltar
        com um UPDATE. Nada é destruído.

    A ÁRVORE É RECIÁVEL
        Rodar de novo não duplica: casa por nome normalizado (sem acento, sem
        caixa, só letras e números), que é a mesma regra de
        `mod_lista_telefonica.bd_manipulador._norm` — duas grafias de "Saúde"
        são a mesma secretaria.
    """
    try:
        from mod_intranet import integracoes
        modelo = _arvore_real(folha)
        # Plano flat, de raiz para a folha: (nome, tipo, pai, ordem).
        plano = []
        for i, (sec, setores) in enumerate(sorted(
                modelo["secretarias"].items(),
                key=lambda kv: modelo["ordem"].get(kv[0], 999))):
            plano.append((sec, "secretaria", None, i))
            for j, setor in enumerate(sorted(setores)):
                plano.append((setor, "setor", sec, j))
        return integracoes.sincronizar_organograma_cadastro(
            plano, aplicar=aplicar, ator=ATOR)
    except Exception as e:
        _log(f"  organograma nao sincronizado: {e}")
        return {"secretarias_criadas": 0, "setores_criadas": 0,
                "setores_criados": 0, "reativadas": 0, "desativadas": 0,
                "erros": [str(e)]}


def _comparar_dados(unidade_atual, lotacao_atual, cargo_atual,
                    unidade_nova, lotacao_nova, cargo_nova) -> str:
    """Monta o texto do alerta comparando o cadastro com a folha.

    O texto é escrito **para o servidor ler**, não para o técnico: "seu
    departamento mudou de A para B" e não "lote divergente: atual=..., novo=
    ...". A diferença é que o primeiro se responde, e o segundo só se
    traduz.

    Devolve "" quando não há diferença — e compara SEM ACENTO, porque o
    portal guarda "Educacao" e o cadastro pode ter "Educação" sem que isso
    seja mudança de setor. Sem essa tolerância, metade da prefeitura
    receberia um alerta por causa de acento.
    """
    partes = []
    for rotulo, atual, novo in (("secretaria", unidade_atual, unidade_nova),
                                ("departamento", lotacao_atual, lotacao_nova),
                                ("cargo", cargo_atual, cargo_nova)):
        atual = (atual or "").strip()
        novo = (novo or "").strip()
        if not novo:
            continue  # a folha não trouxe: não é mudança, é ausência
        if _sem_acento(atual) == _sem_acento(novo):
            continue
        if not atual:
            partes.append(f"o seu {rotulo} agora é \"{novo}\"")
        else:
            partes.append(f"seu {rotulo} mudou de \"{atual}\" para \"{novo}\"")
    if not partes:
        return ""
    return "; ".join(partes).capitalize() + "."


def _esta_ativo(bd, user_nome) -> bool:
    """A conta está ativa (não bloqueada) no cadastro?"""
    try:
        cur = bd.get_connection()
        try:
            cur.execute("SELECT user_ativo FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            linha = cur.fetchone()
        finally:
            cur.close()
        return bool(linha and linha[0])
    except Exception:
        # Sem conseguir ler, NÃO assume bloqueado: devolver False aqui
        # desbloquearia contas que talvez devam estar fechadas. O erro de
        # verdade é o da gravação do desbloqueio, não o da leitura.
        return True


def sincronizar(folha: dict, aplicar: bool = False) -> dict:
    """Walks the sheet and creates/updates each server. Returns a summary."""
    global COMPETENCIA_FOLHA
    from mod_gest_cad_usuario import bd_manipulador as bd
    COMPETENCIA_FOLHA = str(folha.get("competencia") or "").strip()
    folha_competencia = COMPETENCIA_FOLHA

    servidores = folha.get("servidores") or []
    resumo = {"criados": 0, "nomes_corrigidos": 0, "marcados": 0,
              "a_marcar": 0, "inalterados": 0, "bloqueados": 0,
              "desbloqueados": 0, "erros": [], "vinculos": {}}

    for i, reg in enumerate(servidores, 1):
        mat = ""
        try:
            mat = _matricula(reg)
            # NAO grava a competencia dentro de `reg`: `reg` e a linha da
            # folha, do chamador. Mutar o dado de quem chamou para carregar
            # um carimbo nosso e um efeito colateral que reaparece no CSV
            # quando alguem reexporta a folha.
            nome = (reg.get("nome") or "").strip()
            if not mat or not nome:
                resumo["erros"].append(f"linha {i}: sem matrícula ou nome")
                continue

            bloq, _motivo = _bloqueado(reg)
            vinculo = reg.get("vinculo") or "(sem vínculo)"
            resumo["vinculos"][vinculo] = resumo["vinculos"].get(vinculo, 0) + 1
            unidade = _bonito(reg.get("unidade"))
            lotacao = _bonito(reg.get("lotacao"))
            # A lotação repete a unidade quando o servidor está ligado direto
            # na secretaria, sem departamento. Repetir na ficha é ruído.
            if _sem_acento(lotacao) == _sem_acento(unidade):
                lotacao = ""
            cargo = _bonito(reg.get("cargo"))

            existente = bd.obter_usuario(mat)
            if not existente:
                if not aplicar:
                    resumo["criados"] += 1
                else:
                    ok, msg = bd.criar_usuario(
                        ATOR, mat, SENHA_PROVISORIA, perfil="comum",
                        nome_completo=nome, exigir_telefone=True)
                    if not ok:
                        resumo["erros"].append(f"{mat}: {msg}")
                        continue
                    resumo["criados"] += 1
                    bd.definir_dados_funcionais(ATOR, mat, unidade=unidade,
                                               lotacao=lotacao, cargo=cargo)
            else:
                # JÁ EXISTE — e aqui é onde mudou a philosophy (28/09/2026).
                #
                # O script NÃO sobrescreve mais o setor, o departamento e o
                # cargo. Ele COMPARA com o que está no cadastro e, havendo
                # diferença, MARCA a pendência para a pessoa confirmar no
                # primeiro acesso.
                #
                # Por que perguntar e não escrever:
                #   - o portal é a fonte do setor, mas o telefone só a pessoa
                #     sabe; quem responde é quem sabe;
                #   - overwrite apagaria o ajuste que o administrador fez à
                #     mão no painel do organograma;
                #   - e o mais concreto: uma transferência de setor é
                #     informação do RH. Se o sistema troca sozinho, um erro
                #     de digitação no portal muda o cadastro de uma pessoa
                #     real sem ninguém ter visto.
                # `get_connection()` devolve a CONEXÃO; quem lê é o CURSOR.
                # Chamar `.fetchone()` na conexão levanta AttributeError e,
                # dentro do try por linha, a falha aparecia como "1165 erros"
                # sem parar a carga — e o ensaio (`--so-ensaio`) retorna antes
                # deste trecho, então só a aplicação real descobria o defeito.
                conn = bd.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT user_nome_completo, unidade, lotacao, "
                                "cargo FROM tb_usuarios WHERE user_nome=?",
                                (mat,))
                    linha = cur.fetchone()
                finally:
                    conn.close()
                if not linha:
                    continue
                nome_atual = (linha[0] or "")
                mudou_nome = _sem_acento(nome_atual) != _sem_acento(nome)
                if mudou_nome:
                    # o NOME mudou: este sim é objetivo, e corrigir é seguro.
                    # Não vira pergunta — ninguém tem ânimo de responder
                    # "qual é o seu nome, o do cadastro ou o do portal?".
                    if aplicar:
                        bd.editar_usuario(ATOR, mat, nome_completo=nome,
                                          auditar=False)
                    resumo["nomes_corrigidos"] += 1
                diferencas = _comparar_dados(linha[1], linha[2], linha[3],
                                             unidade, lotacao, cargo)
                if diferencas and aplicar:
                    ok_m, _m = bd.marcar_pendencia_dados(ATOR, mat,
                                                          diferencas)
                    if ok_m:
                        resumo["marcados"] += 1
                elif diferencas:
                    resumo["a_marcar"] += 1
                if not diferencas and not mudou_nome:
                    resumo["inalterados"] += 1

            if bloq:
                resumo["bloqueados"] += 1
                if aplicar:
                    bd.bloquear_usuario(ATOR, mat, True)
            elif aplicar and not _esta_ativo(bd, mat):
                # O CAMINHO DE VOLTA. Bloquear sem saber desbloquear é meio
                # caminho: um servidor que era pensionista e foi reverso para
                # efetivo pelo RH aparece ativo no portal e CONTINUARIA
                # bloqueado aqui, sem ninguém saber por quê. A folha da
                # prefeitura é a fonte da verdade: se ela diz que a pessoa
                # está no serviço, a conta abre.
                bd.bloquear_usuario(ATOR, mat, False)
                resumo["desbloqueados"] += 1

            # ---- Vínculo e situação: objetivo, como a remuneração (28/09/2026)
            # "é efetivo?" e "está ativo?" saem da folha, e a folha é a fonte.
            # Sem isto, a lista telefônica não consegue responder essas duas
            # perguntas de quem não autorizou telefone — e a pessoa some da
            # busca, que é o contrário do que a lista precisa fazer.
            vinculo = (reg.get("vinculo") or "").strip()
            situacao_reg = (reg.get("situacao") or "").strip()
            if aplicar and (vinculo or situacao_reg):
                bd.definir_vinculo(ATOR, mat, vinculo=vinculo or None,
                                   situacao=situacao_reg or None)
                # A chave `vinculos` do resumo JÁ é usada (histograma por tipo
                # de vínculo, na linha 269). Somar um contador nela quebrava
                # com "unsupported operand type(s) for +: 'dict' and 'int'".
                resumo["vinculos_gravados"] = resumo.get("vinculos_gravados", 0) + 1

            # ---- Remuneração: atualiza e registra histórico (28/09/2026) ----
            # Objetivo e publicado todo mês por lei. Este NÃO pergunta a
            # ninguém: não há o que a pessoa confirme, o valor é o oficial e
            # o registro é do RH. A mudança vai direto para o histórico.
            rem = (reg.get("remuneracao") or "").strip()
            ficha = (reg.get("ficha_contracheque") or "").strip()
            if aplicar and (rem or ficha):
                bd.definir_remuneracao(
                    ATOR, mat, remuneracao=rem,
                    competencia=folha_competencia,
                    ficha_contracheque=ficha)
                resumo["remuneracoes"] = resumo.get("remuneracoes", 0) + 1

            if i % 100 == 0 or i == len(servidores):
                _log(f"  {i}/{len(servidores)} "
                     f"(criados {resumo['criados']}, "
                     f"marcados {resumo['marcados']})")
        except Exception as e:
            resumo["erros"].append(f"linha {i} ({mat or '?'}): {e}")

    return resumo


COLUNAS_CSV = ("matricula", "nome", "unidade", "lotacao", "cargo",
              "vinculo", "situacao", "remuneracao", "ficha_contracheque",
              "regime", "carga_horaria", "admissao", "exoneracao")

# ---- Configuração da fonte (28/09/2026) ----
# O sistema é publicado em git para qualquer prefeitura ou empresa usar.
# Nada de município, empresa, URL ou nome de órgão pode estar no código: o
# que a prefeitura é entra no ARQUIVO DE CONFIGURAÇÃO, e o padrão é
# "desligado", para quem não configurar nada receber um sistema funcionando
# e vazio, em vez de um sistema que tenta se conectar a um lugar estranho.
CONFIG_PADRAO = {
    "ativo": False,
    "origem": "csv",
    "caminho_csv": "mod_gest_cad_usuario/dados/funcionarios.csv",
    "delimitador": "auto",
    "competencia": "",
    "portal_url": "",
    "portal_pagina": "/servidores-por-nomes",
    "portal_intervalo_min_s": 1.0,
    "portal_intervalo_max_s": 5.0,
    "portal_user_agent": "intranet/1.0 (carga de servidores - dados publicos)",
    "origem_rotulo": "",
    "portal_endpoints": {"folha": "", "competencia": ""},
    "colunas": {campo: [campo] for campo in COLUNAS_CSV},
}
ARQUIVO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "fonte_folha.json")


def carregar_config(caminho=None):
    """Lê a configuração da fonte, com o padrão quando ela não existe.

    Devolve o dicionário pronto para uso. Um JSON quebrado NÃO derruba o
    script: cai no padrão (desligado) e diz o que houve. Um arquivo de
    configuração com vírgula faltando é motivo para o técnico corrigir, não
    para o sistema de intranet parar.
    """
    arq = caminho or ARQUIVO_CONFIG
    cfg = dict(CONFIG_PADRAO)
    cfg["colunas"] = {k: list(v) for k, v in CONFIG_PADRAO["colunas"].items()}
    if not os.path.exists(arq):
        return cfg, f"sem arquivo de configuração em {arq}"
    try:
        with open(arq, encoding="utf-8") as f:
            bruto = json.load(f)
        for chave in ("ativo", "origem", "caminho_csv", "delimitador",
                      "competencia", "portal_url", "portal_pagina",
                      "portal_intervalo_s", "portal_user_agent",
                      "origem_rotulo", "portal_endpoints"):
            if chave in bruto:
                cfg[chave] = bruto[chave]
        if isinstance(bruto.get("colunas"), dict):
            for campo, apelidos in bruto["colunas"].items():
                if isinstance(apelidos, str):
                    apelidos = [apelidos]
                if apelidos:
                    cfg["colunas"][campo] = list(apelidos)
        return cfg, None
    except Exception as e:
        return cfg, f"configuração ilegível ({e}) — usando o padrão DESLIGADO"


def _detectar_delimitador(amostra, preferido="auto"):
    """`;`, `,` ou tabulação — whichever o arquivo usa.

    Pontua pela CONSISTÊNCIA entre linhas, e não pela contagem: um nome de
    servidor com vírgula ("Souza, Ana") pontua alto numa coluna só, e um
    arquivo inteiro com `,` pontua igual em todas. Quem decide é a segunda
    linha, que é onde o padrão se mostra.
    """
    if preferido and preferido != "auto":
        return preferido
    linhas = [l for l in amostra.splitlines() if l.strip()][:8]
    if not linhas:
        return ";"
    melhor, pontos = ";", -1
    for sep in (";", ",", "\t", "|"):
        contagens = {sep: l.count(sep) for l in linhas}
        if not max(contagens.values()):
            continue
        moda = max(set(contagens.values()), key=contagens.get)
        # precisa ser o mesmo número de separadores em todas as linhas
        if all(c == moda for c in contagens.values()) and moda > pontos:
            melhor, pontos = sep, moda
    return melhor


def _resolver_coluna(cabecalho, apelidos):
    """acha a coluna do arquivo entre os apelidos aceitos.

    A comparação tira acento, espaço e pontuação, porque "Carga Horária",
    "carga_horaria" e "CARGA-HORARIA" são a mesma coluna para quem está
    configuring e três campos lostos para quem não sabe disso.
    """
    def chave(txt):
        return re.sub(r"[^a-z0-9]", "", _sem_acento(txt or ""))

    mapa = {chave(h): h for h in cabecalho}
    for apelido in (apelidos or []):
        achado = mapa.get(chave(apelido))
        if achado:
            return achado
    return None


def ler_csv_configuravel(caminho, cfg):
    """Lê o CSV do município/empresa seguindo a configuração.

    Aceita o mesmo formato do JSON do coletor, para que as duas entradas
    (`--csv` e o arquivo padrão) levem ao mesmo sync.
    """
    import csv
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        primeiro = f.readline()
        f.seek(0)
        sep = _detectar_delimitador(primeiro, cfg.get("delimitador", "auto"))
        leitor = csv.reader(f, delimiter=sep)
        cabecalho = next(leitor, [])
        if not cabecalho:
            return {"origem": f"CSV ({caminho})", "competencia": "",
                    "coletado_em": "", "total": 0, "servidores": []}
        # mapa: campo que a tela precisa -> coluna real do arquivo
        resolucao = {}
        for campo in COLUNAS_CSV:
            achado = _resolver_coluna(cabecalho, cfg["colunas"].get(campo))
            if achado:
                resolucao[campo] = achado
        faltando = [c for c in ("matricula", "nome") if c not in resolucao]
        if faltando:
            raise ValueError(
                f"o CSV não tem coluna de {', '.join(faltando)}. "
                f"Colunas encontradas: {', '.join(cabecalho)}. "
                f"Renomeie a coluna no arquivo, ou acrescente o nome dela em "
                f"'colunas' no arquivo fonte_folha.json.")
        servidores = []
        for linha in leitor:
            if not any((v or "").strip() for v in linha):
                continue
            reg = {}
            for campo, coluna in resolucao.items():
                try:
                    valor = (linha[cabecalho.index(coluna)] or "").strip()
                except (IndexError, ValueError):
                    valor = ""
                reg[campo] = valor or None
            servidores.append(reg)
        return {
            "origem": f"CSV ({os.path.basename(caminho)})",
            "url": "",
            "competencia": cfg.get("competencia") or "",
            "coletado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(servidores),
            "aviso": f"delimitador '{sep}' | colunas: "
                     f"{', '.join(sorted(resolucao.values()))}",
            "servidores": servidores,
        }


def _tem_terminal() -> bool:
    """Da para perguntar algo a quem esta rodando?"""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


# ===========================================================================
# CARGA AUTOMÁTICA (chamada pelo agendador, sem ninguém perguntando nada)
# ===========================================================================
# A carga automática tem uma regra a mais que a manual: ela só age sobre um
# arquivo NOVO. A manual pode ser rodada a qualquer hora por alguém que sabe o
# que está fazendo; a automática roda sozinha, todo dia, e o requisito dela é
# ser inofensiva para quem não a configurou e para quem configurou mas ainda
# não fechou o mês.
#
# Três travas, nesta ordem:
#   1. `ativo` precisa estar ligado no `fonte_folha.json`;
#   2. a folha precisa ter PELO MENOS um servidor — arquivo vazio ou truncado
#      é o jeito mais comum de a prefeitura errar o caminho, e zerar o
#      cadastro por causa disso seria o pior resultado possível;
#   3. o arquivo precisa ser DIFERENTE do da última carga — repetir o mesmo
#      arquivo todo dia não reconta nada, não gera alerta e não gasta tempo.
#
# Nenhuma das travas depende de o arquivo estar certo: mesmo com a folha
# trocada, a carga NUNCA sobrescreve o cadastro de quem já existe. Servidor que
# mudou de setor recebe pendência e confirma no primeiro acesso.

ESTADO_CARGA = os.path.join(DIR_DADOS, ".ultima_carga.json")
# Abaixo disto é suspiciously pouco para uma folha de servidores; o piso evita
# que um CSV exportado pela metade vire "cadastro de 3 pessoas".
MINIMO_SERVIDORES = 1


def _importar_coletor():
    """Carrega o `coleta_folha` esteja ele como script ou como pacote.

    O mesmo arquivo é executável de dois jeitos (`python coleta_folha.py`) e
    importável (`from mod_gest_cad_usuario import coleta_folha`), e o nome do
    módulo é diferente nos dois casos. Testar os dois, em vez de escolher um,
    é o que evita a falha que só apareceria no agendador — que importa por
    pacote — e nunca na mão do técnico — que roda por script.
    """
    try:
        from mod_gest_cad_usuario import coleta_folha as modulo
        return modulo
    except Exception:
        pass
    try:
        if DIR_DADOS not in sys.path:
            sys.path.insert(0, DIR_DADOS)
        import coleta_folha as modulo
        return modulo
    except Exception:
        return None


def _digitalizar(caminho: str) -> str:
    """Impressão digital do arquivo: muda se o conteúdo mudar."""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(caminho, "rb") as f:
            for bloco in iter(lambda: f.read(65536), b""):
                h.update(bloco)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def ler_ultima_carga():
    """O que foi carregado por último (para o log e para a Home)."""
    try:
        with open(ESTADO_CARGA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _registrar_carga(estado: dict) -> bool:
    try:
        os.makedirs(DIR_DADOS, exist_ok=True)
        with open(ESTADO_CARGA, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        _log(f"  nao deu para registrar o estado da carga: {e}")
        return False


def carregar_folha(cfg):
    """Folha a ser sincronizada, conforme a origem configurada.

    `csv`  -> lê o arquivo local (é o padrão, e não depende de terceiro).
    `portal` -> recolhe do portal e devolve a folha freshly coletada; se o
               portal não estiver configurado, avisa e devolve None em vez de
               cair no CSV por baixo dos panos — porque quem pediu `portal` e
               receber o arquivo de três meses atrás sem saber é pior que
               não receber nada.
    """
    origem = (cfg.get("origem") or "csv").strip().lower()
    if origem == "portal":
        coletor = _importar_coletor()
        if coletor is None:
            _log("  'origem' pede portal, mas o coletor nao carregou. Nada foi "
                 "coletado.")
            return None
        if not getattr(coletor, "RAIZ", "") or not getattr(coletor, "GRID", ""):
            _log("  'origem' pede portal, mas 'portal_url'/'portal_endpoints' "
                 "estao vazios. Nada foi coletado.")
            return None
        coleta_folha = coletor
        try:
            os.makedirs(DIR_DADOS, exist_ok=True)
            return coleta_folha.coletar()
        except Exception as e:
            _log(f"  coleta do portal falhou: {e}")
            return None
    # csv (padrao)
    caminho = cfg.get("caminho_csv") or ""
    if caminho and not os.path.isabs(caminho):
        caminho = os.path.join(RAIZ_REPO, caminho)
    if not caminho or not os.path.exists(caminho):
        _log(f"  CSV nao encontrado: {caminho or '(nao configurado)'}")
        return None
    return ler_csv_configuravel(caminho, cfg)


def servidores_no_cadastro() -> int:
    """Quantos servidores da folha já estão no cadastro de usuários.

    A contagem é sobre quem tem **vínculo gravado**, que é o que a folha
    preenche (`sincronizar`, `carga_folha.py:242`) e o que o seed **não**
    preenche. Isso evita a lista de nomes de fábrica — que mudaria a cada
    renomeação de conta, e cuja lista explícita seria uma constante para
    manter. Um cadastro recém-criado tem os servidores de fábrica sem
    vínculo, então a conta começa em zero, que é exatamente o estado de
    "ainda não carregou".

    EN: How many sheet servers are already in the user register.
    """
    try:
        from mod_gest_cad_usuario import bd_manipulador as bd
        conn = bd.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios "
                        "WHERE vinculo IS NOT NULL AND TRIM(vinculo) <> ''")
            return int(cur.fetchone()[0] or 0)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        try:
            _log(f"  nao deu para contar os servidores no cadastro ({e})")
        except Exception:
            pass
        return 0


def primeira_carga_pendente() -> bool:
    """A carga da folha ainda nunca rodou neste banco? (30/09/2026)

    É o que separa o **primeiro boot** dos outros. A coleta do portal leva
    ~100 s e quase 50 requisições; pagar isso a cada reinício tornaria o
    servidor impraticável de subir. E o custo é real: com a folha já no
    cadastro, o agendador das 03:00 (com as três travas) é quem atualiza —
    que é o desenho que o `AGENTS.md` e o `docs/carga_de_servidores.md`
    já descrevem.

    **Por que o estado é o cadastro, e não um arquivo de marcador:** o banco é
    o que o administrador reinstala, apaga e recria. Um marcador em arquivo
    sobreviveria a `DELETE FROM tb_usuarios` e deixaria a installation com o
    banco vazio e a carga pulada — que é justamente o estado ruim que este
    passo existe para evitar.

    EN: True when the sheet has never been loaded into this database.
    """
    try:
        return servidores_no_cadastro() == 0
    except Exception:
        # Falhou a contagem: carrega. Uma folha a mais é desperdício de tempo;
        # um cadastro de servidores vazio é o sistema quebrado.
        return True


def carga_automatica(forcar: bool = False, config: str | None = None) -> dict:
    """Uma passada da carga, sozinha, sem prompt. Chamada pelo agendador.

    `config` existe para os testes (e para o técnico conferir uma configuração
    alternativa sem tocar na do sistema). O agendador não passa nada e usa a
    de `fonte_folha.json`.

    Devolve um dicionário de relatório (nunca levanta exceção) — quem chama é
    um job de fundo, e um job de fundo que levanta exceção some do log do
    APScheduler sem ninguém ver.
    """
    relatorio = {"rodou": False, "motivo": "", "criados": 0, "marcados": 0,
                 "bloqueados": 0, "erros": []}
    try:
        cfg, aviso_cfg = carregar_config(config)
        if aviso_cfg:
            relatorio["motivo"] = aviso_cfg
            return relatorio
        if not cfg.get("ativo") and not forcar:
            relatorio["motivo"] = "fonte desativada (fonte_folha.json: ativo=false)"
            return relatorio

        folha = carregar_folha(cfg)
        if not folha or not (folha.get("servidores") or []):
            relatorio["motivo"] = ("folha vazia ou indisponivel — nada foi "
                                   "gravado (o cadastro existente esta intacto)")
            return relatorio
        if len(folha["servidores"]) < MINIMO_SERVIDORES:
            relatorio["motivo"] = (f"folha com {len(folha['servidores'])} "
                                   "servidor(es) — abaixo do minimo, descartada")
            return relatorio

        # trava 3: o arquivo é o mesmo da última carga?
        origem_arquivo = (cfg.get("caminho_csv") if (cfg.get("origem") or "") == "csv"
                          else ARQUIVO_PADRAO)
        if origem_arquivo and not os.path.isabs(origem_arquivo):
            origem_arquivo = os.path.join(RAIZ_REPO, origem_arquivo)
        digital = _digitalizar(origem_arquivo) if origem_arquivo else ""
        if not digital:
            # origem portal: usa a própria folha, que acabou de ser coletada
            digital = _digitalizar(ARQUIVO_PADRAO) or str(len(folha["servidores"]))
        anterior = ler_ultima_carga()
        if digital and anterior.get("digital") == digital and not forcar:
            relatorio["motivo"] = (f"folha inalterada desde a carga de "
                                   f"{anterior.get('em', '?')[:16]} — nada a fazer")
            return relatorio

        relatorio["rodou"] = True
        uni = sincronizar_unidades(folha, aplicar=True)
        resumo = sincronizar(folha, aplicar=True)
        relatorio.update({
            "criados": resumo.get("criados", 0),
            "marcados": resumo.get("marcados", 0),
            "bloqueados": resumo.get("bloqueados", 0),
            "desbloqueados": resumo.get("desbloqueados", 0),
            "secretarias_criadas": uni.get("secretarias_criadas", 0),
            "setores_criados": uni.get("setores_criados", 0),
            "competencia": folha.get("competencia") or "",
            "total": len(folha["servidores"]),
            "erros": resumo.get("erros", [])[:20],
        })
        # O que MUDOU, e não só o que sobrou (01/10/2026). Sem estes três o
        # relatório respondia "criados 0, bloqueados 0" numa folha em que 40
        # salários tinham mudado e 600 continuavam iguais — e quem lê o log do
        # boot não distinguiria "a folha não mudou" de "a carga não rodou".
        #   nomes_corrigidos — o nome do portal discordou do cadastro e o
        #                      sistema corrigiu (objetivo, sem perguntar)
        #   vinculos_gravados/remuneracoes — vínculo, situação e salário
        #                      reescritos com a competência da folha
        #   inalterados      — quantos já estavam certos (o "de nada" que
        #                      prova que a travessia rodou mesmo)
        relatorio.update({
            "nomes_corrigidos": resumo.get("nomes_corrigidos", 0),
            "vinculos_gravados": resumo.get("vinculos_gravados", 0),
            "remuneracoes": resumo.get("remuneracoes", 0),
            "inalterados": resumo.get("inalterados", 0),
        })
        _registrar_carga({
            "digital": digital,
            "em": datetime.now().isoformat(timespec="seconds"),
            "origem": folha.get("origem", ""),
            "competencia": folha.get("competencia", ""),
            "total": len(folha["servidores"]),
            "criados": relatorio["criados"],
            "marcados": relatorio["marcados"],
        })
        return relatorio
    except Exception as e:
        relatorio["erros"].append(f"{type(e).__name__}: {e}")
        relatorio["motivo"] = f"falhou: {e}"
        try:
            import traceback
            relatorio["erros"].append(traceback.format_exc(limit=3))
        except Exception:
            pass
        return relatorio


def folha_arquivo_atual() -> dict:
    """A folha de servidores como está no ARQUIVO, sem gravar nada (01/10/2026).

    Lê o mesmo arquivo que a carga lê — o `dados/funcionarios.json` quando ele
    existe, e o CSV configurado em `fonte_folha.json` quando não — e devolve
    o dicionário cru: `origem`, `url`, `competencia`, `coletado_em`, `total`,
    `aviso` e a lista `servidores`.

    **Por que existe, e por que aqui:** quem publica dado público sobre a folha
    é o módulo de Dados Abertos, e ele NÃO pode ler um arquivo que mora na
    pasta deste módulo (AGENTS.md §2: módulo de negócio não alcança outro). A
    costura oficial é `mod_intranet/integracoes.folha_de_servidores_publica()`,
    que chama ESTA função. O conhecimento do arquivo — nome, caminho, formato,
    delimitador, colunas — fica aqui, com quem escreveu o arquivo; lá fora só
    circula o dicionário.

    **O que ela NÃO faz:** não grava, não audita, não bloqueia, não calcula
    média. É a leitura mais burra possível, porque é a que a tela de dados
    abertos precisa: mostrar o que a fonte publica, e não o que o cadastro
    Virou depois. `{}` em qualquer falha (fail-soft) — quem chama decide o
    que mostrar quando não há folha.

    EN: The server sheet as it sits in the FILE, writing nothing.
    """
    try:
        if os.path.exists(ARQUIVO_PADRAO):
            with open(ARQUIVO_PADRAO, encoding="utf-8") as f:
                folha = json.load(f)
            if isinstance(folha, dict):
                return folha
        # Sem o JSON: cai no CSV configurado — a mesma folha, em outro formato.
        cfg, _aviso = carregar_config()
        if not cfg.get("caminho_csv"):
            return {}
        caminho = cfg["caminho_csv"]
        if not os.path.isabs(caminho):
            caminho = os.path.join(RAIZ_REPO, caminho)
        if not os.path.exists(caminho):
            return {}
        return ler_csv_configuravel(caminho, cfg) or {}
    except Exception as e:
        _log(f"  nao deu para ler a folha do arquivo ({e})")
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grava a folha de servidores no cadastro de usuarios.")
    ap.add_argument("--arquivo", default=ARQUIVO_PADRAO,
                    help="folha em JSON (padrao: funcionarios.json)")
    ap.add_argument("--csv", dest="arquivo_csv",
                    help="folha em CSV, em vez do JSON")
    ap.add_argument("--aplicar", action="store_true",
                    help="grava sem perguntar (para cron). Sem esta flag, "
                         "pergunta - e sem terminal, nao grava.")
    ap.add_argument("--so-ensaio", action="store_true",
                    help="mostra o que faria e nao grava, mesmo com --aplicar.")
    ap.add_argument("--config", default=ARQUIVO_CONFIG,
                    help="arquivo de configuracao da fonte (fonte_folha.json).")
    ap.add_argument("--forcar", action="store_true",
                    help="ignora 'ativo: false' da configuracao.")
    args = ap.parse_args()

    cfg, aviso_cfg = carregar_config(args.config)
    if aviso_cfg:
        print(f"  (configuracao: {aviso_cfg})")
    if not cfg.get("ativo") and not args.forcar:
        # NADA CONFIGURADO, NADA ACONTECE. E sai com 0, e nao com erro: um
        # sistema novo de uma prefeitura sem folha de funcionarios pronta
        # esta perfectly normal, e um codigo de saida diferente de zero faria
        # o cron acusar falha onde nada falhou.
        print("\n  Carga de funcionarios DESLIGADA "
              "(fonte_folha.json com \"ativo\": true).")
        print("  Nada foi lido e nada foi gravado — este e o estado normal de "
              "um sistema")
        print("  recem-instalado. Para ligar: edite "
              "mod_gest_cad_usuario/fonte_folha.json, aponte o CSV e rode de novo.")
        print("  Para forcar agora, use --forcar.\n")
        return 0

    # ---- carrega a folha ----
    origem = args.arquivo_csv or args.arquivo
    try:
        if args.arquivo_csv:
            folha = ler_csv_configuravel(args.arquivo_csv, cfg)
        else:
            with open(args.arquivo, encoding="utf-8") as f:
                folha = json.load(f)
            # a competencia do JSON tem prioridade sobre a da configuracao:
            # o JSON foi coletado de uma folha especifica
            if not folha.get("competencia") or folha.get("competencia") == "(do CSV)":
                folha["competencia"] = cfg.get("competencia") or ""
    except FileNotFoundError:
        print(f"\n  Folha nao encontrada: {origem}\n"
              f"  Apontar o CSV:  edite 'caminho_csv' em {args.config}\n"
              f"  Ou coletar:     python mod_gest_cad_usuario/coleta_folha.py --atualizar\n",
              file=sys.stderr)
        return 1

    servidores = folha.get("servidores") or []
    print(f"\n  Folha   : {origem}")
    print(f"  Origem  : {folha.get('origem')}")
    print(f"  Competencia: {folha.get('competencia')}  ({len(servidores)} servidores)")

    # ---- o que vai acontecer, ANTES de qualquer escrita ----
    modelo = _arvore_real(folha)
    bloq = sum(1 for r in servidores if _bloqueado(r)[0])
    try:
        from mod_gest_cad_usuario import bd_manipulador as _bd_ensaio
        # `listar_usuarios()` devolve tuplas por índice e o índice 0 é o ID,
        # não o login — ler o login de lá dava sempre "não cadastrado" e o
        # ensaio prometia 1165 servidores novos sobre uma base já cheia.
        _c = _bd_ensaio.get_connection()
        try:
            existentes = {r[0] for r in _c.execute(
                "SELECT user_nome FROM tb_usuarios").fetchall()}
        finally:
            _c.close()
    except Exception:
        existentes = set()
    novos = sum(1 for r in servidores if _matricula(r) not in existentes)
    conhecidos = len(servidores) - novos

    print(f"\n  {novos} servidor(es) NOVOS seriam criados")
    print(f"  {conhecidos} ja cadastrados seriam conferidos")
    print(f"  {bloq} BLOQUEADOS (pensionista/inativo/eleito/demitido)")
    print(f"  Senha provisoria {SENHA_PROVISORIA} para os novos, com troca "
          f"+ telefone obrigatorios no 1o acesso")
    print(f"\n  Organograma: {len(modelo['secretarias'])} secretarias e "
          f"{sum(len(v) for v in modelo['secretarias'].values())} "
          f"departamentos; as unidades de demonstracao que o portal nao "
          f"conhece seriam DESATIVADAS")
    print("\n  Nos servidores ja cadastrados, o script NAO sobrescreve o setor:")
    print("  quem ja tem cadastro e mudou de secretaria/departamento/cargo")
    print("  recebe um ALERTA e confirma sozinho no primeiro acesso.")

    # ---- a pergunta ----
    aplicar = args.aplicar
    if not args.so_ensaio and not aplicar:
        if not _tem_terminal():
            print("\n  Sem terminal para perguntar (cron, pipe, servico). "
                  "Nada foi gravado.")
            print("  Use --aplicar para gravar sem perguntar, ou rode num "
                  "terminal.\n")
            return 0
        print("\n  Aplicar no banco de dados?")
        try:
            resp = input("     [s/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            resp = ""
        aplicar = resp in ("s", "sim", "y", "yes")
        if not aplicar:
            print("\n  Nada foi gravado.\n")
            return 0
    if args.so_ensaio:
        aplicar = False

    if not aplicar:
        print("\n  ENSAIO: nada sera gravado.\n")
        return 0

    print("\n  --- Organograma ---")
    uni = sincronizar_unidades(folha, aplicar=True)
    print(f"  secretarias criadas : {uni['secretarias_criadas']}")
    print(f"  setores criados      : {uni['setores_criados']}")
    print(f"  reativadas           : {uni['reativadas']}")
    print(f"  desativadas (demo)   : {uni['desativadas']}")

    print("\n  --- Usuarios ---")
    resumo = sincronizar(folha, aplicar=True)
    print(f"\n  criados        : {resumo['criados']}")
    print(f"  nomes corrigidos: {resumo['nomes_corrigidos']}")
    print(f"  marcados p/ confirmar: {resumo['marcados']}")
    print(f"  inalterados    : {resumo['inalterados']}")
    print(f"  bloqueados     : {resumo['bloqueados']}")
    if resumo["desbloqueados"]:
        print(f"  desbloqueados  : {resumo['desbloqueados']} "
              f"(voltaram a aparecer como ativos no portal)")
    if resumo["marcados"]:
        print("\n  Os servidores marcados veem o alerta no proximo acesso.")
        print("  O DTI acompanha a pendencia na Home.")
    if resumo["erros"]:
        print(f"\n  {len(resumo['erros'])} erro(s) - primeiros 10:")
        for e in resumo["erros"][:10]:
            print(f"    {e}")
    print()
    return 0



if __name__ == "__main__":
    sys.exit(main())
