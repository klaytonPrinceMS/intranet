"""Módulo Editor de PDF — BD próprio, cotas, operações e limpeza automática.

Arquivos ficam em /editorPDF/<usuario>/ com prefixo:
  dataHora_usuario_operacao_nomeOriginal.pdf
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import zipfile
from datetime import datetime

from mod_intranet.conexao_bd import get_connection, get_config
from mod_intranet.manipulador_bd import audit_log


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("edit_pdf")


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PDF_PATH = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")
PASTA_EDITOR = os.path.join(BASE_DIR, "editorPDF")

QUOTA_GLOBAL_BYTES_DEFAULT = 10 * 1024**3   # 10 GB
QUOTA_USUARIO_BYTES = 1 * 1024**3           # 1 GB por usuário (legado; usar cfg_usuario_gb)


# ============ CONFIGURAÇÕES DINÂMICAS (tb_config central, prefixo editpdf_) ============

def _cfg(chave, default):
    try:
        return get_config(f"editpdf_{chave}", str(default))
    except Exception:
        return str(default)


def cfg_lote_arquivos():
    """Máximo de arquivos por lote de upload."""
    try:
        return max(1, int(_cfg("lote_arquivos", 10)))
    except ValueError:
        return 10


def cfg_lote_mb():
    """Máximo de MB por lote de upload."""
    try:
        return max(1, int(_cfg("lote_mb", 1024)))
    except ValueError:
        return 1024


def cfg_usuario_gb():
    """Cota de disco por usuário (GB)."""
    try:
        return max(1, int(_cfg("usuario_gb", 1)))
    except ValueError:
        return 1


def cfg_expiracao_min():
    """Minutos de vida dos arquivos no editorPDF."""
    try:
        return max(1, int(_cfg("expiracao_min", 10)))
    except ValueError:
        return 10


# ============ TEMA (cores/tamanhos padronizados dos botões, abas e fundo) ============

def cfg_tema(chave, default):
    """Lê uma chave de tema ('cor_botao', 'cor_texto_botao', …) de tb_config."""
    try:
        return (_cfg(chave, default) or "").strip() or default
    except Exception:
        return default


def _conn():
    conn = sqlite3.connect(DB_PDF_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_pdf():
    conn = _conn()
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
    conn.close()

    _semear_versao_modulo()


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
            ("versao_modulo:editar_pdf", "1.0.260827"))
        conn.commit()
        conn.close()
    except Exception:
        _log().exception("falha ao semear versão do módulo editar_pdf")

def pasta_usuario(usuario):
    p = os.path.join(PASTA_EDITOR, usuario)
    os.makedirs(p, exist_ok=True)
    return p


def uso_global_bytes():
    """Uso REAL em disco do diretório editorPDF (todos os usuários)."""
    total = 0
    if os.path.isdir(PASTA_EDITOR):
        for root, _dirs, files in os.walk(PASTA_EDITOR):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return total


def nome_padronizado(usuario, operacao, nome_original):
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    seguro = "".join(c for c in (nome_original or "arquivo") if c.isalnum() or c in "._- ")[:60].strip()
    return f"{stamp}_{usuario}_{operacao}_{seguro}"


def _cota_global_bytes():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT CAST(valor AS INTEGER) FROM tb_config WHERE chave='cotadisco_global_gb'")
        row = cur.fetchone()
        conn.close()
        if row:
            return int(row[0]) * 1024**3
    except Exception:
        _log().exception("falha ao ler cota global de disco")
    return QUOTA_GLOBAL_BYTES_DEFAULT


def verificar_quota(usuario, tamanho_bytes):
    """Retorna (ok: bool, msg)."""
    conn = _conn()
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
    finally:
        conn.close()


def registrar_arquivo(usuario, caminho_fisico, operacao, tamanho_bytes=None):
    """Registra arquivo existente no disco e atualiza cota. Retorna id ou None."""
    if not os.path.isfile(caminho_fisico):
        return None
    if tamanho_bytes is None:
        tamanho_bytes = os.path.getsize(caminho_fisico)
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
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_arquivos (nome_arquivo, usuario, tamanho_bytes, operacao) VALUES (?, ?, ?, ?)",
            (nome, usuario, tamanho_bytes, operacao),
        )
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
        audit_log(usuario, "edit-pdf", operacao, f"Arquivo {nome} ({tamanho_bytes} bytes)")
        _log().info(f"arquivo registrado: {nome} usuario={usuario} operacao={operacao}")
        return cur.lastrowid
    finally:
        conn.close()


def ui_notify_erro(msg):  # isolado para não acoplar UI na lógica
    print(f"[quota] {msg}")
    _log().error(f"[quota] {msg}")


def obter_meus_arquivos(usuario):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nome_arquivo, tamanho_bytes, operacao, data_operacao
               FROM tb_arquivos WHERE usuario=? AND ativo=1 ORDER BY id DESC""",
            (usuario,),
        )
        rows = []
        for r in cur.fetchall():
            path = os.path.join(pasta_usuario(usuario), r[1])
            if not os.path.exists(path):  # arquivo já limpo pelo scheduler
                continue
            rows.append(r)
        return rows
    finally:
        conn.close()


