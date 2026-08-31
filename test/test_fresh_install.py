import sys
import os

# Garante que o pacote do projeto seja importavel a partir desta pasta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import tempfile
import shutil

DBS = [
    "db_mod_intranet.db",
    "db_mod_blog.db",
    "db_mod_gest_cad_usuario.db",
    "db_mod_edit_pdf.db",
    "db_mod_renomear_empenho.db",
]


def test_fresh_install_creates_empty_databases():
    """PLANO.md: bancos devem ser criados do zero quando nao existirem.

    Faz backup dos .db atuais (o usuario pode ter dados reais em outro
    lugar), remove todos, roda o bootstrap e restaura o backup ao final
    para nao destruir o ambiente de desenvolvimento.
    """
    from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bak = tempfile.mkdtemp(prefix="bkp_intranet_")
    try:
        # backup + remocao
        for f in DBS:
            for suf in ("", "-wal", "-shm"):
                p = os.path.join(root, f + suf)
                if os.path.exists(p):
                    shutil.move(p, os.path.join(bak, f + suf))

        for f in DBS:
            assert not os.path.exists(os.path.join(root, f)), \
                f"{f} deveria estar ausente para teste limpo"

        inicializar_bancos()

        for f in DBS:
            assert os.path.exists(os.path.join(root, f)), \
                f"{f} nao foi criado pelo bootstrap"

        c = sqlite3.connect(os.path.join(root, "db_mod_gest_cad_usuario.db"))
        m = c.execute(
            "SELECT user_nome, user_perfil FROM tb_usuarios WHERE user_nome='master'"
        ).fetchone()
        c.close()
        assert m == ("master", "administrador_geral"), \
            f"seed de master incorreto: {m}"

        print("OK: instalacao limpa cria bancos vazios + master/master")
    finally:
        # restaura o backup para nao perder dados do desenvolvedor
        for f in DBS:
            for suf in ("", "-wal", "-shm"):
                bp = os.path.join(bak, f + suf)
                tp = os.path.join(root, f + suf)
                if os.path.exists(bp):
                    if os.path.exists(tp):
                        os.remove(tp)
                    shutil.move(bp, tp)
        shutil.rmtree(bak, ignore_errors=True)


if __name__ == "__main__":
    test_fresh_install_creates_empty_databases()
