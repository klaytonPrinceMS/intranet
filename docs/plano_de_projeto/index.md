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
- **Fase 4 — mod_renomear_empenho:** ✅ CONCLUÍDO — monitor multi-pasta, extração 48 campos (40+), FTS 59 cols, quarentena individual+em lote sem reiniciar (`promover_quarentena`/`reprocessar_fila`, botão "Reprocessar fila", separação de múltiplos documentos), organizador físico com `capa.pdf/txt` + `matrizDeDocumentos.pdf/.txt` (31/31, 16/16, 18/18 + 46 Blog).
- **Fase 5 — mod_edit_pdf:** ✅ CONCLUÍDO — cotas, expiração 10 min, operações, auditoria SHA-256.
- **Fase 6 — mod_auditoria:** ✅ CONCLUÍDO — leitura/filtro `tb_auditoria`, acesso geral.
- **Fase 7 — mod_solicita_impressao:** ✅ CONCLUÍDO (upload/rascunho, fórmula, cotas, autorização, marca d'água, auditoria; `1.0.260908`).
- **Fase 8 — Observabilidade (loguru):** ✅ CONCLUÍDO.
- **Fase 9 — Backlog (`analise.md`):** ✅ CONCLUÍDO — todos os itens realizados e documentados, removidos de `analise.md` (roadmap histórico).

## Status da Documentação

Todos os 7 módulos possuem análise em `docs/`; `analise_mod_renomear_empenho.md` (4b/4c com `capa.pdf` + `reprocessar_fila` em lote) e `plano_de_projeto` refletem o plano concluído.

Veja [Registro de Mudanças](../registro_de_mudancas/index.md) e [Versionamento](../versionamento/index.md).