def contar_uploads_ativos(usuario):
    """Arquivos tipo 'upload' REALMENTE presentes no espaço do usuário."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT nome_arquivo FROM tb_arquivos
               WHERE usuario=? AND operacao='upload' AND ativo=1""",
            (usuario,),
        )
        nomes = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    pasta = pasta_usuario(usuario)
    return sum(1 for n in nomes if os.path.exists(os.path.join(pasta, n)))


# ================= OPERAÇÕES =================

def hash_sha256(caminho):
    """SHA-256 de um arquivo (leitura em blocos)."""
    import hashlib
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def op_reduzir(caminho_in, caminho_out, qualidade=50, dpi=None, modo="leve", biblioteca="auto"):
    """Reduz o tamanho do PDF.

    modo 'leve': recompressão de streams — biblioteca 'auto' (pymupdf→pikepdf→pypdf)
                 ou fixa ('pymupdf'|'pikepdf'|'pypdf').
    modo 'agressivo': rasteriza cada página no DPI alvo como JPEG (qualidade 10-100),
                      sempre via pymupdf; texto vira imagem — ganho real de tamanho.
    Retorna (ok, msg).
    """
    qualidade = max(10, min(100, int(qualidade)))
    if str(modo).lower() == "agressivo":
        return _reduzir_agressivo(caminho_in, caminho_out, qualidade, dpi)
    return _reduzir_leve(caminho_in, caminho_out, biblioteca)


def _reduzir_leve(caminho_in, caminho_out, biblioteca):
    ordem = {
        "pymupdf": ["pymupdf"],
        "pikepdf": ["pikepdf"],
        "pypdf": ["pypdf"],
    }.get(str(biblioteca).lower(), ["pymupdf", "pikepdf", "pypdf"])
    erros = []
    for lib in ordem:
        try:
            if lib == "pymupdf":
                import pymupdf
                doc = pymupdf.open(caminho_in)
                doc.save(caminho_out, garbage=4, deflate=True, deflate_images=True,
                         deflate_fonts=True, clean=True)
                doc.close()
            elif lib == "pikepdf":
                import pikepdf
                with pikepdf.open(caminho_in) as pdf:
                    pdf.save(caminho_out, compress_streams=True,
                             object_stream_mode=pikepdf.ObjectStreamMode.generate)
            elif lib == "pypdf":
                from pypdf import PdfWriter
                escritor = PdfWriter(clone_from=caminho_in)
                for pagina in escritor.pages:
                    try:
                        pagina.compress_content_streams(level=9)
                    except Exception:
                        pass
                escritor.compress_identical_objects(remove_duplicates=True,
                                                    remove_orphans=True)
                with open(caminho_out, "wb") as f:
                    escritor.write(f)
            else:
                continue
            if os.path.isfile(caminho_out):
                return True, f"OK ({lib})"
        except Exception as ex:
            erros.append(f"{lib}: {ex}")
    _log().error(f"falha ao reduzir (leve) {caminho_in}: " +
                 (" | ".join(erros) or "nenhuma biblioteca disponível"))
    return False, " | ".join(erros) or "nenhuma biblioteca disponível"


