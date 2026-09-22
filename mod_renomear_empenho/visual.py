"""Visual switcher for mod_renomear_empenho — uma tela por CSS disponível.

Módulo de comutação visual: cada framework em assets/css/frameworks
(bootstrap, bulma, daisyui, pico, picnic) + pic nativo + hibrido (mistura
PIC+Bootstrap) gera uma tela dedicada /renomear-empenho-{framework}. O
hibrido é o padrão (mistura suave+impactante); todos são injetados por página
via tema_css.injetar_framework — sem CDN, sem reset global fora do escopo.

Uso:
    from mod_renomear_empenho.visual import ler_modelo, eh_bootstrap, aplicar_framework, classes_card_pdf, ...

Data-testid e assinaturas mostrar_tela/mostrar_administracao são preservados.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mod_intranet import observabilidade

log = observabilidade.get_logger("renomear_empenho")

CHAVE_CONFIG = "empenhos_modelo_visual"
MODELO_PADRAO = "pic"
# Pic nativo é o padrão; cada CSS novo tem tela dedicada /renomear-empenho-{nome}
# Mantém os 5 antigos em disco mas expõe só pic + 12 novos (remove os anteriores do menu).
FRAMEWORKS = ("spectre", "chota", "milligram", "skeleton", "water", "mvp", "tachyons", "uikit", "foundation", "semantic", "materialize", "primer")
VALIDOS = ("pic",) + FRAMEWORKS
# Mapa de rótulo amigável para menu/admin
ROTULOS = {
    "pic": "PIC — Quasar nativo suave (padrão)",
    "spectre": "Spectre 0.5.9",
    "chota": "Chota 0.8.0",
    "milligram": "Milligram 1.4.1",
    "skeleton": "Skeleton 2.0.4",
    "water": "Water.css 2.1.1",
    "mvp": "MVP.css 1.14",
    "tachyons": "Tachyons 4.12.0",
    "uikit": "UIkit 3.21.5",
    "foundation": "Foundation 6.8.1",
    "semantic": "Semantic UI 2.5",
    "materialize": "Materialize 1.0",
    "primer": "Primer 21",
}

# Variável simples para forçar sem depender de tb_config (ex.: "pic" ou "bootstrap").
# Deixe None para usar tb_config (comportamento padrão/pedido).
FORCAR_MODELO = None  # type: ignore

# Overridable via env var para testes locais sem tocar o BD.
_ENV_FORCAR = (os.environ.get("EMPENHOS_MODELO_VISUAL") or "").strip().lower()
if _ENV_FORCAR in VALIDOS:
    FORCAR_MODELO = _ENV_FORCAR


def _get_config_safe(chave, default, get_config=None):
    if get_config is not None:
        try:
            return get_config(chave, default)
        except Exception:
            return default
    try:
        from mod_intranet.bd_conexao import get_config as _gc
        return _gc(chave, default)
    except Exception:
        return default


def ler_modelo(get_config=None) -> str:
    """Lê o modelo visual atual (pic|bootstrap), fail-soft para 'pic'."""
    if FORCAR_MODELO in VALIDOS:
        return FORCAR_MODELO
    try:
        raw = _get_config_safe(CHAVE_CONFIG, MODELO_PADRAO, get_config)
        v = (raw or "").strip().lower()
        return v if v in VALIDOS else MODELO_PADRAO
    except Exception:
        return MODELO_PADRAO


def eh_bootstrap(get_config=None) -> bool:
    try:
        return ler_modelo(get_config) == "bootstrap"
    except Exception as e:
        log.exception(f"eh_bootstrap falhou: {e}")
        return None


def eh_hibrido(get_config=None) -> bool:
    try:
        return ler_modelo(get_config) == "hibrido"
    except Exception as e:
        log.exception(f"eh_hibrido falhou: {e}")
        return None


def eh_pic(get_config=None) -> bool:
    try:
        return ler_modelo(get_config) == "pic"
    except Exception as e:
        log.exception(f"eh_pic falhou: {e}")
        return None


def eh_framework(nome: str, get_config=None) -> bool:
    try:
        return ler_modelo(get_config) == (nome or "").strip().lower()
    except Exception as e:
        log.exception(f"eh_framework falhou: {e}")
        return None


def salvar_modelo(valor: str, set_config=None) -> bool:
    """Grava o modelo em tb_config; retorna True se gravou."""
    v = (valor or "").strip().lower()
    if v not in VALIDOS:
        return False
    try:
        if set_config is not None:
            set_config(CHAVE_CONFIG, v)
        else:
            from mod_intranet.bd_conexao import set_config as _sc
            _sc(CHAVE_CONFIG, v)
        # limpar caches de tema se existirem
        try:
            from mod_intranet.tema_modulo import _cfg as _cfg_cache, ler_tema
            _cfg_cache.cache_clear()  # type: ignore
            ler_tema.cache_clear()  # type: ignore
        except Exception:
            pass
        return True
    except Exception:
        return False


def aplicar_framework(nome_ou_flag=True) -> bool:
    """Injeta o CSS local do framework (str) ou compat bool (True=bootstrap)."""
    try:
        from mod_intranet import tema_css
        if isinstance(nome_ou_flag, str):
            nome = nome_ou_flag.strip().lower()
            if not nome or nome in ("pic", "hibrido"):
                return False
            return bool(tema_css.injetar_framework(nome))
        # compat bool
        if not nome_ou_flag:
            return False
        return bool(tema_css.injetar_framework("bootstrap"))
    except Exception:
        return False


def aplicar_modelo(modelo: str) -> bool:
    """Aplica o modelo completo (injetando framework/CSS correto)."""
    try:
        m = (modelo or "").strip().lower()
        if m == "hibrido":
            injetar_hibrido()
            return True
        if m == "pic":
            injetar_pic_suave()
            return True
        if m in FRAMEWORKS:
            ok = aplicar_framework(m)
            # css suave de convivência para não quebrar Quasar
            try:
                injetar_bootstrap_overrides()
            except Exception:
                pass
            return ok
        injetar_pic_suave()
        return False
    except Exception as e:
        log.exception(f"aplicar_modelo falhou: {e}")
        return None


def injetar_pic_suave():
    """PIC puro — Quasar nativo suave (sem Bootstrap) — sombras, bordas e foco a11y."""
    try:
        from nicegui import ui
        ui.add_head_html("""
