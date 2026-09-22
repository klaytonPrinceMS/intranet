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
import unicodedata

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


def _migrar_midia_para_imagem(cur):
    """Migra CHECK antigo de tb_midia (só audio/video) para aceitar imagem.

    Recria a tabela preservando dados quando o CHECK ainda não inclui
    'imagem'. Falha silenciosa no backend Postgres (tabela nova já nasce certa).
    """
    try:
        row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='tb_midia'"
        ).fetchone()
    except Exception:
        return
    if not row or not row[0]:
        return
    if "imagem" in (row[0] or ""):
        return
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_midia_nova (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('audio','video','imagem')),
                caminho TEXT NOT NULL,
                arquivo_original TEXT DEFAULT '',
                ordem INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                fila_id INTEGER REFERENCES tb_fila(id) ON DELETE CASCADE,
                volume INTEGER NOT NULL DEFAULT 40,
                duracao INTEGER NOT NULL DEFAULT 8,
                slot INTEGER NOT NULL DEFAULT 0,
                duracao_real REAL,
                fundo INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            INSERT INTO tb_midia_nova
                (id, nome, tipo, caminho, arquivo_original, ordem, ativo, criado_em, fila_id, volume, duracao, slot, duracao_real, fundo)
            SELECT id, nome, tipo, caminho, arquivo_original, ordem, ativo, criado_em, fila_id, volume, duracao, slot, duracao_real, 0
            FROM tb_midia
        """)
        cur.execute("DROP TABLE tb_midia")
        cur.execute("ALTER TABLE tb_midia_nova RENAME TO tb_midia")
    except Exception as e:
        try:
            _log().warning(f"migracao tb_midia imagem ignorada: {e}")
        except Exception:
            pass


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
    # voz: quais campos são falados + repetição automática
    _garantir_coluna(cur, "tb_fila", "voz_nome", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_senha", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_destino", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_guiche", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_fila", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_hora", "INTEGER DEFAULT 1")
    _garantir_coluna(cur, "tb_fila", "voz_ordem", "TEXT DEFAULT 'fila,senha,nome,destino,guiche'")
    _garantir_coluna(cur, "tb_fila", "voz_repetir", "INTEGER DEFAULT 0")
    _garantir_coluna(cur, "tb_fila", "voz_intervalo", "INTEGER DEFAULT 2")
    # textos da TV editáveis pelo criador da fila
    _garantir_coluna(cur, "tb_fila", "tv_titulo", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "tv_subtitulo", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "tv_aguardando", "TEXT DEFAULT 'AGUARDE CHAMADA'")
    _garantir_coluna(cur, "tb_fila", "tv_midia_legenda", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_fila", "tv_noticias_titulo", "TEXT DEFAULT 'Notícias'")
    _garantir_coluna(cur, "tb_fila", "prio_turno", "INTEGER DEFAULT 0")

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
            chamado_por TEXT,
            prioridade TEXT NOT NULL DEFAULT 'comum',
            manchester TEXT NOT NULL DEFAULT ''
        )
    """)
    _garantir_coluna(cur, "tb_chamada", "paciente_nome", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_chamada", "etapa_nome", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_chamada", "fila_nome", "TEXT DEFAULT ''")
    _garantir_coluna(cur, "tb_chamada", "prioridade", "TEXT NOT NULL DEFAULT 'comum'")
    _garantir_coluna(cur, "tb_chamada", "manchester", "TEXT NOT NULL DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_midia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('audio','video','imagem')),
            caminho TEXT NOT NULL,
            arquivo_original TEXT DEFAULT '',
            ordem INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            fila_id INTEGER REFERENCES tb_fila(id) ON DELETE CASCADE,
            volume INTEGER NOT NULL DEFAULT 40,
            duracao INTEGER NOT NULL DEFAULT 8,
            slot INTEGER NOT NULL DEFAULT 0,
            duracao_real REAL
        )
    """)
    _garantir_coluna(cur, "tb_midia", "fila_id", "INTEGER REFERENCES tb_fila(id) ON DELETE CASCADE")
    _garantir_coluna(cur, "tb_midia", "volume", "INTEGER NOT NULL DEFAULT 40")
    _garantir_coluna(cur, "tb_midia", "duracao", "INTEGER NOT NULL DEFAULT 8")
    _garantir_coluna(cur, "tb_midia", "slot", "INTEGER NOT NULL DEFAULT 0")
    _garantir_coluna(cur, "tb_midia", "duracao_real", "REAL")
    _garantir_coluna(cur, "tb_midia", "fundo", "INTEGER NOT NULL DEFAULT 0")
    _migrar_midia_para_imagem(cur)
    # preenche duração real de mídias antigas (melhor esforço)
    try:
        for _mid, _cam in cur.execute("SELECT id, caminho FROM tb_midia WHERE duracao_real IS NULL").fetchall():
            _real = duracao_real_arquivo(_cam)
            if _real:
                cur.execute("UPDATE tb_midia SET duracao_real=? WHERE id=?", (_real, _mid))
    except Exception:
        pass
    cur.execute("CREATE INDEX IF NOT EXISTS idx_midia_fila_slot ON tb_midia(fila_id, slot, ordem)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config_filas (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    for k, v in (("filas_modo_tv", "1"), ("filas_senha_prefixo", "A"), ("filas_guiche_padrao", "01")):
        cur.execute("INSERT OR IGNORE INTO tb_config_filas (chave, valor) VALUES (?, ?)", (k, v))

    # Projeto nasce SEM filas: nenhum seed. Cada usuário cria as suas.
    # Migra grupos legados (com acento/espaço) para slug seguro de URL.
    try:
        for _fid, _grupo in cur.execute(
                "SELECT id, tv_grupo FROM tb_fila WHERE tv_grupo IS NOT NULL AND tv_grupo<>''").fetchall():
            _ok, _slug = normalizar_tv_grupo(_grupo)
            if _ok and _slug != _grupo:
                cur.execute("UPDATE tb_fila SET tv_grupo=? WHERE id=?", (_slug, _fid))
    except Exception:
        pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_fila_nomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fila_id INTEGER NOT NULL REFERENCES tb_fila(id) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            ordem INTEGER NOT NULL DEFAULT 0,
            usado INTEGER NOT NULL DEFAULT 0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            prioridade TEXT NOT NULL DEFAULT 'comum',
            manchester TEXT NOT NULL DEFAULT '',
            etapa TEXT NOT NULL DEFAULT ''
        )
    """)
    _garantir_coluna(cur, "tb_fila_nomes", "prioridade", "TEXT NOT NULL DEFAULT 'comum'")
    _garantir_coluna(cur, "tb_fila_nomes", "manchester", "TEXT NOT NULL DEFAULT ''")
    _garantir_coluna(cur, "tb_fila_nomes", "etapa", "TEXT NOT NULL DEFAULT ''")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fila_nomes_fila ON tb_fila_nomes(fila_id, usado, ordem)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_tv_estado (
            chave TEXT PRIMARY KEY,
            slot_atual INTEGER NOT NULL DEFAULT 0,
            pausado INTEGER NOT NULL DEFAULT 0,
            comando TEXT NOT NULL DEFAULT '',
            atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            fala_ate REAL NOT NULL DEFAULT 0,
            ultima_falada INTEGER NOT NULL DEFAULT 0
        )
    """)
    _garantir_coluna(cur, "tb_tv_estado", "fala_ate", "REAL NOT NULL DEFAULT 0")
    _garantir_coluna(cur, "tb_tv_estado", "ultima_falada", "INTEGER NOT NULL DEFAULT 0")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_fila_acesso (
            fila_id INTEGER NOT NULL REFERENCES tb_fila(id) ON DELETE CASCADE,
            user_nome TEXT NOT NULL,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fila_id, user_nome)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fila_acesso_user ON tb_fila_acesso(user_nome)")

    os.makedirs(PASTA_MIDIA, exist_ok=True)
    # limpa staging órfão (stage_* com +24h sem vincular)
    try:
        import time as _t
        agora = _t.time()
        for arq in os.listdir(PASTA_MIDIA):
            if arq.startswith("stage_"):
                full = os.path.join(PASTA_MIDIA, arq)
                try:
                    if os.path.isfile(full) and agora - os.path.getmtime(full) > 86400:
                        os.remove(full)
                except Exception:
                    continue
    except Exception:
        pass
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
    """Filas visíveis: próprias + liberadas + legado sem dono. Admin geral/módulo vê todas."""
    eh_admin_geral = (perfil_global == "administrador_geral")
    eh_admin = eh_admin_geral or eh_admin_modulo
    if eh_admin:
        return listar_filas()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, senha_atual, status, guiche, data_criacao, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo
            FROM tb_fila
            WHERE criado_por=? OR criado_por='' OR criado_por IS NULL
               OR id IN (SELECT fila_id FROM tb_fila_acesso WHERE user_nome=?)
            ORDER BY nome
        """, (user_nome, user_nome))
        return cur.fetchall()
    finally:
        conn.close()


