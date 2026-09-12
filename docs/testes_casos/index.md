# Test Cases — Intranet Modular

> Test cases and scripts available under `test/`. Manual scripts executed with the venv Python (no framework).

---

# Testes — Casos — Intranet Modular

> Casos de teste e scripts disponíveis em `test/`. Scripts manuais executados com o Python do venv (sem framework).

## Scripts disponíveis

| Script | Escopo |
|:---|:---|
| `test_server.py` | Smoke test do servidor (sobe e valida) |
| `test/teste_aba_config_intranet.py` | Aba Config de `/configuracoes` campo a campo (render headless da tela real: ativação/habilitação/editabilidade — BASE_DIR readonly, valores iniciais do `tb_config`, APLICAR sem editar com anti-zeramento + reconfiguração de observabilidade + reagendamento de backups + reload, edição dos 19 campos → chaves corretas, saneamento 0/-3/99/"abc"/"gigante"/cor vazia, "Restaurar padrão" dos 4 cards + páginas nativas da aba Módulo, upload de favicon (.ico aplica; .png e vazio recusados) e acesso restrito a não-admin; autocontido — snapshot/restore de `tb_config`, favicon e `tb_modulos`) |
| `test_auditoria.py` | Auditoria (12 verificações: banco exclusivo `db_mod_auditoria.db`/tabela por módulo, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral, preferência de campos/ordem por usuário) |
| `test_editor_pdf.py` | Editor PDF ponta a ponta (32 verificações: hash SHA-256, redução, união, corte, divisão, cotas, auditoria, expiração) |
| `test_solicita_impressao.py` | Solicitação de impressão (fórmula, cadastros, fluxo, cota, marca d'água, rascunho/expiração) |
| `test_fase1_login.py` / `validar_fase1_login.py` | Login (fase 1) |
| `test_fresh_install.py` / `fresh_install_test2.py` | Boot/seed (move os `.db` reais temporariamente — não interromper) |
| `diag_db.py` / `diag_config.py` | Diagnóstico de banco/config |
| `step_boot.py` / `debug_boot.py` / `wtest.py` | Auxiliares de boot/depuração |

## Catálogo `data-testid` — drawer / menu hambúrguer

> EN — Drawer `data-testid` catalog (all set via `.props('data-testid=...')` in `mod_intranet/ui_comum.py:852-937` factory `ItemMenuDrawer`/`item_menu_drawer` and `mod_intranet/telas.py:218-332`): use these selectors in Playwright/pytest-playwright (`page.get_by_test_id(...)`), never CSS/XPath.

> PT — Catálogo de `data-testid` do drawer (todos aplicados via `.props('data-testid=...')` na fábrica `ItemMenuDrawer`/`item_menu_drawer` em `mod_intranet/ui_comum.py:852-937` e no drawer em `mod_intranet/telas.py:218-332`): use estes seletores no Playwright/pytest-playwright (`page.get_by_test_id(...)`), nunca CSS/XPath.

| `data-testid` | Onde | Quem vê | Ação |
|:---|:---|:---|:---|
| `menu-hamburguer` | Header (`telas.py:216-220`, `botao_icone "menu"`) — `aria-label="Abrir menu de navegação"` | todos os perfis logados | alterna (`toggle`) o `ui.left_drawer` (inicia fechado, `value=False`) |
| `menu-home` | Drawer (`telas.py:255-261`), fábrica com `ativo=(not chave_modulo)` | todos | navega para `/` |
| `menu-<chave>` | Drawer (`telas.py:266-272`), um por módulo ATIVO de `autenticacao.modulos_do_usuario()` (ex. `menu-blog`, `menu-usuarios`) — `aria-current="page"` quando `ativo` | só quem tem vínculo válido (`validar_acesso_modulo`) | navega para a rota do módulo |
| `menu-<chave>-indisponivel` | Drawer (`telas.py:274-287`), módulo com vínculo remanescente mas DESATIVADO — `aria-label="<nome> — módulo indisponível"`, visual laranja `bg-orange-2 border-orange-6` | só quem mantém o vínculo | só `notificar()` warning — NÃO navega |
| `menu-admin` | Drawer (`telas.py:299-306`), rótulo `Administração` (ou `Administração (sistema)` na Home) | só `administrador_geral` (`perfil_global_de() == "administrador_geral"`) — `comum` e `administrador_modulo` NÃO veem | navega para `/admin/<chave>` (ou `/configuracoes` na Home) |
| `menu-docs` | Drawer (`telas.py:309-316`), rótulo `Documentação` | só `administrador_geral` | abre `/documentacao` em nova aba |
| `menu-sair` | Drawer (`telas.py:319-324`), rótulo `Sair` | todos | `_logout` (encerra sessão) |

Notas de acessibilidade da fábrica (`ui_comum.py:883-918`): `ui.item` `w-full rounded-lg my-0.5` + `.style('min-width: 0')`, seção avatar com ícone `text-primary shrink-0` + `aria-hidden="true"`, rótulo `truncate max-w-full grow`, tooltip PT-BR, anel `focus-visible:ring-2`, estado ativo `bg-blue-100 font-bold` + `aria-current="page"`; item só-ícone (rótulo vazio) recebe `aria-label`. Falha de montagem = fail-soft (`None` + log exception).

## Roteiro manual — drawer × perfis × larguras

> EN — Manual drawer checklist: 3 profiles × 3 widths (320/768/1024). Drawer starts closed, opens/closes via `menu-hamburguer`, is full-width without overflow, every visible item is keyboard-focusable with a visible ring, and ARIA states hold.

> PT — Roteiro manual do drawer: 3 perfis × 3 larguras (320/768/1024). Drawer inicia fechado, abre/fecha via `menu-hamburguer`, ocupa 100% da largura sem overflow, todo item visível recebe foco por teclado com anel visível, e os estados ARIA se mantêm.

Pré-condição: logar com cada perfil (`comum` = usuário sem admin; `administrador_modulo` = `administrador` em ≥1 módulo via gestão de usuários, sem ser geral; `administrador_geral` = `master`). Repetir cada passo em 320 px (mobile), 768 px (tablet) e 1024 px (desktop) — DevTools responsivo.

| # | Passo | Esperado |
|:---|:---|:---|
| M1 | Drawer inicia FECHADO ao abrir qualquer tela | nenhum item `menu-*` visível até clicar em `menu-hamburguer` |
| M2 | Clicar `menu-hamburguer` → clicar de novo | abre na 1ª, fecha na 2ª; foco permanece operável por teclado |
| M3 | Largura 100% (RNF-UI-01) em 320/768/1024 | drawer e itens sem overflow horizontal, sem colapso flex (`w-full` + `min-width: 0`, sem `gap-*` em `ui.row()`) |
| M4 | Teclado: `Tab` até o drawer | todos os itens visíveis recebem foco na ordem, anel `focus-visible` visível em cada um |
| M5 | ARIA: item da tela atual | tem `aria-current="page"`; ícones têm `aria-hidden="true"`; hambúrguer tem `aria-label="Abrir menu de navegação"`; só-ícone/indisponível têm `aria-label` próprio |
| M6 | `comum`: só `menu-home` + `menu-<chave>` dos módulos liberados + `menu-sair` | SEM `menu-admin`, SEM `menu-docs` |
| M7 | `administrador_modulo`: idem M6 (módulos do vínculo + `menu-sair`) | SEM `menu-admin`, SEM `menu-docs` (admin de módulo NÃO abre menu de sistema) |
| M8 | `administrador_geral`: M6 + `menu-admin` + `menu-docs` | `menu-admin` → `/admin/<chave>` (ou `/configuracoes` na Home); `menu-docs` → `/documentacao` nova aba |
| M9 | `menu-<chave>-indisponivel` (se houver módulo desativado com vínculo) | clica → `notify` warning laranja, permanece na tela (não navega) |

Automação correspondente (pirâmide): base unitária em `assets/test/verifica_ui_comum.py` (fábrica byte-a-byte, 190/190) → topo manual/E2E com este roteiro via `page.get_by_test_id(...)`.

## Como executar

```bash
.venv/bin/python test/test_server.py
.venv/bin/python test/test_auditoria.py
.venv/bin/python test/test_editor_pdf.py
.venv/bin/python test/teste_aba_config_intranet.py
.venv/bin/python assets/test/verifica_ui_comum.py
```

Veja [Testes — Plano](../testes_plano/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
