"""Blog module — access to db_mod_blog.db (WAL) and business rules.

Módulo Blog — acesso ao db_mod_blog.db (WAL) e regras de negócio.

CRUD de postagens/comentários com sanitização nh3 (whitelist configurável),
config local do módulo (tb_config), formatação rica para exibição
(títulos/imagens/justificado) e modos de exibição histórico/única/carrossel.
Semeia postagens de guia "Como usar" em bancos recém-criados e expõe
configs do carrossel (tempo e ids selecionados).
Escritas relevantes auditam via `audit_reg` (wrapper fail-soft de
`audit_log`, banco exclusivo de auditoria).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import os
import html
import re
from html.parser import HTMLParser

from mod_intranet.bd_conexao import get_connection, DB_PATH, get_config, set_config
from mod_intranet.crud_base import CrudBase, audit_reg
from mod_intranet.decoradores import requer_pode_publicar, auditado, falha_suave
from nh3 import clean

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")

# Conjunto de tags permitidas para o sistema de blog (padrão; editável em
# tb_config central na chave 'blog_tags_permitidas', CSV)
_TAGS_PADRAO = "b,i,u,strong,em,p,a,img,h1,h2,h3,ul,ol,li,blockquote,code,pre"
TAGS_PERMITIDAS = set(_TAGS_PADRAO.split(","))


def _log():
    """Logger do módulo (loguru) — arquivo dedicado logs/blog_<data>.log."""
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


# Fence de bloco Mermaid no conteúdo (```mermaid ... ```). O nh3 escapa
# entidades HTML no texto armazenado; ao extrair, revertemos com html.unescape.
_FENCE_MERMAID = re.compile(r"```mermaid[ \t]*\r?\n(.*?)```", re.DOTALL)


def obter_habilitar_mermaid():
    """Whether Mermaid diagrams are enabled in posts (configurable).

    Lê `blog_habilitar_mermaid` da config local (default '1' = habilitado);
    valores '0'/'false'/'off' desabilitam. Falha de leitura cai em habilitado."""
    try:
        v = (get_config_local("blog_habilitar_mermaid", "1") or "1").strip().lower()
        return v not in ("0", "false", "off", "nao", "não")
    except Exception:
        _log().warning("falha ao ler 'blog_habilitar_mermaid'; assumindo habilitado")
        return True


def extrair_segmentos_mermaid(conteudo):
    """Splits sanitized post content into ('texto'|'mermaid', trecho) segments.

    Divide o conteúdo sanitizado em segmentos: 'texto' (renderizado via
    `formatar_conteudo_para_exibicao`) e 'mermaid' (blocos ```mermaid,
    com entidades HTML revertidas para sintaxe Mermaid). Retorna lista de
    tuplas (tipo, trecho)."""
    if not conteudo:
        return [("texto", "")]
    segmentos = []
    pos = 0
    for m in _FENCE_MERMAID.finditer(conteudo):
        if m.start() > pos:
            segmentos.append(("texto", conteudo[pos:m.start()]))
        corpo_mermaid = html.unescape(m.group(1)).strip()
        if corpo_mermaid:
            segmentos.append(("mermaid", corpo_mermaid))
        pos = m.end()
    if pos < len(conteudo):
        segmentos.append(("texto", conteudo[pos:]))
    if not segmentos:
        segmentos = [("texto", conteudo)]
    return segmentos


_crud = CrudBase(DB_BLOG_PATH, "blog")

# Autor padrão usado no seed de postagens de guia "Como usar" (inseridas
# quando o banco do blog é criado do zero).
AUTOR_PADRAO = "master"

# Postagens de guia de uso voltadas ao usuário comum (não administrativo),
# cada uma encerrando com um fluxograma Mermaid (```mermaid) ao final. São
# semeadas automaticamente em bancos novos (tabela vazia) por `init_db`.
POSTAGENS_PADRAO = [
    {
        "titulo": "Editor de PDF — Como usar",
        "conteudo": """**Editor de PDF** — um espaço pessoal e rápido para trabalhar com seus PDFs: enviar, reduzir, juntar, cortar, dividir, verificar e baixar. Cada usuário só enxerga os próprios arquivos.

# Como usar
- **Envie** seus PDFs pelo campo *Envie um ou mais PDFs* (arraste ou clique; só aceita .pdf).
- **Marque** na tabela os arquivos que quer usar. A ordem de marcação é a ordem do **Juntar**.
- Escolha a operação: **Juntar**, **Reduzir**, **Cortar** ou **Dividir**.
- **Baixe** o resultado (ZIP ou arquivos individuais).
- **Exclua** o que não precisa para liberar espaço.

# Dicas
- Os arquivos **expirem automaticamente** em alguns minutos — conclua o trabalho com calma, mas não deixe para depois.
- Para reduzir, use o modo **Leve** no dia a dia; o **Agressivo** transforma texto em imagem (perde a busca no texto).
- Você tem uma **cota de espaço** por usuário — exclua PDFs antigos para liberar.

# Limites
- Cada usuário **só vê os próprios arquivos**.
- O upload em lote tem limite de arquivos e de tamanho por vez.

```mermaid
flowchart TD
    A[Entrar em Editor de PDF] --> B[Enviar um ou mais PDFs]
    B --> C[Selecionar os arquivos na lista]
    C --> D[Escolher a operação]
    D -->|Juntar| E[Juntar selecionados]
    D -->|Reduzir| F[Reduzir tamanho]
    D -->|Cortar ou dividir| G[Cortar / Dividir páginas]
    E --> H[Baixar o resultado]
    F --> H
    G --> H
    H --> I[Baixar ou excluir ao terminar]
```""",
    },
    {
        "titulo": "Solicitação de Impressão — Como usar",
        "conteudo": """**Solicitação de Impressão** — central de pedidos de impressão. Anexe seus PDFs, escolha as opções e envie a solicitação. O pedido pode precisar de **autorização** e é impresso pelo setor responsável.

# Como usar
- Na aba **Nova Solicitação**, **anexe os PDFs** (até 10 por solicitação).
- Preencha: **quantidade de cópias**, **tamanho do papel**, **cor** e, se aplicável, **frente e verso**.
- Se desmarcar *papel sulfite*, você deve **levar o papel**.
- Escolha a **secretaria** (e o setor, se houver) e clique **Enviar solicitação**.
- Acompanhe em **Minhas Solicitações** o andamento de cada pedido.

# Status possíveis
- **Autorizado** — pronto para impressão.
- **Aguardando autorização** — o responsável vai avaliar.
- **Excedente de cota** — ultrapassou a cota do mês; precisa de autorização.
- **Recusado / Cancelado / Impresso** — fim do fluxo.

# Dicas
- Enquanto o pedido estiver pendente/aguardando, você pode **cancelar** em *Minhas Solicitações*.
- Baixe o **PDF com marca d'água** se precisar conferir.
- Cada arquivo anexado gera **uma solicitação separada** com as mesmas opções.

```mermaid
flowchart TD
    A[Entrar em Solicitação de Impressão] --> B[Aba Nova Solicitação]
    B --> C[Anexar PDFs]
    C --> D[Preencher opções: cópias, papel, cor, frente e verso]
    D --> E[Escolher secretaria / setor]
    E --> F[Enviar solicitação]
    F --> G{Acompanhar status}
    G -->|Aguardando autorização| H[Responsável autoriza]
    G -->|Autorizado| I[Setor imprime]
    G -->|Excedente de cota| J[Depende de autorização]
    G -->|Recusado ou cancelado| K[Revisar e enviar de novo]
```""",
    },
    {
        "titulo": "Empenhos — Como usar",
        "conteudo": """**Empenhos** — o módulo monitora as pastas com PDFs de empenhos, **extrai automaticamente** o número e organiza/renomeia os documentos. Você pode navegar, processar, pesquisar e solicitar o envio de um documento.

# Como usar
- Na aba **Navegar**, abra as pastas monitoradas e veja os PDFs com status **processado** (verde) ou **pendente** (laranja).
- **Processe** os pendentes (na aba **Fila Renomeação** ou pela ação na pasta) — o módulo renomeia e organiza sozinho.
- Use o botão **Baixar** para obter o documento já processado.
- **Solicite o envio** por e-mail quando precisar que o documento seja enviado a alguém.
- Na aba **Pesquisar**, busque por conteúdo nos empenhos indexados.

# Dicas
- A renomeação usa o **número do empenho** lido do próprio PDF (texto ou OCR).
- Documentos **pendentes** podem ser solicitados sempre; **processados** dependem de liberação do administrador.
- O histórico das solicitações fica na aba **Solicitação**.

```mermaid
flowchart TD
    A[Entrar em Empenhos] --> B[Aba Navegar: abrir pastas]
    B --> C{PDF pendente?}
    C -->|Sim| D[Processar / revisar renomeação]
    C -->|Não| E[Ver arquivos processados]
    D --> F[Baixar ou solicitar envio]
    E --> F
    F --> G[Pesquisar na aba Pesquisar]
```""",
    },
]


