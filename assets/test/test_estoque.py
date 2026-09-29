"""Estoque (mod_estoque): almoxarifado, entrada, transferência, devolução,
item em uso, item parado, pedido de recolhimento, tarefa de depósito e
numeração (28/09/2026).

EN: Covers the Stock module through `bd_manipulador` only (no server, no
Playwright): the central warehouse and the decentralised one per secretariat,
entry into the central, transfer between warehouses, the refusal of a transfer
bigger than the available stock, devolution to the central, delivery to a room
(becoming "in use"), the "standing still" indicator, the collection request
answered by the central, the deposit task with its invited servers and who is
handling it, the sequential numbers of item and document (distinct, returned on
rollback) and the per-role permissions.

PT-BR: Cobre o módulo de estoque pelo `bd_manipulador` (sem servidor e sem
Playwright): o estoque central e o almoxarifado descentralizado por secretaria,
a entrada no central, a transferência entre almoxarifados, a recusa da
transferência maior que o disponível, a devolução ao central, a entrega para
uma sala (vira "em uso"), o indicador de item parado, o pedido de recolhimento
atendido pelo central, a tarefa de depósito com os servidores chamados e quem
está atendendo, os números sequenciais de item e de documento (distintos,
devolvidos no rollback) e as permissões por papel.

O que o banco de verdade recebe e o que o teste devolve:
  - seis usuários de teste no cadastro de servidores (login `est_t00X`), com
    nome fictício;
  - os almoxarifados, itens, saldos, documentos, movimentos, entregas,
    recolhimentos, tarefas, convites e vínculos criados aqui;
  - o estoque central NÃO é apagado (é fixo): o que o teste faz com ele é
    devolver tudo ao saldo zero, para rodar duas vezes seguidas dar o mesmo.

TUDO é apagado no `finally` do `main()` — rodar duas vezes seguidas dá o
mesmo resultado.

Execute: .venv/bin/python assets/test/test_estoque.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from mod_estoque import bd_manipulador as est  # noqa: E402
from mod_gest_cad_usuario import bd_manipulador as gb  # noqa: E402

_OK = 0
_FALHAS = []

# Logins de teste: letra + número (nunca matrícula de 6 dígitos, AGENTS §8.3).
USUARIOS_TESTE = (
    ("est_t001", "Ana Beatriz Souza Rocha"),    # administradora do módulo
    ("est_t002", "Bruno Carvalho Lima"),        # operador do almoxarifado
    ("est_t003", "Camila Nogueira Prado"),      # somente consulta
    ("est_t004", "Diego Henrique Sales"),       # convidado do depósito
    ("est_t005", "Elisa Maria Tavares Nunes"),  # convidado do depósito
    ("est_t006", "Fabio Antunes Ribeiro"),      # de fora, sem vínculo
)
ADMIN, OPERADOR, CONSULTA, CONVIDADO_1, CONVIDADO_2, SEM_VINCULO = (
    login for login, _nome in USUARIOS_TESTE)

_ALMOXARIFADOS_DO_TESTE = []   # ids: apagados no fim (o central não entra)

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

def _central():
    """O estoque central (fixo, único)."""
    return est.garantir_estoque_central()


def _almoxarifado_novo(nome, unidade_nome, **kwargs):
    """Cria um almoxarifado, registra na limpeza e devolve (ok, msg, id)."""
    try:
        ok, msg, almoxarifado_id = est.criar_almoxarifado(
            nome, unidade_id=kwargs.pop("unidade_id", None),
            unidade_nome=unidade_nome, ator=ADMIN, eh_admin_geral=True, **kwargs)
    except Exception as exc:
        return (False, f"excecao ao criar o almoxarifado: {exc}", None)
    if almoxarifado_id:
        _ALMOXARIFADOS_DO_TESTE.append(almoxarifado_id)
    return (ok, msg, almoxarifado_id)


def _item(descricao, **kwargs):
    """Cadastra um item no almoxarifado dado e devolve (ok, msg, id)."""
    return est.cadastrar_item(descricao, ator=ADMIN, eh_admin_geral=True, **kwargs)


def _item_por_descricao(descricao):
    """O item do catálogo com aquela descrição normalizada."""
    for item in est.listar_itens():
        if est._norm(item["descricao"]) == est._norm(descricao):
            return item
    return None


def _saldo(item_id, almoxarifado_id):
    return est.saldo_item(item_id, almoxarifado_id)


def _data(dias):
    """Data no formato do módulo, `dias` no futuro (+) ou no passado (-)."""
    return (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")


def _recolocar_entrega(entrega_id, dias_atras):
    """Empurra a data de entrega para o passado (simula material parado).

    A entrega é criada com a data de hoje; para o indicador de PARADO existir,
    a data precisa estar além do prazo. Mexer na data pela conexão do próprio
    módulo é o caminho honesto: simula o tempo que passou sem fingir que o
    código sabe Retrodatar entrega.
    """
    try:
        conn = est.get_connection()
    except Exception:
        return False
    try:
        conn.execute("UPDATE tb_estoque_entrega SET data_entrega=? WHERE id=?",
                     (_data(-dias_atras), int(entrega_id)))
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _zerar_estoque_central():
    """Devolve o CENTRAL ao saldo zero — o central é fixo, não se apaga.

    Sem isso a segunda rodada do teste começaria com material de mais e os
    números de verificação mudariam entre uma execução e outra."""
    try:
        conn = est.get_connection()
    except Exception:
        return
    try:
        conn.execute("UPDATE tb_estoque_saldo SET quantidade=0")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    # busca de quem entra no almoxarifado.
    for login, _nome in USUARIOS_TESTE:
        conn = gb.get_connection()
        try:
            conn.execute("UPDATE tb_usuarios SET telefone_pendente=0, "
                         "user_perfil='comum' WHERE user_nome=?", (login,))
            conn.commit()
        finally:
            conn.close()


def _vincular_papeis():
    """Liga os servidores de teste ao módulo com o papel que cada um exercita.

    Feito ANTES dos cenários, porque o módulo recusa quem não tem vínculo: um
    operador sem vínculo entra como consulta, e a primeira verificação de
    movimento passaria a provar a coisa errada."""
    for login, papel in ((ADMIN, est.PAPEL_ADMINISTRADOR),
                         (OPERADOR, est.PAPEL_OPERADOR),
                         (CONVIDADO_1, est.PAPEL_OPERADOR),
                         (CONVIDADO_2, est.PAPEL_OPERADOR),
                         (CONSULTA, est.PAPEL_CONSULTA)):
        ok, msg = est.vincular_usuario(login, papel, ator=ADMIN, eh_admin_geral=True)
        if not ok:
            check(False, f"vinculou {login} como {papel} ({msg})")
            return
    check(True, "vinculou os servidores de teste aos papéis que eles exercitam")


def _limpar():
    """Apaga tudo que o teste criou: vínculos, almoxarifados e usuários."""
    # apaga as linhas criadas por QUALQUER login de teste, em qualquer coluna
    # que guarde "quem fez" (inclusive as que só existem por causa de convite)
    try:
        conn = est.get_connection()
        try:
            for tabela, colunas in (
                    ("tb_estoque_usuario", ("user_nome",)),
                    ("tb_estoque_convite", ("convidado_user_nome", "convidado_por")),
                    ("tb_estoque_tarefa", ("criado_por", "responsavel_user_nome",
                                           "atendente_user_nome")),
                    ("tb_estoque_recolhimento", ("solicitante_user_nome", "atendido_por")),
                    ("tb_estoque_entrega", ("criado_por", "responsavel_user_nome")),
                    ("tb_estoque_movimento", ("usuario_actor",)),
                    ("tb_estoque_documento", ("criado_por", "responsavel_user_nome")),
                    ("tb_estoque_item", ("criado_por",)),
            ):
                condicoes = " OR ".join(f"{c}=?" for c in colunas)
                for login, _nome in USUARIOS_TESTE:
                    conn.execute(f"DELETE FROM {tabela} WHERE {condicoes}",
                                 tuple([login] * len(colunas)))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    for almoxarifado_id in list(reversed(_ALMOXARIFADOS_DO_TESTE)):
        try:
            # zera o saldo e libera as entregas para o `excluir_almoxarifado`
            # aceitar: ele recusa almoxarifado com material, e quem decide o
            # que sobra no fim do teste é o teste, não o módulo
            conn = est.get_connection()
            try:
                conn.execute("UPDATE tb_estoque_saldo SET quantidade=0 "
                             "WHERE almoxarifado_id=?", (almoxarifado_id,))
                conn.execute("UPDATE tb_estoque_entrega SET situacao='recolhido', "
                             "quantidade=0 WHERE almoxarifado_id=?",
                             (almoxarifado_id,))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
        try:
            est.excluir_almoxarifado(almoxarifado_id, ator=ADMIN,
                                     eh_admin_geral=True)
        except Exception:
            pass
    del _ALMOXARIFADOS_DO_TESTE[:]
    for login, _nome in USUARIOS_TESTE:
        _apagar_usuario(login)


def _contar(conexao, sql, logins):
    """`SELECT COUNT(*)` com a lista de logins de teste no `IN`."""
    marcadores = ",".join(["?"] * len(logins))
    linha = conexao.execute(f"{sql} IN ({marcadores})", tuple(logins)).fetchone()
    return int(linha[0] or 0) if linha else 0


# ============ 1) almoxarifados: o central fixo e o da secretaria ============

def teste_almoxarifados():
    """O estoque central é único e fixo; a secretaria tem o almoxarifado dela."""
    print("\n[almoxarifados] central fixo e almoxarifado da secretaria")
    check(est.init_db() is True, "init_db monta o schema e garante o central")
    central = _central()
    check(central is not None, "o estoque central existe")
    check(central["nome"] == "Estoque Central",
          f"o central se chama Estoque Central (veio {central['nome']!r})")
    check(int(central["central"]) == 1, "o central é marcado como central")
    outro = _central()
    check(outro["id"] == central["id"],
          "pedir o central de novo devolve o MESMO (não cria um segundo)")

    ok, msg, almoxarifado_id = _almoxarifado_novo(
        "Almoxarifado de Materiais", "Secretaria de Obras",
        responsavel_user_nome=OPERADOR)
    check(ok, f"o administrador cria o almoxarifado da secretaria ({msg})")
    if not ok:
        return
    almoxarifado = est.obter_almoxarifado(almoxarifado_id)
    check(almoxarifado["unidade_nome"] == "Secretaria de Obras",
          f"o almoxarifado fica ligado à secretaria do organograma "
          f"(veio {almoxarifado['unidade_nome']!r})")
    check(int(almoxarifado["central"]) == 0,
          "o almoxarifado da secretaria NÃO é o central")
    check(almoxarifado["responsavel_user_nome"] == OPERADOR,
          "o responsável do almoxarifado fica gravado")
    check(est.obter_almoxarifado(central["id"])["nome"] == "Estoque Central",
          "o central continua com o nome, depois de criar outro almoxarifado")

    # secretaria não pode ter dois almoxarifados
    ok2, msg2, _id2 = _almoxarifado_novo(
        "Outro Almoxarifado", "Secretaria de Obras", responsavel_user_nome=OPERADOR)
    check(ok2 is False,
          f"a mesma secretaria não ganha um segundo almoxarifado ({msg2!r})")

    # recusas na porta
    check(est.criar_almoxarifado("X", unidade_nome="Secretaria de Obras",
                                 ator=ADMIN, eh_admin_geral=True)[0] is False,
          "almoxarifado de nome curto é recusado")
    check(est.criar_almoxarifado("Sem Secretaria", ator=ADMIN,
                                 eh_admin_geral=True)[0] is False,
          "almoxarifado sem secretaria é recusado")
    check(est.criar_almoxarifado("Almoxarifado_so_com_convite",
                                 unidade_nome="Secretaria de Cultura",
                                 ator=CONSULTA)[0] is False,
          "quem só consulta NÃO cria almoxarifado")
    check(est.criar_almoxarifado("Almoxarifado do operador",
                                 unidade_nome="Secretaria de Cultura",
                                 ator=OPERADOR)[0] is False,
          "quem é só operador NÃO cria almoxarifado (só o administrador cria)")

    # o central é fixo: não renomeia, não altera, não exclui
    check(est.atualizar_almoxarifado(central["id"], {"nome": "Outro nome"},
                                     ator=ADMIN, eh_admin_geral=True)[0] is False,
          "o estoque central NÃO se renomeia")
    check(est.excluir_almoxarifado(central["id"], ator=ADMIN,
                                   eh_admin_geral=True)[0] is False,
          "o estoque central NÃO se exclui")
    check(est.obter_almoxarifado(central["id"])["nome"] == "Estoque Central",
          "e o central continua no lugar depois das duas tentativas")

    # almoxarifado com saldo não se exclui
    _item("Papel Sulfite A4", unidade_medida="CX", almoxarifado_id=central["id"])
    ok3, msg3 = est.registrar_entrada("Papel Sulfite A4", 5, "CX",
                                      almoxarifado_id=almoxarifado_id, ator=OPERADOR)
    check(ok3, f"o operador registra entrada no almoxarifado da secretaria ({msg3})")
    ok4, msg4 = est.excluir_almoxarifado(almoxarifado_id, ator=ADMIN,
                                         eh_admin_geral=True)
    check(ok4 is False,
          f"almoxarifado com material em estoque NÃO se exclui ({msg4!r})")

    # ativar/desativar
    ok5, msg5 = est.atualizar_almoxarifado(almoxarifado_id, {"ativo": False},
                                           ator=ADMIN, eh_admin_geral=True)
    check(ok5, f"o administrador desativa o almoxarifado ({msg5})")
    check(int(est.obter_almoxarifado(almoxarifado_id)["ativo"]) == 0,
          "o almoxarifado fica gravado como inativo")
    est.atualizar_almoxarifado(almoxarifado_id, {"ativo": True},
                               ator=ADMIN, eh_admin_geral=True)
    check(est.criar_almoxarifado("X", unidade_nome="Qualquer",
                                 ator=CONSULTA)[0] is False,
          "quem só consulta continua sem criar almoxarifado")


# ============ 2) entrada, transferência e estoque negativo ============

def teste_entrada_e_transferencia():
    """Entrada no central, transferência com documento e recusa de negativo."""
    print("\n[entrada e transferência] documento de saída e estoque negativo")
    central = _central()
    almoxarifados = est.listar_almoxarifados_descentralizados()
    destino = almoxarifados[0]

    # ---- entrada no central ----
    sequencial_antes = est.proximo_numero(central["id"], "item")
    ok, msg = est.registrar_entrada("Resma A4", 10, "CX", data_entrada=_data(-2),
                                    origem="nota_empenho", nota_empenho="NE-2026-0145",
                                    responsavel_user_nome=ADMIN, ator=OPERADOR)
    check(ok, f"o operador registra entrada no estoque central ({msg})")
    resma = _item_por_descricao("Resma A4")
    check(resma is not None, "o item entra no catálogo com a entrada")
    esperado = est.montar_numero(central["prefixo_item"], sequencial_antes + 1,
                                 central["digitos_numero"])
    check(resma["numero"] == esperado,
          f"o item novo recebe o próximo número do central (veio "
          f"{resma['numero']!r}, esperado {esperado!r})")
    check(resma["unidade_medida"] == "CX", "a unidade de medida fica gravada")
    check(_saldo(resma["id"], central["id"]) == 10,
          f"o disponível no central é 10 (veio {_saldo(resma['id'], central['id'])})")

    # a mesma entrada de novo SOMA no mesmo item, sem criar item novo
    est.registrar_entrada("resma  a4", 5, "CX", ator=OPERADOR)
    resma2 = _item_por_descricao("Resma A4")
    check(resma2["id"] == resma["id"],
          '"resma  a4" é o MESMO item de "Resma A4" (normalizado)')
    check(_saldo(resma["id"], central["id"]) == 15,
          f"a segunda entrada soma no mesmo item (ficou "
          f"{_saldo(resma['id'], central['id'])})")

    # recusas na entrada
    check(est.registrar_entrada("X", 5, "CX", ator=OPERADOR)[0] is False,
          "entrada de item de nome curto é recusada")
    check(est.registrar_entrada("Item sem quantidade", 0, "CX",
                                ator=OPERADOR)[0] is False,
          "entrada com quantidade zero é recusada")
    check(est.registrar_entrada("Item do leitor", 5, "CX", ator=CONSULTA)[0] is False,
          "quem só consulta NÃO registra entrada")

    # ---- transferência central → secretaria ----
    ok, msg, numero_doc = est.transferir(
        resma["id"], 4, destino["id"], almoxarifado_origem_id=central["id"],
        data_movimento=_data(-1), responsavel=ADMIN, ator=OPERADOR)
    check(ok, f"o operador transfere do central para a secretaria ({msg})")
    check(bool(numero_doc) and numero_doc.startswith("DOC-"),
          f"a transferência gera DOCUMENTO DE SAÍDA (veio {numero_doc!r})")
    check(_saldo(resma["id"], central["id"]) == 11,
          f"o central baixou 4 (ficou {_saldo(resma['id'], central['id'])})")
    check(_saldo(resma["id"], destino["id"]) == 4,
          f"a secretaria recebeu 4 (ficou {_saldo(resma['id'], destino['id'])})")

    # ---- estoque negativo é PROIBIDO ----
    tem = _saldo(resma["id"], central["id"])
    ok, msg, _doc = est.transferir(resma["id"], tem + 1, destino["id"],
                                   almoxarifado_origem_id=central["id"],
                                   ator=OPERADOR)
    check(ok is False, f"transferência maior que o disponível é RECUSADA ({msg!r})")
    check(f"{tem:g}" in msg,
          f"a recusa diz quanto tem (veio {msg!r}, disponível {tem:g})")
    check("negativo" in msg.lower(), "a recusa explica que é para o estoque não "
                                     "ficar negativo")
    check(_saldo(resma["id"], central["id"]) == tem,
          "e o saldo NÃO mudou depois da recusa")
    ok, msg, _doc = est.transferir(resma["id"], 11, destino["id"],
                                   almoxarifado_origem_id=central["id"],
                                   ator=OPERADOR)
    check(ok is True,
          f"transferir exatamente o disponível é permitido ({msg!r})")
    check(_saldo(resma["id"], central["id"]) == 0,
          "o central pode zerar — nunca ficar negativo")

    # recusas na transferência
    ok, msg, _doc = est.transferir(resma["id"], 5, destino["id"],
                                   almoxarifado_origem_id=destino["id"],
                                   ator=OPERADOR)
    check(ok is False, f"origem e destino iguais é recusado ({msg!r})")
    ok, msg, _doc = est.transferir(resma["id"], 5, _ID_QUE_NAO_EXISTE,
                                   almoxarifado_origem_id=central["id"],
                                   ator=OPERADOR)
    check(ok is False, f"destino inexistente é recusado ({msg!r})")
    ok, msg, _doc = est.transferir(_ID_QUE_NAO_EXISTE, 5, destino["id"],
                                   almoxarifado_origem_id=central["id"],
                                   ator=OPERADOR)
    check(ok is False, f"item inexistente é recusado ({msg!r})")
    ok, msg, _doc = est.transferir(resma["id"], 5, destino["id"],
                                   almoxarifado_origem_id=central["id"],
                                   ator=CONSULTA)
    check(ok is False, f"quem só consulta NÃO transfere ({msg!r})")
    ok, msg, _doc = est.transferir(resma["id"], 0, destino["id"],
                                   almoxarifado_origem_id=central["id"],
                                   ator=OPERADOR)
    check(ok is False, f"transferência de quantidade zero é recusada ({msg!r})")
    check(est.proximo_numero(central["id"], "documento") > 0
          and est.proximo_numero(central["id"], "item") > 0,
          "as recusas não apagam os contadores do almoxarifado")


# ============ 3) transferência entre almoxarifados e devolução ao central ============

def teste_entre_almoxarifados_e_devolucao():
    """Entre dois almoxarifados e de volta para o central."""
    print("\n[entre almoxarifados] empréstimo entre secretarias e devolução")
    central = _central()
    ok, msg, id_b = _almoxarifado_novo("Almoxarifado de Manutencao",
                                       "Secretaria de Manutencao",
                                       responsavel_user_nome=OPERADOR)
    check(ok, f"cria o segundo almoxarifado de secretaria ({msg})")
    if not ok:
        return
    alvo = est.obter_almoxarifado(id_b)

    # entra material no central e vai para a primeira secretaria
    est.registrar_entrada("Broca Furadeira", 6, "UN", ator=OPERADOR)
    broca = _item_por_descricao("Broca Furadeira")
    check(broca is not None, "a broca entrou no catálogo")
    origem = est.listar_almoxarifados_descentralizados()[0]
    est.transferir(broca["id"], 5, origem["id"],
                   almoxarifado_origem_id=central["id"], ator=OPERADOR)
    check(_saldo(broca["id"], origem["id"]) == 5,
          f"a primeira secretaria ficou com 5 (veio "
          f"{_saldo(broca['id'], origem['id'])})")

    # ---- almoxarifado → almoxarifado ----
    ok, msg, numero_doc = est.transferir(
        broca["id"], 2, alvo["id"], almoxarifado_origem_id=origem["id"],
        observacao="Emprestimo para a obra da escola", ator=OPERADOR)
    check(ok, f"transferência entre dois almoxarifados ({msg})")
    check(bool(numero_doc), f"e também gera documento (veio {numero_doc!r})")
    check(_saldo(broca["id"], origem["id"]) == 3,
          f"a origem baixou 2 (ficou {_saldo(broca['id'], origem['id'])})")
    check(_saldo(broca["id"], alvo["id"]) == 2,
          f"o destino da secretaria recebeu 2 (ficou "
          f"{_saldo(broca['id'], alvo['id'])})")
    ok, msg, _doc = est.transferir(broca["id"], 9, alvo["id"],
                                   almoxarifado_origem_id=origem["id"],
                                   ator=OPERADOR)
    check(ok is False, "transferência entre almoxarifados também recusa o negativo")

    # ---- devolução → central ----
    central_antes = _saldo(broca["id"], central["id"])
    ok, msg, numero_doc = est.devolver(alvo["id"], 2, broca["id"],
                                       data_movimento=_data(-1), ator=OPERADOR)
    check(ok, f"a secretaria devolve material ao estoque central ({msg})")
    check(_saldo(broca["id"], central["id"]) == central_antes + 2,
          f"o item VOLTOU a ficar disponível no central (ficou "
          f"{_saldo(broca['id'], central['id'])}, era {central_antes})")
    check(_saldo(broca["id"], alvo["id"]) == 0,
          "e saiu do almoxarifado que devolveu")
    ok, msg, _doc = est.devolver(alvo["id"], 5, broca["id"], ator=OPERADOR)
    check(ok is False, f"devolução maior que o disponível é recusada ({msg!r})")
    ok, msg, _doc = est.devolver(alvo["id"], 1, _ID_QUE_NAO_EXISTE, ator=OPERADOR)
    check(ok is False, f"devolução de item inexistente é recusada ({msg!r})")
    ok, msg, _doc = est.devolver(alvo["id"], 1, broca["id"], ator=CONSULTA)
    check(ok is False, f"quem só consulta NÃO devolve ({msg!r})")


# ============ 4) entrega na sala: em uso e item parado ============

def teste_em_uso_e_parado():
    """Entregar à sala é o que vira "em uso"; parado é o que vira desperdício."""
    print("\n[em uso] entrega na sala, dias parados e o painel da secretaria")
    # almoxarifado NOVO: o painel é um total do almoxarifado, e um que já
    # recebeu material de outros testes não diria "recebido = 4"
    ok, msg, almoxarifado_id = _almoxarifado_novo(
        "Almoxarifado de Patio", "Secretaria de Patio",
        responsavel_user_nome=OPERADOR)
    check(ok, f"cria o almoxarifado do cenário de uso ({msg})")
    if not ok:
        return
    almoxarifado = est.obter_almoxarifado(almoxarifado_id)
    est.registrar_entrada("Cadeira Ergonometrica", 4, "UN",
                          almoxarifado_id=almoxarifado["id"], ator=OPERADOR)
    cadeira = _item_por_descricao("Cadeira Ergonometrica")

    # sem destino e sem data, "em uso" não é número
    ok, msg = est.entregar_item(2, almoxarifado["id"], "", ator=OPERADOR)
    check(ok is False, f"entrega sem sala é recusada ({msg!r})")
    ok, msg = est.entregar_item(0, almoxarifado["id"], "Sala 1", ator=OPERADOR)
    check(ok is False, f"entrega com quantidade zero é recusada ({msg!r})")
    ok, msg = est.entregar_item(99, almoxarifado["id"], "Sala 1",
                                item_id=cadeira["id"], ator=OPERADOR)
    check(ok is False, f"entrega maior que o disponível é recusada ({msg!r})")
    ok, msg = est.entregar_item(1, almoxarifado["id"], "Sala 1",
                                item_id=_ID_QUE_NAO_EXISTE, ator=OPERADOR)
    check(ok is False, f"entrega de item inexistente é recusada ({msg!r})")
    ok, msg = est.entregar_item(1, almoxarifado["id"], "Sala 1",
                                item_id=cadeira["id"], ator=CONSULTA)
    check(ok is False, f"quem só consulta NÃO entrega para a sala ({msg!r})")

    ok, msg = est.entregar_item(2, almoxarifado["id"], "Sala 12",
                                destino_departamento="Obras Publicas",
                                responsavel_user_nome=ADMIN,
                                data_entrega=_data(-1), item_id=cadeira["id"],
                                ator=OPERADOR)
    check(ok, f"entrega material para a sala com destino e data ({msg})")
    check(_saldo(cadeira["id"], almoxarifado["id"]) == 2,
          f"o disponível da secretaria baixou (ficou "
          f"{_saldo(cadeira['id'], almoxarifado['id'])})")

    entregas = est.listar_entregas(almoxarifado_id=almoxarifado["id"])
    check(len(entregas) == 1, f"a entrega aparece na lista (veio {len(entregas)})")
    entrega = entregas[0]
    check(entrega["situacao"] == "em_uso", "a entrega conta como EM USO")
    check(entrega["destino_sala"] == "Sala 12", "a entrega guarda a sala de destino")
    check(entrega["destino_departamento"] == "Obras Publicas",
          "a entrega guarda o departamento")
    check(entrega["data_entrega"] == _data(-1), "a entrega guarda a data da entrega")
    check(entrega["dias_parado"] == 1,
          f"o painel conta os dias sem baixa (veio {entrega['dias_parado']})")
    check(entrega["parado"] is False,
          f"com 1 dia não está parado (prazo é "
          f"{est.dias_parado()} dias)")

    # ---- o painel da secretaria ----
    painel = est.painel_almoxarifado(almoxarifado["id"])
    check(painel is not None, "o painel da secretaria monta")
    check(painel["em_uso"] == 2, f"em uso = 2 (veio {painel['em_uso']})")
    check(painel["disponivel"] == 2,
          f"disponível = 2 (veio {painel['disponivel']})")
    check(painel["recebido"] == 4, f"recebido = 4 (veio {painel['recebido']})")
    check(painel["parado"] == 0, f"parado = 0 com prazo de "
                                  f"{painel['dias_limite']} dias (veio "
                                  f"{painel['parado']})")

    # ---- item PARADO: passou do prazo sem baixa ----
    check(_recolocar_entrega(entrega["id"], 45) is True,
          "a entrega foi antecipada em 45 dias (simula o tempo passado)")
    entregas = est.listar_entregas(almoxarifado_id=almoxarifado["id"])
    check(len(entregas) == 1, "a entrega continua sendo a mesma")
    check(entregas[0]["dias_parado"] == 45,
          f"a entrega conta 45 dias sem baixa (veio {entregas[0]['dias_parado']})")
    check(entregas[0]["parado"] is True,
          "e entra na lista de item PARADO (o indicador de desperdício)")
    check([e["id"] for e in est.listar_entregas(apenas_parados=True)] ==
          [entrega["id"]],
          "a listagem só de parados traz exatamente essa entrega")
    painel = est.painel_almoxarifado(almoxarifado["id"])
    check(painel["parado"] == 2,
          f"o painel da secretaria mostra 2 unidades PARADAS (veio {painel['parado']})")

    # o prazo é configurável e muda o que é parado
    est.salvar_dias_parado(60, ator=ADMIN, eh_admin_geral=True)
    check(est.dias_parado() == 60,
          f"o administrador muda o prazo de item parado (ficou {est.dias_parado()})")
    check(est.painel_almoxarifado(almoxarifado["id"])["parado"] == 0,
          "com prazo maior a entrega de 45 dias NÃO conta mais como parada")
    est.salvar_dias_parado(30, ator=ADMIN, eh_admin_geral=True)
    check(est.dias_parado() == 30, "e volta ao prazo padrão de 30 dias")
    check(est.salvar_dias_parado(15, ator=OPERADOR)[0] is False,
          "quem é só operador NÃO muda o prazo de item parado")


# ============ 5) pedido de recolhimento: o que evita desperdício ============

def teste_recolhimento():
    """O almoxarifado pede, o central atende, e o material volta ao disponível."""
    print("\n[recolhimento] pedido do almoxarifado, atendimento do central")
    central = _central()
    ok, msg, almoxarifado_id = _almoxarifado_novo(
        "Almoxarifado de Archive", "Secretaria de Archive",
        responsavel_user_nome=OPERADOR)
    check(ok, f"cria o almoxarifado do cenário de recolhimento ({msg})")
    if not ok:
        return
    almoxarifado = est.obter_almoxarifado(almoxarifado_id)
    est.registrar_entrada("Ar Condicionado 12000 BTUs", 3, "UN",
                          almoxarifado_id=almoxarifado["id"], ator=OPERADOR)
    equip = _item_por_descricao("Ar Condicionado 12000 BTUs")
    ok, msg = est.entregar_item(2, almoxarifado["id"], "Sala do Arquivo",
                                destino_departamento="Arquivo Geral",
                                data_entrega=_data(-40), item_id=equip["id"],
                                ator=OPERADOR)
    check(ok, f"entrega material que vai ficar parado na sala ({msg})")
    entrega = est.listar_entregas(almoxarifado_id=almoxarifado["id"])[0]
    check(_recolocar_entrega(entrega["id"], 40) is True,
          "a entrega foi antecipada em 40 dias (está parada há mais do prazo)")

    # ---- quem está com o item também pode devolver por não uso ----
    ok, msg, pedido_id = est.abrir_pedido_recolhimento(
        almoxarifado["id"], equip["id"], 2, tipo_pedido="devolucao",
        destino_sala="Sala do Arquivo", motivo="Obra adiada, nao instalou",
        solicitante_user_nome=CONVIDADO_1, ator=CONVIDADO_1)
    check(ok, f"quem está com o item abre o mesmo pedido por não uso ({msg})")
    check(pedido_id is not None, "o pedido de devolução foi gravado")
    check(est.listar_pedidos_recolhimento(situacao="aberto")[0]["tipo_pedido"]
          == "devolucao", "o pedido guarda quem pediu (devolução)")

    # quem está com o item também pode pedir RECOLHIMENTO pelo almoxarifado
    ok, msg, pedido_id2 = est.abrir_pedido_recolhimento(
        almoxarifado["id"], equip["id"], 1, tipo_pedido="recolhimento",
        destino_sala="Sala do Arquivo", motivo="Sobra do almoxarifado",
        solicitante_user_nome=OPERADOR, ator=OPERADOR)
    check(ok, f"o almoxarifado abre pedido de recolhimento do material parado ({msg})")
    check(est.listar_pedidos_recolhimento(situacao="aberto")[0]["tipo_pedido"]
          == "recolhimento", "o pedido guarda quem pediu (recolhimento)")

    # pedido maior que o que está em uso é recusado
    ok, msg, _pid = est.abrir_pedido_recolhimento(
        almoxarifado["id"], equip["id"], 99, solicitante_user_nome=OPERADOR,
        ator=OPERADOR)
    check(ok is False,
          f"pedido maior que a entrega em aberto é recusado ({msg!r})")
    ok, msg, _pid = est.abrir_pedido_recolhimento(
        almoxarifado["id"], _ID_QUE_NAO_EXISTE, 1, solicitante_user_nome=OPERADOR,
        ator=OPERADOR)
    check(ok is False, f"pedido de item inexistente é recusado ({msg!r})")

    # ---- quem pode atender ----
    check(est.pode_atender_recolhimento(CONSULTA, almoxarifado["id"]) is False,
          "quem só consulta NÃO atende pedido de recolhimento")
    check(est.pode_atender_recolhimento(SEM_VINCULO, almoxarifado["id"]) is False,
          "servidor sem vínculo com o módulo NÃO atende")
    check(est.pode_atender_recolhimento(CONVIDADO_1, almoxarifado["id"]) is False,
          "quem não é da secretaria e não é do central NÃO atende")
    check(est.pode_atender_recolhimento(ADMIN, almoxarifado["id"],
                                        eh_admin_geral=True) is True,
          "o administrador do módulo atende")
    check(est.pode_atender_recolhimento(OPERADOR, almoxarifado["id"]) is True,
          "o responsável pelo almoxarifado atende o pedido dele")
    check(est.pode_atender_recolhimento(OPERADOR, central["id"]) is True,
          "o operador do estoque central é quem recolhe para todos")

    # ---- atendimento: o material VOLTA ao disponível da secretaria ----
    antes = _saldo(equip["id"], almoxarifado["id"])
    check(antes == 1, f"o disponível da secretaria estava em 1 (veio {antes})")
    ok, msg = est.atender_pedido_recolhimento(pedido_id2, 1,
                                              parecer="Material nao usado",
                                              ator=ADMIN, eh_admin_geral=True)
    check(ok, f"o central atende o recolhimento ({msg})")
    check(_saldo(equip["id"], almoxarifado["id"]) == antes + 1,
          f"a quantidade VOLTOU ao disponível da secretaria (ficou "
          f"{_saldo(equip['id'], almoxarifado['id'])}, era {antes})")
    atendido = [p for p in est.listar_pedidos_recolhimento(situacao="atendido")
                if p["id"] == pedido_id2]
    check(len(atendido) == 1, "o pedido fica marcado como ATENDIDO")
    check(bool(atendido[0]["data_atendimento"]), "o atendimento grava a data")
    check(atendido[0]["atendido_por"] == ADMIN, "o atendimento grava QUEM atendeu")
    restante = [e for e in est.listar_entregas(situacao="em_uso")
                if e["id"] == entrega["id"]]
    check(len(restante) == 1 and restante[0]["quantidade"] == 1,
          f"a entrega ficou com o que não foi recolhido (veio "
          f"{restante[0]['quantidade'] if restante else 'sumiu'})")

    # pedido já atendido não se atende duas vezes
    ok, msg = est.atender_pedido_recolhimento(pedido_id2, 1, ator=ADMIN,
                                              eh_admin_geral=True)
    check(ok is False, f"pedido já atendido não se atende de novo ({msg!r})")
    # e quem não pode atender é barrado na porta
    ok, msg = est.atender_pedido_recolhimento(pedido_id, 1, ator=CONVIDADO_1)
    check(ok is False, f"servidor sem permissão é barrado no atendimento ({msg!r})")
    # atendimento maior que o pedido é recusado
    ok, msg = est.atender_pedido_recolhimento(pedido_id, 99, ator=ADMIN,
                                              eh_admin_geral=True)
    check(ok is False, f"atendimento maior que o pedido é recusado ({msg!r})")

    # ---- recusa: o material continua em uso ----
    ok, msg = est.recusar_pedido_recolhimento(
        pedido_id, parecer="Sala em reforma", ator=ADMIN, eh_admin_geral=True)
    check(ok, f"o central recusa o pedido ({msg})")
    check(est.listar_pedidos_recolhimento(situacao="recusado")[0]["id"] == pedido_id,
          "o pedido fica marcado como RECUSADO")
    check(_saldo(equip["id"], almoxarifado["id"]) == 2,
          "e o material continua em uso (o disponível não mudou)")
    ok, msg = est.recusar_pedido_recolhimento(pedido_id, ator=ADMIN,
                                              eh_admin_geral=True)
    check(ok is False, f"pedido já recusado não se recusa de novo ({msg!r})")
    ok, msg = est.atender_pedido_recolhimento(_ID_QUE_NAO_EXISTE, 1, ator=ADMIN,
                                              eh_admin_geral=True)
    check(ok is False, f"atendimento de pedido inexistente é recusado ({msg!r})")

    # ---- o recolhimento vira evento e aparece no histórico ----
    movimentos = est.listar_movimentos(item_id=equip["id"])
    tipos = [m["tipo"] for m in movimentos]
    check("devolucao" in tipos,
          f"o recolhimento virou MOVIMENTO de devolução (veio {tipos})")
    check(all(m["criado_em"] for m in movimentos),
          "todo movimento tem data de gravação")
    check(all(m["usuario_actor"] for m in movimentos),
          "todo movimento guarda QUEM registrou")


# ============ 6) tarefa de depósito: quem chama quem para tratar ============

def teste_tarefa_deposito():
    """Tarefa de depósito com necessários, aceite e quem está atendendo."""
    print("\n[depósito] tarefa, convidados, aceite e quem está atendendo")
    central = _central()
    almoxarifado = est.listar_almoxarifados_descentralizados()[0]

    ok, msg, tarefa_id = est.criar_tarefa_deposito(
        "Conferencia da entrada do mes", tipo="conferir",
        descricao="Conferir nota de empenho contra o material recebido",
        almoxarifado_id=central["id"], responsavel_user_nome=ADMIN,
        necessarios_convidados=2, ator=ADMIN, eh_admin_geral=True)
    check(ok, f"o responsável abre a tarefa de depósito ({msg})")
    if not ok:
        return
    check(est.listar_tarefas(almoxarifado_id=almoxarifado["id"]) == [],
          f"a tarefa foi aberta no central, não no almoxarifado da secretaria "
          f"(veio {len(est.listar_tarefas(almoxarifado_id=almoxarifado['id']))})")
    tarefa = est.obter_tarefa(tarefa_id)
    check(tarefa["numero"].startswith("IT-"),
          f"a tarefa recebe número do almoxarifado (veio {tarefa['numero']!r})")
    check(tarefa["situacao"] == "aberta", "a tarefa nasce ABERTA")
    check(int(tarefa["necessarios_convidados"]) == 2,
          f"a tarefa guarda quantos convidados são necessários (veio "
          f"{tarefa['necessarios_convidados']})")
    check(tarefa["tipo"] == "conferir", "a tarefa guarda o tipo (conferir)")

    ok, msg, _tid = est.criar_tarefa_deposito("AB", tipo="conferir",
                                              almoxarifado_id=central["id"],
                                              ator=ADMIN, eh_admin_geral=True)
    check(ok is False, f"tarefa de título curto é recusada ({msg!r})")
    ok, msg, _tid = est.criar_tarefa_deposito("Tarefa do leitor",
                                              almoxarifado_id=central["id"],
                                              ator=CONSULTA)
    check(ok is False, f"quem só consulta NÃO abre tarefa de depósito ({msg!r})")

    # ---- quem pode chamar quem ----
    ok, msg = est.convidar_para_tarefa(tarefa_id, CONVIDADO_1, ator=ADMIN,
                                      eh_admin_geral=True)
    check(ok, f"quem responde pela tarefa CHAMA servidor cadastrado ({msg})")
    convites = est.listar_convites_tarefa(tarefa_id)
    check(len(convites) == 1, f"a tarefa tem 1 convidado (veio {len(convites)})")
    check(convites[0]["situacao"] == "pendente", "o convite nasce PENDENTE")
    check(convites[0]["convidado_user_nome"] == CONVIDADO_1,
          "o convite aponta para o servidor cadastrado")
    check(bool(convites[0]["nome_exibicao"]),
          "o convite traz o nome de exibição do servidor")

    # convite pendente NÃO conta como aceito
    tarefa = est.listar_tarefas()[0]
    check(tarefa["aceitos"] == 0,
          f"convite pendente NÃO conta como aceito (veio {tarefa['aceitos']})")
    check(tarefa["convites_pendentes"] == 1, "e o pendente fica visível")

    # responder convite de outra pessoa
    ok, msg, _num = est.responder_convite_tarefa(convites[0]["id"], CONVIDADO_2,
                                                True)
    check(ok is False, f"convite de um só é do próprio convidado ({msg!r})")

    # ---- aceite ----
    pendentes = est.listar_convites_pendentes(CONVIDADO_1)
    check(len(pendentes) == 1, "o convidado vê o convite pendente")
    check(pendentes[0]["tarefa_id"] == tarefa_id, "o pendente é desta tarefa")
    ok, msg, numero = est.responder_convite_tarefa(pendentes[0]["id"],
                                                   CONVIDADO_1, True)
    check(ok, f"o convidado aceita tratar o depósito ({msg})")
    check(est.listar_convites_pendentes(CONVIDADO_1) == [],
          "convite aceito sai da lista de pendentes")
    check(est.listar_convites_tarefa(tarefa_id)[0]["situacao"] == "aceito",
          "a tarefa registra o convite como aceito")
    tarefa = est.listar_tarefas()[0]
    check(tarefa["aceitos"] == 1, f"a tarefa conta 1 aceito (veio {tarefa['aceitos']})")
    ok, msg, _num = est.responder_convite_tarefa(pendentes[0]["id"],
                                                CONVIDADO_1, True)
    check(ok is False, f"convite já respondido não se responde duas vezes ({msg!r})")

    # recusas no convite
    ok, msg = est.convidar_para_tarefa(tarefa_id, ADMIN, ator=ADMIN,
                                       eh_admin_geral=True)
    check(ok is False, f"quem responde pela tarefa não se convida ({msg!r})")
    ok, msg = est.convidar_para_tarefa(tarefa_id, CONVIDADO_2, ator=ADMIN,
                                       eh_admin_geral=True)
    check(ok, f"convida o segundo servidor ({msg})")
    antes = len(est.listar_convites_tarefa(tarefa_id))
    ok, msg = est.convidar_para_tarefa(tarefa_id, CONVIDADO_1, ator=ADMIN,
                                       eh_admin_geral=True)
    check(ok, f"convidar quem já aceitou renova sem criar segunda linha ({msg})")
    check(len(est.listar_convites_tarefa(tarefa_id)) == antes,
          "e a quantidade de convidados continua a mesma")
    ok, msg = est.convidar_para_tarefa(tarefa_id, SEM_VINCULO, ator=CONSULTA)
    check(ok is False, f"quem não responde pela tarefa não convida ({msg!r})")
    ok, msg = est.convidar_para_tarefa(tarefa_id, "", ator=ADMIN,
                                       eh_admin_geral=True)
    check(ok is False, f"convite sem servidor escolhido é recusado ({msg!r})")

    # cancelar convite
    convites = est.listar_convites_tarefa(tarefa_id)
    pendente = [c for c in convites if c["situacao"] == "pendente"][0]
    ok, msg = est.cancelar_convite_tarefa(pendente["id"], ator=ADMIN,
                                          eh_admin_geral=True)
    check(ok, f"cancela o convite pendente ({msg})")
    check(est.listar_convites_tarefa(tarefa_id)[1]["situacao"] == "cancelado",
          "o convite fica como cancelado")
    ok, msg = est.cancelar_convite_tarefa(_ID_QUE_NAO_EXISTE, ator=ADMIN,
                                          eh_admin_geral=True)
    check(ok is False, f"cancelar convite inexistente é recusado ({msg!r})")

    # ---- quem está ATENDENDO ----
    ok, msg = est.assumir_tarefa(tarefa_id, CONVIDADO_1)
    check(ok, f"o convidado assume o atendimento do depósito ({msg})")
    tarefa = est.listar_tarefas()[0]
    check(tarefa["atendente_user_nome"] == CONVIDADO_1,
          "a tarefa guarda QUEM está atendendo")
    check(tarefa["situacao"] == "em_andamento",
          f"e a tarefa passa a EM ANDAMENTO (veio {tarefa['situacao']!r})")
    check(est.obter_tarefa(tarefa_id)["responsavel_user_nome"] == ADMIN,
          "quem atende não é o mesmo que quem responde pela tarefa")
    ok, msg = est.assumir_tarefa(tarefa_id, SEM_VINCULO)
    check(ok is False, f"servidor sem vínculo não assume tarefa ({msg!r})")

    # concluir
    ok, msg = est.concluir_tarefa(tarefa_id, ator=OPERADOR)
    check(ok, f"o operador conclui o depósito ({msg})")
    tarefa = est.obter_tarefa(tarefa_id)
    check(tarefa["situacao"] == "concluida", "a tarefa fica CONCLUÍDA")
    check(bool(tarefa["data_conclusao"]), "a conclusão grava a data")
    ok, msg = est.concluir_tarefa(tarefa_id, ator=OPERADOR)
    check(ok is False, f"tarefa já concluída não se conclui de novo ({msg!r})")
    ok, msg = est.convidar_para_tarefa(tarefa_id, CONVIDADO_2, ator=ADMIN,
                                       eh_admin_geral=True)
    check(ok is False, f"tarefa concluída não aceita mais convite ({msg!r})")
    ok, msg, _num = est.responder_convite_tarefa(_ID_QUE_NAO_EXISTE, CONVIDADO_2,
                                                True)
    check(ok is False, f"responder convite inexistente é recusado ({msg!r})")


# ============ 7) permissões por papel ============

def teste_papeis():
    """Consulta não movimenta, operador movimenta, administrador cria."""
    print("\n[papéis] quem pode fazer o quê no módulo de estoque")
    est.vincular_usuario(ADMIN, est.PAPEL_ADMINISTRADOR, ator=ADMIN,
                         eh_admin_geral=True)
    est.vincular_usuario(OPERADOR, est.PAPEL_OPERADOR, ator=ADMIN,
                         eh_admin_geral=True)
    est.vincular_usuario(CONSULTA, est.PAPEL_CONSULTA, ator=ADMIN,
                         eh_admin_geral=True)
    check(True, "o administrador vincula os três servidores ao módulo")

    vinculos = {v["user_nome"]: v["papel"]
                for v in est.listar_usuarios_vinculados()}
    check(vinculos.get(OPERADOR) == est.PAPEL_OPERADOR,
          "o vínculo guarda o papel de operador")
    check(vinculos.get(CONSULTA) == est.PAPEL_CONSULTA,
          "o vínculo guarda o papel de consulta")

    # ---- quem tem acesso ao módulo mas não foi vinculado entra como consulta --
    check(est.papel_no_estoque(SEM_VINCULO) == est.PAPEL_CONSULTA,
          f"sem vínculo, o servidor entra como CONSULTA (veio "
          f"{est.papel_no_estoque(SEM_VINCULO)!r})")
    check(est.pode_consultar(SEM_VINCULO) is True, "e ele pode consultar")
    check(est.pode_movimentar(SEM_VINCULO) is False,
          "mas NÃO pode movimentar estoque")
    check(est.papel_no_estoque("") is None,
          "sem login não há papel nenhum no módulo")

    # ---- recusas na porta do vínculo ----
    check(est.vincular_usuario("", ator=ADMIN, eh_admin_geral=True)[0] is False,
          "vínculo sem servidor escolhido é recusado")
    check(est.vincular_usuario(CONVIDADO_1, "chefe", ator=ADMIN,
                               eh_admin_geral=True)[0] is False,
          "papel fora de consulta/operador/administrador é recusado")
    check(est.vincular_usuario(CONVIDADO_1, est.PAPEL_OPERADOR, ator=CONSULTA)[0]
          is False, "quem só consulta NÃO escolhe quem opera")
    check(est.vincular_usuario(CONVIDADO_1, est.PAPEL_OPERADOR, ator=OPERADOR)[0]
          is False, "quem é só operador NÃO escolhe quem opera")

    # ---- administrador: cria almoxarifado e item ----
    check(est.pode_administrar(ADMIN, eh_admin_geral=True) is True,
          "o administrador do módulo administra")
    check(est.criar_almoxarifado("X", unidade_nome="Secretaria Teste",
                                 ator=ADMIN, eh_admin_geral=True)[0] is False,
          "almoxarifado de nome curto é recusado")
    check(est.cadastrar_item("Item do operador", almoxarifado_id=_central()["id"],
                             ator=OPERADOR)[0] is False,
          "quem é só operador NÃO cadastra item")
    ok, msg, _item_id = est.cadastrar_item("Papel A4 75g", "CX",
                                           almoxarifado_id=_central()["id"],
                                           ator=ADMIN, eh_admin_geral=True)
    check(ok, f"o administrador cadastra item ({msg})")
    ok, msg, _item_id = est.cadastrar_item("ab", almoxarifado_id=_central()["id"],
                                           ator=ADMIN, eh_admin_geral=True)
    check(ok is False, f"item de nome curto é recusado ({msg!r})")
    ok, msg, _item_id = est.cadastrar_item("Papel A4 75g", "CX",
                                           almoxarifado_id=_central()["id"],
                                           ator=ADMIN, eh_admin_geral=True)
    check(ok is False,
          f"item repetido no mesmo almoxarifado não cria linha nova ({msg!r})")

    # ---- desligar o vínculo muda o que a pessoa pode fazer ----
    check(est.pode_movimentar(CONSULTA) is False,
          "quem é só consulta não movimenta")
    est.vincular_usuario(CONSULTA, est.PAPEL_OPERADOR, ator=ADMIN,
                         eh_admin_geral=True)
    check(est.papel_no_estoque(CONSULTA) == est.PAPEL_OPERADOR,
          "promover o servidor muda o papel dele")
    check(est.pode_movimentar(CONSULTA) is True,
          "e agora ele movimenta estoque")
    est.vincular_usuario(CONSULTA, est.PAPEL_CONSULTA, ator=ADMIN,
                         eh_admin_geral=True)
    check(est.pode_movimentar(CONSULTA) is False,
          "rebaixar volta a não movimentar")

    ok, msg = est.remover_vinculo(CONSULTA, ator=ADMIN, eh_admin_geral=True)
    check(ok, f"o administrador retira o servidor do módulo ({msg})")
    check(CONSULTA not in {v["user_nome"]
                           for v in est.listar_usuarios_vinculados()},
          "quem saiu do módulo não está mais na lista de quem opera")
    # Quem tem acesso liberado no cadastro mas não foi escolhido para operar
    # volta ao PADRÃO do módulo, que é CONSULTA: melhor olhar e perguntar do
    # que movimentar material alheio por uma liberação padrão.
    check(est.papel_no_estoque(CONSULTA) == est.PAPEL_CONSULTA,
          f"sem vínculo, o servidor volta ao padrão do módulo (veio "
          f"{est.papel_no_estoque(CONSULTA)!r})")
    check(est.pode_movimentar(CONSULTA) is False,
          "e NÃO volta a movimentar estoque")
    check(est.pode_administrar(CONSULTA) is False,
          "nem a administrar o módulo")
    check(est.remover_vinculo(CONSULTA, ator=ADMIN, eh_admin_geral=True)[0] is False,
          "retirar quem não está na lista é recusado")
    check(est.remover_vinculo(CONSULTA, ator=CONSULTA)[0] is False,
          "quem não administra não retira servidor do módulo")


# ============ 8) numeração: item, documento e rollback ============

def teste_numeracao():
    """PREFIXO-0001, contagens separadas e rollback devolvendo o número."""
    print("\n[número] formato, item x documento e rollback devolvendo")
    check(est.montar_numero("IT", 1, 4) == "IT-0001", "monta o número como PREFIXO-0001")
    check(est.montar_numero("it", 42, 6) == "IT-000042",
          "prefixo minúsculo sai em maiúsculo, com os dígitos pedidos")
    check(est.montar_numero("", 7, 4) == "IT-0007", "sem prefixo usa IT")
    check(est.montar_numero("SAUDE", 1, 99) == "SAUDE-00000001",
          f"o número respeita o limite de dígitos (veio "
          f"{est.montar_numero('SAUDE', 1, 99)!r})")
    check(est.normalizar_prefixo("Chamado SP") == "CHAMADOSP",
          f"o prefixo digitado é normalizado (veio "
          f"{est.normalizar_prefixo('Chamado SP')!r})")
    for entrada, esperado in ((3, 3), (8, 8), ("6", 6), (2, 3), (0, 3),
                              (-4, 3), (9, 8), (99, 8), ("lixo", 4), (None, 4)):
        obtido = est.validar_digitos(entrada)
        check(obtido == esperado,
              f"validar_digitos({entrada!r}) = {esperado} (veio {obtido})")

    central = _central()
    # almoxarifado NOVO: a contagem por almoxarifado só começa em zero uma vez
    ok, msg, almoxarifado_id = _almoxarifado_novo(
        "Almoxarifado da numeracao", "Secretaria da Numeracao",
        responsavel_user_nome=OPERADOR)
    check(ok, f"cria o almoxarifado do cenário de numeração ({msg})")
    if not ok:
        return
    almoxarifado = est.obter_almoxarifado(almoxarifado_id)

    # item novo no almoxarifado da secretaria: sequência PRÓPRIA
    est.definir_formato_numero(almoxarifado["id"], prefixo_item="SAUDE",
                               prefixo_documento="SAIDA", digitos=4,
                               ator=ADMIN, eh_admin_geral=True)
    check(est.proximo_numero(almoxarifado["id"], "item") == 0,
          f"almoxarifado novo começa a contagem de item em zero (veio "
          f"{est.proximo_numero(almoxarifado['id'], 'item')})")
    check(est.proximo_numero(almoxarifado["id"], "item") == 0,
          "consultar o próximo número não reserva nada")
    ok, msg, item_id = est.cadastrar_item("Estante Aco Modular", "UN",
                                          almoxarifado_id=almoxarifado["id"],
                                          ator=ADMIN, eh_admin_geral=True)
    check(ok, f"cadastra o item com o prefixo do almoxarifado ({msg})")
    item = est.obter_item(item_id)
    check(item["numero"] == "SAUDE-0001",
          f"o primeiro item do almoxarifado sai SAUDE-0001 (veio "
          f"{item['numero']!r})")
    check(est.proximo_numero(almoxarifado["id"], "item") == 1,
          f"a contagem de item do almoxarifado fica em 1 (veio "
          f"{est.proximo_numero(almoxarifado['id'], 'item')})")
    check(est.proximo_numero(almoxarifado["id"], "documento") == 0,
          "a contagem de DOCUMENTO é separada e ainda está em zero")
    check(est.proximo_numero(central["id"], "item") > 0,
          "e o central conta por conta própria, sem misturar com a secretaria")

    # cadastro repetido não queima número
    est.cadastrar_item("Estante Aco Modular", "UN", almoxarifado_id=almoxarifado["id"],
                       ator=ADMIN, eh_admin_geral=True)
    check(est.proximo_numero(almoxarifado["id"], "item") == 1,
          f"item repetido NÃO queima número do almoxarifado (ficou "
          f"{est.proximo_numero(almoxarifado['id'], 'item')})")

    # documento com o prefixo do almoxarifado
    est.registrar_entrada("Estante Aco Modular", 2, "UN",
                          almoxarifado_id=almoxarifado["id"], ator=OPERADOR)
    documentos = est.listar_documentos(almoxarifado_id=almoxarifado["id"])
    check(bool(documentos), f"a entrada gerou documento (veio {len(documentos)})")
    check(documentos[0]["numero"] == "SAIDA-0001",
          f"o primeiro documento do almoxarifado sai SAIDA-0001 (veio "
          f"{documentos[0]['numero']!r})")
    check(documentos[0]["tipo"] == "entrada", "o documento guarda o tipo (entrada)")
    check(est.proximo_numero(almoxarifado["id"], "documento") == 1,
          "a contagem de documento andou por conta própria")

    # ---- troca de formato NÃO renumera o que já existe ----
    est.definir_formato_numero(almoxarifado["id"], prefixo_item="SAUDE2",
                               digitos=5, ator=ADMIN, eh_admin_geral=True)
    ok, msg, novo_id = est.cadastrar_item("Armarioaco Arquivo", "UN",
                                          almoxarifado_id=almoxarifado["id"],
                                          ator=ADMIN, eh_admin_geral=True)
    check(ok, f"cadastra o item com o formato novo ({msg})")
    check(est.obter_item(novo_id)["numero"] == "SAUDE2-00002",
          f"o item NOVO usa o formato novo (veio "
          f"{est.obter_item(novo_id)['numero']!r})")
    check(est.obter_item(item_id)["numero"] == "SAUDE-0001",
          f"o item ANTIGO mantém o número que já tinha (veio "
          f"{est.obter_item(item_id)['numero']!r})")
    check(est.definir_formato_numero(_ID_QUE_NAO_EXISTE, prefixo_item="X",
                                     ator=ADMIN, eh_admin_geral=True)[0] is False,
          "trocar o formato de almoxarifado inexistente é recusado")
    check(est.definir_formato_numero(almoxarifado["id"], prefixo_item="INVADIDO",
                                     ator=CONSULTA)[0] is False,
          "servidor sem permissão NÃO troca o formato do número")
    check(est.obter_almoxarifado(almoxarifado["id"])["prefixo_item"] == "SAUDE2",
          "e o formato do almoxarifado continua o que o administrador deixou")

    # ---- rollback devolve o número (item e documento) ----
    antes_item = est.proximo_numero(almoxarifado["id"], "item")
    antes_doc = est.proximo_numero(almoxarifado["id"], "documento")
    reservas_item, reservas_doc = [], []
    for _tentativa in range(2):
        conn = est.get_connection()
        try:
            reservas_item.append(est.alocar_numero_na_conexao(
                conn, almoxarifado["id"], "item"))
            reservas_doc.append(est.alocar_numero_na_conexao(
                conn, almoxarifado["id"], "documento"))
            conn.rollback()
        finally:
            conn.close()
    check(reservas_item[0] == reservas_item[1] == antes_item + 1,
          f"reserva de ITEM desfeita devolve o mesmo número ({reservas_item})")
    check(reservas_doc[0] == reservas_doc[1] == antes_doc + 1,
          f"reserva de DOCUMENTO desfeita devolve o mesmo número ({reservas_doc})")
    check(est.proximo_numero(almoxarifado["id"], "item") == antes_item
          and est.proximo_numero(almoxarifado["id"], "documento") == antes_doc,
          "o rollback não queima nenhum dos dois contadores")
    ok, msg, _item_id = est.cadastrar_item("Mesa de Rebadada", "UN",
                                           almoxarifado_id=almoxarifado["id"],
                                           ator=ADMIN, eh_admin_geral=True)
    check(ok and est.obter_item(_item_id)["numero"] == "SAUDE2-00003",
          f"o próximo item usa o número devolvido pelo rollback (veio "
          f"{est.obter_item(_item_id)['numero']!r})")

    # rollback de uma TRANSFERÊNCIA inteira devolve item, saldo e documento
    doc_antes = est.proximo_numero(almoxarifado["id"], "documento")
    est.registrar_entrada("Estante Aco Modular", 4, "UN",
                          almoxarifado_id=almoxarifado["id"], ator=OPERADOR)
    saldo_com_estoque = _saldo(item_id, almoxarifado["id"])
    est.transferir(item_id, 1, central["id"], almoxarifado_origem_id=almoxarifado["id"],
                   ator=OPERADOR)
    check(_saldo(item_id, almoxarifado["id"]) == saldo_com_estoque - 1,
          "a transferência tirou do almoxarifado de origem")
    # devolve tudo ao almoxarifado para o resto do teste ficar previsível
    est.transferir(item_id, 1, almoxarifado["id"],
                   almoxarifado_origem_id=central["id"], ator=OPERADOR)
    check(_saldo(item_id, almoxarifado["id"]) == saldo_com_estoque,
          "e a devolução repõe o saldo")
    check(est.proximo_numero(central["id"], "documento") > doc_antes,
          "o central contou o documento da transferência de volta")


# ============ 9) histórico e visão geral ============

def teste_historico_e_visao():
    """Movimentações com documento e a visão geral do painel de administração."""
    print("\n[histórico] movimentação completa e visão geral do módulo")
    movimentos = est.listar_movimentos(limite=500)
    check(len(movimentos) > 0, f"o histórico tem movimientos (veio {len(movimentos)})")
    check(all(m["descricao"] for m in movimentos),
          "todo movimento sabe o que foi movimentado")
    check(all(m["data_movimento"] for m in movimentos),
          "todo movimento tem data de negócio")
    check(all(m["tipo"] in est.TIPOS_MOVIMENTO for m in movimentos),
          "todo movimento tem um tipo do vocabulário do módulo")
    com_doc = [m for m in movimentos if m["documento_numero"]]
    check(len(com_doc) == len(movimentos),
          f"todo movimento está amarrado a um documento ({len(com_doc)} de "
          f"{len(movimentos)})")
    entradas = [m for m in movimentos if m["tipo"] == "entrada"
                and m["nota_empenho"]]
    check(bool(entradas), "a entrada guarda a nota de empenho que a originou")

    # o filtro por almoxarifado devolve o que envolveu ele
    central = _central()
    do_central = est.listar_movimentos(almoxarifado_id=central["id"], limite=500)
    check(len(do_central) > 0, "o histórico do estoque central não está vazio")
    check(all(m["almoxarifado_origem_id"] == central["id"]
              or m["almoxarifado_destino_id"] == central["id"]
              for m in do_central),
          "e traz só o que passou por ele")

    visao = est.visao_geral()
    for chave in ("almoxarifados", "itens", "disponivel", "em_uso", "parado",
                  "pedidos", "tarefas", "convites", "servidores", "documentos",
                  "dias_parado", "por_almoxarifado"):
        check(chave in visao, f"a visão geral tem a chave {chave!r}")
    check(visao["itens"] > 0, f"a visão geral conta itens (veio {visao['itens']})")
    check(visao["almoxarifados"] >= 2,
          f"a visão geral conta os almoxarifados de secretaria (veio "
          f"{visao['almoxarifados']})")
    check(visao["dias_parado"] == est.dias_parado(),
          f"a visão geral usa o prazo de item parado configurado ({visao['dias_parado']})")
    check(len(visao["por_almoxarifado"]) >= 3,
          f"a visão geral traz o painel de cada almoxarifado (veio "
          f"{len(visao['por_almoxarifado'])})")
    for linha in visao["por_almoxarifado"]:
        check(all(k in linha for k in ("nome", "recebido", "disponivel",
                                       "em_uso", "parado")),
              f"o painel de {linha['nome']!r} tem os quatro números")


# ============ 10) limpeza ============

def teste_limpeza():
    """Depois do teste, o banco não tem almoxarifado, item nem usuário de teste."""
    print("\n[limpeza] nada do teste sobrou no banco")
    logins = tuple(login for login, _nome in USUARIOS_TESTE)
    conexao = None
    try:
        conexao = est.get_connection()
        vinculos = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_usuario "
                                   "WHERE user_nome", logins)
        almoxarifados = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_almoxarifado "
                                        "WHERE responsavel_user_nome", logins)
        itens = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_item "
                                "WHERE criado_por", logins)
        documentos = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_documento "
                                     "WHERE criado_por", logins)
        movimentos = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_movimento "
                                     "WHERE usuario_actor", logins)
        entregas = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_entrega "
                                   "WHERE criado_por", logins)
        tarefas = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_tarefa "
                                   "WHERE criado_por", logins)
        convites = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_convite "
                                   "WHERE convidado_user_nome", logins)
        convites_por = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_convite "
                                        "WHERE convidado_por", logins)
        recolhimentos = _contar(conexao, "SELECT COUNT(*) FROM tb_estoque_recolhimento "
                                        "WHERE solicitante_user_nome", logins)
        almox_com_responsavel = _contar(
            conexao, "SELECT COUNT(*) FROM tb_estoque_almoxarifado "
            "WHERE responsavel_user_nome", logins)
        orfas = 0
        # cada tabela aponta para o almoxarifado por uma coluna própria (o
        # convite aponta para a TAREFA, não para o almoxarifado)
        for tabela, coluna in (("tb_estoque_saldo", "almoxarifado_id"),
                               ("tb_estoque_item", "almoxarifado_id"),
                               ("tb_estoque_documento", "almoxarifado_id"),
                               ("tb_estoque_movimento", "almoxarifado_origem_id"),
                               ("tb_estoque_movimento", "almoxarifado_destino_id"),
                               ("tb_estoque_entrega", "almoxarifado_id"),
                               ("tb_estoque_recolhimento", "almoxarifado_id"),
                               ("tb_estoque_tarefa", "almoxarifado_id"),
                               ("tb_estoque_convite", "tarefa_id"),
                               ("tb_estoque_sequencia", "almoxarifado_id")):
            if coluna == "tarefa_id":
                linha = conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela} WHERE {coluna} NOT IN "
                    f"(SELECT id FROM tb_estoque_tarefa)").fetchone()
            else:
                linha = conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela} WHERE {coluna} IS NOT NULL "
                    f"AND {coluna} NOT IN "
                    f"(SELECT id FROM tb_estoque_almoxarifado)").fetchone()
            orfas += int(linha[0] or 0) if linha else 0
        central = conexao.execute("SELECT COUNT(*) FROM tb_estoque_almoxarifado "
                                  "WHERE central=1").fetchone()
        linha_saldo = conexao.execute(
            "SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_saldo "
            "WHERE almoxarifado_id=(SELECT id FROM tb_estoque_almoxarifado "
            "WHERE central=1)").fetchone()
        saldo_central = linha_saldo[0] if linha_saldo else 0
    finally:
        if conexao is not None:
            conexao.close()
    check(vinculos == 0, f"nenhum vínculo de teste ficou (veio {vinculos})")
    check(almoxarifados == 0, f"nenhum almoxarifado de teste ficou (veio {almoxarifados})")
    check(itens == 0, f"nenhum item criado pelo teste ficou (veio {itens})")
    check(documentos == 0, f"nenhum documento de teste ficou (veio {documentos})")
    check(movimentos == 0, f"nenhum movimento de teste ficou (veio {movimentos})")
    check(entregas == 0, f"nenhuma entrega de teste ficou (veio {entregas})")
    check(tarefas == 0, f"nenhuma tarefa de teste ficou (veio {tarefas})")
    check(convites == 0 and convites_por == 0,
          f"nenhum convite de teste ficou (veio {convites} / {convites_por})")
    check(recolhimentos == 0, f"nenhum recolhimento de teste ficou (veio {recolhimentos})")
    check(almox_com_responsavel == 0, "e nenhum almoxarifado ficou com o "
                                      "responsável de teste")
    check(orfas == 0, f"nenhuma linha órfã ficou (veio {orfas})")
    check(int((central or [0])[0] or 0) == 1,
          "o estoque central continua lá — ele é fixo")
    check(_arred(saldo_central) == 0,
          f"e o central volta ao saldo zero para a próxima rodada (ficou "
          f"{_arred(saldo_central)})")

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
    check(usuarios == 0, f"nenhum usuário de teste ficou no cadastro (veio {usuarios})")
    check(acessos == 0 and telefones == 0,
          f"nem o vínculo de acesso ficou (veio {acessos} / {telefones})")


def _arred(valor):
    return round(float(valor or 0), 3)


def main():
    print("\n=== estoque: almoxarifado, entrada, em uso, recolhimento e número ===")
    try:
        est.init_db()
        _zerar_estoque_central()
        _criar_usuarios()
        _vincular_papeis()
        teste_almoxarifados()
        teste_entrada_e_transferencia()
        teste_entre_almoxarifados_e_devolucao()
        teste_em_uso_e_parado()
        teste_recolhimento()
        teste_tarefa_deposito()
        teste_papeis()
        teste_numeracao()
        teste_historico_e_visao()
    except Exception as e:
        import traceback
        traceback.print_exc()
        _FALHAS.append(f"excecao: {e}")
    finally:
        _zerar_estoque_central()
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
