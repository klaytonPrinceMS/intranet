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
    from mod_auditoria.db_manipulador import init_db_auditoria, migrar_dados_existentes
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

    from mod_edit_pdf.bd_manipulador import init_db_pdf
    init_db_pdf()         # db_mod_edit_pdf.db

    from mod_renomear_empenho.bd_manipulador import init_db_empenho
    init_db_empenho()     # db_mod_renomear_empenho.db

    from mod_solicita_impressao.bd_manipulador import init_db as init_solicita
    init_solicita()       # db_mod_solicita_impressao.db


if __name__ == "__main__":
    inicializar_bancos()
