# Phone Directory Module — `mod_lista_telefonica`

> Phone directory / expandable organogram module: route `/lista-telefonica` (key `lista_telefonica`) · own database `db_mod_lista_telefonica.db` (WAL) · **current screen (27/09/2026)**: **ONE single search field** (`lista-busca-termo`, matches name, phone **OR** unit) plus **THREE cascading `ui.select`s** for the organogram walk (`lista-cascata-1/2/3`, Unidade / Subunidade / Sub-subunidade) — there is **no `lista-nav-*` button left** · contacts in a **single continuous 3+ column grid** of fixed-height cards (`CSS_GRADE` `minmax(200px, 1fr)` + `ALTURA_CARTAO` `5.9rem`) · card phone **without the `+55` prefix** (the `tel:` link keeps the full number) · **admin CRUD inside the screen** (server-side guard) · **printing** (PDF download via `GET /lista-telefonica/pdf` + browser print) · **recursive** organogram tree (depth cap 20 against `parent_id` cycles) · **mirroring of the user register through the core** (27/09/2026): `mod_intranet/integracoes.espelhar_cadastro_na_lista_telefonica(ator)` reads `leitura_lista.listar_para_lista_telefonica()` and hands the list to `sincronizar_contatos_do_cadastro(contatos, ator)` — **the directory never opens the register database** (AGENTS.md §2, enforced by `assets/test/check_integridade.py`) · **consent rule** `telefone_e_publicavel` (institutional landline always, company mobile only on consent, personal numbers never) · **"deixe recado"** in the card for a sector line (27/09/2026, `integracoes.telefones_de_recado_para_lista()`, one query per screen draw) · `tb_sincronizacao` + `INTERVALO_REFRESH_MIN` 15 + silent auto re-mirror · admin panel: delete branch, move, elevate/relegate, reorder/swap, transfer contacts.

---

# Módulo Lista Telefônica — `mod_lista_telefonica`

> Módulo de lista telefônica / organograma expansível: rota `/lista-telefonica` (chave `lista_telefonica`) · banco próprio `db_mod_lista_telefonica.db` (WAL) · **tela atual (27/09/2026)**: **um único campo de busca** (`lista-busca-termo`, que casa nome, telefone **OU** unidade) e **três `ui.select` em cascata** para percorrer o organograma (`lista-cascata-1/2/3`, Unidade / Subunidade / Sub-subunidade) — **não existe mais nenhum `lista-nav-*`** · contatos em **uma só grade contínua de 3+ colunas**, com cartões de altura fixa (`CSS_GRADE` `minmax(200px, 1fr)` + `ALTURA_CARTAO` `5.9rem`) · o telefone do cartão **não mostra o `+55`** (o link `tel:` continua com o número completo) · **CRUD do admin na própria tela** (guarda no servidor) · **impressão em PDF** (`impressao.py`, rota `GET /lista-telefonica/pdf`) + impressão do navegador · **árvore do organograma recursiva** (teto de profundidade 20 contra ciclo de `parent_id`) · **espelhamento do cadastro de usuários pelo núcleo** (27/09/2026): `mod_intranet/integracoes.espelhar_cadastro_na_lista_telefonica(ator)` lê `leitura_lista.listar_para_lista_telefonica()` e entrega a lista a `sincronizar_contatos_do_cadastro(contatos, ator)` — **o diretório nunca abre o banco do cadastro** (AGENTS.md §2, garantido por `assets/test/check_integridade.py`) · **regra de consentimento** `telefone_e_publicavel` (fixo institucional sempre, celular da prefeitura só com autorização, particular nunca) · **"deixe recado"** no cartão para o número do setor (27/09/2026, `integracoes.telefones_de_recado_para_lista()`, uma consulta por desenho da tela) · `tb_sincronizacao` + `INTERVALO_REFRESH_MIN` 15 + reespelhamento automático silencioso · painel admin: excluir ramo, mover, elevar/rebaixar, ordenar/comutar, transferir contatos.

## Propósito

Lista telefônica interna com **organograma genérico de 12 secretarias**. O usuário recorta a listagem por **três selects em cascata** (Unidade → Subunidade → Sub-subunidade) e vê os contatos **sempre em ordem alfabética** — a ordem vem do banco (`listar_arvore_contatos`, que já ordena secretaria → setor → subsetor → contato), então a tela não reordena nada.

A busca é **um campo só** (`lista-busca-termo`): o mesmo texto casa com **nome**, **telefone** ou **unidade**, com comparação **OU** entre os três e normalização sem acentos. No celular, o telefone é **clicável** (`tel:`) e oferece diálogo "Ligar agora" com fallback para desktop.

A listagem é **uma grade contínua de 3+ colunas** (não uma grade por unidade): os cartões fluem na grade e cada um carrega o **caminho da sua unidade**, que é o que preserva a leitura de organograma. O **recorte** vem do nível mais fundo escolhido na cascata (`nivel_3 > nivel_2 > nivel_1`).

!!! warning "Botões de navegação do organograma nunca existiram nesta versão"
    Versões anteriores da documentação falavam em `lista-nav-todas`,
    `lista-nav-secretaria-<id>`, `lista-nav-setor-<id>`,
    `lista-nav-subsetor-<id>` e em três campos de busca
    (`lista-busca-nome`, `lista-busca-telefone`, `lista-busca-unidade`).
    **Nada disso existe no código atual.** O que existe é o
    `lista-busca-termo` (único) e `lista-cascata-1/2/3`. A única
    ocorrência de `lista-nav` que sobrou é um seletor de CSS
    **inerte** em `CSS_IMPRESSAO` (`telas.py:48`), que esconde
    qualquer elemento com esse prefixo na impressão — não há elemento
    algum para esconder.

O organograma base é **genérico** e desacoplado de vínculo territorial, servindo como semente inicial editável pelo administrador (criar, mover, elevar, reordenar, excluir ramo).

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:207` (chamada no import da tela, `bd_manipulador.py:1223` `init_db()`; bootstrap central `mod_intranet/bd_criador.py`).

Conexão via `mod_intranet/banco_conexao.conexao("lista_telefonica")` (backend duplo SQLite/PostgreSQL, `PRAGMA journal_mode=WAL` + `foreign_keys=ON`). Índices `idx_unidade_parent`, `idx_contato_unidade`, `idx_contato_nome`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_unidade` | `id` PK, `nome`, `tipo` (`secretaria`\|`setor`\|`subsetor` `CHECK`), `parent_id` FK CASCADE → `tb_unidade.id`, `ordem`, `telefone`, `ativo` (default 1) |
| `tb_contato` | `id` PK, `unidade_id` FK CASCADE → `tb_unidade.id`, `nome`, `telefone`, `user_nome` (vínculo opcional à base de usuários), `tipo` (`vinculado`\|`externo` default `externo`), `data_criacao` |
| `tb_sincronizacao` | `id` PK `CHECK (id = 1)` (**uma única linha**), `ultima_em`, `total_criados`, `total_atualizados` — carimbo do último espelhamento do cadastro |

Semente idempotente (`bd_manipulador.py:238-259`): só semeia quando `COUNT(tb_unidade)==0` (log `info "Organograma base semeado: 12 secretarias"`). Constante `ORGANOGRAMA_BASE` (`bd_manipulador.py:30`) com 12 secretarias e respectivos setores/subsetores:

- Gabinete, Administração, Finanças, Saúde, Educação, Obras e Infraestrutura, Agricultura, Meio Ambiente, Assistência Social, Cultura, Esporte e Lazer, Planejamento — cada uma com setores e subsetores (ex.: Administração → Recursos Humanos → Folha/Capacitação, Patrimônio → Compras/Licitações, T.I. → Suporte/Redes, etc.). Ordem semeada via `ordem` sequencial por nível.

⚠️ `bd_criador.py` é **legado/morto** — não executar (schema real em `bd_manipulador.py`).

Modelos tipados: `models/__init__.py` com dataclasses `Unidade` (`id`, `nome`, `tipo`, `parent_id`, `ordem`, `telefone`, `ativo`) e `Contato` (`id`, `unidade_id`, `nome`, `telefone`, `user_nome`, `tipo`) espelhando `tb_unidade`/`tb_contato` (sem `map_imperatively`; acesso ao banco segue via `banco_conexao.conexao("lista_telefonica")` + SQL direto no `bd_manipulador`).

### Árvore recursiva, com teto de profundidade

`listar_arvore_contatos(raiz_id=None, termo="")` (`bd_manipulador.py:836`) monta a árvore com a função interna `montar(u, prof)`, **recursiva e sem limite de negócio**: a estrutura é `parent_id`, então aceitar mais de 3 níveis é natural. A profundidade entra no dict como `nivel` (0 na raiz).

A única trava é o **teto `_PROFUNDIDADE_MAXIMA = 20`** (`bd_manipulador.py:833`), que não é limite de organograma: é proteção contra **ciclo acidental de `parent_id`** (o dado é editável na tela). Ao estourar, loga `warning "…profundidade %s excedeu o teto na unidade %s - suspeita de ciclo em parent_id"` e devolve o nó com `filhos: []`, sem interromper a listagem.

!!! note "`tipo` continua restrito a 3 valores no banco"
    `CHECK(tipo IN ('secretaria','setor','subsetor'))` e a validação em
    `criar_unidade`/`mover_unidade`/`elevar_rebaixar` seguem como estão: a
    recursão da **leitura** aceita qualquer profundidade, mas **não se cria**
    um quarto tipo pela tela.

## Telefones — DDI +55 via `mod_intranet.telefone`

Telefones são gravados como texto livre (validação mínima: ≥8 caracteres) e normalizados só na exibição/ligação via `mod_intranet.telefone`:

