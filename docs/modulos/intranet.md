# Intranet Core Module — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (WAL: unified audit, config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru).

---

# Módulo Núcleo Intranet — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (auditoria unificada em WAL, configurações, sessões e cadastro de módulos) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru).

## Propósito

Pacote núcleo que centraliza o que todos os módulos compartilham: banco central (auditoria LGPD, configurações, sessões e cadastro de módulos), autenticação com sessões revogáveis, layout padrão de 4 partes com guarda de página, rotinas agendadas e a tela de personalização `/configuracoes`. **Não possui `telas.py` próprio** — suas telas são montadas pelas rotas de `main.py`.

## Banco central `db_mod_intranet.db`

Arquitetura de acesso: **SQLAlchemy 2.0 ORM + Dataclasses** (piloto, 07/09).

```
models/              # dataclasses + Table metadata
  __init__.py        Configuracao · Sessao · Modulo
repositorio.py       Repositorio (CRUD tipado via Session)
bd_conexao.py        get_config/set_config delegam para Repositorio
                     (fallback sqlite3 raw em caso de falha)
```

Toda conexão executa `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` + `foreign_keys=ON` (via event listener em `repositorio.py:engine()`). Tabelas:

| Tabela | Conteúdo | Acesso ORM |
|:---|:---|:---|
| `tb_config` | chave/valor — aparência, cotas, `versao_modulo:*`, `log_*`, `smtp_*`, `banco_tipo`, `postgres_url` | `Repositorio.obter_config` / `Repositorio.definir_config` |
| `tb_sessoes` | sessões com `cookie_hash`, `ip`, `user_agent`, `dispositivo`, `mac` | `Repositorio.registrar_sessao` / `Repositorio.sessao_ativa` / `Repositorio.fechar_sessao` |
| `tb_modulos` | cadastro de módulos (nome, ícone, rota, ativo, nativo, **ordem**) | `Repositorio.listar_modulos` / `Repositorio.obter_modulo` / `Repositorio.atualizar_modulo` |

