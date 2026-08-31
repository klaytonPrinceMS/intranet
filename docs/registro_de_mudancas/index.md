# Change Log — Intranet Modular

> Tracking of implemented, partial and pending items (backlog from `PLANO.md` Fase 9 and roadmap from `analise.md`). In conflict, executable code prevails.

---

# Registro de Mudanças — Intranet Modular

> Registro de itens implementados, parciais e pendentes (backlog de `PLANO.md` Fase 9 e roadmap de `analise.md`). Em conflito, prevalece o código executável.

## Status geral (Fase 9)

**59 REALIZADOS · 0 PARCIAL · 0 PENDENTE** (Fase 9.1 concluída: RF-04/16, RF-08, RF-26, RF-35, RF-36; Experiência/Blog: RF-09, RF-32; Renomear: RF-41, RF-45, RF-40, RF-44, RF-39; Infra: RF-58, RF-57).

## Concluído recente

- Troca obrigatória de senha do `master` por auto-cura no boot.
- `mod_solicita_impressao` (Fase 7) e Observabilidade/loguru (Fase 8).
- **Fase 9.1 (Hardening de segurança/auditoria):** RF-04/16 (cookie `HttpOnly` em nível de framework), RF-08 (`tb_auditoria.timestamp` em `localtime`), RF-26 (impedir rebaixar/bloquear o último `administrador_geral` por outro admin), RF-35 (Auditoria exclusiva do `administrador_geral`), RF-36 (filtro por hora + `rotulo_dispositivo`).
- **Solicitação de Impressão — concessão de permissão de autorizar impressão:** em *Administração → Responsáveis* o admin localiza usuários cadastrados via seletor buscável e concede a permissão; usuários `comum` que recebem a permissão passam a acessar a aba **Autorização** ao logar.
- **Fase 9.1 — Experiência e Blog (RF-09, RF-32):** o dashboard `/` carrega o feed do Blog por padrão (substituindo os cards de módulos, que continuam no drawer); `formatar_conteudo_para_exibicao` aplica títulos negrito/centralizados, imagens 200–400px à esquerda e texto justificado (HTML/Markdown/texto puro).
- **Renomear Empenho — Indexação FTS5 (RF-41):** criada `tb_indexador_pesquisa_fts5` com 32 colunas (cabeçalho do empenho); a busca na tela `/renomeador` usa FTS5 (`MATCH`), com fallback `LIKE`. Regras regex ganharam `campo_destino` para alimentar campos FTS customizados.
- **Renomear Empenho — Ferramentas de PDF embutidas (RF-45):** corte (pares/ímpares/intervalo), mesclagem e redução de tamanho disponíveis DENTRO do módulo (reutilizam `op_cortar`/`op_juntar`/`op_reduzir` de `mod_edit_pdf`); saídas em `datahora_cortePDF/`, `datahora_mergePDF/`, `datahora_reducaoPDF/`.
- **Renomear Empenho — Monitor de pasta automático (RF-40):** job `monitor_empenho` no APScheduler varre a pasta monitorada em intervalo configurável (`empenhos_monitor_intervalo_seg`, padrão 10 s), além do botão manual; reagendável sem restart.
- **Renomear Empenho — Organizador completo (RF-44):** `organizar_pastas` agora gera `capa.txt` por caixa e `matrizDeDocumentos.txt`/`.pdf`; `validar_presenca_matriz` confere a presença dos documentos listados.
- **Renomear Empenho — Ações de usuário comum (RF-39):** card "Ações de usuário comum" com **Baixar ZIP** e **Enviar por e-mail** dos empenhos organizados; liberado por `renomear_autorizar_download` (admin).
- **Infraestrutura — SMTP (RF-58):** `mod_intranet/email_util.py` + cartão "E-mail / SMTP" em Configurações (`smtp_*` em `tb_config`) com teste de conexão.
- **Infraestrutura — Configurações gerais (RF-57):** cartão "Configurações gerais" com `backup_interval_hours` (reagenda todos os backups), `sessao_retencao` e exibição da pasta raiz.

Veja [Plano de Projeto](../plano_de_projeto/index.md) e [Versionamento](../versionamento/index.md).
