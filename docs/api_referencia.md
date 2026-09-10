# Intranet Modular — API and Code Reference

> API and code reference of the Intranet Modular: NiceGUI routes (`/login`, `/`, `/blog`, `/users`, `/auditoria`, `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao`, `/configuracoes`) and FastAPI helpers, key functions with `file:line` references, and the database tables per module. All references verified against the code on 06/09/2026.

---

# Intranet Modular — Referência de API e Código

> Referência de API e código da Intranet Modular: rotas NiceGUI (`/login`, `/`, `/blog`, `/users`, `/auditoria`, `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao`, `/configuracoes`) e auxiliares FastAPI, funções-chave com referência `arquivo:linha` e as tabelas de banco por módulo. Referências conferidas contra o código em 06/09/2026.

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
| `/login` | `@ui.page` | `mod_intranet` | público | `main.py:115` |
| `/` | `@ui.page` | `mod_intranet` | usuários ativos | `main.py:189` |
| `/blog` | `@ui.page` | `mod_blog` | liberados (`blog`) | `main.py:297` |
| `/users` | `@ui.page` | `mod_gest_cad_usuario` | admin do módulo / geral | `main.py:311` |
| `/auditoria` | `@ui.page` | `mod_auditoria` | `administrador_geral` | `main.py:325` |
| `/edit-pdf` | `@ui.page` | `mod_edit_pdf` | liberados (`editar_pdf`) | `main.py:339` |
| `/renomear-empenho` | `@ui.page` | `mod_renomear_empenho` | liberados (`empenhos`) | `main.py:353` |
| `/solicita-impressao/pdf/{id}` | `@app.get` | `mod_solicita_impressao` | solicitante/responsável/admin | `main.py:367` |
| `/solicita-impressao` | `@ui.page` | `mod_solicita_impressao` | liberados (`solicita_impressao`) | `main.py:414` |
| `/solicita-impressao/src/impressao.js` | `@app.get` | `mod_solicita_impressao` | público (JS) | `main.py:430` |
| `/configuracoes` | `@ui.page` | `mod_intranet` | `administrador_geral` | `main.py:439` |
| `/documentacao` | `app.mount` (FastAPI) | `mod_intranet` | público | `mod_intranet/documentacao.py:44` |
| `/css/frameworks/*` | rota estática | `mod_intranet` | público (CSS) | `mod_intranet/tema_css.py` (`montar_rotas_static`) |

> **Rota ≠ slug:** a rota não é a chave do módulo — `CHAVE_POR_ROTA` (`autenticacao.py:25`) mapeia `/users`→`usuarios`, `/edit-pdf`→`editar_pdf`, `/renomear-empenho`→`empenhos` etc. Slugs customizados são re-registrados por `rotas_modulos.montar_rotas_ativas()` (`main.py:452-453`); os decorators fixos permanecem (links antigos válidos).

## Funções-chave — núcleo

### Bootstrap e banco central (`../mod_intranet/bd_criador.py` e `../mod_intranet/bd_conexao.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `inicializar_bancos()` | `mod_intranet_inicializacao_bd.py:13` | cria o central + auditoria + bancos dos módulos na ordem correta (idempotente) |
| `get_connection()` | `conexao_bd.py:54` | conexão WAL (`synchronous=NORMAL`) no banco central |
| `init_db()` | `conexao_bd.py:61` | cria `tb_config`, `tb_sessoes`, `tb_modulos` (via `autenticacao`) + seeds (versão, cotas, `versao_modulo:*`, `PADRAO_CONFIG`) |
| `get_config(chave, default)` | `conexao_bd.py:103` | leitura de configuração (`tb_config`) |
| `set_config(chave, valor)` | `conexao_bd.py:115` | gravação de configuração |
| `favicon_versao()` | `conexao_bd.py:126` | mtime do favicon (cache-busting `?v=`) |
| `DB_PATH` / `PADRAO_CONFIG` | `conexao_bd.py:11` / `:13` | caminho do banco central / padrões de aparência |

