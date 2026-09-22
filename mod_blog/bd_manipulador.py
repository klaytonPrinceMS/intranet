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
from mod_intranet.decoradores import requer_pode_publicar, requer_flag, auditado, falha_suave
from nh3 import clean

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")

# Conjunto de tags permitidas para o sistema de blog (padrão; editável em
# tb_config central na chave 'blog_tags_permitidas', CSV). `div`/`br` são
# estruturais do editor WYSIWYG (linhas e quebras) — sempre permitidas em
# `_sanitizar_texto`, sem atributos.
_TAGS_PADRAO = "b,i,u,strong,em,p,a,img,h1,h2,h3,ul,ol,li,blockquote,code,pre,div,br"
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
    try:
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
    except Exception:
        _log().exception("extrair_segmentos_mermaid: falha ao segmentar conteúdo")
        return [("texto", conteudo or "")]


_crud = CrudBase(DB_BLOG_PATH, "blog")

# Autor padrão usado no seed de postagens de guia "Como usar" (inseridas
# quando o banco do blog é criado do zero).
AUTOR_PADRAO = "master"

# Postagens de guia de uso voltadas ao usuário comum (não administrativo),
# cada uma encerrando com um fluxograma Mermaid (```mermaid) ao final. São
# semeadas automaticamente em bancos novos (tabela vazia) por `init_db`.
# PADRÃO ÚNICO (14/09/2026, espelho da postagem "Editor de PDF — Como usar"):
# `# **Título**` (faixa gigante centralizada), `### subtítulo`, parágrafo
# de apresentação e seções em **negrito** com listas; diagrama centralizado
# no render (`_renderizar_conteudo_postagem`).
POSTAGENS_PADRAO = [
    {
        "titulo": "Editor de PDF — Como usar",
        "conteudo": """# **Editor de PDF**
### Um espaço pessoal e rápido para trabalhar com seus PDFs:
Enviar, reduzir, juntar, cortar, dividir, verificar e baixar. Cada usuário só enxerga os próprios arquivos, respeitando ao máximo a Lei Geral de Proteção de Dados.

**Como usar**
- **Envie** seus PDFs pelo campo *Envie um ou mais PDFs* (arraste ou clique; só aceita .pdf, até 10 arquivos e 1024 MB por vez).
- **Marque** na tabela os arquivos que quer usar (as badges `#` mostram a ordem). A ordem de marcação é a ordem do **Juntar**.
- Escolha a operação: **Juntar selecionados**, **Reduzir**, **Cortar** ou **Dividir** — ou **Verificar integridade** para conferir um arquivo.
- **Baixe** o resultado (ZIP, arquivos individuais ou pelo menu da linha) e **Exclua** o que não precisa.
- Acompanhe a coluna **Expira em** (contagem regressiva) e os avisos de recusas nominais do lote.

**Dicas**
- Os arquivos **expirem automaticamente em 10 minutos** (padrão, ajustável pelo admin) — conclua com calma, mas não deixe para depois.
- Para reduzir, use o modo **Leve** no dia a dia; o **Agressivo** transforma texto em imagem (perde a busca no texto). Há ajustes de qualidade/DPI e 4 modos de Dividir.
- Você tem uma **cota de 1 GB** (10 GB global) — exclua PDFs antigos para liberar espaço.

```mermaid
flowchart TD
    A[Entrar em Editor de PDF] --> B[Enviar PDFs: até 10 por vez]
    B --> C[Marcar arquivos na ordem do Juntar]
    C --> D[Escolher: Juntar, Reduzir, Cortar, Dividir ou Verificar]
    D --> E[Baixar ZIP, individuais ou da linha]
    E --> F[Excluir ao terminar e liberar a cota]
```""",
    },
    {
        "titulo": "Solicitação de Impressão — Como usar",
        "conteudo": """# **Solicitação de Impressão**
### Central de pedidos de impressão:
Envie os PDFs e acompanhe tudo em um único Pedido com N arquivos e status único. Pode precisar de **autorização**; quem imprime e confirma é o admin do módulo.

**Como usar**
- Na aba **Nova Solicitação**, **anexe os PDFs** (até 10 por envio — todos entram no mesmo Pedido).
- Preencha: **cópias**, **tipo e tamanho do papel**, **cor**, **frente e verso**, **borda** (só com frente e verso) e **observações**.
- Papel **Fotográfico/Vergê**: traga o próprio papel (aviso "(trazer)").
- Escolha a **secretaria** (e o setor) e clique **Enviar solicitação**.
- Acompanhe em **Minhas Solicitações** (com contagem regressiva do rascunho) e na aba **Autorização**.

**Status possíveis**
- **Pendente** — enviado, aguardando definição (sem responsável vinculado).
- **Aguardando autorização** — o responsável vai avaliar.
- **Autorizado** — liberado; o admin ainda precisa **Imprimir e Confirmar**.
- **Excedente de cota** — ultrapassou a cota do mês; precisa de autorização.
- **Recusado** — pode **Reenviar**; **Cancelado** — sai da lista; **Impresso** — fim do fluxo (arquivos apagados do servidor).

**Dicas**
- Respeite o **limite de pedidos abertos** e a **cota em páginas**.
- A **marca d'água** é opcional e aplicada na impressão (configurada pelo admin).
- Relatórios, impressoras e cotas ficam na **Administração** do módulo.

```mermaid
flowchart TD
    A[Entrar em Solicitação] --> B[Aba Nova Solicitação: anexar até 10 PDFs]
    B --> C[Preencher cópias, papel, cor, borda e observações]
    C --> D[Enviar: 1 Pedido com N arquivos]
    D --> E{Tem responsável?}
    E -->|Não| F[Pendente]
    E -->|Sim| G[Aguardando autorização]
    G --> H[Responsável autoriza ou recusa]
    H --> I[Autorizado: admin imprime e confirma]
    I --> J[Impresso: fim]
```""",
    },
    {
        "titulo": "Empenhos — Como usar",
        "conteudo": """# **Empenhos**
### Renomeação automática dos seus empenhos:
O módulo monitora as pastas, **extrai automaticamente** o número e organiza/renomeia. O uso comum acontece na aba **Navegar**; o resto é do admin.

**Como usar (aba Navegar)**
- Abra as pastas e use a **busca integrada** (conteúdo + todos os campos).
- Status **processado** (verde) ou **pendente** (laranja); filtro **Só pendentes**, **Marcar visíveis** e envio em lote.
- **Processar pasta agora** (tudo), **Processar (auto)** ou o lápis para **revisar** (Ficha/Empenho/Parcela/Ano, tipos DOC/EC/EE/EG/AE).
- **Solicitar envio** por e-mail é livre (avulso ou em lote); **Baixar** exige liberação do admin.
- Acompanhe o **Histórico completo** na aba **Solicitação**.

**Para o admin**
- Abas **Fila Renomeação**, **Organizador** (caixas, capas, matriz, ferramentas PDF) e **Quarentena** (reprocessar a fila, separar documentos).
- Pastas locais ou de rede (UNC), template de nome e regras por campo nas Configurações.

```mermaid
flowchart TD
    A[Entrar em Empenhos: aba Navegar] --> B[Buscar ou abrir pastas]
    B --> C{PDF pendente?}
    C -->|Sim| D[Processar pasta agora, auto ou revisar]
    C -->|Não| E[Arquivo processado]
    D --> F[Solicitar envio por e-mail, livre]
    E --> G[Baixar, com liberação do admin]
    F --> H[Histórico na Solicitação]
    G --> H
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


def _garantir_carrossel_padrao(cur):
    """Garante padrão de exibição carrossel com as 3 postagens básicas.

    - Banco novo: modo já vem 'carrossel' (INSERT OR IGNORE), mas ids vazios —
      preenche com os ids das 3 postagens padrão recém-semeadas (ou das 3 primeiras ativas).
    - Banco legado: migra 'historico' + ids vazio para 'carrossel' com as mesmas 3 postagens,
      preservando escolha manual do admin quando ids já definidos.
    Idempotente: nunca sobrescreve ids já preenchidos nem modo já em 'carrossel'/'unica'.
    """
    try:
        cur.execute("SELECT valor FROM tb_config WHERE chave='blog_modo_exibicao'")
        row = cur.fetchone()
        modo = (row[0] if row else "").strip() if row else ""
        cur.execute("SELECT valor FROM tb_config WHERE chave='blog_carrossel_postagens_ids'")
        row2 = cur.fetchone()
        ids_csv = (row2[0] if row2 else "").strip() if row2 else ""
        if ids_csv:
            return  # já configurado manualmente — preserva
        # ids vazio: precisa preencher com as 3 básicas
        cur.execute("SELECT id, titulo FROM tb_postagens WHERE ativo=1 ORDER BY id")
        linhas = cur.fetchall()
        if not linhas:
            return
        # tenta casar pelas 3 básicas (sanitizadas); fallback nas 3 primeiras ativas
        esperados = {_sanitizar_texto(p["titulo"]) for p in POSTAGENS_PADRAO}
        ids_escolhidos = [str(r[0]) for r in linhas if r[1] in esperados]
        if len(ids_escolhidos) < 3:
            ids_escolhidos = [str(r[0]) for r in linhas[:3]]
        else:
            ids_escolhidos = ids_escolhidos[:3]
        if len(ids_escolhidos) < 2:
            return
        csv_ids = ",".join(ids_escolhidos)
        if modo == "historico" and not ids_csv:
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='blog_modo_exibicao'", ("carrossel",))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='blog_carrossel_postagens_ids'", (csv_ids,))
            _log().info(f"carrossel padrão garantido: migra historico→carrossel ids={csv_ids}")
        elif modo == "carrossel" and not ids_csv:
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='blog_carrossel_postagens_ids'", (csv_ids,))
            _log().info(f"carrossel padrão semeado: ids={csv_ids}")
        elif not modo:
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='blog_modo_exibicao'", ("carrossel",))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='blog_carrossel_postagens_ids'", (csv_ids,))
            _log().info(f"carrossel padrão aplicado (sem modo): ids={csv_ids}")
    except Exception as e:
        _log().warning(f"_garantir_carrossel_padrao falhou: {e}")


def init_db():
    """Creates tables and local config seeds (idempotent bootstrap, via CrudBase).

    Cria `tb_postagens`, `tb_comentarios` (FK CASCADE) e a `tb_config` LOCAL
    do módulo com os padrões (`blog_modo_exibicao` padrão ``carrossel`` com as
    3 postagens básicas, `blog_postagem_unica_id`, `blog_largura_imagem`,
    `blog_tags_permitidas`, `blog_texto_header`, `blog_habilitar_mermaid`,
    `blog_carrossel_tempo`, `blog_carrossel_postagens_ids`) e semeia as
    postagens de guia "Como usar" (apenas em banco recém-criado). Garante via
    `_garantir_carrossel_padrao` que o carrossel com as 3 básicas seja o
    padrão inclusive em bancos legados (migra ``historico``→``carrossel`` quando
    ids vazio). Executado no import e pelo bootstrap central; nunca sobrescreve
    edições manuais de ids já definidos. O DDL e os seeds rodam numa única
    transação de `CrudBase.transacao` (commit/rollback e fechamento garantidos)."""
    try:
        _init_db_seguro()
    except Exception:
        _log().exception("init_db: falha no bootstrap do blog")


def _init_db_seguro():
    """Body of `init_db`, isolated so the entry point can protect it."""
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
            ("blog_modo_exibicao", "carrossel"),  # 'unica' | 'historico' | 'carrossel' — padrão carrossel com 3 postagens básicas
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
        # Garante padrão de exibição carrossel com as 3 postagens básicas (migração + seed de ids).
        _garantir_carrossel_padrao(cur)
    # Pasta de imagens do editor (dentro do módulo; servida em /img_postagens/*).
    try:
        os.makedirs(PASTA_IMAGENS, exist_ok=True)
    except Exception:
        pass


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
    try:
        return _crud.listar("SELECT chave, valor FROM tb_config ORDER BY chave")
    except Exception as e:
        _log().exception(f"listar_config_local: falha ao listar config local | {e}")
        return []


def _ordem_sql(ordem):
    """Converte ordem ('ASC'/'DESC') para SQL seguro."""
    try:
        ordem = (ordem or "DESC").strip().upper()
        if ordem in ("ASC", "DESC"):
            return ordem
        return "DESC"
    except Exception:
        _log().warning("_ordem_sql: ordem inválida; usando DESC")
        return "DESC"


def listar_postagens(ativo=True, ordem="DESC"):
    """Lists posts (id, titulo, conteudo, autor, data_criacao) with ordering.

    Lista postagens do banco próprio. `ativo=None` retorna todas (ativas e
    inativas — usado pela gestão de despublicadas); `ordem` aceita apenas
    'ASC'/'DESC' (validado por `_ordem_sql`, qualquer outro valor cai em
    'DESC' — imune a injeção na cláusula ORDER BY)."""
    try:
        order = _ordem_sql(ordem)
        if ativo is None:
            return _crud.listar(
                "SELECT id, titulo, conteudo, autor, data_criacao "
                f"FROM tb_postagens ORDER BY data_criacao {order}")  # nosec B608 — order só ASC/DESC via _ordem_sql
        return _crud.listar(
            "SELECT id, titulo, conteudo, autor, data_criacao "
            f"FROM tb_postagens WHERE ativo=? ORDER BY data_criacao {order}",  # nosec B608 — order só ASC/DESC via _ordem_sql
            (1 if ativo else 0,))
    except Exception as e:
        _log().exception(f"listar_postagens: falha ao listar postagens | {e}")
        return []


def contar_postagens(ativo=True):
    """Contagem de postagens no banco do blog (db_mod_blog.db, via CrudBase)."""
    try:
        return _crud.obter("SELECT COUNT(*) FROM tb_postagens WHERE ativo=?",
                           (1 if ativo else 0,))[0]
    except Exception as e:
        _log().exception(f"contar_postagens: falha ao contar postagens | {e}")
        return 0


def remover_vinculos_usuario(user_nome):
    """Remove postagens e comentários do usuário (LGPD).

    Chamado pelo módulo de gestão de usuários na exclusão definitiva:
    cada módulo limpa o PRÓPRIO banco (isolamento total — sem cross-query
    entre bancos). Sem o arquivo do banco no SQLite, limpa a cópia legada
    do banco central. Retorna o nº de postagens removidas."""
    try:
        if os.path.exists(DB_BLOG_PATH):
            with _crud.transacao() as cc:
                cc.execute("SELECT id FROM tb_postagens WHERE autor=?", (user_nome,))
                ids = [r[0] for r in cc.fetchall()]
                if ids:
                    cc.executemany("DELETE FROM tb_comentarios WHERE postagem_id=?",
                                   [(i,) for i in ids])
                cc.execute("DELETE FROM tb_comentarios WHERE autor=?", (user_nome,))
                cc.execute("DELETE FROM tb_postagens WHERE autor=?", (user_nome,))
            return len(ids)
        conn = get_connection()
        try:
            cc = conn.cursor()
            cc.execute("PRAGMA foreign_keys=ON")
            cc.execute("SELECT id FROM tb_postagens WHERE autor=?", (user_nome,))
            ids = [r[0] for r in cc.fetchall()]
            if ids:
                q = ",".join("?" * len(ids))
                cc.execute(f"DELETE FROM tb_comentarios WHERE postagem_id IN ({q})", ids)  # nosec B608 — q só tem "?" (len); ids via parâmetros
            cc.execute("DELETE FROM tb_comentarios WHERE autor=?", (user_nome,))
            cc.execute("DELETE FROM tb_postagens WHERE autor=?", (user_nome,))
            conn.commit()
            return len(ids)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        _log().exception(f"remover_vinculos_usuario: falha ao remover vínculos de {user_nome} | {e}")
        return 0


def renomear_autor(nome_atual, novo_nome):
    """Propaga o renomeio para as colunas de autoria do módulo.

    Chamado pelo módulo de gestão de usuários: cada módulo atualiza o
    PRÓPRIO banco (isolamento total). Sem o arquivo do banco no SQLite,
    atualiza a cópia legada do banco central. Exceção propaga (fail-loud)
    e o chamador registra o aviso."""
    if os.path.exists(DB_BLOG_PATH):
        with _crud.transacao() as cc:
            cc.execute("UPDATE tb_postagens SET autor=? WHERE autor=?", (novo_nome, nome_atual))
            cc.execute("UPDATE tb_comentarios SET autor=? WHERE autor=?", (novo_nome, nome_atual))
        return
    try:
        conn = get_connection()
    except Exception:
        _log().exception(f"renomear_autor: falha ao conectar para renomear {nome_atual}->{novo_nome}")
        raise
    try:
        cc = conn.cursor()
        cc.execute("UPDATE tb_postagens SET autor=? WHERE autor=?", (novo_nome, nome_atual))
        cc.execute("UPDATE tb_comentarios SET autor=? WHERE autor=?", (novo_nome, nome_atual))
        conn.commit()
    except Exception:
        _log().exception(f"renomear_autor: falha ao renomear {nome_atual}->{novo_nome}")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def obter_postagem(id_post):
    """Fetches a single post with all columns (via CrudBase).

    Busca postagem por id com todas as colunas (incl. `ativo`/
    `data_atualizacao`); retorna `None` quando inexistente."""
    try:
        return _crud.obter(
            "SELECT id, titulo, conteudo, autor, data_criacao, "
            "data_atualizacao, ativo FROM tb_postagens WHERE id=?", (id_post,))
    except Exception as e:
        _log().exception(f"obter_postagem: falha ao buscar postagem #{id_post} | {e}")
        return None


_URL_SCHEMES = {"http", "https", "data", "mailto", "relative"}
# Atributos permitidos por tag (usados na sanitização; essenciais p/ links e
# imagens, incluindo data:/URLs relativas pedidas pelo PLANO Fase 3).
# `img` aceita `class` (CSS online/frameworks) e `style` (CSS local inline,
# sanitizado pelo nh3) para edição da imagem pelo autor.
_ATTRS = {
    "a": {"href"},
    "img": {"src", "alt", "title", "width", "height", "class", "style"},
    "code": {"class"},
    "pre": {"class"},
    "blockquote": {"class"},
}

# Pasta de imagens enviadas pelo editor (dentro do módulo, servida em
# `/img_postagens/*` via `mod_blog.montar_rotas_static`, montada no main.py).
MOD_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_IMAGENS = os.path.join(MOD_DIR, "img_postagens")
# Limites do envio de imagem do editor (valores fixos do módulo).
IMAGEM_EXTENSOES = {".jpg", ".jpeg", ".png"}
IMAGEM_MAX_BYTES = 5 * 1024 * 1024
IMAGEM_EXPIRACAO_MIN = 5


def _nome_usuario_seguro(usuario):
    """Normaliza o login para uso no nome do arquivo (só [a-z0-9_-])."""
    base = re.sub(r"[^a-zA-Z0-9_-]", "_", (usuario or "anonimo").strip() or "anonimo")
    return base[:40].lower() or "anonimo"


def salvar_imagem_postagem(nome_original, conteudo, usuario):
    """Salva uma imagem do editor em `img_postagens` (JPG/PNG, até 5 MB).

    Nome padrão `dataHora_nomeDoUsuario.ext` (`AAMMDDHHMM_usuario`), com sufixo
    contador em colisão. Valida extensão e assinatura do arquivo (JPEG FFD8,
    PNG 89504E47). Retorna `(True, nome_servidor)` ou `(False, motivo)`.
    """
    try:
        import datetime as _dt
        ext = os.path.splitext(nome_original or "")[1].lower()
        if ext not in IMAGEM_EXTENSOES:
            return False, "Envie um arquivo .jpg ou .png"
        if not conteudo or len(conteudo) > IMAGEM_MAX_BYTES:
            return False, "Arquivo vazio ou maior que 5 MB"
        if ext in (".jpg", ".jpeg"):
            ok_tipo = conteudo[:2] == b"\xff\xd8"
        else:
            ok_tipo = conteudo[:8] == b"\x89PNG\r\n\x1a\n"
        if not ok_tipo:
            return False, "O arquivo não é uma imagem JPG/PNG válida"
        os.makedirs(PASTA_IMAGENS, exist_ok=True)
        base = f"{_dt.datetime.now().strftime('%y%m%d%H%M')}_{_nome_usuario_seguro(usuario)}"
        nome = f"{base}{ext}"
        for i in range(2, 1000):
            if not os.path.exists(os.path.join(PASTA_IMAGENS, nome)):
                break
            nome = f"{base}_{i}{ext}"
        with open(os.path.join(PASTA_IMAGENS, nome), "wb") as fh:
            fh.write(conteudo)
        _log().info(f"imagem do editor salva: {nome} por {usuario}")
        return True, nome
    except Exception as e:
        _log().exception(f"salvar_imagem_postagem falhou: {e}")
        return False, f"Falha ao salvar a imagem: {e}"


def expirar_imagens_orfas(minutos=IMAGEM_EXPIRACAO_MIN):
    """Remove imagens não concretizadas em postagem (órfãs há +5 min).

    Uma imagem é órfã quando seu nome não aparece em nenhum `conteudo` de
    `tb_postagens`. Chamado pelo agendador a cada 1 min (`cleanup_blog_imagens`).
    Retorna a quantidade removida.
    """
    try:
        import time as _time
        if not os.path.isdir(PASTA_IMAGENS):
            return 0
        try:
            with _crud.transacao() as cur:
                cur.execute("SELECT conteudo FROM tb_postagens")
                textos = " ".join((r[0] or "") for r in cur.fetchall())
        except Exception:
            textos = ""
        agora = _time.time()
        removidas = 0
        for nome in os.listdir(PASTA_IMAGENS):
            caminho = os.path.join(PASTA_IMAGENS, nome)
            if not os.path.isfile(caminho):
                continue
            try:
                if agora - os.path.getmtime(caminho) < minutos * 60:
                    continue
                if nome in textos:
                    continue
                os.remove(caminho)
                removidas += 1
            except Exception:
                continue
        if removidas:
            _log().info(f"imagens órfãs expiradas: {removidas}")
        return removidas
    except Exception as e:
        _log().exception(f"expirar_imagens_orfas falhou: {e}")
        return 0


def _sanitizar_texto(texto):
    """Sanitiza texto removendo XSS, permitindo apenas tags seguras.

    Para links e imagens são aceitos os esquemas http/https (e relativos), além
    de data: para imagens, conforme PLANO Fase 3. URLs relativas são mantidas.
    `div`/`br` (estrutura de linhas do editor WYSIWYG) são sempre permitidas,
    sem atributos.
    """
    if isinstance(texto, str):
        try:
            return clean(
                texto,
                tags=tags_permitidas() | {"div", "br"},
                attributes=_ATTRS,
                url_schemes=_URL_SCHEMES,
                url_relative="pass_through",
                link_rel="noopener noreferrer",
            )
        except Exception:
            _log().exception("_sanitizar_texto: falha na sanitização; usando escape")
            return html.escape(texto)
    return str(texto) if texto else ""


def _pode_publicar(usuario):
    """Regra do módulo: usuário COMUM só LÊ o blog.
    Publicar/comentar/excluir é privilégio de administrador geral ou
    administrador do módulo blog."""
    try:
        if not usuario:
            return False
        from mod_intranet import autenticacao
        try:
            return autenticacao.pode_publicar_no_blog(usuario)
        except Exception:
            return False
    except Exception:
        _log().exception(f"_pode_publicar: falha ao verificar permissão de {usuario}")
        return False


def mover_mermaid_para_fim(conteudo):
    """Move blocos ```mermaid para o fim do texto (ordem preservada).

    PADRÃO DO MÓDULO: diagramas sempre encerram a postagem (e renderizam
    centralizados em `_renderizar_conteudo_postagem`). Sem fence completo,
    devolve o conteúdo intacto.
    """
    if not isinstance(conteudo, str) or "```mermaid" not in conteudo:
        return conteudo
    blocos = [m.group(0) for m in _FENCE_MERMAID.finditer(conteudo)]
    if not blocos:
        return conteudo
    resto = _FENCE_MERMAID.sub("", conteudo).rstrip()
    return (resto + "\n\n" + "\n\n".join(blocos) + "\n") if resto else ("\n\n".join(blocos) + "\n")


@falha_suave(default=None, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@auditado(modulo="blog", acao="criar_postagem")
def criar_postagem(titulo, conteudo, autor):
    """Creates a post (sanitized) after checking publish permission.

    Valida permissão (`_pode_publicar`), censura (palavras bloqueadas no
    título), move ```mermaid para o fim, sanitiza título e conteúdo com nh3,
    grava no banco próprio, audita `criar_postagem` e registra no loguru.
    Retorna o id criado ou None em falha/sem permissão/bloqueado."""
    # censura: título não pode conter palavra bloqueada (admin configura em /admin/blog)
    try:
        from mod_intranet.censura import titulo_bloqueado
        bloqueado, palavra = titulo_bloqueado(titulo or "")
        if bloqueado:
            _log().warning(f"postagem bloqueada por censura: palavra '{palavra}' no título '{titulo}' por {autor}")
            try:
                from mod_intranet.tema_modulo import notificar as _not
                _not(f"Título contém palavra bloqueada: '{palavra}'", type="negative")
            except Exception:
                pass
            return None
    except Exception:
        pass
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(mover_mermaid_para_fim(conteudo))
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

    Valida permissão e censura do título, move ```mermaid para o fim,
    sanitiza com nh3, atualiza `data_atualizacao` e audita. False em
    falha/sem permissão/bloqueado/postagem inexistente."""
    try:
        from mod_intranet.censura import titulo_bloqueado
        bloqueado, palavra = titulo_bloqueado(titulo or "")
        if bloqueado:
            _log().warning(f"atualização bloqueada por censura: palavra '{palavra}' no título '{titulo}' por {autor}")
            return False
    except Exception:
        pass
    titulo_sanitizado = _sanitizar_texto(titulo)
    conteudo_sanitizado = _sanitizar_texto(mover_mermaid_para_fim(conteudo))
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
    try:
        return _crud.listar(
            "SELECT id, autor, conteudo, data_criacao FROM tb_comentarios "
            "WHERE postagem_id=? ORDER BY data_criacao", (postagem_id,))
    except Exception as e:
        _log().exception(f"listar_comentarios: falha ao listar comentários da postagem #{postagem_id} | {e}")
        return []


@falha_suave(default=False, nivel="exception")
@requer_pode_publicar(arg_usuario="autor")
@requer_flag("blog.comentar", arg_usuario="autor")
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


def ajustar_imagem_html(html_texto, alinhamento=None, largura=None):
    """Aplica alinhamento/largura à ÚLTIMA `<img>` do HTML (puro, testável).

    Reescreve só as props de layout do `style` (`float`, `margin*`,
    `display`, `vertical-align`, `clear`, `shape-outside`, `position`,
    `z-index`, `opacity`, `max/min/width`), preservando o restante do CSS
    do autor e o outro eixo quando só um muda (`largura=None` mantém a
    atual; `alinhamento=None` mantém/infere o atual).
    `largura="original"` remove o `max-width` (vale o padrão do render).
    Alinhamentos: `esquerda`, `direita`, `centro` + quebras de texto estilo
    Word — `em_linha` (na linha do texto), `quadrado` (contorno retangular),
    `justo` (texto colado no contorno), `atraves` (texto atravessa as
    margens), `sup_inf` (linha própria, texto acima/abaixo), `atras`
    (atrás do texto, marca d'água), `frente` (em frente ao texto,
    sobreposta). Retorna `(novo_html, detalhe)`; levanta `ValueError` se
    não há imagem.
    """
    html_atual = html_texto or ""
    tags = list(re.finditer(r"<img\b[^>]*>", html_atual, flags=re.IGNORECASE))
    if not tags:
        raise ValueError("Nenhuma imagem no texto")
    m = tags[-1]
    tag = m.group(0)
    ms = re.search(r'style="([^"]*)"', tag, flags=re.IGNORECASE)
    props = {}
    for parte in (ms.group(1) if ms else "").split(";"):
        if ":" in parte:
            k, v = parte.split(":", 1)
            props[k.strip().lower()] = v.strip()
    if alinhamento is None:
        _margem = props.get("margin", "")
        if props.get("float") == "right":
            if (props.get("position") == "relative"
                    and "z-index" in props):
                alinhamento = "frente"
            else:
                alinhamento = "direita"
        elif props.get("float") == "left":
            if "shape-outside" in props:
                alinhamento = ("atraves" if _margem == "0"
                               else "justo")
            elif _margem == "8px":
                alinhamento = "quadrado"
            else:
                alinhamento = "esquerda"
        elif props.get("display") == "inline":
            alinhamento = "em_linha"
        elif props.get("display") == "block":
            if "auto" in _margem:
                try:
                    _opaco = float(props.get("opacity", "1") or "1")
                except (TypeError, ValueError):
                    _opaco = 1.0
                alinhamento = "atras" if _opaco < 1 else "centro"
            elif props.get("clear") == "both":
                alinhamento = "sup_inf"
    larg_atual = props.get("max-width")
    if largura is None:
        largura = larg_atual or "original"
    for k in ("float", "margin", "margin-left", "margin-right",
              "margin-top", "margin-bottom", "display",
              "vertical-align", "clear", "shape-outside",
              "position", "z-index", "opacity",
              "max-width", "min-width", "width"):
        props.pop(k, None)
    if largura and largura != "original":
        props["max-width"] = largura
    props["height"] = "auto"
    if alinhamento == "esquerda":
        props.update({"float": "left", "margin": "0 12px 12px 0"})
    elif alinhamento == "direita":
        props.update({"float": "right", "margin": "0 0 12px 12px"})
    elif alinhamento == "centro":
        props.update({"display": "block", "margin": "8px auto"})
    elif alinhamento == "em_linha":
        props.update({"display": "inline", "vertical-align": "middle"})
    elif alinhamento == "quadrado":
        props.update({"float": "left", "margin": "8px"})
    elif alinhamento == "justo":
        props.update({"float": "left", "margin": "2px",
                      "shape-outside": "margin-box"})
    elif alinhamento == "atraves":
        props.update({"float": "left", "margin": "0",
                      "shape-outside": "margin-box"})
    elif alinhamento == "sup_inf":
        props.update({"display": "block", "clear": "both",
                      "margin": "8px 0"})
    elif alinhamento == "atras":
        props.update({"display": "block", "margin": "8px auto",
                      "opacity": "0.45"})
    elif alinhamento == "frente":
        props.update({"float": "right", "margin": "0 0 12px 12px",
                      "position": "relative", "z-index": "1"})
    estilo = ";".join(f"{k}:{v}" for k, v in props.items())
    if ms:
        nova = tag[:ms.start(1)] + estilo + tag[ms.end(1):]
    else:
        nova = tag[:-1].rstrip() + f' style="{estilo}">'
    detalhe = (alinhamento or "") + (" " + largura if largura else "")
    return html_atual[:m.start()] + nova + html_atual[m.end():], detalhe.strip() or "padrão"


def _merge_style(base, extra):
    """Concatena estilos CSS sem duplicar o separador ';'."""
    base = (base or "").strip()
    if not base:
        return extra
    return base.rstrip(";") + ";" + extra


class _FormatadorBlog(HTMLParser):
    """Reescreve HTML sanitizado aplicando o padrão visual do Blog:
    - h1/h2/h3: negrito + centralizado
    - img: alinhada à esquerda, limites 200-400px, responsiva — SALVO quando o
      autor definiu alinhamento/tamanho no `style` (botões do editor): `float`
      ou margens `auto` do autor vencem o padrão; `max-width` do autor dispensa
      os limites padrão (inclusive o `min-width`, que estouraria % pequenas)
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
            declaradas = {p.split(":", 1)[0].strip().lower()
                          for p in style.split(";") if ":" in p}
            tem_max = "max-width" in declaradas
            alinhada = ("float" in declaradas
                        or ("margin-left" in declaradas and "margin-right" in declaradas)
                        or ("margin" in declaradas and "auto" in style))
            padrao = ""
            if not alinhada:
                padrao += "float:left;margin:0 12px 12px 0;"
            if not tem_max:
                padrao += (f"max-width:{self.img_max}px;"
                           f"min-width:{self.img_min}px;")
            style = _merge_style(style, padrao)
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
    - Markdown leve (`#`, `-`, `**`) dentro de HTML do editor WYSIWYG convertido
    """
    try:
        if not conteudo:
            return ""
        limpo = _sanitizar_texto(conteudo)
        if not limpo.strip():
            return ""
        # Sem tags HTML -> trata como texto puro/Markdown
        if "<" not in limpo:
            corpo = _markdown_leve(html.escape(limpo, quote=False))
            return f'<div style="text-align:justify">{corpo}</div>'
        # HTML (ex. do editor WYSIWYG, que envolve tudo em <p>) -> converte o
        # Markdown digitado nos blocos antes de aplicar os estilos do padrão
        limpo = _markdown_em_html(limpo)
        # HTML sanitizado -> aplica estilos do padrão (largura de imagem configurável)
        min_l, max_l = _largura_imagem()
        parser = _FormatadorBlog(img_min=min_l, img_max=max_l)
        parser.feed(limpo)
        return f'<div style="text-align:justify">{parser.getvalue()}</div>'
    except Exception:
        _log().exception("formatar_conteudo_para_exibicao: falha ao formatar conteúdo")
        return html.escape(conteudo or "")


def _markdown_em_html(limpo):
    """Converte Markdown leve dentro de blocos HTML (texto do editor WYSIWYG).

    O editor envolve cada linha em `<p>` (e a primeira pode vir solta, com as
    demais em `<div>`, que o nh3 mantém sem atributos) — por isso normaliza
    `<div>` para `<p>` e converte também eventual primeira linha solta:
    `<p>#..</p>` → `<h1..3>`, `<p>- ..</p>` vizinhos → `<ul><li>` e
    `**x**` → `<b>x</b>` (só em texto, nunca em atributos). Conteúdo de
    `code`/`pre` é preservado intacto.
    """
    # Normaliza blocos do editor: <div> (sem atributos pós-nh3) equivale a <p>.
    limpo = re.sub(r"<div[^>]*>", "<p>", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r"</div\s*>", "</p>", limpo, flags=re.IGNORECASE)

    def _titulo_solteiro(m):
        nivel = len(m.group(1))
        return f"<h{nivel}>{m.group(2).strip()}</h{nivel}>"

    limpo = re.sub(r"\A\s*(#{1,3})\s+([^<]*?)(?=<|\Z)", _titulo_solteiro, limpo)

    def _item_solteiro(m):
        return f"<ul><li>{m.group(1).strip()}</li></ul>"

    limpo = re.sub(r"\A\s*[-*]\s+([^<]*?)(?=<|\Z)", _item_solteiro, limpo)
    partes = re.split(r"(<(?:code|pre)[^>]*>.*?</(?:code|pre)>)", limpo,
                      flags=re.DOTALL | re.IGNORECASE)
    for i in range(0, len(partes), 2):
        parte = partes[i]

        def _titulo(m):
            nivel = len(m.group(1))
            return f"<h{nivel}>{m.group(2).strip()}</h{nivel}>"

        parte = re.sub(r"<p>\s*(#{1,3})\s+(.*?)</p>", _titulo, parte,
                       flags=re.DOTALL)

        def _grupo_lista(m):
            itens = re.findall(r"<p>\s*[-*]\s+(.*?)</p>", m.group(0),
                               flags=re.DOTALL)
            return "<ul>" + "".join(f"<li>{it.strip()}</li>" for it in itens) + "</ul>"

        parte = re.sub(r"(?:<p>\s*[-*]\s+.*?</p>\s*)+", _grupo_lista, parte,
                       flags=re.DOTALL)
        toks = re.split(r"(<[^>]+>)", parte)
        for j in range(0, len(toks), 2):
            toks[j] = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", toks[j])
        partes[i] = "".join(toks)
    return "".join(partes)


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

    Lê a config local; default carrossel com as 3 postagens básicas.
    """
    try:
        modo = (get_config_local("blog_modo_exibicao", "carrossel") or "carrossel").strip()
        return modo if modo in ("unica", "historico", "carrossel") else "carrossel"
    except Exception:
        return "carrossel"


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
    try:
        return set_config_local("blog_postagem_unica_id",
                                "" if pid is None else str(int(pid)))
    except Exception as e:
        _log().exception(f"definir_postagem_unica_id: falha ao fixar {pid} | {e}")
        return False


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
            sql = (f"SELECT id, titulo, conteudo, autor, data_criacao "  # nosec B608 — marcador só tem "?" (len(ids)); ids via parâmetros
                   f"FROM tb_postagens WHERE ativo=? AND id IN ({marcador})")  # nosec B608 — idem
        else:
            params = list(ids)
            sql = (f"SELECT id, titulo, conteudo, autor, data_criacao "  # nosec B608 — marcador só tem "?" (len(ids)); ids via parâmetros
                   f"FROM tb_postagens WHERE id IN ({marcador})")  # nosec B608 — idem
        linhas = _crud.listar(sql, tuple(params))
        pos = {i: idx for idx, i in enumerate(ids)}
        linhas.sort(key=lambda r: pos.get(r[0], 10**9))
        return linhas
    except Exception:
        _log().exception("falha ao listar postagens por ids (carrossel)")
        return []