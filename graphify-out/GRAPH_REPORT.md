# Graph Report - intranet  (2026-09-18)

## Corpus Check
- 21 files · ~297,617 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3412 nodes · 8068 edges · 170 communities (139 shown, 31 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 493 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- mod_solicita_impressao/bd_manipulador.py
- ativacao.py
- os
- ui_comum.py
- atualizar
- mostrar_administracao
- rotinas.py
- mod_renomear_empenho/bd_manipulador.py
- AGENTS.md (fonte de verdade do desenvolvimento)
- audit_log
- test_blog_editor_imagens.py
- mod_gest_cad_usuario/bd_manipulador.py
- pdf_operacoes.py
- ler_tema
- botao
- mostrar_tela
- teste_aba_config_intranet.py
- Repositorio
- test_cobertura_total.py
- mod_edit_pdf/bd_manipulador.py
- _ler_telas
- mostrar_tela
- App
- mod_renomear_empenho/telas.py
- docker_detector.py
- grafana_provision.py
- autenticacao.py
- observabilidade.py
- test_ativacao.py
- teste_carrossel_blog.py
- main.py
- tema_modulo.py
- mod_intranet/telas.py
- _tela_navegar
- _FormatadorBlog
- otel_integracao.py
- mod_gest_cad_usuario/telas.py
- banco_conexao.py
- mod_intranet — Núcleo Intranet
- alterar_rota_modulo
- guia_API/index.md
- _CursorPostgres
- FormularioBuilder
- teste_fluxo_renomeador.py
- port_scanner.py
- mod_blog/telas.py
- mod_blog/bd_manipulador.py
- CrudBase
- iniciar_stack_otel
- repositorio.py
- pesquisar_levantamento
- mostrar_tela
- home_visual.py
- notificar
- get_config
- mostrar_tela
- PainelLista
- CSS Frameworks Embarcados (README)
- mostrar_tela
- teste_fluxo_blog.py
- verifica_ui_comum.py
- test_solicita_impressao.py
- visual.py
- _tela_nova
- helpers.js
- _fazer_login
- test_fabrica_documentos.py
- confirmar_lote
- _garantir_tb_modulos
- Ferramentas e Práticas de Segurança (DevSecOps)
- instrumentacao_app.py
- docker_instalado
- Docker - Stack OTel LGTM (README)
- check_integridade.py
- 06_blog_editor.spec.js
- Pasta de testes assets/test (README)
- _El
- construir_e_montar_documentacao
- hora_servidor.py
- obter_config
- mod_intranet
- _El
- aplicar_modelo
- _admin_configuracoes
- Servico Grafana (3000, admin master/master via env)
- verify-credentials.sh
- package.json
- montar
- _construir_dashboard
- tema_css.py
- start.sh
- fabrica_documentos.py
- nicegui_patch.py
- Audit Log Para Registrar Auditoria
- docs/index.md
- mod_solicita_impressao/telas.py
- mod_solicita_impressao/telas_administracao.py
- setup-grafana-credentials.sh
- @playwright/test
- configurar_docker_windows
- _SMTPOk
- sgbd_ativo
- _porta_valida
- get_connection
- mes_atual
- Graphify Query BFS DFS
- _global_setup.js
- arquitetura_de_software_das/index.md
- confirmar_rascunho
- _admin_configuracoes
- _card_grupo
- aplicar_banco
- Registro de Mudanças
- _ConexaoPostgres
- _admin_responsaveis
- _log
- 02_varredura.spec.js
- expirar_rascunhos_e_impressos
- Contrato Config Central Get Config Modulo Chave
- Isolamento Um Banco Por Modulo Sem Cross Query
- iniciar.sh
- _encerrar
- page_admin_modulo
- test_seg_aplicar.py
- registrar_hook_config
- opencode.json
- Extraction Confidence Rubric
- mod_auditoria/__init__.py
- teste_boot.py
- _admin_relatorio
- mod_edit_pdf/__init__.py
- mod_gest_cad_usuario/__init__.py
- precisa_trocar_senha
- _confirmar_fallback_sqlite
- mod_renomear_empenho/__init__.py
- iniciar
- mod_solicita_impressao/__init__.py
- Wiki Export Agent Crawlable
- Cross Repo Merge
- Whisper Transcription
- God Nodes Community Detection
- _SrvFalso
- docs/inicio_rapido_otel.md
- page_login
- init_db
- aplicar_portas
- page
- impressao.js
- auto_iniciar_otel
- paleta_escura
- mod_edit_pdf_bd_manipulador_hash_sha256
- mod_edit_pdf_bd_manipulador_op_cortar
- mod_edit_pdf_bd_manipulador_op_dividir
- mod_edit_pdf_bd_manipulador_op_dividir_partes
- mod_edit_pdf_bd_manipulador_op_juntar
- mod_edit_pdf_bd_manipulador_op_reduzir
- mod_edit_pdf_bd_manipulador_op_verificar
- _opencode_skills_graphify_skill_god_nodes
- docs_convencoes_codigo_config_local_via_crudbase
- docs_convencoes_codigo_registrar_hook_config
- docs_manual_de_uso_administrador_index_administrador_modulo
- mod_edit_pdf_bd_manipulador_hash_sha256
- mod_edit_pdf_bd_manipulador_op_cortar
- mod_edit_pdf_bd_manipulador_op_dividir
- mod_edit_pdf_bd_manipulador_op_dividir_partes
- mod_edit_pdf_bd_manipulador_op_juntar
- mod_edit_pdf_bd_manipulador_op_reduzir
- mod_edit_pdf_bd_manipulador_op_verificar

## God Nodes (most connected - your core abstractions)
1. `audit_log()` - 116 edges
2. `notificar()` - 101 edges
3. `botao()` - 98 edges
4. `get_config()` - 97 edges
5. `usuario_logado()` - 96 edges
6. `set_config()` - 84 edges
7. `get_connection()` - 64 edges
8. `get_connection()` - 60 edges
9. `mostrar_tela()` - 60 edges
10. `Repositorio` - 54 edges

## Surprising Connections (you probably didn't know these)
- `A1 — storage_secret com fallback fraco (main.py:616)` --conceptually_related_to--> `pagina_restrita()`  [INFERRED]
  docs/seguranca/auditoria_menu_2026-09-12.md → mod_intranet/telas.py
- `datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim)` --conceptually_related_to--> `auto_iniciar_otel()`  [INFERRED]
  assets/docker/config/grafana-provisioning/datasources/datasources.yml → mod_intranet/docker_detector.py
- `mod_intranet — Núcleo Intranet` --references--> `Repositorio`  [EXTRACTED]
  docs/modulos/intranet.md → mod_intranet/repositorio.py
- `bd_criador.py legado/morto (schema real em bd_manipulador)` --references--> `CrudBase`  [EXTRACTED]
  docs/licoes_aprendida/index.md → mod_intranet/crud_base.py
- `mod_blog — Módulo Blog` --references--> `CrudBase`  [EXTRACTED]
  docs/modulos/blog.md → mod_intranet/crud_base.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CSS frameworks para comparacao visual via rota dedicada /renomear-empenho-{nome}** — assets_css_frameworks_readme_pic_padrao, assets_css_frameworks_readme_bootstrap, assets_css_frameworks_readme_bulma, assets_css_frameworks_readme_daisyui, assets_css_frameworks_readme_pico, assets_css_frameworks_readme_picnic, assets_css_frameworks_readme_spectre, assets_css_frameworks_readme_chota, assets_css_frameworks_readme_milligram, assets_css_frameworks_readme_skeleton, assets_css_frameworks_readme_water, assets_css_frameworks_readme_mvp, assets_css_frameworks_readme_tachyons, assets_css_frameworks_readme_uikit, assets_css_frameworks_readme_foundation, assets_css_frameworks_readme_semantic, assets_css_frameworks_readme_materialize, assets_css_frameworks_readme_primer [EXTRACTED 1.00]
- **Contrato config central local hook** — docs_convencoes_codigo_config_local_via_crudbase, docs_convencoes_codigo_registrar_hook_config [EXTRACTED 1.00]
- **Fluxo trilha auditoria LGPD** — docs_analise_mod_auditoria_audit_log_registrar_auditoria, docs_analise_mod_auditoria_banco_exclusivo_auditoria, docs_analise_mod_auditoria_tabela_por_modulo_produtor [EXTRACTED 1.00]
- **Graphify query path explain trio** — _opencode_skills_graphify_references_query_graphify_query, _opencode_skills_graphify_references_query_graphify_path, _opencode_skills_graphify_references_query_graphify_explain [EXTRACTED 1.00]
- **Grafana OTel LGTM - stack de observabilidade da intranet** — assets_docker_readme_lgtm_stack, assets_docker_compose, assets_docker_compose_otel_collector, assets_docker_compose_loki, assets_docker_compose_tempo, assets_docker_compose_mimir, assets_docker_compose_grafana, assets_docker_config_otel_collector_config, assets_docker_config_loki_config, assets_docker_config_tempo_config, assets_docker_config_mimir_config, assets_docker_config_grafana_provisioning_datasources_datasources, assets_docker_config_grafana_provisioning_dashboards_dashboards [EXTRACTED 1.00]
- **Módulos em operação (hub intranet modular)** — docs_modulos_intranet_mod_intranet, docs_modulos_blog_mod_blog, docs_modulos_edit_pdf_mod_edit_pdf, docs_modulos_solicitacao_impressao_mod_solicita_impressao [EXTRACTED 1.00]
- **Perfis globais do sistema (PERFIS_GLOBAIS)** — docs_manual_de_uso_administrador_index_administrador_geral, docs_manual_de_uso_administrador_index_administrador_modulo, docs_manual_de_uso_usuario_comum_index_comum [EXTRACTED 1.00]
- **Rotina DevSecOps (SAST + dependências + segredos)** — docs_seguranca_ferramentas_bandit, docs_seguranca_ferramentas_semgrep, docs_seguranca_ferramentas_pip_audit, docs_seguranca_ferramentas_safety, docs_seguranca_ferramentas_gitleaks [EXTRACTED 1.00]
- **Banco próprio por módulo — isolamento e paridade SQLite/PostgreSQL** — agents_md_isolamento_dados, agents_md_paridade_sqlite_postgres, docs_analise_mod_gest_cad_usuario, docs_analise_mod_renomear_empenho, docs_analise_mod_intranet_banco_central [INFERRED 0.75]
- **segurança e conformidade (LGPD, sessões, perfis e risco do segredo)** — docs_arquitetura_de_software_das_index_autenticacao_sessoes, docs_analise_de_risco_index_storage_secret_risco, docs_2_levantamento_requisitos_index_perfis_usuario [INFERRED 0.75]
- **Padronização de UI NiceGUI (ui_comum + aba_modulo + tema_modulo)** — agents_md_nicegui, docs_analise_mod_intranet_ui_comum, docs_analise_mod_intranet_aba_modulo, docs_analise_mod_intranet_tema_modulo, docs_analise_mod_gest_cad_usuario, docs_analise_mod_renomear_empenho [INFERRED 0.75]
- **Arquitetura modular da intranet (núcleo + módulos de negócio)** — agents_md_mod_intranet, docs_analise_mod_intranet, docs_analise_mod_gest_cad_usuario, docs_analise_mod_renomear_empenho [INFERRED 0.85]
- **camada de dados por módulo (um banco WAL por módulo, acesso só via bd_manipulador)** — docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_solicita_impressao_mod_solicita_impressao, docs_arquitetura_de_software_das_index_bd_manipulador_padrao, docs_ferramentas_graphify_crud_base, docs_configuracoes_configuracao_central [INFERRED 0.85]
- **Fixtures PDF ficticios de empenho (massa de teste QA para o editor de PDF)** — assets_test_pdf_doc_0201, assets_test_pdf_ec_24, assets_test_pdf_ee_9570, assets_test_pdf_eg_89, assets_test_fabrica_documentos [INFERRED 0.85]
- **Pesquisa FTS5 do módulo de empenhos (levantamento + indexador)** — docs_modulos_renomear_empenho_tb_indexador_fts5, docs_modulos_renomear_empenho_fts5_prefixo, docs_modulos_renomear_empenho_tb_levantamento_fts, docs_modulos_renomear_empenho_tb_levantamento [INFERRED 0.85]
- **Organizador físico com capas e matriz de documentos (PLANO 4c)** — docs_modulos_renomear_empenho_organizador_4c, docs_modulos_renomear_empenho_gerar_matriz_organizador, docs_manual_de_uso_renomear_empenho_index_organizador [INFERRED 0.85]
- **Fluxo de quarentena reprocessável com regex dinâmica (PLANO 4b)** — assets_analise_plano_quarentena, docs_manual_de_uso_renomear_empenho_index_quarentena, docs_manual_de_uso_renomear_empenho_index_reprocessar_fila, docs_manual_de_uso_renomear_empenho_index_regras_extracao [INFERRED 0.85]
- **fluxo de auditoria LGPD (escrita audit_log → trilha tb_auditoria_<modulo>)** — docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_solicita_impressao_mod_solicita_impressao [INFERRED 0.95]

## Communities (170 total, 31 thin omitted)

### Community 0 - "mod_solicita_impressao/bd_manipulador.py"
Cohesion: 0.03
Nodes (117): garantir(), Garante as credenciais dos usuários QA usados nos testes E2E. EN: Ensures the…, Idempotently fixes QA users' passwords, profiles and change flag., bcrypt, baixar_pdf_impressao(), Rota de download do PDF da solicitação (com marca d'água se ativa). Protegida:…, alterar_senha_admin(), _audit() (+109 more)

