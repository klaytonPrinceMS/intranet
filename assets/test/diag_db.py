import sqlite3, os

for db in ['db_mod_gest_cad_usuario.db', 'db_mod_intranet.db']:
    print(db, 'existe' if os.path.exists(db) else 'FALTA')
    if os.path.exists(db):
        c = sqlite3.connect(db)
        tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        print('  tabelas:', tabs)
        if 'tb_usuarios' in tabs:
            n = c.execute('SELECT COUNT(*) FROM tb_usuarios').fetchone()[0]
            print('  tb_usuarios linhas:', n)
        c.close()
