"""EN: Technical module — own DB, files and backups (db_mod_tecnico.db, WAL).

PT-BR: Módulo Técnico — BD próprio, arquivos e backups.
Acesso ao db_mod_tecnico.db (WAL) e regras de negócio.
Pastas físicas dentro do módulo:
  software/ → executáveis disponibilizados (download)
  backup/   → pastas YYYYMMDD_HHMM_nomePc_ip por técnico/PC (isolamento por owner)

Isolamento total: cada módulo limpa o próprio banco via API pública.
"""

import os
import sys
import re
import time
import sqlite3
import hashlib
import shutil
import zipfile
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_tecnico")
PASTA_SOFTWARE = os.path.join(MOD_DIR, "software")
PASTA_BACKUP = os.path.join(MOD_DIR, "backup")
DB_TECNICO_PATH = os.path.join(BASE_DIR, "db_mod_tecnico.db")


def _log():
    """EN: Technical scoped logger (observabilidade.get_logger('tecnico')).

    PT-BR: Logger escopado do técnico (observabilidade.get_logger('tecnico')).
    """
    from mod_intranet import observabilidade
    return observabilidade.get_logger("tecnico")


def get_connection():
    """EN: Open module connection (WAL) via banco_conexao.conexao('tecnico').

    PT-BR: Abre conexão do módulo (WAL) via banco_conexao.conexao('tecnico').
    """
    from mod_intranet.banco_conexao import conexao
    conn = conexao("tecnico")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão mod_tecnico")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception as e:
        try:
            _log().warning(f"get_connection PRAGMA falhou (ignorado): {e}")
        except Exception:
            pass
    return conn


def _audit(ator, acao, alvo, detalhe=""):
    """EN: Forward technical event to central audit_log (tb_auditoria_tecnico).

    PT-BR: Encaminha evento do técnico ao audit_log central (tb_auditoria_tecnico).
    """
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", "tecnico", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception as e:
        try:
            _log().warning(f"_audit falhou ({acao}/{alvo}): {e}")
        except Exception:
            pass


def _sanitizar_nome(nome: str) -> str:
    """EN: Sanitize nomePc/ip for folder use (only [a-zA-Z0-9_-]).

    PT-BR: Sanitiza nomePc/ip para uso em pasta (só [a-zA-Z0-9_-]).
    """
    try:
        base = re.sub(r"[^a-zA-Z0-9_-]", "_", (nome or "").strip() or "pc")
        base = re.sub(r"_+", "_", base).strip("_")
        return base[:40] or "pc"
    except Exception:
        return "pc"


