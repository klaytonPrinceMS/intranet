"""News aggregator — own DB, multi-source scrapy-like collection, 24h recycle.

EN: News aggregator with own DB db_mod_agregador_noticias.db (WAL). Table
    tb_noticia (title/source/theme/url UNIQUE/image/description/dates), sources
    Google News + BBC + JFP + generic RSS configurable by admin, httpx+parsel
    collection interval 10min–6h with enabled flag, daily recycle at 09:00,
    censorship via titulo_bloqueado (conteudo_palavras_bloqueadas).

Agregador de Notícias — BD próprio, coleta multi-fonte, limpeza 24h.

BD: db_mod_agregador_noticias.db (WAL)
Tabelas: tb_noticia (titulo, fonte, tema, url UNIQUE, imagem_url, descricao, data_publicacao, data_coleta)
Fontes: Google News + BBC + JFP + RSS genérico, configuráveis pelo admin (conteúdo da pesquisa).
Coleta via httpx+parsel (scrapy-like) com intervalo 10min–9360min (teto 6,5 dias), habilitado por flag.
Limpeza: DELETE WHERE data_coleta < corte Python (portável SQLite/PG, sem datetime() com bind).
Reinício diário padrão 09:00 (config hora_reinicio).
Integração: API listar_para_tv() usada pelo mod_filas TV (filtra censura).
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Temas padrão alinhados ao Noticia/main.py
TEMAS_PADRAO = ["Brasil", "Internacional", "Economia", "Saúde", "Ciência e Tecnologia", "Entretenimento", "Esporte", "Monte Santo", "Geral"]

# Default antigo (3 fontes) — usado só para migrar quem nunca customizou (ver init_db)
_FONTES_PADRAO_LEGADO = [
    {"tipo": "google", "nome": "Google News - Brasil", "url": "https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419", "tema": "Brasil"},
    {"tipo": "bbc", "nome": "BBC - Brasil", "url": "https://www.bbc.com/portuguese/topics/cz74k717pw5t", "tema": "Brasil"},
    {"tipo": "google", "nome": "Google News - Saúde", "url": "https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNR3QwTlRFU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419", "tema": "Saúde"},
]

# Fontes padrão (Google/BBC espelham Sites de classesKBP.py; RSS oficiais verificados em 20/09/2026) — admin pode sobrescrever via config
_FONTES_PADRAO_V1 = _FONTES_PADRAO_LEGADO + [
    {"tipo": "rss", "nome": "Agência Brasil", "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias.xml", "tema": "Brasil"},
    {"tipo": "rss", "nome": "Senado Federal", "url": "https://www12.senado.leg.br/noticias/rss", "tema": "Brasil"},
    {"tipo": "rss", "nome": "G1 - Últimas", "url": "https://g1.globo.com/rss/g1/", "tema": "Geral"},
    {"tipo": "rss", "nome": "G1 - Economia", "url": "https://g1.globo.com/rss/g1/economia/", "tema": "Economia"},
    {"tipo": "rss", "nome": "G1 - Saúde", "url": "https://g1.globo.com/rss/g1/saude/", "tema": "Saúde"},
    {"tipo": "rss", "nome": "G1 - Tecnologia", "url": "https://g1.globo.com/rss/g1/tecnologia/", "tema": "Ciência e Tecnologia"},
    {"tipo": "rss", "nome": "Poder9360", "url": "https://www.poder9360.com.br/", "tema": "Brasil"},
    {"tipo": "rss", "nome": "Folha de S.Paulo", "url": "https://s.folha.uol.com.br/emcimadahora/rss091.xml", "tema": "Brasil"},
]

# Default atual = V1 + cobertura dos temas vazios (Internacional/Entretenimento/Esporte/MSM)
FONTES_PADRAO = _FONTES_PADRAO_V1 + [
    {"tipo": "rss", "nome": "G1 - Mundo", "url": "https://g1.globo.com/rss/g1/mundo/", "tema": "Internacional"},
    {"tipo": "rss", "nome": "G1 - Pop e Arte", "url": "https://g1.globo.com/rss/g1/pop-arte/", "tema": "Entretenimento"},
    {"tipo": "rss", "nome": "GE - Esporte", "url": "https://ge.globo.com/rss/ge/", "tema": "Esporte"},
    {"tipo": "rss", "nome": "JFP - Monte Santo de Minas", "url": "https://jfpnoticias.com.br", "tema": "Monte Santo de Minas"},
]

def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("agregador_noticia")


def get_connection():
    from mod_intranet import banco_conexao
    conn = banco_conexao.conexao("agregador_noticias")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão agregador_noticias")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        # herdado por toda conexão do módulo: evita "database is locked" em coleta concorrente com TV
        conn.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def _eh_locked(e: Exception) -> bool:
    """Detecta SQLITE_BUSY/locked para retry (portável: checa mensagem)."""
    try:
        s = str(e).lower()
        return ("locked" in s) or ("busy" in s)
    except Exception:
        return False


def _audit(ator, acao, alvo, detalhe=""):
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", acao, "agregador_noticias", f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
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
    """Intervalo de coleta em minutos, clamp 10–9360 (teto 9360min = 6,5 dias)."""
    try:
        v = int((_get_config("intervalo_min", "60") or "60").strip() or 60)
    except Exception:
        v = 60
    return max(10, min(9360, v))


def definir_intervalo(minutos: int, ator="sistema"):
    v = max(10, min(9360, int(minutos)))
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
                # deduplica preservando ordem (admin pode ter salvo repetidos)
                vistos, unicos = set(), []
                for t in dados:
                    t = str(t).strip()
                    if t and t not in vistos:
                        vistos.add(t)
                        unicos.append(t)
                if unicos:
                    return unicos
        except Exception:
            pass
    return list(TEMAS_PADRAO)


def definir_temas(temas: list[str], ator="sistema"):
    vistos, unicos = set(), []
    for t in temas:
        t = str(t).strip()
        if t and t not in vistos:
            vistos.add(t)
            unicos.append(t)
    txt = json.dumps(unicos, ensure_ascii=False)
    ok = _set_config("temas_json", txt)
    if ok:
        _audit(ator, "configurar", "temas_json", txt)
    return ok


def obter_hora_reinicio() -> str:
    """Hora do reinício diário (HH:MM), padrão 09:00 da manhã."""
    raw = (_get_config("hora_reinicio", "09:00") or "09:00").strip()
    # valida HH:MM
    m = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if not m:
        return "09:00"
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return "09:00"
    return f"{h:02d}:{mi:02d}"


def definir_hora_reinicio(hora_str: str, ator="sistema"):
    s = (hora_str or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return False, "Formato inválido, use HH:MM (ex: 09:00)"
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
        return max(0, n - 1)
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
    # P0 dedup O(1): coluna titulo_norm (lower sem acentos, strip) — elimina full-scan por notícia
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_noticia)").fetchall()]
        if "titulo_norm" not in cols:
            cur.execute("ALTER TABLE tb_noticia ADD COLUMN titulo_norm TEXT DEFAULT ''")
    except Exception:
        pass
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_tema ON tb_noticia(tema)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_fonte ON tb_noticia(fonte)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_data ON tb_noticia(data_coleta)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_noticia_titulo_norm ON tb_noticia(titulo_norm)")
    # backfill titulo_norm para linhas antigas (idempotente, só onde vazio)
    try:
        import unicodedata as _ud
        def _nn(s):
            s = _ud.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
            return " ".join(s.split())
        cur.execute("SELECT id, titulo FROM tb_noticia WHERE titulo_norm IS NULL OR titulo_norm='' LIMIT 2000")
        _pend = [( _nn(t), nid) for nid, t in cur.fetchall()]
        if _pend:
            cur.executemany("UPDATE tb_noticia SET titulo_norm=? WHERE id=?", _pend)
    except Exception:
        pass
    # seeds de config central (idempotente)
    for k, v in [
        ("agregador_noticias_habilitado", "0"),
        ("agregador_noticias_intervalo_min", "60"),
        ("agregador_noticias_termo_pesquisa", ""),
        ("agregador_noticias_temas_json", json.dumps(TEMAS_PADRAO, ensure_ascii=False)),
        ("agregador_noticias_fontes_json", json.dumps(FONTES_PADRAO, ensure_ascii=False)),
        ("agregador_noticias_hora_reinicio", "09:00"),
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
    # migração 20/09/2026: quem tem o default antigo (nunca customizou fontes) ganha os RSS oficiais
    try:
        from mod_intranet.bd_conexao import get_config as _getc, set_config as _setc
        _atual = _getc("agregador_noticias_fontes_json", "")
        if _atual:
            try:
                _dados = json.loads(_atual)
            except Exception:
                _dados = None
            if _dados == _FONTES_PADRAO_LEGADO or _dados == _FONTES_PADRAO_V1:
                _setc("agregador_noticias_fontes_json", json.dumps(FONTES_PADRAO, ensure_ascii=False))
                _log().info("agregador: fontes RSS oficiais adicionadas ao default")
    except Exception:
        pass
    # migração 26/09/2026: repara URL de fonte com o esquema malformado
    # ("https:/host/..." com uma barra só) — a requisição falhava com
    # "Request URL is missing an 'http://' or 'https://' protocol". Só toca
    # em URL realmente quebrada, então NÃO sobrescreve fontes customizadas.
    # Idempotente: se nada mudou, não reescreve a config.
    try:
        import re as _re_url
        from mod_intranet.bd_conexao import get_config as _getc, set_config as _setc
        _atual = _getc("agregador_noticias_fontes_json", "")
        if _atual:
            _dados = json.loads(_atual)
            if isinstance(_dados, list) and _dados:
                _mudou = False
                for _f in _dados:
                    if not isinstance(_f, dict):
                        continue
                    _u = _f.get("url") or ""
                    _corr = _re_url.sub(r"^(https?:)/(?!/)", r"\1//", _u.strip(), count=1)
                    if _corr and _corr != _u:
                        _f["url"] = _corr
                        _mudou = True
                        _log().warning(
                            f"agregador: URL de fonte reparada "
                            f"({_f.get('nome', '?')}): {_u} -> {_corr}")
                if _mudou:
                    _setc("agregador_noticias_fontes_json",
                          json.dumps(_dados, ensure_ascii=False))
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


def _corte_horas(horas):
    """Converte horas (ex: 4) em corte 'YYYY-MM-DD HH:MM:SS' para filtrar notícias recentes."""
    if horas is None:
        return None
    try:
        horas_int = int(horas)
    except Exception:
        return None
    if horas_int <= 0:
        return None
    return (datetime.now() - timedelta(hours=horas_int)).strftime("%Y-%m-%d %H:%M:%S")


def _filtrar_censura_tv(linhas, limite):
    """Filtra linhas censuradas pelo título, preservando no máximo limite itens."""
    try:
        from mod_intranet.censura import titulo_bloqueado
        filtradas = []
        for r in linhas:
            bloqueado, _ = titulo_bloqueado(r[0] or "")
            if not bloqueado:
                filtradas.append(r)
            if len(filtradas) >= limite:
                break
        return filtradas
    except Exception:
        return list(linhas[:limite])


def _linha_tv_para_dict(r):
    """Converte linha SQL da TV no dict público (mesmas 7 chaves de sempre)."""
    return {"titulo": r[0], "descricao": r[1] or r[0], "url": r[2], "imagem": r[3],
            "fonte": r[4], "tema": r[5], "fonte_icon": r[6] if len(r) > 6 else ""}


def listar_para_tv(limite=10, por_tema=False, horas=None):
    """API para mod_filas TV — carrossel título+descrição (filtra censuradas, ordena por tempo real).

    EN: TV feed — latest headlines (censorship filtered, real post time first).
    Params opcionais retrocompatíveis: por_tema=True devolve UMA notícia por
    categoria de temas_config() (na ordem configurada, para rodar as categorias);
    horas=N prioriza notícias com COALESCE(data_publicacao, data_coleta) das
    últimas N horas — no modo por_tema cada categoria sem novidade usa a mais
    recente disponível (fallback por categoria).
    Leitura curta: LIMIT*3 compensa descarte da censura (filtra até limite sem perder slots);
    busy_timeout herdado de get_connection + retry locked; sem escrita (sem rollback salvo fechar).
    """
    try:
        limite = max(1, int(limite or 10))
    except Exception:
        limite = 10
    corte = _corte_horas(horas)
    import time as _t
    ultimo_erro = None
    for _tent in range(3):
        conn = get_connection()
        try:
            cur = conn.cursor()
            if por_tema:
                try:
                    temas = temas_config()
                except Exception:
                    temas = []
                if not temas:
                    temas = []
                coletadas = []
                for tema in temas:
                    if len(coletadas) >= limite:
                        break
                    item = None
                    # 1ª tentativa: só recentes (quando horas pedido); 2ª: qualquer época
                    tentativas = [corte, None] if corte else [None]
                    for tentativa in tentativas:
                        try:
                            if tentativa:
                                cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia WHERE tema=? AND COALESCE(data_publicacao, data_coleta) >= ? ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (tema, tentativa, 5))
                            else:
                                cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia WHERE tema=? ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (tema, 5))
                            candidatas = cur.fetchall()
                        except Exception as e:
                            if _eh_locked(e) and _tent < 2:
                                candidatas = None
                                ultimo_erro = e
                                break
                            candidatas = []
                        if candidatas is None:
                            break
                        filtradas = _filtrar_censura_tv(candidatas, 1)
                        if filtradas:
                            item = _linha_tv_para_dict(filtradas[0])
                            break
                    if candidatas is None:
                        break
                    if item:
                        coletadas.append(item)
                else:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return coletadas
                # locked no meio do loop por_tema: retry externo
                try:
                    conn.close()
                except Exception:
                    pass
                if ultimo_erro is not None and _tent < 2:
                    _t.sleep(0.05 * (_tent + 1))
                    continue
                return coletadas
            # modo geral (legado): mais recentes primeiro, com filtro opcional de horas
            try:
                if corte:
                    cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia WHERE COALESCE(data_publicacao, data_coleta) >= ? ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (corte, limite * 3))
                else:
                    # pega mais que limite para filtrar censuradas sem perder slots, ordena por data real da postagem
                    cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (limite * 3,))
                rows = cur.fetchall()
            except Exception as e:
                ultimo_erro = e
                try:
                    conn.close()
                except Exception:
                    pass
                if _eh_locked(e) and _tent < 2:
                    _t.sleep(0.05 * (_tent + 1))
                    continue
                return []
            # filtra censura
            rows = _filtrar_censura_tv(rows, limite)
            saida = [_linha_tv_para_dict(r) for r in rows[:limite]]
            try:
                conn.close()
            except Exception:
                pass
            return saida
        finally:
            try:
                conn.close()
            except Exception:
                pass
    _log().warning(f"listar_para_tv falhou após retry: {ultimo_erro}")
    return []


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


def _normalizar_titulo(s: str) -> str:
    """Normaliza título p/ dedup: sem acentos, lower, espaços colapsados (usado em titulo_norm indexado)."""
    try:
        import unicodedata
        s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
        return " ".join(s.split())
    except Exception:
        return (s or "").strip().lower()


def limpar_antigas(horas=24):
    """Reinicia banco a cada 24h (DELETE antigas) — sem auditoria de postagens (só config audita).

    Portável SQLite/PG: corte calculado em Python (sem datetime('now', ?) com bind,
    que o proxy PG não traduz e quebrava 100% da coleta no fim).
    """
    try:
        horas_int = int(horas)
    except Exception:
        horas_int = 24
    if horas_int <= 0:
        return 0
    corte = (datetime.now() - timedelta(hours=horas_int)).strftime("%Y-%m-%d %H:%M:%S")
    import time as _t
    ultimo_erro = None
    for tentativa in range(3):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM tb_noticia WHERE data_coleta < ?", (corte,))
            n = cur.rowcount
            conn.commit()
            if n:
                _log().info(f"Limpeza {horas_int}h: {n} notícias removidas")
            return n if n and n > 0 else 0
        except Exception as e:
            ultimo_erro = e
            try:
                conn.rollback()
            except Exception:
                pass
            if _eh_locked(e) and tentativa < 2:
                _t.sleep(0.05 * (tentativa + 1))
                continue
            _log().warning(f"limpar_antigas falhou: {e}")
            return 0
        finally:
            try:
                conn.close()
            except Exception:
                pass
    _log().warning(f"limpar_antigas falhou após retry: {ultimo_erro}")
    return 0


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
    # filtra imagem quebrada de export Trello/Notion do Blog ("/api/attachments/..."
    # relativo ou localhost). NÃO filtra thumbnails legítimos do Google News
    # ("https://news.google.com/api/attachments/..." absoluto — 302 → encrypted-tbn gstatic, 200 image/jpeg).
    for _campo in ("imagem_url", "fonte_icon_url"):
        _v = imagem_url if _campo == "imagem_url" else fonte_icon_url
        if _v and "/api/attachments" in _v:
            _vv = _v.strip()
            if _vv.startswith("/api/attachments") or "localhost" in _vv or "127.0.0.1" in _vv:
                if _campo == "imagem_url":
                    imagem_url = ""
                else:
                    fonte_icon_url = ""
            # absoluto news.google.com/api/attachments → mantém (thumbnail real)
    titulo_norm = _normalizar_titulo(titulo)
    if not titulo_norm:
        return False
    # data_publicacao portável: COALESCE(?, datetime('now')) quebra no PG quando ? é NULL
    # em alguns proxies; calcula agora em Python quando ausente.
    if not data_publicacao:
        data_publicacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    import time as _t
    for tentativa in range(3):
        conn = get_connection()
        try:
            cur = conn.cursor()
            # dedup O(1) indexado por URL (UNIQUE) e titulo_norm (idx_noticia_titulo_norm) — sem full-scan
            cur.execute("SELECT 1 FROM tb_noticia WHERE url=? OR titulo_norm=? LIMIT 1", (url, titulo_norm))
            if cur.fetchone():
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False
            # transação curta: 1 INSERT por chamada
            cur.execute("""
                INSERT OR IGNORE INTO tb_noticia (titulo, titulo_norm, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (titulo, titulo_norm, fonte[:100], tema[:50] or "Geral", url, imagem_url[:2000] or "", fonte_icon_url[:2000] or "", descricao[:1000] or "", data_publicacao))
            conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if _eh_locked(e) and tentativa < 2:
                try:
                    conn.close()
                except Exception:
                    pass
                _t.sleep(0.05 * (tentativa + 1))
                continue
            _log().warning(f"inserir_noticia falhou: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return False


def inserir_noticias_lote(itens: list[dict]) -> int:
    """Insere lote em 1 transação curta (executemany) com retry locked + rollback.

    Cada item: {titulo, fonte, tema, url, imagem_url, descricao, data_publicacao, fonte_icon_url}.
    Dedup O(1) via url/titulo_norm (censura aplicada antes). Retorna qtd inserida.
    """
    if not itens:
        return 0
    try:
        from mod_intranet.censura import titulo_bloqueado as _tb
    except Exception:
        _tb = None
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vistos_url, vistos_norm, linhas = set(), set(), []
    for it in itens:
        try:
            titulo = str(it.get("titulo") or "").strip()[:500]
            url = str(it.get("url") or "").strip()[:2000]
            if not titulo or not url:
                continue
            if url.startswith("/"):
                url = "https://news.google.com" + url
            if _tb:
                try:
                    bloqueado, _ = _tb(titulo)
                    if bloqueado:
                        continue
                except Exception:
                    pass
            norm = _normalizar_titulo(titulo)
            if not norm or url in vistos_url or norm in vistos_norm:
                continue
            vistos_url.add(url)
            vistos_norm.add(norm)
            linhas.append((
                titulo, norm,
                str(it.get("fonte") or "")[:100],
                str(it.get("tema") or "Geral")[:50] or "Geral",
                url,
                str(it.get("imagem_url") or "")[:2000],
                str(it.get("fonte_icon_url") or "")[:2000],
                str(it.get("descricao") or "")[:1000],
                it.get("data_publicacao") or agora,
            ))
        except Exception:
            continue
    if not linhas:
        return 0
    import time as _t
    for tentativa in range(3):
        conn = get_connection()
        try:
            cur = conn.cursor()
            # filtra já-existentes em 1 SELECT por coluna (evita N roundtrips)
            try:
                exist_url = set()
                for i in range(0, len(linhas), 500):
                    bloco = [r[4] for r in linhas[i:i + 500]]
                    ph = ",".join(["?"] * len(bloco))
                    cur.execute(f"SELECT url FROM tb_noticia WHERE url IN ({ph})", bloco)
                    exist_url.update(r[0] for r in cur.fetchall())
                if exist_url:
                    linhas[:] = [r for r in linhas if r[4] not in exist_url]
                if not linhas:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    return 0
            except Exception:
                pass
            try:
                exist_norm = set()
                for i in range(0, len(linhas), 500):
                    bloco = [r[1] for r in linhas[i:i + 500]]
                    ph = ",".join(["?"] * len(bloco))
                    cur.execute(f"SELECT titulo_norm FROM tb_noticia WHERE titulo_norm IN ({ph})", bloco)
                    exist_norm.update(r[0] for r in cur.fetchall())
                if exist_norm:
                    linhas[:] = [r for r in linhas if r[1] not in exist_norm]
                if not linhas:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    return 0
            except Exception:
                pass
            cur.executemany("""
                INSERT OR IGNORE INTO tb_noticia (titulo, titulo_norm, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, linhas)
            conn.commit()
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if _eh_locked(e) and tentativa < 2:
                try:
                    conn.close()
                except Exception:
                    pass
                _t.sleep(0.1 * (tentativa + 1))
                continue
            _log().warning(f"inserir_noticias_lote falhou: {e}")
            return 0
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return 0


# ============ COLETA (scrapy-like) ============

# ============ CORTEZIA ANTI-BAN (scraper educado) ============
# Google bloqueia por reputação de IP + padrão robotizado (429/captcha no /search
# comprovado com httpx E com Chromium real). Scrapy/Playwright/Selenium NÃO burlam:
# são o mesmo nível HTTP (Scrapy usa Twisted, fingerprintável) e o bloqueio é do IP,
# não do motor. Via viável: RSS oficial (permitido para leitores pessoais) com
# tráfego "regular": UA comum de navegador, intervalo mínimo entre requisições com
# jitter (nunca rajada), sem retry agressivo, cooldown após 429.
UA_COLETA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CORTEZIA_SEG = 1.5  # intervalo mínimo entre requisições externas (+jitter 0–1s)
COOLDOWN_429_SEG = 1800  # 30min sem HTML do Google após 429
_ULTIMA_REQ = {"t": 0.0}
_GOOGLE_HTML_BLOQUEADO_ATE = {"t": 0.0}


def _aguardar_cortezia():
    """Espaça requisições externas (nunca rajada) com jitter anti-padrão."""
    import time
    import random
    agora = time.monotonic()
    espera = CORTEZIA_SEG + random.uniform(0, 1.0) - (agora - _ULTIMA_REQ["t"])
    if espera > 0:
        time.sleep(espera)
    _ULTIMA_REQ["t"] = time.monotonic()


def _url_ja_coletada(url: str) -> bool:
    """Pré-checagem para NÃO buscar og:image de notícia repetida (economiza requisições)."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM tb_noticia WHERE url=? LIMIT 1", (url,))
            return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False


def _get_html(url: str, timeout=12) -> str:
    try:
        import httpx
        import time as _time
        _aguardar_cortezia()
        r = httpx.get(url, timeout=timeout, follow_redirects=False, headers={"User-Agent": UA_COLETA})
        if r.status_code == 200:
            return r.text
        if r.status_code == 429 and "news.google.com" in url and "/rss/" not in url:
            _GOOGLE_HTML_BLOQUEADO_ATE["t"] = _time.monotonic() + 60
            return ""
        return ""
    except Exception as e:
        _log().warning(f"_get_html falhou {url}: {e}")
    return ""



def _normalizar_imagem_url(url: str, base: str = "https://news.google.com") -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base.rstrip("/") + url
    if url.startswith("http"):
        return url
    # handle srcset first url
    if "," in url:
        # srcset may contain multiple URLs, take first
        url = url.split(",")[0].strip().split(" ")[0]
    return url


def _coletar_google(url: str, fonte_nome: str, tema: str) -> int:
    import time
    if time.monotonic() < _GOOGLE_HTML_BLOQUEADO_ATE["t"]:
        _log().warning(f"_coletar_google {fonte_nome}: pulado (cooldown 429 ativo)")
        return 0
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
            # normaliza relativo "/api/attachments/..." → absoluto news.google.com (senão cai no fallback localhost)
            img_article = _normalizar_imagem_url(img_article, base="https://news.google.com")
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
                art_img = "" if "faviconV2" in img else _normalizar_imagem_url(img, base="https://news.google.com")
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
        for x in sel.css(".bbc-uk8dsi, .bbc-19j92fr, article, a[href*='/portuguese/articles'], a[href*='/topics']"):
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


def _og_image(url: str, timeout=6) -> str:
    """Busca miniatura via og:image/twitter:image da página (RSS não traz imagem).
    Fail-soft: qualquer falha retorna '' (notícia é salva mesmo sem imagem).
    NOTA: httpx bloqueante por item, SEMPRE fora de transação (nunca segura lock do banco);
    pré-checado via _url_ja_coletada para evitar requisição inútil em repetidas."""
    if not url or not url.startswith("http"):
        return ""
    try:
        import httpx
        _aguardar_cortezia()
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": UA_COLETA})
        if r.status_code != 200 or not r.text:
            return ""
        for tag in re.findall(r"<meta[^>]+>", r.text[:200000], re.I):
            if "og:image" in tag or "twitter:image" in tag:
                m = re.search(r'content=["\']([^"\']+)', tag)
                if m and m.group(1).startswith("http"):
                    return m.group(1).strip()
    except Exception as e:
        _log().warning(f"_og_image falhou {url[:80]}: {e}")
    return ""


def _coletar_rss(url: str, fonte_nome: str, tema: str) -> int:
    xml = _get_html(url)
    if not xml:
        return 0
    try:
        import parsel
        sel = parsel.Selector(text=xml, type="xml")
        candidatos: list[dict] = []
        for item in sel.css("item"):
            txt = (item.css("title::text").get() or "").strip()
            href = (item.css("link::text").get() or item.css("link::attr(href)").get() or "").strip()
            # resumo: description (todos os nós de texto, cobre CDATA e HTML interno) com fallback content:encoded
            try:
                _partes = [t.strip() for t in item.css("description ::text").getall() if (t or "").strip()]
                desc = re.sub(r"\s+", " ", " ".join(_partes)).strip()
            except Exception:
                desc = ""
            if not desc:
                try:
                    _partes = [t.strip() for t in item.css("content\\:encoded ::text").getall() if (t or "").strip()]
                    desc = re.sub(r"\s+", " ", " ".join(_partes)).strip()
                except Exception:
                    desc = ""
            # Google RSS devolve description com HTML (<a>titulo</a><font>fonte</font>) — limpa para texto
            if desc and "<" in desc:
                try:
                    import html as _html
                    desc = _html.unescape(desc)
                    desc = re.sub(r"<[^>]+>", " ", desc)
                    desc = re.sub(r"\s+", " ", desc).strip()
                except Exception:
                    pass
            # suprime resumo redundante (só repete título/fonte, ex: Google RSS "titulo Fonte") — card oculta desc vazia
            try:
                import unicodedata as _ud
                def _nn(s):
                    return _ud.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()
                _dt, _tt = _nn(desc), _nn(txt)
                if desc and (_dt == _tt or _dt.startswith(_tt) or _tt.startswith(_dt)):
                    desc = ""
            except Exception:
                pass
            raw_time = (item.css("pubDate::text").get() or item.css("dc\\:date::text").get() or item.css("published::text").get() or "").strip()
            data_pub = _parse_data_pub(raw_time) if raw_time else None
            img = ""
            m = item.css("media\\:content::attr(url)").get()
            if m:
                img = m.strip()
            if not img:
                # BBC usa media:thumbnail direto no RSS
                m = item.css("media\\:thumbnail::attr(url)").get()
                if m:
                    img = m.strip()
            if not img:
                # tenta enclosure
                enc = item.css("enclosure::attr(url)").get()
                if enc and any(enc.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".webp")):
                    img = enc.strip()
            # fonte real via <source>Nome</source> (ex: G1) + ícone favicon (Google RSS não traz imagem)
            fonte_real = (item.css("source::text").get() or "").strip() or (fonte_nome or "RSS")
            fonte_icon = ""
            try:
                source_url = (item.css("source::attr(url)").get() or "").strip()
                _dom = ""
                if source_url:
                    _dom = re.sub(r"^https?://", "", source_url).split("/")[0].strip()
                if not _dom and href:
                    _dom = re.sub(r"^https?://", "", href).split("/")[0].strip()
                if _dom:
                    from urllib.parse import quote as _qd
                    fonte_icon = f"https://www.google.com/s2/favicons?domain={_qd(_dom)}&sz=32"
            except Exception:
                fonte_icon = ""
            if not txt or not href:
                continue
            # já coletada? pula ANTES do og:image (evita requisição inútil)
            if _url_ja_coletada(href):
                continue
            # RSS (Google) não traz imagem — enriquece via og:image do link (fail-soft, fora de transação)
            if not img:
                img = _og_image(href)
            candidatos.append({"titulo": txt, "fonte": fonte_real, "tema": tema, "url": href,
                               "imagem_url": img, "descricao": (desc or txt)[:500],
                               "data_publicacao": data_pub, "fonte_icon_url": fonte_icon})
            if len(candidatos) >= 15:
                break
        # 1 transação curta em lote (executemany + retry locked + rollback) — sem N conexões
        return inserir_noticias_lote(candidatos)
    except Exception as e:
        _log().warning(f"_coletar_rss {fonte_nome}: {e}")
        return 0


def _coletar_pesquisa_google(termo: str, tema: str = "Geral") -> int:
    """Coleta por termo livre via RSS (HTML /search retorna 429/captcha para scraper)."""
    if not termo:
        return 0
    try:
        from urllib.parse import quote as _q
        url = f"https://news.google.com/rss/search?q={_q(termo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        return _coletar_rss(url, f"Pesquisa:{termo}", tema)
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
