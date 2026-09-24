"""PDF Editor module — own database, quotas, operations and automatic cleanup.

Módulo Editor de PDF — BD próprio, cotas, operações e limpeza automática.

Arquivos ficam em mod_edit_pdf/editorPDF/<usuario>/ com prefixo:
  dataHora_usuario_operacao_nomeOriginal.pdf
"""
import sys, os, time, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import zipfile
from datetime import datetime

from mod_intranet.bd_conexao import get_connection, get_config
from mod_intranet.bd_manipulador import audit_log


def _log():
    """Module logger (loguru) — dedicated file logs/edit_pdf_<data>.log.

    Logger do módulo (loguru) — arquivo dedicado logs/edit_pdf_<data>.log."""
    try:
        from mod_intranet import observabilidade
        return observabilidade.get_logger("edit_pdf")
    except Exception as e:
        # Fallback sem recursão (nunca chamar _log() aqui dentro).
        try:
            print(f"[edit_pdf][log-fallback] {e}")
        except Exception:
            pass
        try:
            import logging
            return logging.getLogger("edit_pdf")
        except Exception:
            return None


def _notificar_falha(msg):
    """Notifica falha de banco sem derrubar handler NiceGUI (fail-soft).

    Tenta `tema_modulo.notificar()`; cai para console+loguru."""
    try:
        _lg = _log()
        if _lg is not None:
            try:
                _lg.error(msg)
            except Exception:
                pass
    except Exception:
        pass
    try:
        from mod_intranet.tema_modulo import notificar as _notificar
        try:
            _notificar(msg, tipo="error")
        except Exception:
            print(f"[edit_pdf] {msg}")
    except Exception:
        try:
            print(f"[edit_pdf] {msg}")
        except Exception:
            pass


def _falha_conexao(contexto):
    """Registra + notifica falha ao abrir conexão (guarda None)."""
    try:
        msg = f"Editor de PDF indisponível no momento ({contexto}). Tente novamente."
        _lg = _log()
        if _lg is not None:
            try:
                _lg.error(f"conexão None em {contexto}")
            except Exception:
                pass
        _notificar_falha(msg)
    except Exception:
        pass
    return None


def _eh_locked(erro):
    """True se o erro for contenção SQLite (database is locked/busy)."""
    try:
        txt = str(erro).lower()
        return ("locked" in txt) or ("busy" in txt)
    except Exception:
        return False


def _fechar_seguro(conn):
    """Fecha conexão ignorando falhas (nunca derruba handler)."""
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def _log_exc(msg):
    """Registra exception sem risco de None/recursão (AGENTS §3.2)."""
    try:
        _lg = _log()
        if _lg is not None:
            try:
                _lg.exception(msg)
                return
            except Exception:
                pass
    except Exception:
        pass
    try:
        print(f"[edit_pdf] {msg}")
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_edit_pdf")
DB_PDF_PATH = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")
PASTA_EDITOR = os.path.join(MOD_DIR, "editorPDF")

QUOTA_GLOBAL_BYTES_DEFAULT = 10 * 1024**3   # 10 GB
QUOTA_USUARIO_BYTES = 1 * 1024**3           # 1 GB por usuário (legado; usar cfg_usuario_gb)


# ============ CONFIGURAÇÕES DINÂMICAS (tb_config central, prefixo editar_pdf_) ============

def _cfg(chave, default):
    """Reads an `editar_pdf_<chave>` key from the central tb_config (fail-soft).

    Lê a chave `editar_pdf_<chave>` da tb_config central (fail-soft)."""
    try:
        return get_config(f"editar_pdf_{chave}", str(default))
    except Exception:
        return str(default)


def cfg_lote_arquivos():
    """Maximum number of files per upload batch (`editar_pdf_lote_arquivos`, min 1).

    Máximo de arquivos por lote de upload (`editar_pdf_lote_arquivos`, mín. 1)."""
    try:
        return max(1, int(_cfg("lote_arquivos", 10)))
    except ValueError:
        return 10


def cfg_lote_mb():
    """Maximum MB per upload batch (`editar_pdf_lote_mb`, min 1).

    Máximo de MB por lote de upload (`editar_pdf_lote_mb`, mín. 1)."""
    try:
        return max(1, int(_cfg("lote_mb", 1024)))
    except ValueError:
        return 1024


