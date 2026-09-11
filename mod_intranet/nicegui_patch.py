"""Patches NiceGUI timers to tolerate page teardown (no "parent slot deleted").

O NiceGUI dispara timers em background tasks; quando a página é navegada ou
fechada, o slot do elemento é removido e um tick pendente lança
`RuntimeError: The parent slot of Timer(...) has been deleted` (ruído no log
do carrossel do Blog e dos timers `once` de reload). Este patch torna esse
cenário silencioso e PARA o timer cujo slot desapareceu (evita ruído e
vazamento de timers).

EN: Silences NiceGUI timers whose parent slot was deleted and stops them,
preventing the noisy "The parent slot of Timer has been deleted" runtime error
after navigating away from a page.
"""
from contextlib import nullcontext

from nicegui.elements.timer import Timer as _Timer

_orig_get_context = _Timer._get_context
_orig_should_stop = _Timer._should_stop


def _get_context(self):
    """Returns nullcontext instead of raising when the parent slot is gone."""
    try:
        return self.parent_slot or nullcontext()
    except RuntimeError:
        return nullcontext()


def _should_stop(self):
    """Stops the timer when its parent slot was deleted (page navegada/fechada).

    Um timer global (sem slot) segue normal; um timer cujo slot morreu (weakref
    expirada) para de rodar."""
    try:
        if getattr(self, "_parent_slot", None) is not None:
            _ = self.parent_slot
    except RuntimeError:
        return True
    return _orig_should_stop(self)


def aplicar():
    """Aplica os patches no NiceGUI (idempotente)."""
    if getattr(_Timer, "_patch_aplicado", False):
        return
    _Timer._get_context = _get_context
    _Timer._should_stop = _should_stop
    _Timer._patch_aplicado = True