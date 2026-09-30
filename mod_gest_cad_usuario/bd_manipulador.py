"""User registration management module — full soft CRUD.

Módulo Gestão de Cadastro de Usuários — soft CRUD completo.

BD próprio: db_mod_gest_cad_usuario.db (WAL).
Tabelas: tb_usuarios, tb_acesso_usuario (perfis POR módulo), tb_modulo_perfil.
Auditoria central com ATOR (quem fez) conforme LGPD.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import time
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CAD_PATH = os.path.join(BASE_DIR, "db_mod_gest_cad_usuario.db")

PERFIS_GLOBAIS = ["comum", "administrador_modulo", "administrador_geral"]
PAPEIS_MODULO = ["comum", "administrador"]
# Módulos com acesso 'comum' liberado por padrão a todo usuário novo.
#
# A lista é o TRABALHO DIÁRIO de quem trabalha na prefeitura (27/09/2026):
# consultar empenho, editar documento, pedir impressão, achar o ramal de um
# colega, ver as notícias do município e abrir quadro de ordens de serviço do
# próprio setor. Um servidor que chega e não tem nenhum destes liberados cai
# em tela vazia e acha que o sistema quebrou.
#
# Ficam de FORA: `usuarios`, `auditoria` e `blog`.
#   - `usuarios` e `auditoria` mexem em conta e registro de todo mundo; são do
#     administrador, concedidos à mão.
#   - `blog` foi deixado de fora deliberadamente: publicar na intranet é ato de
#     comunicação do município, não privilégio de estar com matrícula ativa.
#     Se a prefeitura quiser, o administrador libera na tela de usuários —
#     e é melhor que a liberação seja uma decisão visível do que um padrão
#     que ninguém nota.
ACESSO_PADRAO_NOVO_USUARIO = ("editar_pdf", "empenhos", "solicita_impressao",  # noqa: E501
                              "lista_telefonica", "agregador_noticias", "os",
                              "estoque")


def get_connection():
    """Opens a connection to the module's own database (FKs enabled).

    Conexão via `banco_conexao.conexao` — SQLite (db_mod_gest_cad_usuario.db,
    WAL) ou PostgreSQL (DATABASE `db_mod_gest_cad_usuario`). O
    `busy_timeout=5000`+WAL+`foreign_keys=ON` já vêm herdados do núcleo
    (`mod_intranet.banco_conexao.conexao`); os PRAGMAs abaixo são
    reaplicação idempotente (no PG o proxy os neutraliza sem efeito)."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("usuarios")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão do módulo Gestão de Usuários")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception as e:
        _log().exception(f"get_connection: falha ao abrir conexão | {e}")
        raise


def _eh_violacao_unicidade(exc):
    """True para violação de unicidade em SQLite e PostgreSQL.

    SQLite: `sqlite3.IntegrityError: UNIQUE constraint failed`.
    PostgreSQL (psycopg2): `UniqueViolation` / SQLSTATE 23505 /
    `duplicate key value`. Fallback genérico por mensagem para não
    importar `sqlite3`/`psycopg2` aqui (compatível com o proxy PG)."""
    try:
        nome = type(exc).__name__ or ""
        if nome in ("IntegrityError", "UniqueViolation"):
            texto = str(exc).lower()
            if ("unique" in texto or "duplicate" in texto
                    or "23505" in texto or "already exists" in texto):
                return True
            # IntegrityError sem mensagem clara: presume unicidade apenas
            # se o nome for UniqueViolation; senão deixa o chamador decidir.
            return nome == "UniqueViolation"
        texto = str(exc).lower()
        return ("unique constraint" in texto or "uniqueviolation" in texto
                or "duplicate key" in texto or "23505" in texto)
    except Exception:
        return False


def _eh_bloqueio_banco(exc):
    """True quando o erro é contenção transitória do SQLite."""
    try:
        return "database is locked" in str(exc).lower()
    except Exception:
        return False


def _rollback_seguro(conn, contexto=""):
    """Rollback best-effort que nunca derruba o chamador (AGENTS §3.2)."""
    try:
        if conn is not None:
            conn.rollback()
    except Exception as e:
        try:
            _log().warning(f"_rollback_seguro[{contexto}]: {e}")
        except Exception:
            pass


def _commit_com_retry(conn, contexto="", tentativas=3, espera_s=0.05):
    """Commit com retry curto em `database is locked` (SQLite/WAL).

    Tenta `conn.commit()` até `tentativas` vezes quando a falha for
    contenção transitória; outra falha propaga ao chamador (que faz
    rollback + `logger.exception`, AGENTS §3.2). `busy_timeout=5000`
    já vem herdado de `banco_conexao.conexao` — o retry cobre apenas
    a janela residual de contenção."""
    try:
        ultima = None
        for tentativa in range(1, tentativas + 1):
            try:
                conn.commit()
                return True
            except Exception as e:
                ultima = e
                if _eh_bloqueio_banco(e) and tentativa < tentativas:
                    try:
                        time.sleep(espera_s * tentativa)
                    except Exception:
                        pass
                    continue
                raise
        if ultima is not None:
            raise ultima
        return True
    except Exception:
        raise


def _conexao_segura():
    """Opens the module connection logging the failure (returns None on error).

    Versão fail-soft de `get_connection`: em falha loga a causa e devolve
    None — os chamadores tratam None como estado de erro sem derrubar."""
    try:
        return get_connection()
    except Exception as e:
        _log().exception(f"_conexao_segura: falha ao abrir conexão | {e}")
        return None


def _central():
    """Opens a connection to the CENTRAL database (sessions/config only)."""
    try:
        from mod_intranet.bd_conexao import get_connection as gc
        return gc()
    except Exception as e:
        _log().exception(f"_central: falha ao abrir conexão central | {e}")
        raise


def _audit(ator, acao, alvo, detalhe=""):
    """Writes a central audit record for this module (LGPD trail)."""
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", "gest_cad_usuario", acao,
                  f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception as e:
        _log().exception(f"_audit: falha ao registrar auditoria | {e}")


