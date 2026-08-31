# Project Plan — Intranet Modular

> Phased implementation checklist (from `PLANO.md`). Mark `[x]` as items are completed to allow resumption after interruption. Versioning: `1.0.AAMMDD`.

---

# Plano de Projeto — Intranet Modular

> Checklist de implementação por fases (de `PLANO.md`). Marcar `[x]` ao concluir para retomada após interrupção. Versionamento: `1.0.AAMMDD`.

## Fases

- **Fase 0 — Scaffold:** pastas, Tailwind local (sem CDN), `requirements.txt`, WAL obrigatório, `main.py`.
- **Fase 1 — mod_intranet (núcleo):** `tb_auditoria`/`tb_config`, login HTTP-Only, seed `master` (troca obrigatória), layout 4 partes, dashboard, personalização, backup 12 h.
- **Fase 2 — mod_gest_cad_usuario:** soft CRUD, perfis por módulo, senha provisória, auditoria.
- **Fase 2.5 — Testes de fluxo:** boot, autenticação (19/19), permissões (13/13).
- **Fase 3 — mod_blog:** CRUD, sanitização `nh3`, auditoria (33/33).
- **Fase 4 — mod_renomear_empenho:** monitor/extração/FTS5, quarentena, renomeação, organizador, edição (31/31, 16/16, 18/18).
- **Fase 5 — mod_edit_pdf:** cotas, expiração 10 min, operações, auditoria SHA-256.
- **Fase 6 — mod_auditoria:** leitura/filtro `tb_auditoria`, acesso geral.
- **Fase 7 — mod_solicita_impressao:** ✅ CONCLUÍDO (upload/rascunho, fórmula, cotas, autorização, marca d'água, auditoria; `1.0.260829`).
- **Fase 8 — Observabilidade (loguru):** ✅ CONCLUÍDO.
- **Fase 9 — Backlog (`analise.md`):** 45 realizados · 12 parcial · 3 pendentes.

## Status da Documentação

Todos os 7 módulos possuem análise em `docs/`; `analise_mod_solicita_impressao.md` reflete o novo fluxo. Observabilidade em andamento.

Veja [Registro de Mudanças](../registro_de_mudancas/index.md) e [Versionamento](../versionamento/index.md).