def cfg_usuario_gb():
    """Per-user disk quota in GB (`editar_pdf_usuario_gb`, min 1).

    Cota de disco por usuário em GB (`editar_pdf_usuario_gb`, mín. 1)."""
    try:
        return max(1, int(_cfg("usuario_gb", 1)))
    except ValueError:
        return 1


def cfg_expiracao_min():
    """File lifetime in minutes inside editorPDF (`editar_pdf_expiracao_min`, min 1).

    Tempo de vida do arquivo em minutos dentro de editorPDF (`editar_pdf_expiracao_min`, mín. 1)."""
    try:
        return max(1, int(_cfg("expiracao_min", 10)))
    except ValueError:
        return 10


# ============ TEMA (cores/tamanhos padronizados dos botões, abas e fundo) ============

def cfg_tema(chave, default):
    """Reads a theme key ('cor_botao', 'cor_texto_botao', …) from tb_config.

    Legado: ficou SEM USO após a migração da tela para `tema_modulo.ler_tema`
    (06/09) — mantido apenas por compatibilidade; candidato a remoção."""
    try:
        return (_cfg(chave, default) or "").strip() or default
    except Exception:
        return default


def _conn():
    """Opens a connection to the module's own database (WAL).

    Conexão via `banco_conexao.conexao` — SQLite (db_mod_edit_pdf.db, WAL)
    ou PostgreSQL (schema `editar_pdf`).

    busy_timeout=5000 é HERDADO do núcleo (`mod_intranet.banco_conexao.conexao`
    aplica WAL+synchronous=NORMAL+busy_timeout=5000+foreign_keys=ON no SQLite;
    no Postgres o proxy traduz PRAGMA sem efeito). O PRAGMA abaixo só reforça
    WAL no SQLite e é inócuo no Postgres (proxy devolve vazio)."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("editar_pdf")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão do módulo Editor de PDF")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        return conn
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"_conn falhou: {e}")
        except Exception:
            pass
        return None


def init_db_pdf():
    """Creates the module tables (idempotent bootstrap).

    Cria `tb_arquivos` (id, nome_arquivo, usuario, tamanho_bytes, operacao,
    data_operacao, ativo) e `tb_cota_disco` (usuario PK, total_usado_bytes,
    atualizado_em) em `db_mod_edit_pdf.db` (WAL), e semeia a versão individual
    do módulo na `tb_config` central. Executado no import e pelo bootstrap."""
    try:
        conn = _conn()
        if conn is None:
            _falha_conexao("init_db_pdf")
            return None
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_arquivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_arquivo TEXT NOT NULL,
                usuario TEXT NOT NULL,
                tamanho_bytes INTEGER NOT NULL,
                operacao TEXT NOT NULL,
                data_operacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_cota_disco (
                usuario TEXT PRIMARY KEY,
                total_usado_bytes INTEGER NOT NULL DEFAULT 0,
                atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        _fechar_seguro(conn)

        _semear_versao_modulo()
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"init_db_pdf falhou: {e}")
        except Exception:
            pass
        try:
            _notificar_falha(f"Falha ao inicializar banco do Editor de PDF: {e}")
        except Exception:
            pass
        try:
            if 'conn' in locals():
                try:
                    conn.rollback()
                except Exception:
                    pass
                _fechar_seguro(conn)
        except Exception:
            pass
        return None


def _semear_versao_modulo():
    """Seed idempotente da versão individual do módulo (tb_config central).

    Formato 1.0.AAMMDD, mesmo estilo da versão do sistema. Se já existir, o valor
    manual NÃO é sobrescrito (INSERT OR IGNORE). Atualizar manualmente a cada
    alteração do mod_edit_pdf.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO tb_config (chave, valor) VALUES (?, ?)",
            ("versao_modulo:editar_pdf", "1.0.260908"))
        conn.commit()
        conn.close()
    except Exception:
        _log_exc("falha ao semear versão do módulo editar_pdf")

