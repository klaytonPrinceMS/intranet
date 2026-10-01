"""EN: Phone Directory — own database (expandable organogram).
DB: db_mod_lista_telefonica.db (WAL). Tables: tb_unidade (secretaria|setor|subsetor
hierarchical), tb_contato (alphabetical). No cross-query. Phones as free text
with display via mod_intranet.telefone (DDI +55). Search via normalized LIKE in memory.

PT-BR: Lista Telefônica — BD próprio (organograma expansível).
BD: db_mod_lista_telefonica.db (WAL)
Tabelas: tb_unidade (secretaria|setor|subsetor hierárquico), tb_contato (alfabético).
Sem cross-query. Telefones como texto livre com exibição via mod_intranet.telefone
(DDI +55). Busca via LIKE normalizado em memória.
"""

import os
import sys
import re
import time
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# DB_LISTA_PATH removido (morto/isolado): este módulo NUNCA abre SQLite direto.
# Conexão única via mod_intranet.banco_conexao.conexao("lista_telefonica")
# (SQLite db_mod_lista_telefonica.db ou DATABASE db_mod_lista_telefonica no PG).
# DÍVIDA: sem CrudBase — escritas usam transação curta + _commit_com_retry
# (retry "database is locked") + _rollback_seguro; busy_timeout=5000 herdado
# da conexão central (não reconfigurar aqui).

# Organograma base municipal genérico (sem nome de prefeitura/lei)
ORGANOGRAMA_BASE = [
    ("Gabinete", [
        ("Assessoria", ["Comunicação", "Jurídico"]),
        ("Controle Interno", []),
    ]),
    ("Administração", [
        ("Recursos Humanos", ["Folha", "Capacitação"]),
        ("Patrimônio e Almoxarifado", ["Compras", "Licitações"]),
        ("Tecnologia da Informação", ["Suporte", "Redes"]),
    ]),
    ("Finanças", [
        ("Contabilidade", []),
        ("Tesouraria", []),
        ("Tributação", ["Cadastro", "Fiscalização"]),
    ]),
    ("Saúde", [
        ("Atenção Primária", ["ESF", "Vigilância Sanitária"]),
        ("Assistência Farmacêutica", []),
        ("Regulação", ["Transporte Sanitário"]),
    ]),
    ("Educação", [
        ("Pedagógico", ["Ensino Infantil", "Ensino Fundamental"]),
        ("Transporte Escolar", []),
        ("Merenda", []),
    ]),
    ("Obras e Infraestrutura", [
        ("Engenharia", ["Projetos", "Fiscalização"]),
        ("Serviços Urbanos", ["Limpeza", "Iluminação"]),
    ]),
    ("Agricultura", [
        ("Assistência Rural", []),
        ("Abastecimento", []),
    ]),
    ("Meio Ambiente", [
        ("Licenciamento", []),
        ("Fiscalização Ambiental", []),
    ]),
    ("Assistência Social", [
        ("CRAS", []),
        ("CREAS", []),
        ("Conselho Tutelar", []),
    ]),
    ("Cultura", [
        ("Biblioteca", []),
        ("Eventos", []),
    ]),
    ("Esporte e Lazer", [
        ("Esportes", []),
        ("Juventude", []),
    ]),
    ("Planejamento", [
        ("Projetos", []),
        ("Convênios", []),
    ]),
]


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("lista_telefonica")


# Transação curta + retry locked (SQLite WAL "database is locked" residual).
# busy_timeout=5000 herdado de banco_conexao.conexao; não reconfigurar aqui.
TENTATIVAS_LOCKED = 3
ESPERA_LOCKED_SEG = 0.05


def _eh_bloqueio_banco(exc):
    """Verdadeiro quando o erro é contenção transitória (passível de retry)."""
    try:
        texto = str(exc or "").lower()
        return ("database is locked" in texto or "database table is locked" in texto
                or "locked" in texto or "busy" in texto or "deadlock" in texto
                or "could not obtain lock" in texto)
    except Exception:
        return False


def _rollback_seguro(conn, contexto=""):
    """Rollback best-effort que nunca derruba o chamador (AGENTS §3.2)."""
    try:
        if conn is not None:
            conn.rollback()
    except Exception as exc:
        try:
            _log().warning(f"_rollback_seguro[{contexto}]: {exc}")
        except Exception:
            pass


def _commit_com_retry(conn, contexto="", tentativas=None, espera_s=None):
    """Commit com retry curto em contenção ("database is locked").

    Tenta conn.commit() até N vezes quando a falha for bloqueio transitório;
    outra falha propaga ao chamador (que faz rollback + logger.exception).
    """
    try:
        tentativas = tentativas or TENTATIVAS_LOCKED
        espera_s = espera_s if espera_s is not None else ESPERA_LOCKED_SEG
        ultima = None
        for tentativa in range(1, tentativas + 1):
            try:
                conn.commit()
                return True
            except Exception as exc:
                ultima = exc
                if _eh_bloqueio_banco(exc) and tentativa < tentativas:
                    try:
                        _log().warning(f"_commit_com_retry[{contexto}] locked "
                                       f"tentativa {tentativa}/{tentativas}: {exc}")
                    except Exception:
                        pass
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