<style>
/* PIC puro — mod_renomear_empenho (sem Bootstrap) */
.empenho-card-pic{border-radius:14px;box-shadow:0 1px 6px rgba(0,0,0,.06);border:1px solid #e5e7eb;background:#fff;transition:box-shadow .18s ease, transform .15s ease}
.empenho-card-pic:hover{box-shadow:0 6px 18px rgba(0,0,0,.08);transform:translateY(-1px)}
.empenho-card-pic:focus-within{box-shadow:0 0 0 3px rgba(21,101,192,.18), 0 6px 18px rgba(0,0,0,.08)}
.empenho-badge-soft{border-radius:999px;padding:.22rem .55rem;font-weight:600;font-size:.70rem;letter-spacing:.02em;line-height:1}
.empenho-input-soft .q-field__control{border-radius:10px}
.empenho-input-soft .q-field__control:before{border-color:#e5e7eb}
.empenho-lote-pic{background:linear-gradient(180deg,#ffffff 0%,#fafafa 100%);border:1px solid #e5e7eb;border-radius:14px}
.empenho-breadcrumb-pic{background:#f7f7f8;border:1px solid #ececec;border-radius:10px;padding:.35rem .6rem}
@media (max-width: 640px){
  .empenho-card-pic{padding:.75rem !important}
}
</style>
""")
    except Exception:
        pass


def injetar_hibrido():
    """Híbrido PIC+Bootstrap — mistura suave + impactante sem reset global do Bootstrap."""
    try:
        from nicegui import ui
        # Bootstrap leve só no escopo do híbrido (sem quebrar Quasar)
        aplicar_framework(True)
        ui.add_head_html("""
<style>
/* Híbrido PIC+Bootstrap — mod_renomear_empenho */
.empenho-hibrido{--hb-radius:14px;--hb-shadow:0 2px 10px rgba(0,0,0,.07);--hb-border:#e5e7eb;--hb-accent:#1565c0}
.empenho-card-hibrido{border-radius:var(--hb-radius);box-shadow:var(--hb-shadow);border:1px solid var(--hb-border);background:#fff;transition:box-shadow .18s ease, transform .15s ease, border-color .18s}
.empenho-card-hibrido:hover{box-shadow:0 8px 22px rgba(0,0,0,.10);transform:translateY(-1px);border-color:#d1d5db}
.empenho-card-hibrido:focus-within{box-shadow:0 0 0 3px rgba(21,101,192,.16), 0 8px 22px rgba(0,0,0,.10)}
.empenho-card-hibrido .empenho-card-top{border-left:4px solid var(--hb-accent);border-radius:var(--hb-radius) 0 0 var(--hb-radius);padding-left:.6rem}
.empenho-hibrido .q-field__control{border-radius:12px !important}
.empenho-hibrido .q-field__control:before{border-color:#d1d5db}
.empenho-hibrido .q-field--focused .q-field__control{box-shadow:0 0 0 3px rgba(21,101,192,.12)}
.empenho-badge-hibrido{border-radius:999px;padding:.28rem .62rem;font-weight:700;font-size:.72rem;letter-spacing:.02em;line-height:1;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.empenho-badge-hibrido.bg-success{background:#198754 !important}
.empenho-badge-hibrido.bg-warning{background:#ffc107 !important;color:#212529 !important}
.empenho-badge-hibrido.bg-secondary{background:#6c757d !important}
.empenho-lote-hibrido{background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);border:1px solid var(--hb-border);border-radius:var(--hb-radius);box-shadow:var(--hb-shadow)}
.empenho-breadcrumb-hibrido{background:linear-gradient(180deg,#f8f9fa 0%,#f1f3f5 100%);border:1px solid #e9ecef;border-radius:12px;padding:.45rem .7rem;box-shadow:0 1px 6px rgba(0,0,0,.05)}
.empenho-hibrido .input-group-text{background:#f8f9fa;border-radius:12px 0 0 12px;border-color:#d1d5db}
.empenho-hibrido .form-control{border-radius:12px !important;border-color:#d1d5db}
.empenho-hibrido .alert{border-radius:12px;box-shadow:0 1px 6px rgba(0,0,0,.05)}
@media (max-width: 640px){
  .empenho-card-hibrido{padding:.75rem !important}
}
</style>
""")
        injetar_bootstrap_overrides()
    except Exception:
        pass


def injetar_bootstrap_overrides():
    """Overrides mínimos quando Bootstrap está ativo para convivência com Quasar."""
    try:
        from nicegui import ui
        ui.add_head_html("""
<style>
/* Bootstrap ativo — escopo local do módulo empenhos (evita vazamento) */
.empenho-bootstrap .card{border:1px solid #e9ecef;border-radius:1rem;box-shadow:0 .125rem .25rem rgba(0,0,0,.06)}
.empenho-bootstrap .badge{font-weight:600;letter-spacing:.02em}
.empenho-bootstrap .form-control{border-radius:.6rem}
.empenho-bootstrap .input-group .form-control{border-radius:.6rem}
.empenho-bootstrap .alert{border-radius:.75rem}
</style>
""")
    except Exception:
        pass


# ===== Helpers de classes condicionais =====

def classes_card_pdf(bootstrap: bool) -> str:
    try:
        if bootstrap:
            return "card shadow-sm border-0 rounded-3 w-full p-3 mt-1 empenho-bootstrap"
        return "w-full p-3 mt-1 rounded-xl shadow-sm border border-grey-2 bg-white empenho-card-pic"
    except Exception as e:
        log.exception(f"classes_card_pdf falhou: {e}")
        return None


def classes_card_pdf_hibrido() -> str:
    try:
        return "w-full p-3 mt-1 bg-white empenho-card-hibrido empenho-hibrido"
    except Exception as e:
        log.exception(f"classes_card_pdf_hibrido falhou: {e}")
        return None


def classes_card_lote(bootstrap: bool) -> str:
    try:
        if bootstrap:
            return "card shadow-sm border-0 rounded-3 w-full p-3 mt-2 empenho-bootstrap"
        return "w-full p-3 mt-2 empenho-lote-pic shadow-sm"
    except Exception as e:
        log.exception(f"classes_card_lote falhou: {e}")
        return None


def classes_card_lote_hibrido() -> str:
    try:
        return "w-full p-3 mt-2 empenho-lote-hibrido empenho-hibrido"
    except Exception as e:
        log.exception(f"classes_card_lote_hibrido falhou: {e}")
        return None


def classes_wrap_pesquisa(bootstrap: bool) -> str:
    try:
        if bootstrap:
            return "w-full sm:w-80"
        return "w-full sm:w-80 empenho-input-soft"
    except Exception as e:
        log.exception(f"classes_wrap_pesquisa falhou: {e}")
        return None


def classes_input_pesquisa(bootstrap: bool) -> str:
    try:
        # Mantém Quasar outlined; Bootstrap injeta form-control visual via CSS global quando ativo.
        if bootstrap:
            return "w-full sm:w-80"
        return "w-full sm:w-80"
    except Exception as e:
        log.exception(f"classes_input_pesquisa falhou: {e}")
        return None


def classes_badge_bootstrap(tipo: str) -> str:
    try:
        mapa = {
            "processado": "badge bg-success",
            "pendente": "badge bg-warning text-dark",
            "presente": "badge bg-success",
            "ausente": "badge bg-secondary",
            "fora": "badge bg-secondary",
            "zip_gerado": "badge bg-warning text-dark",
            "pendente_lote": "badge bg-primary",
        }
        return mapa.get(tipo, "badge bg-secondary")
    except Exception as e:
        log.exception(f"classes_badge_bootstrap falhou: {e}")
        return None


def cor_badge_pic(status: str) -> str:
    try:
        mapa = {"processado": "green", "pendente": "orange", "zip_gerado": "orange"}
        return mapa.get((status or "").lower(), "grey")
    except Exception as e:
        log.exception(f"cor_badge_pic falhou: {e}")
        return None
