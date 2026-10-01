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

    # 2.1) PRIMEIRA CARGA DA FOLHA DE SERVIDORES (30/09/2026)
    #
    # Fica AQUI, e não no `main.py`, por um motivo que a ordem acima já
    # impõe: a folha escreve em `tb_usuarios`, que só existe depois do
    # `init_users()` da linha de cima. Colocar a carga no inicializador
    # garante que o cadastro de servidores nasce JUNTO com o banco — um
    # banco recém-criado já entra com a folha dentro, e não com o vazio
    # esperando o agendador das 03:00 rodar.
    #
    # `primeira_carga_pendente()` é o que impede o custo a cada boot. E o
    # custo é grande: **medido em 31/10/2026, ~25–35 minutos** para ~1.165
    # servidores — dos quais ~100 s são a coleta do portal (quase 50
    # requisições) e o resto é gravação, a ~2 s por servidor. Pagar isso em
    # todo reinício tornaria o servidor impraticável de subir. Ela pergunta
    # ao BANCO ("já tem servidor com vínculo?"), e não a um arquivo de
    # marcador — porque o banco é o que se apaga e se recria, e um
    # marcador sobreviveria à dele, deixando a instalação com cadastro vazio
    # e carga pulada, que é o estado ruim que este passo existe para evitar.
    #
    # Fail-soft de propósito: banco de servidores vazio é defeito, mas
    # derrubar o boot por causa disso é pior — o sistema sobe, fica sem a
    # folha e o log diz exatamente por quê.
    try:
        from mod_gest_cad_usuario.carga_folha import (
            carga_automatica, primeira_carga_pendente,
        )
        if primeira_carga_pendente():
            # O número é medido, não estimado: quem está olhando este console
            # precisa saber que vai esperar meia hora, e não vai achar que o
            # servidor travou. "Não responsivo até o fim" é o sintoma real.
            print("[carga_folha] cadastro sem servidores — primeira carga no "
                  "boot. Leva ~25 a 35 min (medido em 31/10/2026, ~1.165 "
                  "servidores); o servidor NÃO responde até terminar. Isso só "
                  "acontece no primeiro boot de um banco recém-criado.",
                  flush=True)
            _rel = carga_automatica()
            _n = _rel.get("criados", 0)
            if _rel.get("rodou"):
                print(f"[carga_folha] primeira carga concluida: {_n} "
                      f"servidor(es) criado(s), "
                      f"{_rel.get('secretarias_criadas', 0)} secretaria(s) — "
                      f"competencia {_rel.get('competencia') or '?'}", flush=True)
            else:
                print(f"[carga_folha] primeira carga NAO rodou: "
                      f"{_rel.get('motivo') or 'sem motivo'}. O sistema sobe "
                      f"sem a folha e o agendador das 03:00 tenta de novo.",
                      flush=True)
        else:
            print("[carga_folha] folha ja carregada — boot nao recoleta.",
                  flush=True)
    except Exception as _e_folha:
        print(f"[carga_folha] aviso: primeira carga falhou (fail-soft): "
              f"{_e_folha}", flush=True)

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


if __name__ == "__main__":
    inicializar_bancos()
