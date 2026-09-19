"""Módulo Técnico — BD próprio, arquivos e backups.

Módulo Técnico — acesso ao db_mod_tecnico.db (WAL) e regras de negócio.
Pastas físicas dentro do módulo:
  software/ → executáveis disponibilizados (download)
  backup/   → pastas YYYYMMDD_HHMM_nomePc_ip por técnico/PC (isolamento por owner)

Isolamento total: cada módulo limpa o próprio banco via API pública.
"""

import os
import sys
import re
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
    from mod_intranet import observabilidade
    return observabilidade.get_logger("tecnico")


def get_connection():
    """Abre conexão do módulo (WAL) via banco_conexao.conexao('tecnico')."""
    from mod_intranet.banco_conexao import conexao
    conn = conexao("tecnico")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão mod_tecnico")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def _audit(ator, acao, alvo, detalhe=""):
    from mod_intranet.bd_manipulador import audit_log
    audit_log(ator or "sistema", "tecnico", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))


def _sanitizar_nome(nome: str) -> str:
    """Sanitiza nomePc/ip para uso em pasta (só [a-zA-Z0-9_-])."""
    base = re.sub(r"[^a-zA-Z0-9_-]", "_", (nome or "").strip() or "pc")
    base = re.sub(r"_+", "_", base).strip("_")
    return base[:40] or "pc"


