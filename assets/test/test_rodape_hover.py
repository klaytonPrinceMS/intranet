"""Rodapé escondido com reveal no hover — bloco FOOTER.

EN: Auto-hide footer — hidden with a 5px hint strip, revealed on
    hover/focus-within at full size; content, colors and labels unchanged.
PT: Rodapé escondido com reveal no hover/focus (faixa de 5px como pista),
    no tamanho original e sem alterar conteúdo/cores; sem JS, sem `hidden`.

Cobre as validações de sessão (evidência Playwright 14/09/2026):
- `ui.footer` expõe `data-testid=rodape-sistema`;
- CSS escopado `[data-testid="rodape-sistema"]` com `opacity:0`,
  `translateY(calc(100% - 5px))`, transição .25s e reveal `:hover` +
  `:focus-within`;
- rótulos do sistema/versões preservados; degradation segura (sem o CSS,
  apenas volta a ficar sempre visível).
O comportamento real (opacity 0 → 1 no hover) é coberto pelo E2E
`assets/test/e2e/05_rodape_hover.spec.js`.

Somente LEITURA (fonte). Sem servidor.

Execute: .venv/bin/python assets/test/test_rodape_hover.py
"""
import inspect
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


print("INICIANDO TESTES — rodapé escondido com reveal no hover")

import mod_intranet.telas as telas_mod  # noqa: E402

fonte = inspect.getsource(telas_mod)
check("data-testid=rodape-sistema" in fonte,
      "footer expõe data-testid=rodape-sistema")
check('[data-testid="rodape-sistema"]{opacity:0' in fonte,
      "CSS escopado inicia oculto (opacity:0)")
check("translateY(calc(100% - 5px))" in fonte,
      "faixa de 5px permanece visível como pista de descoberta")
check(":hover" in fonte and ":focus-within" in fonte,
      "reveal no hover e no focus-within")
check("transition:opacity .25s" in fonte or "transition:opacity.25s" in fonte.replace(" ", ""),
      "transição suave de .25s")
check("bg-grey-8" in fonte,
      "cor de fundo bg-grey-8 preservada")
check("texto_rodape" in fonte and "_formatar_versao_rodape" in fonte,
      "rótulos do sistema/versões preservados no rodapé")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