def _log():
    """Logger central (loguru) — arquivo dedicado logs/gest_cad_usuario_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("gest_cad_usuario")


def senha_minima():
    """Minimum password length (characters) configured for the module.

    Política de senha mínima (em caracteres) do módulo, editável em
    tb_config central na chave `usuarios_senha_min` (painel Administração
    da Gestão de Usuários, 4–32, padrão 6). Fail-soft: em falha de leitura
    registra warning no loguru e retorna 6."""
    try:
        from mod_intranet.bd_conexao import get_config
        return max(4, int(get_config("usuarios_senha_min", "6")))
    except Exception as e:
        _log().warning(f"senha_minima: falha ao ler config; usando padrão 6 | {e}")
        return 6


def _troca_de_credencial_do_master_concluida():
    """True quando o `master` nativo JÁ foi renomeado no primeiro acesso.

    Lê a chave `forcar_troca_credenciais:master` do `tb_config` central. Ela
    vale '1' enquanto a troca está PENDENTE e '0' quando a troca CONCLUÍ
    (`autenticacao.trocar_credenciais_master` zera no fim, depois do rename).

    Serve de MARCADOR para o seed de `init_db`: sem ele, o seed recria
    `master/master` a cada reinício depois da troca, porque o rename tira o
    nome da tabela e a guarda `not obter_usuario("master")` volta a ser
    verdadeira (29/09/2026).

    Fail-soft: em falha de leitura devolve False — ou seja, SEMEIA. Semear
    numa instalação que já trocou é um transtorno; deixar de semear numa
    instalação nova tranca o admin para fora sem a conta de fábrica. Na
    dúvida, a conta existe.
    """
    try:
        from mod_intranet.bd_conexao import get_config
        return (get_config("forcar_troca_credenciais:master", "") or "").strip() == "0"
    except Exception as e:
        _log().warning(f"_troca_de_credencial_do_master_concluida: falha ao ler "
                       f"a marca; assumindo troca pendente | {e}")
        return False


def init_db():
    """Creates/migrates the schema and seeds (idempotent bootstrap).

    Cria `tb_usuarios` e `tb_acesso_usuario` (FK CASCADE/UPDATE CASCADE),
    aplica migrações idempotentes (soft delete `user_deletado`,
    `user_nome_completo`, `user_motivo_exclusao`), migra legados (usuários do
    banco central, CSV de módulos), semeia `master`/`master` com troca
    obrigatória (auto-cura enquanto a senha padrão existir) e os usuários de
    teste QA (`qacomum`/`qamaster`). Executado no import e pelo bootstrap."""
    try:
        _init_db_seguro()
    except Exception as e:
        _log().exception(f"init_db: falha no bootstrap | {e}")


def _init_db_seguro():
    """Runs the real init_db bootstrap inside a protected wrapper.

    Executa o bootstrap de init_db isolado para receber o try/except do
    entry point — falha nunca deve derrubar o import do módulo. Cada
    bloco usa check-then-add idempotente (portável SQLite↔PG via proxy
    `PRAGMA table_info`→`information_schema`; `INSERT OR IGNORE`→
    `ON CONFLICT DO NOTHING`) com `_commit_com_retry` (busy_timeout
    herdado + retry em `database is locked`) e rollback em falha
    parcial. Seed `master`/`qacomum`/`qamaster` preservado idempotente
    (AGENTS §8.2). Sem CrudBase aqui por risco no seed (fila futura)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_nome TEXT NOT NULL UNIQUE,
                user_senha TEXT NOT NULL,
                user_email TEXT,
                user_fone TEXT,
                user_perfil TEXT NOT NULL DEFAULT 'comum',
                user_ativo INTEGER NOT NULL DEFAULT 1,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
                modulo_acesso TEXT DEFAULT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_acesso_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE,
                modulo_chave TEXT NOT NULL,
                papel TEXT NOT NULL DEFAULT 'comum',
                liberado_por TEXT,
                data_liberacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_nome, modulo_chave)
            )
        """)
        _commit_com_retry(conn, contexto="init_db:ddl_base")

        # ---- Telefones múltiplos por usuário (27/09/2026) ----
        # Antes cabia UM telefone em `tb_usuarios.user_fone`, e a lista
        # telefônica só conseguia mostrar esse. Um servidor tem, no mínimo,
        # celular particular, celular da empresa e fixo da empresa, e é o
        # telefone DA EMPRESA que pode entrar na lista. Por isso a tabela
        # separada, com `papel` dizendo a quem o número pertence.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_telefone_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE,
                numero TEXT NOT NULL,
                papel TEXT NOT NULL DEFAULT 'empresa',
                tipo TEXT NOT NULL DEFAULT 'celular',
                principal INTEGER NOT NULL DEFAULT 0,
                visivel INTEGER NOT NULL DEFAULT 0,
                recado INTEGER NOT NULL DEFAULT 0,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ---- Consentimento de exibição do telefone (27/09/2026) ----
        # Ser servidor público não significa ter o número publicado: o prefeito
        # não quer o celular particular na lista, e o responsável pela defesa
        # civil precisa que o seu apareça para todos ligarem. Então a publicação
        # é ESCOLHA de cada um — `visivel` — e não padrão do sistema.
        cur.execute("PRAGMA table_info(tb_telefone_usuario)")
        cols_tel = {r[1] for r in cur.fetchall()}
        if "visivel" not in cols_tel:
            cur.execute("ALTER TABLE tb_telefone_usuario "
                        "ADD COLUMN visivel INTEGER NOT NULL DEFAULT 0")
        # ---- Telefone de recado (27/09/2026) ----
        # Quem não tem linha própria dá o telefone do SETOR, onde alguém
        # anota a mensagem e passa adiante: o da coleta de lixo é o da
        # garagem, o da merenda escolar é o da secretaria da escola. Sem esta
        # marcação, o número do setor entra na lista parecendo linha pessoal
        # de quem não atende — e a pessoa é desconsiderada por isso.
        if "recado" not in cols_tel:
            cur.execute("ALTER TABLE tb_telefone_usuario "
                        "ADD COLUMN recado INTEGER NOT NULL DEFAULT 0")
        _commit_com_retry(conn, contexto="init_db:consentimento_telefone")

        # ---- Tentativas de login (30/09/2026) ----
        # Uma linha por usuário, com a contagem e a última falha. Existe para
        # o ATRASO progressivo de `mod_intranet/politica_senha`: o login errado
        # não trava a conta, mas espera mais a cada erro, o que encarece o
        # ataque de dicionário sem fechar o acesso de quem só esqueceu a senha.
        #
        # `janela_min` é a hora da ÚLTIMA falha, e a contagem só vale dentro da
        # janela (15 min). Sem isso a conta ficaria lenta para sempre depois de
        # um período ruim de digitação — e a pessoa aprenderia a reclamar do
        # sistema, não a escolher senha melhor.
        # ---- Tentativas de login (30/09/2026) ----
        # UMA LINHA por usuário, com a contagem e a última falha. É para o
        # ATRASO progressivo de `mod_intranet/politica_senha`: o login errado
        # não trava a conta, mas espera mais a cada erro.
        #
        # Decisão do responsável (30/09/2026): SEM BLOQUEIO, só atraso. Travar a
        # conta por tentativas transforma "troquei a senha e digitei a antiga
        # duas vezes" em chamado no DTI — e quem mais digita a senha errada é
        # justamente quem trabalha com ela o dia inteiro. A espera encarece o
        # ataque de dicionário sem fechar a conta de servidor nenhum.
        #
        # `ultima_falha` marca a janela (15 min). Passada a janela a contagem
        # vale zero: a conta não fica lenta para sempre depois de um período
        # ruim de digitação. Login CERTO zera na hora — senão a penalidade
        # vazaria para a sessão seguinte de quem entrou corretamente.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_login_tentativas (
                user_nome TEXT PRIMARY KEY
                    REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE,
                falhas INTEGER NOT NULL DEFAULT 0,
                ultima_falha DATETIME DEFAULT CURRENT_TIMESTAMP,
                bloqueada_ate DATETIME
            )
        """)
        _commit_com_retry(conn, contexto="init_db:tentativas_login")

        # ---- Histórico de remuneração (28/09/2026) ----
        # Uma linha por competência, só quando o VALOR MUDA. Guardar todo mês
        # mesmo sem mudança encheria a tabela de repetição; e guardar só o
        # valor atual perderia o histórico, que é a única coisa que interessa
        # quando se pergunta "quanto ele recebeu em março?". A intranet roda
        # o sync mensalmente, então a linha do mês é o registro.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_remuneracao_historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome)
                    ON DELETE CASCADE,
                competencia TEXT NOT NULL,
                remuneracao TEXT NOT NULL DEFAULT '',
                ficha_contracheque TEXT DEFAULT '',
                registrado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_remuneracao_historico "
                    "ON tb_remuneracao_historico(user_nome, competencia)")

        # ---- Dados funcionais públicos (27/09/2026) ----
        # Matrícula, nome, secretaria e cargo são informação pública (portal da
        # transparência), e o cadastro não tinha onde guardar. `matricula` não
        # entra como coluna: o PRÓPRIO `user_nome` é a matrícula.
        cur.execute("PRAGMA table_info(tb_usuarios)")
        cols_usuario = {r[1] for r in cur.fetchall()}
        for _col, _def in (("unidade", "TEXT DEFAULT ''"),
                           ("lotacao", "TEXT DEFAULT ''"),
                           ("cargo", "TEXT DEFAULT ''"),
                           # 1 = o servidor ainda não registrou os telefones.
                           # O portal da transparência não publica ramal, então o
                           # número só existe se ele mesmo informar no 1º acesso.
                           ("telefone_pendente", "INTEGER NOT NULL DEFAULT 0"),
                           # Liberação TEMPORÁRIA (27/09/2026). O servidor que
                           # não sabe o próprio número entra com 4 dias de
                           # prazo e um telefone particular obrigatório; depois
                           # disso a conta fecha e só o DTI reabre. Precisa de
                           # `provisorio_ate` porque `acesso_provisorio` sozinho
                           # não guarda QUANDO o prazo vence.
                           ("acesso_provisorio", "INTEGER NOT NULL DEFAULT 0"),
                           ("provisorio_ate", "DATETIME"),
                           # ---- Pendência de atualização dos dados (28/09/2026) ----
                           # O portal da transparência publica a secretaria, o
                           # departamento e o cargo. Quando um servidor muda de
                           # setor, o sistema NÃO sobrescreve: MARCA, e quem
                           # confirma é a própria pessoa. Dois motivos que se
                           # sustentam: o portal é a fonte do setor mas o
                           # telefone só a pessoa sabe, e overwrite apagaria o
                           # ajuste que o administrador fez à mão no painel.
                           ("pendencia_dados", "TEXT DEFAULT ''"),
                           ("pendencia_em", "DATETIME"),
                           # ---- Remuneração (28/09/2026) ----
                           # Dado público por lei (a remuneração de servidor
                           # é informação pública, e a prefeitura a publica
                           # mensalmente). A intranet importa para que o
                           # servidor veja o próprio valor sem sair do
                           # sistema — e o DTI, que precisa conferir a
                           # folha contra o portal.
                           #
                           # TEXTO, E NÃO NÚMERO: dinheiro em ponto flutuante
                           # perde centavo, e "R$ 3.456,78" arredondado para
                           # 3456.78 vira 3456.779999... no relatório. O valor
                           # entra como o portal envia.
                           ("remuneracao", "TEXT DEFAULT ''"),
                           ("remuneracao_competencia", "TEXT DEFAULT ''"),
                           ("ficha_contracheque", "TEXT DEFAULT ''"),
                           # `vinculo` e `situacao` são o que a folha traz do
                           # portal e que a folha sozinha não consegue responder
                           # depois: "é efetivo?", "está ativo?". A lista
                           # telefônica precisa disso para CONSTAR a pessoa
                           # mesmo sem telefone — e sem essas duas colunas a
                           # resposta seria sempre "não sei", que é pior que
                           # não responder. (28/09/2026)
                           ("vinculo", "TEXT DEFAULT ''"),
                           ("situacao", "TEXT DEFAULT ''")):
            if _col not in cols_usuario:
                cur.execute(f"ALTER TABLE tb_usuarios ADD COLUMN {_col} {_def}")
        _commit_com_retry(conn, contexto="init_db:dados_funcionais")

        # Migração de esquema: garante FK com ON UPDATE CASCADE (renomeio).
        # Portável: no SQLite inspeciona `sqlite_master`; no PG o proxy
        # devolve vazio p/ `sqlite_master` (inalcançável) e o `_ddl_postgres`
        # remove REFERENCES — integridade gerida na aplicação (UPDATE manual
        # em `renomear_usuario` + limpeza de órfãos). Por isso a guarda usa
        # `PRAGMA table_info` (traduzido p/ information_schema no PG) e só
        # executa o rebuild no backend SQLite.
        try:
            from mod_intranet.banco_conexao import sgbd_ativo
            _backend = sgbd_ativo()
        except Exception:
            _backend = "sqlite"
        if _backend != "postgres":
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tb_acesso_usuario'")
            sql_row = cur.fetchone()
            if sql_row and "ON UPDATE" not in (sql_row[0] or "").upper():
                cur.executescript("""
                    ALTER TABLE tb_acesso_usuario RENAME TO tb_acesso_usuario_old;
                    CREATE TABLE tb_acesso_usuario (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE ON UPDATE CASCADE,
                        modulo_chave TEXT NOT NULL,
                        papel TEXT NOT NULL DEFAULT 'comum',
                        liberado_por TEXT,
                        data_liberacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_nome, modulo_chave)
                    );
                    INSERT INTO tb_acesso_usuario SELECT * FROM tb_acesso_usuario_old;
                    DROP TABLE tb_acesso_usuario_old;
                """)
                _commit_com_retry(conn, contexto="init_db:fk_update_cascade")
        else:
            # PG: apenas garante que a tabela existe (marcador portável).
            cur.execute("PRAGMA table_info(tb_acesso_usuario)")
            _ = cur.fetchall()

        # Migração: flags finas de permissão por módulo (JSON em tb_acesso_usuario).
        # Padrão check-then-add (portável; duplicata concorrente tolerada no proxy).
        cur.execute("PRAGMA table_info(tb_acesso_usuario)")
        cols_acesso = {r[1] for r in cur.fetchall()}
        if "flags" not in cols_acesso:
            cur.execute("ALTER TABLE tb_acesso_usuario ADD COLUMN flags TEXT NOT NULL DEFAULT '{}'")
            _commit_com_retry(conn, contexto="init_db:flags")

        # Migração única: usuários do BD central -> BD do módulo (legado).
        # Só roda se o BD central AINDA tiver tb_usuarios; em instalação nova
        # essa tabela não existe mais, então a migração é pulada com segurança
        # (evita quebrar o bootstrap "criar do zero" do PLANO.md).
        cur.execute("SELECT COUNT(*) FROM tb_usuarios")
        if cur.fetchone()[0] == 0:
            c = _central()
            try:
                cc = c.cursor()
                cc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tb_usuarios'")
                if cc.fetchone():
                    cc.execute("SELECT user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo, data_cadastro, modulo_acesso FROM tb_usuarios")
                    for r in cc.fetchall():
                        cur.execute(
                            """INSERT INTO tb_usuarios
                               (user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo, data_cadastro, modulo_acesso)
                               VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)""",
                            r,
                        )
                        # converte legado CSV -> linhas de acesso com papel 'comum'
                        for chave in [x.strip() for x in (r[7] or "").split(",") if x.strip()]:
                            cur.execute(
                                "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'migracao')",
                                (r[0], chave),
                            )
                    _commit_com_retry(conn, contexto="init_db:migracao_legado")
            finally:
                c.close()

        # Migração: coluna de soft-delete explícita (check-then-add portável).
        cur.execute("PRAGMA table_info(tb_usuarios)")
        cols = [r[1] for r in cur.fetchall()]
        if "user_deletado" not in cols:
            cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_deletado INTEGER NOT NULL DEFAULT 0")
            _commit_com_retry(conn, contexto="init_db:user_deletado")
        # Migração: nome de exibição/tratamento (pode ser o nome social — Decreto 8.727/2016)
        cur.execute("PRAGMA table_info(tb_usuarios)")
        cols = [r[1] for r in cur.fetchall()]
        if "user_nome_completo" not in cols:
            cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_nome_completo TEXT")
            cur.execute("UPDATE tb_usuarios SET user_nome_completo='Usuário Master' WHERE user_nome='master'")
            _commit_com_retry(conn, contexto="init_db:nome_completo")
        # Migração: motivo registrado no momento da exclusão lógica (check-then-add).
        cur.execute("PRAGMA table_info(tb_usuarios)")
        cols = [r[1] for r in cur.fetchall()]
        if "user_motivo_exclusao" not in cols:
            cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_motivo_exclusao TEXT")
            _commit_com_retry(conn, contexto="init_db:motivo_exclusao")
    except Exception as e:
        try:
            _rollback_seguro(conn, contexto="init_db_seguro")
        except Exception:
            pass
        try:
            _log().exception(f"_init_db_seguro: falha no bootstrap DDL | {e}")
        except Exception:
            pass
        raise
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    # Segurança: se o master AINDA usa a senha padrão 'master' (instalação nova
    # ou legado), força a troca no primeiro logon — idempotente e auto-cura:
    # depois que ele trocar, a flag nunca mais é rearmada. No primeiro acesso,
    # além da senha, o master nativo deve renomear o usuário (credenciais).
    try:
        from mod_intranet import autenticacao as _auth
        linha = _auth.usuario_existe("master")
        if linha and _auth.verificar_senha("master", linha[0]):
            _auth.marcar_trocar_senha("master", True)
            _auth.marcar_trocar_credenciais("master", True)
    except Exception as e:
        _log().exception(f"init_db: falha ao verificar senha padrão do master | {e}")

    # Garante master (seed idempotente AGENTS §8.2 — sem CrudBase aqui).
    #
    # A guarda tem DUAS condições, e a segunda é a que impede a ressurreição
    # da conta de fábrica (29/09/2026).
    #
    # O primeiro acesso do master é um RENOMEAR (`renomear_usuario` faz UPDATE
    # e preserva o id), então `master` sai da tabela e a guarda
    # `not obter_usuario("master")` volta a ser verdadeira no boot seguinte:
    # o seed recria a conta com a senha de fábrica, perfil administrador_geral
    # e as duas flags de troca rearmadas. O admin troca as credenciais, e no
    # próximo reinício master/master está de volta — observado nesta instalação
    # em 29/09/2026, 16:48:35, um minuto depois da troca concluída às 16:47:13.
    #
    # A segunda condição é o marcador: `forcar_troca_credenciais:master` é
    # gravada como '1' quando a troca é pedida e como '0' quando ela CONCLUÍ
    # (`autenticacao.trocar_credenciais_master` chama `marcar_trocar_credenciais(
    # nome_atual, False)`). Então "a chave existe e vale 0" quer dizer, sem
    # ambiguidade, "o master nativo já foi renomeado" — e um nome de usuário
    # que não existe mais é justamente o que NÃO deve ser ressuscitado.
    # Mesmo padrão do marcador de migração do versionamento (§4.2): uma vez
    # gravado, o estado não volta atrás sozinho.
    if not _troca_de_credencial_do_master_concluida() and not obter_usuario("master"):
        from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha, marcar_trocar_credenciais
        conn = None
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo) VALUES (?, ?, 'administrador_geral', 1)",
                ("master", gerar_hash_senha("master")),
            )
            _commit_com_retry(conn, contexto="init_db:seed_master")
            marcar_trocar_senha("master", True)
            marcar_trocar_credenciais("master", True)
        except Exception as e:
            _rollback_seguro(conn, contexto="init_db:seed_master")
            _log().exception(f"init_db: falha ao semear master | {e}")
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    # Garante usuários de teste de QA (docs) — qacomum (comum) e qamaster (administrador_geral).
    # qacomum segue o padrão de criação vigente (comum em editar_pdf,
    # empenhos e solicita_impressao; SEM acesso a blog/usuarios/auditoria).
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = None
    try:
        conn = get_connection(); cur = conn.cursor()
        if not obter_usuario("qacomum"):
            cur.execute(
                "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'comum', 1, ?)",
                ("qacomum", gerar_hash_senha("123456"), "Usuário de Teste QA Comum"),
            )
            for chave in ACESSO_PADRAO_NOVO_USUARIO:
                cur.execute(
                    "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'sistema')",
                    ("qacomum", chave),
                )
            _commit_com_retry(conn, contexto="init_db:seed_qacomum")
            marcar_trocar_senha("qacomum", True)
        else:
            # Reconcilia o qacomum existente com o padrão vigente (idempotente):
            # garante os 3 acessos comuns e remove o legado 'blog' concedido
            # pelo seed ('sistema') — concessões manuais do admin são mantidas.
            for chave in ACESSO_PADRAO_NOVO_USUARIO:
                cur.execute(
                    "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'sistema')",
                    ("qacomum", chave),
                )
            cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome='qacomum' AND modulo_chave='blog' AND liberado_por='sistema'")
            _commit_com_retry(conn, contexto="init_db:reconcilia_qacomum")
        if not obter_usuario("qamaster"):
            cur.execute(
                "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'administrador_geral', 1, ?)",
                ("qamaster", gerar_hash_senha("123456"), "Usuário de Teste QA Master"),
            )
            _commit_com_retry(conn, contexto="init_db:seed_qamaster")
            marcar_trocar_senha("qamaster", True)
    except Exception as e:
        _rollback_seguro(conn, contexto="init_db:seed_qa")
        _log().exception(f"init_db: falha ao semear QA | {e}")
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# ================= CONSULTAS =================

def _normalizar_data(valor):
    """Normalizes a date value to 'YYYY-MM-DD HH:MM:SS' string.

    No SQLite `data_cadastro`/`data_liberacao` já vêm como string; no
    PostgreSQL o driver retorna `datetime.datetime`. Padroniza para string
    para que o consumo (telas) não precise saber o backend."""
    if valor is None:
        return None
    if isinstance(valor, (datetime,)):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


