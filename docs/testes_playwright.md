# Testes E2E com Playwright

> E2E tests with Playwright (Node) against the NiceGUI app: automated login with the QA users (`qacomum`/`qamaster`) and a route scan that captures console errors, page errors, failed requests and HTTP 4xx/5xx to identify system problems. This page covers installation and how to repeat the tests.

---

# Testes E2E com Playwright

> Testes ponta-a-ponta com Playwright (Node) contra o app NiceGUI: login automatizado com os usuários QA (`qacomum`/`qamaster`) e varredura de rotas que captura erros de console, erros de página, requisições falhas e HTTP 4xx/5xx para identificar problemas no sistema. Esta página cobre a instalação e como repetir os testes.

## O que é

O **Playwright** é um framework de automação de navegador que executa o sistema real (servidor + navegador) e valida comportamento e a ausência de erros. Aqui ele roda em **headless Chromium** contra o app em `http://localhost:8080`, usando os **usuários QA** já semeados:

| Usuário | Senha | Perfil | Acesso |
|---|---|---|---|
| `qacomum` | `123456` | `comum` | blog, editar_pdf, empenhos |
| `qamaster` | `123456` | `administrador_geral` | todos + Administração |

> As credenciais acima são **garantidas a cada execução** pelo *global setup* (`test/e2e/_global_setup.js` → `_garantir_credenciais.py`): redefine a senha, o perfil e limpa a flag de troca obrigatória — mesmo que a senha tenha sido alterada em uso real.

## O que os testes cobrem

- **`test/e2e/01_login.spec.js`** — login com `qacomum` (comum) e `qamaster` (admin); verifica que o dashboard abre sem erros fatais e que usuário comum é **barrado** em `/configuracoes` e em `/admin/auditoria`.
- **`test/e2e/02_varredura.spec.js`** — como `qamaster`, visita as principais rotas (páginas, módulos e painéis `/admin/*`) e **coleta erros** de console, `pageerror`, requisições falhas e respostas HTTP ≥ 400, listando-os no terminal e falhando apenas se houver erros fatais.

Os testes capturam e reportam erros para facilitar a identificação de problemas (seletores estáveis via `data-testid`: hambúrguer `menu-hamburguer`, itens `menu-home`/`menu-<chave>`/`menu-admin`/`menu-docs`/`menu-sair` — fábrica `ui_comum.item_menu_drawer`, 12/09/2026; em testes headless Python, `clicar()` deve aguardar handlers `async` via `inspect.isawaitable` — padrão `teste_aba_config_intranet.py`/AGENTS.md §5.1):

```text
=== ERROS COLETADOS (N) ===
 [http] 404 http://localhost:8080/algum/asset.jpg
 [pageerror] ReferenceError: x is not defined
 [requestfailed] https://cdn.exemplo.com/lib.js net::ERR_NAME_NOT_RESOLVED
```

## Pré-requisitos

- **Node.js + npm** (para o Playwright em JS).
- O **venv Python** do projeto já criado (`.venv/`) — o servidor é iniciado com ele.
- Navegador Chromium do Playwright (instalar uma vez — ver abaixo).

## Instalação

1. **Instalar as dependências npm** (a partir da raiz do projeto):

   ```bash
   npm install
   ```

   Isso instala `@playwright/test` (já listado em `package.json`).

2. **Baixar o navegador Chromium** (uma única vez; ~115 MB em `~/.cache/ms-playwright`):

   ```bash
   npm run test:e2e:install
   # ou: npx playwright install chromium
   ```

## Como repetir os testes (execução)

Com o `.venv` existente e o Chromium baixado:

```bash
# Suíte completa (inicia o servidor na porta 8080 se não estiver de pé,
# ou reutiliza um servidor já ativo):
npm run test:e2e

# Com navegador visível (debug visual):
npm run test:e2e:headed

# Apenas um arquivo/rota:
npx playwright test --config test/playwright.config.js test/e2e/01_login.spec.js

# Relatório HTML da última execução:
npm run test:e2e:report
```

O `webServer` do config (`test/playwright.config.js`) **inicia** `python main.py` na porta 8080 caso não haja servidor ativo (`reuseExistingServer: true`).

## Saída e evidências

- **Terminal**: lista cada teste e imprime os erros coletados na varredura.
- **`playwright-report/`**: relatório HTML interativo da execução.
- **`test-results/`**: evidências (screenshot/vídeo/trace) **somente em falha**.
- Exit code ≠ 0 quando há falha (útil para CI).

## Versionamento (git)

Os **binários e artefatos** do Playwright **não** são versionados (`.gitignore`):

```gitignore
node_modules/
test-results/
playwright-report/
```

Subir apenas os arquivos usados nos testes:

```text
test/playwright.config.js
test/e2e/_global_setup.js
test/e2e/_garantir_credenciais.py
test/e2e/helpers.js
test/e2e/01_login.spec.js
test/e2e/02_varredura.spec.js
package.json        (scripts test:e2e*)
package-lock.json
```

## Solução de problemas

- **Porta ocupada**: se `http://localhost:8080` já responde, o Playwright reutiliza o servidor existente (não inicia outro).
- **Navegador ausente**: rode `npm run test:e2e:install`.
- **Login falhando**: rode o global setup manualmente:

  ```bash
  .venv/bin/python test/e2e/_garantir_credenciais.py
  ```

- **Erros falsos de console**: mensagens de ruído conhecidas (favicon, ResizeObserver, Vue Devtools) são ignoradas pela captura (`helpers.js`).