- Leitura do `tel:`: `_tel_limpo(telefone)` (`telas.py:166`) — `obter_ddi(tel)` + `normalizar_telefone(ddi, tel)`, com fallback `re.sub(r"[^0-9+]", "", tel or "")`; preserva o `+` e os dígitos, então o `tel:` sai sanitizado.
- Exibição: `_tel_exibicao(telefone)` (`telas.py:181`) — ver a seção seguinte.
- Escrita/admin: `_campo_telefone(rotulo, prefixo_testid, valor="")` (`telas.py:306`) encapsula `mod_intranet.telefone.criar_campo_telefone(rotulo=…, valor=…, testid_ddi=…, testid_numero=…)` (seletor de DDI + campo numérico) e cai para `ui.input` simples se o helper falhar. Na tela: prefixos `lista-novo-contato`, `lista-editar-contato`, `lista-nova-unidade`, `lista-editar-unidade` (cada um gera `-ddi` e `-numero`).

### O `+55` some do cartão (decisão de espaço)

`_tel_exibicao` monta o número **a partir dos dígitos** e **tira o `+55`** de propósito:

| Entrada | Exibido no cartão |
|:---|:---|
| `+553535915101` | `(00) 3591-5101` |
| `0035915101` | `(00) 3591-5101` |
| `35915104` | `35915104` (sem separadores, abaixo de 10 dígitos) |

Dois motivos, ambos documentados no próprio código:

1. **Espaço na coluna estreita** — no cartão de ~216px da grade de 3 colunas, o prefixo empurrava o telefone para duas linhas e cortava o nome do contato.
2. **Consistência** — a formatação é feita aqui pelos dígitos, em vez de chamar `telefone.formatar_para_exibicao`: aquela devolve o que já está gravado e, num número parcial, devolve sem separadores — daí o resultado inconsistente entre `(00) 3591-5101` e `35915104` lado a lado.

O link `tel:` **não** é afetado: `_tel_limpo` continua montando o número completo (com `+55` quando gravado), e o nome do cartão é o que recebe o `ui.link(target=f"tel:{limpo}")`.

## Telefone múltiplo por usuário (`mod_gest_cad_usuario`)

O cadastro de usuários ganhou telefone **múltiplo**, o **consentimento** de qual deles pode sair no diretório, e os **dados funcionais públicos** que a lista telefônica exibe:

| Onde | O que |
|:---|:---|
| `mod_gest_cad_usuario/bd_manipulador.py:250-262` | `tb_telefone_usuario` — `id` PK, `user_nome` FK CASCADE → `tb_usuarios.user_nome`, `numero`, **`papel`** (`empresa`\|`pessoal`, default `empresa`), **`tipo`** (`celular`\|`fixo`, default `celular`), **`principal`** (0/1, um por usuário), **`visivel`** (0/1, default 0 — o consentimento), **`recado`** (0/1, default 0 — o número é o do setor) e `data_cadastro` |
| `mod_gest_cad_usuario/bd_manipulador.py:271-273` e `:280-282` | Colunas `visivel` e `recado` adicionadas por `ALTER TABLE … ADD COLUMN`, guardadas por `PRAGMA table_info` (idempotente, inclusive em banco já existente) |
| `mod_gest_cad_usuario/bd_manipulador.py:291-307` | `tb_usuarios` ganhou `unidade`, `lotacao`, `cargo`, **`telefone_pendente`**, **`acesso_provisorio`** e **`provisorio_ate`**, também por `ALTER TABLE` guardado |
| `mod_gest_cad_usuario/bd_manipulador.py:615` | `telefone_e_publicavel(papel, tipo, visivel)` — a regra de publicação (tabela abaixo) |
| `mod_gest_cad_usuario/bd_manipulador.py:641` | `telefone_de_recado(numero, papel, tipo)` — este telefone é o do setor? |
| `mod_gest_cad_usuario/bd_manipulador.py:654` | `telefone_e_recado(user_nome)` — o número que o cartão mostra é recado? |
| `mod_gest_cad_usuario/bd_manipulador.py:672` | `telefones_de_recado_em_lote(user_nomes)` — `dict` `{user_nome: True}` em **uma** consulta (ver *Desempenho* abaixo) |
| `mod_gest_cad_usuario/bd_manipulador.py:707` | `listar_telefones(user_nome, apenas_empresa=False)` — **9 campos**: `(id, user_nome, numero, papel, tipo, principal, visivel, **recado**, data_cadastro)`. Com `apenas_empresa=True` devolve **só os publicáveis** |
| `mod_gest_cad_usuario/bd_manipulador.py:738` | `telefone_empresa_principal(user_nome)` — o marcado `principal`, ou o primeiro publicável; `None` quando não há número liberado |
| `mod_gest_cad_usuario/bd_manipulador.py:752` | `telefones_publicaveis_em_lote(user_nomes)` — `dict` `{user_nome: numero}` em **uma** consulta (ver *Desempenho* abaixo) |
| `mod_gest_cad_usuario/bd_manipulador.py:795` | `adicionar_telefone(ator, user_nome, numero, papel, tipo, principal, visivel=None)` — `principal=True` desmarca os outros, para só haver um principal por vez; normaliza o número |

`matricula` **não** é coluna nova: o próprio `user_nome` **é** a matrícula (é o que o cartão mostra como `@user_nome`).

### A regra de consentimento — `telefone_e_publicavel`

> **EN:** `telefone_e_publicavel(papel, tipo, visivel)` decides whether a phone
> number may appear in the public directory. The institutional landline is
> always publishable; the company mobile needs the server's own consent; a
> personal number is never publishable, even when marked visible.
>
> **PT-BR:** `telefone_e_publicavel(papel, tipo, visivel)` decide se um telefone
> pode sair na lista telefônica. O fixo institucional publica sempre; o celular
> da prefeitura exige o consentimento do próprio servidor; um número pessoal
> nunca publica, mesmo marcado como visível.

| Telefone | Publica na lista? | Por quê |
|:---|:---:|:---|
| **Fixo da prefeitura** (`papel='empresa'`, `tipo='fixo'`) | **SEMPRE** | É a linha institucional, o número que a prefeitura divulga em visita de rotina e em edital. Linha institucional existe para ser achada; guardá-la a torna inútil para o fim a que serve |
| **Celular da prefeitura** (`papel='empresa'`, `tipo='celular'`) | **só se o servidor marcar** `visivel` | Quem atende é a pessoa, no próprio número, a qualquer hora. O responsável pela defesa civil precisa aparecer para todos; o prefeito, não. É consentimento, não configuração do sistema |
| **Celular particular** (`papel='pessoal'`, `tipo='celular'`) | **NUNCA** | O prefeito pode não querer o número publicado — e o consentimento dado para um número não alcança o outro |
| **Residencial** (`papel='pessoal'`, `tipo='fixo'`) | **NUNCA** | Telefone de casa não entra em cadastro de servidor |

A implementação tem exatamente três linhas: `papel='pessoal'` ⇒ `False`; `tipo='fixo'` ⇒ `True`; senão ⇒ `bool(visivel)`.

!!! warning "`papel`/`tipo` corrompidos caem no lado **seguro**"
    `_validar_papel` devolve `empresa` para um papel desconhecido e
    `_validar_tipo` devolve `celular` para um tipo desconhecido
    (`bd_manipulador.py:567-581`). A combinação resultante é
    `empresa`/`celular` — que **exige consentimento explícito**. Um dado
    corrompido nunca vira publicação automática; o pior caso é o telefone
    não aparecer, e não o número particular vazar.

!!! note "`apenas_empresa=True` filtra por `telefone_e_publicavel`, não por `papel='empresa'`"
    `listar_telefones` (`bd_manipulador.py:610`) filtra em **Python**, chamando
    `telefone_e_publicavel`, e não em `SQL WHERE papel='empresa'`. As duas
    coisas não são equivalentes: `papel='empresa'` + `tipo='celular'` +
    `visivel=0` passaria pelo `WHERE` e **não** pode aparecer. Filtrar em
    Python também evita a divergência entre backends (SQLite/PostgreSQL)
    caso a regra precise de uma expressão que o proxy não sabe traduzir.

### Desempenho — `telefones_publicaveis_em_lote` (27/09/2026)

> **EN:** `telefone_empresa_principal` opened one connection per row. With the
> real staff sheet that froze the directory screen, so
> `telefones_publicaveis_em_lote(user_nomes)` resolves every publicable number
> in a **single** query with an `IN` list of placeholders.
>
> **PT-BR:** `telefone_empresa_principal` abria uma conexão por linha. Com a
> folha real de servidores isso travava a tela do diretório, então
> `telefones_publicaveis_em_lote(user_nomes)` resolve todos os números
> publicáveis em **uma** consulta, com um `IN` de placeholders.

Com 60 usuários de demonstração ninguém notava; com a folha real (mais de mil servidores) a tela "carregando" nunca terminava. O sintoma era a tela, não o banco: 1.165 aberturas de conexão para montar a mesma lista. A correção é uma função só:

| Antes | Depois |
|:---|:---|
| `telefone_empresa_principal(user_nome)` por pessoa | `telefones_publicaveis_em_lote(user_nomes)` — **1** consulta, `IN (…)` de placeholders |

O mesmo desenho vale para a marca de recado: `telefones_de_recado_em_lote(user_nomes)`
(`bd_manipulador.py:672`) resolve todos os recados em **uma** consulta, e a lista
telefônica a consome **indiretamente**, por `integracoes.telefones_de_recado_para_lista()`,
**uma vez por desenho da tela** (`telas.py:564-579`) — nunca uma por cartão.

O `IN` é portátil: o proxy `banco_conexao` traduz os placeholders para o PostgreSQL, e os valores vão **sempre** por parâmetro — não há concatenação de texto. Quem usa a função é `leitura_lista.listar_para_lista_telefonica()` (`mod_gest_cad_usuario/leitura_lista.py:159`), que monta o dicionário **sem** passar por `_para_dict` — `_para_dict` chama `telefone_empresa_principal`, que abre uma conexão por linha, e o resultado seria jogado fora logo em seguida, substituído pelo telefone do lote. Medido com a folha real: **6,019 s → 0,050 s** para mais de mil servidores (120×). Quem não liberou número **não aparece no dicionário** — que é o mesmo significado de "sem telefone" que o resto do sistema já usa.

