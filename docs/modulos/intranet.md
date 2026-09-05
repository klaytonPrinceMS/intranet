# Intranet Core Module — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (WAL: unified audit, config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru).

---

# Módulo Núcleo Intranet — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (auditoria unificada em WAL, configurações, sessões e cadastro de módulos) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru).

## Propósito

Pacote núcleo que centraliza o que todos os módulos compartilham: banco central (auditoria LGPD, configurações, sessões e cadastro de módulos), autenticação com sessões revogáveis, layout padrão de 4 partes com guarda de página, rotinas agendadas e a tela de personalização `/configuracoes`. **Não possui `telas.py` próprio** — suas telas são montadas pelas rotas de `main.py`.

## Banco central `db_mod_intranet.db`

Toda conexão executa `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` (`conexao_bd.py:27-31`). Tabelas:

| Tabela | Conteúdo |
|:---|:---|
| `tb_auditoria` | trilha unificada LGPD (`ip`/`user_agent` por migração) |
| `tb_config` | chave/valor — aparência, cotas, `versao_modulo:*`, `log_*`, `smtp_*` |
| `tb_sessoes` | sessões com `cookie_hash`, `ip`, `user_agent`, `dispositivo`, `mac` |
| `tb_modulos` | cadastro de módulos (nome, ícone, rota, ativo, nativo, **ordem**) |

## Funcionalidades