def _hash_sha256(caminho: str) -> str:
    """EN: Compute SHA-256 of a file path (empty string on failure).

    PT-BR: Calcula SHA-256 de um caminho de arquivo (string vazia em falha).
    """
    try:
        h = hashlib.sha256()
        with open(caminho, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _obter_config_tecnico(chave: str, padrao: str = "") -> str:
    """EN: Unified config read — central get_config is source, local tb_config_tecnico fallback.

    PT-BR: Leitura unificada de config — central get_config é a FONTE;
    tb_config_tecnico local é apenas fallback/legado.

    Motivo (dual): tb_config_tecnico nasceu como seed local, mas o painel
    /admin/tecnico e criar_zip_selecionados usam o central
    get_config/set_config (tecnico_max_zip_mb). Para não divergir,
    SEMPRE ler primeiro o central; só se vazio/erro, ler o local.
    Escrita continua no central (set_config) — ver telas_administracao.
    """
    try:
        from mod_intranet.bd_conexao import get_config
        valor = get_config(chave, None)
        if valor is not None and str(valor).strip() != "":
            return str(valor)
    except Exception as e:
        try:
            _log().warning(f"_obter_config_tecnico central falhou ({chave}): {e}")
        except Exception:
            pass
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT valor FROM tb_config_tecnico WHERE chave=?", (chave,))
            row = cur.fetchone()
            if row and row[0] not in (None, ""):
                return str(row[0])
        finally:
            conn.close()
    except Exception as e:
        try:
            _log().warning(f"_obter_config_tecnico fallback local falhou ({chave}): {e}")
        except Exception:
            pass
    return padrao


def _obter_max_zip_mb() -> int:
    """EN: Central tecnico_max_zip_mb (fallback 1024).

    PT-BR: Retorna tecnico_max_zip_mb da fonte central (fallback 1024).
    """
    try:
        raw = _obter_config_tecnico("tecnico_max_zip_mb", "1024")
        return int(str(raw or "1024").strip() or 1024)
    except Exception:
        return 1024


def init_db():
    """EN: Create/migrate technical schema (idempotent, import-safe).

    PT-BR: Cria/migra schema do técnico (idempotente, seguro no import).

    Chamado no import (:528) — NUNCA pode derrubar o import: todo erro é
    logado e engolido. DDL com IF NOT EXISTS + INSERT OR IGNORE (SQLite)
    traduzido pelo proxy para Postgres. makedirs com exist_ok=True.
    Config: seed local tb_config_tecnico apenas como fallback; fonte real
    é o central get_config (ver _obter_config_tecnico).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pasta_nome TEXT NOT NULL UNIQUE,
                owner TEXT NOT NULL,
                ip TEXT,
                hostname TEXT,
                tamanho_total INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'criado',
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_backup_arquivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_id INTEGER NOT NULL REFERENCES tb_backup(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                caminho_relativo TEXT NOT NULL,
                tamanho INTEGER NOT NULL DEFAULT 0,
                hash_sha256 TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_config_tecnico (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
        for k, v in (
            ("tecnico_pasta_software", PASTA_SOFTWARE),
            ("tecnico_pasta_backup", PASTA_BACKUP),
            ("tecnico_max_zip_mb", "1024"),
            ("tecnico_quota_gb", "10"),
        ):
            try:
                cur.execute("INSERT OR IGNORE INTO tb_config_tecnico (chave, valor) VALUES (?, ?)", (k, v))
            except Exception as e:
                # PG traduz INSERT OR IGNORE; se falhar, tenta fallback portável
                try:
                    _log().warning(f"init_db seed {k} falhou, tentando fallback: {e}")
                    cur.execute("SELECT valor FROM tb_config_tecnico WHERE chave=?", (k,))
                    if cur.fetchone() is None:
                        cur.execute("INSERT INTO tb_config_tecnico (chave, valor) VALUES (?, ?)", (k, v))
                except Exception:
                    pass
        conn.commit()
    except Exception as e:
        try:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            _log().exception(f"init_db falhou (import-safe, ignorado): {e}")
        except Exception:
            pass
        return
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
    for p in (PASTA_SOFTWARE, PASTA_BACKUP):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            try:
                _log().warning(f"init_db makedirs falhou {p}: {e}")
            except Exception:
                pass


# ============ SOFTWARE ============

def listar_software(relativo: str = ""):
    """EN: Recursive listing of files/folders in software/ (relative to software/).

    PT-BR: Lista recursiva de arquivos/pastas em software/ (relativo ao software/).

    Blindagem path traversal: relativo nunca escapa de PASTA_SOFTWARE
    (AGENTS.md §1 — todo artefato dentro de mod_tecnico/).
    """
    # Sanitiza relativo: impede traversal fora da base
    if relativo and (".." in relativo or relativo.startswith("/") or "\x00" in relativo):
        return []
    base = os.path.join(PASTA_SOFTWARE, relativo) if relativo else PASTA_SOFTWARE
    # Confirma que base permanece dentro de PASTA_SOFTWARE (canônico)
    try:
        if os.path.commonpath([os.path.abspath(base), os.path.abspath(PASTA_SOFTWARE)]) != os.path.abspath(PASTA_SOFTWARE):
            return []
    except Exception:
        return []
    if not os.path.isdir(base):
        return []
    itens = []
    try:
        for nome in sorted(os.listdir(base), reverse=True):
            if nome == ".gitkeep":
                continue
            caminho = os.path.join(base, nome)
            rel = os.path.join(relativo, nome) if relativo else nome
            eh_dir = os.path.isdir(caminho)
            tamanho = 0
            if not eh_dir:
                try:
                    tamanho = os.path.getsize(caminho)
                except Exception:
                    tamanho = 0
            itens.append({
                "nome": nome,
                "relativo": rel.replace(os.sep, "/"),
                "eh_dir": eh_dir,
                "tamanho": tamanho,
                "caminho_abs": caminho,
            })
    except Exception as e:
        _log().warning(f"listar_software falhou em {relativo}: {e}")
    return itens


def listar_software_recursivo():
    """EN: List all leaf files in software/ recursively (ignore .gitkeep).

    PT-BR: Lista todos os arquivos (folhas) em software/ recursivamente (ignora .gitkeep).
    """
    try:
        arquivos = []
        for root, dirs, files in os.walk(PASTA_SOFTWARE):
            for f in files:
                if f == ".gitkeep":
                    continue
                abs_path = os.path.join(root, f)
                rel = os.path.relpath(abs_path, PASTA_SOFTWARE).replace(os.sep, "/")
                arquivos.append(rel)
        return sorted(arquivos)
    except Exception as e:
        try:
            _log().warning(f"listar_software_recursivo falhou: {e}")
        except Exception:
            pass
        return []


def criar_zip_selecionados(relativos: list[str], owner: str = "") -> str:
    """EN: Create temporary zip with selected files/folders (relative to software/).

    PT-BR: Cria zip temporário com arquivos/pastas selecionados (relativos a software/).

    Blindagem path traversal: verifica commonpath para cada abs_path.
    """
    if not relativos:
        raise ValueError("Nenhum item selecionado")
    # Limite de tamanho — fonte central (ver _obter_config_tecnico)
    max_mb = _obter_max_zip_mb()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    try:
        total = 0
        base_abs = os.path.abspath(PASTA_SOFTWARE)
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in relativos:
                # Rejeita traversal explícito
                if ".." in rel or rel.startswith("/") or "\x00" in rel:
                    continue
                rel_norm = rel.replace("/", os.sep)
                abs_path = os.path.join(PASTA_SOFTWARE, rel_norm)
                # Garante que abs_path está dentro da base (canônico, sem symlink escape)
                try:
                    if os.path.commonpath([os.path.abspath(abs_path), base_abs]) != base_abs:
                        continue
                except Exception:
                    continue
                if os.path.isdir(abs_path):
                    for root, _, files in os.walk(abs_path):
                        for f in files:
                            f_abs = os.path.join(root, f)
                            # Dobra de verificação: f_abs também dentro da base
                            try:
                                if os.path.commonpath([os.path.abspath(f_abs), base_abs]) != base_abs:
                                    continue
                            except Exception:
                                continue
                            arc = os.path.relpath(f_abs, PASTA_SOFTWARE).replace(os.sep, "/")
                            # segurança: não sair de software/
                            if ".." in arc or arc.startswith("/"):
                                continue
                            zf.write(f_abs, arcname=arc)
                            try:
                                total += os.path.getsize(f_abs)
                            except Exception:
                                pass
                elif os.path.isfile(abs_path):
                    arc = rel.replace(os.sep, "/")
                    if ".." in arc or arc.startswith("/"):
                        continue
                    zf.write(abs_path, arcname=arc)
                    try:
                        total += os.path.getsize(abs_path)
                    except Exception:
                        pass
                if total > max_mb * 1024 * 1024:
                    raise ValueError(f"Seleção excede limite de {max_mb} MB")
        try:
            _audit(owner or "sistema", "download_software", ",".join(relativos[:3]), f"total={total} bytes zip={tmp.name}")
        except Exception as e:
            _log().warning(f"criar_zip_selecionados audit falhou: {e}")
        return tmp.name
    except Exception as e:
        try:
            try:
                os.remove(tmp.name)
            except Exception:
                pass
            _log().exception(f"criar_zip_selecionados falhou: {e}")
        except Exception:
            pass
        raise


# ============ BACKUP ============

def nome_pasta_backup(nome_pc: str, ip: str) -> str:
    """EN: Generate default YYYYMMDD_HHMM_pc_ip_SS folder name (seconds suffix).

    PT-BR: Gera nome padrão YYYYMMDD_HHMM_nomePc_ip_SS (sufixo de segundos).

    Por que o sufixo _SS: o formato antigo YYYYMMDD_HHMM colidia quando duas
    pastas eram criadas no mesmo minuto (mesmo PC/IP). O sufixo de segundos
    (_SS, 00-59) elimina a colisão sem quebrar o prefixo YYYYMMDD_HHMM_
    (compatível com regex antiga ^[0-9]{8}_[0-9]{4}_... e com ordenação).
    Ex.: 20260918_1430_NOTE07_192_168_1_10_45
    """

    # Gera nome com sufixo de segundos para evitar colisão no mesmo minuto.
    try:
        agora = datetime.now()
        data = agora.strftime("%Y%m%d_%H%M")
        seg = agora.strftime("%S")
        pc = _sanitizar_nome(nome_pc)
        # ip sanitizado perde pontos, então tratamos separado: manter . como _
        ip_s = re.sub(r"[^a-zA-Z0-9._-]", "_", (ip or "sem_ip").strip() or "sem_ip")
        ip_s = _sanitizar_nome(ip_s.replace(".", "_"))
        return f"{data}_{pc}_{ip_s}_{seg}"
    except Exception as e:
        try:
            _log().exception(f"nome_pasta_backup falhou: {e}")
        except Exception:
            pass
        data = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{data}_pc_sem_ip_00"


def criar_pasta_backup(owner: str, nome_pc: str, ip: str) -> tuple[bool, str]:
    """EN: Create auto-named backup folder. Returns (ok, folder_name|message).

    PT-BR: Cria pasta de backup nomeada automaticamente. Retorna (ok, pasta_nome|msg).

    Nome YYYYMMDD_HHMM_pc_ip_SS (ver nome_pasta_backup): sufixo de segundos
    evita colisão no mesmo minuto. Se FS ou DB já tiver o nome (condição de
    corrida ou retry), NEGA com mensagem clara pedindo nova tentativa em
    alguns segundos — nunca sobrescreve pasta alheia.
    """
    try:
        if not owner:
            return False, "Usuário não identificado"
        pc = (nome_pc or "").strip()
        ip_v = (ip or "").strip()
        if len(pc) < 2:
            return False, "Informe o nome do PC (mín. 2 caracteres)"
        if len(ip_v) < 3:
            return False, "Informe o IP do PC (mín. 3 caracteres)"
        pasta_nome = nome_pasta_backup(pc, ip_v)
        caminho = _pasta_backup_path(pasta_nome)
        if os.path.exists(caminho):
            _log().warning(f"criar_pasta_backup duplicada FS: {pasta_nome} por {owner}")
            return False, f"Pasta já existe: {pasta_nome} — aguarde alguns segundos e tente novamente (nome inclui segundos para evitar colisão)"
        try:
            existente = obter_backup(pasta_nome)
            if existente:
                _log().warning(f"criar_pasta_backup duplicada DB: {pasta_nome} por {owner}")
                return False, f"Pasta já existe: {pasta_nome} — aguarde alguns segundos e tente novamente (nome inclui segundos para evitar colisão)"
        except Exception:
            pass
        try:
            os.makedirs(caminho, exist_ok=False)
        except FileExistsError:
            _log().warning(f"criar_pasta_backup corrida FS: {pasta_nome} por {owner}")
            return False, f"Pasta já existe: {pasta_nome} — aguarde alguns segundos e tente novamente (nome inclui segundos para evitar colisão)"
        except Exception as e:
            _log().exception(f"criar_pasta_backup falhou: {e}")
            return False, f"Falha ao criar pasta: {e}"
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO tb_backup (pasta_nome, owner, ip, hostname) VALUES (?, ?, ?, ?)",
                (pasta_nome, owner, ip_v, pc),
            )
            conn.commit()
            try:
                _audit(owner, "criar_backup", pasta_nome, f"ip={ip_v} host={pc}")
            except Exception as e:
                _log().warning(f"criar_pasta_backup audit falhou: {e}")
            _log().info(f"backup criado: {pasta_nome} por {owner}")
            return True, pasta_nome
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            _log().exception(f"criar_pasta_backup DB falhou: {e}")
            try:
                shutil.rmtree(caminho, ignore_errors=True)
            except Exception:
                pass
            msg = str(e)
            if "UNIQUE" in msg.upper() or "duplicate" in msg.lower():
                return False, f"Pasta já existe: {pasta_nome} — aguarde alguns segundos e tente novamente (nome inclui segundos para evitar colisão)"
            return False, f"Falha no banco: {e}"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        try:
            _log().exception(f"criar_pasta_backup inesperado: {e}")
        except Exception:
            pass
        return False, f"Falha ao criar pasta: {e}"


def listar_backups(owner: str = None, apenas_owner: bool = True) -> list[tuple]:
    """EN: List backups. If apenas_owner and owner given, filter by owner (LGPD).

    PT-BR: Lista backups. Se apenas_owner e owner informado, filtra por dono (LGPD).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        if apenas_owner and owner:
            cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup WHERE owner=? ORDER BY data_criacao ASC", (owner,))
        else:
            cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup ORDER BY data_criacao ASC")
        return cur.fetchall()
    except Exception as e:
        try:
            _log().exception(f"listar_backups falhou: {e}")
        except Exception:
            pass
        return []
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def obter_backup(pasta_nome: str):
    """EN: Fetch one backup row by pasta_nome (None when absent).

    PT-BR: Busca uma linha de backup por pasta_nome (None quando ausente).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup WHERE pasta_nome=?", (pasta_nome,))
        return cur.fetchone()
    except Exception as e:
        try:
            _log().exception(f"obter_backup falhou: {e}")
        except Exception:
            pass
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _pasta_backup_path(pasta_nome: str) -> str:
    """EN: Canonical backup folder path (path traversal shield).

    PT-BR: Retorna caminho canônico da pasta de backup (blindagem path traversal).

    AGENTS.md §1 — tudo dentro de mod_tecnico/backup; nunca escapa.
    Usa basename + sanitização + commonpath.
    """
    try:
        # Remove componentes de caminho e sanitiza
        pasta_nome = os.path.basename((pasta_nome or "").strip())
        pasta_nome = re.sub(r"[^A-Za-z0-9_.-]", "_", pasta_nome)
        # Aceita YYYYMMDD_HHMM_pc_ip (legado) e YYYYMMDD_HHMM_pc_ip_SS (novo,
        # sufixo de segundos) e YYYYMMDD_HHMM_SS_pc_ip; fallback já sanitizado.
        # O prefixo YYYYMMDD_HHMM_ é preservado para compatibilidade.
        if not re.match(r"^[0-9]{8}_[0-9]{4}(_[0-9]{2})?_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+(_[0-9]{2})?$", pasta_nome):
            # mantém sanitizado, mas limita tamanho
            pasta_nome = pasta_nome[:80] or "backup"
        caminho = os.path.join(PASTA_BACKUP, pasta_nome)
        # Verificação canônica: nunca escapar de PASTA_BACKUP
        try:
            if os.path.commonpath([os.path.abspath(caminho), os.path.abspath(PASTA_BACKUP)]) != os.path.abspath(PASTA_BACKUP):
                # fallback seguro: basename sanitizado dentro da base
                caminho = os.path.join(PASTA_BACKUP, _sanitizar_nome(pasta_nome))
        except Exception:
            caminho = os.path.join(PASTA_BACKUP, _sanitizar_nome(pasta_nome))
        return caminho
    except Exception as e:
        try:
            _log().warning(f"_pasta_backup_path falhou, fallback seguro: {e}")
        except Exception:
            pass
        return os.path.join(PASTA_BACKUP, "backup")


def salvar_arquivos_backup(pasta_nome: str, arquivos: list, owner: str) -> tuple[bool, str]:
    """EN: Save uploaded files ((name, bytes) list) into the owner backup folder.

    PT-BR: Salva arquivos enviados (lista de (nome, bytes)) na pasta de backup do owner.

    Atomicidade FS+DB: FS é escrito primeiro (fora da transação); os INSERTs
    em tb_backup_arquivo + UPDATE em tb_backup rodam em transação CURTA com
    retry em "database is locked" (3 tentativas). Se o DB falhar, faz
    rollback + COMPENSAÇÃO no FS (remove os arquivos recém-escritos desta
    chamada) para não deixar pasta órfã/sem registro, e loga tudo.
    """
    try:
        row = obter_backup(pasta_nome)
        if not row:
            return False, "Pasta de backup não encontrada"
        if row[2] != owner:
            try:
                from mod_intranet.autenticacao import perfil_global_de
                if perfil_global_de(owner) != "administrador_geral":
                    return False, "Apenas o dono do backup pode enviar arquivos"
            except Exception as e:
                _log().warning(f"salvar_arquivos_backup perfil falhou: {e}")
                return False, "Apenas o dono do backup pode enviar arquivos"
        caminho = _pasta_backup_path(pasta_nome)
        if not os.path.isdir(caminho):
            try:
                os.makedirs(caminho, exist_ok=True)
            except Exception as e:
                _log().exception(f"salvar_arquivos_backup makedirs falhou: {e}")
                return False, f"Falha ao garantir pasta: {e}"
        # Fase 1 (FS, fora da transação): escreve arquivos e registra pendências
        pendentes: list[tuple] = []
        escritos: list[str] = []
        total = 0
        try:
            for nome, conteudo in arquivos:
                nome_safe = (nome or "").replace("\\", "/").strip()
                partes = [p for p in nome_safe.split("/") if p and p != ".." and "\x00" not in p]
                partes_safe = []
                for p in partes:
                    s = re.sub(r"[^A-Za-z0-9._-]", "_", p)
                    s = s.strip("._")
                    if s:
                        partes_safe.append(s)
                partes = partes_safe
                if not partes:
                    continue
                nome_rel = "/".join(partes)
                dest = os.path.join(caminho, *partes)
                try:
                    if os.path.commonpath([os.path.abspath(dest), os.path.abspath(caminho)]) != os.path.abspath(caminho):
                        continue
                except Exception:
                    continue
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                except Exception as e:
                    _log().warning(f"salvar_arquivos_backup makedirs subpasta falhou {dest}: {e}")
                    continue
                try:
                    with open(dest, "wb") as f:
                        f.write(conteudo)
                except Exception as e:
                    _log().exception(f"salvar_arquivos_backup escrita falhou {dest}: {e}")
                    continue
                escritos.append(os.path.abspath(dest))
                tamanho = len(conteudo)
                total += tamanho
                try:
                    h = hashlib.sha256(conteudo).hexdigest()
                except Exception:
                    h = ""
                pendentes.append((partes[-1], nome_rel, tamanho, h))
        except Exception as e:
            _log().exception(f"salvar_arquivos_backup fase FS falhou: {e}")
            return False, f"Falha ao salvar: {e}"
        if not pendentes:
            return True, f"0 arquivo(s) salvo(s) em {pasta_nome}"
        # Fase 2 (DB, transação curta com retry locked)
        conn = get_connection()
        try:
            ultimo_erro = None
            for tentativa in range(1, 4):
                try:
                    cur = conn.cursor()
                    for nome_f, nome_rel, tamanho, h in pendentes:
                        cur.execute(
                            "INSERT INTO tb_backup_arquivo (backup_id, nome, caminho_relativo, tamanho, hash_sha256) VALUES (?, ?, ?, ?, ?)",
                            (row[0], nome_f, nome_rel, tamanho, h),
                        )
                    cur.execute("UPDATE tb_backup SET tamanho_total = tamanho_total + ?, status='em_envio' WHERE id=?", (total, row[0]))
                    conn.commit()
                    ultimo_erro = None
                    break
                except Exception as e:
                    ultimo_erro = e
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    msg = str(e).lower()
                    if "locked" in msg and tentativa < 3:
                        _log().warning(f"salvar_arquivos_backup locked, retry {tentativa}/3")
                        time.sleep(0.05 * tentativa)
                        continue
                    break
            if ultimo_erro is not None:
                # Compensação FS: remove arquivos desta chamada (evita órfãos)
                for dest in escritos:
                    try:
                        if os.path.isfile(dest):
                            os.remove(dest)
                    except Exception as e:
                        _log().warning(f"salvar_arquivos_backup compensação falhou {dest}: {e}")
                _log().exception(f"salvar_arquivos_backup DB falhou, FS compensado ({len(escritos)} removidos): {ultimo_erro}")
                return False, f"Falha ao salvar: {ultimo_erro}"
            try:
                _audit(owner, "enviar_backup", pasta_nome, f"{len(pendentes)} arquivo(s) total={total}")
            except Exception as e:
                _log().warning(f"salvar_arquivos_backup audit falhou: {e}")
            return True, f"{len(pendentes)} arquivo(s) salvo(s) em {pasta_nome}"
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            for dest in escritos:
                try:
                    if os.path.isfile(dest):
                        os.remove(dest)
                except Exception:
                    pass
            _log().exception(f"salvar_arquivos_backup falhou: {e}")
            return False, f"Falha ao salvar: {e}"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        try:
            _log().exception(f"salvar_arquivos_backup inesperado: {e}")
        except Exception:
            pass
        return False, f"Falha ao salvar: {e}"


def criar_zip_backup(pasta_nome: str, owner: str) -> str:
    """EN: Build temporary zip of the whole backup folder (restore on formatted PC).

    PT-BR: Gera zip temporário de toda a pasta de backup (para restaurar no PC formatado).
    """
    tmp = None
    try:
        row = obter_backup(pasta_nome)
        if not row:
            raise FileNotFoundError("Backup não encontrado")
        if row[2] != owner:
            try:
                from mod_intranet.autenticacao import perfil_global_de
                if perfil_global_de(owner) != "administrador_geral":
                    raise PermissionError("Apenas o dono do backup pode baixar")
            except PermissionError:
                raise
            except Exception as e:
                _log().warning(f"criar_zip_backup perfil falhou: {e}")
                raise PermissionError("Apenas o dono do backup pode baixar")
        caminho = _pasta_backup_path(pasta_nome)
        if not os.path.isdir(caminho):
            raise FileNotFoundError("Pasta física não encontrada")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(caminho):
                for f in files:
                    f_abs = os.path.join(root, f)
                    arc = os.path.relpath(f_abs, caminho).replace(os.sep, "/")
                    zf.write(f_abs, arcname=arc)
        try:
            _audit(owner, "download_backup", pasta_nome, f"zip={tmp.name}")
        except Exception as e:
            _log().warning(f"criar_zip_backup audit falhou: {e}")
        return tmp.name
    except (FileNotFoundError, PermissionError):
        raise
    except Exception as e:
        try:
            if tmp is not None:
                try:
                    os.remove(tmp.name)
                except Exception:
                    pass
            _log().exception(f"criar_zip_backup falhou: {e}")
        except Exception:
            pass
        raise


def remover_vinculos_usuario(user_nome: str) -> int:
    """EN: LGPD — remove user backups and physical files. Returns count.

    PT-BR: LGPD: remove backups e arquivos físicos do usuário.

    Não depende de FK ON DELETE CASCADE: o proxy Postgres remove REFERENCES,
    então apaga EXPLICITAMENTE os filhos tb_backup_arquivo antes dos pais
    tb_backup (funciona em SQLite e Postgres).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, pasta_nome FROM tb_backup WHERE owner=?", (user_nome,))
        linhas = cur.fetchall()
        pastas = [r[1] for r in linhas]
        ids = [r[0] for r in linhas]
        n = len(pastas)
        for p in pastas:
            try:
                caminho = _pasta_backup_path(p)
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho, ignore_errors=True)
            except Exception as e:
                try:
                    _log().warning(f"remover_vinculos rmtree falhou {p}: {e}")
                except Exception:
                    pass
        # DELETE explícito dos filhos (sem depender de CASCADE; sem f-string — loop por id)
        if ids:
            try:
                for bid in ids:
                    cur.execute("DELETE FROM tb_backup_arquivo WHERE backup_id=?", (bid,))
            except Exception as e:
                _log().exception(f"remover_vinculos DELETE filhos falhou: {e}")
                raise
        cur.execute("DELETE FROM tb_backup WHERE owner=?", (user_nome,))
        conn.commit()
        if n:
            try:
                _audit("sistema", "remover_vinculos_tecnico", user_nome, f"{n} backup(s) removido(s)")
            except Exception as e:
                _log().warning(f"remover_vinculos audit falhou: {e}")
        return n
    except Exception as e:
        try:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            _log().exception(f"remover_vinculos_usuario falhou: {e}")
        except Exception:
            pass
        raise
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def renomear_usuario(nome_atual: str, novo_nome: str):
    """EN: Propagate rename to tb_backup.owner.

    PT-BR: Propaga renomeio para tb_backup.owner.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_backup SET owner=? WHERE owner=?", (novo_nome, nome_atual))
        conn.commit()
    except Exception as e:
        try:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            _log().exception(f"renomear_usuario falhou: {e}")
        except Exception:
            pass
        raise
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


init_db()
