"""Agregador de Notícias — BD próprio, coleta multi-fonte, limpeza 24h.

BD: db_mod_agregador_noticias.db (WAL)
Tabelas: tb_noticia (titulo, fonte, tema, url UNIQUE, imagem_url, descricao, data_publicacao, data_coleta)
Fontes: Google News + BBC + JFP + RSS genérico, configuráveis pelo admin (conteúdo da pesquisa).
Coleta via httpx+parsel (scrapy-like) com intervalo 10min–6h, habilitado por flag.
Limpeza: DELETE WHERE data_coleta < now-24h (reiniciado 24/24h).
Integração: API listar_para_tv() usada pelo mod_filas TV.
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_mod_agregador_noticias.db")

# Temas padrão alinhados ao Noticia/main.py
TEMAS_PADRAO = ["Brasil", "Internacional", "Economia", "Saúde", "Ciência e Tecnologia", "Entretenimento", "Esporte", "Monte Santo de Minas", "Geral"]

# Fontes padrão (espelho Sites de classesKBP.py) — admin pode sobrescrever via config
FONTES_PADRAO = [
    {"tipo": "google", "nome": "Google News - Brasil", "url": "https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419", "tema": "Brasil"},
    {"tipo": "bbc", "nome": "BBC - Brasil", "url": "https://www.bbc.com/portuguese/topics/cz74k717pw5t", "tema": "Brasil"},
    {"tipo": "google", "nome": "Google News - Saúde", "url": "https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNR3QwTlRFU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419", "tema": "Saúde"},
]

def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("agregador_noticias")


def get_connection():
    from mod_intranet.banco_conexao import conexao
    conn = conexao("agregador_noticias")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão agregador_noticias")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def _audit(ator, acao, alvo, detalhe=""):
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", "agregador_noticias", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception:
        pass


def _get_config(chave, default=""):
    try:
        from mod_intranet.bd_conexao import get_config
        return get_config(f"agregador_noticias_{chave}", default)
    except Exception:
        return default


def _set_config(chave, valor):
    try:
        from mod_intranet.bd_conexao import set_config
        return set_config(f"agregador_noticias_{chave}", str(valor))
    except Exception:
        return False


# ============ CONFIG HELPERS ============

def habilitado() -> bool:
    return (_get_config("habilitado", "0").strip() == "1")


def definir_habilitado(valor: bool, ator="sistema"):
    ok = _set_config("habilitado", "1" if valor else "0")
    if ok:
        _audit(ator, "configurar", "habilitado", str(valor))
    return ok


def intervalo_min() -> int:
    try:
        v = int((_get_config("intervalo_min", "60") or "60").strip() or 60)
    except Exception:
        v = 60
    return max(10, min(360, v))


def definir_intervalo(minutos: int, ator="sistema"):
    v = max(10, min(360, int(minutos)))
    ok = _set_config("intervalo_min", str(v))
    if ok:
        _audit(ator, "configurar", "intervalo_min", str(v))
    return ok, v


def termo_pesquisa() -> str:
    return (_get_config("termo_pesquisa", "") or "").strip()


def definir_termo(termo: str, ator="sistema"):
    ok = _set_config("termo_pesquisa", (termo or "").strip())
    if ok:
        _audit(ator, "configurar", "termo_pesquisa", termo)
    return ok


def fontes_config() -> list[dict]:
    raw = _get_config("fontes_json", "")
    if not raw:
        return list(FONTES_PADRAO)
    try:
        dados = json.loads(raw)
        if isinstance(dados, list) and dados:
            return dados
    except Exception:
        pass
    return list(FONTES_PADRAO)


def definir_fontes(fontes: list[dict], ator="sistema"):
    try:
        txt = json.dumps(fontes, ensure_ascii=False)
    except Exception as e:
        return False, str(e)
    ok = _set_config("fontes_json", txt)
    if ok:
        _audit(ator, "configurar", "fontes_json", f"{len(fontes)} fontes")
        return True, "Fontes salvas"
    return False, "Falha ao salvar"


def temas_config() -> list[str]:
    raw = _get_config("temas_json", "")
    if raw:
        try:
            dados = json.loads(raw)
            if isinstance(dados, list) and dados:
                return [str(t).strip() for t in dados if str(t).strip()]
        except Exception:
            pass
    return list(TEMAS_PADRAO)


def definir_temas(temas: list[str], ator="sistema"):
    txt = json.dumps([t.strip() for t in temas if t.strip()], ensure_ascii=False)
    ok = _set_config("temas_json", txt)
    if ok:
        _audit(ator, "configurar", "temas_json", txt)
    return ok


# ============ INIT ============

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_noticia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            fonte TEXT NOT NULL,
            tema TEXT NOT NULL DEFAULT 'Geral',
            url TEXT NOT NULL UNIQUE,
            imagem_url TEXT DEFAULT '',
            descricao TEXT DEFAULT '',
            data_publicacao DATETIME,
            data_coleta DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_tema ON tb_noticia(tema)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_fonte ON tb_noticia(fonte)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_data ON tb_noticia(data_coleta)")
    # seeds de config central (idempotente)
    for k, v in [
        ("agregador_noticias_habilitado", "0"),
        ("agregador_noticias_intervalo_min", "60"),
        ("agregador_noticias_termo_pesquisa", ""),
        ("agregador_noticias_temas_json", json.dumps(TEMAS_PADRAO, ensure_ascii=False)),
        ("agregador_noticias_fontes_json", json.dumps(FONTES_PADRAO, ensure_ascii=False)),
    ]:
        try:
            from mod_intranet.bd_conexao import get_connection as gc
            c = gc()
            cur2 = c.cursor()
            cur2.execute("SELECT valor FROM tb_config WHERE chave=?", (k,))
            if not cur2.fetchone():
                cur2.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?)", (k, v))
                c.commit()
            c.close()
        except Exception:
            pass
    conn.commit()
    conn.close()


# ============ CRUD ============

def contar_noticias(tema=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if tema:
            cur.execute("SELECT COUNT(*) FROM tb_noticia WHERE tema=?", (tema,))
        else:
            cur.execute("SELECT COUNT(*) FROM tb_noticia")
        return cur.fetchone()[0]
    finally:
        conn.close()


def listar_noticias(tema=None, limite=30, offset=0):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if tema:
            cur.execute("SELECT id, titulo, fonte, tema, url, imagem_url, descricao, data_publicacao, data_coleta FROM tb_noticia WHERE tema=? ORDER BY data_coleta DESC LIMIT ? OFFSET ?", (tema, limite, offset))
        else:
            cur.execute("SELECT id, titulo, fonte, tema, url, imagem_url, descricao, data_publicacao, data_coleta FROM tb_noticia ORDER BY data_coleta DESC LIMIT ? OFFSET ?", (limite, offset))
        return cur.fetchall()
    finally:
        conn.close()


def listar_para_tv(limite=10):
    """API para mod_filas TV — carrossel título+descrição."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema FROM tb_noticia ORDER BY data_coleta DESC LIMIT ?", (limite,))
        rows = cur.fetchall()
        # fallback: se vazio, retorna lista vazia (TV mostra placeholder)
        return [{"titulo": r[0], "descricao": r[1] or r[0], "url": r[2], "imagem": r[3], "fonte": r[4], "tema": r[5]} for r in rows]
    finally:
        conn.close()


