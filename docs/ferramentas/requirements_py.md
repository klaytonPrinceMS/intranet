# requirements.py — Instalação Complementar de Dependências (dev-only)

> EN: Complementary dependency installer script not managed by `requirements.txt` — Playwright and security devtools. Dev/test-only; never used in production.
> PT-BR: Script de instalação complementar de dependências não gerenciadas pelo `requirements.txt` — Playwright e ferramentas de segurança de desenvolvimento. Apenas para modo de desenvolvimento/testes; nunca usado em produção.

> `requirements.py` padroniza instalações extras que o `requirements.txt` não gerencia:
> - **Playwright** (com detecção de SO: Windows vs Linux) + Chromium
> - **Ferramentas de DevOps/segurança** (gitleaks, bandit, semgrep, pip-audit, safety, k6)
>
> Fonte das dependências de produção: `requirements.txt`. Fonte das dependências dev: `requirements-dev.txt` e `requirements.py`.

## 1. Para que serve

`requirements.py` é um **script complementar de instalação** que cobre dependências que o `requirements.txt` (produção) e o `requirements-dev.txt` (dev) não gerenciam automaticamente:

| Dependência | Módulo | Finalidade |
|:---|:---|:---|
| `playwright` | `--playwright` | Testes E2E headless (navegador automatizado) |
| `chromium` | `--playwright` | Browser alvo do Playwright |
| `bandit` | `--devtools` | SAST Python (análise estática de segurança) |
| `semgrep` | `--devtools` | SAST multi-regra |
| `pip-audit` | `--devtools` | Auditoria de CVEs em dependências |
| `safety` | `--devtools` | Verificação de CVEs conhecidas |
| `gitleaks` | `--devtools` | Varredura de segredos no histórico git |
| `k6` | `--devtools` | Teste de carga/performance |

**Regra de ouro:** `requirements.py` **NUNCA** entra em produção. É usado exclusivamente no ambiente de desenvolvimento e testes da equipe.

## 2. Quando usar

| Cenário | Comando |
|:---|:---|
| **Primeira instalação do ambiente dev** (tudo) | `.venv/bin/python requirements.py` |
| **Só Playwright + Chromium** | `.venv/bin/python requirements.py --playwright` |
| **Só ferramentas de segurança** | `.venv/bin/python requirements.py --devtools` |

> **Diferença entre `requirements.txt` e `requirements.py`:**
> - `requirements.txt` → dependências de **produção** (`pip install -r requirements.txt`). Usado pelo sistema em runtime. Inclui `nicegui`, `sqlalchemy`, `psycopg2-binary`, etc.
> - `requirements.py` → dependências de **desenvolvimento/testes**. Executado manualmente pela equipe. NUNCA usado em produção nem no deploy.

## 3. Como executar

Pré-requisito: `.venv/` do projeto criado (ver `manual_de_uso_instalacao/index.md`).

### 3.1 Instalação completa (tudo)

```bash
.venv/bin/python requirements.py
```

Executa `install_playwright()` + `install_devtools()` — instala Playwright, Chromium e todas as ferramentas de segurança.

### 3.2 Só Playwright

```bash
.venv/bin/python requirements.py --playwright
```

Instala apenas `playwright` + navegador. Antes de baixar o Chromium (~150MB), verifica o **Chrome do sistema** com `channel="chrome"` — se funcionar, o download é dispensado (essencial em links lentos, onde o timeout de 30s do Playwright estoura). Útil quando o navegador precisa ser reinstalado ou atualizado. Flag `--force-chromium` força o download mesmo com Chrome OK.

### 3.3 Só ferramentas de segurança (DevTools)

```bash
.venv/bin/python requirements.py --devtools
```

Instala via pip `bandit`, `semgrep`, `pip-audit` e `safety`, e via winget (Windows) os binários externos `gitleaks` e `k6` (não existem no PyPI — são binários Go). Útil para configurar o ambiente de QA/DevSecOps.

