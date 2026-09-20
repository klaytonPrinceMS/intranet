# API Guide — Intranet Modular

> Routes (NiceGUI pages), key functions with `file:line` references, and per-module database tables. In case of conflict, the executable code prevails.

---

# Guia de API — Intranet Modular

> Rotas (páginas NiceGUI), funções-chave com referência `arquivo:linha` e tabelas de banco por módulo. Em conflito, prevalece o código executável.

## Rotas (páginas)

| Rota | Módulo | Chave `tb_modulos` | Acesso |
|:---|:---|:---|:---|
| `/login` | `mod_intranet` | — | público |
| `/` | `mod_intranet` | — (Home + Resumo Water + feed Blog) | usuários ativos (`pagina_restrita("Início")`) |
| `/configuracoes` | `mod_intranet` | — | `administrador_geral` (`pagina_restrita("Administração")`) |
| `/documentacao` | `mod_intranet` (MkDocs `site/`) | — | `administrador_geral` via drawer; serviça `site/` em `:8000` (`porta_documentacao`, separada de `:8080`) |
| `/admin/{chave_modulo}` | todos com `telas_administracao.py` | `blog`/`usuarios`/`auditoria`/`editar_pdf`/`empenhos`/`solicita_impressao`/`tecnico`/`filas`/`lista_telefonica` | `administrador_geral` ou `administrador_modulo` (`ler_tema` + `mostrar_administracao`) |
| `/users` | `mod_gest_cad_usuario` | `usuarios` | admin de módulo / geral |
| `/blog` | `mod_blog` | `blog` | comum (leitura) / admin (escrita) |
| `/edit-pdf` | `mod_edit_pdf` | `editar_pdf` | liberados (aba Admin: geral) |
| `/renomear-empenho` + 12 variantes `*-pic/spectre/chota/.../primer` | `mod_renomear_empenho` | `empenhos` | liberados |
| `/auditoria` | `mod_auditoria` | `auditoria` | `administrador_geral` |
| `/solicita-impressao` + `/solicita-impressao/pdf/{id}` + `/solicita-impressao/src/impressao.js` | `mod_solicita_impressao` | `solicita_impressao` | liberados (pdf exige ser solicitante/responsável/admin) |
| `/tecnico` | `mod_tecnico` | `tecnico` | liberados (software + backup owner-isolated) |
| `/filas` | `mod_filas` | `filas` | liberados (multi-filas por local, `criado_por` isolado, `Chamar próximo` + `Avançar` + preview isolado) |
| `/tv` | `mod_filas` (`mostrar_tv` com `?grupo=`) | — (pública) | **pública sem login** (TV compartilhada `?grupo=xxx`, auto-refresh 3s + bip+voz só novo id + playlist `/midia_filas` + carrossel censura-filtrado) |
| `/tv/{fila_id}` | `mod_filas` (`mostrar_tv` isolada) | — (pública) | **pública sem login** (TV isolada por fila, ícone padrão intranet, bip+voz só novo id, mídia pausada ao chamar) |
| `/midia_filas/*` | `mod_filas` (`PASTA_MIDIA` `mod_filas/midia`) | — | público (áudios MP3 elevador / vídeos MP4 propaganda, playlist global 40s quando ociosa) |
| `/lista-telefonica` | `mod_lista_telefonica` | `lista_telefonica` | liberados (organograma `Secretaria→Setor→Subsetor`, busca, `tel:`) |
| `censura` | `mod_intranet/censura.py` | `conteudo_palavras_bloqueadas` | central (Blog `criar/atualizar` bloqueia + Agregador `inserir` descarta / `listar_para_tv` filtra `LIMIT*3` / `limpar_censuradas` remove; `lower+NFD` sem acentos) |
| `/css/frameworks/*` | `mod_intranet/tema_css` | — | público (Bulma/DaisyUI/Pico/Picnic etc. locais, sem CDN) |
| `/img_postagens/*` | `mod_blog` | `blog` | público (imagens do WYSIWYG, `mod_blog/img_postagens/`) |

> Drawer 19/09/2026 (`mod_intranet/telas.py:_montar_layout` ~283–367): **Home isolado** no topo → **demais módulos em ordem alfabética por nome** (exceto trio) → **Administração** (só `administrador_geral`) → **trio fixo `Blog → Usuários → Auditoria`** (`_CHAVES_POS_ADMIN`/`_ORDEM_POS_ADMIN`/`_outros.sort`/`_render_lista_modulos`) → **Documentação** (só `administrador_geral`) → **Sair**. Sem `UPDATE` em `tb_modulos.ordem`; filtragem via `modulos_do_usuario`/`validar_acesso_modulo`. Exemplo `master`: `Home | Editor PDF, Empenhos, Filas, Lista Telefônica, Solicitação, Técnico | Administração | Blog, Usuários, Auditoria | Documentação | Sair`.

## Funções-chave

### Autenticação (`mod_intranet/autenticacao.py`)
- `autenticar(user_nome, senha)` — `:179`
- `gerar_hash_senha` / `verificar_senha` — `:161` / `:157`
- `registrar_login` — `:224`; `sessao_ativa` — `:257`; `registrar_logout` — `:276`
- `precisa_trocar_senha` — `:299`; `trocar_senha_propria` — `:336`
- `registrar_modulo` — `:87`
- `CHAVE_POR_ROTA` — mapeamento rota → chave de módulo