def pasta_usuario(usuario):
    """Returns (and creates if missing) the user's folder inside editorPDF/.

    Retorna (criando se inexistente) a pasta do usuário dentro de editorPDF/."""
    try:
        p = os.path.join(PASTA_EDITOR, usuario)
        os.makedirs(p, exist_ok=True)
        return p
    except Exception as e:
        _log_exc(f"pasta_usuario falhou: {e}")
        return None


def uso_global_bytes():
    """Real disk usage of the editorPDF directory (all users, walked on disk).

    Uso real em disco do diretório editorPDF (todos os usuários, varredura em disco)."""
    try:
        total = 0
        if os.path.isdir(PASTA_EDITOR):
            for root, _dirs, files in os.walk(PASTA_EDITOR):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        return total
    except Exception as e:
        _log_exc(f"uso_global_bytes falhou: {e}")
        return None


def nome_padronizado(usuario, operacao, nome_original):
    """Builds the standardized file name: dataHora_usuario_operacao_nome.pdf.

    O nome original é sanitizado (só alfanuméricos/._- e espaço, máx. 60
    chars) — cada usuário vê apenas os próprios arquivos."""
    try:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        seguro = "".join(c for c in (nome_original or "arquivo") if c.isalnum() or c in "._- ")[:60].strip()
        return f"{stamp}_{usuario}_{operacao}_{seguro}"
    except Exception as e:
        _log_exc(f"nome_padronizado falhou: {e}")
        return None


