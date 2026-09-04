"""Teste standalone do helper central de tema (mod_intranet/tema_modulo.py).

Valida o mapeamento de prefixo por chave, a leitura das 6 chaves de aparência
para cada módulo e as funções puras btn_cls/btn_style (regra de uniformidade:
todos os botões de uma mesma tela usam SEMPRE a mesma cor).

Apenas LEITURA — não altera tb_config, não destrói dados do desenvolvedor.

Executar: .venv/bin/python test/test_tema.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULOS = ["blog", "usuarios", "auditoria", "editar_pdf", "empenhos",
           "solicita_impressao"]

PASS = []
FAIL = []


def checar(nome, cond):
    if cond:
        PASS.append(nome)
    else:
        FAIL.append(nome)
    print(f"  {'OK ' if cond else 'FALHA'} {nome}")


def main():
    from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos
    inicializar_bancos()

    from mod_intranet.tema_modulo import (
        PREFIXO_POR_CHAVE, prefixo_da_chave, ler_tema, btn_cls, btn_style)

    print("== Mapeamento de prefixo por chave de módulo ==")
    esperado = {"blog": "blog", "usuarios": "usuarios", "auditoria": "auditoria",
                "editar_pdf": "editpdf", "empenhos": "empenhos",
                "solicita_impressao": "solicita_impressao"}
    for chave, pref in esperado.items():
        checar(f"prefixo {chave} -> {pref}", prefixo_da_chave(chave) == pref)

    print("== Leitura do tema (6 chaves) de cada módulo ==")
    for chave in MODULOS:
        t = ler_tema(chave, cor_botao="#000000", btn_tamanho="medium")
        checar(f"ler_tema {chave} tem 6 campos",
               all(k in t for k in ("cor_botao", "cor_texto_botao", "cor_fundo",
                                    "cor_titulo", "btn_tamanho", "texto_header")))

    print("== btn_cls por tamanho ==")
    checar("small -> min-w-[140px]", btn_cls("small") == "min-w-[140px] text-sm")
    checar("medium -> min-w-[180px]", btn_cls("medium") == "min-w-[180px]")
    checar("large -> min-w-[220px]", btn_cls("large") == "min-w-[220px] text-lg")

    print("== btn_style (regra: mesma cor em todos os botões) ==")
    cor = "#123456"
    txt = "#FFFFFF"
    st = btn_style(cor, txt)
    checar("btn_style contém background-color", f"background-color:{cor};" in st)
    checar("btn_style contém color", f"color:{txt};" in st)
    # Com os mesmos argumentos, todos os botões recebem o MESMO estilo (uniformidade).
    checar("btn_style é determinístico (mesma cor)", btn_style(cor, txt) == st)

    print(f"\n==== RESULTADO: {len(PASS)} OK, {len(FAIL)} falha(s) ====")
    if FAIL:
        print("Falhas:", *FAIL, sep="\n  - ")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
