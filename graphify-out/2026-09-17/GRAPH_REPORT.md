# Graph Report - programacao  (2026-09-17)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2841 nodes · 6925 edges · 132 communities (122 shown, 10 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 374 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- mod_gest_cad_usuario/bd_manipulador.py
- mod_edit_pdf/bd_manipulador.py
- mod_renomear_empenho/bd_manipulador.py
- mostrar_administracao
- rotinas.py
- App
- os
- mod_solicita_impressao/bd_manipulador.py
- audit_log
- grafana_sync.py
- Repositorio
- tema_modulo.py
- _ler_telas
- ui_comum.py
- mod_solicita_impressao/telas.py
- decorator
- _conn
- _tela_navegar
- mostrar_tela
- inicializar_bancos
- teste_fluxo_renomeador.py
- registrar_rascunho
- autenticacao.py
- mod_renomear_empenho/telas.py
- test_navegar_pesquisa_empenhos.py
- _audit
- mod_gest_cad_usuario/telas.py
- observabilidade.py
- test_ativacao.py
- main.py
- get_logger
- ativacao.py
- mod_solicita_impressao/telas_administracao.py
- mod_intranet
- mod_intranet/telas.py
- otel_integracao.py
- botao
- _log
- FormularioBuilder
- test_otel.py
- CrudBase
- repositorio.py
- test_tema.py
- mod_auditoria/telas.py
- docker_instalado
- usuario_logado
- port_scanner.py
- iniciar_stack_otel
- fabrica_documentos.py
- verifica_ui_comum.py
- mostrar_tela
- home_visual.py
- mostrar_tela
- test_cobertura_total.py
- helpers.js
- registrar_login
- _fazer_login
- documentacao.py
- db_manipulador.py
- _CursorPostgres
- docker_detector.py
- listar_arquivos_grupo
- nicegui
- get_config
- teste_aba_config_intranet.py
- banco_conexao.py
- instrumentacao_app.py
- baixar_pdf_impressao
- _garantir_tb_modulos
- visual.py
- mes_atual
- _admin_configuracoes
- hora_servidor.py
- 06_blog_editor.spec.js
- _El
- decoradores.py
- _executar_e_persistir
- configurar_docker_windows
- sgbd_ativo
- listar_secretarias
- re
- test_rodape_testid.py
- teste_fluxo_blog.py
- _El
- _porta_valida
- iniciar
- contexto.py
- obter_engine_modulo
- verify-credentials.sh
- test/package.json
- get_auditoria_connection
- Dialogo
- start.sh
- teste_carrossel_blog.py
- teste_home_blog.py
- nicegui_patch.py
- _construir_dashboard
- _ConexaoPostgres
- setup-grafana-credentials.sh
- @playwright/test
- _SMTPOk
- tema_css.py
- _ArquivoFake
- favicon_versao
- get_modulos_com_auditoria
- get_tracer
- relatorio_impressao
- _global_setup.js
- eh_admin_do_modulo
- engine
- _admin_relatorio
- test_editor_pdf.py
- _encerrar
- tema_escuro
- sessaodb
- _aplicar_tema_escuro
- cancelar_rascunho
- _admin_solicitacoes
- _campo_data
- 02_varredura.spec.js
- TestFabricaCoberturaCampos
- TestFabricaDeterministica
- get
- iniciar.sh
- .opencode/package.json
- iniciar_agendador
- mod_auditoria/__init__.py
- mod_edit_pdf/__init__.py
- mod_gest_cad_usuario/__init__.py
- mod_renomear_empenho/__init__.py
- mod_solicita_impressao/__init__.py

## God Nodes (most connected - your core abstractions)
1. `audit_log()` - 111 edges
2. `notificar()` - 97 edges
3. `get_config()` - 92 edges
4. `botao()` - 90 edges
5. `usuario_logado()` - 83 edges
6. `set_config()` - 82 edges
7. `get_connection()` - 62 edges
8. `mostrar_tela()` - 61 edges
9. `mostrar_tela()` - 55 edges
10. `Repositorio` - 53 edges

## Surprising Connections (you probably didn't know these)
- `painel_backup()` --calls--> `_ler_tema()`  [INFERRED]
  mod_intranet/rotinas.py → assets/test/verifica_ui_comum.py
- `_criar()` --calls--> `criar_lote_principal()`  [INFERRED]
  mod_renomear_empenho/telas.py → assets/test/fabrica_documentos.py
- `atualizar_tabela()` --indirect_call--> `usuario_logado()`  [INFERRED]
  mod_edit_pdf/telas.py → mod_intranet/telas.py
- `_auditar_hash()` --indirect_call--> `usuario_logado()`  [INFERRED]
  mod_edit_pdf/telas.py → mod_intranet/telas.py
- `baixar_zip()` --indirect_call--> `usuario_logado()`  [INFERRED]
  mod_edit_pdf/telas.py → mod_intranet/telas.py

## Import Cycles
- 3-file cycle: `mod_intranet/autenticacao.py -> mod_intranet/bd_conexao.py -> mod_intranet/tema_modulo.py -> mod_intranet/autenticacao.py`
- 4-file cycle: `mod_intranet/autenticacao.py -> mod_intranet/bd_manipulador.py -> mod_intranet/bd_conexao.py -> mod_intranet/tema_modulo.py -> mod_intranet/autenticacao.py`

## Communities (132 total, 10 thin omitted)

### Community 0 - "mod_gest_cad_usuario/bd_manipulador.py"
Cohesion: 0.04
Nodes (95): alterar_senha_admin(), _audit(), bloquear_usuario(), _central(), _conexao_cruzada(), contar_sessoes_ativas(), criar_usuario(), definir_acesso() (+87 more)

### Community 1 - "mod_edit_pdf/bd_manipulador.py"
Cohesion: 0.05
Nodes (90): main(), _conn(), contar_uploads_ativos(), _cota_global_bytes(), deletar_arquivo(), _extrair_paginas(), hash_sha256(), _libs_da_preferencia() (+82 more)

### Community 2 - "mod_renomear_empenho/bd_manipulador.py"
Cohesion: 0.05
Nodes (79): atualizar_levantamento_renomeado(), _basename_sem_ext(), _campos_busca_ativos(), detectar_documentos_no_pdf(), detectar_tipo_especial(), editar_campos_empenho(), eh_multiplo_documento(), _evitar_colisao() (+71 more)

