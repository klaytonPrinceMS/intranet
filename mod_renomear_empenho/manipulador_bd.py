"""Módulo Renomear Empenhos — monitor de pasta, regex dinâmicas, quarentena,
renomeação sequencial e organizador físico (~200 págs/pasta, 4 pastas/caixa)."""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import shutil
import io
from datetime import datetime

from mod_intranet.conexao_bd import get_connection, get_config
from mod_intranet.manipulador_bd import audit_log, hash_arquivo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("renomear_empenho")
DB_EMPENHO_PATH = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")
PASTA_ORGANIZADOR = os.path.join(BASE_DIR, "organizadorPasta")
PASTA_QUARENTENA = os.path.join(BASE_DIR, "quarentena")
_PASTA_MONITORADA_PADRAO = os.path.join(BASE_DIR, "doc")
PASTA_MONITORADA = _PASTA_MONITORADA_PADRAO


def pasta_monitorada():
    """Pasta monitorada pelo módulo; editável em tb_config na chave
    'empenhos_pasta_monitorada' (painel Administração) sem reiniciar."""
    try:
        v = (get_config("empenhos_pasta_monitorada", "") or "").strip()
        if v:
            return v if os.path.isabs(v) else os.path.normpath(os.path.join(BASE_DIR, v))
    except Exception as e:
        _log().warning(f"falha ao ler pasta monitorada de tb_config: {e}")
    return PASTA_MONITORADA

REGEX_PADRAO = r"(?:empenho|emp|ne)[\s\.: nº]*(\d{4,10})(?:[-/](\d{1,3}))?"
NOME_FINAL_PADRAO = "doc_{contador:04d}_numEmpenho_{empenho}_p{parcela:03d}.pdf"
PAGINAS_EXTRACAO = 3

# Colunas do índice FTS5 (RF-41) — cabeçalho do empenho (>=30 campos) + campos
# customizados extraídos por regex dinâmico (via tb_regex_regras.campo_destino).
FTS_COLS = [
    "nome_arquivo_original", "nome_arquivo_final", "numero_empenho", "parcela",
    "usuario", "data_criacao", "status", "caminho_arquivo",
    "pagador", "cpf_cnpj", "orgao", "valor", "data_emissao", "data_vencimento",
    "modalidade", "processo", "dotacao", "favorecido", "cnpj_favorecido",
    "endereco", "municipio", "uf", "cep", "telefone", "email", "observacao",
    "texto_extraido", "campos_regex", "hash_arquivo", "tags", "conteudo_texto", "nota_interna",
]