- **Autenticação bcrypt + sessões revogáveis**: `autenticar` → `registrar_login` (cookie_hash via `secrets`) → `sessao_ativa` revalidada a cada request; encerrar sessão pelo admin derruba o navegador.
- **Guarda de página** (`pagina_restrita`): revalida usuário/sessão/permissão e monta o layout de 4 partes (header, drawer lateral, rodapé com versões, área principal).
- **Dashboard `/`**: saudação, **feed do Blog por padrão** (RF-09), card "Resumo do sistema" (usuários ativos, postagens, auditoria) **exclusivo de administradores** (`administrador_geral` ou `administrador_modulo` — `main.py:155`), métricas em `ui.row()` responsivo (`flex-wrap`), microinterações e feedback de 2s (toast de boas-vindas + "Atualizado ✓" via `ui.timer(2.0, once=True)`). O resumo fica abaixo do banner de boas-vindas e acima do feed, em largura total.
- **Menu lateral (drawer)**: item **"Home"** no topo (rótulo "PÁGINA INICIAL", ícone `home`) navega para `/` — `layout_tela.py:135-144`.
- **Padrão de exibição**: módulo exemplo = Editor de PDF; todos os módulos ocupam **área cheia** (`w-full`) e têm o card **"Aparência"** no admin com as mesmas 6 chaves em `tb_config` (`<chave>_cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`). `aba_modulo.cabecalho()` aceita `cor_titulo`/`cor_fundo` e aplica o tema sem restart.
- **Login `/login`**: customizável por `tb_config`; com favicon dinâmico (`favicon_versao`).
- **Configurações `/configuracoes`** (só `administrador_geral`): organizada no padrão **menu_mod de abas** (`tela_configuracoes.py:189-198`) — **5 abas**: Config (cores/ícone, textos fixos, gerais RF-57), E-mail (SMTP RF-58 + teste de conexão), Módulo (páginas do sistema + registro de módulos e vínculos órfãos), Observabilidade (logs loguru + limpar todos) e Documentação (rebuild MkDocs). Barra com "SALVAR TUDO" à direita e botão "SALVAR <aba>" por aba (helper `botao_salvar_aba`, `tela_configuracoes.py:177-184`); "Restaurar padrão" por cartão. Os painéis são vinculados às abas pelo `name` do Quasar — a ordem DOM dos `ui.tab_panel` (Config, E-mail, Observabilidade, Documentação, Módulo) difere da ordem da barra, sem mudança funcional.
- **Aba "Módulo" — redesenho (05/09)**: a aba (antes "Registro/Nome de módulo") ganhou **campo de ícone editável com seletor visual** — `_campo_icone` (`tela_configuracoes.py:519-546`): input livre + pré-visualização viva + `ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS` (31 ícones, `tela_configuracoes.py:33-39`) + botão `grid_view`; reutilizado no registro de novo módulo (`tela_configuracoes.py:762`). O grid usa a constante compartilhada `COLUNAS_MODULOS` (`tela_configuracoes.py:45`) entre cabeçalho e linhas (mesmo columns/gap/padding — alinhamento corrigido). A lista de páginas é **ÚNICA** (os grupos "Indispensáveis"/"Demais" foram substituídos pela lista reordenável — ver "Reordenação de módulos" abaixo), com linhas em cards (`rounded-lg`, borda, `hover:shadow-sm`) e container `overflow-x-auto` (`tela_configuracoes.py:566-636`).
- **Módulos indispensáveis (05/09)**: `MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}` (`tela_configuracoes.py:30` e `autenticacao.py:216`) — esses módulos **não podem ser desativados**. Na aba "Módulo" eles aparecem destacados na lista única com fundo âmbar + ícone `lock` no lugar do switch (`tela_configuracoes.py:595-630`). No backend, `set_modulo_ativo` recusa a desativação com `(False, msg)` e audita `modulo_desativado_bloqueado` (`autenticacao.py:227-229`); `set_chaves_desativadas` filtra os indispensáveis (`autenticacao.py:481`); `salvar_tudo` força `ativo=1` (`tela_configuracoes.py:123`).
- **Reordenação de módulos (05/09)**: nova coluna `ordem INTEGER NOT NULL DEFAULT 0` em `tb_modulos` (`autenticacao.py:53`) com **migração idempotente** (`autenticacao.py:61-75` — `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`; nativos seguem `MODULOS_SISTEMA` 1..n, não-nativos ficam após os nativos em ordem alfabética). `modulos_registrados()` ordena por `ordem ASC, nome` (`autenticacao.py:113`); `registrar_modulo()` grava `max(ordem)+1` (`autenticacao.py:141-148`); nova função `reordenar_modulos(ator, chaves_ordenadas)` (`autenticacao.py:162-192`) grava a posição 1-based de cada chave, chaves ausentes vão ao fim, audita `modulos_reordenados` e usa try/except + loguru. Na aba "Módulo" a lista de páginas é **ÚNICA e reordenável** com setas ↑/↓ (`refresh_modulos` `tela_configuracoes.py:566-636`, `_mover` `tela_configuracoes.py:638-669`), persistindo de imediato; indispensáveis (auditoria, usuarios) destacados em âmbar com cadeado, reordenáveis porém nunca desativáveis; `restaurar_paginas_padrao()` também restaura a ordem nativa e renumera os não-nativos (`tela_configuracoes.py:673-720`). O menu lateral herda a nova ordem via `modulos_do_usuario` (`layout_tela.py:147`).
- **URL/slug editável dos módulos (05/09)**: novo módulo `mod_intranet/rotas_modulos.py` registra dinamicamente as rotas de páginas de módulos no NiceGUI. `DEFAULT_ROTAS` (`rotas_modulos.py:16-23`) espelha as rotas padrão dos decorators fixos de `main.py`; `REGISTRO_MODULOS` (`rotas_modulos.py:26`) mapeia chave→função de página (preenchido em `main.py` após cada decorator); `_registradas` (`rotas_modulos.py:30`) evita registrar o mesmo path duas vezes (o que quebraria o servidor). `_normalizar_rota()` (`rotas_modulos.py:33-41`) garante `/` inicial, lowercase, espaço→hífen e sem `//`; `registrar_modulo(chave, rota)` (`rotas_modulos.py:44-58`) registra via `ui.page(rota)(func)` de forma **idempotente**; `montar_rotas_ativas()` (`rotas_modulos.py:61-69`) re-registra os slugs customizados persistidos em `tb_modulos.rota` após restart. Em `main.py` o import é protegido por try/except (`main.py:78-82`), `REGISTRO_MODULOS["chave"] = page_*` é preenchido após cada decorator fixo (blog `main.py:281`, usuarios `main.py:295`, auditoria `main.py:309`, editar_pdf `main.py:323`, empenhos `main.py:337`, solicita_impressao `main.py:400`) e `montar_rotas_ativas()` roda antes do START (`main.py:426`). Os decorators fixos são **mantidos** — links antigos continuam válidos.
- **`alterar_rota_modulo(ator, chave, nova_rota)` (05/09)**: nova função em `autenticacao.py:196-232` que altera a URL de um módulo em `tb_modulos` e **re-registra a página ao vivo** via `rotas_modulos.registrar_modulo`. Normaliza a rota, valida com regex `[a-z0-9_\-/]+`, impede colisão de URL entre módulos, audita `modulo_rota_alterada` e usa try/except + loguru. Retorna `(ok, msg)`.
- **Aba "Módulo" — campo "URL da página" e grid responsivo (05/09)**: a lista de páginas ganhou um campo **"URL da página"** editável por linha (`_campo_empilhado("URL da página", rota, ...)` em `tela_configuracoes.py:660-662`), ligado em `campos_url[chave] = inp_url` / `estado_campos["urls"]` (`tela_configuracoes.py:593-594`). `salvar_tudo()` (`tela_configuracoes.py:139-158`) itera `c.get("urls", {})`, compara o trim com a rota vigente no BD e chama `alterar_rota_modulo`, acumulando avisos e notificando "N URL(s) alterada(s) — recarregue com F5". `_mover()` preserva a URL pendente entre remontagens (`pendentes_url`, `tela_configuracoes.py:698-713`); `restaurar_paginas_padrao()` também restaura `rota` para `DEFAULT_ROTAS[chave]` dos nativos (`tela_configuracoes.py:737-744`). O grid usa `COLUNAS_MODULOS` **responsivo** (`tela_configuracoes.py:44-47`): `grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]` — 6 colunas em desktop (setas, chave, nome, URL, ícone, situação), empilhando em telas pequenas; cabeçalho oculto em sm/md (`hidden lg:grid`, `tela_configuracoes.py:619`), `overflow-x-auto` removido e inputs `w-full max-w-[30ch]`.
- **Backup por módulo** (12 h default, reagendável sem restart) + retenção das 10 cópias em `backup/`.
- **CSS frameworks embarcados (05/09)**: `mod_intranet/tema_css.py` serve localmente (sem CDN) os frameworks Bootstrap, Bulma, DaisyUI, Pico e Picnic baixados em `assets/css/frameworks/` via `/css/frameworks/*`. `montar_rotas_static()` registra a rota estática no boot (`main.py:64-71`, com fallback silencioso); `caminho_css(nome)` devolve a URL ou a lista disponível; `injetar_framework(nome)` adiciona o `<link>` no `<head>` da página atual — **injeção por página, nunca global** (evita conflito de resets com Quasar/Tailwind). Logs via `observabilidade.get_logger("intranet")`.
- **Observabilidade (loguru)**: sinks em `logs/` com rotação/retenção/compressão; `get_logger("<modulo>")` por módulo; excepthook global.
- **Documentação embutida**: `documentacao.py` builda o MkDocs e monta `/documentacao`.

