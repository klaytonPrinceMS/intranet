"""Censura de conteúdo — palavras bloqueadas em títulos.

EN: Content censorship — blocked words in titles (admin-configurable).
PT: Lista central de palavras que não podem aparecer em títulos (blog, agregador)
    para evitar conteúdo indesejado (ex: tinder, suicídio). Config via tb_config.
"""
import re
import unicodedata

CHAVE_CONFIG = "conteudo_palavras_bloqueadas"


def _normalizar(texto: str) -> str:
    """Lower + sem acento para comparação insensível."""
    if not texto:
        return ""
    texto = texto.lower().strip()
    # remove acentos
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return texto


def obter_palavras_bloqueadas() -> list[str]:
    """Lista de palavras bloqueadas (lower, sem vazio)."""
    try:
        from mod_intranet.bd_conexao import get_config
        raw = (get_config(CHAVE_CONFIG, "") or "").strip()
        if not raw:
            return []
        # suporta CSV, linha por linha, ou JSON
        if raw.startswith("["):
            import json
            try:
                dados = json.loads(raw)
                if isinstance(dados, list):
                    return [str(p).strip().lower() for p in dados if str(p).strip()]
            except Exception:
                pass
        partes = re.split(r"[,]+", raw)
        return [p.strip().lower() for p in partes if p.strip()]
    except Exception:
        return []


def definir_palavras_bloqueadas(palavras: list[str], ator: str = "sistema") -> bool:
    """Grava lista (normaliza lower, sem duplicatas)."""
    try:
        from mod_intranet.bd_conexao import set_config
        from mod_intranet.bd_manipulador import audit_log
        # normaliza
        norm = []
        vistos = set()
        for p in palavras or []:
            pp = (p or "").strip().lower()
            if not pp or pp in vistos:
                continue
            vistos.add(pp)
            norm.append(pp)
        # grava como CSV
        raw = ", ".join(norm)
        ok = set_config(CHAVE_CONFIG, raw)
        if ok:
            try:
                audit_log(ator or "sistema", "censura", "palavras_bloqueadas", raw[:500])
            except Exception:
                pass
        return ok
    except Exception:
        return False


def titulo_bloqueado(titulo: str, palavras: list[str] = None) -> tuple[bool, str]:
    """Verifica se título contém palavra bloqueada. Retorna (bloqueado, palavra_encontrada)."""
    if not titulo:
        return False, ""
    if palavras is None:
        palavras = obter_palavras_bloqueadas()
    if not palavras:
        return False, ""
    norm_titulo = _normalizar(titulo)
    for palavra in palavras:
        norm_pal = _normalizar(palavra)
        if not norm_pal:
            continue
        if norm_titulo.startswith(norm_pal):
            return True, palavra
    return False, ""


def filtrar_titulo(titulo: str) -> tuple[bool, str]:
    """Atalho para verificar título contra lista atual."""
    return titulo_bloqueado(titulo)