def _semear_postagens_padrao(cur):
    """Seeds default 'How to use' posts into an empty posts table.

    Insere as postagens de guia (POSTAGENS_PADRAO) apenas quando a tabela
    `tb_postagens` está vazia (banco recém-criado), sanitizando título e
    conteúdo com nh3. Todas recebem o MESMO `data_criacao`: o momento de
    criação do banco (instante em que a semeadura roda no bootstrap), em
    horário local. Nunca sobrescreve postagens existentes (idempotente).
    Falha na semeadura é registrada no loguru e não interrompe o bootstrap."""
    try:
        existentes = cur.execute(
            "SELECT COUNT(*) FROM tb_postagens").fetchone()[0]
        if existentes:
            return
        import datetime as _dt
        momento_criacao = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _p in POSTAGENS_PADRAO:
            _titulo = _sanitizar_texto(_p["titulo"])
            _conteudo = _sanitizar_texto(_p["conteudo"])
            cur.execute(
                "INSERT INTO tb_postagens (titulo, conteudo, autor, "
                "data_criacao) VALUES (?, ?, ?, ?)",
                (_titulo, _conteudo, AUTOR_PADRAO, momento_criacao))
        _log().info(f"semeadas {len(POSTAGENS_PADRAO)} postagens padrão no "
                    f"blog (autor '{AUTOR_PADRAO}', data de criação "
                    f"{momento_criacao})")
    except Exception:
        _log().exception("semeadura de postagens padrão falhou no init_db")


