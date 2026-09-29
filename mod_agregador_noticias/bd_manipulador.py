"""News aggregator — own DB, multi-source scrapy-like collection, 24h recycle.

EN: News aggregator with own DB db_mod_agregador_noticias.db (WAL). Table
    tb_noticia (title/source/theme/url UNIQUE/image/description/dates), sources
    Google News + BBC + JFP + generic RSS configurable by admin, httpx+parsel
    automatic collection (60min–6.5 days), manual on-demand collection for admins only,
    censorship via titulo_bloqueado (conteudo_palavras_bloqueadas).

Agregador de Notícias — BD próprio, coleta multi-fonte, limpeza 24h.

BD: db_mod_agregador_noticias.db (WAL)
Tabelas: tb_noticia (titulo, fonte, tema, url UNIQUE, imagem_url, descricao, data_publicacao, data_coleta)
Fontes: Google News + BBC + JFP + RSS genérico, configuráveis pelo admin (conteúdo da pesquisa).
Coleta via httpx+parsel (scrapy-like) com intervalo 60min–9360min (piso 1h, teto 6,5 dias), automatica e habilitada por flag; coleta manual sob demanda so pelo administrador.
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
# "Tribunais de Contas" (26/09/2026): foco dos CONTROLADORES DA PREFEITURA —
# acompanhamento do TCU e dos tribunais estaduais, com destaque para MG.
# Temas de PÚBLICO RESTRITO: somem da listagem padrão do Agregador e só
# aparecem quando o usuário escolhe o tema na barra ou acha por pesquisa.
# Notícia de tribunal de contas é dirigida a um público específico (os
# controladores), não ao público geral que abre a tela. A diferença para
# `_TEMAS_SEM_TV` é que ali o tema é EXCLUÍDO de vez (TV do Filas); aqui
# ele fica acessível sob demanda.
_TEMAS_RESTRITOS = ("Tribunais de Contas",)

# Versão deste módulo (AGENTS.md §4.2 — formato X.Y.AAMMDD, patch = data da
# alteração). É a data em que o CÓDIGO mudou, não um contador de revisões.
# 29/09/2026 — paginação da grade corrigida (página 1 = amostra por tema,
# páginas seguintes = o restante no tamanho configurado) e os dois textos
# fixos da tela movidos para configuração.
VERSAO_MODULO = "1.0.260929"

# Temas que NÃO vão para o carrossel da TV do mod_filas.
# A TV é o painel de atendimento ao público: notícia de julgamento de
# tribunal de contas ali é ruído para quem está esperando ser chamado. As
# notícias de controle seguem disponíveis na tela do Agregador, onde os
# controladores as consultam de propósito.
_TEMAS_SEM_TV = ("Tribunais de Contas",)

TEMAS_PADRAO = ["Brasil", "Internacional", "Economia", "Saúde", "Ciência e Tecnologia",
                "Entretenimento", "Esporte", "Monte Santo", "Geral",
                "Tribunais de Contas"]

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

# Default de 20/09/2026 (V1) e de 20–25/09/2026 (V2) — CONGELADOS: mantidos
# só para reconhecer e migrar quem nunca customizou as fontes (ver init_db).
# NÃO editar mais estas listas.
_FONTES_PADRAO_V2 = _FONTES_PADRAO_V1 + [
    {"tipo": "rss", "nome": "G1 - Mundo", "url": "https://g1.globo.com/rss/g1/mundo/", "tema": "Internacional"},
    {"tipo": "rss", "nome": "G1 - Pop e Arte", "url": "https://g1.globo.com/rss/g1/pop-arte/", "tema": "Entretenimento"},
    {"tipo": "rss", "nome": "GE - Esporte", "url": "https://ge.globo.com/rss/ge/", "tema": "Esporte"},
    {"tipo": "rss", "nome": "JFP - Monte Santo de Minas", "url": "https://jfpnoticias.com.br", "tema": "Monte Santo de Minas"},
]

# Default atual (13 fontes) = V1 sem as 2 fontes mortas, Folha no host real e
# JFP com o tema que existe de fato no filtro. Mantém a cobertura de temas do
# V2: Internacional/Entretenimento/Esporte/Monte Santo.
#
# Auditoria de 26/09/2026 (cada fonte verificada com requisição real):
#   - "Agência Brasil" REMOVIDA — /rss/ultimasnoticias.xml responde 404 e o
#     único feed alcançável (/rss.xml) está abandonado desde 2020 (itens de
#     fev–jun/2020): entraria e seria apagado pela limpeza de 24h.
#   - "Poder9360" REMOVIDA — www.poder9360.com.br devolve NXDOMAIN no DNS
#     público (1.1.1.1): o domínio não existe mais, nunca vai coletar.
#   - "Folha de S.Paulo" URL CORRIGIDA — s.folha.uol.com.br também é NXDOMAIN;
#     o host real é feeds.folha.uol.com.br (100 itens, atualizado).
#   - "JFP - Monte Santo de Minas" MANTIDA no endereço raiz porque é scraper
#     (CSS .td-module-title), não RSS — a raiz já traz 44 elementos. Tema
#     corrigido de "Monte Santo de Minas" (inexistente em TEMAS_PADRAO, logo
#     a fonte sumia do filtro) para "Monte Santo".
_TC = "Tribunais de Contas"

FONTES_PADRAO = _FONTES_PADRAO_LEGADO + [
    {"tipo": "rss", "nome": "Senado Federal", "url": "https://www12.senado.leg.br/noticias/rss", "tema": "Brasil"},
    {"tipo": "rss", "nome": "G1 - Últimas", "url": "https://g1.globo.com/rss/g1/", "tema": "Geral"},
    {"tipo": "rss", "nome": "G1 - Economia", "url": "https://g1.globo.com/rss/g1/economia/", "tema": "Economia"},
    {"tipo": "rss", "nome": "G1 - Saúde", "url": "https://g1.globo.com/rss/g1/saude/", "tema": "Saúde"},
    {"tipo": "rss", "nome": "G1 - Tecnologia", "url": "https://g1.globo.com/rss/g1/tecnologia/", "tema": "Ciência e Tecnologia"},
    {"tipo": "rss", "nome": "Folha de S.Paulo", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "tema": "Brasil"},
    {"tipo": "rss", "nome": "G1 - Mundo", "url": "https://g1.globo.com/rss/g1/mundo/", "tema": "Internacional"},
    {"tipo": "rss", "nome": "G1 - Pop e Arte", "url": "https://g1.globo.com/rss/g1/pop-arte/", "tema": "Entretenimento"},
    {"tipo": "rss", "nome": "GE - Esporte", "url": "https://ge.globo.com/rss/ge/", "tema": "Esporte"},
    {"tipo": "rss", "nome": "JFP - Monte Santo de Minas", "url": "https://jfpnoticias.com.br", "tema": "Monte Santo"},
    # ---------- TRIBUNais DE CONTAS (foco dos controladores da Prefeitura) ----------
    # TCU tem RSS OFICIAL (portal.tcu.gov.br/rss.xml, 30 itens, atualizado).
    # Os estaduais não publicam RSS estável, então entram pela busca do Google
    # News com o nome do tribunal — traz a notícia E a fonte original
    # (item <source>), que vira o "fonte_icon"/nome no card.
    {"tipo": "rss", "nome": "TCU", "url": "https://portal.tcu.gov.br/rss.xml", "tema": _TC},
    # TCE-MG: WEBSCRAPING SOB MEDIDA (`_coletar_tcemg`). O tribunal não
    # publica RSS; pela busca do Google News só viriam notícias de
    # terceiros e perderíamos as comunicações oficiais do próprio TCE.
    # A lista dá data/link/título e a miniatura sai do padrão
    # /ImagemDestaque/<id>.png.
    {"tipo": "tcemg", "nome": "TCE-MG", "url": "https://www.tce.mg.gov.br/Noticia/", "tema": _TC},
    {"tipo": "google", "nome": "TCE-SP", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+de+S%C3%A3o+Paulo&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-RS", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+do+Rio+Grande+do+Sul&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-PR", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+do+Paran%C3%A1&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-BA", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+da+Bahia&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-RJ", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+do+Estado+do+Rio+de+Janeiro&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-GO", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+de+Goi%C3%A1s&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-PE", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+de+Pernambuco&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-CE", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+do+Cear%C3%A1&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
    {"tipo": "google", "nome": "TCE-SC", "url": "https://news.google.com/rss/search?q=Tribunal+de+Contas+de+Santa+Catarina&hl=pt-BR&gl=BR&ceid=BR:pt-419", "tema": _TC},
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
    """Intervalo de coleta em minutos, clamp 60–9360 (mín. 1h, teto 6,5 dias).

    Piso de 1 hora desde 26/09/2026: a coleta é AUTOMÁTICA (não depende de
    clique humano) e cada ciclo varre as 13 fontes + baixa miniatura por
    notícia. Intervalos curtos viravam carga sobre as fontes e sobre a
    própria tela, sem ganho. Para buscar na hora, só o ADMINISTRADOR usa a
    coleta manual (`coletar_todas(forcar=True)`)."""
    try:
        v = int((_get_config("intervalo_min", "60") or "60").strip() or 60)
    except Exception:
        v = 60
    return max(60, min(9360, v))


def definir_intervalo(minutos: int, ator="sistema"):
    v = max(60, min(9360, int(minutos)))
    ok = _set_config("intervalo_min", str(v))
    if ok:
        _audit(ator, "configurar", "intervalo_min", str(v))
    return ok, v


def refresh_seg() -> int:
    """EN: Screen auto-refresh in seconds — how often the news grid checks for new items.

    PT-BR: Atualização automática da tela em segundos — de quanto em quanto
    a grade checa se apareceu notícia nova.

    É o INTERVALO DE EXIBIÇÃO, diferente de `intervalo_min()` (que é o
    intervalo de COLETA, mínimo 1 h). O polling é barato: um único SELECT
    com agregados (`marca_ultimo_coletado`), e só busca linhas quando a
    marca d'água mudou. Clamp 15–600 s (ajustável pelo admin no slider da
    aba Administração do módulo)."""
    try:
        v = int((_get_config("refresh_seg", "60") or "60").strip() or 60)
    except Exception:
        v = 60
    return max(15, min(600, v))


def definir_refresh_seg(segundos: int, ator="sistema"):
    """Grava o intervalo de atualização automática da tela (slider do admin)."""
    v = max(15, min(600, int(segundos)))
    ok = _set_config("refresh_seg", str(v))
    if ok:
        _audit(ator, "configurar", "refresh_seg", str(v))
    return ok, v


# ============ EXIBIÇÃO DA TELA (29/09/2026) ============

# A grade tem 3 COLUNAS no desktop, então o tamanho da página é MÚLTIPLO DE 3:
# é o que evita a linha órfã com 1 ou 2 cards sozinhos no fim da grade.
#
# POR QUE O TETO É 99 E NÃO 100 (29/09/2026, decisão do responsável)
#     Quem pediu o limite disse "100"; 100 não é múltiplo de 3 (100/3 = 33,33)
#     e é exatamente a linha órfã que a regra dos múltiplos existe para
#     impedir. O TETO declarado fica em 100 para atender o pedido, mas o maior
#     valor ALCANÇÁVEL é 99. Gravar 100 direto no banco normaliza para 99, e o
#     painel avisa o porquê em vez de aceitar e quebrar a grade.
POR_PAGINA_PADRAO = 12
POR_PAGINA_MINIMO = 9
POR_PAGINA_MAXIMO = 100
# Alcançável de verdade: todos os múltiplos de 3 de 9 até 99.
POR_PAGINA_OPCOES = tuple(range(9, 100, 3))
# Tetos de caracteres dos textos livres da tela (o excedente é cortado).
TEXTO_HEADER_MAX = 300
TEXTO_SEM_NOVIDADE_MAX = 200


def _ajustar_por_pagina(valor) -> int:
    """EN: Clamps the page size to an int in 9–100 that is a multiple of 3.

    PT-BR: Ajusta o tamanho de página para inteiro entre 9 e 100 e múltiplo
    de 3.

    Valor fora da regra é ARREDONDADO PARA BAIXO até o múltiplo de 3 mais
    próximo (com piso de 9): 10 → 9, 11 → 9, 13 → 12, 58 → 57, 100 → 99. O
    ajuste é determinístico e vale para o valor que vem da TELA e para o que
    alguém gravar direto na chave de configuração — o clamp é do backend,
    não da UI. Valor ilegível cai no padrão (12). Nunca levanta exceção.
    """
    try:
        v = int(valor)
    except Exception:
        return POR_PAGINA_PADRAO
    try:
        v = max(POR_PAGINA_MINIMO, min(POR_PAGINA_MAXIMO, v))
        resto = v % 3
        if resto:
            v -= resto
        return max(POR_PAGINA_MINIMO, v)
    except Exception:
        return POR_PAGINA_PADRAO


def por_pagina() -> int:
    """EN: How many news cards a page shows — multiple of 3, minimum 9.

    PT-BR: Quantas notícias a página mostra — múltiplo de 3, mínimo 9.

    Configurável pelo administrador em `/admin/agregador_noticias`
    (card "Exibição"). É a MESMA conta que a tela fatia as páginas: a
    página 1 de "Todos os temas" é a amostra por tema (uma de cada) e as
    páginas seguintes fatiam o restante no tamanho configurado.
    """
    bruto = _get_config("por_pagina", str(POR_PAGINA_PADRAO)) or ""
    return _ajustar_por_pagina((bruto or "").strip() or POR_PAGINA_PADRAO)


def definir_por_pagina(valor, ator="sistema"):
    """EN: Saves the page size (clamp: int, ≥ 9, ≤ 100, multiple of 3).

    PT-BR: Grava o tamanho de página (clamp: inteiro, ≥ 9, ≤ 100, múltiplo
    de 3; o maior valor alcançável é 99 porque 100 não é múltiplo de 3).

    Devolve `(ok, valor_aplicado)` — o valor devolvido é o que foi realmente
    gravado depois do clamp, para a tela mostrar a verdade e não o que foi
    digitado.
    """
    try:
        v = _ajustar_por_pagina(valor)
        ok = _set_config("por_pagina", str(v))
        if ok:
            _audit(ator, "configurar", "por_pagina", str(v))
        return ok, v
    except Exception:
        _log().warning(f"definir_por_pagina: falha ao gravar ({valor!r})")
        return False, POR_PAGINA_PADRAO


def texto_header() -> str:
    """EN: Header subtitle of the news screen — empty means NO subtitle.

    PT-BR: Subtítulo do cabeçalho da tela — vazio significa NÃO mostrar.

    Chave `agregador_noticias_texto_header`, a mesma que `tema_modulo`
    lê; o padrão é VAZIO, então a tela nasce sem aquele parágrafo fixo que
    descrevia a tela como se fosse sempre verdade.
    """
    return (_get_config("texto_header", "") or "").strip()[:TEXTO_HEADER_MAX]


def definir_texto_header(texto, ator="sistema"):
    """Grava o subtítulo do cabeçalho (vazio = a tela não mostra cabeçalho)."""
    try:
        t = (str(texto or "")).strip()[:TEXTO_HEADER_MAX]
        ok = _set_config("texto_header", t)
        if ok:
            # `tema_modulo` guarda o tema em `lru_cache`: sem limpar, a tela
            # continuaria com o texto velho até reiniciar o servidor.
            _limpar_cache_tema()
            _audit(ator, "configurar", "texto_header", t)
        return ok, t
    except Exception:
        _log().warning("definir_texto_header: falha ao gravar")
        return False, ""


def texto_sem_novidade() -> str:
    """EN: Text shown when the auto-check found nothing new — empty = no text.

    PT-BR: Texto exibido quando a checagem automática não achou nada novo —
    vazio = nenhum texto.

    Aceita o marcador `{seg}`, substituído pelo intervalo de checagem em
    segundos (ex.: `Sem novidade • próxima checagem em {seg}s`).
    """
    return (_get_config("texto_sem_novidade", "") or "").strip()[:TEXTO_SEM_NOVIDADE_MAX]


def definir_texto_sem_novidade(texto, ator="sistema"):
    """Grava o texto de 'sem novidade' (vazio = nada aparece na barra)."""
    try:
        t = (str(texto or "")).strip()[:TEXTO_SEM_NOVIDADE_MAX]
        ok = _set_config("texto_sem_novidade", t)
        if ok:
            _audit(ator, "configurar", "texto_sem_novidade", t)
        return ok, t
    except Exception:
        _log().warning("definir_texto_sem_novidade: falha ao gravar")
        return False, ""


def _limpar_cache_tema():
    """Limpa o cache de tema do núcleo (fail-soft) após gravar o cabeçalho."""
    try:
        from mod_intranet import tema_modulo
        tema_modulo.ler_tema.cache_clear()
    except Exception:
        pass
    try:
        from mod_intranet import tema_modulo
        tema_modulo._cfg.cache_clear()
    except Exception:
        pass


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
        # Coleta AUTOMÁTICA por padrão desde 26/09/2026: o serviço de busca
        # não deve depender de clique humano. Intervalo de coleta com piso
        # de 1h; `refresh_seg` é o intervalo de ATUALIZAÇÃO DA TELA
        # (slider do admin), que é bem menor porque o polling é barato.
        ("agregador_noticias_habilitado", "1"),
        ("agregador_noticias_intervalo_min", "60"),
        ("agregador_noticias_refresh_seg", "60"),
        ("agregador_noticias_termo_pesquisa", ""),
        # Exibição (29/09/2026): tamanho de página e os DOIS textos que
        # eram fixos no código — subtítulo do cabeçalho e aviso de "sem
        # novidade". Todos nascem VAZIOS (exceto o tamanho de página): a
        # tela não escreve mais descrição de si mesma, quem escreve é o
        # administrador em /admin/agregador_noticias.
        ("agregador_noticias_por_pagina", str(POR_PAGINA_PADRAO)),
        ("agregador_noticias_texto_header", ""),
        ("agregador_noticias_texto_sem_novidade", ""),
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
            # O TCE-MG entrou no default como `tcemg` (webscraping oficial) DEPOIS
            # de `_dados` ser lido, então o replace do TCE-MG precisa vir antes
            # da comparação com o default atual — senão quem já tem a versão
            # anterior (TCE-MG via Google News) nunca seria atualizado.
            if isinstance(_dados, list):
                _migrado = False
                for _fonte in _dados:
                    if (isinstance(_fonte, dict) and _fonte.get("nome") == "TCE-MG"
                            and _fonte.get("tipo") == "google"):
                        _fonte["tipo"] = "tcemg"
                        _fonte["url"] = "https://www.tce.mg.gov.br/Noticia/"
                        _migrado = True
                if _migrado:
                    _setc("agregador_noticias_fontes_json",
                          json.dumps(_dados, ensure_ascii=False))
                    _log().info(
                        "agregador: TCE-MG migrado para o webscraping oficial "
                        "(antes vinha via busca do Google News = terceiros)")
            if _dados in (_FONTES_PADRAO_LEGADO, _FONTES_PADRAO_V1, _FONTES_PADRAO_V2):
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
    _migrar_versao_modulo()


# ============ VERSÃO DO MÓDULO (AGENTS.md §4.2) ============

def _migrar_versao_modulo():
    """Migração idempotente do bump de 29/09/2026 — paginação + textos.

    O que mudou: a contagem da paginação passou a bater com a fatia
    (página 1 = amostra por tema, páginas seguintes = o restante no
    tamanho configurado) e os dois textos fixos da tela viraram
    configuração.

    A chave `versao_modulo:agregador_noticias` é a MESMA que o rodapé da
    tela lê e que `mod_auditoria`/`mod_edit_pdf` já semeiam no próprio
    `bd_manipulador` — o INSERT abaixo cria a chave quando ela ainda não
    existe, então banco novo e banco em uso nascem certos.

    Idempotente pelo marcador `migracao_versao_agregador_noticias_260929`:
    roda UMA vez; na segunda não muda nada e não sobrescreve uma versão
    que o administrador tenha ajustado. SQL portátil (SQLite e PostgreSQL).

    NOTA: o marcador-padrão `migracao_versao_<chave>_<data>` que o
    `assets/test/teste_versionamento_modulo.py` procura vive em
    `mod_intranet/bd_conexao.py` (fora do diretório deste módulo). Ele
    precisa ser somado lá para que a checagem estática reconheça o bump;
    funcionalmente esta migração já aplica a versão no banco.
    """
    try:
        from mod_intranet.bd_conexao import get_connection as gc
        conn = gc()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_config "
                        "WHERE chave='migracao_versao_agregador_noticias_260929'")
            if (cur.fetchone()[0] or 0) == 0:
                cur.execute("INSERT INTO tb_config (chave, valor) "
                            "VALUES (?, ?) ON CONFLICT DO NOTHING",
                            ("versao_modulo:agregador_noticias", VERSAO_MODULO))
                cur.execute("UPDATE tb_config SET valor=? "
                            "WHERE chave='versao_modulo:agregador_noticias'",
                            (VERSAO_MODULO,))
                cur.execute("INSERT INTO tb_config (chave, valor) "
                            "VALUES ('migracao_versao_agregador_noticias_260929', '1') "
                            "ON CONFLICT DO NOTHING")
                conn.commit()
        finally:
            conn.close()
    except Exception:
        _log().warning("_migrar_versao_modulo: falha ao aplicar o bump de versão")


# ============ CRUD ============

def contar_noticias(tema=None):
    """Conta as notícias, aplicando a mesma regra de público restrito de
    `listar_noticias` (tema de uso interno só entra quando pedido)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if tema:
            cur.execute("SELECT COUNT(*) FROM tb_noticia WHERE tema=?", (tema,))
        elif _TEMAS_RESTRITOS:
            _neg = ",".join("?" * len(_TEMAS_RESTRITOS))
            cur.execute(f"SELECT COUNT(*) FROM tb_noticia WHERE tema NOT IN ({_neg})",
                        tuple(_TEMAS_RESTRITOS))
        else:
            cur.execute("SELECT COUNT(*) FROM tb_noticia")
        return cur.fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