def _conn():
    conn = sqlite3.connect(DB_EMPENHO_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_empenho():
    os.makedirs(_PASTA_MONITORADA_PADRAO, exist_ok=True)
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_empenhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo_original TEXT,
            nome_arquivo_final TEXT NOT NULL,
            numero_empenho INTEGER,
            parcela INTEGER DEFAULT 1,
            usuario TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ativo',
            caminho_arquivo TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenho_numero ON tb_empenhos(numero_empenho)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_indexador_pesquisa (
            empenho_id INTEGER PRIMARY KEY,
            conteudo_texto TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_quarentena (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT NOT NULL,
            motivo TEXT,
            caminho_atual TEXT,
            data_insercao DATETIME DEFAULT CURRENT_TIMESTAMP,
            processado INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_regex_regras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_regra TEXT NOT NULL UNIQUE,
            padrao_regra TEXT NOT NULL,
            substituicao TEXT,
            ativo INTEGER DEFAULT 1,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_regex_regras")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO tb_regex_regras (nome_regra, padrao_regra) VALUES (?, ?)",
            ("Padrão Empenho", REGEX_PADRAO),
        )
        cur.execute(
            "INSERT INTO tb_regex_regras (nome_regra, padrao_regra) VALUES (?, ?)",
            ("Só números", r"(\d{6,10})"),
        )

    # FTS5 — índice de busca full-text (RF-41): cabeçalho do empenho (>=30 campos).
    cur.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS tb_indexador_pesquisa_fts5 USING fts5("
        + ", ".join(FTS_COLS) + ")"
    )
    # Campo de destino dinâmico nas regras regex (alimenta colunas FTS customizadas).
    try:
        cur.execute("ALTER TABLE tb_regex_regras ADD COLUMN campo_destino TEXT")
    except Exception:
        pass  # coluna já existe em bancos previamente criados
    # Trigger: remove o índice FTS ao excluir o empenho.
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS tr_fts_del_empenho
        AFTER DELETE ON tb_empenhos
        BEGIN
            DELETE FROM tb_indexador_pesquisa_fts5 WHERE rowid = old.id;
        END
    """)
    conn.commit()
    conn.close()


# ================= TEXTO / EXTRAÇÃO =================

def extrair_texto_pdf(caminho):
    """Extrai texto das primeiras páginas.

    Pipeline tolerante a PDFs escaneados:
        pymupdf → pdfplumber → OCR(pytesseract) → pikepdf(metadados) → pymupdf(imagens)
    Cada etapa só avança para a próxima se não produzir texto. PDFs escaneados
    sem camada de texto são reconhecidos via OCR (pytesseract) em vez de irem
    direto para a quarentena.
    """
    # 1) pymupdf (camada de texto nativa)
    try:
        import pymupdf
        doc = pymupdf.open(caminho)
        texto = "\n".join(doc[i].get_text() for i in range(min(PAGINAS_EXTRACAO, len(doc))))
        doc.close()
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pymupdf falhou para {caminho}: {e}")

    # 2) pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages[:PAGINAS_EXTRACAO])
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pdfplumber falhou para {caminho}: {e}")

    # 3) OCR com pytesseract (PDFs escaneados)
    try:
        import pytesseract
        from PIL import Image
        import pymupdf as fitz
        doc = fitz.open(caminho)
        paginas = []
        for i in range(min(PAGINAS_EXTRACAO, len(doc))):
            pix = doc[i].get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            paginas.append(pytesseract.image_to_string(img, lang="por+eng"))
        doc.close()
        texto = "\n".join(paginas)
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: OCR pytesseract falhou para {caminho}: {e}")

    # 4) pikepdf (metadados como último recurso)
    try:
        import pikepdf
        pdf = pikepdf.open(caminho)
        texto = " ".join(str(v) for v in pdf.docinfo.values() if v)
        pdf.close()
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pikepdf falhou para {caminho}: {e}")

    return ""


def extrair_numero(texto):
    """Aplica regras regex ativas. Retorna (numero, parcela) — (None,1) se não achar."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT padrao_regra FROM tb_regex_regras WHERE ativo=1 ORDER BY id")
        for (padrao,) in cur.fetchall():
            try:
                m = re.search(padrao, texto or "", re.IGNORECASE)
            except re.error:
                continue
            if m:
                num = int(m.group(1)) if m.group(1) else None
                parc = int(m.group(2)) if (m.lastindex or 0) >= 2 and m.group(2) and m.group(2).isdigit() else 1
                return num, parc
        # fallback: qualquer número longo no texto
        m = re.search(r"(\d{6,})", texto or "")
        if m:
            return int(m.group(1)), 1
        return None, 1
    finally:
        conn.close()


def _proximo_contador():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_empenhos WHERE status='ativo'")
        n = cur.fetchone()[0]
        # garante unicidade mesmo após exclusões
        cur.execute("SELECT MAX(CAST(SUBSTR(nome_arquivo_final, 5, 4) AS INTEGER)) FROM tb_empenhos")
        mx = cur.fetchone()[0] or 0
        return max(n + 1, mx + 1)
    finally:
        conn.close()


def processar_pdf(usuario, caminho_arquivo, numero=None, parcela=None, regex_custom=None):
    """Processa 1 PDF: extrai nº, renomeia, indexa e move. Retorna dict resultado.

    - Se `regex_custom` for informada, usa-a (case-insensitive) para capturar o nº.
    - Se `numero` for informado, pula a extração e usa o valor.
    """
    nome_original = os.path.basename(caminho_arquivo)
    texto = extrair_texto_pdf(caminho_arquivo)

    if not texto.strip():
        _log().warning(f"processar_pdf: sem texto legível em {nome_original}")
        mover_quarentena(usuario, caminho_arquivo, "PDF sem texto legível (possivelmente escaneado)")
        return {"ok": False, "motivo": "sem texto"}

    if numero is None:
        if regex_custom:
            m = None
            try:
                m = re.search(regex_custom, texto or "", re.IGNORECASE)
            except re.error:
                m = None
            if m and m.group(1):
                numero = int(m.group(1))
                parcela = int(m.group(2)) if (m.lastindex or 0) >= 2 and m.group(2) and m.group(2).isdigit() else 1
            else:
                return {"ok": False, "motivo": "sem correspondência (regex informada)"}
        else:
            numero, parcela = extrair_numero(texto)

    if numero is None:
        _log().warning(f"processar_pdf: nº de empenho não encontrado em {nome_original}")
        mover_quarentena(usuario, caminho_arquivo, "Número de empenho não encontrado no conteúdo")
        return {"ok": False, "motivo": "sem numero"}

    contador = _proximo_contador()
    nome_final = NOME_FINAL_PADRAO.format(contador=contador, empenho=numero, parcela=parcela or 1)

    destino_dir = os.path.dirname(caminho_arquivo)
    destino = os.path.join(destino_dir, nome_final)
    try:
        os.rename(caminho_arquivo, destino)
    except OSError as e:
        _log().error(f"processar_pdf: falha ao renomear {nome_original}: {e}")
        mover_quarentena(usuario, caminho_arquivo, f"Falha ao renomear: {e}")
        return {"ok": False, "motivo": str(e)}

    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_empenhos
               (nome_arquivo_original, nome_arquivo_final, numero_empenho, parcela, usuario, caminho_arquivo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nome_original, nome_final, numero, parcela, usuario, destino),
        )
        eid = cur.lastrowid
        cur.execute(
            "INSERT OR REPLACE INTO tb_indexador_pesquisa (empenho_id, conteudo_texto) VALUES (?, ?)",
            (eid, f"{nome_original} {nome_final} {texto[:4000]}"),
        )
        conn.commit()
        reindexar_empenho(eid)  # mantém o índice FTS5 em sincronia (RF-41)
        hash_arq = hash_arquivo(destino)
        audit_log(usuario, "renomear-empenho", "processar",
                  f"{nome_original} → {nome_final} (empenho {numero}, parcela {parcela})",
                  hash_arquivo=hash_arq)
        _log().info(f"empenho {numero} (parcela {parcela}) processado: {nome_final}")
        return {"ok": True, "id": eid, "nome": nome_final, "numero": numero, "parcela": parcela}
    except Exception as e:
        conn.rollback()
        _log().exception(f"processar_pdf: erro ao gravar {nome_original}")
        return {"ok": False, "motivo": str(e)}
    finally:
        conn.close()