def _reduzir_agressivo(caminho_in, caminho_out, qualidade, dpi):
    try:
        import pymupdf
        dpi = max(50, min(400, int(dpi or 150)))
        doc = pymupdf.open(caminho_in)
        novo = pymupdf.open()
        for pagina in doc:
            pix = pagina.get_pixmap(dpi=dpi)
            img = pix.tobytes("jpeg", jpg_quality=qualidade)
            ret = pagina.rect
            folha = novo.new_page(width=ret.width, height=ret.height)
            folha.insert_image(ret, stream=img)
        novo.save(caminho_out, garbage=4, deflate=True)
        novo.close()
        doc.close()
        return True, f"OK (agressivo {dpi}dpi q{qualidade})"
    except Exception as e:
        _log().exception(f"falha ao reduzir (agressivo) {caminho_in}")
        return False, f"agressivo: {e}"


def op_juntar(caminhos_in, caminho_out):
    """Une SOMENTE os arquivos PDF válidos; ignora e REPORTA os demais
    (ex.: ZIPs ou corrompidos misturados na seleção).

    Retorna (ok, msg) — msg lista os ignorados quando houver.
    """
    import pymupdf
    validos, problemas = [], []
    for c in caminhos_in:
        base = os.path.basename(c)
        if not str(c).lower().endswith(".pdf"):
            problemas.append(f"'{base}': não é PDF")
            continue
        try:
            doc = pymupdf.open(c)
            n = len(doc)
            doc.close()
        except Exception as ex:
            problemas.append(f"'{base}': ilegível ({ex})")
            continue
        if n <= 0:
            problemas.append(f"'{base}': sem páginas")
            continue
        validos.append(c)

    if len(validos) < 2:
        motivo = ("; ".join(problemas)) or "menos de 2 PDFs válidos"
        return False, f"Nada para juntar ({motivo})"

    try:
        saida = pymupdf.open()
        for c in validos:
            src = pymupdf.open(c)
            saida.insert_pdf(src)
            src.close()
        saida.save(caminho_out, garbage=4, deflate=True)
        saida.close()
        msg = f"OK ({len(validos)} unidos)"
        if problemas:
            msg += " — IGNORADOS: " + "; ".join(problemas)
        _log().info(f"juncao: {len(validos)} arquivo(s) unido(s)" +
                    (f" | ignorados: {'; '.join(problemas)}" if problemas else ""))
        return True, msg
    except Exception as e:
        _log().exception(f"falha ao juntar PDFs -> {caminho_out}")
        return False, str(e)


def _paginas_de_filtro(filtro, total):
    """Converte '2-5,8' (ou 'todas') em set de páginas 1-based válidas."""
    selecionadas = set()
    if isinstance(filtro, str) and filtro.strip().lower() in ("all", "todas", ""):
        return set(range(1, total + 1))
    for parte in str(filtro).split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            a, b = parte.split("-", 1)
            try:
                ini, fim = int(a), int(b)
            except ValueError:
                continue
            selecionadas.update(range(max(1, ini), min(total, fim) + 1))
        elif parte.isdigit():
            p = int(parte)
            if 1 <= p <= total:
                selecionadas.add(p)
    return selecionadas


def op_dividir(caminho_in, paginas, pasta_saida, base_name):
    """Divide por páginas (lista 1-based) ou intervalo '2-5'. Retorna lista de arquivos."""
    import pymupdf
    doc = pymupdf.open(caminho_in)
    total = len(doc)
    selecionadas = _paginas_de_filtro(paginas, total)

    arquivos = []
    for p in sorted(selecionadas):
        novo = pymupdf.open()
        novo.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
        destino = os.path.join(pasta_saida, f"{base_name}_pag{p}.pdf")
        novo.save(destino, garbage=4, deflate=True)
        novo.close()
        arquivos.append((destino, p))
    doc.close()
    return True, arquivos


