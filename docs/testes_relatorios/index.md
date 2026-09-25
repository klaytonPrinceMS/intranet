# Test Reports — Intranet Modular

> Test execution reports. Seed document aggregating the pass/fail counts declared in `PLANO.md` and `test/`.

---

# Testes — Relatórios — Intranet Modular

> Relatórios de execução de testes. Documento-semente agregando as contagens de sucesso/falha declaradas em `PLANO.md` e `test/`.

## Última execução conhecida (seed)

| Fluxo | Resultado |
|:---|:---|
| Autenticação | 19/19 OK |
| Permissões | 13/13 OK |
| Blog | 33/33 OK |
| Renomeador (modelo) | 31/31 OK |
| Renomeador (organizador) | 16/16 OK |
| Renomeador (edição) | 18/18 OK |
| Editor de PDF | 20 verificações |
| `ui_comum` + drawer (12/09/2026) | `assets/test/verifica_ui_comum.py` — **190/190 OK** (fábrica `ItemMenuDrawer`/`item_menu_drawer` + drawer `menu-hamburguer/menu-home/menu-<chave>/menu-<chave>-indisponivel/menu-admin/menu-docs/menu-sair`, ARIA e `campo_modulo`; sem commit — validado via `.venv/bin/python assets/test/verifica_ui_comum.py`) |
| Segurança (DevSecOps) | [Relatório de Segurança (06/09/2026)](seguranca_2026-09-06.md) — bandit 0 High/24 Medium/86 Low, semgrep 31, pip-audit sem CVEs, gitleaks 1 segredo real |
| **QA de execução (25/09/2026)** | [Relatório de QA de Execução (25/09/2026)](qa_execucao_2026-09-25.md) — suíte de **60 scripts saiu de 10 falhando para 0** (`pytest` `exit=0`); smoke Playwright 25 rotas 0 erros; `check_integridade.py` **13/13**; `mkdocs --strict` **0 warnings**; `bandit` HIGH 0 / MEDIUM 0; `gitleaks` no leaks. Commit `624c9d5` |

## Sugestão de expansão

Registrar data/hora, ambiente (OS/Python), responsável e evidências (logs) por execução; vincular a [Registro de Mudanças](../registro_de_mudancas/index.md).

Veja [Testes — Casos](../testes_casos/index.md) e [Métricas de Software](../metricas_software/index.md).