def mover_quarentena(usuario, caminho_arquivo, motivo):
    os.makedirs(PASTA_QUARENTENA, exist_ok=True)
    nome = os.path.basename(caminho_arquivo)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    destino = os.path.join(PASTA_QUARENTENA, f"{stamp}_{nome}")
    try:
        shutil.move(caminho_arquivo, destino)
        caminho_atual = destino
    except Exception as e:
        _log().error(f"mover_quarentena: falha ao mover {nome}: {e}")
        caminho_atual = ""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_quarentena (nome_arquivo, motivo, caminho_atual) VALUES (?, ?, ?)",
            (nome, motivo[:300], caminho_atual),
        )
        conn.commit()
    finally:
        conn.close()
    hash_arq = hash_arquivo(destino) if destino and os.path.exists(destino) else None
    audit_log(usuario, "renomear-empenho", "quarentena", f"{nome}: {motivo[:120]}",
              hash_arquivo=hash_arq)


# ================= CONSULTAS =================

def listar_empenhos(status="ativo", limite=200):
    conn = _conn()
    try:
        cur = conn.cursor()
        sql = """SELECT id, nome_arquivo_original, nome_arquivo_final, numero_empenho,
                        parcela, usuario, data_criacao, caminho_arquivo
                 FROM tb_empenhos"""
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _fts_insert_sql():
    cols = ", ".join(FTS_COLS)
    placeholders = ", ".join("?" for _ in FTS_COLS)
    return f"INSERT INTO tb_indexador_pesquisa_fts5 (rowid, {cols}) VALUES (?, {placeholders})"


def _fts_escape(token):
    """Escapa aspas para uso seguro em frase FTS5 (aspas duplas duplicadas)."""
    return (token or "").replace('"', '""').strip()