def listar_usuarios(filtro_ativo=None):
    """Lists users with per-module access aggregated (GROUP_CONCAT).

    Retorna tuplas (id, user_nome, user_perfil, user_ativo, user_email,
    user_fone, data_cadastro, acessos 'modulo:papel, …', user_deletado,
    user_nome_completo, user_motivo_exclusao). `filtro_ativo` filtra por
    `user_ativo` quando informado; ordenado por login. `data_cadastro` é
    normalizada para string (backend-agnóstico). GROUP BY completo
    (portável SQLite↔PG — o PG exige todas as colunas não agregadas;
    `GROUP_CONCAT`→`STRING_AGG` via proxy)."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        sql = """SELECT u.id, u.user_nome, u.user_perfil, u.user_ativo,
                        u.user_email, u.user_fone, u.data_cadastro,
                        GROUP_CONCAT(a.modulo_chave || ':' || a.papel, ', '),
                        u.user_deletado, u.user_nome_completo, u.user_motivo_exclusao
                 FROM tb_usuarios u
                 LEFT JOIN tb_acesso_usuario a ON a.user_nome = u.user_nome
                 WHERE 1=1"""
        params = []
        if filtro_ativo is not None:
            sql += " AND u.user_ativo=?"
            params.append(1 if filtro_ativo else 0)
        sql += (" GROUP BY u.id, u.user_nome, u.user_perfil, u.user_ativo,"
                " u.user_email, u.user_fone, u.data_cadastro,"
                " u.user_deletado, u.user_nome_completo, u.user_motivo_exclusao"
                " ORDER BY u.user_nome")
        cur.execute(sql, params)
        linhas = []
        for r in cur.fetchall():
            linha = list(r)
            linha[6] = _normalizar_data(linha[6])
            linhas.append(tuple(linha))
        return linhas
    except Exception as e:
        _log().exception(f"listar_usuarios: falha ao listar usuários | {e}")
        return []
    finally:
        conn.close()


def obter_usuario(user_nome):
    """Fetches one user row (incl. senha/perfil/ativo/deletado/nome_completo).

    Retorna a tupla completa do usuário ou None. Usada pelo núcleo
    (`autenticacao.usuario_existe`) para validar login/sessão a cada request."""
    conn = _conexao_segura()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_nome, user_senha, user_email, user_fone,
                      user_perfil, user_ativo, data_cadastro,
                      user_deletado, user_nome_completo
               FROM tb_usuarios WHERE user_nome=?""",
            (user_nome,),
        )
        return cur.fetchone()
    except Exception as e:
        _log().exception(f"obter_usuario: falha ao obter usuário {user_nome} | {e}")
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
#  Telefones do usuário e dados funcionais (27/09/2026)
# ---------------------------------------------------------------------------
# Um servidor tem mais de um telefone: celular particular, celular da empresa,
# fixo da empresa. Só o telefone DA EMPRESA pode entrar na lista telefônica, e
# é por isso que `papel` existe — é ele que separa o que a prefeitura publica
# do que é do servidor. A lista telefônica LÊ estes telefones (ver
# `mod_lista_telefonica`); aqui mora a fonte.
PAPEIS_TELEFONE = ("empresa", "pessoal")
TIPOS_TELEFONE = ("celular", "fixo")


def _validar_papel(papel) -> str:
    """Normaliza o `papel` do telefone; desconhecido vira 'empresa'.

    O default é 'empresa' de propósito: o caminho seguro é o número ser
    publicável. Um papel corrompido virando 'pessoal' publicaria um número
    particular sem ninguém pedir."""
    p = (papel or "empresa").strip().lower()
    return p if p in PAPEIS_TELEFONE else "empresa"


def _validar_tipo(tipo) -> str:
    """Normaliza o `tipo` do telefone; desconhecido vira 'celular'."""
    t = (tipo or "celular").strip().lower()
    return t if t in TIPOS_TELEFONE else "celular"


def telefone_e_publicavel(papel, tipo, visivel) -> bool:
    """Diz se um telefone pode sair na lista telefônica.

    A regra do município (27/09/2026), que é uma exceção que vale a pena
    enxergar:

    - **fixo da prefeitura SEMPRE sai**. É a linha institucional, o número
      que a prefeitura divulga em papel de visitation e em editais. Se o
      servidor informou o ramal, é porque quer ser localizado por ele — a
      lista telefônica é justamente o instrumento de localização pública, e
      um fixo institucional guardado é um fixo inútil para a Gemeinde.
    - **celular da prefeitura SÓ sai se ele marcar**. É celular: quem
      atende é a pessoa, no próprio número, a qualquer hora. Um responsável
      pela defesa civil precisa aparecer para todos; o prefeito, não. Isso é
      consentimento, não configuração do sistema.
    - **qualquer número pessoal NUNCA sai**, marque ou não: celular particular
      e residencial não têm por que estar num cadastro de servidor, e o
      consentimento para o celular particular não alcança o residencial.
    """
    if _validar_papel(papel) == 'pessoal':
        return False
    if _validar_tipo(tipo) == 'fixo':
        return True
    return bool(visivel)


def telefone_de_recado(numero, papel, tipo) -> bool:
    """Diz se este telefone é o do SETOR, usado para recado.

    O servidor sem linha própria dá o telefone do setor: o da coleta de lixo
    é o da garagem, o da merenda escolar é o da secretaria da escola. Para o
    diretório, o número é o mesmo — o que muda é o que está escrito ao lado,
    porque "Fulano, 3591-5150" faz a pessoa achar que é a linha dela."""
    try:
        return _eh_telefone_da_prefeitura(papel, tipo)
    except Exception:
        return False


def telefone_e_recado(user_nome) -> bool:
    """O telefone que a lista telefônica vai mostrar é um recado?

    É o número que a pessoa **não atende** e em que alguém anota a mensagem.
    A lista escreve "deixe recado" ao lado do nome, para quem liga não
    procurar a pessoa por dez minutos antes de descobrir que ela não atende
    o próprio ramal."""
    try:
        tels = listar_telefones(user_nome, apenas_empresa=True)
    except Exception:
        return False
    principal = next((t for t in tels if t[5]), tels[0]) if tels else None
    if not principal:
        return False
    # t = (id, user, numero, papel, tipo, principal, visivel, recado, data)
    return bool(principal[7]) if len(principal) > 7 else False


def telefones_de_recado_em_lote(user_nomes) -> dict:
    """Quem tem telefone de recado — uma consulta só.

    Mesmo papel de `telefones_publicaveis_em_lote`: a lista telefônica monta
    mais de mil cartões sem abrir mais de mil conexões. Devolve
    `{user_nome: True}` só para quem tem número de recado marcado."""
    try:
        nomes = [str(n) for n in (user_nomes or []) if n]
        if not nomes:
            return {}
        conn = get_connection()
        try:
            cur = conn.cursor()
            marcas = ",".join("?" * len(nomes))
            cur.execute(
                "SELECT user_nome, numero, principal, papel, tipo, visivel, recado "
                f"FROM tb_telefone_usuario WHERE user_nome IN ({marcas})",
                nomes)
            linhas = cur.fetchall()
        finally:
            conn.close()
        melhores = {}
        for user_nome, numero, principal, papel, tipo, visivel, recado in linhas:
            if not telefone_e_publicavel(papel, tipo, visivel):
                continue
            chave = (0 if principal else 1, str(numero or ""))
            atual = melhores.get(user_nome)
            if atual is None or chave < atual[0]:
                melhores[user_nome] = (chave, bool(recado))
        return {k: v[1] for k, v in melhores.items()}
    except Exception as e:
        _log().exception(f"telefones_de_recado_em_lote: falha | {e}")
        return {}


def listar_telefones(user_nome, apenas_empresa: bool = False):
    """Telefones do usuário, principal primeiro e os demais por número.

    Devolve linhas `(id, user_nome, numero, papel, tipo, principal, visivel,
    recado, data_cadastro)`. `apenas_empresa=True` devolve só os PUBLICÁVEIS —
    é o que a lista telefônica usa, para nunca vazar número particular. A
    filtragem fica em Python por `telefone_e_publicavel` (e não em
    `SQL WHERE papel=...`) para que a regra do fixo institucional valha igual
    nos dois backends. `recado` diz que o número é o do SETOR, usado para
    deixar recado — a lista telefônica escreve isso ao lado do nome.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, user_nome, numero, papel, tipo, principal, visivel, "
                "recado, data_cadastro FROM tb_telefone_usuario WHERE user_nome=?",
                (user_nome,))
            linhas = cur.fetchall()
            if apenas_empresa:
                linhas = [t for t in linhas
                          if telefone_e_publicavel(t[3], t[4], t[6])]
            return sorted(linhas, key=lambda r: (0 if r[5] else 1, r[2] or ""))
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"listar_telefones: falha ao listar de {user_nome} | {e}")
        return []


def telefone_empresa_principal(user_nome):
    """Telefone publicável marcado como principal, ou o primeiro publicável.

    A lista telefônica usa este para ligar um contato que é um servidor
    cadastrado. `None` quando o usuário não liberou nenhum número — e aí o
    contato fica sem telefone, o que é honesto: nem todo servidor quer ser
    localizado no celular particular, e a lista respeita isso."""
    tels = listar_telefones(user_nome, apenas_empresa=True)
    if not tels:
        return None
    principal = next((t for t in tels if t[5]), tels[0])
    return principal[2]


def telefones_publicaveis_em_lote(user_nomes) -> dict:
    """Telefone publicável de vários usuários, NORMALMENTE em uma consulta.

    Existe por causa de um número: a prefeitura tem ~1.200 servidores, e
    `telefone_empresa_principal` por pessoa abria ~1.200 conexões para montar
    a mesma tela. Com 60 usuários de demonstração ninguém notava; com a
    folha real, a tela da lista telefônica deixava de abrir.

    Devolve `{user_nome: numero}` só para quem tem número publicável — quem
    não liberou simplesmente não aparece no dicionário, que é o mesmo
    significado de "sem telefone" que o resto do sistema usa.
    """
    try:
        nomes = [str(n) for n in (user_nomes or []) if n]
        if not nomes:
            return {}
        conn = get_connection()
        try:
            cur = conn.cursor()
            # `IN` com placeholders portátil: o proxy traduz para o PG, e os
            # valores vão sempre por parâmetro — não há concatenação de texto.
            marcas = ",".join("?" * len(nomes))
            cur.execute(
                "SELECT user_nome, numero, papel, tipo, principal, visivel "
                f"FROM tb_telefone_usuario WHERE user_nome IN ({marcas})",
                nomes)
            linhas = cur.fetchall()
        finally:
            conn.close()
        melhores = {}
        for user_nome, numero, papel, tipo, principal, visivel in linhas:
            if not telefone_e_publicavel(papel, tipo, visivel):
                continue
            chave = (0 if principal else 1, str(numero or ""))
            atual = melhores.get(user_nome)
            if atual is None or chave < atual[0]:
                melhores[user_nome] = (chave, numero)
        return {k: v[1] for k, v in melhores.items()}
    except Exception as e:
        _log().exception(f"telefones_publicaveis_em_lote: falha em {len(user_nomes or [])} usuário(s) | {e}")
        return {}


def adicionar_telefone(ator, user_nome, numero, papel="empresa",
                       tipo="celular", principal=False, visivel=None):
    """Cadastra um telefone do usuário. Devolve (True, msg) ou (False, motivo).

    `principal=True` desmarca os outros, para só haver um principal por vez —
    senão a lista telefônica não saberia qual mostrar. Número é normalizado
    aqui, e não na tela, para que a mesma regra valha para toda escrita.

    `visivel` é o CONSENTIMENTO de exibição. `None` (o padrão) deixa a decisão
    para `telefone_e_publicavel`: fixo da prefeitura publica sozinho, celular
    da empresa só se o servidor disser que pode.
    """
    try:
        numero_limpo = _normalizar_telefone_cadastro(numero)
        if not numero_limpo:
            return False, "Telefone inválido."
        papel_n = _validar_papel(papel)
        tipo_n = _validar_tipo(tipo)
        visivel_n = 0 if visivel is None else (1 if visivel else 0)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            if principal:
                cur.execute("UPDATE tb_telefone_usuario SET principal=0 "
                            "WHERE user_nome=?", (user_nome,))
            cur.execute(
                "INSERT INTO tb_telefone_usuario "
                "(user_nome, numero, papel, tipo, principal, visivel) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_nome, numero_limpo, papel_n, tipo_n,
                 1 if principal else 0, visivel_n))
            _commit_com_retry(conn, contexto="adicionar_telefone")
            _limpar_pendencia_telefone(cur, user_nome)
            _commit_com_retry(conn, contexto="adicionar_telefone:pendencia")
            _audit(ator, "telefone_cadastrado", user_nome,
                   f"{numero_limpo} ({papel_n}/{tipo_n})"
                   f"{' principal' if principal else ''}"
                   f"{' publicado' if telefone_e_publicavel(papel_n, tipo_n, visivel_n) else ' restrito'}")
            return True, "Telefone cadastrado."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"adicionar_telefone: falha em {user_nome} | {e}")
        return False, "Erro ao cadastrar o telefone."


def editar_telefone(ator, telefone_id, numero=None, papel=None, tipo=None,
                    principal=None, visivel=None):
    """Altera um telefone do usuário. Devolve (True, msg) ou (False, motivo)."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_nome FROM tb_telefone_usuario WHERE id=?",
                        (telefone_id,))
            linha = cur.fetchone()
            if not linha:
                return False, "Telefone não encontrado."
            user_nome = linha[0]
            numero_limpo = None
            if numero is not None:
                numero_limpo = _normalizar_telefone_cadastro(numero)
                if not numero_limpo:
                    return False, "Telefone inválido."
            if principal:
                cur.execute("UPDATE tb_telefone_usuario SET principal=0 "
                            "WHERE user_nome=?", (user_nome,))
            campos, valores = [], []
            if numero_limpo is not None:
                campos.append("numero=?")
                valores.append(numero_limpo)
            if papel is not None:
                campos.append("papel=?")
                valores.append(_validar_papel(papel))
            if tipo is not None:
                campos.append("tipo=?")
                valores.append(_validar_tipo(tipo))
            if principal is not None:
                campos.append("principal=?")
                valores.append(1 if principal else 0)
            if visivel is not None:
                campos.append("visivel=?")
                valores.append(1 if visivel else 0)
            if not campos:
                return True, "Nada a alterar."
            valores.append(telefone_id)
            cur.execute(f"UPDATE tb_telefone_usuario SET {', '.join(campos)} "
                        f"WHERE id=?", valores)
            _commit_com_retry(conn, contexto="editar_telefone")
            _audit(ator, "telefone_alterado", user_nome,
                   f"id={telefone_id}")
            return True, "Telefone alterado."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"editar_telefone: falha no id {telefone_id} | {e}")
        return False, "Erro ao alterar o telefone."