### Ponte de leitura — `mod_gest_cad_usuario/leitura_lista.py`

Arquivo próprio, **fora** de `bd_manipulador.py`, com duas razões concretas registradas no código:

1. **Não quebra quem já consome** — `obter_usuario` e `listar_usuarios` devolvem tuplas de **tamanho fixo**, lidas **por índice** em vários pontos do sistema. Acrescentar as colunas novas a essas tuplas mudaria a forma do retorno. A ponte devolve **dicionário**, que não tem posição fixa.
2. **A ponte entre os dois módulos é pequena e óbvia** — tudo que a lista telefônica precisa saber de um servidor está nesta página.

| Função | O que devolve |
|:---|:---|
| `nome_para_exibicao(nome_completo)` | Primeiro + último nome: `"Ana Beatriz Souza Rocha"` → `"Ana Rocha"`. A lista é um diretório, não um prontuário; o nome inteiro fica no cadastro |
| `obter_usuario_para_lista(user_nome)` | `user_nome`, `nome_completo`, `nome_exibicao`, `cargo`, `unidade`, `lotacao`, `ativo`, `telefone` (o **publicável** marcado como principal, ou o primeiro) — ou `None` |
| `buscar_usuarios_para_lista(termo="", limite=50)` | Filtra por nome (com/sem acento), matrícula, cargo, unidade e lotação; **só ativo e não excluído**; ordenado por nome de exibição |
| `listar_para_vinculo(limite=20)` | Ativos, para a lista de escolha do diálogo de vínculo |
| `listar_para_lista_telefonica()` | **Todos** os ativos e não excluídos, com o telefone publicável **e** a marca `recado` vindos do **lote** (duas consultas: `telefones_publicaveis_em_lote` + `telefones_de_recado_em_lote`) — é esta função que alimenta `sincronizar_contatos_do_cadastro` e `telefones_de_recado_para_lista` |

!!! info "A ponte não importa outro módulo — e agora é consumida **pelo núcleo**"
    A normalização (`_norm`, duas linhas) fica **local**, de propósito: o banco
    de usuários é do `mod_gest_cad_usuario` e não pode depender do
    organograma (regra de isolamento do AGENTS.md §2); a função é curta; e o
    outro módulo pode mudar a sua sem quebrar este. O único import é
    `mod_gest_cad_usuario.bd_manipulador` (o **próprio** banco do módulo).

    Desde 27/09/2026 a ponte **é** consumida — mas **não pela lista
    telefônica**. Quem a chama é `mod_intranet/integracoes.py` (o núcleo), e
    o resultado é entregue à lista por parâmetro. A lista telefônica
    continua sem **importar** nada do módulo de cadastro; ver a seção
    "Espelhamento do cadastro no diretório" abaixo.

O telefone **particular** (`papel='pessoal'`) existe no cadastro mas **não sai**
da ponte — é a diferença entre o que a prefeitura publica e o que é do servidor.

### "deixe recado" no cartão — a marca que vem pelo núcleo (27/09/2026)

> **EN:** A server with no own line gives the **sector's** number. The card
> writes **"deixe recado"** in a line **below** the number, not as a suffix —
> the suffix does not fit in the ~216px column of the 3-column grid. The mark
> reaches the directory through the core, like the mirroring does.
>
> **PT-BR:** Quem não tem linha própria dá o telefone do **setor**. O cartão
> escreve **"deixe recado"** numa linha **abaixo** do número, e não como
> sufixo — o sufixo não caberia na coluna de ~216px da grade de 3 colunas. A
> marca chega ao diretório pelo núcleo, como o espelhamento.

| Onde | O quê |
|:---|:---|
| `mod_lista_telefonica/telas.py:167-180` | `_contato_e_recado(user_nome)` — o número **deste** contato é do setor? Lê só o `_cache_recado`; `user_nome` vazio (contato digitado à mão) cai em `False` **sem tocar o banco** |
| `mod_lista_telefonica/telas.py:564-579` | O cache: **uma** consulta por desenho da tela, dentro de `_carregar_arvore` (`global _cache_recado` → `integracoes.telefones_de_recado_para_lista()`), com `log.warning` e cache vazio em qualquer falha |
| `mod_lista_telefonica/telas.py:41` | `ALTURA_CARTAO = "5.9rem"` — altura fixa dos três cartões da grade |
| `mod_lista_telefonica/telas.py:889-895` | A linha do "deixe recado": `text-caption text-grey-5 italic truncate`, `data-testid=lista-contato-recado`, **dentro** da mesma coluna do telefone |
| `mod_intranet/integracoes.py:156` | `telefones_de_recado_para_lista()` — a **9ª** função da fachada: `{user_nome: True}` para quem tem `recado` |

!!! note "Por que **linha separada** e não sufixo"
    Escrever `(00) 3591-5150 (deixe recado)` faria o texto não caber na coluna
    de ~216px e **empurraria o nome** do contato — que é a primeira linha do
    cartão, a única que tem a largura toda. O número é o do **setor**, e quem
    liga precisa saber que não vai falar com a pessoa; numa linha abaixo isso é
    dito **sem custar largura ao nome**. É a mesma decisão de espaço que tirou o
    `+55` do cartão.

!!! warning "`_cache_recado` é uma global de módulo sem valor inicial no topo do arquivo"
    Ela é atribuída **dentro** de `_carregar_arvore` (`global _cache_recado`,
    `telas.py:564`), e `_contato_e_recado` (`:167`) a lê. Ou seja: o nome só
    passa a existir depois do **primeiro** desenho da árvore — até lá a
    ordem normal (a árvore vem antes dos cartões). A guarda
    `if cache is None: return False` (`:178`) cobre o cache vazio por falha, **não**
    a ausência do nome. Não quebra o desenho real; é uma dependência de
    ordem que vale conhecer antes de mexer na ordem das chamadas.

!!! note "A lista telefônica **não abre o banco do cadastro**"
    É a regra do AGENTS.md §2, e `assets/test/check_integridade.py` reprova o
    import direto. A marca vem pela **costura do núcleo**
    (`mod_intranet/integracoes.telefones_de_recado_para_lista()`), que lê
    `leitura_lista.listar_para_lista_telefonica()` e devolve só o dicionário. A
    chave é a **matrícula** (`user_nome`), que é exatamente o que
    `tb_contato.user_nome` guarda — é por isso que a consulta bate em cheio e o
    cartão resolve sem ir ao banco durante o desenho.

## Espelhamento do cadastro no diretório (27/09/2026)

> **EN:** The phone directory reads its own `tb_contato` table and **must not
> open the user register database** — that is AGENTS.md §2, and
> `assets/test/check_integridade.py` fails the build on a direct import. The
> seam is the core: `mod_intranet/integracoes.espelhar_cadastro_na_lista_telefonica(ator)`
> reads the register and hands the finished list to the directory.
>
> **PT-BR:** A lista telefônica lê a própria tabela `tb_contato` e **não pode
> abrir o banco do cadastro de usuários** — é a regra do AGENTS.md §2, e
> `assets/test/check_integridade.py` reprova o import direto. A costura é o
> núcleo: `mod_intranet/integracoes.espelhar_cadastro_na_lista_telefonica(ator)`
> lê o cadastro e entrega a lista pronta ao diretório.

### Por que a lista **não** tem acesso direto ao cadastro de usuários

Cada módulo é dono de **um** banco e não faz consulta cruzada (AGENTS.md §2). A allowlist de negócio→negócio do `assets/test/check_integridade.py` é minúscula: só a **cascata LGPD** (`mod_gest_cad_usuario` → `mod_blog`, `mod_edit_pdf`, `mod_renomear_empenho`). Um `import mod_gest_cad_usuario` dentro de `mod_lista_telefonica` reprova essa verificação — e está correto reprovar.

A solução é separar **quem lê** de **quem escreve**:

```
leitura_lista.listar_para_lista_telefonica()      # mod_gest_cad_usuario lê o SEU banco
        │
        ▼
mod_intranet.integracoes
        .espelhar_cadastro_na_lista_telefonica(ator)   # NÚCLEO: a costura autorizada
        │        (a lista chega pronta, por parâmetro)
        ▼
mod_lista_telefonica.bd_manipulador
        .sincronizar_contatos_do_cadastro(contatos, ator)   # grava no SEU banco
```

O núcleo é o único lugar do sistema autorizado a conhecer os dois de perto: ele tem o banco do cadastro (para ler) e o banco do diretório (para gravar), e cada lado do espelhamento toca **só o banco dele**. É a regra do AGENTS.md §2 atravessada por um parâmetro, em vez de atravessada por uma consulta.

### O diretório espelha **TODOS** os servidores, não só quem autorizou telefone (28/09/2026)

> **EN:** The directory now mirrors **every registered server**, not only the
> ones who released a phone number. Previously an empty phone was a `continue`
> and the person was **not written at all**, so a populated staff register with
> nobody authorised produced a directory with **zero contacts** and searching a
> name found nobody. The **consent rule is intact**: whoever did not authorise
> keeps an **empty phone**, and the card says "sem número informado". What
> enters without authorisation is the **post** (name, job, secretariat,
> allocation, link, status) — which is legal publication. The **number** is
> what the consent protects.

Esta é a mudança de comportamento mais importante do módulo, e a distinção
abaixo é o que permite a lista ser útil sem virar vazamento:

| Dado | Entra sem autorização? | Por quê |
|:---|:---:|:---|
| Nome, nome completo | **sim** | identificação da pessoa |
| **Cargo** | **sim** | é o que se procura primeiro numa pessoa |
| **Secretaria / lotação** | **sim** | organograma é informação pública |
| **Vínculo** e **situação** | **sim** | efetivo/estágio, ativo/férias/demitido — objetivo, da folha |
| Matrícula (`@login`) | **sim** | identificação funcional |
| **Telefone** | **NÃO** | é exatamente o que o consentimento protege |