def extrair_campos_regex(texto):
    """Aplica regras regex que possuem `campo_destino` definido e devolve
    dict {campo_destino: valor} — alimenta colunas FTS customizadas (RF-41)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT padrao_regra, campo_destino FROM tb_regex_regras "
            "WHERE ativo=1 AND campo_destino IS NOT NULL AND campo_destino <> ''"
        )
        regras = cur.fetchall()
    finally:
        conn.close()
    out = {}
    if not texto:
        return out
    for padrao, campo in regras:
        try:
            m = re.search(padrao, texto or "", re.IGNORECASE)
        except re.error:
            continue
        if m and m.group(1):
            out[campo] = m.group(1)
    return out


def reindexar_empenho(eid):
    """Reconstrói a linha FTS5 do empenho `eid` a partir de tb_empenhos +
    texto indexado + campos extraídos por regex dinâmico."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome_arquivo_original, nome_arquivo_final, numero_empenho, "
            "parcela, usuario, data_criacao, status, caminho_arquivo "
            "FROM tb_empenhos WHERE id=?", (eid,))
        row = cur.fetchone()
        if not row:
            return
        cur.execute("SELECT conteudo_texto FROM tb_indexador_pesquisa WHERE empenho_id=?", (eid,))
        idx = cur.fetchone()
        texto = idx[0] if idx else ""
        campos = extrair_campos_regex(texto)
        campos_json = json.dumps(campos, ensure_ascii=False)
        valores = {
            "nome_arquivo_original": row[1] or "",
            "nome_arquivo_final": row[2] or "",
            "numero_empenho": str(row[3] or ""),
            "parcela": str(row[4] or ""),
            "usuario": row[5] or "",
            "data_criacao": (row[6] or "")[:19],
            "status": row[7] or "",
            "caminho_arquivo": row[8] or "",
            "texto_extraido": texto,
            "campos_regex": campos_json,
            "conteudo_texto": f"{texto} " + " ".join(f"{k}:{v}" for k, v in campos.items()),
        }
        vals = [valores.get(c, "") for c in FTS_COLS]
        cur.execute("DELETE FROM tb_indexador_pesquisa_fts5 WHERE rowid=?", (eid,))
        cur.execute(_fts_insert_sql(), [eid] + vals)
        conn.commit()
    finally:
        conn.close()


def rebuild_fts():
    """Reconstrói todo o índice FTS5 (usado na 1ª busca se estiver vazio)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_empenhos")
        ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    for eid in ids:
        reindexar_empenho(eid)
    return len(ids)


def pesquisar(termo, limite=50):
    """Busca full-text via FTS5 (RF-41). Fallback para LIKE se o FTS falhar."""
    if not termo or not termo.strip():
        return []
    tokens = [t for t in termo.strip().split() if t]
    if not tokens:
        return []
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_indexador_pesquisa_fts5")
        if cur.fetchone()[0] == 0:
            rebuild_fts()
        query = " AND ".join(f'"{_fts_escape(t)}"' for t in tokens)
        try:
            cur.execute(
                """SELECT e.id, e.nome_arquivo_final, e.numero_empenho, e.parcela,
                          e.usuario, e.data_criacao, e.caminho_arquivo
                   FROM tb_indexador_pesquisa_fts5 f
                   JOIN tb_empenhos e ON e.id = f.rowid
                   WHERE tb_indexador_pesquisa_fts5 MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limite),
            )
            return cur.fetchall()
        except Exception as e:
            _log().warning(f"pesquisar FTS5 falhou, fallback LIKE: {e}")
            like = f"%{termo.strip()}%"
            cur.execute(
                """SELECT e.id, e.nome_arquivo_final, e.numero_empenho, e.parcela,
                          e.usuario, e.data_criacao, e.caminho_arquivo
                   FROM tb_indexador_pesquisa i
                   JOIN tb_empenhos e ON e.id = i.empenho_id
                   WHERE i.conteudo_texto LIKE ?
                   ORDER BY e.id DESC LIMIT ?""",
                (like, limite),
            )
            return cur.fetchall()
    finally:
        conn.close()


def listar_quarentena(limite=100):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nome_arquivo, motivo, data_insercao, processado, caminho_atual
               FROM tb_quarentena ORDER BY id DESC LIMIT ?""",
            (limite,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def reprocesse_quarentena(qid, novo_padrao=None, usuario="sistema"):
    """Reprocessa item da quarentena aplicando a regex informada (ou as regras ativas)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo, caminho_atual FROM tb_quarentena WHERE id=?", (qid,))
        row = cur.fetchone()
        if not row or not row[1] or not os.path.exists(row[1]):
            _log().warning(f"reprocesse_quarentena: item {qid} indisponível")
            return False, "Arquivo indisponível"
    finally:
        conn.close()

    res = processar_pdf(usuario, row[1], regex_custom=novo_padrao)
    if res.get("ok"):
        c = _conn()
        try:
            cc = c.cursor()
            cc.execute("UPDATE tb_quarentena SET processado=1 WHERE id=?", (qid,))
            c.commit()
        finally:
            c.close()
        return True, res["nome"]
    return False, res.get("motivo", "?")


