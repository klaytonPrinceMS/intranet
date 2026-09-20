"""News aggregator — own DB, multi-source scrapy-like collection, 24h recycle.

EN: News aggregator with own DB db_mod_agregador_noticias.db (WAL). Table
    tb_noticia (title/source/theme/url UNIQUE/image/description/dates), sources
    Google News + BBC + JFP + generic RSS configurable by admin, httpx+parsel
    collection interval 10min–6h with enabled flag, daily recycle at 06:00,
    censorship via titulo_bloqueado (conteudo_palavras_bloqueadas).

Agregador de Notícias — BD próprio, coleta multi-fonte, limpeza 24h.

BD: db_mod_agregador_noticias.db (WAL)
Tabelas: tb_noticia (titulo, fonte, tema, url UNIQUE, imagem_url, descricao, data_publicacao, data_coleta)
Fontes: Google News + BBC + JFP + RSS genérico, configuráveis pelo admin (conteúdo da pesquisa).
Coleta via httpx+parsel (scrapy-like) com intervalo 10min–6h, habilitado por flag.
Limpeza: DELETE WHERE data_coleta < now-24h (reiniciado 24/24h).
Integração: API listar_para_tv() usada pelo mod_filas TV (filtra censura).
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


def obter_hora_reinicio() -> str:
    """Hora do reinício diário (HH:MM), padrão 06:00 da manhã."""
    raw = (_get_config("hora_reinicio", "06:00") or "06:00").strip()
    # valida HH:MM
    m = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if not m:
        return "06:00"
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return "06:00"
    return f"{h:02d}:{mi:02d}"


def definir_hora_reinicio(hora_str: str, ator="sistema"):
    s = (hora_str or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return False, "Formato inválido, use HH:MM (ex: 06:00)"
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return False, "Hora inválida"
    norm = f"{h:02d}:{mi:02d}"
    ok = _set_config("hora_reinicio", norm)
    if ok:
        _audit(ator, "configurar", "hora_reinicio", norm)
        return True, norm
    return False, "Falha ao salvar"


def reiniciar_banco(ator="sistema"):
    """Zera todas as notícias (DELETE) — reinício diário da manhã."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_noticia")
        n = cur.fetchone()[0]
        cur.execute("DELETE FROM tb_noticia")
        # opcional: VACUUM para liberar espaço (sem travar muito, usa TRUNCATE pragmático)
        conn.commit()
        if n:
            _log().info(f"Reinício diário: {n} notícias zeradas por {ator}")
            _audit(ator, "reiniciar_banco", f"{n} notícias", f"hora={obter_hora_reinicio()}")
        return n
    finally:
        conn.close()


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
            fonte_icon_url TEXT DEFAULT '',
            descricao TEXT DEFAULT '',
            data_publicacao DATETIME,
            data_coleta DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # migração idempotente para BDs antigos sem fonte_icon_url
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_noticia)").fetchall()]
        if "fonte_icon_url" not in cols:
            cur.execute("ALTER TABLE tb_noticia ADD COLUMN fonte_icon_url TEXT DEFAULT ''")
    except Exception:
        pass
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
        ("agregador_noticias_hora_reinicio", "06:00"),
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