### Community 1 - "ativacao.py"
Cohesion: 0.04
Nodes (62): Seed of "how-to" blog posts for the common user (Editor PDF, Print Request,…, mostra(), QA Diagnostico: fluxo salvar_configs -> reload -> ler valores. Testa se…, mostra(), Teste unitário da paridade SQLite/PostgreSQL (mod_intranet/banco_conexao.py).…, Teste unitário do helper de tema (mod_intranet/tema_modulo.py) — delta a1b1650.…, Documentação sob demanda — trava de boot e subida manual. EN: Docs on demand —…, Shutdown gracioso — agendador e servidor de documentação. EN: Graceful shutdown… (+54 more)

### Community 2 - "os"
Cohesion: 0.05
Nodes (84): test_tipos_especiais(), _painel_sessoes(), Active sessions tab with per-row terminate actions. Aba Sessões Ativas:…, botao_icone(), Icon-only row-action button (themed or white header variants). Atalho para…, arquivo_ja_processado(), _arquivo_registrado_no_bd(), detectar_tipo_especial() (+76 more)

### Community 3 - "ui_comum.py"
Cohesion: 0.04
Nodes (86): alternar_regra(), anonimizar_usuario(), anotar_arquivos(), arquivo_pendente(), atualizar_levantamento_renomeado(), _basename_sem_ext(), _campos_busca_ativos(), _conn() (+78 more)

### Community 4 - "atualizar"
Cohesion: 0.04
Nodes (45): _campo_impar(), Verificação das classes novas do núcleo (CrudBase, ui_painel, ui_form, ui_comum…, BotaoFabrica, campo_cor(), campo_selecao(), campo_texto(), CampoBase, CampoCor (+37 more)

### Community 5 - "mostrar_administracao"
Cohesion: 0.05
Nodes (68): Fetch a theme config value, returning default on failure., _tema(), _cfg(), cfg_expiracao_min(), cfg_lote_arquivos(), cfg_lote_mb(), cfg_tema(), cfg_usuario_gb() (+60 more)

### Community 6 - "rotinas.py"
Cohesion: 0.05
Nodes (39): Teste de papéis/validacão de acesso do ator (mod_intranet/autenticacao.py).…, Teste unitário de e-mail, documentação e observabilidade (sem I/O real). Cobre…, Fase 1: autenticacao master/master, gravacao de sessao em tb_sessoes (cookie…, test_login_e_sessao_em_banco(), PLANO.md: bancos devem ser criados do zero quando nao existirem. Faz backup dos…, test_fresh_install_creates_empty_databases(), Teste unitário/integração das rotinas de backup (mod_intranet/rotinas.py).…, Testes de seguranca do Aplicar async + superficies criticas (standalone).… (+31 more)

### Community 7 - "mod_renomear_empenho/bd_manipulador.py"
Cohesion: 0.05
Nodes (60): AGENTS.md — Diretrizes de Desenvolvimento Assistido por Agente, Anti-disconnect — handlers nunca bloqueiam o event-loop, Convenções de codificação (PascalCase/snake_case/MAIUSCULAS_SNAKE), CrudBase (acesso a dados), DDD — Língua Ubíqua em Português BR, Formato de commit AAMMDD HHMM, Isolamento total de bancos de dados (sem cross-query), Entry point main.py (+52 more)

### Community 8 - "AGENTS.md (fonte de verdade do desenvolvimento)"
Cohesion: 0.05
Nodes (52): _sempre_falha(), _soma(), _dummy(), Flags finas de permissão (JSON) — catálogo, grant, bypass e decorador. EN:…, criar_comentario(), despublicar_postagem(), excluir_postagens_em_lote(), _pode_publicar() (+44 more)

### Community 9 - "audit_log"
Cohesion: 0.07
Nodes (56): test_campos_busca(), excluir_campo_busca(), listar_campos_busca(), listar_quarentena(), listar_regras(), montar_nome_final(), Grava a lista de pastas monitoradas (uma por linha) em tb_config., Template de nome final configurado (empenhos_template_nome) ou o padrão. (+48 more)

### Community 10 - "test_blog_editor_imagens.py"
Cohesion: 0.06
Nodes (55): math, nome_de_tratamento(), Nome usado para tratamento nas telas — nome completo ou social. Cai para o…, _acesso_negado(), _aplicar_acessos(), _dlg_duplicar(), salvar(), _dlg_editar() (+47 more)

### Community 11 - "mod_gest_cad_usuario/bd_manipulador.py"
Cohesion: 0.06
Nodes (53): conexao(), DBAPI-level connection for a module on the ACTIVE backend. sqlite: conexão…, _audit(), autorizar_grupo(), contar_solicitacoes_pendentes(), criar_impressora(), criar_responsavel(), criar_secretaria() (+45 more)

### Community 12 - "pdf_operacoes.py"
Cohesion: 0.06
Nodes (49): config_backend(), Returns the backend selector as a dict (`banco_tipo`, `postgres_url`). Usado…, Persists the backend selector (`banco_tipo`, `postgres_url`). Grava no arquivo…, salvar_backend(), Gravação de configuração via Repositorio (SQLAlchemy ORM). Delega para…, set_config(), _botao_padrao(), _campo_empilhado() (+41 more)

### Community 13 - "ler_tema"
Cohesion: 0.07
Nodes (18): _definicoes_filtrar(), _ler(), _ler_admin(), _ler_bd(), _ler_rotinas(), _ler_telas(), Pesquisa Navegar assíncrona — fiação estática sem servidor., tb_levantamento + FTS no banco do módulo, fallback LIKE, presença. (+10 more)

### Community 14 - "botao"
Cohesion: 0.10
Nodes (48): _resetar(), _salvar(), nome_padronizado(), Builds the standardized file name: dataHora_usuario_operacao_nome.pdf. O nome…, _alvos(), _auditar_hash(), baixar_zip(), _op_cortar_sel() (+40 more)

### Community 15 - "mostrar_tela"
Cohesion: 0.06
Nodes (47): _abre_fecha(), _aguardar_container(), aplicar_portas(), barra(), _compose_cmd(), configurar_docker_windows(), _container_existe(), docker_instalado() (+39 more)

### Community 16 - "teste_aba_config_intranet.py"
Cohesion: 0.08
Nodes (21): App, arquivo_esta_estavel(), buscar_campo(), extrair_dados(), extrair_texto_primeira_pagina(), montar_novo_nome(), obter_prefixo(), Renomeador de Empenhos - Prefeitura de Monte Santo de Minas… (+13 more)

### Community 17 - "Repositorio"
Cohesion: 0.06
Nodes (44): datetime, expirar_imagens_orfas(), Remove imagens não concretizadas em postagem (órfãs há +5 min). Uma imagem é…, abrir_dialogo(), grade(), rodar_agora(), salvar_intervalo(), Opens the module backup dialog. Abre o diálogo de backup do módulo informado. (+36 more)

### Community 18 - "test_cobertura_total.py"
Cohesion: 0.06
Nodes (36): Nome do usuário no menu superior — botão único sempre visível. EN: Header user-…, Rodapé escondido com reveal no hover — bloco FOOTER. EN: Auto-hide footer —…, Piloto @ui.refreshable no Blog — feed, carrossel, preview e despublicadas. EN:…, inspect, definir_tema_escuro(), True se o usuário prefere o tema escuro (config per-usuário). Preferência de…, Define a preferência de tema (escuro/claro) do usuário., tema_escuro() (+28 more)

### Community 19 - "mod_edit_pdf/bd_manipulador.py"
Cohesion: 0.07
Nodes (42): aplicar_banco(), _garantir_tb_config(), Creates the central SQLite file + tb_config if missing (pre-boot). Idempotente:…, Persists the backend selector (banco_tipo/postgres_url) pre-boot., banco_modulo(), conexao_central(), definir_banco_tipo(), definir_postgres_url() (+34 more)

### Community 20 - "_ler_telas"
Cohesion: 0.09
Nodes (41): test_solicitacoes(), menu_modulo(), Builds the module menu tabs (icon above, label below). Cria a barra de abas de…, agrupar_solicitacoes_em_lote(), criar_solicitacao(), enviar_solicitacao_por_email(), gerar_zip_solicitacoes(), listar_solicitacoes() (+33 more)

### Community 21 - "mostrar_tela"
Cohesion: 0.07
Nodes (40): _ler_tema(), _log(), Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log., excluir_postagem(), extrair_segmentos_mermaid(), formatar_conteudo_para_exibicao(), listar_comentarios(), obter_habilitar_mermaid() (+32 more)

### Community 22 - "App"
Cohesion: 0.07
Nodes (37): Editor WYSIWYG do Blog — upload de imagens e expiração de órfãs. EN: Blog…, achar_botoes(), check(), clicar(), main(), Teste do modo de exibição CARROSSEL do Blog (mod_blog/telas.py). Renderiza a…, _varrer(), _cards_blog() (+29 more)

### Community 23 - "mod_renomear_empenho/telas.py"
Cohesion: 0.10
Nodes (37): main(), Test script for OTel LGTM stack integration. Script de teste para verificar se…, Test Docker detection., Test OTel stack status., Test OTel info display., Test OTel integration import., test_docker_detection(), test_otel_import() (+29 more)

### Community 24 - "docker_detector.py"
Cohesion: 0.06
Nodes (34): Ordem do menu hambúrguer — padrão + persistência após reorder + restart. EN:…, alterar_rota_modulo(), chaves_nativas(), excluir_modulo(), _garantir_tb_modulos(), nome_do_modulo(), _podar_sessoes(), precisa_trocar_credenciais() (+26 more)

### Community 25 - "grafana_provision.py"
Cohesion: 0.06
Nodes (25): Controles de imagem do editor do Blog — alinhar/esticar. EN: Blog editor image…, Markdown dentro do editor WYSIWYG do Blog. EN: Markdown inside the WYSIWYG…, Mermaid sempre ao fim da postagem — padrão do Blog. EN: Mermaid diagrams always…, html, html_parser, ajustar_imagem_html(), contar_postagens(), _largura_imagem() (+17 more)

### Community 26 - "autenticacao.py"
Cohesion: 0.09
Nodes (34): _op_verificar(), _extrair_paginas(), _libs_da_preferencia(), _log(), op_cortar(), op_dividir(), op_dividir_partes(), op_juntar() (+26 more)

### Community 27 - "observabilidade.py"
Cohesion: 0.13
Nodes (33): criar_pdf_teste(), main(), Teste do módulo Solicitação de Impressão (mod_solicita_impressao). Valida:…, Gera um PDF simples de n_paginas para teste (PyMuPDF)., teste_cadastros_e_cotas(), teste_contagem_e_formula(), teste_excedente(), teste_fluxo() (+25 more)

### Community 28 - "test_ativacao.py"
Cohesion: 0.09
Nodes (27): checar(), main(), Teste standalone do helper central de tema (mod_intranet/tema_modulo.py).…, Teste do Config do módulo Intranet: Aplicar por card, aparência, avisos e…, functools, Intranet module settings screen (main module) — admin_geral only. Tela de…, _previa(), _pv() (+19 more)

### Community 29 - "teste_carrossel_blog.py"
Cohesion: 0.09
Nodes (17): _log(), Runs a SELECT on the bound database; returns rows as dicts. Executa SQL de…, Runs a DML statement on the bound database; returns rowcount. Executa SQL de…, Returns the last autoincrement id inserted on the bound database. Devolve…, Returns the value for a configuration key or `padrao` if not found. EN: Reads a…, Inserts or replaces a configuration key (upsert ON CONFLICT). EN: Upserts a…, Inserts a new session and returns the new row id. EN: Creates a session record…, True if an active session exists for this user+hash. EN: Checks session… (+9 more)

### Community 30 - "main.py"
Cohesion: 0.11
Nodes (32): c(), Returns the text styled with rich (ANSI no terminal, plano se não-TTY)., botao(), Builds the single standardized button (delegates to `BotaoFabrica`). Wrapper…, atualizar(), _admin_responsaveis(), atualizar(), criar() (+24 more)

### Community 31 - "tema_modulo.py"
Cohesion: 0.08
Nodes (32): abrir_terminal(), _cmd(), _dir_docker(), _executar_e_persistir(), _formatar_achados_otel(), _garantir_sdk_otel(), iniciar_postgres(), iniciar_stack_otel() (+24 more)

### Community 32 - "mod_intranet/telas.py"
Cohesion: 0.09
Nodes (30): hash_arquivo(), Retorna hash SHA-256 de um arquivo., ferramenta_cortar(), ferramenta_fontes(), ferramenta_juntar(), _ferramenta_nome(), ferramenta_reduzir(), gerar_matriz_organizador() (+22 more)

### Community 33 - "_tela_navegar"
Cohesion: 0.07
Nodes (4): Testes funcionais do assistente de ativação (`mod_intranet/ativacao.py`).…, Relógio fake: avança 1 s por chamada (simula o tempo real do loop)., _Relogio, io

### Community 34 - "_FormatadorBlog"
Cohesion: 0.17
Nodes (28): atexit, page_auditoria(), page_blog(), page_configuracoes(), page_dashboard(), page_edit_pdf(), _page_empenho_forcado(), page_renomear_empenho() (+20 more)

### Community 35 - "otel_integracao.py"
Cohesion: 0.10
Nodes (29): atualizar(), _admin_secretarias(), atualizar(), criar(), _admin_setores(), atualizar(), criar(), _confirmar_impressao() (+21 more)

### Community 36 - "mod_gest_cad_usuario/telas.py"
Cohesion: 0.08
Nodes (23): Any, glob, loguru, Blog module — posts and comments with nh3 sanitization (route /blog). Módulo…, configurar(), _console_valido(), formatar_tamanho(), gerar_logs_teste_niveis() (+15 more)

### Community 37 - "banco_conexao.py"
Cohesion: 0.10
Nodes (23): Teste do Dashboard mobile-first (Fase 1, item 6) + padrão de exibição. Script…, concurrent_futures, escanear_portas(), _executar(), portas_com_servico(), _portas_docker(), _portas_por_lsof(), _portas_por_netstat_windows() (+15 more)

### Community 38 - "mod_intranet — Núcleo Intranet"
Cohesion: 0.10
Nodes (25): Levantamento do Renomear Empenhos — leitura anexada à listagem. EN: Empenhos…, _isolamento_pytest(), main(), _pdf(), fixture, Teste do fluxo do módulo Renomear Empenhos. Valida: identificação dos campos…, Aponta o banco e a pasta monitorada do módulo para um ambiente temporário,…, Sob pytest, isola banco + pasta monitorada em temp (igual ao main()), para não… (+17 more)

### Community 39 - "alterar_rota_modulo"
Cohesion: 0.16
Nodes (27): _admin_disponivel(), main(), ok(), Teste do módulo Blog (mod_blog) — teste_fluxo_blog. Valida: sanitização XSS…, teste_auditoria_central(), teste_carrossel(), teste_config_local(), teste_conversores() (+19 more)

### Community 40 - "guia_API/index.md"
Cohesion: 0.10
Nodes (8): _ConexaoPostgres, _CursorPostgres, _ddl_postgres(), Translates SQLite CREATE TABLE DDL into PostgreSQL-compatible DDL. Lida com os…, psycopg2 cursor proxy: translates `?`→`%s`, SQLite DDL/PRAGMA and captures…, Splits a script on ';' and runs each statement (SQLite emulation)., Converts Postgres datetime/date to string (SQLite-compatible)., psycopg2 connection proxy exposing the DBAPI used by the modules.

### Community 41 - "_CursorPostgres"
Cohesion: 0.09
Nodes (22): estado(), Real-NiceGUI smoke test for password fields via `ui_comum.campo_texto`. Smoke…, Visual state of a real NiceGUI element (props/classes/style/children). Estado…, index(), page, csv, json, Audit module screen — read-only viewer of the per-module audit trail. Tela do… (+14 more)

### Community 42 - "FormularioBuilder"
Cohesion: 0.12
Nodes (26): Armadilha hidden sm:*/md:* no NiceGUI 3.15, Perfil administrador_geral, Usuários seed (master/qacomum/qamaster), Perfil comum (usuário comum), Métricas de Software, mod_blog — Módulo Blog, Sanitização HTML nh3 (gravação e renderização), cleanup_pdf (expiração de arquivos 1 min) (+18 more)

### Community 43 - "teste_fluxo_renomeador.py"
Cohesion: 0.11
Nodes (17): FormularioBuilder, criar(), criar(), criar(), criar(), _log(), Registers a numeric field (`ui.number` com min/max/step). Mesmo padrão visual…, Registers an ISO date field (`ui.input` + máscara Quasar `date`). Campo de… (+9 more)

### Community 44 - "port_scanner.py"
Cohesion: 0.11
Nodes (14): bd_criador.py legado/morto (schema real em bd_manipulador), CrudBase, Runs one statement with guaranteed connection close (try/finally). Executa…, Yields a cursor within an atomic multi-statement transaction. Transação atômica…, Runs a SELECT returning all rows (list of tuples)., Runs a SELECT returning the first row (or `None`)., Runs an INSERT with commit, returning the new `lastrowid`., Runs an UPDATE/DELETE with commit, returning `rowcount`. (+6 more)

### Community 45 - "mod_blog/telas.py"
Cohesion: 0.09
Nodes (25): Exception, configurar_log_otel(), inicializar_otel(), _obter_config(), obter_endpoint(), OpenTelemetry integration for Intranet Modular. This module provides…, Initialize OpenTelemetry SDK. Inicializa o SDK do OpenTelemetry. Com…, Register an error in a span. Registra um erro em um span. (+17 more)

### Community 46 - "mod_blog/bd_manipulador.py"
Cohesion: 0.09
Nodes (25): aplicar_framework(), aplicar_modelo(), classes_card_resumo(), classes_stat(), classes_wrap_resumo(), _get_config_safe(), injetar_pic_suave(), injetar_resumo_overrides() (+17 more)

### Community 47 - "CrudBase"
Cohesion: 0.14
Nodes (24): _fazer_pdf(), _novo_contexto(), principal(), Teste de UI dirigido — botões do módulo Solicitação de Impressão. Exercita os…, Cria um Client NiceGUI mínimo para os handlers usarem…, testar_autorizar_recusar(), testar_cancelar(), testar_imprimir_confirmar() (+16 more)

### Community 48 - "iniciar_stack_otel"
Cohesion: 0.12
Nodes (18): achar_botoes(), achar_campos(), _ArquivoFake, check(), clicar(), clicar_seguro(), main(), Teste da aba CONFIG do menu_mod em /configuracoes (módulo Intranet). Script… (+10 more)

### Community 49 - "repositorio.py"
Cohesion: 0.14
Nodes (23): _btn_cls(), _btn_style(), _cfg(), mostrar_administracao(), Audit module administration panel. Painel de administração do módulo Auditoria…, Fetch an auditoria config value, returning default on failure., Return CSS classes for button size., Build inline style dict for button colour. (+15 more)

### Community 50 - "pesquisar_levantamento"
Cohesion: 0.13
Nodes (23): deletar_arquivo(), Deletes a file (disk + soft delete + quota refund) and audits it., _cor_resta(), _fmt_bytes(), _fmt_resta(), mostrar_tela(), _ao_selecionar(), _app_tema() (+15 more)

### Community 51 - "mostrar_tela"
Cohesion: 0.10
Nodes (16): _eco_regex(), Cobertura total: smoke de import + contrato de TODAS as funcoes/classes usadas.…, _botoes_testid(), check(), clicar(), main(), Teste de integração headless do rodapé padrão (ui_comum) — delta a1b1650. Cobre…, _varrer() (+8 more)

### Community 52 - "home_visual.py"
Cohesion: 0.12
Nodes (23): buscar_logs(), _extrair_modulo(), _garantir_tabela_auditoria(), get_modulos_com_auditoria(), init_db_auditoria(), migrar_dados_existentes(), _nome_tabela(), Audit module — exclusive database (db_mod_auditoria.db) with one table per… (+15 more)

### Community 53 - "notificar"
Cohesion: 0.10
Nodes (24): calcular_paginas_contabilizadas(), confirmar_lote(), contar_paginas_pdf(), contar_pedidos_abertos(), criar_solicitacao(), gerar_nome_arquivo(), obter_limite_pedidos_abertos(), obter_secretaria() (+16 more)

### Community 54 - "get_config"
Cohesion: 0.18
Nodes (15): perfis de usuário (comum, administrador_modulo, administrador_geral), mod_blog, mod_edit_pdf (edição de PDF), mod_solicita_impressao (solicitação de impressão), padrão de acesso a dados (bd_manipulador.py), inicializar_bancos (bootstrap do banco central), Validação ast.parse UTF-8 (integridade de arquivos), Lições Aprendidas (+7 more)

### Community 55 - "mostrar_tela"
Cohesion: 0.13
Nodes (20): argparse, ensure_folder(), main(), provision_dashboard(), Grafana Dashboard Provisioning - Intranet Modular Provisions dashboards into…, Perform an HTTP request to Grafana with basic auth., Ensure the target folder exists and return its UID., Upload a single dashboard JSON. (+12 more)

### Community 56 - "PainelLista"
Cohesion: 0.09
Nodes (22): CSS Frameworks Embarcados (README), Bootstrap 5.3.8 (rota dedicada, MIT), Bulma 1.0.2 (mantido em disco, pode colidir com Quasar, MIT), Chota 0.8.0 (rota dedicada, leve, MIT), DaisyUI 5.6.8 + themes (sobre Tailwind v4, MIT), Foundation 6.8.1 (rota dedicada, pesado, MIT), Materialize 1.0.0 (rota dedicada, pesado, MIT), Milligram 1.4.1 (rota dedicada, leve, MIT) (+14 more)

### Community 57 - "CSS Frameworks Embarcados (README)"
Cohesion: 0.14
Nodes (21): criar_lote_demo(), criar_lote_principal(), criar_pdf_empenho(), gerar_dados_empenho(), _nome_empresa(), nome_impressora(), _nome_pessoa(), Fábrica de documentos fictícios do módulo Renomear Empenhos. Factory of… (+13 more)

### Community 58 - "mostrar_tela"
Cohesion: 0.20
Nodes (20): mostrar_tela(), _adicionar_campo(), _atualizar_tabela(), _buscar_logs(), _campos_ativos(), _cfg(), _exportar_csv(), _limpar_filtros() (+12 more)

### Community 59 - "teste_fluxo_blog.py"
Cohesion: 0.16
Nodes (19): _api_autorizada(), atualizar_senha_grafana(), grafana_aguardar_pronto(), grafana_rodando(), obter_grafana_url(), obter_senha_master(), obter_status_grafana(), Grafana credentials sync with Intranet database. Sincroniza as credenciais do… (+11 more)

### Community 60 - "verifica_ui_comum.py"
Cohesion: 0.12
Nodes (19): _baixar(), _eh_responsavel(), _imprimir(), _imprimir_grupo(), disparar(), _log(), mostrar_tela(), _tema() (+11 more)

### Community 61 - "test_solicita_impressao.py"
Cohesion: 0.13
Nodes (20): _admin_cotas(), _excluir_secretaria(), Administration panel for the print-request module. EN — NiceGUI rendering of…, Deletes a department (with confirmation-free immediate action). Exclui uma…, Admin sub-tab: monthly quota report with edit/reset per department/unit. Sub-…, _autorizar_grupo(), _barra_cota(), _card_admin_grupo() (+12 more)

### Community 62 - "visual.py"
Cohesion: 0.15
Nodes (9): GradeTabela, _log(), PainelLista, Builds the panel (search field + body); returns the container.…, Re-renders the body (count/pagination/grade) from the first page. Deve ser…, Returns the loguru logger bound to the core module ("intranet"). Logger loguru…, Standard `ui.grid` table (caption header + cells + action column). Tabela em…, Renders header + one row per item; returns the grid element. `dados` é uma… (+1 more)

### Community 63 - "_tela_nova"
Cohesion: 0.14
Nodes (20): kbp-commit (definição do subagente), Subagente kbp-commit, kbp-devSecOps (definição do subagente), Subagente kbp-devSecOps, kbp-doc_teste (definição do subagente), criar_lote_demo (fábrica de documentos), criar_lote_principal (fábrica de documentos), Subagente kbp-doc_teste (+12 more)

### Community 64 - "helpers.js"
Cohesion: 0.18
Nodes (18): mostrar_tela(), ao_editar(), _aplicar_carrossel_exib(), _aplicar_historico_exib(), _aplicar_unica_exib(), atualizar(), _atualizar_contador(), atualizar_preview() (+10 more)

### Community 65 - "_fazer_login"
Cohesion: 0.15
Nodes (15): listar_secretarias(), Lists departments (id, nome, sigla, cota, limite_pedidos, ativo). Lista as…, _admin_solicitacoes(), ao_aba(), atualizar(), New-request tab: multi-PDF drafts with countdown + form + submission. Upload…, Admin sub-tab: PEDIDOS grouped by secretaria -> setor, with status tabs and…, _tela_nova() (+7 more)

### Community 66 - "test_fabrica_documentos.py"
Cohesion: 0.18
Nodes (11): { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, coletarErros(), ehRuido() (+3 more)

### Community 67 - "confirmar_lote"
Cohesion: 0.12
Nodes (18): Roda iniciar() com _TTY=True e serviços mockados; devolve (cfg, saída)., _rodar_iniciar(), banner(), _confirmar_fallback_sqlite(), _escolha_1_enter(), iniciar(), _msg_porta_em_uso(), _porta_livre() (+10 more)

### Community 68 - "_garantir_tb_modulos"
Cohesion: 0.25
Nodes (8): _abrir_navegar(), _aguardar_contagem(), _fazer_login(), _fechar_dialogos_bloqueadores(), Fluxo real headless: login → /renomear-empenho → digitar no campo., Admin: switch automática; lote spinner — só localhost., TestE2EAdminELote, TestE2ENavegarPesquisa

### Community 69 - "Ferramentas e Práticas de Segurança (DevSecOps)"
Cohesion: 0.11
Nodes (5): _bruto(), _campo_ordem(), Verificação da fábrica central de UI (`ui_comum` + helpers de tela). Script…, Visual state tuple of a stub element (props/classes/style/tooltip/cb). Tupla de…, types

### Community 70 - "instrumentacao_app.py"
Cohesion: 0.14
Nodes (9): eh_framework(), eh_hibrido(), eh_pic(), _get_config_safe(), ler_modelo(), Visual switcher for mod_renomear_empenho — uma tela por CSS disponível. Módulo…, Lê o modelo visual atual (pic|bootstrap), fail-soft para 'pic'., Grava o modelo em tb_config; retorna True se gravou. (+1 more)

### Community 71 - "docker_instalado"
Cohesion: 0.14
Nodes (18): _admin_configuracoes(), _admin_cotas(), _admin_relatorio(), gerar(), _prazo_fixo(), _painel_impressoras(), atualizar(), criar() (+10 more)

### Community 72 - "Docker - Stack OTel LGTM (README)"
Cohesion: 0.15
Nodes (10): browser_type_launch_args(), fixture, QA Renomear Empenhos — pirâmide de testes com evidência headless. EN — Full QA…, Backend sem browser — FTS 1 letra, levantamento presença, EE string., TestIntegracaoBackend, _fts_query_prefixada(), pesquisar_levantamento(), Busca no levantamento: FTS5 (nome+campos+conteúdo) com fallback LIKE. Cobre… (+2 more)

### Community 73 - "check_integridade.py"
Cohesion: 0.15
Nodes (15): _passo_docs(), _build(), construir_e_montar_documentacao(), habilitada_no_boot(), iniciar_servidor(), montar(), porta_documentacao(), Build + mount + start the docs server. Falha NUNCA derruba o servidor. Gera o… (+7 more)

### Community 74 - "06_blog_editor.spec.js"
Cohesion: 0.12
Nodes (17): _detectar_otel_rodando(), _detectar_postgres_rodando(), _normalizar_portas(), _portas_docker_servicos_otel(), _portas_em_uso_cached(), _probe_http(), _probe_servicos_http(), testar() (+9 more)

### Community 75 - "Pasta de testes assets/test (README)"
Cohesion: 0.19
Nodes (16): definir_ntp_ativa(), hora_servidor(), hora_servidor_str(), _ler_ntp_ativa(), _log(), _obter_offset_ntp(), offset_ntp(), Hora do servidor com sincronização opcional via NTP.br (RFC 5905). EN —… (+8 more)

### Community 76 - "_El"
Cohesion: 0.15
Nodes (15): mostrar_tela(), _tema(), Reads a theme key from tb_config, falling back to the default (fail-soft)., Renders the Empenhos screen with its 6 internal tabs. Monta a tela:…, _tema_s(), aplicar_framework(), aplicar_modelo(), injetar_bootstrap_overrides() (+7 more)

### Community 77 - "construir_e_montar_documentacao"
Cohesion: 0.15
Nodes (16): analise.md (backlog vivo / levantamento de requisitos), Indexação FTS5 no renomear (RF-41), Configuração SMTP (RF-58), PLANO.md (checklist de implementação por fase), Organizador físico (4c), mkdocs.yml (configuração da documentação técnica), docs/ (diretório da documentação MkDocs), Módulo mod_blog (+8 more)

### Community 78 - "hora_servidor.py"
Cohesion: 0.12
Nodes (6): assets_test, Testes da fábrica de documentos fictícios (faker + pytest). Validam:…, TestFabricaCoberturaCampos, TestFabricaDeterministica, TestFabricaNomesImpressora, TestFabricaPontaAPonta

### Community 79 - "obter_config"
Cohesion: 0.17
Nodes (15): fastapi, fastapi_responses, logging, _contadores(), OpenTelemetry application instrumentation for Intranet Modular. This module…, Cria e retorna os objetos de metricas (no-op se OTel indisponivel)., criar_contador(), criar_gauge() (+7 more)

### Community 80 - "mod_intranet"
Cohesion: 0.16
Nodes (16): _atualizar_status_grupo(), cancelar_grupo(), imprimir_grupo(), _incrementar_consumo(), listar_arquivos_grupo(), _log(), Adds pages to the monthly consumption (upsert on the period row). Soma páginas…, Central logger (loguru) for execution observability. Logger central (loguru)… (+8 more)

### Community 81 - "_El"
Cohesion: 0.18
Nodes (13): mod_intranet_models, caminho_db(), engine(), garantir_bancos(), SQLAlchemy ORM session factory and repository for mod_intranet. Provides a lazy…, Lazily creates/reuses the SQLAlchemy Engine for a module database. Postgres…, Ensures EVERY module database exists on the ACTIVE backend. postgres: cria…, Returns the SQLite file path for a module key (fallback: central). Devolve o… (+5 more)

### Community 82 - "aplicar_modelo"
Cohesion: 0.19
Nodes (13): Dashboards Intranet (Visao Geral/Mimir, Traces/Tempo, Logs/Loki), dashboards.yml - provider 'Intranet Dashboards' (update 30s), postgres/docker-compose.yml - backend opcional PostgreSQL 16, Docker - Stack OTel LGTM (README), Credenciais master/master compartilhadas com admin da Intranet, Grafana OTel LGTM stack (Grafana + Loki + Tempo + Mimir + OTel Collector), instrumentar_aplicacao(), _observer_requisicoes() (+5 more)

### Community 83 - "_admin_configuracoes"
Cohesion: 0.16
Nodes (11): _alvo_top(), _arquivos_py(), _imports_de(), _visitar(), _modulo_de(), Guarda estrutural do isolamento modular (AST, sem importar nada). Structural…, mod_x do arquivo, 'main' para main.py, None para o resto., mod_x / main do dotted name importado (None se stdlib/terceiro). (+3 more)

### Community 84 - "Servico Grafana (3000, admin master/master via env)"
Cohesion: 0.15
Nodes (10): fs, { login, coletarErros, errosFatais }, os, path, PNG_1X1, { test, expect }, IMPORTANT: keep the reminder string free of backticks and $(...) constructs., ref_fs (+2 more)

### Community 85 - "verify-credentials.sh"
Cohesion: 0.14
Nodes (3): _El, _fab(), _cria()

### Community 86 - "package.json"
Cohesion: 0.20
Nodes (13): contextvars, capturar_contexto(), contexto_atual(), _extrair(), _info(), limpar_contexto(), Current HTTP request context (LGPD traceability). Contexto da requisição HTTP…, Com request explícito: fixa o contexto (QA/integrações). Sem request: apenas… (+5 more)

### Community 87 - "montar"
Cohesion: 0.21
Nodes (13): risco storage_secret placeholder (main.py), Auditoria de Segurança do Menu Hambúrguer (12/09/2026), bandit 1.9.4 (SAST Python), Ferramentas e Práticas de Segurança (DevSecOps), gitleaks 8.24.3 (segredos no histórico git), pip-audit 2.10.1 (CVEs de dependências), safety 3.8.1 (CVEs conhecidas), semgrep 1.176.1 (SAST multi-regra) (+5 more)

### Community 88 - "_construir_dashboard"
Cohesion: 0.20
Nodes (14): fabrica_documentos.criar_lote_principal — massa fictícia de PDFs, Botão Gerar 25 (TEMP) — massa de teste QA, remover em produção, Organizador físico com capas e matriz (PLANO 4c), Módulo Renomear Empenho (mod_renomear_empenho), Contador de acessos apenas logins (centralizado), Busca FTS5 com prefixo (_fts_query_prefixada, 1 letra filtra), Botão Gerar 25 (TEMP) — remover antes de produção (14/09/2026), gerar_matriz_organizador — capas + matrizDeDocumentos (+6 more)

### Community 89 - "tema_css.py"
Cohesion: 0.18
Nodes (14): definir_carrossel_postagens_ids(), _log(), Stores the ordered post id list for carousel mode. Returns bool. Grava…, Seeds default 'How to use' posts into an empty posts table. Insere as postagens…, Writes the module's local tb_config (db_mod_blog.db) via CrudBase. Grava…, Logger do módulo (loguru) — arquivo dedicado logs/blog_<data>.log., _semear_postagens_padrao(), set_config_local() (+6 more)

### Community 90 - "start.sh"
Cohesion: 0.20
Nodes (14): definir_cota(), mes_atual(), obter_consumo(), obter_ou_criar_cota(), percentual_consumo(), Verifica se a impressão excederá alguma cota (secretaria OU setor). Retorna…, Returns (percent 0-100+, used, quota). Retorna (percentual 0-100+, usado, cota)…, Retorna lista de (secretaria_id, secretaria_nome, setor_id, setor_nome, cota,… (+6 more)

### Community 91 - "fabrica_documentos.py"
Cohesion: 0.15
Nodes (3): _El, _fab(), _cria()

### Community 92 - "nicegui_patch.py"
Cohesion: 0.15
Nodes (10): dataclasses, Configuracao, Models package for mod_intranet — dataclasses + SQLAlchemy ORM. Provides type-…, Key-value configuration entry (tb_config). EN: Represents a single key=value…, User session entry (tb_sessoes) with LGPD tracking fields. EN: Represents an…, Sessao, Returns all configuration entries. EN: Returns all rows from tb_config as…, Returns the active session for a user+hash pair. EN: Returns the session row… (+2 more)

### Community 93 - "Audit Log Para Registrar Auditoria"
Cohesion: 0.22
Nodes (13): bd_criador.py legado/morto — schema real via init_db*, CHAVE_POR_ROTA — rota ≠ slug do módulo, Módulo Gestão de Usuários (mod_gest_cad_usuario), bd_criador.py legado — tb_modulo_perfil inexistente, init_db — criador vigente (bd_manipulador.py:61), Limpeza cruzada LGPD em bancos vizinhos, RF-26 — proteção do último administrador_geral ativo, Seed master/master com auto-cura da troca obrigatória (+5 more)

### Community 94 - "docs/index.md"
Cohesion: 0.17
Nodes (12): _cli_app(), cli_opcoes(), config_do_cli(), _config_padrao(), config_persistida(), _porta_valida(), Loads the persisted boot config from tb_config (no prompts). Carrega a…, Builds the Typer app with the boot options (help em PT-BR). `python main.py… (+4 more)

### Community 95 - "mod_solicita_impressao/telas.py"
Cohesion: 0.20
Nodes (5): HTMLParser, _FormatadorBlog, _merge_style(), Concatena estilos CSS sem duplicar o separador ';'., Reescreve HTML sanitizado aplicando o padrão visual do Blog: - h1/h2/h3:…

### Community 96 - "mod_solicita_impressao/telas_administracao.py"
Cohesion: 0.21
Nodes (12): _admin_configuracoes(), _admin_solicitacoes(), mostrar_administracao(), _painel_impressoras(), atualizar(), criar(), _def_padrao(), _excluir_imp() (+4 more)

### Community 97 - "setup-grafana-credentials.sh"
Cohesion: 0.33
Nodes (11): Quarentena e regras dinâmicas (4b), Tipos especiais EC/EE/EG/AE, processar_pdf — extração + renomeação (mod_renomear_empenho), Manual de Uso — Renomeador de Empenho, Extração de texto com fallback pymupdf → pdfplumber → OCR → pikepdf, Quarentena reprocessável (PLANO 4b), Regex dinâmicas de extração (tb_regex_regras), Reprocessar fila em lote sem reiniciar (+3 more)

### Community 98 - "@playwright/test"
Cohesion: 0.47
Nodes (11): compose.yml - definicao dos servicos LGTM, Servico Grafana (3000, admin master/master via env), Servico Loki (3100, logs), Servico Mimir (9009, metricas compat. Prometheus), Servico OTel Collector (4317 gRPC / 4318 HTTP / 8888-8889), Servico Tempo (3200, traces; 4317 interno via rede Docker), datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim), loki-config.yml - TSDB schema v13, compactor com retencao 7d (+3 more)

### Community 99 - "configurar_docker_windows"
Cohesion: 0.35
Nodes (10): check_docker(), check_grafana(), check_loki(), check_mimir(), check_otel_collector(), check_tempo(), main(), print_header() (+2 more)

### Community 100 - "_SMTPOk"
Cohesion: 0.18
Nodes (10): description, devDependencies, @playwright/test, name, private, scripts, e2e:headed, e2e:report (+2 more)

### Community 101 - "sgbd_ativo"
Cohesion: 0.25
Nodes (11): _conta_auditoria(), _orquestrar_resumo_dados(), Coleta os 9 contadores do Resumo — 5 base + fila impressão, quarentena, pdf…, contar_registros(), get_auditoria_connection(), get_tabelas_auditoria(), podar_registros(), Lists the per-module audit tables found in the audit database. Retorna os nomes… (+3 more)

### Community 102 - "_porta_valida"
Cohesion: 0.18
Nodes (6): Dialogo, Standard dialog + themed card as a context-manager class. Classe gerenciadora…, Enters dialog + card contexts; returns `(dlg, card)`. Sequência de criação…, Closes the card and dialog contexts (reverse order)., Opens the dialog (no-op quando o contexto ainda não entrou)., Closes the dialog (no-op quando o contexto ainda não entrou).

### Community 103 - "get_connection"
Cohesion: 0.24
Nodes (11): _baixar_arquivo(), _cancelar_grupo(), _card_grupo(), baixar_selecionados(), baixar_selecionados_zip(), _selecionados_fisicos(), Renders one PEDIDO card (all files of the submission) with actions. O pedido é…, Downloads one file of a pedido (with watermark applied at download time). Baixa… (+3 more)

### Community 104 - "mes_atual"
Cohesion: 0.29
Nodes (9): Spectre 0.5.9 (rota dedicada, leve, MIT), caminho_css(), injetar_framework(), _log(), montar_rotas_static(), Serves the embedded CSS frameworks (Bootstrap, Bulma, DaisyUI, Pico, Picnic)…, Makes /css/frameworks/* serve the local CSS files for the whole app. Registra a…, Return HTTP URL of the CSS file (None lists the available frameworks). Devolve… (+1 more)

### Community 105 - "Graphify Query BFS DFS"
Cohesion: 0.38
Nodes (9): check_docker(), print_header(), start.sh script, show_help(), show_logs(), show_status(), start_stack(), stop_stack() (+1 more)

### Community 106 - "_global_setup.js"
Cohesion: 0.31
Nodes (10): DOC_0201.pdf - fixture PDF ficticio de empenho (massa de teste), EC_24.pdf - fixture PDF ficticio de empenho (massa de teste), EE_9570.pdf - fixture PDF ficticio de empenho (massa de teste), EG_89.pdf - fixture PDF ficticio de empenho (massa de teste), Pasta de testes assets/test (README), Convencoes obrigatorias de teste (standalone, exit-code, data-testid, docstring bilingue, sem destruicao), Infra E2E Playwright (e2e specs, helpers.js, _global_setup.js, playwright.config.js, package.json), INTRANET_FORCE_SQLITE=1 - suite roda forcando SQLite (+2 more)

### Community 107 - "arquitetura_de_software_das/index.md"
Cohesion: 0.24
Nodes (9): contextlib, aplicar(), _get_context(), Patches NiceGUI timers to tolerate page teardown (no "parent slot deleted"). O…, Returns nullcontext instead of raising when the parent slot is gone., Stops the timer when its parent slot was deleted (page navegada/fechada). Um…, Aplica os patches no NiceGUI (idempotente)., _should_stop() (+1 more)

### Community 108 - "confirmar_rascunho"
Cohesion: 0.22
Nodes (10): _construir_dashboard(), _contar_fila_para_autorizar(), _eh_autorizador_impressao(), Card de métrica do Resumo — ícone ampliado + número lateral (4 dígitos, >9999)…, Constrói o conteúdo da Home (banner + resumo dinâmico + feed)., Verifica se o usuário é responsável por autorizar impressão (qualquer…, Conta solicitações pendentes que o usuário pode autorizar (por…, _stat() (+2 more)

### Community 109 - "_admin_configuracoes"
Cohesion: 0.24
Nodes (10): listar_postagens(), _ordem_sql(), publicar_postagem(), Converte ordem ('ASC'/'DESC') para SQL seguro., Lists posts (id, titulo, conteudo, autor, data_criacao) with ordering. Lista…, Reativa/publica uma postagem despublicada (ativo=1)., _painel_despublicadas(), _lista_despublicadas() (+2 more)

### Community 110 - "_card_grupo"
Cohesion: 0.42
Nodes (8): check_docker(), check_grafana(), main(), print_header(), restart_grafana(), setup-grafana-credentials.sh script, show_credentials(), update_grafana_password()

### Community 111 - "aplicar_banco"
Cohesion: 0.22
Nodes (7): { login }, { test, expect }, { defineConfig }, path, root, venvPython, @playwright/test

### Community 112 - "Registro de Mudanças"
Cohesion: 0.50
Nodes (8): check(), main(), Teste funcional do módulo Auditoria (rastreabilidade LGPD). Roda manualmente:…, _testar_acesso(), _testar_audit_log(), _testar_indices(), _testar_poda(), _testar_prefs_campos()

### Community 114 - "_admin_responsaveis"
Cohesion: 0.22
Nodes (9): Audit Log Para Registrar Auditoria, Banco Exclusivo Auditoria db mod auditoria, Tabela Por Modulo Produtor tb auditoria modulo, Bd Criador Legado Morto, Bd Manipulador Unico Ponto Acesso DB, Renomeacao Db Manipulador Para Bd Manipulador Auditoria, CrudBase Base CRUD WAL, Visualizador Auditoria Somente Leitura (+1 more)

### Community 115 - "_log"
Cohesion: 0.31
Nodes (9): Intranet Modular — Referência de API e Código, audit_log — auditoria central com hash SHA-256, Acesso central bd_conexao (get_config/set_config), Módulo mod_auditoria, Módulo mod_gest_cad_usuario, Módulo núcleo mod_intranet, Módulo mod_renomear_empenho, Tabelas por banco — um database por módulo (+1 more)

### Community 116 - "02_varredura.spec.js"
Cohesion: 0.25
Nodes (8): listar_usuarios_ativos(), Lista usuários ativos para seleção nas telas dos módulos. Delega ao módulo de…, _admin_responsaveis(), atualizar(), criar(), _excluir_resp(), Admin sub-tab: grants authorization power to registered users. Sub-aba de…, Removes an authorization grant. Remove um vínculo de autorização.

### Community 117 - "expirar_rascunhos_e_impressos"
Cohesion: 0.29
Nodes (6): iniciar_servidor(), main(), montar_pagina(), page, Teste de viabilidade: ui.mermaid no NiceGUI 3.15 (renderização em navegador).…, playwright_sync_api

### Community 118 - "Contrato Config Central Get Config Modulo Chave"
Cohesion: 0.43
Nodes (3): agendadores em segundo plano (APScheduler), autenticação e sessões (cookie HTTP-Only), configuração central (tb_config)

### Community 119 - "Isolamento Um Banco Por Modulo Sem Cross Query"
Cohesion: 0.25
Nodes (8): _ao_sinal(), _encerrar(), parar_servidor(), Para o servidor de documentação (idempotente, fail-soft). Encerra o…, finalizar_otel(), Shutdown OpenTelemetry SDK. Finaliza o SDK do OpenTelemetry., encerrar_agendador(), Para o agendador de forma ordenada (idempotente, fail-soft). Desliga o…

### Community 120 - "iniciar.sh"
Cohesion: 0.32
Nodes (7): montar_rotas_ativas(), _normalizar_rota(), Dynamic module page-route registration for NiceGUI (custom slugs persist).…, Normalizes a route: leading '/', lowercase, no spaces/duplicate slashes.…, Registers a module page route in NiceGUI (idempotent). Registra a rota de um…, Re-registers persisted custom routes from tb_modulos (idempotent). Lê…, registrar_modulo()

### Community 121 - "_encerrar"
Cohesion: 0.36
Nodes (8): _agregar_impressao(), Runs a print aggregation (status='impresso') over a period. `agrupar_por`:…, Builds the print report (status='impresso') for a period. Dicionário com totais…, relatorio_impressao(), _por_autorizador(), _por_impressor(), _por_secretaria(), _por_setor()

### Community 122 - "page_admin_modulo"
Cohesion: 0.25
Nodes (8): cancelar_rascunho(), expirar_rascunhos_e_impressos(), obter_rascunho(), Removes a file from disk if it exists (fail-soft). Returns True if removed.…, Fetches one upload draft as a dict (all columns) or None. Busca um rascunho de…, Removes the draft and its server file (user gave up before confirming). Remove…, Scheduled cleanup (every 1 min): - drafts whose expira_em has passed -> remove…, _remover_arquivo_se_existir()

### Community 123 - "test_seg_aplicar.py"
Cohesion: 0.29
Nodes (7): Watch Mode Auto Rebuild, Post Commit Hook, Graphify Explain Node, Graphify Path Shortest Path, Graphify Query BFS DFS, Incremental Update Reextract Changed, Graphify Full Pipeline

### Community 124 - "registrar_hook_config"
Cohesion: 0.29
Nodes (6): { execSync }, path, root, script, venvPython, ref_child_process

### Community 125 - "opencode.json"
Cohesion: 0.43
Nodes (6): check(), main(), n_paginas(), pdf_sintetico(), Teste do módulo Editor de PDF (Fase 5.6) — rodar manualmente: python…, mod_edit_pdf

### Community 126 - "Extraction Confidence Rubric"
Cohesion: 0.29
Nodes (6): _conteudo(), restaurar(), _mudou(), _mudou_tamanho(), Restores the module's 6 appearance keys to the provided defaults. Restaura os…, restaurar_tema()

### Community 127 - "mod_auditoria/__init__.py"
Cohesion: 0.33
Nodes (6): _admin_relatorio(), gerar(), _prazo_fixo(), Renders a small report table with header + rows (or an empty note). Monta um…, Admin sub-tab: print report by fixed monthly periods or custom calendar range,…, _tabela_relatorio()

### Community 128 - "teste_boot.py"
Cohesion: 0.33
Nodes (6): page_login(), tentar_login(), incrementar_contador_acessos(), Increments the global access counter — login-only, never navigation/refresh.…, Placeholder hook para metricas de login via OTel. Sobrescrita dinamicamente por…, registrar_login_observabilidade()

### Community 129 - "_admin_relatorio"
Cohesion: 0.33
Nodes (4): Modulo, Module registry entry (tb_modulos). EN: Represents a registered module in the…, Returns all registered modules, ordered by `ordem` then name. EN: Returns…, Returns the module with the given key or None if not found. EN: Single module…

### Community 130 - "mod_edit_pdf/__init__.py"
Cohesion: 0.40
Nodes (4): Creates a new SQLAlchemy Session bound to a module database engine. Uma Session…, Lazily acquires a session if one was not provided at construction., sessaodb(), Session

### Community 131 - "mod_gest_cad_usuario/__init__.py"
Cohesion: 0.33
Nodes (6): _eh_admin_do_modulo(), eh_responsavel_autorizacao(), _pode_autorizar(), System-wide admin OR the print module admin. Admin geral do sistema OU…, Only the responsável for the link OR the module admin may authorize. Só…, Checks whether user_nome is an authorizer for the department/unit. Verifica se…

### Community 132 - "precisa_trocar_senha"
Cohesion: 0.33
Nodes (6): kbp-web-design (definição do subagente), Subagente kbp-web-design, requirements.txt (dependências de execução), mkdocs / mkdocs-material (runtime), NiceGUI 3.15.0, SQLAlchemy 2.x + psycopg2 (PostgreSQL opcional)

### Community 133 - "_confirmar_fallback_sqlite"
Cohesion: 0.40
Nodes (3): _campo_data(), _ao_escolher(), _fmt_data()

### Community 134 - "mod_renomear_empenho/__init__.py"
Cohesion: 0.50
Nodes (4): _log(), main(), Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log., Runs the seed, creating each how-to post and reporting the result. Executa o…

### Community 135 - "iniciar"
Cohesion: 0.50
Nodes (3): { login, coletarErros, errosFatais }, ROTAS, { test, expect }

### Community 137 - "Wiki Export Agent Crawlable"
Cohesion: 0.50
Nodes (4): Backend Duplo SQLite PostgreSQL Um Database Por Modulo, Isolamento Um Banco Por Modulo Sem Cross Query, Motor PDF Compartilhado Pdf Operacoes Op Reutilizaveis, Lingua Ubiqua DDD Portugues BR

### Community 138 - "Cross Repo Merge"
Cohesion: 0.50
Nodes (3): INTRANET_FORCE_SQLITE, INTRANET_SEM_OTEL, iniciar.sh script

### Community 140 - "God Nodes Community Detection"
Cohesion: 0.50
Nodes (4): auto_iniciar_otel(), iniciar_otel_stack(), Start the OTel LGTM stack. Inicia a stack OTel LGTM. Retorna (sucesso,…, Auto-start OTel stack if Docker is available. Auto-inicia a stack OTel se o…

### Community 142 - "docs/inicio_rapido_otel.md"
Cohesion: 0.67
Nodes (3): iniciar_agendador(), _passo_agendador(), Delega ao rotinas: um job de backup POR módulo (intervalo individual…

## Knowledge Gaps
- **126 isolated node(s):** `{ execSync }`, `path`, `root`, `script`, `venvPython` (+121 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1473 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `audit_log()` connect `botao` to `mod_solicita_impressao/bd_manipulador.py`, `ativacao.py`, `os`, `ui_comum.py`, `mostrar_administracao`, `rotinas.py`, `audit_log`, `test_blog_editor_imagens.py`, `mod_gest_cad_usuario/bd_manipulador.py`, `pdf_operacoes.py`, `Repositorio`, `test_cobertura_total.py`, `_ler_telas`, `docker_detector.py`, `test_ativacao.py`, `mod_intranet/telas.py`, `_FormatadorBlog`, `_CursorPostgres`, `FormularioBuilder`, `repositorio.py`, `pesquisar_levantamento`, `home_visual.py`, `verifica_ui_comum.py`, `test_solicita_impressao.py`, `docker_instalado`, `_El`, `tema_css.py`, `mod_solicita_impressao/telas_administracao.py`, `Registro de Mudanças`, `opencode.json`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `Manual de Uso — Renomeador de Empenho` connect `setup-grafana-credentials.sh` to `_construir_dashboard`, `_log`, `get_config`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `mod_intranet — Núcleo Intranet` connect `FormularioBuilder` to `_FormatadorBlog`, `confirmar_lote`, `mod_gest_cad_usuario/bd_manipulador.py`, `Pasta de testes assets/test (README)`, `port_scanner.py`, `botao`, `repositorio.py`, `get_config`, `App`, `docker_detector.py`, `main.py`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **What connects `{ execSync }`, `path`, `root` to the rest of the system?**
  _126 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `mod_solicita_impressao/bd_manipulador.py` be split into smaller, more focused modules?**
  _Cohesion score 0.034873949579831934 - nodes in this community are weakly interconnected._
- **Should `ativacao.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04057017543859649 - nodes in this community are weakly interconnected._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.0499866345896819 - nodes in this community are weakly interconnected._