### Auditoria e rastreabilidade (`../mod_intranet/bd_manipulador.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `get_intranet_conn()` | `:20` | alias de `get_connection()` |
| `garantir_rastreabilidade()` | `:24` | migração idempotente das colunas LGPD de `tb_sessoes` (`ip`/`user_agent`/`dispositivo`/`mac`) + seed `sessao_retencao` |
| `audit_log(usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent)` | `:58` | preenche contexto HTTP e grava no banco EXCLUSIVO de auditoria (`db_mod_auditoria.db`, tabela `tb_auditoria_<modulo>`) via `registrar_auditoria` |
| `hash_arquivo(caminho)` | `:86` | SHA-256 de arquivo (blocos de 8 KB) |

### Autenticação e sessões (`mod_intranet/autenticacao.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `MODULOS_SISTEMA` | `:16` | seed dos 6 módulos nativos `(chave, nome, icone, rota)` |
| `CHAVE_POR_ROTA` | `:25` | dict rota → chave |
| `_garantir_tb_modulos()` | `:30` | cria/popula `tb_modulos` (+ migração da coluna `ordem`) |
| `verificar_senha` / `gerar_hash_senha` | `:294` / `:298` | bcrypt |
| `autenticar(user_nome, senha)` | `:316` | valida credenciais; falha audita `login_falha`; bloqueio recusa login |
| `registrar_login(user_nome, modulo)` | `:361` | cria sessão + `cookie_hash` + IP/UA/dispositivo/MAC; poda histórico (`sessao_retencao`) |
| `sessao_ativa(user_nome, cookie_hash)` | `:394` | revalida sessão (revogável) |
| `registrar_logout` | `:413` | encerra a sessão deste navegador (ou todas, sem hash) |
| `precisa_trocar_senha` | `:436` | flag `forcar_troca:<user>` |
| `trocar_senha_propria` | `:473` | autoatendimento (diálogo Meu Perfil) |
| `eh_admin_do_modulo(user, chave)` | `:547` | papel `administrador` por módulo |
| `perfil_global_de(user)` | `:551` | perfil global do usuário |
| `pode_publicar_no_blog(user)` | `:557` | permissão de escrita no blog |
| `validar_acesso_modulo(user, chave)` | `:564` | delega ao manipulador de usuários (núcleo nunca lê `tb_usuarios`) |
| `listar_modulos_permitidos(user)` | `:571` | módulos ATIVOS do usuário (menu lateral) |
| `modulos_do_usuario(user)` | `:580` | todos os módulos com vínculo (desativados sinalizados) |

### Layout e guarda (`../mod_intranet/telas.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `usuario_logado()` | `:27` | dict do usuário da sessão ou `None` |
| `pagina_restrita(titulo, chave_modulo)` | `:32` | guarda + layout de 4 partes + diálogo de troca de senha |
| `_montar_layout(...)` | `:92` | header/drawer/rodapé/área principal + versões |
| `_dialogo_meu_perfil` / `_dialogo_troca_senha` | `:234` / `:289` | autoatendimento |

### Rotinas e agendador (`mod_intranet/rotinas.py`)

| Função | Linha | Descrição |
|:---|:---|:---|
| `intervalo_backup(chave, default="12")` | `:27` | horas do job de backup (mín. 1) |
| `intervalo_monitor_empenho(default=60)` | `:36` | segundos do monitor de empenhos (padrão 60 s) |
| `reagendar_monitor_empenho(segundos)` | `:49` | reaplica o intervalo ao job vivo |
| `backup_bancos()` / `backup_modulo(chave)` | `:106` / `:124` | cópia para `backup/` com timestamp |
| `_podar_backups(manter=10)` | `:141` | retém as 10 cópias mais recentes por banco |
| `iniciar_agendador()` | `:177` | agenda `backup:*`, `cleanup_pdf`, `cleanup_solicita`, `poda_auditoria`, `monitor_empenho` |
| `reagendar_backup(chave, horas)` | `:236` | altera o intervalo do job vivo |
| `limpar_editor_pdf(minutos=10)` | `:248` | fallback de limpeza de `mod_edit_pdf/editorPDF/` |

### Outros (núcleo)