def marca_ultimo_coletado() -> tuple:
    """EN: Cheap watermark of the table — `(total, max_id, max_coleta)`.

    PT-BR: Marca d'água barata da tabela — `(total, max_id, max_coleta)`.

    Usada pelo `ui.timer` da tela para saber se apareceu notícia nova **sem
    carregar linhas**: um único SELECT com agregados (sem `ORDER BY`, sem
    payload de texto/imagem). É o que permite atualizar só o card novo em
    vez de redesenhar a grade inteira — o polling não pesa. Falha devolve
    `None` (fail-soft) para o timer simplesmente não atualizar."""
    try:
        conn = get_connection()
    except Exception:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(MAX(data_coleta), '') "
                    "FROM tb_noticia")
        linha = cur.fetchone() or (0, 0, "")
        return (int(linha[0] or 0), int(linha[1] or 0), str(linha[2] or ""))
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def listar_novas(apos_id: int, limite: int = 12, tema=None) -> list:
    """EN: Rows with `id` greater than `apos_id`, newest first.

    PT-BR: Linhas com `id` maior que `apos_id`, mais recentes primeiro.

    Complementa `marca_ultimo_coletado`: o timer detecta a marca d'água e
    busca SÓ as linhas novas, para prependê-las na grade já montada.

    Aplica a mesma regra de público restrito de `listar_noticias`: com
    `tema=None`, os temas em `_TEMAS_RESTRITOS` não entram — senão a
    atualização automática (que roda sem o usuário pedir nada) injetaria
    notícia de tribunal na tela de quem não pediu.
    """
    try:
        conn = get_connection()
    except Exception:
        return []
    try:
        cur = conn.cursor()
        if tema:
            cur.execute(
                "SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, "
                "descricao, data_publicacao, data_coleta FROM tb_noticia "
                "WHERE id > ? AND tema = ? "
                "ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC "
                "LIMIT ?", (int(apos_id or 0), tema, int(limite)))
        elif _TEMAS_RESTRITOS:
            _neg = ",".join("?" * len(_TEMAS_RESTRITOS))
            cur.execute(
                "SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, "
                "descricao, data_publicacao, data_coleta FROM tb_noticia "
                f"WHERE id > ? AND tema NOT IN ({_neg}) "
                "ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC "
                "LIMIT ?", (int(apos_id or 0), *_TEMAS_RESTRITOS, int(limite)))
        else:
            cur.execute(
                "SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, "
                "descricao, data_publicacao, data_coleta FROM tb_noticia "
                "WHERE id > ? "
                "ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC "
                "LIMIT ?", (int(apos_id or 0), int(limite)))
        return cur.fetchall() or []
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


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