def remover_telefone(ator, telefone_id):
    """Remove um telefone do usuário. Devolve (True, msg) ou (False, motivo)."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_nome FROM tb_telefone_usuario WHERE id=?",
                        (telefone_id,))
            linha = cur.fetchone()
            if not linha:
                return False, "Telefone não encontrado."
            cur.execute("DELETE FROM tb_telefone_usuario WHERE id=?",
                        (telefone_id,))
            _commit_com_retry(conn, contexto="remover_telefone")
            _audit(ator, "telefone_removido", linha[0], f"id={telefone_id}")
            return True, "Telefone removido."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"remover_telefone: falha no id {telefone_id} | {e}")
        return False, "Erro ao remover o telefone."


def marcar_pendencia_dados(ator, user_nome, descricao):
    """Marca que os dados funcionais do servidor mudaram no portal.

    O texto da `descricao` é o que o servidor vai ler no alerta ("seu
    departamento mudou de A para B"), então deve ser escrito para a pessoa,
    não para o técnico.

    Não sobrescreve nada: `unidade`, `lotacao` e `cargo` continuam como
    estão até a pessoa confirmar. É a diferença entre "o sistema atualiza" e
    "o sistema pergunta" — e perguntar é o certo aqui, porque quem responde é
    quem sabe.

    A marca **não acumula**: chamar de novo substitui o texto e a data. Um
    servidor que mudou duas vezes no mesmo mês precisa de um alerta, não de
    dois, e o segundo sobrecreveria a informação do primeiro.
    """
    try:
        descricao = (descricao or "").strip()
        if not descricao:
            return True, "Nada a marcar."
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE tb_usuarios SET pendencia_dados=?, "
                        "pendencia_em=? WHERE user_nome=?",
                        (descricao, agora, user_nome))
            _commit_com_retry(conn, contexto="marcar_pendencia_dados")
            _audit(ator, "pendencia_dados", user_nome, descricao)
            _log().info(f"pendência de dados marcada para {user_nome}: "
                        f"{descricao}")
            return True, "Dados marcados para revisão."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"marcar_pendencia_dados: falha em {user_nome} | {e}")
        return False, "Erro ao marcar a pendência."


def _limpar_pendencia_dados(cur, user_nome):
    """Baixa a pendência de dados (chamado com o cursor aberto)."""
    try:
        cur.execute("UPDATE tb_usuarios SET pendencia_dados='', "
                    "pendencia_em=NULL WHERE user_nome=?", (user_nome,))
    except Exception as e:
        _log().warning(f"não foi possível baixar a pendência de dados "
                       f"de {user_nome}: {e}")


def informacao_pendencia(user_nome) -> dict:
    """EN: Pending data-change state of one account.

    PT-BR: O estado da pendência de atualização dos dados de uma conta.

    `varios_dias` é o que o alerta do DTI usa para cobrar quem está há
    semanas sem confirmar — a pendência sozinha não diz que está parada, e
    uma pendência parada é uma pendência que ninguém vai resolver."""
    vazio = {"tem": False, "descricao": "", "desde": None, "dias": 0}
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT pendencia_dados, pendencia_em FROM tb_usuarios "
                        "WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
        finally:
            conn.close()
        if not linha or not (linha[0] or "").strip():
            return vazio
        dias = 0
        if linha[1]:
            try:
                marca = datetime.strptime(str(linha[1])[:19], "%Y-%m-%d %H:%M:%S")
                dias = max(0, (datetime.now() - marca).days)
            except (ValueError, TypeError):
                dias = 0
        return {"tem": True, "descricao": linha[0], "desde": linha[1],
                "dias": dias}
    except Exception as e:
        _log().exception(f"informacao_pendencia: falha em {user_nome} | {e}")
        return vazio


def listar_pendencias_dados(limite=50) -> list:
    """Contas com dado funcional mudado e ainda não confirmado.

    Serve ao alerta do DTI na Home. Ordenada pela mais antiga primeiro: a
    pendência de quem está há 3 semanas é o problema, e a de quem abriu
    yesterday é ruído. Devolve dicionários com `user_nome`, `nome_completo`,
    `descricao`, `desde` e `dias`.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""SELECT user_nome, user_nome_completo, pendencia_dados,
                                  pendencia_em, user_ativo
                           FROM tb_usuarios
                           WHERE pendencia_dados IS NOT NULL
                             AND pendencia_dados <> ''
                           ORDER BY (pendencia_em IS NULL), pendencia_em ASC
                           LIMIT ?""", (int(limite or 50),))
            linhas = cur.fetchall()
        finally:
            conn.close()
        saida = []
        for u, nome, desc, desde, ativo in linhas:
            dias = 0
            if desde:
                try:
                    marca = datetime.strptime(str(desde)[:19], "%Y-%m-%d %H:%M:%S")
                    dias = max(0, (datetime.now() - marca).days)
                except (ValueError, TypeError):
                    dias = 0
            saida.append({
                "user_nome": u,
                "nome_completo": nome or "",
                "descricao": desc or "",
                "desde": desde,
                "dias": dias,
                "ativo": bool(ativo),
            })
        return saida
    except Exception as e:
        _log().exception(f"listar_pendencias_dados: falha | {e}")
        return []


def contar_pendencias_dados() -> int:
    """Quantas contas estão com dado funcional aguardando confirmação."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios "
                        "WHERE pendencia_dados IS NOT NULL "
                        "AND pendencia_dados <> ''")
            return int((cur.fetchone()[0] or 0))
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"contar_pendencias_dados: falha | {e}")
        return 0


def definir_remuneracao(ator, user_nome, remuneracao=None, competencia=None,
                       ficha_contracheque=None):
    """Grava a remuneração vinda do portal e registra no histórico.

    Chamado pelo sync mensal, com a `competencia` da folha (ex.: "08/2026").

    A REMUNERAÇÃO É OBJETIVA E NÃO VIRA PERGUNTA
        O aviso de mudança de setor existe porque setor tem dois donos
        possíveis e um deles é a pessoa. Remuneração não: é o valor oficial
        publicado, e não há o que a pessoa confirme — ela sabe quanto ganha,
        mas quem registra é o RH e o portal. Por isso aqui se ATUALIZA e se
        guarda o histórico, em vez de marcar e esperar.

    O HISTÓRICO SÓ GRAVA QUANDO O VALOR MUDA
        Rodar o sync todo mês com o mesmo valor criaria 12 linhas idênticas
        por ano, e a pergunta "quando subiu o salário?" deixaria de ter
        resposta. A linha entra na competência em que o valor mudou — que é
        também a linha que interessa.
    """
    try:
        comp = (competencia or "").strip()
        rem = (remuneracao or "").strip() if remuneracao is not None else None
        ficha = (ficha_contracheque or "").strip() \
            if ficha_contracheque is not None else None
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            if rem is None and ficha is None and not comp:
                return True, "Nada a atualizar."
            cur.execute("SELECT remuneracao, ficha_contracheque FROM tb_usuarios "
                        "WHERE user_nome=?", (user_nome,))
            antes = cur.fetchone() or ("", "")
            rem_final = rem if rem is not None else (antes[0] or "")
            ficha_final = ficha if ficha is not None else (antes[1] or "")
            cur.execute("UPDATE tb_usuarios SET remuneracao=?, "
                        "remuneracao_competencia=?, ficha_contracheque=? "
                        "WHERE user_nome=?",
                        (rem_final, comp or None, ficha_final, user_nome))
            mudou = (antes[0] or "") != rem_final
            if mudou and comp:
                # já existe linha desta competência? então atualiza, não duplica
                cur.execute("SELECT id FROM tb_remuneracao_historico "
                            "WHERE user_nome=? AND competencia=?",
                            (user_nome, comp))
                linha = cur.fetchone()
                if linha:
                    cur.execute("UPDATE tb_remuneracao_historico "
                                "SET remuneracao=?, ficha_contracheque=?, "
                                "registrado_em=CURRENT_TIMESTAMP WHERE id=?",
                                (rem_final, ficha_final, linha[0]))
                else:
                    cur.execute("INSERT INTO tb_remuneracao_historico "
                                "(user_nome, competencia, remuneracao, "
                                "ficha_contracheque) VALUES (?, ?, ?, ?)",
                                (user_nome, comp, rem_final, ficha_final))
                _audit(ator, "remuneracao_atualizada", user_nome,
                       f"{antes[0] or '(vazio)'} -> {rem_final} "
                       f"[{comp or 'sem competência'}]")
            _commit_com_retry(conn, contexto="definir_remuneracao")
            return True, ("Remuneração atualizada." if mudou
                          else "Remuneração conferida, sem mudança.")
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"definir_remuneracao: falha em {user_nome} | {e}")
        return False, "Erro ao gravar a remuneração."


def definir_vinculo(ator, user_nome, vinculo=None, situacao=None):
    """Grava o vínculo (efetivo, concursado, terceirizado...) e a situação.

    Chamado pelo sync mensal, com o que a folha traz do portal.

    É OBJETIVO, COMO A REMUNERAÇÃO, E TAMBÉM NÃO VIRA PERGUNTA
        "Esta pessoa é efetiva?" não tem dois donos possíveis: a folha é a
        fonte e o dado é publicado por lei. A pergunta é para setor, cargo e
        departamento, onde a folha e a pessoa discordam às vezes. Aqui o
        sistema grava e pronto.

    POR QUE EXISTE
        A lista telefônica precisa responder "é efetivo?" e "está ativo?" para
        quem não autorizou telefone. Sem estas duas colunas no cadastro, a
        resposta seria "não sei" — e a pessoa desapareceria da busca, que é
        exatamente o que a busca não deve fazer.

    Só os campos informados mudam (`None` = manter), para uma competência que
        traga o vínculo e não traga a situação não apagar a situação anterior.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            campos, valores = [], []
            for campo, valor in (("vinculo", vinculo), ("situacao", situacao)):
                if valor is not None:
                    campos.append(f"{campo}=?")
                    valores.append(str(valor or "").strip())
            if not campos:
                return True, "Nada a gravar."
            valores.append(user_nome)
            cur.execute(f"UPDATE tb_usuarios SET {', '.join(campos)} "
                        f"WHERE user_nome=?", valores)
            _commit_com_retry(conn, contexto="definir_vinculo")
            _audit(ator, "vinculo_atualizado", user_nome,
                   ", ".join(f"{c}={v}" for c, v in zip(campos, valores[:-1])))
            return True, "Vínculo atualizado."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"definir_vinculo: falha em {user_nome} | {e}")
        return False, "Erro ao gravar o vínculo."


def historico_remuneracao(user_nome, limite=24) -> list:
    """Histórico de remuneração do servidor, do mais recente para o mais antigo."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT competencia, remuneracao, ficha_contracheque, "
                        "registrado_em FROM tb_remuneracao_historico "
                        "WHERE user_nome=? ORDER BY competencia DESC LIMIT ?",
                        (user_nome, int(limite or 24)))
            linhas = cur.fetchall()
        finally:
            conn.close()
        return [{"competencia": l[0], "remuneracao": l[1],
                 "ficha_contracheque": l[2] or "", "registrado_em": l[3]}
                for l in linhas]
    except Exception as e:
        _log().exception(f"historico_remuneracao: falha em {user_nome} | {e}")
        return []


def _limpar_pendencia_telefone(cur, user_nome):
    """Baixa a pendência de telefone do usuário (usado com o cursor aberto).

    Fica em SQL cru e recebe o cursor porque quem chama já está numa
    transação — abrir outra conexão aqui perderia o trabalho em curso."""
    try:
        cur.execute("UPDATE tb_usuarios SET telefone_pendente=0 "
                    "WHERE user_nome=?", (user_nome,))
    except Exception as e:
        _log().warning(f"não foi possível baixar a pendência de telefone "
                       f"de {user_nome}: {e}")


