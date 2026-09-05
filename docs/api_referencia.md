# Intranet Modular — API and Code Reference

> API and code reference of the Intranet Modular: NiceGUI routes (`/login`, `/`, `/blog`, `/users`, `/auditoria`, `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao`, `/configuracoes`) and FastAPI helpers, key functions with `file:line` references, and the database tables per module.

---

# Intranet Modular — Referência de API e Código

> Referência de API e código da Intranet Modular: rotas NiceGUI (`/login`, `/`, `/blog`, `/users`, `/auditoria`, `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao`, `/configuracoes`) e auxiliares FastAPI, funções-chave com referência `arquivo:linha` e as tabelas de banco por módulo.

## Sumário

1. [Rotas (páginas e auxiliares)](#rotas-paginas-e-auxiliares)
2. [Funções-chave — núcleo](#funcoes-chave-nucleo)
3. [Funções-chave — Gestão de Usuários](#funcoes-chave-gestao-de-usuarios)
4. [Funções-chave — Blog](#funcoes-chave-blog)
5. [Funções-chave — Editor de PDF](#funcoes-chave-editor-de-pdf)
6. [Funções-chave — Renomear Empenho](#funcoes-chave-renomear-empenho)
7. [Funções-chave — Auditoria](#funcoes-chave-auditoria)
8. [Funções-chave — Solicitação de Impressão](#funcoes-chave-solicitacao-de-impressao)
9. [Tabelas por banco](#tabelas-por-banco)

> Todas as referências foram conferidas contra o código na data desta documentação. Em conflito, prevalece o código executável.

## Rotas (páginas e auxiliares)

| Rota | Tipo | Módulo | Acesso | Definição |
|:---|:---|:---|:---|:---|
| `/login` | `@ui.page` | `mod_intranet` | público | `main.py:51` |
| `/` | `@ui.page` | `mod_intranet` | usuários ativos | `main.py:112` |
| `/blog` | `@ui.page` | `mod_blog` | liberados (`blog`) | `main.py:188` |
| `/users` | `@ui.page` | `mod_gest_cad_usuario` | admin do módulo / geral | `main.py:198` |
| `/auditoria` | `@ui.page` | `mod_auditoria` | `administrador_geral` | `main.py:208` |
| `/edit-pdf` | `@ui.page` | `mod_edit_pdf` | liberados (`editar_pdf`) | `main.py:218` |
| `/renomear-empenho` | `@ui.page` | `mod_renomear_empenho` | liberados (`empenhos`) | `main.py:228` |
| `/solicita-impressao` | `@ui.page` | `mod_solicita_impressao` | liberados (`solicita_impressao`) | `main.py:285` |
| `/solicita-impressao/pdf/{id}` | `@app.get` | `mod_solicita_impressao` | solicitante/responsável/admin | `main.py:238` |
| `/solicita-impressao/src/impressao.js` | `@app.get` | `mod_solicita_impressao` | público (JS) | `main.py:297` |
| `/configuracoes` | `@ui.page` | `mod_intranet` | `administrador_geral` | `main.py:306` |
| `/documentacao` | `app.mount` (FastAPI) | `mod_intranet` | público | `mod_intranet/documentacao.py:37` |

> **Rota ≠ slug:** a rota não é a chave do módulo — `CHAVE_POR_ROTA` (`autenticacao.py:24`) mapeia `/users`→`usuarios`, `/edit-pdf`→`editar_pdf`, `/renomear-empenho`→`empenhos` etc.

## Funções-chave — núcleo

### Bootstrap e banco central (`mod_intranet/mod_intranet_inicializacao_bd.py` e `mod_intranet/conexao_bd.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `inicializar_bancos()` | `mod_intranet_inicializacao_bd.py:13` | cria o central + bancos dos módulos na ordem correta (idempotente) |
| `get_connection()` | `conexao_bd.py:27` | conexão WAL (`synchronous=NORMAL`) no banco central |
| `init_db()` | `conexao_bd.py:34` | cria `tb_auditoria`, `tb_config`, `tb_sessoes` + seeds (versão, cotas, `versao_modulo:*`, `PADRAO_CONFIG`) |
| `get_config(chave, default)` | `conexao_bd.py:87` | leitura de configuração (`tb_config`) |
| `set_config(chave, valor)` | `conexao_bd.py:99` | gravação de configuração |
| `favicon_versao()` | `conexao_bd.py:110` | mtime do favicon (cache-busting `?v=`) |
| `DB_PATH` / `PADRAO_CONFIG` | `conexao_bd.py:11` / `:13` | caminho do banco central / padrões de aparência |

### Auditoria e rastreabilidade (`mod_intranet/manipulador_bd.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `get_intranet_conn()` | `:20` | alias de `get_connection()` |
| `garantir_rastreabilidade()` | `:24` | migração idempotente (colunas `ip`/`user_agent`/`dispositivo`/`mac`, índice `sessao_retencao`, índices da auditoria) |
| `audit_log(usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent)` | `:66` | grava na `tb_auditoria` com contexto HTTP e horário local |
| `hash_arquivo(caminho)` | `:98` | SHA-256 de arquivo (blocos de 8 KB) |

### Autenticação e sessões (`mod_intranet/autenticacao.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `MODULOS_SISTEMA` | `:15` | seed dos 6 módulos nativos `(chave, nome, icone, rota)` |
| `CHAVE_POR_ROTA` | `:24` | dict rota → chave |
| `_garantir_tb_modulos()` | `:29` | cria/popula `tb_modulos` |
| `verificar_senha` / `gerar_hash_senha` | `:157` / `:161` | bcrypt |
| `autenticar(user_nome, senha)` | `:179` | valida credenciais; falha audita `login_falha`; bloqueio recusa login |
| `registrar_login(user_nome, modulo)` | `:224` | cria sessão + `cookie_hash` + IP/UA; poda histórico |
| `sessao_ativa(user_nome, cookie_hash)` | `:257` | revalida sessão (revogável) |
| `registrar_logout` | `:276` | encerra sessão do navegador |
| `precisa_trocar_senha` | `:299` | flag `forcar_troca:<user>` |
| `trocar_senha_propria` | `:336` | autoatendimento (diálogo Meu Perfil) |
| `eh_admin_do_modulo(user, chave)` | `:405` | papel `administrador` por módulo |
| `perfil_global_de(user)` | `:409` | perfil global do usuário |
| `pode_publicar_no_blog(user)` | `:415` | permissão de escrita no blog |
| `validar_acesso_modulo(user, chave)` | `:422` | delega ao manipulador de usuários (núcleo nunca lê `tb_usuarios`) |
| `listar_modulos_permitidos(user)` | `:429` | módulos do usuário (menu lateral) |

### Layout e guarda (`mod_intranet/layout_tela.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `usuario_logado()` | `:24` | dict do usuário da sessão ou `None` |
| `pagina_restrita(titulo, chave_modulo)` | `:29` | guarda + layout de 4 partes + diálogo de troca de senha |
| `_montar_layout(...)` | `:89` | header/drawer/rodapé/área principal + versões |
| `_dialogo_meu_perfil` / `_dialogo_troca_senha` | `:202` / `:257` | autoatendimento |

### Rotinas e agendador (`mod_intranet/rotinas.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `intervalo_backup(chave, default="12")` | `:27` | horas do job de backup (mín. 1) |
| `intervalo_monitor_empenho(default=10)` | `:36` | segundos do monitor de empenhos |
| `backup_bancos()` / `backup_modulo(chave)` | `:105` / `:123` | cópia para `backup/` com timestamp |
| `_podar_backups(manter=10)` | `:140` | retém as 10 cópias mais recentes por banco |
| `iniciar_agendador()` | `:176` | agenda `backup:*`, `cleanup_pdf`, `cleanup_solicita`, `poda_auditoria`, `monitor_empenho` |
| `reagendar_backup(chave, horas)` | `:235` | altera o intervalo do job vivo |
| `limpar_editor_pdf(minutos=10)` | `:247` | fallback de limpeza de `editorPDF/` |

### Outros (núcleo)

| Função | Linha | Descrição |
|:---|:---|:---|
| `mostrar_tela` (configurações) | `tela_configuracoes.py:23` | tela `/configuracoes` (só admin geral) |
| `abrir_dialogo(usuario, chave_modulo)` | `dialogo_backup.py:28` | diálogo de backup do header |
| `configurar()` / `limpar_todos()` / `instalar_excepthook()` / `get_logger()` | `observabilidade.py:71` / `:127` / `:144` / `:163` | loguru central |
| `enviar_email` / `testar_conexao` | `email_util.py:30` / `:69` | SMTP |
| `capturar_contexto` / `rotulo_dispositivo` / `mac_best_effort` | `contexto.py:48` / `:74` / `:112` | ContextVar IP/UA |
| `construir_e_montar_documentacao()` | `documentacao.py:44` | build + mount do MkDocs |

## Funções-chave — Gestão de Usuários

`mod_gest_cad_usuario/manipulador_bd.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `senha_minima()` | `:43` | política mínima (`usuarios_senha_min`, default 6) |
| `init_db()` | `:54` | cria `tb_usuarios`, `tb_acesso_usuario` + seed `master`/`master` + auto-cura da troca (`:136-156`) |
| `listar_usuarios(filtro_ativo)` | `:178` | lista com filtros |
| `obter_usuario(user_nome)` | `:200` | usuário por login |
| `criar_usuario(ator, ...)` | `:248` | cria com senha provisória + `forcar_troca` |
| `editar_usuario(ator, ...)` | `:283` | edita; protege último `administrador_geral` (RF-26, `:292-305`) |
| `renomear_usuario(ator, atual, novo)` | `:350` | renomeia replicando em dependentes |
| `alterar_senha_admin` | `:388` | redefinição derruba as sessões |
| `bloquear_usuario(ator, nome, bloquear)` | `:410` | bloqueio/desbloqueio com auditoria |
| `soft_delete_usuario(ator, nome, motivo)` | `:435` | exclusão lógica (motivo ≥ 3 chars) |
| `_vinculos_cruzados_excluir` | `:463` | limpeza LGPD em bancos vizinhos |
| `excluir_usuario_definitivo(ator, nome)` | `:572` | DELETE físico (via busca "excluído") |
| `definir_acesso` / `remover_acesso` | `:609` / `:634` | papel por módulo em `tb_acesso_usuario` |
| `validar_acesso_modulo(user, chave)` | `:666` | usado pela guarda do núcleo |
| `listar_sessoes_ativas` / `contar_sessoes_ativas` | `:686` / `:705` | sessões vivas |
| `listar_historico_sessoes(usuario, limite=10)` | `:728` | histórico por usuário |
| `encerrar_sessao(ator, id)` / `encerrar_todas_sessoes(ator, nome)` | `:746` / `:763` | revogação |
| `listar_vinculos_orfaos(chaves_ativas)` | `:771` | vínculos órfãos (INDISPONÍVEL) |

Tela: `mostrar_tela(user_nome, perfil_global)` — `telas.py:33`.

## Funções-chave — Blog

`mod_blog/manipulador_bd.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `tags_permitidas()` | `:29` | whitelist nh3 de `tb_config` (CSV) |
| `init_db()` | `:47` | cria `tb_postagens`, `tb_comentarios`, `tb_config` local |
| `get_config_local` / `set_config_local` | `:91` / `:105` | config local do módulo |
| `listar_postagens(ativo, ordem)` | `:142` | lista com modo de exibição |
| `contar_postagens(ativo=True)` | `:157` | usada pelo dashboard |
| `_sanitizar_texto(texto)` | `:189` | nh3 na gravação |
| `criar_postagem(titulo, conteudo, autor)` | `:220` | cria + audita |
| `atualizar_postagem` / `excluir_postagem` | `:246` / `:270` | edita / soft delete |
| `despublicar_postagem` / `publicar_postagem` | `:288` / `:312` | toggle ativo |
| `criar_comentario(postagem_id, autor, conteudo)` | `:341` | comentário sanitizado |
| `_FormatadorBlog(HTMLParser)` | `:373` | única classe do código (formatação) |
| `_markdown_leve(texto)` | `:425` | Markdown leve (`#`, `**`, `-`) |
| `formatar_conteudo_para_exibicao(conteudo)` | `:468` | títulos centralizados/negrito, imagens 200–400px à esquerda |
| `obter_modo_exibicao()` | `:507` | histórico OU publicação única |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:115` (`_card_postagem` em `:14`).

## Funções-chave — Editor de PDF

`mod_edit_pdf/manipulador_bd.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_PDF_PATH` | `:23` | caminho `db_mod_edit_pdf.db` |
| `cfg_lote_arquivos` / `cfg_lote_mb` / `cfg_usuario_gb` / `cfg_expiracao_min` / `cfg_tema` | `:39`–`:73` | leitura de cotas/tema (defaults se `get_config` faltar) |
| `init_db_pdf()` | `:87` | cria `tb_arquivos`, `tb_cota_disco` |
| `nome_padronizado(usuario, operacao, nome_original)` | `:151` | prefixo `dataHora_usuario_operacao_...` |
| `verificar_quota(usuario, tamanho_bytes)` | `:171` | cotas em 4 níveis |
| `registrar_arquivo(...)` | `:193` | grava upload com hash SHA-256 |
| `obter_meus_arquivos(usuario)` | `:238` | arquivos do usuário |
| `contar_uploads_ativos(usuario)` | `:258` | estoque de uploads |
| `hash_sha256(caminho)` | `:277` | hash para auditoria |
| `op_reduzir(...)` | `:287` | modos leve/agressivo (`_reduzir_leve` `:302`, `_reduzir_agressivo` `:345`) |
| `op_juntar(caminhos_in, caminho_out)` | `:366` | merge respeitando ordem de seleção |
| `op_cortar(...)` | `:503` | pares/ímpares/intervalo |
| `op_dividir_partes(...)` | `:577` | dividir por página/par-ímpar/cortes/intervalos |
| `op_verificar(caminho_in)` | `:647` | integridade |
| `zip_por_ids(usuario, ids)` | `:665` | ZIP da seleção |
| `deletar_arquivo(usuario, arquivo_id)` | `:706` | exclusão com devolução de cota |
| `expirar_antigos(minutos)` | `:734` | chamada pelo scheduler central |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:54`.

## Funções-chave — Renomear Empenho

`mod_renomear_empenho/manipulador_bd.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_EMPENHO_PATH` / `PAGINAS_EXTRACAO` | `:20` / `:40` | banco / páginas iniciais de extração (3) |
| `pasta_monitorada()` | `:27` | `empenhos_pasta_monitorada` |
| `init_db_empenho()` | `:60` | cria `tb_empenhos`, `tb_indexador_pesquisa`, `tb_indexador_pesquisa_fts5`, `tb_quarentena`, `tb_regex_regras` |
| `extrair_texto_pdf(caminho)` | `:139` | pipeline `pymupdf → pdfplumber → OCR (pytesseract) → pikepdf` |
| `extrair_numero(texto)` | `:201` | número do empenho por regex |
| `processar_pdf(usuario, caminho, numero, parcela, regex_custom)` | `:239` | extração + renomeação + FTS5 + auditoria |
| `mover_quarentena(usuario, caminho, motivo)` | `:315` | fila de quarentena |
| `listar_empenhos(status, limite=200)` | `:343` | últimos registros |
| `extrair_campos_regex(texto)` | `:373` | campos customizados de `tb_regex_regras` |
| `reindexar_empenho(eid)` / `rebuild_fts()` | `:399` / `:438` | manutenção FTS5 |
| `pesquisar(termo, limite=50)` | `:452` | busca **FTS5 MATCH** (fallback `LIKE`) |
| `listar_quarentena(limite=100)` | `:494` | pendências |
| `reprocesse_quarentena(qid, novo_padrao)` | `:508` | reprocessa com regex aplicada na hora |
| `salvar_regra(nome, padrao, ativo, campo_destino)` | `:536` | regex dinâmica (vale sem restart) |
| `rodar_monitor(usuario="sistema")` | `:597` | job do APScheduler (RF-40) |
| `organizar_pastas()` | `:616` | caixas/subpastas físicas |
| `gerar_matriz_organizador()` | `:709` | capas `capa.txt` + `matrizDeDocumentos.txt`/`.pdf` |
| `validar_presenca_matriz()` | `:740` | validação da matriz |
| `ferramenta_cortar` / `ferramenta_juntar` / `ferramenta_reduzir` | `:774` / `:797` / `:818` | reutilizam as `op_*` do `mod_edit_pdf` |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:25`.

## Funções-chave — Auditoria

`mod_auditoria/`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `mostrar_tela(usuario_logado, perfil)` | `telas.py:83` | único ponto de entrada; filtros, paginação server-side, exportação CSV, campos/ordem por auditor |
| `check_auditoria.py` | script diagnóstico | contagem/sumário da trilha |

Sem banco próprio: lê `tb_auditoria` via `get_connection()` do núcleo. Configs: `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header`, `auditoria_campos:<usuario>`.

## Funções-chave — Solicitação de Impressão

`mod_solicita_impressao/manipulador_bd.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_PATH` | `:25` | `db_mod_solicita_impressao.db` |
| `init_db()` | `:92` | 7 tabelas + `tb_configuracoes_modulo` |
| `obter_config` / `definir_config` | `:259` / `:270` | config local do módulo |
| `contar_paginas_pdf(caminho)` | `:285` | PyMuPDF (0 ⇒ bloqueia envio) |
| `calcular_paginas_contabilizadas(...)` | `:303` | fórmula `qtd × cópias × fator_papel × fator_frente_verso` |
| `criar_secretaria`/`listar_secretarias`/`editar_secretaria`/`excluir_secretaria` | `:321`–`:394` | cadastro de secretarias |
| `criar_setor`/`listar_setores`/`editar_setor`/`excluir_setor` | `:408`–`:489` | cadastro de setores |
| `criar_responsavel`/`listar_responsaveis`/`excluir_responsavel` | `:503`–`:551` | responsáveis por autorização |
| `eh_responsavel_autorizacao(user, sec, setor)` | `:563` | confere vínculo (independe do perfil) |
| `obter_ou_criar_cota` / `definir_cota` | `:592` / `:626` | cota mensal hierárquica |
| `obter_consumo` / `_incrementar_consumo` / `verificar_excedente` / `resetar_consumo` / `percentual_consumo` | `:647`–`:721` | consumo e excedente |
| `gerar_nome_arquivo(...)` | `:741` | `YYYYMMDD_HHMMSS_usuario_copias_paginas_secretaria_setor.pdf` |
| `criar_solicitacao(...)` | `:753` | cria + audita (com hash) |
| `autorizar_solicitacao` / `recusar_solicitacao` | `:923` / `:949` | autorização (motivo na recusa) |
| `imprimir_solicitacao(sid, admin, ator)` | `:971` | desconta cota + agenda exclusão |
| `recuar_solicitacao` / `cancelar_solicitacao` | `:1011` / `:1031` | revertem e removem o arquivo |
| `tempo_expira_rascunho_min` / `tempo_exclui_impresso_min` | `:1052` / `:1059` | prazos padrão (4/10 min) |
| `registrar_rascunho(usuario, bytes, nome)` | `:1086` | upload automático + uuid (evita colisão) |
| `confirmar_rascunho(...)` | `:1162` | reconfirma e renomeia para o padrão final |
| `expirar_rascunhos_e_impressos()` | `:1248` | job `cleanup_solicita` (1 min) |
| `relatorio_cotas(mes)` | `:1324` | relatório mensal |
| `aplicar_marca_dagua(...)` | `:1357` | marca d'água personalizável |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:24` (subtelas `_tela_nova` `:107`, `_tela_minhas` `:327`, `_tela_autorizar` `:346`, `_tela_admin` `:469`).

## Tabelas por banco

| Banco | Tabelas | Observação |
|:---|:---|:---|
| `db_mod_intranet.db` | `tb_auditoria`, `tb_config`, `tb_sessoes`, `tb_modulos` | central; `tb_auditoria` com `ip`/`user_agent` + índices; `tb_sessoes` com `ip`, `user_agent`, `dispositivo`, `mac` |
| `db_mod_gest_cad_usuario.db` | `tb_usuarios`, `tb_acesso_usuario` | `tb_usuarios`: `id`, `user_nome`, `user_senha` (bcrypt), `user_email`, `user_fone`, `user_perfil`, `user_ativo`, `data_cadastro`, `user_deletado`, `user_nome_completo`, `user_motivo_exclusao`; vínculo `UNIQUE(user_nome, modulo_chave)` |
| `db_mod_blog.db` | `tb_postagens`, `tb_comentarios`, `tb_config` | sanitização nh3 na gravação e renderização |
| `db_mod_edit_pdf.db` | `tb_arquivos`, `tb_cota_disco` | `tb_arquivos`: `nome_arquivo`, `usuario`, `tamanho_bytes`, `operacao`, `hash`; cotas por usuário |
| `db_mod_renomear_empenho.db` | `tb_empenhos`, `tb_indexador_pesquisa`, `tb_indexador_pesquisa_fts5` (32 colunas), `tb_quarentena`, `tb_regex_regras` | FTS5 virtual (RF-41) com MATCH; regex com `campo_destino` |
| `db_mod_solicita_impressao.db` | `tb_solicitacoes`, `tb_secretarias`, `tb_setores`, `tb_responsaveis_autorizacao`, `tb_cotas_impressao`, `tb_consumo_cota`, `tb_configuracoes_modulo` | contabilização com fórmula; cotas mensais hierárquicas |
| — | `mod_auditoria` **não tem banco** | lê `tb_auditoria` do central |

> ⚠️ **`criador_bd.py` é legado/morto** em todos os módulos (aponta para o banco central com esquemas divergentes). As tabelas reais são criadas por `init_db*()` dos respectivos `manipulador_bd.py` — ver [Arquitetura](arquitetura.md#padrao-interno-de-um-modulo).