"""Print request module — database handler.

Módulo Solicitação de Impressão — manipulador de banco de dados.

BD próprio: db_mod_solicita_impressao.db (SQLite WAL).
Todas as tabelas do módulo vivem aqui; nada é misturado com outros módulos.
Arquivos PDF enviados ficam em mod_solicita_impressao/solicitacaoImpressao/.

Regras de cota (mensal, hierárquica):
  - Secretaria tem cota máxima (total do mês).
  - Setor pode ter cota própria; se não tiver, usa o pool da secretaria.
  - Ao exceder: envio É permitido, mas a solicitação fica marcada como excedente
    e a critério do autorizador/admin imprimir ou não.
  - Consumo descontado SOMENTE na impressão efetiva (admin confirma).
"""
import sys
import os
import sqlite3
import datetime
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mod_intranet.hora_servidor import hora_servidor, hora_servidor_str

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_solicita_impressao")
PASTA_SOLICITACOES = os.path.join(MOD_DIR, "solicitacaoImpressao")
DB_PATH = os.path.join(BASE_DIR, "db_mod_solicita_impressao.db")

# Configurações padrão do módulo (seed em tb_configuracoes_modulo)
CONFIG_PADRAO = {
    "pasta_arquivos": "solicitacaoImpressao",
    "max_arquivo_mb": "10",
    # Alertas exibidos no topo da nova solicitação (uma frase por linha).
    "alertas_nova_solicitacao": (
        "Para a sua segurança, os documentos só serão impressos com a presença "
        "de alguém no local para retirar as impressões.\n"
        "Impressões com duas ou mais páginas por folha, ou em modo cartaz, devem "
        "ser preparadas por você no próprio arquivo PDF antes do envio.\n"
        "Como a impressão atende a todas as secretarias e o setor também realiza "
        "outras atividades, o horário preferencial de impressão será pela manhã, "
        "entre 9h e 11h. Por isso, pedimos que as demandas sejam planejadas com "
        "antecedência — a conscientização sobre o melhor horário ajuda a todos!\n"
        "Reduzir custos é uma responsabilidade de todos: economizar papel é "
        "economizar recursos públicos. Cada impressão consciente faz a diferença!"
    ),
    "impressora_padrao_nome": "",
    "impressora_padrao_a3_nome": "",
    "marca_dagua_ativa": "1",
    "marca_dagua_texto": (
        "IMPRESSO EM {data} POR {usuario} - SOLIC. #{id} - {secretaria}/{setor}"
    ),
    "marca_dagua_posicao": "centro",
    "marca_dagua_opacidade": "30",
    "marca_dagua_fonte_tamanho": "24",
    "marca_dagua_cor": "#CCCCCC",
    "marca_dagua_rotacao": "45",
    # Tempo de vida do rascunho (upload feito, ainda não confirmado) em minutos.
    # Passado esse prazo o arquivo é removido do servidor automaticamente.
    "tempo_expira_rascunho_min": "10",
    # Tempo para exclusão do arquivo após a impressão ser confirmada (minutos).
    "tempo_exclui_impresso_min": "10",
    # Valores padrão pré-selecionados no formulário de nova solicitação.
    "padrao_papel": "A4",
    "padrao_cor": "Color",        # padrão: colorido
    "padrao_frente_verso": "0",   # 0 = somente frente, 1 = frente e verso
    "padrao_sulfite": "1",        # 1 = papel sulfite (trazer outro tipo se 0)
    "padrao_tipo_papel": "sulfite",  # sulfite | fotografico | verge
}

STATUS_VALIDOS = (
    "pendente", "aguardando_autorizacao", "autorizado",
    "excedente_cota", "impresso", "recusado", "cancelado",
)


# ================= CONEXÃO =================

def get_connection():
    """Opens a connection to the module's own database (FKs enabled).

    Conexão via `banco_conexao.conexao` — SQLite (db_mod_solicita_impressao.db,
    WAL) ou PostgreSQL (schema `solicita_impressao`)."""
    from mod_intranet.banco_conexao import conexao
    conn = conexao("solicita_impressao")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do módulo Solicitação de Impressão")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ================= AUDITORIA =================

def _audit(usuario, acao, descricao, hash_arquivo=None):
    """Logs to the audit trail (db_mod_auditoria.db, one table per module — LGPD).

    Registra na auditoria (db_mod_auditoria.db, tabela por módulo — LGPD).
    Fail-soft por design: falha de auditoria não interrompe a operação."""
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(usuario or "sistema", "solicita_impressao", acao, descricao, hash_arquivo)
    except Exception as e:
        # Auditoria é fail-soft por design: a trilha não derruba a operação.
        _log().debug(f"auditoria indisponível ({acao}): {e}")


def _log():
    """Central logger (loguru) for execution observability.

    Logger central (loguru) para observabilidade de execução."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("solicita_impressao")


# ================= INIT DB =================

def init_db():
    """Creates tables and idempotent seeds. NEVER deletes data.

    Cria tabelas e seeds idempotentes. NUNCA apaga dados. Aplica migrações
    idempotentes (colunas novas via ALTER, correção de datas gravadas como
    string literal de datetime e padrões antigos migrados sem restart)."""
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # ----- Solicitações -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_solicitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_solicitante TEXT NOT NULL,
            arquivo_original TEXT,
            arquivo_servidor TEXT,
            caminho_arquivo TEXT,
            hash_arquivo TEXT,
            qtd_copias INTEGER NOT NULL DEFAULT 1,
            tamanho_papel TEXT NOT NULL DEFAULT 'A4',
            cor TEXT NOT NULL DEFAULT 'PB',
            frente_verso INTEGER NOT NULL DEFAULT 0,
            tipo_borda TEXT,
            papel_sulfite INTEGER NOT NULL DEFAULT 1,
            tipo_papel TEXT NOT NULL DEFAULT 'sulfite',
            observacoes TEXT,
            secretaria_id INTEGER,
            setor_id INTEGER,
            qtd_paginas_arquivo INTEGER NOT NULL DEFAULT 0,
            paginas_contabilizadas INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente',
            cota_excedida INTEGER NOT NULL DEFAULT 0,
            requer_autorizacao INTEGER NOT NULL DEFAULT 0,
            autorizado_por TEXT,
            data_autorizacao DATETIME,
            motivo_recusa TEXT,
            impresso_por TEXT,
            data_impressao DATETIME,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao DATETIME,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE SET NULL,
            FOREIGN KEY (setor_id) REFERENCES tb_setores(id) ON DELETE SET NULL
        )
    """)

    # ----- Secretarias -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_secretarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            sigla TEXT,
            cota_paginas_mensal INTEGER NOT NULL DEFAULT 0,
            limite_pedidos_abertos INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)
    # Migração: limite de pedidos abertos (0 = sem limite)
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_secretarias)").fetchall()]
        if "limite_pedidos_abertos" not in cols:
            cur.execute("ALTER TABLE tb_secretarias "
                        "ADD COLUMN limite_pedidos_abertos INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    # ----- Setores -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_setores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            secretaria_id INTEGER NOT NULL,
            cota_paginas_mensal INTEGER NOT NULL DEFAULT 0,
            limite_pedidos_abertos INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE
        )
    """)
    # Migração: limite de pedidos abertos do setor (0 = sem limite)
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_setores)").fetchall()]
        if "limite_pedidos_abertos" not in cols:
            cur.execute("ALTER TABLE tb_setores "
                        "ADD COLUMN limite_pedidos_abertos INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    # ----- Responsáveis por autorização -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_responsaveis_autorizacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_nome TEXT NOT NULL,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE,
            FOREIGN KEY (setor_id) REFERENCES tb_setores(id) ON DELETE CASCADE
        )
    """)

    # ----- Cotas (mensal) -----
    # OBS: setor_id usa 0 como sentinela para "sem setor" (SQLite trata NULL como
    # distinto em UNIQUE, o que quebraria o único por (secretaria, setor, mês).
    # Sem FK em setor_id para permitir o valor 0.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_cotas_impressao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER NOT NULL DEFAULT 0,
            cota_paginas INTEGER NOT NULL DEFAULT 0,
            mes_referencia TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            atualizado_em DATETIME,
            UNIQUE(secretaria_id, setor_id, mes_referencia),
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE
        )
    """)

    # ----- Consumo de cota -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_consumo_cota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER NOT NULL DEFAULT 0,
            mes_referencia TEXT NOT NULL,
            paginas_usadas INTEGER NOT NULL DEFAULT 0,
            atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(secretaria_id, setor_id, mes_referencia)
        )
    """)

    # ----- Configurações do módulo -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_configuracoes_modulo (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)

    # ----- Rascunhos de upload (arquivo no servidor, ainda não confirmado) -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_rascunhos_upload (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_solicitante TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            nome_original TEXT,
            nome_servidor TEXT NOT NULL,
            hash_arquivo TEXT,
            qtd_paginas_arquivo INTEGER NOT NULL DEFAULT 0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            expira_em DATETIME NOT NULL
        )
    """)

    # Coluna de agendamento de exclusão do arquivo (após impressão)
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_solicitacoes)").fetchall()]
        if "excluir_arquivo_em" not in cols:
            cur.execute("ALTER TABLE tb_solicitacoes ADD COLUMN excluir_arquivo_em DATETIME")
    except Exception:
        pass

    # Coluna de agrupamento (1 pedido por envio; vários arquivos = mesmo grupo)
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_solicitacoes)").fetchall()]
        if "grupo_id" not in cols:
            cur.execute("ALTER TABLE tb_solicitacoes ADD COLUMN grupo_id INTEGER")
    except Exception:
        pass
    # Backfill: registros existentes sem grupo viram o próprio grupo (cada um o seu).
    cur.execute("UPDATE tb_solicitacoes SET grupo_id = id WHERE grupo_id IS NULL")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_grupo ON tb_solicitacoes(grupo_id)")
    # Migração: tipo de papel (sulfite | fotografico | verge) em bancos existentes
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_solicitacoes)").fetchall()]
        if "tipo_papel" not in cols:
            cur.execute("ALTER TABLE tb_solicitacoes "
                        "ADD COLUMN tipo_papel TEXT NOT NULL DEFAULT 'sulfite'")
    except Exception:
        pass

    # ----- Impressoras cadastradas (seletor de impressão) -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_impressoras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            tamanho_papel TEXT NOT NULL DEFAULT 'A4',
            cor TEXT NOT NULL DEFAULT 'Color',
            frente_verso INTEGER NOT NULL DEFAULT 0,
            papel_sulfite INTEGER NOT NULL DEFAULT 1,
            driver TEXT NOT NULL DEFAULT 'PCL6',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migração: coluna de driver (padrão PCL6) em instalações existentes
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_impressoras)").fetchall()]
        if "driver" not in cols:
            cur.execute("ALTER TABLE tb_impressoras ADD COLUMN driver TEXT NOT NULL DEFAULT 'PCL6'")
    except Exception:
        pass

    # Seeds de configuração
    for chave, valor in CONFIG_PADRAO.items():
        cur.execute(
            "INSERT OR IGNORE INTO tb_configuracoes_modulo (chave, valor) VALUES (?, ?)",
            (chave, valor),
        )

    # Migração de padrões antigos (aplicação sem restart):
    #  - rascunho que ainda está no default antigo (4) passa a 10;
    #  - cor que ainda está no default antigo (PB) passa a Colorido.
    cur.execute("UPDATE tb_configuracoes_modulo SET valor='10' "
                "WHERE chave='tempo_expira_rascunho_min' AND valor='4'")
    cur.execute("UPDATE tb_configuracoes_modulo SET valor='Color' "
                "WHERE chave='padrao_cor' AND valor='PB'")

    # Migração: corrigir datas gravadas como string literal de datetime (bug
    # antigo do _atualizar_status_grupo) para o valor real de agora.
    for col in ("data_impressao", "data_autorizacao"):
        try:
            cur.execute(f"UPDATE tb_solicitacoes SET {col}=datetime('now','localtime') "
                        f"WHERE {col} IN (\"datetime('now')\", \"datetime('now','localtime')\")")
        except Exception:
            pass

    # Seed de versão do módulo
    cur.execute("SELECT COUNT(*) FROM tb_configuracoes_modulo WHERE chave='versao_modulo'")
    if not cur.fetchone()[0]:
        cur.execute(
            "INSERT INTO tb_configuracoes_modulo (chave, valor) VALUES ('versao_modulo', '1.0.260908')"
        )

    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_usuario ON tb_solicitacoes(usuario_solicitante)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_status ON tb_solicitacoes(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_secretaria ON tb_solicitacoes(secretaria_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_data ON tb_solicitacoes(data_criacao)")

    conn.commit()
    conn.close()


# ================= CONFIGURAÇÕES =================

def obter_config(chave, default=""):
    """Reads a module-local config key (tb_configuracoes_modulo).

    Lê uma chave de configuração local do módulo (tb_configuracoes_modulo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_configuracoes_modulo WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def definir_config(chave, valor):
    """Writes a module-local config key (upsert in tb_configuracoes_modulo).

    Grava uma chave de configuração local do módulo (upsert em tb_configuracoes_modulo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_configuracoes_modulo (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
            (chave, str(valor)),
        )
        conn.commit()
    finally:
        conn.close()


# ================= IMPRESSORAS =================

def criar_impressora(nome, tamanho_papel="A4", cor="Color", frente_verso=0,
                     papel_sulfite=1, driver="PCL6", ator="sistema"):
    """Registers a printer in tb_impressoras (for the print selector).

    Cadastra uma impressora usada no seletor do botão 'Imprimir'. O nome é
    obrigatório e único (UNIQUE); driver padrão PCL6. Retorna (ok, msg) e
    audita a ação. Falha com IntegrityError se o nome já existir."""
    if not (nome or "").strip():
        return False, "Nome da impressora é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_impressoras (nome, tamanho_papel, cor, frente_verso, papel_sulfite, driver) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nome.strip(), tamanho_papel or "A4", cor or "Color",
             1 if frente_verso else 0, 1 if papel_sulfite else 0,
             (driver or "PCL6").strip() or "PCL6"),
        )
        pid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_impressora",
               f"{nome.strip()} ({tamanho_papel}/{cor}/{driver})")
        return True, f"Impressora '{nome}' cadastrada (ID #{pid})"
    except sqlite3.IntegrityError:
        return False, "Impressora já cadastrada"
    finally:
        conn.close()


def listar_impressoras(ativo=None):
    """Lists registered printers (id, nome, papel, cor, fv, sulf, driver, ativo).

    Lista as impressoras cadastradas em tb_impressoras. Se `ativo` for
    informado, filtra por status (1/0); caso contrário retorna todas."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, nome, tamanho_papel, cor, frente_verso, papel_sulfite, driver, ativo "
               "FROM tb_impressoras")
        if ativo is not None:
            cur.execute(sql + " WHERE ativo=?", (1 if ativo else 0,))
        else:
            cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def obter_impressora(impressora_id):
    """Fetches one registered printer row by id (or None).

    Busca uma impressora cadastrada pelo id (tupla com id, nome, papel, cor,
    frente/verso, sulfite, driver e ativo). Retorna None se não existir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, tamanho_papel, cor, frente_verso, papel_sulfite, driver, ativo "
            "FROM tb_impressoras WHERE id=?", (impressora_id,))
        return cur.fetchone()
    finally:
        conn.close()


def excluir_impressora(impressora_id, ator="sistema"):
    """Removes a registered printer by id.

    Exclui fisicamente a impressora de tb_impressoras pelo id e audita a ação.
    Retorna (ok, msg)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_impressoras WHERE id=?", (impressora_id,))
        conn.commit()
        _audit(ator, "excluir_impressora", f"ID {impressora_id}")
        return True, "Impressora removida"
    finally:
        conn.close()