def _cota_global_bytes():
    """Global disk quota in bytes (`cotadisco_global_gb`); fallback 10 GB.

    Cota global de disco em bytes (`cotadisco_global_gb`); padrão 10 GB."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT CAST(valor AS INTEGER) FROM tb_config WHERE chave='cotadisco_global_gb'")
        row = cur.fetchone()
        conn.close()
        if row:
            return int(row[0]) * 1024**3
    except Exception:
        _log_exc("falha ao ler cota global de disco")
    return QUOTA_GLOBAL_BYTES_DEFAULT


def verificar_quota(usuario, tamanho_bytes):
    """Checks global and per-user quotas before saving. Returns (ok, msg).

    Verifica as cotas global e por usuário antes de gravar. Retorna (ok, msg)."""
    conn = _conn()
    if conn is None:
        _falha_conexao("verificar_quota")
        return False, "Banco do Editor de PDF indisponível. Tente novamente."
    try:
        cur = conn.cursor()
        cur.execute("SELECT SUM(tamanho_bytes) FROM tb_arquivos WHERE ativo=1")
        total_global = cur.fetchone()[0] or 0
        cur.execute("SELECT total_usado_bytes FROM tb_cota_disco WHERE usuario=?", (usuario,))
        row = cur.fetchone()
        usado_user = row[0] if row else 0
        limite_global = _cota_global_bytes()
        if total_global + tamanho_bytes > limite_global:
            gb = limite_global // 1024**3
            return False, f"Cota global excedida ({gb} GB)"
        if usado_user + tamanho_bytes > cfg_usuario_gb() * 1024**3:
            gb_u = cfg_usuario_gb()
            return False, f"Sua cota de {gb_u} GB foi excedida"
        return True, "OK"
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"verificar_quota falhou: {e}")
        except Exception:
            pass
        return False, f"Falha ao verificar cota: {e}"
    finally:
        _fechar_seguro(conn)


def registrar_arquivo(usuario, caminho_fisico, operacao, tamanho_bytes=None):
    """Registers a file already on disk and updates quota. Returns id or None.

    Registra arquivo existente no disco e atualiza cota. Retorna id ou None.

    Atomicidade: os 2 writes (tb_arquivos + tb_cota_disco) rodam em transação
    curta com commit único; falha faz rollback para a cota nunca estourar.
    Contenção SQLite (`database is locked`) tem retry curto (3x)."""
    conn = None
    try:
        if not os.path.isfile(caminho_fisico):
            return None
        try:
            if tamanho_bytes is None:
                tamanho_bytes = os.path.getsize(caminho_fisico)
        except OSError as e:
            _lg = _log()
            if _lg is not None:
                try:
                    _lg.exception(f"registrar_arquivo stat falhou: {e}")
                except Exception:
                    pass
            return None
        ok, msg = verificar_quota(usuario, tamanho_bytes)
        if not ok:
            ui_notify_erro(msg)
            try:
                os.remove(caminho_fisico)
            except OSError:
                pass
            return None
        nome = os.path.basename(caminho_fisico)
        conn = _conn()
        if conn is None:
            _falha_conexao("registrar_arquivo")
            try:
                os.remove(caminho_fisico)
            except OSError:
                pass
            return None
        last_id = None
        for tentativa in range(3):
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO tb_arquivos (nome_arquivo, usuario, tamanho_bytes, operacao) VALUES (?, ?, ?, ?)",
                    (nome, usuario, tamanho_bytes, operacao),
                )
                last_id = cur.lastrowid
                cur.execute(
                    """
                    INSERT INTO tb_cota_disco (usuario, total_usado_bytes, atualizado_em)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(usuario) DO UPDATE SET
                        total_usado_bytes = total_usado_bytes + ?,
                        atualizado_em = datetime('now')
                    """,
                    (usuario, tamanho_bytes, tamanho_bytes),
                )
                conn.commit()
                break
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if _eh_locked(e) and tentativa < 2:
                    try:
                        _lg = _log()
                        if _lg is not None:
                            _lg.warning(f"registrar_arquivo retry {tentativa+1}/3 (locked)")
                    except Exception:
                        pass
                    time.sleep(0.1 * (tentativa + 1))
                    continue
                try:
                    _lg = _log()
                    if _lg is not None:
                        _lg.exception(f"registrar_arquivo falhou: {e}")
                except Exception:
                    pass
                _notificar_falha(f"Falha ao registrar arquivo {nome}. Tente novamente.")
                try:
                    os.remove(caminho_fisico)
                except OSError:
                    pass
                return None
        try:
            audit_log(usuario, "edit-pdf", operacao, f"Arquivo {nome} ({tamanho_bytes} bytes)")
        except Exception:
            pass
        try:
            _lg = _log()
            if _lg is not None:
                _lg.info(f"arquivo registrado: {nome} usuario={usuario} operacao={operacao}")
        except Exception:
            pass
        return last_id
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"registrar_arquivo falhou: {e}")
        except Exception:
            pass
        _notificar_falha(f"Falha ao registrar arquivo. Tente novamente.")
        return None
    finally:
        _fechar_seguro(conn)


def ui_notify_erro(msg):  # isolado para não acoplar UI na lógica
    """Reports a quota error to console + loguru (UI kept out of the logic).

    Reporta erro de cota no console + loguru (sem acoplar UI à lógica)."""
    try:
        print(f"[quota] {msg}")
        _lg = _log()
        if _lg is not None:
            try:
                _lg.error(f"[quota] {msg}")
            except Exception:
                pass
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"ui_notify_erro falhou: {e}")
        except Exception:
            pass
        return None


def obter_meus_arquivos(usuario):
    """Lists the user's active files that still exist on disk (id, nome, tam, op, dt).

    Registros cujo arquivo já foi removido do disco (pelo scheduler de
    expiração) são ignorados — a lista reflete o que realmente existe."""
    conn = _conn()
    if conn is None:
        _falha_conexao("obter_meus_arquivos")
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nome_arquivo, tamanho_bytes, operacao, data_operacao
               FROM tb_arquivos WHERE usuario=? AND ativo=1 ORDER BY id DESC""",
            (usuario,),
        )
        rows = []
        pasta = pasta_usuario(usuario)
        if pasta is None:
            return []
        for r in cur.fetchall():
            path = os.path.join(pasta, r[1])
            if not os.path.exists(path):  # arquivo já limpo pelo scheduler
                continue
            rows.append(r)
        return rows
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"obter_meus_arquivos falhou: {e}")
        except Exception:
            pass
        _notificar_falha("Falha ao listar arquivos. Tente novamente.")
        return []
    finally:
        _fechar_seguro(conn)