Publicação de cargo, lotação, vínculo e situação é a informação que a lei
obriga os órgãos públicos a disponibilizar sobre seus servidores (Lei
12.527/2011, acesso à informação). O **número de telefone particular ou do
celular corporativo** não está nessa lista: ele entra **só** com autorização
marcada em `tb_telefone_usuario.visivel`, avaliada por
`mod_gest_cad_usuario.telefone_e_publicavel`.

!!! note "`sem número informado` é diferente de telefone vazio"
    Na leitura, telefone vazio parece cadastro quebrado. A tela escreve
    literalmente **"sem número informado"** (`telas.py:983`, `data-testid=
    lista-contato-sem-numero`) para que o servidor entenda que a pessoa
    **escolheu** não publicar, e não que o cadastro dela quebrou.

#### `vinculo` e `situacao` chegaram ao cadastro como dado objetivo (28/09/2026)

`tb_usuarios` ganhou **`vinculo`** e **`situacao`**, gravados pela carga da
folha por `definir_vinculo` — pela **mesma regra da remuneração**: são
**objetivos**, a folha é a fonte, e não se pergunta a ninguém. Sem eles, a
busca da lista telefônica não conseguia responder "é efetivo?" nem "está
ativo?" de quem não autorizou telefone, e a pessoa **desaparecia da busca** —
o oposto do que um diretório precisa fazer.

Resultado real medido em 28/09/2026 sobre a folha de 1.165 servidores:

| Dimensão | Contagem |
|:---|:---|
| Servidores gravados no diretório | **1.165** |
| Efetivos | **542** |
| Contrato determinado | **398** |
| Estagiários | **124** |
| Ativos | **1.054** |
| De férias | **73** |
| Demitidos | **19** |

#### A busca casa com oito campos

`buscar_contatos` e `listar_arvore_contatos` comparam o termo — normalizado
sem acento, comparação por **substring** — contra **nome, telefone, login
(matrícula), cargo, lotação, vínculo e situação**, além do nome completo
(`bd_manipulador.py:875`). A comparação é por substring em Python, não em SQL,
para ser idêntica em SQLite e PostgreSQL e não depender de `LIKE` com acento.

Os três `ui.select` em cascata (`lista-cascata-1/2/3`) continuam o recorte
por organograma; a busca por texto é o **caminho para o que o teto não cabe**
(§ abaixo).

### Teto de desenho: 240 cartões por vez, com aviso explícito

> **EN:** The screen draws **at most 240 cards at a time**, with an explicit
> notice ("Mostrando 240 de N servidores"). One thousand cards is roughly six
> thousand DOM elements and the browser went past 90 seconds **without
> painting**; the backend answers in **0.15 s**. The cost is the **DOM**, not
> the query.

`LIMITE_CONTATOS_TELA = 240` (`telas.py:60`) com a aplicação em
`_limitar_contatos` (`telas.py:1266`) e o aviso em `_aviso_pagina`
(`telas.py:1298`, `data-testid=lista-aviso-limite`).

O número não é vaidade: é o que **cabe com folga em uma página** e ainda mostra
o organograma inteiro com uma parte boa de cada secretaria. Abaixo disso a
lista vira uma parede; acima disso a tela demora.

!!! warning "O aviso é obrigatório, e o laço tem de esvaziar as unidades de fora"
    Duas armadilhas já encontradas e corrigidas:

    1. **Silenciar o corte seria o erro**: a pessoa veria 240 servidores e
       concluiria que a instituição tem 240. O número inteiro é o que
       transforma "lista truncada" em "tem mais, e aqui está o caminho" — por
       isso o aviso diz **quantos** de **quantos**, e manda para a busca ou
       para o filtro de secretaria.
    2. **O laço é `while pilha` e NÃO `while pilha and restante > 0`.** Com a
       segunda forma, quando o teto era atingido o laço parava e deixava os
       contatos das unidades seguintes intactos: **953 de 1.084 cartões** no
       desenho, e a página continuava travando. Percorrer até esvaziar é o
       que faz o teto valer.

    A unidade que ficou sem contato **continua na árvore**: uma secretaria
    vazia ainda é informação — o diretório mostra que existe, mesmo sem quem
    cuide dela.

#### Por que aumentar o teto **não** é a solução

O backend responde em **0,15 s** com o recorte inteiro. Os 90 s sem pintar são
**decrebimento e layout de ~6.000 elementos de DOM** no navegador, não consulta.
Aumentar o teto de 240 para 1.000 não deixa a tela "mais completa": deixa a
tela **travada por mais tempo**, e o usuário não chega nem a ler o começo. A
solução para ver o resto **já está na tela** — a busca por nome, cargo ou
secretaria, que reduz o recorte antes de desenhar, e os três selects de
organograma.

### O que `sincronizar_contatos_do_cadastro(contatos, ator="sistema")` faz

> **EN:** Mirrors registered servers into the directory — **all of them, since
> 28/09/2026**, with or without a released phone number. It creates a
> `vinculado` contact pointing at the matrícula, matches the unit by **lotação**
> and then by **secretaria** (accent-insensitive, active units only), **updates
> the phone and the functional data together** of an existing contact, and
> **never touches** an `externo` contact. Idempotent.
>
> **PT-BR:** Espelha no diretório os servidores cadastrados. Cria um contato do
> tipo `vinculado` apontando para a matrícula, casa a unidade pela **lotação** e
> depois pela **secretaria** (comparação sem acento, só entre unidades **ativas**),
> **só atualiza o telefone** de contato já existente e **nunca toca** em contato
> do tipo `externo`. É idempotente.

`contatos` é a lista de dicionários com `user_nome`, `nome_exibicao`, `telefone`, `unidade` e `lotacao`. Devolve o resumo `{criados, atualizados, sem_unidade, sem_telefone, ja_iguais}`; em qualquer falha devolve o mesmo formato com `erro=True` e zeros — uma falha aqui nunca pode derrubar a tela.

| Regra | O que faz | Por quê |
|:---|:---|:---|
| **Cria `vinculado`** | `criar_contato(unid, nome_exibicao, telefone, user_nome=…)` — o nome é primeiro + último, o telefone é o **publicável** | O particular nunca chega aqui: quem busca já devolveu só os liberados |
| **Casa a unidade pela lotação** | Tenta o **departamento** (`lotacao`) primeiro | A lotação é a informação mais específica do servidor |
| **Cai para a secretaria** | Se não achar por lotação, tenta `unidade` | 124 servidores estão ligados direto na secretaria, sem departamento; sem o fallback eles ficariam sem casa |
| **Só entre unidades ativas** | O dicionário de casamento só recebe `tb_unidade` com `ativo=1` | As unidades de demonstração foram desativadas; casar com elas esconderia o servidor num lugar morto |
| **Comparação sem acento** | `bd_manipulador._norm` (NFKD, sem acento, sem pontuação) | A folha de servidores vem em caixa alta e sem acento; casar sem normalizar não acha |
| **Só atualiza o telefone** | `editar_contato(existente[0], telefone=…, ator=…)` — nome e unidade **ficam** | Um servidor transferido de setor é caso do RH; mudar isso atrás das costas do administrador apagaria um ajuste manual |
| **Nunca toca em `externo`** | A lista de "já existentes" só monta `por_user` com `tipo == 'vinculado'` | Empresa fornecedora e visitante são da prefeitura, não do cadastro de servidores |
| **Idempotente** | Já vinculado + telefone igual ⇒ conta `ja_iguais`, não escreve | Rodar mil vezes não cria mil contatos |

!!! note "O espelhamento não é uma tela de importação"
    Não há menu, botão de "importar" nem etapa de usuário. O espelhamento
    acontece sozinho (§ *Reespelhamento automático* abaixo) e o botão
    "Sincronizar cadastro" é apenas o atalho do administrador. A fonte dos
    dados é o próprio cadastro de usuários, que o servidor mantém.

### `tb_sincronizacao` — saber se o diretório está velho

Uma linha, `id = 1`, com `ultima_em`, `total_criados` e `total_atualizados` (`bd_manipulador.py:242-250`). A linha é criada com `INSERT OR IGNORE` no `init_db`, então o carimbo existe (vazio) desde o banco novo.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `INTERVALO_REFRESH_MIN = 15` | `bd_manipulador.py:1105` | Minutos que o diretório pode ficar velho antes de a tela reespelhar sozinha. Longo o bastante para não reler o cadastro a cada F5 de quem está digitando a busca; curto o bastante para que o número informado no primeiro acesso apareça no mesmo dia |
| `_carregar_sincronizacao(criados, atualizados)` | `bd_manipulador.py:1108` | Grava o carimbo (`UPDATE … WHERE id=1`) ao final de cada espelhamento. Nunca levanta exceção |
| `sincronizacao_desatualizada()` | `bd_manipulador.py:1125` | `True` quando o diretório está velho, **e também quando nunca houve sincronização** (banco recém-criado tem o carimbo zerado — nesse caso o diretório está literalmente vazio) |

O carimbo é gravado pelo **Python** (`datetime.now()`), e não por `CURRENT_TIMESTAMP` do banco. Motivo: o SQLite grava `CURRENT_TIMESTAMP` em **UTC** e a comparação é feita em hora **local** — três horas de diferença num servidor brasileiro, o que fazia a idade sair **negativa** e a tela nunca mais notar que o diretário tinha envelhecido. A sincronização automática ficaria desligada para sempre, sem erro nenhum. A leitura corta a string em 19 caracteres antes do `datetime.strptime(..., "%Y-%m-%d %H:%M:%S")`, porque o banco pode devolver `2026-09-27 19:40:00` no SQLite e ISO com `T` no PostgreSQL via proxy — os 19 primeiros caracteres pegam a parte `YYYY-MM-DD HH:MM:SS` nos dois. Carimbo no **futuro** é tratado como desatualizado (relógio fora de hora: reespelhar é barato), e carimbo ilegível também.

### Reespelhamento automático, silencioso

Na tela (`mod_lista_telefonica/telas.py:1217-1222`):

```python
if lista.sincronizacao_desatualizada():
    ui.timer(0.4, _auto_sincronizar)
```

