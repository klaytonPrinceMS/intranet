"""Fachada de integração entre módulos — API pública do núcleo.

EN: Facade for cross-module integration — the single public seam that lets a
    business module reach another module WITHOUT importing it directly.
    Keeps the DAS rule of AGENTS.md §2 ("never cross-query between databases"):
    a module talks to `mod_intranet`, and the core owns the coupling. Every
    function is fail-soft: if the target module is absent, disabled or raises,
    it returns a neutral value and logs — it NEVER breaks the caller's screen.

PT-BR: Fachada de integração entre módulos — costura pública única para um
    módulo de negócio alcançar outro SEM importá-lo diretamente. Preserva a
    regra do AGENTS.md §2 ("nunca faça cross-query entre bancos"): o módulo
    fala com o `mod_intranet`, e o núcleo possui o acoplamento. Toda função é
    fail-soft: se o módulo de destino estiver ausente, desabilitado ou lançar
    exceção, devolve valor neutro e registra no log — NUNCA quebra a tela.

Usage:
    from mod_intranet import integracoes
    integracoes.listar_usuarios_gestao(filtro_ativo=True)

Imports are LAZY (inside the functions) on purpose: a top-level import of a
business module here would close a top-level import cycle with `main.py`.
"""
import logging

logger = logging.getLogger(__name__)


# ================== Gestão de usuários (mod_gest_cad_usuario) ==================


def obter_usuario_gestao(user_nome: str):
    """EN: One user row from the user registry, or None.

    PT-BR: Uma linha da cadastro de usuários pelo nome, ou None. Usado por
    Filas e Lista Telefônica sem que eles conheçam o módulo de gestão."""
    try:
        nome = (user_nome or "").strip()
        if not nome:
            return None
        from mod_gest_cad_usuario.bd_manipulador import obter_usuario
        return obter_usuario(nome)
    except Exception as exc:
        logger.warning("integracoes.obter_usuario_gestao('%s'): falha (%s) — devolvendo None",
                       user_nome, exc)
        return None


def listar_usuarios_gestao(filtro_ativo=None) -> list:
    """EN: User rows from the registry (per-module access aggregated).

    PT-BR: Linhas do cadastro de usuários (acesso por módulo agregado). Lista
    vazia em qualquer falha — a tela que chama decide o que fazer."""
    try:
        from mod_gest_cad_usuario.bd_manipulador import listar_usuarios
        return list(listar_usuarios(filtro_ativo=filtro_ativo) or [])
    except Exception as exc:
        logger.warning("integracoes.listar_usuarios_gestao(filtro_ativo=%s): falha (%s) — devolvendo []",
                       filtro_ativo, exc)
        return []


# ================== Agregador de notícias (mod_agregador_noticias) ==================


def agregador_habilitado() -> bool:
    """EN: Whether the news aggregator is switched on in its own config.

    PT-BR: Se o agregador de notícias está ligado na configuração do módulo.
    Falso quando o módulo não responde — a TV Filas cai no aviso de pausa."""
    try:
        from mod_agregador_noticias.bd_manipulador import habilitado
        return bool(habilitado())
    except Exception as exc:
        logger.warning("integracoes.agregador_habilitado: falha (%s) — devolvendo False", exc)
        return False


def listar_noticias_para_tv(limite: int = 200) -> list:
    """EN: Up to `limite` recent headlines for the Filas TV carousel (censorship filtered).

    PT-BR: Até `limite` manchetes recentes para o carrossel da TV Filas
    (censura já filtrada na origem). Lista vazia em qualquer falha."""
    try:
        from mod_agregador_noticias.bd_manipulador import listar_para_tv
        return list(listar_para_tv(limite=limite) or [])
    except Exception as exc:
        logger.warning("integracoes.listar_noticias_para_tv(limite=%s): falha (%s) — devolvendo []",
                       limite, exc)
        return []


def limpar_noticias_censuradas() -> int:
    """EN: Drop already-collected headlines whose title is censored; returns how many.

    PT-BR: Remove as notícias já coletadas cujo título está censurado e devolve
    quantas saíram. Usado pelo admin do Blog ao salvar a lista de censura —
    quem orquestra é o núcleo, não o Blog conhecendo o Agregador."""
    try:
        from mod_agregador_noticias.bd_manipulador import limpar_censuradas
        return int(limpar_censuradas() or 0)
    except Exception as exc:
        logger.warning("integracoes.limpar_noticias_censuradas: falha (%s) — devolvendo 0", exc)
        return 0


# ================== Lista telefônica (mod_lista_telefonica) ==================


def obter_organograma_base():
    """EN: The shared organogram seed (secretaria -> sector -> subsector).

    PT-BR: A semente do organograma compartilhado (secretaria → setor → subsetor),
    fonte única das cotas por área. Devolve `None` quando o módulo não responde,
    para o chamador manter o seu próprio fallback local."""
    try:
        from mod_lista_telefonica.bd_manipulador import ORGANOGRAMA_BASE
        return ORGANOGRAMA_BASE
    except Exception as exc:
        logger.warning("integracoes.obter_organograma_base: falha (%s) — devolvendo None", exc)
        return None


# ================== Módulos do sistema ==================


def modulo_habilitado(chave: str) -> bool:
    """EN: Whether a business module is switched on (`tb_modulos.ativo`).

    PT-BR: Se um módulo de negócio está ligado (`tb_modulos.ativo`).
    Módulo desconhecido conta como desligado."""
    try:
        from mod_intranet.autenticacao import modulos_registrados
        alvo = (chave or "").strip()
        if not alvo:
            return False
        for linha in modulos_registrados() or []:
            # linha = (chave, nome, icone, rota, ativo)
            if len(linha) >= 5 and linha[0] == alvo:
                return bool(linha[4])
        return False
    except Exception as exc:
        logger.warning("integracoes.modulo_habilitado('%s'): falha (%s) — devolvendo False",
                       chave, exc)
        return False
