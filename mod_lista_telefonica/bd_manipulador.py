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

        # seed organograma base (idempotente)
        cur.execute("SELECT COUNT(*) FROM tb_unidade")
        if cur.fetchone()[0] == 0:
            ordem_sec = 1
            for sec_nome, setores in ORGANOGRAMA_BASE:
                cur.execute("INSERT INTO tb_unidade (nome, tipo, parent_id, ordem, telefone) VALUES (?, 'secretaria', NULL, ?, '')",
                            (sec_nome, ordem_sec))
                sec_id = cur.lastrowid
                ordem_sec += 1
                ordem_set = 1
                for set_nome, subsetores in setores:
                    cur.execute("INSERT INTO tb_unidade (nome, tipo, parent_id, ordem, telefone) VALUES (?, 'setor', ?, ?, '')",
                                (set_nome, sec_id, ordem_set))
                    set_id = cur.lastrowid
                    ordem_set += 1
                    ordem_sub = 1
                    for sub_nome in subsetores:
                        cur.execute("INSERT INTO tb_unidade (nome, tipo, parent_id, ordem, telefone) VALUES (?, 'subsetor', ?, ?, '')",
                                    (sub_nome, set_id, ordem_sub))
                        ordem_sub += 1
            _log().info(f"Organograma base semeado: {len(ORGANOGRAMA_BASE)} secretarias")
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


def criar_unidade(nome, tipo, parent_id=None, telefone="", ator="sistema"):
    try:
        nome = (nome or "").strip()
        if len(nome) < 2:
            return False, "Nome muito curto"
        if tipo not in ("secretaria", "setor", "subsetor"):
            return False, "Tipo inválido"
        # valida parent
        if tipo == "secretaria" and parent_id is not None:
            return False, "Secretaria não pode ter pai"
        if tipo == "setor":
            p = obter_unidade(parent_id) if parent_id else None
            if not p or p[2] != "secretaria":
                return False, "Setor deve estar sob secretaria"
        if tipo == "subsetor":
            p = obter_unidade(parent_id) if parent_id else None
            if not p or p[2] != "setor":
                return False, "Subsetor deve estar sob setor"
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
            cur.execute("INSERT INTO tb_unidade (nome, tipo, parent_id, ordem, telefone) VALUES (?, ?, ?, ?, ?)",
                        (nome, tipo, parent_id, prox, (telefone or "").strip()))
            nid = cur.lastrowid
            _commit_com_retry(conn, "criar_unidade")
            _audit(ator, "criar_unidade", nome, f"{tipo} id={nid} pai={parent_id}")
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
        # valida novo pai conforme tipo
        if tipo == "secretaria":
            if novo_parent_id is not None:
                return False, "Secretaria não pode ser movida para dentro de outra"
        elif tipo == "setor":
            p = obter_unidade(novo_parent_id) if novo_parent_id else None
            if not p or p[2] != "secretaria":
                return False, "Setor deve ficar sob secretaria"
        elif tipo == "subsetor":
            p = obter_unidade(novo_parent_id) if novo_parent_id else None
            if not p or p[2] != "setor":
                return False, "Subsetor deve ficar sob setor"
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


def elevar_rebaixar(uid, novo_tipo, ator="sistema"):
    """Eleva setor→secretaria ou rebaixa secretaria→setor etc."""
    try:
        alvo = obter_unidade(uid)
        if not alvo:
            return False, "Unidade não encontrada"
        tipo_atual = alvo[2]
        parent_atual = alvo[3]
        if novo_tipo == tipo_atual:
            return True, "Já está no tipo solicitado"
        if novo_tipo not in ("secretaria", "setor", "subsetor"):
            return False, "Tipo inválido"
        # regras de elevação/rebaixamento
        # secretaria ↔ setor : setor vira secretaria (parent NULL), secretaria vira setor (precisa escolher secretaria pai)
        # setor ↔ subsetor : similar
        # Para simplificar, exige que o chamador informe novo_parent via mover depois; aqui só troca tipo quando compatível sem pai
        # Se elevar setor→secretaria, parent deve ir para NULL
        # Se rebaixar secretaria→setor, parent deve ser secretaria (exige escolha)
        # Esta função apenas troca tipo quando parent atual já é compatível ou NULL
        novo_parent = parent_atual
        if tipo_atual == "setor" and novo_tipo == "secretaria":
            novo_parent = None
        elif tipo_atual == "secretaria" and novo_tipo == "setor":
            return False, "Para rebaixar secretaria a setor, use Mover e escolha a secretaria de destino"
        elif tipo_atual == "subsetor" and novo_tipo == "setor":
            # subsetor virar setor: precisa estar sob secretaria
            p = obter_unidade(parent_atual) if parent_atual else None
            if p:
                # sobe um nível: parent do setor
                novo_parent = p[3]  # parent do setor atual
            else:
                novo_parent = None
        elif tipo_atual == "setor" and novo_tipo == "subsetor":
            return False, "Para transformar setor em subsetor, use Mover para um setor pai"
        else:
            return False, "Transição não suportada diretamente — use Mover"

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
    try:
        termo_n = _norm(termo)
        if not termo_n:
            return []
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, unidade_id, nome, telefone, user_nome, tipo, data_criacao FROM tb_contato")
            todos = cur.fetchall()
            res = []
            for r in todos:
                if termo_n in _norm(r[2]) or termo_n in _norm(r[3]) or termo_n in _norm(r[4] or ""):
                    res.append(r)
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


init_db()