def _libs_da_preferencia(biblioteca):
    """Resolve a escolha de biblioteca numa lista de tentativas ordenadas.
    'auto' segue o fallback padrão do módulo: pymupdf → pikepdf → pypdf."""
    bib = (biblioteca or "auto").strip().lower()
    if bib == "auto":
        return ["pymupdf", "pikepdf", "pypdf"]
    return [bib]


def _extrair_paginas(caminho_in, paginas, destino, biblioteca):
    """Gera `destino` contendo as páginas informadas (lista 1-based,
    aceita não-contíguas). biblioteca: pymupdf | pikepdf | pypdf.
    Levanta exceção em falha (quem chama decide o fallback)."""
    bib = (biblioteca or "").strip().lower()
    if bib == "pymupdf":
        import pymupdf
        doc = pymupdf.open(caminho_in)
        try:
            out = pymupdf.open()
            for p in paginas:
                out.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
            out.save(destino, garbage=4, deflate=True)
            out.close()
        finally:
            doc.close()
    elif bib == "pikepdf":
        import pikepdf
        src = pikepdf.open(caminho_in)
        try:
            dst = pikepdf.Pdf.new()
            for p in paginas:
                dst.pages.append(src.pages[p - 1])
            dst.save(destino)
        finally:
            src.close()
    elif bib == "pypdf":
        from pypdf import PdfReader, PdfWriter
        leitor = PdfReader(caminho_in)
        escritor = PdfWriter()
        for p in paginas:
            escritor.add_page(leitor.pages[p - 1])
        with open(destino, "wb") as fh:
            escritor.write(fh)
    else:
        raise ValueError(f"biblioteca desconhecida: {biblioteca}")


def op_cortar(caminho_in, filtro, pasta_saida, base_name, biblioteca="pymupdf"):
    """Corta páginas em UM ÚNICO PDF.

    filtro: 'pares' | 'impares' | lista tipo '2-5,8'.
    biblioteca: 'auto' | 'pymupdf' | 'pikepdf' | 'pypdf'
      ('auto' tenta pymupdf → pikepdf → pypdf).
    Retorna (ok, caminho_out|msg).
    """
    import pymupdf
    filtro_norm = str(filtro or "").strip().lower()
    doc = pymupdf.open(caminho_in)
    total = len(doc)
    doc.close()
    if filtro_norm == "pares":
        pags = list(range(2, total + 1, 2))
    elif filtro_norm == "impares":
        pags = list(range(1, total + 1, 2))
    else:
        pags = sorted(_paginas_de_filtro(filtro_norm, total))
    if not pags:
        return False, "Nenhuma página válida para o corte"
    destino = os.path.join(pasta_saida, f"{base_name}.pdf")
    erros = []
    for bib in _libs_da_preferencia(biblioteca):
        try:
            _extrair_paginas(caminho_in, pags, destino, bib)
            _log().info(f"corte: {caminho_in} -> {destino} (filtro='{filtro}')")
            return True, destino
        except Exception as e:
            erros.append(f"{bib}: {e}")
    _log().error(f"falha no corte de {caminho_in} (filtro='{filtro}'): " +
                 " | ".join(erros))
    return False, ("falha no corte — " + " | ".join(erros))


# ---------- Divisão em várias partes ----------

def partes_pares_impares(total):
    """Duas partes complementares: [('pares',[2,4..]), ('impares',[1,3..])]."""
    return [("pares", list(range(2, total + 1, 2))),
            ("impares", list(range(1, total + 1, 2)))]


