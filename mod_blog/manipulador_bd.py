import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os
import html
from html.parser import HTMLParser

from mod_intranet.conexao_bd import get_connection, DB_PATH, get_config, set_config
from mod_intranet.manipulador_bd import audit_log
from nh3 import clean

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")

# Conjunto de tags permitidas para o sistema de blog (padrão; editável em
# tb_config central na chave 'blog_tags_permitidas', CSV)
_TAGS_PADRAO = "b,i,u,strong,em,p,a,img,h1,h2,h3,ul,ol,li,blockquote,code,pre"
TAGS_PERMITIDAS = set(_TAGS_PADRAO.split(","))


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("blog")


def tags_permitidas():
    """Lê as tags permitidas (config local do módulo primeiro, fallback na
    central), CSV; fallback no padrão."""
    try:
        csv_ = (get_config_local("blog_tags_permitidas", "") or "").strip()
        if not csv_:
            csv_ = (get_config("blog_tags_permitidas", _TAGS_PADRAO) or "").strip()
        return {t.strip().lower() for t in csv_.split(",") if t.strip()}
    except Exception:
        return set(TAGS_PERMITIDAS)


def _conn():
    conn = sqlite3.connect(DB_BLOG_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_postagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            autor TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            postagem_id INTEGER NOT NULL,
            autor TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (postagem_id) REFERENCES tb_postagens(id) ON DELETE CASCADE
        )
    """)
    # Tabela de configuração local do módulo (pedida pela Fase 3 do PLANO.md).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    # Padrões locais do módulo (idempotente; não sobrescreve edições manuais).
    for _chave_local, _valor in (
        ("blog_modo_exibicao", "historico"),  # 'unica' | 'historico'
        ("blog_largura_imagem", "200-400"),
        ("blog_tags_permitidas", _TAGS_PADRAO),
        ("blog_texto_header", "Comunique novidades para toda a equipe."),
    ):
        cur.execute("INSERT OR IGNORE INTO tb_config (chave, valor) VALUES (?, ?)",
                    (_chave_local, _valor))
    conn.commit()
    conn.close()


def get_config_local(chave, default=""):
    """Lê configuração da tabela tb_config local do módulo (db_mod_blog.db)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    except Exception:
        return default
    finally:
        conn.close()


def set_config_local(chave, valor):
    """Grava configuração na tabela tb_config local do módulo (db_mod_blog.db)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def listar_config_local():
    """Lista as chaves de configuração local do módulo blog."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT chave, valor FROM tb_config ORDER BY chave")
        return cur.fetchall()
    finally:
        conn.close()


def _ordem_sql(ordem):
    """Converte ordem ('ASC'/'DESC') para SQL seguro."""
    ordem = ordem.strip().upper()
    if ordem in ("ASC", "DESC"):
        return ordem
    return "DESC"


def listar_postagens(ativo=True, ordem="DESC"):
    conn = _conn()
    cur = conn.cursor()
    order = _ordem_sql(ordem)
    if ativo is None:
        sql = f"SELECT id, titulo, conteudo, autor, data_criacao FROM tb_postagens ORDER BY data_criacao {order}"
        cur.execute(sql)
    else:
        sql = f"SELECT id, titulo, conteudo, autor, data_criacao FROM tb_postagens WHERE ativo=? ORDER BY data_criacao {order}"
        cur.execute(sql, (1 if ativo else 0,))
    rows = cur.fetchall()
    conn.close()
    return rows