def filas_liberadas(user_nome: str) -> list:
    """Ids das filas com acesso liberado para o usuário."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT fila_id FROM tb_fila_acesso WHERE user_nome=?", (user_nome,))
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def listar_acessos(fila_id: int) -> list:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_nome, criado_em FROM tb_fila_acesso WHERE fila_id=? ORDER BY user_nome", (fila_id,))
        return cur.fetchall()
    finally:
        conn.close()


def liberar_acesso(fila_id: int, user_nome: str, ator: str = ""):
    """Libera fila para usuário cadastrado (busca via gestão de usuários). Dono/admin."""
    user_nome = (user_nome or "").strip()
    if not user_nome:
        return False, "Usuário é obrigatório"
    try:
        from mod_gest_cad_usuario.bd_manipulador import obter_usuario as _obter
        if not _obter(user_nome):
            return False, f"Usuário '{user_nome}' não cadastrado"
    except Exception:
        pass
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT criado_por FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return False, "Fila não encontrada"
        if row[0] == user_nome:
            return False, "Usuário já é o dono da fila"
        cur.execute("INSERT OR IGNORE INTO tb_fila_acesso (fila_id, user_nome) VALUES (?, ?)", (fila_id, user_nome))
        conn.commit()
        _audit(ator or "sistema", "liberar_acesso", str(fila_id), f"usuario={user_nome}")
        return True, f"Acesso liberado para {user_nome}"
    finally:
        conn.close()


def remover_acesso(fila_id: int, user_nome: str, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_fila_acesso WHERE fila_id=? AND user_nome=?", (fila_id, user_nome))
        conn.commit()
        _audit(ator or "sistema", "remover_acesso", str(fila_id), f"usuario={user_nome}")
        return True, f"Acesso de {user_nome} removido"
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


VOZ_ORDEM_PADRAO = "fila,senha,nome,destino,guiche"
VOZ_CAMPOS = ("fila", "senha", "nome", "destino", "guiche")


def normalizar_voz_ordem(valor: str) -> tuple[bool, str]:
    """Valida ordem da fala: só fila|senha|nome|destino|guiche, sem repetir; completa faltantes no fim."""
    vistos = []
    for tok in (valor or "").split(","):
        t = tok.strip().lower()
        if t and t in VOZ_CAMPOS and t not in vistos:
            vistos.append(t)
    if not vistos:
        return False, "Ordem da fala vazia — use ex: senha,nome,destino (campos: fila,senha,nome,destino,guiche)"
    for t in VOZ_CAMPOS:
        if t not in vistos:
            vistos.append(t)
    return True, ",".join(vistos)


def obter_extras_fila(fila_id: int) -> dict:
    """Config extras da fila: voz (quais campos + repetição) e textos da TV."""
    padrao = {"voz_nome": 1, "voz_senha": 1, "voz_destino": 1, "voz_guiche": 1,
              "voz_fila": 1, "voz_hora": 1, "voz_ordem": VOZ_ORDEM_PADRAO,
              "voz_repetir": 0, "voz_intervalo": 2, "tv_titulo": "",
              "tv_subtitulo": "", "tv_aguardando": "AGUARDE CHAMADA",
              "tv_midia_legenda": "", "tv_noticias_titulo": "Notícias"}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT voz_nome, voz_senha, voz_destino, voz_guiche, voz_fila, voz_hora, voz_ordem, voz_repetir, voz_intervalo, tv_titulo, tv_subtitulo, tv_aguardando, tv_midia_legenda, tv_noticias_titulo FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return padrao
        chaves = list(padrao.keys())
        for i, chave in enumerate(chaves):
            if row[i] is not None:
                padrao[chave] = row[i]
        return padrao
    finally:
        conn.close()


def criar_fila(nome: str, endereco: str = "", descricao: str = "", prefixo: str = "A", guiche: str = "01", ator: str = "", senha_inicio: int = 1, senha_fim: int = 0, tv_grupo: str = "", voz_nome: int = 1, voz_senha: int = 1, voz_destino: int = 1, voz_guiche: int = 1, voz_fila: int = 1, voz_hora: int = 1, voz_ordem: str = VOZ_ORDEM_PADRAO, voz_repetir: int = 0, voz_intervalo: int = 2, tv_titulo: str = "", tv_subtitulo: str = "", tv_aguardando: str = "AGUARDE CHAMADA", tv_midia_legenda: str = "", tv_noticias_titulo: str = "Notícias", etapas=None):
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
    ok_grupo, slug_grupo = normalizar_tv_grupo(tv_grupo)
    if not ok_grupo:
        return False, slug_grupo
    tv_grupo = slug_grupo
    ok_ordem, voz_ordem = normalizar_voz_ordem(voz_ordem)
    if not ok_ordem:
        return False, voz_ordem
    try:
        voz_repetir = max(0, min(int(voz_repetir or 0), 10))
    except Exception:
        voz_repetir = 0
    try:
        voz_intervalo = max(1, min(int(voz_intervalo or 2), 60))
    except Exception:
        voz_intervalo = 2
    conn = get_connection()
    try:
        cur = conn.cursor()
        # senha_atual inicia em inicio-1 para que o próximo seja inicio
        senha_atual = f"{prefixo}{(senha_inicio - 1):03d}" if senha_inicio > 0 else f"{prefixo}000"
        # padding dinâmico: se inicio/fim >999 usa 4+ dígitos
        if senha_inicio > 999 or senha_fim > 999:
            senha_atual = f"{prefixo}{(senha_inicio - 1):04d}" if senha_inicio > 0 else f"{prefixo}0000"
        cur.execute("INSERT INTO tb_fila (nome, senha_atual, status, guiche, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo, voz_nome, voz_senha, voz_destino, voz_guiche, voz_fila, voz_hora, voz_ordem, voz_repetir, voz_intervalo, tv_titulo, tv_subtitulo, tv_aguardando, tv_midia_legenda, tv_noticias_titulo) VALUES (?, ?, 'ativa', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (nome, senha_atual, guiche, endereco, descricao, prefixo, ator or "", senha_inicio, senha_fim, tv_grupo, 1 if voz_nome else 0, 1 if voz_senha else 0, 1 if voz_destino else 0, 1 if voz_guiche else 0, 1 if voz_fila else 0, 1 if voz_hora else 0, voz_ordem, voz_repetir, voz_intervalo, (tv_titulo or "").strip(), (tv_subtitulo or "").strip(), (tv_aguardando or "AGUARDE CHAMADA").strip(), (tv_midia_legenda or "").strip(), (tv_noticias_titulo or "Notícias").strip()))
        conn.commit()
        fid = cur.lastrowid
        # sequência de etapas/salas: cada etapa vira subfila (guichê próprio, TV replicável)
        seq = []
        for item in (etapas or []):
            if isinstance(item, (list, tuple)):
                en, eg = (item[0] if len(item) > 0 else ""), (item[1] if len(item) > 1 else "")
            else:
                en, eg = str(item or ""), ""
            en = (en or "").strip()[:80]
            if en:
                seq.append((en, (eg or "").strip()[:20]))
        if not seq:
            seq = [("Atendimento", guiche), ("Triagem", ""), ("Consultório 3", "")]
        for i, (et_nome, et_guiche) in enumerate(seq, start=1):
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


def atualizar_fila(fila_id: int, nome: str = None, endereco: str = None, descricao: str = None, prefixo: str = None, guiche: str = None, status: str = None, senha_inicio=None, senha_fim=None, tv_grupo: str = None, ator: str = "", voz_nome=None, voz_senha=None, voz_destino=None, voz_guiche=None, voz_fila=None, voz_hora=None, voz_ordem: str = None, voz_repetir=None, voz_intervalo=None, tv_titulo: str = None, tv_subtitulo: str = None, tv_aguardando: str = None, tv_midia_legenda: str = None, tv_noticias_titulo: str = None):
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
            ok_grupo, slug_grupo = normalizar_tv_grupo(tv_grupo)
            if not ok_grupo:
                return False, slug_grupo
            sets.append("tv_grupo=?"); vals.append(slug_grupo)
        for campo, val in (("voz_nome", voz_nome), ("voz_senha", voz_senha), ("voz_destino", voz_destino), ("voz_guiche", voz_guiche), ("voz_fila", voz_fila), ("voz_hora", voz_hora)):
            if val is not None:
                sets.append(f"{campo}=?"); vals.append(1 if val else 0)
        if voz_ordem is not None:
            ok_ordem, ordem_norm = normalizar_voz_ordem(voz_ordem)
            if not ok_ordem:
                return False, ordem_norm
            sets.append("voz_ordem=?"); vals.append(ordem_norm)
        if voz_repetir is not None:
            try:
                sets.append("voz_repetir=?"); vals.append(max(0, min(int(voz_repetir or 0), 10)))
            except Exception:
                return False, "Repetição deve ser número de 0 a 10"
        if voz_intervalo is not None:
            try:
                sets.append("voz_intervalo=?"); vals.append(max(1, min(int(voz_intervalo or 2), 60)))
            except Exception:
                return False, "Intervalo deve ser de 1 a 60 segundos"
        for campo, val in (("tv_titulo", tv_titulo), ("tv_subtitulo", tv_subtitulo), ("tv_aguardando", tv_aguardando), ("tv_midia_legenda", tv_midia_legenda), ("tv_noticias_titulo", tv_noticias_titulo)):
            if val is not None:
                sets.append(f"{campo}=?"); vals.append((val or "").strip())
        if not sets:
            return True, "Nada a atualizar"
        vals.append(fila_id)
        cur.execute(f"UPDATE tb_fila SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
        # nome mudou → reaplica datahora_nomeFila nos arquivos (padrão sempre vale)
        if any(s.startswith("nome=") for s in sets):
            try:
                renomear_arquivos_fila(fila_id, ator or "sistema")
            except Exception:
                pass
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
        cur.execute("DELETE FROM tb_fila WHERE id=?", (fila_id,))
        conn.commit()
        _audit(ator or "sistema", "excluir_fila", nome)
        return True, f"Fila '{nome}' excluída"
    finally:
        conn.close()


def excluir_todas_filas(ator: str = "", somente_do_criador: str = None, eh_admin: bool = False):
    """Exclui todas as filas. Se somente_do_criador informado e não eh_admin, exclui só as do criador."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if eh_admin or not somente_do_criador:
            cur.execute("SELECT COUNT(*) FROM tb_fila")
            total = cur.fetchone()[0]
            if total == 0:
                return False, "Nenhuma fila para excluir"
            cur.execute("DELETE FROM tb_fila")
        else:
            cur.execute("SELECT COUNT(*) FROM tb_fila WHERE criado_por=?", (somente_do_criador,))
            total = cur.fetchone()[0]
            if total == 0:
                return False, "Você não tem filas para excluir"
            cur.execute("DELETE FROM tb_fila WHERE criado_por=?", (somente_do_criador,))
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


