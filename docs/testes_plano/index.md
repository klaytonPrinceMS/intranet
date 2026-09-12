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
- **Ativação** (`test_ativacao.py`, 11/09): assistente de boot — regra padrão SQLite **ignorando a `tb_config`**, `_garantir_sdk_otel`, persistência `otel_ativo`, portas/DSN/faixa, `_compose_cmd`, `_mascarar_comando`, `_validar_senha`, `aplicar_portas` (57 verificações).
- **Blog na Home** (`teste_home_blog.py`, 11/09): feed da página inicial nos modos carrossel/única/histórico via `renderizar_postagens` (3 verificações, headless).
- **Anti-disconnect + segurança do Aplicar** (`test_seg_aplicar.py`, 12/09/2026, delta a1b1650): handlers pesados `async` com `run.io_bound` + trava `ocupado`; path traversal (backup); injeção de rota/DSN mascarado; SMTP `timeout=15` + `io_bound`; `db_mod_*.db` no `.gitignore`.
- **Rodapé + `data-testid`** (`test_rodape_testid.py`, 12/09/2026, delta a1b1650): `rodape_salvar_restaurar` retorna `(restaurar, aplicar)`, Aplicar com `data-testid`, Banco sem reload, docs/SMTP via `io_bound` (UI real headless; `clicar()` aguarda `awaitable`).
- **Tema + trava** (`test_tema_cache_trava.py`, 12/09/2026, delta a1b1650): cache `ler_tema` com invalidação em `salvar_tema`, clamp `notificacao_timeout`, `notificar`, `paleta_escura`, trava `ocupado`.
- **E-mail/docs/observabilidade** (`test_email_docs_obs.py`, 12/09/2026): `enviar_email`/`testar_conexao` com mock SMTP, `documentacao.reconstruir` com mocks (sem mkdocs real), `observabilidade.configurar` em `LOG_DIR` isolado.
- **Backup/rotinas** (`test_rotinas_backup.py`, 12/09/2026, delta a1b1650): checkpoint WAL + `OSError→None` em `backup_modulo`, handlers async, `_podar_backups`/`listar_backups`/`limpar_editor_pdf` (pastas em `/tmp`, sem tocar `backup/`).
- **Papéis do ator** (`test_autenticacao_papeis.py`, 12/09/2026): hash/senha, `papel_no_modulo`/`validar_acesso_modulo`, ciclo conceder→revogar com usuário temporário (LGPD).
- **Paridade SQLite↔PostgreSQL** (`test_banco_conexao.py`, 12/09/2026, AGENTS.md §4): `sgbd_ativo`, `_CursorPostgres._preparar` (traduções), `_ddl_postgres`, `conexao('intranet')` com PRAGMA WAL (só leitura).
- **Cobertura total** (`test_cobertura_total.py`, 12/09/2026): smoke de import + contrato de TODAS as funções/classes dos 64 arquivos `mod_*/` (puras com asserts + guardas anti-disconnect).
- **Drawer / menu hambúrguer** (`verifica_ui_comum.py`, 12/09 + roteiro manual): fábrica `ItemMenuDrawer`/`item_menu_drawer` (`ui_comum.py:852-937`) e drawer (`telas.py:218-332`) — testids `menu-hamburguer/menu-home/menu-<chave>/menu-<chave>-indisponivel/menu-admin/menu-docs/menu-sair` (190/190 OK); matriz manual 3 perfis × 3 larguras em [Testes — Casos](../testes_casos/index.md) (seção "Roteiro manual — drawer × perfis × larguras").

## Drawer / menu hambúrguer — estratégia (pirâmide)

> EN — Drawer test strategy: unit base (`verifica_ui_comum.py`, byte-identical factory props/classes/ARIA, 190/190) + manual/E2E top (profile × width matrix in Test Cases). Selectors always via `get_by_test_id`.

> PT — Estratégia do drawer: base unitária (`verifica_ui_comum.py`, fábrica byte-idêntica em props/classes/ARIA, 190/190) + topo manual/E2E (matriz perfis × larguras nos Casos de Teste). Seletores sempre via `get_by_test_id`.

- **Base (unitário, automático):** `verifica_ui_comum.py` prova props/classes/estilo/tooltip/ARIA da fábrica idênticos à construção crua de referência (stub NiceGUI, sem servidor).
- **Topo (manual/E2E, poucos):** roteiro [manual do drawer](../testes_casos/index.md) (seção "Roteiro manual — drawer × perfis × larguras") — perfis `comum`/`administrador_modulo`/`administrador_geral` × larguras 320/768/1024: drawer abre/fecha via `menu-hamburguer`, 100% largura sem overflow (RNF-UI-01), foco por teclado com anel `focus-visible`, ARIA (`aria-current` no ativo, `aria-hidden` nos ícones, `aria-label` no hambúrguer/indisponível). Regra de visibilidade: `menu-admin`/`menu-docs` só para `administrador_geral`.

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

- `test_suite_standalone()` (`test_suite.py:50`) — percorre `assets/test/*.py` (`_scripts()`, `test_suite.py:44-47`), executa cada script em subprocesso com timeout de 240 s (`subprocess.run([sys.executable, str(p)], ..., timeout=240, env=_env_limpo())`) e falha se `returncode != 0`. Execução direta com progresso: `.venv/bin/python assets/test/test_suite.py` (bloco `__main__` + `_rodar_suite(progresso=True)` — imprime `[N] script ... OK em Xs`, 12/09/2026).
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
