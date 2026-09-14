"""Blog module — posts and comments with nh3 sanitization (route /blog).

Módulo Blog — postagens e comentários com sanitização nh3 (rota /blog)."""
import os


def montar_rotas_static():
    """Serve as imagens do editor em `/img_postagens/*` (pasta do módulo).

    Monta `mod_blog/img_postagens/` como arquivos estáticos (mesmo padrão de
    `mod_intranet.tema_css.montar_rotas_static`); chamada no boot pelo main.py.
    """
    try:
        from nicegui import app
        _base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img_postagens")
        os.makedirs(_base, exist_ok=True)
        app.add_static_files("/img_postagens", _base)
    except Exception as e:
        try:
            from mod_intranet import observabilidade
            observabilidade.get_logger("blog").warning(
                f"montar_rotas_static: não foi possível montar /img_postagens: {e}")
        except Exception:
            pass
