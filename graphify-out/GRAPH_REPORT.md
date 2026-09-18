# Graph Report - intranet  (2026-09-18)

## Corpus Check
- 48 files · ~297,073 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3316 nodes · 7689 edges · 148 communities (122 shown, 26 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 433 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Testes Solicitacao Impressao
- Ativacao Docker e CLI
- QA Diagnostico e Seeds
- Testes Classes CRUD
- Botoes Tema e Cotas
- Quarentena e Campos Busca
- Rotinas Expirar e Podar
- Empenho BD Manipulador
- Diretrizes de Desenvolvimento
- Configs Especificas Auditoria
- Testes Infra e Paridade
- Gestao Usuarios Core
- Editor PDF Testes
- Painel Admin Auditoria
- Admin Cadastros Impressao
- Testes Tema Central
- Testes Rodape TestID
- Camada Central de Dados
- Regras de Permissao Blog
- Editor PDF Testes
- Pesquisa Levantamento Empenhos
- Empenho BD Manipulador
- App Legado Renomeador
- Nucleo Solicitacao Impressao
- Testes Integracao OTel
- Provisionamento Grafana
- Autenticacao e Downloads
- Nucleo do Modulo Blog
- Testes Ativacao Ativos
- Testes Editor e Carrossel
- Paginas Principais do App
- Menu e Ferramentas UI
- Tema Escuro e Sessoes
- Sessoes e Botoes Admin
- Formatacao HTML Blog
- Integracao OpenTelemetry
- Dialogos de Sessoes
- Testes Paridade SQLite/Postgres
- Perfis e Seed Auditoria
- Seguranca Aplicar e Shutdown
- Docs Requisitos e Riscos
- Proxy Conexao Postgres
- FormularioBuilder UI
- Testes Levantamento Empenho
- Scanner de Portas
- Logger Auditoria e Blog
- Editor Blog Markdown
- CrudBase Legado
- Grants de Acesso Modulos
- Testes Paridade SQLite/Postgres
- QA Empenho Playwright
- Exibicao Carrossel Blog
- Estilizacao Home Visual
- Login e Sessao em Banco
- Contadores Auditoria
- Tela Busca de Logs
- Tabelas e Listas UI
- Frameworks CSS Embarcados
- Smoke Campos Senha
- Testes Fluxo Blog
- Verificacao UI Comum
- Posts e Comentarios Blog
- Visual Renomear Empenho
- Nova Solicitacao Upload
- Specs E2E Login/Header
- E2E Admin e Lote Empenhos
- Testes Fabrica Documentos
- Contexto Sessoes LGPD
- Registro de Modulos
- Ferramentas Seguranca
- Instrumentacao OTel App
- Listagem e Exibicao Blog
- Dashboards e Stack LGTM
- Guarda Integridade Modular
- Spec E2E Editor Blog
- Fixtures PDF e Infra Teste
- Wrappers Elementos NiceGUI
- Construtor Documentacao
- Hora Servidor NTP
- Marca Dagua e Listas
- Smoke Campos Senha
- Wrappers Dialogos NiceGUI
- Injetores Framework Visual
- Admin Relatorio Sub-aba
- Compose LGTM
- Verificar Credenciais
- Pacote Playwright E2E
- Renderizacao Feed Blog
- Dashboard Resumo Home
- Servir Frameworks CSS
- Start.sh Stack
- Fabrica de Documentos
- Patches Timer NiceGUI
- Padroes Auditoria e Nomes
- Manuais e Licoes Aprendidas
- Gestao Usuarios Core
- Fluxo de Grupos de Impressao
- Setup Credenciais Grafana
- Config E2E Exclusao Blog
- Testes Funcionais Auditoria
- Mocks de Envio Email
- Menu e Ferramentas UI
- Gestao Usuarios Core
- Relatorios Agregacao Impressao
- Consumo Cotas Mensais
- Graphify Operacoes
- Global Setup Playwright
- Fabrica de Documentos
- Testes Solicitacao Impressao
- Cascata LGPD Vinculos
- Sessao SQLAlchemy Lazy
- Cadastros Solicitacao Impressao
- Sanitizacao e Metricas Blog
- Tela Busca de Logs
- Testes Email Docs OTel
- Seed Postagens Blog
- Spec E2E Varredura
- QA Diagnostico e Seeds
- Contrato Config e Hooks
- Isolamento e Motor PDF
- Script Iniciar
- Rotinas de Encerramento
- Painel Admin Modulos
- Gestao Usuarios Core
- Hook Registrar Config
- Config Plugin opencode
- Rubrica Extracao
- Init Modulo Auditoria
- Renomear Autor Blog
- Renomear Usuario Modulos
- Init Modulo Editor PDF
- Init Modulo Gestao Usuarios
- Chaves Desativadas
- Init Nucleo Intranet
- Init Modulo Renomear Empenho
- Cadastros Solicitacao Impressao
- Init Modulo Solicitacao Impressao
- Graphify Wiki
- Graphify Merge
- Graphify Whisper
- Graphify God Nodes
- Paginas Principais do App

## God Nodes (most connected - your core abstractions)
1. `audit_log()` - 116 edges
2. `notificar()` - 101 edges
3. `get_config()` - 97 edges
4. `set_config()` - 84 edges
5. `botao()` - 67 edges
6. `get_connection()` - 63 edges
7. `get_connection()` - 59 edges
8. `mostrar_tela()` - 58 edges
9. `mostrar_tela()` - 54 edges
10. `Repositorio` - 54 edges

## Surprising Connections (you probably didn't know these)
- `A1 — storage_secret com fallback fraco (main.py:616)` --conceptually_related_to--> `pagina_restrita()`  [INFERRED]
  docs/seguranca/auditoria_menu_2026-09-12.md → mod_intranet/telas.py
- `datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim)` --conceptually_related_to--> `auto_iniciar_otel()`  [INFERRED]
  assets/docker/config/grafana-provisioning/datasources/datasources.yml → mod_intranet/docker_detector.py
- `mod_intranet — Núcleo Intranet` --references--> `conexao()`  [EXTRACTED]
  docs/modulos/intranet.md → mod_intranet/banco_conexao.py
- `conexao()` --references--> `Backend duplo SQLite/PostgreSQL (um database por módulo)`  [EXTRACTED]
  mod_intranet/banco_conexao.py → docs/modulos/intranet.md
- `Docker - Stack OTel LGTM (README)` --references--> `auto_iniciar_otel()`  [EXTRACTED]
  assets/docker/README.md → mod_intranet/docker_detector.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CSS frameworks para comparacao visual via rota dedicada /renomear-empenho-{nome}** — assets_css_frameworks_readme_pic_padrao, assets_css_frameworks_readme_bootstrap, assets_css_frameworks_readme_bulma, assets_css_frameworks_readme_daisyui, assets_css_frameworks_readme_pico, assets_css_frameworks_readme_picnic, assets_css_frameworks_readme_spectre, assets_css_frameworks_readme_chota, assets_css_frameworks_readme_milligram, assets_css_frameworks_readme_skeleton, assets_css_frameworks_readme_water, assets_css_frameworks_readme_mvp, assets_css_frameworks_readme_tachyons, assets_css_frameworks_readme_uikit, assets_css_frameworks_readme_foundation, assets_css_frameworks_readme_semantic, assets_css_frameworks_readme_materialize, assets_css_frameworks_readme_primer [EXTRACTED 1.00]
- **Usuários pré-cadastrados (seed) e seus perfis** — agents_seed_master, agents_seed_qacomum, agents_seed_qamaster, agents_perfil_administrador_geral, agents_perfil_comum [EXTRACTED 1.00]
- **Grafana OTel LGTM - stack de observabilidade da intranet** — assets_docker_readme_lgtm_stack, assets_docker_compose, assets_docker_compose_otel_collector, assets_docker_compose_loki, assets_docker_compose_tempo, assets_docker_compose_mimir, assets_docker_compose_grafana, assets_docker_config_otel_collector_config, assets_docker_config_loki_config, assets_docker_config_tempo_config, assets_docker_config_mimir_config, assets_docker_config_grafana_provisioning_datasources_datasources, assets_docker_config_grafana_provisioning_dashboards_dashboards [EXTRACTED 1.00]
- **Módulos em operação (hub intranet modular)** — docs_modulos_intranet_mod_intranet, docs_modulos_gest_cad_usuario_mod_gest_cad_usuario, docs_modulos_blog_mod_blog, docs_modulos_edit_pdf_mod_edit_pdf, docs_modulos_renomear_empenho_mod_renomear_empenho, docs_modulos_solicitacao_impressao_mod_solicita_impressao [EXTRACTED 1.00]
- **Perfis globais do sistema (PERFIS_GLOBAIS)** — docs_manual_de_uso_administrador_index_administrador_geral, docs_manual_de_uso_administrador_index_administrador_modulo, docs_manual_de_uso_usuario_comum_index_comum [EXTRACTED 1.00]
- **Rotina DevSecOps (SAST + dependências + segredos)** — docs_seguranca_ferramentas_bandit, docs_seguranca_ferramentas_semgrep, docs_seguranca_ferramentas_pip_audit, docs_seguranca_ferramentas_safety, docs_seguranca_ferramentas_gitleaks [EXTRACTED 1.00]
- **segurança e conformidade (LGPD, sessões, perfis e risco do segredo)** — docs_arquitetura_de_software_das_index_autenticacao_sessoes, docs_analise_de_risco_index_storage_secret_risco, docs_2_levantamento_requisitos_index_perfis_usuario, docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario [INFERRED 0.75]
- **camada de dados por módulo (um banco WAL por módulo, acesso só via bd_manipulador)** — docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario, docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_renomear_empenho_mod_renomear_empenho, docs_analise_mod_solicita_impressao_mod_solicita_impressao, docs_arquitetura_de_software_das_index_bd_manipulador_padrao, docs_ferramentas_graphify_crud_base, docs_configuracoes_configuracao_central [INFERRED 0.85]
- **Fixtures PDF ficticios de empenho (massa de teste QA para o editor de PDF)** — assets_test_pdf_doc_0201, assets_test_pdf_ec_24, assets_test_pdf_ee_9570, assets_test_pdf_eg_89, assets_test_fabrica_documentos [INFERRED 0.85]
- **fluxo de auditoria LGPD (escrita audit_log → trilha tb_auditoria_<modulo>)** — docs_analise_mod_gest_cad_usuario_mod_gest_cad_usuario, docs_analise_mod_blog_mod_blog, docs_analise_mod_edit_pdf_mod_edit_pdf, docs_analise_mod_renomear_empenho_mod_renomear_empenho, docs_analise_mod_solicita_impressao_mod_solicita_impressao [INFERRED 0.95]
- **Subagentes kbp-* (padrão kbp-*)** — opencode_agent_kbp_commit_kbp_commit, opencode_agent_kbp_devsecops_kbp_devsecops, opencode_agent_kbp_doc_kbp_doc, opencode_agent_kbp_doc_teste_kbp_doc_teste, opencode_agent_kbp_qa_kbp_qa, opencode_agent_kbp_web_design_kbp_web_design [INFERRED 0.95]
- **Fluxo trilha auditoria LGPD** — docs_analise_mod_auditoria_audit_log_registrar_auditoria, docs_analise_mod_auditoria_banco_exclusivo_auditoria, docs_analise_mod_auditoria_tabela_por_modulo_produtor [EXTRACTED 1.00]
- **Contrato config central local hook** — docs_api_referencia_contrato_config_central_get_config, docs_convencoes_codigo_config_local_via_crudbase, docs_convencoes_codigo_registrar_hook_config [EXTRACTED 1.00]
- **Graphify query path explain trio** — _opencode_skills_graphify_references_query_graphify_query, _opencode_skills_graphify_references_query_graphify_path, _opencode_skills_graphify_references_query_graphify_explain [EXTRACTED 1.00]

## Communities (148 total, 26 thin omitted)

### Community 0 - "Testes Solicitacao Impressao"
Cohesion: 0.04
Nodes (126): criar_pdf_teste(), main(), Teste do módulo Solicitação de Impressão (mod_solicita_impressao). Valida:…, Gera um PDF simples de n_paginas para teste (PyMuPDF)., teste_cadastros_e_cotas(), teste_contagem_e_formula(), teste_excedente(), teste_fluxo() (+118 more)

### Community 1 - "Ativacao Docker e CLI"
Cohesion: 0.03
Nodes (126): _abre_fecha(), abrir_terminal(), _aguardar_container(), aplicar_banco(), aplicar_portas(), banner(), barra(), c() (+118 more)

### Community 2 - "QA Diagnostico e Seeds"
Cohesion: 0.04
Nodes (74): mostra(), QA Diagnostico: fluxo salvar_configs -> reload -> ler valores. Testa se…, mostra(), Teste de papéis/validacão de acesso do ator (mod_intranet/autenticacao.py).…, Teste unitário de e-mail, documentação e observabilidade (sem I/O real). Cobre…, PLANO.md: bancos devem ser criados do zero quando nao existirem. Faz backup dos…, test_fresh_install_creates_empty_databases(), Nome do usuário no menu superior — botão único sempre visível. EN: Header user-… (+66 more)

### Community 3 - "Testes Classes CRUD"
Cohesion: 0.03
Nodes (61): _campo_impar(), Verificação das classes novas do núcleo (CrudBase, ui_painel, ui_form, ui_comum…, _btn_cls(), _btn_style(), Audit module administration panel. Painel de administração do módulo Auditoria…, Return CSS classes for button size., Build inline style dict for button colour., mostrar_administracao() (+53 more)

### Community 4 - "Botoes Tema e Cotas"
Cohesion: 0.05
Nodes (80): botao(), Builds a themed button from the module's 6 appearance keys. Cria um `ui.button`…, percentual_consumo(), Returns (percent 0-100+, used, quota). Retorna (percentual 0-100+, usado, cota)…, _admin_configuracoes(), salvar(), _admin_cotas(), atualizar() (+72 more)

### Community 5 - "Quarentena e Campos Busca"
Cohesion: 0.05
Nodes (71): browser_type_launch_args(), fixture, QA Renomear Empenhos — pirâmide de testes com evidência headless. EN — Full QA…, alternar_regra(), excluir_campo_busca(), listar_campos_busca(), listar_quarentena(), listar_regras() (+63 more)

### Community 6 - "Rotinas Expirar e Podar"
Cohesion: 0.05
Nodes (65): expirar_imagens_orfas(), Remove imagens não concretizadas em postagem (órfãs há +5 min). Uma imagem é…, _cfg(), cfg_expiracao_min(), cfg_lote_arquivos(), cfg_lote_mb(), cfg_usuario_gb(), expirar_antigos() (+57 more)

### Community 7 - "Empenho BD Manipulador"
Cohesion: 0.04
Nodes (67): anonimizar_usuario(), anotar_arquivos(), arquivo_ja_processado(), arquivo_pendente(), _arquivo_registrado_no_bd(), _basename_sem_ext(), _campos_busca_ativos(), contar_quarentena_pendente() (+59 more)

### Community 8 - "Diretrizes de Desenvolvimento"
Cohesion: 0.07
Nodes (65): AGENTS.md (fonte de verdade do desenvolvimento), Anti-disconnect: handlers nunca bloqueiam o event-loop, Arquitetura modular (mod_*) com bancos isolados por módulo, CrudBase (padrão obrigatório de acesso a dados), init_db (seed idempotente de usuários), Língua Ubíqua do DDD (vocabulário de negócio em PT-BR), Entry point único main.py, Módulo mod_auditoria (+57 more)

### Community 9 - "Configs Especificas Auditoria"
Cohesion: 0.09
Nodes (57): tentar_login(), mostrar_administracao(), _resetar(), _salvar(), Render the audit administration panel (colors + specific settings). Monta o…, mod_edit_pdf_bd_manipulador_hash_sha256, nome_padronizado(), Builds the standardized file name: dataHora_usuario_operacao_nome.pdf. O nome… (+49 more)

### Community 10 - "Testes Infra e Paridade"
Cohesion: 0.04
Nodes (36): Teste unitário da paridade SQLite/PostgreSQL (mod_intranet/banco_conexao.py).…, Editor WYSIWYG do Blog — upload de imagens e expiração de órfãs. EN: Blog…, _eco_regex(), falha_suave, valida_regex, Cobertura total: smoke de import + contrato de TODAS as funcoes/classes usadas.…, _sempre_falha(), _soma() (+28 more)

### Community 11 - "Gestao Usuarios Core"
Cohesion: 0.08
Nodes (54): alterar_senha_admin(), _audit(), bloquear_usuario(), criar_usuario(), definir_acesso(), definir_flags(), duplicar_usuario(), editar_usuario() (+46 more)

### Community 12 - "Editor PDF Testes"
Cohesion: 0.06
Nodes (51): check(), n_paginas(), pdf_sintetico(), Teste do módulo Editor de PDF (Fase 5.6) — rodar manualmente: python…, mod_edit_pdf, cfg_tema(), _cota_global_bytes(), _log() (+43 more)

### Community 13 - "Painel Admin Auditoria"
Cohesion: 0.06
Nodes (46): checar(), main(), Teste standalone do helper central de tema (mod_intranet/tema_modulo.py).…, Teste do Config do módulo Intranet: Aplicar por card, aparência, avisos e…, config_backend(), Returns the backend selector as a dict (`banco_tipo`, `postgres_url`). Usado…, obter_grafana_url(), Resolves the Grafana base URL (env GRAFANA_URL wins over tb_config). Resolve a… (+38 more)

### Community 14 - "Admin Cadastros Impressao"
Cohesion: 0.06
Nodes (51): excluir_responsavel(), excluir_secretaria(), excluir_setor(), Physically deletes a department (setors cascade; requests keep FK NULL). Exclui…, Physically deletes a unit (responsáveis cascade; requests keep FK NULL). Exclui…, Removes an authorization grant by id and audits it. Remove um vínculo de…, _admin_cotas(), atualizar() (+43 more)

### Community 15 - "Testes Tema Central"
Cohesion: 0.07
Nodes (46): _cfg(), Fetch an auditoria config value, returning default on failure., Fetch a theme config value, returning default on failure., _tema(), Persists the backend selector (`banco_tipo`, `postgres_url`). Grava no arquivo…, salvar_backend(), get_config(), Leitura pontual de configuração via Repositorio (SQLAlchemy ORM). Camada mais… (+38 more)

### Community 16 - "Testes Rodape TestID"
Cohesion: 0.05
Nodes (34): _botoes_testid(), check(), clicar(), main(), Teste de integração headless do rodapé padrão (ui_comum) — delta a1b1650. Cobre…, _varrer(), achar_botoes(), achar_campos() (+26 more)

### Community 17 - "Camada Central de Dados"
Cohesion: 0.06
Nodes (28): Conjunto de usuários com senha provisória ainda não trocada. Usa `Repositorio`…, usuarios_com_troca_pendente(), Modulo, Module registry entry (tb_modulos). EN: Represents a registered module in the…, _log(), Centralised data access layer for mod_intranet (and module DBs). Wraps a…, Closes the session and releases the connection., Runs a SELECT on the bound database; returns rows as dicts. Executa SQL de… (+20 more)

### Community 18 - "Regras de Permissao Blog"
Cohesion: 0.06
Nodes (44): _dummy(), _pode_publicar(), Regra do módulo: usuário COMUM só LÊ o blog. Publicar/comentar/excluir é…, admin_tela(), decorator(), wrapper(), auditado(), decorator() (+36 more)

### Community 19 - "Editor PDF Testes"
Cohesion: 0.08
Nodes (45): main(), _conn(), contar_uploads_ativos(), deletar_arquivo(), obter_meus_arquivos(), mod_edit_pdf_bd_manipulador_op_cortar, mod_edit_pdf_bd_manipulador_op_dividir, mod_edit_pdf_bd_manipulador_op_dividir_partes (+37 more)

### Community 20 - "Pesquisa Levantamento Empenhos"
Cohesion: 0.07
Nodes (18): _definicoes_filtrar(), _ler(), _ler_admin(), _ler_bd(), _ler_rotinas(), _ler_telas(), Pesquisa Navegar assíncrona — fiação estática sem servidor., tb_levantamento + FTS no banco do módulo, fallback LIKE, presença. (+10 more)

### Community 21 - "Empenho BD Manipulador"
Cohesion: 0.08
Nodes (45): test_tipos_especiais(), atualizar_levantamento_renomeado(), detectar_documentos_no_pdf(), detectar_tipo_especial(), eh_multiplo_documento(), extrair_dados_empenho(), extrair_dados_tipo_especial(), extrair_texto_pdf() (+37 more)

### Community 22 - "App Legado Renomeador"
Cohesion: 0.08
Nodes (21): App, arquivo_esta_estavel(), buscar_campo(), extrair_dados(), extrair_texto_primeira_pagina(), montar_novo_nome(), obter_prefixo(), Renomeador de Empenhos - Prefeitura de Monte Santo de Minas… (+13 more)

### Community 23 - "Nucleo Solicitacao Impressao"
Cohesion: 0.09
Nodes (44): test_solicitacoes(), Opens a connection to the module's own database (WAL). Conexão via…, agrupar_solicitacoes_em_lote(), _conn(), criar_solicitacao(), enviar_solicitacao_por_email(), gerar_zip_solicitacoes(), listar_arquivos_auditoria() (+36 more)

### Community 24 - "Testes Integracao OTel"
Cohesion: 0.09
Nodes (41): main(), Test script for OTel LGTM stack integration. Script de teste para verificar se…, Test Docker detection., Test OTel stack status., Test OTel info display., Test OTel integration import., test_docker_detection(), test_otel_import() (+33 more)

### Community 25 - "Provisionamento Grafana"
Cohesion: 0.07
Nodes (37): argparse, ensure_folder(), main(), provision_dashboard(), Grafana Dashboard Provisioning - Intranet Modular Provisions dashboards into…, Perform an HTTP request to Grafana with basic auth., Ensure the target folder exists and return its UID., Upload a single dashboard JSON. (+29 more)

### Community 26 - "Autenticacao e Downloads"
Cohesion: 0.09
Nodes (38): bcrypt, baixar_pdf_impressao(), Rota de download do PDF da solicitação (com marca d'água se ativa). Protegida:…, autenticar(), chaves_ativas(), chaves_desativadas(), editar_meu_perfil(), eh_admin_do_modulo() (+30 more)

### Community 27 - "Nucleo do Modulo Blog"
Cohesion: 0.07
Nodes (26): Any, Seed of "how-to" blog posts for the common user (Editor PDF, Print Request,…, glob, loguru, Diagnostic script — prints audit-related keys from the central tb_config.…, Blog module — posts and comments with nh3 sanitization (route /blog). Módulo…, configurar(), _console_valido() (+18 more)

### Community 28 - "Testes Ativacao Ativos"
Cohesion: 0.06
Nodes (8): Testes funcionais do assistente de ativação (`mod_intranet/ativacao.py`).…, Roda iniciar() com _TTY=True e serviços mockados; devolve (cfg, saída)., Relógio fake: avança 1 s por chamada (simula o tempo real do loop)., _Relogio, _rodar_iniciar(), csv, io, Audit module screen — read-only viewer of the per-module audit trail. Tela do…

### Community 29 - "Testes Editor e Carrossel"
Cohesion: 0.10
Nodes (32): achar_botoes(), check(), clicar(), main(), Teste do modo de exibição CARROSSEL do Blog (mod_blog/telas.py). Renderiza a…, _varrer(), _cards_blog(), check() (+24 more)

### Community 30 - "Paginas Principais do App"
Cohesion: 0.12
Nodes (32): atexit, fastapi_responses, get, iniciar_agendador(), page_auditoria(), page_blog(), page_configuracoes(), page_edit_pdf() (+24 more)

### Community 31 - "Menu e Ferramentas UI"
Cohesion: 0.09
Nodes (32): hash_arquivo(), Retorna hash SHA-256 de um arquivo., ferramenta_cortar(), ferramenta_fontes(), ferramenta_juntar(), _ferramenta_nome(), ferramenta_reduzir(), gerar_matriz_organizador() (+24 more)

### Community 32 - "Tema Escuro e Sessoes"
Cohesion: 0.09
Nodes (31): definir_tema_escuro(), Fecha a sessão deste navegador; sem hash, fecha todas (comportamento antigo)., True se o usuário prefere o tema escuro (config per-usuário). Preferência de…, Define a preferência de tema (escuro/claro) do usuário., registrar_logout(), tema_escuro(), favicon_versao(), mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba). (+23 more)

### Community 33 - "Sessoes e Botoes Admin"
Cohesion: 0.12
Nodes (30): obter_email_usuario(), E-mail cadastrado do usuário ("" quando ausente). Delega ao módulo de gestão de…, pasta_monitorada(), Pasta monitorada principal do módulo (primeira da lista). Legado: usado pela…, Browse tab: protected navigation of monitored folders (PDFs only). Navegação…, _tela_navegar(), _alternar_filtro(), _alternar_selecao() (+22 more)

### Community 34 - "Formatacao HTML Blog"
Cohesion: 0.07
Nodes (17): Controles de imagem do editor do Blog — alinhar/esticar. EN: Blog editor image…, HTMLParser, ajustar_imagem_html(), _FormatadorBlog, formatar_conteudo_para_exibicao(), _largura_imagem(), _markdown_em_html(), _markdown_leve() (+9 more)

### Community 35 - "Integracao OpenTelemetry"
Cohesion: 0.07
Nodes (29): Exception, configurar_log_otel(), finalizar_otel(), inicializar_otel(), _obter_config(), obter_endpoint(), OpenTelemetry integration for Intranet Modular. This module provides…, Initialize OpenTelemetry SDK. Inicializa o SDK do OpenTelemetry. Com… (+21 more)

### Community 36 - "Dialogos de Sessoes"
Cohesion: 0.10
Nodes (28): _dlg_excluir(), _dlg_excluir_definitivo(), excluir(), excluir(), _dlg_sessoes(), _duracao(), refresh_interno(), _gest_bloq() (+20 more)

### Community 37 - "Testes Paridade SQLite/Postgres"
Cohesion: 0.09
Nodes (30): banco_modulo(), conexao(), conexao_central(), _dsn_publico(), engine_disponivel(), garantir_bancos_postgres(), _garantir_bd_postgres(), _ler_config_sqlite() (+22 more)

### Community 38 - "Perfis e Seed Auditoria"
Cohesion: 0.11
Nodes (29): Armadilha hidden sm:*/md:* no NiceGUI 3.15, Perfil administrador_geral, Perfil administrador_modulo, Usuários seed (master/qacomum/qamaster), Perfil comum (usuário comum), Modo carrossel do Blog (rotação automática), mod_blog — Módulo Blog, Sanitização HTML nh3 (gravação e renderização) (+21 more)

### Community 39 - "Seguranca Aplicar e Shutdown"
Cohesion: 0.08
Nodes (18): Testes de seguranca do Aplicar async + superficies criticas (standalone).…, Shutdown gracioso — agendador e servidor de documentação. EN: Graceful shutdown…, _SrvFalso, habilitada_no_boot(), parar_servidor(), Embedded MkDocs documentation: static build + serving. Documentação MkDocs…, Para o servidor de documentação (idempotente, fail-soft). Encerra o…, Lê tb_config docs_ativo (padrão ligada). Fail-soft: erro = ligada. (+10 more)

### Community 40 - "Docs Requisitos e Riscos"
Cohesion: 0.09
Nodes (14): perfis de usuário (comum, administrador_modulo, administrador_geral), risco storage_secret placeholder (main.py), mod_blog, mod_edit_pdf (edição de PDF), mod_gest_cad_usuario (gestão de usuários), mod_renomear_empenho (renomeador de empenho), mod_solicita_impressao (solicitação de impressão), agendadores em segundo plano (APScheduler) (+6 more)

### Community 41 - "Proxy Conexao Postgres"
Cohesion: 0.10
Nodes (8): _ConexaoPostgres, _CursorPostgres, _ddl_postgres(), Translates SQLite CREATE TABLE DDL into PostgreSQL-compatible DDL. Lida com os…, psycopg2 cursor proxy: translates `?`→`%s`, SQLite DDL/PRAGMA and captures…, Splits a script on ';' and runs each statement (SQLite emulation)., Converts Postgres datetime/date to string (SQLite-compatible)., psycopg2 connection proxy exposing the DBAPI used by the modules.

### Community 42 - "FormularioBuilder UI"
Cohesion: 0.10
Nodes (18): _log(), FormularioBuilder, criar(), criar(), criar(), criar(), _log(), Registers a numeric field (`ui.number` com min/max/step). Mesmo padrão visual… (+10 more)

### Community 43 - "Testes Levantamento Empenho"
Cohesion: 0.11
Nodes (24): Levantamento do Renomear Empenhos — leitura anexada à listagem. EN: Empenhos…, _isolamento_pytest(), main(), _pdf(), fixture, Teste do fluxo do módulo Renomear Empenhos. Valida: identificação dos campos…, Aponta o banco e a pasta monitorada do módulo para um ambiente temporário,…, Sob pytest, isola banco + pasta monitorada em temp (igual ao main()), para não… (+16 more)

### Community 44 - "Scanner de Portas"
Cohesion: 0.10
Nodes (24): concurrent_futures, _cli_app(), cli_opcoes(), Builds the Typer app with the boot options (help em PT-BR). `python main.py…, Parses the CLI options with Typer; returns a dict of the values. `--help`…, escanear_portas(), _executar(), portas_com_servico() (+16 more)

### Community 45 - "Logger Auditoria e Blog"
Cohesion: 0.11
Nodes (26): _log(), Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log., extrair_segmentos_mermaid(), listar_comentarios(), obter_habilitar_mermaid(), Lê as tags permitidas (config local do módulo primeiro, fallback na central),…, Whether Mermaid diagrams are enabled in posts (configurable). Lê…, Lists comments of a post in chronological order (via CrudBase). Lista `(id,… (+18 more)

### Community 46 - "Editor Blog Markdown"
Cohesion: 0.09
Nodes (21): Markdown dentro do editor WYSIWYG do Blog. EN: Markdown inside the WYSIWYG…, Mermaid sempre ao fim da postagem — padrão do Blog. EN: Mermaid diagrams always…, montar_pagina(), page, html, html_parser, contar_postagens(), mover_mermaid_para_fim() (+13 more)

### Community 47 - "CrudBase Legado"
Cohesion: 0.11
Nodes (14): bd_criador.py legado/morto (schema real em bd_manipulador), CrudBase, Runs one statement with guaranteed connection close (try/finally). Executa…, Yields a cursor within an atomic multi-statement transaction. Transação atômica…, Runs a SELECT returning all rows (list of tuples)., Runs a SELECT returning the first row (or `None`)., Runs an INSERT with commit, returning the new `lastrowid`., Runs an UPDATE/DELETE with commit, returning `rowcount`. (+6 more)

### Community 48 - "Grants de Acesso Modulos"
Cohesion: 0.14
Nodes (25): math, listar_acessos(), Lists the user's per-module grants (modulo_chave, papel, liberado_por, data)., _aplicar_acessos(), _dlg_duplicar(), salvar(), _dlg_editar(), salvar() (+17 more)

### Community 49 - "Testes Paridade SQLite/Postgres"
Cohesion: 0.10
Nodes (20): Ordem do menu hambúrguer — padrão + persistência após reorder + restart. EN:…, dataclasses, mod_intranet_models, Configuracao, Models package for mod_intranet — dataclasses + SQLAlchemy ORM. Provides type-…, Key-value configuration entry (tb_config). EN: Represents a single key=value…, User session entry (tb_sessoes) with LGPD tracking fields. EN: Represents an…, Sessao (+12 more)

### Community 50 - "QA Empenho Playwright"
Cohesion: 0.11
Nodes (20): Backend sem browser — FTS 1 letra, levantamento presença, EE string., TestIntegracaoBackend, _fts_escape(), _fts_query_prefixada(), levantar_arquivos(), listar_empenhos(), _nome_final_especial(), pesquisar() (+12 more)

### Community 51 - "Exibicao Carrossel Blog"
Cohesion: 0.13
Nodes (23): definir_postagem_unica_id(), Fixa o id da postagem exibida no modo 'unica' (None/'' = mais recente). Grava…, mostrar_tela(), ao_editar(), _aplicar_carrossel_exib(), _aplicar_historico_exib(), _aplicar_unica_exib(), atualizar() (+15 more)

### Community 52 - "Estilizacao Home Visual"
Cohesion: 0.11
Nodes (22): aplicar_framework(), aplicar_modelo(), classes_card_resumo(), classes_stat(), classes_wrap_resumo(), _get_config_safe(), injetar_pic_suave(), injetar_resumo_overrides() (+14 more)

### Community 53 - "Login e Sessao em Banco"
Cohesion: 0.11
Nodes (22): Fase 1: autenticacao master/master, gravacao de sessao em tb_sessoes (cookie…, test_login_e_sessao_em_banco(), nome_de_tratamento(), _podar_sessoes(), precisa_trocar_credenciais(), precisa_trocar_senha(), Retenção LGPD: mantém as N sessões mais recentes por usuário. Configuração…, Registra sessão e devolve o cookie_hash. Usa `Repositorio` (SQLAlchemy ORM)… (+14 more)

### Community 54 - "Contadores Auditoria"
Cohesion: 0.19
Nodes (21): _conta_auditoria(), _orquestrar_resumo_dados(), Coleta os 9 contadores do Resumo — 5 base + fila impressão, quarentena, pdf…, buscar_logs(), contar_registros(), _extrair_modulo(), _garantir_tabela_auditoria(), get_auditoria_connection() (+13 more)

### Community 55 - "Tela Busca de Logs"
Cohesion: 0.20
Nodes (20): mostrar_tela(), _adicionar_campo(), _atualizar_tabela(), _buscar_logs(), _campos_ativos(), _cfg(), _exportar_csv(), _limpar_filtros() (+12 more)

### Community 56 - "Tabelas e Listas UI"
Cohesion: 0.14
Nodes (10): GradeTabela, _log(), PainelLista, Standardized listing panels: GradeTabela (ui.grid) and PainelLista. Componentes…, Builds the panel (search field + body); returns the container.…, Re-renders the body (count/pagination/grade) from the first page. Deve ser…, Returns the loguru logger bound to the core module ("intranet"). Logger loguru…, Standard `ui.grid` table (caption header + cells + action column). Tabela em… (+2 more)

### Community 57 - "Frameworks CSS Embarcados"
Cohesion: 0.10
Nodes (20): CSS Frameworks Embarcados (README), Bootstrap 5.3.8 (rota dedicada, MIT), Bulma 1.0.2 (mantido em disco, pode colidir com Quasar, MIT), Chota 0.8.0 (rota dedicada, leve, MIT), DaisyUI 5.6.8 + themes (sobre Tailwind v4, MIT), Foundation 6.8.1 (rota dedicada, pesado, MIT), Materialize 1.0.0 (rota dedicada, pesado, MIT), Milligram 1.4.1 (rota dedicada, leve, MIT) (+12 more)

### Community 58 - "Smoke Campos Senha"
Cohesion: 0.13
Nodes (18): _acesso_negado(), mostrar_tela(), novo_usuario(), Renders the 'access restricted' panel for non-admin users., Renders the user management screen (admin-only). Monta a tela completa:…, barra_acoes(), _botoes_acoes(), cabecalho() (+10 more)

### Community 59 - "Testes Fluxo Blog"
Cohesion: 0.26
Nodes (18): _admin_disponivel(), main(), ok(), Teste do módulo Blog (mod_blog) — teste_fluxo_blog. Valida: sanitização XSS…, teste_auditoria_central(), teste_carrossel(), teste_config_local(), teste_conversores() (+10 more)

### Community 60 - "Verificacao UI Comum"
Cohesion: 0.11
Nodes (6): _bruto(), _campo_ordem(), Verificação da fábrica central de UI (`ui_comum` + helpers de tela). Script…, Visual state tuple of a stub element (props/classes/style/tooltip/cb). Tupla de…, hashlib, types

### Community 61 - "Posts e Comentarios Blog"
Cohesion: 0.19
Nodes (19): auditado, atualizar_postagem(), criar_comentario(), despublicar_postagem(), excluir_postagem(), excluir_postagens_em_lote(), _log(), publicar_postagem() (+11 more)

### Community 62 - "Visual Renomear Empenho"
Cohesion: 0.13
Nodes (10): eh_bootstrap(), eh_framework(), eh_hibrido(), eh_pic(), _get_config_safe(), ler_modelo(), Visual switcher for mod_renomear_empenho — uma tela por CSS disponível. Módulo…, Lê o modelo visual atual (pic|bootstrap), fail-soft para 'pic'. (+2 more)

### Community 63 - "Nova Solicitacao Upload"
Cohesion: 0.15
Nodes (15): listar_secretarias(), Lists departments (id, nome, sigla, cota, limite_pedidos, ativo). Lista as…, _admin_solicitacoes(), ao_aba(), atualizar(), New-request tab: multi-PDF drafts with countdown + form + submission. Upload…, Admin sub-tab: PEDIDOS grouped by secretaria -> setor, with status tabs and…, _tela_nova() (+7 more)

### Community 64 - "Specs E2E Login/Header"
Cohesion: 0.18
Nodes (11): { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, coletarErros(), ehRuido() (+3 more)

### Community 65 - "E2E Admin e Lote Empenhos"
Cohesion: 0.25
Nodes (8): _abrir_navegar(), _aguardar_contagem(), _fazer_login(), _fechar_dialogos_bloqueadores(), Fluxo real headless: login → /renomear-empenho → digitar no campo., Admin: switch automática; lote spinner — só localhost., TestE2EAdminELote, TestE2ENavegarPesquisa

### Community 66 - "Testes Fabrica Documentos"
Cohesion: 0.12
Nodes (6): assets_test, Testes da fábrica de documentos fictícios (faker + pytest). Validam:…, TestFabricaCoberturaCampos, TestFabricaDeterministica, TestFabricaNomesImpressora, TestFabricaPontaAPonta

### Community 67 - "Contexto Sessoes LGPD"
Cohesion: 0.17
Nodes (15): contextvars, capturar_contexto(), contexto_atual(), _extrair(), _info(), limpar_contexto(), mac_best_effort(), Resolve MAC via ARP para IPs da mesma sub-rede (best-effort). HTTP não expõe… (+7 more)

### Community 68 - "Registro de Modulos"
Cohesion: 0.12
Nodes (16): alterar_rota_modulo(), chaves_nativas(), excluir_modulo(), _garantir_tb_modulos(), nome_do_modulo(), Registers a NEW (future) module, born unavailable until activated. Cadastra um…, Reorder display order of modules (sidebar, user management). Reordena a ordem…, Changes a module's page route (URL) and re-registers it live. Altera a rota/URL… (+8 more)

### Community 69 - "Ferramentas Seguranca"
Cohesion: 0.17
Nodes (15): Auditoria de Segurança do Menu Hambúrguer (12/09/2026), bandit 1.9.4 (SAST Python), Ferramentas e Práticas de Segurança (DevSecOps), gitleaks 8.24.3 (segredos no histórico git), pip-audit 2.10.1 (CVEs de dependências), safety 3.8.1 (CVEs conhecidas), semgrep 1.176.1 (SAST multi-regra), Riscos de Segurança em IA/ML (+7 more)

### Community 70 - "Instrumentacao OTel App"
Cohesion: 0.18
Nodes (14): fastapi, logging, _contadores(), OpenTelemetry application instrumentation for Intranet Modular. This module…, Cria e retorna os objetos de metricas (no-op se OTel indisponivel)., criar_contador(), criar_gauge(), criar_histograma() (+6 more)

### Community 71 - "Listagem e Exibicao Blog"
Cohesion: 0.14
Nodes (15): listar_postagens(), listar_postagens_por_ids(), obter_modo_exibicao(), _ordem_sql(), Retorna o modo de exibição do blog ('unica', 'historico' ou 'carrossel'). Lê a…, Lists posts matching the given ordered ids (carousel selection). Retorna…, Converte ordem ('ASC'/'DESC') para SQL seguro., Lists posts (id, titulo, conteudo, autor, data_criacao) with ordering. Lista… (+7 more)

### Community 72 - "Dashboards e Stack LGTM"
Cohesion: 0.19
Nodes (13): Dashboards Intranet (Visao Geral/Mimir, Traces/Tempo, Logs/Loki), dashboards.yml - provider 'Intranet Dashboards' (update 30s), postgres/docker-compose.yml - backend opcional PostgreSQL 16, Docker - Stack OTel LGTM (README), Credenciais master/master compartilhadas com admin da Intranet, Grafana OTel LGTM stack (Grafana + Loki + Tempo + Mimir + OTel Collector), instrumentar_aplicacao(), _observer_requisicoes() (+5 more)

### Community 73 - "Guarda Integridade Modular"
Cohesion: 0.16
Nodes (11): _alvo_top(), _arquivos_py(), _imports_de(), _visitar(), _modulo_de(), Guarda estrutural do isolamento modular (AST, sem importar nada). Structural…, mod_x do arquivo, 'main' para main.py, None para o resto., mod_x / main do dotted name importado (None se stdlib/terceiro). (+3 more)

### Community 74 - "Spec E2E Editor Blog"
Cohesion: 0.15
Nodes (10): fs, { login, coletarErros, errosFatais }, os, path, PNG_1X1, { test, expect }, IMPORTANT: keep the reminder string free of backticks and $(...) constructs., ref_fs (+2 more)

### Community 75 - "Fixtures PDF e Infra Teste"
Cohesion: 0.24
Nodes (13): Fábrica de documentos fictícios do módulo Renomear Empenhos. Factory of…, DOC_0201.pdf - fixture PDF ficticio de empenho (massa de teste), EC_24.pdf - fixture PDF ficticio de empenho (massa de teste), EE_9570.pdf - fixture PDF ficticio de empenho (massa de teste), EG_89.pdf - fixture PDF ficticio de empenho (massa de teste), Pasta de testes assets/test (README), Convencoes obrigatorias de teste (standalone, exit-code, data-testid, docstring bilingue, sem destruicao), Infra E2E Playwright (e2e specs, helpers.js, _global_setup.js, playwright.config.js, package.json) (+5 more)

### Community 76 - "Wrappers Elementos NiceGUI"
Cohesion: 0.14
Nodes (3): _El, _fab(), _cria()

### Community 77 - "Construtor Documentacao"
Cohesion: 0.18
Nodes (12): _build(), construir_e_montar_documentacao(), iniciar_servidor(), montar(), porta_documentacao(), Build + mount + start the docs server. Falha NUNCA derruba o servidor. Gera o…, Para o botão de Configurações: rebuild + garante rota. (ok, mensagem)., Gera site/ com o mkdocs do próprio venv. Retorna (ok, erro_curto). (+4 more)

### Community 78 - "Hora Servidor NTP"
Cohesion: 0.19
Nodes (14): definir_ntp_ativa(), hora_servidor(), hora_servidor_str(), _ler_ntp_ativa(), _log(), _obter_offset_ntp(), offset_ntp(), Returns the server's current datetime (NTP-corrected when available). A hora… (+6 more)

### Community 79 - "Marca Dagua e Listas"
Cohesion: 0.14
Nodes (13): aplicar_marca_dagua(), listar_impressoras(), obter_config(), Minutes a draft survives before automatic removal (default 10, min 1). Minutos…, Minutes before the file is deleted after printing (default 10, min 1). Minutos…, Generates a new PDF (copy) with a watermark if active. Returns the final PDF…, Reads a module-local config key (tb_configuracoes_modulo, via CrudBase). Lê uma…, Lists registered printers (id, nome, papel, cor, fv, sulf, driver, ativo).… (+5 more)

### Community 80 - "Smoke Campos Senha"
Cohesion: 0.15
Nodes (7): estado(), Real-NiceGUI smoke test for password fields via `ui_comum.campo_texto`. Smoke…, Visual state of a real NiceGUI element (props/classes/style/children). Estado…, index(), page, Teste unitário do helper de tema (mod_intranet/tema_modulo.py) — delta a1b1650.…, nicegui

### Community 81 - "Wrappers Dialogos NiceGUI"
Cohesion: 0.15
Nodes (3): _El, _fab(), _cria()

### Community 82 - "Injetores Framework Visual"
Cohesion: 0.20
Nodes (12): PIC - visual padrao (Quasar nativo suave, sem CSS externo), aplicar_framework(), aplicar_modelo(), injetar_bootstrap_overrides(), injetar_hibrido(), injetar_pic_suave(), visual.MODELO_PADRAO = 'pic' (mod_renomear_empenho/visual.py), Injeta o CSS local do framework (str) ou compat bool (True=bootstrap). (+4 more)

### Community 83 - "Admin Relatorio Sub-aba"
Cohesion: 0.20
Nodes (11): _admin_relatorio(), gerar(), _prazo_fixo(), _admin_relatorio(), gerar(), _prazo_fixo(), Renders a small report table with header + rows (or an empty note). Monta um…, _tabela_relatorio() (+3 more)

### Community 84 - "Compose LGTM"
Cohesion: 0.47
Nodes (11): compose.yml - definicao dos servicos LGTM, Servico Grafana (3000, admin master/master via env), Servico Loki (3100, logs), Servico Mimir (9009, metricas compat. Prometheus), Servico OTel Collector (4317 gRPC / 4318 HTTP / 8888-8889), Servico Tempo (3200, traces; 4317 interno via rede Docker), datasources.yml - Loki/Tempo/Mimir com UIDs fixos (loki/tempo/mim), loki-config.yml - TSDB schema v13, compactor com retencao 7d (+3 more)

### Community 85 - "Verificar Credenciais"
Cohesion: 0.35
Nodes (10): check_docker(), check_grafana(), check_loki(), check_mimir(), check_otel_collector(), check_tempo(), main(), print_header() (+2 more)

### Community 86 - "Pacote Playwright E2E"
Cohesion: 0.18
Nodes (10): description, devDependencies, @playwright/test, name, private, scripts, e2e:headed, e2e:report (+2 more)

### Community 87 - "Renderizacao Feed Blog"
Cohesion: 0.25
Nodes (10): _ler_tema(), ao_toggle_selecao(), Renders a rotating carousel of selected posts (no min, auto slide). Exibe as…, _renderizar_carrossel(), montar(), anterior(), barra_acoes(), expandir() (+2 more)

### Community 88 - "Dashboard Resumo Home"
Cohesion: 0.20
Nodes (11): _construir_dashboard(), _contar_fila_para_autorizar(), _eh_autorizador_impressao(), page_dashboard(), Card de métrica do Resumo — ícone ampliado + número lateral (4 dígitos, >9999)…, Constrói o conteúdo da Home (banner + resumo dinâmico + feed)., Verifica se o usuário é responsável por autorizar impressão (qualquer…, Conta solicitações pendentes que o usuário pode autorizar (por… (+3 more)

### Community 89 - "Servir Frameworks CSS"
Cohesion: 0.29
Nodes (9): Spectre 0.5.9 (rota dedicada, leve, MIT), caminho_css(), injetar_framework(), _log(), montar_rotas_static(), Serves the embedded CSS frameworks (Bootstrap, Bulma, DaisyUI, Pico, Picnic)…, Makes /css/frameworks/* serve the local CSS files for the whole app. Registra a…, Return HTTP URL of the CSS file (None lists the available frameworks). Devolve… (+1 more)

### Community 90 - "Start.sh Stack"
Cohesion: 0.38
Nodes (9): check_docker(), print_header(), start.sh script, show_help(), show_logs(), show_status(), start_stack(), stop_stack() (+1 more)

### Community 91 - "Fabrica de Documentos"
Cohesion: 0.20
Nodes (10): criar_lote_demo(), criar_lote_principal(), criar_pdf_empenho(), nome_impressora(), Renders the PDF text lines matching every tb_campos_busca regex., Writes the fictitious record as a real PDF file., Recreates the demo mass: <pasta>/<DOC_*.pdf> with ALL fields. Recria a massa…, Generates a random printer/scanner-style file name (pending pattern). Gera nome… (+2 more)

### Community 92 - "Patches Timer NiceGUI"
Cohesion: 0.24
Nodes (9): contextlib, aplicar(), _get_context(), Patches NiceGUI timers to tolerate page teardown (no "parent slot deleted"). O…, Returns nullcontext instead of raising when the parent slot is gone., Stops the timer when its parent slot was deleted (page navegada/fechada). Um…, Aplica os patches no NiceGUI (idempotente)., _should_stop() (+1 more)

### Community 93 - "Padroes Auditoria e Nomes"
Cohesion: 0.20
Nodes (10): Audit Log Para Registrar Auditoria, Banco Exclusivo Auditoria db mod auditoria, Tabela Por Modulo Produtor tb auditoria modulo, Guarda Pagina Restrita Layout Quatro Partes, Bd Criador Legado Morto, Bd Manipulador Unico Ponto Acesso DB, Renomeacao Db Manipulador Para Bd Manipulador Auditoria, CrudBase Base CRUD WAL (+2 more)

### Community 94 - "Manuais e Licoes Aprendidas"
Cohesion: 0.22
Nodes (10): Validação ast.parse UTF-8 (integridade de arquivos), Lições Aprendidas, Manual de Uso — Administrador, Manual de Uso — Instalação, Manual de Uso — Renomeador de Empenho, Manual de Uso — Usuário Comum, POSTAGENS_PADRAO (3 seeds "Como usar"), Padrões de Codificação (+2 more)

### Community 95 - "Gestao Usuarios Core"
Cohesion: 0.20
Nodes (10): _central(), contar_sessoes_ativas(), listar_historico_sessoes(), listar_sessoes_ativas(), Opens a connection to the CENTRAL database (sessions/config only)., Sessões abertas (sem logout), agora com rastreabilidade IP/dispositivo/MAC., Counts the user's open sessions (logout_timestamp IS NULL)., {usuario: qtd_ativas} — uma única consulta para a tabela inteira. (+2 more)

### Community 96 - "Fluxo de Grupos de Impressao"
Cohesion: 0.22
Nodes (10): _atualizar_status_grupo(), autorizar_grupo(), listar_arquivos_grupo(), Lists the files of one PEDIDO (group). Lista os arquivos de um pedido (grupo):…, Updates the status (and optional fields) of ALL files in a group. Atualiza o…, Authorizes ALL files of a PEDIDO (aguardando/excedente/pendente). Autoriza…, Refuses ALL files of a PEDIDO (mandatory reason) and removes the files. Recusa…, Cancels ALL files of a PEDIDO (status=cancelado) and removes the files. Cancela… (+2 more)

### Community 97 - "Setup Credenciais Grafana"
Cohesion: 0.42
Nodes (8): check_docker(), check_grafana(), main(), print_header(), restart_grafana(), setup-grafana-credentials.sh script, show_credentials(), update_grafana_password()

### Community 98 - "Config E2E Exclusao Blog"
Cohesion: 0.22
Nodes (7): { login }, { test, expect }, { defineConfig }, path, root, venvPython, @playwright/test

### Community 99 - "Testes Funcionais Auditoria"
Cohesion: 0.50
Nodes (8): check(), main(), Teste funcional do módulo Auditoria (rastreabilidade LGPD). Roda manualmente:…, _testar_acesso(), _testar_audit_log(), _testar_indices(), _testar_poda(), _testar_prefs_campos()

### Community 101 - "Menu e Ferramentas UI"
Cohesion: 0.22
Nodes (6): mostrar_tela(), _gerar_25_temp(), _tema(), Reads a theme key from tb_config, falling back to the default (fail-soft)., Renders the Empenhos screen with its 6 internal tabs. Monta a tela:…, _tema_s()

### Community 102 - "Gestao Usuarios Core"
Cohesion: 0.25
Nodes (8): obter_papel_no_modulo(), Retorna 'administrador', 'comum' ou None., True if the user may access the module (used by the core page guard). RF-35: o…, True se o usuário tem a flag (admin global/modular passam pelo papel)., Backward-compatible alias of `validar_acesso_modulo`., tem_flag(), validar_acesso_modulo(), validar_acesso_modulo_compat()

### Community 103 - "Relatorios Agregacao Impressao"
Cohesion: 0.36
Nodes (8): _agregar_impressao(), Runs a print aggregation (status='impresso') over a period. `agrupar_por`:…, Builds the print report (status='impresso') for a period. Dicionário com totais…, relatorio_impressao(), _por_autorizador(), _por_impressor(), _por_secretaria(), _por_setor()

### Community 104 - "Consumo Cotas Mensais"
Cohesion: 0.29
Nodes (8): mes_atual(), obter_consumo(), Zeros the month's consumption (manual). Zera o consumo do mês (manual). O…, Retorna lista de (secretaria_id, secretaria_nome, setor_id, setor_nome, cota,…, Current month reference in 'YYYY-MM' format (quota period key). Chave do…, Pages already consumed in the month for the department/unit (0 if none).…, relatorio_cotas(), resetar_consumo()

### Community 105 - "Graphify Operacoes"
Cohesion: 0.29
Nodes (7): Watch Mode Auto Rebuild, Post Commit Hook, Graphify Explain Node, Graphify Path Shortest Path, Graphify Query BFS DFS, Incremental Update Reextract Changed, Graphify Full Pipeline

### Community 106 - "Global Setup Playwright"
Cohesion: 0.29
Nodes (6): { execSync }, path, root, script, venvPython, ref_child_process

### Community 107 - "Fabrica de Documentos"
Cohesion: 0.38
Nodes (7): gerar_dados_empenho(), _nome_empresa(), _nome_pessoa(), Generates one deterministic fictitious record with ALL monitored fields. Gera…, Uppercase letters/spaces only (safe for Favorecido/Recebedor regex)., _so_letras_maiusculas(), _valor_br()

### Community 108 - "Testes Solicitacao Impressao"
Cohesion: 0.33
Nodes (5): _fazer_pdf(), _novo_contexto(), Teste de UI dirigido — botões do módulo Solicitação de Impressão. Exercita os…, Cria um Client NiceGUI mínimo para os handlers usarem…, mod_solicita_impressao

### Community 109 - "Cascata LGPD Vinculos"
Cohesion: 0.33
Nodes (6): Remove postagens e comentários do usuário (LGPD). Chamado pelo módulo de gestão…, remover_vinculos_usuario(), Remove arquivos físicos, registros e cota do usuário (LGPD). Chamado pelo…, remover_vinculos_usuario(), Remove/anonimiza referências do usuário nos demais módulos (LGPD). Blog:…, _vinculos_cruzados_excluir()

### Community 110 - "Sessao SQLAlchemy Lazy"
Cohesion: 0.40
Nodes (4): Creates a new SQLAlchemy Session bound to a module database engine. Uma Session…, Lazily acquires a session if one was not provided at construction., sessaodb(), Session

### Community 111 - "Cadastros Solicitacao Impressao"
Cohesion: 0.33
Nodes (6): _eh_admin_do_modulo(), eh_responsavel_autorizacao(), _pode_autorizar(), System-wide admin OR the print module admin. Admin geral do sistema OU…, Only the responsável for the link OR the module admin may authorize. Só…, Checks whether user_nome is an authorizer for the department/unit. Verifica se…

### Community 112 - "Sanitizacao e Metricas Blog"
Cohesion: 0.60
Nodes (5): Métricas de Software, Plano de Projeto, Registro de Mudanças, Versionamento, Versionamento 1.0.AAMMDD (major.minor.data)

### Community 113 - "Tela Busca de Logs"
Cohesion: 0.40
Nodes (3): _campo_data(), _ao_escolher(), _fmt_data()

### Community 114 - "Testes Email Docs OTel"
Cohesion: 0.40
Nodes (5): _cfg(), enviar_email(), Envia e-mail via SMTP configurado. Retorna (ok, msg)., Testa a conexão/autenticação SMTP sem enviar mensagem. Retorna (ok, msg)., testar_conexao()

### Community 115 - "Seed Postagens Blog"
Cohesion: 0.50
Nodes (4): _log(), main(), Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log., Runs the seed, creating each how-to post and reporting the result. Executa o…

### Community 116 - "Spec E2E Varredura"
Cohesion: 0.50
Nodes (3): { login, coletarErros, errosFatais }, ROTAS, { test, expect }

### Community 117 - "QA Diagnostico e Seeds"
Cohesion: 0.50
Nodes (3): garantir(), Garante as credenciais dos usuários QA usados nos testes E2E. EN: Ensures the…, Idempotently fixes QA users' passwords, profiles and change flag.

### Community 118 - "Contrato Config e Hooks"
Cohesion: 0.50
Nodes (4): Tema Modulo Aparencia Padronizada, Contrato Config Central Get Config Modulo Chave, Config Local Do Modulo Via CrudBase, Registrar Hook Config

### Community 119 - "Isolamento e Motor PDF"
Cohesion: 0.50
Nodes (4): Backend Duplo SQLite PostgreSQL Um Database Por Modulo, Isolamento Um Banco Por Modulo Sem Cross Query, Motor PDF Compartilhado Pdf Operacoes Op Reutilizaveis, Lingua Ubiqua DDD Portugues BR

### Community 120 - "Script Iniciar"
Cohesion: 0.50
Nodes (3): INTRANET_FORCE_SQLITE, INTRANET_SEM_OTEL, iniciar.sh script

### Community 121 - "Rotinas de Encerramento"
Cohesion: 0.50
Nodes (4): _ao_sinal(), _encerrar(), encerrar_agendador(), Para o agendador de forma ordenada (idempotente, fail-soft). Desliga o…

### Community 123 - "Gestao Usuarios Core"
Cohesion: 0.50
Nodes (4): listar_usuarios(), _normalizar_data(), Normalizes a date value to 'YYYY-MM-DD HH:MM:SS' string. No SQLite…, Lists users with per-module access aggregated (GROUP_CONCAT). Retorna tuplas…

## Knowledge Gaps
- **100 isolated node(s):** `{ login }`, `{ test, expect }`, `{ defineConfig }`, `path`, `root` (+95 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1407 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_config()` connect `Testes Tema Central` to `Ativacao Docker e CLI`, `QA Diagnostico e Seeds`, `Testes Classes CRUD`, `Botoes Tema e Cotas`, `Quarentena e Campos Busca`, `Rotinas Expirar e Podar`, `Empenho BD Manipulador`, `Configs Especificas Auditoria`, `Testes Infra e Paridade`, `Gestao Usuarios Core`, `Editor PDF Testes`, `Painel Admin Auditoria`, `Testes Rodape TestID`, `Camada Central de Dados`, `Editor PDF Testes`, `Nucleo Solicitacao Impressao`, `Provisionamento Grafana`, `Nucleo do Modulo Blog`, `Testes Ativacao Ativos`, `Paginas Principais do App`, `Menu e Ferramentas UI`, `Tema Escuro e Sessoes`, `Sessoes e Botoes Admin`, `Integracao OpenTelemetry`, `Seguranca Aplicar e Shutdown`, `Logger Auditoria e Blog`, `Editor Blog Markdown`, `QA Empenho Playwright`, `Estilizacao Home Visual`, `Contadores Auditoria`, `Tela Busca de Logs`, `Visual Renomear Empenho`, `Hora Servidor NTP`, `Smoke Campos Senha`, `Dashboard Resumo Home`, `Testes Funcionais Auditoria`, `Menu e Ferramentas UI`, `Testes Email Docs OTel`, `Painel Admin Modulos`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `audit_log()` connect `Configs Especificas Auditoria` to `Testes Solicitacao Impressao`, `QA Diagnostico e Seeds`, `Testes Classes CRUD`, `Chaves Desativadas`, `Quarentena e Campos Busca`, `Rotinas Expirar e Podar`, `Empenho BD Manipulador`, `Botoes Tema e Cotas`, `Gestao Usuarios Core`, `Editor PDF Testes`, `Painel Admin Auditoria`, `Admin Cadastros Impressao`, `Testes Tema Central`, `Editor PDF Testes`, `Empenho BD Manipulador`, `Nucleo Solicitacao Impressao`, `Autenticacao e Downloads`, `Testes Ativacao Ativos`, `Menu e Ferramentas UI`, `Tema Escuro e Sessoes`, `Perfis e Seed Auditoria`, `Grants de Acesso Modulos`, `Login e Sessao em Banco`, `Contadores Auditoria`, `Registro de Modulos`, `Testes Funcionais Auditoria`, `Menu e Ferramentas UI`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `set_config()` connect `Configs Especificas Auditoria` to `Ativacao Docker e CLI`, `QA Diagnostico e Seeds`, `Testes Classes CRUD`, `Quarentena e Campos Busca`, `Rotinas Expirar e Podar`, `Empenho BD Manipulador`, `Testes Infra e Paridade`, `Painel Admin Auditoria`, `Testes Tema Central`, `Testes Rodape TestID`, `Camada Central de Dados`, `Editor PDF Testes`, `Nucleo Solicitacao Impressao`, `Testes Ativacao Ativos`, `Paginas Principais do App`, `Editor Blog Markdown`, `Estilizacao Home Visual`, `Contadores Auditoria`, `Tela Busca de Logs`, `Visual Renomear Empenho`, `Hora Servidor NTP`, `Smoke Campos Senha`, `Testes Funcionais Auditoria`, `Painel Admin Modulos`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `get_config()` (e.g. with `page_admin_modulo()` and `_eh_bs()`) actually correct?**
  _`get_config()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `{ login }`, `{ test, expect }`, `{ defineConfig }` to the rest of the system?**
  _100 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Testes Solicitacao Impressao` be split into smaller, more focused modules?**
  _Cohesion score 0.043061023622047244 - nodes in this community are weakly interconnected._
- **Should `Ativacao Docker e CLI` be split into smaller, more focused modules?**
  _Cohesion score 0.029871266091738534 - nodes in this community are weakly interconnected._