def listar_noticias(tema=None, limite=30, offset=0, excluir_restritos=True):
    """Lista as notícias mais recentes.

    **Público restrito:** os temas em `_TEMAS_RESTRITOS` (Tribunais de
    Contas) ficam FORA da listagem padrão e SÓ aparecem em dois casos, ambos
    deliberados do usuário:
      1. selecionar o tema na barra de temas (`tema=` explícito), ou
      2. achá-las pela pesquisa (`excluir_restritos=False`).
    Notícia de tribunal é dirigida a um público específico (os
    controladores), não ao público geral que abre a tela — por isso não
    ocupa a listagem geral. Selecionar o tema já é uma escolha explícita, e
    por isso o filtro de restrito não se aplica nesse caminho.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cols = ("SELECT id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, "
                "descricao, data_publicacao, data_coleta FROM tb_noticia")
        ordem = " ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC"
        if tema:
            # tema escolhido pelo usuário: o filtro de restrito não se aplica
            cur.execute(f"{cols} WHERE tema=?{ordem} LIMIT ? OFFSET ?", (tema, limite, offset))
        elif excluir_restritos and _TEMAS_RESTRITOS:
            _neg = ",".join("?" * len(_TEMAS_RESTRITOS))
            cur.execute(f"{cols} WHERE tema NOT IN ({_neg}){ordem} LIMIT ? OFFSET ?",
                        (*_TEMAS_RESTRITOS, limite, offset))
        else:
            cur.execute(f"{cols}{ordem} LIMIT ? OFFSET ?", (limite, offset))
        return cur.fetchall() or []
    except Exception:
        return []
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


# (as duas constantes de tema foram movidas para o topo do módulo — as
# funções `listar_noticias`, `listar_novas` e `contar_noticias` já as
# referenciam, e depender da resolução em tempo de chamada era frágil)


def listar_para_tv(limite=10, por_tema=False, horas=None):
    """API para mod_filas TV — carrossel título+descrição (filtra censuradas, ordena por tempo real).

    EN: TV feed — latest headlines (censorship filtered, real post time first).
    Params opcionais retrocompatíveis: por_tema=True devolve UMA notícia por
    categoria de temas_config() (na ordem configurada, para rodar as categorias);
    horas=N prioriza notícias com COALESCE(data_publicacao, data_coleta) das
    últimas N horas — no modo por_tema cada categoria sem novidade usa a mais
    recente disponível (fallback por categoria).
    Temas em `_TEMAS_SEM_TV` (Tribunais de Contas) são SEMPRE excluídos: a TV
    é o painel de atendimento, não o painel de controle.
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
                temas = [t for t in temas if t not in _TEMAS_SEM_TV]
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
                # exclui os temas sem TV (ver _TEMAS_SEM_TV)
                _excluir = " AND tema NOT IN (%s)" % ",".join("?" * len(_TEMAS_SEM_TV))
                if corte:
                    cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia WHERE COALESCE(data_publicacao, data_coleta) >= ?" + _excluir + " ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (corte, *_TEMAS_SEM_TV, limite * 3))
                else:
                    # pega mais que limite para filtrar censuradas sem perder slots, ordena por data real da postagem
                    cur.execute("SELECT titulo, descricao, url, imagem_url, fonte, tema, fonte_icon_url FROM tb_noticia WHERE 1=1" + _excluir + " ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?", (*_TEMAS_SEM_TV, limite * 3))
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