### Community 3 - "mostrar_administracao"
Cohesion: 0.07
Nodes (61): test_campos_busca(), alternar_regra(), excluir_campo_busca(), listar_campos_busca(), listar_quarentena(), listar_regras(), montar_nome_final(), Grava a lista de pastas monitoradas (uma por linha) em tb_config. (+53 more)

### Community 4 - "rotinas.py"
Cohesion: 0.05
Nodes (58): cfg_expiracao_min(), expirar_antigos(), File lifetime in minutes inside editorPDF (`editar_pdf_expiracao_min`, min 1)., Expiração automática (roda sem usuário logado — basta o servidor vivo). Remove…, _expirar_agora(), Força a limpeza imediata dos arquivos expirados., expirar_agora(), abrir_dialogo() (+50 more)

### Community 5 - "App"
Cohesion: 0.07
Nodes (28): App, arquivo_esta_estavel(), buscar_campo(), extrair_dados(), extrair_texto_primeira_pagina(), montar_novo_nome(), obter_prefixo(), Renomeador de Empenhos - Prefeitura de Monte Santo de Minas… (+20 more)

### Community 6 - "os"
Cohesion: 0.09
Nodes (30): mostra(), QA Diagnostico: fluxo salvar_configs -> reload -> ler valores. Testa se…, mostra(), Teste unitário do helper de tema (mod_intranet/tema_modulo.py) — delta a1b1650.…, Diagnostic script — prints audit-related keys from the central tb_config.…, init_db(), Legacy database creator — mod_auditoria (kept only for compatibility). Criador…, Creates the audit metadata table in the module's own database (legacy). Cria… (+22 more)

### Community 7 - "mod_solicita_impressao/bd_manipulador.py"
Cohesion: 0.06
Nodes (52): teste_cadastros_e_cotas(), Opens a connection to the module's own database (FKs enabled). Conexão via…, contar_pedidos_abertos(), criar_impressora(), criar_responsavel(), criar_secretaria(), criar_setor(), definir_impressora_padrao() (+44 more)

### Community 8 - "audit_log"
Cohesion: 0.08
Nodes (53): _resetar(), _salvar(), Restaura os valores padrão do card 'Configurações específicas'. Grava os…, _resetar_configs(), _app_tema(), baixar_originais(), _montar_hint(), resetar_configs() (+45 more)

### Community 9 - "grafana_sync.py"
Cohesion: 0.06
Nodes (44): argparse, ensure_folder(), main(), provision_dashboard(), Grafana Dashboard Provisioning - Intranet Modular Provisions dashboards into…, Perform an HTTP request to Grafana with basic auth., Ensure the target folder exists and return its UID., Upload a single dashboard JSON. (+36 more)

### Community 10 - "Repositorio"
Cohesion: 0.07
Nodes (26): Modulo, Module registry entry (tb_modulos). EN: Represents a registered module in the…, _log(), Centralised data access layer for mod_intranet (and module DBs). Wraps a…, Closes the session and releases the connection., Runs a SELECT on the bound database; returns rows as dicts. Executa SQL de…, Runs a DML statement on the bound database; returns rowcount. Executa SQL de…, Returns the last autoincrement id inserted on the bound database. Devolve… (+18 more)

### Community 11 - "tema_modulo.py"
Cohesion: 0.08
Nodes (45): _btn_cls(), _btn_style(), _cfg(), mostrar_administracao(), Audit module administration panel. Painel de administração do módulo Auditoria…, Fetch an auditoria config value, returning default on failure., Return CSS classes for button size., Build inline style dict for button colour. (+37 more)

### Community 12 - "_ler_telas"
Cohesion: 0.07
Nodes (18): _definicoes_filtrar(), _ler(), _ler_admin(), _ler_bd(), _ler_rotinas(), _ler_telas(), Pesquisa Navegar assíncrona — fiação estática sem servidor., tb_levantamento + FTS no banco do módulo, fallback LIKE, presença. (+10 more)

