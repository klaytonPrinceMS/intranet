# Requirements Elicitation — Intranet Modular

> Functional and non-functional requirements extracted from `analise.md` and `PLANO.md`. This is the engineering baseline for the Intranet Modular system.

---

# Levantamento de Requisitos — Intranet Modular

> Requisitos funcionais e não funcionais extraídos de `analise.md` e `PLANO.md`. Esta é a base de engenharia do sistema Intranet Modular.

## Requisitos funcionais centrais (resumo)

- **RF-001** Parametrização flexível do padrão de monitoramento (Configurações).
- **Gestão de Usuários** (soft CRUD): criar, alterar, bloquear, desbloquear, soft delete, perfis por módulo (`administrador_geral`, `administrador do módulo`, `comum`), senha provisória com troca obrigatória, nome social (Decreto 8.727/2016), exclusão em dois estágios (LGPD).
- **Intranet (núcleo):** trilha de auditoria LGPD (banco exclusivo `db_mod_auditoria.db`, uma tabela por módulo), login por cookie `HTTP-Only`, sessões revogáveis, layout de 4 partes, personalização (cor primária), edição de perfil.
- **Blog:** CRUD com soft delete, sanitização `nh3` (XSS), leitura somente para `comum`, escrita restrita a admin.
- **Edição de PDF:** cotas (10 GB global / 1 GB por usuário), expiração em 10 min, reduzir/juntar/cortar/dividir/verificar/ZIP/excluir, auditoria com hash SHA-256.
- **Renomeador de Empenho:** monitor de pastas, extração com fallback (`pytesseract`→`pdfplumber`→`pikepdf`→`pymupdf`), índice FTS5, quarentena, renomeação automática, organizador físico.
- **Auditoria:** leitura/filtro da trilha (banco exclusivo `db_mod_auditoria.db`, navegação por tabela de módulo), acesso exclusivo `administrador_geral`.
- **Solicitação de Impressão:** upload/rascunho com expiração, fórmula de paginação, cotas hierárquicas, autorização, marca d'água, auditoria.

## Requisitos não funcionais

- Execução **estritamente em intranet** (sem internet); Tailwind servido localmente (sem CDN).
- SQLite em modo **WAL** obrigatório em toda conexão.
- Rastreabilidade LGPD: IP (`X-Forwarded-For`), User-Agent, rótulo de dispositivo, MAC best-effort.
- Backup automático a cada 12 h (retenção de 10 cópias).
- **RNF-UI-01 — Padronização visual global de botões + Responsividade global mobile-first (REALIZADO 06/09; responsividade 09/2026):** todos os botões de ação do sistema seguem **um único padrão** — fábrica central `mod_intranet/ui_comum.botao(chave_modulo=...)` (`BotaoFabrica`, 06/09, ~120 `ui.button` crus migrados em 12 arquivos), **centralizados** em linhas `w-full justify-center flex-wrap` com `.style('gap: 0.75rem')` e `.style('min-width: 0')`, **mesmo formato** `size=md` `min-w-[180px]` `no-caps` `shadow-sm` (ou `outline` para `contorno`/`restaurar`/`perigo` com mesma largura) e **cor única por módulo** via tema (`<prefixo>_cor_botao`/`cor_texto_botao`, `ui.colors(primary=cor)` + `cabecalho` borda + `botao` fundo, todos em `#000000` quando vazios via `PADROES_TEMA`). Referência de tamanho: botão `Aplicar configurações` / `Aplicar` do card `card_admin`/`bloco_aparencia`. **Responsividade (RNF-UI-01 extensão):** layout **mobile-first** validado em **320 / 768 / 1024 px** (auditoria `kbp-web-design` cobrindo `main.py`, `mod_intranet`, `mod_gest_cad_usuario`, `mod_auditoria`, `mod_renomear_empenho`, `mod_solicita_impressao`, `mod_edit_pdf`, `mod_blog`, `tela_configuracoes`, `ui_comum`); padrão global: containers `w-full p-4 sm:p-6` com `min-width:0`, `flex-wrap` + `gap` via `.style()` (nunca `gap-*` Tailwind em `ui.row`/`ui.column`), `truncate`/`max-w` em badges/títulos, `overflow-x-auto` em tabs/tabelas, `w-full max-w-[420px] mx-4` em dialogs/cards de login, `grid-cols-1 sm:grid-cols-2 md:grid-cols-3` e `scroll_area` com altura explícita. Corrigido: `main.py` login (`w-[420px] p-10` → `w-full max-w-[420px] mx-4 p-6 sm:p-10`, `p-4 min-width:0`, header `flex-wrap` `truncate` `max-w` `gap` via `.style`) e `mod_gest_cad_usuario` barra superior (`flex-nowrap` → `flex-wrap`, tabs `overflow-x-auto`, busca `flex-1 min-w`, dialogs `w-full max-w`); `mod_edit_pdf` já com botões `justify-center`, toggle `spread`, grids responsivos; `mod_blog` já com filtros justificados, exibição centralizada, seleção em lote. Checklist P0/P1/P2 e proposta de classes Tailwind por `container`/`row`/`grid` disponível por módulo na auditoria `kbp-web-design`. Validado por `assets/test/verifica_ui_comum.py` (190 verificações) + `mkdocs build` (tema `readthedocs`). Ver [Padrões de Codificação](../padroes_codificacao/index.md) §8 e [Convenções](../convencoes_codigo.md) checklist.

## Backlog (pendente/parcial)

Ver [Registro de Mudanças](../registro_de_mudancas/index.md) — todos os itens da Fase 9 concluídos (RF-04/16, RF-08, RF-09, RF-26, RF-32, RF-35, RF-36, **RF-41**, **RF-45**, **RF-40**, **RF-44**, **RF-39**, **RF-58**, **RF-57**), conforme `PLANO.md`.

Veja também [Visão de Produto](../visao_de_produto/index.md) e [Arquitetura](../arquitetura_de_software_das/index.md).