def telefone_pendente(user_nome) -> bool:
    """True se o servidor ainda precisa registrar os telefones.

    O portal da transparência publica matrícula, nome, secretaria e cargo —
    mas NÃO o ramal. Ou seja: sem esse passo, um servidor recém-cadastrado
    entraria na lista telefônica sem número nenhum. Por isso a pendência
    acompanha a troca de senha no primeiro acesso."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT telefone_pendente FROM tb_usuarios "
                        "WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
            return bool(linha and linha[0])
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"telefone_pendente: falha em {user_nome} | {e}")
        return False


# Prazo da liberação temporária, em dias. Depois dele a conta fecha e só o
# DTI reabre — o prazo curto é o ponto: quatro dias é o bastante para o
# servidor descobrir o número perguntando à secretaria da escola, à unidade de
# saúde, à garagem ou ao almoxarifado, e curto o bastante para que a conta não
# vire cadastro órfão no sistema.
DIAS_LIBERACAO_PROVISORIA = 4


def _eh_telefone_da_prefeitura(papel, tipo) -> bool:
    """Fixo da prefeitura — o número institucional.

    Celular da prefeitura NÃO conta: celular é a pessoa, e o que a
    prefeitura precisa garantir é que exista uma **linha** que toque em
    algum lugar do prédio. É por isso que a exigência é de um fixo, e não de
    "um telefone da prefeitura" em geral."""
    return _validar_papel(papel) == 'empresa' and _validar_tipo(tipo) == 'fixo'


def avaliar_telefones_primeiro_acesso(contatos):
    """EN: Evaluates the phones before saving — what is missing, what is out
    of range. PT-BR: Avalia os telefones antes de gravar.

    Devolve um dicionário para o chamador, sem gravar nada:

    ```
    {
      "tem_da_prefeitura": bool,   # existe fixo da prefeitura (próprio ou recado)
      "particulares":     int,     # quantos particulares o servidor informou
      "fora_da_faixa":    [(numero, descricao_da_faixa_mais_proxima)],
      "pode_prosseguir":  bool,
    }
    ```

    Separar a avaliação da gravação é o que permite à tela mostrar o aviso de
    "fora da faixa" **enquanto** o servidor digita, e não só depois que ele
    já salvou e descobriu que errou."""
    try:
        from mod_intranet import telefone_faixas as _fx
        tem_prefeitura = False
        particulares = 0
        fora = []
        for c in (contatos or []):
            if not isinstance(c, dict):
                continue
            num = _normalizar_telefone_cadastro(c.get("numero"))
            if not num:
                continue
            if _eh_telefone_da_prefeitura(c.get("papel"), c.get("tipo")):
                tem_prefeitura = True
                dentro, _faixa = _fx.numero_dentro_da_faixa(num)
                if not dentro:
                    perto = _fx.faixa_mais_proxima(num)
                    fora.append((num, (perto or {}).get("descricao", "")))
            else:
                particulares += 1
        return {
            "tem_da_prefeitura": tem_prefeitura,
            "particulares": particulares,
            "fora_da_faixa": fora,
            "pode_prosseguir": tem_prefeitura or particulares > 0,
        }
    except Exception as e:
        _log().exception(f"avaliar_telefones_primeiro_acesso: falha | {e}")
        return {"tem_da_prefeitura": False, "particulares": 0,
                "fora_da_faixa": [], "pode_prosseguir": False}


def registrar_contatos_primeiro_acesso(ator, user_nome, contatos,
                                       liberacao_provisoria=False):
    """Grava de uma vez os telefones do primeiro acesso.

    `contatos` é uma lista de dicionários com `numero`, `papel`
    ('empresa'/'pessoal'), `tipo` ('celular'/'fixo'), `visivel` e `recado`.
    Tudo numa transação só: ou entra o conjunto inteiro, ou nada — um cadastro
    pela metade é pior do que um cadastro recusado, porque o servidor fica sem
    saber o que já preencheu.

    A EXIGÊNCIA DE UM TELEFONE DA PREFEITURA
        Todo servidor está atrelado a uma secretaria ou a um setor, e todo
        setor tem linha. Então o sistema pede um **fixo da prefeitura** — o
        próprio ou o de recado. Celular particular e celular da prefeitura
        não satisfazem: os dois vão para o celular de quem atende, e quem
        precisa é a prefeitura ser localizada.

    A LIBERAÇÃO TEMPORÁRIA (o paliativo)
        Quando o servidor não sabe o número — e é mais comum do que parece,
        porque a maioria não tem linha própria — ele confirma duas vezes que
        não sabe, e aí entra com prazo: `liberacao_provisoria=True` grava
        `acesso_provisorio` com `DIAS_LIBERACAO_PROVISORIA` de validade e
        **exige um telefone particular**. Passado o prazo, `bloqueio_provisorio_pendente`
        fecha a conta e só o DTI reabre.

    O QUE NÃO É BLOQUEADO
        Telefone fora das faixas da prefeitura: é avisado, não recusado. Ver
        `avaliar_telefones_primeiro_acesso`.

    Devolve `(ok, msg, detalhes)` — `detalhes` traz `provisorio` e
    `fora_da_faixa` para a tela mostrar o que precisa mostrar.
    """
    detalhes = {"provisorio": False, "fora_da_faixa": [],
                "ate": None, "pode_prosseguir": False}
    try:
        monta = []
        for c in (contatos or []):
            if not isinstance(c, dict):
                continue
            if not _normalizar_telefone_cadastro(c.get("numero")):
                continue  # campo em branco: o servidor optou por não informar
            monta.append(c)

        avalio = avaliar_telefones_primeiro_acesso(monta)
        detalhes["fora_da_faixa"] = avalio["fora_da_faixa"]
        detalhes["pode_prosseguir"] = avalio["pode_prosseguir"]

        if not monta:
            return False, ("Informe ao menos um telefone — sem ele você não "
                           "aparece na lista telefônica."), detalhes

        if not avalio["tem_da_prefeitura"]:
            if not liberacao_provisoria:
                return False, ("Falta um telefone da prefeitura (fixo). "
                               "Se você usa o telefone do setor para recado, "
                               "marque-o como telefone de recado."), detalhes
            # paliativo: entra com prazo, mas SÓ com particular informado
            if avalio["particulares"] <= 0:
                return False, ("Para liberar o acesso por um período você "
                               "precisa informar um telefone particular de "
                               "contato."), detalhes
            detalhes["provisorio"] = True

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado.", detalhes
            cur.execute("DELETE FROM tb_telefone_usuario WHERE user_nome=?",
                        (user_nome,))
            principal_definido = any(bool(c.get("principal")) for c in monta)
            for i, c in enumerate(monta):
                papel_n = _validar_papel(c.get("papel"))
                tipo_n = _validar_tipo(c.get("tipo"))
                principal = 1 if (c.get("principal") or (i == 0 and not principal_definido)) else 0
                if principal:
                    cur.execute("UPDATE tb_telefone_usuario SET principal=0 "
                                "WHERE user_nome=?", (user_nome,))
                cur.execute(
                    "INSERT INTO tb_telefone_usuario "
                    "(user_nome, numero, papel, tipo, principal, visivel, recado) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_nome, _normalizar_telefone_cadastro(c.get("numero")),
                     papel_n, tipo_n, principal,
                     1 if c.get("visivel") else 0,
                     1 if c.get("recado") else 0))
            if detalhes["provisorio"]:
                dias = DIAS_LIBERACAO_PROVISORIA
                cur.execute(
                    "UPDATE tb_usuarios SET acesso_provisorio=1, "
                    "provisorio_ate=? WHERE user_nome=?",
                    (_prazo(dias), user_nome))
                cur.execute("SELECT provisorio_ate FROM tb_usuarios "
                            "WHERE user_nome=?", (user_nome,))
                linha_prazo = cur.fetchone()
                detalhes["ate"] = linha_prazo[0] if linha_prazo else None
            else:
                # TEM um telefone nosso: a liberação é definitiva e o prazo
                # anterior (se houve) deixa de valer.
                cur.execute("UPDATE tb_usuarios SET acesso_provisorio=0, "
                            "provisorio_ate=NULL WHERE user_nome=?", (user_nome,))
            _limpar_pendencia_telefone(cur, user_nome)
            _commit_com_retry(conn, contexto="registrar_contatos_primeiro_acesso")
            _audit(ator, "contatos_primeiro_acesso", user_nome,
                   f"{len(monta)} telefone(s)"
                   + (" | LIBERACAO PROVISORIA" if detalhes["provisorio"] else ""))
            _log().info(f"contatos do 1º acesso de {user_nome}: {len(monta)}"
                        + (f" (provisório até {detalhes['ate']})"
                           if detalhes["provisorio"] else ""))
            if detalhes["provisorio"]:
                return True, (f"Telefones registrados. Acesso liberado por "
                               f"{DIAS_LIBERACAO_PROVISORIA} dias — depois "
                               f"disso a conta fica bloqueada até o DTI "
                               f"liberar."), detalhes
            return True, "Telefones registrados.", detalhes
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"registrar_contatos_primeiro_acesso: "
                         f"falha em {user_nome} | {e}")
        return False, "Erro ao registrar os telefones.", detalhes


def _prazo(dias):
    """Data/hora em que a liberação temporária vence, no mesmo formato do
    banco. Sem `strftime` do SQLite para continuar funcionando no Postgres
    pelo proxy."""
    try:
        return (datetime.now() + timedelta(days=int(dias))).strftime(
            "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def bloqueio_provisorio_pendente(user_nome) -> bool:
    """True se a liberação temporária desta conta JÁ VENCEU e ela está ativa.

    Chamado no login: é aí que a janela de 4 dias se cumpre. Sem essa
    checagem, a liberação temporária seria um prazo que ninguém nunca
    fiscaliza — a conta entraria para sempre, e o paliativo viraria norma."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT acesso_provisorio, provisorio_ate, user_ativo "
                        "FROM tb_usuarios WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
        finally:
            conn.close()
        if not linha or not linha[0] or not linha[1]:
            return False
        if not linha[2]:
            return False  # já está bloqueada: nada a fazer
        try:
            prazo = datetime.strptime(str(linha[1])[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return False
        return datetime.now() > prazo
    except Exception as e:
        _log().exception(f"bloqueio_provisorio_pendente: falha em {user_nome} | {e}")
        return False


def confirmar_pendencia_dados(ator, user_nome, unidade=None, lotacao=None,
                              cargo=None):
    """O servidor confirmou a mudança: grava os valores novos e baixa a marca.

    A confirmação é da PESSOA, não do técnico. Quando ela confirma, o que
    ela está dizendo é "é isso mesmo, meu departamento mudou" — e a partir
    daí o banco passa a refletir isso.

    Só os campos informados mudam (`None` = manter), para que a confirmação
    não apague o campo que o portal não trouxe.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            campos, valores = [], []
            for campo, valor in (("unidade", unidade), ("lotacao", lotacao),
                                 ("cargo", cargo)):
                if valor is not None:
                    campos.append(f"{campo}=?")
                    valores.append(str(valor or "").strip())
            if campos:
                valores.append(user_nome)
                cur.execute(f"UPDATE tb_usuarios SET {', '.join(campos)} "
                            f"WHERE user_nome=?", valores)
            _limpar_pendencia_dados(cur, user_nome)
            _commit_com_retry(conn, contexto="confirmar_pendencia_dados")
            _audit(ator, "pendencia_dados_confirmada", user_nome,
                   ", ".join(campos) if campos else "sem alteração de valor")
            _log().info(f"pendência de dados confirmada por {user_nome}: "
                        f"{', '.join(campos) or 'nenhum campo'}")
            return True, "Dados atualizados."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"confirmar_pendencia_dados: falha em {user_nome} | {e}")
        return False, "Erro ao confirmar a atualização."


def definir_dados_funcionais(ator, user_nome, unidade=None, lotacao=None,
                             cargo=None):
    """Grava unidade, lotação e cargo do usuário (informação pública).

    Só os campos informados são alterados (`None` = manter). Devolve
    (True, msg) ou (False, motivo).
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            campos, valores = [], []
            for campo, valor in (("unidade", unidade), ("lotacao", lotacao),
                                 ("cargo", cargo)):
                if valor is not None:
                    campos.append(f"{campo}=?")
                    valores.append(str(valor or "").strip())
            if not campos:
                return True, "Nada a alterar."
            valores.append(user_nome)
            cur.execute(f"UPDATE tb_usuarios SET {', '.join(campos)} "
                        f"WHERE user_nome=?", valores)
            _commit_com_retry(conn, contexto="definir_dados_funcionais")
            _audit(ator, "dados_funcionais_alterados", user_nome,
                   ", ".join(campos))
            return True, "Dados funcionais salvos."
        finally:
            conn.close()
    except Exception as e:
        _log().exception(
            f"definir_dados_funcionais: falha em {user_nome} | {e}")
        return False, "Erro ao salvar os dados funcionais."


def _normalizar_telefone_cadastro(numero):
    """Normaliza para apenas dígitos e `+`, para gravar e comparar.

    Aceita o que o usuário digita ('(00) 3591-5101', '00 3591 5101', '+55 00
    ...') e devolve uma forma canônica. Regra local de propósito: o módulo
    não pode depender do `mod_intranet.telefone` (que é do núcleo) para gravar,
    e a comparação de duplicidade precisa de uma forma só.
    """
    try:
        bruto = re.sub(r"[^0-9+]", "", str(numero or ""))
        if not bruto:
            return ""
        # '+' só no começo; '+55' duplicado vira um só.
        tem_mais = bruto.startswith("+")
        digitos = re.sub(r"[^0-9]", "", bruto)
        if tem_mais and digitos.startswith("55") and len(digitos) > 12:
            digitos = digitos[2:]
        if not digitos:
            return ""
        return ("+" + digitos) if tem_mais else digitos
    except Exception:
        return ""


def _primeiro_e_ultimo(nome_completo):
    """"Ana Beatriz Souza Rocha" -> "Ana Rocha".

    Função LOCAL, e não importada de `leitura_lista.nome_para_exibicao`, pelo
    mesmo motivo daquele arquivo: `leitura_lista` importa este módulo, e o
    caminho inverso fecharia um ciclo de import. São quatro linhas.

    A regra é a mesma da lista telefônica: ninguém é tratado pelo nome
    inteiro em voz alta. No cabeçalho, "Ana Rocha" diz quem é; "Ana Beatriz
    Souza Rocha" ocupa a tela toda; e a matrícula "000123" não diz nada sobre
    a pessoa. (Exemplo fictício, e a matrícula também.)"""
    partes = [p for p in str(nome_completo or "").split() if p]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[-1]}"


def nome_de_tratamento(user_nome):
    """Display name for greetings/screens — first name + surname.

    Nome usado para tratamento nas telas — **primeiro e último nome** do
    cadastro (que guarda o nome completo ou social, Decreto 8.727/2016).

    POR QUE PRIMEIRO E ÚLTIMO, E NÃO O NOME TODO
        O nome de usuário desta prefeitura é a **matrícula** (`MT-1234`).
        Mostrar isso no cabeçalho é mostrar um código de barras com nome de
        pessoa: não diz nada, e a pessoa se reconhece no número como se
        reconhece numa placa. E o nome completo em tela cheia empurra o
        rótulo do perfil para fora. Primeiro e último é o que a pessoa ouve
        quando é chamada.

    Cai para o login só quando não existe nome completo — nesse caso não há
    outra coisa a mostrar, e o nome de login é melhor do que um campo vazio."""
    try:
        row = obter_usuario(user_nome)
        completo = (row[9] or "").strip() if row and len(row) > 9 else ""
        curto = _primeiro_e_ultimo(completo)
        return curto or completo or user_nome
    except Exception as e:
        _log().exception(f"nome_de_tratamento: falha para {user_nome} | {e}")
        return user_nome


def listar_acessos(user_nome):
    """Lists the user's per-module grants (modulo_chave, papel, liberado_por, data)."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT modulo_chave, papel, liberado_por, data_liberacao
               FROM tb_acesso_usuario WHERE user_nome=? ORDER BY modulo_chave""",
            (user_nome,),
        )
        linhas = []
        for r in cur.fetchall():
            linha = list(r)
            linha[3] = _normalizar_data(linha[3])
            linhas.append(tuple(linha))
        return linhas
    except Exception as e:
        _log().exception(f"listar_acessos: falha ao listar acessos de {user_nome} | {e}")
        return []
    finally:
        conn.close()


# ================= CRUD =================

def _validar_nome_completo(nome_completo, user_nome):
    """Validates the display/social name (min 3 chars, different from login)."""
    nc = (nome_completo or "").strip()
    if len(nc) < 3:
        return None, "Nome completo/social é obrigatório (mín. 3 caracteres)"
    if nc.lower() == (user_nome or "").strip().lower():
        return None, "O nome de exibição deve ser diferente do nome de login"
    return nc, None