### Community 13 - "ui_comum.py"
Cohesion: 0.06
Nodes (27): _campo_impar(), Verificação das classes novas do núcleo (CrudBase, ui_painel, ui_form, ui_comum…, BotaoFabrica, campo_cor(), campo_selecao(), campo_texto(), CampoBase, CampoCor (+19 more)

### Community 14 - "mod_solicita_impressao/telas.py"
Cohesion: 0.07
Nodes (45): _autorizar_grupo(), _baixar(), _baixar_arquivo(), _cancelar_grupo(), _card_grupo(), baixar_selecionados(), baixar_selecionados_zip(), _selecionados_fisicos() (+37 more)

### Community 15 - "decorator"
Cohesion: 0.06
Nodes (40): _eco_regex(), _sempre_falha(), _soma(), admin_tela(), decorator(), wrapper(), decorator(), wrapper() (+32 more)

### Community 16 - "_conn"
Cohesion: 0.08
Nodes (44): test_solicitacoes(), agrupar_solicitacoes_em_lote(), _conn(), criar_solicitacao(), enviar_solicitacao_por_email(), extrair_numero(), gerar_zip_solicitacoes(), listar_regras_padrao() (+36 more)

### Community 17 - "_tela_navegar"
Cohesion: 0.09
Nodes (41): _arquivo_registrado_no_bd(), listar_navegacao(), pasta_monitorada(), pasta_navegavel(), _path_real(), raizes_navegacao(), Absolute normalized path (resolves '~', '.' and '..' — anti-traversal)., Protected navigation roots: monitored folders + organizer folder. (+33 more)

### Community 18 - "mostrar_tela"
Cohesion: 0.08
Nodes (36): Persists the backend selector (`banco_tipo`, `postgres_url`). Grava no arquivo…, salvar_backend(), _botao_padrao(), _campo_empilhado(), _campo_icone(), mostrar_tela(), _alertar_restart(), aplicar_banco() (+28 more)

### Community 19 - "inicializar_bancos"
Cohesion: 0.07
Nodes (25): Teste de papéis/validacão de acesso do ator (mod_intranet/autenticacao.py).…, Editor WYSIWYG do Blog — upload de imagens e expiração de órfãs. EN: Blog…, PLANO.md: bancos devem ser criados do zero quando nao existirem. Faz backup dos…, test_fresh_install_creates_empty_databases(), Teste unitário/integração das rotinas de backup (mod_intranet/rotinas.py).…, _http(), Teste de boot / Fase 2.5 — `teste_boot.py`. Valida que o sistema sobe em…, GET simples retornando (status, corpo). None se não alcançável. (+17 more)

### Community 20 - "teste_fluxo_renomeador.py"
Cohesion: 0.07
Nodes (38): Levantamento do Renomear Empenhos — leitura anexada à listagem. EN: Empenhos…, _isolamento_pytest(), main(), _pdf(), fixture, Teste do fluxo do módulo Renomear Empenhos. Valida: identificação dos campos…, Aponta o banco e a pasta monitorada do módulo para um ambiente temporário,…, Sob pytest, isola banco + pasta monitorada em temp (igual ao main()), para não… (+30 more)

### Community 21 - "registrar_rascunho"
Cohesion: 0.13
Nodes (38): criar_pdf_teste(), main(), Teste do módulo Solicitação de Impressão (mod_solicita_impressao). Valida:…, Gera um PDF simples de n_paginas para teste (PyMuPDF)., teste_contagem_e_formula(), teste_excedente(), teste_fluxo(), teste_fluxo_grupo() (+30 more)

### Community 22 - "autenticacao.py"
Cohesion: 0.09
Nodes (36): bcrypt, autenticar(), chaves_ativas(), chaves_desativadas(), editar_meu_perfil(), _gest(), listar_modulos_permitidos(), marcar_trocar_credenciais() (+28 more)

### Community 23 - "mod_renomear_empenho/telas.py"
Cohesion: 0.09
Nodes (34): hash_arquivo(), Retorna hash SHA-256 de um arquivo., ferramenta_cortar(), ferramenta_fontes(), ferramenta_juntar(), _ferramenta_nome(), ferramenta_reduzir(), gerar_matriz_organizador() (+26 more)

### Community 24 - "test_navegar_pesquisa_empenhos.py"
Cohesion: 0.08
Nodes (24): browser_type_launch_args(), fixture, QA Renomear Empenhos — pirâmide de testes com evidência headless. EN — Full QA…, Backend sem browser — FTS 1 letra, levantamento presença, EE string., TestIntegracaoBackend, ast, _fts_escape(), _fts_query_prefixada() (+16 more)

### Community 25 - "_audit"
Cohesion: 0.11
Nodes (31): hora_servidor(), Returns the server's current datetime (NTP-corrected when available). A hora…, _audit(), calcular_paginas_contabilizadas(), cancelar_grupo(), confirmar_lote(), confirmar_rascunho(), contar_paginas_pdf() (+23 more)

### Community 26 - "mod_gest_cad_usuario/telas.py"
Cohesion: 0.10
Nodes (27): math, _dlg_senha(), salvar(), _dlg_sessoes(), _duracao(), refresh_interno(), _gest_bloq(), _nomes_modulos() (+19 more)

### Community 27 - "observabilidade.py"
Cohesion: 0.08
Nodes (23): Any, Listagem de logs — arquivos com tamanho e marca de uso. EN: Log listing — files…, glob, loguru, configurar(), _console_valido(), formatar_tamanho(), gerar_logs_teste_niveis() (+15 more)

### Community 28 - "test_ativacao.py"
Cohesion: 0.07
Nodes (4): Testes funcionais do assistente de ativação (`mod_intranet/ativacao.py`).…, Relógio fake: avança 1 s por chamada (simula o tempo real do loop)., _Relogio, io

### Community 29 - "main.py"
Cohesion: 0.17
Nodes (28): atexit, page_auditoria(), page_blog(), page_configuracoes(), page_dashboard(), page_edit_pdf(), _page_empenho_forcado(), page_renomear_empenho() (+20 more)

### Community 30 - "get_logger"
Cohesion: 0.10
Nodes (17): _log(), Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log., _log(), get_logger(), Retorna o logger. Se `modulo` for informado, o registro é marcado para ir…, encerrar_agendador(), Para o agendador de forma ordenada (idempotente, fail-soft). Desliga o…, Returns the loguru logger bound to the core module ("intranet"). Logger loguru… (+9 more)

### Community 31 - "ativacao.py"
Cohesion: 0.10
Nodes (28): _abre_fecha(), _detectar_otel_rodando(), _detectar_postgres_rodando(), _msg_porta_em_uso(), _normalizar_portas(), _portas_docker_servicos_otel(), _portas_em_uso_cached(), _portas_livres() (+20 more)

### Community 32 - "mod_solicita_impressao/telas_administracao.py"
Cohesion: 0.12
Nodes (28): _admin_configuracoes(), salvar(), _admin_secretarias(), atualizar(), criar(), _admin_setores(), atualizar(), criar() (+20 more)

### Community 33 - "mod_intranet"
Cohesion: 0.08
Nodes (16): garantir(), Garante as credenciais dos usuários QA usados nos testes E2E. EN: Ensures the…, Idempotently fixes QA users' passwords, profiles and change flag., Teste unitário de e-mail, documentação e observabilidade (sem I/O real). Cobre…, Testes de seguranca do Aplicar async + superficies criticas (standalone).…, Shutdown gracioso — agendador e servidor de documentação. EN: Graceful shutdown…, _SrvFalso, mod_intranet (+8 more)

### Community 34 - "mod_intranet/telas.py"
Cohesion: 0.09
Nodes (18): Mermaid sempre ao fim da postagem — padrão do Blog. EN: Mermaid diagrams always…, Nome do usuário no menu superior — botão único sempre visível. EN: Header user-…, Rodapé escondido com reveal no hover — bloco FOOTER. EN: Auto-hide footer —…, Piloto @ui.refreshable no Blog — feed, carrossel, preview e despublicadas. EN:…, inspect, mod_blog_telas, _formatar_versao_rodape(), _mesclar_patch() (+10 more)

### Community 35 - "otel_integracao.py"
Cohesion: 0.09
Nodes (25): Exception, configurar_log_otel(), inicializar_otel(), _obter_config(), obter_endpoint(), OpenTelemetry integration for Intranet Modular. This module provides…, Initialize OpenTelemetry SDK. Inicializa o SDK do OpenTelemetry. Com…, Register an error in a span. Registra um erro em um span. (+17 more)

### Community 36 - "botao"
Cohesion: 0.12
Nodes (25): c(), Returns the text styled with rich (ANSI no terminal, plano se não-TTY)., botao(), Builds the single standardized button (delegates to `BotaoFabrica`). Wrapper…, _admin_cotas(), atualizar(), _admin_secretarias(), atualizar() (+17 more)

### Community 37 - "_log"
Cohesion: 0.11
Nodes (15): Cartao, _log(), Resolves one `tb_config` value for the field factories (fail-soft). Resolve o…, Resolves the initial value (`tb_config` via `chave` or `valor`)., Applies props/classes/style/tooltip/`ao_mudar` to the element. Sequência fixa…, Creates the `ui.color_input` with the resolved value., Creates the `ui.input`/`ui.textarea` and finishes it., Creates the `ui.select` with the resolved value. (+7 more)

### Community 38 - "FormularioBuilder"
Cohesion: 0.11
Nodes (16): FormularioBuilder, criar(), criar(), criar(), criar(), _log(), Registers a numeric field (`ui.number` com min/max/step). Mesmo padrão visual…, Registers an ISO date field (`ui.input` + máscara Quasar `date`). Campo de… (+8 more)

### Community 39 - "test_otel.py"
Cohesion: 0.13
Nodes (24): main(), Test script for OTel LGTM stack integration. Script de teste para verificar se…, Test Docker detection., Test OTel stack status., Test OTel info display., Test OTel integration import., test_docker_detection(), test_otel_import() (+16 more)

### Community 40 - "CrudBase"
Cohesion: 0.12
Nodes (13): CrudBase, Runs one statement with guaranteed connection close (try/finally). Executa…, Yields a cursor within an atomic multi-statement transaction. Transação atômica…, Runs a SELECT returning all rows (list of tuples)., Runs a SELECT returning the first row (or `None`)., Runs an INSERT with commit, returning the new `lastrowid`., Runs an UPDATE/DELETE with commit, returning `rowcount`., Runs a DELETE with commit, returning removed `rowcount`. (+5 more)

### Community 41 - "repositorio.py"
Cohesion: 0.10
Nodes (18): Teste unitário da paridade SQLite/PostgreSQL (mod_intranet/banco_conexao.py).…, Ordem do menu hambúrguer — padrão + persistência após reorder + restart. EN:…, dataclasses, datetime, conexao(), DBAPI-level connection for a module on the ACTIVE backend. sqlite: conexão…, mod_intranet_models, Configuracao (+10 more)

### Community 42 - "test_tema.py"
Cohesion: 0.11
Nodes (22): checar(), main(), Teste standalone do helper central de tema (mod_intranet/tema_modulo.py).…, _conteudo(), restaurar(), salvar(), _mudou(), _mudou_tamanho() (+14 more)

### Community 43 - "mod_auditoria/telas.py"
Cohesion: 0.11
Nodes (21): csv, Audit module screen — read-only viewer of the per-module audit trail. Tela do…, _acesso_negado(), mostrar_tela(), novo_usuario(), Renders the 'access restricted' panel for non-admin users., Renders the user management screen (admin-only). Monta a tela completa:…, abas() (+13 more)

### Community 44 - "docker_instalado"
Cohesion: 0.09
Nodes (24): _aguardar_container(), barra(), _container_existe(), docker_instalado(), fim_barra(), _imagem_baixada(), instalar_docker(), _otel_docker_ativo() (+16 more)

### Community 45 - "usuario_logado"
Cohesion: 0.16
Nodes (21): Retorna dict do usuário da sessão ou None., usuario_logado(), _painel_impressoras(), atualizar(), criar(), _def_padrao(), _excluir_imp(), _painel_impressoras() (+13 more)

### Community 46 - "port_scanner.py"
Cohesion: 0.13
Nodes (20): concurrent_futures, escanear_portas(), _executar(), portas_com_servico(), _portas_docker(), _portas_por_lsof(), _portas_por_netstat_windows(), _portas_por_ss_linux() (+12 more)

### Community 47 - "iniciar_stack_otel"
Cohesion: 0.10
Nodes (22): abrir_terminal(), _cmd(), _dir_docker(), _formatar_achados_otel(), _garantir_sdk_otel(), iniciar_stack_otel(), _mascarar_comando(), _pre_pull() (+14 more)

### Community 48 - "fabrica_documentos.py"
Cohesion: 0.15
Nodes (20): criar_lote_demo(), criar_lote_principal(), criar_pdf_empenho(), gerar_dados_empenho(), _nome_empresa(), nome_impressora(), _nome_pessoa(), Fábrica de documentos fictícios do módulo Renomear Empenhos. Factory of… (+12 more)

### Community 49 - "verifica_ui_comum.py"
Cohesion: 0.10
Nodes (7): _bruto(), _campo_ordem(), _ler_tema(), Verificação da fábrica central de UI (`ui_comum` + helpers de tela). Script…, Visual state tuple of a stub element (props/classes/style/tooltip/cb). Tupla de…, hashlib, types

### Community 50 - "mostrar_tela"
Cohesion: 0.23
Nodes (18): mostrar_tela(), _adicionar_campo(), _atualizar_tabela(), _buscar_logs(), _campos_ativos(), _exportar_csv(), _limpar_filtros(), _linha_bruta() (+10 more)

### Community 51 - "home_visual.py"
Cohesion: 0.13
Nodes (19): aplicar_framework(), aplicar_modelo(), classes_card_resumo(), classes_stat(), classes_wrap_resumo(), _get_config_safe(), injetar_pic_suave(), injetar_resumo_overrides() (+11 more)

### Community 52 - "mostrar_tela"
Cohesion: 0.13
Nodes (17): Injeta o CSS local do framework (str) ou compat bool (True=bootstrap)., mostrar_tela(), _gerar_25_temp(), _criar(), _tema(), Reads a theme key from tb_config, falling back to the default (fail-soft)., Renders the Empenhos screen with its 6 internal tabs. Monta a tela:…, _tema_s() (+9 more)

### Community 53 - "test_cobertura_total.py"
Cohesion: 0.12
Nodes (10): _log(), main(), Seed of "how-to" blog posts for the common user (Editor PDF, Print Request,…, Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log., Runs the seed, creating each how-to post and reporting the result. Executa o…, Controles de imagem do editor do Blog — alinhar/esticar. EN: Blog editor image…, Markdown dentro do editor WYSIWYG do Blog. EN: Markdown inside the WYSIWYG…, Cobertura total: smoke de import + contrato de TODAS as funcoes/classes usadas.… (+2 more)

### Community 54 - "helpers.js"
Cohesion: 0.18
Nodes (11): { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, { login, coletarErros, errosFatais }, { test, expect }, coletarErros(), ehRuido() (+3 more)

### Community 55 - "registrar_login"
Cohesion: 0.09
Nodes (18): Fase 1: autenticacao master/master, gravacao de sessao em tb_sessoes (cookie…, test_login_e_sessao_em_banco(), _podar_sessoes(), precisa_trocar_credenciais(), precisa_trocar_senha(), Retenção LGPD: mantém as N sessões mais recentes por usuário. Configuração…, Registra sessão e devolve o cookie_hash. Usa `Repositorio` (SQLAlchemy ORM)…, True se existe linha de sessão ABERTA com esse hash no banco central. Usado… (+10 more)

### Community 56 - "_fazer_login"
Cohesion: 0.25
Nodes (8): _abrir_navegar(), _aguardar_contagem(), _fazer_login(), _fechar_dialogos_bloqueadores(), Fluxo real headless: login → /renomear-empenho → digitar no campo., Admin: switch automática; lote spinner — só localhost., TestE2EAdminELote, TestE2ENavegarPesquisa

### Community 57 - "documentacao.py"
Cohesion: 0.17
Nodes (15): _passo_docs(), _build(), construir_e_montar_documentacao(), iniciar_servidor(), montar(), porta_documentacao(), Embedded MkDocs documentation: static build + serving. Documentação MkDocs…, Build + mount + start the docs server. Falha NUNCA derruba o servidor. Gera o… (+7 more)

### Community 58 - "db_manipulador.py"
Cohesion: 0.15
Nodes (17): _garantir_tabela_auditoria(), init_db_auditoria(), migrar_dados_existentes(), _nome_tabela(), Audit module — exclusive database (db_mod_auditoria.db) with one table per…, Grava a ação na tabela exclusiva do módulo em db_mod_auditoria.db. A tabela é…, Returns the audit table name for a module (`tb_auditoria_<modulo>`). Sanitiza o…, Remove a tabela tb_auditoria legada do banco central. Após a auditoria migrar… (+9 more)

### Community 59 - "_CursorPostgres"
Cohesion: 0.16
Nodes (5): _CursorPostgres, _ddl_postgres(), Translates SQLite CREATE TABLE DDL into PostgreSQL-compatible DDL. Lida com os…, psycopg2 cursor proxy: translates `?`→`%s`, SQLite DDL/PRAGMA and captures…, Converts Postgres datetime/date to string (SQLite-compatible).

### Community 60 - "docker_detector.py"
Cohesion: 0.19
Nodes (16): auto_iniciar_otel(), _compose_command(), _get_compose_path(), iniciar_otel_stack(), linux_com_docker(), otel_stack_rodando(), parar_otel_stack(), Docker and OTel detection module for Intranet Modular. This module detects if… (+8 more)

### Community 61 - "listar_arquivos_grupo"
Cohesion: 0.12
Nodes (18): _atualizar_status_grupo(), autorizar_grupo(), cancelar_solicitacao(), listar_arquivos_grupo(), Refuses a request (mandatory reason) and removes its file. Returns (ok, msg).…, Cancels an already authorized/printed request (status=cancelado). Cancela…, User cancels their own request if still pending/awaiting/over-quota. Usuário…, Removes the physical file of a request (on refuse/recall/cancel). Remove o… (+10 more)

### Community 62 - "nicegui"
Cohesion: 0.13
Nodes (13): estado(), Real-NiceGUI smoke test for password fields via `ui_comum.campo_texto`. Smoke…, Visual state of a real NiceGUI element (props/classes/style/children). Estado…, index(), page, montar_rotas_ativas(), _normalizar_rota(), Dynamic module page-route registration for NiceGUI (custom slugs persist).… (+5 more)

### Community 63 - "get_config"
Cohesion: 0.21
Nodes (16): check(), main(), Teste funcional do módulo Auditoria (rastreabilidade LGPD). Roda manualmente:…, _testar_acesso(), _testar_audit_log(), _testar_indices(), _testar_poda(), _testar_prefs_campos() (+8 more)

### Community 64 - "teste_aba_config_intranet.py"
Cohesion: 0.19
Nodes (16): achar_botoes(), achar_campos(), check(), clicar(), clicar_seguro(), main(), Teste da aba CONFIG do menu_mod em /configuracoes (módulo Intranet). Script…, Elementos da tela em ORDEM do DOM (BFS — índices = ordem de render). (+8 more)

### Community 65 - "banco_conexao.py"
Cohesion: 0.15
Nodes (16): aplicar_banco(), _garantir_tb_config(), Creates the central SQLite file + tb_config if missing (pre-boot). Idempotente:…, Persists the backend selector (banco_tipo/postgres_url) pre-boot., conexao_central(), definir_banco_tipo(), definir_postgres_url(), eh_chave_modulo() (+8 more)

### Community 66 - "instrumentacao_app.py"
Cohesion: 0.17
Nodes (15): fastapi, fastapi_responses, logging, _contadores(), OpenTelemetry application instrumentation for Intranet Modular. This module…, Cria e retorna os objetos de metricas (no-op se OTel indisponivel)., criar_contador(), criar_gauge() (+7 more)

### Community 67 - "baixar_pdf_impressao"
Cohesion: 0.13
Nodes (16): baixar_pdf_impressao(), Rota de download do PDF da solicitação (com marca d'água se ativa). Protegida:…, aplicar_marca_dagua(), obter_config(), obter_limite_pedidos_abertos(), obter_secretaria(), obter_setor(), Returns the open-request limits (department, unit) — 0 means unlimited. Lê os… (+8 more)

### Community 68 - "_garantir_tb_modulos"
Cohesion: 0.12
Nodes (16): alterar_rota_modulo(), chaves_nativas(), excluir_modulo(), _garantir_tb_modulos(), nome_do_modulo(), Registers a NEW (future) module, born unavailable until activated. Cadastra um…, Reorder display order of modules (sidebar, user management). Reordena a ordem…, Changes a module's page route (URL) and re-registers it live. Altera a rota/URL… (+8 more)

### Community 69 - "visual.py"
Cohesion: 0.16
Nodes (7): eh_framework(), eh_hibrido(), eh_pic(), _get_config_safe(), ler_modelo(), Visual switcher for mod_renomear_empenho — uma tela por CSS disponível. Módulo…, Lê o modelo visual atual (pic|bootstrap), fail-soft para 'pic'.

### Community 70 - "mes_atual"
Cohesion: 0.16
Nodes (16): definir_cota(), _incrementar_consumo(), mes_atual(), obter_consumo(), obter_ou_criar_cota(), percentual_consumo(), Adds pages to the monthly consumption (upsert on the period row). Soma páginas…, Zeros the month's consumption (manual). Zera o consumo do mês (manual). O… (+8 more)

### Community 71 - "_admin_configuracoes"
Cohesion: 0.14
Nodes (16): _admin_configuracoes(), salvar(), _admin_relatorio(), gerar(), _prazo_fixo(), _admin_setores(), atualizar(), criar() (+8 more)

### Community 72 - "hora_servidor.py"
Cohesion: 0.20
Nodes (14): definir_ntp_ativa(), hora_servidor_str(), _ler_ntp_ativa(), _log(), _obter_offset_ntp(), offset_ntp(), Hora do servidor com sincronização opcional via NTP.br (RFC 5905). EN —…, Returns the server time as a string in the given format. Retorna a hora do… (+6 more)

### Community 73 - "06_blog_editor.spec.js"
Cohesion: 0.15
Nodes (10): fs, { login, coletarErros, errosFatais }, os, path, PNG_1X1, { test, expect }, IMPORTANT: keep the reminder string free of backticks and $(...) constructs., ref_fs (+2 more)

### Community 74 - "_El"
Cohesion: 0.14
Nodes (3): _El, _fab(), _cria()

### Community 75 - "decoradores.py"
Cohesion: 0.18
Nodes (11): _dummy(), Flags finas de permissão (JSON) — catálogo, grant, bypass e decorador. EN:…, functools, mod_gest_cad_usuario, audit_reg(), Registers one action in the central audit trail (fail-soft). Wrapper fino de…, auditado(), Central decorators for cross-cutting concerns (permission, audit, fail-soft).… (+3 more)

### Community 76 - "_executar_e_persistir"
Cohesion: 0.18
Nodes (14): aplicar_portas(), _executar_e_persistir(), iniciar_postgres(), _motivo_legivel(), _porta_livre(), Starts PostgreSQL (or REUSES an already-running container) and waits until it…, Starts the chosen services, persists the config and prints the summary. Sobe…, Best-effort: replaces `orig:cont` port mappings in a compose file. (+6 more)

### Community 77 - "configurar_docker_windows"
Cohesion: 0.15
Nodes (14): _compose_cmd(), configurar_docker_windows(), _garantir_docker_compose(), instalar_docker_compose(), perguntar(), Asks a question and returns a normalized answer (default if empty).…, Returns the available docker compose command (plugin v2 or v1) or None., Installs the Docker Compose plugin when missing (best-effort, sudo). (+6 more)

### Community 78 - "sgbd_ativo"
Cohesion: 0.16
Nodes (14): config_backend(), _dsn_publico(), engine_disponivel(), _ler_config_sqlite(), obter_engine(), Returns the backend selector as a dict (`banco_tipo`, `postgres_url`). Usado…, Cached internal helper for sgbd_ativo (without env-var check)., Returns the active SGBD ('sqlite' or 'postgres') from the central file. Lê… (+6 more)

### Community 79 - "listar_secretarias"
Cohesion: 0.19
Nodes (12): listar_secretarias(), Lists departments (id, nome, sigla, cota, limite_pedidos, ativo). Lista as…, _admin_responsaveis(), atualizar(), criar(), _admin_responsaveis(), atualizar(), criar() (+4 more)

### Community 80 - "re"
Cohesion: 0.15
Nodes (6): assets_test, Teste do Dashboard mobile-first (Fase 1, item 6) + padrão de exibição. Script…, Testes da fábrica de documentos fictícios (faker + pytest). Validam:…, TestFabricaNomesImpressora, TestFabricaPontaAPonta, re

### Community 81 - "test_rodape_testid.py"
Cohesion: 0.21
Nodes (9): _botoes_testid(), check(), clicar(), main(), Teste de integração headless do rodapé padrão (ui_comum) — delta a1b1650. Cobre…, _varrer(), asyncio, collections (+1 more)

### Community 82 - "teste_fluxo_blog.py"
Cohesion: 0.42
Nodes (12): _admin_disponivel(), main(), ok(), Teste do módulo Blog (mod_blog) — teste_fluxo_blog. Valida: sanitização XSS…, teste_auditoria_central(), teste_carrossel(), teste_config_local(), teste_conversores() (+4 more)

### Community 83 - "_El"
Cohesion: 0.15
Nodes (3): _El, _fab(), _cria()

### Community 84 - "_porta_valida"
Cohesion: 0.17
Nodes (12): _cli_app(), cli_opcoes(), config_do_cli(), _config_padrao(), config_persistida(), _porta_valida(), Loads the persisted boot config from tb_config (no prompts). Carrega a…, Builds the Typer app with the boot options (help em PT-BR). `python main.py… (+4 more)

### Community 85 - "iniciar"
Cohesion: 0.18
Nodes (12): Roda iniciar() com _TTY=True e serviços mockados; devolve (cfg, saída)., _rodar_iniciar(), banner(), _confirmar_fallback_sqlite(), _escolha_1_enter(), iniciar(), Pergunta binária estrita: '1' = {rotulo_1} | ENTER/0 = {rotulo_padrao}. SOMENTE…, Pergunta sim/não com o MÍNIMO de teclas: '1' = ativa, ENTER/0 = não. SOMENTE… (+4 more)

### Community 86 - "contexto.py"
Cohesion: 0.24
Nodes (11): contextvars, capturar_contexto(), contexto_atual(), _extrair(), _info(), limpar_contexto(), Current HTTP request context (LGPD traceability). Contexto da requisição HTTP…, Com request explícito: fixa o contexto (QA/integrações). Sem request: apenas… (+3 more)

### Community 87 - "obter_engine_modulo"
Cohesion: 0.21
Nodes (12): banco_modulo(), garantir_bancos_postgres(), _garantir_bd_postgres(), obter_engine_modulo(), postgres_url(), Returns the configured PostgreSQL DSN (SQLAlchemy format). Lê `postgres_url` da…, PostgreSQL database name for a module key (mirrors SQLite file). O nome do…, Swaps the database (last path segment) in a postgresql DSN URL. (+4 more)

### Community 88 - "verify-credentials.sh"
Cohesion: 0.35
Nodes (10): check_docker(), check_grafana(), check_loki(), check_mimir(), check_otel_collector(), check_tempo(), main(), print_header() (+2 more)

### Community 89 - "test/package.json"
Cohesion: 0.18
Nodes (10): description, devDependencies, @playwright/test, name, private, scripts, e2e:headed, e2e:report (+2 more)

### Community 90 - "get_auditoria_connection"
Cohesion: 0.25
Nodes (11): _conta_auditoria(), _orquestrar_resumo_dados(), Coleta os 9 contadores do Resumo — 5 base + fila impressão, quarentena, pdf…, contar_registros(), get_auditoria_connection(), get_tabelas_auditoria(), podar_registros(), Lists the per-module audit tables found in the audit database. Retorna os nomes… (+3 more)

### Community 91 - "Dialogo"
Cohesion: 0.18
Nodes (6): Dialogo, Standard dialog + themed card as a context-manager class. Classe gerenciadora…, Enters dialog + card contexts; returns `(dlg, card)`. Sequência de criação…, Closes the card and dialog contexts (reverse order)., Opens the dialog (no-op quando o contexto ainda não entrou)., Closes the dialog (no-op quando o contexto ainda não entrou).

### Community 92 - "start.sh"
Cohesion: 0.38
Nodes (9): check_docker(), print_header(), start.sh script, show_help(), show_logs(), show_status(), start_stack(), stop_stack() (+1 more)

### Community 93 - "teste_carrossel_blog.py"
Cohesion: 0.31
Nodes (9): achar_botoes(), check(), clicar(), main(), Teste do modo de exibição CARROSSEL do Blog (mod_blog/telas.py). Renderiza a…, _varrer(), mod_blog, nicegui_elements_number (+1 more)

### Community 94 - "teste_home_blog.py"
Cohesion: 0.27
Nodes (9): _cards_blog(), check(), main(), Teste do feed do Blog na HOME (mod_intranet/main.py) — padrão de exibição.…, Post cards do blog (borda colorida border-left) presentes no DOM., _varrer(), nicegui_client, nicegui_elements_card (+1 more)

### Community 95 - "nicegui_patch.py"
Cohesion: 0.24
Nodes (9): contextlib, aplicar(), _get_context(), Patches NiceGUI timers to tolerate page teardown (no "parent slot deleted"). O…, Returns nullcontext instead of raising when the parent slot is gone., Stops the timer when its parent slot was deleted (page navegada/fechada). Um…, Aplica os patches no NiceGUI (idempotente)., _should_stop() (+1 more)

### Community 96 - "_construir_dashboard"
Cohesion: 0.22
Nodes (10): _construir_dashboard(), _contar_fila_para_autorizar(), _eh_autorizador_impressao(), Card de métrica do Resumo — ícone ampliado + número lateral (4 dígitos, >9999)…, Constrói o conteúdo da Home (banner + resumo dinâmico + feed)., Verifica se o usuário é responsável por autorizar impressão (qualquer…, Conta solicitações pendentes que o usuário pode autorizar (por…, _stat() (+2 more)

### Community 97 - "_ConexaoPostgres"
Cohesion: 0.22
Nodes (3): _ConexaoPostgres, Splits a script on ';' and runs each statement (SQLite emulation)., psycopg2 connection proxy exposing the DBAPI used by the modules.

### Community 98 - "setup-grafana-credentials.sh"
Cohesion: 0.42
Nodes (8): check_docker(), check_grafana(), main(), print_header(), restart_grafana(), setup-grafana-credentials.sh script, show_credentials(), update_grafana_password()

### Community 99 - "@playwright/test"
Cohesion: 0.22
Nodes (7): { login }, { test, expect }, { defineConfig }, path, root, venvPython, @playwright/test

### Community 101 - "tema_css.py"
Cohesion: 0.33
Nodes (8): caminho_css(), injetar_framework(), _log(), montar_rotas_static(), Serves the embedded CSS frameworks (Bootstrap, Bulma, DaisyUI, Pico, Picnic)…, Makes /css/frameworks/* serve the local CSS files for the whole app. Registra a…, Return HTTP URL of the CSS file (None lists the available frameworks). Devolve…, Adds the framework <link> to the current page <head> (per-page usage). Adiciona…

### Community 103 - "favicon_versao"
Cohesion: 0.25
Nodes (8): page_login(), tentar_login(), favicon_versao(), incrementar_contador_acessos(), Increments the global access counter — login-only, never navigation/refresh.…, mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba)., Placeholder hook para metricas de login via OTel. Sobrescrita dinamicamente por…, registrar_login_observabilidade()

### Community 104 - "get_modulos_com_auditoria"
Cohesion: 0.25
Nodes (8): buscar_logs(), _extrair_modulo(), get_modulos_com_auditoria(), Lists modules that produce audit records: [(modulo, tabela)]. Lê…, Extracts the module key from an audit table name (reverse of _nome_tabela)., Searches audit records with filters and server-side pagination. Consulta da…, _opcoes_navegacao(), _rotulo_modulo()

### Community 105 - "get_tracer"
Cohesion: 0.29
Nodes (7): instrumentar_aplicacao(), _observer_requisicoes(), Registra o middleware HTTP + metricas de login na aplicacao. Registra um…, criar_span(), get_tracer(), Get a tracer instance. Retorna uma instancia de tracer., Create a span with context manager. Cria um span com context manager.

### Community 106 - "relatorio_impressao"
Cohesion: 0.36
Nodes (8): _agregar_impressao(), Runs a print aggregation (status='impresso') over a period. `agrupar_por`:…, Builds the print report (status='impresso') for a period. Dicionário com totais…, relatorio_impressao(), _por_autorizador(), _por_impressor(), _por_secretaria(), _por_setor()

### Community 107 - "_global_setup.js"
Cohesion: 0.29
Nodes (6): { execSync }, path, root, script, venvPython, ref_child_process

### Community 108 - "eh_admin_do_modulo"
Cohesion: 0.29
Nodes (5): page_admin_modulo(), Renders the standalone administration panel for a given module. Rota dedicada…, eh_admin_do_modulo(), papel_no_modulo(), administrador', 'comum' ou None. Delega ao módulo de usuários.

### Community 109 - "engine"
Cohesion: 0.29
Nodes (6): engine(), Lazily creates/reuses the SQLAlchemy Engine for a module database. Postgres…, Builds the database URI from a SQLite file path. Uses SQLite with WAL…, True se TODAS as tabelas centrais do metadata já existem no engine. Usado para…, _tem_schema_central(), _uri()

### Community 110 - "_admin_relatorio"
Cohesion: 0.33
Nodes (6): _admin_relatorio(), gerar(), _prazo_fixo(), Renders a small report table with header + rows (or an empty note). Monta um…, _tabela_relatorio(), Admin sub-tab: print report by fixed monthly periods or custom calendar range.…

### Community 111 - "test_editor_pdf.py"
Cohesion: 0.33
Nodes (5): check(), n_paginas(), pdf_sintetico(), Teste do módulo Editor de PDF (Fase 5.6) — rodar manualmente: python…, mod_edit_pdf

### Community 112 - "_encerrar"
Cohesion: 0.33
Nodes (6): _ao_sinal(), _encerrar(), parar_servidor(), Para o servidor de documentação (idempotente, fail-soft). Encerra o…, finalizar_otel(), Shutdown OpenTelemetry SDK. Finaliza o SDK do OpenTelemetry.

### Community 113 - "tema_escuro"
Cohesion: 0.33
Nodes (6): definir_tema_escuro(), True se o usuário prefere o tema escuro (config per-usuário). Preferência de…, Define a preferência de tema (escuro/claro) do usuário., tema_escuro(), _alternar_tema(), Toggles the current user's dark/light theme preference (individual).

### Community 114 - "sessaodb"
Cohesion: 0.40
Nodes (4): Creates a new SQLAlchemy Session bound to a module database engine. Uma Session…, Lazily acquires a session if one was not provided at construction., sessaodb(), Session

### Community 115 - "_aplicar_tema_escuro"
Cohesion: 0.33
Nodes (6): _aplicar_tema_escuro(), Applies the user's dark-theme override (per-user, non-global). Aplica o tema…, _hex_para_rgb(), paleta_escura(), Converts a hex color (#RGB/#RRGGBB) to an (r, g, b) tuple., Gera a paleta do MODO ESCURO na ordem MAIS ESCURO → MAIS CLARO, do que está…

### Community 116 - "cancelar_rascunho"
Cohesion: 0.33
Nodes (6): cancelar_rascunho(), obter_rascunho(), Removes a file from disk if it exists (fail-soft). Returns True if removed.…, Fetches one upload draft as a dict (all columns) or None. Busca um rascunho de…, Removes the draft and its server file (user gave up before confirming). Remove…, _remover_arquivo_se_existir()

### Community 117 - "_admin_solicitacoes"
Cohesion: 0.40
Nodes (5): _admin_solicitacoes(), ao_aba(), atualizar(), Admin sub-tab: PEDIDOS grouped by secretaria -> setor, with status tabs and…, ao_secretaria()

### Community 118 - "_campo_data"
Cohesion: 0.40
Nodes (3): _campo_data(), _ao_escolher(), _fmt_data()

### Community 119 - "02_varredura.spec.js"
Cohesion: 0.50
Nodes (3): { login, coletarErros, errosFatais }, ROTAS, { test, expect }

### Community 122 - "get"
Cohesion: 0.33
Nodes (3): get, servir_js_impressao(), Intranet core package — central database, authentication, theme, layouts,…

### Community 123 - "iniciar.sh"
Cohesion: 0.50
Nodes (3): INTRANET_FORCE_SQLITE, INTRANET_SEM_OTEL, iniciar.sh script

### Community 124 - ".opencode/package.json"
Cohesion: 0.50
Nodes (3): dependencies, @opencode-ai/plugin, @opencode-ai/plugin

### Community 125 - "iniciar_agendador"
Cohesion: 0.67
Nodes (3): iniciar_agendador(), _passo_agendador(), Delega ao rotinas: um job de backup POR módulo (intervalo individual…

## Knowledge Gaps
- **40 isolated node(s):** `{ execSync }`, `path`, `root`, `script`, `venvPython` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1204 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_config()` connect `get_config` to `mod_gest_cad_usuario/bd_manipulador.py`, `mod_edit_pdf/bd_manipulador.py`, `mod_renomear_empenho/bd_manipulador.py`, `mostrar_administracao`, `rotinas.py`, `os`, `grafana_sync.py`, `Repositorio`, `tema_modulo.py`, `ui_comum.py`, `mod_solicita_impressao/telas.py`, `_tela_navegar`, `mostrar_tela`, `inicializar_bancos`, `autenticacao.py`, `mod_renomear_empenho/telas.py`, `test_navegar_pesquisa_empenhos.py`, `observabilidade.py`, `main.py`, `ativacao.py`, `mod_intranet`, `mod_intranet/telas.py`, `otel_integracao.py`, `_log`, `mod_auditoria/telas.py`, `mostrar_tela`, `home_visual.py`, `mostrar_tela`, `db_manipulador.py`, `teste_aba_config_intranet.py`, `visual.py`, `_admin_configuracoes`, `hora_servidor.py`, `_porta_valida`, `get_auditoria_connection`, `_construir_dashboard`, `favicon_versao`, `eh_admin_do_modulo`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `audit_log()` connect `audit_log` to `mod_gest_cad_usuario/bd_manipulador.py`, `mod_edit_pdf/bd_manipulador.py`, `mod_renomear_empenho/bd_manipulador.py`, `mostrar_administracao`, `rotinas.py`, `os`, `mod_solicita_impressao/bd_manipulador.py`, `tema_modulo.py`, `mod_solicita_impressao/telas.py`, `_conn`, `mostrar_tela`, `autenticacao.py`, `mod_renomear_empenho/telas.py`, `_audit`, `mod_gest_cad_usuario/telas.py`, `main.py`, `mod_solicita_impressao/telas_administracao.py`, `mod_intranet/telas.py`, `test_tema.py`, `mod_auditoria/telas.py`, `mostrar_tela`, `registrar_login`, `db_manipulador.py`, `get_config`, `_garantir_tb_modulos`, `_admin_configuracoes`, `decoradores.py`, `test_editor_pdf.py`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `botao()` connect `botao` to `mod_gest_cad_usuario/bd_manipulador.py`, `mod_edit_pdf/bd_manipulador.py`, `mod_renomear_empenho/bd_manipulador.py`, `mostrar_administracao`, `rotinas.py`, `audit_log`, `tema_modulo.py`, `ui_comum.py`, `mod_solicita_impressao/telas.py`, `_conn`, `_tela_navegar`, `mostrar_tela`, `autenticacao.py`, `mod_renomear_empenho/telas.py`, `mod_gest_cad_usuario/telas.py`, `mod_solicita_impressao/telas_administracao.py`, `_log`, `mod_auditoria/telas.py`, `usuario_logado`, `mostrar_tela`, `mostrar_tela`, `_admin_configuracoes`, `listar_secretarias`, `test_rodape_testid.py`, `_admin_relatorio`, `_admin_solicitacoes`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `get_config()` (e.g. with `page_admin_modulo()` and `_eh_bs()`) actually correct?**
  _`get_config()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `{ execSync }`, `path`, `root` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `mod_gest_cad_usuario/bd_manipulador.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04364035087719298 - nodes in this community are weakly interconnected._
- **Should `mod_edit_pdf/bd_manipulador.py` be split into smaller, more focused modules?**
  _Cohesion score 0.050560512468542665 - nodes in this community are weakly interconnected._