def contar_postagens(ativo=True):
    """Contagem de postagens no banco do blog (db_mod_blog.db)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_postagens WHERE ativo=?", (1 if ativo else 0,))
        return cur.fetchone()[0]
    finally:
        conn.close()


def obter_postagem(id_post):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT id, titulo, conteudo, autor, data_criacao, data_atualizacao, ativo FROM tb_postagens WHERE id=?", (id_post,))
    row = cur.fetchone()
    conn.close()
    return row


_URL_SCHEMES = {"http", "https", "data", "mailto", "relative"}
# Atributos permitidos por tag (usados na sanitização; essenciais p/ links e
# imagens, incluindo data:/URLs relativas pedidas pelo PLANO Fase 3).
_ATTRS = {
    "a": {"href"},
    "img": {"src", "alt", "title", "width", "height"},
    "code": {"class"},
    "pre": {"class"},
    "blockquote": {"class"},
}


def _sanitizar_texto(texto):
    """Sanitiza texto removendo XSS, permitindo apenas tags seguras.

    Para links e imagens são aceitos os esquemas http/https (e relativos), além
    de data: para imagens, conforme PLANO Fase 3. URLs relativas são mantidas.
    """
    if isinstance(texto, str):
        return clean(
            texto,
            tags=tags_permitidas(),
            attributes=_ATTRS,
            url_schemes=_URL_SCHEMES,
            url_relative="pass_through",
            link_rel="noopener noreferrer",
        )
    return str(texto) if texto else ""


def _pode_publicar(usuario):
    """Regra do módulo: usuário COMUM só LÊ o blog.
    Publicar/comentar/excluir é privilégio de administrador geral ou
    administrador do módulo blog."""
    if not usuario:
        return False
    from mod_intranet import autenticacao
    try:
        return autenticacao.pode_publicar_no_blog(usuario)
    except Exception:
        return False


def criar_postagem(titulo, conteudo, autor):
    if not _pode_publicar(autor):
        _log().warning(f"'{autor}' sem permissão de publicação bloqueado")
        return None
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO tb_postagens (titulo, conteudo, autor) VALUES (?, ?, ?)",
            (titulo_sanitizado, conteudo_sanitizado, autor),
        )
        post_id = cur.lastrowid
        conn.commit()
        _log().info(f"postagem criada #{post_id} por {autor}")
        audit_log(autor, "blog", "criar_postagem", f"Postagem #{post_id} criada por {autor}")
        return post_id
    except Exception:
        _log().exception("Erro ao criar postagem")
        return None
    finally:
        conn.close()


def atualizar_postagem(id_post, titulo, conteudo, autor):
    if not _pode_publicar(autor):
        return False
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE tb_postagens SET titulo=?, conteudo=?, data_atualizacao=datetime('now') WHERE id=?",
            (titulo_sanitizado, conteudo_sanitizado, id_post),
        )
        conn.commit()
        _log().info(f"postagem atualizada #{id_post} por {autor}")
        audit_log(autor, "blog", "atualizar_postagem", f"Postagem #{id_post} atualizada por {autor}")
        return cur.rowcount > 0
    except Exception:
        _log().exception(f"Erro ao atualizar postagem #{id_post}")
        return False
    finally:
        conn.close()


def excluir_postagem(id_post, autor):
    if not _pode_publicar(autor):
        return False
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tb_postagens SET ativo=0 WHERE id=?", (id_post,))
        conn.commit()
        _log().info(f"postagem excluída (ativo=0) #{id_post} por {autor}")
        audit_log(autor, "blog", "excluir_postagem", f"Postagem #{id_post} excluída (soft delete) por {autor}")
        return cur.rowcount > 0
    except Exception:
        _log().exception(f"Erro ao excluir postagem #{id_post}")
        return False
    finally:
        conn.close()


def despublicar_postagem(id_post, autor):
    """Remove uma postagem da exibição pública (ativo=0, despublicar).

    Equivale a ocultar do histórico sem a remover do banco. Permite republicar
    posteriormente via publicar_postagem.
    """
    if not _pode_publicar(autor):
        return False
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tb_postagens SET ativo=0 WHERE id=?", (id_post,))
        conn.commit()
        _log().info(f"postagem despublicada (ativo=0) #{id_post} por {autor}")
        audit_log(autor, "blog", "despublicar_postagem",
                  f"Postagem #{id_post} despublicada por {autor}")
        return cur.rowcount > 0
    except Exception:
        _log().exception(f"Erro ao despublicar postagem #{id_post}")
        return False
    finally:
        conn.close()


def publicar_postagem(id_post, autor):
    """Reativa/publica uma postagem despublicada (ativo=1)."""
    if not _pode_publicar(autor):
        return False
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tb_postagens SET ativo=1 WHERE id=?", (id_post,))
        conn.commit()
        _log().info(f"postagem republicada (ativo=1) #{id_post} por {autor}")
        audit_log(autor, "blog", "publicar_postagem",
                  f"Postagem #{id_post} republicada por {autor}")
        return cur.rowcount > 0
    except Exception:
        _log().exception(f"Erro ao republicar postagem #{id_post}")
        return False
    finally:
        conn.close()


def listar_comentarios(postagem_id):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT id, autor, conteudo, data_criacao FROM tb_comentarios WHERE postagem_id=? ORDER BY data_criacao", (postagem_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def criar_comentario(postagem_id, autor, conteudo):
    if not _pode_publicar(autor):
        _log().warning(f"'{autor}' sem permissão de comentar bloqueado")
        return False
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO tb_comentarios (postagem_id, autor, conteudo) VALUES (?, ?, ?)",
            (postagem_id, autor, conteudo_sanitizado),
        )
        conn.commit()
        _log().info(f"comentario criado na postagem #{postagem_id} por {autor}")
        audit_log(autor, "blog", "criar_comentario", f"Comentário criado na postagem #{postagem_id} por {autor}")
        return True
    except Exception:
        _log().exception(f"Erro ao criar comentario na postagem #{postagem_id}")
        return False
    finally:
        conn.close()


def _merge_style(base, extra):
    """Concatena estilos CSS sem duplicar o separador ';'."""
    base = (base or "").strip()
    if not base:
        return extra
    return base.rstrip(";") + ";" + extra


class _FormatadorBlog(HTMLParser):
    """Reescreve HTML sanitizado aplicando o padrão visual do Blog:
    - h1/h2/h3: negrito + centralizado
    - img: alinhada à esquerda, limites 200-400px, responsiva
    """

    _VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self, img_min=200, img_max=400):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.img_min = img_min
        self.img_max = img_max

    def _emit_start(self, tag, attrs):
        d = dict(attrs)
        style = d.get("style", "")
        if tag in ("h1", "h2", "h3"):
            style = _merge_style(style, "text-align:center;font-weight:bold;")
        elif tag == "img":
            style = _merge_style(
                style,
                f"float:left;margin:0 12px 12px 0;max-width:{self.img_max}px;"
                f"min-width:{self.img_min}px;",
            )
            if "loading" not in d:
                d["loading"] = "lazy"
        if style:
            d["style"] = style
        attrs_str = "".join(
            f' {k}="{html.escape(str(v), quote=True)}"' for k, v in d.items()
        )
        self.parts.append(f"<{tag}{attrs_str}>")

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self._VOID:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data))

    def getvalue(self):
        return "".join(self.parts)


def _markdown_leve(texto):
    """Conversão mínima de Markdown para HTML (sobre texto já escapado):
    - '#'/'##'/'###' -> h1/h2/h3
    - '- ' ou '* ' -> itens de lista
    - '**texto**' -> negrito
    """
    import re
    linhas = texto.split("\n")
    saida = []
    em_lista = False

    def fecha_lista():
        nonlocal em_lista
        if em_lista:
            saida.append("</ul>")
            em_lista = False

    for linha in linhas:
        if not linha.strip():
            fecha_lista()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", linha)
        if m:
            fecha_lista()
            nivel = len(m.group(1))
            saida.append(f"<h{nivel}>{m.group(2)}</h{nivel}>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", linha)
        if m:
            if not em_lista:
                saida.append("<ul>")
                em_lista = True
            saida.append(f"<li>{m.group(1)}</li>")
            continue
        fecha_lista()
        saida.append(f"<p>{linha}</p>")
    fecha_lista()
    # negrito simples **x**
    html_out = "".join(saida)
    html_out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html_out)
    return html_out


def formatar_conteudo_para_exibicao(conteudo):
    """Formata conteúdo para exibição no frontend seguindo o padrão do sistema.
    - Títulos em negrito e centralizados
    - Imagens alinhadas à esquerda, limites 200-400px responsivas
    - Texto puro/Markdown com alinhamento justificado
    - HTML sanitizado (nh3) preservado e estilizado
    """
    if not conteudo:
        return ""
    limpo = _sanitizar_texto(conteudo)
    if not limpo.strip():
        return ""
    # Sem tags HTML -> trata como texto puro/Markdown
    if "<" not in limpo:
        corpo = _markdown_leve(html.escape(limpo, quote=False))
        return f'<div style="text-align:justify">{corpo}</div>'
    # HTML sanitizado -> aplica estilos do padrão (largura de imagem configurável)
    min_l, max_l = _largura_imagem()
    parser = _FormatadorBlog(img_min=min_l, img_max=max_l)
    parser.feed(limpo)
    return f'<div style="text-align:justify">{parser.getvalue()}</div>'


def _largura_imagem():
    """Retorna (min, max) de largura de imagem a partir da config local.

    Suporta formatos '200-400' ou '200,400'; fallback do padrão do sistema.
    """
    try:
        raw = (get_config_local("blog_largura_imagem", "200-400") or "200-400").strip()
        raw = raw.replace(",", "-")
        partes = raw.split("-")
        if len(partes) == 2:
            return int(partes[0].strip()), int(partes[1].strip())
    except (ValueError, IndexError):
        pass
    return 200, 400


def obter_modo_exibicao():
    """Retorna o modo de exibição do blog ('unica' ou 'historico').

    Lê a config local; default histórico.
    """
    try:
        modo = (get_config_local("blog_modo_exibicao", "historico") or "historico").strip()
        return modo if modo in ("unica", "historico") else "historico"
    except Exception:
        return "historico"