def criar_usuario(ator, user_nome, senha, email=None, fone=None, perfil="comum",
                   nome_completo="", exigir_telefone=True):
    """Creates a user with a provisional password (mandatory first-login change).

    Valida login, senha mínima (`senha_minima`), perfil global e nome de
    exibição; grava hash bcrypt, libera o acesso padrão 'comum'
    (`ACESSO_PADRAO_NOVO_USUARIO`), marca `forcar_troca` e audita
    `criar_usuario`. Senha vazia/None cai no padrão inicial ``123456``.

    `exigir_telefone=True` (padrão) marca `telefone_pendente`, e o primeiro
    acesso pede os telefones depois da troca de senha: o portal da
    transparência não publica ramal, então o telefone da lista só existe se o
    próprio servidor informar. Contas de serviço (robô, integração) passam
    `False` — não têm pessoa para atender o telefone.
    Retorna `(ok, msg)`."""
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    senha = (senha or "").strip() or "123456"
    if not user_nome or not user_nome.strip():
        return False, "Nome de usuário é obrigatório"
    if len(senha or "") < senha_minima():
        return False, f"Senha provisória deve ter no mínimo {senha_minima()} caracteres"
    if perfil not in PERFIS_GLOBAIS:
        return False, f"Perfil inválido: {perfil}"
    nome_c, erro = _validar_nome_completo(nome_completo, user_nome)
    if erro:
        return False, erro
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        hash_s = gerar_hash_senha(senha)
        cur.execute(
            """INSERT INTO tb_usuarios
               (user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo,
                user_nome_completo, telefone_pendente)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            (user_nome.strip(), hash_s, email, fone, perfil, nome_c,
             1 if exigir_telefone else 0),
        )
        for chave in ACESSO_PADRAO_NOVO_USUARIO:
            cur.execute(
                "INSERT INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', ?)",
                (user_nome.strip(), chave, ator),
            )
        _commit_com_retry(conn, contexto=f"criar_usuario:{user_nome}")
        marcar_trocar_senha(user_nome.strip(), True)
        _audit(ator, "criar_usuario", user_nome.strip(), f"perfil={perfil} | exibição: {nome_c}")
        _log().info(f"usuário criado: {user_nome.strip()} perfil={perfil} por {ator}")
        return True, "Usuário criado (senha provisória — troca obrigatória no 1º acesso)"
    except Exception as e:
        if _eh_violacao_unicidade(e):
            _rollback_seguro(conn, contexto=f"criar_usuario:{user_nome}")
            _log().warning(f"criar_usuario: nome já existe: {user_nome}")
            return False, "Nome de usuário já existe"
        _rollback_seguro(conn, contexto=f"criar_usuario:{user_nome}")
        _log().exception(f"criar_usuario: falha ao criar usuário {user_nome} | {e}")
        return False, "Erro inesperado ao criar usuário"
    finally:
        conn.close()


def editar_usuario(ator, user_nome, email="__NULO__", fone="__NULO__",
                   perfil=None, ativo=None, deletado=None, nome_completo="__NULO__",
                   auditar=True):
    """Edits personal data/global profile (RF-26 last-admin guard).

    Edita dados pessoais/perfil global. Use '__NULO__' p/ manter campo.
    Protege o último `administrador_geral` ativo (RF-26) e veda
    auto-rebaixamento/auto-desativação."""
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (user_nome,))
        if not cur.fetchone():
            return False, "Usuário não existe"
        # RF-26: outro administrador não pode rebaixar nem bloquear o último
        # administrador_geral ativo do sistema.
        if ator != user_nome:
            cur.execute("SELECT user_perfil, user_ativo FROM tb_usuarios WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
            if linha and linha[0] == "administrador_geral" and linha[1] == 1:
                vai_rebaixar = perfil is not None and perfil != "administrador_geral"
                vai_bloquear = ativo is not None and not ativo
                if vai_rebaixar or vai_bloquear:
                    cur.execute(
                        "SELECT COUNT(*) FROM tb_usuarios "
                        "WHERE user_perfil='administrador_geral' AND user_ativo=1")
                    if cur.fetchone()[0] <= 1:
                        return False, "Não é possível rebaixar/bloquear o último administrador geral ativo"
        sets, params, mudancas = [], [], []
        if nome_completo != "__NULO__":
            nc, erro = _validar_nome_completo(nome_completo, user_nome)
            if erro:
                return False, erro
            sets.append("user_nome_completo=?"); params.append(nc)
            mudancas.append(f"nome de exibição: {nc}")
        if email != "__NULO__":
            sets.append("user_email=?"); params.append(email or None); mudancas.append("email")
        if fone != "__NULO__":
            sets.append("user_fone=?"); params.append(fone or None); mudancas.append("telefone")
        if perfil:
            if perfil not in PERFIS_GLOBAIS:
                return False, f"Perfil inválido: {perfil}"
            if ator == user_nome:
                cur.execute("SELECT user_perfil FROM tb_usuarios WHERE user_nome=?", (user_nome,))
                atual = cur.fetchone()
                if atual and atual[0] == "administrador_geral" and perfil != "administrador_geral":
                    return False, "Você não pode remover o próprio perfil de administrador geral"
            sets.append("user_perfil=?"); params.append(perfil); mudancas.append(f"perfil={perfil}")
        if ativo is not None:
            if ator == user_nome and not ativo:
                return False, "Você não pode desativar a própria conta"
            sets.append("user_ativo=?"); params.append(1 if ativo else 0)
            mudancas.append("ativo" if ativo else "inativo")
        if deletado is not None:
            if ator == user_nome and deletado:
                return False, "Você não pode excluir a própria conta"
            sets.append("user_deletado=?"); params.append(1 if deletado else 0)
            mudancas.append("restaurado" if not deletado else "soft")
        if not sets:
            return True, "Nada a alterar"
        params.append(user_nome)
        cur.execute(f"UPDATE tb_usuarios SET {', '.join(sets)} WHERE user_nome=?", tuple(params))  # nosec B608 — sets só literais fixos "col=?"; valores via ?
        _commit_com_retry(conn, contexto=f"editar_usuario:{user_nome}")
        if auditar:
            _audit(ator, "editar_usuario", user_nome, ", ".join(mudancas))
        _log().info(f"usuário editado: {user_nome} | {', '.join(mudancas)} por {ator}")
        return True, "Usuário atualizado"
    except Exception as e:
        _rollback_seguro(conn, contexto=f"editar_usuario:{user_nome}")
        _log().exception(f"editar_usuario: falha ao editar {user_nome} | {e}")
        return False, "Erro inesperado ao editar usuário"
    finally:
        conn.close()


def renomear_usuario(ator, nome_atual, novo_nome, permitir_master=False):
    """Renames the login keeping the PK id, propagating to dependents.

    Renomeia mantendo o ID (chave primária), replicando nas tabelas
    dependentes (`tb_acesso_usuario`, sessões centrais e autorias nos
    demais módulos). `permitir_master=True` libera a renomeação do
    `master` nativo — usado EXCLUSIVAMENTE no primeiro acesso (troca de
    credenciais obrigatória). Paridade PG: o `_ddl_postgres` do núcleo
    remove `REFERENCES ... ON DELETE/UPDATE CASCADE` — a integridade é
    gerida na aplicação (UPDATE manual nas duas tabelas + limpeza de
    órfãos abaixo); commit com retry em `database is locked` e rollback
    em falha parcial (AGENTS §3.2)."""
    novo_nome = (novo_nome or "").strip()
    if not novo_nome:
        return False, "Novo nome vazio"
    if nome_atual == "master" and not permitir_master:
        return False, "A conta master nativa não pode ser renomeada"
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (novo_nome,))
        if cur.fetchone():
            # Mensagem que diz o que fazer: o diálogo de troca de credenciais
            # traz o nome pré-preenchido com um valor fixo, e se esse nome já
            # estiver em uso o rename falha. Como as flags de troca SÓ caem
            # depois de um rename bem-sucedido (`autenticacao.py`), a recusa
            # aqui abre um ciclo — o diálogo reabre no boot seguinte e falha
            # igual, sem caminho de saída (29/09/2026). Dizer "já existe" sem
            # orientar deixa quem instala sem saber que basta trocar o nome.
            return False, (f"'{novo_nome}' já é o login de outro usuário. "
                           f"Escolha um nome de usuário diferente.")
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (nome_atual,))
        if not cur.fetchone():
            return False, "Usuário não existe"
        cur.execute("UPDATE tb_usuarios SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
        cur.execute("UPDATE tb_acesso_usuario SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
        # Limpeza manual de órfãos (PG sem FKs — ver docstring): remove
        # vínculos cujo user_nome não existe mais em tb_usuarios.
        try:
            cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome NOT IN (SELECT user_nome FROM tb_usuarios)")
        except Exception as e_orf:
            _log().warning(f"renomear_usuario: falha na limpeza de órfãos | {e_orf}")
        _commit_com_retry(conn, contexto=f"renomear_usuario:{nome_atual}->{novo_nome}")
        _audit(ator, "renomear_usuario", nome_atual, f"→ {novo_nome} (ID preservado)")
        # reflete também nas sessões do banco central
        try:
            c = _central(); cc = c.cursor()
            cc.execute("UPDATE tb_sessoes SET usuario=? WHERE usuario=? AND logout_timestamp IS NULL",
                       (novo_nome, nome_atual))
            c.commit(); c.close()
        except Exception as e:
            _log().warning(f"renomear_usuario: falha ao refletir em sessões centrais | {e}")
        _vinculos_cruzados_renomear(nome_atual, novo_nome)
        _log().info(f"usuário renomeado: {nome_atual} -> {novo_nome} por {ator}")
        return True, f"Renomeado para '{novo_nome}'"
    except Exception as e:
        if _eh_violacao_unicidade(e):
            _rollback_seguro(conn, contexto=f"renomear_usuario:{nome_atual}")
            _log().warning(f"renomear_usuario: conflito de unicidade para '{novo_nome}'")
            return False, "Conflito de unicidade"
        _rollback_seguro(conn, contexto=f"renomear_usuario:{nome_atual}")
        _log().exception(f"renomear_usuario: falha ao renomear {nome_atual} | {e}")
        return False, "Erro inesperado ao renomear usuário"
    finally:
        conn.close()


def alterar_senha_admin(ator, user_nome, nova_senha):
    """Admin password reset (provisional, forces change, drops sessions).

    Troca administrativa de senha (reenvio provisório): valida o mínimo
    (`senha_minima`), marca `forcar_troca` e encerra todas as sessões."""
    if len(nova_senha or "") < senha_minima():
        return False, f"Mínimo {senha_minima()} caracteres"
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_usuarios SET user_senha=? WHERE user_nome=?",
                    (gerar_hash_senha(nova_senha), user_nome))
        if cur.rowcount == 0:
            return False, "Usuário não existe"
        _commit_com_retry(conn, contexto=f"alterar_senha_admin:{user_nome}")
        marcar_trocar_senha(user_nome, True)
        _fechar_sessoes_central(user_nome)  # senha redefinida -> todas as sessões caem
        _audit(ator, "alterar_senha", user_nome, "senha provisória definida pelo admin; sessões encerradas")
        _log().info(f"senha redefinida (admin): {user_nome} por {ator}")
        return True, "Senha redefinida — sessões encerradas e troca obrigatória no próximo acesso"
    except Exception as e:
        _rollback_seguro(conn, contexto=f"alterar_senha_admin:{user_nome}")
        _log().exception(f"alterar_senha_admin: falha ao redefinir senha de {user_nome} | {e}")
        return False, "Erro inesperado ao redefinir senha"
    finally:
        conn.close()


def liberar_acesso_definitivo(ator, user_nome):
    """Libera em definitivo uma conta que estava em liberação temporária.

    É o botão do DTI — o contrário de `bloqueio_provisorio_pendente`.
    O servidor entra, o prazo de 4 dias vence, a conta fecha; ele vai ao
    departamento de tecnologia, descobre o número do setor e o técnico libera
    aqui. Sem esta função, a conferência seria feita direto no banco, e
    cadastro de servidor não se arruma direto no banco.

    A liberação é definitiva: a conta volta a ser normal. Se o servidor
    estiver sem telefone da prefeitura ainda hoje, o DTI precisa
    cadastrar o número **antes** de chamar esta função — a verificação é
    feita aqui, não na tela, para que a conta não fique "liberada" e
    sem telefone. Se o DTI liberar sem telefone, o paliativo recomeça.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome=?",
                        (user_nome,))
            if not (cur.fetchone()[0] or 0):
                return False, "Usuário não encontrado."
            tem_prefeitura = cur.execute(
                "SELECT COUNT(*) FROM tb_telefone_usuario "
                "WHERE user_nome=? AND papel='empresa' AND tipo='fixo'",
                (user_nome,)).fetchone()[0]
            pendente = cur.execute(
                "SELECT telefone_pendente FROM tb_usuarios WHERE user_nome=?",
                (user_nome,)).fetchone()[0]
        finally:
            conn.close()
        if not tem_prefeitura:
            return False, ("Este cadastro ainda não tem telefone da "
                           "prefeitura (fixo). Cadastre o número — o próprio "
                           "ou o do setor como recado — antes de liberar.")
        cur2 = get_connection()
        try:
            c2 = cur2.cursor()
            c2.execute("UPDATE tb_usuarios SET acesso_provisorio=0, "
                       "provisorio_ate=NULL, telefone_pendente=0, "
                       "user_ativo=1 WHERE user_nome=?", (user_nome,))
            _commit_com_retry(cur2, contexto="liberar_acesso_definitivo")
        finally:
            cur2.close()
        _audit(ator, "liberar_acesso_definitivo", user_nome,
               "liberado em definitivo" + (" (tinha telefone pendente)"
                                           if pendente else ""))
        _log().info(f"acesso liberado em definitivo para {user_nome} por {ator}")
        return True, "Acesso liberado em definitivo."
    except Exception as e:
        _log().exception(f"liberar_acesso_definitivo: falha em {user_nome} | {e}")
        return False, "Erro ao liberar o acesso."