def definir_impressora_padrao(impressora_id, ator="sistema"):
    """Marks a registered printer as the module default (A4); other stay unmarked.

    Marca a impressora como padrão do módulo conforme o papel: A4 grava
    `impressora_padrao_nome`, A3 grava `impressora_padrao_a3_nome`. Retorna
    (ok, msg) e audita a ação."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        imp = obter_impressora(impressora_id)
        if not imp:
            return False, "Impressora não encontrada"
        if (imp[2] or "A4").upper() == "A4":
            definir_config("impressora_padrao_nome", imp[1])
        else:
            definir_config("impressora_padrao_a3_nome", imp[1])
        _audit(ator, "definir_impressora_padrao", f"ID {impressora_id} -> {imp[1]}")
        return True, f"Impressora padrão definida: {imp[1]}"
    finally:
        conn.close()


# ================= CONTAGEM DE PÁGINAS =================

def contar_paginas_pdf(caminho):
    """Counts PDF pages using PyMuPDF; falls back to pdfplumber.

    Conta páginas do PDF usando PyMuPDF; fallback pdfplumber. Retorna 0 se
    nenhum dos dois conseguir ler o arquivo (fail-soft)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(caminho)
        n = doc.page_count
        doc.close()
        return n
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            return len(pdf.pages) if pdf.pages else 0
    except Exception:
        return 0


def calcular_paginas_contabilizadas(qtd_paginas, qtd_copias, tamanho_papel, frente_verso):
    """Fórmula exata (regra do projeto):
    paginas = qtd_paginas * qtd_copias * fator_papel * fator_frente_verso
      fator_papel: A4=1, A3=2
      fator_frente_verso: não=1, sim=2
    """
    fator_papel = 2 if (tamanho_papel or "A4").upper() == "A3" else 1
    fator_fv = 2 if frente_verso else 1
    try:
        qtd_paginas = int(qtd_paginas)
        qtd_copias = int(qtd_copias)
    except (TypeError, ValueError):
        return 0
    return max(0, qtd_paginas) * max(0, qtd_copias) * fator_papel * fator_fv


# ================= SECRETARIAS =================

def criar_secretaria(nome, sigla="", cota_paginas_mensal=0, limite_pedidos_abertos=0,
                     ator="sistema"):
    """Creates a department (secretaria) with its monthly page quota and open-request limit.

    Cria uma secretaria com cota mensal de páginas e limite de pedidos abertos (0 = sem limite)."""
    if not (nome or "").strip():
        return False, "Nome da secretaria é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_secretarias (nome, sigla, cota_paginas_mensal, limite_pedidos_abertos) "
            "VALUES (?, ?, ?, ?)",
            (nome.strip(), (sigla or "").strip(), int(cota_paginas_mensal or 0),
             int(limite_pedidos_abertos or 0)),
        )
        sid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_secretaria",
               f"Secretaria: {nome} (cota={cota_paginas_mensal}, limite_pedidos={limite_pedidos_abertos})")
        return True, f"Secretaria '{nome}' criada (ID #{sid})"
    except sqlite3.IntegrityError:
        return False, "Secretaria já existe"
    finally:
        conn.close()


def listar_secretarias(ativo=None):
    """Lists departments (id, nome, sigla, cota, limite_pedidos, ativo).

    Lista as secretarias cadastradas (id, nome, sigla, cota, limite de pedidos, ativo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, nome, sigla, cota_paginas_mensal, limite_pedidos_abertos, ativo "
               "FROM tb_secretarias")
        if ativo is not None:
            sql += " WHERE ativo=?"
            cur.execute(sql, (1 if ativo else 0,))
        else:
            cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def obter_secretaria(secretaria_id):
    """Fetches one department row by id (or None).

    Busca uma secretaria pelo id (ou None se não existir)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, sigla, cota_paginas_mensal, limite_pedidos_abertos, ativo "
            "FROM tb_secretarias WHERE id=?", (secretaria_id,))
        return cur.fetchone()
    finally:
        conn.close()


def editar_secretaria(secretaria_id, nome=None, sigla=None, cota_paginas_mensal=None,
                       limite_pedidos_abertos=None, ativo=None, ator="sistema"):
    """Updates department fields (only the provided ones) and audits it.

    Atualiza os campos informados da secretaria e audita a ação."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets, params = [], []
        if nome is not None:
            sets.append("nome=?"); params.append(nome.strip())
        if sigla is not None:
            sets.append("sigla=?"); params.append((sigla or "").strip())
        if cota_paginas_mensal is not None:
            sets.append("cota_paginas_mensal=?"); params.append(int(cota_paginas_mensal or 0))
        if limite_pedidos_abertos is not None:
            sets.append("limite_pedidos_abertos=?"); params.append(int(limite_pedidos_abertos or 0))
        if ativo is not None:
            sets.append("ativo=?"); params.append(1 if ativo else 0)
        if not sets:
            return True, "Nada a alterar"
        params.append(secretaria_id)
        cur.execute(f"UPDATE tb_secretarias SET {', '.join(sets)} WHERE id=?", tuple(params))
        conn.commit()
        _audit(ator, "editar_secretaria", f"ID {secretaria_id}")
        return True, "Secretaria atualizada"
    finally:
        conn.close()


def excluir_secretaria(secretaria_id, ator="sistema"):
    """Physically deletes a department (setors cascade; requests keep FK NULL).

    Exclui fisicamente a secretaria (setores em cascata; solicitações ficam com FK NULL)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_secretarias WHERE id=?", (secretaria_id,))
        conn.commit()
        _audit(ator, "excluir_secretaria", f"ID {secretaria_id}")
        return True, "Secretaria excluída"
    finally:
        conn.close()


# ================= SETORES =================

def criar_setor(nome, secretaria_id, cota_paginas_mensal=0, limite_pedidos_abertos=0,
                ator="sistema"):
    """Creates a unit (setor) under a department, with optional own quota and open-request limit.

    Cria um setor vinculado a uma secretaria, com cota própria opcional e limite de pedidos."""
    if not (nome or "").strip():
        return False, "Nome do setor é obrigatório"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_setores (nome, secretaria_id, cota_paginas_mensal, limite_pedidos_abertos) "
            "VALUES (?, ?, ?, ?)",
            (nome.strip(), int(secretaria_id), int(cota_paginas_mensal or 0),
             int(limite_pedidos_abertos or 0)),
        )
        sid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_setor",
               f"Setor: {nome} (secretaria={secretaria_id}, limite_pedidos={limite_pedidos_abertos})")
        return True, f"Setor '{nome}' criado (ID #{sid})"
    except sqlite3.IntegrityError:
        return False, "Setor já existe nesta secretaria"
    finally:
        conn.close()


def listar_setores(secretaria_id=None, ativo=None):
    """Lists units (id, nome, secretaria_id, cota, limite_pedidos, ativo).

    Lista os setores (id, nome, secretaria_id, cota, limite de pedidos, ativo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, nome, secretaria_id, cota_paginas_mensal, limite_pedidos_abertos, ativo "
               "FROM tb_setores")
        params = []
        where = []
        if secretaria_id is not None:
            where.append("secretaria_id=?")
            params.append(int(secretaria_id))
        if ativo is not None:
            where.append("ativo=?")
            params.append(1 if ativo else 0)
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def obter_setor(setor_id):
    """Fetches one unit row by id (or None).

    Busca um setor pelo id (ou None se não existir)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, secretaria_id, cota_paginas_mensal, limite_pedidos_abertos, ativo "
            "FROM tb_setores WHERE id=?", (setor_id,))
        return cur.fetchone()
    finally:
        conn.close()


