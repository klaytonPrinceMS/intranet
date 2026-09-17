"""Controles de imagem do editor do Blog — alinhar/esticar.

EN: Blog editor image controls — left/center/right alignment and width on
    the last `<img>`, preserving the other axis and author CSS; renderer
    respects author alignment/size, defaults otherwise.
PT: Linha "Imagem:" do editor — botões esquerda/centro/direita + seletor de
    largura aplicados à ÚLTIMA `<img>` (`ajustar_imagem_html` pura); linha
    "Quebra:" com 7 estilos Word (em_linha, quadrado, justo, atraves,
    sup_inf, atras, frente); o render (`_FormatadorBlog`) respeita
    (`_FormatadorBlog`) respeita `float`/margens `auto`/`max-width` do autor
    e só aplica o padrão (esquerda, 200–400px configuráveis) no resto.

Cobre as validações de sessão (Playwright + backend 14/09/2026):
- centro/direita/esquerda, larguras, preservação do outro eixo e do CSS;
- sem imagem levanta `ValueError` (tela avisa); última imagem é o alvo;
- feed: centro sem `float:left`, 50% sem limites padrão, sem estilo do
  autor com padrão aplicado.

Somente LEITURA (sem banco, sem servidor).

Execute: .venv/bin/python assets/test/test_blog_imagem_controles.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


print("INICIANDO TESTES — controles de imagem do editor")

from mod_blog.bd_manipulador import (  # noqa: E402
    ajustar_imagem_html,
    formatar_conteudo_para_exibicao as fmt,
    _largura_imagem,
)

_BASE = '<p><img src="/img_postagens/a.png" style="max-width:100%;height:auto;"></p>'

# ---------- alinhamentos ----------
novo, det = ajustar_imagem_html(_BASE, alinhamento="centro")
check("display:block" in novo and "margin:8px auto" in novo and "float" not in novo,
      "centro ancora sem float")
novo, det = ajustar_imagem_html(_BASE, alinhamento="direita")
check("float:right" in novo and "margin:0 0 12px 12px" in novo,
      "direita com recuo")
novo, det = ajustar_imagem_html(_BASE, alinhamento="esquerda")
check("float:left" in novo, "esquerda")

# ---------- preservação do outro eixo ----------
novo, _det = ajustar_imagem_html(_BASE, alinhamento="direita")
novo2, _det2 = ajustar_imagem_html(novo, largura="50%")
check("float:right" in novo2 and "max-width:50%" in novo2,
      "trocar largura preserva o alinhamento")
novo3, _det3 = ajustar_imagem_html(novo2, alinhamento="centro")
check("margin:8px auto" in novo3 and "max-width:50%" in novo3,
      "trocar alinhamento preserva a largura")
novo4, _det4 = ajustar_imagem_html(novo3, largura="original")
check("max-width" not in novo4 and "margin:8px auto" in novo4,
      "'original' remove o max-width e mantém o centro")

# ---------- CSS do autor e alvo ----------
novo5, _d5 = ajustar_imagem_html(
    '<p><img src="a.png" style="border-radius:8px"></p>', alinhamento="esquerda")
check("border-radius:8px" in novo5 and "float:left" in novo5,
      "CSS do autor (border-radius) preservado")
novo6, _d6 = ajustar_imagem_html(
    '<p><img src="a.png"><img src="b.png"></p>', alinhamento="direita")
_primeira = novo6.split('src="b.png"')[0]
check(novo6.count("float:right") == 1 and "style=" not in _primeira,
      "alvo é a ÚLTIMA imagem (primeira intacta)")
try:
    ajustar_imagem_html("<p>sem imagem</p>")
    check(False, "sem imagem levanta ValueError (tela avisa)")
except ValueError:
    check(True, "sem imagem levanta ValueError (tela avisa)")

# ---------- render respeita o autor ----------
c = fmt('<p><img src="/img_postagens/a.png" '
        'style="max-width:50%;height:auto;display:block;margin:8px auto;"></p>')
check("float:left" not in c and "max-width:50%" in c and "min-width" not in c,
      "feed: centro+50% sem float e sem limites padrão")
d = fmt('<p><img src="/img_postagens/a.png" '
        'style="max-width:100%;height:auto;float:right;margin:0 0 12px 12px;"></p>')
check("float:right" in d and "float:left" not in d,
      "feed: direita do autor respeitada")
min_l, max_l = _largura_imagem()
p = fmt('<p><img src="/img_postagens/a.png"></p>')
check("float:left" in p and f"max-width:{max_l}px" in p and f"min-width:{min_l}px" in p,
      "feed: sem estilo do autor aplica o padrão configurado")

# ---------- quebra de texto (estilos Word) ----------
nq, _d = ajustar_imagem_html(_BASE, alinhamento="em_linha")
check("display:inline" in nq and "float" not in nq,
      "em_linha ancora na linha sem float")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="quadrado")
check("float:left" in nq and "margin:8px" in nq,
      "quadrado contorna em retângulo uniforme")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="justo")
check("float:left" in nq and "margin:2px" in nq
      and "shape-outside:margin-box" in nq,
      "justo cola o texto no contorno")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="atraves")
check("float:left" in nq and ";margin:0;" in nq
      and "shape-outside:margin-box" in nq,
      "atraves atravessa as margens")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="sup_inf")
check("display:block" in nq and "clear:both" in nq
      and "float" not in nq,
      "sup_inf isola em linha própria")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="atras")
check("opacity:0.45" in nq and "margin:8px auto" in nq,
      "atras vira marca d'água centralizada")
nq, _d = ajustar_imagem_html(_BASE, alinhamento="frente")
check("float:right" in nq and "z-index:1" in nq
      and "position:relative" in nq,
      "frente sobrepõe o texto à direita")

# ---------- preservação do outro eixo nos novos estilos ----------
nq, _d = ajustar_imagem_html(_BASE, alinhamento="justo")
nq2, _d2 = ajustar_imagem_html(nq, largura="50%")
check("shape-outside:margin-box" in nq2 and "max-width:50%" in nq2,
      "trocar largura preserva o justo")
nq3, _d3 = ajustar_imagem_html(nq2, alinhamento="sup_inf")
check("clear:both" in nq3 and "max-width:50%" in nq3
      and "shape-outside" not in nq3,
      "trocar estilo limpa o anterior e preserva a largura")
nq4, _d4 = ajustar_imagem_html(_BASE, alinhamento="frente")
nq5, _d5 = ajustar_imagem_html(nq4, largura="50%")
check("float:right" in nq5 and "z-index:1" in nq5
      and "max-width:50%" in nq5,
      "trocar largura preserva o frente")

# ---------- feed respeita a quebra ----------
e = fmt('<p><img src="/img_postagens/a.png" '
        'style="max-width:100%;height:auto;display:block;clear:both;margin:8px 0;"></p>')
check("clear:both" in e and "float:left" not in e,
      "feed: superior/inferior sem float")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
