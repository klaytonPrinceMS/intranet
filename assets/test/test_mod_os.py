"""Ordens de Serviço (mod_os): quadro, coluna, cartão, número e linha do
tempo (28/09/2026).

EN: Covers the OS module through `bd_manipulador` only (no server, no
Playwright): boards (private and per unit), the standard columns, invites and
per-board roles, service orders (cards) with the board's sequential number,
concurrent number allocation, due-date overrun and the event timeline.

PT-BR: Cobre o módulo de ordens de serviço pelo `bd_manipulador` (sem servidor
e sem Playwright): o quadro (privado e de unidade), as colunas padrão, o
convite com papel, a ordem de serviço (o cartão) com o número sequencial do
quadro, a reserva de número sob criação concorrente, o atraso de prazo e a
linha do tempo.

O que o banco de verdade recebe e o que o teste devolve:
  - seis usuários de teste no cadastro de servidores (login `os_t00X`), com
    nome fictício;
  - os quadros criados aqui (com colunas, ordens de serviço, comentários,
    convites e a sequência de cada um);
  - UMA unidade do organograma da lista telefônica é ligada só durante o teste
    (o quadro de unidade só se mostra para servidor que o organograma
    reconhece) e volta ao valor original no fim.

TUDO é apagado no `finally` do `main()` — rodar duas vezes seguidas dá o
mesmo resultado.

Execute: .venv/bin/python assets/test/test_mod_os.py
"""
import os
import sys
import threading
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from mod_os import bd_manipulador as bd  # noqa: E402
from mod_gest_cad_usuario import bd_manipulador as gb  # noqa: E402
from mod_lista_telefonica import bd_manipulador as ltb  # noqa: E402

_OK = 0
_FALHAS = []

# Logins de teste: letra + número (nunca matrícula de 6 dígitos, AGENTS §8.3).
USUARIOS_TESTE = (
    ("os_t001", "Ana Beatriz Souza Rocha"),      # dona dos quadros
    ("os_t002", "Bruno Carvalho Lima"),          # convidado como leitor
    ("os_t003", "Camila Nogueira Prado"),        # convidada como editor
    ("os_t004", "Diego Henrique Sales"),         # convidado como administrador
    ("os_t005", "Elisa Maria Tavares Nunes"),    # de outra unidade
    ("os_t006", "Fabio Antunes Ribeiro"),        # da unidade do quadro
)
DONO, LEITOR, EDITOR, ADMIN_QUADRO, FORA_DA_UNIDADE, DA_UNIDADE = (
    login for login, _nome in USUARIOS_TESTE)

_QUADROS_DO_TESTE = []   # ids de quadro: apagados no fim

# id que o módulo não tem: serve para provar que a função recusa o que não
# existe. Não é matrícula de ninguém — é o número de uma linha que não está lá.
_ID_QUE_NAO_EXISTE = 99999


def check(cond, msg):
    """Conta uma verificação e imprime o resultado."""
    global _OK
    if cond:
        _OK += 1
        print(f"  ok   {msg}")
    else:
        _FALHAS.append(msg)
        print(f"  FALHA {msg}")


# ============ ajudas ============

def _quadro_novo(nome, dono=DONO, **kwargs):
    """Cria um quadro, registra na limpeza e devolve (ok, msg, quadro_id)."""
    try:
        ok, msg, quadro_id = bd.criar_quadro(dono, nome, **kwargs)
    except Exception as exc:
        return (False, f"excecao ao criar o quadro: {exc}", None)
    if quadro_id:
        _QUADROS_DO_TESTE.append(quadro_id)
    return (ok, msg, quadro_id)


def _convidar_e_aceitar(quadro_id, convidado, papel, ator=DONO):
    """Convida e o convidado aceita (o papel só vale depois do aceite)."""
    ok, msg = bd.convidar_usuario(quadro_id, convidado, papel, ator=ator)
    pendentes = [c for c in bd.listar_convites_pendentes(convidado)
                 if c["quadro_id"] == quadro_id and c["papel"] == papel]
    if not (ok and pendentes):
        return (False, msg)
    ok_resposta, msg_resposta, _nome = bd.responder_convite(
        pendentes[0]["id"], convidado, aceitar=True)
    if not ok_resposta:
        return (False, msg_resposta)
    return (True, msg)


def _colunas(quadro_id):
    """As colunas do quadro (dicionários: id, nome, ordem, conclusiva)."""
    return bd.listar_colunas(quadro_id)


def _coluna(quadro_id, nome):
    for coluna in _colunas(quadro_id):
        if coluna["nome"] == nome:
            return coluna
    return None


def _coluna_conclusiva(quadro_id):
    for coluna in _colunas(quadro_id):
        if coluna["conclusiva"]:
            return coluna
    return None


def _tipos_da_linha_do_tempo(ordem_id):
    return [evento["tipo"] for evento in bd.listar_eventos(ordem_id)]


