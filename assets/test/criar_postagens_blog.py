"""Seed of "how-to" blog posts for the common user (Editor PDF, Print Request, Empenhos).

Seed de postagens de "como usar" para o Blog (módulos Editor PDF, Solicitação de
Impressão e Empenhos). Reutiliza o padrão oficial `POSTAGENS_PADRAO` de
`mod_blog/bd_manipulador` (título `# **..**`, subtítulo `###`, seções em
negrito, Mermaid ao fim) — sem duplicar conteúdo, para nunca divergir.
Reutiliza a função `criar_postagem` do módulo blog (sanitização nh3, permissão e
auditoria, que move o Mermaid para o fim). Falhas por postagem são registradas
no loguru e não interrompem o restante do seed (fail-soft).

Executar com o venv: `source .venv/bin/activate && python test/criar_postagens_blog.py`
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mod_blog.bd_manipulador import criar_postagem, POSTAGENS_PADRAO as POSTAGENS

AUTOR = "master"


def _log():
    """Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("blog")


def main():
    """Runs the seed, creating each how-to post and reporting the result.

    Executa o seed criando cada postagem de "como usar" via `criar_postagem`
    (autor `master`). Cada postagem é tratada isoladamente: falha em uma não
    interrompe as demais (fail-soft) e é registrada no loguru. Ao final imprime
    o total criado e retorna o número de postagens inseridas com sucesso."""
    criadas = 0
    try:
        for p in POSTAGENS:
            try:
                pid = criar_postagem(p["titulo"], p["conteudo"], AUTOR)
                if pid:
                    criadas += 1
                    _log().info(f"seed: postagem criada #{pid} '{p['titulo']}' por {AUTOR}")
                    print(f"OK  #{pid}  {p['titulo']}  (autor: {AUTOR})")
                else:
                    _log().warning(f"seed: falha ao criar '{p['titulo']}' (sem permissão ou erro)")
                    print(f"FALHA  {p['titulo']}")
            except Exception as e:
                _log().exception(f"seed: erro ao criar '{p['titulo']}': {e}")
                print(f"FALHA  {p['titulo']}  ({e})")
        print(f"\nTotal criadas: {criadas}/{len(POSTAGENS)}")
        return criadas
    except Exception as e:
        _log().exception(f"seed: falha geral ao executar: {e}")
        return criadas


if __name__ == "__main__":
    main()