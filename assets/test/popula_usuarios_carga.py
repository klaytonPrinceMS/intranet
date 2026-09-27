"""EN: Seeds load-test users (perf/users) for the k6 login test.

PT-BR: Popula usuários de teste de carga (perf/usuarios) para o teste de login k6.

Por que um script e não SQL direto: `criar_usuario` é a ÚNICA porta de
entrada de usuário no sistema (AGENTS.md §4 — `bd_manipulador.py` é o único
que toca o banco). Ela valida login, senha mínima, perfil e nome de exibição,
gera o hash bcrypt, libera o acesso padrão `comum` e **marca `forcar_troca`**.

Esse último ponto é o que torna o teste k6 mais honesto: os 120 usuários
nascem com a troca de senha pendente, exatamente como qualquer servidor
novo. O script k6 tem de resolver esse diálogo no login — que é o caminho
real de primeiro acesso, e por isso mede o pior caso.

`--perfil` permite criar também administradores, para medir a tela mais
pesada (que carrega o painel) e não só a home.

Uso:
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py --qtd 120 --perfil administrador_geral
    .venv/bin/python assets/test/popula_usuarios_carga.py --limpar
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

PREFIXO = "user"
SENHA_PADRAO = "123456"   # provisória, como o seed do AGENTS.md §8.2


def _conectar():
    """Abre o banco de usuários para leitura/limpeza (o módulo cuida do resto)."""
    import sqlite3
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    caminho = raiz / "db_mod_gest_cad_usuario.db"
    if not caminho.exists():
        return None, caminho
    return sqlite3.connect(str(caminho), timeout=30), caminho


def listar_existentes() -> set:
    """Logins de carga já cadastrados (idempotente: não duplica)."""
    conn, caminho = _conectar()
    if conn is None:
        return set()
    try:
        linhas = conn.execute(
            "SELECT user_nome FROM tb_usuarios WHERE user_nome LIKE ?",
            (f"{PREFIXO}%",)).fetchall()
        return {linha[0] for linha in linhas}
    finally:
        conn.close()


def limpar() -> int:
    """Remove os usuários de carga e suas permissões. Devolve quantos saiu."""
    conn, caminho = _conectar()
    if conn is None:
        print(f"  banco não encontrado: {caminho}")
        return 0
    try:
        cur = conn.cursor()
        n_usuarios = cur.execute(
            "SELECT COUNT(*) FROM tb_usuarios WHERE user_nome LIKE ?",
            (f"{PREFIXO}%",)).fetchone()[0]
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome LIKE ?",
                    (f"{PREFIXO}%",))
        cur.execute("DELETE FROM tb_usuarios WHERE user_nome LIKE ?",
                    (f"{PREFIXO}%",))
        conn.commit()
        return n_usuarios
    finally:
        conn.close()


def marcar_ja_migraram(logins=None) -> int:
    """Zera `forcar_troca` dos usuários de carga, como se tivem trocado a senha.

    Por que isso importa para o teste: `criar_usuario` marca `forcar_troca=1`
    por desenho (o 1º login de qualquer servidor novo abre o diálogo de troca
    obrigatória). Medir login com o diálogo pendente mede o **pior caso de
    primeiro acesso**, não o estado normal de produção — onde o usuário já
    trocou a senha uma vez e o flag já está zerado.

    Mantemos a senha como `123456` (a provisória): o objetivo é o estado
    "já migrado", não uma senha forte — senha forte só adicionaria o custo
    do bcrypt, que é o mesmo.

    Vai por `autenticacao.marcar_trocar_senha`, e não por `sqlite3` direto,
    para funcionar também com `banco_tipo=postgres` (AGENTS.md §4.1).
    """
    from mod_intranet import autenticacao
    if logins is None:
        logins = sorted(listar_existentes())
    forzados = 0
    for login in logins:
        try:
            autenticacao.marcar_trocar_senha(login, forcar=False)
            forzados += 1
        except Exception:
            continue
    return forzados


def popular(qtd: int = 120, perfil: str = "comum", ja_migraram: bool = True) -> dict:
    """Cria `qtd` usuários de carga. Idempotente: pula quem já existe.

    Com `ja_migraram=True` (padrão), zera `forcar_troca` ao final — os usuários
    ficam como os de um servidor já em produção.
    """
    from mod_gest_cad_usuario import bd_manipulador as bd

    existentes = listar_existentes()
    criados, falhas = 0, []
    inicio = time.perf_counter()

    for i in range(1, qtd + 1):
        login = f"{PREFIXO}{i:03d}"
        if login in existentes:
            continue
        nome = f"Usuario Carga {i:03d}"
        ok, msg = bd.criar_usuario(
            "sistema", login, SENHA_PADRAO,
            email=f"{login}@carga.local",
            perfil=perfil,
            nome_completo=nome,
        )
        if ok:
            criados += 1
        else:
            falhas.append((login, msg))

    decorrido = time.perf_counter() - inicio
    total = len(existentes) + criados

    migrados = marcar_ja_migraram() if ja_migraram else 0

    print(f"  criados agora     : {criados}")
    print(f"  já existentes     : {len(existentes)}")
    print(f"  total de carga    : {total}")
    print(f"  perfil            : {perfil}")
    print(f"  senha             : {SENHA_PADRAO}")
    print(f"  troca de senha    : {'já feita (forcar_troca=0)' if ja_migraram else 'PENDENTE'}"
          f" — {migrados} usuário(s)")
    if decorrido > 0:
        print(f"  tempo             : {decorrido:.1f}s ({criados / decorrido:.1f}/s)")
    if falhas:
        print(f"  FALHAS ({len(falhas)}):")
        for login, msg in falhas[:10]:
            print(f"    {login}: {msg}")
    return {"criados": criados, "existentes": len(existentes),
            "total": total, "falhas": len(falhas), "perfil": perfil,
            "migrados": migrados}


def main() -> int:
    ap = argparse.ArgumentParser(description="Popula usuários de carga para o k6")
    ap.add_argument("--qtd", type=int, default=120,
                    help="quantidade de usuários (padrão 120)")
    ap.add_argument("--perfil", default="comum",
                    choices=["comum", "administrador_geral"],
                    help="perfil global dos usuários")
    ap.add_argument("--limpar", action="store_true",
                    help="remove os usuários de carga e sai")
    ap.add_argument("--somente-migrar", action="store_true",
                    help="apenas zera forcar_troca dos já existentes (sem criar)")
    ap.add_argument("--com-troca-pendente", action="store_true",
                    help="NÃO zera forcar_troca (mede o pior caso de 1º acesso)")
    args = ap.parse_args()

    if args.limpar:
        n = limpar()
        print(f"  {n} usuário(s) de carga removido(s)")
        return 0
    if args.somente_migrar:
        n = marcar_ja_migraram()
        print(f"  {n} usuário(s) com troca de senha marcada como feita")
        return 0
    print(f"  populando {args.qtd} usuário(s) de carga, perfil={args.perfil}")
    resultado = popular(args.qtd, args.perfil,
                        ja_migraram=not args.com_troca_pendente)
    return 1 if resultado["falhas"] else 0


if __name__ == "__main__":
    sys.exit(main())