### Bootstrap
- `inicializar_bancos()` (`mod_intranet/mod_intranet_inicializacao_bd.py:13`) — ordem: `init_central` (tb_config/tb_sessoes/tb_modulos) → `garantir_rastreabilidade` → `init_db_auditoria` + `migrar_dados_existentes` → `init_blog` → `init_users` (seed `master`/`qacomum`/`qamaster`, senha `123456` QA, troca forçada) → `init_db_pdf` → `init_db_empenho` → `init_solicita` (ORGANOGRAMA_BASE 1000/200) → `init_db` técnico → `init_db` filas → `init_db` lista telefônica. Cria o central **antes** de importar qualquer módulo; `mod_intranet/bd_criador.py` e `bd_criador.py` dos módulos são legado/morto.

### Gestão de usuários (`mod_gest_cad_usuario/bd_manipulador.py`)
- Seed `master`/`qacomum`/`qamaster` com auto-cura de troca obrigatória (`marcar_trocar_senha`/`marcar_trocar_credenciais`) — `:136-156`, `init_db` em `bd_manipulador.py:185-224`

## Tabelas por módulo

- **Central** `db_mod_intranet.db`: `tb_config` (incl. `versao_sistema`/`versao_modulo:*`/`banco_tipo`/`postgres_url`/temas), `tb_sessoes` (com `ip`/`user_agent`/`dispositivo`/`mac` + `cookie_hash`), `tb_modulos` (`chave` UNIQUE, `nome`, `icone`, `rota`, `ativo`, `nativo`, `ordem` — seed `MODULOS_SISTEMA` 9 + núcleo).
- **Auditoria** `db_mod_auditoria.db`: `tb_auditoria_<modulo>` (uma tabela por módulo produtor — `intranet`, `usuarios`, `blog`, `editar_pdf`, `empenhos`, `auditoria`, `solicita_impressao`, `tecnico`, `filas`, `lista_telefonica`) + `tb_auditoria_meta`.
- `db_mod_gest_cad_usuario.db`: `tb_usuarios` (`user_nome` UNIQUE, `user_perfil` `comum|administrador_modulo|administrador_geral`, `user_ativo`, `user_deletado`, `user_nome_completo`) + `tb_acesso_usuario` (papel por módulo).
- `db_mod_blog.db`: `tb_postagens`/`tb_comentarios` (sanitizados por `nh3`, `blog_modo_exibicao` `carrossel` com 3 básicas), `img_postagens/` (JPG/PNG ≤5 MB, assinatura `FFD8`/`89504E47`).
- `db_mod_edit_pdf.db`: `tb_arquivos`/`tb_cota_disco` + `editorPDF/` temporários (expiração `cfg_expiracao_min` default 10 min).
- `db_mod_renomear_empenho.db`: `tb_empenhos` + `tb_indexador_pesquisa_fts5` (32 colunas, FTS5) + `tb_quarentena` + `tb_regex_regras`/`tb_campos_busca` + `doc/`/`organizadorPasta/`/`quarentena/`.
- `db_mod_solicita_impressao.db`: `tb_solicitacoes` (com `grupo_id`, `tipo_papel` `sulfite|fotografico|verge`, `cota_excedida`/`requer_autorizacao`/`grupo_id`), `tb_secretarias` (**1000 padrão via `ORGANOGRAMA_BASE`**), `tb_setores` (**200 padrão**, subsetores achatados), `tb_responsaveis_autorizacao`, `tb_cotas_impressao`/`tb_consumo_cota`/`tb_impressoras` + `solicitacaoImpressao/` (rascunhos 10 min, `MAX_ARQ=10`).
- `db_mod_tecnico.db`: `tb_backup` (`pasta_nome` UNIQUE `YYYYMMDD_HHMM_nomePc_ip`, `owner`, `ip`/`hostname`) + `tb_backup_arquivo` (`caminho_relativo`, `hash_sha256`) + pastas `software/` (download zip multi-seleção, limite `tecnico_max_zip_mb` 1024) + `backup/`.
- `db_mod_filas.db`: `tb_fila` (`Geral` seed `A000`/`ativa`/`01` + `endereco/prefixo/inicio→fim` `fim=0` infinito + `criado_por` + `tv_grupo`, `tb_fila_etapa` 3 etapas padrão) + `tb_chamada` (`fila_id` FK CASCADE, `senha`, `guiche` snapshot + `paciente_nome/etapa_nome/fila_nome`) + `tb_midia` (playlist TV `audio/video` global, `/midia_filas/*`) + `tb_config_filas` (`filas_modo_tv`, `filas_senha_prefixo`, `filas_guiche_padrao`) + `PASTA_MIDIA` `mod_filas/midia` + censura filtrada em `listar_para_tv`.
- `db_mod_lista_telefonica.db`: `tb_unidade` (`secretaria|setor|subsetor`, `parent_id` FK CASCADE, `ordem`, `telefone`) + `tb_contato` (`unidade_id` FK CASCADE, `nome`/`telefone`, `user_nome` opcional, `tipo` `vinculado|externo`, `COLLATE NOCASE`) + semente `ORGANOGRAMA_BASE` 12 secretarias (exportada para `solicita_impressao` 1000/200).

Veja [Padrões de Codificação](../padroes_codificacao/index.md) para o modelo de módulo.