`_auto_sincronizar` (`telas.py:662`) é `async` e roda a espelhamento em `run.io_bound` (fora do event-loop, AGENTS.md §5.1), com a trava de reentrância `_sincronizando`. É **silencioso de propósito**: quem abriu a tela não pediu nada e não precisa de um aviso de "3 contatos sincronizados". A diferença entre o diretório velho e o novo é que o contato simplesmente passa a estar lá. Um aviso barulhento a cada 15 min seria treinar o usuário a ignorar avisos — e o dia em que aparecer um importante, ele também ignoraria. Só quando houve `criados` ou `atualizados` é que o `log.info` registra e a cascata é repovoada.

O `ui.timer(0.4, …)` com atraso existe porque o desenho inicial acontece de qualquer forma: se a sincronização demorar, quem está vendo é a tela vazia por instantes, não a página pendurada.

### Botão "Sincronizar cadastro" (`lista-admin-sincronizar`)

Só o administrador vê, no cabeçalho do recorte, junto de "Novo contato" / "Nova unidade" / "Editar unidade" (`telas.py:605-608`). `_sincronizar_cadastro` (`telas.py:612`) é `async` + `run.io_bound` — a sincronização lê mais de mil usuários e escreve contatos, e um handler `sync` travaria o event-loop por segundos e derrubaria a conexão de quem está na mesma tela. O botão fica desabilitado durante a operação (trava `_sincronizando`) para não haver dois cliques pedindo a mesma coisa.

O resumo sai em `notificar(...)`, montado por partes:

| Resumo | Notificação |
|:---|:---|
| `criados` | `N contato(s) criado(s)` |
| `atualizados` | `N telefone(s) atualizado(s)` |
| `sem_telefone` | `N sem telefone liberado` |
| `sem_unidade` | `N sem unidade correspondente` |
| tudo zero | `nada mudou.` |

Depois disso, `_preencher_cascata(None)` + `render_organograma.refresh()`: a sincronização pode ter criado unidades novas, e um select com as opções antigas esconderia o resultado do clique que o usuário acabou de dar.

## Funcionalidades

### Busca em UM campo + cascata de selects + grade contínua (27/09/2026)

- **Um campo de busca só** (`lista-busca-termo`): `campo_busca("🔍 Buscar — nome, telefone ou unidade", …, tooltip="Um único campo: pesquisa nome, telefone e unidade ao mesmo tempo (sem acentos)")` com `debounce='150'`; a digitação chama `_ao_filtrar("busca", e)` → `render_organograma.refresh()`. O filtro é `impressao.filtrar_arvore(arvore, termo=estado["busca"])` → `_filtrar_termo`: o termo casa com o **nome do contato**, o **telefone** ou o **caminho da unidade** (secretaria > setor > subsetor), com `bd_manipulador._norm` (sem acento, sem pontuação — é ela que faz `ti` achar `T.I.`). A comparação entre os três é **OU**, não E: quem digita `Saúde` quer os servidores da Saúde, e quem digita `3591` quer os telefones, não a interseção dos dois. A unidade continua na árvore mesmo sem contato casado, para o diretório não "pular" a secretaria e deixar o usuário sem contexto de onde o contato veio. O card da busca mantém `data-testid=lista-busca` com `role="search"` (é o **invólucro**, não o campo) e fica **fora** do `refreshable` de propósito — os campos precisam manter foco e valor enquanto a lista é redesenhada a cada tecla. Botão **Limpar** (`lista-limpar-busca`) zera o termo, os três níveis e todos os selects. Ele repopula o **primeiro** select com `_opcoes_nivel(0, _carregar_arvore())` (`telas.py:424`) — o **mesmo** nível da carga inicial, que é o das raízes. (Houve aqui um bug corrigido em 27/09/2026: o botão usava `_opcoes_nivel(1)`, isto é, os **filhos** das raízes, e depois de limpar o primeiro select listava os setores no lugar das secretarias.)
- **Três selects em cascata** (`lista-cascata-1/2/3`, rótulos **Unidade** / **Subunidade** / **Sub-subunidade**), no mesmo card da busca: `ui.select({}, label=rotulo, with_input=True).props("outlined dense clearable")`. Escolher a unidade popula o select seguinte com os **filhos** dela (`_preencher_cascata` → `_caminho_do_id` + `no["filhos"]`); o select que não tem o que mostrar fica **vazio e desabilitado** (`sel.disable()`), que é a informação honesta ("aqui embaixo não tem mais nada"). `_preencher_cascata(None)` roda **antes** do primeiro desenho — sem isso o primeiro select nascia vazio e desligado e só ganhava as unidades depois que o usuário mexesse em algum campo. O **recorte** da listagem vem do nível mais fundo escolhido: `for chave in ("nivel_3", "nivel_2", "nivel_1")` e, no primeiro não-`None`, `_recortar(recorte, estado[chave])` devolve a subárvore (que já traz os descendentes).
- **Estado da tela** (`telas.py:380`): `{"unidade": None, "busca": "", "nivel_1": None, "nivel_2": None, "nivel_3": None}`. `unidade` é o recorte herdado do diálogo de novo contato (`_dlg_novo_contato` grava `estado["unidade"] = sel_unidade.value` ao salvar, para o contato criado já aparecer).
- **Grade de contatos — UMA grade contínua** (`CSS_GRADE`, `telas.py:39`): `display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; align-items: stretch;`. **Não existe mais uma grade por unidade**: como quase toda unidade tem um contato só, a grade de 3 colunas nunca aparecia e o resultado era uma coluna de cartões, um por unidade — o oposto do pedido. O `minmax` é de **200px** porque `3 × 200px + 2 × 12px = 624px`; com 260px eram necessárias 804px e num contentor de 673px (janela de 800px menos a margem) a grade caía em **duas** colunas. `ui.row()` não serve aqui (é flex e nunca quebra em colunas). `align-items: stretch` + **altura fixa** `ALTURA_CARTAO = "5.9rem"` são o que fazem todos os cartões terem o **mesmo** tamanho (3 linhas: nome+ações, telefone, matrícula/unidade).
- **Cartão de contato** (`_cartao_contato`, `telas.py:822`): `lista-cartao-contato`, `data-testid=lista-contato-<cid>`, `role="listitem"`, `aria-label="<nome> <caminho>"`. A estrutura é **coluna**, com os botões de ação só na **primeira** linha — como irmãos de uma coluna de texto eles espremiam a largura em todas as linhas, e num cartão de ~216px o telefone `(00) 3591-5101` quebrava no meio. Conteúdo: ícone do tipo (`person` vinculado / `badge` externo), nome como `ui.link(target=f"tel:{_tel_limpo(telefone)}")` com `truncate` e tooltip "Toque para ligar (celular)" (`ui.label` sem `tel:` quando o telefone está vazio), o telefone em `font-mono` na largura inteira — e, **logo abaixo dele e na mesma coluna**, o **"deixe recado"** (`text-caption text-grey-5 italic`, `data-testid=lista-contato-recado`) quando o contato é de recado — e na 3ª linha a matrícula (`@user_nome`, quando vinculada) e o **caminho da unidade** com `tooltip` — como a grade é uma só e os cartões fluem em 3+ colunas, sem este rótulo o diretório perderia a hierarquia. Ações: `lista-ligar` (sempre) e, para admin, `lista-contato-editar-<cid>` / `lista-contato-remover-<cid>`.
- **Unidade sem contato** não vira cartão: vira uma **faixa de seção** ocupando a linha toda (`grid-column: 1 / -1`, `lista-secao no-print`, ícone por `tipo`) — na tela informa que a unidade existe; no papel some, porque um título sozinho na folha impressa é só ruído. Só aparece **sem filtro ligado** (`elif not _tem_filtro()`).
- **Ordem alfabética**: garantida no banco (`listar_arvore_contatos` ordena com `casefold()` em Python, portátil SQLite↔PostgreSQL). A tela percorre a árvore como veio — sem `sorted()`.
- **Cabeçalho temático**: `ler_tema("lista_telefonica", cor_botao="#000000", cor_texto_botao="#FFFFFF", texto_header=TEXTO_HEADER)` + `ui.colors(primary=tema["cor_botao"])` + `cabecalho("Lista Telefônica", …, chave_modulo="lista_telefonica")` (borda = cor do módulo via `PADROES_TEMA["lista_telefonica"]` → `#000000`).
- **Responsividade**: `w-full p-6 gap-4`; o campo de busca e os três selects empilham no celular (`w-full sm:w-[320px]` / `sm:w-[210px]`, `min-width: 0`, `shrink-0`) e a `ui.row` usa `flex-wrap` com `style("gap: 0.75rem")` — nada usa `gap-*` em `ui.row()` (AGENTS.md §5).

### CRUD do administrador na própria tela (27/09/2026)

Quem passa em `_eh_admin(user_nome, perfil)` vê, no cabeçalho do recorte, **Novo contato** (`lista-admin-novo-contato`), **Nova unidade** (`lista-admin-nova-unidade`) e **Editar unidade** (`lista-admin-editar-unidade`, exige unidade selecionada) e, em cada cartão, **editar** (`lista-contato-editar-<cid>`) e **remover** (`lista-contato-remover-<cid>`).

| Ação | Diálogo (`dialogo_card`) | Chamada no `bd_manipulador` | Testids |
|:---|:---|:---|:---|
| Novo contato | unidade (opções `caminho (tipo)`), nome, telefone (DDI+numero) | `criar_contato(unidade_id, nome, telefone, ator=user_nome)` | `lista-novo-contato-unidade`, `lista-novo-contato-nome`, `lista-novo-contato-ddi`, `lista-novo-contato-numero`, `lista-novo-contato-salvar` |
| Editar contato | nome, telefone | `editar_contato(cid, nome=, telefone=, ator=)` | `lista-editar-contato-nome`, `lista-editar-contato-ddi`, `lista-editar-contato-numero`, `lista-editar-contato-salvar` |
| Remover contato | confirmação ("A remoção não pode ser desfeita") | `excluir_contato(cid, ator=)` | `lista-remover-contato-confirmar` |
| Nova unidade | nome, tipo (secretaria/setor/subsetor), pai (acompanha o tipo), telefone | `criar_unidade(nome, tipo, pai, telefone, ator=)` | `lista-nova-unidade-nome`, `lista-nova-unidade-tipo`, `lista-nova-unidade-pai`, `lista-nova-unidade-ddi`, `lista-nova-unidade-numero`, `lista-nova-unidade-salvar` |
| Editar unidade | nome, telefone | `editar_unidade(uid, nome=, telefone=, ator=)` | `lista-editar-unidade-nome`, `lista-editar-unidade-ddi`, `lista-editar-unidade-numero`, `lista-editar-unidade-salvar` |

