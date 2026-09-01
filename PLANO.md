# PLANO DE IMPLEMENTAÇÃO

> Checklist rastreável por fase. **Marcar `[x]` cada item concluído** para permitir retomada após interrupção. Versionamento: `1.0.AAMMDD`. Não executar `git commit` (responsabilidade do autor).
> Antes de Qualquer fase, obrigatorio, garantir que caso os bancos de dados db_mod_blog, db_mod_edit_pdf, db_modgest_cad_usuario, db_mod_intranet, db_mod_nomear_empenho, ou qualquer outro banco de dados nao exista na rais do sistema onde o script ou o exetuvel gerado no futuro estiver rodanto tiver os bancos de dados deve ser criado os bancos de dados do zero, e para o usuario deve ser inserio sempre o usuario master senha master inicialmente com permissao de administrador geral 

## Fase 0 — Scaffold e estrutura base

- [x] Estrutura de pastas (`assets/`, `assets/css/`, `doc/`, `editorPDF/`, `organizadorPasta/`, `backup/`) — concluída; pastas operacionais com `.gitkeep`
- [x] Tailwind CSS servido localmente pelo próprio NiceGUI (`tailwindcss.min.js` embutido no pacote, `ui.run(tailwind=True)`) — sem CDN (rede interna)
- [x] `requirements.txt` (NiceGUI, APScheduler, nh3, pdfplumber, pikepdf, pymupdf, pytesseract)
- [x] Utilitário SQLite em modo WAL obrigatório
- [x] `main.py` com bootstrap NiceGUI sobe a aplicação


## Fase 1 — mod_intranet (núcleo/centralizador)

- [x] `db_mod_intranet.db` com tabela central `tb_auditoria` + `tb_config` (criadas por `conexao_bd.init_db()`; o arquivo `mod_intranet_criador_bd.py` previsto não existe — a inicialização é centralizada no `conexao_bd`)
- [x] Registro centralizado de auditoria (`manipulador_bd.audit_log()` + `garantir_rastreabilidade()`)
- [x] Tela de login (cookie HTTP-Only, sessão registrada em banco `tb_sessoes`) — `main.py:page_login`
- [x] Usuário inicial `master`/`master` com **troca de senha obrigatória no 1º logon** (seed em `mod_gest_cad_usuario/manipulador_bd.py`, flag `forcar_troca`)
- [x] Layout 4 partes: menu superior, menu lateral retrátil, rodapé com versão, área principal (`layout_tela._montar_layout`)
- [x] Dashboard home mobile-first (Tailwind, grid fluido 360–1440px, microinterações, feedback de 2s via setTimeout) — `main.py:page_dashboard`
- [x] Personalização do sistema (título, ícones, pasta raiz, paleta de cores, SMTP) lida de `tb_config`
- [x] Backup automático dos bancos a cada 12h (configurável, `backup_horas:<modulo>`)
- [x] Módulos secundários visíveis apenas para usuários autorizados; alerta para módulos removidos do `main.py`

### Padrão de exibição (Fase 1) — "módulo exemplo" = Editor de PDF

> Todos os módulos seguem o padrão de exibição do `mod_edit_pdf/telas.py` (módulo
> exemplo): **área cheia** (`w-full`, sem `max-w-*` centralizador) e **cupê
> "Aparência" padronizado** na aba/expansão Administração, com as mesmas 6 chaves
> em `tb_config` central (`cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`,
> `btn_tamanho`, `texto_header`) sob o prefixo `<chave>_` do módulo
> (`blog_*`, `usuarios_*`, `auditoria_*`, `empenhos_*`, `solicita_impressao_*`,
> `editar_pdf` usa `editpdf_*`). Aplicação imediata, sem restart
> (`_btn_cls`/`_btn_style`/`cor_fundo`/`cor_titulo` no `cabecalho` do
> `aba_modulo.py`).

## Fase 2 — mod_gest_cad_usuario (soft CRUD)