def _hash_sha256(caminho: str) -> str:
    try:
        h = hashlib.sha256()
        with open(caminho, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def init_db():
    """Cria/migra schema do técnico (idempotente)."""
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
        cur.execute("INSERT OR IGNORE INTO tb_config_tecnico (chave, valor) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    for p in (PASTA_SOFTWARE, PASTA_BACKUP):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass


# ============ SOFTWARE ============

def listar_software(relativo: str = ""):
    """Lista recursiva de arquivos/pastas em software/ (relativo ao software/)."""
    base = os.path.join(PASTA_SOFTWARE, relativo) if relativo else PASTA_SOFTWARE
    if not os.path.isdir(base):
        return []
    itens = []
    try:
        for nome in sorted(os.listdir(base)):
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
    """Lista todos os arquivos (folhas) em software/ recursivamente (ignora .gitkeep)."""
    arquivos = []
    for root, dirs, files in os.walk(PASTA_SOFTWARE):
        for f in files:
            if f == ".gitkeep":
                continue
            abs_path = os.path.join(root, f)
            rel = os.path.relpath(abs_path, PASTA_SOFTWARE).replace(os.sep, "/")
            arquivos.append(rel)
    return sorted(arquivos)


def criar_zip_selecionados(relativos: list[str], owner: str = "") -> str:
    """Cria zip temporário com arquivos/pastas selecionados (relativos a software/)."""
    if not relativos:
        raise ValueError("Nenhum item selecionado")
    # Limite de tamanho
    max_mb = 1024
    try:
        from mod_intranet.bd_conexao import get_config
        max_mb = int((get_config("tecnico_max_zip_mb", "1024") or "1024").strip() or 1024)
    except Exception:
        pass
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    total = 0
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in relativos:
            rel_norm = rel.replace("/", os.sep)
            abs_path = os.path.join(PASTA_SOFTWARE, rel_norm)
            if os.path.isdir(abs_path):
                for root, _, files in os.walk(abs_path):
                    for f in files:
                        f_abs = os.path.join(root, f)
                        arc = os.path.relpath(f_abs, PASTA_SOFTWARE).replace(os.sep, "/")
                        # segurança: não sair de software/
                        if ".." in arc:
                            continue
                        zf.write(f_abs, arcname=arc)
                        try:
                            total += os.path.getsize(f_abs)
                        except Exception:
                            pass
            elif os.path.isfile(abs_path):
                arc = rel.replace(os.sep, "/")
                zf.write(abs_path, arcname=arc)
                try:
                    total += os.path.getsize(abs_path)
                except Exception:
                    pass
            if total > max_mb * 1024 * 1024:
                raise ValueError(f"Seleção excede limite de {max_mb} MB")
    _audit(owner or "sistema", "download_software", ",".join(relativos[:3]), f"total={total} bytes zip={tmp.name}")
    return tmp.name


# ============ BACKUP ============

def nome_pasta_backup(nome_pc: str, ip: str) -> str:
    """Gera nome padrão YYYYMMDD_HHMM_nomePc_ip."""
    data = datetime.now().strftime("%Y%m%d_%H%M")
    pc = _sanitizar_nome(nome_pc)
    ip_s = _sanitizar_nome(ip).replace(".", "_") if ip else "sem_ip"
    # ip sanitizado perde pontos, então tratamos separado: manter . como _
    ip_s = re.sub(r"[^a-zA-Z0-9._-]", "_", (ip or "sem_ip").strip() or "sem_ip")
    ip_s = _sanitizar_nome(ip_s.replace(".", "_"))
    return f"{data}_{pc}_{ip_s}"


def criar_pasta_backup(owner: str, nome_pc: str, ip: str) -> tuple[bool, str]:
    """Cria pasta de backup nomeada automaticamente. Retorna (ok, pasta_nome|caminho|msg)."""
    if not owner:
        return False, "Usuário não identificado"
    pc = (nome_pc or "").strip()
    ip_v = (ip or "").strip()
    if len(pc) < 2:
        return False, "Informe o nome do PC (mín. 2 caracteres)"
    if len(ip_v) < 3:
        return False, "Informe o IP do PC (mín. 3 caracteres)"
    pasta_nome = nome_pasta_backup(pc, ip_v)
    caminho = os.path.join(PASTA_BACKUP, pasta_nome)
    if os.path.exists(caminho):
        return False, f"Pasta já existe: {pasta_nome}"
    try:
        os.makedirs(caminho, exist_ok=False)
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
        _audit(owner, "criar_backup", pasta_nome, f"ip={ip_v} host={pc}")
        _log().info(f"backup criado: {pasta_nome} por {owner}")
        return True, pasta_nome
    except Exception as e:
        _log().exception(f"criar_pasta_backup DB falhou: {e}")
        try:
            shutil.rmtree(caminho, ignore_errors=True)
        except Exception:
            pass
        return False, f"Falha no banco: {e}"
    finally:
        conn.close()


def listar_backups(owner: str = None, apenas_owner: bool = True) -> list[tuple]:
    """Lista backups. Se apenas_owner e owner informado, filtra por dono (LGPD)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if apenas_owner and owner:
            cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup WHERE owner=? ORDER BY data_criacao DESC", (owner,))
        else:
            cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup ORDER BY data_criacao DESC")
        return cur.fetchall()
    finally:
        conn.close()


def obter_backup(pasta_nome: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, pasta_nome, owner, ip, hostname, tamanho_total, status, data_criacao FROM tb_backup WHERE pasta_nome=?", (pasta_nome,))
        return cur.fetchone()
    finally:
        conn.close()


def _pasta_backup_path(pasta_nome: str) -> str:
    # sanitiza para evitar path traversal
    base = _sanitizar_nome(pasta_nome)
    # pasta_nome já é sanitizado, mas mantém data prefixo com _
    # validação extra: só permite caracteres do padrão
    if not re.match(r"^[0-9]{8}_[0-9]{4}_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+$", pasta_nome):
        # tenta sanitizar fallback: permite qualquer sanitizado
        pasta_nome = re.sub(r"[^A-Za-z0-9_.-]", "_", pasta_nome)
    return os.path.join(PASTA_BACKUP, pasta_nome)


def salvar_arquivos_backup(pasta_nome: str, arquivos: list, owner: str) -> tuple[bool, str]:
    """Salva arquivos enviados (lista de (nome, bytes)) na pasta de backup do owner."""
    row = obter_backup(pasta_nome)
    if not row:
        return False, "Pasta de backup não encontrada"
    if row[2] != owner:
        # apenas dono pode gravar (LGPD)
        # permite admin geral também? Por ora, só dono
        from mod_intranet.autenticacao import perfil_global_de
        if perfil_global_de(owner) != "administrador_geral":
            return False, "Apenas o dono do backup pode enviar arquivos"
    caminho = _pasta_backup_path(pasta_nome)
    if not os.path.isdir(caminho):
        try:
            os.makedirs(caminho, exist_ok=True)
        except Exception as e:
            return False, f"Falha ao garantir pasta: {e}"
    total = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        for nome, conteudo in arquivos:
            # sanitiza nome e preserva subpastas se vier com "/" (webkitdirectory)
            nome_safe = nome.replace("\\", "/").strip()
            # remove .. e //
            partes = [p for p in nome_safe.split("/") if p and p != ".."]
            if not partes:
                continue
            nome_rel = "/".join(partes)
            dest = os.path.join(caminho, *partes)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(conteudo)
            tamanho = len(conteudo)
            total += tamanho
            h = hashlib.sha256(conteudo).hexdigest()
            cur.execute(
                "INSERT INTO tb_backup_arquivo (backup_id, nome, caminho_relativo, tamanho, hash_sha256) VALUES (?, ?, ?, ?, ?)",
                (row[0], partes[-1], nome_rel, tamanho, h),
            )
        cur.execute("UPDATE tb_backup SET tamanho_total = tamanho_total + ?, status='em_envio' WHERE id=?", (total, row[0]))
        conn.commit()
        _audit(owner, "enviar_backup", pasta_nome, f"{len(arquivos)} arquivo(s) total={total}")
        return True, f"{len(arquivos)} arquivo(s) salvo(s) em {pasta_nome}"
    except Exception as e:
        conn.rollback()
        _log().exception(f"salvar_arquivos_backup falhou: {e}")
        return False, f"Falha ao salvar: {e}"
    finally:
        conn.close()


def criar_zip_backup(pasta_nome: str, owner: str) -> str:
    """Gera zip temporário de toda a pasta de backup (para restaurar no PC formatado)."""
    row = obter_backup(pasta_nome)
    if not row:
        raise FileNotFoundError("Backup não encontrado")
    # isolamento: apenas dono ou admin geral pode baixar
    if row[2] != owner:
        from mod_intranet.autenticacao import perfil_global_de
        if perfil_global_de(owner) != "administrador_geral":
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
    _audit(owner, "download_backup", pasta_nome, f"zip={tmp.name}")
    return tmp.name


def remover_vinculos_usuario(user_nome: str) -> int:
    """LGPD: remove backups e arquivos físicos do usuário."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT pasta_nome FROM tb_backup WHERE owner=?", (user_nome,))
        pastas = [r[0] for r in cur.fetchall()]
        n = len(pastas)
        for p in pastas:
            caminho = _pasta_backup_path(p)
            try:
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho, ignore_errors=True)
            except Exception:
                pass
        cur.execute("DELETE FROM tb_backup WHERE owner=?", (user_nome,))
        conn.commit()
        if n:
            _audit("sistema", "remover_vinculos_tecnico", user_nome, f"{n} backup(s) removido(s)")
        return n
    finally:
        conn.close()


def renomear_usuario(nome_atual: str, novo_nome: str):
    """Propaga renomeio para tb_backup.owner."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_backup SET owner=? WHERE owner=?", (novo_nome, nome_atual))
        conn.commit()
    finally:
        conn.close()


init_db()