⚠️ **A guarda é no servidor**: cada handler começa com `_guarda_admin(acao)`, que **rechama** `_eh_admin(user_nome, perfil_global)` (papel global + `eh_admin_do_modulo`) e, sem permissão, avisa e sai **sem escrever**. Esconder o botão não é proteção — o evento chega pelo socket. Todo sucesso fecha o diálogo, mostra `notificar(...)` e dá `render_organograma.refresh()` (a unidade nova aparece sem recarregar a página). O painel `/admin/lista_telefonica` continua existindo para mover/elevar/reordenar/excluir ramo/transferir.

### Impressão — PDF e impressora do usuário (27/09/2026)

Os dois caminhos partem do **recorte atual** (nível mais fundo da cascata) com o **termo único** da busca aplicado.

- **PDF para baixar** — `mod_lista_telefonica/impressao.py`:
  - `gerar_pdf_lista(destino, nos, titulo, rodape)` grava o PDF com **pymupdf** em **3 colunas por página** (A4 retrato 595.28×841.89 pt, margem 34pt, gap 13pt), com títulos de grupo (secretaria em caixa-alta negrito + fio, setor negrito, subsetor cinza, recuo por nível), contatos em ordem alfabética e telefone alinhado à direita; cabeçalho com título + data; rodapé com contagem, unidade e `Página X de Y` (desenhado depois de todas as páginas, quando o total já é conhecido). Fontes **embutidas** do pymupdf (`helv`/`hebo`) — **nada é baixado da internet**. Devolve `(True, caminho)` ou `(False, mensagem)`.
  - `pdf_bytes(nos, titulo, rodape)` devolve o mesmo layout em bytes (é o que o download usa — nenhum arquivo temporário em disco).
  - `registrar_rota_pdf()` (`impressao.py:619`) registra `GET /lista-telefonica/pdf?recorte=&termo=&nome=&telefone=&unidade=` (idempotente pela flag `_ROTA_REGISTRADA`; chamada na importação de `telas.py:160-163`, antes de qualquer clique). A rota revalida sessão viva + `usuario_existe` + `validar_acesso_modulo` (mesma guarda de `/solicita-impressao/pdf/{id}` no `main.py`), monta o PDF na requisição e responde `Response(content=…, media_type="application/pdf", headers={"Content-Disposition": "attachment; …"})` — `Response` e **não** `FileResponse`, porque o arquivo nasce em memória (passar bytes no primeiro argumento do `FileResponse` faria ele tentar `os.stat` no conteúdo). Sem resultado → `RedirectResponse("/lista-telefonica")`; sem sessão → `RedirectResponse("/login")`.
  - Na tela o botão é um `ui.link` (um `<a>` de verdade) com `data-testid=lista-pdf-baixar`: só uma requisição HTTP traz o arquivo para o disco do usuário — **sem JavaScript** nessa parte. O recorte enviado é o **mesmo da tela**: `nivel = estado.get("nivel_3") or estado.get("nivel_2") or estado.get("nivel_1")` e o termo de `estado["busca"]` (ler o estado antigo aqui gerava um PDF diferente do que a tela mostra).
- **Imprimir na impressora do usuário** — botão `lista-imprimir` → `ui.run_javascript("window.print()")` (**exceção intencional de "sem JS direto"**: não existe elemento NiceGUI para `window.print()`; mesmo motivo já registrado em `mod_intranet/telas.py` e no diálogo "Ligar agora"). O trabalho real é a folha `CSS_IMPRESSAO` (`telas.py:45`, `@media print`, via `ui.add_head_html`): esconde `header`/`footer`, menu, dialogs, tudo com prefixo `lista-busca` / `lista-limpar` / `lista-admin` / `lista-ligar` / `lista-imprimir` / `lista-pdf` (o `no-print` vai no *invólucro* dos campos — o testid cai no `<input>` nativo do Quasar e esconder só ele deixaria a caixa em branco impressa), as **faixas de seção** (unidades sem contato) e o subtítulo do cabeçalho; põe a grade em `repeat(3, 1fr)`, `break-inside: avoid` nos cartões, fundo branco e `@page { size: A4; margin: 10mm }`.
  - Detalhe de cascate: o fundo branco precisa de `body[class]` (e não só `body`), porque a classe `bg-grey-2` do Quasar/Tailwind é `!important` e tem especificidade maior que `body`.
  - A folha também tem o seletor `[data-testid^="lista-nav"]`, **herança sem elemento correspondente** desde que a navegação por botões saiu: inerte, mas inofensivo.

### Administração (`/admin/lista_telefonica`)

`telas_administracao.py:22` `mostrar_administracao(usuario_logado)` — `bloco_aparencia(usuario_logado, "lista_telefonica", tema, prefixo_auditoria="lista_telefonica", com_texto_header=True)` (`:33`) + 2 cards + `painel_backup` (`:984`).

**Card "Unidades — criar, mover, elevar/rebaixar, excluir ramo"** (`card_admin`, `account_tree`, `grade=False`, `:36`):

- **Criar** (`:41-51`): `Nome da unidade *` (`admin-unidade-nome`) + `Tipo` secretaria/setor/subsetor (`admin-unidade-tipo`) + `Unidade pai` (`admin-unidade-pai`, `clearable`) + `Telefone` (`admin-unidade-tel`); botão `Criar unidade` (`admin-criar-unidade`). `_montar_pai()` popula pai conforme o tipo (secretaria → desabilita; setor → secretarias; subsetor → todos setores com caminho `"Sec > Setor"`). `criar_unidade` valida nome ≥2, tipo, parent, duplicado no mesmo pai, ordem = `MAX(ordem)+1`; audita `criar_unidade`.
- **Listagem expansível** (`@ui.refreshable` `:130`): secretarias com `ui.expansion("Nome (tel)", icon="apartment")` + row de ações: `edit` (editar nome/tel), `delete_forever` (excluir ramo cascata, `text-red-8`), `drive_file_move` (mover), `vertical_align_top` (elevar), `swap_vert` (reordenar). Setores aninhados (`expansion business` com `ml-4`) + subsetores (`row ml-8 border-b`).
- **Excluir ramo (cascata)**: `dialogo_card` com `border-2 border-red-6` + aviso "e TODOS os filhos/contatos — não pode ser desfeita"; `excluir_ramo(uid)` coleta ids recursivos com `_coletar_ramo_ids` e `DELETE FROM tb_unidade WHERE id=?` (FK CASCADE apaga filhos/contatos); audita `excluir_ramo` com `ids`.
- **Mover**: valida tipo → novo pai; evita ciclo subindo `parent_id` até raiz; ordem final = `MAX+1`; `mover_unidade(uid, novo_parent_id)`.
- **Elevar/rebaixar**: `setor→secretaria` (parent NULL) ou `subsetor→setor` (parent = avô); `secretaria→setor` e `setor→subsetor` pedem `Mover`; `elevar_rebaixar(uid, novo_tipo)`.
- **Reordenar (comutar)**: lista irmãs (`listar_unidades(parent_id, tipo)`) com lista `ordem = [ids]` + botões `arrow_upward`/`arrow_downward` que comutam `ordem[i-1]↔ordem[i]` e re-renderizam; `Salvar ordem` → `reordenar_unidades(parent_id, ordem_ids)`.

**Card "Contatos — incluir via usuários ou externo, telefone, transferir"** (`contacts`, `grade=False`, `:640`):

- **Criar contato** (`:659-812`): `sel_unidade` (`admin-contato-unidade`, opções `caminho (tipo)`) + `Nome *`/`Telefone *` (`admin-contato-nome`/`admin-contato-tel`) + linha de vínculo à base de usuários: `inp_busca_user` (`ui.input "Buscar usuário na base"`, placeholder "digite nome, login ou e-mail", `admin-contato-busca`, `clearable`) + `sel_user` (`ui.select "Usuário encontrado (opcional)"`, `admin-contato-user`, `clearable`). `inp_busca_user.on_value_change(ao_buscar_user)` filtra **em tempo real** via a fachada `mod_intranet.integracoes.listar_usuarios_gestao()` por `login`/`nome_completo`/e-mail com `_norm`, **exclui deletados** (`not r[8]`), mostra **20 primeiros quando vazio** e **até 30 filtrados**; botão `Usar usuário` preenche `Nome` com `nome_completo` e `Telefone` com `user_fone` quando vazio, via `integracoes.obter_usuario_gestao(...)`. `criar_contato(unidade_id, nome, telefone, user_nome=…)` valida nome ≥2, tel ≥8, unidade existe, duplicado na unidade; tipo = `vinculado` se `user_nome` else `externo`; audita `criar_contato`.
- **Lista por unidade** (`@ui.refreshable` `:815`): `listar_contatos(uid)` alfabético + `@user` badge; por contato: `edit` (nome/tel), `swap_horiz` (transferir — `dialogo_card` com `sel_dest` de todas unidades → `transferir_contato(cid, nova_unidade)` com checagem de duplicado no destino), `delete` (excluir direto + `notificar` + `refresh`).

**Rodapé**: `painel_backup(usuario_logado, "lista_telefonica")` (`:984`, job `backup:lista_telefonica` 12h, `mod_intranet/rotinas.py:MAPA_BACKUPS`).

- **Versionamento**: `versao_modulo:lista_telefonica` no rodapé de `/lista-telefonica`.

## Permissões