- [ ] `db_mod_gest_cad_usuario.db`: tabela `tb_usuario` (ID como chave primária), `tb_perfil`, vínculo usuário↔módulo↔perfil
- [ ] CRUD com soft delete: criar, alterar, bloquear, desbloquear (`user_nome`, `user_senha`, `user_email`, `user_fone`)
- [ ] Tela de gestão `/gestao-usuarios` com tabela de usuarios, modal de novos usuarios, toggle ativo/bloqueado
- [ ] Perfis por módulo (`administrador_geral`, `administrador_modulo`, `comum`) e controle granular de acesso
- [ ] Senha provisória para novos usuarios + troca no primeiro acesso
- [ ] Auditoria central em `tb_auditoria` (criação/edição/exclusão/liberação, LGPD)

## Fase 2.5 — Testes do fluxo completo (pasta `testes/`)

- [ ] `testes/teste_boot.py`: servidor sobe, `/login` com Tailwind local + CSS custom
- [ ] `testes/teste_fluxo_autenticacao.py`: login master → senha provisória → troca obrigatória → sessão/logout → auditoria → soft delete (19/19 OK)
- [ ] `testes/teste_fluxo_permissoes.py`: concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (13/13 OK)
- [ ] Correções: inputs dentro do diálogo, evento `.value` do checkbox, senha provisória aleatória revelada ao admin, remoção de rascunho quebrado (`mod_gest_cad_usuario_api.py`)
- [ ] Controle granular aplicado no menu lateral, cards do dashboard e página `/modulo/{slug}` (acesso negado)

## Fase 3 — mod_blog

- [ ] `db_mod_blog.db` + CRUD de postagens (soft delete, publicar/despublicar, `tb_config` local do módulo)
- [ ] Sanitização obrigatória com `nh3` (na gravação e na renderização; `data:`/relativas permitidas para imagens)
- [ ] Formatação: títulos em negrito/centralizado, imagens 200–400px alinhadas à esquerda, texto puro/Markdown/HTML
- [ ] Exibição única ou histórico cronológico; auditoria central
- [ ] Página `/blog` com editor (pré-visualização), configurações (modo + largura de imagem) e gestão restrita a admin geral/admin. do módulo
- [ ] `testes/teste_fluxo_blog.py`: sanitização XSS, conversores, CRUD, soft delete, config local, auditoria central (33/33 OK)

## Fase 4 — mod_renomear_empenho

### 4a. Monitor, extração e indexação

- [ ] Monitor de pastas (live ou intervalo configurável, padrão 10s), somente `.pdf` (`mod_renomear_empenho_monitor_pasta.py`, APScheduler)
- [ ] Extração com fallback automático `pytesseract` → `pdfplumber` → `pikepdf` → `pymupdf` (tratar encoding cp1252/Latin-1 e OCR em páginas-imagem) — mojibake neutralizado via texto tolerante (`?`)
- [x] Indexação FTS5 `tb_indexador_pesquisa_fts5` (32 campos do cabeçalho) + campos customizados por Regex dinâmico em `tb_regras_regex` — **REALIZADO** (busca na tela usa FTS5 MATCH).
- [ ] Documento-modelo `DOC_0201.pdf` processado ponta a ponta (fixture de teste — `testes/teste_fluxo_renameador.py`, 31/31 OK)

### 4b. Quarentena e regras dinâmicas

- [ ] Fila de quarentena para PDFs com erro de leitura/corrupção/Regex não reconhecido (tela `/renomeador`)
- [ ] Interface do administrador: identificação manual + cadastro de Regex dinâmico com reprocessamento sem reiniciar (`promover_quarentena`/`reprocessar_fila`, botão "Reprocessar fila")

### 4c. Renomeação e organizador físico

- [ ] Renomeação automática (somente campos validados sem divergência) e sequencial com contador em banco (`doc_0032_numEmpenho_numParcela.pdf`)
- [ ] Organizador: subpastas ~200 páginas, 4 pastas/caixa, capas PDF/TXT em `organizadorPasta/` (`mod_renomear_empenho_organizador.py`, 16/16 OK)
- [ ] Validação de presença via `matrizDeDocumentos.pdf`