def _coletar_google_rss(url: str, fonte_nome: str, tema: str) -> int:
    """EN: Collects a Google News **search** RSS (`/rss/search?q=…`).

    PT-BR: Coleta o RSS de **busca** do Google News (`/rss/search?q=…`).

    Usado pelas fontes de tema (Tribunais de Contas), onde não existe RSS
    próprio do órgão: a busca entrega a notícia, a data e a fonte original
    no item `<source>` — que vira o nome/fonte exibido no card. Retorna 0 em
    falha (fail-soft) e nunca levanta."""
    try:
        xml = _get_html(url)
        if not xml:
            return 0
        import parsel
        sel = parsel.Selector(text=xml, type="xml")
        n = 0
        for item in sel.css("item"):
            titulo = (item.css("title::text").get() or "").strip()
            href = (item.css("link::text").get() or "").strip()
            if not titulo or not href:
                continue
            fonte_real = (item.css("source::text").get() or "").strip()
            # título do Google vem como "Headline - Fonte"; usa a fonte real
            # como rótulo e limpa o sufixo duplicado
            rotulo = fonte_real or fonte_nome
            if fonte_real and titulo.endswith(f" - {fonte_real}"):
                titulo = titulo[: -(len(fonte_real) + 3)].strip()
            partes = [t.strip() for t in item.css("description ::text").getall() if (t or "").strip()]
            desc = re.sub(r"\s+", " ", " ".join(partes)).strip()
            if "<" in desc:
                try:
                    import html as _html
                    desc = _html.unescape(desc)
                    desc = re.sub(r"<[^>]+>", " ", desc)
                    desc = re.sub(r"\s+", " ", desc).strip()
                except Exception:
                    pass
            data_pub = _parse_data_pub(
                (item.css("pubDate::text").get() or "").strip()) or None
            if inserir_noticia(titulo, rotulo, tema, href, "", desc, data_pub):
                n += 1
            if n >= 15:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_google_rss {fonte_nome}: {e}")
        return 0