def editar_setor(setor_id, nome=None, secretaria_id=None, cota_paginas_mensal=None,
                 limite_pedidos_abertos=None, ativo=None, ator="sistema"):
    """Updates unit fields (only the provided ones) and audits it.

    Atualiza os campos informados do setor e audita a ação."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets, params = [], []
        if nome is not None:
            sets.append("nome=?"); params.append(nome.strip())
        if secretaria_id is not None:
            sets.append("secretaria_id=?"); params.append(int(secretaria_id))
        if cota_paginas_mensal is not None:
            sets.append("cota_paginas_mensal=?"); params.append(int(cota_paginas_mensal or 0))
        if limite_pedidos_abertos is not None:
            sets.append("limite_pedidos_abertos=?"); params.append(int(limite_pedidos_abertos or 0))
        if ativo is not None:
            sets.append("ativo=?"); params.append(1 if ativo else 0)
        if not sets:
            return True, "Nada a alterar"
        params.append(setor_id)
        cur.execute(f"UPDATE tb_setores SET {', '.join(sets)} WHERE id=?", tuple(params))
        conn.commit()
        _audit(ator, "editar_setor", f"ID {setor_id}")
        return True, "Setor atualizado"
    finally:
        conn.close()


def excluir_setor(setor_id, ator="sistema"):
    """Physically deletes a unit (responsáveis cascade; requests keep FK NULL).

    Exclui fisicamente o setor (responsáveis em cascata; solicitações ficam com FK NULL)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_setores WHERE id=?", (setor_id,))
        conn.commit()
        _audit(ator, "excluir_setor", f"ID {setor_id}")
        return True, "Setor excluído"
    finally:
        conn.close()


# ================= RESPONSÁVEIS POR AUTORIZAÇÃO =================

def criar_responsavel(user_nome, secretaria_id, setor_id=None, ator="sistema"):
    """Grants a user the power to authorize requests for a department/unit.

    Funciona para qualquer usuário cadastrado (inclusive perfil `comum`) —
    a checagem de autorização usa esta tabela, independente do perfil."""
    if not (user_nome or "").strip():
        return False, "Usuário é obrigatório"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_responsaveis_autorizacao (user_nome, secretaria_id, setor_id) "
            "VALUES (?, ?, ?)",
            (user_nome.strip(), int(secretaria_id), setor_id),
        )
        rid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_responsavel", f"{user_nome} (secr={secretaria_id}, setor={setor_id})")
        return True, f"Responsável '{user_nome}' cadastrado (ID #{rid})"
    except sqlite3.IntegrityError:
        return False, "Responsável já cadastrado para este vínculo"
    finally:
        conn.close()


def listar_responsaveis(secretaria_id=None, setor_id=None, ativo=None):
    """Lists authorization responsáveis (id, user, secretaria, setor, ativo).

    Lista os responsáveis por autorização (id, usuário, secretaria, setor, ativo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, user_nome, secretaria_id, setor_id, ativo "
               "FROM tb_responsaveis_autorizacao")
        params = []
        where = []
        if secretaria_id is not None:
            where.append("secretaria_id=?")
            params.append(int(secretaria_id))
        if setor_id is not None:
            where.append("setor_id=?")
            params.append(setor_id)
        if ativo is not None:
            where.append("ativo=?")
            params.append(1 if ativo else 0)
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def excluir_responsavel(responsavel_id, ator="sistema"):
    """Removes an authorization grant by id and audits it.

    Remove um vínculo de autorização pelo id e audita a ação."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_responsaveis_autorizacao WHERE id=?", (responsavel_id,))
        conn.commit()
        _audit(ator, "excluir_responsavel", f"ID {responsavel_id}")
        return True, "Responsável removido"
    finally:
        conn.close()


def eh_responsavel_autorizacao(user_nome, secretaria_id, setor_id=None):
    """Checks whether user_nome is an authorizer for the department/unit.

    Verifica se user_nome é responsável por autorizar para a secretaria/setor."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if setor_id:
            cur.execute(
                "SELECT 1 FROM tb_responsaveis_autorizacao "
                "WHERE user_nome=? AND secretaria_id=? AND setor_id=? AND ativo=1 LIMIT 1",
                (user_nome, int(secretaria_id), setor_id),
            )
            if cur.fetchone():
                return True
        cur.execute(
            "SELECT 1 FROM tb_responsaveis_autorizacao "
            "WHERE user_nome=? AND secretaria_id=? AND (setor_id IS NULL OR setor_id=?) AND ativo=1 LIMIT 1",
            (user_nome, int(secretaria_id), setor_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


# ================= COTAS (MENSAL) =================

def mes_atual():
    """Current month reference in 'YYYY-MM' format (quota period key).

    Chave do período de cota no formato 'YYYY-MM', calculada a partir da hora
    do SERVIDOR (`hora_servidor()`) — nunca do cliente."""
    return hora_servidor().strftime("%Y-%m")


def obter_ou_criar_cota(secretaria_id, setor_id, mes=None):
    """Retorna (cota_paginas, existe). Cria registro se não existir.
    setor_id=None (sem setor) é normalizado para 0 (sentinelas)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT cota_paginas FROM tb_cotas_impressao "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        row = cur.fetchone()
        if row:
            return row[0], True
        # Cria com cota da secretaria/setor (do cadastro)
        sec = obter_secretaria(secretaria_id)
        cota_base = sec[3] if sec else 0
        if setor_id:
            st = obter_setor(setor_id)
            if st and st[3]:
                cota_base = st[3]
        cur.execute(
            "INSERT OR IGNORE INTO tb_cotas_impressao "
            "(secretaria_id, setor_id, cota_paginas, mes_referencia) VALUES (?, ?, ?, ?)",
            (int(secretaria_id), setor_id, int(cota_base or 0), mes),
        )
        conn.commit()
        return int(cota_base or 0), False
    finally:
        conn.close()


def definir_cota(secretaria_id, setor_id, cota_paginas, mes=None, ator="sistema"):
    """Defines/updates the monthly page quota for a department/unit (upsert).

    Define/atualiza a cota mensal de páginas de uma secretaria/setor (upsert).
    O `atualizado_em` usa `datetime('now','localtime')` (relógio do servidor)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_cotas_impressao (secretaria_id, setor_id, cota_paginas, mes_referencia, atualizado_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime')) "
            "ON CONFLICT(secretaria_id, setor_id, mes_referencia) DO UPDATE SET "
            "cota_paginas=excluded.cota_paginas, atualizado_em=datetime('now','localtime')",
            (int(secretaria_id), setor_id, int(cota_paginas or 0), mes),
        )
        conn.commit()
        _audit(ator, "definir_cota",
               f"secr={secretaria_id} setor={setor_id} cota={cota_paginas} mes={mes}")
        return True, "Cota definida"
    finally:
        conn.close()


def obter_consumo(secretaria_id, setor_id, mes=None):
    """Pages already consumed in the month for the department/unit (0 if none).

    Páginas já consumidas no mês para a secretaria/setor (0 se não houver)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT paginas_usadas FROM tb_consumo_cota "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _incrementar_consumo(secretaria_id, setor_id, paginas, mes=None):
    """Adds pages to the monthly consumption (upsert on the period row).

    Soma páginas ao consumo mensal (upsert na linha do período). O
    `atualizado_em` usa `datetime('now','localtime')` (relógio do servidor)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_consumo_cota (secretaria_id, setor_id, mes_referencia, paginas_usadas) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(secretaria_id, setor_id, mes_referencia) DO UPDATE SET "
            "paginas_usadas = paginas_usadas + excluded.paginas_usadas, "
            "atualizado_em = datetime('now','localtime')",
            (int(secretaria_id), setor_id, mes, int(paginas or 0)),
        )
        conn.commit()
    finally:
        conn.close()


def verificar_excedente(secretaria_id, setor_id, paginas_contabilizadas):
    """Verifica se a impressão excederá alguma cota (secretaria OU setor).
    Retorna (excedente: bool, detalhe: str)."""
    setor_id = int(setor_id or 0)
    # Cota da secretaria
    cota_secr, _ = obter_ou_criar_cota(secretaria_id, 0)
    usado_secr = obter_consumo(secretaria_id, 0)
    if cota_secr > 0 and (usado_secr + paginas_contabilizadas) > cota_secr:
        return True, f"Excede cota da secretaria ({usado_secr + paginas_contabilizadas}/{cota_secr})"
    # Cota do setor (se houver)
    if setor_id:
        cota_setor, _ = obter_ou_criar_cota(secretaria_id, setor_id)
        usado_setor = obter_consumo(secretaria_id, setor_id)
        if cota_setor > 0 and (usado_setor + paginas_contabilizadas) > cota_setor:
            return True, f"Excede cota do setor ({usado_setor + paginas_contabilizadas}/{cota_setor})"
    return False, ""


def resetar_consumo(secretaria_id, setor_id, mes=None, ator="sistema"):
    """Zeros the month's consumption (manual).

    Zera o consumo do mês (manual). O `atualizado_em` usa
    `datetime('now','localtime')` (relógio do servidor)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_consumo_cota SET paginas_usadas=0, atualizado_em=datetime('now','localtime') "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        conn.commit()
        _audit(ator, "resetar_consumo",
               f"secr={secretaria_id} setor={setor_id} mes={mes}")
        return True, "Consumo do mês resetado"
    finally:
        conn.close()


def obter_limite_pedidos_abertos(secretaria_id, setor_id=None):
    """Returns the open-request limits (department, unit) — 0 means unlimited.

    Lê os tetos de pedidos abertos configurados na secretaria e no setor
    (coluna `limite_pedidos_abertos`). Retorna a tupla
    (limite_secretaria, limite_setor); 0 = sem limite."""
    limite_secr = 0
    limite_secr = 0
    sec = obter_secretaria(secretaria_id) if secretaria_id else None
    if sec:
        limite_secr = int(sec[4] or 0)
    limite_setor = 0
    if setor_id:
        st = obter_setor(setor_id)
        if st:
            limite_setor = int(st[4] or 0)
    return limite_secr, limite_setor


