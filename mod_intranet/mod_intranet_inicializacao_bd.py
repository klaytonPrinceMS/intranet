"""Bootstrap agregado dos bancos (PLANO.md, Fase 0/1).

Idempotente: cria tabelas e o usuário master apenas quando não existem.
NUNCA apaga dados. Reutilizável no boot (main.py) e futuramente por CLI.

ATENÇÃO À ORDEM: `mod_gest_cad_usuario/manipulador_bd.py` executa `init_db()`
no nível do módulo (import dispara a criação + seed). Como esse `init_db`
escreve em `tb_config` (banco central), o banco central DEVE ser criado
ANTES de importar aquele módulo — caso contrário falha com
"no such table: tb_config" em instalação limpa.
"""

def inicializar_bancos():
    from mod_intranet.conexao_bd import init_db as init_central
    from mod_intranet.manipulador_bd import garantir_rastreabilidade

    # 1) Banco central primeiro (tb_auditoria, tb_config, tb_sessoes)
    init_central()
    garantir_rastreabilidade()

    # 1.1) Banco exclusivo de auditoria (db_mod_auditoria.db), tabela por
    # módulo. Inicializa o banco de auditoria e, uma única vez, migra os
    # registros antigos da tb_auditoria central (legado) para as novas
    # tabelas por módulo.
    from mod_auditoria.manipulador_bd import init_db_auditoria, migrar_dados_existentes
    init_db_auditoria()
    try:
        migrar_dados_existentes()
    except Exception:
        pass

    # 2) Demais módulos (cada import pode disparar init_db no nível do módulo)
    from mod_blog.manipulador_bd import init_db as init_blog
    init_blog()           # db_mod_blog.db

    from mod_gest_cad_usuario.manipulador_bd import init_db as init_users
    init_users()          # db_mod_gest_cad_usuario.db + seed master/master

    from mod_edit_pdf.manipulador_bd import init_db_pdf
    init_db_pdf()         # db_mod_edit_pdf.db

    from mod_renomear_empenho.manipulador_bd import init_db_empenho
    init_db_empenho()     # db_mod_renomear_empenho.db

    from mod_solicita_impressao.manipulador_bd import init_db as init_solicita
    init_solicita()       # db_mod_solicita_impressao.db


if __name__ == "__main__":
    inicializar_bancos()