def partes_de_cortes(total, pontos):
    """Pontos de corte APÓS a página X: '5' ou '5,12' →
    [(parte1,[1..5]), (parte2,[6..12]), (parte3,[13..fim])].
    Pontos fora de 1..total-1 são ignorados."""
    ps = set()
    for pedaco in str(pontos or "").split(","):
        pedaco = pedaco.strip()
        if pedaco.isdigit() and 1 <= int(pedaco) < total:
            ps.add(int(pedaco))
    limites = [0] + sorted(ps) + [total]
    return [(f"parte{i + 1}", list(range(limites[i] + 1, limites[i + 1] + 1)))
            for i in range(len(limites) - 1)]


def partes_de_intervalos(total, texto):
    """'1-4,5-9' → [('grupo1',[1..4]), ('grupo2',[5..9])] na ordem digitada;
    grupos sem páginas válidas são ignorados."""
    partes = []
    for idx, pedaco in enumerate(str(texto or "").split(","), start=1):
        sels = sorted(_paginas_de_filtro(pedaco, total))
        if sels:
            partes.append((f"grupo{idx}", sels))
    return partes


def partes_pagina_a_pagina(total, texto_filtro):
    """'todas' ou '1,3-5' → uma parte por página ([('pag1',[1]), …])."""
    return [(f"pag{p}", [p])
            for p in sorted(_paginas_de_filtro(texto_filtro, total))]


def op_dividir_partes(caminho_in, modo, parametro, pasta_saida, base_name,
                      biblioteca="pymupdf"):
    """Divide em VÁRIOS PDFs. modo: 'pagina' | 'parimpar' | 'cortes' |
    'intervalos'; parametro depende do modo ('' para parimpar).
    biblioteca: 'auto'|'pymupdf'|'pikepdf'|'pypdf' (aplicada por parte;
    'auto' tenta pymupdf → pikepdf → pypdf).

    Retorna (ok, dados, aviso):
      ok=True  → dados=[(caminho, sufixo)], aviso='' ou falhas parciais
      ok=False → dados=msg do motivo, aviso=''
    """
    import pymupdf
    try:
        doc = pymupdf.open(caminho_in)
        total = len(doc)
        doc.close()
    except Exception as e:
        _log().error(f"PDF ilegível para divisão: {caminho_in}")
        return False, f"PDF ilegível: {e}", ""

    modo_norm = (modo or "").strip().lower()
    if modo_norm == "pagina":
        partes = partes_pagina_a_pagina(total, parametro)
    elif modo_norm == "parimpar":
        partes = partes_pares_impares(total)
    elif modo_norm == "cortes":
        partes = partes_de_cortes(total, parametro)
        if len(partes) <= 1:
            # sem ponto válido (< total) não há divisão: recusar em vez de
            # devolver o documento inteiro disfarçado de "parte1"
            return False, ("Nenhum ponto de corte válido — informe páginas "
                           f"entre 1 e {total - 1} (ex.: 5 ou 5,12)"), ""
    elif modo_norm == "intervalos":
        partes = partes_de_intervalos(total, parametro)
    else:
        return False, f"modo de divisão desconhecido: {modo}", ""

    if not partes:
        return False, "Nenhuma página válida para este modo/filtro", ""
    if any(not pags for _s, pags in partes):
        return False, "Uma das partes ficou vazia (verifique pontos/limites)", ""

    libs = _libs_da_preferencia(biblioteca)
    resultados, erros = [], []
    for sufixo, pags in partes:
        destino = os.path.join(pasta_saida, f"{base_name}_{sufixo}.pdf")
        feito = False
        ultimo_erro = ""
        for bib in libs:
            try:
                _extrair_paginas(caminho_in, pags, destino, bib)
                resultados.append((destino, sufixo))
                feito = True
                break
            except Exception as e:
                ultimo_erro = f"{sufixo} via {bib}: {e}"
        if not feito:
            erros.append(ultimo_erro)

    if not resultados:
        _log().error(f"falha na divisão em partes de {caminho_in}: " +
                     ("; ".join(erros) if erros else "sem partes geradas"))
        return False, ("falha na divisão — " + "; ".join(erros)), ""
    if erros:
        _log().warning(f"divisão parcial de {caminho_in}: {len(erros)} falha(s) — " +
                       "; ".join(erros))
    aviso = ("FALHAS parciais: " + "; ".join(erros)) if erros else ""
    return True, resultados, aviso