def informacao_acesso_provisorio(user_nome) -> dict:
    """EN: The temporary-release state of an account, for screens and the DTI.

    PT-BR: O estado da liberação temporária de uma conta, para as telas e
    para o DTI ver quem está no prazo e quem já venceu."""
    vazio = {"provisorio": False, "ate": None, "vencido": False,
             "bloqueado": True, "dias_restantes": None}
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT acesso_provisorio, provisorio_ate, user_ativo "
                        "FROM tb_usuarios WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
        finally:
            conn.close()
        if not linha:
            return vazio
        bloqueado = not bool(linha[2])
        if not linha[0] or not linha[1]:
            # sem liberação temporária: a conta é normal. `bloqueado` continua
            # valendo, porque é o que a tela do DTI quer mostrar.
            return {**vazio, "bloqueado": bloqueado}
        try:
            prazo = datetime.strptime(str(linha[1])[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return {**vazio, "bloqueado": bloqueado}
        restante = prazo - datetime.now()
        return {"provisorio": True, "ate": linha[1],
                # `vencido` é o PRAZO. A conta estar bloqueada é outra
                # coisa — no começo estes dois campos eram o mesmo, e uma
                # conta liberada aparecia como vencida no primeiro dia.
                "vencido": restante.total_seconds() <= 0,
                "bloqueado": bloqueado,
                "dias_restantes": max(0, restante.days)}
    except Exception as e:
        _log().exception(f"informacao_acesso_provisorio: falha em {user_nome} | {e}")
        return vazio


def bloquear_usuario(ator, user_nome, bloquear=True):
    """Blocks/unblocks an account (unblock also clears soft-delete).

    Bloqueia (ativo=0). Desbloquear também restaura soft-delete (limpa
    `user_motivo_exclusao`) e ganha trilha dedicada (`bloquear_usuario` /
    `desbloquear_usuario`)."""
    if ator == user_nome and bloquear:
        return False, "Você não pode bloquear a si mesmo"
    try:
        kw = {"deletado": False} if not bloquear else {}
        # 'auditar=False': a ação ganha trilha DEDICADA abaixo (bloquear_usuario ou
        # desbloquear_usuario) em vez de um 'editar_usuario' genérico.
        ok, msg = editar_usuario(ator, user_nome, ativo=(not bloquear), auditar=False, **kw)
        if ok:
            if not bloquear:  # restauração limpa o motivo da exclusão lógica
                conn = _conexao_segura()
                if conn is not None:
                    try:
                        conn.execute("UPDATE tb_usuarios SET user_motivo_exclusao=NULL WHERE user_nome=?",
                                     (user_nome,))
                        _commit_com_retry(conn, contexto=f"bloquear_usuario:{user_nome}")
                    except Exception as e2:
                        _rollback_seguro(conn, contexto=f"bloquear_usuario:{user_nome}")
                        _log().exception(f"bloquear_usuario: falha ao limpar motivo de {user_nome} | {e2}")
                    finally:
                        conn.close()
            if bloquear:
                _fechar_sessoes_central(user_nome)
            _audit(ator, "bloquear_usuario" if bloquear else "desbloquear_usuario",
                   user_nome, "conta bloqueada" if bloquear else "conta restaurada (inclui soft delete)")
            _log().info(f"usuário {'bloqueado' if bloquear else 'restaurado'}: {user_nome} por {ator}")
        return ok, msg
    except Exception as e:
        _log().exception(f"bloquear_usuario: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao bloquear/restaurar conta"


def soft_delete_usuario(ator, user_nome, motivo=None):
    """Logical delete with mandatory reason — moves to the deleted list.

    Exclusão LÓGICA com motivo obrigatório — vai para a lista de
    excluídos. Não apaga nada: reversível via 'Restaurar'. A exclusão
    permanente (LGPD) é ação separada, disponível apenas na lista de
    excluídos."""
    if user_nome == "master":
        return False, "A conta master nativa não pode ser excluída"
    if ator == user_nome:
        return False, "Você não pode excluir a própria conta"
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        return False, "Informe o motivo da exclusão (mín. 3 caracteres)"
    try:
        ok, msg = editar_usuario(ator, user_nome, ativo=False, deletado=True)
        if not ok:
            return ok, msg
        conn = _conexao_segura()
        if conn is not None:
            try:
                conn.execute("UPDATE tb_usuarios SET user_motivo_exclusao=? WHERE user_nome=?",
                             (motivo, user_nome))
                _commit_com_retry(conn, contexto=f"soft_delete:{user_nome}")
            except Exception as e2:
                _rollback_seguro(conn, contexto=f"soft_delete:{user_nome}")
                _log().exception(f"soft_delete_usuario: falha ao gravar motivo de {user_nome} | {e2}")
            finally:
                conn.close()
        _fechar_sessoes_central(user_nome)
        _audit(ator, "soft_delete", user_nome, f"motivo: {motivo}")
        _log().info(f"exclusão lógica: {user_nome} por {ator} | motivo: {motivo}")
        return True, f"'{user_nome}' movido para a lista de excluídos"
    except Exception as e:
        _log().exception(f"soft_delete_usuario: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao excluir usuário"


def _vinculos_cruzados_excluir(user_nome):
    """Removes/anonymizes the user's references in other modules (LGPD).

    Remove/anonimiza referências do usuário nos demais módulos (LGPD).
    Blog: postagens e comentários apagados. EditorPDF: arquivos físicos,
    registros e cota apagados. Empenhos: registros públicos preservados
    com autoria anonimizada.

    Isolamento total: cada módulo limpa o PRÓPRIO banco através de sua
    API pública — nunca há cross-query entre bancos."""
    det = []
    try:
        from mod_blog import bd_manipulador as _blog
        n = _blog.remover_vinculos_usuario(user_nome)
        if n:
            det.append(f"{n} postagem(ns)")
    except Exception as e:
        det.append("blog: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: blog falhou para {user_nome} | {e}")
    try:
        from mod_edit_pdf import bd_manipulador as _pdf
        removidos, nomes = _pdf.remover_vinculos_usuario(user_nome)
        if removidos or nomes:
            det.append(f"{removidos} arquivo(s) PDF")
    except Exception as e:
        det.append("pdf: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: pdf falhou para {user_nome} | {e}")
    try:
        from mod_renomear_empenho import bd_manipulador as _emp
        n = _emp.anonimizar_usuario(user_nome)
        if n:
            det.append(f"{n} empenho(s) anonimizado(s)")
    except Exception as e:
        det.append("empenhos: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: empenhos falhou para {user_nome} | {e}")
    return det


def _vinculos_cruzados_renomear(nome_atual, novo_nome):
    """Propagates a rename to authorship columns in other modules.

    Propaga o renomeio para colunas de autoria nos demais módulos
    (Blog, EditorPDF, Empenhos).

    Isolamento total: cada módulo atualiza o PRÓPRIO banco através de
    sua API pública — nunca há cross-query entre bancos."""
    try:
        from mod_blog import bd_manipulador as _blog
        _blog.renomear_autor(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")
    try:
        from mod_edit_pdf import bd_manipulador as _pdf
        _pdf.renomear_usuario(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")
    try:
        from mod_renomear_empenho import bd_manipulador as _emp
        _emp.renomear_usuario(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")


def excluir_usuario_definitivo(ator, user_nome):
    """Permanently deletes a user (LGPD) with cross-module cleanup.

    Exclusivo do `administrador_geral` (revalidado no backend). Remove
    postagens/comentários do Blog, arquivos/cota do editorPDF e anonimiza
    autoria de empenhos (`_vinculos_cruzados_excluir`), apaga acessos e o
    usuário, encerra sessões e audita `excluir_definitivo`. `master` e a
    própria conta do ator são protegidos; o último admin geral ativo também.
    Retorna `(ok, msg)`."""
    conn = None
    try:
        from mod_intranet import autenticacao  # import tardio: evita ciclo de imports
        if autenticacao.perfil_global_de(ator) != "administrador_geral":
            return False, "Apenas o administrador geral do sistema pode excluir definitivamente (LGPD)"
        if user_nome == "master":
            return False, "A conta master nativa não pode ser excluída"
        if ator == user_nome:
            return False, "Você não pode excluir a própria conta"
        conn = _conexao_segura()
        if conn is None:
            return False, "Falha ao conectar no banco de usuários"
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM tb_usuarios WHERE user_perfil='administrador_geral' AND user_ativo=1 AND user_nome=?",
            (user_nome,),
        )
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_perfil='administrador_geral' AND user_ativo=1")
            if cur.fetchone()[0] <= 1:
                return False, "Não é possível excluir o último administrador ativo"
        detalhes = _vinculos_cruzados_excluir(user_nome)
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=?", (user_nome,))
        cur.execute("DELETE FROM tb_usuarios WHERE user_nome=?", (user_nome,))
        _commit_com_retry(conn, contexto=f"excluir_definitivo:{user_nome}")
        _fechar_sessoes_central(user_nome)
        extra = f" | {', '.join(detalhes)}" if detalhes else ""
        _audit(ator, "excluir_definitivo", user_nome, f"DELETE físico (LGPD){extra}")
        _log().info(f"exclusão definitiva (LGPD): {user_nome} por {ator}{extra}")
        msg = "Usuário excluído definitivamente"
        if detalhes:
            msg += f" ({', '.join(detalhes)})"
        return True, msg
    except Exception as e:
        try:
            _rollback_seguro(conn, contexto=f"excluir_definitivo:{user_nome}")
        except Exception:
            pass
        _log().exception(f"excluir_usuario_definitivo: falha ao excluir {user_nome} | {e}")
        return False, "Erro inesperado ao excluir definitivamente"
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def duplicar_usuario(ator, usuario_origem, novo_nome, senha, email=None,
                     fone=None, nome_completo=""):
    """Duplicates a user with all per-module access (profile + flags).

    Duplica um usuário existente e todas as suas configurações de acesso.
    Copia o perfil global e o papel do usuário origem em cada módulo
    (tb_acesso_usuario, incluindo flags finas). O novo usuário é criado
    exigindo apenas os dados essenciais (login, nome, senha e email) —
    as permissões vêm da origem. Senha vazia/None cai no padrão inicial
    ``123456``.
    """
    try:
        senha = (senha or "").strip() or "123456"
        origem = obter_usuario(usuario_origem)
        if not origem:
            return False, "Usuário origem não encontrado"
        perfil_origem = origem[5]
        ok, msg = criar_usuario(ator, novo_nome, senha,
                                email=email, fone=fone, perfil=perfil_origem,
                                nome_completo=nome_completo)
        if not ok:
            return False, msg
        # replica acessos por módulo (perfil) da origem
        for chave, papel, _liberado, _data in listar_acessos(usuario_origem):
            gest_sys = definir_acesso(ator, novo_nome, chave, papel)
            if not gest_sys[0]:
                _log().warning(f"duplicar_usuario: falha ao replicar acesso {chave} "
                               f"para {novo_nome} | {gest_sys[1]}")
            else:
                _flags_origem = obter_flags(usuario_origem, chave)
                if _flags_origem:
                    ok_f, msg_f = definir_flags(ator, novo_nome, chave, _flags_origem)
                    if not ok_f:
                        _log().warning(f"duplicar_usuario: falha ao replicar flags {chave} "
                                       f"para {novo_nome} | {msg_f}")
        _audit(ator, "duplicar_usuario", novo_nome,
               f"origem={usuario_origem} | perfil={perfil_origem}")
        _log().info(f"usuário duplicado: {novo_nome} a partir de {usuario_origem} por {ator}")
        return True, "Usuário duplicado com as permissões da origem"
    except Exception as e:
        _log().exception(f"duplicar_usuario: falha ao duplicar {novo_nome} a partir de {usuario_origem} | {e}")
        return False, "Erro inesperado ao duplicar usuário"

# ================= PERFIS POR MÓDULO =================

def definir_acesso(ator, user_nome, modulo_chave, papel):
    """Grants a per-module role ('comum'|'administrador'). None removes it.

    Atribui papel do usuário num módulo ('comum'|'administrador'). None
    remove (delega a `remover_acesso`). Upsert idempotente com auditoria
    `definir_acesso`."""
    if papel is None:
        return remover_acesso(ator, user_nome, modulo_chave)
    if papel not in PAPEIS_MODULO:
        return False, f"Papel inválido: {papel}"
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por, data_liberacao)
               VALUES (?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(user_nome, modulo_chave) DO UPDATE SET
                   papel=excluded.papel, liberado_por=excluded.liberado_por,
                   data_liberacao=excluded.data_liberacao""",
            (user_nome, modulo_chave, papel, ator),
        )
        _commit_com_retry(conn, contexto=f"definir_acesso:{user_nome}@{modulo_chave}")
        _audit(ator, "definir_acesso", user_nome, f"{modulo_chave}={papel}")
        _log().info(f"acesso definido: {user_nome} {modulo_chave}={papel} por {ator}")
        return True, f"{modulo_chave}: {papel}"
    except Exception as e:
        _rollback_seguro(conn, contexto=f"definir_acesso:{user_nome}")
        _log().exception(f"definir_acesso: falha ao definir acesso {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao definir acesso"
    finally:
        conn.close()


def remover_acesso(ator, user_nome, modulo_chave):
    """Removes the user's grant on a module and audits it. Returns (ok, msg)."""
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        _commit_com_retry(conn, contexto=f"remover_acesso:{user_nome}@{modulo_chave}")
        _audit(ator, "remover_acesso", user_nome, f"módulo {modulo_chave}")
        _log().info(f"acesso removido: {user_nome} módulo {modulo_chave} por {ator}")
        return True, f"Acesso a '{modulo_chave}' removido"
    except Exception as e:
        _rollback_seguro(conn, contexto=f"remover_acesso:{user_nome}")
        _log().exception(f"remover_acesso: falha ao remover acesso {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao remover acesso"
    finally:
        conn.close()


def obter_papel_no_modulo(user_nome, modulo_chave):
    """Effective role in a module ('administrador'|'comum'|None).

    Retorna 'administrador', 'comum' ou None. O `administrador_geral`
    ativo sempre resolve como 'administrador' em qualquer módulo."""
    conn = _conexao_segura()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_perfil FROM tb_usuarios WHERE user_nome=? AND user_ativo=1",
                    (user_nome,))
        row = cur.fetchone()
        if row and row[0] == "administrador_geral":
            return "administrador"
        cur.execute("SELECT papel FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        _log().exception(f"obter_papel_no_modulo: falha para {user_nome}@{modulo_chave} | {e}")
        return None
    finally:
        conn.close()


def validar_acesso_modulo(user_nome, modulo_chave):
    """True if the user may access the module (used by the core page guard).

    RF-35: o módulo de Auditoria é exclusivo do `administrador_geral`.
    Demais módulos: basta existir vínculo em `tb_acesso_usuario` (o papel
    `administrador` em qualquer módulo é concedido ao admin geral)."""
    try:
        # RF-35: o módulo de Auditoria é exclusivo do administrador geral do sistema.
        if modulo_chave == "auditoria":
            from mod_intranet import autenticacao
            return autenticacao.perfil_global_de(user_nome) == "administrador_geral"
        return obter_papel_no_modulo(user_nome, modulo_chave) is not None
    except Exception as e:
        _log().exception(f"validar_acesso_modulo: falha para {user_nome}@{modulo_chave} | {e}")
        return False


# ================= FLAGS FINAS DE PERMISSÃO (JSON) =================

FLAGS_PERMISSAO = {
    "blog.publicar": "Publicar e editar postagens do blog",
    "blog.comentar": "Comentar nas postagens do blog",
    "blog.configurar": "Configurar exibição e aparência do blog",
}


def _flags_validas(flags):
    """Validates a flags dict against the allowlist catalog.

    Valida o dicionário de flags contra o catálogo (allowlist
    `FLAGS_PERMISSAO`): chaves conhecidas e valores booleanos."""
    if not isinstance(flags, dict):
        return False, "flags deve ser um dicionário {flag: bool}"
    desconhecidas = [k for k in flags if k not in FLAGS_PERMISSAO]
    if desconhecidas:
        return False, f"flags desconhecidas: {', '.join(desconhecidas)}"
    if any(not isinstance(v, bool) for v in flags.values()):
        return False, "valores das flags devem ser booleanos"
    return True, ""


def obter_flags(user_nome, modulo_chave):
    """Reads the fine-grained flags of a grant (dict, fail-soft {}).

    Lê as flags finas do vínculo (dict). Fail-soft: ausente/erro/JSON
    inválido devolve {}."""
    try:
        conn = get_connection()
    except Exception as e:
        _log().exception(f"obter_flags: falha ao conectar para {user_nome}@{modulo_chave} | {e}")
        return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT flags FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        row = cur.fetchone()
        if not row or not row[0]:
            return {}
        try:
            import json
            dados = json.loads(row[0])
        except (ValueError, TypeError):
            return {}
        return dados if isinstance(dados, dict) else {}
    except Exception as e:
        _log().exception(f"obter_flags: falha ao ler flags de {user_nome}@{modulo_chave} | {e}")
        return {}
    finally:
        conn.close()


def definir_flags(ator, user_nome, modulo_chave, flags):
    """Replaces the fine-grained flags of a grant (catalog-validated).

    Substitui as flags finas do vínculo (validadas pelo catálogo
    `FLAGS_PERMISSAO`). Exige vínculo pré-existente em
    `tb_acesso_usuario`."""
    ok, msg = _flags_validas(flags)
    if not ok:
        return False, msg
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        import json
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        if not cur.fetchone():
            return False, f"sem vínculo {user_nome}@{modulo_chave} (libere o acesso primeiro)"
        cur.execute("UPDATE tb_acesso_usuario SET flags=? WHERE user_nome=? AND modulo_chave=?",
                    (json.dumps(flags, sort_keys=True), user_nome, modulo_chave))
        _commit_com_retry(conn, contexto=f"definir_flags:{user_nome}@{modulo_chave}")
        _audit(ator, "definir_flags", user_nome, f"{modulo_chave}={sorted(flags)}")
        _log().info(f"flags definidas: {user_nome} {modulo_chave}={sorted(flags)} por {ator}")
        return True, f"{modulo_chave}: {len(flags)} flag(s)"
    except Exception as e:
        _rollback_seguro(conn, contexto=f"definir_flags:{user_nome}")
        _log().exception(f"definir_flags: falha para {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao definir flags"
    finally:
        conn.close()


def tem_flag(user_nome, modulo_chave, flag):
    """True when the user holds a fine-grained flag (admins pass by role).

    True se o usuário tem a flag (admin global/modular passam pelo papel
    'administrador' sem precisar da flag explícita)."""
    try:
        if obter_papel_no_modulo(user_nome, modulo_chave) == "administrador":
            return True
        return bool(obter_flags(user_nome, modulo_chave).get(flag))
    except Exception:
        return False


# ================= SESSÕES ATIVAS =================

def _fechar_sessoes_central(user_nome):
    """Closes ALL open central sessions of the user (block/delete/password reset)."""
    try:
        c = _central(); cc = c.cursor()
        cc.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE usuario=? AND logout_timestamp IS NULL",
                   (user_nome,))
        c.commit(); c.close()
    except Exception as e:
        _log().warning(f"_fechar_sessoes_central: falha ao encerrar sessões de {user_nome} | {e}")


def registrar_tentativa_login(user_nome):
    """Conta um login errado e devolve o total **dentro da janela**.

    A janela é de 15 min (`mod_intranet.politica_senha.JANELA_TENTATIVAS_SEG`):
    passando dela, a contagem zera sozinha. É o que impede a conta de ficar
    lenta para sempre depois de um período ruim de digitação — e o que impede
    o atacante de só esperar a contagem cair, porque 15 min é pouco tempo para
    girar um dicionário grande.

    Login de usuário que **não existe** também conta, e é de propósito: a
    mensagem de resposta é a mesma nos dois casos ("Usuário ou senha
    inválidos"), então sem contar aqui o atacante testaria logins inexistentes
    de graça — e é assim que se descobre a lista de quem tem conta. A
    `tb_login_tentativas` tem chave estrangeira para `tb_usuarios`, então
    inexistente não tem onde ser gravado: o atraso sai de uma contagem em
    memória, e só para esta requisição.

    Devolve 0 em qualquer falha: perder a contagem só faz o atacante ganhar
    tempo, e um erro aqui jamais pode barrar o servidor legítimo.
    """
    try:
        from mod_intranet import politica_senha as ps
        # Foreign key: usuário inexistente não tem linha em tb_usuarios, e
        # `tb_login_tentativas.user_nome` referencia essa tabela. Gravar
        # falharia com "FOREIGN KEY constraint failed" a cada tentativa — e
        # encher o log de warning a cada erro de digitação.
        if not _usuario_existe_para_tentativa(user_nome):
            # Mesmo efeito, sem tocar no banco: um erro contra um login
            # inexistente não pode custar mais que um erro contra um existente.
            _tentativas_fantasma[str(user_nome)] = 1
            return 1
        conn = get_connection()
        if conn is None:
            return 0
        cur = conn.cursor()
        cur.execute("SELECT falhas, ultima_falha FROM tb_login_tentativas "
                    "WHERE user_nome=?", (user_nome,))
        linha = cur.fetchone()
        falhas = 0
        if linha:
            try:
                ultima = datetime.fromisoformat(str(linha[1]))
                if datetime.now() - ultima <= \
                        timedelta(seconds=ps.JANELA_TENTATIVAS_SEG):
                    falhas = int(linha[0] or 0)
            except Exception:
                falhas = 0
        falhas += 1
        cur.execute("INSERT INTO tb_login_tentativas "
                    "(user_nome, falhas, ultima_falha) VALUES (?, ?, ?) "
                    "ON CONFLICT (user_nome) DO UPDATE SET "
                    "falhas=excluded.falhas, ultima_falha=excluded.ultima_falha",
                    (user_nome, falhas, datetime.now().isoformat()))
        _commit_com_retry(conn, contexto=f"tentativa:{user_nome}")
        conn.close()
        _tentativas_fantasma.pop(str(user_nome), None)
        return falhas
    except Exception as e:
        _log().warning(f"registrar_tentativa_login: falha ao contar tentativa "
                       f"de {user_nome} | {e}")
        return 0


# Contagem em memória para login de usuário INEXISTENTE. Precisa existir
# porque a tabela tem chave estrangeira para `tb_usuarios`, e o usuário que não
# existe é justamente o que o atacante testa de graça. É deliberadamente
# descartável: se o processo reiniciar, a contagem volta a zero e o atacante
# ganha um pouco de tempo — o que não é perda de segurança, porque a resposta
# do sistema é idêntica com e sem ela.
_tentativas_fantasma: dict[str, int] = {}


def _usuario_existe_para_tentativa(user_nome):
    """O login existe em `tb_usuarios`? Falha de banco conta como 'não'."""
    try:
        conn = get_connection()
        if conn is None:
            return False
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tb_usuarios WHERE user_nome=? LIMIT 1",
                    (user_nome,))
        achou = cur.fetchone() is not None
        conn.close()
        return achou
    except Exception:
        return False


def zerar_tentativas_login(user_nome):
    """Login certo: zera a contagem. Sem isso a penalidade vazaria para a sessão
    seguinte de quem entrou certo."""
    try:
        conn = get_connection()
        if conn is None:
            return False
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_login_tentativas WHERE user_nome=?",
                    (user_nome,))
        _commit_com_retry(conn, contexto=f"zerar_tentativas:{user_nome}")
        conn.close()
        _tentativas_fantasma.pop(str(user_nome), None)
        return True
    except Exception as e:
        _log().warning(f"zerar_tentativas_login: falha ao zerar contagem de "
                       f"{user_nome} | {e}")
        return False


def tentativas_login(user_nome):
    """Falhas dentro da janela agora. 0 fora dela."""
    try:
        from mod_intranet import politica_senha as ps
        conn = get_connection()
        if conn is None:
            return 0
        cur = conn.cursor()
        cur.execute("SELECT falhas, ultima_falha FROM tb_login_tentativas "
                    "WHERE user_nome=?", (user_nome,))
        linha = cur.fetchone()
        conn.close()
        if not linha:
            return 0
        try:
            ultima = datetime.fromisoformat(str(linha[1]))
            if datetime.now() - ultima > \
                    timedelta(seconds=ps.JANELA_TENTATIVAS_SEG):
                return 0
        except Exception:
            return 0
        return int(linha[0] or 0)
    except Exception as e:
        _log().warning(f"tentativas_login: falha ao ler contagem de "
                       f"{user_nome} | {e}")
        return 0


def zerar_tentativas_todos():
    """Zera as contagens de todo mundo (admin, no painel de usuários)."""
    try:
        conn = get_connection()
        if conn is None:
            return 0
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_login_tentativas")
        total = cur.rowcount or 0
        _commit_com_retry(conn, contexto="zerar_tentativas: todos")
        conn.close()
        _tentativas_fantasma.clear()
        return total
    except Exception as e:
        _log().warning(f"zerar_tentativas_todos: falha ao zerar contagens | {e}")
        return 0


def listar_sessoes_ativas(usuario=None):
    """Open sessions (no logout) with IP/device/MAC traceability.

    Sessões abertas (sem logout), agora com rastreabilidade
    IP/dispositivo/MAC (colunas do `tb_sessoes` central)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"listar_sessoes_ativas: falha ao abrir conexão central | {e}")
        return []
    try:
        cur = c.cursor()
        sql = """SELECT id, usuario, modulo, login_timestamp, cookie_hash,
                        COALESCE(ip,'—'), COALESCE(dispositivo,'—'), COALESCE(mac,'—')
                 FROM tb_sessoes WHERE logout_timestamp IS NULL"""
        params = []
        if usuario:
            sql += " AND usuario=?"
            params.append(usuario)
        sql += " ORDER BY login_timestamp DESC"
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        _log().exception(f"listar_sessoes_ativas: falha ao listar sessões | {e}")
        return []
    finally:
        c.close()


def contar_sessoes_ativas(usuario):
    """Counts the user's open sessions (logout_timestamp IS NULL)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"contar_sessoes_ativas: falha ao abrir conexão central | {e}")
        return 0
    try:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_sessoes WHERE usuario=? AND logout_timestamp IS NULL",
                    (usuario,))
        return cur.fetchone()[0]
    except Exception as e:
        _log().exception(f"contar_sessoes_ativas: falha para {usuario} | {e}")
        return 0
    finally:
        c.close()


def sessoes_ativas_por_usuario():
    """{usuario: qtd_ativas} — uma única consulta para a tabela inteira."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"sessoes_ativas_por_usuario: falha ao abrir conexão central | {e}")
        return {}
    try:
        cur = c.cursor()
        cur.execute("""SELECT usuario, COUNT(*) FROM tb_sessoes
                       WHERE logout_timestamp IS NULL GROUP BY usuario""")
        return dict(cur.fetchall())
    except Exception as e:
        _log().exception(f"sessoes_ativas_por_usuario: falha ao agrupar sessões | {e}")
        return {}
    finally:
        c.close()


def listar_historico_sessoes(usuario, limite=10):
    """Last CLOSED sessions of a user (LGPD traceability).

    Últimas sessões ENCERRADAS do usuário (rastreabilidade LGPD: entrada,
    saída, duração calculada na tela, IP/dispositivo/MAC)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"listar_historico_sessoes: falha ao abrir conexão central | {e}")
        return []
    try:
        cur = c.cursor()
        cur.execute(
            """SELECT id, modulo, login_timestamp, logout_timestamp,
                      COALESCE(ip,'—'), COALESCE(dispositivo,'—'), COALESCE(mac,'—')
               FROM tb_sessoes
               WHERE usuario=? AND logout_timestamp IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (usuario, int(limite)),
        )
        return cur.fetchall()
    except Exception as e:
        _log().exception(f"listar_historico_sessoes: falha para {usuario} | {e}")
        return []
    finally:
        c.close()


def encerrar_sessao(ator, sessao_id):
    """Closes ONE open session by id and audits it. Returns (ok, msg)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"encerrar_sessao: falha ao abrir conexão central | {e}")
        return False, "Falha ao conectar no banco central"
    try:
        cur = c.cursor()
        cur.execute("SELECT usuario FROM tb_sessoes WHERE id=? AND logout_timestamp IS NULL", (sessao_id,))
        row = cur.fetchone()
        if not row:
            return False, "Sessão já encerrada"
        cur.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE id=?", (sessao_id,))
        c.commit()
        _audit(ator, "encerrar_sessao", row[0], f"sessão #{sessao_id}")
        _log().info(f"sessão encerrada: #{sessao_id} de {row[0]} por {ator}")
        return True, "Sessão encerrada"
    except Exception as e:
        _log().exception(f"encerrar_sessao: falha ao encerrar sessão #{sessao_id} | {e}")
        return False, "Erro inesperado ao encerrar sessão"
    finally:
        c.close()


def encerrar_todas_sessoes(ator, user_nome):
    """Closes ALL open sessions of the user and audits the bulk action."""
    try:
        _fechar_sessoes_central(user_nome)
        _audit(ator, "encerrar_todas_sessoes", user_nome)
        return True, f"Sessões de {user_nome} encerradas"
    except Exception as e:
        _log().exception(f"encerrar_todas_sessoes: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao encerrar sessões"


# ================= VÍNCULOS ÓRFÃOS =================

def listar_vinculos_orfaos(chaves_ativas):
    """Grants pointing at modules no longer registered (orphan links).

    Acessos em `tb_acesso_usuario` apontando para módulos que não existem
    mais no sistema (chave fora de `chaves_ativas`). Na tela aparecem como
    badge INDISPONÍVEL nos seletores."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_nome, modulo_chave, papel FROM tb_acesso_usuario")
        return [(u, m, p) for u, m, p in cur.fetchall() if m not in chaves_ativas]
    except Exception as e:
        _log().exception(f"listar_vinculos_orfaos: falha ao listar vínculos | {e}")
        return []
    finally:
        conn.close()


# ================= COMPATIBILIDADE =================

PERFIS_VALIDOS = PERFIS_GLOBAIS
DB_PATH = DB_CAD_PATH


def validar_acesso_modulo_compat(user_nome, modulo_chave):
    """Backward-compatible alias of `validar_acesso_modulo`."""
    return validar_acesso_modulo(user_nome, modulo_chave)


init_db()