| Ação | `comum` com `lista_telefonica` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/lista-telefonica` (busca em 1 campo + cascata de selects + grade) | ✓ | ✓ | ✗ (tela "Acesso restrito — Somente usuários com acesso à Lista Telefônica") |
| Baixar a lista em PDF (`GET /lista-telefonica/pdf`) | ✓ (mesma sessão + `validar_acesso_modulo`) | ✓ | ✗ (307 → `/login`) |
| Imprimir na impressora do usuário | ✓ | ✓ | — |
| Ver telefone / Ligar `tel:` | ✓ | ✓ | — |
| **Criar/editar/remover contato na própria tela** (27/09/2026) | ✗ | ✓ | ✗ |
| **Criar/editar unidade na própria tela** (27/09/2026) | ✗ | ✓ | ✗ |
| **Botão "Sincronizar cadastro"** (`lista-admin-sincronizar`, 27/09/2026) | ✗ (o botão nem é desenhado) | ✓ | ✗ |
| Criar/mover/elevar/excluir ramo (painel admin) | ✗ | ✓ | ✗ |
| Transferir contato entre unidades (painel admin) | ✗ | ✓ | ✗ |
| Reordenar / comutar (painel admin) | ✗ | ✓ | ✗ |
| Ver `/admin/lista_telefonica` | ✗ | ✓ | ✗ (redirect para `/lista-telefonica` + `ui.notify` "Acesso restrito a administradores") |

Gate: `_pode_ver(user, perfil)` (`telas.py:73`) — `administrador_geral` sempre; senão `autenticacao.validar_acesso_modulo(user, "lista_telefonica")`. Admin: `_eh_admin` (`:84`) — **reavaliado no servidor dentro de cada handler de escrita** (`_guarda_admin`, `:807`), não só para esconder o botão. A rota do PDF repete a validação de sessão + módulo. `/admin/lista_telefonica` revalida `eh_admin_do_modulo`.

LGPD: `remover_vinculos_usuario(user_nome)` (`bd_manipulador.py:1164`) remove `DELETE FROM tb_contato WHERE user_nome=?` (audita `remover_vinculos_lista`); `renomear_usuario` (`:1195`) propaga `UPDATE tb_contato SET user_nome/nome WHERE user_nome/nome`.

## Rota e integrações

- Rota: `/lista-telefonica` (chave `lista_telefonica`, ícone `call`) — `main.py` (`pagina_restrita("Lista Telefônica", chave_modulo="lista_telefonica")` + `REGISTRO_MODULOS["lista_telefonica"] = page_lista_telefonica`); slug customizável em `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Download do PDF: `GET /lista-telefonica/pdf` (27/09/2026) — registrada por `mod_lista_telefonica/impressao.py::registrar_rota_pdf()`, chamada na importação de `telas.py`; mesmo padrão de `mod_intranet/preview_estilos.py` (rota própria do módulo, sem mexer no `main.py`).
- Admin: `/admin/lista_telefonica` — `main.py` (`eh_admin` + `ui.colors(primary=ler_tema("lista_telefonica"))` + `mostrar_administracao(nome)`; não-admin navega para `/lista-telefonica`).
- Cadastro central: `MODULOS_SISTEMA` (`autenticacao.py` → `("lista_telefonica","Lista Telefônica","call","/lista-telefonica")`), `MODULOS_BD` (`repositorio.py` → `lista_telefonica: db_mod_lista_telefonica.db`), `PADROES_TEMA["lista_telefonica"]` (`tema_modulo.py` → `#000000`), `PREFIXO_POR_CHAVE["lista_telefonica"]` → `lista_telefonica`.
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_lista_telefonica` (`criar_unidade`, `editar_unidade`, `excluir_ramo`, `mover_unidade`, `elevar_rebaixar`, `reordenar`, `criar_contato`, `editar_contato`, `excluir_contato`, `transferir_contato`).
- Backup do banco: job `backup:lista_telefonica` (`backup_horas:lista_telefonica` default 12h, `MAPA_BACKUPS` inclui `lista_telefonica: db_mod_lista_telefonica.db`).
- **Cadastro de usuários**: a tela **não importa** `mod_gest_cad_usuario` — nem para ler o telefone, nem para qualquer outra coisa. O espelhamento passa pelo **núcleo**: `mod_intranet.integracoes.espelhar_cadastro_na_lista_telefonica(ator)` (ver "Espelhamento do cadastro no diretório"). A ponte de leitura `mod_gest_cad_usuario/leitura_lista.py` (dicionários, **só telefone publicável**) é chamada pelo núcleo, não pela lista.
- **Núcleo**: **`telefones_de_recado_para_lista()`** (9ª função da fachada, 27/09/2026) — consumida em `telas.py:576` para alimentar o `_cache_recado` que escreve o "deixe recado" no cartão; `mod_intranet.autenticacao` (`validar_acesso_modulo`, `eh_admin_do_modulo`, `perfil_global_de`, `usuario_existe`), `mod_intranet.banco_conexao`, `mod_intranet.aba_modulo` (`cabecalho`, `campo_busca`), `mod_intranet.tema_modulo` (`ler_tema`, `notificar`), `mod_intranet.ui_comum` (`botao`, `botao_icone`, `dialogo_card`, `card_admin`, `painel_backup`), `mod_intranet.telefone`, `mod_intranet.observabilidade`, `mod_intranet.integracoes` (vínculo de contato no `telas_administracao.py` + **`espelhar_cadastro_na_lista_telefonica` na tela**).
- **Integração com Solicitação de Impressão**: `mod_solicita_impressao/bd_manipulador.py` importa `ORGANOGRAMA_BASE` pela fachada `mod_intranet.integracoes.obter_organograma_base()` para semear `tb_secretarias` (1000 cópias) e `tb_setores` (200 cópias, subsetores achatados como setores) + migração `UPDATE` idempotente para bancos existentes — ver [Módulo Solicitação de Impressão](solicitacao_impressao.md).

## Testes

```bash
# Smoke do módulo (import + init_db + CRUD mínimo)
.venv/bin/python -c "from mod_lista_telefonica.bd_manipulador import init_db, listar_unidades, buscar_contatos; init_db(); print(listar_unidades(tipo='secretaria')[:2]); print(buscar_contatos('a'))"
# Árvore + impressão (o PDF sai em memória, sem arquivo em disco)
.venv/bin/python -c "
from mod_lista_telefonica import bd_manipulador as l, impressao as i
arvore = l.listar_arvore_contatos()
print(i.contar(arvore), 'contatos')
print(len(i.filtrar_arvore(arvore, termo='saude')), 'com saude (filtro OU)')
print(len(i.filtrar_arvore(arvore, nome='maria')), 'com maria (campo separado, E)')
print(len(i.pdf_bytes(arvore, 'Lista Telefônica', 'teste')[0]), 'bytes de PDF')"
# Análise estática (undefined name é bloqueante)
.venv/bin/python -m pyflakes mod_lista_telefonica/telas.py mod_lista_telefonica/impressao.py
# Consentimento do telefone, ciclo da pendência, recado e faixas (51 asserções, script standalone)
.venv/bin/python assets/test/test_telefone_consentimento.py
# Primeiro acesso E2E: aviso de faixa ao vivo, as DUAS travas, o bilhete (20 asserções)
# Playwright PYTHON (o pacote npm não está instalado) — exige o servidor no ar
.venv/bin/python assets/test/test_primeiro_acesso_e2e.py
# Playwright (servidor vivo em localhost:8080; o resto da suíte roda sem ele)
.venv/bin/pytest assets/test/test_e2e_lista_telefonica.py -v -m "unit"
.venv/bin/pytest assets/test/test_e2e_lista_telefonica.py -v          # precisa do servidor no ar
```

`assets/test/test_telefone_consentimento.py` cobre a parte que atravessa os dois módulos: a regra pura de `telefone_e_publicavel`, o ciclo da pendência (`telefone_pendente` nasce ligado e só baixa com `registrar_contatos_primeiro_acesso`), a gravação dos quatro telefones, a idempotência, o usuário bloqueado fora do diretório, o lote, e — desde 27/09/2026, em `teste_recado_e_faixas` — o **recado**, as **faixas** da prefeitura e a **liberação temporária de 4 dias** (inclusive o bloqueio por prazo e a recusa do DTI sem fixo). São **51 asserções** (era 31) e roda como **script standalone** (sem pytest), com usuários de prefixo de teste que são apagados no fim.

`assets/test/test_primeiro_acesso_e2e.py` (27/09/2026, **novo**, 20 asserções) prova o que só a tela real prova: o diálogo abre, o aviso de faixa aparece **enquanto se digita** e some quando o número entra na faixa, a **primeira** trava aparece e nada é gravado, a **segunda** escreve o preço (4 dias, bloqueio, DTI), o bilhete aparece depois de liberar, e no banco o particular **não** entra na lista, a pendência baixou e o prazo é de no máximo 4 dias. Usa **Playwright Python** (`sync_api`) porque o pacote npm não está instalado, e exige o servidor no ar em `http://localhost:8080`.

Os testes E2E da tela usam os testids **atuais**: `lista-busca-termo` e
`lista-cascata-1` (`assets/test/test_e2e_lista_telefonica.py:264-268`,
`assets/test/test_e2e_cobertura_extra_sec.py:1191-1225`,
`assets/test/carga_uso_navegador.py:387-388`).