| Função | Linha | Descrição |
|:---|:---|:---|
| `mostrar_tela` (configurações) | `tela_configuracoes.py:140` | tela `/configuracoes` (só admin geral) |
| `abrir_dialogo(usuario, chave_modulo)` | `dialogo_backup.py:31` | diálogo de backup do header |
| `configurar()` / `limpar_todos()` / `instalar_excepthook()` / `get_logger()` | `observabilidade.py:86` / `:168` / `:205` / `:224` | loguru central |
| `enviar_email` / `testar_conexao` | `email_util.py:30` / `:69` | SMTP |
| `capturar_contexto` / `rotulo_dispositivo` / `mac_best_effort` | `contexto.py:48` / `:74` / `:112` | ContextVar IP/UA |
| `construir_e_montar_documentacao()` | `documentacao.py:44` | build + mount do MkDocs |
| `registrar_modulo(chave, rota)` / `montar_rotas_ativas()` | `rotas_modulos.py:44` / `:56` | re-registro ao vivo de slugs customizados |

## Funções-chave — Gestão de Usuários

`../mod_gest_cad_usuario/bd_manipulador.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `senha_minima()` | `:46` | política mínima (`usuarios_senha_min`, default 6) |
| `init_db()` | `:61` | cria `tb_usuarios`, `tb_acesso_usuario` + migrações + seed `master`/`master` + auto-cura da troca (`:168-194`) |
| `listar_usuarios(filtro_ativo)` | `:217` | lista com acessos agregados |
| `obter_usuario(user_nome)` | `:245` | usuário por login |
| `criar_usuario(ator, ...)` | `:299` | cria com senha provisória + `forcar_troca` |
| `editar_usuario(ator, ...)` | `:339` | edita; protege último `administrador_geral` (RF-26, `:349-362`) |
| `renomear_usuario(ator, atual, novo)` | `:406` | renomeia replicando em dependentes |
| `alterar_senha_admin` | `:444` | redefinição derruba as sessões |
| `bloquear_usuario(ator, nome, bloquear)` | `:466` | bloqueio/restauração com auditoria dedicada |
| `soft_delete_usuario(ator, nome, motivo)` | `:491` | exclusão lógica (motivo ≥ 3 chars) |
| `_vinculos_cruzados_excluir` | `:519` | limpeza LGPD em bancos vizinhos |
| `excluir_usuario_definitivo(ator, nome)` | `:628` | DELETE físico (via busca "excluído") |
| `duplicar_usuario(ator, origem, ...)` | `:663` | duplica perfil + acessos por módulo |
| `definir_acesso` / `remover_acesso` | `:693` / `:718` | papel por módulo em `tb_acesso_usuario` |
| `validar_acesso_modulo(user, chave)` | `:750` | usado pela guarda do núcleo (auditoria exclusiva do admin geral — RF-35) |
| `listar_sessoes_ativas` / `contar_sessoes_ativas` | `:771` / `:790` | sessões vivas |
| `listar_historico_sessoes(usuario, limite=10)` | `:814` | histórico por usuário |
| `encerrar_sessao(ator, id)` / `encerrar_todas_sessoes(ator, nome)` | `:832` / `:850` | revogação |
| `listar_vinculos_orfaos(chaves_ativas)` | `:859` | vínculos órfãos (INDISPONÍVEL) |

Tela: `mostrar_tela(user_nome, perfil_global)` — `telas.py:55`.

## Funções-chave — Blog

`../mod_blog/bd_manipulador.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `tags_permitidas()` | `:29` | whitelist nh3 (config local com fallback na central, CSV) |
| `init_db()` | `:48` | cria `tb_postagens`, `tb_comentarios`, `tb_config` local + seeds |
| `get_config_local` / `set_config_local` | `:98` / `:112` | config local do módulo |
| `listar_postagens(ativo, ordem)` | `:149` | lista com ordem validada (`ativo=None` = todas) |
| `contar_postagens(ativo=True)` | `:170` | usada pelo dashboard |
| `_sanitizar_texto(texto)` | `:203` | nh3 na gravação (atributos/esquemas configurados) |
| `criar_postagem(titulo, conteudo, autor)` | `:234` | cria + audita |
| `atualizar_postagem` / `excluir_postagem` | `:260` / `:284` | edita / soft delete |
| `despublicar_postagem` / `publicar_postagem` | `:302` / `:326` | toggle ativo |
| `criar_comentario(postagem_id, autor, conteudo)` | `:356` | comentário sanitizado |
| `_FormatadorBlog(HTMLParser)` | `:388` | única classe do código (formatação) |
| `_markdown_leve(texto)` | `:440` | Markdown leve (`#`, `**`, `-`) |
| `formatar_conteudo_para_exibicao(conteudo)` | `:483` | títulos centralizados/negrito, imagens com largura configurável |
| `obter_modo_exibicao()` | `:522` | histórico OU publicação única |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:124` (`_card_postagem` em `:15`).

## Funções-chave — Editor de PDF

`../mod_edit_pdf/bd_manipulador.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_PDF_PATH` | `:23` | caminho `db_mod_edit_pdf.db` |
| `cfg_lote_arquivos` / `cfg_lote_mb` / `cfg_usuario_gb` / `cfg_expiracao_min` / `cfg_tema` | `:40` / `:48` / `:56` / `:64` / `:74` | leitura de cotas/tema (`cfg_tema` sem uso desde 06/09) |
| `init_db_pdf()` | `:92` | cria `tb_arquivos`, `tb_cota_disco` + seed da versão |
| `nome_padronizado(usuario, operacao, nome_original)` | `:163` | prefixo `dataHora_usuario_operacao_...` |
| `verificar_quota(usuario, tamanho_bytes)` | `:188` | cotas em 4 níveis |
| `registrar_arquivo(...)` | `:210` | grava arquivo + atualiza cota |
| `obter_meus_arquivos(usuario)` | `:256` | arquivos do usuário (só os que existem em disco) |
| `contar_uploads_ativos(usuario)` | `:280` | estoque de uploads |
| `hash_sha256(caminho)` | `:299` | hash para auditoria |
| `op_reduzir(...)` | `:309` | modos leve/agressivo (`_reduzir_leve` `:324`, `_reduzir_agressivo` `:367`) |
| `op_juntar(caminhos_in, caminho_out)` | `:388` | merge respeitando ordem de seleção |
| `op_cortar(...)` | `:525` | pares/ímpares/intervalo (biblioteca auto/fixa) |
| `op_dividir_partes(...)` | `:599` | dividir por página/par-ímpar/cortes/intervalos |
| `op_verificar(caminho_in)` | `:669` | integridade |
| `zip_por_ids(usuario, ids)` | `:688` | ZIP da seleção |
| `deletar_arquivo(usuario, arquivo_id)` | `:730` | exclusão com devolução de cota |
| `expirar_antigos(minutos)` | `:759` | chamada pelo scheduler central |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:64`.

