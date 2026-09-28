"""EN: Syncs the collected server sheet into the user register.

PT-BR: Sincroniza a folha de servidores coletada no cadastro de usuários.

O QUE ESTE SCRIPT FAZ
    Lê o arquivo produzido por `coleta_servidores.py` e grava cada servidor em
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
    python assets/populacao/sincroniza_servidores.py            # ensaia
    python assets/populacao/sincroniza_servidores.py --aplicar   # grava
    python assets/populacao/sincroniza_servidores.py --aplicar --competencia 07/2026

    Sem `--aplicar` nada é escrito: o script só mostra o que faria.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

ARQUIVO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "servidores_coletados.json")
SENHA_PROVISORIA = "123456"
ATOR = "sincroniza_servidores"

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
    """Cria as unidades que o portal conhece e desativa as que ele não conhece.

    POR QUE DESATIVAR E NÃO APAGAR
        O banco já vem com um organograma de demonstração (12 secretarias
        fictícias, semeado por `init_db`). Diante da folha real, elas viram
        pastas vazias na lista telefônica de uma prefeitura de verdade —
        confusão pura. Mas apagar é definitivo, e pasta vazia tem vez: o
        administrador pode estar montando um organograma que o portal ainda
        não publica. Então: `ativo=0`, que some da lista e pode voltar com um
        UPDATE. Nada é destruído.

    A ÁRVORE É RECRIÁVEL
        Rodar de novo não duplica: casa por nome normalizado (sem acento,
        sem caixa, só letras e números), que é a mesma regra de
        `mod_lista_telefonica.bd_manipulador._norm`.
    """
    from mod_lista_telefonica import bd_manipulador as bd_lt

    def _norm(texto):
        s = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
        return " ".join(re.findall(r"[a-z0-9]+", s))

    def _ativar(unidade_id, valor):
        c = bd_lt.get_connection()
        try:
            c.execute("UPDATE tb_unidade SET ativo=? WHERE id=?", (valor, unidade_id))
            c.commit()
        finally:
            c.close()

    modelo = _arvore_real(folha)
    resumo = {"secretarias_criadas": 0, "setores_criados": 0,
              "reativadas": 0, "desativadas": 0, "erros": []}

    def _id_de(nome, parent_id):
        """Acha o id de uma unidade pelo nome — `criar_unidade` devolve
        `(ok, msg)` e o id fica dentro da mensagem, então buscar por nome é
        mais honesto que fazer regex no texto de retorno."""
        for u in bd_lt.listar_todas_unidades():
            if u[3] == parent_id and _norm(u[1]) == _norm(nome):
                return u[0]
        return None

    # u = (id, nome, tipo, parent_id, ordem, telefone, ativo)
    existentes = {}
    for u in bd_lt.listar_todas_unidades():
        existentes.setdefault((u[3], _norm(u[1])), []).append(u)

    reais = set()
    for sec, setores in sorted(modelo["secretarias"].items(),
                               key=lambda kv: modelo["ordem"].get(kv[0], 999)):
        chave_sec = (None, _norm(sec))
        reais.add(chave_sec)
        achada = existentes.get(chave_sec)
        if achada:
            sec_id = achada[0][0]
            if not achada[0][6]:  # exists but is OFF -> the unit came back
                if aplicar:
                    _ativar(sec_id, 1)
                resumo["reativadas"] += 1
        else:
            if aplicar:
                ok, msg = bd_lt.criar_unidade(sec, "secretaria", None, "", ATOR)
                if not ok:
                    resumo["erros"].append(f"secretaria '{sec}': {msg}")
                    continue
                sec_id = _id_de(sec, None)
            else:
                sec_id = None
            resumo["secretarias_criadas"] += 1
        if sec_id is None:
            continue
        for setor in setores:
            chave_set = (sec_id, _norm(setor))
            reais.add(chave_set)
            achado = existentes.get(chave_set)
            if achado:
                if not achado[0][6]:
                    if aplicar:
                        _ativar(achado[0][0], 1)
                    resumo["reativadas"] += 1
            else:
                if aplicar:
                    ok, msg = bd_lt.criar_unidade(setor, "setor", sec_id, "", ATOR)
                    if not ok:
                        resumo["erros"].append(
                            f"setor '{setor}' em '{sec}': {msg}")
                        continue
                resumo["setores_criados"] += 1

    # What the portal does not know about -> deactivate. `u[6]` is `ativo`, so
    # 1 means ON. Only the ONES not in the sheet are touched; the ones already
    # off are left alone so re-running does not inflate the counter.
    for chave, unidades in existentes.items():
        if chave in reais:
            continue
        for u in unidades:
            if not u[6]:
                continue
            if aplicar:
                _ativar(u[0], 0)
            resumo["desativadas"] += 1

    return resumo


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
    from mod_gest_cad_usuario import bd_manipulador as bd

    servidores = folha.get("servidores") or []
    resumo = {"criados": 0, "atualizados": 0, "inalterados": 0,
              "bloqueados": 0, "desbloqueados": 0, "erros": [], "vinculos": {}}

    for i, reg in enumerate(servidores, 1):
        mat = ""
        try:
            mat = _matricula(reg)
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
                # Já existe: só mexe no que mudou, para não reescrever 1165
                # usuários e gerar 1165 linhas de auditoria à toa.
                cur = bd.get_connection()
                try:
                    cur.execute("SELECT user_nome_completo FROM tb_usuarios "
                                "WHERE user_nome=?", (mat,))
                    linha = cur.fetchone()
                finally:
                    cur.close()
                nome_atual = (linha[0] if linha else "") or ""
                mudou = _sem_acento(nome_atual) != _sem_acento(nome)
                if aplicar:
                    if mudou:
                        bd.editar_usuario(ATOR, mat, nome_completo=nome,
                                          auditar=False)
                    bd.definir_dados_funcionais(ATOR, mat, unidade=unidade,
                                               lotacao=lotacao, cargo=cargo)
                if mudou:
                    resumo["atualizados"] += 1
                else:
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

            if i % 100 == 0 or i == len(servidores):
                _log(f"  {i}/{len(servidores)} "
                     f"(criados {resumo['criados']}, "
                     f"atualizados {resumo['atualizados']})")
        except Exception as e:
            resumo["erros"].append(f"linha {i} ({mat or '?'}): {e}")

    return resumo


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grava a folha de servidores no cadastro de usuários.")
    ap.add_argument("--arquivo", default=ARQUIVO_PADRAO,
                    help="folha coletada por coleta_servidores.py")
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de verdade. Sem esta flag, é só um ensaio.")
    args = ap.parse_args()

    try:
        with open(args.arquivo, encoding="utf-8") as f:
            folha = json.load(f)
    except FileNotFoundError:
        print(f"\n  Folha não encontrada: {args.arquivo}\n"
              f"  Rode antes:  python assets/populacao/coleta_servidores.py --atualizar\n",
              file=sys.stderr)
        return 1

    servidores = folha.get("servidores") or []
    print(f"\n  Folha   : {args.arquivo}")
    print(f"  Origem  : {folha.get('origem')}")
    print(f"  Competência: {folha.get('competencia')}  ({len(servidores)} servidores)")
    print(f"  Modo    : {'GRAVANDO' if args.aplicar else 'ENSAIO (nada é gravado)'}\n")

    if not args.aplicar:
        modelo = _arvore_real(folha)
        bloq = sum(1 for r in servidores if _bloqueado(r)[0])
        print(f"  Seriam criados ~{len(servidores)} usuários")
        print(f"  Dentre eles, {bloq} BLOQUEADOS (pensionista/inativo/eleito/demitido)")
        print(f"  Todos com senha provisória {SENHA_PROVISORIA} e troca + "
              f"telefone obrigatórios no 1º acesso")
        print(f"\n  Organograma: {len(modelo['secretarias'])} secretarias e "
              f"{sum(len(v) for v in modelo['secretarias'].values())} "
              f"departamentos seriam criados; as unidades de demonstração "
              f"que o portal não conhece seriam DESATIVADAS")
        print("\n  Rode com --aplicar para gravar.\n")
        return 0

    print("  --- Organograma ---")
    uni = sincronizar_unidades(folha, aplicar=True)
    print(f"  secretarias criadas : {uni['secretarias_criadas']}")
    print(f"  setores criados      : {uni['setores_criados']}")
    print(f"  reativadas           : {uni['reativadas']}")
    print(f"  desativadas (demo)   : {uni['desativadas']}")

    print("\n  --- Usuários ---")
    resumo = sincronizar(folha, aplicar=True)
    print(f"\n  criados      : {resumo['criados']}")
    print(f"  atualizados  : {resumo['atualizados']}")
    print(f"  inalterados  : {resumo['inalterados']}")
    print(f"  bloqueados   : {resumo['bloqueados']}")
    if resumo["desbloqueados"]:
        print(f"  desbloqueados: {resumo['desbloqueados']} "
              f"(voltaram a aparecer como ativos no portal)")
    if resumo["erros"]:
        print(f"\n  {len(resumo['erros'])} erro(s) — primeiros 10:")
        for e in resumo["erros"][:10]:
            print(f"    {e}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