def init_db():
    """Creates tables and local config seeds (idempotent bootstrap, via CrudBase).

    Cria `tb_postagens`, `tb_comentarios` (FK CASCADE) e a `tb_config` LOCAL
    do módulo com os padrões (`blog_modo_exibicao`, `blog_postagem_unica_id`,
    `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header`,
    `blog_habilitar_mermaid`, `blog_carrossel_tempo`,
    `blog_carrossel_postagens_ids`) e semeia as postagens de guia "Como usar"
    (apenas em banco recém-criado). Executado no import e pelo
    bootstrap central; nunca sobrescreve edições manuais. O DDL e os seeds
    rodam numa única transação de `CrudBase.transacao` (commit/rollback e
    fechamento garantidos)."""
    with _crud.transacao() as cur:
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
            ("blog_postagem_unica_id", ""),  # id fixado no modo 'unica' (vazio = mais recente)
            ("blog_largura_imagem", "200-400"),
            ("blog_tags_permitidas", _TAGS_PADRAO),
            ("blog_texto_header", "Comunique novidades para toda a equipe."),
            ("blog_habilitar_mermaid", "1"),  # '1' habilita diagramas Mermaid
            ("blog_carrossel_tempo", "10"),  # segundos por slide no modo carrossel
            ("blog_carrossel_postagens_ids", ""),  # CSV de ids exibidos no carrossel
        ):
            cur.execute("INSERT OR IGNORE INTO tb_config (chave, valor) VALUES (?, ?)",
                        (_chave_local, _valor))
        # Postagens de guia "Como usar" (apenas em banco recém-criado, tabela vazia).
        _semear_postagens_padrao(cur)