def _data(dias):
    """Data no formato do módulo, `dias` no futuro (+) ou no passado (-)."""
    return (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")


def _ligar_unidade():
    """Liga uma unidade do organograma e devolve a função que restaura.

    O quadro de unidade só aparece para quem o organograma reconhece como
    servidor da unidade; o teste liga uma unidade existente, usa e devolve o
    valor original. Sem unidade no organograma, devolve (None, None, None) e o
    quadro de unidade é verificado só pela recusa de permissão.
    """
    try:
        unidades = ltb.listar_todas_unidades() or []
    except Exception:
        unidades = []
    if not unidades:
        return (None, None, None)
    unidade_id, nome, ativo_antes = unidades[0][0], unidades[0][1], unidades[0][6]

    def _gravar(valor):
        conn = ltb.get_connection()
        try:
            conn.execute("UPDATE tb_unidade SET ativo=? WHERE id=?",
                         (1 if valor else 0, int(unidade_id)))
            conn.commit()
        finally:
            conn.close()

    try:
        _gravar(1)
    except Exception:
        return (None, None, None)
    return (unidade_id, nome, lambda: _gravar(ativo_antes))


def _apagar_usuario(login):
    """Tira o usuário de teste do cadastro de servidores (nada fica)."""
    conn = None
    try:
        conn = gb.get_connection()
        for tabela in ("tb_telefone_usuario", "tb_acesso_usuario", "tb_usuarios"):
            conn.execute(f"DELETE FROM {tabela} WHERE user_nome=?", (login,))
        conn.commit()
    except Exception:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    try:
        from mod_intranet.autenticacao import marcar_trocar_senha
        marcar_trocar_senha(login, False)
    except Exception:
        pass


def _criar_usuarios():
    """Cria os usuários de teste; apaga os que já ficaram de uma corrida."""
    for login, _nome in USUARIOS_TESTE:
        _apagar_usuario(login)
    for login, nome in USUARIOS_TESTE:
        ok, msg = gb.criar_usuario("teste", login, "123456", perfil="comum",
                                   nome_completo=nome)
        if not ok:
            check(False, f"criou o usuário de teste {login} ({msg})")
            return
    check(True, f"criou os {len(USUARIOS_TESTE)} usuários de teste")
    # o servidor de teste não tem telefone nenhum: a pendência do 1º acesso não
    # é assunto deste módulo, e um cadastro pendente não pode atrapalhar a
    # busca de quem entra no quadro.
    for login, _nome in USUARIOS_TESTE:
        conn = gb.get_connection()
        try:
            conn.execute("UPDATE tb_usuarios SET telefone_pendente=0, "
                         "user_perfil='comum' WHERE user_nome=?", (login,))
            conn.commit()
        finally:
            conn.close()


def _limpar():
    """Apaga tudo que o teste criou: quadros (com tudo dentro) e usuários.

    VARRE TAMBÉM O QUE SOBROU DE RODADA ANTERIOR.

    A limpeza por id só alcança os quadros desta rodada, e a verificação final
    conta todos os quadros de teste que existem na tabela. Então uma rodada
    interrompida (Ctrl-C, timeout, reboot no meio) deixava sobras que fazem a
    PRÓXIMA rodada falhar sem ter feito nada de errado — e a segunda rodada
    falha com sobras da primeira, e assim por diante. Teste que não roda duas
    vezes seguidas não é teste de suíte, é teste de uma vez.

    Por isso a varredura é por PADRÃO DE NOME e por lista de login, e não por
    id. Ela é idempotente e não toca em nada que não seja deste teste.
    """
    for quadro_id in list(reversed(_QUADROS_DO_TESTE)):
        try:
            bd.excluir_quadro(quadro_id, ator=DONO, eh_admin_geral=True)
        except Exception:
            pass
    del _QUADROS_DO_TESTE[:]
    # Sobras de rodada anterior: varredura pelo DONO, que é exato e não
    # depende do nome do quadro. Todo quadro do teste pertence a um login de
    # teste, então "dono está na lista" é o critério — e quadro de pessoa
    # real nunca entra, porque ninguém real tem login `os_t...`.
    try:
        _logins = [u[0] for u in USUARIOS_TESTE] + [DONO]
        _marc = ",".join(["?"] * len(_logins))
        _conn = bd.get_connection()
        try:
            _sobras = [r[0] for r in _conn.execute(
                f"SELECT id FROM tb_os_quadro "
                f"WHERE dono_user_nome IN ({_marc})", tuple(_logins)).fetchall()]
        finally:
            _conn.close()
        for quadro_id in reversed(_sobras):
            try:
                bd.excluir_quadro(quadro_id, ator=DONO, eh_admin_geral=True)
            except Exception:
                pass
    except Exception:
        pass
    for login, _nome in USUARIOS_TESTE:
        _apagar_usuario(login)


def _contar(conexao, sql, logins):
    """`SELECT COUNT(*)` com a lista de logins de teste no `IN`."""
    marcadores = ",".join(["?"] * len(logins))
    linha = conexao.execute(f"{sql} IN ({marcadores})", tuple(logins)).fetchone()
    return int(linha[0] or 0) if linha else 0


# ============ 1) quadro: criação, colunas padrão e visibilidade ============

def teste_quadro_e_visibilidade():
    """O quadro nasce com as colunas do sistema e só aparece para quem é dele."""
    print("\n[quadro] criação, colunas padrão e visibilidade")
    ok, msg, qid = _quadro_novo("Obras Prediais 2026",
                               descricao="Reparos do prédio sede")
    check(ok, f"cria o quadro próprio ({msg})")
    if not ok:
        return
    quadro = bd.obter_quadro(qid)
    check(quadro is not None, "o quadro volta com os dados gravados")
    check(quadro["dono_user_nome"] == DONO, "o quadro é do servidor que o criou")
    check(quadro["visibilidade"] == "privado", "quadro novo é privado por padrão")
    check(quadro["prefixo_numero"] == "OBRAS",
          f"prefixo derivado do nome do quadro (veio {quadro['prefixo_numero']!r})")
    check(int(quadro["digitos_numero"]) == 4,
          f"número com 4 dígitos por padrão (veio {quadro['digitos_numero']})")

    # colunas padrão do sistema
    colunas = _colunas(qid)
    esperadas = bd.colunas_padrao()
    check([c["nome"] for c in colunas] == esperadas,
          f"as colunas padrão vêm criadas ({[c['nome'] for c in colunas]})")
    check([c["ordem"] for c in colunas] == list(range(1, len(colunas) + 1)),
          "as colunas vêm numeradas de 1 em 1, na ordem em que aparecem")
    check(len([c for c in colunas if c["conclusiva"]]) == 1,
          "o quadro tem UMA coluna de conclusão")
    check(colunas[-1]["conclusiva"] == 1,
          "a coluna de conclusão é a última do quadro")

    # a sequência do quadro começa zerada: o primeiro número é ...-0001
    check(bd.proximo_numero(qid) == 0,
          f"quadro novo começa a sequência em zero (veio {bd.proximo_numero(qid)})")
    check(bd.proximo_numero(qid) == 0,
          "consultar o próximo número não reserva nada")

    # quadro privado: só o dono (e o administrador geral) enxerga
    visiveis = [q["id"] for q in bd.listar_quadros_visiveis(LEITOR)]
    check(qid not in visiveis, "quadro privado NÃO aparece para outro servidor")
    check(bd.pode_ver(LEITOR, qid) is False,
          "e o outro servidor também não pode ver o quadro")
    check(bd.papel_no_quadro(LEITOR, qid) is None,
          "quem não foi convidado não tem papel no quadro")
    check(bd.papeis_do_quadro(qid) == {}, "ainda ninguém aceitou convite no quadro")
    check(qid in [q["id"] for q in bd.listar_quadros_visiveis(DONO)],
          "o dono enxerga o próprio quadro")
    check(bd.papel_no_quadro(DONO, qid) == "dono", "o papel do dono é 'dono'")
    check(bd.pode_ver(LEITOR, qid, eh_admin_geral=True) is True,
          "administrador geral enxerga qualquer quadro")

    # nome curto e quadro sem dono: recusado na porta
    check(bd.criar_quadro(DONO, "O")[0] is False, "recusa quadro de nome curto")
    check(bd.criar_quadro("", "Quadro sem dono")[0] is False,
          "recusa quadro sem dono identificado")

    # quadro de unidade: só quem administra cria, e ele exige a unidade
    unidade_id, unidade_nome, restaurar = _ligar_unidade()
    try:
        ok_neg, msg_neg, _ = bd.criar_quadro(
            DONO, "Quadro do Setor", visibilidade="unidade",
            unidade_id=unidade_id, unidade_nome=unidade_nome)
        check(ok_neg is False,
              f"quadro de unidade sem permissão é recusado ({msg_neg!r})")
        ok_neg, msg_neg, _ = bd.criar_quadro(
            DONO, "Quadro do Setor", visibilidade="unidade",
            unidade_id=unidade_id, pode_criar_unidade=True)
        check(ok_neg is False,
              f"quadro de unidade sem a unidade escolhida é recusado ({msg_neg!r})")

        if unidade_id is None:
            check(True, "sem unidade no organograma: quadro de unidade não é "
                        "verificado além da recusa de permissão")
            return
        ok_un, msg_un, quid = _quadro_novo(
            "Quadro do Setor", visibilidade="unidade", unidade_id=unidade_id,
            unidade_nome=unidade_nome, pode_criar_unidade=True)
        check(ok_un, f"o administrador cria o quadro da unidade ({msg_un})")
        if not ok_un:
            return
        check(bd.obter_quadro(quid)["visibilidade"] == "unidade",
              "o quadro da unidade fica gravado como de unidade")

        # o servidor da unidade enxerga; quem é de outro lugar, não
        gb.definir_dados_funcionais("teste", DA_UNIDADE, unidade=unidade_nome,
                                    lotacao=unidade_nome, cargo="Agente")
        gb.definir_dados_funcionais("teste", FORA_DA_UNIDADE,
                                    unidade="Unidade de Outro Setor",
                                    lotacao="Unidade de Outro Setor",
                                    cargo="Agente")
        visiveis_unidade = [q["id"] for q in bd.listar_quadros_visiveis(DA_UNIDADE)]
        check(quid in visiveis_unidade,
              "quadro de unidade aparece para o servidor da mesma unidade")
        check(bd.papel_no_quadro(DA_UNIDADE, quid) == "unidade",
              "o servidor da unidade tem o papel 'unidade' no quadro")
        check(bd.pode_editar(DA_UNIDADE, quid) is False,
              "e 'unidade' lê o quadro, mas não cria cartão nele")
        visiveis_fora = [q["id"]
                        for q in bd.listar_quadros_visiveis(FORA_DA_UNIDADE)]
        check(quid not in visiveis_fora,
              "quadro de unidade NÃO aparece para servidor de outra unidade")
        check(qid not in visiveis_unidade,
              "quadro privado continua escondido de quem só é da unidade")
    finally:
        if restaurar:
            try:
                restaurar()
            except Exception:
                pass


# ============ 2) convite e papel no quadro ============

def teste_convite_e_papeis():
    """O convite fica pendente até o convidado aceitar; o papel define o que
    ele faz no quadro."""
    print("\n[convite] pendente, aceite e o que cada papel pode fazer")
    nome_quadro = "Quadro de Convite"
    ok, msg, qid = _quadro_novo(nome_quadro)
    check(ok, f"cria o quadro do convite ({msg})")
    if not ok:
        return

    ok, msg = bd.convidar_usuario(qid, LEITOR, "leitor", ator=DONO)
    check(ok, f"convida o servidor cadastrado com papel de leitor ({msg})")
    convites = bd.listar_convites_quadro(qid)
    check(len(convites) == 1, f"o quadro tem 1 convite (veio {len(convites)})")
    check(convites[0]["status"] == "pendente", "o convite nasce pendente")
    check(convites[0]["papel"] == "leitor", "o convite guarda o papel pedido")
    check(convites[0]["convidado_por"] == DONO, "o convite guarda quem convidou")

    pendentes = bd.listar_convites_pendentes(LEITOR)
    check(len(pendentes) == 1, "o convidado vê o convite pendente")
    check(pendentes[0]["quadro_id"] == qid, "o pendente é deste quadro")
    check(pendentes[0]["quadro_nome"] == nome_quadro,
          f"o pendente traz o nome do quadro (veio {pendentes[0]['quadro_nome']!r})")
    check(pendentes[0]["status"] == "pendente", "o pendente segue pendente")
    check(bd.papeis_do_quadro(qid) == {},
          "convite pendente NÃO dá papel ainda (ninguém aceitou)")

    # recusas na porta
    check(bd.convidar_usuario(qid, DONO, "editor", ator=DONO)[0] is False,
          "o dono do quadro não se convida")
    check(bd.convidar_usuario(qid, EDITOR, "chefe", ator=DONO)[0] is False,
          "papel fora de leitor/editor/administrador é recusado")
    check(bd.convidar_usuario(qid, EDITOR, "leitor", ator=LEITOR)[0] is False,
          "quem não administra o quadro não convida")
    check(bd.convidar_usuario(qid, "", "leitor", ator=DONO)[0] is False,
          "convite sem servidor escolhido é recusado")

    # responder convite de outra pessoa
    ok_neg, msg_neg, _ = bd.responder_convite(convites[0]["id"], EDITOR,
                                              aceitar=True)
    check(ok_neg is False, f"convite de um só é do próprio convidado ({msg_neg!r})")

    # aceitar
    ok, msg, nome_vindo = bd.responder_convite(convites[0]["id"], LEITOR,
                                               aceitar=True)
    check(ok, f"o convidado aceita o convite ({msg})")
    check(nome_vindo == nome_quadro,
          f"o aceite devolve o nome do quadro (veio {nome_vindo!r})")
    check(bd.listar_convites_pendentes(LEITOR) == [],
          "convite aceito sai da lista de pendentes")
    check(bd.listar_convites_quadro(qid)[0]["status"] == "aceito",
          "o quadro registra o convite como aceito")
    check(bd.papel_no_quadro(LEITOR, qid) == "leitor",
          f"o papel do convidado é o do convite (veio "
          f"{bd.papel_no_quadro(LEITOR, qid)!r})")
    check(qid in [q["id"] for q in bd.listar_quadros_visiveis(LEITOR)],
          "quem aceitou enxerga o quadro")
    ok_neg, msg_neg, _ = bd.responder_convite(convites[0]["id"], LEITOR,
                                              aceitar=True)
    check(ok_neg is False, f"convite já respondido não se responde duas vezes "
                           f"({msg_neg!r})")

    # ---- o que cada papel pode fazer no mesmo quadro ----
    coluna = _colunas(qid)[0]["id"]
    check(bd.criar_ordem_servico(qid, coluna, "Cartão de teste do dono",
                                 ator=DONO)[0] is True,
          "o dono cria ordem de serviço")
    ok, msg, _num = bd.criar_ordem_servico(qid, coluna, "Cartão do leitor",
                                           ator=LEITOR)
    check(ok is False, f"leitor NÃO cria ordem de serviço ({msg!r})")
    ok, msg = bd.criar_coluna(qid, "Coluna do leitor", ator=LEITOR)
    check(ok is False, f"leitor NÃO gerencia coluna ({msg!r})")
    ok, msg = bd.definir_formato_numero(qid, prefixo="INVADIDO", ator=LEITOR)
    check(ok is False, f"leitor NÃO muda o formato do número ({msg!r})")
    check(bd.obter_quadro(qid)["prefixo_numero"] != "INVADIDO",
          "e o prefixo do quadro continua o que era")

    ok, msg = _convidar_e_aceitar(qid, EDITOR, "editor")
    check(ok, f"convida e aceita o editor ({msg})")
    ok, msg, num_editor = bd.criar_ordem_servico(qid, coluna,
                                                "Cartão do editor", ator=EDITOR)
    check(ok, f"editor cria ordem de serviço ({msg})")
    check(bool(num_editor), "e a criação devolve o número gerado")
    ok, msg = bd.criar_coluna(qid, "Urgente", ator=EDITOR)
    check(ok is False, f"editor NÃO gerencia coluna ({msg!r})")
    check(bd.pode_editar(EDITOR, qid) is True, "editor pode editar o quadro")

    ok, msg = _convidar_e_aceitar(qid, ADMIN_QUADRO, "administrador")
    check(ok, f"convida e aceita o administrador do quadro ({msg})")
    ok, msg = bd.criar_coluna(qid, "Urgente", ator=ADMIN_QUADRO)
    check(ok, f"administrador gerencia coluna ({msg})")
    check(bd.pode_gerenciar(ADMIN_QUADRO, qid) is True,
          "administrador pode gerenciar o quadro")
    check(bd.pode_gerenciar(EDITOR, qid) is False,
          "editor não gerencia o quadro")
    check(bd.pode_gerenciar(FORA_DA_UNIDADE, qid) is False,
          "servidor de fora não gerencia o quadro")

    # recusa de movimento e de comentário para quem só lê
    ordem = bd.listar_ordens(qid, coluna_id=coluna)[0]
    ok, msg = bd.mover_ordem(ordem["id"], _colunas(qid)[1]["id"], ator=LEITOR)
    check(ok is False, f"leitor NÃO move ordem de serviço ({msg!r})")
    ok, msg = bd.comentar_ordem(ordem["id"], "Leitor escreve na linha do tempo.",
                                ator=LEITOR)
    check(ok is False, f"leitor NÃO comenta na ordem de serviço ({msg!r})")
    check(len(bd.listar_comentarios(ordem["id"])) == 0,
          "e o comentário do leitor não ficou gravado")
    ok, msg = bd.comentar_ordem(ordem["id"], "Servidor de fora comenta.",
                                ator=FORA_DA_UNIDADE)
    check(ok is False,
          f"quem nem enxerga o quadro NÃO comenta ({msg!r})")
    ok, msg = bd.comentar_ordem(ordem["id"], "O editor escreve aqui.",
                                ator=EDITOR)
    check(ok, f"editor comenta na ordem de serviço ({msg})")
    ok, msg = bd.atualizar_ordem(ordem["id"], {"prioridade": "urgente"},
                                 ator=LEITOR)
    check(ok is False, f"leitor NÃO edita a ordem de serviço ({msg!r})")
    ok, msg = bd.arquivar_ordem(ordem["id"], True, ator=LEITOR)
    check(ok is False, f"leitor NÃO arquiva a ordem de serviço ({msg!r})")
    ok, msg = bd.arquivar_quadro(qid, True, ator=LEITOR)
    check(ok is False, f"leitor NÃO arquiva o quadro ({msg!r})")
    ok, msg = bd.excluir_quadro(qid, ator=LEITOR)
    check(ok is False, f"leitor NÃO exclui o quadro ({msg!r})")
    check(bd.obter_quadro(qid) is not None, "o quadro continua no lugar")
    check(bd.comentar_ordem(ordem["id"], "Administrador comenta.",
                            ator=ADMIN_QUADRO)[0] is True,
          "administrador do quadro comenta na ordem de serviço")
    ok, msg = bd.comentar_ordem(_ID_QUE_NAO_EXISTE, "Ordem inexistente",
                                ator=DONO)
    check(ok is False, f"comentário em ordem de serviço inexistente é recusado "
                       f"({msg!r})")
    ok, msg, _nome = bd.responder_convite(_ID_QUE_NAO_EXISTE, LEITOR, aceitar=True)
    check(ok is False, f"responder convite inexistente é recusado ({msg!r})")

    # renovar o papel de quem já entrou não cria convite novo
    antes = len(bd.listar_convites_quadro(qid))
    ok, msg = bd.convidar_usuario(qid, LEITOR, "editor", ator=DONO)
    check(ok, f"convite de quem já entrou renova o papel ({msg})")
    check(len(bd.listar_convites_quadro(qid)) == antes,
          "e não cria um segundo convite")
    check(bd.papel_no_quadro(LEITOR, qid) == "editor",
          "o papel do convidado passa a ser o novo")
    bd.convidar_usuario(qid, LEITOR, "leitor", ator=DONO)  # volta ao leitor

    # convidar usuário inexistente: o módulo avisa, não quebra
    ok, msg = bd.convidar_usuario(qid, "os_t999", "leitor", ator=DONO)
    check(ok, f"convite de servidor inexistente não derruba o quadro ({msg})")


# ============ 3) colunas, cartão e linha do tempo ============

def teste_colunas_e_cartoes():
    """Coluna nova, número sequencial, movimento, comentário, conclusão e
    reabertura."""
    print("\n[colunas e cartões] número, movimento, conclusão e linha do tempo")
    ok, msg, qid = _quadro_novo("Quadro de Ordens")
    check(ok, f"cria o quadro das ordens de serviço ({msg})")
    if not ok:
        return
    colunas = _colunas(qid)
    aberta, andamento, concluida = colunas[0], colunas[1], colunas[-1]
    prefixo = bd.obter_quadro(qid)["prefixo_numero"]

    # ---- coluna nova ----
    ok, msg = bd.criar_coluna(qid, "Urgente", cor="#EF6C00", ator=DONO)
    check(ok, f"cria coluna nova ({msg})")
    check(len(_colunas(qid)) == len(colunas) + 1, "a coluna nova entra no quadro")
    check(bd.criar_coluna(qid, "Urgente", ator=DONO)[0] is False,
          "coluna repetida é recusada")
    check(bd.criar_coluna(qid, "  ", ator=DONO)[0] is False,
          "coluna sem nome é recusada")
    urgente = _coluna(qid, "Urgente")
    check(urgente is not None and urgente["ordem"] == len(colunas) + 1,
          "a coluna nova entra no fim, com a posição certa")
    # uma coluna de conclusão por quadro: a nova marca e a antiga perde a marca
    ok, msg = bd.criar_coluna(qid, "Encerrada", ator=DONO, conclusiva=True)
    check(ok, f"cria outra coluna de conclusão ({msg})")
    marcadas = [c["nome"] for c in _colunas(qid) if c["conclusiva"]]
    check(marcadas == ["Encerrada"],
          f"só a última coluna de conclusão vale (veio {marcadas})")
    concluida = _coluna_conclusiva(qid)
    check(concluida["nome"] == "Encerrada",
          "a coluna de conclusão do quadro passa a ser a nova")

    # o editor entra no quadro: quem mexe no cartão depois é ele
    ok, msg = _convidar_e_aceitar(qid, EDITOR, "editor")
    check(ok, f"convida o editor para o quadro das ordens ({msg})")

    # ---- número sequencial a partir de 1 ----
    numeros = []
    for indice in range(3):
        ok_c, msg_c, num = bd.criar_ordem_servico(
            qid, aberta["id"], f"Reparo numero {indice + 1}",
            descricao="Chamado docitizen", prioridade="alta", ator=DONO)
        check(ok_c, f"cria a ordem de serviço {indice + 1} ({msg_c})")
        numeros.append(num)
    check(numeros == [f"{prefixo}-0001", f"{prefixo}-0002", f"{prefixo}-0003"],
          f"os números saem consecutivos, de 0001 a 0003 (veio {numeros})")
    check(bd.proximo_numero(qid) == 3,
          f"a sequência do quadro fica em 3 (veio {bd.proximo_numero(qid)})")

    ordens = bd.listar_ordens(qid, coluna_id=aberta["id"])
    check(len(ordens) == 3, f"as 3 ordens estão na coluna (veio {len(ordens)})")
    check(all(isinstance(o, dict) and "id" in o for o in ordens),
          "a listagem devolve dicionário com o id da ordem de serviço")
    check([o["ordem"] for o in ordens] == [1, 2, 3],
          "as ordens da coluna ficam posicionadas de 1 em 1")
    check(ordens[0]["coluna_nome"] == aberta["nome"],
          "a listagem traz o nome da coluna de cada ordem")
    check(ordens[0]["prioridade"] == "alta", "a prioridade gravada volta na leitura")

    # ---- recusas na criação do cartão ----
    check(bd.criar_ordem_servico(qid, aberta["id"], "ab", ator=DONO)[0] is False,
          "título de menos de 3 letras é recusado")
    check(bd.criar_ordem_servico(qid, aberta["id"], "", ator=DONO)[0] is False,
          "ordem de serviço sem título é recusada")
    check(bd.criar_ordem_servico(qid, _ID_QUE_NAO_EXISTE, "Cartao em coluna",
                                 ator=DONO)[0] is False,
          "cartão em coluna de outro quadro é recusado")
    # número não pode ser furado por uma recusa
    check(bd.proximo_numero(qid) == 3,
          f"recusa não queima número do quadro (ficou {bd.proximo_numero(qid)})")

    # ---- prazo e atraso ----
    ok, msg, num_atraso = bd.criar_ordem_servico(
        qid, aberta["id"], "Vazamento na cozinha", data_vencimento=_data(-3),
        rotulos="hidraulica, urgente", ator=DONO)
    check(ok, f"cria ordem de serviço com prazo vencido ({msg})")
    atraso = bd.obter_ordem([o["id"] for o in bd.listar_ordens(qid)
                             if o["numero"] == num_atraso][0])
    check(atraso["data_vencimento"] == _data(-3),
          f"o prazo é uma data, sem hora (veio {atraso['data_vencimento']!r})")
    check(atraso["rotulos"] == "hidraulica, urgente",
          f"os rótulos são gravados limpos (veio {atraso['rotulos']!r})")
    marcadas = [o["id"] for o in bd.listar_ordens(qid) if o["atrasada"]]
    check([o["id"] for o in bd.listar_ordens(qid, atraso=True)] == marcadas,
          "a listagem com atraso traz só as ordens vencidas")
    check(len(marcadas) == 1, f"a ordem vencida aparece como atrasada "
                             f"(veio {len(marcadas)})")
    atrasada_id = marcadas[0]

    # ---- responsável, comentário, movimento, conclusão e reabertura ----
    ok, msg, _num = bd.criar_ordem_servico(
        qid, aberta["id"], "Troca de responsavel", ator=DONO)
    check(ok, f"cria a ordem que vai percorrer a linha do tempo ({msg})")
    alvo = [o for o in bd.listar_ordens(qid)
            if o["titulo"] == "Troca de responsavel"][0]
    oid = alvo["id"]

    ok, msg = bd.atualizar_ordem(oid, {"responsavel_user_nome": EDITOR},
                                 ator=DONO)
    check(ok, f"define o responsável da ordem de serviço ({msg})")
    check(bd.obter_ordem(oid)["responsavel_user_nome"] == EDITOR,
          "o responsável fica gravado")
    ok, msg = bd.comentar_ordem(oid, "Equipechedule para amanha", ator=EDITOR)
    check(ok, f"comenta na ordem de serviço ({msg})")
    comentarios = bd.listar_comentarios(oid)
    check(len(comentarios) == 1, f"o comentário fica gravado (veio "
                                 f"{len(comentarios)})")
    check(comentarios[0]["autor_user_nome"] == EDITOR,
          "o comentário guarda o autor")
    check(bd.comentar_ordem(oid, "x", ator=EDITOR)[0] is False,
          "comentário em branco é recusado")

    ok, msg = bd.mover_ordem(oid, andamento["id"], ator=EDITOR)
    check(ok, f"move o cartão para outra coluna ({msg})")
    check(bd.obter_ordem(oid)["coluna_id"] == andamento["id"],
          "a ordem de serviço passou a estar na coluna de destino")

    ok, msg = bd.mover_ordem(oid, concluida["id"], ator=EDITOR)
    check(ok, f"move o cartão para a coluna de conclusão ({msg})")
    depois = bd.obter_ordem(oid)
    check(bool(depois["concluido_em"]),
          f"chegar na coluna de conclusão marca concluído "
          f"(veio {depois['concluido_em']!r})")
    ok, msg = bd.mover_ordem(oid, aberta["id"], ator=EDITOR)
    check(ok, f"reabre a ordem de serviço tirando da conclusão ({msg})")
    check(bd.obter_ordem(oid)["concluido_em"] == "",
          "reabrir limpa a marca de concluído")

    # ---- linha do tempo: criação, movimento, responsável, comentário,
    #      conclusão e reabertura, cada uma com autor e data ----
    tipos = _tipos_da_linha_do_tempo(oid)
    check(tipos == ["criacao", "responsavel", "comentario", "movimento",
                    "movimento", "conclusao", "movimento", "reabertura"],
          f"a linha do tempo guarda tudo na ordem (veio {tipos})")
    eventos = bd.listar_eventos(oid)
    check(all(e["autor_user_nome"] for e in eventos),
          "todo evento da linha do tempo tem autor")
    check(all(e["criado_em"] for e in eventos),
          "todo evento da linha do tempo tem data")
    check(eventos[0]["autor_user_nome"] == DONO,
          "a criação foi registrada em nome de quem abriu o cartão")
    check(any(e["tipo"] == "responsavel" and e["autor_user_nome"] == DONO
              for e in eventos),
          "a troca de responsável tem autor e evento próprio")
    check(any(e["tipo"] == "comentario" and e["autor_user_nome"] == EDITOR
              for e in eventos),
          "o comentário também entra na linha do tempo, com o autor")
    check(all(e["texto"] for e in eventos),
          "todo evento da linha do tempo tem o que aconteceu escrito")

    # linha do tempo de uma ordem que ninguém mexeu: só a criação
    sossego = [o for o in bd.listar_ordens(qid)
               if o["titulo"] == "Reparo numero 1"][0]
    check(_tipos_da_linha_do_tempo(sossego["id"]) == ["criacao"],
          "ordem parada tem só o evento de criação na linha do tempo")

    # concluir uma ordem atrasada tira ela do atraso
    ok, msg = bd.mover_ordem(atrasada_id, concluida["id"], ator=DONO)
    check(ok, f"conclui a ordem de serviço atrasada ({msg})")
    check(bd.obter_ordem(atrasada_id)["concluido_em"] != "",
          "a ordem atrasada ficou concluída")
    check(atrasada_id not in [o["id"] for o in bd.listar_ordens(qid, atraso=True)],
          "ordem concluída NAO entra mais na lista de atrasadas")


# ============ 4) número sob criação concorrente ============

def teste_numero_concorrente():
    """N threads criando cartão ao mesmo tempo: número nenhum se repete."""
    print("\n[concorrência] N cartões criados ao mesmo tempo no mesmo quadro")
    ok, msg, qid = _quadro_novo("Quadro Concorrente")
    check(ok, f"cria o quadro do teste concorrente ({msg})")
    if not ok:
        return
    coluna_id = _colunas(qid)[0]["id"]
    total = 12
    barreira = threading.Barrier(total)
    resultados = []
    erros = []
    trava = threading.Lock()

    def _criar(indice):
        try:
            barreira.wait(timeout=30)
            retorno = bd.criar_ordem_servico(
                qid, coluna_id, f"Cartao concorrente {indice:02d}", ator=DONO)
        except Exception as exc:
            with trava:
                erros.append(f"thread {indice}: {exc}")
            return
        with trava:
            resultados.append(retorno)

    threads = [threading.Thread(target=_criar, args=(i,)) for i in range(total)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    check(not erros, f"nenhuma thread estourou exceção ({erros[:2]})")
    check(len(resultados) == total,
          f"as {total} threads responderam (veio {len(resultados)})")
    criadas = [retorno for retorno in resultados if retorno and retorno[0]]
    perdidas = [retorno for retorno in resultados if not (retorno and retorno[0])]
    check(not perdidas,
          f"nenhum cartão foi recusado sob concorrência (perdeu: {perdidas[:2]})")
    numeros = [retorno[2] for retorno in criadas]
    check(len(set(numeros)) == len(numeros),
          f"nenhum número se repete (veio {len(set(numeros))} distintos de "
          f"{len(numeros)})")
    prefixo = bd.obter_quadro(qid)["prefixo_numero"]
    esperados = [f"{prefixo}-{n:04d}" for n in range(1, len(numeros) + 1)]
    check(sorted(numeros) == esperados,
          f"os números saem em sequência, sem buraco e sem repetição "
          f"(veio {sorted(numeros)})")
    gravadas = bd.listar_ordens(qid)
    sequenciais = sorted(o["numero_sequencial"] for o in gravadas)
    check(len(set(sequenciais)) == len(sequenciais) and
          len(gravadas) == len(numeros),
          f"o quadro guardou {len(numeros)} ordens distintas "
          f"(veio {len(gravadas)})")
    check(bd.proximo_numero(qid) == len(numeros),
          f"a sequência do quadro parou em {len(numeros)} "
          f"(veio {bd.proximo_numero(qid)})")

    # a mesma prova pelo caminho de dentro da transação: reserva e rollback
    antes = bd.proximo_numero(qid)
    reservas = []
    for _tentativa in range(2):
        conn = bd.get_connection()
        try:
            reservas.append(bd.alocar_numero_na_conexao(conn, qid))
            conn.rollback()
        finally:
            conn.close()
    check(reservas[0] == reservas[1] == antes + 1,
          f"reserva desfeita devolve o mesmo número ({reservas})")
    check(bd.proximo_numero(qid) == antes,
          f"o rollback da reserva não queima número (ficou "
          f"{bd.proximo_numero(qid)}, era {antes})")
    ok, msg, numero_final = bd.criar_ordem_servico(
        qid, coluna_id, "Cartao depois do rollback", ator=DONO)
    check(ok and numero_final == f"{prefixo}-{antes + 1:04d}",
          f"o próximo cartão usa o número devolvido ({numero_final})")


# ============ 5) o número sequencial: formato, troca e independência ============

def teste_numero_sequencial():
    """Formato PREFIXO-0001, troca de formato só para o que vem depois."""
    print("\n[número] formato, troca de formato e sequência por quadro")
    check(bd.montar_numero("OBRAS", 1, 4) == "OBRAS-0001",
          "monta o número como PREFIXO-0001")
    check(bd.montar_numero("os", 42, 6) == "OS-000042",
          "prefixo minúsculo sai em maiúsculo, com os dígitos pedidos")
    check(bd.montar_numero("", 7, 4) == "OS-0007",
          "quadro sem prefixo usa OS")
    check(bd.montar_numero("OBRAS", 1, 99) == "OBRAS-00000001",
          f"o número respeita o limite de dígitos (veio "
          f"{bd.montar_numero('OBRAS', 1, 99)!r})")

    # validar_digitos: aceita de 3 a 8, limita fora disso
    for entrada, esperado in ((3, 3), (8, 8), (5, 5), ("6", 6),
                              (2, 3), (1, 3), (0, 3), (-4, 3),
                              (9, 8), (99, 8), ("lixo", 4), (None, 4)):
        obtido = bd.validar_digitos(entrada)
        check(obtido == esperado,
              f"validar_digitos({entrada!r}) = {esperado} (veio {obtido})")

    # prefixo derivado do nome: primeira palavra, até 6 caracteres
    ok, msg, qid = _quadro_novo("Manutencao_predial do sede")
    check(ok, f"cria o quadro do formato do número ({msg})")
    if not ok:
        return
    check(bd.obter_quadro(qid)["prefixo_numero"] == "MANUTE",
          f"o prefixo sai da primeira palavra do nome, até 6 letras "
          f"(veio {bd.obter_quadro(qid)['prefixo_numero']!r})")
    coluna_id = _colunas(qid)[0]["id"]
    ok, msg, num_antigo = bd.criar_ordem_servico(qid, coluna_id,
                                                 "Ordem antes da troca",
                                                 ator=DONO)
    check(ok and num_antigo == "MANUTE-0001",
          f"a primeira ordem do quadro sai MANUTE-0001 (veio {num_antigo})")

    # trocar o formato NÃO renumera o que já existe
    ok, msg = bd.definir_formato_numero(qid, prefixo="Chamado SP", digitos=6,
                                        ator=DONO)
    check(ok, f"troca o formato do número do quadro ({msg})")
    check(bd.obter_quadro(qid)["prefixo_numero"] == "CHAMADOSP",
          f"o prefixo é normalizado e guardado (veio "
          f"{bd.obter_quadro(qid)['prefixo_numero']!r})")
    digitos = bd.obter_quadro(qid)["digitos_numero"]
    check(int(digitos) == 6,
          f"o quadro passa a mostrar 6 dígitos no número (veio {digitos!r})")
    ordem_antiga = bd.listar_ordens(qid)[0]
    check(ordem_antiga["numero"] == "MANUTE-0001",
          f"a ordem ANTIGA mantém o número que já tinha "
          f"(veio {ordem_antiga['numero']!r})")
    ok, msg, num_novo = bd.criar_ordem_servico(qid, coluna_id,
                                              "Ordem depois da troca",
                                              ator=DONO)
    check(ok and num_novo == "CHAMADOSP-000002",
          f"a ordem NOVA usa o formato novo, sem renumerar a antiga "
          f"(veio {num_novo})")
    check(bd.definir_formato_numero(_ID_QUE_NAO_EXISTE, prefixo="X",
                                   ator=DONO)[0] is False,
          "trocar o formato de quadro inexistente é recusado")
    check(bd.definir_formato_numero(qid, prefixo="MANUTE",
                                    ator=FORA_DA_UNIDADE)[0] is False,
          "servidor de fora NÃO troca o formato do número de quadro alheio")
    check(bd.obter_quadro(qid)["prefixo_numero"] == "CHAMADOSP",
          "e o formato do quadro continua o que o administrador deixou")

    # dois quadros: sequências independentes
    ok, msg, outro_id = _quadro_novo("Quadro Irmao")
    check(ok, f"cria um segundo quadro com o mesmo nome base ({msg})")
    if not ok:
        return
    check(bd.obter_quadro(outro_id)["prefixo_numero"] == "QUADRO",
          f"o quadro irmão tem prefixo próprio (veio "
          f"{bd.obter_quadro(outro_id)['prefixo_numero']!r})")
    check(bd.proximo_numero(outro_id) == 0,
          "a sequência do quadro irmão começa zerada")
    coluna_irmao = _colunas(outro_id)[0]["id"]
    ok, msg, num_irmao = bd.criar_ordem_servico(outro_id, coluna_irmao,
                                                "Ordem do quadro irmao",
                                                ator=DONO)
    check(ok and num_irmao == "QUADRO-0001",
          f"o quadro irmão começa no 0001, independente do primeiro "
          f"(veio {num_irmao})")
    check(bd.proximo_numero(qid) == 2 and bd.proximo_numero(outro_id) == 1,
          f"cada quadro conta por conta própria "
          f"({bd.proximo_numero(qid)} e {bd.proximo_numero(outro_id)})")


# ============ 6) prazo vencido ============

def teste_atraso():
    """Prazo vencido e não concluído aparece como atraso para quem tem o
    cartão."""
    print("\n[atraso] prazo vencido e não concluído")
    ok, msg, qid = _quadro_novo("Quadro de Prazos")
    check(ok, f"cria o quadro de prazos ({msg})")
    if not ok:
        return
    ok, msg = _convidar_e_aceitar(qid, LEITOR, "leitor")
    check(ok, f"o leitor entra no quadro de prazos ({msg})")
    coluna_id = _colunas(qid)[0]["id"]
    vencida = _colunas(qid)[-1]["id"]

    ok, msg, num_vencida = bd.criar_ordem_servico(
        qid, coluna_id, "Poda de arvore", data_vencimento=_data(-2),
        responsavel_user_nome=LEITOR, ator=DONO)
    check(ok, f"cria ordem de serviço com prazo vencido ({msg})")
    ok, msg, num_no_prazo = bd.criar_ordem_servico(
        qid, coluna_id, "Limpeza da praca", data_vencimento=_data(7),
        responsavel_user_nome=LEITOR, ator=DONO)
    check(ok, f"cria ordem de serviço com prazo a vencer ({msg})")
    ok, msg, num_sem_prazo = bd.criar_ordem_servico(
        qid, coluna_id, "Ordem sem prazo", responsavel_user_nome=LEITOR,
        ator=DONO)
    check(ok, f"cria ordem de serviço sem prazo ({msg})")

    atrasadas = [o["numero"] for o in bd.listar_atrasadas(LEITOR)]
    check(atrasadas == [num_vencida],
          f"só a vencida e não concluída aparece como atraso (veio {atrasadas})")
    atrasadas_dono = [o["numero"] for o in bd.listar_atrasadas(DONO)]
    check(num_vencida in atrasadas_dono,
          "quem abriu o cartão também enxerga o atraso dele")
    check([o["numero"] for o in bd.listar_atrasadas(FORA_DA_UNIDADE)] == [],
          "servidor que não vê o quadro não tem atraso nenhum")
    check([o["numero"] for o in bd.listar_minhas_ordens(LEITOR)] ==
          sorted([num_vencida, num_no_prazo, num_sem_prazo]),
          "'meus cartões' traz as ordens de que o servidor é responsável")

    # com prazo no futuro, a mesma ordem não está atrasada
    prorrogada = [o for o in bd.listar_ordens(qid)
                  if o["numero"] == num_vencida][0]
    ok, msg = bd.atualizar_ordem(prorrogada["id"],
                                 {"data_vencimento": _data(10)}, ator=DONO)
    check(ok, f"prorroga o prazo da ordem de serviço ({msg})")
    check([o["numero"] for o in bd.listar_atrasadas(LEITOR)] == [],
          "prazo prorrogado tira a ordem da lista de atrasadas")
    tipos = _tipos_da_linha_do_tempo(prorrogada["id"])
    check("edicao" in tipos, f"a troca de prazo entra na linha do tempo ({tipos})")

    # prazo atrasado e concluído não é atraso
    ok, msg, num_outra = bd.criar_ordem_servico(
        qid, coluna_id, "Reparo ja feito", data_vencimento=_data(-5),
        responsavel_user_nome=LEITOR, ator=DONO)
    check(ok, f"cria outra ordem vencida ({msg})")
    reparo = [o for o in bd.listar_ordens(qid) if o["numero"] == num_outra][0]
    bd.mover_ordem(reparo["id"], vencida, ator=DONO)
    check([o["numero"] for o in bd.listar_atrasadas(LEITOR)] == [],
          "ordem vencida mas concluída NAO é atraso")
    # concluí-la no fim não é o mesmo que estar concluída: o prazo ainda vence
    bd.mover_ordem(reparo["id"], coluna_id, ator=DONO)
    check([o["numero"] for o in bd.listar_atrasadas(LEITOR)] == [num_outra],
          "reaberta, a ordem vencida volta para a lista de atrasadas")


# ============ 7) limpeza ============

def teste_limpeza():
    """Depois do teste, o banco não tem quadro, cartão nem usuário de teste."""
    print("\n[limpeza] nada do teste sobrou no banco")
    logins = tuple(login for login, _nome in USUARIOS_TESTE)
    conexao = None
    try:
        conexao = bd.get_connection()
        quadros = _contar(conexao, "SELECT COUNT(*) FROM tb_os_quadro "
                                  "WHERE dono_user_nome", logins)
        convites = _contar(conexao, "SELECT COUNT(*) FROM tb_os_convite "
                                   "WHERE convidado_user_nome", logins)
        convites_convidador = _contar(conexao, "SELECT COUNT(*) FROM tb_os_convite "
                                              "WHERE convidado_por", logins)
        orfas = 0
        for tabela in ("tb_os_evento", "tb_os_comentario", "tb_os_ordem",
                       "tb_os_convite", "tb_os_coluna", "tb_os_sequencia"):
            linha = conexao.execute(
                f"SELECT COUNT(*) FROM {tabela} WHERE quadro_id NOT IN "
                "(SELECT id FROM tb_os_quadro)").fetchone()
            orfas += int(linha[0] or 0) if linha else 0
    finally:
        if conexao is not None:
            conexao.close()
    check(quadros == 0, f"nenhum quadro de teste ficou no banco (veio {quadros})")
    check(convites == 0 and convites_convidador == 0,
          f"nenhum convite de teste ficou no banco (veio {convites} / "
          f"{convites_convidador})")
    check(orfas == 0,
          f"nenhuma coluna, cartão, comentário, evento ou contador órfão "
          f"(veio {orfas})")

    conexao = None
    try:
        conexao = gb.get_connection()
        usuarios = _contar(conexao, "SELECT COUNT(*) FROM tb_usuarios "
                                   "WHERE user_nome", logins)
        acessos = _contar(conexao, "SELECT COUNT(*) FROM tb_acesso_usuario "
                                   "WHERE user_nome", logins)
        telefones = _contar(conexao, "SELECT COUNT(*) FROM tb_telefone_usuario "
                                     "WHERE user_nome", logins)
    finally:
        if conexao is not None:
            conexao.close()
    check(usuarios == 0,
          f"nenhum usuário de teste ficou no cadastro (veio {usuarios})")
    check(acessos == 0 and telefones == 0,
          f"nem o vínculo de acesso ficou (veio {acessos} / {telefones})")


def main():
    print("\n=== ordens de serviço: quadro, cartão, número e linha do tempo ===")
    try:
        bd.init_db()
        # Varredura ANTES de criar qualquer coisa.
        #
        # A verificação de limpeza conta todos os quadros/convites de teste que
        # existem na tabela — inclusive os que sobraram de uma rodada
        # interrompida. Sem varrer no começo, o resultado alterna: a rodada que
        # segue a interrupção falha contando a sujeira anterior, e a seguinte
        # passa. Teste que passa só na segunda vez não serve para a suíte, que
        # roda cada script uma vez por rodada e não pode depender de o banco
        # estar limpio de uma execução anterior.
        _limpar()
        _criar_usuarios()
        teste_quadro_e_visibilidade()
        teste_convite_e_papeis()
        teste_colunas_e_cartoes()
        teste_numero_concorrente()
        teste_numero_sequencial()
        teste_atraso()
    except Exception as e:
        import traceback
        traceback.print_exc()
        _FALHAS.append(f"excecao: {e}")
    finally:
        _limpar()
        try:
            teste_limpeza()
        except Exception as e:
            import traceback
            traceback.print_exc()
            _FALHAS.append(f"excecao na limpeza: {e}")
    print(f"\n{_OK} ok, {len(_FALHAS)} falha(s)")
    for falha in _FALHAS:
        print(f"  - {falha}")
    return 1 if _FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
