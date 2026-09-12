"""Run the whole standalone test suite from a single pytest entrypoint.

EN — Executes every standalone script in `assets/test/` as a subprocess and
fails if any exits non-zero. Helps the mandatory `.venv/bin/pytest` command
run the existing script-based suite.

PT — Executa todos os scripts standalone de `assets/test/` em subprocesso e
falha se algum terminar com código de saída diferente de zero. Permite que o
comando obrigatório `.venv/bin/pytest` rode a suíte baseada em scripts.

Usage:
    .venv/bin/pytest
    .venv/bin/python assets/test/test_suite.py   # roda direto, com progresso
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "test"

# Scripts auxiliares, destrutivos de ambiente ou dependentes de instalação
# limpa (assumem master/master ainda válidos) — não entram na suíte.
EXCLUIR = {
    "test_suite.py",  # este próprio arquivo
    "debug_boot.py", "step_boot.py", "diag_config.py", "wtest.py",
    "criar_postagens_blog.py",
    "test_fresh_install.py", "fresh_install_test.py", "fresh_install_test2.py",
    "test_fase1_login.py", "validar_fase1_login.py",
    "test_server.py",  # helper: sobe a app na 8080 (bloqueia)
    "test_otel.py",    # integração OTel: depende da stack Docker/porta
}


def _env_limpo():
    """Environment without pytest markers (NiceGUI's is_pytest would demand
    NICEGUI_SCREEN_TEST_PORT inside `ui.run` in the subprocess), and forcing
    the SQLite backend so the standalone tests never depend on a live
    PostgreSQL (o backend persistido pode ser 'postgres' na máquina)."""
    env = dict(__import__("os").environ)
    for k in list(env):
        if k.startswith("PYTEST_"):
            del env[k]
    env["INTRANET_FORCE_SQLITE"] = "1"
    return env


def _scripts():
    for p in sorted(SUITE_DIR.glob("*.py")):
        if p.name not in EXCLUIR:
            yield p


def test_suite_standalone():
    """Runs every standalone test script and asserts all exit 0."""
    falhas = _rodar_suite(progresso=True)
    assert not falhas, "Falharam:\n\n" + "\n\n".join(falhas)


def _rodar_suite(progresso=False):
    """Executes every script, optionally printing live progress.

    Executa cada script e devolve a lista de falhas (vazia = tudo OK).
    Com `progresso=True`, imprime uma linha por script na hora (evita a
    sensacao de travamento: a suite completa leva varios minutos).
    """
    import time as _time
    falhas = []
    total = 0
    for p in _scripts():
        total += 1
        if progresso:
            print(f"[{total}] {p.name} ...", flush=True)
        ini = _time.time()
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True,
                               text=True, timeout=240, env=_env_limpo())
        except subprocess.TimeoutExpired:
            falhas.append(f"{p.name}: timeout 240s")
            if progresso:
                print(f"    FALHOU (timeout 240s)", flush=True)
            continue
        dur = _time.time() - ini
        if r.returncode != 0:
            saida = (r.stdout or "")[-1200:] + "\n" + (r.stderr or "")[-1200:]
            falhas.append(f"{p.name}: exit={r.returncode}\n{saida}")
            if progresso:
                print(f"    FALHOU em {dur:.0f}s (exit={r.returncode})",
                      flush=True)
        elif progresso:
            print(f"    OK em {dur:.0f}s", flush=True)
    return falhas


if __name__ == "__main__":
    _falhas = _rodar_suite(progresso=True)
    if _falhas:
        print(f"\nSUITE: {_falhas.__len__()} script(s) falharam:", flush=True)
        for f in _falhas:
            print(f"\n--- {f}", flush=True)
        sys.exit(1)
    print("\nSUITE OK: todos os scripts passaram.", flush=True)