def get_config_local(chave, default=""):
    """Reads the module's local tb_config (db_mod_blog.db) via CrudBase.

    Lê configuração da tabela tb_config local do módulo; falha de leitura
    registra warning no loguru e devolve `default` (fail-soft, igual ao
    comportamento original)."""
    try:
        row = _crud.obter("SELECT valor FROM tb_config WHERE chave=?", (chave,))
        return row[0] if row else default
    except Exception as e:
        _log().warning(f"get_config_local: falha ao ler '{chave}': {e}")
        return default


def set_config_local(chave, valor):
    """Writes the module's local tb_config (db_mod_blog.db) via CrudBase.

    Grava configuração da tabela tb_config local (upsert); falha registra
    exception no loguru e devolve `False` (fail-soft, igual ao original)."""
    try:
        _crud.criar(
            "INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor))
        return True
    except Exception as e:
        _log().exception(f"set_config_local: falha ao gravar '{chave}': {e}")
        return False


def listar_config_local():
    """Lists the module's local config keys (ordered) via CrudBase.

    Lista as chaves de configuração local do módulo blog, ordenadas por
    chave."""
    return _crud.listar("SELECT chave, valor FROM tb_config ORDER BY chave")


def _ordem_sql(ordem):
    """Converte ordem ('ASC'/'DESC') para SQL seguro."""
    ordem = ordem.strip().upper()
    if ordem in ("ASC", "DESC"):
        return ordem
    return "DESC"


def listar_postagens(ativo=True, ordem="DESC"):
    """Lists posts (id, titulo, conteudo, autor, data_criacao) with ordering.

    Lista postagens do banco próprio. `ativo=None` retorna todas (ativas e
    inativas — usado pela gestão de despublicadas); `ordem` aceita apenas
    'ASC'/'DESC' (validado por `_ordem_sql`, qualquer outro valor cai em
    'DESC' — imune a injeção na cláusula ORDER BY)."""
    order = _ordem_sql(ordem)
    if ativo is None:
        return _crud.listar(
            "SELECT id, titulo, conteudo, autor, data_criacao "
            f"FROM tb_postagens ORDER BY data_criacao {order}")
    return _crud.listar(
        "SELECT id, titulo, conteudo, autor, data_criacao "
        f"FROM tb_postagens WHERE ativo=? ORDER BY data_criacao {order}",
        (1 if ativo else 0,))


def contar_postagens(ativo=True):
    """Contagem de postagens no banco do blog (db_mod_blog.db, via CrudBase)."""
    return _crud.obter("SELECT COUNT(*) FROM tb_postagens WHERE ativo=?",
                       (1 if ativo else 0,))[0]


def obter_postagem(id_post):
    """Fetches a single post with all columns (via CrudBase).

    Busca postagem por id com todas as colunas (incl. `ativo`/
    `data_atualizacao`); retorna `None` quando inexistente."""
    return _crud.obter(
        "SELECT id, titulo, conteudo, autor, data_criacao, "
        "data_atualizacao, ativo FROM tb_postagens WHERE id=?", (id_post,))


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


@falha_suave(default=None, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="criar_postagem")
def criar_postagem(titulo, conteudo, autor):
    """Creates a post (sanitized) after checking publish permission.

    Valida permissão (`_pode_publicar`), sanitiza título e conteúdo com nh3,
    grava no banco próprio, audita `criar_postagem` e registra no loguru.
    Retorna o id criado ou None em falha/sem permissão."""
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    post_id = _crud.criar(
        "INSERT INTO tb_postagens (titulo, conteudo, autor) VALUES (?, ?, ?)",
        (titulo_sanitizado, conteudo_sanitizado, autor))
    _log().info(f"postagem criada #{post_id} por {autor}")
    return post_id


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="atualizar_postagem")
def atualizar_postagem(id_post, titulo, conteudo, autor):
    """Updates title/content (sanitized) after checking permission. Returns bool.

    Valida permissão, sanitiza com nh3, atualiza `data_atualizacao` e audita
    `atualizar_postagem`. False em falha/sem permissão/postagem inexistente."""
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    afetadas = _crud.atualizar(
        "UPDATE tb_postagens SET titulo=?, conteudo=?, "
        "data_atualizacao=datetime('now') WHERE id=?",
        (titulo_sanitizado, conteudo_sanitizado, id_post))
    _log().info(f"postagem atualizada #{id_post} por {autor}")
    return afetadas > 0


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="excluir_postagem")
def excluir_postagem(id_post, autor):
    """Soft-deletes a post (ativo=0) after checking permission. Returns bool."""
    afetadas = _crud.atualizar(
        "UPDATE tb_postagens SET ativo=0 WHERE id=?", (id_post,))
    _log().info(f"postagem excluída (ativo=0) #{id_post} por {autor}")
    return afetadas > 0