def _coletar_google(url: str, fonte_nome: str, tema: str) -> int:
    import time
    # RSS de busca do Google News (`/rss/search?q=`) tem parser próprio
    if "/rss/search" in (url or ""):
        return _coletar_google_rss(url, fonte_nome, tema)
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


def _coletar_tcemg(url: str, tema: str) -> int:
    """EN: Custom scraper for TCE-MG (Tribunal de Contas de Minas Gerais).

    PT-BR: Webscraping sob medida do TCE-MG (Tribunal de Contas de Minas).

    O TCE-MG **não publica RSS**, então a coleta é feita na página de
    notícias. Estrutura observada em 26/09/2026 (verificada por requisição):

        <span class="data-noticia-internas">25/09/2026 - </span>
        <a href="/Slug-da-noticia.html/Noticia/1111629205" title="Título">
        Título
        </a>
        <p><a ...><span class="cliqueaqui">Clique aqui</span></a></p>

    • A LISTA entrega data (dd/mm/aaaa), link e título completo — 20 itens
      por página, sem paginação.
    • O `title` vem em HTML entities (`&#231;`), por isso o unescape.
    • O resumo sai do `<p>` que segue o item, descartando o "Clique aqui".
    • **Sem miniatura**: testado em 26/09/2026 — o padrão deduzido
      `/ImagemDestaque/<id>.png` devolve 404 na maioria dos itens e a
      página de detalhe só traz o logo institucional. Preferimos gravar sem
      imagem (o card mostra o 🖼 e o `_og_image` do módulo tenta depois)
      a gravar URL quebrada, que apareceria como imagem corrompida.
    • Retorna 0 em falha (fail-soft) e nunca levanta.
    """
    try:
        html = _get_html(url)
        if not html:
            return 0
        import re as _re
        from html import unescape as _unescape
        from urllib.parse import urljoin as _urljoin
        # data dd/mm/aaaa + link + title num único item
        padrao = _re.compile(
            r'<span class="data-noticia-internas">\s*(\d{2}/\d{2}/\d{4})\s*-\s*</span>'
            r'\s*<a href="([^"]+)"\s+title="([^"]*)"[^>]*>(.*?)</a>'
            r'(.*?)</h2>', _re.S | _re.I)
        achados = padrao.findall(html or "")
        if not achados:
            _log().warning(
                "_coletar_tcemg: nenhum item encontrado — o layout do site "
                "pode ter mudado (verificar .data-noticia-internas)")
            return 0
        base = (url or "").rstrip("/")
        base = base[: base.rfind("/")] if "/Noticia" in base else base
        n = 0
        for data_br, href, title_attr, _corpo, cauda in achados:
            titulo = _unescape((title_attr or "").strip())
            if not titulo:
                continue
            link = _urljoin(base + "/", href)
            # Miniatura: verificado em 26/09/2026 que o padrão deduzido
            # /ImagemDestaque/<id>.png NÃO é confiável (a maioria devolve
            # 404) e a página de detalhe só tem o logo institucional.
            # Então fica SEM imagem e o `_og_image` (padrão do módulo) trata.
            img = ""
            # resumo: primeiro <p> útil do item, sem o "Clique aqui"
            resumo = ""
            for p in _re.findall(r"<p[^>]*>(.*?)</p>", cauda or "", _re.S | _re.I):
                limpo = _unescape(_re.sub(r"<[^>]+>", " ", p))
                limpo = _re.sub(r"\s+", " ", limpo).replace("Clique aqui", "").strip()
                if len(limpo) > 40:
                    resumo = limpo
                    break
            if not resumo:
                resumo = titulo
            dia, mes, ano = (data_br.split("/") + ["", "", ""])[:3]
            data_pub = f"{ano}-{mes}-{dia}" if ano else None
            if inserir_noticia(titulo, "TCE-MG", tema, link, img, resumo, data_pub):
                n += 1
            if n >= 20:
                break
        return n
    except Exception as e:
        _log().warning(f"_coletar_tcemg {tema}: {e}")
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
            elif tipo == "tcemg":
                total += _coletar_tcemg(url, tema)
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