def contar_pedidos_abertos(secretaria_id, setor_id=None):
    """Counts still-open requests (not printed/refused/cancelled) for a department/unit.

    'Aberto' = status em pendente/aguardando/autorizado/excedente. A impressão
    (ou recusa/cancelamento) libera a vaga (contagem elástica). Retorna a tupla
    (total_secretaria, total_setor); o total do setor é 0 quando `setor_id` é None."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Total da secretaria (qualquer setor)
        cur.execute(
            "SELECT COUNT(*) FROM tb_solicitacoes "
            "WHERE secretaria_id=? AND status NOT IN ('impresso','recusado','cancelado')",
            (int(secretaria_id),))
        total_secr = cur.fetchone()[0]
        # Total do setor específico
        total_setor = 0
        if setor_id:
            cur.execute(
                "SELECT COUNT(*) FROM tb_solicitacoes "
                "WHERE secretaria_id=? AND setor_id=? "
                "AND status NOT IN ('impresso','recusado','cancelado')",
                (int(secretaria_id), int(setor_id)))
            total_setor = cur.fetchone()[0]
        return total_secr, total_setor
    finally:
        conn.close()


def verificar_limite_pedidos(secretaria_id, setor_id=None):
    """Checks the elastic open-request limits. Returns (ok, msg).

    O setor só pode pedir se a secretaria não atingiu o máximo; cada um tem
    seu próprio teto. 0 = sem limite. Quando o limite é atingido, retorna
    (False, mensagem) para bloquear a criação/confirmação da solicitação."""
    if not secretaria_id:
        return True, ""
    limite_secr, limite_setor = obter_limite_pedidos_abertos(secretaria_id, setor_id)
    aberto_secr, aberto_setor = contar_pedidos_abertos(secretaria_id, setor_id)
    if limite_secr > 0 and aberto_secr >= limite_secr:
        return False, (f"Limite de {limite_secr} pedidos abertos da secretaria atingido. "
                       f"Imprima (ou cancele) pedidos pendentes para liberar vaga.")
    if limite_setor > 0 and aberto_setor >= limite_setor:
        return False, (f"Limite de {limite_setor} pedidos abertos do setor atingido. "
                       f"Aguardando autorização/impressão dos pedidos atuais.")
    return True, ""


def percentual_consumo(secretaria_id, setor_id, mes=None):
    """Returns (percent 0-100+, used, quota).

    Retorna (percentual 0-100+, usado, cota) do consumo do mês para o vínculo."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    cota, _ = obter_ou_criar_cota(secretaria_id, setor_id)
    usado = obter_consumo(secretaria_id, setor_id)
    if cota <= 0:
        return 0, usado, cota
    return round((usado / cota) * 100, 1), usado, cota


# ================= SOLICITAÇÕES =================

