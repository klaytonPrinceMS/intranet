# Requirements Elicitation — Intranet Modular

> Functional and non-functional requirements extracted from `analise.md` and `PLANO.md`. This is the engineering baseline for the Intranet Modular system.

---

# Levantamento de Requisitos — Intranet Modular

> Requisitos funcionais e não funcionais extraídos de `analise.md` e `PLANO.md`. Esta é a base de engenharia do sistema Intranet Modular.

## Requisitos funcionais centrais (resumo)

- **RF-001** Parametrização flexível do padrão de monitoramento (Configurações).
- **Gestão de Usuários** (soft CRUD): criar, alterar, bloquear, desbloquear, soft delete, perfis por módulo (`administrador_geral`, `administrador do módulo`, `comum`), senha provisória com troca obrigatória, nome social (Decreto 8.727/2016), exclusão em dois estágios (LGPD).
- **Intranet (núcleo):** `tb_auditoria` central, login por cookie `HTTP-Only`, sessões revogáveis, layout de 4 partes, personalização (cor primária), edição de perfil.
- **Blog:** CRUD com soft delete, sanitização `nh3` (XSS), leitura somente para `comum`, escrita restrita a admin.
- **Edição de PDF:** cotas (10 GB global / 1 GB por usuário), expiração em 10 min, reduzir/juntar/cortar/dividir/verificar/ZIP/excluir, auditoria com hash SHA-256.
- **Renomeador de Empenho:** monitor de pastas, extração com fallback (`pytesseract`→`pdfplumber`→`pikepdf`→`pymupdf`), índice FTS5, quarentena, renomeação automática, organizador físico.
- **Auditoria:** leitura/filtro de `tb_auditoria`, acesso exclusivo `administrador_geral`.
- **Solicitação de Impressão:** upload/rascunho com expiração, fórmula de paginação, cotas hierárquicas, autorização, marca d'água, auditoria.

## Requisitos não funcionais

- Execução **estritamente em intranet** (sem internet); Tailwind servido localmente (sem CDN).
- SQLite em modo **WAL** obrigatório em toda conexão.
- Rastreabilidade LGPD: IP (`X-Forwarded-For`), User-Agent, rótulo de dispositivo, MAC best-effort.
- Backup automático a cada 12 h (retenção de 10 cópias).

## Backlog (pendente/parcial)

Ver [Registro de Mudanças](../registro_de_mudancas/index.md) — todos os itens da Fase 9 concluídos (RF-04/16, RF-08, RF-09, RF-26, RF-32, RF-35, RF-36, **RF-41**, **RF-45**, **RF-40**, **RF-44**, **RF-39**, **RF-58**, **RF-57**), conforme `PLANO.md`.

Veja também [Visão de Produto](../visao_de_produto/index.md) e [Arquitetura](../arquitetura_de_software_das/index.md).
