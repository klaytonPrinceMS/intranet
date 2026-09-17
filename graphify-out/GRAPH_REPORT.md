# Graph Report - intranet  (2026-09-17)

## Corpus Check
- 235 files · ~295,267 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 30 file(s) not represented in the graph (top: .css 18, (none) 9, .ico 1)

## Summary
- 3286 nodes · 7940 edges · 141 communities (122 shown, 19 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 483 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Editor PDF Testes
- QA Diagnostico e Seeds
- Empenho BD Manipulador
- Gestao Usuarios Core
- Painel Admin Auditoria
- Quarentena e Campos Busca
- Diretrizes de Desenvolvimento
- Configs Especificas Auditoria
- Testes Paridade SQLite/Postgres
- Smoke Campos Senha
- Testes Funcionais Auditoria
- Cadastros Solicitacao Impressao
- Testes Classes CRUD
- Testes Tema Central
- Menu e Ferramentas UI
- Sessoes e Botoes Admin
- Testes Rodape TestID
- Pesquisa Levantamento Empenhos
- Camada Central de Dados
- Testes Solicitacao Impressao
- Scripts Ativacao Docker
- App Legado Renomeador
- Logger Auditoria e Blog
- Relatorios e Cadastros Admin
- Regras de Permissao Blog
- Autenticacao e Downloads
- Config e HTML Blog
- Docs Requisitos e Riscos
- Testes Integracao OTel
- Rotinas Expirar e Podar
- Testes Levantamento Empenho
- Testes Email Docs OTel
- Paginas Principais do App
- Tema Escuro e Sessoes
- Email e Lotes Impressao
- Testes Ativacao Ativos
- Testes Editor Blog
- Tela Busca de Logs
- Nucleo do Modulo Blog
- Proxy Conexao Postgres
- Testes Editor e Carrossel
- Testes Fluxo Blog
- FormularioBuilder UI
- Config Intranet e Grafana
- CrudBase Legado
- Integracao OpenTelemetry
- Scripts Docker e OTel
- QA Empenho Playwright
- Fluxo de Grupos de Impressao
- Cotas e Paginas Impressao
- Estilizacao Home Visual
- Provisionamento Grafana
- Fabrica de Documentos
- Scanner de Portas
- Exibicao Carrossel Blog
- CLI Aplicar Banco
- Perfis e Seed Auditoria
- Grants de Acesso Modulos
- Dialogos de Sessoes
- Probes Portas OTel/Postgres
- Frameworks CSS Embarcados
- Testes Flags Permissao
- Tabelas e Listas UI
- Verificacao UI Comum
- Renderizacao Feed Blog
- Visual Renomear Empenho
- Specs E2E Login/Header
- E2E Admin e Lote Empenhos
- Contexto Sessoes LGPD
- Marca Dagua e Listas
- Construtor Documentacao
- Hora Servidor NTP
- Testes Fabrica Documentos
- Sanitizacao e Metricas Blog
- Instrumentacao OTel App
- Confirmacao Impressao Admin
- Dashboards e Stack LGTM
- Spec E2E Editor Blog
- Wrappers Elementos NiceGUI
- Registro de Modulos
- Consumo Cotas Mensais
- Wrappers Dialogos NiceGUI
- Boot Config CLI
- Injetores Framework Visual
- Formatacao HTML Blog
- Admin Secretarias e Setores
- Compose LGTM
- Verificar Credenciais
- Pacote Playwright E2E
- Models SQLAlchemy
- Ferramentas Seguranca
- Dashboard Resumo Home
- Download Grupos Empenho
- Tela Solicitacao Impressao
- Nova Solicitacao Upload
- Servir Frameworks CSS
- Start.sh Stack
- Fixtures PDF e Infra Teste
- Patches Timer NiceGUI
- Manuais e Licoes Aprendidas
- Setup Credenciais Grafana
- Config E2E Exclusao Blog
- Mocks de Envio Email
- Rotinas de Encerramento
- Registro Rotas Modulos
- Relatorios Agregacao Impressao
- Admin Solicitacoes Sub-abas
- Global Setup Playwright
- Admin Cotas Sub-aba
- Admin Responsaveis Sub-aba
- Login e Sessao em Banco
- Contadores Auditoria
- Telas Controle Acesso
- Dialogos Troca Credenciais
- Admin Relatorio Sub-aba
- Painel Impressoras
- Mermaid no Blog
- Testes Dashboard
- Seed Postagens Blog
- Spec E2E Varredura
- Servidor SMTP de Teste
- Riscos IA/ML
- Script Iniciar
- Painel Admin Modulos
- Probes Postgres
- Auto Start OTel
- Sessao SQLAlchemy Lazy
- Config Plugin opencode
- Convencoes Codigo Docs
- Servir JS Impressao
- Init Modulo Auditoria
- Rotas Imagens Blog
- Init Modulo Editor PDF
- Init Modulo Gestao Usuarios
- Flag Troca Credenciais
- Chaves Desativadas
- Init Nucleo Intranet
- Hook Login Observabilidade
- Init Modulo Renomear Empenho
- Init Modulo Solicitacao Impressao

## God Nodes (most connected - your core abstractions)
1. `audit_log()` - 118 edges
2. `notificar()` - 101 edges
3. `botao()` - 98 edges
4. `get_config()` - 97 edges
5. `usuario_logado()` - 96 edges
6. `set_config()` - 84 edges
7. `get_connection()` - 62 edges
8. `get_connection()` - 62 edges
9. `mostrar_tela()` - 60 edges
10. `mostrar_tela()` - 55 edges

## Surprising Connections (you probably didn't know these)
- `A1 — storage_secret com fallback fraco (main.py:616)` --conceptually_related_to--> `pagina_restrita()`  [INFERRED]
  docs/seguranca/auditoria_menu_2026-09-12.md → mod_intranet/telas.py
- `datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim)` --conceptually_related_to--> `auto_iniciar_otel()`  [INFERRED]
  assets/docker/config/grafana-provisioning/datasources/datasources.yml → mod_intranet/docker_detector.py
- `CSS Frameworks Embarcados (README)` --references--> `_page_empenho_forcado()`  [EXTRACTED]
  assets/css/frameworks/README.md → main.py
- `mod_blog — Módulo Blog` --references--> `mover_mermaid_para_fim()`  [EXTRACTED]
  docs/modulos/blog.md → mod_blog/bd_manipulador.py
- `Modo carrossel do Blog (rotação automática)` --references--> `renderizar_postagens()`  [EXTRACTED]
  docs/modulos/blog.md → mod_blog/telas.py

## Import Cycles
- 3-file cycle: `mod_intranet/autenticacao.py -> mod_intranet/bd_conexao.py -> mod_intranet/tema_modulo.py -> mod_intranet/autenticacao.py`
- 4-file cycle: `mod_intranet/autenticacao.py -> mod_intranet/bd_manipulador.py -> mod_intranet/bd_conexao.py -> mod_intranet/tema_modulo.py -> mod_intranet/autenticacao.py`

## Hyperedges (group relationships)
- **Subagentes kbp-* (padrão kbp-*)** — opencode_agent_kbp_commit_kbp_commit, opencode_agent_kbp_devsecops_kbp_devsecops, opencode_agent_kbp_doc_kbp_doc, opencode_agent_kbp_doc_teste_kbp_doc_teste, opencode_agent_kbp_qa_kbp_qa, opencode_agent_kbp_web_design_kbp_web_design [INFERRED 0.95]
- **Usuários pré-cadastrados (seed) e seus perfis** — agents_seed_master, agents_seed_qacomum, agents_seed_qamaster, agents_perfil_administrador_geral, agents_perfil_comum [EXTRACTED 1.00]
- **Pipeline do skill graphify (SKILL + references)** — opencode_skills_graphify_skill, opencode_skills_graphify_skill_graphify, opencode_skills_graphify_references_extraction_spec, opencode_skills_graphify_references_query, opencode_skills_graphify_references_update, opencode_skills_graphify_references_add_watch, opencode_skills_graphify_references_exports, opencode_skills_graphify_references_github_and_merge, opencode_skills_graphify_references_hooks, opencode_skills_graphify_references_transcribe [EXTRACTED 1.00]
- **Grafana OTel LGTM - stack de observabilidade da intranet** — assets_docker_readme_lgtm_stack, assets_docker_compose, assets_docker_compose_otel_collector, assets_docker_compose_loki, assets_docker_compose_tempo, assets_docker_compose_mimir, assets_docker_compose_grafana, assets_docker_config_otel_collector_config, assets_docker_config_loki_config, assets_docker_config_tempo_config, assets_docker_config_mimir_config, assets_docker_config_grafana_provisioning_datasources_datasources, assets_docker_config_grafana_provisioning_dashboards_dashboards [EXTRACTED 1.00]
- **CSS frameworks para comparacao visual via rota dedicada /renomear-empenho-{nome}** — assets_css_frameworks_readme_pic_padrao, assets_css_frameworks_readme_bootstrap, assets_css_frameworks_readme_bulma, assets_css_frameworks_readme_daisyui, assets_css_frameworks_readme_pico, assets_css_frameworks_readme_picnic, assets_css_frameworks_readme_spectre, assets_css_frameworks_readme_chota, assets_css_frameworks_readme_milligram, assets_css_frameworks_readme_skeleton, assets_css_frameworks_readme_water, assets_css_frameworks_readme_mvp, assets_css_frameworks_readme_tachyons, assets_css_frameworks_readme_uikit, assets_css_frameworks_readme_foundation, assets_css_frameworks_readme_semantic, assets_css_frameworks_readme_materialize, assets_css_frameworks_readme_primer [EXTRACTED 1.00]
- **Fixtures PDF ficticios de empenho (massa de teste QA para o editor de PDF)** — assets_test_pdf_doc_0201, assets_test_pdf_ec_24, assets_test_pdf_ee_9570, assets_test_pdf_eg_89, assets_test_fabrica_documentos [INFERRED 0.85]
- **camada de dados por módulo (um banco WAL por módulo, acesso só via bd_manipulador)** — docs_analise_mod_intranet_mod_intranet, docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario, docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_renomear_empenho_mod_renomear_empenho, docs_analise_mod_auditoria_mod_auditoria, docs_analise_mod_solicita_impressao_mod_solicita_impressao, docs_arquitetura_de_software_das_index_bd_manipulador_padrao, docs_ferramentas_graphify_crud_base, docs_configuracoes_configuracao_central [INFERRED 0.85]
- **fluxo de auditoria LGPD (escrita audit_log → trilha tb_auditoria_<modulo>)** — docs_analise_mod_intranet_mod_intranet, docs_analise_mod_auditoria_mod_auditoria, docs_analise_mod_auditoria_trilha_auditoria_lgpd, docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario, docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_renomear_empenho_mod_renomear_empenho, docs_analise_mod_solicita_impressao_mod_solicita_impressao [INFERRED 0.95]
- **segurança e conformidade (LGPD, sessões, perfis e risco do segredo)** — docs_arquitetura_de_software_das_index_autenticacao_sessoes, docs_analise_mod_auditoria_trilha_auditoria_lgpd, docs_analise_de_risco_index_storage_secret_risco, docs_2_levantamento_requisitos_index_perfis_usuario, docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario [INFERRED 0.75]
- **Módulos em operação (hub intranet modular)** — docs_modulos_intranet_mod_intranet, docs_modulos_gest_cad_usuario_mod_gest_cad_usuario, docs_modulos_blog_mod_blog, docs_modulos_edit_pdf_mod_edit_pdf, docs_modulos_renomear_empenho_mod_renomear_empenho, docs_modulos_auditoria_mod_auditoria, docs_modulos_solicitacao_impressao_mod_solicita_impressao [EXTRACTED 1.00]
- **Perfis globais do sistema (PERFIS_GLOBAIS)** — docs_manual_de_uso_administrador_index_administrador_geral, docs_manual_de_uso_administrador_index_administrador_modulo, docs_manual_de_uso_usuario_comum_index_comum [EXTRACTED 1.00]
- **Rotina DevSecOps (SAST + dependências + segredos)** — docs_seguranca_ferramentas_bandit, docs_seguranca_ferramentas_semgrep, docs_seguranca_ferramentas_pip_audit, docs_seguranca_ferramentas_safety, docs_seguranca_ferramentas_gitleaks [EXTRACTED 1.00]

## Communities (141 total, 19 thin omitted)

### Community 0 - "Editor PDF Testes"
Cohesion: 0.04
Nodes (105): check(), main(), n_paginas(), pdf_sintetico(), Teste do módulo Editor de PDF (Fase 5.6) — rodar manualmente: python…, mod_edit_pdf, _cfg(), cfg_lote_arquivos() (+97 more)

### Community 1 - "QA Diagnostico e Seeds"
Cohesion: 0.04
Nodes (60): Seed of "how-to" blog posts for the common user (Editor PDF, Print Request,…, mostra(), QA Diagnostico: fluxo salvar_configs -> reload -> ler valores. Testa se…, Garante as credenciais dos usuários QA usados nos testes E2E. EN: Ensures the…, mostra(), Nome do usuário no menu superior — botão único sempre visível. EN: Header user-…, Rodapé escondido com reveal no hover — bloco FOOTER. EN: Auto-hide footer —…, Teste unitário/integração das rotinas de backup (mod_intranet/rotinas.py).… (+52 more)

### Community 2 - "Empenho BD Manipulador"
Cohesion: 0.05
Nodes (87): anotar_arquivos(), arquivo_ja_processado(), arquivo_pendente(), _arquivo_registrado_no_bd(), atualizar_levantamento_renomeado(), _basename_sem_ext(), _campos_busca_ativos(), detectar_documentos_no_pdf() (+79 more)

### Community 3 - "Gestao Usuarios Core"
Cohesion: 0.05
Nodes (82): garantir(), Idempotently fixes QA users' passwords, profiles and change flag., alterar_senha_admin(), _audit(), bloquear_usuario(), _central(), _conexao_cruzada(), contar_sessoes_ativas() (+74 more)

### Community 4 - "Painel Admin Auditoria"
Cohesion: 0.04
Nodes (74): _btn_cls(), _btn_style(), _cfg(), mostrar_administracao(), Audit module administration panel. Painel de administração do módulo Auditoria…, Fetch an auditoria config value, returning default on failure., Fetch a theme config value, returning default on failure., Return CSS classes for button size. (+66 more)

### Community 5 - "Quarentena e Campos Busca"
Cohesion: 0.05
Nodes (74): test_campos_busca(), alternar_regra(), _conn(), excluir_campo_busca(), extrair_numero(), listar_arquivos_auditoria(), listar_campos_busca(), listar_quarentena() (+66 more)

### Community 6 - "Diretrizes de Desenvolvimento"
Cohesion: 0.05
Nodes (75): AGENTS.md (fonte de verdade do desenvolvimento), Anti-disconnect: handlers nunca bloqueiam o event-loop, Arquitetura modular (mod_*) com bancos isolados por módulo, CrudBase (padrão obrigatório de acesso a dados), init_db (seed idempotente de usuários), Língua Ubíqua do DDD (vocabulário de negócio em PT-BR), Entry point único main.py, Módulo mod_auditoria (+67 more)

### Community 7 - "Configs Especificas Auditoria"
Cohesion: 0.07
Nodes (66): tentar_login(), Seeds the module version key (`versao_modulo:auditoria`) in tb_config., _semear_versao_modulo(), _resetar(), _salvar(), Persiste as alterações do card 'Configurações específicas' e recarrega. Grava…, Restaura os valores padrão do card 'Configurações específicas'. Grava os…, _resetar_configs() (+58 more)

### Community 8 - "Testes Paridade SQLite/Postgres"
Cohesion: 0.05
Nodes (55): Teste unitário da paridade SQLite/PostgreSQL (mod_intranet/banco_conexao.py).…, Cobertura total: smoke de import + contrato de TODAS as funcoes/classes usadas.…, Ordem do menu hambúrguer — padrão + persistência após reorder + restart. EN:…, datetime, importlib, banco_modulo(), conexao_central(), definir_banco_tipo() (+47 more)

### Community 9 - "Smoke Campos Senha"
Cohesion: 0.05
Nodes (49): estado(), Real-NiceGUI smoke test for password fields via `ui_comum.campo_texto`. Smoke…, Visual state of a real NiceGUI element (props/classes/style/children). Estado…, index(), page, math, _gest_bloq(), User management screen — soft CRUD with per-module access control. Tela de… (+41 more)

### Community 10 - "Testes Funcionais Auditoria"
Cohesion: 0.06
Nodes (51): check(), main(), Teste funcional do módulo Auditoria (rastreabilidade LGPD). Roda manualmente:…, _testar_acesso(), _testar_audit_log(), _testar_indices(), _testar_poda(), _testar_prefs_campos() (+43 more)

### Community 11 - "Cadastros Solicitacao Impressao"
Cohesion: 0.07
Nodes (56): teste_cadastros_e_cotas(), _audit(), cancelar_solicitacao(), criar_impressora(), criar_responsavel(), criar_secretaria(), criar_setor(), definir_cota() (+48 more)

### Community 12 - "Testes Classes CRUD"
Cohesion: 0.05
Nodes (27): _campo_impar(), Verificação das classes novas do núcleo (CrudBase, ui_painel, ui_form, ui_comum…, BotaoFabrica, CampoBase, CampoCor, CampoSelecao, CampoTexto, card_config() (+19 more)

### Community 13 - "Testes Tema Central"
Cohesion: 0.06
Nodes (47): checar(), main(), Teste standalone do helper central de tema (mod_intranet/tema_modulo.py).…, config_backend(), Returns the backend selector as a dict (`banco_tipo`, `postgres_url`). Usado…, Persists the backend selector (`banco_tipo`, `postgres_url`). Grava no arquivo…, salvar_backend(), _botao_padrao() (+39 more)

### Community 14 - "Menu e Ferramentas UI"
Cohesion: 0.06
Nodes (48): menu_modulo(), Builds the module menu tabs (icon above, label below). Cria a barra de abas de…, hash_arquivo(), Retorna hash SHA-256 de um arquivo., ferramenta_cortar(), ferramenta_fontes(), ferramenta_juntar(), _ferramenta_nome() (+40 more)

### Community 15 - "Sessoes e Botoes Admin"
Cohesion: 0.08
Nodes (50): _painel_sessoes(), refresh(), Active sessions tab with per-row terminate actions. Aba Sessões Ativas:…, botao(), botao_icone(), Builds the single standardized button (delegates to `BotaoFabrica`). Wrapper…, Icon-only row-action button (themed or white header variants). Atalho para…, criar_solicitacao() (+42 more)

### Community 16 - "Testes Rodape TestID"
Cohesion: 0.05
Nodes (34): _botoes_testid(), check(), clicar(), main(), Teste de integração headless do rodapé padrão (ui_comum) — delta a1b1650. Cobre…, _varrer(), achar_botoes(), achar_campos() (+26 more)

### Community 17 - "Pesquisa Levantamento Empenhos"
Cohesion: 0.07
Nodes (18): _definicoes_filtrar(), _ler(), _ler_admin(), _ler_bd(), _ler_rotinas(), _ler_telas(), Pesquisa Navegar assíncrona — fiação estática sem servidor., tb_levantamento + FTS no banco do módulo, fallback LIKE, presença. (+10 more)

### Community 18 - "Camada Central de Dados"
Cohesion: 0.08
Nodes (24): _log(), Centralised data access layer for mod_intranet (and module DBs). Wraps a…, Closes the session and releases the connection., Runs a SELECT on the bound database; returns rows as dicts. Executa SQL de…, Runs a DML statement on the bound database; returns rowcount. Executa SQL de…, Returns the last autoincrement id inserted on the bound database. Devolve…, Returns the value for a configuration key or `padrao` if not found. EN: Reads a…, Inserts or replaces a configuration key (upsert ON CONFLICT). EN: Upserts a… (+16 more)

### Community 19 - "Testes Solicitacao Impressao"
Cohesion: 0.11
Nodes (44): criar_pdf_teste(), main(), Teste do módulo Solicitação de Impressão (mod_solicita_impressao). Valida:…, Gera um PDF simples de n_paginas para teste (PyMuPDF)., teste_contagem_e_formula(), teste_excedente(), teste_fluxo(), teste_fluxo_grupo() (+36 more)

### Community 20 - "Scripts Ativacao Docker"
Cohesion: 0.07
Nodes (45): _abre_fecha(), _aguardar_container(), aplicar_portas(), barra(), _compose_cmd(), configurar_docker_windows(), _container_existe(), docker_instalado() (+37 more)

### Community 21 - "App Legado Renomeador"
Cohesion: 0.08
Nodes (21): App, arquivo_esta_estavel(), buscar_campo(), extrair_dados(), extrair_texto_primeira_pagina(), montar_novo_nome(), obter_prefixo(), Renomeador de Empenhos - Prefeitura de Monte Santo de Minas… (+13 more)

### Community 22 - "Logger Auditoria e Blog"
Cohesion: 0.08
Nodes (43): _sempre_falha(), _log(), Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log., atualizar_postagem(), criar_comentario(), despublicar_postagem(), excluir_postagem(), excluir_postagens_em_lote() (+35 more)

### Community 23 - "Relatorios e Cadastros Admin"
Cohesion: 0.07
Nodes (41): _admin_relatorio(), gerar(), _prazo_fixo(), _admin_responsaveis(), atualizar(), criar(), _admin_secretarias(), atualizar() (+33 more)

### Community 24 - "Regras de Permissao Blog"
Cohesion: 0.06
Nodes (37): _eco_regex(), _soma(), _pode_publicar(), Regra do módulo: usuário COMUM só LÊ o blog. Publicar/comentar/excluir é…, admin_tela(), decorator(), wrapper(), decorator() (+29 more)

### Community 25 - "Autenticacao e Downloads"
Cohesion: 0.08
Nodes (41): bcrypt, baixar_pdf_impressao(), Rota de download do PDF da solicitação (com marca d'água se ativa). Protegida:…, autenticar(), chaves_ativas(), chaves_desativadas(), editar_meu_perfil(), eh_admin_do_modulo() (+33 more)

### Community 26 - "Config e HTML Blog"
Cohesion: 0.08
Nodes (40): html, html_parser, definir_carrossel_postagens_ids(), definir_postagem_unica_id(), get_config_local(), _largura_imagem(), _log(), _nome_usuario_seguro() (+32 more)

### Community 27 - "Docs Requisitos e Riscos"
Cohesion: 0.10
Nodes (17): perfis de usuário (comum, administrador_modulo, administrador_geral), risco storage_secret placeholder (main.py), mod_auditoria (trilha de auditoria LGPD), trilha de auditoria LGPD (tb_auditoria_<modulo>), mod_blog, mod_edit_pdf (edição de PDF), mod_gest_cad_usuario (gestão de usuários), mod_intranet (núcleo da intranet) (+9 more)

### Community 28 - "Testes Integracao OTel"
Cohesion: 0.10
Nodes (37): main(), Test script for OTel LGTM stack integration. Script de teste para verificar se…, Test Docker detection., Test OTel stack status., Test OTel info display., Test OTel integration import., test_docker_detection(), test_otel_import() (+29 more)

### Community 29 - "Rotinas Expirar e Podar"
Cohesion: 0.08
Nodes (38): podar_registros(), Remove registros mais antigos que `dias` em todas as tabelas de auditoria.…, expirar_imagens_orfas(), Remove imagens não concretizadas em postagem (órfãs há +5 min). Uma imagem é…, cfg_expiracao_min(), expirar_antigos(), File lifetime in minutes inside editorPDF (`editar_pdf_expiracao_min`, min 1)., Expiração automática (roda sem usuário logado — basta o servidor vivo). Remove… (+30 more)

### Community 30 - "Testes Levantamento Empenho"
Cohesion: 0.08
Nodes (32): Levantamento do Renomear Empenhos — leitura anexada à listagem. EN: Empenhos…, _isolamento_pytest(), main(), _pdf(), fixture, Teste do fluxo do módulo Renomear Empenhos. Valida: identificação dos campos…, Aponta o banco e a pasta monitorada do módulo para um ambiente temporário,…, Sob pytest, isola banco + pasta monitorada em temp (igual ao main()), para não… (+24 more)

### Community 31 - "Testes Email Docs OTel"
Cohesion: 0.07
Nodes (19): Teste unitário de e-mail, documentação e observabilidade (sem I/O real). Cobre…, PLANO.md: bancos devem ser criados do zero quando nao existirem. Faz backup dos…, test_fresh_install_creates_empty_databases(), Testes de seguranca do Aplicar async + superficies criticas (standalone).…, _http(), Teste de boot / Fase 2.5 — `teste_boot.py`. Valida que o sistema sobe em…, GET simples retornando (status, corpo). None se não alcançável., Shutdown gracioso — agendador e servidor de documentação. EN: Graceful shutdown… (+11 more)

### Community 32 - "Paginas Principais do App"
Cohesion: 0.15
Nodes (31): atexit, iniciar_agendador(), page_auditoria(), page_blog(), page_configuracoes(), page_edit_pdf(), _page_empenho_forcado(), page_login() (+23 more)

### Community 33 - "Tema Escuro e Sessoes"
Cohesion: 0.09
Nodes (31): definir_tema_escuro(), Fecha a sessão deste navegador; sem hash, fecha todas (comportamento antigo)., True se o usuário prefere o tema escuro (config per-usuário). Preferência de…, Define a preferência de tema (escuro/claro) do usuário., registrar_logout(), tema_escuro(), favicon_versao(), mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba). (+23 more)

### Community 34 - "Email e Lotes Impressao"
Cohesion: 0.10
Nodes (32): enviar_email(), Envia e-mail via SMTP configurado. Retorna (ok, msg)., agrupar_solicitacoes_em_lote(), enviar_solicitacao_por_email(), gerar_zip_solicitacoes(), listar_solicitacoes(), listar_solicitacoes_acao_pendente(), marcar_solicitacao_enviada() (+24 more)

### Community 35 - "Testes Ativacao Ativos"
Cohesion: 0.06
Nodes (6): Testes funcionais do assistente de ativação (`mod_intranet/ativacao.py`).…, Roda iniciar() com _TTY=True e serviços mockados; devolve (cfg, saída)., Relógio fake: avança 1 s por chamada (simula o tempo real do loop)., _Relogio, _rodar_iniciar(), io

### Community 36 - "Testes Editor Blog"
Cohesion: 0.07
Nodes (19): Controles de imagem do editor do Blog — alinhar/esticar. EN: Blog editor image…, Markdown dentro do editor WYSIWYG do Blog. EN: Markdown inside the WYSIWYG…, iniciar_servidor(), main(), montar_pagina(), page, Teste de viabilidade: ui.mermaid no NiceGUI 3.15 (renderização em navegador).…, ajustar_imagem_html() (+11 more)

### Community 37 - "Tela Busca de Logs"
Cohesion: 0.14
Nodes (25): mostrar_tela(), _adicionar_campo(), _atualizar_tabela(), _buscar_logs(), _campo_data(), _ao_escolher(), _campos_ativos(), _cfg() (+17 more)

### Community 38 - "Nucleo do Modulo Blog"
Cohesion: 0.08
Nodes (23): Any, glob, loguru, Blog module — posts and comments with nh3 sanitization (route /blog). Módulo…, configurar(), _console_valido(), formatar_tamanho(), gerar_logs_teste_niveis() (+15 more)

### Community 39 - "Proxy Conexao Postgres"
Cohesion: 0.10
Nodes (8): _ConexaoPostgres, _CursorPostgres, _ddl_postgres(), Translates SQLite CREATE TABLE DDL into PostgreSQL-compatible DDL. Lida com os…, psycopg2 cursor proxy: translates `?`→`%s`, SQLite DDL/PRAGMA and captures…, Splits a script on ';' and runs each statement (SQLite emulation)., Converts Postgres datetime/date to string (SQLite-compatible)., psycopg2 connection proxy exposing the DBAPI used by the modules.

### Community 40 - "Testes Editor e Carrossel"
Cohesion: 0.11
Nodes (23): Editor WYSIWYG do Blog — upload de imagens e expiração de órfãs. EN: Blog…, achar_botoes(), check(), clicar(), main(), Teste do modo de exibição CARROSSEL do Blog (mod_blog/telas.py). Renderiza a…, _varrer(), _cards_blog() (+15 more)

### Community 41 - "Testes Fluxo Blog"
Cohesion: 0.16
Nodes (26): _admin_disponivel(), main(), ok(), Teste do módulo Blog (mod_blog) — teste_fluxo_blog. Valida: sanitização XSS…, teste_auditoria_central(), teste_carrossel(), teste_config_local(), teste_conversores() (+18 more)

### Community 42 - "FormularioBuilder UI"
Cohesion: 0.11
Nodes (17): FormularioBuilder, criar(), criar(), criar(), criar(), _log(), Registers a numeric field (`ui.number` com min/max/step). Mesmo padrão visual…, Registers an ISO date field (`ui.input` + máscara Quasar `date`). Campo de… (+9 more)

### Community 43 - "Config Intranet e Grafana"
Cohesion: 0.12
Nodes (21): Teste do Config do módulo Intranet: Aplicar por card, aparência, avisos e…, json, _api_autorizada(), atualizar_senha_grafana(), grafana_aguardar_pronto(), grafana_rodando(), obter_grafana_url(), obter_senha_master() (+13 more)

### Community 44 - "CrudBase Legado"
Cohesion: 0.11
Nodes (14): bd_criador.py legado/morto (schema real em bd_manipulador), CrudBase, Runs one statement with guaranteed connection close (try/finally). Executa…, Yields a cursor within an atomic multi-statement transaction. Transação atômica…, Runs a SELECT returning all rows (list of tuples)., Runs a SELECT returning the first row (or `None`)., Runs an INSERT with commit, returning the new `lastrowid`., Runs an UPDATE/DELETE with commit, returning `rowcount`. (+6 more)

### Community 45 - "Integracao OpenTelemetry"
Cohesion: 0.09
Nodes (25): Exception, configurar_log_otel(), inicializar_otel(), _obter_config(), obter_endpoint(), OpenTelemetry integration for Intranet Modular. This module provides…, Initialize OpenTelemetry SDK. Inicializa o SDK do OpenTelemetry. Com…, Register an error in a span. Registra um erro em um span. (+17 more)

### Community 46 - "Scripts Docker e OTel"
Cohesion: 0.10
Nodes (26): abrir_terminal(), _cmd(), _dir_docker(), _formatar_achados_otel(), _garantir_sdk_otel(), iniciar_postgres(), iniciar_stack_otel(), _mascarar_comando() (+18 more)

### Community 47 - "QA Empenho Playwright"
Cohesion: 0.11
Nodes (18): browser_type_launch_args(), fixture, QA Renomear Empenhos — pirâmide de testes com evidência headless. EN — Full QA…, Backend sem browser — FTS 1 letra, levantamento presença, EE string., TestIntegracaoBackend, ast, _fts_escape(), _fts_query_prefixada() (+10 more)

### Community 48 - "Fluxo de Grupos de Impressao"
Cohesion: 0.11
Nodes (24): _atualizar_status_grupo(), autorizar_grupo(), cancelar_grupo(), cancelar_rascunho(), expirar_rascunhos_e_impressos(), imprimir_grupo(), listar_arquivos_grupo(), _log() (+16 more)

### Community 49 - "Cotas e Paginas Impressao"
Cohesion: 0.10
Nodes (24): calcular_paginas_contabilizadas(), confirmar_lote(), contar_pedidos_abertos(), criar_solicitacao(), gerar_nome_arquivo(), obter_limite_pedidos_abertos(), obter_secretaria(), obter_setor() (+16 more)

### Community 50 - "Estilizacao Home Visual"
Cohesion: 0.11
Nodes (22): aplicar_framework(), aplicar_modelo(), classes_card_resumo(), classes_stat(), classes_wrap_resumo(), _get_config_safe(), injetar_pic_suave(), injetar_resumo_overrides() (+14 more)

### Community 51 - "Provisionamento Grafana"
Cohesion: 0.13
Nodes (20): argparse, ensure_folder(), main(), provision_dashboard(), Grafana Dashboard Provisioning - Intranet Modular Provisions dashboards into…, Perform an HTTP request to Grafana with basic auth., Ensure the target folder exists and return its UID., Upload a single dashboard JSON. (+12 more)

### Community 52 - "Fabrica de Documentos"
Cohesion: 0.14
Nodes (21): criar_lote_demo(), criar_lote_principal(), criar_pdf_empenho(), gerar_dados_empenho(), _nome_empresa(), nome_impressora(), _nome_pessoa(), Fábrica de documentos fictícios do módulo Renomear Empenhos. Factory of… (+13 more)

### Community 53 - "Scanner de Portas"
Cohesion: 0.13
Nodes (20): concurrent_futures, escanear_portas(), _executar(), portas_com_servico(), _portas_docker(), _portas_por_lsof(), _portas_por_netstat_windows(), _portas_por_ss_linux() (+12 more)

### Community 54 - "Exibicao Carrossel Blog"
Cohesion: 0.16
Nodes (21): mostrar_tela(), ao_editar(), ao_toggle_selecao(), _aplicar_carrossel_exib(), _aplicar_historico_exib(), _aplicar_unica_exib(), atualizar(), _atualizar_contador() (+13 more)

### Community 55 - "CLI Aplicar Banco"
Cohesion: 0.13
Nodes (22): aplicar_banco(), banner(), c(), _confirmar_fallback_sqlite(), _escolha_1_enter(), _executar_e_persistir(), _garantir_tb_config(), iniciar() (+14 more)

### Community 56 - "Perfis e Seed Auditoria"
Cohesion: 0.13
Nodes (21): Perfil administrador_geral, Perfil administrador_modulo, Usuários seed (master/qacomum/qamaster), Perfil comum (usuário comum), Banco exclusivo db_mod_auditoria.db (uma tabela por módulo produtor), mod_auditoria — Módulo Auditoria, poda_auditoria (poda LGPD diária, retenção 90 dias), cleanup_pdf (expiração de arquivos 1 min) (+13 more)

### Community 57 - "Grants de Acesso Modulos"
Cohesion: 0.15
Nodes (21): listar_acessos(), Lists the user's per-module grants (modulo_chave, papel, liberado_por, data)., _aplicar_acessos(), _dlg_duplicar(), salvar(), _dlg_editar(), salvar(), _dlg_novo() (+13 more)

### Community 58 - "Dialogos de Sessoes"
Cohesion: 0.12
Nodes (19): _dlg_excluir(), _dlg_excluir_definitivo(), excluir(), excluir(), _dlg_sessoes(), _duracao(), refresh_interno(), _nomes_modulos() (+11 more)

### Community 59 - "Probes Portas OTel/Postgres"
Cohesion: 0.10
Nodes (21): _detectar_otel_rodando(), _detectar_postgres_rodando(), _msg_porta_em_uso(), _normalizar_portas(), _portas_docker_servicos_otel(), _portas_em_uso_cached(), _portas_livres(), _probe_http() (+13 more)

### Community 60 - "Frameworks CSS Embarcados"
Cohesion: 0.10
Nodes (20): CSS Frameworks Embarcados (README), Bootstrap 5.3.8 (rota dedicada, MIT), Bulma 1.0.2 (mantido em disco, pode colidir com Quasar, MIT), Chota 0.8.0 (rota dedicada, leve, MIT), DaisyUI 5.6.8 + themes (sobre Tailwind v4, MIT), Foundation 6.8.1 (rota dedicada, pesado, MIT), Materialize 1.0.0 (rota dedicada, pesado, MIT), Milligram 1.4.1 (rota dedicada, leve, MIT) (+12 more)

### Community 61 - "Testes Flags Permissao"
Cohesion: 0.12
Nodes (11): Teste de papéis/validacão de acesso do ator (mod_intranet/autenticacao.py).…, _dummy(), Flags finas de permissão (JSON) — catálogo, grant, bypass e decorador. EN:…, Teste do fluxo de permissões por módulo — Fase 2.5. Valida a…, Listagem de logs — arquivos com tamanho e marca de uso. EN: Log listing — files…, functools, mod_gest_cad_usuario, Central decorators for cross-cutting concerns (permission, audit, fail-soft).… (+3 more)

### Community 62 - "Tabelas e Listas UI"
Cohesion: 0.15
Nodes (9): GradeTabela, _log(), PainelLista, Builds the panel (search field + body); returns the container.…, Re-renders the body (count/pagination/grade) from the first page. Deve ser…, Returns the loguru logger bound to the core module ("intranet"). Logger loguru…, Standard `ui.grid` table (caption header + cells + action column). Tabela em…, Renders header + one row per item; returns the grid element. `dados` é uma… (+1 more)

### Community 63 - "Verificacao UI Comum"
Cohesion: 0.11
Nodes (6): _bruto(), _campo_ordem(), Verificação da fábrica central de UI (`ui_comum` + helpers de tela). Script…, Visual state tuple of a stub element (props/classes/style/tooltip/cb). Tupla de…, hashlib, types

### Community 64 - "Renderizacao Feed Blog"
Cohesion: 0.13
Nodes (18): _ler_tema(), listar_postagens_por_ids(), obter_postagem_unica_id(), Lists posts matching the given ordered ids (carousel selection). Retorna…, Retorna o id da postagem fixada no modo 'unica' (None = mais recente). Lê…, Extracts a plain-text summary (no HTML/Markdown/Mermaid). Remove blocos…, Renders a rotating carousel of selected posts (no min, auto slide). Exibe as…, Renders feed content into the CURRENT slot (no container handling). Conteúdo do… (+10 more)

### Community 65 - "Visual Renomear Empenho"
Cohesion: 0.13
Nodes (10): eh_bootstrap(), eh_framework(), eh_hibrido(), eh_pic(), _get_config_safe(), ler_modelo(), Visual switcher for mod_renomear_empenho — uma tela por CSS disponível. Módulo…, Lê o modelo visual atual (pic|bootstrap), fail-soft para 'pic'. (+2 more)

### Community 66 - "Specs E2E Login/Header"
Cohesion: 0.18
Nodes (11): { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, coletarErros(), ehRuido() (+3 more)

### Community 67 - "E2E Admin e Lote Empenhos"
Cohesion: 0.25
Nodes (8): _abrir_navegar(), _aguardar_contagem(), _fazer_login(), _fechar_dialogos_bloqueadores(), Fluxo real headless: login → /renomear-empenho → digitar no campo., Admin: switch automática; lote spinner — só localhost., TestE2EAdminELote, TestE2ENavegarPesquisa

### Community 68 - "Contexto Sessoes LGPD"
Cohesion: 0.15
Nodes (17): contextvars, _podar_sessoes(), Retenção LGPD: mantém as N sessões mais recentes por usuário. Configuração…, Registra sessão e devolve o cookie_hash. Usa `Repositorio` (SQLAlchemy ORM)…, registrar_login(), capturar_contexto(), contexto_atual(), _extrair() (+9 more)

### Community 69 - "Marca Dagua e Listas"
Cohesion: 0.12
Nodes (17): aplicar_marca_dagua(), listar_impressoras(), listar_pedidos(), obter_config(), Minutes a draft survives before automatic removal (default 10, min 1). Minutos…, Minutes before the file is deleted after printing (default 10, min 1). Minutos…, Lists PEDIDOS (one per group) with group metadata and file count. Lista os…, Generates a new PDF (copy) with a watermark if active. Returns the final PDF… (+9 more)

### Community 70 - "Construtor Documentacao"
Cohesion: 0.15
Nodes (16): _passo_docs(), _build(), construir_e_montar_documentacao(), habilitada_no_boot(), iniciar_servidor(), __init__(), montar(), porta_documentacao() (+8 more)

### Community 71 - "Hora Servidor NTP"
Cohesion: 0.19
Nodes (16): definir_ntp_ativa(), hora_servidor(), hora_servidor_str(), _ler_ntp_ativa(), _log(), _obter_offset_ntp(), offset_ntp(), Hora do servidor com sincronização opcional via NTP.br (RFC 5905). EN —… (+8 more)

### Community 72 - "Testes Fabrica Documentos"
Cohesion: 0.12
Nodes (6): assets_test, Testes da fábrica de documentos fictícios (faker + pytest). Validam:…, TestFabricaCoberturaCampos, TestFabricaDeterministica, TestFabricaNomesImpressora, TestFabricaPontaAPonta

### Community 73 - "Sanitizacao e Metricas Blog"
Cohesion: 0.18
Nodes (16): Armadilha hidden sm:*/md:* no NiceGUI 3.15, Métricas de Software, Modo carrossel do Blog (rotação automática), mod_blog — Módulo Blog, Sanitização HTML nh3 (gravação e renderização), Layout padrão de 4 partes (header/drawer/rodapé/área), mod_intranet — Núcleo Intranet, RNF-UI-01 responsividade mobile-first 320/768/1024 (+8 more)

### Community 74 - "Instrumentacao OTel App"
Cohesion: 0.17
Nodes (15): fastapi, fastapi_responses, logging, _contadores(), OpenTelemetry application instrumentation for Intranet Modular. This module…, Cria e retorna os objetos de metricas (no-op se OTel indisponivel)., criar_contador(), criar_gauge() (+7 more)

### Community 75 - "Confirmacao Impressao Admin"
Cohesion: 0.15
Nodes (15): _confirmar_impressao(), _editar_cota(), salvar(), _editar_secretaria(), salvar(), _editar_setor(), salvar(), Confirms the effective print (status=impresso + quota deduction). Confirma a… (+7 more)

### Community 76 - "Dashboards e Stack LGTM"
Cohesion: 0.19
Nodes (13): Dashboards Intranet (Visao Geral/Mimir, Traces/Tempo, Logs/Loki), dashboards.yml - provider 'Intranet Dashboards' (update 30s), postgres/docker-compose.yml - backend opcional PostgreSQL 16, Docker - Stack OTel LGTM (README), Credenciais master/master compartilhadas com admin da Intranet, Grafana OTel LGTM stack (Grafana + Loki + Tempo + Mimir + OTel Collector), instrumentar_aplicacao(), _observer_requisicoes() (+5 more)

### Community 77 - "Spec E2E Editor Blog"
Cohesion: 0.15
Nodes (10): fs, { login, coletarErros, errosFatais }, os, path, PNG_1X1, { test, expect }, IMPORTANT: keep the reminder string free of backticks and $(...) constructs., ref_fs (+2 more)

### Community 78 - "Wrappers Elementos NiceGUI"
Cohesion: 0.14
Nodes (3): _El, _fab(), _cria()

### Community 79 - "Registro de Modulos"
Cohesion: 0.14
Nodes (14): chaves_nativas(), excluir_modulo(), _garantir_tb_modulos(), nome_do_modulo(), Registers a NEW (future) module, born unavailable until activated. Cadastra um…, Reorder display order of modules (sidebar, user management). Reordena a ordem…, Remove módulo NÃO-nativo do cadastro. Usa `Repositorio` (SQLAlchemy ORM)., Activates/deactivates a module, blocking deactivation of essential ones. Ativa… (+6 more)

### Community 80 - "Consumo Cotas Mensais"
Cohesion: 0.20
Nodes (14): _incrementar_consumo(), mes_atual(), obter_consumo(), obter_ou_criar_cota(), percentual_consumo(), Adds pages to the monthly consumption (upsert on the period row). Soma páginas…, Verifica se a impressão excederá alguma cota (secretaria OU setor). Retorna…, Returns (percent 0-100+, used, quota). Retorna (percentual 0-100+, usado, cota)… (+6 more)

### Community 81 - "Wrappers Dialogos NiceGUI"
Cohesion: 0.15
Nodes (3): _El, _fab(), _cria()

### Community 82 - "Boot Config CLI"
Cohesion: 0.17
Nodes (12): _cli_app(), cli_opcoes(), config_do_cli(), _config_padrao(), config_persistida(), _porta_valida(), Loads the persisted boot config from tb_config (no prompts). Carrega a…, Builds the Typer app with the boot options (help em PT-BR). `python main.py… (+4 more)

### Community 83 - "Injetores Framework Visual"
Cohesion: 0.20
Nodes (12): PIC - visual padrao (Quasar nativo suave, sem CSS externo), aplicar_framework(), aplicar_modelo(), injetar_bootstrap_overrides(), injetar_hibrido(), injetar_pic_suave(), visual.MODELO_PADRAO = 'pic' (mod_renomear_empenho/visual.py), Injeta o CSS local do framework (str) ou compat bool (True=bootstrap). (+4 more)

### Community 84 - "Formatacao HTML Blog"
Cohesion: 0.20
Nodes (5): HTMLParser, _FormatadorBlog, _merge_style(), Concatena estilos CSS sem duplicar o separador ';'., Reescreve HTML sanitizado aplicando o padrão visual do Blog: - h1/h2/h3:…

### Community 85 - "Admin Secretarias e Setores"
Cohesion: 0.20
Nodes (12): _admin_secretarias(), atualizar(), criar(), _admin_setores(), atualizar(), criar(), _excluir_secretaria(), _excluir_setor() (+4 more)

### Community 86 - "Compose LGTM"
Cohesion: 0.47
Nodes (11): compose.yml - definicao dos servicos LGTM, Servico Grafana (3000, admin master/master via env), Servico Loki (3100, logs), Servico Mimir (9009, metricas compat. Prometheus), Servico OTel Collector (4317 gRPC / 4318 HTTP / 8888-8889), Servico Tempo (3200, traces; 4317 interno via rede Docker), datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim), loki-config.yml - TSDB schema v13, compactor com retencao 7d (+3 more)

### Community 87 - "Verificar Credenciais"
Cohesion: 0.35
Nodes (10): check_docker(), check_grafana(), check_loki(), check_mimir(), check_otel_collector(), check_tempo(), main(), print_header() (+2 more)

### Community 88 - "Pacote Playwright E2E"
Cohesion: 0.18
Nodes (10): description, devDependencies, @playwright/test, name, private, scripts, e2e:headed, e2e:report (+2 more)

### Community 89 - "Models SQLAlchemy"
Cohesion: 0.18
Nodes (10): dataclasses, Configuracao, Modulo, Models package for mod_intranet — dataclasses + SQLAlchemy ORM. Provides type-…, Module registry entry (tb_modulos). EN: Represents a registered module in the…, Key-value configuration entry (tb_config). EN: Represents a single key=value…, User session entry (tb_sessoes) with LGPD tracking fields. EN: Represents an…, Sessao (+2 more)

### Community 90 - "Ferramentas Seguranca"
Cohesion: 0.24
Nodes (11): Auditoria de Segurança do Menu Hambúrguer (12/09/2026), bandit 1.9.4 (SAST Python), Ferramentas e Práticas de Segurança (DevSecOps), gitleaks 8.24.3 (segredos no histórico git), pip-audit 2.10.1 (CVEs de dependências), safety 3.8.1 (CVEs conhecidas), semgrep 1.176.1 (SAST multi-regra), Testes — Casos (+3 more)

### Community 91 - "Dashboard Resumo Home"
Cohesion: 0.20
Nodes (11): _construir_dashboard(), _contar_fila_para_autorizar(), _eh_autorizador_impressao(), page_dashboard(), Card de métrica do Resumo — ícone ampliado + número lateral (4 dígitos, >9999)…, Constrói o conteúdo da Home (banner + resumo dinâmico + feed)., Verifica se o usuário é responsável por autorizar impressão (qualquer…, Conta solicitações pendentes que o usuário pode autorizar (por… (+3 more)

### Community 92 - "Download Grupos Empenho"
Cohesion: 0.24
Nodes (11): _baixar_arquivo(), _cancelar_grupo(), _card_grupo(), baixar_selecionados(), baixar_selecionados_zip(), _selecionados_fisicos(), Renders one PEDIDO card (all files of the submission) with actions. O pedido é…, Downloads one file of a pedido (with watermark applied at download time). Baixa… (+3 more)

### Community 93 - "Tela Solicitacao Impressao"
Cohesion: 0.18
Nodes (11): _eh_responsavel(), _log(), mostrar_tela(), _tema(), True if the user has any active authorization grant (any department/unit).…, Renders the print-request screen with permission-based tabs. Monta a tela: abas…, My-requests tab: the user's own PEDIDOS (one card per submission/group),…, Authorization tab "Solicitação pendente": the authorizer sees only pedidos of… (+3 more)

### Community 94 - "Nova Solicitacao Upload"
Cohesion: 0.27
Nodes (8): New-request tab: multi-PDF drafts with countdown + form + submission. Upload…, _tela_nova(), ao_upload(), enviar(), rebuild(), _remover_selecionados(), _remover_um(), tick()

### Community 95 - "Servir Frameworks CSS"
Cohesion: 0.29
Nodes (9): Spectre 0.5.9 (rota dedicada, leve, MIT), caminho_css(), injetar_framework(), _log(), montar_rotas_static(), Serves the embedded CSS frameworks (Bootstrap, Bulma, DaisyUI, Pico, Picnic)…, Makes /css/frameworks/* serve the local CSS files for the whole app. Registra a…, Return HTTP URL of the CSS file (None lists the available frameworks). Devolve… (+1 more)

### Community 96 - "Start.sh Stack"
Cohesion: 0.38
Nodes (9): check_docker(), print_header(), start.sh script, show_help(), show_logs(), show_status(), start_stack(), stop_stack() (+1 more)

### Community 97 - "Fixtures PDF e Infra Teste"
Cohesion: 0.31
Nodes (10): DOC_0201.pdf - fixture PDF ficticio de empenho (massa de teste), EC_24.pdf - fixture PDF ficticio de empenho (massa de teste), EE_9570.pdf - fixture PDF ficticio de empenho (massa de teste), EG_89.pdf - fixture PDF ficticio de empenho (massa de teste), Pasta de testes assets/test (README), Convencoes obrigatorias de teste (standalone, exit-code, data-testid, docstring bilingue, sem destruicao), Infra E2E Playwright (e2e specs, helpers.js, _global_setup.js, playwright.config.js, package.json), INTRANET_FORCE_SQLITE=1 - suite roda forcando SQLite (+2 more)

### Community 98 - "Patches Timer NiceGUI"
Cohesion: 0.24
Nodes (9): contextlib, aplicar(), _get_context(), Patches NiceGUI timers to tolerate page teardown (no "parent slot deleted"). O…, Returns nullcontext instead of raising when the parent slot is gone., Stops the timer when its parent slot was deleted (page navegada/fechada). Um…, Aplica os patches no NiceGUI (idempotente)., _should_stop() (+1 more)

### Community 99 - "Manuais e Licoes Aprendidas"
Cohesion: 0.22
Nodes (10): Validação ast.parse UTF-8 (integridade de arquivos), Lições Aprendidas, Manual de Uso — Administrador, Manual de Uso — Instalação, Manual de Uso — Renomeador de Empenho, Manual de Uso — Usuário Comum, POSTAGENS_PADRAO (3 seeds "Como usar"), Padrões de Codificação (+2 more)

### Community 100 - "Setup Credenciais Grafana"
Cohesion: 0.42
Nodes (8): check_docker(), check_grafana(), main(), print_header(), restart_grafana(), setup-grafana-credentials.sh script, show_credentials(), update_grafana_password()

### Community 101 - "Config E2E Exclusao Blog"
Cohesion: 0.22
Nodes (7): { login }, { test, expect }, { defineConfig }, path, root, venvPython, @playwright/test

### Community 103 - "Rotinas de Encerramento"
Cohesion: 0.25
Nodes (8): _ao_sinal(), _encerrar(), parar_servidor(), Para o servidor de documentação (idempotente, fail-soft). Encerra o…, finalizar_otel(), Shutdown OpenTelemetry SDK. Finaliza o SDK do OpenTelemetry., encerrar_agendador(), Para o agendador de forma ordenada (idempotente, fail-soft). Desliga o…

### Community 104 - "Registro Rotas Modulos"
Cohesion: 0.25
Nodes (8): alterar_rota_modulo(), Changes a module's page route (URL) and re-registers it live. Altera a rota/URL…, montar_rotas_ativas(), _normalizar_rota(), Normalizes a route: leading '/', lowercase, no spaces/duplicate slashes.…, Registers a module page route in NiceGUI (idempotent). Registra a rota de um…, Re-registers persisted custom routes from tb_modulos (idempotent). Lê…, registrar_modulo()

### Community 105 - "Relatorios Agregacao Impressao"
Cohesion: 0.36
Nodes (8): _agregar_impressao(), Runs a print aggregation (status='impresso') over a period. `agrupar_por`:…, Builds the print report (status='impresso') for a period. Dicionário com totais…, relatorio_impressao(), _por_autorizador(), _por_impressor(), _por_secretaria(), _por_setor()

### Community 106 - "Admin Solicitacoes Sub-abas"
Cohesion: 0.29
Nodes (7): _admin_solicitacoes(), ao_aba(), atualizar(), _admin_solicitacoes(), Admin sub-tab: PEDIDOS grouped by secretaria -> setor (delegates to telas).…, Admin sub-tab: PEDIDOS grouped by secretaria -> setor, with status tabs and…, ao_secretaria()

### Community 107 - "Global Setup Playwright"
Cohesion: 0.29
Nodes (6): { execSync }, path, root, script, venvPython, ref_child_process

### Community 108 - "Admin Cotas Sub-aba"
Cohesion: 0.29
Nodes (7): _admin_cotas(), atualizar(), Admin sub-tab: monthly quota report with edit/reset per department/unit. Sub-…, Zeros the month's consumption for the department/unit. Zera o consumo do mês…, Administration tab with 7 sub-tabs (requests + master data + report + config).…, _resetar_cota(), _tela_admin()

### Community 109 - "Admin Responsaveis Sub-aba"
Cohesion: 0.33
Nodes (6): _admin_responsaveis(), atualizar(), criar(), _excluir_resp(), Admin sub-tab: grants authorization power to registered users. Sub-aba de…, Removes an authorization grant. Remove um vínculo de autorização.

### Community 110 - "Login e Sessao em Banco"
Cohesion: 0.33
Nodes (6): Fase 1: autenticacao master/master, gravacao de sessao em tb_sessoes (cookie…, test_login_e_sessao_em_banco(), precisa_trocar_senha(), True se existe linha de sessão ABERTA com esse hash no banco central. Usado…, Verifica flag de troca obrigatória de senha (primeiro acesso). Usa…, sessao_ativa()

### Community 111 - "Contadores Auditoria"
Cohesion: 0.40
Nodes (6): _orquestrar_resumo_dados(), Coleta os 9 contadores do Resumo — 5 base + fila impressão, quarentena, pdf…, contar_registros(), get_tabelas_auditoria(), Lists the per-module audit tables found in the audit database. Retorna os nomes…, Counts audit records in one table or across all of them. Total de registros de…

### Community 112 - "Telas Controle Acesso"
Cohesion: 0.33
Nodes (5): _acesso_negado(), mostrar_tela(), novo_usuario(), Renders the 'access restricted' panel for non-admin users., Renders the user management screen (admin-only). Monta a tela completa:…

### Community 113 - "Dialogos Troca Credenciais"
Cohesion: 0.33
Nodes (6): _dialogo_troca_credenciais(), confirmar(), _dialogo_troca_senha(), confirmar(), Forces master's first-access combined change (username + password + dados).…, Forces the mandatory first-login password change dialog. Diálogo persistente de…

### Community 114 - "Admin Relatorio Sub-aba"
Cohesion: 0.40
Nodes (6): _admin_relatorio(), gerar(), _prazo_fixo(), Renders a small report table with header + rows (or an empty note). Renderiza…, Admin sub-tab: print report by fixed monthly periods or custom calendar range.…, _tabela_relatorio()

### Community 115 - "Painel Impressoras"
Cohesion: 0.53
Nodes (6): _painel_impressoras(), atualizar(), criar(), _def_padrao(), _excluir_imp(), Admin block: register/list/set-default printers used by the print selector.…

### Community 116 - "Mermaid no Blog"
Cohesion: 0.40
Nodes (3): Mermaid sempre ao fim da postagem — padrão do Blog. EN: Mermaid diagrams always…, mover_mermaid_para_fim(), Move blocos ```mermaid para o fim do texto (ordem preservada). PADRÃO DO…

### Community 118 - "Seed Postagens Blog"
Cohesion: 0.50
Nodes (4): _log(), main(), Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log., Runs the seed, creating each how-to post and reporting the result. Executa o…

### Community 119 - "Spec E2E Varredura"
Cohesion: 0.50
Nodes (3): { login, coletarErros, errosFatais }, ROTAS, { test, expect }

### Community 121 - "Riscos IA/ML"
Cohesion: 0.67
Nodes (4): Riscos de Segurança em IA/ML, Defesa adversarial IA/ML (regras obrigatórias), Microsoft Learn — Fundamentos de segurança de IA, Prompt injection (risco LLM)

### Community 122 - "Script Iniciar"
Cohesion: 0.50
Nodes (3): INTRANET_FORCE_SQLITE, INTRANET_SEM_OTEL, iniciar.sh script

### Community 124 - "Probes Postgres"
Cohesion: 0.50
Nodes (4): _probe_postgres_porta(), True se um PostgreSQL aceita as credenciais do sistema na `porta`. Testa o DSN…, True if the PostgreSQL DSN is reachable (psycopg2 connect). Remove o sufixo…, _verificar_postgres()

### Community 125 - "Auto Start OTel"
Cohesion: 0.50
Nodes (4): auto_iniciar_otel(), iniciar_otel_stack(), Start the OTel LGTM stack. Inicia a stack OTel LGTM. Retorna (sucesso,…, Auto-start OTel stack if Docker is available. Auto-inicia a stack OTel se o…

## Knowledge Gaps
- **96 isolated node(s):** `$schema`, `plugin`, `{ test, expect }`, `{ login, coletarErros, errosFatais }`, `{ test, expect }` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1413 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_config()` connect `Painel Admin Auditoria` to `Editor PDF Testes`, `QA Diagnostico e Seeds`, `Empenho BD Manipulador`, `Gestao Usuarios Core`, `Quarentena e Campos Busca`, `Configs Especificas Auditoria`, `Smoke Campos Senha`, `Testes Funcionais Auditoria`, `Testes Classes CRUD`, `Testes Tema Central`, `Menu e Ferramentas UI`, `Sessoes e Botoes Admin`, `Testes Rodape TestID`, `Camada Central de Dados`, `Scripts Ativacao Docker`, `Config e HTML Blog`, `Rotinas Expirar e Podar`, `Testes Email Docs OTel`, `Paginas Principais do App`, `Tema Escuro e Sessoes`, `Tela Busca de Logs`, `Nucleo do Modulo Blog`, `Config Intranet e Grafana`, `Integracao OpenTelemetry`, `QA Empenho Playwright`, `Estilizacao Home Visual`, `Visual Renomear Empenho`, `Construtor Documentacao`, `Hora Servidor NTP`, `Boot Config CLI`, `Dashboard Resumo Home`, `Tela Solicitacao Impressao`, `Contadores Auditoria`, `Painel Admin Modulos`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `botao()` connect `Sessoes e Botoes Admin` to `Editor PDF Testes`, `Empenho BD Manipulador`, `Painel Admin Auditoria`, `Quarentena e Campos Busca`, `Smoke Campos Senha`, `Testes Funcionais Auditoria`, `Testes Classes CRUD`, `Testes Tema Central`, `Menu e Ferramentas UI`, `Testes Rodape TestID`, `Logger Auditoria e Blog`, `Relatorios e Cadastros Admin`, `Tema Escuro e Sessoes`, `Email e Lotes Impressao`, `Tela Busca de Logs`, `Exibicao Carrossel Blog`, `Grants de Acesso Modulos`, `Dialogos de Sessoes`, `Renderizacao Feed Blog`, `Marca Dagua e Listas`, `Sanitizacao e Metricas Blog`, `Confirmacao Impressao Admin`, `Admin Secretarias e Setores`, `Download Grupos Empenho`, `Tela Solicitacao Impressao`, `Nova Solicitacao Upload`, `Admin Solicitacoes Sub-abas`, `Admin Cotas Sub-aba`, `Admin Responsaveis Sub-aba`, `Telas Controle Acesso`, `Admin Relatorio Sub-aba`, `Painel Impressoras`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `audit_log()` connect `Configs Especificas Auditoria` to `Editor PDF Testes`, `QA Diagnostico e Seeds`, `Empenho BD Manipulador`, `Gestao Usuarios Core`, `Painel Admin Auditoria`, `Quarentena e Campos Busca`, `Chaves Desativadas`, `Smoke Campos Senha`, `Testes Funcionais Auditoria`, `Cadastros Solicitacao Impressao`, `Testes Tema Central`, `Menu e Ferramentas UI`, `Sessoes e Botoes Admin`, `Autenticacao e Downloads`, `Config e HTML Blog`, `Rotinas Expirar e Podar`, `Paginas Principais do App`, `Tema Escuro e Sessoes`, `Email e Lotes Impressao`, `Perfis e Seed Auditoria`, `Contexto Sessoes LGPD`, `Sanitizacao e Metricas Blog`, `Registro de Modulos`, `Registro Rotas Modulos`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **What connects `$schema`, `plugin`, `{ test, expect }` to the rest of the system?**
  _96 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Editor PDF Testes` be split into smaller, more focused modules?**
  _Cohesion score 0.042035029190992494 - nodes in this community are weakly interconnected._
- **Should `QA Diagnostico e Seeds` be split into smaller, more focused modules?**
  _Cohesion score 0.041022469593898166 - nodes in this community are weakly interconnected._
- **Should `Empenho BD Manipulador` be split into smaller, more focused modules?**
  _Cohesion score 0.047497446373850866 - nodes in this community are weakly interconnected._