def limpar_antigas(horas=24):
    """Reinicia banco a cada 24h (DELETE antigas)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_noticia WHERE data_coleta < datetime('now', ?)", (f"-{int(horas)} hours",))
        n = cur.rowcount
        conn.commit()
        if n:
            _log().info(f"Limpeza 24h: {n} notícias removidas")
            _audit("sistema", "limpar_antigas", f"{n} removidas", f"{horas}h")
        return n
    finally:
        conn.close()


def inserir_noticia(titulo, fonte, tema, url, imagem_url="", descricao="", data_publicacao=None):
    if not titulo or not url:
        return False
    # sanitiza
    titulo = titulo.strip()[:500]
    url = url.strip()[:2000]
    if not titulo or not url:
        return False
    # normaliza url google news
    if url.startswith("/"):
        url = "https://news.google.com" + url
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO tb_noticia (titulo, fonte, tema, url, imagem_url, descricao, data_publicacao)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))
        """, (titulo, fonte[:100], tema[:50] or "Geral", url, imagem_url[:2000] or "", descricao[:1000] or "", data_publicacao))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ============ COLETA (scrapy-like) ============

def _get_html(url: str, timeout=12) -> str:
    try:
        import httpx
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (IntrAnEt; AgregadorNoticias)"})
        if r.status_code == 200:
            return r.text
    except Exception as e:
        _log().warning(f"_get_html falhou {url}: {e}")
    return ""