def _sanitizar_nome(s):
    """ASCII-sanitizes a name for file names (accents out, non-alnum → '_').

    Sanitiza um nome para uso em nomes de arquivo (acentos removidos, não alfanuméricos → '_')."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = "".join(c if c.isalnum() else "_" for c in s)
    return s.strip("_") or "x"


def gerar_nome_arquivo(data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id,
                       cor="Color", tipo_papel="sulfite", ordem_envio=1):
    """Builds the final file name:
    AAMMDDHHMMSS_secretaria_setor_nomeSolicitante_qtdCopias_cor_tipoPapel_quantidadeFolhas_ordemDoenvioArquivo.pdf.

    Monta o nome final do arquivo no padrão do projeto: data/hora no formato
    `%y%m%d%H%M%S`, secretaria, setor, solicitante, quantidade de cópias, cor
    (`colorido`/`pretoebranco`), tipo de papel (`sulfite`/`fotografico`/`verge`),
    quantidade de folhas do arquivo e a ordem de envio do arquivo (1, 2, 3…),
    garantindo unicidade mesmo quando vários arquivos chegam no mesmo segundo
    com a mesma quantidade de páginas. Nomes são sanitizados (acentos
    removidos, espaços→`_`)."""
    sec = obter_secretaria(secretaria_id)
    sec_nome = _sanitizar_nome(sec[2] or sec[1]) if sec else "secretaria"
    set_nome = "sem_setor"
    if setor_id:
        st = obter_setor(setor_id)
        if st:
            set_nome = _sanitizar_nome(st[1])
    usuario_san = _sanitizar_nome(usuario)
    cor_nome = "colorido" if (cor or "Color").lower().startswith("col") else "pretoebranco"
    papel_nome = _sanitizar_nome(tipo_papel or "sulfite")
    data_hora = (data_hora or hora_servidor().strftime("%Y%m%d_%H%M%S"))
    data_hora = data_hora.replace("-", "").replace(":", "").replace(" ", "_")
    if len(data_hora) >= 14 and data_hora[2].isdigit():
        try:
            ano = data_hora[:4]
            resto = data_hora[4:].replace("_", "")
            data_hora = f"{ano[2:]}{resto[:12]}"
        except Exception:
            pass
    return (f"{data_hora}_{sec_nome}_{set_nome}_{usuario_san}_{qtd_copias}_{cor_nome}_"
            f"{papel_nome}_{qtd_paginas}_{ordem_envio}.pdf")


def criar_solicitacao(usuario, caminho_tmp, arquivo_original, qtd_copias, tamanho_papel,
                      cor, frente_verso, tipo_borda, papel_sulfite, observacoes,
                      secretaria_id, setor_id, ator="sistema", tipo_papel="sulfite",
                      ordem_envio=1):
    """Creates a request: saves the PDF, counts pages, computes accounting and
    marks over-quota when needed.

    Cria solicitação: salva PDF na pasta do módulo, conta páginas, calcula
    contabilização e marca excedente se necessário. Recebe `tipo_papel`
    (sulfite/fotografico/verge) e `ordem_envio` para o nome final do arquivo."""
    if not caminho_tmp or not os.path.exists(caminho_tmp):
        return False, "Arquivo PDF não encontrado"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"

    limite_ok, limite_msg = verificar_limite_pedidos(secretaria_id, setor_id)
    if not limite_ok:
        return False, limite_msg

    qtd_paginas = contar_paginas_pdf(caminho_tmp)
    if qtd_paginas <= 0:
        return False, "Não foi possível contar as páginas do PDF (arquivo inválido?)"

    paginas_calc = calcular_paginas_contabilizadas(
        qtd_paginas, qtd_copias, tamanho_papel, frente_verso)

    # Nome e destino
    agora = hora_servidor()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    nome_servidor = gerar_nome_arquivo(
        data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id, cor,
        tipo_papel, ordem_envio=ordem_envio)
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    destino = os.path.join(PASTA_SOLICITACOES, nome_servidor)
    import shutil
    shutil.copy2(caminho_tmp, destino)

    hash_arq = None
    try:
        from mod_intranet.bd_manipulador import hash_arquivo
        hash_arq = hash_arquivo(destino)
    except Exception:
        pass

    # Excedente de cota
    excedente, detalhe = verificar_excedente(secretaria_id, setor_id, paginas_calc)
    cota_excedida = 1 if excedente else 0

    # Requer autorização? (se há responsável cadastrado para secretaria/setor)
    requer_auth = 1 if tem_responsavel_para(secretaria_id, setor_id) else 0

    if excedente:
        status = "excedente_cota"
    elif requer_auth:
        status = "aguardando_autorizacao"
    else:
        status = "autorizado"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_solicitacoes
               (usuario_solicitante, arquivo_original, arquivo_servidor, caminho_arquivo,
                hash_arquivo, qtd_copias, tamanho_papel, cor, frente_verso, tipo_borda,
                papel_sulfite, tipo_papel, observacoes, secretaria_id, setor_id,
                qtd_paginas_arquivo, paginas_contabilizadas, status, cota_excedida,
                requer_autorizacao, data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
            (usuario, arquivo_original, nome_servidor, destino, hash_arq,
             int(qtd_copias), tamanho_papel, cor, 1 if frente_verso else 0, tipo_borda,
             1 if papel_sulfite else 0, tipo_papel or "sulfite", observacoes,
             int(secretaria_id), setor_id, qtd_paginas, paginas_calc, status,
             cota_excedida, requer_auth),
        )
        sid = cur.lastrowid
        cur.execute("UPDATE tb_solicitacoes SET grupo_id = id WHERE id=?", (sid,))
        conn.commit()
        _audit(ator, "criar_solicitacao",
               f"#{sid} {nome_servidor} | paginas_calc={paginas_calc} | {status}"
               + (" | EXCEDENTE" if excedente else ""),
               hash_arq)
        msg = f"Solicitação #{sid} criada"
        if excedente:
            msg += " — ATENÇÃO: excedente de cota (sujeita à autorização)"
        elif requer_auth:
            msg += " — aguardando autorização"
        else:
            msg += " — autorizada, pronta para impressão"
        return True, msg
    except Exception as e:
        _log().exception(f"falha ao criar solicitação: {e}")
        return False, f"Erro ao criar solicitação: {e}"
    finally:
        conn.close()


def tem_responsavel_para(secretaria_id, setor_id):
    """True if any active responsável covers the department (unit optional).

    Verdadeiro se há responsável ativo cobrindo a secretaria (setor opcional)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM tb_responsaveis_autorizacao "
            "WHERE secretaria_id=? AND ativo=1 "
            "AND (setor_id IS NULL OR setor_id=?) LIMIT 1",
            (int(secretaria_id), setor_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def listar_solicitacoes(usuario=None, status=None, secretaria_id=None, setor_id=None,
                        apenas_excedentes=False, limite=200,
                        busca=None, data_inicio=None, data_fim=None):
    """Lists requests joined with department/unit names, with optional filters.

    `busca`: texto livre casado (case-insensitive) com solicitante, observações,
    nome original/servidor do arquivo e nome da secretaria/setor.
    `data_inicio`/`data_fim`: filtro de data em 'YYYY-MM-DD' (sobre data_criacao)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT s.id, s.usuario_solicitante, s.arquivo_servidor, s.arquivo_original, "
               "s.qtd_copias, s.tamanho_papel, s.cor, s.frente_verso, s.tipo_borda, "
               "s.papel_sulfite, s.tipo_papel, s.observacoes, s.secretaria_id, s.setor_id, "
               "s.qtd_paginas_arquivo, s.paginas_contabilizadas, s.status, s.cota_excedida, "
               "s.requer_autorizacao, s.autorizado_por, s.data_autorizacao, s.motivo_recusa, "
               "s.impresso_por, s.data_impressao, s.data_criacao, "
               "sec.nome, sec.sigla, st.nome, s.grupo_id "
               "FROM tb_solicitacoes s "
               "LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id "
               "LEFT JOIN tb_setores st ON st.id = s.setor_id "
               "WHERE 1=1")
        params = []
        if usuario:
            sql += " AND s.usuario_solicitante=?"
            params.append(usuario)
        if status:
            sql += " AND s.status=?"
            params.append(status)
        if secretaria_id is not None:
            sql += " AND s.secretaria_id=?"
            params.append(int(secretaria_id))
        if setor_id is not None:
            sql += " AND s.setor_id=?"
            params.append(setor_id)
        if apenas_excedentes:
            sql += " AND s.cota_excedida=1"
        if busca:
            like = f"%{busca.strip()}%"
            sql += (" AND (s.usuario_solicitante LIKE ? COLLATE NOCASE "
                    "OR s.observacoes LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_servidor LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_original LIKE ? COLLATE NOCASE "
                    "OR sec.nome LIKE ? COLLATE NOCASE "
                    "OR sec.sigla LIKE ? COLLATE NOCASE "
                    "OR st.nome LIKE ? COLLATE NOCASE)")
            params += [like] * 7
        if data_inicio:
            sql += " AND date(s.data_criacao) >= ?"
            params.append(data_inicio)
        if data_fim:
            sql += " AND date(s.data_criacao) <= ?"
            params.append(data_fim)
        sql += " ORDER BY s.data_criacao DESC LIMIT ?"
        params.append(int(limite))
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def obter_solicitacao(solicitacao_id):
    """Fetches one request as a dict (all columns) or None.

    Busca uma solicitação como dict (todas as colunas) ou None."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tb_solicitacoes WHERE id=?", (solicitacao_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def _eh_admin_do_modulo(user):
    """System-wide admin OR the print module admin.

    Admin geral do sistema OU administrador do módulo de impressão."""
    try:
        from mod_intranet import autenticacao
        return (autenticacao.perfil_global_de(user) == "administrador_geral"
                or autenticacao.eh_admin_do_modulo(user, "solicita_impressao"))
    except Exception:
        return False


def _pode_autorizar(user, secretaria_id, setor_id):
    """Only the responsável for the link OR the module admin may authorize.

    Só autoriza quem é responsável pelo vínculo OU administrador do módulo."""
    if _eh_admin_do_modulo(user):
        return True
    if not secretaria_id:
        return False
    return eh_responsavel_autorizacao(user, int(secretaria_id), setor_id)


def autorizar_solicitacao(solicitacao_id, autor, motivo=None):
    """Authorizes a pending/over-quota request (permission-checked). Returns (ok, msg).

    Autoriza uma solicitação pendente/excedente (com checagem de permissão). Retorna (ok, msg)."""
    sol = obter_solicitacao(solicitacao_id)
    if not sol:
        return False, "Solicitação não encontrada"
    if sol["status"] not in ("aguardando_autorizacao", "excedente_cota"):
        return False, "Não autorizável neste estado"
    if not _pode_autorizar(autor, sol.get("secretaria_id"), sol.get("setor_id")):
        return False, "Usuário sem permissão de autorização para este vínculo"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='autorizado', autorizado_por=?, "
            "data_autorizacao=datetime('now','localtime'), data_atualizacao=datetime('now','localtime') "
            "WHERE id=? AND status IN ('aguardando_autorizacao', 'excedente_cota')",
            (autor, solicitacao_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _audit(autor, "autorizar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação autorizada" if ok else "Não autorizável neste estado"
    finally:
        conn.close()


def recusar_solicitacao(solicitacao_id, autor, motivo):
    """Refuses a request (mandatory reason) and removes its file. Returns (ok, msg).

    Recusa uma solicitação (motivo obrigatório) e remove o arquivo. Retorna (ok, msg)."""
    if not (motivo or "").strip():
        return False, "Motivo da recusa é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='recusado', motivo_recusa=?, "
            "data_atualizacao=datetime('now','localtime') WHERE id=? "
            "AND status IN ('aguardando_autorizacao', 'excedente_cota', 'autorizado')",
            (motivo.strip(), solicitacao_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(autor, "recusar_solicitacao", f"#{solicitacao_id} motivo={motivo}", None)
        return ok, "Solicitação recusada" if ok else "Não recusável"
    finally:
        conn.close()


def imprimir_solicitacao(solicitacao_id, admin_user, ator="sistema"):
    """Marks as printed and deducts the quota (department + unit if any).

    Marca como impresso e desconta cota (secretaria + setor se houver). A data
    de impressão e o prazo de exclusão do arquivo usam a hora do servidor
    (`hora_servidor()` / `datetime('now','localtime')`)."""
    sol = obter_solicitacao(solicitacao_id)
    if not sol:
        return False, "Solicitação não encontrada"
    if sol["status"] != "autorizado":
        return False, f"Status '{sol['status']}' não permite impressão (é necessário autorizar antes)"
    if not sol.get("autorizado_por"):
        return False, "Solicitação ainda não foi autorizada — liberada só após autorização"
    secr = sol["secretaria_id"]
    setor = sol["setor_id"]
    paginas = sol["paginas_contabilizadas"]
    # Desconta da secretaria (sempre)
    _incrementar_consumo(secr, 0, paginas)
    # Desconta do setor apenas se houver setor próprio (evita duplo desconto
    # na mesma linha secretaria/0 quando setor é None)
    if setor:
        _incrementar_consumo(secr, setor, paginas)
    conn = get_connection()
    try:
        cur = conn.cursor()
        minutos = tempo_exclui_impresso_min()
        exclui_em = (hora_servidor() + datetime.timedelta(minutes=minutos)).strftime(
            "%Y-%m-%d %H:%M:%S")
        cur.execute(
            "UPDATE tb_solicitacoes SET status='impresso', impresso_por=?, "
            "data_impressao=datetime('now','localtime'), excluir_arquivo_em=?, "
            "data_atualizacao=datetime('now','localtime') WHERE id=?",
            (admin_user, exclui_em, solicitacao_id),
        )
        conn.commit()
        _audit(ator, "imprimir_solicitacao",
               f"#{solicitacao_id} paginas={paginas} arquivo_exclui_em={exclui_em}", None)
        _log().info(f"impressao #{solicitacao_id} por {admin_user} | paginas={paginas} "
                    f"arquivo_exclui_em={exclui_em}")
        return True, f"Solicitação #{solicitacao_id} marcada como impressa"
    finally:
        conn.close()


def recuar_solicitacao(solicitacao_id, ator="sistema"):
    """Cancels an already authorized/printed request (status=cancelado).

    Cancela solicitação já autorizada/impressa (status=cancelado) e remove o arquivo."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='cancelado', data_atualizacao=datetime('now','localtime') "
            "WHERE id=? AND status IN ('autorizado', 'excedente_cota', 'impresso')",
            (solicitacao_id,),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(ator, "recuar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação cancelada" if ok else "Não cancelável"
    finally:
        conn.close()


def cancelar_solicitacao(solicitacao_id, usuario, ator="sistema"):
    """User cancels their own request if still pending/awaiting/over-quota.

    Usuário cancela própria solicitação se ainda pendente/aguardando/excedente."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='cancelado', data_atualizacao=datetime('now','localtime') "
            "WHERE id=? AND usuario_solicitante=? AND status IN "
            "('pendente', 'aguardando_autorizacao', 'excedente_cota')",
            (solicitacao_id, usuario),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(ator, "cancelar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação cancelada" if ok else "Não cancelável pelo usuário"
    finally:
        conn.close()


def tempo_expira_rascunho_min():
    """Minutes a draft survives before automatic removal (default 10, min 1).

    Minutos que um rascunho sobrevive antes da remoção automática (padrão 10,
    mínimo 1). Valor inválido cai no padrão 10 (fail-soft)."""
    try:
        return max(1, int(obter_config("tempo_expira_rascunho_min", "10")))
    except (TypeError, ValueError):
        return 10


def tempo_exclui_impresso_min():
    """Minutes before the file is deleted after printing (default 10, min 1).

    Minutos antes de excluir o arquivo após a impressão (padrão 10, mínimo 1).
    Valor inválido cai no padrão 10 (fail-soft)."""
    try:
        return max(1, int(obter_config("tempo_exclui_impresso_min", "10")))
    except (TypeError, ValueError):
        return 10


def _remover_arquivo_se_existir(caminho):
    """Removes a file from disk if it exists (fail-soft). Returns True if removed.

    Remove um arquivo do disco se existir (fail-soft). Retorna True se removeu."""
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
            return True
    except OSError:
        pass
    return False


def _remover_arquivo_solicitacao(solicitacao_id):
    """Removes the physical file of a request (on refuse/recall/cancel).

    Remove o arquivo físico de uma solicitação (ao recusar/recuar/cancelar)."""
    try:
        sol = obter_solicitacao(solicitacao_id)
        if sol and sol.get("caminho_arquivo"):
            _remover_arquivo_se_existir(sol["caminho_arquivo"])
    except Exception:
        pass


def registrar_rascunho(usuario, conteudo_bytes, nome_original):
    """Receives the PDF (bytes) from the upload, saves it ON THE SERVER with the
    system name (original name discarded), counts pages and registers the draft
    with an expiration. Returns (rascunho_id, nome_servidor, qtd_paginas, caminho).

    Recebe o PDF (bytes) do upload, salva NO SERVIDOR já com nome do sistema
    (sem usar o nome original), conta páginas e registra rascunho com expiração.
    Retorna (rascunho_id, nome_servidor, qtd_paginas, caminho). A data de
    criação/expiração usa a hora do servidor (`hora_servidor()`)."""
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    agora = hora_servidor()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    usuario_san = _sanitizar_nome(usuario)
    # Nome único por rascunho (evita colisão no mesmo segundo ao anexar vários PDFs)
    destino = os.path.join(PASTA_SOLICITACOES,
                           f"{data_hora}_{usuario_san}_{uuid.uuid4().hex[:8]}_rascunho.pdf")
    with open(destino, "wb") as f:
        f.write(conteudo_bytes)
    qtd_paginas = contar_paginas_pdf(destino)
    if qtd_paginas <= 0:
        _remover_arquivo_se_existir(destino)
        _log().warning(f"rascunho de {usuario}: PDF inválido/sem páginas (nome original="
                        f"{nome_original})")
        return None, "", 0, None
    hash_arq = None
    try:
        from mod_intranet.bd_manipulador import hash_arquivo
        hash_arq = hash_arquivo(destino)
    except Exception:
        pass
    minutos = tempo_expira_rascunho_min()
    expira_dt = (agora + datetime.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_rascunhos_upload "
            "(usuario_solicitante, caminho_arquivo, nome_original, nome_servidor, "
            "hash_arquivo, qtd_paginas_arquivo, criado_em, expira_em) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?)",
            (usuario, destino, nome_original or "", os.path.basename(destino),
             hash_arq, qtd_paginas, expira_dt))
        rid = cur.lastrowid
        conn.commit()
        _audit(usuario, "rascunho_upload",
               f"#{rid} {os.path.basename(destino)} paginas={qtd_paginas} expira_em={expira_dt}",
               hash_arq)
        return rid, os.path.basename(destino), qtd_paginas, destino
    finally:
        conn.close()


def obter_rascunho(rascunho_id):
    """Fetches one upload draft as a dict (all columns) or None.

    Busca um rascunho de upload como dict (todas as colunas) ou None."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def cancelar_rascunho(rascunho_id, ator="sistema"):
    """Removes the draft and its server file (user gave up before confirming).

    Remove o rascunho e o arquivo do servidor (usuário desistiu antes de confirmar)."""
    r = obter_rascunho(rascunho_id)
    if not r:
        return False, "Rascunho não encontrado"
    _remover_arquivo_se_existir(r["caminho_arquivo"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        conn.commit()
        _audit(ator, "rascunho_cancelado", f"#{rascunho_id} {r['nome_servidor']}", None)
        return True, "Rascunho removido"
    finally:
        conn.close()


def confirmar_rascunho(rascunho_id, qtd_copias, tamanho_papel, cor, frente_verso,
                       tipo_borda, papel_sulfite, observacoes, secretaria_id, setor_id,
                       ator="sistema", tipo_papel="sulfite"):
    """Converts a draft into a request: renames the file to the final pattern,
    creates the record in tb_solicitacoes and removes the draft.

    Converte um rascunho em solicitação: renomeia o arquivo para o padrão final,
    cria o registro em tb_solicitacoes e remove o rascunho. Recebe `tipo_papel`
    (sulfite/fotografico/verge) gravado na coluna `tipo_papel`."""
    r = obter_rascunho(rascunho_id)
    if not r:
        return False, "Rascunho não encontrado (expirado?)", None
    if not os.path.exists(r["caminho_arquivo"]):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
            conn.commit()
        finally:
            conn.close()
        return False, "Arquivo do rascunho sumiu do servidor", None
    if not secretaria_id:
        return False, "Secretaria é obrigatória", None

    limite_ok, limite_msg = verificar_limite_pedidos(secretaria_id, setor_id)
    if not limite_ok:
        return False, limite_msg, None

    usuario = r["usuario_solicitante"]
    qtd_paginas = r["qtd_paginas_arquivo"] or contar_paginas_pdf(r["caminho_arquivo"])
    paginas_calc = calcular_paginas_contabilizadas(
        qtd_paginas, qtd_copias, tamanho_papel, frente_verso)

    # Nome final (padrão do projeto) — dataHora da confirmação
    agora = hora_servidor()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    nome_servidor = gerar_nome_arquivo(
        data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id, cor,
        tipo_papel)
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    destino = os.path.join(PASTA_SOLICITACOES, nome_servidor)
    import shutil
    shutil.move(r["caminho_arquivo"], destino)

    hash_arq = r["hash_arquivo"]
    excedente, detalhe = verificar_excedente(secretaria_id, setor_id, paginas_calc)
    cota_excedida = 1 if excedente else 0
    requer_auth = 1 if tem_responsavel_para(secretaria_id, setor_id) else 0
    if excedente:
        status = "excedente_cota"
    elif requer_auth:
        status = "aguardando_autorizacao"
    else:
        status = "autorizado"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_solicitacoes
               (usuario_solicitante, arquivo_original, arquivo_servidor, caminho_arquivo,
                hash_arquivo, qtd_copias, tamanho_papel, cor, frente_verso, tipo_borda,
                papel_sulfite, tipo_papel, observacoes, secretaria_id, setor_id,
                qtd_paginas_arquivo, paginas_contabilizadas, status, cota_excedida,
                requer_autorizacao, data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
            (usuario, r["nome_original"], nome_servidor, destino, hash_arq,
             int(qtd_copias), tamanho_papel, cor, 1 if frente_verso else 0, tipo_borda,
             1 if papel_sulfite else 0, tipo_papel or "sulfite", observacoes,
             int(secretaria_id), setor_id, qtd_paginas, paginas_calc, status,
             cota_excedida, requer_auth),
        )
        sid = cur.lastrowid
        cur.execute("UPDATE tb_solicitacoes SET grupo_id = id WHERE id=?", (sid,))
        cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        conn.commit()
        _audit(ator, "criar_solicitacao",
               f"#{sid} {nome_servidor} | copias={qtd_copias} paginas_arq={qtd_paginas} "
               f"paginas_calc={paginas_calc} secr={secretaria_id} setor={setor_id} | {status}"
               + (" | EXCEDENTE" if excedente else ""),
               hash_arq)
        _log().info(f"solicitacao criada #{sid} por {usuario} | copias={qtd_copias} "
                    f"paginas_calc={paginas_calc} secr={secretaria_id} setor={setor_id} "
                    f"status={status}")
        msg = f"Solicitação #{sid} criada"
        if excedente:
            msg += " — ATENÇÃO: excedente de cota (sujeita à autorização)"
        elif requer_auth:
            msg += " — aguardando autorização"
        else:
            msg += " — autorizada, pronta para impressão"
        return True, msg, sid
    except Exception as e:
        _log().exception(f"falha ao confirmar rascunho: {e}")
        return False, f"Erro ao criar solicitação: {e}", None
    finally:
        conn.close()


# ================= AGRUPAMENTO (1 PEDIDO POR ENVIO) =================

def _proximo_grupo_id():
    """Returns the next available grupo_id (max+1) in tb_solicitacoes.

    Retorna o próximo grupo_id disponível (max+1) em tb_solicitacoes."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(grupo_id), 0) FROM tb_solicitacoes")
        return int(cur.fetchone()[0]) + 1
    finally:
        conn.close()


def confirmar_lote(usuario, rascunho_ids, qtd_copias, tamanho_papel, cor, frente_verso,
                   tipo_borda, papel_sulfite, observacoes, secretaria_id, setor_id,
                   ator="sistema", tipo_papel="sulfite"):
    """Converte vários rascunhos de UM envio em UM único pedido (grupo).

    Todos os arquivos recebem o mesmo `grupo_id` e compartilham o mesmo status
    (autorizado/recusado/impresso juntos). O nome de cada arquivo segue o padrão
    do projeto. Retorna (ok, msg, grupo_id)."""
    if not rascunho_ids:
        return False, "Nenhum arquivo para enviar", None
    if not secretaria_id:
        return False, "Secretaria é obrigatória", None

    # Limite de pedidos abertos (1 envio = 1 pedido, verifica uma vez)
    limite_ok, limite_msg = verificar_limite_pedidos(secretaria_id, setor_id)
    if not limite_ok:
        return False, limite_msg, None

    # Valida rascunhos existem e soma as páginas contabilizadas do grupo
    detalhes = []
    total_paginas_calc = 0
    for rid in rascunho_ids:
        r = obter_rascunho(rid)
        if not r:
            return False, f"Rascunho {rid} não encontrado (expirado?)", None
        if not os.path.exists(r["caminho_arquivo"]):
            return False, f"Arquivo do rascunho {rid} sumiu do servidor", None
        qtd_pag = r["qtd_paginas_arquivo"] or contar_paginas_pdf(r["caminho_arquivo"])
        calc = calcular_paginas_contabilizadas(qtd_pag, qtd_copias, tamanho_papel, frente_verso)
        detalhes.append((r, qtd_pag, calc))
        total_paginas_calc += calc

    # Excedente e autorização (status do grupo)
    excedente, _ = verificar_excedente(secretaria_id, setor_id, total_paginas_calc)
    cota_excedida = 1 if excedente else 0
    requer_auth = 1 if tem_responsavel_para(secretaria_id, setor_id) else 0
    if excedente:
        status = "excedente_cota"
    elif requer_auth:
        status = "aguardando_autorizacao"
    else:
        # Sem autorizador cadastrado -> fica PENDENTE (admin autoriza+imprime).
        status = "pendente"

    grupo_id = _proximo_grupo_id()
    agora = hora_servidor()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)

    conn = get_connection()
    try:
        cur = conn.cursor()
        for idx, (r, qtd_pag, calc) in enumerate(detalhes, start=1):
            nome_servidor = gerar_nome_arquivo(
                data_hora, usuario, qtd_copias, qtd_pag, secretaria_id, setor_id, cor,
                tipo_papel, ordem_envio=idx)
            destino = os.path.join(PASTA_SOLICITACOES, nome_servidor)
            import shutil
            shutil.move(r["caminho_arquivo"], destino)
            hash_arq = r["hash_arquivo"]
            cur.execute(
                """INSERT INTO tb_solicitacoes
                   (usuario_solicitante, arquivo_original, arquivo_servidor, caminho_arquivo,
                    hash_arquivo, qtd_copias, tamanho_papel, cor, frente_verso, tipo_borda,
                    papel_sulfite, tipo_papel, observacoes, secretaria_id, setor_id,
                    qtd_paginas_arquivo, paginas_contabilizadas, status, cota_excedida,
                    requer_autorizacao, grupo_id, data_atualizacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
                (usuario, r["nome_original"], nome_servidor, destino, hash_arq,
                 int(qtd_copias), tamanho_papel, cor, 1 if frente_verso else 0, tipo_borda,
                 1 if papel_sulfite else 0, tipo_papel or "sulfite", observacoes,
                 int(secretaria_id), setor_id, qtd_pag, calc, status, cota_excedida,
                 requer_auth, grupo_id),
            )
            cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (r["id"],))
        conn.commit()
    except Exception as e:
        conn.close()
        _log().exception("falha ao gravar grupo")
        return False, f"Erro ao criar pedido: {e}", None
    conn.close()

    # Auditoria do grupo (com SHA256 dos arquivos)
    hashes = ",".join((d[0].get("hash_arquivo") or "") for d in detalhes)
    _audit(ator, "criar_grupo",
           f"grupo #{grupo_id} | {len(detalhes)} arquivo(s) | paginas_calc={total_paginas_calc} "
           f"secr={secretaria_id} setor={setor_id} | {status} | sha256={hashes}", None)
    _log().info(f"pedido grupo #{grupo_id} por {usuario} | arquivos={len(detalhes)} "
                f"paginas_calc={total_paginas_calc} secr={secretaria_id} setor={setor_id} status={status}")

    msg = f"Pedido #{grupo_id} criado ({len(detalhes)} arquivo(s))"
    if excedente:
        msg += " — ATENÇÃO: excedente de cota (sujeito à autorização)"
    elif requer_auth:
        msg += " — aguardando autorização"
    else:
        msg += " — pendente de autorização"
    return True, msg, grupo_id


def listar_pedidos(usuario=None, status=None, secretaria_id=None, setor_id=None,
                   apenas_excedentes=False, limite=200, busca=None,
                   data_inicio=None, data_fim=None):
    """Lists PEDIDOS (one per group) with group metadata and file count.

    Lista os pedidos agrupados por `grupo_id` (1 pedido por envio), com
    metadados do grupo e nº de arquivos. Cada linha: (grupo_id, usuario,
    copias, papel, cor, fv, borda, sulf, obs, secretaria_id, setor_id, status,
    cota_exc, req_auth, aut_por, dt_aut, motivo, imp_por, dt_imp, data_criacao,
    sec_nome, sec_sig, st_nome, num_arquivos, paginas_calc_total,
    paginas_arquivo_total)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT s.grupo_id, s.usuario_solicitante, s.qtd_copias, s.tamanho_papel, "
               "s.cor, s.frente_verso, s.tipo_borda, s.papel_sulfite, s.tipo_papel, "
               "s.observacoes, "
               "s.secretaria_id, s.setor_id, s.status, s.cota_excedida, s.requer_autorizacao, "
               "s.autorizado_por, s.data_autorizacao, s.motivo_recusa, s.impresso_por, "
               "s.data_impressao, MIN(s.data_criacao) AS data_criacao, "
               "sec.nome, sec.sigla, st.nome, COUNT(*) AS num_arquivos, "
               "SUM(s.paginas_contabilizadas) AS paginas_calc_total, "
               "SUM(s.qtd_paginas_arquivo) AS paginas_arquivo_total "
               "FROM tb_solicitacoes s "
               "LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id "
               "LEFT JOIN tb_setores st ON st.id = s.setor_id "
               "WHERE 1=1 AND s.grupo_id IS NOT NULL")
        params = []
        if usuario:
            sql += " AND s.usuario_solicitante=?"
            params.append(usuario)
        if status:
            sql += " AND s.status=?"
            params.append(status)
        if secretaria_id is not None:
            sql += " AND s.secretaria_id=?"
            params.append(int(secretaria_id))
        if setor_id is not None:
            sql += " AND s.setor_id=?"
            params.append(setor_id)
        if apenas_excedentes:
            sql += " AND s.cota_excedida=1"
        if busca:
            like = f"%{busca.strip()}%"
            sql += (" AND (s.usuario_solicitante LIKE ? COLLATE NOCASE "
                    "OR s.observacoes LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_servidor LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_original LIKE ? COLLATE NOCASE "
                    "OR sec.nome LIKE ? COLLATE NOCASE "
                    "OR st.nome LIKE ? COLLATE NOCASE)")
            params += [like] * 6
        if data_inicio:
            sql += " AND date(s.data_criacao) >= ?"
            params.append(data_inicio)
        if data_fim:
            sql += " AND date(s.data_criacao) <= ?"
            params.append(data_fim)
        sql += " GROUP BY s.grupo_id ORDER BY MIN(s.data_criacao) DESC LIMIT ?"
        params.append(int(limite))
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def listar_arquivos_grupo(grupo_id):
    """Lists the files of one PEDIDO (group).

    Lista os arquivos de um pedido (grupo): (id, arquivo_servidor,
    arquivo_original, qtd_paginas_arquivo, paginas_contabilizadas,
    hash_arquivo, caminho_arquivo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, arquivo_servidor, arquivo_original, qtd_paginas_arquivo, "
            "paginas_contabilizadas, hash_arquivo, caminho_arquivo "
            "FROM tb_solicitacoes WHERE grupo_id=? ORDER BY id", (int(grupo_id),))
        return cur.fetchall()
    finally:
        conn.close()


def listar_pedidos_responsavel(user_nome, status=None, limite=200, busca=None,
                               data_inicio=None, data_fim=None):
    """Lists PEDIDOS of the secretarias/setores the user authorizes.

    Lista os pedidos das secretarias/setores onde o usuário é responsável.
    Um responsável vinculado à secretaria inteira (setor_id NULL) vê todos os
    pedidos da secretaria; vinculado a um setor, só os daquele setor."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT secretaria_id, setor_id FROM tb_responsaveis_autorizacao "
            "WHERE user_nome=? AND ativo=1", (user_nome,))
        vinculos = cur.fetchall()
        if not vinculos:
            return []
        cond = []
        params = []
        for secr, setor in vinculos:
            if setor:
                cond.append("(s.secretaria_id=? AND s.setor_id=?)")
                params += [int(secr), int(setor)]
            else:
                cond.append("(s.secretaria_id=?)")
                params.append(int(secr))
        where_escopo = "(" + " OR ".join(cond) + ")"
        sql = ("SELECT s.grupo_id, s.usuario_solicitante, s.qtd_copias, s.tamanho_papel, "
               "s.cor, s.frente_verso, s.tipo_borda, s.papel_sulfite, s.tipo_papel, "
               "s.observacoes, "
               "s.secretaria_id, s.setor_id, s.status, s.cota_excedida, s.requer_autorizacao, "
               "s.autorizado_por, s.data_autorizacao, s.motivo_recusa, s.impresso_por, "
               "s.data_impressao, MIN(s.data_criacao) AS data_criacao, "
               "sec.nome, sec.sigla, st.nome, COUNT(*) AS num_arquivos, "
               "SUM(s.paginas_contabilizadas) AS paginas_calc_total, "
               "SUM(s.qtd_paginas_arquivo) AS paginas_arquivo_total "
               "FROM tb_solicitacoes s "
               "LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id "
               "LEFT JOIN tb_setores st ON st.id = s.setor_id "
               f"WHERE 1=1 AND s.grupo_id IS NOT NULL AND {where_escopo}")
        if status:
            sql += " AND s.status=?"
            params.append(status)
        if busca:
            like = f"%{busca.strip()}%"
            sql += (" AND (s.usuario_solicitante LIKE ? COLLATE NOCASE "
                    "OR s.observacoes LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_servidor LIKE ? COLLATE NOCASE "
                    "OR s.arquivo_original LIKE ? COLLATE NOCASE)")
            params += [like] * 4
        if data_inicio:
            sql += " AND date(s.data_criacao) >= ?"; params.append(data_inicio)
        if data_fim:
            sql += " AND date(s.data_criacao) <= ?"; params.append(data_fim)
        sql += " GROUP BY s.grupo_id ORDER BY MIN(s.data_criacao) DESC LIMIT ?"
        params.append(int(limite))
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _atualizar_status_grupo(grupo_id, status, campos=None, cond_status=None):
    """Updates the status (and optional fields) of ALL files in a group.

    Atualiza o status (e campos opcionais) de TODOS os arquivos do grupo,
    com commit. `cond_status` restringe os status de origem aceitos. O valor
    especial `"datetime('now','localtime')"` nos campos é injetado como expressão SQL
    (avaliada pelo banco), não como string literal."""
    sets = ["status=?"]
    params = [status]
    for col, val in (campos or {}).items():
        if val == "datetime('now','localtime')":
            sets.append(f"{col}=datetime('now','localtime')")
        else:
            sets.append(f"{col}=?")
            params.append(val)
    sql = f"UPDATE tb_solicitacoes SET {', '.join(sets)}, data_atualizacao=datetime('now','localtime') "
    sql += "WHERE grupo_id=?"
    params.append(int(grupo_id))
    if cond_status:
        sql += f" AND status IN ({','.join('?' * len(cond_status))})"
        params += list(cond_status)
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            ok = cur.rowcount > 0
            conn.commit()
            return ok
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"falha ao atualizar status do grupo #{grupo_id}: {e}")
        return False


def autorizar_grupo(grupo_id, autor, motivo=None):
    """Authorizes ALL files of a PEDIDO (aguardando/excedente/pendente).

    Autoriza todos os arquivos de um pedido (grupo) em conjunto, registrando
    o autorizador e a data. Retorna (ok, msg)."""
    if not _atualizar_status_grupo(
            grupo_id, "autorizado",
            campos={"autorizado_por": autor, "data_autorizacao": "datetime('now','localtime')"},
            cond_status=("aguardando_autorizacao", "excedente_cota", "pendente")):
        return False, "Pedido não autorizável neste estado"
    _audit(autor, "autorizar_grupo", f"grupo #{grupo_id}", None)
    return True, f"Pedido #{grupo_id} autorizado"


def recusar_grupo(grupo_id, autor, motivo):
    """Refuses ALL files of a PEDIDO (mandatory reason) and removes the files.

    Recusa todos os arquivos de um pedido (grupo) em conjunto, exigindo motivo
    obrigatório, e remove os arquivos do servidor. Retorna (ok, msg)."""
    if not (motivo or "").strip():
        return False, "Motivo da recusa é obrigatório"
    if not _atualizar_status_grupo(
            grupo_id, "recusado",
            campos={"motivo_recusa": motivo.strip(), "autorizado_por": autor,
                    "data_autorizacao": "datetime('now','localtime')"},
            cond_status=("aguardando_autorizacao", "excedente_cota", "pendente", "autorizado")):
        return False, "Pedido não recusável"
    for (fid, *_ ) in listar_arquivos_grupo(grupo_id):
        _remover_arquivo_solicitacao(fid)
    _audit(autor, "recusar_grupo", f"grupo #{grupo_id} motivo={motivo}", None)
    return True, "Pedido recusado"


def imprimir_grupo(grupo_id, admin_user, ator="sistema"):
    """Marks ALL files as printed, deducts the quota and DELETES the files from
    the server immediately (the printed pedido leaves the admin's active view).

    Marca todos os arquivos como impresso, desconta a cota e apaga os arquivos
    do servidor imediatamente (o pedido impresso sai da gestão ativa do admin).
    A cota é descontada pelo total de páginas contabilizadas do grupo, tanto na
    secretaria quanto no setor (se houver). Retorna (ok, msg)."""
    arquivos = listar_arquivos_grupo(grupo_id)
    if not arquivos:
        return False, "Pedido não encontrado"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT status, secretaria_id, setor_id FROM tb_solicitacoes "
            "WHERE grupo_id=?", (int(grupo_id),))
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return False, "Pedido não encontrado"
    status_atual = rows[0][0]
    if status_atual not in ("autorizado", "pendente", "excedente_cota"):
        return False, f"Status '{status_atual}' não permite impressão (é necessário autorizar antes)"
    secr = rows[0][1]
    setor = rows[0][2]
    paginas_total = sum(a[4] for a in arquivos)  # paginas_contabilizadas

    # Desconta cota (secretaria sempre; setor se houver)
    if secr:
        _incrementar_consumo(secr, 0, paginas_total)
        if setor:
            _incrementar_consumo(secr, setor, paginas_total)

    _atualizar_status_grupo(grupo_id, "impresso",
                            campos={"impresso_por": admin_user,
                                    "data_impressao": "datetime('now','localtime')",
                                    "excluir_arquivo_em": "datetime('now','localtime')"})
    # Apaga os arquivos do servidor imediatamente
    removidos = 0
    for (fid, *_ ) in arquivos:
        if _remover_arquivo_solicitacao(fid):
            removidos += 1
    _audit(ator, "imprimir_grupo",
           f"grupo #{grupo_id} paginas={paginas_total} arquivos_removidos={removidos}", None)
    _log().info(f"impressao grupo #{grupo_id} por {admin_user} | paginas={paginas_total} "
                f"arquivos_removidos={removidos}")
    return True, f"Pedido #{grupo_id} marcado como impresso (arquivos removidos)"


def recuar_grupo(grupo_id, ator="sistema"):
    """Cancels ALL files of a PEDIDO (status=cancelado) and removes the files.

    Cancela todos os arquivos de um pedido (grupo) em conjunto e remove os
    arquivos do servidor. Retorna (ok, msg)."""
    if not _atualizar_status_grupo(
            grupo_id, "cancelado",
            cond_status=("autorizado", "pendente", "excedente_cota", "impresso", "aguardando_autorizacao")):
        return False, "Pedido não cancelável"
    for (fid, *_ ) in listar_arquivos_grupo(grupo_id):
        _remover_arquivo_solicitacao(fid)
    _audit(ator, "recuar_grupo", f"grupo #{grupo_id}", None)
    return True, "Pedido cancelado"


def cancelar_grupo(grupo_id, usuario, ator="sistema"):
    """User cancels their own PEDIDO if still pendente/aguardando/excedente.

    Usuário cancela seu próprio pedido (grupo) se ainda pendente/aguardando/
    excedente ou recusado, removendo os arquivos do servidor. Retorna (ok, msg)."""
    ok = False
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE tb_solicitacoes SET status='cancelado', data_atualizacao=datetime('now','localtime') "
                "WHERE grupo_id=? AND usuario_solicitante=? AND status IN "
                "('pendente', 'aguardando_autorizacao', 'excedente_cota', 'recusado')",
                (int(grupo_id), usuario))
            ok = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"falha ao cancelar pedido #{grupo_id}: {e}")
        return False, "Não cancelável pelo usuário"
    if ok:
        for (fid, *_ ) in listar_arquivos_grupo(grupo_id):
            _remover_arquivo_solicitacao(fid)
        _audit(ator, "cancelar_grupo", f"grupo #{grupo_id}", None)
    return ok, "Pedido cancelado" if ok else "Não cancelável pelo usuário"