def _emitir_senha(cur, fila_id: int, etapa_nome: str, paciente_nome: str, prioridade: str, manchester: str, ator: str):
    """Emite senha (incrementa contador) e registra chamada. Retorna (nova, fila_nome, guiche)."""
    cur.execute("SELECT nome, senha_atual, prefixo, guiche, senha_inicio, senha_fim FROM tb_fila WHERE id=?", (fila_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Fila não encontrada")
    fila_nome, atual, prefixo, guiche_fila, senha_inicio, senha_fim = row
    senha_inicio = senha_inicio if senha_inicio is not None else 1
    senha_fim = senha_fim if senha_fim is not None else 0
    nova = _proxima_senha(atual, prefixo, senha_inicio, senha_fim)
    cur.execute("SELECT guiche FROM tb_fila_etapa WHERE fila_id=? AND nome=?", (fila_id, etapa_nome))
    et = cur.fetchone()
    guiche = (et[0] if et and et[0] else guiche_fila) if et else (guiche_fila or "01")
    cur.execute("UPDATE tb_fila SET senha_atual=? WHERE id=?", (nova, fila_id))
    cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por, paciente_nome, etapa_nome, fila_nome, prioridade, manchester) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fila_id, nova, guiche, ator or "sistema", paciente_nome, etapa_nome, fila_nome, prioridade, manchester))
    return nova, fila_nome, guiche