def _coletar_google(url: str, fonte_nome: str, tema: str) -> int:
    html = _get_html(url)
    if not html:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=html)
        n = 0
        for x in sel.css(".gPFEn, .JtKRv, .a7P8L, article"):
            txt = (x.css("a::text").get() or "").strip()
            href = (x.css("a::attr(href)").get() or "").strip()
            if not txt or txt in ["Local","Página inicial","Para você","Brasil","Mundo","Esportes",""]:
                continue
            if href.startswith("./"):
                href = "https://news.google.com/" + href.lstrip("./")
            elif href.startswith("/"):
                href = "https://news.google.com" + href
            # imagem
            img = (x.css("img::attr(src)").get() or x.css("img::attr(data-src)").get() or "").strip()
            if inserir_noticia(txt, f"Google News - {fonte_nome}", tema, href, img, txt):
                n += 1
            if n >= 20:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_google {fonte_nome}: {e}")
        return 0


def _coletar_bbc(url: str, tema: str) -> int:
    html = _get_html(url)
    if not html:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=html)
        n = 0
        for x in sel.css(".bbc-uk8dsi, .bbc-19j92fr, article"):
            txt = (x.css("a::text").get() or "").strip()
            href = (x.css("a::attr(href)").get() or "").strip()
            if not txt or not href:
                continue
            if href.startswith("/"):
                href = "https://www.bbc.com" + href
            img = (x.css("img::attr(src)").get() or "").strip()
            if inserir_noticia(txt, "BBC", tema, href, img, txt):
                n += 1
            if n >= 15:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_bbc {tema}: {e}")
        return 0


def _coletar_jfp(url: str, tema: str) -> int:
    html = _get_html(url)
    if not html:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=html)
        n = 0
        for x in sel.css(".td-module-title a"):
            txt = (x.css("::text").get() or "").strip()
            href = (x.css("::attr(href)").get() or "").strip()
            if not txt or not href:
                continue
            img = (x.css("img::attr(src)").get() or "").strip()
            if inserir_noticia(txt, "JFP Notícias", tema, href, img, txt):
                n += 1
            if n >= 15:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_jfp {tema}: {e}")
        return 0


def _coletar_rss(url: str, fonte_nome: str, tema: str) -> int:
    xml = _get_html(url)
    if not xml:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=xml, type="xml")
        n = 0
        for item in sel.css("item"):
            txt = (item.css("title::text").get() or "").strip()
            href = (item.css("link::text").get() or item.css("link::attr(href)").get() or "").strip()
            desc = (item.css("description::text").get() or "").strip()
            img = ""
            # tenta media:content
            m = item.css("media\\:content::attr(url)").get()
            if m:
                img = m.strip()
            if not txt or not href:
                continue
            if inserir_noticia(txt, fonte_nome or "RSS", tema, href, img, desc[:500]):
                n += 1
            if n >= 15:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_rss {fonte_nome}: {e}")
        return 0


def _coletar_pesquisa_google(termo: str, tema: str = "Geral") -> int:
    if not termo:
        return 0
    try:
        from urllib.parse import quote as _q
        url = f"https://news.google.com/search?q={_q(termo)}&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"
        return _coletar_google(url, f"Pesquisa:{termo}", tema)
    except Exception as e:
        _log().warning(f"_coletar_pesquisa {termo}: {e}")
        return 0


def coletar_todas(ator="sistema"):
    """Investiga fontes com intervalo configurado, se habilitado. Retorna total inseridas."""
    if not habilitado():
        _log().info("Coleta ignorada: módulo desabilitado")
        return 0
    fontes = fontes_config()
    termo = termo_pesquisa()
    total = 0
    for f in fontes:
        try:
            tipo = (f.get("tipo") or "google").lower()
            url = f.get("url") or ""
            tema = f.get("tema") or "Geral"
            nome = f.get("nome") or url[:30]
            if not url:
                continue
            if tipo == "google":
                total += _coletar_google(url, nome, tema)
            elif tipo == "bbc":
                total += _coletar_bbc(url, tema)
            elif tipo == "jfp":
                total += _coletar_jfp(url, tema)
            elif tipo == "rss":
                total += _coletar_rss(url, nome, tema)
            else:
                total += _coletar_google(url, nome, tema)
        except Exception as e:
            _log().warning(f"coletar fonte {f}: {e}")
    if termo:
        total += _coletar_pesquisa_google(termo, "Geral")
    # limpeza 24h após coleta (reiniciado 24/24h)
    try:
        limpar_antigas(24)
    except Exception:
        pass
    _audit(ator, "coletar", f"{total} novas", f"fontes={len(fontes)} termo={termo[:30]}")
    _log().info(f"Coleta agregador: {total} novas de {len(fontes)} fontes (termo={termo})")
    return total


def intervalo_criar_job():
    """Helper para rotinas: retorna (habilitado, minutos)."""
    return habilitado(), intervalo_min()


init_db()