def reenviar_grupo(grupo_id, usuario, ator="sistema"):
    """Re-opens a refused PEDIDO for a new authorization round (own request).

    Usuário reenvia o próprio pedido recusado: o status volta para
    `aguardando_autorizacao` (se há responsável) ou `pendente`, limpando o
    motivo da recusa e os dados de autorização. Retorna (ok, msg)."""
    ok = False
    novo_status = "pendente"
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT secretaria_id, setor_id FROM tb_solicitacoes "
                "WHERE grupo_id=? AND usuario_solicitante=? AND status='recusado' LIMIT 1",
                (int(grupo_id), usuario))
            row = cur.fetchone()
            if not row:
                return False, "Pedido não pode ser reenviado (não está recusado ou não é seu)"
            secr, setor = row
            requer_auth = 1 if tem_responsavel_para(secr, setor) else 0
            novo_status = "aguardando_autorizacao" if requer_auth else "pendente"
            cur.execute(
                "UPDATE tb_solicitacoes SET status=?, motivo_recusa=NULL, autorizado_por=NULL, "
                "data_autorizacao=NULL, cota_excedida=0, data_atualizacao=datetime('now','localtime') "
                "WHERE grupo_id=? AND usuario_solicitante=? AND status='recusado'",
                (novo_status, int(grupo_id), usuario))
            ok = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        _log().exception(f"falha ao reenviar pedido #{grupo_id}: {e}")
        return False, "Não foi possível reenviar"
    if ok:
        _audit(ator, "reenviar_grupo", f"grupo #{grupo_id} -> {novo_status}", None)
    return ok, ("Pedido reenviado para autorização" if ok else "Não foi possível reenviar")