@falha_suave(default=(0, 0), nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="excluir_postagens_em_lote")
def excluir_postagens_em_lote(ids, autor):
    """Soft-deletes multiple posts (ativo=0) after checking permission. Returns (ok_count, falha_count)."""
    if not ids:
        return 0, 0
    ok, falha = 0, 0
    for pid in ids:
        try:
            pid_int = int(pid)
        except (ValueError, TypeError):
            falha += 1
            continue
        try:
            afetadas = _crud.atualizar(
                "UPDATE tb_postagens SET ativo=0 WHERE id=?", (pid_int,))
            if afetadas and afetadas > 0:
                ok += 1
            else:
                falha += 1
        except Exception:
            _log().exception(f"Erro ao excluir postagem #{pid_int} em lote")
            falha += 1
    if ok:
        _log().info(f"exclusão em lote: {ok} postagem(ns) por {autor} (falhas: {falha})")
    return ok, falha


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="despublicar_postagem")
def despublicar_postagem(id_post, autor):
    """Remove uma postagem da exibição pública (ativo=0, despublicar).

    Equivale a ocultar do histórico sem a remover do banco. Permite republicar
    posteriormente via publicar_postagem.
    """
    afetadas = _crud.atualizar(
        "UPDATE tb_postagens SET ativo=0 WHERE id=?", (id_post,))
    _log().info(f"postagem despublicada (ativo=0) #{id_post} por {autor}")
    return afetadas > 0


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="publicar_postagem")
def publicar_postagem(id_post, autor):
    """Reativa/publica uma postagem despublicada (ativo=1)."""
    afetadas = _crud.atualizar(
        "UPDATE tb_postagens SET ativo=1 WHERE id=?", (id_post,))
    _log().info(f"postagem republicada (ativo=1) #{id_post} por {autor}")
    return afetadas > 0


def listar_comentarios(postagem_id):
    """Lists comments of a post in chronological order (via CrudBase).

    Lista `(id, autor, conteudo, data_criacao)` dos comentários da
    postagem, ordenados cronologicamente."""
    return _crud.listar(
        "SELECT id, autor, conteudo, data_criacao FROM tb_comentarios "
        "WHERE postagem_id=? ORDER BY data_criacao", (postagem_id,))


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="criar_comentario")
def criar_comentario(postagem_id, autor, conteudo):
    """Creates a sanitized comment after checking permission. Returns bool.

    Regra do módulo: usuário comum não comenta — a tentativa é bloqueada com
    warning no loguru. Conteúdo sanitizado com nh3; audita `criar_comentario`."""
    conteudo_sanitizado = _sanitizar_texto(conteudo)
    _crud.criar(
        "INSERT INTO tb_comentarios (postagem_id, autor, conteudo) VALUES (?, ?, ?)",
        (postagem_id, autor, conteudo_sanitizado))
    _log().info(f"comentario criado na postagem #{postagem_id} por {autor}")
    return True


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
    """Retorna o modo de exibição do blog ('unica', 'historico' ou 'carrossel').

    Lê a config local; default histórico.
    """
    try:
        modo = (get_config_local("blog_modo_exibicao", "historico") or "historico").strip()
        return modo if modo in ("unica", "historico", "carrossel") else "historico"
    except Exception:
        return "historico"


def obter_postagem_unica_id():
    """Retorna o id da postagem fixada no modo 'unica' (None = mais recente).

    Lê `blog_postagem_unica_id` da config local; valor ausente/inválido
    devolve `None` — o feed exibe a publicação mais recente (comportamento
    automático herdado do padrão anterior).
    """
    try:
        raw = (get_config_local("blog_postagem_unica_id", "") or "").strip()
        return int(raw) if raw else None
    except (ValueError, TypeError):
        return None