def contar_uploads_ativos(usuario):
    """Counts 'upload' files REALLY present in the user's space (stock limit).

    Conta os arquivos 'upload' REALMENTE presentes no espaço do usuário (limite de estoque)."""
    conn = _conn()
    if conn is None:
        _falha_conexao("contar_uploads_ativos")
        return 0
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT nome_arquivo FROM tb_arquivos
               WHERE usuario=? AND operacao='upload' AND ativo=1""",
            (usuario,),
        )
        nomes = [r[0] for r in cur.fetchall()]
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"contar_uploads_ativos falhou: {e}")
        except Exception:
            pass
        return 0
    finally:
        _fechar_seguro(conn)
    try:
        pasta = pasta_usuario(usuario)
        if pasta is None:
            return 0
        return sum(1 for n in nomes if os.path.exists(os.path.join(pasta, n)))
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"contar_uploads_ativos disco falhou: {e}")
        except Exception:
            pass
        return 0


# ================= OPERAÇÕES PDF (núcleo compartilhado) =================
# Motor puro de PDFs mora em `mod_intranet.pdf_operacoes` (sem banco, sem
# estado de módulo) para que nenhum módulo importe outro. Re-export aqui
# para manter a superfície pública deste módulo inalterada.
from mod_intranet.pdf_operacoes import (
    hash_sha256,
    op_reduzir,
    op_juntar,
    op_cortar,
    op_dividir,
    op_dividir_partes,
    op_verificar,
    partes_pares_impares,
    partes_de_cortes,
    partes_de_intervalos,
    partes_pagina_a_pagina,
)




def zip_do_usuario(usuario):
    """Zips ALL active files of the user. Returns the ZIP path.

    Compacta TODOS os arquivos ativos do usuário. Retorna o caminho do ZIP."""
    try:
        arquivos = obter_meus_arquivos(usuario)
        return _zipar(usuario, arquivos)
    except Exception as e:
        _log_exc(f"zip_do_usuario falhou: {e}")
        return None


def zip_por_ids(usuario, ids):
    """Zips only the given files (tb_arquivos ids). Returns path or None.

    Compacta apenas os arquivos informados (ids de tb_arquivos). Retorna caminho ou None."""
    if not ids:
        return None
    conn = _conn()
    if conn is None:
        _falha_conexao("zip_por_ids")
        return None
    try:
        cur = conn.cursor()
        marks = ",".join("?" for _ in ids)
        cur.execute(
            f"""SELECT id, nome_arquivo, tamanho_bytes, operacao, data_operacao
                FROM tb_arquivos WHERE usuario=? AND ativo=1 AND id IN ({marks})""",  # nosec B608 — marks de lista de IDs, não input usuário
            (usuario, *ids),
        )
        arquivos = cur.fetchall()
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"zip_por_ids falhou: {e}")
        except Exception:
            pass
        _notificar_falha("Falha ao compactar arquivos. Tente novamente.")
        return None
    finally:
        _fechar_seguro(conn)
    try:
        return _zipar(usuario, arquivos)
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"zip_por_ids _zipar falhou: {e}")
        except Exception:
            pass
        return None


def _zipar(usuario, arquivos):
    """Writes the ZIP into the user's folder; removes it if nothing was included.

    Grava o ZIP na pasta do usuário; remove se nada foi incluído."""
    try:
        if not arquivos:
            return None
        pasta = pasta_usuario(usuario)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        zip_path = os.path.join(pasta, f"{usuario}_{stamp}_selecao.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            incluidos = 0
            for _id, nome, _tam, _op, _dt in arquivos:
                caminho = os.path.join(pasta, nome)
                if os.path.exists(caminho):
                    z.write(caminho, nome)
                    incluidos += 1
        if not incluidos:
            try:
                os.remove(zip_path)
            except OSError:
                pass
            return None
        return zip_path
    except Exception as e:
        _log_exc(f"_zipar falhou: {e}")
        return None


def deletar_arquivo(usuario, arquivo_id):
    """Deletes a file (disk + soft delete + quota refund) and audits it.

    Exclui um arquivo (disco + soft delete + estorno da cota) com auditoria."""
    conn = _conn()
    if conn is None:
        _falha_conexao("deletar_arquivo")
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo FROM tb_arquivos WHERE id=? AND usuario=?", (arquivo_id, usuario))
        row = cur.fetchone()
        if not row:
            return False
        try:
            pasta = pasta_usuario(usuario)
            if pasta is not None:
                os.remove(os.path.join(pasta, row[0]))
        except OSError:
            pass
        except Exception as e:
            try:
                _lg = _log()
                if _lg is not None:
                    _lg.exception(f"deletar_arquivo disco falhou: {e}")
            except Exception:
                pass
        for tentativa in range(3):
            try:
                cur.execute("UPDATE tb_arquivos SET ativo=0 WHERE id=?", (arquivo_id,))
                cur.execute(
                    """UPDATE tb_cota_disco SET total_usado_bytes = MAX(0, total_usado_bytes -
                       COALESCE((SELECT SUM(tamanho_bytes) FROM tb_arquivos WHERE id=?),0)) WHERE usuario=?""",
                    (arquivo_id, usuario),
                )
                conn.commit()
                break
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if _eh_locked(e) and tentativa < 2:
                    time.sleep(0.1 * (tentativa + 1))
                    continue
                raise
        try:
            audit_log(usuario, "edit-pdf", "deletar", f"Arquivo {row[0]} removido")
        except Exception:
            pass
        return True
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"deletar_arquivo falhou: {e}")
        except Exception:
            pass
        try:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
        except Exception:
            pass
        _notificar_falha("Falha ao excluir arquivo. Tente novamente.")
        return False
    finally:
        _fechar_seguro(conn)


def remover_vinculos_usuario(user_nome):
    """Remove arquivos físicos, registros e cota do usuário (LGPD).

    Chamado pelo módulo de gestão de usuários na exclusão definitiva:
    cada módulo limpa o PRÓPRIO banco (isolamento total — sem cross-query
    entre bancos). Retorna (removidos_do_disco, nomes_registrados).

    Pasta correta: `editorPDF/<usuario>/` via `pasta_usuario()` (nunca a raiz
    `editorPDF/`). Ao final remove resíduos não registrados (ZIPs) varrendo a
    pasta do usuário, garantindo estorno da cota e sem órfãos."""
    conn = _conn()
    if conn is None:
        _falha_conexao("remover_vinculos_usuario")
        return 0, []
    try:
        cc = conn.cursor()
        cc.execute("SELECT nome_arquivo FROM tb_arquivos WHERE usuario=?", (user_nome,))
        nomes = [r[0] for r in cc.fetchall()]
        pasta = pasta_usuario(user_nome)
        if pasta is None:
            pasta = os.path.join(PASTA_EDITOR, user_nome)
        removidos = 0
        for nome in nomes:
            # Defesa: nunca escapar da pasta do usuário (basename).
            fpath = os.path.join(pasta, os.path.basename(nome))
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    removidos += 1
                except OSError:
                    pass
            cc.execute("DELETE FROM tb_arquivos WHERE usuario=? AND nome_arquivo=?",
                       (user_nome, nome))
        cc.execute("DELETE FROM tb_cota_disco WHERE usuario=?", (user_nome,))
        conn.commit()
        # Sem órfãos LGPD: remove resíduos não registrados (ex.: ZIPs de
        # download criados em disco sem registro em tb_arquivos) e a pasta.
        try:
            if os.path.isdir(pasta):
                for resto in os.listdir(pasta):
                    try:
                        os.remove(os.path.join(pasta, resto))
                    except OSError:
                        pass
                try:
                    shutil.rmtree(pasta, ignore_errors=True)
                except Exception:
                    pass
        except Exception as e:
            try:
                _lg = _log()
                if _lg is not None:
                    _lg.exception(f"remover_vinculos_usuario limpeza residual falhou: {e}")
            except Exception:
                pass
        return removidos, nomes
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"remover_vinculos_usuario falhou: {e}")
        except Exception:
            pass
        try:
            conn.rollback()
        except Exception:
            pass
        _notificar_falha("Falha ao remover dados do usuário no Editor de PDF.")
        return 0, []
    finally:
        _fechar_seguro(conn)


def renomear_usuario(nome_atual, novo_nome):
    """Propaga o renomeio para as colunas de usuário do módulo.

    Chamado pelo módulo de gestão de usuários: cada módulo atualiza o
    PRÓPRIO banco (isolamento total). Exceção propaga (fail-loud) e o
    chamador registra o aviso."""
    conn = _conn()
    if conn is None:
        _falha_conexao("renomear_usuario")
        raise RuntimeError("Banco do Editor de PDF indisponível (renomear_usuario)")
    try:
        cc = conn.cursor()
        cc.execute("UPDATE tb_arquivos SET usuario=? WHERE usuario=?", (novo_nome, nome_atual))
        cc.execute("UPDATE tb_cota_disco SET usuario=? WHERE usuario=?", (novo_nome, nome_atual))
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"renomear_usuario falhou: {e}")
        except Exception:
            pass
        raise
    finally:
        _fechar_seguro(conn)


def contar_arquivos_ativos():
    """Counts the module's active files (used in main.py summary).

    Conta arquivos ativos do módulo (usado no Resumo do main.py)."""
    conn = _conn()
    if conn is None:
        _falha_conexao("contar_arquivos_ativos")
        return 0
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_arquivos WHERE ativo=1")
        return cur.fetchone()[0]
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"contar_arquivos_ativos falhou: {e}")
        except Exception:
            pass
        return 0
    finally:
        _fechar_seguro(conn)


init_db_pdf()


def expirar_antigos(minutos=None):
    """Expiração automática (roda sem usuário logado — basta o servidor vivo).

    Remove do disco PDFs com mtime > N min, INATIVA seus registros na
    tb_arquivos e devolve a cota dos usuários. Retorna total inativado.
    minutos=None usa a configuração editar_pdf_expiracao_min.
    """
    try:
        if minutos is None:
            minutos = cfg_expiracao_min()
        if not os.path.isdir(PASTA_EDITOR):
            return 0
        agora = time.time()
        usuarios_tocados = set()
        for root, _dirs, files in os.walk(PASTA_EDITOR):
            for f in files:
                caminho = os.path.join(root, f)
                try:
                    if agora - os.path.getmtime(caminho) > minutos * 60:
                        os.remove(caminho)
                        usuarios_tocados.add(os.path.basename(os.path.dirname(caminho)))
                except Exception:
                    try:
                        _lg = _log()
                        if _lg is not None:
                            _lg.debug(f"falha ao verificar/expirar arquivo: {caminho}")
                    except Exception:
                        pass
        if not usuarios_tocados:
            return 0

        conn = _conn()
        if conn is None:
            _falha_conexao("expirar_antigos")
            return 0
        try:
            cur = conn.cursor()
            total_inativados = 0
            for usuario in usuarios_tocados:
                pasta = pasta_usuario(usuario)
                if pasta is None:
                    continue
                cur.execute(
                    "SELECT id, nome_arquivo, tamanho_bytes FROM tb_arquivos WHERE usuario=? AND ativo=1",
                    (usuario,),
                )
                ids, liberar = [], 0
                for _id, nome, tam in cur.fetchall():
                    if not os.path.exists(os.path.join(pasta, nome)):
                        ids.append(_id)
                        liberar += tam
                if not ids:
                    continue
                marks = ",".join("?" for _ in ids)
                cur.execute(f"UPDATE tb_arquivos SET ativo=0 WHERE id IN ({marks})", ids)  # nosec B608 — marks de lista de IDs, não input usuário
                cur.execute(
                    """UPDATE tb_cota_disco SET total_usado_bytes = MAX(0, total_usado_bytes - ?),
                       atualizado_em = datetime('now') WHERE usuario=?""",
                    (liberar, usuario),
                )
                total_inativados += len(ids)
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                _lg = _log()
                if _lg is not None:
                    _lg.exception(f"expirar_antigos DB falhou: {e}")
            except Exception:
                pass
            return 0
        finally:
            _fechar_seguro(conn)

        if total_inativados:
            try:
                _lg = _log()
                if _lg is not None:
                    _lg.info(f"expiracao: {total_inativados} arquivo(s) removidos "
                             f"automaticamente (> {minutos} min)")
            except Exception:
                pass
            try:
                from mod_intranet.bd_manipulador import audit_log
                audit_log("sistema", "edit-pdf", "expiracao",
                          f"{total_inativados} arquivo(s) removidos automaticamente (> {minutos} min)")
            except Exception:
                pass
        return total_inativados
    except Exception as e:
        try:
            _lg = _log()
            if _lg is not None:
                _lg.exception(f"expirar_antigos falhou: {e}")
        except Exception:
            pass
        return 0