## 4. Detecção de SO (Windows vs Linux)

O script detecta automaticamente o sistema operacional via `platform.system()` e adapta o comportamento:

```python
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX   = platform.system() == "Linux"
```

| Plataforma | Playwright | Chromium | DevTools extras |
|:---|:---|:---|:---|
| **Windows** | `playwright install chromium` (download automático) | Download automático via Playwright | `winget install gitleaks.Gitleaks` (fallback: `go install`) |
| **Linux** | Dependências de sistema (`apt`) + `playwright install chromium` | Requer libs do sistema antes do download | Instalação via pip apenas |

### 4.1 No Windows

- O Playwright baixa o Chromium automaticamente.
- Se o download falhar (proxy/firewall), o script exibe o comando manual:
  ```bash
  .venv/bin/playwright install chromium
  ```
- O `gitleaks` é instalado via `winget` (fallback: `go install github.com/gitleaks/gitleaks@latest`).

### 4.2 No Linux

- Dependências de sistema necessárias antes do Playwright:
  ```bash
  sudo apt-get install -y curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libxshmfence1
  ```
- Após instalar as dependências, o script executa `playwright install chromium`.
- Se o download falhar, verificar proxy/firewall.

## 5. Estrutura do script

```
requirements.py
├── main()                     # Entrada: parseia --playwright / --devtools
├── install_playwright()       # Playwright + Chromium (detecção de SO)
├── install_devtools()         # Ferramentas de segurança (bandit, semgrep, ...)
├── pip_install(packages, desc)  # Helper: instala pacotes via pip
└── IS_WINDOWS / IS_LINUX      # Detecção de SO via platform.system()
```

## 6. Fluxo de execução

```
.venv/bin/python requirements.py [--playwright | --devtools]
│
├── Sem flags       → install_playwright() + install_devtools()
├── --playwright    → install_playwright() apenas
└── --devtools      → install_devtools() apenas
```

Cada função:
1. Imprime cabeçalho identificando o bloco (PLAYWRIGHT / DEVTOOLS).
2. Executa `pip_install()` com os pacotes necessários.
3. No Windows: tenta `winget install gitleaks`.
4. No Linux: exibe comandos `apt-get` e executa `playwright install chromium`.
5. Em caso de falha no download do Chromium: avisa e exibe comando manual de retry.

## 7. Troubleshooting

| Sintoma | Causa provável | Correção |
|:---|:---|:---|
| `playwright install chromium` falha | Proxy/firewall bloqueando download | Verificar proxy; executar manualmente quando a rede liberar |
| `gitleaks` não encontrado no Windows | `winget` indisponível | Usar `go install github.com/gitleaks/gitleaks@latest` |
| Dependências de sistema faltando (Linux) | libs do Playwright não instaladas | Executar o `sudo apt-get install` listado na saída do script |
| `ModuleNotFoundError: No module named 'playwright'` | Playwright não instalado no `.venv` | Rodar `.venv/bin/python requirements.py --playwright` |
| Venv não encontrado | `.venv/bin/python` não existe | O script auto-detecta e usa `sys.executable` como fallback |

## 8. Regras e boas práticas

- **NUNCA** adicione dependências do `requirements.py` ao `requirements.txt` — isso polui o ambiente de produção.
- **SEMPRE** use `.venv/bin/python requirements.py` (nunca `python` cru).
- **NÃO** execute `requirements.py` no servidor de produção — é script dev-only.
- Após instalar com `--playwright`, valide com:
  ```bash
  .venv/bin/playwright --version
  ```
- Após instalar com `--devtools`, valide com:
  ```bash
  .venv/bin/bandit --version
  .venv/bin/semgrep --version
  ```

> Veja também [Ferramentas de Segurança](../seguranca/ferramentas_de_seguranca.md), [Graphify (dev-only)](graphify.md) e [Manual de Instalação](../manual_de_uso_instalacao/index.md).