## Funções-chave — Renomear Empenho

`../mod_renomear_empenho/bd_manipulador.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_EMPENHO_PATH` / `PAGINAS_EXTRACAO` | `:20` / `:108` | banco / páginas iniciais de extração (3) |
| `pastas_monitoradas()` / `pasta_monitorada()` | `:27` / `:78` | lista multi-pasta (local/UNC) / primeira pasta |
| `salvar_pastas_monitoradas(lista)` | `:95` | grava a lista em `empenhos_pastas_monitoradas` |
| `init_db_empenho()` | `:289` | cria todas as tabelas do módulo + FTS5 + seeds |
| `extrair_texto_pdf(caminho)` | `:475` | pipeline `pymupdf → pdfplumber → OCR (pytesseract) → pikepdf` |
| `extrair_numero(texto)` | `:537` | número do empenho por regex |
| `processar_pdf(usuario, caminho, numero, parcela, regex_custom)` | `:659` | extração + renomeação + FTS5 + auditoria |
| `mover_quarentena(usuario, caminho, motivo)` | `:987` | fila de quarentena |
| `listar_empenhos(status, limite=200)` | `:1025` | últimos registros |
| `extrair_campos_regex(texto)` | `:1056` | campos customizados de `tb_regex_regras` |
| `reindexar_empenho(eid)` / `rebuild_fts()` | `:1082` / `:1121` | manutenção FTS5 |
| `pesquisar(termo, limite=50)` | `:1135` | busca **FTS5 MATCH** (fallback `LIKE`) |
| `listar_quarentena(limite=100)` | `:1177` | pendências |
| `reprocesse_quarentena(qid, novo_padrao)` | `:1192` | reprocessa com regex aplicada na hora |
| `salvar_regra(nome, padrao, ativo, campo_destino)` | `:1220` | regex dinâmica (vale sem restart) |
| `rodar_monitor(usuario="sistema")` | `:1354` | job do APScheduler (RF-40) |
| `organizar_pastas()` | `:1392` | caixas/subpastas físicas |
| `gerar_matriz_organizador()` | `:1495` | capas `capa.txt` + `matrizDeDocumentos.txt`/`.pdf` |
| `validar_presenca_matriz()` | `:1526` | validação da matriz |
| `ferramenta_cortar` / `ferramenta_juntar` / `ferramenta_reduzir` | `:1561` / `:1584` / `:1605` | reutilizam as `op_*` do `mod_edit_pdf` |
| `listar_navegacao(pasta)` / `status_arquivo(caminho)` | `:1661` / `:1692` | navegação protegida / status por arquivo |
| `renomear_manual(usuario, caminho, ...)` | `:1772` | revisão manual com gate de validação |
| `criar_solicitacao(...)` / `listar_solicitacoes_acao_pendente()` | `:1884` / `:1925` | fluxo comum→admin |
| `marcar_solicitacao_enviada` / `_zip_gerado` / `_pendente` / `_recusada` | `:1951`–`:1997` | ciclo de vida das solicitações |
| `gerar_zip_solicitacoes(itens)` / `enviar_solicitacao_por_email(itens)` | `:2023` / `:2047` | entrega por ZIP ou SMTP central |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:44`.

## Funções-chave — Auditoria

`../mod_auditoria/db_manipulador.py` (banco exclusivo `db_mod_auditoria.db`):

| Função | Linha | Descrição |
|:---|:---|:---|
| `_nome_tabela(modulo)` | `:14` | nome da tabela por módulo (`tb_auditoria_<modulo>`) |
| `init_db_auditoria()` | `:34` | cria `tb_auditoria_meta` (idempotente) |
| `_garantir_tabela_auditoria(conn, tabela, modulo)` | `:54` | cria a tabela do módulo + índices + registro em meta |
| `get_modulos_com_auditoria()` | `:108` | módulos produtores (menu dinâmico da tela) |
| `registrar_auditoria(usuario, modulo, acao, ...)` | `:130` | grava na tabela do módulo (cria se necessário) |
| `contar_registros(tabela=None)` | `:158` | total (uma tabela ou todas — usado pelo dashboard) |
| `podar_registros(dias)` | `:182` | poda LGPD em todas as tabelas |
| `buscar_logs(tabela, filtros..., pagina, limite_sql)` | `:209` | consulta com filtros + paginação server-side (UNION ALL quando sem tabela) |
| `migrar_dados_existentes(forcar=False)` | `:316` | migração idempotente do legado central |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:88`. Script diagnóstico: `check_auditoria.py`.

