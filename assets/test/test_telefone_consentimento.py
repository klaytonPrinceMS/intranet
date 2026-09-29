"""Consentimento de telefone e cadastro de primeiro acesso (27/09/2026).

Cobre a regra que a prefeitura definiu para a lista telefônica:

    - fixo da prefeitura     -> publica SEMPRE (linha institucional)
    - celular da prefeitura  -> publica só se o servidor autorizar
    - celular particular       -> NUNCA publica
    - residencial             -> NUNCA publica

E o ciclo da pendência: todo servidor nasce com `telefone_pendente=1` (o
portal da transparência não publica ramal), e a pendência só baixa depois
que ele mesmo registra os telefones.

Executa contra um banco TEMPORÁRIO próprio: cria os usuários com prefixo de
teste e apaga tudo no fim. Não toca nos servidores reais.

Execute: .venv/bin/python assets/test/test_telefone_consentimento.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from mod_gest_cad_usuario import bd_manipulador as bd  # noqa: E402

_OK = 0
_FALHAS = []


def check(cond, msg):
    global _OK
    if cond:
        _OK += 1
        print(f"  ok   {msg}")
    else:
        _FALHAS.append(msg)
        print(f"  FALHA {msg}")


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t or "")
                   if not unicodedata.combining(c)).lower()


def teste_regra_publicavel():
    """A regra pura, sem banco: é o coração do consentimento."""
    print("\n[telefone_e_publicavel] a regra de publicação")
    p = bd.telefone_e_publicavel
    check(p("empresa", "fixo", False) is True,
          "fixo da prefeitura publica mesmo sem marcar")
    check(p("empresa", "fixo", True) is True,
          "fixo da prefeitura publica marcando")
    check(p("empresa", "celular", True) is True,
          "celular da prefeitura publica QUANDO o servidor marca")
    check(p("empresa", "celular", False) is False,
          "celular da prefeitura NAO publica sem autorizacao")
    check(p("pessoal", "celular", True) is False,
          "celular particular NUNCA publica, nem marcando")
    check(p("pessoal", "fixo", True) is False,
          "residencial NUNCA publica, nem marcando")
    check(p("pessoal", "fixo", False) is False,
          "residencial nao publica")
    # entrada corrompida tem de cair no lado SEGURO (nao publicar)
    check(p("xxx", "xxx", False) is False,
          "papel/tipo corrompido sem consentimento nao publica")
    check(p("xxx", "xxx", True) is True,
          "papel/tipo corrompido COM consentimento publica como empresa")


def teste_pendencia_e_registro():
    """Ciclo da pendência e gravação do primeiro acesso."""
    print("\n[primeiro acesso] pendencia e gravacao dos telefones")
    nome = "TESTE_TEL_001"
    ok, msg = bd.criar_usuario("teste", nome, "123456", perfil="comum",
                               nome_completo="Servidor de Teste Telefone")
    check(ok, f"criou o usuario de teste ({msg})")
    if not ok:
        return
    try:
        check(bd.telefone_pendente(nome) is True,
              "servidor nasce com a pendencia de telefone ligada")

        # 1) cadastro vazio -> recusado, com mensagem que diz o que fazer
        ok, msg, _d = bd.registrar_contatos_primeiro_acesso(nome, nome, [])
        check(ok is False, "recusa cadastro sem nenhum telefone")
        check("telefone" in (msg or "").lower(),
              f"a recusa explica o motivo ({msg!r})")
        check(bd.telefone_pendente(nome) is True,
              "pendencia continua ligada depois da recusa")

        # 2) os quatro campos do formulário, como a tela manda
        contatos = [
            {"numero": "(35) 98888-1111", "papel": "pessoal",
             "tipo": "celular", "visivel": True},     # nao pode publicar
            {"numero": "(35) 98888-2222", "papel": "empresa",
             "tipo": "celular", "visivel": False},    # nao autorizou
            {"numero": "(00) 3591-5100", "papel": "empresa",
             "tipo": "fixo", "visivel": True},        # publica sozinho
            {"numero": "(00) 3800-3030", "papel": "pessoal",
             "tipo": "fixo", "visivel": False},       # residencial
        ]
        ok, msg, _d = bd.registrar_contatos_primeiro_acesso(nome, nome, contatos)
        check(ok, f"grava os quatro telefones ({msg})")
        check(bd.telefone_pendente(nome) is False,
              "pendencia BAIXA depois do cadastro")

        todos = bd.listar_telefones(nome)
        check(len(todos) == 4, f"guardou os 4 telefones (veio {len(todos)})")

        publicos = bd.listar_telefones(nome, apenas_empresa=True)
        numeros = sorted(t[2] for t in publicos)
        # Guardado só com dígitos, DDD junto: "(00) 3591-5100" vira
        # "0035915100". A forma canônica evita que o mesmo ramal digitado de
        # dois jeitos vire dois contatos. Quem exibe.formata para leitura
        # ("(00) 3591-5100") e o `tel:` do link monta o número internacional.
        check(numeros == ["0035915100"],
              f"sai na lista SO o fixo da prefeitura (veio {numeros})")

        principal = bd.telefone_empresa_principal(nome)
        check(principal == "0035915100",
              f"telefone principal e o fixo institucional (veio {principal})")

        # 3) idempotencia: rodar de novo nao duplica
        bd.registrar_contatos_primeiro_acesso(nome, nome, contatos)
        check(len(bd.listar_telefones(nome)) == 4,
              "reenviar os mesmos telefones nao duplica")

        # 4) quem so tem celular particular nao entra na lista
        nome2 = "TESTE_TEL_002"
        ok, _ = bd.criar_usuario("teste", nome2, "123456",
                                 nome_completo="Somente Particular")
        if ok:
            bd.registrar_contatos_primeiro_acesso(nome2, nome2, [
                {"numero": "00 98888-3333", "papel": "pessoal",
                 "tipo": "celular", "visivel": True}])
            check(bd.telefone_empresa_principal(nome2) is None,
                  "quem so tem celular particular fica SEM numero na lista")
            check(bd.listar_telefones(nome2, apenas_empresa=True) == [],
                  "e nao tem telefone publicavel nenhum")

        # 5) o lote bate com o individual (o N+1 foi removido)
        lote = bd.telefones_publicaveis_em_lote([nome, nome2, "NAO_EXISTE_9"])
        check(lote.get(nome) == "0035915100",
              f"lote traz o fixo do servidor 1 ({lote.get(nome)})")
        check(nome2 not in lote, "lote NAO traz quem so tem particular")
        check("NAO_EXISTE_9" not in lote, "lote ignora usuario inexistente")
    finally:
        _limpar(nome, "TESTE_TEL_002")


def teste_ponte_da_lista():
    """A ponte que a lista telefônica lê, com o consentimento já aplicado."""
    print("\n[ponte da lista] o que a lista telefonica enxerga")
    nome = "TESTE_TEL_003"
    ok, _ = bd.criar_usuario("teste", nome, "123456",
                             nome_completo="Ana Beatriz Souza Rocha")
    if not ok:
        _FALHAS.append("nao criou TESTE_TEL_003")
        return
    try:
        bd.definir_dados_funcionais("teste", nome, unidade="Secretaria de Saude",
                                    cargo="Agente de Saude")
        bd.registrar_contatos_primeiro_acesso(nome, nome, [
            {"numero": "00 3591-5150", "papel": "empresa",
             "tipo": "fixo", "visivel": True}])
        from mod_gest_cad_usuario import leitura_lista
        item = leitura_lista.obter_usuario_para_lista(nome)
        check(item is not None, "a ponte encontra o usuario")
        if item:
            check(item["nome_exibicao"] == "Ana Rocha",
                  f"mostra primeiro + ultimo (veio {item['nome_exibicao']!r})")
            check(item["telefone"] == "0035915150",
                  f"traz o fixo liberado (veio {item['telefone']!r})")
            check(item["cargo"] == "Agente de Saude", "traz o cargo")
        # quem esta bloqueado nao entra no diretório
        bd.bloquear_usuario("teste", nome, True)
        achados = leitura_lista.buscar_usuarios_para_lista("TESTE_TEL_003")
        check(achados == [], "usuario bloqueado NAO aparece na busca da lista")
        todos = leitura_lista.listar_para_lista_telefonica()
        check(nome not in {t["user_nome"] for t in todos},
              "usuario bloqueado NAO entra na lista de sincronizacao")
    finally:
        _limpar(nome)



def teste_recado_e_faixas():
    """Recado, faixas e a liberação temporária de 4 dias."""
    print("\n[recado e faixas] numero do setor e faixa da prefeitura")
    from mod_intranet import telefone_faixas as fx
    nome = "TESTE_RECADO"

    def limpar():
        conn = bd.get_connection()
        try:
            for t in ("tb_telefone_usuario", "tb_acesso_usuario", "tb_usuarios"):
                conn.execute(f"DELETE FROM {t} WHERE user_nome=?", (nome,))
            conn.commit()
        finally:
            conn.close()

    limpar()
    ok, msg = bd.criar_usuario("teste", nome, "123456",
                               nome_completo="Coletor Lixo Recado")
    check(ok, f"criou o usuario de teste ({msg})")
    if not ok:
        return
    try:
        # 1) o FIXO DA PREFEITURA e o que libera o acesso; celular nao
        avalio = bd.avaliar_telefones_primeiro_acesso([
            {"numero": "00988881111", "papel": "pessoal", "tipo": "celular"}])
        check(not avalio["tem_da_prefeitura"],
              "celular particular NAO satisfaz a exigencia da prefeitura")
        ok, msg, _d = bd.registrar_contatos_primeiro_acesso("teste", nome, [
            {"numero": "00988881111", "papel": "pessoal", "tipo": "celular"}])
        check(ok is False, "recusa sem telefone da prefeitura e sem liberacao")

        # 2) fixo de RECADO do setor satisfaz
        avalio = bd.avaliar_telefones_primeiro_acesso([
            {"numero": "0035915300", "papel": "empresa", "tipo": "fixo",
             "recado": True}])
        check(avalio["tem_da_prefeitura"],
              "fixo do setor marcado como recado satisfaz a exigencia")

        # 3) numero FORA da faixa e avisado, nao bloqueado
        fx.salvar_faixas("teste", [
            {"inicio": "0035915101", "fim": "0035915199", "descricao": "Central"}])
        avalio = bd.avaliar_telefones_primeiro_acesso([
            {"numero": "0035999999", "papel": "empresa", "tipo": "fixo"}])
        check(bool(avalio["fora_da_faixa"]),
              "numero fora da faixa e sinalizado")
        ok, msg, det = bd.registrar_contatos_primeiro_acesso("teste", nome, [
            {"numero": "0035999999", "papel": "empresa", "tipo": "fixo"}])
        check(ok, f"numero fora da faixa SALVA (so avisa): {msg}")

        # 4) multiplas faixas cadastradas pelo admin
        ok, _m = fx.salvar_faixas("teste", [
            {"inicio": "0035915101", "fim": "0035915199", "descricao": "Central"},
            {"inicio": "0035915300", "fim": "0035915350", "descricao": "Garagem"}])
        check(ok, "admin cadastra MAIS DE UMA faixa")
        for num, desc in (("0035915150", "Central"), ("0035915320", "Garagem")):
            dentro, f = fx.numero_dentro_da_faixa(num)
            check(dentro and f["descricao"] == desc,
                  f"{num} cai na faixa {desc}")
        fx.salvar_faixas("teste", [])

        # 5) liberacao TEMPORARIA de 4 dias
        limpar()
        bd.criar_usuario("teste", nome, "123456",
                         nome_completo="Servador Sem Numero")
        ok, msg, det = bd.registrar_contatos_primeiro_acesso("teste", nome, [
            {"numero": "00988881111", "papel": "pessoal", "tipo": "celular"}],
            liberacao_provisoria=True)
        check(ok, f"paliativo libera o acesso: {msg}")
        check(det["provisorio"] is True, "marcado como liberacao provisoria")
        info = bd.informacao_acesso_provisorio(nome)
        check(info["provisorio"] and not info["vencido"],
              f"prazo valido de {info['dias_restantes']} dia(s)")
        check(info["dias_restantes"] <= bd.DIAS_LIBERACAO_PROVISORIA,
              f"prazo de no maximo {bd.DIAS_LIBERACAO_PROVISORIA} dias")
        check(bd.listar_telefones(nome, apenas_empresa=True) == [],
              "particular nao entra na lista mesmo no paliativo")

        # 6) prazo vencido -> bloqueio automatico no login
        conn = bd.get_connection()
        conn.execute("UPDATE tb_usuarios SET provisorio_ate='2020-01-01 00:00:00' "
                     "WHERE user_nome=?", (nome,))
        conn.commit()
        conn.close()
        check(bd.bloqueio_provisorio_pendente(nome),
              "prazo vencido e detectado")
        from mod_intranet import autenticacao as aut
        ok, msg = aut.autenticar(nome, "123456")
        check(ok is False, f"login bloqueado apos o prazo: {msg!r}")
        conn = bd.get_connection()
        ativo = conn.execute("SELECT user_ativo FROM tb_usuarios WHERE user_nome=?",
                             (nome,)).fetchone()[0]
        conn.commit()
        conn.close()
        check(ativo == 0, "conta ficou bloqueada no banco")

        # 7) DTI so libera em definitivo com telefone da prefeitura
        ok, msg = bd.liberar_acesso_definitivo("dti", nome)
        check(ok is False, f"DTI nao libera sem telefone da prefeitura: {msg!r}")
        conn = bd.get_connection()
        conn.execute("INSERT INTO tb_telefone_usuario "
                     "(user_nome,numero,papel,tipo,principal,visivel,recado) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (nome, "0035915300", "empresa", "fixo", 0, 1, 1))
        conn.commit()
        conn.close()
        ok, msg = bd.liberar_acesso_definitivo("dti", nome)
        check(ok, f"DTI libera depois de cadastrar o telefone: {msg}")
        info = bd.informacao_acesso_provisorio(nome)
        check(not info["provisorio"], "liberacao virou definitiva")
    finally:
        limpar()


def _limpar(*nomes):
    conn = bd.get_connection()
    try:
        for n in nomes:
            conn.execute("DELETE FROM tb_telefone_usuario WHERE user_nome=?", (n,))
            conn.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=?", (n,))
            conn.execute("DELETE FROM tb_usuarios WHERE user_nome=?", (n,))
        conn.commit()
    finally:
        conn.close()
    for n in nomes:
        try:
            from mod_intranet.autenticacao import marcar_trocar_senha
            marcar_trocar_senha(n, False)
        except Exception:
            pass


def main():
    print("\n=== telefone: consentimento e primeiro acesso ===")
    try:
        bd.init_db()
        teste_regra_publicavel()
        teste_pendencia_e_registro()
        teste_ponte_da_lista()
        teste_recado_e_faixas()
    except Exception as e:
        import traceback
        traceback.print_exc()
        _FALHAS.append(f"excecao: {e}")
    print(f"\n{_OK} ok, {len(_FALHAS)} falha(s)")
    for f in _FALHAS:
        print(f"  - {f}")
    return 1 if _FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
