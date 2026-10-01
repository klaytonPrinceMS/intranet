"""Aggregated database bootstrap (PLANO.md, Phase 0/1).

Bootstrap agregado dos bancos (PLANO.md, Fase 0/1).

Idempotente: cria tabelas e o usuário master apenas quando não existem.
NUNCA apaga dados. Reutilizável no boot (main.py) e futuramente por CLI.

ATENÇÃO À ORDEM: `mod_gest_cad_usuario/db_manipulador.py` executa `init_db()`
no nível do módulo (import dispara a criação + seed). Como esse `init_db`
escreve em `tb_config` (banco central), o banco central DEVE ser criado
ANTES de importar aquele módulo — caso contrário falha com
"no such table: tb_config" em instalação limpa.
"""

def inicializar_bancos():
    # 0) Garante TODOS os bancos de módulo ANTES dos `init_db`: no SQLite
    # cria o ARQUIVO apenas quando não existe; no Postgres cria o DATABASE
    # `db_mod_<chave>` de cada módulo (garantir_bancos → garantir_bancos_postgres).
    # O schema de cada banco entra pelos `init_db` abaixo (CREATE TABLE IF NOT EXISTS).
    from mod_intranet.repositorio import garantir_bancos
    garantir_bancos()

    from mod_intranet.bd_conexao import init_db as init_central
    from mod_intranet.bd_manipulador import garantir_rastreabilidade

    # 1) Banco central primeiro (tb_auditoria, tb_config, tb_sessoes) —
    # com os databases já materializados no backend ativo.
    init_central()
    garantir_rastreabilidade()

    # 1.1) Banco exclusivo de auditoria (db_mod_auditoria.db), tabela por
    # módulo. Inicializa o banco de auditoria e, uma única vez, migra os
    # registros antigos da tb_auditoria central (legado) para as novas
    # tabelas por módulo.
    from mod_auditoria.bd_manipulador import init_db_auditoria, migrar_dados_existentes
    init_db_auditoria()
    try:
        migrar_dados_existentes()
    except Exception:
        pass

    # 2) Demais módulos (cada import pode disparar init_db no nível do módulo)
    from mod_blog.bd_manipulador import init_db as init_blog
    init_blog()           # db_mod_blog.db

    from mod_gest_cad_usuario.bd_manipulador import init_db as init_users
    init_users()          # db_mod_gest_cad_usuario.db + seed master/master

    # 2.1) FOLHA DE SERVIDORES — RELIDA EM TODO BOOT (01/10/2026)
    #
    # Fica AQUI, e não no `main.py`, por um motivo que a ordem acima já
    # impõe: a folha escreve em `tb_usuarios`, que só existe depois do
    # `init_users()` da linha de cima. Colocar a carga no inicializador
    # garante que o cadastro de servidores nasce JUNTO com o banco.
    #
    # ANTES (30/09) isto rodava só quando `primeira_carga_pendente()` era
    # verdadeiro — isto é, quando o cadastro não tinha NENHUM servidor com
    # vínculo. Resolvia o primeiro boot e abria um buraco depois dele: a
    # folha é a fonte da verdade e muda todo mês, então servidor novo,
    # mudança de vínculo, férias, licença-maternidade, demissão e salário
    # novo entravam no arquivo e NÃO chegavam ao banco. Ninguém percebia:
    # o administrador só descobria o cadastro velho quando alguém ligava
    # reclamando de um servidor que já tinha saído.
    #
    # AGORA a carga roda em TODO boot. O que segura o custo é a trava do
    # arquivo, dentro de `carga_automatica`: folha inalterada sai em menos
    # de 1 s sem tocar em linha nenhuma. Folha mudada roda a sincronização
    # inteira — medido em 01/10/2026, **~450 ms por servidor** na criação
    # (o grosso é a auditoria, que grava ~3 linhas por servidor), o que dá
    # **~5 min para ~650 servidores**. A janela de ~25–35 min que esta
    # mensagem anunciava antes era de antes do banco de auditoria reutilizar
    # a conexão de gravação (280 ms -> 2,4 ms por registro).
    #
    # Por que no BOOT e não só no agendador das 03:00: é o servidor que o
    # administrador reinicia quando algo está errado, e cadastro velho é
    # justamente o sintoma que ele não sabe diagnosticar. Reler a folha ao
    # subir diz qual é o estado real antes do primeiro login.
    #
    # Fail-soft de propósito: cadastro desatualizado é defeito, mas derrubar
    # o boot por causa disso é pior — o sistema sobe, fica com a folha
    # anterior e o log diz exatamente por quê.
    try:
        from mod_gest_cad_usuario.carga_folha import (
            carga_automatica, primeira_carga_pendente,
        )
        if primeira_carga_pendente():
            # O número é medido, não estimado: quem está olhando este console
            # precisa saber que vai esperar, e não vai achar que o servidor
            # travou. "Não responsivo até o fim" é o sintoma real.
            print("[carga_folha] cadastro sem servidores — primeira carga no "
                  "boot. Leva ~5 min (medido 01/10/2026, ~450 ms por servidor "
                  "em ~650 servidores); o servidor NÃO responde até terminar. "
                  "Isso só acontece no primeiro boot de um banco recém-criado.",
                  flush=True)
        else:
            print("[carga_folha] relendo a folha no boot — servidor novo, "
                  "vínculo, férias, licença ou salário novo entram no "
                  "cadastro. Folha inalterada sai em menos de 1 s; folha "
                  "mudada leva ~5 min em ~650 servidores.", flush=True)

        # A carga é a MESMA nos dois casos. A diferença é só o que se diz
        # antes dela — porque a trava do arquivo (`carga_automatica`) resolve
        # sozinha quando não há o que fazer, e inventar um caminho separado
        # para "só revalidar" seria duplicar a mesma travessia.
        _rel = carga_automatica()
        _erros = _rel.get("erros") or []
        if _rel.get("rodou"):
            print(f"[carga_folha] folha sincronizada: "
                  f"{_rel.get('total', 0)} servidor(es) lido(s), competencia "
                  f"{_rel.get('competencia') or '?'} — "
                  f"{_rel.get('criados', 0)} criado(s), "
                  f"{_rel.get('bloqueados', 0)} bloqueado(s) "
                  f"(ferias/licenca/demissao), "
                  f"{_rel.get('desbloqueados', 0)} desbloqueado(s), "
                  f"{_rel.get('nomes_corrigidos', 0)} nome(s) corrigido(s), "
                  f"{_rel.get('marcados', 0)} com pendencia de setor/cargo, "
                  f"{_rel.get('inalterados', 0)} sem mudanca.",
                  flush=True)
            if _erros:
                print(f"[carga_folha] {len(_erros)} erro(s) na carga — falha "
                      f"nao impede o boot; veja o log do modulo. Primeiro: "
                      f"{str(_erros[0])[:160]}", flush=True)
        else:
            print(f"[carga_folha] nada a sincronizar: "
                  f"{_rel.get('motivo') or 'sem motivo'}.", flush=True)
    except Exception as _e_folha:
        print(f"[carga_folha] aviso: leitura da folha no boot falhou "
              f"(fail-soft): {_e_folha}", flush=True)

    from mod_edit_pdf.bd_manipulador import init_db_pdf
    init_db_pdf()         # db_mod_edit_pdf.db

    from mod_renomear_empenho.bd_manipulador import init_db_empenho
    init_db_empenho()     # db_mod_renomear_empenho.db

    from mod_solicita_impressao.bd_manipulador import init_db as init_solicita
    init_solicita()       # db_mod_solicita_impressao.db

    from mod_tecnico.bd_manipulador import init_db as init_tecnico
    init_tecnico()        # db_mod_tecnico.db

    from mod_filas.bd_manipulador import init_db as init_filas
    init_filas()          # db_mod_filas.db

    from mod_lista_telefonica.bd_manipulador import init_db as init_lista
    init_lista()          # db_mod_lista_telefonica.db

    from mod_agregador_noticias.bd_manipulador import init_db as init_agregador
    init_agregador()      # db_mod_agregador_noticias.db

    from mod_os.bd_manipulador import init_db as init_os
    init_os()             # db_mod_os.db

    from mod_estoque.bd_manipulador import init_db as init_estoque
    init_estoque()        # db_mod_estoque.db

    # Dados Abertos entra POR ÚLTIMO de propósito: o card de servidores lê a
    # folha pela fachada, e a folha só está completa depois que os módulos
    # acima já gravaram o cadastro e o organograma. Sem essa ordem, a primeira
    # tela de dados abertos abriria com o organograma ainda vazio.
    from mod_dados_abertos.bd_manipulador import init_db as init_dados_abertos
    init_dados_abertos()  # db_mod_dados_abertos.db


if __name__ == "__main__":
    inicializar_bancos()