## Funções-chave — Solicitação de Impressão

`../mod_solicita_impressao/bd_manipulador.py`:

| Função | Linha | Descrição |
|:---|:---|:---|
| `DB_PATH` | `:25` | `db_mod_solicita_impressao.db` |
| `init_db()` | `:93` | 7 tabelas + `tb_configuracoes_modulo` + seeds |
| `obter_config` / `definir_config` | `:260` / `:272` | config local do módulo |
| `contar_paginas_pdf(caminho)` | `:288` | PyMuPDF (0 ⇒ bloqueia envio) |
| `calcular_paginas_contabilizadas(...)` | `:306` | fórmula `qtd × cópias × fator_papel × fator_frente_verso` |
| `criar_secretaria`/`listar_secretarias`/`editar_secretaria`/`excluir_secretaria` | `:324`–`:401` | cadastro de secretarias |
| `criar_setor`/`listar_setores`/`editar_setor`/`excluir_setor` | `:416`–`:501` | cadastro de setores |
| `criar_responsavel`/`listar_responsaveis`/`excluir_responsavel` | `:516`–`:569` | responsáveis por autorização |
| `eh_responsavel_autorizacao(user, sec, setor)` | `:582` | confere vínculo (independe do perfil) |
| `obter_ou_criar_cota` / `definir_cota` | `:612` / `:646` | cota mensal hierárquica |
| `obter_consumo` / `_incrementar_consumo` / `verificar_excedente` / `resetar_consumo` / `percentual_consumo` | `:667`–`:743` | consumo e excedente |
| `gerar_nome_arquivo(...)` | `:764` | `YYYYMMDD_HHMMSS_usuario_copias_paginas_secretaria_setor.pdf` |
| `criar_solicitacao(...)` | `:777` | cria + audita (com hash) |
| `autorizar_solicitacao` / `recusar_solicitacao` | `:949` / `:976` | autorização (motivo na recusa) |
| `imprimir_solicitacao(sid, admin, ator)` | `:999` | desconta cota + agenda exclusão |
| `recuar_solicitacao` / `cancelar_solicitacao` | `:1039` / `:1059` | revertem e removem o arquivo |
| `tempo_expira_rascunho_min` / `tempo_exclui_impresso_min` | `:1080` / `:1087` | prazos padrão (4/10 min) |
| `registrar_rascunho(usuario, bytes, nome)` | `:1115` | upload automático + uuid (evita colisão) |
| `confirmar_rascunho(...)` | `:1192` | converte rascunho em solicitação (renomeia para o padrão final) |
| `expirar_rascunhos_e_impressos()` | `:1278` | job `cleanup_solicita` (1 min) |
| `solicitar_solicitacoes_responsavel(user)` | `:1315` | pendentes dos vínculos do responsável |
| `relatorio_cotas(mes)` | `:1354` | relatório mensal |
| `aplicar_marca_dagua(...)` | `:1387` | marca d'água personalizável |