### 4d. Ferramentas de edição embutidas

- [ ] Corte (pares/ímpares/intervalo), merge e redução de tamanho (DPI/qualidade); saídas em `datahora_mergePDF/`, `datahora_cortePDF/`, `datahora_reducaoPDF/` (18/18 OK)
- [ ] Ações do usuário comum: pesquisa (FTS5 na tela), ZIP; auditoria com hash SHA-256 em todas as operações

## Fase 5 — mod_edit_pdf

- [ ] `db_mod_edit_pdf.db` + `editorPDF/` com cota global 10 GB e limites por lote (10 arquivos/1 GB)
- [ ] Expiração automática após 10 min (rotina agendada) e prefixo `dataHora_usuario_operacao_nomeArquivo.pdf`
- [ ] Operações: reduzir (DPI 50–400, qualidade 10–100%, escolha de biblioteca), juntar, dividir, verificar integridade, ZIP, excluir
- [ ] Auditoria central com hash SHA-256 (origem/destino)

## Fase 6 — mod_auditoria

- [ ] Leitura/filtro da `tb_auditoria` central (data, hora, usuário, tipo de ação, módulo de origem)
- [ ] Acesso exclusivo `administrador_geral`

> ⚠️ **Nota de teste (CORRIGIDO)** — `test/test_auditoria.py` usava a assinatura antiga
> de `audit_log()` (`ip=`, `user_agent=`); o núcleo (`mod_intranet/manipulador_bd.py:66`)
> usa `client_ip`/`client_user_agent`. Corrigido no script chamando
> `client_ip="127.0.0.1", client_user_agent="zz-ua"` — **12/12 OK**.

---

## Fase 7 — mod_solicita_impressao (CONCLUÍDO)

