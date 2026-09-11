# Test Plan — Intranet Modular

> Test plan by flow, derived from `PLANO.md` (Fases 2.5 a 5). Standalone scripts in `assets/test/*.py`; run the whole suite with `.venv/bin/pytest` (runner `assets/test/test_suite.py`) — see [Execution](#execucao-dos-testes).

---

# Testes — Plano — Intranet Modular

> Plano de testes por fluxo, de `PLANO.md` (Fases 2.5 a 5). Scripts standalone em `assets/test/*.py`; a suíte completa roda com `.venv/bin/pytest` (runner `assets/test/test_suite.py`) — veja [Execução dos testes](#execucao-dos-testes).

## Fluxos cobertos

- **Boot** (`teste_boot.py`): servidor sobe, `/login` com Tailwind local.
- **Autenticação** (`teste_fluxo_autenticacao.py`): login master → senha provisória → troca obrigatória → sessão/logout → auditoria → soft delete (19/19 OK).
- **Permissões** (`teste_fluxo_permissoes.py`): concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (13/13 OK).
- **Blog** (`teste_fluxo_blog.py`): sanitização XSS, conversores, CRUD, soft delete, config local, auditoria central (33/33 OK).
- **Renomeador** (`teste_fluxo_renameador.py`): documento-modelo `DOC_0201.pdf` ponta a ponta (31/31 OK); organizador (16/16); edição embutida (18/18).
- **Editor de PDF** (`test/test_editor_pdf.py`): 20 verificações.
- **Auditoria** (`test/test_auditoria.py`): índices, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral e preferência de campos/ordem por usuário (12 verificações).

## Critérios de entrada/saída

- Bancos `db_mod_*` devem ser (re)criados do zero se ausentes; seed `master`/`master` com `administrador_geral`.
- Nenhuma falha em silêncio: recusas de upload/quota listadas nominalmente.

## Execução dos testes

> EN — How to run the automated suite: the project's tests are **standalone scripts** in `assets/test/*.py` with their own checks/asserts; the mandatory command is `.venv/bin/pytest`, configured by `pytest.ini` (root) to collect **only** the runner `assets/test/test_suite.py`, which executes the whole suite in subprocesses (≈3–5 min) and fails if any script exits non-zero. Run a single script with `.venv/bin/python assets/test/<arquivo>.py`. Playwright E2E: `cd assets/test && npm install && npm run test:e2e`.

> PT — Como executar a suíte automatizada: os testes do projeto são **scripts standalone** em `assets/test/*.py` com checagens/asserts próprios; o comando obrigatório é `.venv/bin/pytest`, configurado pelo `pytest.ini` (raiz) para coletar **apenas** o runner `assets/test/test_suite.py`, que executa toda a suíte em subprocessos (≈3–5 min) e falha se algum script terminar com código ≠ 0. Para um script isolado: `.venv/bin/python assets/test/<arquivo>.py`. E2E Playwright: `cd assets/test && npm install && npm run test:e2e`.

### Suíte completa — `.venv/bin/pytest`

O comando oficial de testes do projeto (AGENTS.md) é `.venv/bin/pytest`. Sem configuração, o pytest tentava **coletar os scripts standalone** de `assets/test/*.py` e quebrava com `INTERNALERROR` (o `sys.exit` no import de `test_dashboard.py` derruba o coletor). O `pytest.ini` na raiz resolve:

```ini
[pytest]
testpaths = assets/test/test_suite.py
addopts = -p no:cacheprovider
```

- `testpaths = assets/test/test_suite.py` (`pytest.ini:2`) — o pytest coleta **apenas** o runner `assets/test/test_suite.py`, que roda TODA a suíte standalone em subprocessos e falha se algum script retornar código ≠ 0. Duração: ≈3–5 min.
- `addopts = -p no:cacheprovider` (`pytest.ini:3`) — desativa o cache do pytest (não cria `.pytest_cache/`).

### Script isolado

Para depurar um fluxo sem rodar a suíte inteira, execute o script diretamente:

```bash
.venv/bin/python assets/test/<arquivo>.py
```

Exemplo: `.venv/bin/python assets/test/teste_fluxo_blog.py`.

### E2E Playwright

```bash
cd assets/test && npm install && npm run test:e2e
```

- Config em `assets/test/playwright.config.js` (`testDir: './e2e'`, `playwright.config.js:24`); o `webServer` inicia/reutiliza o servidor na porta 8080 (`playwright.config.js:44-49`).
- Specs em `assets/test/e2e/*.spec.js` (`01_login`, `02_varredura`, `03_exclusao_blog`).
- Credenciais QA garantidas pelo global setup (`e2e/_global_setup.js` → `_garantir_credenciais.py`): `qacomum`/`qamaster` = `123456`.
- Detalhes: [Testes E2E com Playwright](../testes_playwright.md).

### O que o runner executa e exclui

`assets/test/test_suite.py`:

- `test_suite_standalone()` (`test_suite.py:50`) — percorre `assets/test/*.py` (`_scripts()`, `test_suite.py:44-47`), executa cada script em subprocesso com timeout de 240 s (`subprocess.run([sys.executable, str(p)], ..., timeout=240, env=_env_limpo())`, `test_suite.py:55-56`) e falha se `returncode != 0` (`test_suite.py:60-62`).
- `_env_limpo()` (`test_suite.py:34-41`) — remove as variáveis `PYTEST_*` do ambiente do subprocesso; sem isso, o NiceGUI ativa o modo de teste e exige `NICEGUI_SCREEN_TEST_PORT`.
- **Excluídos** (`EXCLUIR`, `test_suite.py:23-31`) — não entram na suíte automatizada:
  - **Helpers**: `debug_boot.py`, `step_boot.py`, `diag_config.py`, `wtest.py`, `criar_postagens_blog.py` e `test_server.py` (sobe a app na 8080 e bloqueia).
  - **Destrutivos de banco**: `test_fresh_install.py`, `fresh_install_test.py`, `fresh_install_test2.py`.
  - **Dependentes de instalação limpa** (assumem `master`/`master` ainda válidos): `test_fase1_login.py`, `validar_fase1_login.py`.
  - **OTel**: `test_otel.py` (depende da stack Docker/porta).

Motivo: são auxiliares (não são testes de regressão), alteram/destroem o estado dos bancos ou dependem de ambiente específico — incluí-los quebraria a suíte ou geraria falsos negativos.

## Varredura de segurança (DevSecOps)

Toda alteração de código deve passar pela varredura de segurança (subagente
`qa_seguranca`):

| Ferramenta | Comando | Critério de saída |
|:---|:---|:---|
| `bandit` | `bandit -r main.py mod_* -q` | 0 achados High; médios justificados |
| `semgrep` | `semgrep scan --config auto --error ...` | sem vulnerabilidade explorável confirmada |
| `pip-audit` | `pip-audit -r requirements.txt -r requirements-dev.txt` | 0 CVEs conhecidas |
| `gitleaks` | `gitleaks detect --source . --redact` | 0 segredos reais (ignorar falsos positivos de `site/`) |

Ferramentas de segurança de desenvolvimento ficam em `requirements-dev.txt`.
Detalhes de uso e resultados: [Ferramentas de Segurança](../seguranca/ferramentas_de_seguranca.md)
e [Relatório de Segurança (06/09/2026)](../testes_relatorios/seguranca_2026-09-06.md).

Veja [Testes — Casos](../testes_casos/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