Tela: `mostrar_tela(usuario_logado, perfil)` — `telas.py:24` (subtelas `_tela_nova` `:120`, `_tela_minhas` `:340`, `_tela_autorizar` `:359`, `_tela_admin` `:485`).

## Tabelas por banco

| Banco | Tabelas | Observação |
|:---|:---|:---|
| `db_mod_intranet.db` | `tb_config`, `tb_sessoes`, `tb_modulos` | central; `tb_sessoes` com `ip`, `user_agent`, `dispositivo`, `mac`; `tb_modulos` com `ordem` (a antiga `tb_auditoria` central foi migrada e removida) |
| `db_mod_auditoria.db` | `tb_auditoria_<modulo>` (uma por produtor) + `tb_auditoria_meta` | trilha LGPD com `ip`/`user_agent`/`client_hostname`/`hash_arquivo`; índices por módulo/usuário/timestamp |
| `db_mod_gest_cad_usuario.db` | `tb_usuarios`, `tb_acesso_usuario` | `tb_usuarios`: `id`, `user_nome`, `user_senha` (bcrypt), `user_email`, `user_fone`, `user_perfil`, `user_ativo`, `data_cadastro`, `user_deletado`, `user_nome_completo`, `user_motivo_exclusao`; vínculo `UNIQUE(user_nome, modulo_chave)` |
| `db_mod_blog.db` | `tb_postagens`, `tb_comentarios`, `tb_config` (local) | sanitização nh3 na gravação e renderização |
| `db_mod_edit_pdf.db` | `tb_arquivos`, `tb_cota_disco` | `tb_arquivos`: `nome_arquivo`, `usuario`, `tamanho_bytes`, `operacao`, `data_operacao`, `ativo`; cotas por usuário |
| `db_mod_renomear_empenho.db` | `tb_empenhos`, `tb_indexador_pesquisa`, `tb_indexador_pesquisa_fts5` (32 colunas), `tb_quarentena`, `tb_regex_regras`, `tb_campos_busca`, `tb_arquivos_auditoria`, `tb_eventos_arquivos`, `tb_solicitacoes` | FTS5 virtual (RF-41) com MATCH; regex com `campo_destino`; trilha por arquivo |
| `db_mod_solicita_impressao.db` | `tb_solicitacoes`, `tb_secretarias`, `tb_setores`, `tb_responsaveis_autorizacao`, `tb_cotas_impressao`, `tb_consumo_cota`, `tb_configuracoes_modulo`, `tb_rascunhos_upload` | contabilização com fórmula; cotas mensais hierárquicas; rascunhos expiráveis |

> ⚠️ **`db_criador.py` é legado/morto** em todos os módulos (aponta para o banco central com esquemas divergentes). As tabelas reais são criadas por `init_db*()` dos respectivos `db_manipulador.py` — ver [Arquitetura](arquitetura.md#padrao-interno-de-um-modulo).