def expirar_rascunhos_e_impressos():
    """Scheduled cleanup (every 1 min):
    - drafts whose expira_em has passed -> remove file + record;
    - printed requests whose excluir_arquivo_em has passed -> remove server file.

    Limpeza agendada (a cada 1 min):
    - rascunhos cujo expira_em passou -> remove arquivo + registro;
    - solicitações impressas cujo excluir_arquivo_em passou -> remove arquivo do servidor.
    A comparação usa a hora do servidor (`hora_servidor_str`)."""
    agora = hora_servidor_str("%Y-%m-%d %H:%M:%S")
    removidos = 0
    # Rascunhos expirados
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, caminho_arquivo, nome_servidor FROM tb_rascunhos_upload "
                    "WHERE expira_em < ?", (agora,))
        for rid, caminho, nome in cur.fetchall():
            _remover_arquivo_se_existir(caminho)
            cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rid,))
            removidos += 1
            _audit("sistema", "rascunho_expirado",
                   f"#{rid} {nome} removido automaticamente (não confirmado)", None)
        # Arquivos de solicitações impressas vencidos
        cur.execute("SELECT id, caminho_arquivo FROM tb_solicitacoes "
                    "WHERE status='impresso' AND excluir_arquivo_em IS NOT NULL "
                    "AND excluir_arquivo_em < ?", (agora,))
        for sid, caminho in cur.fetchall():
            if _remover_arquivo_se_existir(caminho):
                removidos += 1
            cur.execute("UPDATE tb_solicitacoes SET excluir_arquivo_em=NULL "
                        "WHERE id=?", (sid,))
            _audit("sistema", "arquivo_impresso_excluido",
                   f"#{sid} arquivo removido após prazo de retenção", None)
        conn.commit()
    finally:
        conn.close()
    if removidos:
        _log().info(f"limpeza de rascunhos/impressos: {removidos} arquivo(s) removido(s)")
    return removidos