> A trilha de auditoria foi migrada para o banco exclusivo `db_mod_auditoria.db` (uma tabela por módulo — ver [Auditoria LGPD](../arquitetura.md#auditoria-lgpd-banco-exclusivo)). A antiga `tb_auditoria` central foi removida.

## Funcionalidades

- **Autenticação bcrypt + sessões revogáveis**: `autenticar` → `registrar_login` (cookie_hash via `secrets`) → `sessao_ativa` revalidada a cada request; encerrar sessão pelo admin derruba o navegador.
- **Guarda de página** (`pagina_restrita`): revalida usuário/sessão/permissão e monta o layout de 4 partes (header, drawer lateral, rodapé com versões, área principal).
- **Dashboard `/`**: saudação, **feed do Blog por padrão** (RF-09), card "Resumo do sistema" (usuários ativos, postagens, auditoria) **exclusivo de administradores** (`administrador_geral` ou `administrador_modulo` — `main.py:155`), métricas em `ui.row()` responsivo (`flex-wrap`), microinterações e feedback de 2s (toast de boas-vindas + "Atualizado ✓" via `ui.timer(2.0, once=True)`). O resumo fica abaixo do banner de boas-vindas e acima do feed, em largura total.
- **Menu lateral (drawer) — fábrica `item_menu_drawer` (refatorado 12/09/2026)**: todos os itens usam a fábrica `ui_comum.item_menu_drawer()` / classe `ItemMenuDrawer` (`mod_intranet/ui_comum.py:850`) — `ui.item` acessível `w-full rounded-lg my-0.5` com `.style('min-width: 0')`, avatar com ícone `text-primary shrink-0 aria-hidden`, rótulo `truncate max-w-full grow`, tooltip PT-BR, anel `focus-visible`, estado ativo (`bg-blue-100` + `aria-current="page"`) e `data-testid` via `.props()` (`menu-home`, `menu-<chave>`, `menu-admin`, `menu-docs`, `menu-sair`; indisponível: `menu-<chave>-indisponivel`); itens só-ícone recebem `aria-label`; falha de montagem retorna `None` (fail-soft). O drawer (`mod_intranet/telas.py:_montar_layout`, abre **fechado** `value=False`, `p-2`) tem item **"Home"** no topo (navega para `/`, `ativo` quando `chave_modulo=None`), módulos liberados via `autenticacao.modulos_do_usuario` (vínculo a módulo inativo vira item laranja de alerta), item **"Administração" contextual/dinâmico** (ícone `admin_panel_settings`: dentro de um módulo → `/admin/{chave_modulo}`; no Home → `/configuracoes`; tooltip "Configurações de {nome}" vs "Configurações gerais do sistema", exclusivo do `administrador_geral`), **"Documentação"** (`/documentacao` em nova aba) e **"Sair"** no rodapé. **Sem labels de seção** desde 06/09 (apenas separadores). **Bootstrap local avaliado e dispensado**: `assets/css/frameworks/bootstrap@5.3.8.min.css` (servido em `/css/frameworks/*` via `tema_css.montar_rotas_static()`) **NÃO é injetado** no drawer — o reset global quebraria o Quasar; o visual list-group é replicado com Tailwind (`.classes()`) + Quasar (`.props()`) (justificativa no código). Header responsivo com botão hambúrguer (`data-testid=menu-hamburguer`, `aria-label="Abrir menu de navegação"`).
- **Padrão de exibição**: módulo exemplo = Editor de PDF; todos os módulos ocupam **área cheia** (`w-full`) e têm o card **"Aparência"** no admin com as mesmas 6 chaves em `tb_config` (`<chave>_cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`). `aba_modulo.cabecalho()` aceita `cor_titulo`/`cor_fundo` e aplica o tema sem restart; com `chave_modulo` (06/09) resolve TODAS as cores pelo tema do módulo — a borda de destaque é a MESMA cor dos botões (ver bullet abaixo).
- **Padrão próprio do tema de botões (06/09)**: chave de botão do módulo **VAZIA** (`<prefixo>_cor_botao`, `<prefixo>_cor_texto_botao`, `<prefixo>_btn_tamanho`) = **padrão do módulo** — precedência em `tema_modulo.ler_tema` (`tema_modulo.py:94-126`): (1) chave do módulo não vazia → (2) default do parâmetro → (3) `PADROES_TEMA` — mapa único com **TODOS os módulos em `#000000`** (a cor do intranet: blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao, intranet). O tema do sistema (`intranet_*` / card **"Botões do sistema"** em `/configuracoes`) **NÃO é herdado** por outros módulos — **todos os módulos usam a cor do intranet (`#000000`)**; `cor_fundo`, `cor_titulo` e `texto_header` seguem a mesma regra. O override por módulo continua possível no cupê "Aparência" da Administração — inputs exibem o valor resolvido (rótulo "vazio = padrão do módulo" — `tema_modulo.py:319-322`) e "Restaurar padrão" grava `""` para voltar ao padrão do módulo. `PADRAO_CONFIG` não semeia chaves de botão por módulo (instalações novas já iniciam com a cor única `#000000`). Coberto por `test/verifica_ui_comum.py` (190 verificações — seção 15 "ler_tema real: padrão próprio do módulo").
- **Login `/login`**: customizável por `tb_config`; com favicon dinâmico (`favicon_versao`). **Responsivo (09/2026, RNF-UI-01)**: card `w-full max-w-[420px] mx-4 p-6 sm:p-10` (antes `w-[420px] p-10`), wrapper `p-4 min-width:0`; header `flex-wrap` `truncate` `max-w` `gap` via `.style` (auditado 320/768/1024 — `kbp-web-design`). Validar `mkdocs build` tema `readthedocs`.
- **Responsividade global (RNF-UI-01, 09/2026)**: padrão mobile-first 320/768/1024 — containers `w-full p-4 sm:p-6` `min-width:0`, `flex-wrap` + `gap` via `.style()`, `truncate`/`max-w`, `overflow-x-auto` tabs/tabelas, `w-full max-w` dialogs, grids `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`, `scroll_area` altura explícita; proposta P0/P1/P2 por `container`/`row`/`grid` na auditoria `kbp-web-design`.
- **Configurações `/configuracoes`** (só `administrador_geral`): organizada no padrão **menu_mod de abas** (`tela_configuracoes.py:476-486`) — **5 abas**: Config (cards reordenados em 06/09 para **Configurações de cores → Textos fixos exibidos aos usuários → Configurações gerais do sistema → Ícones** — antes o card Ícones abria a aba; blocos movidos verbatim: Cores em grade 4+4 com prévia `:492`, textos com rótulo interno `:645`, gerais no padrão responsivo da aba Módulo `:769`, Ícones em grid único responsivo `:814`), E-mail (SMTP RF-58 + teste de conexão), Módulo (páginas do sistema + registro de módulos e vínculos órfãos), Observabilidade (logs loguru: ativo/nível/rotação/retenção/console/envio Loki + telemetria OTel local ou remota + URL Grafana + limpar todos) e Documentação (rebuild MkDocs). **Sem botão "APLICAR" geral** desde 06/09: cada card é `card_admin` recolhível (`aberto=False`) com rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card — o Aplicar grava só os campos daquele card, aguarda 1 s e recarrega (`_aplicar_card`, `tela_configuracoes.py:284-308`). Os painéis são vinculados às abas pelo `name` do Quasar — a ordem DOM dos `ui.tab_panel` (Config, E-mail, Observabilidade, Documentação, Módulo) difere da ordem da barra, sem mudança funcional.
- **Card "Cores" do Config — prévia ao vivo no topo do card (06/09)**: dentro do 1º card da aba Config (`tela_configuracoes.py:433-582`) a **pré-visualização ao vivo subiu para logo abaixo da legenda** — nova ordem interna **título → legenda → prévia (visualização exemplo) → campos de cores → "Restaurar padrão"** (bloco de 50 linhas movido verbatim: antes `:491-540`, depois `:440-489`, antes do grid `:491`). A prévia (`previa()` com `@ui.refreshable`, `tela_configuracoes.py:443-487`) exibe barra do sistema (ícone + nome sobre a cor principal), card de exemplo e botões de exemplo, lendo o estado pendente com fallback ao banco (`_prev` — `:245-255`); `_refresh_previa()` (`:235-243`) é order-independent (silenciosa se a prévia ainda não existir) e é acionada por `_mudou`/`_mudou_cor` em qualquer campo (`:223-233`) — renderização inicial idêntica, mudança apenas de posicionamento. Grid dos 8 seletores (4+4), seeds e "Restaurar padrão" byte-idênticos; card "Ícones" intocado. Coberto por `test/verifica_ui_comum.py` (**187 verificações OK**) e `test/teste_config_intranet.py` (50 OK).
- **Card "Ícones" do Config — grid único responsivo, itens equilibrados (06/09)**: o card (4º da aba Config após a reordenação) usa um **único grid inline responsivo** `grid-cols-1 sm:grid-cols-2 md:grid-cols-3` (`tela_configuracoes.py:776-802`) com 3 itens na ordem **1º** input "Ícone do sistema (nome Material)", **2º** `ui.upload` do favicon e **3º** botão "Restaurar padrão" (no grid, mesmo `on_click` via `pos_acao=remover_fav`) — os três alinhados `w-full self-center` (colunas equilibradas: o input herda `w-full` do `campo_texto` + `self-center`; upload e botão com classes explícitas). O rótulo do upload foi **encurtado para "Enviar arquivo .ico"**, com o detalhe movido para o tooltip "Substitui o ícone da aba do navegador (favicon) — extensão .ico, até 1 MB" (`tela_configuracoes.py:785-791`). Removidos os badges de status do favicon e o preview base64 (`_linha_fav`); `receber_ico`/`remover_fav` inalteradas (validação `.ico` ≤1 MB + auditoria — `tela_configuracoes.py:736-774`). Coberto por `test/teste_config_intranet.py` (50 verificações — novo label na `:104`).
- **Aba "Módulo" — redesenho (05/09)**: a aba (antes "Registro/Nome de módulo") ganhou **campo de ícone editável com seletor visual** — `_campo_icone` (`tela_configuracoes.py:519-546`): input livre + pré-visualização viva + `ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS` (31 ícones, `tela_configuracoes.py:33-39`) + botão `grid_view`; reutilizado no registro de novo módulo (`tela_configuracoes.py:762`). O grid usa a constante compartilhada `COLUNAS_MODULOS` (`tela_configuracoes.py:45`) entre cabeçalho e linhas (mesmo columns/gap/padding — alinhamento corrigido). A lista de páginas é **ÚNICA** (os grupos "Indispensáveis"/"Demais" foram substituídos pela lista reordenável — ver "Reordenação de módulos" abaixo), com linhas em cards (`rounded-lg`, borda, `hover:shadow-sm`) e container `overflow-x-auto` (`tela_configuracoes.py:566-636`).
- **Módulos indispensáveis (05/09)**: `MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}` (`tela_configuracoes.py:30` e `autenticacao.py:216`) — esses módulos **não podem ser desativados**. Na aba "Módulo" eles aparecem destacados na lista única com fundo âmbar + ícone `lock` no lugar do switch (`tela_configuracoes.py:1217-1421`). No backend, `set_modulo_ativo` recusa a desativação com `(False, msg)` e audita `modulo_desativado_bloqueado` (`autenticacao.py:227-229`); `set_chaves_desativadas` filtra os indispensáveis (`autenticacao.py:481`); `aplicar_paginas` força `ativo=1` (`tela_configuracoes.py:420`).
- **Reordenação de módulos (05/09)**: nova coluna `ordem INTEGER NOT NULL DEFAULT 0` em `tb_modulos` (`autenticacao.py:53`) com **migração idempotente** (`autenticacao.py:61-75` — `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`; nativos seguem `MODULOS_SISTEMA` 1..n, não-nativos ficam após os nativos em ordem alfabética). **Correção 07/09**: o `INSERT OR IGNORE` de `_garantir_tb_modulos` passou a incluir `ativo` e `ordem` explicitamente (1 e 0) (`autenticacao.py:59-64`) — em banco novo (sem defaults SQL) o INSERT omitia essas colunas e violava NOT NULL, sendo silenciosamente ignorado (tabela vazia, menu sem módulos). `modulos_registrados()` ordena por `ordem ASC, nome` (`autenticacao.py:113`); `registrar_modulo()` grava `max(ordem)+1` (`autenticacao.py:141-148`); nova função `reordenar_modulos(ator, chaves_ordenadas)` (`autenticacao.py:162-192`) grava a posição 1-based de cada chave, chaves ausentes vão ao fim, audita `modulos_reordenados` e usa try/except + loguru. Na aba "Módulo" a lista de páginas é **ÚNICA e reordenável** com setas ↑/↓ (`refresh_modulos` `tela_configuracoes.py:566-636`, `_mover` `tela_configuracoes.py:638-669`), persistindo de imediato; indispensáveis (auditoria, usuarios) destacados em âmbar com cadeado, reordenáveis porém nunca desativáveis; `restaurar_paginas_padrao()` também restaura a ordem nativa e renumera os não-nativos (`tela_configuracoes.py:673-720`). O menu lateral herda a nova ordem via `modulos_do_usuario` (`mod_intranet/telas.py:_montar_layout`).
- **URL/slug editável dos módulos (05/09)**: novo módulo `mod_intranet/rotas_modulos.py` registra dinamicamente as rotas de páginas de módulos no NiceGUI. `DEFAULT_ROTAS` (`rotas_modulos.py:16-23`) espelha as rotas padrão dos decorators fixos de `main.py`; `REGISTRO_MODULOS` (`rotas_modulos.py:26`) mapeia chave→função de página (preenchido em `main.py` após cada decorator); `_registradas` (`rotas_modulos.py:30`) evita registrar o mesmo path duas vezes (o que quebraria o servidor). `_normalizar_rota()` (`rotas_modulos.py:33-41`) garante `/` inicial, lowercase, espaço→hífen e sem `//`; `registrar_modulo(chave, rota)` (`rotas_modulos.py:44-58`) registra via `ui.page(rota)(func)` de forma **idempotente**; `montar_rotas_ativas()` (`rotas_modulos.py:61-69`) re-registra os slugs customizados persistidos em `tb_modulos.rota` após restart. Em `main.py` o import é protegido por try/except (`main.py:78-82`), `REGISTRO_MODULOS["chave"] = page_*` é preenchido após cada decorator fixo (blog `main.py:281`, usuarios `main.py:295`, auditoria `main.py:309`, editar_pdf `main.py:323`, empenhos `main.py:337`, solicita_impressao `main.py:400`) e `montar_rotas_ativas()` roda antes do START (`main.py:426`). Os decorators fixos são **mantidos** — links antigos continuam válidos.
- **`alterar_rota_modulo(ator, chave, nova_rota)` (05/09)**: nova função em `autenticacao.py:196-232` que altera a URL de um módulo em `tb_modulos` e **re-registra a página ao vivo** via `rotas_modulos.registrar_modulo`. Normaliza a rota, valida com regex `[a-z0-9_\-/]+`, impede colisão de URL entre módulos, audita `modulo_rota_alterada` e usa try/except + loguru. Retorna `(ok, msg)`.
- **Aba "Módulo" — campo "URL da página" e grid responsivo (05/09)**: a lista de páginas ganhou um campo **"URL da página"** editável por linha (`_campo_empilhado("URL da página", rota, ...)` em `tela_configuracoes.py:660-662`), ligado em `campos_url[chave] = inp_url` / `estado_campos["urls"]` (`tela_configuracoes.py:593-594`). `aplicar_paginas()` (`tela_configuracoes.py:412-452`) itera `c.get("urls", {})`, compara o trim com a rota vigente no BD e chama `alterar_rota_modulo`, acumulando avisos e notificando "N URL(s) alterada(s) — recarregue com F5". `_mover()` preserva a URL pendente entre remontagens (`pendentes_url`, `tela_configuracoes.py:698-713`); `restaurar_paginas_padrao()` também restaura `rota` para `DEFAULT_ROTAS[chave]` dos nativos (`tela_configuracoes.py:1360-1417`). O grid usa `COLUNAS_MODULOS` **responsivo** (`tela_configuracoes.py:44-47`): `grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]` — 6 colunas em desktop (setas, chave, nome, URL, ícone, situação), empilhando em telas pequenas; cabeçalho oculto em sm/md (`hidden lg:grid`, `tela_configuracoes.py:619`), `overflow-x-auto` removido e inputs `w-full max-w-[30ch]`.
- **Backup por módulo** (12 h default, reagendável sem restart) + retenção das 10 cópias em `backup/`.
- **CSS frameworks embarcados (05/09)**: `mod_intranet/tema_css.py` serve localmente (sem CDN) os frameworks Bootstrap, Bulma, DaisyUI, Pico e Picnic baixados em `assets/css/frameworks/` via `/css/frameworks/*`. `montar_rotas_static()` registra a rota estática no boot (`main.py:64-71`, com fallback silencioso); `caminho_css(nome)` devolve a URL ou a lista disponível; `injetar_framework(nome)` adiciona o `<link>` no `<head>` da página atual — **injeção por página, nunca global** (evita conflito de resets com Quasar/Tailwind). Logs via `observabilidade.get_logger("intranet")`.
- **Fábrica central de UI — `ui_comum.py` (05/09)**: novo módulo `mod_intranet/ui_comum.py` unifica botões, diálogos e rodapés num padrão único — paleta semântica `CORES` (`ui_comum.py:37`), `botao()` (`ui_comum.py:52`, variantes `primario`/`secundario`/`texto`/`neutro`/`restaurar`/`restaurar_fill`/`perigo`/`icone` com aliases `solido`/`contorno`), `botao_icone()` (`ui_comum.py:153`), `dialogo_card()` (`ui_comum.py:176`), `rodape_dialogo()` (`ui_comum.py:204`) e `rodape_salvar_restaurar()` (`ui_comum.py:231`); reexporta `notificar`. `tema_modulo.botao` (`tema_modulo.py:128`), o rodapé do `bloco_aparencia` (`tema_modulo.py:300`) e o `_botao_padrao` da tela de Configurações (`tela_configuracoes.py:78`, 20 chamadas intactas) **delegam** a ele — visual idêntico (prova de render + suítes 31/31, 19/19, 18/18, 50/50). Fail-soft com loguru (`observabilidade.get_logger("intranet")`). Novo parâmetro `no_caps` (06/09, `ui_comum.py:54`): `False` remove o token `no-caps` das props da variante (botões UPPERCASE herdados do Quasar); o default `True` mantém a saída byte-idêntica. Os módulos `mod_*` devem migrar gradualmente para cá (guia em [Convenções de Código](../convencoes_codigo.md)) — primeiro módulo de negócio migrado: **Editor de PDF** (10 botões + 32 avisos + `CORES`; ver [Módulo Editor de PDF](edit_pdf.md)).
- **Helpers de tela de módulo — `aba_modulo.py` (05/09)**: três helpers padronizam os componentes de tela repetidos entre os módulos — `menu_modulo(itens, valor=None)` (`aba_modulo.py:77`, abas de menu com ícone em cima/nome embaixo, padrão do Renomeador de Empenhos), `campo_busca(placeholder, on_change, valor_inicial, tooltip)` (`aba_modulo.py:95`, `outlined dense clearable debounce='150'`, padrão da Gestão de Usuários) e `barra_acoes(busca, acoes)` (`aba_modulo.py:112`, barra branca com busca à esquerda e botões `ui_comum.botao` primários à direita; itens malformados ignorados com loguru). `abas()` permanece para blog/auditoria (compatibilidade). Pilotos: Renomeador de Empenhos usa `menu_modulo` (tabs crus removidos — `mod_renomear_empenho/telas.py:89`); Gestão de Usuários usa `campo_busca` (`mod_gest_cad_usuario/telas.py:104`) e o botão "Novo usuário" passou a `ui_comum.botao` com `chave_modulo="usuarios"` (`mod_gest_cad_usuario/telas.py:110`) — **mudança visual intencional**: a cor segue o tema do módulo (`usuarios_cor_botao`) em vez do `color=primary` da página, ajustável pelo admin na aba Administração. Coberto por `test/verifica_ui_comum.py` (97 verificações).
- **Cabeçalho dos módulos pelo tema do módulo (06/09)**: `aba_modulo.cabecalho()` (`aba_modulo.py:33-79`) ganhou o parâmetro `chave_modulo` — com ele, as cores vêm de `tema_modulo.ler_tema(chave)`: **cor de destaque da borda esquerda = `tema["cor_botao"]`** (a MESMA cor geral do módulo, chave `<prefixo>_cor_botao`, vazia = padrão do próprio módulo via `PADROES_TEMA`, editável no cupê Aparência "Cor geral do módulo"), `cor_titulo`/`cor_fundo` idem; parâmetros explícitos vencem o tema (retrocompatível); sem chave → defaults `ui_comum.CORES` (byte-idêntico); falha ao ler tema → warning loguru + defaults (fail-soft). Módulos migrados (zero `cor_borda="#..."` hardcoded): renomear_empenho (`mod_renomear_empenho/telas.py:85`), auditoria (`mod_auditoria/telas.py:345`), blog (`mod_blog/telas.py:159`), solicita_impressao (`mod_solicita_impressao/telas.py:49`) e gest_cad_usuario (`mod_gest_cad_usuario/telas.py:97`). Exceção: `mod_edit_pdf` mantém header custom (label admin + cota com `ui.linear_progress` — `mod_edit_pdf/telas.py:610-625`). **Mudança visual intencional**: as bordas seguem hoje o padrão do próprio módulo (`PADROES_TEMA`); a identidade de cada módulo é configurável por módulo. Coberto por `test/verifica_ui_comum.py` (139 → **150 verificações**, +11 de `cabecalho`) e `test/test_dashboard.py` (2 checks da assinatura).
- **Padrões `ui_comum` aplicados no núcleo (06/09)**: `campo_texto` ganhou `senha=False` (`password=True, password_toggle_button=True` — campo de senha com botão exibir/ocultar) e `placeholder=None` (repassado ao construtor quando informado; **sem valor resolvido o kwarg `value` NÃO é repassado** — réplica crua byte-idêntica, descoberta validada no NiceGUI real: `value=None` seria literal) e `campo_selecao` ganhou `tooltip=None` (`ui_comum.py:314-317, 374-376`). Migrações byte-idênticas em `tela_configuracoes.py` (diálogo `confirmar` → `dialogo_card(largura="", max_altura=False)` — `tela_configuracoes.py:158`; `f_icone` `:487`, `inp_raiz` `:783`, 3 selects de Observabilidade `:906-932`, `n_chave`/`n_nome`/`n_rota` do diálogo de novo módulo `:1328-1337`) e em `telas.py` (`_dialogo_meu_perfil` — 3 campos + 3 senhas `:249-270`; `_dialogo_troca_senha` — 3 senhas com `props=""` `:302-304`). Exceções mantidas cruas por byte-identidade: `_campo_empilhado`/`_campo_icone` (label empilhada), botões da prévia (estado não salvo), cards Cores/Textos fixos e o `ui.number` do `dialogo_backup` (candidato a futuro `campo_numero`). Contagens: `tela_configuracoes.py` `ui.input` 7→2, `ui.select` 3→0, `ui.dialog` 1→0, `campo_texto` 7→12, `campo_selecao` 1→4; `telas.py` `ui.input` 9→0 (6 senhas). Novo `test/smoke_senha_ui_comum.py` (8 verificações com NiceGUI real — senha byte-idêntica ao `ui.input` cru).
- **Cupê "Edição do módulo" (`campo_modulo`) restaurado (06/09)**: havia sido removido acidentalmente (regressão — o admin do módulo perdia renomear módulo/ícone/ativo). `campo_modulo` reposto em `tema_modulo.py:338-409` byte-idêntico ao original com 2 modernizações: inputs via `campo_texto` e docstring bilíngue; rodapé `rodape_salvar_restaurar` ("Salvar módulo") mantido. Chamadas restauradas nos 6 módulos: auditoria (`mod_auditoria/telas.py:570`), blog (`mod_blog/telas.py:417`), edit_pdf (`mod_edit_pdf/telas.py:927`), gest (`mod_gest_cad_usuario/telas.py:705`), renomear (`mod_renomear_empenho/telas.py:951`) e solicita_impressao (`mod_solicita_impressao/telas.py:986`) + imports. A edição também permanece no painel central `/configuracoes` (aba Módulo).
- **Padronização TOTAL de botões + `card_admin` (06/09)**: ~120 botões crus (`ui.button`) dos módulos migrados para `ui_comum.botao/botao_icone(chave_modulo=...)` em 12 arquivos (auditoria, edit_pdf, gest_cad_usuario, renomear_empenho e solicita_impressao — telas+admin) — alterar a cor/tamanho do tema do módulo na administração agora aplica em TODOS os botões do módulo (a fábrica lê o tema a cada render). `rodape_salvar_restaurar` (`ui_comum.py:338`) também na fábrica: "Restaurar padrão" → variante `restaurar` (contorno âmbar, `text-color=amber-10` — aparência ÚNICA no projeto, contraste WCAG ~3,8:1 em card branco), "Salvar" → `solido` do tema. Exceções INTENCIONAIS de `ui.button` cru: `ui_comum.py:163` (a própria fábrica), `ui_comum.py:326` (Cancelar de `rodape_dialogo`) e `tela_configuracoes.py:493,497` (preview ao vivo da aba Cores — valores não salvos). Novo **`ui_comum.card_admin`** (`ui_comum.py:765`): card essencial de administração — `ui.card` w-full com borda esquerda temática (cor_botao do módulo, fallback `#607D8B`) + fundo `estilo_cartao`, `ui.expansion` como cabeçalho retrátil interno e grade responsiva (`grade=True` padrão: 1/2/3 colunas em sm/md; `grade=False` para conteúdo livre). Usado em blog (2 seções), auditoria, empenhos (8 seções, `grade=False`) e no `bloco_aparencia` (`tema_modulo.py:342`; `com_card=False` para callers que já têm card). Coberto por `test/verifica_ui_comum.py` (**188 verificações** — checks de migração dos botões, rodapé e variante restaurar).
- **Ativação e CLI — `ativacao.py` / `main.py` (Opção C, 09/2026)**: `python main.py` **sem argumentos** sobe direto com `config_persistida()` (`ativacao.py:1284`) — lê `tb_config` (banco_tipo, postgres_url + porta via regex, otel_ativo, porta_*) com fallback em `_config_padrao()`; primeira execução usa padrão puro (SQLite, sem OTel). `--config`/`-c` abre o wizard interativo (ENTER=básico, `1`=configurar — `_escolha_1_enter`/`_sim_nao`). Demais flags via **Typer** com prefixos semânticos: **ativação** `--ativ-otel` (alias `--otel`, `-o`) e `--ativ-postgres` (aliases `--ativ-postgress` typo + `--postgres`, `-p`); **portas** `--porta-docs` (`--portadocumentacao`, `-d`), `--porta-db` (`--portapostgres`, `-k`), `--porta-site` (`--portasite`, `-s`), `--porta-grafana` (`--portatelemetria`, `-t`); **utilitário** `--scan-ports` (`-S`, lista portas/serviços e encerra exit 0). Flags agrupadas por tipo e em ordem alfabética dentro do grupo, com contrações curtas `-c/-o/-p/-d/-k/-s/-t/-S` (`ativacao._cli_app()` `ativacao.py:1331`; help: *"Sem argumentos, sobe direto com a configuração persistida"*). `main.py:38-56` decide: sem args → `config_persistida()`; `--config` → wizard; flags `-` → `cli_opcoes()` → `config_do_cli()` → `iniciar(cli_cfg)`. Persistência via `aplicar_banco`/`aplicar_portas` + `set_config("otel_ativo")`.
- **Observabilidade (loguru)**: sinks em `logs/` com rotação/retenção/compressão; `get_logger("<modulo>")` por módulo; excepthook global.
- **Hora do servidor (NTP) — `hora_servidor.py` (07/09)**: fonte da verdade de data/hora do sistema — `hora_servidor()`/`hora_servidor_str()` retornam a hora do SERVIDOR (nunca do cliente), sincronizada com **NTP.br** (RFC 5905, socket UDP puro, timeout 2 s, cache 60 s, lock threading) quando há internet; sem internet usa o relógio local. `offset_ntp()` devolve o offset com cache; `definir_ntp_ativa(valor)` grava a chave `hora_ntp_ativa` (`1`/`0`, default `"1"`) em `tb_config` central. Todas as funções com try/except + loguru (fail-soft). Adotado pelo `mod_solicita_impressao` em todas as datas (criação/autorização/impressão/expiração/mês de cota).
- **Documentação embutida**: `documentacao.py` builda o MkDocs e monta `/documentacao` (site em `porta_documentacao` 8000, separada de `porta_site` 8080 — via `ativacao.config_persistida()` + `main.py:_cfg`).

## Classes do núcleo (06/09)

Componentes reutilizáveis que eliminam o boilerplate replicado nos módulos — todos com docstrings bilíngues EN+PT-BR, `try/except` + loguru (`_log()` por módulo) e comportamento fail-soft.

### Acesso a dados — `mod_intranet/crud_base.py`

| Símbolo | Uso |
|:---|:---|
| `CrudBase(db_path, modulo, *, foreign_keys=False, synchronous="NORMAL")` (`crud_base.py:60`) | base CRUD do banco exclusivo do módulo: conexão SQLite padronizada (WAL + `synchronous`, `foreign_keys=ON` opcional para FK CASCADE), fechamento garantido (try/finally), commit/rollback. Atalhos: `listar` (`:154`), `obter` (`:158`), `criar` (INSERT → `lastrowid`, `:162`), `atualizar`/`excluir` (UPDATE/DELETE → `rowcount`, `:166`/`:170`), `executar_muitas` (`:174`) e `criar_tabela` (DDL idempotente, `:189`). Exceções são registradas no loguru e PROPAGAM (fail-loud — a camada de negócio decide o fail-soft) |
| `CrudBase.transacao()` (`crud_base.py:135`) | context manager de transação atômica multi-instrução: `commit` ao fim do bloco sem erro, `rollback` + repasse da exceção em falha (registrada no loguru); conexão sempre fechada no `finally` |
| `audit_reg(ator, modulo, acao, alvo="", detalhe="", hash_arquivo=None)` (`crud_base.py:43`) | wrapper fail-soft de `audit_log` com assinatura curta: falha de auditoria registra exception no loguru e NÃO interrompe a operação de negócio (a trilha não derruba a gravação do módulo) |

### Componentes de tela — `ui_painel.py` / `ui_form.py`

| Símbolo | Uso |
|:---|:---|
| `GradeTabela(colunas, *, gap="0.5rem", chave_modulo="intranet")` (`ui_painel.py:30`) | `ui.grid` padronizada: `colunas` = pares `(rotulo, largura_css)`; `montar(dados, celulas, acoes=None)` (`ui_painel.py:56`) renderiza cabeçalho em `text-caption text-grey-7 font-bold` + uma linha por item — `celulas(dado)` cria as células e, com `acoes(dado, i)`, os `botao_icone` da coluna final. Falha em uma linha não derruba a grade (fail-soft, loguru) |
| `PainelLista(colunas, dados, *, filtrar=None, por_pagina=10, ...)` (`ui_painel.py:93`) | painel de listagem completo numa coluna `w-full gap-2`: `campo_busca` (de `aba_modulo`) + filtro callável `filtrar(dado, termo)` + paginação client-side (rodapé "N registro(s) — página X/Y" com `chevron_left`/`chevron_right` desabilitados nas bordas) + `GradeTabela`. `dados` é um **CALLABLE** reavaliado a cada render — após qualquer CRUD chamar `atualizar()` (`ui_painel.py:140`); `montar(celulas, acoes)` (`ui_painel.py:120`) retorna a coluna container |
| `FormularioBuilder(*, props="outlined dense", largura="w-full")` (`ui_form.py:32`) | construtor fluente de formulários: `campo_texto`/`campo_senha`/`campo_selecao`/`campo_numero`/`campo_data` acumulam especificações e `build()` (`ui_form.py:146`) monta tudo num `ui.column().classes('w-full gap-2')` (nada nasce antes do `build()`). Leitura por `valores()` (`ui_form.py:181`), `valor(nome)` (`:176`) e `elemento(nome)` (`:169`); campos com falha de montagem são ignorados com loguru (fail-soft) |

### Classes de `ui_comum.py` + wrappers finos

`ui_comum.py` foi **refatorado em classes** (06/09) mantendo a API funcional: as funções `botao`/`botao_icone`/`dialogo_card`/`campo_*`/`card_config` continuam existindo como **wrappers finos** que delegam às classes — comportamento **byte-idêntico** (prova: `test/verifica_ui_comum.py`, **187 verificações OK**).

| Classe | Wrapper funcional |
|:---|:---|
| `BotaoFabrica` (`ui_comum.py:58`) — leitura do tema do módulo + montagem de props/classes/estilo por variante (`primario`/`secundario` tematizadas; `neutro`/`restaurar`/`perigo`/`icone_branco`/`texto_branco` fixas; `cor` sobrepõe sem ler tema) | `botao(...)` (`ui_comum.py:177`), `botao_icone(...)` (`ui_comum.py:202`) |
| `Dialogo(titulo, largura, ...)` (`ui_comum.py:224`) — context manager com `ExitStack` (escopo do card permanece aberto até `__exit__`), estilo de cartão do tema, `abrir()`/`fechar()`; devolve `(dlg, card)` | `dialogo_card(...)` (`ui_comum.py:294`) |
| `Cartao` (`ui_comum.py:628`) — card de configuração: estilo `cor_fundo`/`estilo_cartao`, título/legenda, grid de campos (CALLABLES), extras entre grid e ações, row de ações | `card_config(...)` (`ui_comum.py:746`) |
| `CampoBase` (`ui_comum.py:384`) — resolução de valor `tb_config` (`chave`/`padrao`) + acabamento fixo (props, classes, estilo inline, tooltip, `ao_mudar`); subclasses `CampoCor` (`ui_comum.py:442`), `CampoTexto` (`ui_comum.py:467`) e `CampoSelecao` (`ui_comum.py:529`) | `campo_cor(...)` (`ui_comum.py:562`), `campo_texto(...)` (`ui_comum.py:582`), `campo_selecao(...)` (`ui_comum.py:609`) |

### Seleção de SGBD — `mod_intranet/banco_conexao.py` (08/09)

Backend **duplo e controlado pelo sistema**: **SQLite** (padrão, um arquivo por módulo) ou **PostgreSQL** (opcional, **um DATABASE `db_mod_<chave>` por módulo**, espelhando o arquivo SQLite). O seletor `banco_tipo` e o DSN `postgres_url` vivem **no arquivo SQLite central** e são lidos **DIRETO dele** (`_ler_config_sqlite`, `banco_conexao.py:60`) — seletor de backend autoritativo no boot, sem recursão (`sgbd_ativo → get_config → engine → sgbd_ativo`).

| Função | Local | Comportamento |
|:---|:---|:---|
| `_ler_config_sqlite(chave)` | `banco_conexao.py:60` | lê `banco_tipo`/`postgres_url` direto do `db_mod_intranet.db` (evita recursão); fail-soft → default |
| `_gravar_config_sqlite(chave, valor)` | `banco_conexao.py:83` | upsert portável `ON CONFLICT (chave) DO UPDATE` no arquivo SQLite central |
| `config_backend()` | `banco_conexao.py:118` | dict `{banco_tipo, postgres_url}` lido do SQLite central (usado pelo card admin) |
| `salvar_backend(banco_tipo, postgres_url)` | `banco_conexao.py:131` | grava o seletor no arquivo SQLite central — **exige reiniciar o servidor** para aplicar |
| `sgbd_ativo()` | `banco_conexao.py:141` | `'sqlite'`\|`'postgres'` (fail-soft: valor inválido cai em `sqlite`) |
| `banco_modulo(chave)` | `banco_conexao.py:263` | nome do DATABASE do módulo no Postgres — espelha o arquivo (`db_mod_<chave>.db` → `db_mod_<chave>`); fallback: central |
| `_garantir_bd_postgres(banco)` | `banco_conexao.py:281` | cria o banco ausente via `CREATE DATABASE` no banco de manutenção `postgres` (autocommit; idempotente por processo) |
| `garantir_bancos_postgres()` | `banco_conexao.py:317` | garante TODOS os bancos de módulo no boot (chamado por `repositorio.garantir_bancos()`) |
| `obter_engine_modulo(chave)` | `banco_conexao.py:330` | engine SQLAlchemy para o BANCO do módulo (`db_mod_<chave>`, criado se necessário) — cache por chave; `None` em SQLite |
| `conexao(chave)` | `banco_conexao.py:570` | **camada única dos módulos**: conexão DBAPI do backend ativo — sqlite (arquivo do módulo, WAL) ou postgres (proxy psycopg2 com tradução) |
| `conexao_central()` | `banco_conexao.py:601` | atalho `conexao('intranet')` |
| `obter_engine()` | `banco_conexao.py:194` | engine SQLAlchemy sob demanda (lazy singleton) com troca de DSN; `None` em SQLite ou sem driver (fail-soft) |
| `_dsn_publico(url)` | `banco_conexao.py:43` | mascara credenciais do DSN em logs (`postgresql+psycopg2://***@host/db`) |

**Proxy psycopg2 (`_CursorPostgres`, `banco_conexao.py:390`):** traduz `?`→`%s`; `datetime('now','localtime')`→`LOCALTIMESTAMP`; DDL SQLite→Postgres (`_ddl_postgres`, `:358` — `AUTOINCREMENT` removido, `INTEGER PRIMARY KEY`→`SERIAL PRIMARY KEY`, `BLOB`→`BYTEA`, `DATETIME`→`TIMESTAMP`, remoção de `FOREIGN KEY`); `INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`; `INSERT OR REPLACE`→`ON CONFLICT`; `PRAGMA`/`sqlite_master`/FTS5 (`CREATE VIRTUAL TABLE`/`CREATE TRIGGER`) ignorados; `PRAGMA table_info`→`information_schema.columns`; `lastrowid` via `RETURNING id` com SAVEPOINT e SAVEPOINT por statement (falha isolada não desfaz a transação).

**Roteamento:** `repositorio.engine(chave)`/`sessaodb(chave)` roteiam para o Postgres via `obter_engine_modulo(chave)` quando `banco_tipo='postgres'`; senão mantêm SQLite por arquivo. `CrudBase._conectar` também roteia pelo backend ativo.

**Dependência habilitada:** `requirements.txt:24-25` — `sqlalchemy>=2.0` + `psycopg2-binary>=2.9` (sem driver o sistema segue de pé em SQLite com exception no loguru). Container: `assets/docker/postgres/docker-compose.yml`. Toggle no admin: `/configuracoes` → aba **Documentação** → card **"Banco de dados — SQLite ou PostgreSQL"** (ícone `storage`). Detalhes: [Arquitetura — Backend duplo](../arquitetura.md#arquitetura-de-acesso-a-dados-do-nucleo-backend-duplo-0809) e [Configurações](../configuracoes.md#card-banco-de-dados-sqlite-ou-postgresql-0809).

### Painel de backup reutilizável — `rotinas.painel_backup()` (06/09)

`painel_backup(chave_modulo)` (`rotinas.py:189`) é a função centralizada que renderiza o painel de backup (intervalo em horas + botão "Fazer backup agora") nos painéis administrativos dos módulos. **Extraída de `dialogo_backup.py`** e reutilizada nos 6 `telas_administracao.py`: blog, usuarios, auditoria, edit_pdf, empenhos e solicita. `MAPA_BACKUPS` em `rotinas.py:16-22` controla quais bancos são copiados (intranet, usuarios, blog, editar_pdf, auditoria, empenhos, solicita). O botão de backup foi **removido do header** do `telas.py` (já está acessível via menu hambúrguer → Administração do módulo).

!!! note "Migração gradual"
    Telas novas dos módulos devem usar os componentes acima em vez de criar `ui.grid`/`ui.input`/`ui.button` crus e `sqlite3` direto — regra registrada em [Padrões de Codificação](../padroes_codificacao/index.md) e [Convenções de Código](../convencoes_codigo.md). Pilotos: `mod_blog` (BD 100% via `CrudBase` + `audit_reg`) e o diálogo `confirmar` de `tela_configuracoes.py:154-160` (classe `Dialogo`).

### Repositório — `mod_intranet/repositorio.py` (07/09; multi-banco 06/09)

Classe `Repositorio` com CRUD tipado via SQLAlchemy ORM Session. Todas as operações retornam instâncias de dataclasses (`Configuracao`, `Sessao`, `Modulo`) e são fail-soft com loguru. A instância pode ser vinculada a **qualquer banco de `MODULOS_BD`** via `Repositorio(chave_db="blog")` (default: central).

**Multi-banco (`MODULOS_BD`, `repositorio.py:57-65`):** 7 bancos — `intranet`→`db_mod_intranet.db`, `blog`→`db_mod_blog.db`, `editar_pdf`→`db_mod_edit_pdf.db`, `usuarios`→`db_mod_gest_cad_usuario.db`, `empenhos`→`db_mod_renomear_empenho.db`, `auditoria`→`db_mod_auditoria.db`, `solicita_impressao`→`db_mod_solicita_impressao.db`.

**Engine por banco** (`repositorio.py:engine(chave)`):
- Um engine POR banco, cacheado por chave (`_engines` + `_lock` — double-checked locking).
- Event listener para pragmas: `journal_mode=WAL` + `synchronous=NORMAL` + `foreign_keys=ON`.
- **Criação condicional:** `metadata.create_all()` + log só quando o ARQUIVO do banco NÃO existe — num boot normal (bancos existentes) nada é criado nem logado. Para módulos (≠ `intranet`) NUNCA roda `create_all`: o schema é do `init_db` de cada módulo; arquivo novo é criado na primeira conexão.
- Retorna `None` se SQLAlchemy indisponível (fail-soft).

**Bootstrap:** `garantir_bancos()` (`repositorio.py:177`) percorre `MODULOS_BD`, cria o engine de cada banco e força a primeira conexão quando o arquivo está ausente; `inicializar_bancos()` (`mod_intranet_inicializacao_bd.py:13`) chama no **passo 0 do boot**, antes dos `init_db` dos módulos.

**Helpers genéricos (SQL cru no banco vinculado):**

| Método | Retorno | Fail-soft |
|:---|:---|:---|
| `consultar(sql, params)` | `list[dict]` (SELECT, rows como dicts) | `[]` |
| `executar(sql, params)` | `int` (rowcount; DML + commit, rollback em falha) | `-1` |
| `ultimo_id()` | id (`last_insert_rowid()`) | `None` |

**Métodos — `tb_config`:**

| Método | Retorno | Fail-soft |
|:---|:---|:---|
| `obter_config(chave, padrao="")` | `str` | `padrao` |
| `definir_config(chave, valor)` | `bool` | `False` |
| `listar_config()` | `list[Configuracao]` | `[]` |

**Métodos — `tb_sessoes`:**

| Método | Retorno | Fail-soft |
|:---|:---|:---|
| `registrar_sessao(...)` | `int?` (rowid) | `None` |
| `obter_sessao_ativa(usuario, cookie_hash)` | `Sessao?` | `None` |
| `sessao_ativa(usuario, cookie_hash)` | `bool` | `False` |
| `fechar_sessao(usuario, cookie_hash)` | `bool` | `False` |
| `fechar_todas_sessoes(usuario)` | `int` (qtd.) | `0` |
| `podar_sessoes(usuario, limite=50)` | `int` (qtd.) | `0` |

**Métodos — `tb_modulos`:**

| Método | Retorno | Fail-soft |
|:---|:---|:---|
| `listar_modulos(somente_ativos=False)` | `list[Modulo]` | `[]` |
| `obter_modulo(chave)` | `Modulo?` | `None` |
| `registrar_modulo(...)` | `bool` | `False` |
| `atualizar_modulo(...)` | `bool` | `False` |
| `reordenar_modulos(chaves_ordenadas)` | `bool` | `False` |
| `excluir_modulo(chave)` | `bool` | `False` |
| `modulo_existe(chave)` | `bool` | `False` |

### Models — `mod_intranet/models/__init__.py` (07/09)

| Dataclass | Colunas da tabela |
|:---|:---|
| `Configuracao` | `chave: str`, `valor: str` |
| `Sessao` | `id?`, `usuario`, `modulo?`, `login_timestamp?`, `logout_timestamp?`, `cookie_hash`, `ip?`, `user_agent?`, `dispositivo?`, `mac?` |
| `Modulo` | `id?`, `chave`, `nome`, `icone`, `rota`, `ativo`, `nativo`, `ordem` |

Mapeamento via `sqlalchemy.orm.registry.map_imperatively()` — SQLAlchemy fica **opcional** (o ORM layer em `repositorio.py` retorna `padrao`/`False`/`[]` se indisponível).

!!! note "Defaults SQL em `tb_modulos` (07/09)"
    As colunas `ativo` (="1"), `nativo` (="0") e `ordem` (="0") ganharam **`server_default`** (`models/__init__.py:80-82`) — antes os defaults eram apenas do lado Python do ORM, então o DDL gerado por `metadata.create_all` criava a tabela SEM defaults SQL (colunas NOT NULL sem DEFAULT). Em banco recém-criado isso fazia o `INSERT OR IGNORE` de `_garantir_tb_modulos` violar NOT NULL e ser silenciosamente ignorado (tabela vazia, menu sem módulos). Ver [Correção de bug — seed de `tb_modulos`](../registro_de_mudancas/index.md).

### Credenciais PostgreSQL — chaves em `tb_config` (07/09)

| Chave | Default | Descrição |
|:---|:---|:---|
| `banco_usuario` | `klayton` | Usuário de operações normais |
| `banco_senha` | `klayton` | Senha do usuário normal |
| `banco_admin_usuario` | `master` | Usuário de operações administrativas |
| `banco_admin_senha` | `master` | Senha do admin |
| `postgres_url` | `postgresql+psycopg2://klayton:klayton@localhost:5432/intranet` | DSN base |

`banco_conexao.postgres_url(como_admin=False)` monta o DSN com as credenciais de `banco_usuario`/`banco_senha` (operações normais) ou `banco_admin_usuario`/`banco_admin_senha` (admin — criação de banco, migrations).

## Permissões

| Área | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Login/Dashboard | ✓ | ✓ | ✓ |
| Meu Perfil / troca de senha | ✓ | ✓ | ✓ |
| Drawer lateral | módulos liberados | módulos liberados | todos |
| `/configuracoes` | ✗ | ✗ | ✓ |

## Rota e integrações

- Rotas: `/` (`main.py:189`), `/login` (`main.py:115`), `/admin/{chave_modulo}` (`main.py:439` — dispatch de admin por módulo, renderiza `mod_<nome>/telas_administracao.py` standalone), `/configuracoes` (`main.py:527` — painel central, guarda `pagina_restrita("Administração")`), `/documentacao` (mount).
- Consumido por todos: `pagina_restrita`, `get_connection`/`get_config`/`set_config`, `audit_log`/`audit_reg`, `CrudBase`, `gerar_hash_senha`, `validar_acesso_modulo`.
- Jobs: `backup:<chave>` (12 h), `cleanup_pdf`/`cleanup_solicita` (1 min), `poda_auditoria` (24 h), `monitor_empenho` (10 s).

## Testes

```bash
.venv/bin/python test/test_fase1_login.py
.venv/bin/python test/test_server.py
.venv/bin/python test/verifica_ui_comum.py   # 190 verificações (ui_comum + no_caps + helpers de tela + padrão próprio do tema + edit_pdf migrado + cabecalho com tema do módulo + campo_texto/campo_selecao + campo_cor/card_config + campo_modulo restaurado + equivalência wrapper↔classe)
.venv/bin/python test/smoke_senha_ui_comum.py # 8 verificações (NiceGUI real: campo_texto(senha=True) byte-idêntico ao ui.input cru)
.venv/bin/python test/teste_classes_crud.py   # 68 verificações (CrudBase em SQLite real, gancho de auditoria, banco_conexao, equivalência wrapper↔classe, GradeTabela/PainelLista/FormularioBuilder)
```

## Pontos de atenção

- `inicializar_bancos()` roda o central **antes** de importar módulos (ordem crítica — `main.py:16-17`).
- `storage_secret` é placeholder (`main.py:336`) — trocar em produção.
- `backup_interval_hours` é seed legada; os jobs usam `backup_horas:<modulo>`.

Ver [Análise do Núcleo](../analise_mod_intranet.md) (detalhe completo, incluindo reconstrução de `bd_conexao.py`/`bd_manipulador.py` a partir de `*.pyc`).