# ================= REGRAS =================

def salvar_regra(nome, padrao, ativo=True, campo_destino=None):
    try:
        re.compile(padrao)  # valida antes de salvar
    except re.error as e:
        return False, f"Regex inválida: {e}"
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_regex_regras (nome_regra, padrao_regra, ativo, campo_destino)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(nome_regra) DO UPDATE SET padrao_regra=?, ativo=?, campo_destino=?""",
            (nome, padrao, 1 if ativo else 0, campo_destino,
             padrao, 1 if ativo else 0, campo_destino),
        )
        conn.commit()
        return True, "Regra salva (aplicada imediatamente, sem reiniciar)"
    finally:
        conn.close()


def listar_regras():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome_regra, padrao_regra, ativo, campo_destino "
            "FROM tb_regex_regras ORDER BY id")
        return cur.fetchall()
    finally:
        conn.close()


def alternar_regra(rid, ativo):
    """Ativa (1) ou inativa (0) uma regra regex. Retorna (ok, msg)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_regex_regras SET ativo=? WHERE id=?", (1 if ativo else 0, rid))
        conn.commit()
        return True, "Regra " + ("ativada" if ativo else "inativada")
    except Exception as e:
        _log().error(f"alternar_regra: erro ao alternar regra {rid}: {e}")
        return False, f"Erro: {e}"
    finally:
        conn.close()


def listar_regras_padrao(rid):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT padrao_regra FROM tb_regex_regras WHERE id=?", (rid,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ================= MONITOR E ORGANIZADOR =================

def rodar_monitor(usuario="sistema"):
    """Varre pasta monitorada processando todos os PDFs pendentes."""
    pasta = pasta_monitorada()
    if not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
        return []
    _log().info(f"monitor iniciado em {pasta} (usuário {usuario})")
    resultados = []
    for f in sorted(os.listdir(pasta)):
        if f.lower().endswith(".pdf"):
            caminho = os.path.join(pasta, f)
            try:
                resultados.append(processar_pdf(usuario, caminho))
            except Exception as e:
                _log().exception(f"rodar_monitor: erro ao processar {f}")
                resultados.append({"ok": False, "motivo": str(e), "arquivo": f})
    return resultados


def organizar_pastas():
    """Organiza PDFs: ~200 páginas por subpasta, 4 subpastas por caixa.

    Estrutura: organizadorPasta/caixa_N/sub_X/doc_*.pdf
    Retorna (ok, msg).
    """
    import pymupdf
    os.makedirs(PASTA_ORGANIZADOR, exist_ok=True)
    movidos, erros = 0, 0
    paginas_por_pasta = 200
    pastas_por_caixa = 4

    paginas_acum = 0
    sub_atual = 1
    caixa_atual = 1
    for row in listar_empenhos(status="ativo", limite=5000):
        _id, _orig, final, _num, _parc, _user, _dt, caminho = row
        if not caminho or not os.path.exists(caminho):
            continue
        try:
            doc = pymupdf.open(caminho)
            n_paginas = len(doc)
            doc.close()
        except Exception as e:
            _log().warning(f"organizar_pastas: não abriu {caminho}: {e}")
            n_paginas = 1

        # fecha a subpasta ao ultrapassar o limite de páginas por pasta
        if paginas_acum + n_paginas > paginas_por_pasta:
            paginas_acum = 0
            sub_atual += 1
            if sub_atual > pastas_por_caixa:
                sub_atual = 1
                caixa_atual += 1

        dir_caixa = os.path.join(PASTA_ORGANIZADOR, f"caixa_{caixa_atual:02d}")
        dir_sub = os.path.join(dir_caixa, f"sub_{sub_atual}")
        os.makedirs(dir_sub, exist_ok=True)

        destino = os.path.join(dir_sub, final)
        try:
            shutil.move(caminho, destino)
            c = _conn(); cc = c.cursor()
            cc.execute("UPDATE tb_empenhos SET caminho_arquivo=? WHERE id=?", (destino, _id))
            c.commit(); c.close()
            movidos += 1
            paginas_acum += n_paginas
        except Exception as e:
            _log().error(f"organizar_pastas: falha ao mover {final}: {e}")
            erros += 1

    _log().info(f"organizar_pastas: {movidos} organizado(s), {erros} erro(s)")
    # RF-44: gera capas por caixa + matrizDeDocumentos (txt/pdf) ao final da organização
    try:
        ok_m, msg_m = gerar_matriz_organizador()
        if ok_m:
            _log().info(f"organizar_pastas: {msg_m}")
            return True, f"{movidos} arquivo(s) organizado(s), {erros} erro(s). {msg_m}"
    except Exception:
        _log().exception("organizar_pastas: falha ao gerar matriz/capas")
    return True, f"{movidos} arquivo(s) organizado(s), {erros} erro(s)"