def _parse_data_pub(raw: str):
    """Tenta converter data crua de RSS/Google/BBC para YYYY-MM-DD HH:MM:SS."""
    if not raw:
        return None
    s = str(raw).strip()
    # tenta RFC822 via email.utils (robusto para Tue, 19 Sep 2026 12:34:56 GMT)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt:
            # normaliza para naive local (sem tz)
            if dt.tzinfo:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    # normaliza Z
    t = s.replace("Z", "+00:00")
    # remove colon em tz para strptime (+00:00 -> +0000)
    if len(t) >= 6 and t[-3] == ":" and t[-6] in "+-":
        t = t[:-3] + t[-2:]
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d/%m/%Y %H:%M",
    ):
        try:
            dt = datetime.strptime(t, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", s)
    if m:
        try:
            dt = datetime.strptime(m.group(1).replace("T", " "), "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return None


def listar_noticias(tema=None, limite=30, offset=0):
    conn = get_connection()
    try:
        cur = conn.cursor()
        # ordena por tempo real da postagem (data_publicacao) com fallback data_coleta
        if tema:
            cur.execute("SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao, data_coleta FROM tb_noticia WHERE tema=? ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ? OFFSET ?", (tema, limite, offset))
        else:
            cur.execute("SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao, data_coleta FROM tb_noticia ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ? OFFSET ?", (limite, offset))
        return cur.fetchall()
    finally:
        conn.close()


def listar_para_tv(limite=10):
    """API para mod_filas TV — carrossel título+descrição (filtra censuradas, ordena por tempo real)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # pega mais que limite para filtrar censuradas sem perder slots, ordena por data real da postagem
        cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (limite * 3,))
        rows = cur.fetchall()
        # filtra censura
        try:
            from mod_intranet.censura import titulo_bloqueado
            filtradas = []
            for r in rows:
                bloqueado, _ = titulo_bloqueado(r[0] or "")
                if not bloqueado:
                    filtradas.append(r)
                if len(filtradas) >= limite:
                    break
            rows = filtradas
        except Exception:
            rows = rows[:limite]
        return [{"titulo": r[0], "descricao": r[1] or r[0], "url": r[2], "imagem": r[3], "fonte": r[4], "tema": r[5], "fonte_icon": r[6] if len(r) > 6 else ""} for r in rows[:limite]]
    finally:
        conn.close()


def limpar_censuradas():
    """Remove do banco notícias já coletadas cujo título contém palavra bloqueada. Retorna qtd removida — sem auditoria de postagens."""
    try:
        from mod_intranet.censura import obter_palavras_bloqueadas, titulo_bloqueado
        palavras = obter_palavras_bloqueadas()
        if not palavras:
            return 0
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, titulo FROM tb_noticia")
            todas = cur.fetchall()
            ids_remover = []
            for nid, tit in todas:
                bloqueado, _ = titulo_bloqueado(tit or "", palavras)
                if bloqueado:
                    ids_remover.append((nid,))
            if ids_remover:
                cur.executemany("DELETE FROM tb_noticia WHERE id=?", ids_remover)
                conn.commit()
                _log().info(f"limpeza censura: {len(ids_remover)} notícias removidas")
                return len(ids_remover)
            return 0
        finally:
            conn.close()
    except Exception as e:
        _log().warning(f"limpar_censuradas falhou: {e}")
        return 0


def limpar_antigas(horas=24):
    """Reinicia banco a cada 24h (DELETE antigas) — sem auditoria de postagens (só config audita)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_noticia WHERE data_coleta < datetime('now', ?)", (f"-{int(horas)} hours",))
        n = cur.rowcount
        conn.commit()
        if n:
            _log().info(f"Limpeza 24h: {n} notícias removidas")
        return n
    finally:
        conn.close()


def inserir_noticia(titulo, fonte, tema, url, imagem_url="", descricao="", data_publicacao=None, fonte_icon_url=""):
    if not titulo or not url:
        return False
    # censura
    try:
        from mod_intranet.censura import titulo_bloqueado
        bloqueado, palavra = titulo_bloqueado(titulo or "")
        if bloqueado:
            _log().info(f"notícia censurada: palavra '{palavra}' no título '{titulo[:80]}' — descartada")
            return False
    except Exception:
        pass
    titulo = titulo.strip()[:500]
    url = url.strip()[:2000]
    if not titulo or not url:
        return False
    if url.startswith("/"):
        url = "https://news.google.com" + url
    # normaliza título para deduplicação (sem acentos, lower, strip)
    import unicodedata
    def _norm_tit(s):
        s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
        return " ".join(s.split())
    titulo_norm = _norm_tit(titulo)
    conn = get_connection()
    try:
        cur = conn.cursor()
        # impede duplicatas por URL (UNIQUE) e por título normalizado (mesma notícia já incluída)
        cur.execute("SELECT 1 FROM tb_noticia WHERE url=? LIMIT 1", (url,))
        if cur.fetchone():
            return False
        # verifica título duplicado (case-insensitive, sem acentos)
        cur.execute("SELECT titulo FROM tb_noticia")
        for (t_exist,) in cur.fetchall():
            if _norm_tit(t_exist) == titulo_norm:
                return False
        cur.execute("""
            INSERT OR IGNORE INTO tb_noticia (titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))
        """, (titulo, fonte[:100], tema[:50] or "Geral", url, imagem_url[:2000] or "", fonte_icon_url[:2000] or "", descricao[:1000] or "", data_publicacao))
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
        # Google News: cada notícia tem <a class="gPFEn"> e <time class="hvbAAd" datetime="..."> como irmãos
        for a in sel.css("a.gPFEn, a.JtKRv"):
            txt = (a.css("::text").get() or "").strip()
            href = (a.attrib.get("href") or "").strip()
            if not txt or txt in ["Local","Página inicial","Para você","Brasil","Mundo","Esportes",""]:
                continue
            if href.startswith("./"):
                href = "https://news.google.com/" + href.lstrip("./")
            elif href.startswith("/"):
                href = "https://news.google.com" + href
            if not href:
                continue
            # tenta extrair tempo real da postagem: datetime do <time> seguinte ou ancestral
            raw_time = (a.xpath("following::time[1]/@datetime").get() or a.xpath("ancestor::div[1]//time/@datetime").get() or a.xpath("ancestor::div[2]//time/@datetime").get() or "").strip()
            if not raw_time:
                # fallback: texto relativo "3 horas atrás" / "Ontem"
                raw_time = (a.xpath("following::time[1]/text()").get() or "").strip()
                # converte relativo para absoluto se for "X horas atrás"
                if "atrás" in raw_time or "hora" in raw_time.lower():
                    data_pub = _parse_relativo_para_absoluto(raw_time)
                else:
                    data_pub = _parse_data_pub(raw_time) if raw_time else None
            else:
                data_pub = _parse_data_pub(raw_time)
            # tenta extrair imagem do artigo (prioridade /api/attachments) e ícone da fonte (faviconV2)
            # busca em ancestrais que contêm o bloco da notícia (IBr9hb ou similar)
            img_article = ""
            fonte_icon = ""
            # procura em até 3 níveis de ancestral que contenham o bloco
            for level in [2, 3, 1]:
                anc = a.xpath(f"ancestor::div[{level}]")
                if anc:
                    # tenta artigo: img com /api/attachments ou lh3.googleusercontent
                    cand = anc.xpath(".//img[contains(@src,'/api/attachments') or contains(@src,'lh3.googleusercontent')]/@src").get()
                    if cand and not img_article:
                        img_article = cand.strip()
                    # tenta favicon
                    cand_fav = anc.xpath(".//img[contains(@src,'faviconV2')]/@src").get()
                    if cand_fav and not fonte_icon:
                        fonte_icon = cand_fav.strip()
                    if img_article and fonte_icon:
                        break
            # fallback: busca genérica se não achou
            if not img_article:
                img_article = (a.xpath("ancestor::div[1]//img/@src").get() or a.xpath("ancestor::div[2]//img/@src").get() or "").strip()
                # se for favicon, não usar como artigo
                if "faviconV2" in img_article:
                    fonte_icon = img_article
                    img_article = ""
            if not fonte_icon:
                fonte_icon = (a.xpath("ancestor::div[1]//img[contains(@src,'faviconV2')]/@src").get() or "").strip()
            data_pub = data_pub  # já definido acima
            if inserir_noticia(txt, f"Google News - {fonte_nome}", tema, href, img_article, txt, data_pub, fonte_icon):
                n += 1
            if n >= 20:
                break
        # fallback: caso não achou via a.gPFEn, tenta seletores antigos
        if n == 0:
            for x in sel.css(".gPFEn, .JtKRv, .a7P8L, article"):
                txt = (x.css("a::text").get() or "").strip()
                href = (x.css("a::attr(href)").get() or "").strip()
                if not txt or txt in ["Local","Página inicial","Para você","Brasil","Mundo","Esportes",""]:
                    continue
                if href.startswith("./"):
                    href = "https://news.google.com/" + href.lstrip("./")
                elif href.startswith("/"):
                    href = "https://news.google.com" + href
                img = (x.css("img::attr(src)").get() or x.css("img::attr(data-src)").get() or "").strip()
                # separa favicon vs artigo
                fonte_ic = img if "faviconV2" in img else ""
                art_img = "" if "faviconV2" in img else img
                raw_time = (x.css("time::attr(datetime)").get() or x.css("time::text").get() or x.css("[datetime]::attr(datetime)").get() or "").strip()
                data_pub = _parse_data_pub(raw_time) if raw_time else None
                if inserir_noticia(txt, f"Google News - {fonte_nome}", tema, href, art_img, txt, data_pub, fonte_ic):
                    n += 1
                if n >= 20:
                    break
        return n
    except Exception as e:
        _log().warning(f"_coletar_google {fonte_nome}: {e}")
        return 0


def _parse_relativo_para_absoluto(texto: str):
    """Converte '3 horas atrás', '25 minutos atrás', 'Ontem', '2 dias atrás' para datetime absoluto."""
    if not texto:
        return None
    txt = texto.strip().lower()
    agora = datetime.now()
    try:
        if txt == "ontem":
            dt = agora - timedelta(days=1)
            return dt.strftime("%Y-%m-%d 12:00:00")
        m = re.search(r"(\d+)\s*minuto", txt)
        if m:
            dt = agora - timedelta(minutes=int(m.group(1)))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        m = re.search(r"(\d+)\s*hora", txt)
        if m:
            dt = agora - timedelta(hours=int(m.group(1)))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        m = re.search(r"(\d+)\s*dia", txt)
        if m:
            dt = agora - timedelta(days=int(m.group(1)))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        m = re.search(r"(\d+)\s*semana", txt)
        if m:
            dt = agora - timedelta(weeks=int(m.group(1)))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return _parse_data_pub(texto)


def _coletar_bbc(url: str, tema: str) -> int:
    html = _get_html(url)
    if not html:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=html)
        n = 0
        for x in sel.css(".bbc-uk8dsi, .bbc-19j92fr, article, a[href*='/portuguese/articles'], a[href*='/portuguese/topics']"):
            txt = (x.css("::text").get() or x.css("a::text").get() or "").strip()
            href = (x.css("::attr(href)").get() or x.css("a::attr(href)").get() or "").strip()
            if not txt or not href:
                if x.css("::text").get():
                    txt = x.css("::text").get().strip()
                    href = x.css("::attr(href)").get().strip()
                if not txt or not href:
                    continue
            if href.startswith("/"):
                href = "https://www.bbc.com" + href
            if href.count("/") < 3 or len(txt) < 15:
                continue
            img = (x.css("img::attr(src)").get() or x.css("img::attr(data-src)").get() or "").strip()
            raw_time = (x.css("time::attr(datetime)").get() or x.css("time::text").get() or "").strip()
            data_pub = _parse_data_pub(raw_time) if raw_time else None
            if inserir_noticia(txt, "BBC", tema, href, img, txt, data_pub):
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
        for x in sel.css(".td-module-title"):
            txt = (x.css("a::text").get() or x.css("::text").get() or "").strip()
            href = (x.css("a::attr(href)").get() or "").strip()
            if not txt or not href:
                continue
            img = (x.css("img::attr(src)").get() or "").strip()
            raw_time = (x.css("time::attr(datetime)").get() or x.css(".td-post-date::text").get() or "").strip()
            data_pub = _parse_data_pub(raw_time) if raw_time else None
            if inserir_noticia(txt, "JFP Notícias", tema, href, img, txt, data_pub):
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
            raw_time = (item.css("pubDate::text").get() or item.css("dc\\:date::text").get() or item.css("published::text").get() or "").strip()
            data_pub = _parse_data_pub(raw_time) if raw_time else None
            img = ""
            m = item.css("media\\:content::attr(url)").get()
            if m:
                img = m.strip()
            else:
                # tenta enclosure
                enc = item.css("enclosure::attr(url)").get()
                if enc and any(enc.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".webp")):
                    img = enc.strip()
            if not txt or not href:
                continue
            if inserir_noticia(txt, fonte_nome or "RSS", tema, href, img, desc[:500], data_pub):
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


def coletar_todas(ator="sistema", forcar: bool = False):
    """Investiga fontes com intervalo configurado, se habilitado (forcar ignora flag). Retorna total inseridas."""
    if not forcar and not habilitado():
        _log().info("Coleta ignorada: módulo desabilitado (use forcar=True para coleta manual)")
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
    # limpeza 24h após coleta (reiniciado 24/24h) — sem auditoria de postagens
    try:
        limpar_antigas(24)
    except Exception:
        pass
    _log().info(f"Coleta agregador: {total} novas de {len(fontes)} fontes (termo={termo})")
    return total


def intervalo_criar_job():
    """Helper para rotinas: retorna (habilitado, minutos)."""
    return habilitado(), intervalo_min()


init_db()