Módulo `mod_solicita_impressao` (rota `/solicita-impressao`, banco `db_mod_solicita_impressao.db`).
Implementado e validado por `test/test_solicita_impressao.py` (fórmula, cadastros, fluxo com
autorização, excedente de cota, marca d'água, rascunho/confirmação/expiração).

- [x] Upload automático para o servidor ao selecionar o PDF + renomeação (nome original descartado)
- [x] Rascunho com expiração (`tempo_expira_rascunho_min`, padrão 4 min) — arquivo removido do
      servidor automaticamente se não confirmado; botão "Remover arquivo"
- [x] Botão "Enviar solicitação" reconfirma e renomeia para o padrão final
      `dataHora_usuario_copias_paginas_secretaria_setor.pdf`
- [x] Contabilização: `paginas = qtd × copias × fator_papel × fator_frente_verso` (A4=1/A3=2,
      frente=1/verso=2)
- [x] Cotas mensais hierárquicas (secretaria/setor), excedente marcado, visual 80%/100%, reset/editar
- [x] Autorização por responsável cadastrado (secretaria/setor); sem responsável → autorizado direto
- [x] Impressão (admin): desconta cota e agenda exclusão do arquivo em `tempo_exclui_impresso_min`
      (padrão 10 min); recusar/recuar/cancelar removem o arquivo na hora
- [x] Marca d'água opcional e personalizável (texto/posição/opacidade/fonte/cor/rotação)
- [x] Auditoria central (`tb_auditoria`, módulo `solicita_impressao`): quem solicitou/autorizou/
      imprimiu/recusou (com quantidades e motivo)
- [x] Padrões do formulário pré-selecionados e editáveis (A4, PB, somente frente, sulfite)
- [x] Variáveis de tempo e padrões expostas na aba Administração → Configurações do módulo
- [x] Job de limpeza agendado (`cleanup_solicita`, 1 min) em `mod_intranet/rotinas.py`
- [x] Seed de versão `versao_modulo:solicita_impressao = 1.0.260829` em `tb_config` central
- [x] Upload de PDF corrigido: o handler usava `e.content`/`e.name` (inexistentes em
      `UploadEventArguments`); passou a usar `on_multi_upload` + `FileUpload.read()`, espelhando o
      Editor de PDF (era a causa de "não enviava arquivo")
- [x] Upload agora aceita **múltiplos PDFs (padrão 10)**: lista com checkbox por arquivo,
      "Remover selecionados" e remoção individual; cada arquivo marcado vira uma solicitação
      (com as opções do formulário); expiração por arquivo com descarte automático
- [x] Bug de colisão de nome de rascunho no mesmo segundo corrigido (uuid no nome do arquivo)

## Fase 8 — Observabilidade / logs (loguru) (CONCLUÍDO)

Módulo central `mod_intranet/observabilidade.py`, configurável na administração do Intranet.

- [x] Instalação de `loguru` (em `requirements.txt`)
- [x] Sink de arquivo em `logs/` com rotação (tempo, ex. `1 month`, ou tamanho, ex. `50 MB`),
      retenção (padrão `4 months`) e compressão `.zip`
- [x] Nível configurável (DEBUG/INFO/WARNING/ERROR) e liga/desliga (`log_ativo`)
- [x] Captura de exceções não tratadas (thread principal + loop assíncrono) via `excepthook`
- [x] `(Re)configuração em runtime` ao salvar na administração; logs de erro nos jobs de limpeza
- [x] Cartão "Observabilidade e logs" na administração do Intranet (salvar + "Limpar TODOS os logs")
- [x] Configs persistidas em `tb_config`: `log_ativo`, `log_nivel`, `log_rotacao`, `log_retencao`
- [x] Console (terminal) APENAS quando rodado via `python`: logs aparecem no terminal até o
      encerramento. No executável (`.exe` / auto-py-to-exe, `sys.frozen`) logs vão só para arquivo
- [x] Arquivo de log POR MÓDULO para separação: `logs/intranet_<data>.log` (core) + um por módulo
      (`solicita_impressao_<data>.log`, `blog_<data>.log`, etc.); cada módulo usa
      `observabilidade.get_logger("<modulo>")` para direcionar ao seu arquivo (sem duplicar no core)
- [x] Todos os módulos rotulam seus logs via `get_logger("<modulo>")` (blog, edit_pdf, renomear_empenho,
      gest_cad_usuario, auditoria, solicita_impressao) — agentes por módulo concluíram o cabeamento
- [x] Documentação dedicada em `docs/` (ver Status da Documentação abaixo)

---

## Fase 9 — Backlog do `analise.md` (CONCLUÍDO)

Todos os RFs do Backlog foram **implementados, documentados em `docs/` e removidos do
`analise.md`** (fonte viva, hoje **cortada por fase — sem itens ativos**), seguindo o workflow
de conclusão: implementar → padronizar doc em `docs/` (cabeçalho EN+PT-BR, status REALIZADO) →
remover o item do `analise.md`. O registro histórico está em `analise.md` → "Roadmap (histórico)".

### Finalizados e documentados (REALIZADO)

| RF | Resumo | Documentação em `docs/` |
|:---|:---|:---|
| RF-41 | Indexação FTS5 no renomear (32 colunas + regex customizada) | `analise_mod_renomear_empenho.md` |
| RF-45 | Ferramentas de PDF embutidas no renomear (corte/juntar/reduzir) | `analise_mod_renomear_empenho.md` |
| RF-58 | Configuração SMTP (credenciais + teste de conexão) | `analise_mod_intranet.md` |
| RF-57 | Tela Configurações (`backup_interval_hours`, `sessao_retencao`, pasta raiz) | `analise_mod_intranet.md` |
| RF-04/16 | Cookie de sessão `HttpOnly` (nível de framework) | `analise_mod_intranet.md` |
| RF-08 | `tb_auditoria.timestamp` gravado em `localtime` | `analise_mod_intranet.md` |
| RF-09 | Dashboard `/` carrega o Blog por padrão | `analise_mod_intranet.md` |
| RF-26 | Proteção do último `administrador_geral` (rebaixar/bloquear) | `analise_mod_gest_cad_usuario.md` |
| RF-32 | Formatação rica no Blog (títulos negrito/centralizados, imagens 200–400px) | `analise_mod_blog.md` |
| RF-35 | Auditoria restrita a `administrador_geral` | `analise_mod_auditoria.md` |
| RF-36 | Filtro por hora + `rotulo_dispositivo` na Auditoria | `analise_mod_auditoria.md` |
| RF-39 | Ações de usuário comum no renomear (ZIP/e-mail) | `analise_mod_renomear_empenho.md` |
| RF-40 | Monitor automático de pasta (job `monitor_empenho`, 10 s padrão) | `analise_mod_renomear_empenho.md` |
| RF-44 | Capas PDF/TXT + validação `matrizDeDocumentos.pdf` no organizador | `analise_mod_renomear_empenho.md` |

> As Fases 7 (`mod_solicita_impressao`) e 8 (Observabilidade/loguru) já constam como **CONCLUÍDAS**
> acima, com documentação em `docs/analise_mod_solicita_impressao.md` e na seção
> "Observabilidade / Logs (loguru)" de `docs/analise_mod_intranet.md`.

---

## Status da Documentação (pasta `docs/`)

Documentação técnica por módulo, servida em `/documentacao` (build MkDocs `docs/` → `site/`,
montado pela app). `mkdocs.yml` indexa todos os módulos; build validado.

| Arquivo em `docs/` | Módulo | Status | Conteúdo |
|---|---|---|---|
| `index.md` | Visão geral | OK | Índice/visão geral do sistema |
| `analise_mod_intranet.md` | Núcleo | **ATUALIZADO** | Banco central, layout 4 partes, **dashboard mobile-first + padronização de exibição (Fase 1)**, versão no rodapé, personalização |
| `analise_mod_gest_cad_usuario.md` | Gestão de Usuários | OK | CRUD soft, perfis, auditoria, **cupê Aparência padrão**, versionamento |
| `analise_mod_blog.md` | Blog | OK | Sanitização nh3, CRUD, versionamento |
| `analise_mod_edit_pdf.md` | Editor de PDF | OK | Lote, expiração 10 min, operações, auditoria |
| `analise_mod_renomear_empenho.md` | Renomear Empenhos | OK | Monitor, FTS5, quarentena, renomeação, organizador |
| `analise_mod_auditoria.md` | Auditoria | OK | Leitura/filtro `tb_auditoria`, acesso admin geral |
| `analise_mod_solicita_impressao.md` | Solicitação de Impressão | **ATUALIZADO** | Fluxo de upload/rascunho, fórmula, cotas, autorização, retenção de arquivo, auditoria, versionamento `1.0.260829` |
| `analise_mod_intranet.md` (seção Observabilidade) | Núcleo | **OK / REALIZADO** | Observabilidade central `mod_intranet/observabilidade.py` documentada (loguru: rotação/retenção/compressão, excepthook, limpeza, `get_logger` por módulo) |

**Feito:** todos os 7 módulos possuem análise em `docs/`; `analise_mod_solicita_impressao.md`
reflete o novo fluxo de envio (upload automático, rascunho com expiração, confirmação, retenção
pós-impressão) e a auditoria; a seção "Observabilidade / Logs (loguru)" foi adicionada a
`docs/analise_mod_intranet.md` (Fase 8) cobrindo configuração de logs, retenção, compressão,
limpeza e adoção por módulo — espelhando a Fase 8 acima. A Fase 1 está **concluída e testada**
(`test/test_dashboard.py` 30/30 OK: grid mobile-first, microinterações, feedback 2s, 6 chaves de
aparência por módulo; boot HTTP 200 em `/login` `/` `/blog` `/configuracoes`; `mkdocs build` OK;
testes regressivos de blog/editor/solicita passando).

> Pendente de confirmação do autor: `git commit` (padrão `AAMMDD HHMM ...`) — não executar push.
