# Intranet Core Module — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (WAL: config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru) · **`integracoes.py` integration facade** (single public seam between modules, lazy imports + fail-soft).

---

# Módulo Núcleo Intranet — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (configurações, sessões e cadastro de módulos em WAL) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru) · **fachada de integração `integracoes.py`** (costura pública única entre módulos, imports lazy + fail-soft).

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
- **Fachada de integração `integracoes.py` (25/09/2026; 9 funções em 27/09/2026)**: funções públicas com **imports lazy** (dentro da função — um import de topo fecharia ciclo com `main.py`) e contrato **fail-soft** (valor neutro + `logger.warning`, nunca derruba a tela). É a forma canônica de um módulo de negócio acessar dado de outro módulo: **o negócio fala com o núcleo, e o núcleo possui o acoplamento** — o SQL continua rodando só no banco do módulo de destino, pelo `bd_manipulador` dele. Precedente: `censura.py` (dado compartilhado que mora no núcleo); validação: `assets/test/check_integridade.py` (13/13, era 5 falhas/17). Detalhes e checklist: [Fachada de Integração](../arquitetura_de_software_das/fachada_integracoes.md).
- **Guarda de página** (`pagina_restrita`): revalida usuário/sessão/permissão e monta o layout de 4 partes (header, drawer lateral, rodapé com versões, área principal). Ao final, chama `_primeiro_acesso(user["nome"])` — ver [Primeiro acesso: senha e telefone](#primeiro-acesso-senha-e-telefone-27092026).
- **Dashboard `/` (redesign Home 09/2026)**: saudação + **feed do Blog por padrão** (RF-09) + **2 cards de Resumo sem botão Atualizar** — dados recalculados a cada acesso via `_orquestrar_resumo_dados()` (`main.py:250`):
    - **"Resumo do sistema" (8 métricas, só `administrador_geral`/`administrador_modulo` — `main.py:500` `eh_admin`)**: `Usuários ativos` (`people`, `filtro_ativo=None`), `Sessões ativas` (`sensors`, `tb_sessoes WHERE logout IS NULL`), `Visitas` (`login`, `tb_config contador_acessos_total`), `Postagens` (`article`), `Quarentena pendente` (`warning`, `tb_quarentena processado=0`), `PDFs ativos` (`picture_as_pdf`, `tb_arquivos ativo=1`), `Registros de auditoria` (`history`), `Auditoria 24h` (`schedule`, `SUM COUNT WHERE timestamp >= -1 day` por `tb_auditoria_*`). Ordem: `[Usuários, Sessões, Visitas, Postagens, Quarentena, PDFs, Logs, Logs 24h]`, `gap-1 px-2 py-1`, ícone 36px `text-2xl`, número `text-h6` 4 dígitos (`>9999` com total real no tooltip) — `_stat()` (`main.py:325`).
    - **"Resumo do sistema — Impressão" (2 métricas, só autorizador `tb_responsaveis_autorizacao ativo=1` ou `administrador_geral` — `main.py:417`/`446`)**: `Fila geral` (`print`, `tb_solicitacoes WHERE status NOT IN impresso/recusado/cancelado`) e `Para autorizar` (`rule`, `tb_responsaveis_autorizacao` por secretaria/setor — `main.py:460` `_contar_fila_para_autorizar()`; admin geral = fila geral).
    - **Visual escopado Water só no card** (`home_visual.injetar_water_card()` `home_visual.py:176` → `aplicar_modelo("water")` em `_construir_dashboard()` `main.py:371`; `page_dashboard` fixa `modelo="water"` `main.py:502`; classes `.home-resumo-water/.home-stat-water` border `#dfe8f0` bg `#fafcfd` **+ 18/09/2026 `box-shadow:6px 0 16px rgba(0,0,0,.07)` lateral direita + `border-left-color` = cor do módulo `intranet` via `ler_tema("intranet")["cor_botao"]` (`main.py:406-441`) + `shadow-md` em `classes_card_resumo` (`home_visual.py:237`); antes `#000000`/`#EF6C00` fixos, sem sombra lateral**): altura reduzida ~50%+25%, layout horizontal ícone esq + número, tooltip único no card (rótulos curtos `Usuarios/Sessões/Noticias/Logs/Visitas/Fila geral/Para autorizar/Quarentena/PDFs/Auditoria 24h` via `_desc_base` `main.py:331`; `Logs>9999` adiciona alerta `⚠️ Alerta: volume elevado — realize backup do banco de auditoria (db_mod_auditoria.db)`). Feed do Blog usa `renderizar_postagens` (**sem botão "Abrir Blog completo" desde 18/09/2026** — `main.py:448` só `label`). Sem comparativo `/home-*` (revertido) e sem seção comparativa no hambúrguer.
    - **Contador de visitas**: `tb_config contador_acessos_total/contador_acessos_inicio` semeados em `bd_conexao.init_db()` (`bd_conexao.py:70-72` + `188-196`), `contador_acessos_inicio` em `YYYY-MM-DD` (tooltip padronizado para `Visitas`), incrementado **só em login bem-sucedido** (`incrementar_contador_acessos()` `bd_conexao.py:200` chamada em `tentar_login()` `main.py:229` — nunca em navegação/refresh).
    - Métricas em `ui.row() flex-wrap`, microinteração Water `hover:shadow + translateY(-2px)`, toast de boas-vindas 2s (`notificar(..., timeout=2)` + `ui.timer(0.1)` `main.py:385`), serviço `http://localhost:8080`.
- **Menu lateral (drawer) — fábrica `item_menu_drawer` (refatorado 12/09/2026; ordenação 19/09/2026)**: todos os itens usam a fábrica `ui_comum.item_menu_drawer()` / classe `ItemMenuDrawer` (`mod_intranet/ui_comum.py:850`) — `ui.item` acessível `w-full rounded-lg my-0.5` com `.style('min-width: 0')`, avatar com ícone `text-primary shrink-0 aria-hidden`, rótulo `truncate max-w-full grow`, tooltip PT-BR, anel `focus-visible`, estado ativo (`bg-blue-100` + `aria-current="page"`) e `data-testid` via `.props()` (`menu-home`, `menu-<chave>`, `menu-admin`, `menu-docs`, `menu-sair`; indisponível: `menu-<chave>-indisponivel`); itens só-ícone recebem `aria-label`; falha de montagem retorna `None` (fail-soft). O drawer (`mod_intranet/telas.py:_montar_layout` ~283–367, abre **fechado** `value=False`, `p-2`) segue a **ordenação 19/09/2026** — **Home isolado no topo** (`menu-home`, `ativo` quando `chave_modulo=None`); **demais módulos em ordem alfabética por nome** (`_outros.sort(key=lambda t: t[1].lower())`, exceto trio); **Administração** só `administrador_geral` após os demais (contextual `/admin/{chave_modulo}` vs `/configuracoes`); **trio fixo `Blog → Usuários → Auditoria`** (`_CHAVES_POS_ADMIN`/`_ORDEM_POS_ADMIN`) sempre após Administração e antes de Documentação/Sair; **Documentação** só `administrador_geral` (`/documentacao` nova aba, `menu-docs`); **Sair sempre último** (`menu-sair`). Módulos filtrados via `autenticacao.modulos_do_usuario` (vínculo a módulo inativo vira item laranja de alerta `menu-<chave>-indisponivel` via `_render_lista_modulos`). **Apresentação ≠ persistência:** `tb_modulos.ordem` (aba Módulo ↑/↓) não é alterado pelo drawer. **Sem labels de seção** desde 06/09 (apenas separadores). **Bootstrap local avaliado e dispensado**: `assets/css/frameworks/bootstrap@5.3.8.min.css` (servido em `/css/frameworks/*` via `tema_css.montar_rotas_static()`) **NÃO é injetado** no drawer — o reset global quebraria o Quasar; o visual list-group é replicado com Tailwind (`.classes()`) + Quasar (`.props()`) (justificativa no código). Header responsivo com botão hambúrguer (`data-testid=menu-hamburguer`, `aria-label="Abrir menu de navegação"`). Exemplo `master`: `Home | Editor PDF, Empenhos, Filas, Lista Telefônica, Solicitação, Técnico | Administração | Blog, Usuários, Auditoria | Documentação | Sair`.
- **Header — botão único sempre visível (correção final 14/09/2026)**: a row direita do header é `flex-1` (`mod_intranet/telas.py:225-260`) com **UM único botão** de "Meu Perfil" (`_dialogo_meu_perfil`): `data-testid=header-nome-usuario` sempre visível (rótulo = nome de tratamento completo, `tooltip` = nome completo, `max-width: min(28ch, 55vw)` com ellipsis sempre à direita). `header-nome-curto` foi **REMOVIDO**. Badge de perfil sempre visível (`max-w-[12ch] truncate shrink-0`, sem `hidden md:block`) e separador vertical sempre visível (sem `hidden sm:block`). Origem: `autenticacao.nome_de_tratamento` → `user_nome_completo` (nome social), fallback login. Detalhe Quasar: o `.q-btn__content` interno é `justify-content:center`, então CSS escopado via `ui.add_head_html` (padrão `home_visual.injetar_water_card`) ancora o texto à esquerda com ellipsis à direita, seletor `[data-testid="header-nome-usuario"]`, sem vazamento global. Comportamento validado via Playwright real: desktop 1280 mostra o nome completo + clique abre "Meu Perfil"; mobile 360 mostra o início preservado com ellipsis à direita (ex. "Usuário de Teste QA C…") + clique abre "Meu Perfil". Segurança: só `ui.button` (escapa), sem `ui.html`/JS, sem mudança em sessão/DB.
- **Rodapé escondido com reveal no hover — bloco FOOTER (14/09/2026)**: parte 4 do layout (`mod_intranet/telas.py:432-476`) — `ui.footer` (`bg-grey-8 w-full`, `data-testid=rodape-sistema`) **escondido por padrão** (`opacity:0 + translateY(calc(100% - 5px))`, transição `.25s`, faixa de 5px como pista) e **revela no hover/foco** (`:hover`/`:focus-within` → `opacity:1 + transform:none`). CSS escopado via `ui.add_head_html` (padrão `home_visual.injetar_water_card`), seletor `[data-testid="rodape-sistema"]`, sem vazamento global. Esteticamente inalterados desde 14/09: o texto `"{titulo} Básica — {texto_rodape}"` à esquerda e a versão única global/módulo com tooltip detalhado à direita (ver "Versionamento no rodapé" na [Análise do Núcleo](../analise_mod_intranet.md)). **Desde 27/09/2026 o rodapé ganhou um 3º item no MEIO** — o [menu de estilo visual](../estilo_visual.md) (4 estilos + "Padrão" + rótulo `estilo-atual`), centralizado por grade de 3 colunas (`assets/css/preview-estilos-v1.css:145-161`); os dois itens antigos seguem presentes. Sem JS, sem `hidden`. Validação Playwright real (`/login` 200): opacity inicial `0`, após hover `1` + transform `none`, screenshots desktop; texto preservado (`"INTRANET Básica — uso interno"`, `"v1.0.260913"`). Ressalvas: no touch o reveal ocorre no toque na faixa (rodapé só informativo, sem focáveis); se o CSS falhar, degrada para sempre visível.
-
- !!! warning "REGRA DE PROJETO — nunca usar `hidden sm:*` / `hidden md:*` neste stack"
-     O `tailwindcss.min.js` embutido no NiceGUI 3.15 resolve `hidden` acima de `sm:flex`/`md:block` mesmo a 1280 px (probe com div pura confirmou `display:none` — os dois botões sumiam, e o mesmo padrão quebrava o badge `hidden md:block`). **Nunca usar toggles `hidden sm:*` / `hidden md:*` neste projeto** — usar um único elemento sempre visível com `max-width` + `truncate`/ellipsis e `tooltip` completo.
- **Padrão de exibição**: módulo exemplo = Editor de PDF; todos os módulos ocupam **área cheia** (`w-full`) e têm o card **"Aparência"** no admin com as mesmas 6 chaves em `tb_config` (`<chave>_cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`). `aba_modulo.cabecalho()` aceita `cor_titulo`/`cor_fundo` e aplica o tema sem restart; com `chave_modulo` (06/09) resolve TODAS as cores pelo tema do módulo — a borda de destaque é a MESMA cor dos botões (ver bullet abaixo).
- **Padrão próprio do tema de botões (06/09)**: chave de botão do módulo **VAZIA** (`<prefixo>_cor_botao`, `<prefixo>_cor_texto_botao`, `<prefixo>_btn_tamanho`) = **padrão do módulo** — precedência em `tema_modulo.ler_tema` (`tema_modulo.py:115-148`): (1) chave do módulo não vazia → (2) default do parâmetro → (3) `PADROES_TEMA` — mapa único com **TODOS os 11 módulos em `#000000`** (intranet, blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao, tecnico, filas, lista_telefonica, agregador_noticias — paleta preta desde 27/09/2026, ver [Estilo Visual](../estilo_visual.md)). O tema do sistema (`intranet_*` / card **"Botões do sistema"** em `/configuracoes`) **NÃO é herdado** por outros módulos — **todos os módulos usam a cor do intranet (`#000000`)**; `cor_fundo`, `cor_titulo` e `texto_header` seguem a mesma regra. O override por módulo continua possível no cupê "Aparência" da Administração — inputs exibem o valor resolvido (rótulo "vazio = padrão do módulo" — `tema_modulo.py:319-322`) e "Restaurar padrão" grava `""` para voltar ao padrão do módulo. `PADRAO_CONFIG` não semeia chaves de botão por módulo (instalações novas já iniciam com a cor única `#000000`). Coberto por `test/verifica_ui_comum.py` (190 verificações — seção 15 "ler_tema real: padrão próprio do módulo").
- **Login `/login`**: customizável por `tb_config`; com favicon dinâmico (`favicon_versao`). **Responsivo (09/2026, RNF-UI-01)**: card `w-full max-w-[420px] mx-4 p-6 sm:p-10` (antes `w-[420px] p-10`), wrapper `p-4 min-width:0`; header `flex-wrap` `truncate` `max-w` `gap` via `.style` (auditado 320/768/1024 — `kbp-web-design`). Validar `mkdocs build` tema `readthedocs`.
- **Responsividade global (RNF-UI-01, 09/2026)**: padrão mobile-first 320/768/1024 — containers `w-full p-4 sm:p-6` `min-width:0`, `flex-wrap` + `gap` via `.style()`, `truncate`/`max-w`, `overflow-x-auto` tabs/tabelas, `w-full max-w` dialogs, grids `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`, `scroll_area` altura explícita; proposta P0/P1/P2 por `container`/`row`/`grid` na auditoria `kbp-web-design`.
- **Configurações `/configuracoes`** (só `administrador_geral`): organizada no padrão **menu_mod de abas** (`tela_configuracoes.py:604-612`) — **6 abas**: Config (cards reordenados em 06/09 para **Configurações de cores → Textos fixos exibidos aos usuários → Configurações gerais do sistema → Ícones** — antes o card Ícones abria a aba; blocos movidos verbatim: Cores em grade 4+4 com prévia `:492`, textos com rótulo interno `:645`, gerais no padrão responsivo da aba Módulo `:769`, Ícones em grid único responsivo `:814`), E-mail (SMTP RF-58 + teste de conexão), Módulo (páginas do sistema + registro de módulos e vínculos órfãos), **Telefones** (faixas de número da prefeitura, 27/09/2026 — ver abaixo), Observabilidade (logs loguru: ativo/nível/rotação/retenção/console/envio Loki + telemetria OTel local ou remota + URL Grafana + limpar todos) e Documentação (rebuild MkDocs). **Sem botão "APLICAR" geral** desde 06/09: cada card é `card_admin` recolhível (`aberto=False`) com rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card — o Aplicar grava só os campos daquele card, aguarda 1 s e recarrega (`_aplicar_card`, `tela_configuracoes.py:284-308`). Os painéis são vinculados às abas pelo `name` do Quasar — a ordem DOM dos `ui.tab_panel` (Config, E-mail, Observabilidade, Documentação, Módulo) difere da ordem da barra, sem mudança funcional.
- **Card "Cores" do Config — prévia ao vivo no topo do card (06/09)**: dentro do 1º card da aba Config (`tela_configuracoes.py:433-582`) a **pré-visualização ao vivo subiu para logo abaixo da legenda** — nova ordem interna **título → legenda → prévia (visualização exemplo) → campos de cores → "Restaurar padrão"** (bloco de 50 linhas movido verbatim: antes `:491-540`, depois `:440-489`, antes do grid `:491`). A prévia (`previa()` com `@ui.refreshable`, `tela_configuracoes.py:443-487`) exibe barra do sistema (ícone + nome sobre a cor principal), card de exemplo e botões de exemplo, lendo o estado pendente com fallback ao banco (`_prev` — `:245-255`); `_refresh_previa()` (`:235-243`) é order-independent (silenciosa se a prévia ainda não existir) e é acionada por `_mudou`/`_mudou_cor` em qualquer campo (`:223-233`) — renderização inicial idêntica, mudança apenas de posicionamento. Grid dos 8 seletores (4+4), seeds e "Restaurar padrão" byte-idênticos; card "Ícones" intocado. Coberto por `test/verifica_ui_comum.py` (**187 verificações OK**) e `test/teste_config_intranet.py` (50 OK).
- **Card "Ícones" do Config — grid único responsivo, itens equilibrados (06/09)**: o card (4º da aba Config após a reordenação) usa um **único grid inline responsivo** `grid-cols-1 sm:grid-cols-2 md:grid-cols-3` (`tela_configuracoes.py:776-802`) com 3 itens na ordem **1º** input "Ícone do sistema (nome Material)", **2º** `ui.upload` do favicon e **3º** botão "Restaurar padrão" (no grid, mesmo `on_click` via `pos_acao=remover_fav`) — os três alinhados `w-full self-center` (colunas equilibradas: o input herda `w-full` do `campo_texto` + `self-center`; upload e botão com classes explícitas). O rótulo do upload foi **encurtado para "Enviar arquivo .ico"**, com o detalhe movido para o tooltip "Substitui o ícone da aba do navegador (favicon) — extensão .ico, até 1 MB" (`tela_configuracoes.py:785-791`). Removidos os badges de status do favicon e o preview base64 (`_linha_fav`); `receber_ico`/`remover_fav` inalteradas (validação `.ico` ≤1 MB + auditoria — `tela_configuracoes.py:736-774`). Coberto por `test/teste_config_intranet.py` (50 verificações — novo label na `:104`).
- **Aba "Módulo" — redesenho (05/09)**: a aba (antes "Registro/Nome de módulo") ganhou **campo de ícone editável com seletor visual** — `_campo_icone` (`tela_configuracoes.py:519-546`): input livre + pré-visualização viva + `ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS` (31 ícones, `tela_configuracoes.py:33-39`) + botão `grid_view`; reutilizado no registro de novo módulo (`tela_configuracoes.py:762`). O grid usa a constante compartilhada `COLUNAS_MODULOS` (`tela_configuracoes.py:45`) entre cabeçalho e linhas (mesmo columns/gap/padding — alinhamento corrigido). A lista de páginas é **ÚNICA** (os grupos "Indispensáveis"/"Demais" foram substituídos pela lista reordenável — ver "Reordenação de módulos" abaixo), com linhas em cards (`rounded-lg`, borda, `hover:shadow-sm`) e container `overflow-x-auto` (`tela_configuracoes.py:566-636`).
- **Módulos indispensáveis (05/09)**: `MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}` (`tela_configuracoes.py:30` e `autenticacao.py:216`) — esses módulos **não podem ser desativados**. Na aba "Módulo" eles aparecem destacados na lista única com fundo âmbar + ícone `lock` no lugar do switch (`tela_configuracoes.py:1217-1421`). No backend, `set_modulo_ativo` recusa a desativação com `(False, msg)` e audita `modulo_desativado_bloqueado` (`autenticacao.py:227-229`); `set_chaves_desativadas` filtra os indispensáveis (`autenticacao.py:481`); `aplicar_paginas` força `ativo=1` (`tela_configuracoes.py:420`).
- **Reordenação de módulos (05/09, correção de persistência 14/09/2026)**: nova coluna `ordem INTEGER NOT NULL DEFAULT 0` em `tb_modulos` (`autenticacao.py:53`) com **migração idempotente** (`autenticacao.py:61-75` — `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`; nativos seguem `MODULOS_SISTEMA` 1..n, não-nativos ficam após os nativos em ordem alfabética). **Correção 07/09**: o `INSERT OR IGNORE` de `_garantir_tb_modulos` passou a incluir `ativo` e `ordem` explicitamente (1 e 0) (`autenticacao.py:59-64`) — em banco novo (sem defaults SQL) o INSERT omitia essas colunas e violava NOT NULL, sendo silenciosamente ignorado (tabela vazia, menu sem módulos). `modulos_registrados()` ordena por `ordem ASC, nome` (`autenticacao.py:113`); `registrar_modulo()` grava `max(ordem)+1` (`autenticacao.py:141-148`); nova função `reordenar_modulos(ator, chaves_ordenadas)` (`autenticacao.py:162-192`) grava a posição 1-based de cada chave, chaves ausentes vão ao fim, audita `modulos_reordenados` e usa try/except + loguru. Na aba "Módulo" a lista de páginas é **ÚNICA e reordenável** com setas ↑/↓ (`refresh_modulos` `tela_configuracoes.py:566-636`, `_mover` `tela_configuracoes.py:638-669`), persistindo de imediato; indispensáveis (auditoria, usuarios) destacados em âmbar com cadeado, reordenáveis porém nunca desativáveis; `restaurar_paginas_padrao()` também restaura a ordem nativa e renumera os não-nativos (`tela_configuracoes.py:673-720`). O menu lateral herda a nova ordem via `modulos_do_usuario` (`mod_intranet/telas.py:_montar_layout`).
- **Ordem padrão + persistência após restart (14/09/2026)**: ordem padrão vigente (`autenticacao.py:15-22` `MODULOS_SISTEMA`) = `blog → editar_pdf → empenhos → solicita_impressao → usuarios → auditoria` (instalações novas e "Restaurar padrão"). **Causa raiz corrigida**: `Repositorio.reordenar_modulos` (`repositorio.py:675`) usava `enumerate` 0-based — primeiro item gravava `ordem=0` — e o boot via `COUNT(*) WHERE ordem=0 > 0` reescrevia TODOS os nativos, apagando a personalização a cada reinício. Fix: `enumerate(..., start=1)` (1-based) + `_garantir_tb_modulos` (`autenticacao.py:29-80`) endurecido — numera SOMENTE linhas com `ordem=0`, nunca reescreve a ordem do usuário. Garantia: após ↑/↓ + Aplicar, a ordem permanece após reinícios (validado após 2 restarts, `/login` 200). Ver [Registro de Mudanças](../registro_de_mudancas/index.md).
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

## Faixas de telefone da prefeitura — `mod_intranet/telefone_faixas.py` (27/09/2026)

> **EN:** The municipality's phone is not a loose number: it is a **PABX with
> ranges**. The screen tells the server, **while he types**, whether the number
> belongs to the municipality — and which is the nearest range, so he can
> discover his own. A number **outside** the ranges is **warned about, not
> blocked**: blocking would punish a real situation (a health unit that
> answers on the neighbouring town's number). Either the server fixes the
> number, or he marks it as a **message phone**.
>
> **PT-BR:** O telefone da prefeitura não é um número solto: é um **PABX com
> faixas**. A tela diz ao servidor, **enquanto ele digita**, se o número pertence
> à prefeitura — e qual é a faixa mais próxima, para ele descobrir o próprio.
> Um número **fora** das faixas é **avisado, não bloqueado**: bloquear puniria
> uma situação real (unidade de saúde que atende no telefone da cidade
> vizinha). O servidor ou corrige o número, ou marca como **recado**.

O arquivo mora no **núcleo** porque a faixa é conhecimento da prefeitura, não do
cadastro nem do diretório: quem valida o cadastro é o `mod_gest_cad_usuario`, que é
dono do telefone, e o núcleo só responde "este número está dentro de alguma faixa
nossa?". Ele é o **único** que fala com `tb_config` central e com o cadastro, então é
o lugar onde a pergunta sobre a faixa pode ser feita sem quebrar o isolamento de
bancos (AGENTS.md §2).

### Armazenamento e API

| Símbolo | Arquivo:linha | O que faz |
|:---|:---|:---|
| `CONFIG_FAIXAS = "faixas_telefone_prefeitura"` | `telefone_faixas.py:38` | Chave em `tb_config`. O valor é uma **lista JSON** de `{"inicio","fim","descricao"}`, **tudo em dígitos** — são **várias** faixas, porque a prefeitura tem mais de uma central e a lista cresce |
| `FAIXA_INICIAL` | `telefone_faixas.py:46-47` | A faixa de instalação `0035915101-0035915199` ("Central de linhas") |
| `faixa_inicial()` | `telefone_faixas.py:94` | Devolve uma **cópia** da faixa de instalação |
| `listar_faixas(incluir_padrao=True)` | `telefone_faixas.py:99` | Todas as faixas configuradas, normalizadas; sem faixa cadastrada devolve a de instalação |
| `salvar_faixas(ator, faixas)` | `telefone_faixas.py:131` | Grava. Devolve `(ok, mensagem)` |
| `faixa_que_contem(numero)` | `telefone_faixas.py:165` | A faixa que contém o número, ou `None` |
| `numero_dentro_da_faixa(numero)` | `telefone_faixas.py:182` | `(bool, faixa)` |
| `faixa_mais_proxima(numero)` | `telefone_faixas.py:188` | A faixa **própria** mais próxima — é o que gera a dica do aviso |
| `_normalizar_faixa(bruto)` | `telefone_faixas.py:66` | Aceita `dict` **ou** string `"0035915101 a 0035915199"` |
| `_digitos(texto)` | `telefone_faixas.py:57` | Só os dígitos, para comparar sem se preocupar com máscara, espaço ou o `+55` da frente |

!!! note "Por que `faixa_inicial()` existe, e não um banco sem faixa"
    Um sistema instalado **sem nenhuma faixa** avisaria "fora da faixa" para o
    **próprio telefone da prefeitura** — que é o caso que mais destrói a
    confiança no aviso. Com a faixa de instalação, o aviso só aparece quando há
    algo real para avisar, e o administrador troca pela faixa verdadeira pela
    tela.

!!! note "Faixa **invertida** é normalizada; faixa **inválida** é recusada **com o número**"
    Uma faixa pode vir invertida (o usuário digitou o maior primeiro): a
    `_normalizar_faixa` **troca** início e fim, e o salvamento segue. Já uma
    faixa que não faz sentido (início ≥ fim depois de normalizar, ou número
    curto demais — menos de 10 dígitos) é **recusada**, e a mensagem traz o
    **número da faixa**, não a contagem: *"a faixa 3 tem o fim antes do
    início"* é um erro que o usuário corrige sozinho; *"erro ao salvar"* não é.
    Linha em branco da tela é ignorada, e `salvar_faixas` devolve `ok=True`
    com um aviso do tipo *"2 faixa(s) salva(s). Ignoradas por serem inválidas:
    faixa 3"* quando há linha boa **e** linha ruim.

!!! note "`faixa_mais_proxima` é a diferença entre o usuário arrumar e desistir"
    "esse número está fora das faixas da prefeitura" é uma **repreensão**;
    "a faixa mais próxima é a Garagem" é uma **ajuda** para a pessoa descobrir a
    dela. A comparação é pelos **últimos 10 dígitos** (DDD + assinatura), que é
    onde a prefeitura opera, então o `+55` digitado na frente não quebra o
    casamento.

### A aba "Telefones" em `/configuracoes` (6ª aba)

| Onde | O quê |
|:---|:---|
| `tela_configuracoes.py:608` | `tab_tel = ui.tab("Telefones", icon="support_agent")` — a **6ª** aba, junto de Config, E-mail, Módulo, Observabilidade e Documentação |
| `tela_configuracoes.py:1443-1447` | `ui.tab_panel(tab_tel)` com um `card_admin("Faixas de telefone da prefeitura", icone="support_agent", chave_modulo="intranet", grade=False, aberto=True)` |
| `tela_configuracoes.py:1453-1459` | O formato, escrito na tela: uma faixa por linha, `início-fim  descrição` |
| `tela_configuracoes.py:1467-1470` | `_para_texto(faixas)` — lista de faixas → texto do campo |
| `tela_configuracoes.py:1472-1500` | `_do_texto(texto)` — texto → lista de faixas |
| `tela_configuracoes.py:1502-1506` | `ui.textarea(value=_para_texto(telefone_faixas.listar_faixas()))` com `outlined dense rows=5 autogrow` e `data-testid=config-faixas-texto` |
| `tela_configuracoes.py:1544-1548` | Botões **"Salvar faixas"** (`save`) e **"Voltar à faixa inicial"** (`restart_alt`) |

`_do_texto` é tolerante de propósito: aceita espaço, tabulação ou vírgula entre as
partes, e o administrador pode escrever **só os dois números** — a descrição é
opcional e serve justamente para o aviso dizer qual é a faixa mais próxima do
número errado. Linha sem `-` é ignorada com `warning` no log.

!!! note "Por que é um `ui.textarea` — uma decisão, não uma limitação"
    A primeira versão montava as linhas com **elements dinâmicos** (`ui.row` +
    `clear()` manual, depois `@ui.refreshable`), e o resultado foi: a lista
    aparecia **vazia no primeiro desenho**, embora com a faixa carregada do
    banco, e o **botão de remover disparava durante a montagem da página** — o
    clique do próprio primeiro desenho chegava no handler de apagar.

    Um campo de texto não tem estado de slot: é um valor só, que o navegador
    desenha, e a tela relê do banco a cada montagem. Por isso ele **não tem**
    esses dois defeitos, e ganha mais dois: é **mais fácil de revisar** pelo
    administrador (vê as faixas inteiras, em bloco) e é **copiável e colável
    entre ambientes** — servidor de homologação vira produção colando cinco
    linhas, sem clicar em N botões de adicionar e remover.

    O que se perde: remover uma faixa é apagar a linha e salvar, em vez de
    clicar num `X`. A troca compensa porque a lista é **curta**, é **editada por
    texto** e quem mexe nela é o **administrador** — tarefa rara, não o fluxo de
    quem usa o sistema.

### Onde a faixa é consultada

| Momento | Chamador | Efeito |
|:---|:---|:---|
| Enquanto o servidor **digita** o fixo no 1º acesso | `telas.py:1092-1127` (`_reavaliar_faixa`, ligado por `fixo_empresa.on_value_change`) | Escreve o aviso **ao vivo** com o nome da faixa mais próxima |
| Ao **avaliar** o conjunto de telefones | `mod_gest_cad_usuario/bd_manipulador.py:974` (`avaliar_telefones_primeiro_acesso`) | Preenche `fora_da_faixa` com `(numero, descricao_da_faixa_mais_proxima)`, **sem gravar** |
| Ao **gravar** | `bd_manipulador.py:1023` (`registrar_contatos_primeiro_acesso`) | **Salva** e devolve o mesmo aviso em `detalhes["fora_da_faixa"]` — avisado, nunca recusado |

## Primeiro acesso: senha e telefone (27/09/2026)

> **ATUALIZADO em 30/09/2026** — a troca de senha deixou de ser um modal sobre
> a página montada e virou um **guard de servidor**, com tela própria. A tabela
> abaixo e as linhas `1a`/`1b` descrevem o desenho **antigo**; o que vale hoje
> está em [A troca obrigatória passou a bloquear](#a-troca-obrigatória-passou-a-bloquear)
> e em [Força e vazamento de senha](#força-e-vazamento-de-senha-30092026).

> **EN:** `pagina_restrita` calls `_primeiro_acesso` after the layout is built.
> It chains **two** mandatory steps — password, then phone numbers — and only
> opens the second when the first was really completed. The server sheet of the
> municipality has no extension, so the directory number only exists if the
> server types it.
>
> **PT-BR:** `pagina_restrita` chama `_primeiro_acesso` depois de montar o
> layout. Ele encadeia **dois** passos obrigatórios — senha e telefones — e
> só abre o segundo quando o primeiro foi de fato concluído. A folha de
> servidores do município não traz ramal, então o número do diretório só
> existe se o próprio servidor o informar.

`pagina_restrita` (`mod_intranet/telas.py:117-131`) chama `_primeiro_acesso(user["nome"])` dentro de `try/except`; se a montagem falhar, loga e avisa "Erro ao abrir a troca obrigatória — recarregue a página" em vez de derrubar a página.

| Ordem | Condição e chamada | Arquivo:linha |
|:--:|:---|:---|
| 1a | `autenticacao.precisa_trocar_credenciais(nome)` ⇒ `_dialogo_troca_credenciais(nome, ao_concluir=abrir_telefones)` | diálogos em `:554`, com as variantes mínima `:586` e completa `:666` |
| 1b | `autenticacao.precisa_trocar_senha(nome)` ⇒ `_dialogo_troca_senha(nome, ao_concluir=abrir_telefones)` | diálogo em `:801` |
| 2 | `abrir_telefones()` ⇒ `bd.telefone_pendente(alvo)` ⇒ `_dialogo_telefones(alvo)` | encadeamento em `:1281-1300` · diálogo em `:982` |

Os três diálogos de senha agora aceitam **`ao_concluir`**. Sem esse parâmetro, um diálogo de senha que fechasse sem trocar deixaria o telefone para trás, e o servidor entraria no sistema **com a pendência e sem saber por quê**.

!!! note "`novo_nome`: a pendência é do usuário NOVO"
    `abrir_telefones(novo_nome=None)` recebe o login escolhido quando o
    `master` é renomeado. A pendência de telefone está no usuário **novo**,
    não no `master` que já saiu de cena — por isso o alvo é
    `novo_nome or nome_usuario`.

### `_dialogo_telefones` — o consentimento em caixas

`dialogo_card` de `w-[620px]` com `max_altura=True` e **`persistent`** (não fecha com ESC): fechar sem decidir deixaria o servidor sem número para sempre. São **quatro** campos, e cada um com a sua regra de consentimento.

| Campo | `papel`/`tipo` | Caixa de consentimento | Publica? |
|:---|:---|:---|:---:|
| **Celular particular** | `pessoal`/`celular` | `primeiro-acesso-chk-pessoal`, **começa desmarcada** | **nunca** |
| **Celular da prefeitura** | `empresa`/`celular` | `primeiro-acesso-chk-empresa`, **começa desmarcada** | **só se marcar** |
| **Telefone fixo da prefeitura** | `empresa`/`fixo` | `primeiro-acesso-chk-fixo`, **`disable` — travada marcada** | **sempre** |
| **Telefone residencial** (opcional) | `pessoal`/`fixo` | **não tem caixa** | **nunca** |

As três caixas são o **espelho visual** de `mod_gest_cad_usuario.bd_manipulador.telefone_e_publicavel`; a decisão real fica no banco. O fixo é gravado com `visivel=True` e o residencial com `visivel=False` de qualquer forma (`telas.py:1080-1089`) — marcar o celular particular não publica nada, e o checkbox travado do fixo não é o que autoriza a linha institucional.

A **quinta** linha do formulário (27/09/2026) é a caixa de **recado**, e ela não é uma caixa de consentimento:

| Caixa | `data-testid` | Rótulo | Efeito |
|:---|:---|:---|:---|
| **Telefone de recado** | `primeiro-acesso-chk-recado` | **"Não tenho linha própria: este é o telefone do setor, para recado"** | Marca o **fixo** com `recado=True` (`telas.py:1086`) |

O texto de apoio (`telas.py:1055-1059`) diz **onde** o número do setor costuma estar
— *a garagem, a secretaria da escola, a unidade de saúde, o almoxarifado* — e o que
acontece com a ligação: *quem receber anota o recado e passa adiante*. Sem essa
explicação, o servidor entende "recado" como "não atendem" e desiste de marcar.

#### O aviso de faixa, **enquanto digita**

> **EN:** While he types the landline, the dialog tells him whether the number
> is one of ours, and which is the nearest range. Showing the warning **after**
> saving is too late: he already saved, already got "telefones registrados",
> and only then finds out the number was wrong. The range exists to catch the
> mistake **in the finger**, not in the report.
>
> **PT-BR:** Enquanto ele digita o fixo, o diálogo diz se o número é nosso e
> qual é a faixa mais próxima. Mostrar o aviso **depois** de salvar é tarde: o
> servidor já salvou, já recebeu o "telefones registrados", e só depois
> descobre que o número estava errado. A faixa existe para pegar o erro **no
> dedo**, não no relatório.

`fixo_empresa.on_value_change(_reavaliar_faixa)` (`telas.py:1127`) chama
`_reavaliar_faixa` (`:1092-1125`), que monta o texto:

```
Atenção: 0035999999 está fora das faixas de telefone da prefeitura.
A faixa mais próxima é a Garagem — confira o número.
```

O aviso vive num `ui.label` de `text-caption text-orange-8` que fica **vazio** quando o
número entra na faixa (o elemento continua no DOM, com texto vazio — `set_text("")`, não
remoção; conferir ausência de elemento daria falso negativo, que foi exatamente o que
aconteceu na primeira versão do teste E2E). O `on_value_change` é o **caminho do próprio
projeto** (`campo_texto(ao_mudar=...)`); `on("update:model-value")` também funcionaria,
mas mistura duas formas de fazer a mesma coisa no mesmo arquivo.

#### `_montar_contatos()` separa a **leitura** da gravação

`telas.py:1071-1090` é puro: lê os **quatro** campos e devolve a lista de dicionários
que o cadastro grava, **sem** gravar nada. É essa separação que permite (a) o aviso ao
vivo, (b) `avaliar_telefones_primeiro_acesso` antes de salvar, e (c) que
`_salvar(liberacao_provisoria)` e `_confirmar()` cuidem só da **decisão**.

#### `_salvar(liberacao_provisoria)` e `_confirmar()` separam a decisão

`_salvar(liberacao_provisoria=False)` (`telas.py:1129-1167`) é quem chama
`registrar_contatos_primeiro_acesso(nome_usuario, nome_usuario, contatos,
liberacao_provisoria=liberacao_provisoria)` e desempacota os **três** valores
(`ok, msg, detalhes`) — com `detalhes` deciding o que aparece depois:

| `detalhes` | O que a tela faz |
|:---|:---|
| `fora_da_faixa` não vazio | `notificar(..., tipo="warning")` — salvou, mas o número não é nosso |
| `provisorio` verdadeiro | abre o **bilhete** `_aviso_provisorio(nome_usuario, DIAS_LIBERACAO_PROVISORIA)` (`:1259-1278`) |
| qualquer coisa | `dlg.close()` e `ao_concluir()` |

`_confirmar()` (`telas.py:1169-1187`) é o que o botão "Salvar telefones" chama, e é o
**guardião** do `liberacao_provisoria`: só ele pode passar `True`, e só depois das
**duas** travas.

## Política de senha: medidor, aceite de risco e tentativas de login (30/09/2026)

> **EN:** Password difficulty meter in the password-change form, a risk
> acceptance with double confirmation quoting the LGPD, and login attempts
> limited by **progressive delay** (never by account lockout).
>
> **PT-BR:** Medidor de dificuldade de senha no formulário de troca, aceite de
> risco com confirmação dupla citando a LGPD, e tentativas de login limitadas
> por **atraso progressivo** (nunca por bloqueio de conta).

Módulo: `mod_intranet/politica_senha.py`.

### O medidor responde "mas ela vazou e ainda assim…"

Vazamento e dificuldade são **duas leituras diferentes**, e a tela mostra as
duas. Uma senha pode vazar e ser forte; pode não vazar e ser fraca, porque é
adivinhável.

| Senha | Bits | Faixa |
|:---|---:|:---|
| `123456` | 15,5 | Muito fraca |
| `Senha@2025` | 31,2 | Fraca |
| `prefeitura2026` | 47,3 | Média |
| `MinhaSenhaForte#2026` | 76,4 | Forte |
| `aB3$Kq9!zR7#vN2@wT6^yL4&mP8*` | 134,6 | Muito forte |

`prefeitura2026` é o caso que mostra a diferença: 47 bits, barra no meio, e
mesmo assim o validador recusa — porque contém a palavra da instituição e um
ano. A **medida** é uma coisa; a **dedução** é outra.

Pisos das faixas: 0 / 30 / 45 / 60 / **90** bits. O topo é 90 de propósito —
uma senha humana de 20 caracteres dá ~76, e com o piso em 75 quase toda senha
boa cairia em "Muito forte", deixando a barra de distinguir nada.

### O aceite: pode usar, mas assinando

Senha fraca ou vazada é **recusada por padrão**. Mas quem escolheu a senha pode
usá-la assim mesmo — marcando duas coisas:

1. um checkbox ("li e estou ciente");
2. a palavra **`ESTOU CIENTE`** digitada.

O botão "Salvar nova senha" fica **desabilitado** até as duas. Sem isso o
servidor leria um botão apagado como defeito e clicaria por força, e o aceite
viraria teatro.

O aceite vale **só para aquela troca**. Não vira marca permanente no cadastro
porque amanhã a pessoa pode trocar a senha, e um rótulo de "usa senha fraca" que
ninguém pode apagar é estigma, não registro.

O que fica para sempre é a **auditoria**: quem assinou, quando, e que o texto da
LGPD foi apresentado. **A senha nunca entra no registro.**

### O texto do aceite e a LGPD

`politica_senha.TEXTO_ACEITE_RISCO` (bilíngue, EN no topo / PT-BR abaixo)
reproduz o que a lei estabelece **e o que ela não estabelece**:

- **Art. 6º, VI e VII** (segurança e prevenção) e **Art. 46**: a prefeitura é
  a **controladora** e adota medidas técnicas e administrativas contra acessos
  não autorizados. Esse é o dever do controlador, e é o que o sistema entrega.
- A **co-responsabilidade** é do servidor: escolher senha fácil é ato dele.
- Se a conta for invadida por senha fraca ou vazada, o uso indevido é
  atribuído ao perfil dele.

O texto **não** promete o que a lei não promete. Não há isenção de
responsabilidade, nem "a prefeitura não responde", nem cláusula que anule o
dever do controlador. Um aceite que só cita artigo para assustar é propaganda, e
a prefeitura não pode fazer isso com servidor público.

### Decisões que o responsável tomou (e o que elas custam)

| Decisão | Motivo registrado |
|:---|:---|
| Aceite **só avisa**, não bloqueia promoção de perfil | A responsabilidade é de quem escolheu a senha fraca, e se prova no registro — não num trinco que o próprio sistema aplicaria |
| Restrição vale **só para `administrator`**, não para permissão comum | Impressão e demais permissões de comum não ficam impedidas |
| Tentativas de login: **atraso**, sem bloqueio | "Troquei a senha e digitei a antiga duas vezes" viraria chamado no DTI — e quem mais digita errado é quem trabalha com a senha o dia todo |

### Tentativas de login: atraso, nunca bloqueio

| Falhas | Espera |
|---:|---:|
| 0 | 0 s |
| 1 | 1 s |
| 2 | 2,5 s |
| 3 | 5,2 s |
| 5 | 13 s |
| 9+ | 30 s (teto) |

`login_tentativas_maximas` — **piso 3**, configurável até 20. Abaixo de 3 ele
ignora; acima de 20, limita.

O efeito real do limite não é o tempo, é o **custo**: um ataque de dicionário
fica caro sem nunca fechar a conta de quem só esqueceu a senha.

Três detalhes que valem o registro:

- **Login certo zera a contagem** — senão a penalidade vaza para a sessão
  seguinte de quem entrou corretamente.
- **A janela é de 15 min.** Passada ela, vale zero: a conta não fica lenta
  para sempre depois de um período ruim de digitação.
- **Login inexistente também conta.** A mensagem é a mesma nos dois casos
  ("Usuário ou senha inválidos"), então sem contar aqui o atacante testaria
  logins inexistentes de graça — e é assim que se descobre a lista de quem tem
  conta. Como `tb_login_tentativas` tem chave estrangeira para `tb_usuarios`, o
  inexistente é contado em memória.

Medido no login real: tentativas 1 e 2 sem aviso; da 3 em diante o aviso de
espera entra na mensagem, e `qacomum` continua entrando com a senha certa.

`tb_login_tentativas` fica no banco do módulo **`usuarios`** — que é o dono do
login — e não no central.

---

## A cor dos botões é uma só para todo o sistema (30/09/2026)

> **EN:** Every button in the system follows the same rule. If the user picked a
> style, every button takes that style's colour; if the user picked "Padrão",
> every button takes the colour the administrator configured.
>
> **PT-BR:** Todo botão do sistema segue a mesma regra. Se a pessoa escolheu um
> estilo, todos os botões tomam a cor desse estilo; se escolheu "Padrão", todos
> tomam a cor que o administrador configurou.

### O defeito, e por que era estrutural

O botão do diálogo "Duplicar usuário" saía **teal fixo** numa tela inteira azul.
Não era um botão com a cor errada: era o **único botão que não ouvia** a escolha
da pessoa.

A causa era o `BotaoFabrica` escrever `background-color` em **estilo inline**
com a cor do módulo, e **estilo inline vence CSS** — nenhuma custom property
chegava naquele botão. A regra do estilo já funcionava para o cabeçalho e para
tudo que usava o token; o botão padronizado estava do lado de fora disso.

### A correção: um ponto único de resolução

```
preview_estilos.cor_do_botao(padrao)
   ├─ pessoa escolheu estilo?  → paleta do estilo, `primaria_q` (contraste 4,5:1)
   └─ "Padrão"/sem escolha?    → cor_principal do administrador
```

`aplicar_no_botao()` é chamado pela fábrica **por último**, depois do
`.style()` — escrever antes seria sobrescrito na sequência. E só nas variantes
**tematizadas** (`primario`, `secundario`, `texto`, `icone`).

### O que NÃO mexe

Cor de **estado** é cor de estado, em qualquer estilo:

| Cor | Significado | Segue o estilo? |
|:---|:---|:--:|
| `negative` | apagar, recusar, excluir | **não** |
| `warning` | restaurar | **não** |
| `grey-*` | neutro | **não** |
| `primario`/`secundario`/`texto`/`icone` | ação normal | **sim** |

Pintar o botão de "excluir" de azul esconderia o que a ação faz. É o mesmo
raciocínio do botão de aviso âmbar: a cor carrega significado, e_significado_
não é decoração.

### Inventário (levantado por AST, todo o sistema)

31 chamadas passavam `cor=`. Depois da correção:

| Situação | Antes | Depois |
|:---|---:|:---|
| Cor de **estado** (`negative`, `warning`, `grey`) | 10 | 10 — mantida |
| Cor de **marca** chumbada (`teal-8`, `green-8`, `orange-9`, `primary`…) | 18 | **0** |
| Passagem interna da fábrica | 2 | 2 — não é ponto de chamada |
| Props `color=` fora da fábrica | 0 | 0 |

Os 18 removidos estavam em `mod_gest_cad_usuario` (13), `mod_solicita_impressao`
(4) e `mod_renomear_empenho` (1).

### `PADRAO_ADM` deixou de ser `None`

Havia um segundo defeito, do mesmo underp: com `PADRAO_ADM = None`, a comparação
`p == PADRAO_ADM` nunca era verdadeira, e aí **"Padrão" caía na paleta default do
protótipo** (verde) em vez da cor do administrador. Escolher "Padrão" e receber
uma cor que ninguém configurou é a mesma confusão do botão verde.

Agora `PADRAO_ADM = PADRAO_PADRAO`, e "Padrão" significa exatamente o que a
pessoa lê: a cor configurada pelo administrador.

| Escolha | Cor do botão |
|:---|:---|
| (sem escolha) / `padrao` | `cor_principal` do administrador |
| `azul` | `#1668d8` |
| `verde` | `#0f7a6d` |
| `roxo` | `#7c3aed` |
| `preto` | `#111111` |

---

## A troca obrigatória passou a bloquear (30/09/2026)

> **EN:** The mandatory password change used to be a modal drawn **on top of the
> already-built page**. `_montar_layout` ran first — header, drawer and the menu
> with every module — then the dialog opened over it, and `pagina_restrita`
> returned the user, so the caller's `with` went on and rendered the whole
> screen. `persistent` stops the modal from being **closed**; it never stopped
> the user from **navigating**. A reported symptom: pressing "back" moved to
> another module. The change is now enforced on the server.
>
> **PT-BR:** A troca obrigatória era um modal desenhado **por cima da página já
> montada**. `_montar_layout` rodava primeiro — cabeçalho, drawer e o menu com
> todos os módulos —, o diálogo abria sobre ele e `pagina_restrita` devolvia o
> usuário, então o `with` do chamador continuava e desenhava a tela inteira. O
> `persistent` só impedia o modal de ser **fechado**; nunca impediu a pessoa de
> **navegar**. Um sintoma relatado: apertar "voltar" levava a outro módulo. A
> trava passou para o servidor.

`pagina_restrita` é o **único** ponto por onde passa toda rota protegida do
projeto, e o guard fica **antes** de `_montar_layout`:

```
pagina_restrita()
   ├─ sem sessão / sessão revogada  → /login
   ├─ _pendencia_de_troca(nome)     → /troca-obrigatoria   ← o guard novo
   ├─ validar_acesso_modulo         → /
   ├─ _montar_layout(...)           ← nunca chega aqui com pendência
   └─ _primeiro_acesso(nome)        ← só telefone e dados
```

`tela_troca_obrigatoria()` monta **uma tela solta**: sem cabeçalho, sem drawer,
sem menu. Três garantias, as três verificadas no navegador:

| Garantia | Como |
|:---|:---|
| Não há o que navegar | A tela solta não tem **nenhum** `<a href>` — não há link nem botão de módulo |
| Não é porta de entrada | Sem `usuario_logado()`, vai para `/login` |
| Não é beco sem saída | Sem pendência, vai para `/`; `pagina_restrita` não é chamada aqui, senão as duas rotas se devolveriam para sempre |

Rotas testadas com a pendência armada — `/`, `/blog`, `/auditoria`,
`/configuracoes`, `/estoque` e `/agregador-noticias` caem **todas** em
`/troca-obrigatoria`, com `drawer` ausente. Depois da troca, a navegação volta
(`/` com 16 itens de menu).

**"Sair e entrar com outro usuário"** — os dois diálogos (senha e credenciais)
ganharam essa saída, para **máquina compartilhada**: quem abriu o sistema e não
quer assumir o login de outra pessoa precisa poder simplesmente liberar o
equipamento. Chama o `_logout` do cabeçalho, que encerra a sessão no banco e
limpa o `app.storage.user` — só fechar o modal deixaria a sessão viva, e quem
viesse depois entraria sem passar pela tela de login.

`_primeiro_acesso` **deixou de abrir os diálogos de senha**: eles só nascem na
tela solta. O passo seguinte (telefone e dados) continua em `/`, dentro de
`_primeiro_acesso`, depois que a senha já foi trocada. A tela solta tem uma
responsabilidade só.

---

## Força e vazamento de senha (30/09/2026)

> **EN:** `validador_senha.py` checks password strength and whether the password
> appears in known breaches. The path that **blocks** a change is fully
> offline, so changing a password never depends on the network — which is what
> a municipality running on a closed local network needs.
>
> **PT-BR:** `validador_senha.py` verifica a força da senha e se ela aparece em
> vazamentos conhecidos. O caminho que **bloqueia** uma troca é totalmente
> offline, então trocar senha nunca depende da rede — que é o que uma
> prefeitura em rede local fechada precisa.

### Duas camadas, e só uma decide

| Camada | O que faz | Rede |
|:---|:---|:---|
| `analisar_offline()` | Entropia total de Shannon, teclado, sequência, repetição, nome do usuário, ano, padrões do órgão | **não** |
| `analisar_online()` | Consulta de vazamento por k-anonimato | sim, e nunca bloqueia |

`veredito_bloqueante()` é o que `trocar_senha_propria` chama, e ele é **offline
por contrato** (medido: **0,003 s**). Ele só olha o veredito de vazamento no
cache — local, no banco — então uma senha já consultada continua bloqueada
**sem internet**. Quem decide é a análise de força.

A camada de vazamento só informa, e foi desenhada para **não poder travar**:
sai por `run.io_bound` (fora do event-loop), tem tempo máximo próprio (conexão
1 s, leitura 2 s), **zero retries**, é precedida por sondagem de internet com
cache de 15 min, e qualquer falha vira `indisponivel` em vez de exceção.

Comportamento sem internet, medido:

| Situação | Resultado |
|:---|:---|
| Senha nunca consultada | `sem_internet` em **0,029 s** — ignorada, senha forte é aceita |
| Senha já consultada | `cache` em **0,006 s** — o veredito sobrevive sem rede |

### Consulta por k-anonimato

Manda-se só os **5 primeiros caracteres** do SHA-1 (hex, maiúsculo) e a
comparação do pedaço que falta é feita aqui. São 1.048.576 prefixos possíveis,
então um prefixo é compartilhado por centenas de senhas. A senha em claro
**nunca sai do servidor** — nem completa, nem em hash.

Medido nesta máquina:

| Senha | Vazou | Ocorrências |
|:---|:--:|---:|
| `123456` | sim | 210.461.208 |
| `password` | sim | 52.372.427 |
| aleatória de 16 caracteres | não | 0 |

### Por que a lista de senhas vazadas NÃO está no banco

Os quatro motivos estão em `validador_senha.motivos_sem_corpus()`. Em resumo:
o veredito de uma tabela local é **fotografia de uma data**; o corpus não cabe
numa base de prefeitura e **não evita** o trabalho da chamada viva; `AGENTS.md`
§7 e §8.3 proíbem segredo no git imutável e replicado; e é tratamento de dado
pessoal em massa (LGPD) numa intranet que não tem essa função.

O que **é** gravado, e é defensável:

| Tabela | O que é |
|:---|:---|
| `tb_senha_vazamento_cache` | Memória das **consultas feitas**: par (prefixo, sufixo) do SHA-1 e a contagem |
| `tb_senha_padrao_organizacao` | **Padrões de nomeação do próprio órgão** — `prefeitura`, `municipio`, `detran`… Configuração do município, revisável, não dado de terceiro |

Chaves de configuração: `senha_consultar_vazamento` (1), `senha_sondar_internet`
(1) e `senha_tamanho_minimo` (6).

### Contas de teste: a regra não se aplica — e a tela não diz nada

`qacomum` e `qamaster` (`validador_senha.CONTAS_DE_TESTE`) entram com a senha
`123456` e ficam **fora** da regra de força. Sem essa isenção o primeiro acesso
delas seria um beco sem saída: troca obrigatória com a senha recusada.

A isenção vale nos **dois lados**, e essa simetria é o ponto: se ficasse só na
camada de bloqueio, o serviço deixaria passar e a tela acusaria em vermelho —
a pessoa leria que foi recusado e o sistema gravaria assim mesmo. Por isso
`analisar_offline()` devolve `ok=True` e sem `bloqueios` para elas.

**Na tela não aparece nada.** `texto_para_usuario()` devolve vazio para conta
de teste, e o rótulo é limpo. A justificativa fica aqui e no código — quem lê
esta documentação é quem escreve o sistema; quem loga não precisa saber por que
uma conta de teste escapa da regra, e um aviso ali só ocuparia a tela.

Da mesma forma, a situação da consulta (`sem_internet`, `limite_requisicoes`) é
traduzida por `_SITUACAO_PT_BR` antes de aparecer. **Nome de arquivo e número
de seção não vão para a tela**: quem lê a mensagem é servidor da prefeitura no
balcão, não quem escreve o código.

### As DUAS travas (27/09/2026)

> **EN:** Two gates instead of one is not distrust of the server — it is the
> opposite. The only failure left is the hurried click on a warning screen, and
> it goes through two. A server who read the warning twice and went ahead is
> someone who understood; someone who clicked once may have read only the first
> line.
>
> **PT-BR:** Duas travas em vez de uma não é desconfiança do servidor — é o
> contrário. A única falha que sobra é o clique apressado numa tela de
> advertência, e ele passa por duas. Um servidor que leu o aviso duas vezes e
> seguiu em frente é alguém que entendeu; alguém que clicou uma vez pode ter só
> lido a primeira linha.

O encadeamento inteiro, com **nada gravado** até a segunda confirmação:

```
_confirmar()                                    # telas.py:1169
   └─ sem particular?      → notificar e PARA (nem abre a trava)
   └─ tem fixo da prefeitura? → _salvar()
   └─ SÓ AQUI (sem fixo, com particular):
        └─ _travas_falta_numero(...)            # telas.py:1195-1226  — TRAVA 1
             ├─ "Informar o telefone do setor"  → fecha e volta ao formulário
             └─ "Não sei meu número"
                  └─ _travas_confirmar(...)     # telas.py:1229-1256  — TRAVA 2
                       ├─ "Voltar e informar o número" → fecha
                       └─ "Entendo, liberar por enquanto"
                            └─ fecha as duas + ao_confirmar(True)  # _salvar(True)
                                 └─ _aviso_provisorio(...)          # telas.py:1259 — o bilhete
```

| Trava | Onde | O que **escreve** |
|:--:|:---|:---|
| **1ª** — `_travas_falta_numero` | `telas.py:1195-1226` | "Falta um telefone da prefeitura". Explica que todo servidor está ligado a uma secretaria ou setor e todo setor tem telefone; oferece **"Informar o telefone do setor"** (volta ao formulário) ou **"Não sei meu número"**; e lista **onde perguntar**: secretaria da escola, unidade de saúde, **setor de empilhadeiras**, garagem, almoxarifado |
| **2ª** — `_travas_confirmar` | `telas.py:1229-1256` | "Acesso temporário". **Escreve o preço**: liberado por `DIAS_LIBERACAO_PROVISORIA` (**4 dias**), depois disso a conta é **bloqueada** e **só o DTI** reabre. Repete onde perguntar e diz para voltar pelo perfil depois |
| **Bilhete** — `_aviso_provisorio` | `telas.py:1259-1278` | "Acesso liberado por enquanto". Avisa que o nome **aparece na lista telefônica, mas sem número** — a prefeitura ainda não sabe como falar com a pessoa |

O preço da 2ª trava é lido de `DIAS_LIBERACAO_PROVISORIA` (o **mesmo** valor que o
cadastro grava), então mudar o prazo no cadastro muda o texto da tela — não há
número duplicado em dois lugares.

### A liberação temporária e o paliativo de 4 dias (27/09/2026)

> **EN:** The window is served **at login**. `autenticar` calls
> `bloqueio_provisorio_pendente(user_nome)` right after the password check; if
> the 4-day deadline has passed, it blocks the account, writes
> `acesso_provisorio_expirado` to the audit trail and refuses the login.
>
> **PT-BR:** A janela é cumprida **no login**. `autenticar` chama
> `bloqueio_provisorio_pendente(user_nome)` logo depois de checar a senha; se o
> prazo de 4 dias venceu, bloqueia a conta, grava
> `acesso_provisorio_expirado` na auditoria e recusa o login.

| Passo | Arquivo:linha | O quê |
|:--|:---|:---|
| 1 | `autenticacao.py:332` | `autenticar(user_nome, senha)` — assinatura intacta `(ok, msg)` |
| 2 | `autenticacao.py:355-361` | `try: _gest_ = _gest()` + `bloqueio_provisorio_pendente(user_nome)`; se verdadeiro, `bloquear_usuario("sistema", user_nome, True)` e `audit_log(user_nome, "intranet", "acesso_provisorio_expirado", …)` |
| 3 | `autenticacao.py:362-364` | A mensagem: **"Seu acesso temporário de 4 dias terminou. Procure o DTI para liberar seu cadastro depois de atualizar seu telefone."** |
| 4 | `autenticacao.py:365-368` | `except Exception: pass` — a checagem que falha **não** bloqueia ninguém |

!!! danger "Por que a checagem está no **login**, e por que ela é engolida"
    Sem essa checagem, a liberação temporária seria um prazo que **ninguém nunca
    fiscaliza** — a conta entraria para sempre e o paliativo viraria norma.
    Checar mais tarde (rotina noturna) existiria; o problema é que viraria
    norma **sem ninguém perceber**.

    E o `except: pass` não é descuido: um erro de banco ali transformaria
    **todo servidor** em "usuário bloqueado" no primeiro dia. Uma checagem que
    pode bloquear a prefeitura inteira por causa de uma tabela travada é
    pior do que um prazo que passa. O log registra; a conta fica aberta.

Detalhe das funções de gravação e do estado (`informacao_acesso_provisorio` com
`vencido` = prazo e `bloqueado` = conta, campos **independentes**):
[Módulo Gestão de Usuários](gest_cad_usuario.md#a-liberacao-temporaria-de-4-dias-o-paliativo).

!!! info "Por que o telefone é pergunta e não importação"
    A folha de servidores do município traz matrícula, nome, secretaria,
    departamento, cargo e vínculo — mas **não traz ramal**. O número do
    diretório só existe se o próprio servidor informar, e é por isso que
    este passo é obrigatório no primeiro acesso, em vez de ser um dado
    copiado.

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
| `Dialogo(titulo, largura, ...)` (`ui_comum.py:242`) — context manager com `ExitStack` (escopo do card permanece aberto até `__exit__`), estilo de cartão do tema, `abrir()`/`fechar()`; devolve `(dlg, card)` | `dialogo_card(...)` (`ui_comum.py:299`) — **confirmações e fichas curtas** |
| — | `dialogo_formulario(...)` (`ui_comum.py:359`) + `LARGURA_DIALOGO_FORMULARIO` (`:342`), `CSS_GRADE_CAMPOS` (`:347`), `CSS_GRADE_AVISOS` (`:353`) — **diálogos de FORMULÁRIO**: `w-[88vw] max-w-[1600px]`, teto `max-h-[90vh]` com rolagem **interna** (`miolo` com `min-h-0`) e grade `repeat(auto-fit, minmax(300px, 1fr))`. Devolve `(dlg, card, miolo, grade)`; `miolo`/`grade` saem **antes** do `yield` para o rodapé nascer no card. **Regra de classificação formulário × confirmação + inventário dos 25 diálogos: [Diálogo de Formulário](../dialogo_formulario.md)** |
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
| `_banco_central_sem_schema()` | `banco_conexao.py:61` | `True` quando o SQLite central ainda não tem **nenhuma** tabela — classifica o erro de boot (ver [Aviso de primeiro boot](#aviso-de-primeiro-boot-o-erro-esperado-da-primeira-execucao-29092026)) |

**Proxy psycopg2 (`_CursorPostgres`, `banco_conexao.py:390`):** traduz `?`→`%s`; `datetime('now','localtime')`→`LOCALTIMESTAMP`; DDL SQLite→Postgres (`_ddl_postgres`, `:358` — `AUTOINCREMENT` removido, `INTEGER PRIMARY KEY`→`SERIAL PRIMARY KEY`, `BLOB`→`BYTEA`, `DATETIME`→`TIMESTAMP`, remoção de `FOREIGN KEY`); `INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`; `INSERT OR REPLACE`→`ON CONFLICT`; `PRAGMA`/`sqlite_master`/FTS5 (`CREATE VIRTUAL TABLE`/`CREATE TRIGGER`) ignorados; `PRAGMA table_info`→`information_schema.columns`; `lastrowid` via `RETURNING id` com SAVEPOINT e SAVEPOINT por statement (falha isolada não desfaz a transação).

**Roteamento:** `repositorio.engine(chave)`/`sessaodb(chave)` roteiam para o Postgres via `obter_engine_modulo(chave)` quando `banco_tipo='postgres'`; senão mantêm SQLite por arquivo. `CrudBase._conectar` também roteia pelo backend ativo.

**Dependência habilitada:** `requirements.txt:24-25` — `sqlalchemy>=2.0` + `psycopg2-binary>=2.9` (sem driver o sistema segue de pé em SQLite com exception no loguru). Container: `assets/docker/postgres/docker-compose.yml`. Toggle no admin: `/configuracoes` → aba **Config** (ao final, após o card "Ícones") → card **"Banco de dados — SQLite ou PostgreSQL"** (ícone `storage`, `data-testid="config-aplicar-banco"`, sem reload — exige **reiniciar o servidor**). Detalhes: [Arquitetura — Backend duplo](../arquitetura.md#arquitetura-de-acesso-a-dados-do-nucleo-backend-duplo-0809) e [Configurações](../configuracoes.md#card-banco-de-dados-sqlite-ou-postgresql-0809).

#### Aviso de primeiro boot — o erro esperado da primeira execução (29/09/2026)

No **primeiro boot**, `main.py` lê `banco_tipo` em `tb_config` **antes** de o banco existir. O `sqlite3.connect()` de `_ler_config_sqlite` **cria o arquivo vazio** e o `SELECT` seguinte falha com `sqlite3.OperationalError: no such table: tb_config` — o `init_db()` só semeia o schema em seguida.

**O comportamento fail-soft já estava certo** antes desta mudança: a exceção cai no `except`, o loguru registra e a função devolve o `default` (`sqlite`), e o sistema sobe. O que mudou em 29/09/2026 foi **apenas a impressão no terminal**: a nova função `_banco_central_sem_schema()` (`banco_conexao.py:61`) classifica o caso e imprime, logo abaixo do traceback:

```
[banco] Primeira execução: 'banco_tipo' ainda não existe em tb_config porque o
banco central ainda não foi criado. Erro esperado no primeiro boot — o schema é
semeado em seguida. Causa registrada no log.
```

| Item | Comportamento |
|:---|:---|
| O que mudou | **só a impressão** — o traceback e o log ERROR continuam |
| O que NÃO mudou | o comportamento fail-soft: `default` devolvido, sistema sobe |
| Como classifica | `True` = banco central sem **nenhuma** tabela (`sqlite_master` vazio) ou arquivo inexistente → é o primeiro boot. `False` = banco já semeado, e aí a falha é **anômala** e precisa de atenção |
| Falha na inspeção | devolve `False` — **não** mascaramos falha real como se fosse primeiro boot |
| Por que o log **não** foi suprimido | AGENTS.md §3.2 proíbe engolir erro em silêncio: a causa continua registrada em ERROR. O que muda é a leitura de quem olha o boot |

!!! danger "Não "limpe" esse log achando que é segurança"
    A supressão do log **não** é um ganho de segurança aqui: ela apagaria a
    única evidência de que a leitura do seletor de backend falhou, num sistema
    em que `banco_tipo` decide se o banco inteiro é SQLite ou PostgreSQL. O que
    foi feito foi **explicar** o erro, não escondê-lo. Se um dia a classificação
    ficar imprecisa (por exemplo, banco semeado mas `tb_config` derrubada), a
    impressão dirá "primeira execução" onde há defeito — e por isso a função
    consulta `sqlite_master`, que é o que separa os dois casos de verdade.

**Onde verificar:** o aviso só aparece **uma vez**, no primeiro boot de uma
instalação nova. Ver o log (`logs/`) — a entrada `ERROR` de
`_ler_config_sqlite('banco_tipo')` continua lá em qualquer boot em que ele
reapareça.

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

> **Os valores padrão de credencial não são documentados aqui de propósito.**
> Eles ficam no código e saem do texto no momento da entrega do produto. O que
> esta tabela precisa dizer é *qual chave guarda o quê*: quem for configurar
> procura o default no código, e um default escrito num arquivo versionado é um
> default copiado junto para o proximo servidor.

| Chave | Onde esta | Descrição |
|:---|:---|:---|
| `banco_usuario` | `mod_intranet/bd_conexao.py` | Usuário de operações normais |
| `banco_senha` | `mod_intranet/bd_conexao.py` | Senha do usuário normal |
| `banco_admin_usuario` | `mod_intranet/bd_conexao.py` | Usuário de operações administrativas |
| `banco_admin_senha` | `mod_intranet/bd_conexao.py` | Senha do admin |
| `postgres_url` | `mod_intranet/bd_conexao.py` | DSN base, montada a partir das chaves acima |

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
- **Fachada de integração** (`integracoes.py`, 25/09/2026; 9 funções em 27/09/2026) — funções fail-soft de imports lazy que permitem a um módulo de negócio alcançar outro **sem importá-lo** (o núcleo possui o acoplamento; o banco de cada módulo continua isolado): `obter_usuario_gestao`/`listar_usuarios_gestao` (Filas, Lista Telefônica → Gestão de Usuários), `agregador_habilitado`/`listar_noticias_para_tv` (Filas → Agregador), `limpar_noticias_censuradas` (Blog → Agregador), `obter_organograma_base` (Solicitação → Lista Telefônica, com fallback local no chamador), **`espelhar_cadastro_na_lista_telefonica`** (núcleo → Gestão de Usuários **e** Lista Telefônica, 27/09/2026), **`telefones_de_recado_para_lista`** (núcleo → Gestão de Usuários, para o "deixe recado" do cartão, 27/09/2026) e `modulo_habilitado`. Fecha as 5 violações de isolamento detectadas por `assets/test/check_integridade.py` (**5 falhas/17 → 13/13**). Referência completa: [Fachada de Integração](../arquitetura_de_software_das/fachada_integracoes.md).
- Jobs: `backup:<chave>` (12 h), `cleanup_pdf`/`cleanup_solicita` (1 min), `poda_auditoria` (24 h), `monitor_empenho` (10 s).

## Testes

```bash
.venv/bin/python test/test_fase1_login.py
.venv/bin/python test/test_server.py
.venv/bin/python test/verifica_ui_comum.py   # 190 verificações (ui_comum + no_caps + helpers de tela + padrão próprio do tema + edit_pdf migrado + cabecalho com tema do módulo + campo_texto/campo_selecao + campo_cor/card_config + campo_modulo restaurado + equivalência wrapper↔classe)
.venv/bin/python test/smoke_senha_ui_comum.py # 8 verificações (NiceGUI real: campo_texto(senha=True) byte-idêntico ao ui.input cru)
.venv/bin/python test/teste_classes_crud.py   # 68 verificações (CrudBase em SQLite real, gancho de auditoria, banco_conexao, equivalência wrapper↔classe, GradeTabela/PainelLista/FormularioBuilder)
.venv/bin/python assets/test/check_integridade.py  # 13/13 — isolamento modular por AST (fachada integracoes.py)
```

## Pontos de atenção

- `inicializar_bancos()` roda o central **antes** de importar módulos (ordem crítica — `main.py:16-17`).
- `storage_secret` é placeholder (`main.py:336`) — trocar em produção.
- `backup_interval_hours` é o intervalo do card "Configurações gerais" (grava e **reagenda** o job global); os jobs por módulo usam `backup_horas:<modulo>`. `sessao_retencao` (dias, padrão 50) tem campo no mesmo card. **Desde 25/09/2026 as duas chaves estão em `PADRAO_CONFIG`**, junto com todos os outros defaults de `tb_config` — o default nunca mais pode ser escrito como literal em outro ponto (ver [Análise do Núcleo — `PADRAO_CONFIG`](../analise_mod_intranet.md#padrao_config-fonte-unica-de-verdade-dos-defaults-25092026)).
- **`grafana_sync.obter_grafana_url()` só aceita `http(s)`**: valor fora do esquema (ex.: `file://`) é ignorado e cai no padrão `http://localhost:3000` (correção de segurança 25/09/2026, bandit B310).

Ver [Análise do Núcleo](../analise_mod_intranet.md) (detalhe completo, incluindo reconstrução de `bd_conexao.py`/`bd_manipulador.py` a partir de `*.pyc`).