def solicitar_solicitacoes_responsavel(user_nome, limite=200):
    """Retorna solicitações pendentes das secretarias/setores onde o user é responsável.

    Escopo: um responsável vinculado à secretaria inteira (setor_id IS NULL) vê
    todas as solicitações da secretaria; um responsável vinculado a um setor vê
    apenas as daquele setor (não sobre-expoe outros setores)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT secretaria_id, setor_id FROM tb_responsaveis_autorizacao "
            "WHERE user_nome = ? AND ativo = 1",
            (user_nome,),
        )
        vinculos = cur.fetchall()
        if not vinculos:
            return []
        vistos = set()
        resultados = []
        for secr, setor in vinculos:
            for row in listar_solicitacoes(
                    secretaria_id=secr, setor_id=setor,
                    status="aguardando_autorizacao", limite=limite):
                if row[0] not in vistos:
                    resultados.append(row)
                    vistos.add(row[0])
            for row in listar_solicitacoes(
                    secretaria_id=secr, setor_id=setor,
                    status="excedente_cota", limite=limite):
                if row[0] not in vistos:
                    resultados.append(row)
                    vistos.add(row[0])
        return resultados
    finally:
        conn.close()


# ================= RELATÓRIO DE COTAS =================

def relatorio_cotas(mes=None):
    """Retorna lista de (secretaria_id, secretaria_nome, setor_id, setor_nome,
    cota, usado, percentual) para todas as secretarias/setores ativas."""
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, sigla, cota_paginas_mensal FROM tb_secretarias WHERE ativo=1"
        )
        secrs = cur.fetchall()
        rel = []
        for sid, nome, sigla, cota_secr in secrs:
            cota, _ = obter_ou_criar_cota(sid, 0, mes)
            usado = obter_consumo(sid, 0, mes)
            pct = round((usado / cota) * 100, 1) if cota > 0 else 0
            rel.append((sid, nome, None, "—", cota, usado, pct))
            # Setores
            cur.execute(
                "SELECT id, nome, cota_paginas_mensal FROM tb_setores "
                "WHERE secretaria_id=? AND ativo=1", (sid,))
            for stid, stnome, cota_st in cur.fetchall():
                c, _ = obter_ou_criar_cota(sid, stid, mes)
                u = obter_consumo(sid, stid, mes)
                p = round((u / c) * 100, 1) if c > 0 else 0
                rel.append((sid, nome, stid, stnome, c, u, p))
        return rel
    finally:
        conn.close()


# ================= RELATÓRIO DE IMPRESSÃO =================

def _agregar_impressao(data_inicio, data_fim, agrupar_por):
    """Runs a print aggregation (status='impresso') over a period.

    `agrupar_por`: coluna SQL para GROUP BY (ex.: 's.secretaria_id'), ou None
    para total geral. Retorna lista de tuplas:
      (rótulo, num_pedidos, copias_total, copias_color, copias_pb,
       paginas_total, paginas_color, paginas_pb).
    Filtra por `data_impressao` no intervalo e separa color/PB pela coluna `cor`."""
    join = ""
    if agrupar_por in ("s.secretaria_id", "s.setor_id", "sec.nome"):
        join = "LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id"
    grupo = f"GROUP BY {agrupar_por}" if agrupar_por else ""
    rotulo = (agrupar_por if agrupar_por else "'TOTAL'")
    sql = f"""
        SELECT {rotulo},
               COUNT(DISTINCT s.grupo_id) AS num_pedidos,
               COALESCE(SUM(s.qtd_copias), 0) AS copias_total,
               COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN s.qtd_copias ELSE 0 END), 0) AS copias_color,
               COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN 0 ELSE s.qtd_copias END), 0) AS copias_pb,
               COALESCE(SUM(s.paginas_contabilizadas), 0) AS paginas_total,
               COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN s.paginas_contabilizadas ELSE 0 END), 0) AS paginas_color,
               COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN 0 ELSE s.paginas_contabilizadas END), 0) AS paginas_pb
        FROM tb_solicitacoes s
        {join}
        WHERE s.status = 'impresso'
          AND s.data_impressao IS NOT NULL
    """
    params = []
    if data_inicio:
        sql += " AND date(s.data_impressao) >= ?"
        params.append(data_inicio)
    if data_fim:
        sql += " AND date(s.data_impressao) <= ?"
        params.append(data_fim)
    sql += f" {grupo} ORDER BY copias_total DESC"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def relatorio_impressao(data_inicio=None, data_fim=None):
    """Builds the print report (status='impresso') for a period.

    Dicionário com totais prontos para o administrador:
      - 'geral': tupla (num_pedidos, copias_total, copias_color, copias_pb,
        paginas_total, paginas_color, paginas_pb)
      - 'por_secretaria': lista de (secretaria_nome, ...) mesmos campos
      - 'por_setor': lista de (secretaria_nome, setor_nome, ...)
      - 'por_autorizador': lista de (autorizado_por, ...)
      - 'por_impressor': lista de (impresso_por, ...)
    `data_inicio`/`data_fim` em 'YYYY-MM-DD' filtram por `data_impressao`."""
    geral = _agregar_impressao(data_inicio, data_fim, None)
    total = geral[0] if geral else (0, 0, 0, 0, 0, 0, 0)
    linhas = total[1:]  # (num_pedidos, copias_total, copias_color, copias_pb, paginas_total, paginas_color, paginas_pb)

    def _por_secretaria():
        rows = _agregar_impressao(data_inicio, data_fim, "sec.nome")
        return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows]

    def _por_setor():
        sql = """
            SELECT COALESCE(sec.nome, '—'), COALESCE(st.nome, '—'),
                   COUNT(DISTINCT s.grupo_id),
                   COALESCE(SUM(s.qtd_copias), 0),
                   COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN s.qtd_copias ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN 0 ELSE s.qtd_copias END), 0),
                   COALESCE(SUM(s.paginas_contabilizadas), 0),
                   COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN s.paginas_contabilizadas ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN s.cor LIKE 'Col%' THEN 0 ELSE s.paginas_contabilizadas END), 0)
            FROM tb_solicitacoes s
            LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id
            LEFT JOIN tb_setores st ON st.id = s.setor_id
            WHERE s.status = 'impresso' AND s.data_impressao IS NOT NULL
        """
        params = []
        if data_inicio:
            sql += " AND date(s.data_impressao) >= ?"; params.append(data_inicio)
        if data_fim:
            sql += " AND date(s.data_impressao) <= ?"; params.append(data_fim)
        sql += " GROUP BY sec.nome, st.nome ORDER BY 5 DESC"
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()

    def _por_autorizador():
        rows = _agregar_impressao(data_inicio, data_fim, "s.autorizado_por")
        return [(r[0] or '—', r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows]

    def _por_impressor():
        rows = _agregar_impressao(data_inicio, data_fim, "s.impresso_por")
        return [(r[0] or '—', r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows]

    return {
        "geral": linhas,
        "por_secretaria": _por_secretaria(),
        "por_setor": _por_setor(),
        "por_autorizador": _por_autorizador(),
        "por_impressor": _por_impressor(),
    }


# ================= MARCAS D'ÁGUA (PDF) =================

def aplicar_marca_dagua(caminho_pdf, solicitacao_id, usuario, secretaria_nome,
                        setor_nome, solicitante):
    """Generates a new PDF (copy) with a watermark if active. Returns the final PDF path.

    Gera um novo PDF (cópia) com marca d'água se ativa. Retorna caminho do PDF final.
    A data do texto usa a hora do servidor (`hora_servidor_str`). Falha na geração
    devolve o PDF original (fail-soft)."""
    if obter_config("marca_dagua_ativa", "1") != "1":
        return caminho_pdf  # sem marca d'água
    try:
        import pymupdf as fitz
        ativa = obter_config("marca_dagua_ativa", "1") == "1"
        if not ativa:
            return caminho_pdf
        texto = obter_config("marca_dagua_texto",
                             "IMPRESSO EM {data} POR {usuario} - SOLIC. #{id} - {secretaria}/{setor}")
        pos = obter_config("marca_dagua_posicao", "centro")
        opac = int(obter_config("marca_dagua_opacidade", "30")) / 100.0
        fs = int(obter_config("marca_dagua_fonte_tamanho", "24"))
        cor = obter_config("marca_dagua_cor", "#CCCCCC")
        rot = int(obter_config("marca_dagua_rotacao", "45"))
        if rot not in (0, 90, 180, 270):
            rot = 0  # PyMuPDF só aceita múltiplos de 90°
        agora = hora_servidor_str("%d/%m/%Y %H:%M")
        texto = (texto.replace("{data}", agora).replace("{usuario}", usuario or "")
                 .replace("{id}", str(solicitacao_id)).replace("{secretaria}", secretaria_nome or "")
                 .replace("{setor}", setor_nome or "—").replace("{solicitante}", solicitante or "")
                 .replace("{copias}", "").replace("{paginas}", ""))

        doc = fitz.open(caminho_pdf)
        try:
            rgb = fitz.utils.hex_to_rgb(cor)
        except Exception:
            rgb = (0.8, 0.8, 0.8)
        for page in doc:
            w, h = page.rect.width, page.rect.height
            if pos == "centro":
                x, y = w / 2, h / 2
            elif pos == "rodape":
                x, y = w / 2, h - 40
            elif pos == "canto_superior":
                x, y = 60, 40
            else:  # canto_inferior
                x, y = 60, h - 40
            page.insert_text(
                (x, y), texto,
                fontsize=fs, color=rgb, fill_opacity=opac,
                rotate=rot,
            )
        saida = caminho_pdf.replace(".pdf", f"_wm_{solicitacao_id}.pdf")
        doc.save(saida)
        doc.close()
        return saida
    except Exception as e:
        print(f"Marca d'água falhou: {e}")
        return caminho_pdf


# Inicialização ao importar
init_db()