Ver [Análise do Módulo](../analise_mod_lista_telefonica.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Não há navegação por botões.** Se a documentação ou um teste citar `lista-nav-*`, `lista-busca-nome`, `lista-busca-telefone` ou `lista-busca-unidade`, está descrevendo uma versão que não existe mais: o recorte é pelos três `lista-cascata-{1,2,3}` e a busca é o `lista-busca-termo` único.
- **Filtro OU no termo, filtro E nos campos separados.** `filtrar_arvore(arvore, termo="", nome="", telefone="", unidade="")` — quando `termo` vem preenchido, ele tem **precedência** e vale como OU entre nome, telefone e caminho da unidade; `nome`/`telefone`/`unidade` continuam aceitos (impressão de recorte, testes) e se combinam como **E**, como eram. A comparação de telefone é feita sobre os **dígitos** (`_digitos`), então `3591` acha `(00) 3591-5101`.
- **`+55` fora do cartão, dentro do `tel:`.** Decisão de espaço na coluna de ~216px da grade de 3 colunas (o prefixo empurrava o telefone para duas linhas e cortava o nome) e de consistência entre números completos e parciais. `_tel_limpo` continua produzindo o número completo para o link.
- **Altura fixa é requisito, não enfeite.** `ALTURA_CARTAO = "5.9rem"` + `align-items: stretch` são o que garante cartões do **mesmo** tamanho; com `align-items: start` cada cartão mediria o próprio conteúdo e a coluna ficaria com alturas diferentes.
- **`minmax(200px, 1fr)`, não 260px.** A conta está no comentário do código (`3 × 200px + 2 × 12px = 624px`): a 260px a grade caía em duas colunas no contentor de 673px e o mínimo de 3 colunas não era cumprido.
- **Cascata recursiva com teto 20.** A leitura do organograma (`listar_arvore_contatos` → `montar`) aceita quantos níveis existirem; `_PROFUNDIDADE_MAXIMA = 20` é proteção contra ciclo de `parent_id`, não limite de negócio. O `CHECK` do banco continua aceitando só `secretaria`/`setor`/`subsetor`.
- **`lista-busca` é o invólucro, não o campo.** O testid `lista-busca-termo` cai no `<input>` nativo do Quasar; por isso o `no-print` da folha de impressão vai no *invólucro* do card — esconder só o input deixaria a caixa em branco impressa.
- `tel:` é suportado nativamente em mobile; em desktop o diálogo avisa que discador pode não estar configurado — `ui.run_javascript` é `try/except` (fail-soft). A impressão do navegador é a **única** função da tela que **precisa** de `ui.run_javascript` (`window.print()`), e a justificativa está no comentário do handler.
- **O PDF nunca toca o disco** (bytes na resposta), então o módulo não deixa arquivo temporário para limpar.
- **A rota do PDF revalida a sessão e o acesso ao módulo**, mas quem chega nela é sempre alguém da própria lista: não há vazamento entre usuários (a lista é do módulo inteiro, igual à tela).
- **A ponte `leitura_lista.py` é chamada pelo NÚCLEO, não pela lista.** `mod_lista_telefonica` não importa `mod_gest_cad_usuario` — nem para ler o telefone. Quem costura é `mod_intranet/integracoes.espelhar_cadastro_na_lista_telefonica(ator)`, que recebe a lista pronta por parâmetro. Um `import mod_gest_cad_usuario` dentro do módulo reprova `assets/test/check_integridade.py`, e está correto.
- **O espelhamento nunca apaga nada.** Ele cria, atualiza **só o telefone** e conta o resto. Desativar/excluir ramo continua sendo ação de administrador, no painel admin. A única coisa que o espelhamento desliga é a **sincronização automática** — nunca a unidade.
- **`sincronizacao_desatualizada()` devolve `True` em banco recém-criado** (carimbo vazio), então a primeira abertura da tela já dispara o espelhamento. Isso é o comportamento certo: o diretório recém-criado está literalmente vazio.
- **O resumo `{criados, atualizados, sem_unidade, sem_telefone, ja_iguais}` é somado por rodada, não acumulado.** `sem_telefone` e `sem_unidade` contam servidores que **não entraram** nesta rodada; `tb_sincronizacao.total_criados`/`total_atualizados` guardam só a última rodada também. Não são contadores históricos.
- **`_auto_sincronizar` roda 0,4 s depois do desenho, por usuário.** Quem tem a lista aberta em várias abas dispara um espelhamento por aba. É idempotente e silencioso, e a trava `_sincronizando` só protege **dentro** da mesma tela — entre telas diferentes a corrida existe e é inofensiva (mesma escrita, mesmo resultado).
- Nunca commitar `db_mod_lista_telefonica.db`; `bd_criador.py` morto — nunca executar.
- API real do `bd_manipulador` (todas com `try/except` + `notificar`/log): `get_connection` (WAL + `foreign_keys=ON` via `banco_conexao.conexao`), `_log`/`_audit` (auditoria via `audit_log`), `_norm` (NFKD sem acentos), `init_db`, `listar_unidades(parent_id, tipo, ativo)`, `listar_todas_unidades`, `obter_unidade(uid)`, `criar_unidade`, `editar_unidade`, `excluir_ramo` (+ `_coletar_ramo_ids` recursivo), `mover_unidade` (anti-ciclo), `elevar_rebaixar`, `reordenar_unidades`, `buscar_unidades`, `listar_contatos`, `buscar_contatos`, `listar_arvore_contatos(raiz_id, termo)` (árvore aninhada já alfabética, recursiva, com `nivel` e teto de profundidade), `contar_contatos`, `criar_contato`, `editar_contato`, `excluir_contato`, `transferir_contato`, `contar_unidades` (contagem de `tb_unidade`), **`sincronizar_contatos_do_cadastro(contatos, ator)`**, **`INTERVALO_REFRESH_MIN`**, **`_carregar_sincronizacao(criados, atualizados)`**, **`sincronizacao_desatualizada()`**, `remover_vinculos_usuario`/`renomear_usuario` (LGPD).
- API real de `impressao.py`: `gerar_pdf_lista(destino, nos, titulo, rodape)`, `pdf_bytes(nos, titulo, rodape)`, `contar(arvore)`, `filtrar_arvore(arvore, termo, nome, telefone, unidade)`, `titulo_para_impressao`, `rodape_para_impressao`, `registrar_rota_pdf()`.
- Tela pública (`telas.py`): API real é `mostrar_tela(user_nome, perfil_global)` + helpers `_pode_ver`/`_eh_admin`/`_falha`/`_falhar`/`_testid`/`_texto_curto`/`_tel_limpo`/`_tel_exibicao`/`_caminho_unidade`/`_no_por_id`/`_recortar`/`_unidades_para_selecao`/`_opcoes_pai`/`_campo_telefone`/`_url_pdf` e os internos `_ao_filtrar`, `_limpar_busca`, `_tem_filtro`, `_niveis_da_arvore`, `_opcoes_nivel`, `_caminho_do_id`, `_preencher_cascata`, `_ao_mudar_nivel`, `_carregar_arvore`, `_escolher`, `_cabecalho_recorte`, **`_sincronizar_cadastro`** (async, botão admin), **`_auto_sincronizar`** (async, silenciosa, disparada por `ui.timer`), `_botao_pdf`, `_imprimir`, `_desenhar_blocos`, `_preencher_grade`, `_cartao_contato`, `_dlg_ligar`, `_guarda_admin`, `_dlg_novo_contato`, `_dlg_editar_contato`, `_dlg_remover_contato`, `_dlg_nova_unidade`, `_dlg_editar_unidade` e o `@ui.refreshable render_organograma`; **não existem** `_barra_navegacao` nem `_botao_nav` (navegação por botões foi abandonada) — mover/elevar/reordenar/excluir ramo e transferir contato continuam só no painel admin.
- **`_escolher(uid)` (`telas.py:544`) é resíduo da navegação por botões**: alterna `estado["unidade"]` e redesenha, mas **nada a chama** — o recorte hoje vem da cascata (`nivel_3/nivel_2/nivel_1`). Está documentada aqui para quem ler o arquivo e a procurar na tela.
- **"Limpar" repopula a cascata no nível certo — corrigido em 27/09/2026.** `_limpar_busca` usava `_opcoes_nivel(1)`, e como `_niveis_da_arvore` numera a raiz como 0, o nível 1 são os **filhos** das raízes: limpar a busca trocava as secretarias pelos setores no primeiro select. Hoje (`telas.py:424`) usa `_opcoes_nivel(0, _carregar_arvore())`, o mesmo nível da carga inicial.
- **Docstrings do código que ficaram atrás da tela** (ao ler o arquivo, não acredite nelas): o docstring do módulo em `telas.py:1-7` ainda diz *"3-field search"* e o de `_limpar_busca` (`:402-404`) ainda diz *"os três campos"*; o de `_opcoes_nivel` (`:455-462`) promete o **caminho completo** como rótulo ("Administração > Patrimônio e Almoxarifado > Compras") mas devolve só `n["nome"]` (`:465`) — dois subsetores homônimos em secretarias diferentes aparecem com o mesmo rótulo; o de `listar_arvore_contatos` (`bd_manipulador.py:854-855`) ainda diz que `filhos` "só vem preenchido no nível de secretaria", o que a recursão `montar` (`:889`) já não faz; e o de `render_organograma` (`telas.py:1036`) ainda diz "Botões + recorte". A documentação acima segue o **código**, não esses textos.
- `data-testid` da tela (prefixo `lista-`): `lista-busca` (container `role="search"`), `lista-busca-termo`, `lista-cascata-1`, `lista-cascata-2`, `lista-cascata-3`, `lista-limpar-busca`, `lista-grade`, `lista-contato-<cid>`, `lista-ligar`, `lista-pdf-baixar`, `lista-imprimir`, `lista-admin-novo-contato`, `lista-admin-nova-unidade`, `lista-admin-editar-unidade`, **`lista-admin-sincronizar`** (27/09/2026), `lista-contato-editar-<cid>`, `lista-contato-remover-<cid>` e os `lista-{novo-contato|editar-contato|remover-contato|nova-unidade|editar-unidade}-*` dos diálogos. **Removidos** em 27/09/2026: `lista-select-secretaria`, `lista-select-setor`, `lista-select-subsetor`, `lista-nav`, `lista-nav-todas`, `lista-nav-{secretaria|setor|subsetor}-<id>`, `lista-busca-nome`, `lista-busca-telefone`, `lista-busca-unidade` — `assets/test/test_e2e_cobertura_extra_sec.py`, `assets/test/carga_uso_navegador.py` e `assets/test/test_e2e_lista_telefonica.py` foram acompanhados.