def get_connection():
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("lista_telefonica")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão lista_telefonica")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        return conn
    except Exception:
        try:
            try:
                _log().exception("get_connection falhou")
            except NameError:
                try:
                    log.exception("get_connection falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("get_connection falhou")
        except Exception:
            pass
        raise


def _audit(ator, acao, alvo, detalhe=""):
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", "lista_telefonica", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception:
        try:
            try:
                _log().exception("_audit falhou")
            except NameError:
                try:
                    log.exception("_audit falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("_audit falhou")
        except Exception:
            pass
        return None


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", s))


def init_db():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_unidade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('secretaria','setor','subsetor')),
                parent_id INTEGER REFERENCES tb_unidade(id) ON DELETE CASCADE,
                ordem INTEGER NOT NULL DEFAULT 0,
                telefone TEXT DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)
        # ---- Origem da unidade: 'folha' ou 'manual' (01/10/2026) ----
        # A lista telefônica é a DONA do organograma: é daqui que todo módulo
        # que precisa de secretaria/setor tira a hierarquia (pela fachada do
        # núcleo). A folha de servidores é a FONTE inicial — ela cria o que a
        # prefeitura tem — mas o administrador pode cadastrar unidade que a
        # folha ainda não publica (uma secretaria recém-criada, um setor em
        # Implantação). Sem esta marca, a próxima sincronização desligava a
        # unidade manual, porque "não está na folha" e "não deveria existir"
        # eram a mesma condição.
        # A marca é o que separa as duas perguntas:
        #   origem='folha'   -> a folha manda: se sumiu dela, desativa.
        #   origem='manual'  -> o administrador manda: a folha não desativa.
        cur.execute("PRAGMA table_info(tb_unidade)")
        _cols_unidade = {r[1] for r in cur.fetchall()}
        if "origem" not in _cols_unidade:
            cur.execute("ALTER TABLE tb_unidade ADD COLUMN origem "
                        "TEXT NOT NULL DEFAULT 'manual'")
        # Banco já existente: as unidades que existiam antes desta coluna já
        # foram criadas pelo administrador ou pela folha — sem distinguir. O
        # padrão 'manual' as PRESERVA, que é o lado seguro: desativar por engano
        # some secretaria da tela; manter uma unidade a mais é só uma pasta
        # vazia, e o administrador desativa quando quiser.
        cur.execute("UPDATE tb_unidade SET origem='folha' "
                    "WHERE (origem IS NULL OR TRIM(origem)='') AND ativo=1 "
                    "AND id IN (SELECT parent_id FROM tb_unidade "
                    "WHERE parent_id IS NOT NULL)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_contato (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unidade_id INTEGER NOT NULL REFERENCES tb_unidade(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL DEFAULT '',
                user_nome TEXT,
                tipo TEXT NOT NULL DEFAULT 'externo' CHECK(tipo IN ('vinculado','externo')),
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_unidade_parent ON tb_unidade(parent_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contato_unidade ON tb_contato(unidade_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contato_nome ON tb_contato(nome)")

        # Dados funcionais no contato (28/09/2026).
        #
        # POR QUE ISSO EXISTE: o contato era "nome + telefone", e quem não
        # autorizou telefone simplesmente NÃO ERA GRAVADO — a busca por nome
        # não encontrava a pessoa, e a lista ficava com folders vazios. As
        # colunas abaixo permitem gravar o servidor SEM número e ainda assim
        # responder "é efetivo?", "qual o cargo?", "de qual secretaria?".
        #
        # O telefone continua sendo opcional e continua vindo só de quem
        # autorizou: o que é público por lei é o posto (nome, cargo, lotação),
        # não o número.
        try:
            cur.execute("SELECT * FROM tb_contato LIMIT 1")
            _cols_contato = {d[0] for d in (cur.description or [])}
        except Exception:
            _cols_contato = set()
        for _col, _def in (("nome_completo", "TEXT DEFAULT ''"),
                           ("cargo", "TEXT DEFAULT ''"),
                           ("lotacao", "TEXT DEFAULT ''"),
                           ("vinculo", "TEXT DEFAULT ''"),
                           ("situacao", "TEXT DEFAULT ''"),
                           ("ativo", "INTEGER NOT NULL DEFAULT 1")):
            if _col not in _cols_contato:
                try:
                    cur.execute(f"ALTER TABLE tb_contato ADD COLUMN {_col} {_def}")
                except Exception:
                    pass

        # Quando a lista foi espelhada do cadastro pela última vez. Existe
        # para a tela saber se está olhando para um diretário velho: os
        # servidores cadastram o telefone no primeiro acesso, e sem isto o
        # diretório só mudaria quando alguém lembrasse de apertar o botão.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_sincronizacao (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                ultima_em DATETIME,
                total_criados INTEGER NOT NULL DEFAULT 0,
                total_atualizados INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("INSERT OR IGNORE INTO tb_sincronizacao (id) VALUES (1)")

        # ---- Organograma: NÃO é semeado (28/09/2026) ----
        # Antes, um banco novo nascia com 12 secretarias de demonstração
        # ("Administração", "Agricultura", "Saúde"...) e seus setores. Numa
        # prefeitura real isso é o pior jeito de começar: a lista
        # telefônica abria mostrando órganos que não existem, com pasta
        # vazia em cada, e o administrador tinha de desativar 60 unidades
        # para chegar nas 9 de verdade.
        #
        # Agora o banco nasce VAZIO e o organograma é o que a folha de
        # servidores trouxer (`mod_gest_cad_usuario/carga_folha.py`).
        # A vantagem de não haver unidade de mentira é que a lista telefônica
        # não há mentira possível: o que aparece é secretaria que tem
        # gente dentro.
        #
        # A constante `ORGANOGRAMA_BASE` continua no arquivo porque a módulo de
        # Solicitação de Impressão lê a estrutura de cargos para semear cotas
        # — e é lá a única coisa de que ela ainda precisa. Ver
        # `integracoes.obter_organograma_base()`.
        cur.execute("SELECT COUNT(*) FROM tb_unidade")
        if cur.fetchone()[0] == 0:
            _log().info(
                "Organograma vazio: será preenchido pela folha de servidores. "
                "Nenhuma unidade de demonstração é criada (28/09/2026).")
        _commit_com_retry(conn, "init_db")
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        try:
            _rollback_seguro(conn, "init_db")
        except Exception:
            pass
        try:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            try:
                _log().exception("init_db falhou")
            except NameError:
                try:
                    log.exception("init_db falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("init_db falhou")
        except Exception:
            pass
        return None


# ============ UNIDADES ============

def listar_unidades(parent_id=None, tipo=None, ativo=1):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            sql = "SELECT id, nome, tipo, parent_id, ordem, telefone, ativo FROM tb_unidade WHERE 1=1"
            params = []
            if parent_id is None:
                sql += " AND parent_id IS NULL"
            else:
                sql += " AND parent_id=?"
                params.append(parent_id)
            if tipo:
                sql += " AND tipo=?"
                params.append(tipo)
            if ativo is not None:
                sql += " AND ativo=?"
                params.append(1 if ativo else 0)
            sql += " ORDER BY ordem ASC, nome ASC"
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("listar_unidades falhou")
            except NameError:
                try:
                    log.exception("listar_unidades falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("listar_unidades falhou")
        except Exception:
            pass
        return []


def listar_todas_unidades():
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nome, tipo, parent_id, ordem, telefone, ativo FROM tb_unidade ORDER BY tipo, ordem, nome")
            return cur.fetchall()
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("listar_todas_unidades falhou")
            except NameError:
                try:
                    log.exception("listar_todas_unidades falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("listar_todas_unidades falhou")
        except Exception:
            pass
        return []


def obter_unidade(uid):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nome, tipo, parent_id, ordem, telefone, ativo FROM tb_unidade WHERE id=?", (uid,))
            return cur.fetchone()
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("obter_unidade falhou")
            except NameError:
                try:
                    log.exception("obter_unidade falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("obter_unidade falhou")
        except Exception:
            pass
        return None


def _pai_valido(tipo, parent_id):
    """A ÚNICA regra de hierarquia do módulo, e vale para criar e para mover.

    A regra cabe numa frase: **secretaria é raiz; qualquer outra unidade pode
    ficar sob qualquer outra.**

    POR QUE A REGRA ANTIGA FOI TIRADA (27/09/2026)
        Antes era `subsetor` só pode ficar sob `setor`, o que travava a
        árvore em **três** degraus. E a prefeitura tem mais: secretaria >
        departamento > unidade de trabalho > posto. O quarto degrau era
        impossível de criar, e o organograma é editável na tela — o
        administrador batia numa parede sem mensagem que explicasse a
        parede. A árvore é `parent_id`, não uma lista de três posições; a
        restrição era do formulário, não do dado.

    O que continua valendo é `secretaria` sem pai, e por um motivo concreto:
        a secretaria é a raiz que dá nome ao organograma e é por ela que a
        cascata da tela começa. Raiz sem nome não é raiz.

    Devolve `(ok, motivo)`.
    """
    if tipo not in ("secretaria", "setor", "subsetor"):
        return False, "Tipo inválido"
    if tipo == "secretaria":
        if parent_id is not None:
            return False, "Secretaria é a raiz do organograma e não tem pai."
        return True, ""
    if parent_id is None:
        return False, (f"{tipo.capitalize()} precisa ficar dentro de uma "
                       f"unidade acima.")
    pai = obter_unidade(parent_id)
    if not pai:
        return False, "Unidade acima não encontrada."
    if pai[2] == "secretaria" and tipo not in ("setor", "subsetor"):
        return False, "Tipo inválido"
    return True, ""


def criar_unidade(nome, tipo, parent_id=None, telefone="", ator="sistema",
                  origem="manual"):
    """EN: Creates one organogram unit. `origem` marks who owns it.

    PT-BR: Cria uma unidade do organograma. `origem` marca quem manda nela.

    `origem='manual'` (padrão) é a criação pelo ADMINISTRADOR — a folha não
    desliga o que ele cadastrou. `origem='folha'` é a criação pela
    sincronização da folha de servidores, e aí a folha manda: se a unidade
    sumir da folha, é desativada na próxima carga (nunca apagada).
    """
    try:
        nome = (nome or "").strip()
        if len(nome) < 2:
            return False, "Nome muito curto"
        if origem not in ("folha", "manual"):
            origem = "manual"
        ok_pai, motivo = _pai_valido(tipo, parent_id)
        if not ok_pai:
            return False, motivo
        conn = get_connection()
        try:
            cur = conn.cursor()
            # verifica duplicado no mesmo pai/tipo
            if parent_id is None:
                cur.execute("SELECT 1 FROM tb_unidade WHERE nome=? AND tipo=? AND parent_id IS NULL LIMIT 1", (nome, tipo))
            else:
                cur.execute("SELECT 1 FROM tb_unidade WHERE nome=? AND tipo=? AND parent_id=? LIMIT 1", (nome, tipo, parent_id))
            if cur.fetchone():
                return False, "Já existe unidade com esse nome no local"
            # ordem = max+1
            if parent_id is None:
                cur.execute("SELECT COALESCE(MAX(ordem),0) FROM tb_unidade WHERE parent_id IS NULL AND tipo=?", (tipo,))
            else:
                cur.execute("SELECT COALESCE(MAX(ordem),0) FROM tb_unidade WHERE parent_id=?", (parent_id,))
            prox = (cur.fetchone()[0] or 0) + 1
            cur.execute("INSERT INTO tb_unidade (nome, tipo, parent_id, ordem, telefone, origem) VALUES (?, ?, ?, ?, ?, ?)",
                        (nome, tipo, parent_id, prox, (telefone or "").strip(),
                         origem))
            nid = cur.lastrowid
            _commit_com_retry(conn, "criar_unidade")
            _audit(ator, "criar_unidade", nome, f"{tipo} id={nid} pai={parent_id} origem={origem}")
            return True, f"Unidade '{nome}' criada (id {nid})"
        except Exception:
            _rollback_seguro(conn, "criar_unidade")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("criar_unidade falhou")
            except NameError:
                try:
                    log.exception("criar_unidade falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("criar_unidade falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def editar_unidade(uid, nome=None, telefone=None, ator="sistema"):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            sets, params = [], []
            if nome is not None:
                n = nome.strip()
                if len(n) < 2:
                    return False, "Nome muito curto"
                sets.append("nome=?"); params.append(n)
            if telefone is not None:
                sets.append("telefone=?"); params.append(telefone.strip())
            if not sets:
                return True, "Nada a alterar"
            params.append(uid)
            cur.execute(f"UPDATE tb_unidade SET {', '.join(sets)} WHERE id=?", tuple(params))  # nosec B608 — sets com literais fixos, valores via ?
            _commit_com_retry(conn, "editar_unidade")
            _audit(ator, "editar_unidade", str(uid), ",".join(sets))
            return True, "Unidade atualizada"
        except Exception:
            _rollback_seguro(conn, "editar_unidade")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("editar_unidade falhou")
            except NameError:
                try:
                    log.exception("editar_unidade falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("editar_unidade falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def excluir_ramo(uid, ator="sistema"):
    """Exclui unidade e todo o ramo (filhos + contatos) — DELETE recursivo manual.

    Portável SQLite↔PostgreSQL: o proxy PG (_CursorPostgres/_ddl_postgres)
    remove REFERENCES/ON DELETE CASCADE do DDL, então NÃO confia em CASCADE
    do banco. Coleta o ramo via _coletar_ramo_ids e apaga na ordem
    contatos → unidades filhas → pai, em transação curta com retry locked.
    """
    try:
        alvo = obter_unidade(uid)
        if not alvo:
            return False, "Unidade não encontrada"
        conn = get_connection()
        try:
            cur = conn.cursor()
            # coleta via recursão simples (portável, sem CTE recursivo)
            ids = _coletar_ramo_ids(cur, uid) or []
            ids.append(uid)
            # 1) contatos de todo o ramo (evita órfãos sem CASCADE no PG)
            # 2) unidades filhas primeiro, pai por último (sem depender de FK)
            try:
                placeholders = ",".join(["?"] * len(ids))
                cur.execute(f"DELETE FROM tb_contato WHERE unidade_id IN ({placeholders})", tuple(ids))  # nosec B608 — placeholders gerados, valores via ?
                for ramo_id in reversed(ids):
                    cur.execute("DELETE FROM tb_unidade WHERE id=?", (ramo_id,))
            except Exception:
                _rollback_seguro(conn, "excluir_ramo")
                raise
            _commit_com_retry(conn, "excluir_ramo")
            _audit(ator, "excluir_ramo", alvo[1], f"ids={ids}")
            return True, f"Ramo '{alvo[1]}' e {len(ids)-1} filho(s) excluído(s)"
        except Exception:
            try:
                _rollback_seguro(conn, "excluir_ramo")
            except Exception:
                pass
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("excluir_ramo falhou")
            except NameError:
                try:
                    log.exception("excluir_ramo falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("excluir_ramo falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def _coletar_ramo_ids(cur, parent_id):
    """Coleta ids descendentes do ramo (portável; sem CTE/FK CASCADE)."""
    try:
        cur.execute("SELECT id FROM tb_unidade WHERE parent_id=?", (parent_id,))
        filhos = [r[0] for r in cur.fetchall()]
        todos = []
        for fid in filhos:
            todos.append(fid)
            todos.extend(_coletar_ramo_ids(cur, fid) or [])
        return todos
    except Exception:
        try:
            try:
                _log().exception("_coletar_ramo_ids falhou")
            except NameError:
                try:
                    log.exception("_coletar_ramo_ids falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("_coletar_ramo_ids falhou")
        except Exception:
            pass
        return []


def mover_unidade(uid, novo_parent_id, ator="sistema"):
    try:
        alvo = obter_unidade(uid)
        if not alvo:
            return False, "Unidade não encontrada"
        tipo = alvo[2]
        # a MESMA regra de criar: secretaria é raiz, o resto fica sob
        # qualquer coisa. Uma validação só, para as duas coisas não divergirem.
        ok_pai, motivo = _pai_valido(tipo, novo_parent_id)
        if not ok_pai:
            return False, motivo
        # evita ciclo
        if novo_parent_id == uid:
            return False, "Não pode mover para si mesmo"
        conn = get_connection()
        try:
            cur = conn.cursor()
            # detecta ciclo via ramo
            if novo_parent_id:
                # verifica se novo pai é descendente do alvo
                cur.execute("SELECT parent_id FROM tb_unidade WHERE id=?", (novo_parent_id,))
                r = cur.fetchone()
                # sobe até raiz
                atual = novo_parent_id
                while atual:
                    if atual == uid:
                        return False, "Movimento criaria ciclo"
                    cur.execute("SELECT parent_id FROM tb_unidade WHERE id=?", (atual,))
                    rr = cur.fetchone()
                    atual = rr[0] if rr else None
            # atualiza ordem para final
            if novo_parent_id is None:
                cur.execute("SELECT COALESCE(MAX(ordem),0) FROM tb_unidade WHERE parent_id IS NULL AND tipo=?", (tipo,))
            else:
                cur.execute("SELECT COALESCE(MAX(ordem),0) FROM tb_unidade WHERE parent_id=?", (novo_parent_id,))
            prox = (cur.fetchone()[0] or 0) + 1
            cur.execute("UPDATE tb_unidade SET parent_id=?, ordem=? WHERE id=?", (novo_parent_id, prox, uid))
            _commit_com_retry(conn, "mover_unidade")
            _audit(ator, "mover_unidade", alvo[1], f"→ pai {novo_parent_id}")
            return True, "Unidade movida"
        except Exception:
            _rollback_seguro(conn, "mover_unidade")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("mover_unidade falhou")
            except NameError:
                try:
                    log.exception("mover_unidade falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("mover_unidade falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def elevar_rebaixar(uid, novo_tipo, ator="sistema", novo_parent_id=None):
    """Promove ou rebaixa o tipo de uma unidade (secretaria / setor / subsetor).

    Com a hierarquia relaxada (ver `_pai_valido`), **qualquer transição é
    possível** e a unidade fica onde está. Virar `secretaria` é a única que
    exige soltar o pai, porque secretaria é raiz.

    `novo_parent_id` é opcional: quem quiser trocar o tipo E o lugar de uma
    vez passa o novo pai aqui. Sem ele, a unidade continua onde está, e
    `mover_unidade` segue sendo o caminho para mudar só o lugar.
    """
    try:
        alvo = obter_unidade(uid)
        if not alvo:
            return False, "Unidade não encontrada"
        tipo_atual = alvo[2]
        parent_atual = alvo[3]
        if novo_tipo not in ("secretaria", "setor", "subsetor"):
            return False, "Tipo inválido"
        # Nova regra (27/09/2026): a hierarquia não tem mais degraus fixos, e
        # portanto NÃO há transição proibida. Antes havia quatro casos fixos e
        # três recusas ("use Mover"); a recusa dupla era o problema — para
        # promover o administrador tinha que escolher "Mover" e depois
        # escolher de novo o tipo: dois passos para uma coisa só.
        novo_parent = parent_atual if novo_parent_id is None else novo_parent_id
        if novo_tipo == "secretaria":
            # secretaria é raiz: mesmo que o chamador tenha mandado um pai,
            # quem manda é a regra
            novo_parent = None
        ok_pai, motivo = _pai_valido(novo_tipo, novo_parent)
        if not ok_pai:
            return False, motivo
        if novo_parent == uid:
            return False, "A unidade não pode ficar dentro dela mesma."
        if novo_parent is not None:
            # nem dentro de um descendente: virar filho do próprio filho
            # é o caminho mais curto para um ciclo na árvore
            acima = obter_unidade(novo_parent)
            while acima is not None and acima[3] is not None:
                if acima[3] == uid:
                    return False, "A unidade não pode ficar dentro de si mesma."
                acima = obter_unidade(acima[3])
        conn = get_connection()
        try:
            cur = conn.cursor()
            # verifica nome duplicado no novo local
            if novo_parent is None:
                cur.execute("SELECT 1 FROM tb_unidade WHERE nome=? AND tipo=? AND parent_id IS NULL AND id<>? LIMIT 1", (alvo[1], novo_tipo, uid))
            else:
                cur.execute("SELECT 1 FROM tb_unidade WHERE nome=? AND tipo=? AND parent_id=? AND id<>? LIMIT 1", (alvo[1], novo_tipo, novo_parent, uid))
            if cur.fetchone():
                return False, "Já existe unidade com esse nome no destino"
            cur.execute("UPDATE tb_unidade SET tipo=?, parent_id=? WHERE id=?", (novo_tipo, novo_parent, uid))
            _commit_com_retry(conn, "elevar_rebaixar")
            _audit(ator, "elevar_rebaixar", alvo[1], f"{tipo_atual}→{novo_tipo}")
            return True, f"Unidade elevada/rebaixada para {novo_tipo}"
        except Exception:
            _rollback_seguro(conn, "elevar_rebaixar")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("elevar_rebaixar falhou")
            except NameError:
                try:
                    log.exception("elevar_rebaixar falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("elevar_rebaixar falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def reordenar_unidades(parent_id, ordem_ids: list[int], ator="sistema"):
    """Reordena unidades irmãs conforme lista de ids na ordem desejada."""
    try:
        if not ordem_ids:
            return True, "Nada a ordenar"
        conn = get_connection()
        try:
            cur = conn.cursor()
            for idx, uid in enumerate(ordem_ids, start=1):
                cur.execute("UPDATE tb_unidade SET ordem=? WHERE id=? AND coalesce(parent_id,-1)=coalesce(?, -1)",
                            (idx, uid, parent_id if parent_id is not None else None))
            _commit_com_retry(conn, "reordenar_unidades")
            _audit(ator, "reordenar", str(parent_id), f"ordem={ordem_ids}")
            return True, "Ordem atualizada"
        except Exception:
            _rollback_seguro(conn, "reordenar_unidades")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("reordenar_unidades falhou")
            except NameError:
                try:
                    log.exception("reordenar_unidades falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("reordenar_unidades falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def buscar_unidades(termo: str):
    try:
        termo_n = _norm(termo)
        if not termo_n:
            return []
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nome, tipo, parent_id, ordem, telefone, ativo FROM tb_unidade WHERE ativo=1")
            todos = cur.fetchall()
            res = []
            for r in todos:
                if termo_n in _norm(r[1]) or termo_n in _norm(r[5]):
                    res.append(r)
            return res
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("buscar_unidades falhou")
            except NameError:
                try:
                    log.exception("buscar_unidades falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("buscar_unidades falhou")
        except Exception:
            pass
        return []

# ============ CONTATOS ============

def listar_contatos(unidade_id: int):
    """Lista contatos da unidade sempre em ordem alfabética (nome).

    Portável SQLite↔PostgreSQL: sem COLLATE NOCASE (SQLite-only na forma usada;
    quebra/falha no PG via proxy). Ordena em Python (casefold) — determinístico
    nos dois backends.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, unidade_id, nome, telefone, user_nome, tipo, data_criacao FROM tb_contato WHERE unidade_id=?", (unidade_id,))
            linhas = cur.fetchall()
            try:
                return sorted(linhas, key=lambda r: ((r[2] or "").casefold(), (r[2] or "")))
            except Exception:
                return linhas
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("listar_contatos falhou")
            except NameError:
                try:
                    log.exception("listar_contatos falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("listar_contatos falhou")
        except Exception:
            pass
        return []


def buscar_contatos(termo: str):
    """Contatos que casam com o termo, em qualquer campo pesquisável.

    A busca é por NOME, telefone, cargo, secretaria, lotação, vínculo e
    situação (28/09/2026). Antes eram só nome, telefone e login: quem
    procurasse "Agente Administrativo" ou "Educação" não achava ninguém, e
    quem não tivesse telefone não estava gravado.

    Devolve DICIONÁRIOS (não tuplas) com `id`, `unidade_id`, `nome`,
    `nome_completo`, `telefone`, `user_nome`, `tipo`, `cargo`, `lotacao`,
    `vinculo`, `situacao`, `ativo` e `sem_telefone`. Dicionário porque a tela
    consome por nome e a lista de campos cresce; tupla por índice obrigaria a
    tela a saber a ordem, e foi assim que um campo novo quebrou o desenho.
    """
    try:
        termo_n = _norm(termo)
        if not termo_n:
            return []
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, unidade_id, nome, telefone, user_nome, tipo, "
                        "nome_completo, cargo, lotacao, vinculo, situacao, ativo "
                        "FROM tb_contato")
            todos = cur.fetchall()
            res = []
            for r in todos:
                alvo = (r[2], r[3] or "", r[4] or "", r[7] or "", r[8] or "",
                        r[9] or "", r[10] or "", r[6] or "")
                if any(termo_n in _norm(a) for a in alvo):
                    res.append({
                        "id": r[0], "unidade_id": r[1], "nome": r[2],
                        "telefone": r[3] or "", "user_nome": r[4] or "",
                        "tipo": r[5] or "", "nome_completo": r[6] or "",
                        "cargo": r[7] or "", "lotacao": r[8] or "",
                        "vinculo": r[9] or "", "situacao": r[10] or "",
                        "ativo": int(r[11] or 0),
                        "sem_telefone": not (r[3] or "").strip(),
                    })
            return res
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("buscar_contatos falhou")
            except NameError:
                try:
                    log.exception("buscar_contatos falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("buscar_contatos falhou")
        except Exception:
            pass
        return []


# Teto de profundidade do organograma. A estrutura é `parent_id`, então o número
# de níveis é livre; o teto existe só para o `montar` não entrar em laço
# infinito se um `parent_id`_cycle for gravado pela tela (o dado é editável).
# 20 níveis cobrem qualquer organograma real de prefeitura com folga.
_PROFUNDIDADE_MAXIMA = 20


def _contato_para_dict(c):
    """Contato da árvore como dicionário, com os dados funcionais (28/09/2026).

    Índices 6 a 11 são `nome_completo`, `cargo`, `lotacao`, `vinculo`,
    `situacao` e `ativo`. São lidos com guarda de tamanho porque a árvore pode
    ser montada a partir de um SELECT antigo em outro ponto do módulo, e um
    `IndexError` aqui derrubaria a tela inteira em vez de mostrar um campo a
    menos.

    `sem_telefone` vem pronto porque é a informação que a tela precisa para
    escrever "sem número informado" em vez de deixar o campo em branco — que
    na leitura parece telefone vazio, e não pessoa que não autorizou.
    """
    telefone = (c[3] or "").strip()
    return {
        "id": c[0], "unidade_id": c[1], "nome": c[2], "telefone": c[3] or "",
        "user_nome": c[4] or "", "tipo": c[5] or "",
        "nome_completo": (c[6] or "") if len(c) > 6 else "",
        "cargo": (c[7] or "") if len(c) > 7 else "",
        "lotacao": (c[8] or "") if len(c) > 8 else "",
        "vinculo": (c[9] or "") if len(c) > 9 else "",
        "situacao": (c[10] or "") if len(c) > 10 else "",
        "ativo": int(c[11]) if len(c) > 11 and c[11] is not None else 1,
        "sem_telefone": not telefone,
    }


def listar_arvore_contatos(raiz_id: int = None, termo: str = ""):
    """Árvore completa de unidades com contatos, em ordem alfabética.

    Usada pela navegação por organograma e pela impressão. A ordem é a mesma em
    tela e no papel, senão a impressão não correspondia ao que o usuário viu:

        Secretaria (alfabética)
          Setor (alfabético)
            Subsetor (alfabético)
              Contato (alfabético)

    `raiz_id` recorta a árvore numa unidade (e nos seus descendentes) para a
    impressão de um trecho só; `None` traz todas. `termo` filtra contatos por
    nome, telefone ou usuário vinculado, normalizado sem acento — o filtro
    mantém as unidades no organograma, mesmo vazias, para não desalinhar a
    leitura do usuário.

    Devolve lista de dicts `{"id", "nome", "tipo", "nivel", "telefone",
    "ativo", "contatos", "filhos"}`. `nivel` é a profundidade (0 na raiz) e
    `filhos` vem preenchido em TODOS os níveis — a montagem é recursiva, e o
    organograma real da prefeitura tem mais de três degraus. (Uma versão
    anterior preenchia `filhos` só na secretaria e tratava setor e subsetor
    como folhas; isso quebrou com unidades reais e foi corrigido em
    27/09/2026.)

    Portável SQLite↔PostgreSQL: a ordenação é feita em Python com `casefold()`
    (nada de `COLLATE NOCASE`, que é SQLite-only e quebra no PG pelo proxy) —
    mesma convenção já usada em `listar_contatos`.
    """
    try:
        termo_n = _norm(termo) if termo else ""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nome, tipo, parent_id, ordem, telefone, ativo "
                        "FROM tb_unidade WHERE ativo=1")
            unidades = cur.fetchall()
            cur.execute("SELECT id, unidade_id, nome, telefone, user_nome, tipo, "
                        "nome_completo, cargo, lotacao, vinculo, situacao, ativo "
                        "FROM tb_contato")
            todos_contatos = cur.fetchall()
        finally:
            conn.close()

        por_unidade = {}
        for c in todos_contatos:
            # A busca cobre também cargo, secretaria, lotação, vínculo e
            # situação (28/09/2026): quem procura "Agente Administrativo" ou
            # "Efetivo" precisa achar a pessoa, e não só quem tem número.
            if termo_n and not any(termo_n in _norm(x or "") for x in
                                   (c[2], c[3], c[4], c[7], c[8], c[9], c[10])):
                continue
            por_unidade.setdefault(c[1], []).append(c)

        def ordenar(linhas):
            return sorted(linhas, key=lambda r: ((r[1] or "").casefold(), (r[1] or "")))

        def self_contatos(linhas):
            """Contatos de uma unidade já como dicionário, ordenados por nome."""
            return [_contato_para_dict(c) for c in
                    sorted(linhas,
                           key=lambda c: ((c[2] or "").casefold(), (c[2] or "")))]

        filhos_por_pai = {}
        for u in unidades:
            filhos_por_pai.setdefault(u[3], []).append(u)

        def montar(u, prof):
            """Monta o dict de uma unidade, já com contatos ordenados.

            Recursivo e SEM limite de profundidade: o organograma tem
            secretaria/setor/subsetor hoje, mas a estrutura é `parent_id` e o
            pedido é aceitar mais níveis. A profundidade entra no dict como
            `nivel` (0 na raiz) para a tela saber quantos botões de
            navegação precisa desenhar, e um teto protege contra ciclo
            acidental de `parent_id` (o dado é editável na tela).
            """
            try:
                if prof > _PROFUNDIDADE_MAXIMA:
                    _log().warning(
                        "listar_arvore_contatos: profundidade %s excedeu o teto "
                        "na unidade %s - suspeita de ciclo em parent_id",
                        prof, u[0])
                    return {"id": u[0], "nome": u[1], "tipo": u[2], "nivel": prof,
                            "telefone": u[5], "ativo": u[6],
                            "contatos": self_contatos(por_unidade.get(u[0], [])),
                            "filhos": []}
                no = {
                    "id": u[0], "nome": u[1], "tipo": u[2], "nivel": prof,
                    "telefone": u[5], "ativo": u[6],
                    "contatos": self_contatos(por_unidade.get(u[0], [])),
                    "filhos": [],
                }
                for f in ordenar(filhos_por_pai.get(u[0], [])):
                    no["filhos"].append(montar(f, prof + 1))
                return no
            except Exception:
                _log().exception("montar da unidade %s falhou", u[0])
                return {"id": u[0], "nome": u[1], "tipo": u[2], "nivel": prof,
                        "telefone": u[5], "ativo": u[6], "contatos": [],
                        "filhos": []}

        if raiz_id is not None:
            raiz = next((u for u in unidades if u[0] == raiz_id), None)
            if not raiz:
                return []
            return [montar(raiz, 0)]

        return [montar(u, 0) for u in ordenar(filhos_por_pai.get(None, []))]
    except Exception:
        try:
            _log().exception("listar_arvore_contatos falhou")
        except NameError:
            try:
                log.exception("listar_arvore_contatos falhou")
            except NameError:
                from mod_intranet import observabilidade as _obs_fail
                _obs_fail.get_logger("lista_telefonica").exception(
                    "listar_arvore_contatos falhou")
        except Exception:
            pass
        return []


def contar_contatos() -> int:
    """Total de contatos cadastrados (rodapé da navegação e da impressão)."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_contato")
            linha = cur.fetchone()
            return int(linha[0]) if linha else 0
        finally:
            conn.close()
    except Exception:
        try:
            _log().exception("contar_contatos falhou")
        except NameError:
            try:
                log.exception("contar_contatos falhou")
            except NameError:
                from mod_intranet import observabilidade as _obs_fail
                _obs_fail.get_logger("lista_telefonica").exception(
                    "contar_contatos falhou")
        except Exception:
            pass
        return 0


def sincronizar_contatos_do_cadastro(contatos, ator="sistema") -> dict:
    """Espelha no diretório os servidores que já cadastraram telefone.

    POR QUE ESTA FUNÇÃO RECEBE DADOS E NÃO BUSCA
        A lista telefônica é dona do banco dela e não pode abrir o banco do
        cadastro de usuários — é a regra do AGENTS.md §2, e o
        `assets/test/check_integridade.py` reprova o import direto. Então
        quem busca é o NÚCLEO (`mod_intranet.integracoes`), que é a costura
        pública entre módulos; esta função só recebe a lista pronta e grava
        no banco dela. Separar quem lê de quem escreve é o que mantém cada
        módulo com um banco só.

    POR QUE ISTO EXISTE
        A lista vivia de contatos digitados à mão, um por um, e a
        prefeitura tem mais de mil servidores. Digitar mil nomes não é
        solução, é dívida. O cadastro já tem nome, matrícula, secretaria,
        cargo e — depois do primeiro acesso — o telefone que a pessoa
        autorizou. Este é o caminho que leva um dado ao outro.

    O QUE É CRIADO
        Um `tb_contato` do tipo `vinculado`, apontando para o `user_nome`
        (a matrícula). O nome mostrado é primeiro + último, e o telefone é o
        publicável — o particular nunca chega aqui, porque quem busca já
        devolve só os liberados.

    O QUE NÃO É TOCADO
        - Contato do tipo `externo` (empresa fornecedora, visitante): é da
          prefeitura, não do cadastro de servidores. A sincronização
          jamais mexe neles.
        - Contato `vinculado` que o administrador editou à mão para outra
          unidade: só o telefone é atualizado, o nome e a unidade ficam. Um
          servidor que foi transferido de setor é caso do RH; mudar isso
          atrás das costas do administrador apagaria um ajuste manual.

    Idempotente: rodar mil vezes não cria mil contatos.

    `contatos` é a lista de dicionários com `user_nome`, `nome_exibicao`,
    `telefone`, `unidade` e `lotacao`.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nome, tipo, parent_id, ordem, telefone, ativo "
                        "FROM tb_unidade")
            unidades = cur.fetchall()
            # Traz os dados funcionais (7 a 12) porque a atualização de um
            # contato já espelhado compara telefone E posto — sem os campos
            # aqui, quem mudasse de cargo ou passasse a efetivo nunca
            # atualizaria na lista.
            cur.execute("SELECT id, unidade_id, nome, telefone, user_nome, tipo, "
                        "nome_completo, cargo, lotacao, vinculo, situacao, ativo "
                        "FROM tb_contato")
            contatos_existentes = cur.fetchall()
        finally:
            conn.close()

        # nome normalizado -> unidades ATIVAS com esse nome. Só as ativas
        # entram: as de demonstração foram desativadas pela sincronização do
        # organograma, e casar com elas esconderia o servidor num lugar morto.
        consulta = {}
        for u in unidades:
            if u[6]:
                consulta.setdefault(_norm(u[1]), []).append(u)

        por_user = {}
        for c in contatos_existentes:
            if c[4] and c[5] == 'vinculado':
                por_user[c[4]] = c

        resumo = {"criados": 0, "atualizados": 0, "sem_unidade": 0,
                  "sem_telefone": 0, "ja_iguais": 0, "rejeitados": 0}

        # Prepara a lista ANTES de gravar. Separar as fases é o que permite
        # uma transção só: `criar_contato` por pessoa custava ~480 ms (uma
        # conexão e um commit cada), e o espelhamento de 1.165 servidores
        # levava quase dez minutos — com a tela esperando. Aqui é UMA
        # conexão e UM commit para o lote inteiro.
        a_criar, a_atualizar = [], []
        # (unidade_id, nome) já existente — mesma trava de `criar_contato`
        nomes_por_unidade = {}
        for c in contatos_existentes:
            nomes_por_unidade.setdefault((c[1], c[2]), set()).add(c[2])

        for s in (contatos or []):
            telefone = (s.get("telefone") or "").strip()
            # SEM TELEFONE A PESSOA ENTRA ASSIM MESMO (28/09/2026).
            #
            # Antes, telefone vazio era `continue`: a pessoa não era gravada.
            # Com a folha do RH populada e ninguém tendo autorizado número
            # ainda, a lista ficava com ZERO contatos e buscar o nome de um
            # servidor não retornava nada — a lista telefônica inexistia.
            #
            # O telefone continua sendo o que o consentimento protege: quem
            # não autorizou fica com o campo VAZIO, e é isso que a tela
            # mostra. O que entra sem autorização é o posto (nome, cargo,
            # secretaria, lotação, vínculo), que é publicação legal.
            nome_exibicao = (s.get("nome_exibicao") or "").strip()
            nome_completo = (s.get("nome_completo") or "").strip()
            cargo = (s.get("cargo") or "").strip()
            lotacao = (s.get("lotacao") or "").strip()
            vinculo = (s.get("vinculo") or "").strip()
            situacao = (s.get("situacao") or "").strip()
            if len(nome_exibicao) < 2:
                resumo["rejeitados"] += 1
                continue
            if not telefone:
                resumo["sem_telefone"] += 1
            elif len(telefone) < 8:
                resumo["rejeitados"] += 1
                continue
            # tenta o departamento (lotação); se não existir, a secretaria
            unid = None
            if s.get("lotacao"):
                unid = next((u[0] for u in consulta.get(_norm(s["lotacao"]), [])),
                            None)
            if unid is None and s.get("unidade"):
                unid = next((u[0] for u in consulta.get(_norm(s["unidade"]), [])),
                            None)
            if unid is None:
                resumo["sem_unidade"] += 1
                continue

            existente = por_user.get(s["user_nome"])
            if existente:
                # Atualiza telefone E dados funcionais. Antes, quem já estava
                # espelhado e depois autorizava o número era atualizado só no
                # telefone; e quem já estava sem número simplesmente não
                # existia para ser atualizado. Agora as duas coisas andam juntas,
                # e a comparação é de todos os campos que vieram do cadastro.
                dados = (telefone, nome_completo, cargo, lotacao, vinculo,
                         situacao, 1 if s.get("ativo", True) else 0)
                if (existente[3] or "") != telefone or \
                        (len(existente) > 7 and list(existente[7:13]) != list(dados[1:])):
                    a_atualizar.append((dados, existente[0]))
                else:
                    resumo["ja_iguais"] += 1
                continue
            if nome_exibicao in nomes_por_unidade.get(unid, set()):
                # já existe um contato com esse nome na mesma unidade: não é
                # duplicar, é colidir. O cadastro manda, então o espelhamento
                # recusa e conta.
                resumo["rejeitados"] += 1
                continue
            nomes_por_unidade.setdefault(unid, set()).add(nome_exibicao)
            a_criar.append((unid, nome_exibicao, telefone, s["user_nome"],
                            nome_completo, cargo, lotacao, vinculo, situacao,
                            1 if s.get("ativo", True) else 0))

        if a_atualizar or a_criar:
            conn = get_connection()
            try:
                cur = conn.cursor()
                for dados, cid in a_atualizar:
                    cur.execute(
                        "UPDATE tb_contato SET telefone=?, nome_completo=?, "
                        "cargo=?, lotacao=?, vinculo=?, situacao=?, ativo=? "
                        "WHERE id=?", (dados[0], dados[1], dados[2], dados[3],
                                       dados[4], dados[5], dados[6], int(cid)))
                if a_criar:
                    # `executemany` em vez de um INSERT por linha: mesmo
                    # resultado, uma ida ao driver em vez de mais de mil.
                    cur.executemany(
                        "INSERT INTO tb_contato "
                        "(unidade_id, nome, telefone, user_nome, tipo, "
                        " nome_completo, cargo, lotacao, vinculo, situacao, ativo) "
                        "VALUES (?, ?, ?, ?, 'vinculado', ?, ?, ?, ?, ?, ?)",
                        [tuple(c) for c in a_criar])
                _commit_com_retry(conn, contexto="sincronizar_contatos:lote")
            except Exception:
                _rollback_seguro(conn, contexto="sincronizar_contatos:lote")
                _log().exception("sincronizar_contatos_do_cadastro: lote falhou")
                return {**resumo, "erro": True}
            finally:
                conn.close()
            resumo["atualizados"] = len(a_atualizar)
            resumo["criados"] = len(a_criar)
            # UM registro de auditoria para o lote, e não um por contato:
            # são o mesmo ato ("espelhei o cadastro"), feito uma vez.
            _audit(ator, "sincronizar_contatos",
                   f"{len(a_criar)} criados / {len(a_atualizar)} atualizados",
                   f"descartados: {resumo['sem_telefone']} sem telefone, "
                   f"{resumo['sem_unidade']} sem unidade, "
                   f"{resumo['rejeitados']} rejeitados")

        _log().info(
            "sincronizar_contatos_do_cadastro: "
            f"criados={resumo['criados']} atualizados={resumo['atualizados']} "
            f"iguais={resumo['ja_iguais']} sem_unidade={resumo['sem_unidade']} "
            f"sem_telefone={resumo['sem_telefone']}")
        _carregar_sincronizacao(resumo["criados"], resumo["atualizados"])
        return resumo
    except Exception:
        _log().exception("sincronizar_contatos_do_cadastro falhou")
        return {"criados": 0, "atualizados": 0, "sem_unidade": 0,
                "sem_telefone": 0, "ja_iguais": 0, "erro": True}


# Tempo que o diretório pode ficar velho antes de a tela reespelhar sozinho.
# Longo o bastante para não lêr o cadastro a cada F5 de quem está digitando a
# busca, curto o bastante para que o número informado no primeiro acesso
# apareça no mesmo dia.
INTERVALO_REFRESH_MIN = 15


def _carregar_sincronizacao(criados=0, atualizados=0):
    """Grava o carimbo da última sincronização. Nunca levanta.

    A hora vem do PYTHON, e não de `CURRENT_TIMESTAMP` do banco. Motivo: o
    SQLite grava `CURRENT_TIMESTAMP` em UTC e o Python compara em hora
    local — três horas de diferença num servidor brasileiro, o que fazia a
    subtração dar NEGATIVO e a tela nunca mais notar que o diretório tinha
    envelhecido. A sincronização automática ficaria desligada para sempre,
    em silêncio. Um relógio que nunca dispara é pior do que nenhum relógio.
    """
    try:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE tb_sincronizacao SET ultima_em=?, "
                "total_criados=?, total_atualizados=? WHERE id=1",
                (agora, int(criados or 0), int(atualizados or 0)))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        _log().warning("não foi possível gravar o carimbo de sincronização")


def sincronizacao_desatualizada() -> bool:
    """True se o diretório está velho demais para ser mostrado sem reespelhar.

    Devolve True quando nunca houve sincronização também — o banco recém-criado
    tem o carimbo zerado, e nesse caso o diretório está literalmente vazio.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT ultima_em FROM tb_sincronizacao WHERE id=1")
            linha = cur.fetchone()
        finally:
            conn.close()
        if not linha or not linha[0]:
            return True
        ultima = str(linha[0])
        # O banco devolve o carimbo em formatos diferentes (SQLite:
        # "2026-09-27 19:40:00"; Postgres via proxy pode vir com "T" e
        # fuso). Cortar nos 19 caracteres pega a parte YYYY-MM-DD HH:MM:SS
        # nos dois, e a comparação é feita em hora local nos dois lados.
        try:
            marca = datetime.strptime(ultima[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return True
        idade = (datetime.now() - marca).total_seconds()
        # Idade negativa significa carimbo no futuro: relógio fora de hora,
        # não diretório novo. Tratar como desatualizado é a leitura segura —
        # reespelhar de novo é barato e barato-não-dói.
        if idade < 0:
            _log().warning(
                "carimbo de sincronização está no futuro (%s); reespelhando",
                ultima)
            return True
        return idade > INTERVALO_REFRESH_MIN * 60
    except Exception:
        _log().warning("sincronizacao_desatualizada: falha na leitura do carimbo")
        return False


def criar_contato(unidade_id: int, nome: str, telefone: str, user_nome: str = None, ator="sistema"):
    try:
        nome = (nome or "").strip()
        if len(nome) < 2:
            return False, "Nome muito curto"
        tel = (telefone or "").strip()
        if len(tel) < 8:
            return False, "Telefone muito curto"
        uni = obter_unidade(unidade_id)
        if not uni:
            return False, "Unidade não encontrada"
        tipo = "vinculado" if user_nome else "externo"
        conn = get_connection()
        try:
            cur = conn.cursor()
            # duplicado na mesma unidade?
            cur.execute("SELECT 1 FROM tb_contato WHERE unidade_id=? AND nome=? LIMIT 1", (unidade_id, nome))
            if cur.fetchone():
                return False, "Já existe contato com esse nome na unidade"
            cur.execute("INSERT INTO tb_contato (unidade_id, nome, telefone, user_nome, tipo) VALUES (?, ?, ?, ?, ?)",
                        (unidade_id, nome, tel, user_nome, tipo))
            nid = cur.lastrowid
            _commit_com_retry(conn, "criar_contato")
            _audit(ator, "criar_contato", nome, f"unidade={unidade_id} tel={tel} tipo={tipo}")
            return True, f"Contato '{nome}' criado (id {nid})"
        except Exception:
            _rollback_seguro(conn, "criar_contato")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("criar_contato falhou")
            except NameError:
                try:
                    log.exception("criar_contato falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("criar_contato falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def editar_contato(cid, nome=None, telefone=None, ator="sistema"):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            sets, params = [], []
            if nome is not None:
                n = nome.strip()
                if len(n) < 2:
                    return False, "Nome muito curto"
                sets.append("nome=?"); params.append(n)
            if telefone is not None:
                t = telefone.strip()
                if len(t) < 8:
                    return False, "Telefone muito curto"
                sets.append("telefone=?"); params.append(t)
            if not sets:
                return True, "Nada a alterar"
            params.append(cid)
            cur.execute(f"UPDATE tb_contato SET {', '.join(sets)} WHERE id=?", tuple(params))  # nosec B608 — sets com literais fixos, valores via ?
            _commit_com_retry(conn, "editar_contato")
            _audit(ator, "editar_contato", str(cid), ",".join(sets))
            return True, "Contato atualizado"
        except Exception:
            _rollback_seguro(conn, "editar_contato")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("editar_contato falhou")
            except NameError:
                try:
                    log.exception("editar_contato falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("editar_contato falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def excluir_contato(cid, ator="sistema"):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT nome FROM tb_contato WHERE id=?", (cid,))
            r = cur.fetchone()
            if not r:
                return False, "Contato não encontrado"
            cur.execute("DELETE FROM tb_contato WHERE id=?", (cid,))
            _commit_com_retry(conn, "excluir_contato")
            _audit(ator, "excluir_contato", r[0], f"id={cid}")
            return True, "Contato excluído"
        except Exception:
            _rollback_seguro(conn, "excluir_contato")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("excluir_contato falhou")
            except NameError:
                try:
                    log.exception("excluir_contato falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("excluir_contato falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def transferir_contato(cid, nova_unidade_id: int, ator="sistema"):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT nome, unidade_id FROM tb_contato WHERE id=?", (cid,))
            r = cur.fetchone()
            if not r:
                return False, "Contato não encontrado"
            nome, old_uid = r
            if old_uid == nova_unidade_id:
                return True, "Já está nesta unidade"
            dest = obter_unidade(nova_unidade_id)
            if not dest:
                return False, "Unidade destino não encontrada"
            # verifica duplicado
            cur.execute("SELECT 1 FROM tb_contato WHERE unidade_id=? AND nome=? LIMIT 1", (nova_unidade_id, nome))
            if cur.fetchone():
                return False, "Já existe contato com esse nome na unidade destino"
            cur.execute("UPDATE tb_contato SET unidade_id=? WHERE id=?", (nova_unidade_id, cid))
            _commit_com_retry(conn, "transferir_contato")
            _audit(ator, "transferir_contato", nome, f"{old_uid}→{nova_unidade_id}")
            return True, "Contato transferido"
        except Exception:
            _rollback_seguro(conn, "transferir_contato")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("transferir_contato falhou")
            except NameError:
                try:
                    log.exception("transferir_contato falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("transferir_contato falhou")
        except Exception:
            pass
        return False, "Erro interno. Tente novamente."


def contar_unidades():
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_unidade")
            return cur.fetchone()[0]
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("contar_unidades falhou")
            except NameError:
                try:
                    log.exception("contar_unidades falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("contar_unidades falhou")
        except Exception:
            pass
        return 0


def remover_vinculos_usuario(user_nome: str) -> int:
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM tb_contato WHERE user_nome=?", (user_nome,))
            n = cur.rowcount
            _commit_com_retry(conn, "remover_vinculos_usuario")
            if n:
                _audit("sistema", "remover_vinculos_lista", user_nome, f"{n} contato(s)")
            return n
        except Exception:
            _rollback_seguro(conn, "remover_vinculos_usuario")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("remover_vinculos_usuario falhou")
            except NameError:
                try:
                    log.exception("remover_vinculos_usuario falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("remover_vinculos_usuario falhou")
        except Exception:
            pass
        return None


def renomear_usuario(nome_atual: str, novo_nome: str):
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE tb_contato SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
            cur.execute("UPDATE tb_contato SET nome=? WHERE nome=? AND tipo='vinculado'", (novo_nome, nome_atual))
            _commit_com_retry(conn, "renomear_usuario")
        except Exception:
            _rollback_seguro(conn, "renomear_usuario")
            raise
        finally:
            conn.close()
    except Exception:
        try:
            try:
                _log().exception("renomear_usuario falhou")
            except NameError:
                try:
                    log.exception("renomear_usuario falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("renomear_usuario falhou")
        except Exception:
            pass
        return None


def _origens_por_unidade():
    """EN: `{unidade_id: 'folha'|'manual'}` — fail-soft `{}` on any failure.

    PT-BR: `{unidade_id: 'folha'|'manual'}` — `{}` em qualquer falha.

    Banco sem a coluna `origem` (instalação anterior a 01/10/2026 que não
    passou pelo `init_db`) devolve vazio, e o chamador trata a ausência como
    'manual' — o lado que preserva a unidade em vez de desligá-la.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, origem FROM tb_unidade")
            return {linha[0]: (linha[1] or "manual") for linha in cur.fetchall()}
        finally:
            conn.close()
    except Exception as e:
        try:
            _log().warning(f"_origens_por_unidade: falha ({e}) — "
                           f"assumindo 'manual' (preserva)")
        except Exception:
            pass
        return {}


def sincronizar_organograma(plano, aplicar=True, ator="sistema"):
    """Grava o organograma recebido da folha de servidores, nesta lista.

    ESTA é a função de escrita do organograma, e ela mora aqui porque o banco é
    deste módulo. Quem chama é o módulo de cadastro de usuários, e chega pela
    fachada do núcleo (`mod_intranet.integracoes.sincronizar_organograma_cadastro`)
    — a regra do repositório é que módulo de negócio não importe outro módulo
    de negócio, nem para ler e muito menos para escrever (AGENTS.md §2, e
    `check_integridade.py` reprova).

    `plano` é uma lista FLAT, de raiz para a folha, de tuplas
    `(nome, tipo, nome_do_pai_ou_None, ordem)`. Flat e com o pai por NOME
    porque quem monta o plano é quem tem a folha, e a folha tem nome de
    departamento, não id de banco. A profundidade é livre: N subsetores de N
    subsetores, que é a regra do organograma desde 28/09/2026.

    Casa por nome normalizado (`_norm`: sem acento, sem caixa, só letras e
    números), que é a MESMA regra usada para casar servidor com unidade — duas
    grafias de "Saúde" são a mesma secretaria, e tratar como duas criaria
    organograma partido.

    Devolve `{"secretarias_criadas", "setores_criados", "reativadas",
    "desativadas", "erros"}`. Nunca levanta exceção.
    """
    resumo = {"secretarias_criadas": 0, "setores_criados": 0,
              "reativadas": 0, "desativadas": 0, "erros": []}
    try:
        existentes = listar_todas_unidades() or []
        # (parent_id, nome normalizado) -> linha
        por_chave = {}
        for u in existentes:
            por_chave.setdefault((u[3], _norm(u[1])), u)
        # nome normalizado -> id, para resolver o pai
        id_por_nome = {_norm(u[1]): u[0] for u in existentes if not u[3]}

        def _ativar(unidade_id, valor):
            conn = get_connection()
            try:
                conn.execute("UPDATE tb_unidade SET ativo=? WHERE id=?",
                             (int(valor), int(unidade_id)))
                _commit_com_retry(conn, "sincronizar_organograma")
            finally:
                conn.close()

        def _marcar_origem(unidade_id, valor):
            """Grava a origem sem reabrir a unidade nem mexer na ordem."""
            conn = get_connection()
            try:
                conn.execute("UPDATE tb_unidade SET origem=? WHERE id=?",
                             (valor, int(unidade_id)))
                _commit_com_retry(conn, "sincronizar_organograma_origem")
            finally:
                conn.close()

        reais = set()
        for item in plano or []:
            nome = (item[0] or "").strip()
            tipo = (item[1] or "setor").strip()
            pai_nome = item[2] if len(item) > 2 else None
            if not nome:
                continue
            pai_id = id_por_nome.get(_norm(pai_nome)) if pai_nome else None
            chave = (pai_id, _norm(nome))
            reais.add(chave)
            achada = por_chave.get(chave)
            if achada:
                # A folha volta a ser dona desta unidade: é ela que decide o
                # que desativa daqui para frente.
                if aplicar:
                    _marcar_origem(achada[0], "folha")
                if not achada[6]:  # existe mas está desligada -> a unidade voltou
                    if aplicar:
                        _ativar(achada[0], 1)
                    resumo["reativadas"] += 1
                if not pai_id:
                    id_por_nome.setdefault(_norm(nome), achada[0])
                continue
            if aplicar:
                ok, msg = criar_unidade(nome, tipo, pai_id, "", ator,
                                        origem="folha")
                if not ok:
                    resumo["erros"].append(f"{tipo} '{nome}': {msg}")
                    continue
                # `criar_unidade` devolve (ok, msg); o id novo é lido do banco
                # em vez de fazer regex na mensagem de retorno.
                novas = listar_todas_unidades() or []
                achada2 = next((u for u in novas
                                if u[3] == pai_id and _norm(u[1]) == _norm(nome)),
                               None)
                if not achada2:
                    resumo["erros"].append(
                        f"{tipo} '{nome}': criado mas não encontrado")
                    continue
                if not pai_id:
                    id_por_nome.setdefault(_norm(nome), achada2[0])
            if tipo == "secretaria":
                resumo["secretarias_criadas"] += 1
            else:
                resumo["setores_criados"] += 1

        # O que a folha não conhece é desativado — nunca apagado: pode haver
        # contato apontando para a unidade, e apagar deixaria órfão.
        # Só conta/desativa o que está LIGADO, para rodar duas vezes não
        # inflar o contador.
        #
        # **EXCETO a unidade que o ADMINISTRADOR cadastrou** (01/10/2026). A
        # lista telefônica é a dona do organograma, e a folha é só a fonte
        # INICIAL: o administrador pode criar uma secretaria ou um setor que a
        # folha ainda não publica, e aí a folha não tem opinião sobre ele —
        # tratá-lo como "sumiu da folha" desligaria, na carga seguinte, a
        # unidade que o administrador acabou de criar. É o mesmo motivo pelo
        # qual o desativamento nunca apaga: some da tela é pior do que sobrar
        # uma pasta vazia.
        #
        # `listar_todas_unidades` traz colunas fixas (id, nome, tipo, parent_id,
        # ordem, telefone, ativo) e a origem é lida à parte — acrescentar uma
        # coluna ao SELECT mudaria a posição em que o chamador lê `ativo`, que
        # é `[6]` em todo o código do módulo e da fachada.
        origem_por_id = _origens_por_unidade()
        for u in existentes:
            if (u[3], _norm(u[1])) in reais or not u[6]:
                continue
            if (origem_por_id.get(u[0]) or "manual") != "folha":
                resumo["preservadas_manual"] = resumo.get(
                    "preservadas_manual", 0) + 1
                continue
            if aplicar:
                _ativar(u[0], 0)
            resumo["desativadas"] += 1
        return resumo
    except Exception as e:
        try:
            _log().exception(f"sincronizar_organograma falhou: {e}")
        except Exception:
            pass
        resumo["erros"].append(str(e))
        return resumo


init_db()
