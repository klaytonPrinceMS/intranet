"""Instalação complementar de dependências não-cobertura do requirements.txt.

Este script padroniza instalações extras que o requirements.txt não gerencia:
  - Playwright (com detecção de SO: Windows vs Linux)
  - Chromium para Playwright
  - Ferramentas de DevOps (gitleaks, bandit, semgrep)

Uso:
    .venv/bin/python requirements.py           # instala tudo
    .venv/bin/python requirements.py --playwright  # só playwright
    .venv/bin/python requirements.py --devtools    # só ferramentas de segurança
"""
import sys
import platform
import subprocess
import os

# Força UTF-8 na saída do console (Windows PowerShell usa CP1252
# por padrão e crasha em símbolos como ⚠ ✅ → sem isto).
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable


def pip_install(packages: list[str], desc: str):
    """Instala pacotes via pip."""
    print(f"\n--> {desc}")
    cmd = [VENV_PYTHON, "-m", "pip", "install", "-q"] + packages
    print(f"    {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _chrome_sistema_ok():
    """Testa se o Chrome do sistema funciona com o Playwright.

    Retorna (ok, versao_ou_erro). Evita o download do Chromium
    (~150MB) quando o Chrome já está instalado — útil em links
    lentos onde o timeout de 30s do Playwright sempre estoura.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            versao = b.version
            b.close()
            return True, versao
    except Exception as e:
        return False, str(e)[:120]


def install_playwright(forcar_chromium=False):
    """Instala Playwright + Chromium com detecção de SO."""
    print("\n" + "=" * 60)
    print("  PLAYWRIGHT — Detecção de SO: Windows" if IS_WINDOWS else "  PLAYWRIGHT — Detecção de SO: Linux")
    print("=" * 60)

    pip_install(["playwright"], "Instalando playwright...")

    if not forcar_chromium:
        print("\n  Verificando Chrome do sistema (evita download ~150MB)...")
        ok, info = _chrome_sistema_ok()
        if ok:
            print(f"  ✅ Chrome do sistema OK (versão {info}).")
            print("  Use channel='chrome' nos testes — Chromium dispensado.")
            print("  (Para forçar o Chromium: python requirements.py --playwright --force-chromium)")
            print("\n  ✅ Playwright instalado com sucesso!")
            return
        print(f"  Chrome do sistema indisponível ({info}) — baixando Chromium...")

    if IS_WINDOWS:
        # No Windows, o playwright baixa o Chromium automaticamente.
        # Em rede corporativa com proxy, exporte HTTP_PROXY/HTTPS_PROXY
        # antes de rodar este script.
        print("\n  [Windows] Instalando Chromium via Playwright...")
        print("  (Se o download falhar por timeout, causas comuns:")
        print("   proxy/firewall corporativo, CDN cdn.playwright.dev bloqueada.)")
        print("   Tente: set HTTPS_PROXY=http://proxy:porta antes de rodar,")
        print("   ou execute manualmente quando a rede liberar:")
        print("   .venv\\Scripts\\playwright install chromium)")
        try:
            subprocess.run([VENV_PYTHON, "-m", "playwright", "install", "chromium"], check=True)
        except subprocess.CalledProcessError:
            print("  ⚠ Chromium download falhou — verifique proxy/firewall.")
            print("  Execute manualmente quando a rede liberar:")
            print(f"  {VENV_PYTHON} -m playwright install chromium")
    elif IS_LINUX:
        # No Linux, dependências do sistema são necessárias
        print("\n  [Linux] Instalando dependências do sistema + Chromium...")
        deps = [
            "curl", "gnupg", "libnss3", "libatk1.0-0", "libatk-bridge2.0-0",
            "libcups2", "libdrm2", "libxkbcommon0", "libxcomposite1",
            "libxdamage1", "libxrandr2", "libgbm1", "libpango-1.0-0",
            "libcairo2", "libasound2", "libatspi2.0-0", "libxshmfence1",
        ]
        print(f"  Dependências apt: {' '.join(deps)}")
        print("  Execute: sudo apt-get install -y " + " ".join(deps))
        try:
            subprocess.run([VENV_PYTHON, "-m", "playwright", "install", "chromium"], check=True)
        except subprocess.CalledProcessError:
            print("  ⚠ Chromium download falhou — verifique proxy/firewall.")

    print("\n  ✅ Playwright instalado com sucesso!")


def install_devtools():
    """Instala ferramentas de segurança e DevOps.

    Pacotes pip (Python): bandit, semgrep, pip-audit, safety.
    Binários externos (NÃO estão no PyPI): gitleaks e k6 são
    instalados via winget (Windows) ou gerenciador do SO (Linux).
    """
    print("\n" + "=" * 60)
    print("  DEVTOOLS — Ferramentas de segurança e DevOps")
    print("=" * 60)

    # Apenas pacotes que existem no PyPI — gitleaks e k6 NÃO são
    # pacotes Python (são binários Go) e quebram o pip install.
    tools = [
        "bandit>=1.9.4",
        "semgrep>=1.176.1",
        "pip-audit>=2.10.1",
        "safety>=3.8.1",
    ]
    pip_install(tools, "Instalando ferramentas Python de segurança...")

    _instalar_binarios_externos()

    print("\n  ✅ DevTools instalados com sucesso!")


def _instalar_binarios_externos():
    """Instala gitleaks e k6 (binários Go, fora do PyPI)."""
    if IS_WINDOWS:
        print("\n  [Windows] Instalando binários externos via winget...")
        for pkg_id, nome in (("Gitleaks.Gitleaks", "gitleaks"),
                             ("GrafanaLabs.k6", "k6")):
            try:
                # --source winget explícito (fonte ambígua msstore vs
                # winget causa 0x8A150014). SEM -e: o exact-match quebra
                # o install nesta versão do winget mesmo com --id.
                r = subprocess.run(
                    ["winget", "install", "--id", pkg_id,
                     "--source", "winget",
                     "--accept-source-agreements", "--accept-package-agreements"],
                    capture_output=True, text=True, timeout=180,
                )
                if r.returncode == 0:
                    print(f"  ✅ {nome} instalado via winget.")
                else:
                    print(f"  ⚠ winget falhou para {nome} (código {r.returncode}).")
                    _alternativas_binario(nome)
            except FileNotFoundError:
                print("  ⚠ winget não encontrado no PATH.")
                _alternativas_binario(nome)
                break
            except subprocess.TimeoutExpired:
                print(f"  ⚠ winget timeout para {nome}.")
                _alternativas_binario(nome)
    elif IS_LINUX:
        print("\n  [Linux] Binários externos (gitleaks, k6) — instale via:")
        print("    # gitleaks:")
        print("    curl -sSfL https://raw.githubusercontent.com/gitleaks/gitleaks/master/scripts/install.sh | sh -s -- -b /usr/local/bin")
        print("    # k6:")
        print("    sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E34138")
        print("    echo 'deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list")
        print("    sudo apt-get update && sudo apt-get install -y k6")


def _alternativas_binario(nome):
    """Imprime alternativas manuais quando o winget falha."""
    if nome == "gitleaks":
        print("    Alternativas gitleaks:")
        print("      go install github.com/gitleaks/gitleaks/v8@latest")
        print("      ou baixe em: https://github.com/gitleaks/gitleaks/releases")
    elif nome == "k6":
        print("    Alternativas k6:")
        print("      choco install k6   (se Chocolatey instalado)")
        print("      ou baixe em: https://github.com/grafana/k6/releases")


def _caminho_chromium_playwright():
    """Devolve o caminho exato onde o Playwright espera o chrome.exe."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return p.chromium.executable_path
    except Exception:
        base = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright")
        return os.path.join(base, "chromium-1243", "chrome-win", "chrome.exe")


def abrir_downloads():
    """Abre o navegador nos links de download manual + instruções.

    Para links lentos onde todo download automatizado (playwright,
    winget, curl) estoura timeout: o navegador faz o download com
    resume e o usuário extrai manualmente nas pastas indicadas.
    """
    import webbrowser

    print("\n" + "=" * 60)
    print("  DOWNLOADS MANUAIS — abrindo o navegador...")
    print("=" * 60)

    exe_chromium = _caminho_chromium_playwright()
    pasta_chromium = os.path.dirname(exe_chromium)

    links = [
        ("Chromium (chrome-win64.zip ~150MB)",
         "https://storage.googleapis.com/chrome-for-testing-public/153.0.8010.12/win64/chrome-win64.zip"),
        ("gitleaks (releases — arquivo windows_x64.zip)",
         "https://github.com/gitleaks/gitleaks/releases"),
        ("k6 (releases — arquivo windows-amd64.zip)",
         "https://github.com/grafana/k6/releases"),
    ]
    for nome, url in links:
        print(f"\n  Abrindo: {nome}\n    {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"  ⚠ Não foi possível abrir o navegador: {e}")

    print("\n" + "-" * 60)
    print("  O QUE FAZER COM CADA DOWNLOAD:")
    print("-" * 60)
    print(f"""
  1) Chromium — extrair o chrome-win64.zip DIRETAMENTE em:
       {os.path.dirname(pasta_chromium)}
     (o zip já contém a pasta 'chrome-win64' no nome esperado).
     Resultado final esperado:
       {exe_chromium}
     Depois valide com:
       .venv\\Scripts\\python -m playwright install chromium
     (detecta o existente e pula o download)

  2) gitleaks — extrair o .zip e copiar gitleaks.exe para uma
     pasta no PATH, ex.: C:\\Windows\\System32 ou
     C:\\opencode\\.venv\\Scripts\\

  3) k6 — extrair o .zip e copiar k6.exe para a mesma pasta
     do item 2.
""")


def main():
    print(f"Python: {sys.version}")
    print(f"SO: {platform.system()} {platform.release()}")
    print(f"Arquitetura: {platform.machine()}")

    import argparse
    parser = argparse.ArgumentParser(description="Instalação complementar de dependências")
    parser.add_argument("--playwright", action="store_true", help="Só instala Playwright + Chromium")
    parser.add_argument("--devtools", action="store_true", help="Só instala ferramentas de segurança")
    parser.add_argument("--force-chromium", action="store_true",
                        help="Força o download do Chromium mesmo com Chrome do sistema OK")
    parser.add_argument("--abrir-downloads", action="store_true",
                        help="Abre o navegador nos links de download manual (chromium, gitleaks, k6)")
    args = parser.parse_args()

    if args.abrir_downloads:
        abrir_downloads()
        return

    if args.playwright:
        install_playwright(forcar_chromium=args.force_chromium)
    elif args.devtools:
        install_devtools()
    else:
        install_playwright(forcar_chromium=args.force_chromium)
        install_devtools()

    print("\n" + "=" * 60)
    print("  Instalação completa!")
    print("=" * 60)


if __name__ == "__main__":
    main()