def definir_postagem_unica_id(pid):
    """Fixa o id da postagem exibida no modo 'unica' (None/'' = mais recente).

    Grava `blog_postagem_unica_id` na config local (upsert); `None`/'' limpa
    a fixação, voltando a exibir a mais recente. Retorna `True` em sucesso
    (fail-soft via `set_config_local`).
    """
    return set_config_local("blog_postagem_unica_id",
                            "" if pid is None else str(int(pid)))


def obter_carrossel_tempo():
    """Returns the carousel slide interval (seconds) from local config.

    Lê `blog_carrossel_tempo` (segundos por slide no modo carrossel); default
    10. Valores inválidos (não numéricos) caem no padrão 10."""
    try:
        v = (get_config_local("blog_carrossel_tempo", "10") or "10").strip()
        return max(1, int(v))
    except (ValueError, TypeError):
        return 10


def definir_carrossel_tempo(segundos):
    """Sets the carousel slide interval (seconds) in local config. Returns bool.

    Grava `blog_carrossel_tempo` (upsert); valores <= 0 são fixados em 1.
    Fail-soft via `set_config_local`."""
    try:
        s = max(1, int(segundos))
    except (ValueError, TypeError):
        return False
    return set_config_local("blog_carrossel_tempo", str(s))


def obter_carrossel_postagens_ids():
    """Returns the list of post ids selected for the carousel mode.

    Lê `blog_carrossel_postagens_ids` (CSV de ids) da config local; devolve
    lista de inteiros (vazia quando ausente). Ordem preserva a seleção.
    Falha de leitura registra warning e devolve lista vazia (fail-soft)."""
    try:
        raw = (get_config_local("blog_carrossel_postagens_ids", "") or "").strip()
        ids = []
        for parte in raw.split(","):
            parte = parte.strip()
            if not parte.isdigit():
                continue
            ids.append(int(parte))
        return ids
    except Exception:
        _log().warning("falha ao ler 'blog_carrossel_postagens_ids'; "
                       "assumindo lista vazia")
        return []


def definir_carrossel_postagens_ids(ids):
    """Stores the ordered post id list for carousel mode. Returns bool.

    Grava `blog_carrossel_postagens_ids` como CSV (upsert); ids inválidos são
    ignorados. Fail-soft via `set_config_local`."""
    try:
        validos = []
        for i in ids:
            try:
                n = int(i)
            except (ValueError, TypeError):
                continue
            if n not in validos:
                validos.append(n)
        csv_ = ",".join(str(i) for i in validos)
        return set_config_local("blog_carrossel_postagens_ids", csv_)
    except Exception:
        _log().exception("falha ao gravar 'blog_carrossel_postagens_ids'")
        return False


def listar_postagens_por_ids(ids, ativo=True):
    """Lists posts matching the given ordered ids (carousel selection).

    Retorna postagens (id, titulo, conteudo, autor, data_criacao) na ordem
    informada em `ids`, filtrando `ativo`; ids inexistentes são ignorados.
    Imune a injeção (placeholders `?` por id). Falha registra exception e
    devolve lista vazia (fail-soft)."""
    try:
        if not ids:
            return []
        marcador = ",".join("?" * len(ids))
        if ativo is not None:
            params = [1 if ativo else 0] + list(ids)
            sql = (f"SELECT id, titulo, conteudo, autor, data_criacao "
                   f"FROM tb_postagens WHERE ativo=? AND id IN ({marcador})")
        else:
            params = list(ids)
            sql = (f"SELECT id, titulo, conteudo, autor, data_criacao "
                   f"FROM tb_postagens WHERE id IN ({marcador})")
        linhas = _crud.listar(sql, tuple(params))
        pos = {i: idx for idx, i in enumerate(ids)}
        linhas.sort(key=lambda r: pos.get(r[0], 10**9))
        return linhas
    except Exception:
        _log().exception("falha ao listar postagens por ids (carrossel)")
        return []