## Permissões

| Área | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Login/Dashboard | ✓ | ✓ | ✓ |
| Meu Perfil / troca de senha | ✓ | ✓ | ✓ |
| Drawer lateral | módulos liberados | módulos liberados | todos |
| `/configuracoes` | ✗ | ✗ | ✓ |

## Rota e integrações

- Rotas: `/` (`main.py:112`), `/login` (`main.py:51`), `/configuracoes` (`main.py:306`), `/documentacao` (mount).
- Consumido por todos: `pagina_restrita`, `get_connection`/`get_config`/`set_config`, `audit_log`, `gerar_hash_senha`, `validar_acesso_modulo`.
- Jobs: `backup:<chave>` (12 h), `cleanup_pdf`/`cleanup_solicita` (1 min), `poda_auditoria` (24 h), `monitor_empenho` (10 s).

## Testes

```bash
.venv/bin/python test/test_fase1_login.py
.venv/bin/python test/test_server.py
```

## Pontos de atenção

- `inicializar_bancos()` roda o central **antes** de importar módulos (ordem crítica — `main.py:16-17`).
- `storage_secret` é placeholder (`main.py:336`) — trocar em produção.
- `backup_interval_hours` é seed legada; os jobs usam `backup_horas:<modulo>`.

Ver [Análise do Núcleo](../analise_mod_intranet.md) (detalhe completo, incluindo reconstrução de `conexao_bd.py`/`manipulador_bd.py` a partir de `*.pyc`).