def op_verificar(caminho_in):
    try:
        import pymupdf
        doc = pymupdf.open(caminho_in)
        n = len(doc)
        doc.close()
        return True, f"PDF íntegro ({n} página(s))"
    except Exception as e:
        _log().error(f"PDF inválido/corrompido: {caminho_in}")
        return False, f"PDF corrompido ou inválido: {e}"


def zip_do_usuario(usuario):
    """Gera ZIP dos arquivos ativos do usuário. Retorna caminho do ZIP."""
    arquivos = obter_meus_arquivos(usuario)
    return _zipar(usuario, arquivos)


def zip_por_ids(usuario, ids):
    """ZIP apenas dos arquivos informados (ids da tb_arquivos). Retorna caminho ou None."""
    if not ids:
        return None
    conn = _conn()
    try:
        cur = conn.cursor()
        marks = ",".join("?" for _ in ids)
        cur.execute(
            f"""SELECT id, nome_arquivo, tamanho_bytes, operacao, data_operacao
                FROM tb_arquivos WHERE usuario=? AND ativo=1 AND id IN ({marks})""",
            (usuario, *ids),
        )
        arquivos = cur.fetchall()
    finally:
        conn.close()
    return _zipar(usuario, arquivos)


def _zipar(usuario, arquivos):
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


def deletar_arquivo(usuario, arquivo_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo FROM tb_arquivos WHERE id=? AND usuario=?", (arquivo_id, usuario))
        row = cur.fetchone()
        if not row:
            return False
        try:
            os.remove(os.path.join(pasta_usuario(usuario), row[0]))
        except OSError:
            pass
        cur.execute("UPDATE tb_arquivos SET ativo=0 WHERE id=?", (arquivo_id,))
        cur.execute(
            """UPDATE tb_cota_disco SET total_usado_bytes = MAX(0, total_usado_bytes -
               COALESCE((SELECT SUM(tamanho_bytes) FROM tb_arquivos WHERE id=?),0)) WHERE usuario=?""",
            (arquivo_id, usuario),
        )
        conn.commit()
        audit_log(usuario, "edit-pdf", "deletar", f"Arquivo {row[0]} removido")
        return True
    finally:
        conn.close()


init_db_pdf()


def expirar_antigos(minutos=None):
    """Expiração automática (roda sem usuário logado — basta o servidor vivo).

    Remove do disco PDFs com mtime > N min, INATIVA seus registros na
    tb_arquivos e devolve a cota dos usuários. Retorna total inativado.
    minutos=None usa a configuração editpdf_expiracao_min.
    """
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
                _log().debug(f"falha ao verificar/expirar arquivo: {caminho}")
    if not usuarios_tocados:
        return 0

    conn = _conn()
    try:
        cur = conn.cursor()
        total_inativados = 0
        for usuario in usuarios_tocados:
            pasta = pasta_usuario(usuario)
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
            cur.execute(f"UPDATE tb_arquivos SET ativo=0 WHERE id IN ({marks})", ids)
            cur.execute(
                """UPDATE tb_cota_disco SET total_usado_bytes = MAX(0, total_usado_bytes - ?),
                   atualizado_em = datetime('now') WHERE usuario=?""",
                (liberar, usuario),
            )
            total_inativados += len(ids)
        conn.commit()
    finally:
        conn.close()

    if total_inativados:
        _log().info(f"expiracao: {total_inativados} arquivo(s) removidos "
                    f"automaticamente (> {minutos} min)")
        try:
            from mod_intranet.manipulador_bd import audit_log
            audit_log("sistema", "edit-pdf", "expiracao",
                      f"{total_inativados} arquivo(s) removidos automaticamente (> {minutos} min)")
        except Exception:
            pass
    return total_inativados
