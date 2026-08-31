# Levantamento de Requisitos — Intranet Modular (Plano de Ação / Backlog)

> Documento de requisitos original: `analise.md`. Os itens **já realizados** foram movidos para a
> documentação técnica em `docs/analise_mod_*.md` (ver `PLANO.md` → "Status da Documentação").
> Este arquivo é o **BACKLOG VIVO**: a cada fase concluída, o item correspondente é **removido daqui**
> e o documento de `docs/` é **padronizado** (cabeçalho EN+PT-BR, status REALIZADO).

---

## Workflow de conclusão (repetir por fase/item)

1. **Implementar** o RF (código + testes em `test/` ou `testes/`).
2. **Padronizar a escrita** no(s) doc(s) de `docs/` correspondente(s):
   - Cabeçalho obrigatório **Inglês + Português do Brasil**.
   - Seção de **Status** marcada como `REALIZADO`, removendo a menção "Em aberto".
   - Texto consistente com o padrão do especialista de documentação (sem apagar o existente).
3. **Remover o item deste `analise.md`** (recortar da fase), deixando só o que resta.

> Fonte de status no `PLANO.md`: Fase 9 (espelho). O `analise.md` é a fonte viva cortada por fase.
> **Estado atual**: o Backlog está **vazio** — todos os RFs das Fases 9.1–9.4 foram implementados,
> documentados em `docs/` e movidos para o "Roadmap (histórico)" abaixo.

---

## Roadmap (histórico)

- ~~Troca obrigatória de senha do `master` no 1º login~~ → **REALIZADO**.
- ~~Indexação FTS5 no renomear (RF-41)~~ → **REALIZADO** (32 colunas + campos regex customizados;
  `pesquisar()` usa MATCH) — `docs/analise_mod_renomear_empenho.md`.
- ~~Ferramentas de PDF embutidas no renomear (RF-45)~~ → **REALIZADO** (reutiliza
  `op_cortar`/`op_juntar`/`op_reduzir` do `mod_edit_pdf`; saídas em `datahora_cortePDF/`,
  `datahora_mergePDF/`, `datahora_reducaoPDF/`) — `docs/analise_mod_renomear_empenho.md`.
- ~~Configuração SMTP (RF-58)~~ → **REALIZADO** (`mod_intranet/email_util.py` + cartão
  "E-mail / SMTP", credenciais `smtp_*` em `tb_config`) — `docs/analise_mod_intranet.md`.
- ~~Tela Configurações do Sistema (RF-57)~~ → **REALIZADO** (cartão "Configurações gerais":
  `backup_interval_hours` reagenda todos os backups, `sessao_retencao` e pasta raiz;
  `mod_intranet/tela_configuracoes.py`) — `docs/analise_mod_intranet.md`.
- ~~Cookie de sessão `HttpOnly` (RF-04/16)~~ → **REALIZADO** (nível de framework —
  NiceGUI/Starlette define `HttpOnly=True` em `app.storage.user`) — `docs/analise_mod_intranet.md`.
- ~~`tb_auditoria.timestamp` em `localtime` (RF-08)~~ → **REALIZADO** (default do schema +
  `audit_log` grava horário local) — `docs/analise_mod_intranet.md`.
- ~~Dashboard `/` carrega Blog por padrão (RF-09)~~ → **REALIZADO** (feed de publicações do Blog
  na área principal) — `docs/analise_mod_intranet.md`.
- ~~Proteção do último `administrador_geral` (RF-26)~~ → **REALIZADO** (rebaixar/bloquear o último
  admin ativo por OUTRO admin é bloqueado em `mod_gest_cad_usuario/manipulador_bd.py`) —
  `docs/analise_mod_gest_cad_usuario.md`.
- ~~Formatação rica no Blog (RF-32)~~ → **REALIZADO** (`formatar_conteudo_para_exibicao`:
  títulos negrito/centralizados + imagens 200–400px à esquerda) — `docs/analise_mod_blog.md`.
- ~~Auditoria restrita a `administrador_geral` (RF-35)~~ → **REALIZADO** (backend + UI) —
  `docs/analise_mod_auditoria.md`.
- ~~Filtro por hora + `rotulo_dispositivo` na Auditoria (RF-36)~~ → **REALIZADO**
  (`strftime('%H:%M')` + `rotulo_dispositivo`) — `docs/analise_mod_auditoria.md`.
- ~~Ações de usuário comum no renomear — ZIP/e-mail (RF-39)~~ → **REALIZADO** (card
  "Ações de usuário comum" com ZIP/e-mail, liberado por `renomear_autorizar_download`;
  envio via `mod_intranet/email_util.py`) — `docs/analise_mod_renomear_empenho.md`.
- ~~Monitor automático de pasta (RF-40)~~ → **REALIZADO** (job `monitor_empenho` no APScheduler,
  intervalo padrão 10 s, configurável via `empenhos_monitor_intervalo_seg`) —
  `docs/analise_mod_renomear_empenho.md`.
- ~~Capas PDF/TXT + `matrizDeDocumentos.pdf` no organizador (RF-44)~~ → **REALIZADO**
  (`gerar_matriz_organizador` gera `capa.txt` por caixa + `matrizDeDocumentos.txt`/`.pdf`;
  `validar_presenca_matriz` confere presença) — `docs/analise_mod_renomear_empenho.md`.