# ================= ORGANIZADOR FÍSICO COMPLETO (RF-44) =================
def _inventario_organizador():
    """Lista por caixa as subpastas e seus documentos PDF."""
    itens = []
    if not os.path.isdir(PASTA_ORGANIZADOR):
        return itens
    for caixa in sorted(os.listdir(PASTA_ORGANIZADOR)):
        dir_c = os.path.join(PASTA_ORGANIZADOR, caixa)
        if not os.path.isdir(dir_c):
            continue
        subs = []
        for sub in sorted(os.listdir(dir_c)):
            dir_s = os.path.join(dir_c, sub)
            if not os.path.isdir(dir_s):
                continue
            docs = [f for f in sorted(os.listdir(dir_s)) if f.lower().endswith(".pdf")]
            subs.append((sub, docs))
        itens.append((caixa, subs))
    return itens


def _gerar_pdf_texto(conteudo, caminho):
    import pymupdf
    doc = pymupdf.open()
    pag = doc.new_page()
    pag.insert_text((40, 40), conteudo, fontname="helv", fontsize=10)
    doc.save(caminho, garbage=4, deflate=True)
    doc.close()


def gerar_matriz_organizador():
    """Gera capa por caixa + `matrizDeDocumentos.txt`/`.pdf` (RF-44). Retorna (ok, msg)."""
    inv = _inventario_organizador()
    if not inv:
        return False, "Nada organizado ainda."
    linhas = ["MATRIZ DE DOCUMENTOS - Renomeador de Empenhos", "=" * 60]
    total = 0
    for caixa, subs in inv:
        linhas.append(f"\nCAIXA {caixa}")
        capa_caixa = []
        for sub, docs in subs:
            linhas.append(f"  {sub}: {len(docs)} doc(s)")
            capa_caixa.append(f"{sub}: {len(docs)} doc(s) -> " + ", ".join(docs))
            total += len(docs)
        try:
            with open(os.path.join(PASTA_ORGANIZADOR, caixa, "capa.txt"), "w", encoding="utf-8") as f:
                f.write(f"CAPA DA CAIXA {caixa}\n" + "\n".join(capa_caixa) + "\n")
        except Exception:
            _log().warning(f"gerar_matriz: falha ao gravar capa de {caixa}")
    linhas.append(f"\nTOTAL DE DOCUMENTOS: {total}")
    texto = "\n".join(linhas)
    try:
        with open(os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.txt"), "w", encoding="utf-8") as f:
            f.write(texto)
        _gerar_pdf_texto(texto, os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.pdf"))
        return True, f"Matriz gerada ({total} documentos)."
    except Exception as e:
        _log().exception("gerar_matriz: falha ao gravar matriz")
        return False, str(e)


def validar_presenca_matriz():
    """Valida que todos os PDFs listados na matriz existem no disco (RF-44).
    Retorna (ok, faltando)."""
    import re
    path = os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.txt")
    if not os.path.exists(path):
        return False, ["matrizDeDocumentos.txt ausente - gere a matriz primeiro"]
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    faltando = []
    for m in re.findall(r"(\S+\.pdf)", txt):
        achou = False
        for raiz, _, arq in os.walk(PASTA_ORGANIZADOR):
            if m in arq:
                achou = True
                break
        if not achou:
            faltando.append(m)
    return (len(faltando) == 0), faltando


# ================= FERRAMENTAS DE PDF (RF-45) =================
# Saídas em pastas específicas, reutilizando as operações do mod_edit_pdf.
PASTA_MERGE = os.path.join(BASE_DIR, "datahora_mergePDF")
PASTA_CORTE = os.path.join(BASE_DIR, "datahora_cortePDF")
PASTA_REDUCAO = os.path.join(BASE_DIR, "datahora_reducaoPDF")
PASTA_TEMP_FERR = os.path.join(BASE_DIR, "tmp_ferramentas_pdf")


def _ferramenta_nome(base, sufixo):
    from datetime import datetime as _dt
    return f"{_dt.now():%Y%m%d%H%M%S}_{base}{sufixo}"


def ferramenta_cortar(caminho_in, filtro, usuario="sistema"):
    """Corta um PDF (pares/ímpares/intervalo) usando o motor do mod_edit_pdf.
    Retorna (ok, caminho_ou_msg)."""
    if not caminho_in or not os.path.exists(caminho_in):
        return False, "Arquivo de entrada inexistente"
    os.makedirs(PASTA_CORTE, exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho_in))[0]
    destino = os.path.join(PASTA_CORTE, _ferramenta_nome(base, "_corte.pdf"))
    try:
        from mod_edit_pdf.manipulador_bd import op_cortar
        ok, res = op_cortar(caminho_in, filtro, PASTA_CORTE,
                            os.path.basename(destino)[:-4])
        if ok:
            audit_log(usuario, "renomear-empenho", "ferramenta_corte",
                      f"{os.path.basename(caminho_in)} -> {os.path.basename(res)} (filtro={filtro})",
                      hash_arquivo=hash_arquivo(res))
            return True, res
        return False, res
    except Exception as e:
        _log().exception(f"ferramenta_cortar falhou para {caminho_in}")
        return False, str(e)


def ferramenta_juntar(caminhos_in, usuario="sistema"):
    """Mescla múltiplos PDFs em um único arquivo. Retorna (ok, caminho_ou_msg)."""
    caminhos = [c for c in (caminhos_in or []) if c and os.path.exists(c)]
    if len(caminhos) < 2:
        return False, "Selecione ao menos 2 PDFs válidos para mesclar"
    os.makedirs(PASTA_MERGE, exist_ok=True)
    destino = os.path.join(PASTA_MERGE, _ferramenta_nome("merge", ".pdf"))
    try:
        from mod_edit_pdf.manipulador_bd import op_juntar
        ok, msg = op_juntar(caminhos, destino)
        if ok and os.path.exists(destino):
            audit_log(usuario, "renomear-empenho", "ferramenta_juntar",
                      f"{len(caminhos)} arquivo(s) -> {os.path.basename(destino)}",
                      hash_arquivo=hash_arquivo(destino))
            return True, destino
        return False, msg
    except Exception as e:
        _log().exception("ferramenta_juntar falhou")
        return False, str(e)


def ferramenta_reduzir(caminho_in, usuario="sistema", qualidade=50, modo="leve", dpi=None):
    """Reduz o tamanho de um PDF. Retorna (ok, caminho_ou_msg)."""
    if not caminho_in or not os.path.exists(caminho_in):
        return False, "Arquivo de entrada inexistente"
    os.makedirs(PASTA_REDUCAO, exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho_in))[0]
    destino = os.path.join(PASTA_REDUCAO, _ferramenta_nome(base, "_reducao.pdf"))
    try:
        from mod_edit_pdf.manipulador_bd import op_reduzir
        ok, msg = op_reduzir(caminho_in, destino, qualidade=qualidade, modo=modo, dpi=dpi)
        if ok and os.path.exists(destino):
            audit_log(usuario, "renomear-empenho", "ferramenta_reducao",
                      f"{os.path.basename(caminho_in)} -> {os.path.basename(destino)} "
                      f"(modo={modo} q{qualidade})",
                      hash_arquivo=hash_arquivo(destino))
            return True, destino
        return False, msg
    except Exception as e:
        _log().exception(f"ferramenta_reduzir falhou para {caminho_in}")
        return False, str(e)


def ferramenta_fontes(usuario="sistema"):
    """Lista fontes disponíveis: empenhos processados (caminho_arquivo)."""
    return [(r[0], r[2], r[7]) for r in listar_empenhos(status="ativo", limite=1000)
            if r[7] and os.path.exists(r[7])]


init_db_empenho()
