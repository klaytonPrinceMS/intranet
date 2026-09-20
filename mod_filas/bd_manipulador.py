"""Filas module — call manager with TV, multi-queues and media playlist.

EN: Queue/call manager with TV, multiple queues and media playlist (own DB
    db_mod_filas.db). Tables tb_fila, tb_fila_etapa (sequential flow),
    tb_chamada, tb_midia (TV playlist), tb_config_filas. Access via
    banco_conexao; no cross-query.

Módulo Filas — gestor de chamadas com TV, múltiplas filas e mídia.

BD próprio: db_mod_filas.db (WAL).
Tabelas: tb_fila, tb_fila_etapa (fluxo sequencial), tb_chamada, tb_midia (playlist TV), tb_config_filas.
Acesso via banco_conexao; sem cross-query.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILAS_PATH = os.path.join(BASE_DIR, "db_mod_filas.db")
PASTA_MIDIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midia")


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("filas")


def get_connection():
    from mod_intranet.banco_conexao import conexao
    conn = conexao("filas")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão mod_filas")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def _audit(ator, acao, alvo, detalhe=""):
    from mod_intranet.bd_manipulador import audit_log
    audit_log(ator or "sistema", "filas", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))


def _colunas_tabela(cur, tabela):
    try:
        rows = cur.execute(f"PRAGMA table_info({tabela})").fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def _garantir_coluna(cur, tabela, coluna, definicao):
    cols = _colunas_tabela(cur, tabela)
    if coluna not in cols:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # tb_fila base
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_fila (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            senha_atual TEXT NOT NULL DEFAULT 'A000',
            status TEXT NOT NULL DEFAULT 'ativa',
            guiche TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # migração colunas novas
    _garantir_coluna(cur, "tb_fila", "endereco", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "descricao", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "prefixo", "TEXT DEFAULT 'A'")
    _garantir_coluna(cur, "tb_fila", "criado_por", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "senha_inicio", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "senha_fim", "INTEGER DEFAULT 0")
    _garantir_coluna(cur, "tb_fila", "tv_grupo", "TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_fila_etapa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fila_id INTEGER NOT NULL REFERENCES tb_fila(id) ON DELETE CASCADE,
            ordem INTEGER NOT NULL,
            nome TEXT NOT NULL,
            guiche TEXT DEFAULT '',
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fila_etapa_fila ON tb_fila_etapa(fila_id, ordem)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_chamada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fila_id INTEGER NOT NULL REFERENCES tb_fila(id) ON DELETE CASCADE,
            senha TEXT NOT NULL,
            guiche TEXT,
            chamado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            chamado_por TEXT
        )
    """)
    _garantir_coluna(cur, "tb_chamada", "paciente_nome", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_chamada", "etapa_nome", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_chamada", "fila_nome", "TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_midia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('audio','video')),
            caminho TEXT NOT NULL,
            arquivo_original TEXT DEFAULT '',
            ordem INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config_filas (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    for k, v in (("filas_modo_tv", "1"), ("filas_senha_prefixo", "A"), ("filas_guiche_padrao", "01")):
        cur.execute("INSERT OR IGNORE INTO tb_config_filas (chave, valor) VALUES (?, ?)", (k, v))

    # seed fila Geral (criada por sistema, visível só ao admin geral até ter dono — legada mantém compatibilidade)
    cur.execute("INSERT OR IGNORE INTO tb_fila (nome, senha_atual, status, guiche, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo) VALUES ('Geral', 'A000', 'ativa', '01', '', 'Fila geral de atendimento', 'A', '', 1, 0, '')")
    # seed etapas padrão para Geral se vazia (Atendimento → Triagem → Consultório 3)
    cur.execute("SELECT COUNT(*) FROM tb_fila_etapa WHERE fila_id=(SELECT id FROM tb_fila WHERE nome='Geral')")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM tb_fila WHERE nome='Geral'")
        gid = cur.fetchone()
        if gid:
            gid = gid[0]
            for i, (nome, guiche) in enumerate([("Atendimento", "01"), ("Triagem", "02"), ("Consultório 3", "03")], start=1):
                cur.execute("INSERT INTO tb_fila_etapa (fila_id, ordem, nome, guiche) VALUES (?, ?, ?, ?)", (gid, i, nome, guiche))

    os.makedirs(PASTA_MIDIA, exist_ok=True)
    conn.commit()
    conn.close()


# ============ FILAS ============

def listar_filas():
    """Lista TODAS as filas (uso interno/admin). Retorna tupla com 13 colunas incluindo criado_por, senha_inicio/fim, tv_grupo."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, senha_atual, status, guiche, data_criacao, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo FROM tb_fila ORDER BY nome")
        return cur.fetchall()
    finally:
        conn.close()


def listar_filas_visiveis(user_nome: str, perfil_global: str = "", eh_admin_modulo: bool = False):
    """Filas visíveis ao usuário: dono (criado_por) ou admin geral/modulo vê todas. Legado com criado_por vazio fica visível a todos até ser assumido."""
    eh_admin_geral = (perfil_global == "administrador_geral")
    eh_admin = eh_admin_geral or eh_admin_modulo
    if eh_admin:
        return listar_filas()
    conn = get_connection()
    try:
        cur = conn.cursor()
        # dono ou legado vazio
        cur.execute("""
            SELECT id, nome, senha_atual, status, guiche, data_criacao, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo
            FROM tb_fila
            WHERE criado_por=? OR criado_por='' OR criado_por IS NULL
            ORDER BY nome
        """, (user_nome,))
        return cur.fetchall()
    finally:
        conn.close()


def obter_fila(fila_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, senha_atual, status, guiche, data_criacao, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo FROM tb_fila WHERE id=?", (fila_id,))
        return cur.fetchone()
    finally:
        conn.close()


def obter_fila_por_nome(nome: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, senha_atual, status, guiche, data_criacao, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo FROM tb_fila WHERE nome=?", (nome,))
        return cur.fetchone()
    finally:
        conn.close()


def listar_grupos_tv():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT tv_grupo FROM tb_fila WHERE tv_grupo IS NOT NULL AND tv_grupo<>'' ORDER BY tv_grupo")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def criar_fila(nome: str, endereco: str = "", descricao: str = "", prefixo: str = "A", guiche: str = "01", ator: str = "", senha_inicio: int = 1, senha_fim: int = 0, tv_grupo: str = ""):
    nome = (nome or "").strip()
    if not nome:
        return False, "Nome da fila é obrigatório"
    endereco = (endereco or "").strip()
    descricao = (descricao or "").strip()
    prefixo = (prefixo or "A").strip().upper()[:2] or "A"
    guiche = (guiche or "01").strip()
    if not re.match(r"^[A-Za-z0-9]+$", prefixo):
        return False, "Prefixo deve ser letras/números (ex: A, B, AMB)"
    try:
        senha_inicio = int(senha_inicio) if str(senha_inicio).strip() != "" else 1
    except Exception:
        return False, "Início deve ser número"
    try:
        senha_fim = int(senha_fim) if str(senha_fim).strip() != "" else 0
    except Exception:
        return False, "Fim deve ser número ou 0 para infinito"
    if senha_inicio < 0:
        return False, "Início não pode ser negativo"
    if senha_fim != 0 and senha_fim < senha_inicio:
        return False, "Fim deve ser >= início ou 0 para infinito"
    conn = get_connection()
    try:
        cur = conn.cursor()
        # senha_atual inicia em inicio-1 para que o próximo seja inicio
        senha_atual = f"{prefixo}{(senha_inicio - 1):03d}" if senha_inicio > 0 else f"{prefixo}000"
        # padding dinâmico: se inicio/fim >999 usa 4+ dígitos
        if senha_inicio > 999 or senha_fim > 999:
            senha_atual = f"{prefixo}{(senha_inicio - 1):04d}" if senha_inicio > 0 else f"{prefixo}0000"
        tv_grupo = (tv_grupo or "").strip()
        cur.execute("INSERT INTO tb_fila (nome, senha_atual, status, guiche, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo) VALUES (?, ?, 'ativa', ?, ?, ?, ?, ?, ?, ?, ?)",
                    (nome, senha_atual, guiche, endereco, descricao, prefixo, ator or "", senha_inicio, senha_fim, tv_grupo))
        conn.commit()
        fid = cur.lastrowid
        # etapas padrão
        for i, (et_nome, et_guiche) in enumerate([("Atendimento", guiche), ("Triagem", ""), ("Consultório 3", "")], start=1):
            cur.execute("INSERT INTO tb_fila_etapa (fila_id, ordem, nome, guiche) VALUES (?, ?, ?, ?)", (fid, i, et_nome, et_guiche))
        conn.commit()
        _audit(ator or "sistema", "criar_fila", nome, f"endereco={endereco} prefixo={prefixo} inicio={senha_inicio} fim={senha_fim} tv=/tv/{fid}")
        return True, fid
    except Exception as e:
        if "UNIQUE" in str(e):
            return False, f"Já existe fila com nome '{nome}'"
        _log().exception(f"criar_fila falhou: {e}")
        return False, str(e)
    finally:
        conn.close()


def atualizar_fila(fila_id: int, nome: str = None, endereco: str = None, descricao: str = None, prefixo: str = None, guiche: str = None, status: str = None, senha_inicio=None, senha_fim=None, tv_grupo: str = None, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome, senha_inicio, senha_fim, prefixo, senha_atual FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return False, "Fila não encontrada"
        sets = []
        vals = []
        if nome is not None:
            nome = nome.strip()
            if not nome:
                return False, "Nome não pode ser vazio"
            sets.append("nome=?"); vals.append(nome)
        if endereco is not None:
            sets.append("endereco=?"); vals.append(endereco.strip())
        if descricao is not None:
            sets.append("descricao=?"); vals.append(descricao.strip())
        if prefixo is not None:
            prefixo = prefixo.strip().upper()[:2] or "A"
            sets.append("prefixo=?"); vals.append(prefixo)
        if guiche is not None:
            sets.append("guiche=?"); vals.append(guiche.strip())
        if status is not None:
            sets.append("status=?"); vals.append(status.strip())
        if senha_inicio is not None:
            try:
                si = int(senha_inicio) if str(senha_inicio).strip() != "" else row[1]
            except Exception:
                return False, "Início deve ser número"
            sets.append("senha_inicio=?"); vals.append(si)
        if senha_fim is not None:
            try:
                sf = int(senha_fim) if str(senha_fim).strip() != "" else row[2]
                # permite string vazia/0 para infinito
                if str(senha_fim).strip() == "":
                    sf = 0
            except Exception:
                return False, "Fim deve ser número"
            sets.append("senha_fim=?"); vals.append(sf)
        if tv_grupo is not None:
            sets.append("tv_grupo=?"); vals.append((tv_grupo or "").strip())
        if not sets:
            return True, "Nada a atualizar"
        vals.append(fila_id)
        cur.execute(f"UPDATE tb_fila SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
        _audit(ator or "sistema", "atualizar_fila", str(fila_id), ",".join(sets))
        return True, "Fila atualizada"
    except Exception as e:
        if "UNIQUE" in str(e):
            return False, "Já existe fila com esse nome"
        return False, str(e)
    finally:
        conn.close()


def excluir_fila(fila_id: int, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return False, "Fila não encontrada"
        nome = row[0]
        if nome == "Geral":
            return False, "Fila Geral não pode ser excluída"
        cur.execute("DELETE FROM tb_fila WHERE id=?", (fila_id,))
        conn.commit()
        _audit(ator or "sistema", "excluir_fila", nome)
        return True, f"Fila '{nome}' excluída"
    finally:
        conn.close()


def excluir_todas_filas(ator: str = "", somente_do_criador: str = None, eh_admin: bool = False):
    """Exclui uma ou todas as filas (exceto Geral). Se somente_do_criador informado e não eh_admin, exclui só as do criador."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if eh_admin or not somente_do_criador:
            cur.execute("SELECT COUNT(*) FROM tb_fila WHERE nome<>'Geral'")
            total = cur.fetchone()[0]
            if total == 0:
                return False, "Nenhuma fila para excluir (só Geral)"
            cur.execute("DELETE FROM tb_fila WHERE nome<>'Geral'")
        else:
            cur.execute("SELECT COUNT(*) FROM tb_fila WHERE nome<>'Geral' AND criado_por=?", (somente_do_criador,))
            total = cur.fetchone()[0]
            if total == 0:
                return False, "Você não tem filas para excluir"
            cur.execute("DELETE FROM tb_fila WHERE nome<>'Geral' AND criado_por=?", (somente_do_criador,))
        conn.commit()
        _audit(ator or "sistema", "excluir_todas_filas", f"{total} filas", f"admin={eh_admin} criador={somente_do_criador}")
        return True, f"{total} fila(s) excluída(s)"
    finally:
        conn.close()


# ============ ETAPAS ============

def listar_etapas(fila_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, fila_id, ordem, nome, guiche, ativo FROM tb_fila_etapa WHERE fila_id=? ORDER BY ordem", (fila_id,))
        return cur.fetchall()
    finally:
        conn.close()


def criar_etapa(fila_id: int, nome: str, guiche: str = "", ator: str = ""):
    nome = (nome or "").strip()
    if not nome:
        return False, "Nome da etapa é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tb_fila WHERE id=?", (fila_id,))
        if not cur.fetchone():
            return False, "Fila não encontrada"
        cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM tb_fila_etapa WHERE fila_id=?", (fila_id,))
        ordem = cur.fetchone()[0]
        cur.execute("INSERT INTO tb_fila_etapa (fila_id, ordem, nome, guiche) VALUES (?, ?, ?, ?)", (fila_id, ordem, nome, (guiche or "").strip()))
        conn.commit()
        _audit(ator or "sistema", "criar_etapa", nome, f"fila={fila_id} ordem={ordem}")
        return True, "Etapa criada"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def atualizar_etapa(etapa_id: int, nome: str = None, guiche: str = None, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets = []; vals = []
        if nome is not None:
            nome = nome.strip()
            if not nome:
                return False, "Nome não pode ser vazio"
            sets.append("nome=?"); vals.append(nome)
        if guiche is not None:
            sets.append("guiche=?"); vals.append(guiche.strip())
        if not sets:
            return True, "Nada a atualizar"
        vals.append(etapa_id)
        cur.execute(f"UPDATE tb_fila_etapa SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
        return True, "Etapa atualizada"
    finally:
        conn.close()


def excluir_etapa(etapa_id: int, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_fila_etapa WHERE id=?", (etapa_id,))
        conn.commit()
        return True, "Etapa excluída"
    finally:
        conn.close()


def reordenar_etapas(fila_id: int, ordem_ids: list[int]):
    conn = get_connection()
    try:
        cur = conn.cursor()
        for idx, eid in enumerate(ordem_ids, start=1):
            cur.execute("UPDATE tb_fila_etapa SET ordem=? WHERE id=? AND fila_id=?", (idx, eid, fila_id))
        conn.commit()
        return True, "Ordem atualizada"
    finally:
        conn.close()


# ============ CHAMADAS ============

def _proxima_senha(atual: str, prefixo: str, inicio: int, fim: int):
    """Calcula próxima senha respeitando inicio/fim (0=infinito) com padding dinâmico."""
    prefixo = (prefixo or "A").strip() or "A"
    inicio = int(inicio) if inicio else 1
    fim = int(fim) if fim else 0
    atual = (atual or "").strip()
    m = re.match(r"([A-Za-z]*)(\d+)", atual)
    if m:
        pref = m.group(1) or prefixo
        num = int(m.group(2))
        prox = num + 1
    else:
        pref = prefixo
        prox = inicio
    if fim and fim > 0 and prox > fim:
        prox = inicio  # reinicia no início (circular); infinito quando fim=0
    # padding: 3 se max<1000 senão 4+
    max_n = max(prox, inicio, fim if fim else 0)
    width = 4 if max_n > 999 else 3
    return f"{pref}{prox:0{width}d}"


def gerar_senha(fila_id: int, ator: str = "", paciente_nome: str = "", etapa_nome: str = "") -> tuple[bool, str]:
    """Gera próxima senha da fila e registra chamada na etapa informada (ou primeira)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome, senha_atual, prefixo, guiche, senha_inicio, senha_fim FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return False, "Fila não encontrada"
        fila_nome, atual, prefixo, guiche_fila, senha_inicio, senha_fim = row
        senha_inicio = senha_inicio if senha_inicio is not None else 1
        senha_fim = senha_fim if senha_fim is not None else 0
        nova = _proxima_senha(atual, prefixo, senha_inicio, senha_fim)
        # etapa destino
        if not etapa_nome:
            cur.execute("SELECT nome, guiche FROM tb_fila_etapa WHERE fila_id=? ORDER BY ordem LIMIT 1", (fila_id,))
            et = cur.fetchone()
            if et:
                etapa_nome, guiche_et = et
                guiche = guiche_et or guiche_fila
            else:
                etapa_nome = "Atendimento"
                guiche = guiche_fila
        else:
            cur.execute("SELECT guiche FROM tb_fila_etapa WHERE fila_id=? AND nome=?", (fila_id, etapa_nome))
            et = cur.fetchone()
            guiche = (et[0] if et and et[0] else guiche_fila) if et else guiche_fila

        paciente_nome = (paciente_nome or "").strip()
        cur.execute("UPDATE tb_fila SET senha_atual=? WHERE id=?", (nova, fila_id))
        cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por, paciente_nome, etapa_nome, fila_nome) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (fila_id, nova, guiche, ator or "sistema", paciente_nome, etapa_nome, fila_nome))
        conn.commit()
        _audit(ator or "sistema", "gerar_senha", nova, f"fila={fila_nome} etapa={etapa_nome} paciente={paciente_nome}")
        return True, nova
    except Exception as e:
        _log().exception(f"gerar_senha falhou: {e}")
        return False, str(e)
    finally:
        conn.close()


def avancar_chamada(chamada_id: int, ator: str = "") -> tuple[bool, str]:
    """Avança chamada para próxima etapa da mesma fila (sequencial)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT fila_id, senha, paciente_nome, etapa_nome, fila_nome FROM tb_chamada WHERE id=?", (chamada_id,))
        row = cur.fetchone()
        if not row:
            return False, "Chamada não encontrada"
        fila_id, senha, paciente_nome, etapa_atual, fila_nome = row
        cur.execute("SELECT id, nome, guiche, ordem FROM tb_fila_etapa WHERE fila_id=? ORDER BY ordem", (fila_id,))
        etapas = cur.fetchall()
        if not etapas:
            return False, "Fila sem etapas configuradas"
        idx = -1
        for i, (_, nome, _, _) in enumerate(etapas):
            if nome == etapa_atual:
                idx = i
                break
        if idx == -1:
            prox = etapas[0]
        elif idx + 1 >= len(etapas):
            return False, "Já está na última etapa"
        else:
            prox = etapas[idx + 1]
        prox_id, prox_nome, prox_guiche, prox_ordem = prox
        cur.execute("SELECT guiche FROM tb_fila WHERE id=?", (fila_id,))
        guiche_fila = cur.fetchone()[0] or "01"
        guiche = prox_guiche or guiche_fila
        cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por, paciente_nome, etapa_nome, fila_nome) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (fila_id, senha, guiche, ator or "sistema", paciente_nome, prox_nome, fila_nome))
        conn.commit()
        _audit(ator or "sistema", "avancar_chamada", senha, f"fila={fila_nome} {etapa_atual} -> {prox_nome}")
        return True, f"Avançado para {prox_nome}"
    except Exception as e:
        _log().exception(f"avancar_chamada falhou: {e}")
        return False, str(e)
    finally:
        conn.close()


def ultima_chamada(fila_id: int = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if fila_id:
            cur.execute("SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome FROM tb_chamada WHERE fila_id=? ORDER BY id DESC LIMIT 1", (fila_id,))
        else:
            cur.execute("SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome FROM tb_chamada ORDER BY id DESC LIMIT 1")
        return cur.fetchone()
    finally:
        conn.close()


def ultima_chamada_tv(fila_id: int = None, tv_grupo: str = None):
    """Última chamada para TV isolada (fila_id) ou compartilhada (tv_grupo). Se tv_grupo fornecido, busca em todas as filas do grupo."""
    if tv_grupo:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=?", (tv_grupo,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return None
            placeholders = ",".join("?" for _ in ids)
            cur.execute(f"SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome FROM tb_chamada WHERE fila_id IN ({placeholders}) ORDER BY id DESC LIMIT 1", ids)
            return cur.fetchone()
        finally:
            conn.close()
    return ultima_chamada(fila_id)


def listar_chamadas(limite: int = 20, fila_id: int = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if fila_id:
            cur.execute("SELECT id, fila_id, senha, guiche, chamado_em, chamado_por, paciente_nome, etapa_nome, fila_nome FROM tb_chamada WHERE fila_id=? ORDER BY id DESC LIMIT ?", (fila_id, limite))
        else:
            cur.execute("SELECT id, fila_id, senha, guiche, chamado_em, chamado_por, paciente_nome, etapa_nome, fila_nome FROM tb_chamada ORDER BY id DESC LIMIT ?", (limite,))
        return cur.fetchall()
    finally:
        conn.close()


def listar_chamadas_tv(limite: int = 20, fila_id: int = None, tv_grupo: str = None):
    if tv_grupo:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=?", (tv_grupo,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            cur.execute(f"SELECT id, fila_id, senha, guiche, chamado_em, chamado_por, paciente_nome, etapa_nome, fila_nome FROM tb_chamada WHERE fila_id IN ({placeholders}) ORDER BY id DESC LIMIT ?", ids + [limite])
            return cur.fetchall()
        finally:
            conn.close()
    return listar_chamadas(limite, fila_id)


# ============ MIDIA ============

def listar_midias(somente_ativas=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if somente_ativas:
            cur.execute("SELECT id, nome, tipo, caminho, arquivo_original, ordem, ativo, criado_em FROM tb_midia WHERE ativo=1 ORDER BY ordem, id")
        else:
            cur.execute("SELECT id, nome, tipo, caminho, arquivo_original, ordem, ativo, criado_em FROM tb_midia ORDER BY ordem, id")
        return cur.fetchall()
    finally:
        conn.close()


def adicionar_midia(nome: str, tipo: str, caminho: str, arquivo_original: str = "", ator: str = ""):
    if tipo not in ("audio", "video"):
        return False, "Tipo deve ser audio ou video"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM tb_midia")
        ordem = cur.fetchone()[0]
        cur.execute("INSERT INTO tb_midia (nome, tipo, caminho, arquivo_original, ordem) VALUES (?, ?, ?, ?, ?)",
                    ((nome or arquivo_original or tipo).strip(), tipo, caminho, arquivo_original, ordem))
        conn.commit()
        _audit(ator or "sistema", "adicionar_midia", nome, f"tipo={tipo}")
        return True, "Mídia adicionada"
    finally:
        conn.close()


def excluir_midia(midia_id: int, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT caminho FROM tb_midia WHERE id=?", (midia_id,))
        row = cur.fetchone()
        if not row:
            return False, "Mídia não encontrada"
        caminho = row[0]
        try:
            full = os.path.join(PASTA_MIDIA, os.path.basename(caminho)) if not os.path.isabs(caminho) else caminho
            if os.path.exists(full) and PASTA_MIDIA in os.path.abspath(full):
                os.remove(full)
        except Exception:
            pass
        cur.execute("DELETE FROM tb_midia WHERE id=?", (midia_id,))
        conn.commit()
        _audit(ator or "sistema", "excluir_midia", str(midia_id))
        return True, "Mídia excluída"
    finally:
        conn.close()


def reordenar_midias(ordem_ids: list[int]):
    conn = get_connection()
    try:
        cur = conn.cursor()
        for idx, mid in enumerate(ordem_ids, start=1):
            cur.execute("UPDATE tb_midia SET ordem=? WHERE id=?", (idx, mid))
        conn.commit()
        return True, "Ordem atualizada"
    finally:
        conn.close()


def set_midia_ativa(midia_id: int, ativo: bool):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_midia SET ativo=? WHERE id=?", (1 if ativo else 0, midia_id))
        conn.commit()
        return True, "ok"
    finally:
        conn.close()


def montar_rotas_static():
    try:
        from nicegui import app
        os.makedirs(PASTA_MIDIA, exist_ok=True)
        app.add_static_files("/midia_filas", PASTA_MIDIA)
    except Exception as e:
        try:
            from mod_intranet import observabilidade
            observabilidade.get_logger("filas").warning(f"montar_rotas_static midia falhou: {e}")
        except Exception:
            pass


def remover_vinculos_usuario(user_nome: str) -> int:
    return 0


def renomear_usuario(nome_atual: str, novo_nome: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_chamada SET chamado_por=? WHERE chamado_por=?", (novo_nome, nome_atual))
        cur.execute("UPDATE tb_fila SET criado_por=? WHERE criado_por=?", (novo_nome, nome_atual))
        conn.commit()
    finally:
        conn.close()


init_db()