def gerar_senha(fila_id: int, ator: str = "", paciente_nome: str = "", etapa_nome: str = "", prioridade: str = "comum", manchester: str = "") -> tuple[bool, str]:
    """Gera próxima senha da fila e registra chamada na etapa informada (ou primeira).

    Se paciente_nome vazio, consome o próximo elegível (etapa '' ou primeira):
    Manchester domina; sem Manchester: chegada até 3, revezamento acima disso.
    Nome com etapa vinculada (#recepcao) nasce direto naquela etapa.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tb_fila WHERE id=?", (fila_id,))
        if not cur.fetchone():
            return False, "Fila não encontrada"
        if not etapa_nome:
            etapa_nome = _primeira_etapa(cur, fila_id) or "Atendimento"
        paciente_nome = (paciente_nome or "").strip()
        if (prioridade or "") not in PRIORIDADES:
            prioridade = "comum"
        manchester = (manchester or "").strip().lower()
        if manchester not in MANCHESTER:
            manchester = ""
        if not paciente_nome:
            escolhido = _escolher_proximo_nome(cur, fila_id)
            if escolhido:
                cur.execute("UPDATE tb_fila_nomes SET usado=1 WHERE id=?", (escolhido[0],))
                paciente_nome = escolhido[1]
                prioridade = escolhido[2] or "comum"
                manchester = escolhido[3] or ""
                if escolhido[4]:
                    etapa_nome = escolhido[4]
        nova, fila_nome, _ = _emitir_senha(cur, fila_id, etapa_nome, paciente_nome, prioridade, manchester, ator)
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
        cur.execute("SELECT fila_id, senha, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada WHERE id=?", (chamada_id,))
        row = cur.fetchone()
        if not row:
            return False, "Chamada não encontrada"
        fila_id, senha, paciente_nome, etapa_atual, fila_nome, prio, manch = row
        prio = prio or "comum"
        manch = manch or ""
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
        cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por, paciente_nome, etapa_nome, fila_nome, prioridade, manchester) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fila_id, senha, guiche, ator or "sistema", paciente_nome, prox_nome, fila_nome, prio, manch))
        conn.commit()
        _audit(ator or "sistema", "avancar_chamada", senha, f"fila={fila_nome} {etapa_atual} -> {prox_nome}")
        return True, f"Avançado para {prox_nome}"
    except Exception as e:
        _log().exception(f"avancar_chamada falhou: {e}")
        return False, str(e)
    finally:
        conn.close()


def ultima_chamada(fila_id: int = None, etapa_nome: str = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        base = "SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada"
        conds = []
        vals = []
        if fila_id:
            conds.append("fila_id=?")
            vals.append(fila_id)
        if etapa_nome:
            conds.append("etapa_nome=?")
            vals.append(etapa_nome)
        if conds:
            base += " WHERE " + " AND ".join(conds)
        base += " ORDER BY id DESC LIMIT 1"
        cur.execute(base, vals)
        return cur.fetchone()
    finally:
        conn.close()


def ultima_chamada_tv(fila_id: int = None, tv_grupo: str = None, etapa_nome: str = None):
    """Última chamada para TV isolada (fila_id), compartilhada (tv_grupo) e/ou etapa/sala."""
    if tv_grupo:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=?", (tv_grupo,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return None
            placeholders = ",".join("?" for _ in ids)
            sql = f"SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada WHERE fila_id IN ({placeholders})"
            params = list(ids)
            if etapa_nome:
                sql += " AND etapa_nome=?"
                params.append(etapa_nome)
            sql += " ORDER BY id DESC LIMIT 1"
            cur.execute(sql, params)
            return cur.fetchone()
        finally:
            conn.close()
    return ultima_chamada(fila_id, etapa_nome)


def listar_chamadas(limite: int = 20, fila_id: int = None, etapa_nome: str = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        base = "SELECT id, fila_id, senha, guiche, chamado_em, chamado_por, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada"
        conds = []
        vals = []
        if fila_id:
            conds.append("fila_id=?")
            vals.append(fila_id)
        if etapa_nome:
            conds.append("etapa_nome=?")
            vals.append(etapa_nome)
        if conds:
            base += " WHERE " + " AND ".join(conds)
        base += " ORDER BY id DESC LIMIT ?"
        vals.append(limite)
        cur.execute(base, vals)
        return cur.fetchall()
    finally:
        conn.close()


def listar_chamadas_tv(limite: int = 20, fila_id: int = None, tv_grupo: str = None, etapa_nome: str = None):
    if tv_grupo:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=?", (tv_grupo,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            sql = f"SELECT id, fila_id, senha, guiche, chamado_em, chamado_por, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada WHERE fila_id IN ({placeholders})"
            params = list(ids)
            if etapa_nome:
                sql += " AND etapa_nome=?"
                params.append(etapa_nome)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(limite)
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()
    return listar_chamadas(limite, fila_id, etapa_nome)


def espera_etapa(fila_id: int, etapa_nome: str) -> list:
    """Senhas aguardando numa etapa/sala: última posição ainda é a etapa (não avançou).

    Retorna dicts (senha, paciente, prioridade, manchester, chegada) por ordem de chegada.
    """
    rows = listar_chamadas(limite=5000, fila_id=fila_id)
    ultima_etapa = {}
    chegada = {}
    dados = {}
    for r in reversed(rows):
        cid, _, senha, guiche, _, _, pac, etapa, _, prio, manch = r
        if senha not in chegada and etapa == etapa_nome:
            chegada[senha] = cid
        ultima_etapa[senha] = etapa
        dados[senha] = {"senha": senha, "paciente": pac or "", "prioridade": prio or "comum",
                        "manchester": manch or "", "guiche": guiche or "", "chegada": chegada.get(senha, cid)}
    espera = [dados[s] for s in dados if ultima_etapa.get(s) == etapa_nome and s in chegada]
    espera.sort(key=lambda d: d["chegada"])
    return espera


def proximo_da_etapa(fila_id: int, etapa_nome: str, ator: str = "") -> tuple[bool, str]:
    """A etapa/sala pede o próximo, SÓ de quem está atribuído a ela:
    1) senha mais antiga aguardando na etapa (reanuncia);
    2) senão, próximo nome da lista vinculado a esta etapa (emite senha nova ali)."""
    espera = espera_etapa(fila_id, etapa_nome)
    conn = get_connection()
    try:
        cur = conn.cursor()
        if espera:
            alvo = espera[0]
            cur.execute("SELECT nome FROM tb_fila WHERE id=?", (fila_id,))
            frow = cur.fetchone()
            fila_nome = frow[0] if frow else ""
            cur.execute("SELECT guiche FROM tb_fila WHERE id=?", (fila_id,))
            guiche_fila = (cur.fetchone()[0] or "01")
            cur.execute("SELECT guiche FROM tb_fila_etapa WHERE fila_id=? AND nome=?", (fila_id, etapa_nome))
            et = cur.fetchone()
            guiche = (et[0] if et and et[0] else guiche_fila)
            cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por, paciente_nome, etapa_nome, fila_nome, prioridade, manchester) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (fila_id, alvo["senha"], guiche, ator or "sistema", alvo["paciente"], etapa_nome, fila_nome, alvo["prioridade"], alvo["manchester"]))
            conn.commit()
            _audit(ator or "sistema", "proximo_da_etapa", alvo["senha"], f"fila={fila_nome} etapa={etapa_nome}")
            return True, alvo["senha"]
        escolhido = _escolher_proximo_nome(cur, fila_id, etapa_filtro=etapa_nome)
        if not escolhido:
            return False, f"Ninguém atribuído a {etapa_nome}"
        cur.execute("UPDATE tb_fila_nomes SET usado=1 WHERE id=?", (escolhido[0],))
        nova, fila_nome, _ = _emitir_senha(cur, fila_id, etapa_nome, escolhido[1], escolhido[2] or "comum", escolhido[3] or "", ator)
        conn.commit()
        _audit(ator or "sistema", "proximo_da_etapa", nova, f"fila={fila_nome} etapa={etapa_nome} paciente={escolhido[1]}")
        return True, nova
    finally:
        conn.close()


# ============ NOMES (nomes.txt — chamados em ordem, 1 lista por fila) ============

PRIORIDADES = ("comum", "gestante", "idoso", "deficiente")
# Revezamento quando há mais de 3 pendentes: 1 de cada prioridade + 2 comuns
CICLO_PRIORIDADE = ("gestante", "idoso", "deficiente", "comum", "comum")
# Manchester: cor domina a demografia (vermelho passa na frente de tudo)
MANCHESTER = ("vermelho", "laranja", "amarelo", "verde", "azul")
_RANK_MANCHESTER = {"vermelho": 0, "laranja": 1, "amarelo": 2, "verde": 3, "azul": 4}
_RANK_DEMOGRAFICA = {"gestante": 0, "idoso": 1, "deficiente": 2, "comum": 3}


def _norm_etapa(texto: str) -> str:
    n = unicodedata.normalize("NFKD", texto or "").lower()
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", n).strip()


def csv_para_tags(texto: str):
    """Converte CSV (nome,grupo,cor,etapa com , ou ;) para linhas de tags. Retorna None se não for CSV."""
    linhas = [l.strip() for l in (texto or "").splitlines() if l.strip()]
    if not linhas:
        return None
    if any(";" in l for l in linhas):
        delim = ";"
    elif sum(1 for l in linhas if "," in l) >= max(1, len(linhas) // 2):
        delim = ","
    else:
        return None
    nomes_cab = {"nome", "nomes", "name", "paciente", "usuario", "usuário"}
    grupo_cab = {"grupo", "prioridade", "categoria"}
    cor_cab = {"cor", "manchester", "classificacao", "classificação", "risco"}
    etapa_cab = {"etapa", "setor", "sala", "destino", "local"}
    def _norm_cab(s):
        n = unicodedata.normalize("NFKD", (s or "").strip().lower())
        return "".join(c for c in n if not unicodedata.combining(c))
    primeira = [_norm_cab(c) for c in linhas[0].split(delim)]
    tem_cab = any(c in nomes_cab for c in primeira)
    idx = {"nome": 0, "grupo": 1, "cor": 2, "etapa": 3}
    inicio = 0
    if tem_cab:
        inicio = 1
        for i, c in enumerate(primeira):
            if c in nomes_cab:
                idx["nome"] = i
            elif c in grupo_cab:
                idx["grupo"] = i
            elif c in cor_cab:
                idx["cor"] = i
            elif c in etapa_cab:
                idx["etapa"] = i
    saida = []
    for lin in linhas[inicio:]:
        cels = [c.strip() for c in lin.split(delim)]
        nome = cels[idx["nome"]] if idx["nome"] < len(cels) else ""
        if not nome:
            continue
        tags = []
        if idx["grupo"] < len(cels) and cels[idx["grupo"]]:
            tags.append("#" + cels[idx["grupo"]])
        if idx["cor"] < len(cels) and cels[idx["cor"]]:
            tags.append("#" + cels[idx["cor"]])
        if idx["etapa"] < len(cels) and cels[idx["etapa"]]:
            tags.append("#" + cels[idx["etapa"]])
        saida.append((nome + " " + " ".join(tags)).strip())
    return "\n".join(saida) if saida else None


def _parse_nome_tags(linha: str, etapas: list = None) -> tuple[str, str, str, str]:
    """Separa 'Maria #gestante #vermelho #recepcao' em (nome, prioridade, manchester, etapa).

    Etapa = tag igual (sem acento/maiúscula) a uma etapa da fila. Tags
    desconhecidas (ex: #finanças) são ignoradas. Aceita [colchetes].
    """
    texto = (linha or "").strip().strip("[]()")
    mapa = {}
    if etapas:
        for en in etapas:
            mapa[_norm_etapa(en)] = en
    partes = re.split(r"\s*[#,;]\s*", texto)
    nome = (partes[0] if partes else "").strip()
    prio = "comum"
    manch = ""
    etapa = ""
    for tag in partes[1:]:
        t = tag.strip().lower()
        t = re.sub(r"^manchester[\s_-]*", "", t)
        if t in ("gestante", "gestantes"):
            prio = "gestante"
        elif t in ("idoso", "idosa", "idosos", "idosas"):
            prio = "idoso"
        elif t.startswith("defic") or t in ("pcd", "pcds", "cadeirante"):
            prio = "deficiente"
        elif t in ("comum", "normal", "geral"):
            prio = "comum"
        elif t in ("vermelho", "vermelha", "emergente", "emergencia"):
            manch = "vermelho"
        elif t == "laranja":
            manch = "laranja"
        elif t in ("amarelo", "amarela"):
            manch = "amarelo"
        elif t == "verde":
            manch = "verde"
        elif t in ("azul", "azuis"):
            manch = "azul"
        elif t and _norm_etapa(t) in mapa:
            etapa = mapa[_norm_etapa(t)]
        # desconhecida: ignora (ex: #finanças)
    if not nome:
        return "", "comum", "", ""
    return nome[:120], prio, manch, etapa


def _parse_nome_prioridade(linha: str) -> tuple[str, str]:
    """Compat: Separa 'Maria #gestante' em (nome, prioridade)."""
    nome, prio, _, _ = _parse_nome_tags(linha)
    return nome, prio


def importar_nomes(fila_id: int, texto: str, ator: str = "", substituir: bool = False):
    """Importa nomes (um por linha: 'Maria #gestante #vermelho').

    Cada fila aceita UMA lista: se já houver nomes e substituir=False, recusa.
    Com substituir=True apaga a lista atual e importa a nova.
    """
    itens = []
    vistos = set()
    try:
        _conn_e = get_connection()
        try:
            _cur_e = _conn_e.cursor()
            _cur_e.execute("SELECT nome FROM tb_fila_etapa WHERE fila_id=? ORDER BY ordem", (fila_id,))
            _etapas_fila = [r[0] for r in _cur_e.fetchall()]
        finally:
            _conn_e.close()
    except Exception:
        _etapas_fila = []
    for linha in (texto or "").splitlines():
        nome, prio, manch, etapa = _parse_nome_tags(linha, _etapas_fila)
        if nome and (nome.lower(), prio, manch, etapa) not in vistos:
            vistos.add((nome.lower(), prio, manch, etapa))
            itens.append((nome, prio, manch, etapa))
    if not itens:
        return False, "Nenhum nome válido (um por linha, ex: Maria #gestante #amarelo #recepcao)"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tb_fila WHERE id=?", (fila_id,))
        if not cur.fetchone():
            return False, "Fila não encontrada"
        cur.execute("SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=?", (fila_id,))
        existentes = cur.fetchone()[0]
        if existentes and not substituir:
            return False, f"Fila já possui uma lista ({existentes} nome(s)) — apague ou marque Substituir"
        if substituir:
            cur.execute("DELETE FROM tb_fila_nomes WHERE fila_id=?", (fila_id,))
        for i, (nome, prio, manch, etapa) in enumerate(itens, start=1):
            cur.execute("INSERT INTO tb_fila_nomes (fila_id, nome, ordem, prioridade, manchester, etapa) VALUES (?, ?, ?, ?, ?, ?)",
                        (fila_id, nome, i, prio, manch, etapa))
        conn.commit()
        _audit(ator or "sistema", "importar_nomes", str(fila_id), f"{len(itens)} nomes")
        return True, f"{len(itens)} nome(s) importado(s)"
    finally:
        conn.close()


def listar_nomes(fila_id: int, somente_pendentes: bool = False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if somente_pendentes:
            cur.execute("SELECT id, nome, ordem, usado, prioridade, manchester, etapa FROM tb_fila_nomes WHERE fila_id=? AND usado=0 ORDER BY ordem DESC", (fila_id,))
        else:
            cur.execute("SELECT id, nome, ordem, usado, prioridade, manchester, etapa FROM tb_fila_nomes WHERE fila_id=? ORDER BY ordem DESC", (fila_id,))
        return cur.fetchall()
    finally:
        conn.close()


def contar_nomes_pendentes(fila_id: int) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=? AND usado=1", (fila_id,))
        return cur.fetchone()[0]
    finally:
        conn.close()


def remover_nome(nome_id: int, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_fila_nomes WHERE id=?", (nome_id,))
        conn.commit()
        return True, "Nome removido"
    finally:
        conn.close()


def limpar_nomes(fila_id: int, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_fila_nomes WHERE fila_id=?", (fila_id,))
        conn.commit()
        _audit(ator or "sistema", "limpar_nomes", str(fila_id))
        return True, "Lista de nomes apagada"
    finally:
        conn.close()


def definir_etapa_nome(nome_id: int, etapa: str, ator: str = ""):
    """Atribui etapa de atendimento ao nome ('' = recepção/primeira etapa)."""
    etapa = (etapa or "").strip()[:80]
    conn = get_connection()
    try:
        cur = conn.cursor()
        if etapa:
            cur.execute("SELECT fila_id FROM tb_fila_nomes WHERE id=?", (nome_id,))
            row = cur.fetchone()
            if not row:
                return False, "Nome não encontrado"
            cur.execute("SELECT 1 FROM tb_fila_etapa WHERE fila_id=? AND nome=?", (row[0], etapa))
            if not cur.fetchone():
                return False, f"Etapa '{etapa}' não existe nesta fila"
        cur.execute("UPDATE tb_fila_nomes SET etapa=? WHERE id=?", (etapa, nome_id))
        conn.commit()
        return True, "Etapa atualizada"
    finally:
        conn.close()


def definir_manchester_nome(nome_id: int, cor: str, ator: str = ""):
    cor = (cor or "").strip().lower()
    if cor and cor not in MANCHESTER:
        return False, "Manchester deve ser vermelho, laranja, amarelo, verde, azul ou vazio"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_fila_nomes SET manchester=? WHERE id=?", (cor, nome_id))
        conn.commit()
        return True, "Manchester atualizado"
    finally:
        conn.close()


def definir_nome_senha(fila_id: int, senha: str, nome: str, ator: str = ""):
    """Vincula nome a senha já distribuída (papelzinho vira chamada nominal). Qualquer atendente."""
    nome = (nome or "").strip()[:120]
    if not nome:
        return False, "Nome é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_chamada WHERE fila_id=? AND senha=?", (fila_id, senha))
        if not cur.fetchone()[0]:
            return False, "Senha não encontrada nesta fila"
        cur.execute("UPDATE tb_chamada SET paciente_nome=? WHERE fila_id=? AND senha=?", (nome, fila_id, senha))
        conn.commit()
        _audit(ator or "sistema", "definir_nome_senha", senha, f"fila={fila_id} nome={nome}")
        return True, f"{senha} agora é {nome}"
    finally:
        conn.close()


def definir_manchester_senha(fila_id: int, senha: str, cor: str, ator: str = ""):
    """Altera Manchester da senha a qualquer momento, por qualquer atendente (chamadas + lista)."""
    cor = (cor or "").strip().lower()
    if cor and cor not in MANCHESTER:
        return False, "Manchester deve ser vermelho, laranja, amarelo, verde, azul ou vazio"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT paciente_nome FROM tb_chamada WHERE fila_id=? AND senha=? ORDER BY id DESC LIMIT 1", (fila_id, senha))
        row = cur.fetchone()
        if not row:
            return False, "Senha não encontrada nesta fila"
        cur.execute("UPDATE tb_chamada SET manchester=? WHERE fila_id=? AND senha=?", (cor, fila_id, senha))
        if row[0]:
            cur.execute("UPDATE tb_fila_nomes SET manchester=? WHERE fila_id=? AND nome=?", (cor, fila_id, row[0]))
        conn.commit()
        _audit(ator or "sistema", "definir_manchester_senha", senha, f"fila={fila_id} cor={cor or '—'}")
        return True, f"Manchester de {senha}: {cor or 'removido'}"
    finally:
        conn.close()


def definir_prioridade_nome(nome_id: int, prioridade: str, ator: str = ""):
    if (prioridade or "") not in PRIORIDADES:
        return False, "Prioridade deve ser comum, gestante, idoso ou deficiente"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_fila_nomes SET prioridade=? WHERE id=?", (prioridade, nome_id))
        conn.commit()
        return True, "Prioridade atualizada"
    finally:
        conn.close()


def transferir_nome(nome_id: int, fila_destino: int, ator: str = ""):
    """Envia um nome para outra fila da mesma TV (ex: recepção → ultrassom)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT fila_id, nome, prioridade FROM tb_fila_nomes WHERE id=?", (nome_id,))
        row = cur.fetchone()
        if not row:
            return False, "Nome não encontrado"
        origem, nome, prio = row
        if origem == fila_destino:
            return False, "Já está nesta fila"
        cur.execute("SELECT tv_grupo FROM tb_fila WHERE id=?", (origem,))
        r1 = cur.fetchone()
        cur.execute("SELECT tv_grupo FROM tb_fila WHERE id=?", (fila_destino,))
        r2 = cur.fetchone()
        if not r2:
            return False, "Fila de destino não encontrada"
        g1 = (r1[0] if r1 else "") or ""
        g2 = (r2[0] if r2 else "") or ""
        if g1 != g2:
            return False, "Só é permitido enviar para fila da mesma TV"
        cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM tb_fila_nomes WHERE fila_id=?", (fila_destino,))
        ordem = cur.fetchone()[0]
        cur.execute("UPDATE tb_fila_nomes SET fila_id=?, ordem=?, usado=0 WHERE id=?", (fila_destino, ordem, nome_id))
        conn.commit()
        _audit(ator or "sistema", "transferir_nome", nome, f"{origem} -> {fila_destino}")
        return True, f"{nome} enviado para a outra fila"
    finally:
        conn.close()


def transferir_todos(fila_origem: int, fila_destino: int, ator: str = ""):
    """Envia todos os pendentes para outra fila da mesma TV (destino deve estar sem lista)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT tv_grupo FROM tb_fila WHERE id=?", (fila_origem,))
        r1 = cur.fetchone()
        cur.execute("SELECT tv_grupo FROM tb_fila WHERE id=?", (fila_destino,))
        r2 = cur.fetchone()
        if not r1 or not r2:
            return False, "Fila não encontrada"
        if ((r1[0] or "") != (r2[0] or "")):
            return False, "Só é permitido enviar para fila da mesma TV"
        cur.execute("SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=?", (fila_destino,))
        if cur.fetchone()[0] > 0:
            return False, "Fila de destino já possui uma lista"
        cur.execute("SELECT id FROM tb_fila_nomes WHERE fila_id=? AND usado=0 ORDER BY ordem", (fila_origem,))
        ids = [r[0] for r in cur.fetchall()]
        if not ids:
            return False, "Nenhum nome pendente para enviar"
        for nid in ids:
            cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM tb_fila_nomes WHERE fila_id=?", (fila_destino,))
            ordem = cur.fetchone()[0]
            cur.execute("UPDATE tb_fila_nomes SET fila_id=?, ordem=?, usado=0 WHERE id=?", (fila_destino, ordem, nid))
        conn.commit()
        _audit(ator or "sistema", "transferir_todos", str(fila_origem), f"{len(ids)} nomes -> {fila_destino}")
        return True, f"{len(ids)} nome(s) enviado(s)"
    finally:
        conn.close()


def _primeira_etapa(cur, fila_id: int) -> str:
    cur.execute("SELECT nome FROM tb_fila_etapa WHERE fila_id=? ORDER BY ordem LIMIT 1", (fila_id,))
    row = cur.fetchone()
    return row[0] if row else ""


def _escolher_proximo_nome(cur, fila_id: int, etapa_filtro: str = None):
    """Escolhe próximo nome da recepção (chamar geral) ou de uma etapa específica.

    Elegíveis: etapa '' (geral) ou igual à etapa pedida (None = primeira etapa).
    - Se há Manchester entre elegíveis: cor domina tudo, desempate demografia/chegada.
    - Sem Manchester e até 3 elegíveis: ordem de chegada.
    - Sem Manchester e mais que 3: revezamento (1 gestante, 1 idoso, 1 deficiente, 2 comuns).
    Retorna (id, nome, prioridade, manchester, etapa)."""
    if etapa_filtro is None:
        etapa_filtro = _primeira_etapa(cur, fila_id)
    cond = "AND (etapa='' OR etapa=?)"
    params = [fila_id, etapa_filtro]
    cur.execute(f"SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=? AND usado=0 {cond}", params)
    total = cur.fetchone()[0]
    if total == 0:
        return None
    cols = "id, nome, prioridade, manchester, etapa"
    cur.execute(f"SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=? AND usado=0 AND manchester<>'' {cond}", params)
    with_manchester = cur.fetchone()[0]
    if with_manchester:
        cur.execute(f"SELECT {cols} FROM tb_fila_nomes WHERE fila_id=? AND usado=0 {cond}", params)
        cand = cur.fetchall()
        def _chave(r):
            return (_RANK_MANCHESTER.get(r[3] or "", 9), _RANK_DEMOGRAFICA.get(r[2] or "comum", 3), r[0])
        cand.sort(key=_chave)
        return cand[0]
    if total <= 3:
        cur.execute(f"SELECT {cols} FROM tb_fila_nomes WHERE fila_id=? AND usado=0 {cond} ORDER BY ordem LIMIT 1", params)
        return cur.fetchone()
    cur.execute("SELECT prio_turno FROM tb_fila WHERE id=?", (fila_id,))
    row = cur.fetchone()
    turno = ((row[0] if row and row[0] else 0)) % len(CICLO_PRIORIDADE)
    for k in range(len(CICLO_PRIORIDADE)):
        passo = (turno + k) % len(CICLO_PRIORIDADE)
        prio = CICLO_PRIORIDADE[passo]
        cur.execute(f"SELECT {cols} FROM tb_fila_nomes WHERE fila_id=? AND usado=0 AND prioridade=? {cond} ORDER BY ordem LIMIT 1", [fila_id, prio, etapa_filtro])
        achado = cur.fetchone()
        if achado:
            cur.execute("UPDATE tb_fila SET prio_turno=? WHERE id=?", ((passo + 1) % len(CICLO_PRIORIDADE), fila_id))
            return achado
    cur.execute(f"SELECT {cols} FROM tb_fila_nomes WHERE fila_id=? AND usado=0 {cond} ORDER BY ordem LIMIT 1", params)
    return cur.fetchone()


def _proximo_nome_pendente(cur, fila_id: int):
    row = _escolher_proximo_nome(cur, fila_id)
    return (row[0], row[1]) if row else None


# ============ MIDIA ============

VOLUME_AMBIENTE_PADRAO = 40
VOLUME_CHAMADA = 0.8
TIPOS_MIDIA = ("audio", "video", "imagem")
EXTENSAO_TIPO = {
    ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".m4a": "audio",
    ".mp4": "video", ".webm": "video", ".mov": "video",
    ".jpg": "imagem", ".jpeg": "imagem", ".png": "imagem", ".webp": "imagem",
}


def tipo_por_extensao(nome_arquivo: str):
    return EXTENSAO_TIPO.get(os.path.splitext(nome_arquivo or "")[1].lower())


def duracao_real_arquivo(caminho_registrado: str):
    """Duração real (segundos) de áudio/vídeo — mutagen, com fallback WAV nativo."""
    base = os.path.basename(caminho_registrado or "")
    if not base:
        return None
    canais = os.path.join(PASTA_MIDIA, base)
    if not os.path.isfile(canais):
        return None
    try:
        from mutagen import File as _MutFile
        mf = _MutFile(canais)
        if mf is not None and getattr(mf, "info", None) is not None:
            comp = float(getattr(mf.info, "length", 0) or 0)
            if comp > 0:
                return round(comp, 1)
    except Exception:
        pass
    try:
        import wave
        import contextlib
        with contextlib.closing(wave.open(canais, "rb")) as w:
            fr = w.getframerate()
            if fr:
                return round(max(1.0, w.getnframes() / float(fr)), 1)
    except Exception:
        pass
    return None


def calcular_passo(itens: list) -> tuple:
    """Tempo da exibição: itens = [(tipo, duracao_cfg, duracao_real)].

    Áudio/vídeo valem o tempo REAL; fotos dividem esse tempo
    (áudio 40s + 4 fotos = 10s cada). Sem tempo real, fotos somam a duração
    configurada; só áudio/vídeo sem real = 12s/25s.
    Retorna (total_seg, [seg_por_foto]).
    """
    base = max([float(r or 0) for t, _, r in itens if t in ("audio", "video")] or [0])
    n_img = sum(1 for t, _, _ in itens if t == "imagem")
    if base > 0:
        por_foto = [round(base / n_img, 1)] * n_img if n_img else []
        return round(base, 1), por_foto
    if n_img:
        por_foto = [max(3.0, float(d or 8)) for t, d, _ in itens if t == "imagem"]
        return round(sum(por_foto), 1), por_foto
    tem_video = any(t == "video" for t, _, _ in itens)
    return (25.0 if tem_video else 12.0), []


def nome_arquivo_midia(fila_id=None, nome_original: str = "midia") -> str:
    """Nome no servidor: datahora_nomeFila.ext (ex: 20260920_121500_ambulatorio.mp3).

    Fila global (sem fila_id) usa 'global'. Se o nome existir, sufixa _2, _3...
    """
    from datetime import datetime
    datahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(nome_original or "")[1].lower() or ".mp3"
    base = "global"
    if fila_id:
        try:
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT nome FROM tb_fila WHERE id=?", (fila_id,))
                row = cur.fetchone()
                if row and row[0]:
                    base = row[0]
            finally:
                conn.close()
        except Exception:
            base = f"fila{fila_id}"
    normalizado = unicodedata.normalize("NFKD", str(base))
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    seguro = re.sub(r"[^a-zA-Z0-9_-]", "_", sem_acento.strip().replace(" ", "_"))
    seguro = re.sub(r"_+", "_", seguro).strip("_").lower()[:30] or "fila"
    os.makedirs(PASTA_MIDIA, exist_ok=True)
    candidato = f"{datahora}_{seguro}{ext}"
    contador = 2
    while os.path.exists(os.path.join(PASTA_MIDIA, candidato)):
        candidato = f"{datahora}_{seguro}_{contador}{ext}"
        contador += 1
    return candidato


def listar_midias(somente_ativas=False, fila_id=None):
    """Mídias: fila_id=None lista TODAS (admin global); fila_id=X lista SÓ a fila X (isolada)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        base = "SELECT id, nome, tipo, caminho, arquivo_original, ordem, ativo, criado_em, fila_id, volume, duracao, slot, duracao_real, fundo FROM tb_midia"
        conds = []
        vals = []
        if somente_ativas:
            conds.append("ativo=1")
        if fila_id is not None:
            conds.append("fila_id=?")
            vals.append(fila_id)
        if conds:
            base += " WHERE " + " AND ".join(conds)
        base += " ORDER BY slot, ordem, id"
        cur.execute(base, vals)
        return cur.fetchall()
    finally:
        conn.close()


def salvar_lista_nomes(fila_id, conteudo) -> tuple[bool, str]:
    """Salva lista de pacientes no servidor como datahora_nomeFila.txt. Retorna (ok, nome/msg)."""
    try:
        if isinstance(conteudo, str):
            dados = conteudo.encode("utf-8")
        else:
            dados = bytes(conteudo or b"")
        if not dados.strip():
            return False, "Lista vazia"
        nome_seguro = nome_arquivo_midia(fila_id, "lista.txt")
        dest = os.path.join(PASTA_MIDIA, nome_seguro)
        with open(dest, "wb") as f:
            f.write(dados)
        return True, nome_seguro
    except Exception as e:
        return False, str(e)


def midias_para_tv(fila_ids=None) -> list:
    """Playlist da TV: mídias próprias (fila isolada ou do grupo) + áudios globais do admin.

    Áudio ambiente global (fila_id NULL) toca em TODAS as TVs, após as mídias
    próprias. Vídeo/foto global fica só na TV geral (/tv).
    """
    todas = listar_midias(somente_ativas=True)
    if fila_ids is None:
        return [m for m in todas if m[8] is None]
    proprias = [m for m in todas if m[8] in (fila_ids or [])]
    base = max([m[11] for m in proprias], default=-1) + 1
    saida = list(proprias)
    for i, m in enumerate([x for x in todas if x[8] is None and x[2] == "audio"]):
        ml = list(m)
        ml[11] = base + i
        saida.append(tuple(ml))
    return saida


def ids_do_grupo(tv_grupo: str) -> list:
    """Ids das filas de um tv_grupo (para TV compartilhada e controle remoto)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=? ORDER BY id", (tv_grupo,))
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def adicionar_midia(nome: str, tipo: str, caminho: str, arquivo_original: str = "", ator: str = "", fila_id=None, volume: int = VOLUME_AMBIENTE_PADRAO, duracao: int = 8, slot: int = 0):
    if tipo not in TIPOS_MIDIA:
        return False, "Tipo deve ser audio, video ou imagem"
    try:
        volume = max(0, min(int(volume), 100))
    except Exception:
        volume = VOLUME_AMBIENTE_PADRAO
    try:
        duracao = max(3, min(int(duracao), 120))
    except Exception:
        duracao = 8
    try:
        slot = max(0, min(int(slot or 0), 999))
    except Exception:
        slot = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM tb_midia WHERE (fila_id=? OR (fila_id IS NULL AND ? IS NULL))", (fila_id, fila_id))
        ordem = cur.fetchone()[0]
        cur.execute("INSERT INTO tb_midia (nome, tipo, caminho, arquivo_original, ordem, fila_id, volume, duracao, slot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ((nome or arquivo_original or tipo).strip(), tipo, caminho, arquivo_original, ordem, fila_id, volume, duracao, slot))
        mid_novo = cur.lastrowid
        try:
            real = duracao_real_arquivo(caminho)
            if real:
                cur.execute("UPDATE tb_midia SET duracao_real=? WHERE id=?", (real, mid_novo))
        except Exception:
            pass
        conn.commit()
        _audit(ator or "sistema", "adicionar_midia", nome, f"tipo={tipo} fila={fila_id} slot={slot}")
        return True, "Mídia adicionada"
    finally:
        conn.close()


def atualizar_midia(midia_id: int, volume=None, duracao=None, slot=None, nome: str = None, ator: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets = []
        vals = []
        if volume is not None:
            try:
                sets.append("volume=?"); vals.append(max(0, min(int(volume), 100)))
            except Exception:
                return False, "Volume deve ser de 0 a 100"
        if duracao is not None:
            try:
                sets.append("duracao=?"); vals.append(max(3, min(int(duracao), 120)))
            except Exception:
                return False, "Duração deve ser de 3 a 120 segundos"
        if slot is not None:
            try:
                sets.append("slot=?"); vals.append(max(0, min(int(slot or 0), 999)))
            except Exception:
                return False, "Exibição deve ser número"
        if nome is not None:
            if not (nome or "").strip():
                return False, "Nome não pode ser vazio"
            sets.append("nome=?"); vals.append(nome.strip())
        if not sets:
            return True, "Nada a atualizar"
        vals.append(midia_id)
        cur.execute(f"UPDATE tb_midia SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
        return True, "Mídia atualizada"
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


def set_midia_fundo(midia_id: int, fundo: bool, ator: str = ""):
    """Marca foto como papel de fundo (uma por fila/global: as demais saem)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT fila_id, tipo FROM tb_midia WHERE id=?", (midia_id,))
        row = cur.fetchone()
        if not row:
            return False, "Mídia não encontrada"
        if fundo and row[1] != "imagem":
            return False, "Só foto pode ser papel de fundo"
        if fundo:
            cur.execute("UPDATE tb_midia SET fundo=0 WHERE (fila_id=? OR (fila_id IS NULL AND ? IS NULL)) AND id<>?",
                        (row[0], row[0], midia_id))
        cur.execute("UPDATE tb_midia SET fundo=? WHERE id=?", (1 if fundo else 0, midia_id))
        conn.commit()
        _audit(ator or "sistema", "fundo_midia", str(midia_id), f"fundo={bool(fundo)}")
        return True, ("Papel de fundo ativado" if fundo else "Papel de fundo removido")
    finally:
        conn.close()


def renomear_arquivos_fila(fila_id: int, ator: str = "") -> tuple[bool, str]:
    """Reaplica datahora_nomeFila em todas as mídias da fila (ex: fila renomeada)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, arquivo_original FROM tb_midia WHERE fila_id=?", (fila_id,))
        linhas = cur.fetchall()
        n = 0
        for mid, orig in linhas:
            try:
                final = nome_arquivo_midia(fila_id, orig or "midia")
                cur.execute("SELECT caminho FROM tb_midia WHERE id=?", (mid,))
                antigo = (cur.fetchone()[0] or "")
                src = os.path.join(PASTA_MIDIA, os.path.basename(antigo))
                dst = os.path.join(PASTA_MIDIA, final)
                if os.path.isfile(src) and src != dst:
                    os.rename(src, dst)
                    cur.execute("UPDATE tb_midia SET caminho=? WHERE id=?", (f"/midia_filas/{final}", mid))
                    n += 1
            except Exception:
                continue
        conn.commit()
        return True, f"{n} arquivo(s) renomeado(s)"
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


TV_GRUPO_MAX = 40
TV_GRUPO_RESERVADOS = frozenset({
    "tv", "admin", "login", "api", "geral", "grupo",
    "static", "configuracoes", "midia-filas", "favicon",
})


def normalizar_tv_grupo(valor: str) -> tuple[bool, str]:
    """Normaliza tv_grupo para slug seguro de URL.

    Vazio = TV isolada (permitido). Não-vazio vira slug minúsculo
    `a-z0-9` com hífens: remove acentos, troca espaço/_ por hífen,
    colapsa hífens repetidos. Ex.: 'Ambulatório Geral' -> 'ambulatorio-geral'.
    Retorna (True, slug) ou (False, mensagem de erro).
    """
    texto = (valor or "").strip()
    if not texto:
        return True, ""
    normalizado = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    slug = sem_acento.lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if len(slug) < 2:
        return False, "TV grupo deve ter ao menos 2 letras/números (ex: recepcao)"
    if len(slug) > TV_GRUPO_MAX:
        return False, f"TV grupo com no máximo {TV_GRUPO_MAX} caracteres"
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
        return False, "TV grupo usa só letras, números e hífen (ex: recepcao-2)"
    if slug in TV_GRUPO_RESERVADOS:
        return False, f"TV grupo '{slug}' é reservado do sistema"
    return True, slug


def chave_tv(fila_id: int = None, tv_grupo: str = "") -> str:
    """Chave do estado da TV: 'grupo:<slug>' (compartilhada) ou 'fila:<id>' (isolada)."""
    if tv_grupo:
        return f"grupo:{tv_grupo}"
    if fila_id:
        return f"fila:{fila_id}"
    return "geral"


def chave_tv_etapa(fila_id: int = None, tv_grupo: str = "", etapa: str = "") -> str:
    """Chave por etapa/sala: mesma TV, fila de anúncio independente por etapa."""
    base = chave_tv(fila_id, tv_grupo)
    etapa = (etapa or "").strip()
    return f"{base}+{etapa}" if etapa else base


def obter_estado_tv(chave: str) -> dict:
    """Estado atual da TV (slot, pausado, comando, fala). Cria linha se inexistir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tb_tv_estado (chave) VALUES (?)", (chave,))
        conn.commit()
        cur.execute("SELECT slot_atual, pausado, comando, fala_ate, ultima_falada FROM tb_tv_estado WHERE chave=?", (chave,))
        row = cur.fetchone()
        if not row:
            return {"slot_atual": 0, "pausado": 0, "comando": "", "fala_ate": 0.0, "ultima_falada": 0}
        return {"slot_atual": row[0] or 0, "pausado": row[1] or 0, "comando": row[2] or "",
                "fala_ate": float(row[3] or 0), "ultima_falada": int(row[4] or 0)}
    finally:
        conn.close()


def tv_livre(chave: str) -> bool:
    """TV sem anúncio em andamento (para repeats e fila de voz)."""
    import time as _t
    try:
        return _t.time() >= float(obter_estado_tv(chave).get("fala_ate", 0) or 0)
    except Exception:
        return True


def tv_bloquear(chave: str, dur_seg: float):
    """Reserva a voz da TV por dur_seg segundos."""
    import time as _t
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tb_tv_estado (chave) VALUES (?)", (chave,))
        cur.execute("UPDATE tb_tv_estado SET fala_ate=? WHERE chave=?", (_t.time() + max(1.0, float(dur_seg or 5)), chave))
        conn.commit()
    finally:
        conn.close()


def tv_claim_fala(chave: str, chamada_id: int, dur_seg: float) -> bool:
    """Tenta assumir o próximo anúncio (compare-and-swap): um anuncia por vez, sem cortar.

    Retorna True se esta TV assumiu (deve falar); False se outra assumiu ou voz ocupada.
    """
    import time as _t
    agora = _t.time()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tb_tv_estado (chave) VALUES (?)", (chave,))
        conn.commit()
        cur.execute("SELECT fala_ate, ultima_falada FROM tb_tv_estado WHERE chave=?", (chave,))
        row = cur.fetchone()
        fala_ate = float((row[0] if row else 0) or 0)
        ultima = int((row[1] if row else 0) or 0)
        if chamada_id <= ultima:
            return False
        if fala_ate > agora:
            return False
        cur.execute("UPDATE tb_tv_estado SET fala_ate=?, ultima_falada=? WHERE chave=? AND ultima_falada=?",
                    (agora + max(1.0, float(dur_seg or 5)), chamada_id, chave, ultima))
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def buscar_proxima_fala(fila_id: int = None, tv_grupo: str = None, etapa_nome: str = None, apos_id: int = 0):
    """Anúncio mais antigo ainda não falado (id > apos_id), no escopo da TV/etapa."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        base = "SELECT id, senha, guiche, chamado_em, paciente_nome, etapa_nome, fila_nome, prioridade, manchester FROM tb_chamada WHERE id>?"
        vals = [apos_id or 0]
        if tv_grupo:
            cur.execute("SELECT id FROM tb_fila WHERE tv_grupo=?", (tv_grupo,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return None
            base += f" AND fila_id IN ({','.join('?' for _ in ids)})"
            vals += ids
        elif fila_id:
            base += " AND fila_id=?"
            vals.append(fila_id)
        if etapa_nome:
            base += " AND etapa_nome=?"
            vals.append(etapa_nome)
        base += " ORDER BY id ASC LIMIT 1"
        cur.execute(base, vals)
        return cur.fetchone()
    finally:
        conn.close()


def definir_estado_tv(chave: str, slot_atual: int = None, pausado: int = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tb_tv_estado (chave) VALUES (?)", (chave,))
        sets = []
        vals = []
        if slot_atual is not None:
            sets.append("slot_atual=?")
            vals.append(int(slot_atual))
        if pausado is not None:
            sets.append("pausado=?")
            vals.append(1 if pausado else 0)
        if sets:
            vals.append(chave)
            cur.execute(f"UPDATE tb_tv_estado SET {', '.join(sets)} WHERE chave=?", vals)
            conn.commit()
    finally:
        conn.close()


def enviar_comando_tv(chave: str, comando: str):
    """Comando remoto da edição para a TV: pausar|retomar|proximo|anterior|slot:<n>."""
    comando = (comando or "").strip()[:20]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tb_tv_estado (chave) VALUES (?)", (chave,))
        cur.execute("UPDATE tb_tv_estado SET comando=? WHERE chave=?", (comando, chave))
        conn.commit()
    finally:
        conn.close()


def consumir_comando_tv(chave: str) -> str:
    """TV lê e limpa o comando pendente (chamada a cada refresh)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT comando FROM tb_tv_estado WHERE chave=?", (chave,))
        row = cur.fetchone()
        comando = (row[0] or "") if row else ""
        if comando:
            cur.execute("UPDATE tb_tv_estado SET comando='' WHERE chave=?", (chave,))
            conn.commit()
        return comando
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
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_fila_acesso WHERE user_nome=?", (user_nome,))
        n = cur.rowcount or 0
        conn.commit()
        return n
    finally:
        conn.close()


def renomear_usuario(nome_atual: str, novo_nome: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_chamada SET chamado_por=? WHERE chamado_por=?", (novo_nome, nome_atual))
        cur.execute("UPDATE tb_fila SET criado_por=? WHERE criado_por=?", (novo_nome, nome_atual))
        cur.execute("UPDATE tb_fila_acesso SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
        conn.commit()
    finally:
        conn.close()


init_db()
