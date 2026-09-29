# Gestão de Usuários — `mod_gest_cad_usuario`

> User management module: route `/users` (key `usuarios`) · own database `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, multi-profile/role, revocable sessions, cross-module LGPD cleanup · **the single user registry, consumed by other modules through the `mod_intranet/integracoes.py` facade (never a direct import)**.

---

# Gestão de Usuários — `mod_gest_cad_usuario`

> Módulo de gestão de usuários: rota `/users` (chave `usuarios`) · banco próprio `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, múltiplos perfis/papéis, sessões revogáveis, limpeza cruzada LGPD · **fonte única do cadastro, consumida pelos demais módulos pela fachada `mod_intranet/integracoes.py` (nunca por import direto)**.

## Propósito

Soft CRUD completo de usuários: criar, editar, renomear, bloquear/desbloquear, excluir logicamente (com motivo) e excluir permanentemente (LGPD). Gerencia perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo, além da visualização e revogação de sessões ativas de todo o sistema. Acesso restrito ao administrador geral ou administrador do módulo `usuarios`.

## Banco próprio

Conexão com WAL + `foreign_keys=ON`. Criador vigente: `init_db()` em `bd_manipulador.py:61-215`, executado no import do módulo e pelo bootstrap central.

**`tb_usuarios`** (após migrações):

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT — renomeio de login preserva o ID |
| `user_nome` | UNIQUE NOT NULL |
| `user_senha` | hash bcrypt |
| `user_email`, `user_fone` | contato |
| `user_perfil` | global, default `comum` |
| `user_ativo` | 0/1 |
| `data_cadastro` | timestamp |
| `modulo_acesso` | legado CSV (migrado para linhas) |
| `user_deletado` | soft delete |
| `user_nome_completo` | nome social/tratamento (Decreto 8.727/2016) |
| `user_motivo_exclusao` | motivo da exclusão lógica |

**`tb_acesso_usuario`** — vínculo usuário×módulo×papel (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE para `tb_usuarios`); `modulo_chave` é texto livre — origem dos vínculos órfãos (helper `listar_vinculos_orfaos(chaves_ativas)`; tela marca como badge `INDISPONÍVEL`). Coluna `flags` (JSON TEXT, default `'{}'`) para permissões finas.

**Flags finas** — catálogo `FLAGS_PERMISSAO` (`blog.publicar`, `blog.comentar`, `blog.configurar`): `obter_flags` (fail-soft `{}`), `definir_flags` (allowlist, exige vínculo) e `tem_flag` (admin passa pelo papel). `duplicar_usuario` replica papéis + flags da origem.

**Sessões (banco central `tb_sessoes`)** — `id, usuario, modulo, login_timestamp, cookie_hash, ip, dispositivo, mac, logout_timestamp`; abertas = `logout_timestamp IS NULL`. Helpers: `listar_sessoes_ativas`, `contar_sessoes_ativas`, `sessoes_ativas_por_usuario`, `listar_historico_sessoes` (10 últimas encerradas), `encerrar_sessao` / `encerrar_todas_sessoes` / `_fechar_sessoes_central` (invocado em bloqueio, soft/hard delete e reset de senha). Renomear reflete nas sessões centrais abertas.

⚠️ `tb_modulo_perfil` existe apenas no `bd_criador.py`, que é **código legado/morto**: usa a conexão do banco **central** (criaria as tabelas em `db_mod_intranet.db`) e não é importado por ninguém.

## Fluxo da tela

- Gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user,'usuarios')`; caso contrário painel "Acesso restrito".
- Abas: **Usuários** | **Sessões Ativas** | **Administração** (só admin geral). A aba **Excluídos** foi **removida**: usuários excluídos (soft) são acessados pela busca por "excluído" na aba Usuários.
- Busca instantânea (debounce 150 ms) insensível a acentos/pontuação, localiza também pelo nome completo/social.
- Lista com filtros situação/perfil, paginação client-side 10/20/50/100 e badges: `ativo`, `bloqueado`, `excluído (soft)`, `senha provisória`. Ações ocultas na própria linha do ator ("use Meu Perfil").
- Diálogos: Novo usuário (senha provisória com mínimo configurável `usuarios_senha_min` + seletores de acesso por módulo registrado, inativos marcados INDISPONÍVEL), Editar (login travado p/ master; aplica só diferenças), Redefinir senha, Excluir lógico (motivo ≥3 chars obrigatório), Exclusão definitiva (digitar o login; aviso LGPD listando a limpeza cruzada).
- Aba Sessões Ativas: todas as vivas do sistema (IP, dispositivo, MAC em tooltip) com encerramento individual/em massa; diálogo por usuário mostra histórico das 10 últimas com duração calculada.

## Regras de negócio relevantes

- **Exclusão em dois estágios**: estágio 1 = soft delete com motivo, encerra sessões, reversível ("Restaurar" limpa o motivo); estágio 2 = DELETE físico, acessível nas linhas de usuários excluídos via busca "excluído" (admin geral revalidado no backend).
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do editorPDF (`mod_edit_pdf/editorPDF/`) e anonimiza autoria de empenhos como "(usuário excluído)". Auditoria sempre preservada. Nota: implementa cross-query SQLite ad-hoc aos bancos vizinhos (contrariando a convenção geral do projeto).
- **Proteções**: vedado agir sobre a própria conta (bloquear/excluir/rebaixar); `master` não é renomeado nem excluído; último admin geral ativo protegido contra **exclusão definitiva**; RF-26: `editar_usuario`/`bloquear_usuario` bloqueiam **rebaixar ou bloquear** o último `administrador_geral` ativo quando o ator é OUTRO admin (`bd_manipulador.py:349-362`).
- **Senha provisória**: criação/redefinição marcam `forcar_troca`; redefinição derruba todas as sessões. O admin digita a senha manualmente (não é gerada aleatória como diz o PLANO 2.5).
- **Auto-cura do master**: enquanto a senha de fábrica estiver em uso, a troca é rearmada a cada boot (`bd_manipulador.py:501-512`) — corrige o roadmap do README que dizia o contrário. **Não confundir com o seed:** o *rearme da troca* é desirable; a *recriação da conta* não é, e desde 29/09/2026 o seed respeita a marca `forcar_troca_credenciais:master` para não recriar a conta de fábrica depois do primeiro acesso — ver [Conta de fábrica `master` ressuscitando](seguranca/conta_de_fabrica_master_2026-09-29.md).

## Soft CRUD, perfis/papéis e sessões revogáveis — referência de API

O módulo expõe uma API funcional pura (sem camada de classe) dividida em 7 blocos
por separadores `# =================`. Todas as funções devolvem
`(ok, msg)` nas operações de escrita e `None`/`[]`/falsy nas consultas, com
`try/except` + loguru (fail-soft, AGENTS.md §3.2).

### Consultas (`bd_manipulador.py:423-544`)

| Função | Devolve | Observação |
|:---|:---|:---|
| `listar_usuarios(filtro_ativo=None)` | `list[tuple]` de **11 campos**: `(0)id, (1)user_nome, (2)user_perfil, (3)user_ativo, (4)user_email, (5)user_fone, (6)data_cadastro, (7)acessos "modulo:papel, …", (8)user_deletado, (9)user_nome_completo, (10)user_motivo_exclusao`. `filtro_ativo` filtra `user_ativo`; **não** filtra `user_deletado` (os soft-deleted **aparecem** com a flag ligada em `[8]`); ordenação por login |
| `obter_usuario(user_nome)` | `tuple` de **10 campos** ou `None`: `(0)id, (1)user_nome, (2)user_senha, (3)user_email, (4)user_fone, (5)user_perfil, (6)user_ativo, (7)data_cadastro, (8)user_deletado, (9)user_nome_completo`. Inclui o hash da senha (uso interno do núcleo); ponto de entrada da fachada `obter_usuario_gestao` |
| `nome_de_tratamento(user_nome)` | `str` | **Primeiro + último nome** de `user_nome_completo` (nome social, Decreto 8.727/2016), via `_primeiro_e_ultimo`; cai no nome completo e depois no login só se não houver nome. `"Ana Beatriz Souza Rocha"` → `"Ana Rocha"` (exemplo fictício). Motivo (27/09/2026): o login é a matrícula (`000123`, também fictícia), e mostrar matrícula no cabeçalho é mostrar um código de barras com nome de pessoa; o nome inteiro empurra o rótulo do perfil para fora da tela. |
| `listar_acessos(user_nome)` | `list[tuple]` | Papéis por módulo + flags finas |

!!! warning "Os dois formatos de tupla NÃO são o mesmo"
    `listar_usuarios` e `obter_usuario` devolvem **layouts diferentes** — só
    coincidem em `[1]` (login) e `[9]` (nome completo). Assim, `[4]` é
    **`user_email`** em `listar_usuarios` e **`user_fone`** em `obter_usuario`:
    quem consome precisa saber qual função chamou. Os consumidores atuais
    respeitam isso — `mod_lista_telefonica/telas_administracao.py:697` filtra a
    **lista** por `[1]`/`[9]`/`[4]` (login, nome completo, e-mail) e, em
    `:746-756`, lê `[9]` e `[4]` da **tupla única** (nome completo, telefone).

### CRUD (`:546-1018`)

| Função | Regra de negócio |
|:---|:---|
| `criar_usuario(ator, user_nome, senha, email=None, fone=None, perfil="comum", ...)` | Senha vazia/`None` → padrão inicial; mínimo `usuarios_senha_min` (default 6); marca `forcar_troca`; semeia `ACESSO_PADRAO_NOVO_USUARIO`; audita `criar_usuario` |
| `editar_usuario(ator, user_nome, ...)` | Aplica **só diferenças**; login travado para `master`; **RF-26** bloqueia rebaixar/bloquear o último `administrador_geral` ativo quando o ator é outro admin; marcador `__NULO__` distingue "não informado" de "limpar" |
| `renomear_usuario(ator, nome_atual, novo_nome, permitir_master=False)` | Preserva o `id`; propaga em `tb_acesso_usuario`, sessões centrais abertas e autorias dos demais módulos (`_vinculos_cruzados_renomear`) |
| `alterar_senha_admin(ator, user_nome, nova_senha)` | Marca troca pendente e **derruba todas as sessões** do usuário |
| `bloquear_usuario(ator, user_nome, bloquear=True)` | Fecha as sessões (`_fechar_sessoes_central`) |
| `soft_delete_usuario(ator, user_nome, motivo=None)` | Exclusão **lógica** com motivo **≥ 3 chars obrigatório**; grava `user_motivo_exclusao`; encerra sessões; **reversível** ("Restaurar" limpa o motivo); recusa `master` e a própria conta |
| `excluir_usuario_definitivo(ator, user_nome)` | Estágio 2 LGPD: `DELETE` físico + limpeza cruzada; **só** admin geral; protege o último `administrador_geral` ativo |
| `duplicar_usuario(ator, usuario_origem, novo_nome, senha, ...)` | Clona perfil global, papéis por módulo **e flags finas** da origem |

### Papéis por módulo (`:1020-1119`)

| Função | Devolve |
|:---|:---|
| `definir_acesso(ator, user_nome, modulo_chave, papel)` | Concede/vincula — papel em `PAPEIS_MODULO = ["comum", "administrador"]` |
| `remover_acesso(ator, user_nome, modulo_chave)` | Revoga o vínculo |
| `obter_papel_no_modulo(user_nome, modulo_chave)` | `"administrador"`, `"comum"` ou `None` — **`administrador_geral` ativo resolve como `administrador` em qualquer módulo** |
| `validar_acesso_modulo(user_nome, modulo_chave)` | Booleano usado pela guarda de página do núcleo (`autenticacao.py`) e pelo menu. **RF-35:** `auditoria` é exclusivo do `administrador_geral` |

`PERFIS_GLOBAIS = ["comum", "administrador_modulo", "administrador_geral"]` e
`ACESSO_PADRAO_NOVO_USUARIO = ("editar_pdf", "empenhos", "solicita_impressao")` —
`usuarios`, `auditoria` e `blog` **nascem sem vínculo** (concessão manual do admin).

### Flags finas — JSON por vínculo (`:1121-1219`)

Catálogo `FLAGS_PERMISSAO` = `blog.publicar`, `blog.comentar`, `blog.configurar`
(JSON TEXT na coluna `flags` de `tb_acesso_usuario`, default `'{}'`).
`obter_flags` (fail-soft `{}`), `definir_flags` (allowlist — valida contra o
catálogo — e **exige vínculo prévio**) e `tem_flag(user, modulo, flag)` (quem é
admin passa pelo papel, sem precisar da flag).

### Sessões revogáveis (`:1221-1363`)

As sessões vivem no **banco central** (`tb_sessoes` do `mod_intranet`) — este
módulo é o **único** autorizado a lê-las e a **fechá-las** por ação administrativa
(o login/sessão em si é do núcleo).

| Função | Papel |
|:---|:---|
| `_fechar_sessoes_central(user_nome)` | Usada internamente por bloqueio, soft/hard delete e reset de senha — **fecha todas** as sessões abertas do usuário |
| `listar_sessoes_ativas(usuario=None)` | Todas do sistema ou de um usuário (IP, dispositivo, MAC em tooltip) |
| `contar_sessoes_ativas(usuario=None)` / `sessoes_ativas_por_usuario()` | Agregados do painel e do dashboard `/` |
| `listar_historico_sessoes(usuario, limite=10)` | 10 últimas encerradas por usuário (duração calculada na tela) |
| `encerrar_sessao(ator, sessao_id)` | Encerra **uma** sessão por id (idempotente: "Sessão já encerrada"); audita `encerrar_sessao` |
| `encerrar_todas_sessoes(ator, user_nome)` | Encerramento em massa; audita `encerrar_todas_sessoes` |

O mecanismo completo (cookie `cookie_hash` via `secrets`, revalidação a cada
request em `sessao_ativa`) é do núcleo — ver
[Análise do Núcleo](analise_mod_intranet.md#autenticacao-e-sessoes). A retenção do
histórico usa a chave `sessao_retencao` (dias, default 50 — `PADRAO_CONFIG`).

### Vínculos órfãos (`:1365-1385`)

`listar_vinculos_orfaos(chaves_ativas)` devolve os vínculos cujo `modulo_chave`
não está mais em `tb_modulos` — a tela os exibe com badge `INDISPONÍVEL` nos
seletores. Observação: a função existe mas **não é chamada** pela tela (ver
"Pontos de atenção").

## Limpeza cruzada LGPD — a única exceção de negócio→negócio

Quando um usuário é **excluído** (definitivo) ou **renomeado**, a Gestão de
Usuários precisa limpar/anonimizar a autoria dele **nos demais módulos**:
postagens e comentários do Blog, arquivos e cota do Editor de PDF, e autoria dos
Empenhos (que vira `"(usuário excluído)"`). A **auditoria é sempre preservada**
(rastro legal não se apaga).

Essa necessidade é a **única exceção documentada** à regra de isolamento: cada
módulo é acionado pela sua **API pública** (`_vinculos_cruzados_excluir` /
`_vinculos_cruzados_renomear` chamam o `bd_manipulador` de cada vizinho), então
**cada módulo continua tocando só o seu próprio banco** — não existe cross-query
de SQL nem `sqlite3.connect` em banco alheio. É uma operação de negócio que
precisa ser coerente na frente do usuário, não uma consulta que atravessa
bancos.

Por isso o `assets/test/check_integridade.py` mantém a allowlist
`CASCATA_LGPD` com exatamente estes três pares e considera **qualquer outro**
par negócio→negócio uma falha estrutural:

```python
CASCATA_LGPD = {("mod_gest_cad_usuario", "mod_blog"),
                ("mod_gest_cad_usuario", "mod_edit_pdf"),
                ("mod_gest_cad_usuario", "mod_renomear_empenho")}
```

Desde 25/09/2026 os **demais** usos de dado entre módulos passaram a passar pela
fachada `mod_intranet/integracoes.py` (ver seção seguinte e
[Fachada de Integração](arquitetura_de_software_das/fachada_integracoes.md)).

## Fonte única do cadastro — consumo via `mod_intranet/integracoes.py` (25/09/2026)

Este módulo é a **fonte única do cadastro de usuários** da intranet. A partir de
25/09/2026 os demais módulos **não o importam mais direto**: consomem o cadastro
pela **fachada pública do núcleo**, `mod_intranet.integracoes`
(imports lazy + fail-soft, AGENTS.md §2 — nunca cross-query entre bancos).

| Fachada (`integracoes.py`) | Delegada a | Consumidores |
|:---|:---|:---|
| `obter_usuario_gestao(user_nome)` `:32` | `obter_usuario` | `mod_filas/bd_manipulador.py:454` (reconhecer `administrador_geral` antes de autorizar) · `mod_filas/bd_manipulador.py:483` (`liberar_acesso` recusa usuário não cadastrado) · `mod_lista_telefonica/telas_administracao.py:745` (preenche nome e telefone do contato) |
| `listar_usuarios_gestao(filtro_ativo=None)` `:49` | `listar_usuarios` | `mod_filas/telas.py:631` (autocomplete "liberar fila para usuário cadastrado") · `mod_lista_telefonica/telas_administracao.py:689` (busca de contato por nome, login ou e-mail) |

**O que muda para quem consome:**

- O `try/except` fica no **núcleo**; a fachada devolve `None`/`[]` e registra
  `logger.warning` — a tela do consumidor decide se exibe "Nenhum usuário
  encontrado" ou um aviso amigável.
- Os **valores neutros** cobrem três cenários que antes viravam `try/except`
  espalhado no chamador: módulo ausente, banco fechado/locked e usuário inexistente.
- O **formato posicional das tuplas** é contrato informal de consumo — por isso
  a fachada repassa a lista como veio, sem reordenar (quem indexa é o chamador).
  Layouts **diferentes** entre as duas funções: `listar_usuarios` (11 campos,
  `[4]` = e-mail) e `obter_usuario` (10 campos, `[4]` = telefone); só `[1]`
  (login) e `[9]` (nome completo) coincidem. Ver o alerta na seção de consultas.
- `obter_usuario_gestao` repassa a tupla **com o hash da senha** no campo
  `[2]` (é o mesmo `obter_usuario` que o núcleo usa em `usuario_existe`): nunca
  logar nem exibir esse campo na tela.

!!! tip "Se você precisa de dado que NÃO é o cadastro de usuário"
    Não abra exceção no isolamento: acrescente uma função à fachada
    `mod_intranet/integracoes.py` seguindo o
    [checklist de 7 passos](arquitetura_de_software_das/fachada_integracoes.md#como-adicionar-uma-funcao-nova-na-fachada)
    (import lazy, fail-soft, docstring bilíngue, `check_integridade.py` verde).
    Dados que são **configuração global** nem precisam da fachada — use
    `get_config`/`set_config` (precedente `censura.py`).

## Seeds idempotentes de contas (AGENTS.md §8.2)

`init_db()` (`bd_manipulador.py:174-186`, executado no import **e** pelo
bootstrap central) é a **fonte única** dos seeds. São criados **só se ainda não
existirem** (idempotente) — nunca duplicados em outro ponto do código.

| Usuário | Perfil global | Observações |
|:---|:---|:---|
| `master` | `administrador_geral` | Conta **de fábrica**; 1º login **força** troca de senha **e** de credenciais (`marcar_trocar_senha` + `marcar_trocar_credenciais`) — o primeiro acesso **renomeia** o login. Enquanto a senha padrão existir, a troca é **rearmada a cada boot** (auto-cura idempotente, `:501-512`). **Depois do primeiro acesso o seed NÃO recria a conta** — a guarda tem duas condições e respeita a marca `forcar_troca_credenciais:master` (`:535`) |
| `qacomum` | `comum` | Teste/QA; reconciliado a cada boot com `ACESSO_PADRAO_NOVO_USUARIO` (`INSERT OR IGNORE` dos 3 acessos comuns + `DELETE` do vínculo `blog` legado concedido por `sistema`) — **concessões manuais do admin são preservadas** (`:394-404`); troca forçada no 1º login |
| `qamaster` | `administrador_geral` | Teste/QA; troca forçada no 1º login |

!!! danger "Credenciais fora desta documentação"
    As senhas provisórias dos seeds **não** são publicadas aqui nem em nenhum
    artefato versionado. A senha padrão é **provisória**: qualquer fluxo de teste
    deve supor que ela **já pode ter sido trocada** pelo usuário. A tabela acima é
    o contrato (login + perfil + regras); os valores vivem apenas no código
    (`bd_manipulador.py`, contexto interno do AGENTS.md §8.2).

!!! danger "O seed do `master` existe **só para nascer o sistema** (29/09/2026)"
    A guarda do seed era `if not obter_usuario("master")` — mas o primeiro acesso
    do `master` é um **renomear**, e `renomear_usuario` faz `UPDATE` **preservando
    o `id`**: o login `master` sai da tabela, a guarda volta a ser verdadeira no
    boot seguinte, e o seed **recriava a conta de fábrica** com perfil
    `administrador_geral` e as flags de troca rearmadas. O diálogo de troca
    reabria em ciclo, indefinidamente.

    Hoje a guarda é `if not _troca_de_credencial_do_master_concluida() and not obter_usuario("master")` (`:535`), e a função nova (`:190`) lê a marca `forcar_troca_credenciais:master` do `tb_config` **central** — `'1'` = troca pendente, `'0'` = troca **concluída** (gravada por `trocar_credenciais_master` **depois** do rename, no núcleo). "Chave existe e vale 0" = "o `master` nativo já foi renomeado". **Fail-soft:** em falha de leitura devolve `False` e semeia, porque semear numa instalação já trocada é transtorno e deixar de semear numa instalação nova **tranca o admin para fora**.

    A **mesma** lógica, a **mesma** falha e a correção completa — com evidência,
    com o `bd_criador.py` bloqueado (segundo caminho de criação) e com o padrão
    "estado que se auto-restaura" — estão em
    [Conta de fábrica `master` ressuscitando a cada reinício](seguranca/conta_de_fabrica_master_2026-09-29.md).

O bootstrap em si é **check-then-add idempotente** e portátil SQLite↔PostgreSQL
(`PRAGMA table_info` → `information_schema` no proxy; `INSERT OR IGNORE` →
`ON CONFLICT DO NOTHING`), com `_commit_com_retry` (busy_timeout herdado + retry
em `database is locked`) e rollback em falha parcial. `init_db()` **nunca**
derruba o import do módulo: o `try/except` do entry point absorve e registra.

## Integrações com o núcleo

Importa `autenticacao` (hash/verificação de senha, papéis, troca pendente), `get_connection` central e `audit_log`. Ações auditadas: `criar_usuario`, `editar_usuario`, `renomear_usuario`, `alterar_senha`, `soft_delete`, `excluir_definitivo`, `definir_acesso`, `remover_acesso`, `encerrar_sessao`, `encerrar_todas_sessoes`. Escreve/lê diretamente `tb_sessoes` central. Nenhuma chave `tb_config` usada (exceto a leitura de `usuarios_senha_min`, feita pelo núcleo via `get_config`).

**Na direção inversa (25/09/2026)**: este módulo é a **fonte do cadastro** e
passou a ser acessado **pela fachada** `mod_intranet.integracoes` — o Blog, as
Filas e a Lista Telefônica **não o importam mais**. Detalhes na seção
"Fonte única do cadastro". A auditoria das próprias ações deste módulo também
segue pelo `audit_log` do núcleo para `db_mod_auditoria.db`
(tabela `tb_auditoria_usuarios`) — ver
[Análise do Módulo Auditoria](analise_mod_auditoria.md#anatomia-da-escrita-na-trilha-25092026).

## Pontos de atenção

- `bd_criador.py` é morto e aponta para o banco central — não executar. **Desde 29/09/2026 `init_db()` levanta `RuntimeError`** (fail-loud, como `mod_edit_pdf/bd_criador.py:21`) e o corpo legado ficou em `_init_db_legado_morto()`: ele tinha um `INSERT` próprio de `master` com senha de fábrica, **segundo caminho de criação** sem a marca que impede a ressurreição.
- `listar_vinculos_orfaos()` existe mas não é chamada pela tela (órfãos aparecem apenas como badge INDISPONÍVEL nos seletores).
- Renomear usuário replica o nome nas tabelas dependentes (`tb_acesso_usuario`), nas sessões centrais abertas e nas autorias dos demais módulos (`_vinculos_cruzados_renomear`).
- **Duplicar usuário** (`duplicar_usuario` + `_dlg_duplicar` em `telas.py`): clona perfil global, papéis por módulo e flags finas da origem (ajustáveis nos seletores antes de salvar).
- **Seed idempotente (fonte única do módulo, `init_db`)**: conta nativa `master` (`administrador_geral`) + contas QA (`qacomum` `comum`, `qamaster` `administrador_geral`); todas com troca forçada no 1º login e auto-cura do `master` a cada boot; `qacomum` reconcilia `ACESSO_PADRAO_NOVO_USUARIO` (`editar_pdf`, `empenhos`, `solicita_impressao` como `comum`; sem `blog`/`usuarios`/`auditoria`). Valores das senhas provisórias não publicados nesta doc (contexto interno em `bd_manipulador.py`).
- **Administração (`/admin/usuarios`, `telas_administracao.py:mostrar_administracao`, só admin geral)**: cupê de cores `bloco_aparencia` (chaves `usuarios_*`) + `usuarios_senha_min` (4–32, padrão 6, via `senha_minima()`, vale sem restart) + `painel_backup`.

## Status — Fases 2 e 2.5 do PLANO.md

**Implementado:** CRUD completo (criar, editar, renomear, bloquear/desbloquear, soft delete, exclusão definitiva LGPD); hash **bcrypt**; múltiplos perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo (`tb_acesso_usuario`); seed da conta de fábrica `master` com troca obrigatória de **usuário e senha** no 1º login (auto-cura idempotente em boot; o seed não recria a conta depois do primeiro acesso — marca `forcar_troca_credenciais:master`); senha provisória (`forcar_troca`); nome completo/social (`user_nome_completo`, Decreto 8.727/2016); exclusão em 2 estágios com motivo; limpeza cruzada LGPD (Blog, editorPDF, empenhos anonimizados; auditoria preservada); proteções (vedado agir sobre a própria conta, `master` não renomeável/excluível); lista paginada (10/20/50/100), busca instantânea em todos os campos + palavras-chave de estado (debounce 150 ms), filtros situação/perfil, ordenação A→Z/numérica e exibição compacta com hover (tooltip com nomes de módulos); alerta de módulos inexistentes (vínculos órfãos como INDISPONÍVEL); gestão/revogação de sessões ativas + histórico; auditoria central LGPD.

**Desvios aceitáveis:** tabela chama-se `tb_usuarios` (não `tb_usuario`); não há tabela `tb_perfil` separada; rota real é `/users` (não `/gestao-usuarios`).

**Proteção do último `administrador_geral` contra bloqueio/rebaixamento por OUTRO admin** (RF-26): `editar_usuario`/`bloquear_usuario` bloqueiam rebaixar ou bloquear o último `administrador_geral` ativo quando o ator é outro admin — **REALIZADO** (`../mod_gest_cad_usuario/bd_manipulador.py`).

## Fase 2.5 — Testes do fluxo completo

A Fase 2.5 do PLANO.md foi **concluída** com scripts standalone em `test/`
(no padrão do projeto, não em `testes/` como o PLANO chegou a citar). Todos
autocontidos (criam usuários de nome único e os removem definitivamente ao
fim — LGPD), sem destruir dados do desenvolvedor:

| Script | Cobertura | Resultado |
|:---|:---|:---|
| `test/teste_boot.py` | Bootstrap cria os bancos do zero + seed `master`; `main.py` importa; Tailwind **local** (sem CDN) + CSS custom no `/login`; HTTP real em `/login` (200 + Tailwind local) quando o servidor está no ar | 16/16 OK |
| `test/teste_fluxo_autenticacao.py` | Login → senha provisória → troca obrigatória no 1º acesso → sessão/logout (revogação) → trilha de auditoria central → soft delete → restauração | 19/19 OK |
| `test/teste_fluxo_permissoes.py` | Concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (auditoria exclusiva) | 13/13 OK |

Os testes refletem o comportamento atual do núcleo:
- **Auditoria** agora é gravada no banco exclusivo `db_mod_auditoria.db` (tabela
  por módulo, ex. `tb_auditoria_blog`), e não mais na `tb_auditoria` central
  (legado migrado via `migrar_dados_existentes`).
- **Senha provisória** é digitada pelo administrador (não gerada aleatória):
  geração aleatória continua **não implementada** — desvio documentado.
- Controle granular é aplicado via `validar_acesso_modulo`/`listar_modulos_permitidos`,
  usados no **menu lateral** (filtro `modulos_do_usuario`, `main.py:251`) e na guarda de
  página `/modulo/{slug}` (`autenticacao.py:421`); o **dashboard `/`** exibe o feed do
  Blog e o **Resumo do sistema** apenas para administradores (geral/de módulo, `main.py:254`).

### Adições recentes (05/09)

Oito melhorias na tela de usuários (`mod_gest_cad_usuario/telas.py`), todas na aba **Usuários** e no diálogo de edição:

1. **Botão "Salvar alterações" no diálogo de edição** — `_dlg_editar` definia a função `salvar()` internamente, mas nunca a conectava a um botão. Adicionada linha de ações com "Cancelar" (flat) + "Salvar alterações" (primário, ícone `save`) (`telas.py:621-624`), seguindo o padrão dos diálogos Novo/Duplicar.

2. **Busca em qualquer campo** — A função `_filtrar` agora pesquisa em **todos** os campos do registro: ID numérico, login, perfil global, e-mail, telefone, string módulos:papel e nome completo/tratamento (`telas.py:236-244`). O placeholder e o tooltip do campo de busca foram atualizados para refletir a abrangência (`telas.py:108-112`).

3. **Ordenação alfabética ou numérica** — Seletor "Ordenar por" (`ORDEM_OPCOES`) na barra de filtros, com opções `A→Z (nome)` e `Numérica (ID)` (`telas.py:195`, `telas.py:282-284`). A função `_chave_ordenacao` ordena por nome de tratamento/login (alfabética, via `_norm` que ignora acentos) ou por ID (`telas.py:197-203`). Limpar filtros restaura `nome` como ordem padrão (`telas.py:286`). A ordenação é aplicada no final de `_filtrar` (`telas.py:253`).

4. **Exibição compacta** — A tabela encolheu de 8 colunas para 4: `[ID][Tratamento][Senha provisória][Ações]`, com grid `60px 1fr 150px 220px` (`telas.py:310-311`). Os demais campos (login @, perfil global, situação, e-mail, telefone, cadastro, módulos:papel) são expostos em tooltip ao passar o mouse no nome de tratamento, com ícone `info_outline` como dica visual (`telas.py:329-360`).

5. **Nomes de módulos no tooltip** — Os acessos do usuário no tooltip exibem o **nome de exibição** do módulo (via `_nomes_modulos()`, que usa `autenticacao.modulos_registrados()` com cache lazy em `_MAP_MODULOS`) ao invés da chave bruta (ex. `blog` em vez de `blog:comum`). Cada linha de acesso exibe ícone do módulo + nome + badge do papel usando `ROTULOS_PAPEL` ("Comum"/"Administrador") (`telas.py:25-34`, `telas.py:346-358`).

6. **Busca por palavras-chave de estado** — Digitar "provisório" ("provisor"), "bloqueado" ("bloque"), "sessão" ("sess") ou "excluído" ("exclu") filtra pelos estados computados: senha provisória pendente (`autenticacao.usuarios_com_troca_pendente()`), bloqueado (`user_ativo=0`), sessão ativa (`gest.sessoes_ativas_por_usuario()`) e excluído (`user_deletado=1`). As consultas extras (troca pendente, sessões) só rodam quando um token de estado está presente, evitando custo desnecessário (`telas.py:213-234`).

7. **Busca "excluído" revela excluídos + aba Excluídos removida** — Quando o termo de busca contém "exclu", a base do filtro em `_filtrar` inclui soft-deleted (`user_deletado=1`), fazendo-os aparecer na aba Usuários (`telas.py:207-211`). Como isso tornou essa aba redundante, a aba "Excluídos" foi **removida do menu** (agora são 3 abas: Usuários | Sessões Ativas | Administração). Nas linhas de excluídos que aparecem na busca, o botão de exclusão é o permanente (`delete_forever`, `_dlg_excluir_definitivo`) com aviso LGPD, mantendo também "Restaurar conta" (`telas.py:396-405`).

8. **Tabulação consistente** — O grid da tabela mudou de `60px 1fr auto` (implícito) para `60px 1fr 150px 220px` tanto no cabeçalho quanto nas linhas (`telas.py:311`, `telas.py:325`). O badge "senha provisória" virou coluna própria ao invés de ficar embutido na coluna situação, alinhando as ações de todas as linhas à mesma posição horizontal (`telas.py:362-368`).

### Adições recentes (26/08)

- **Aba "Administração"** (exclusiva do admin geral, nas tabs existentes): bloco **Aparência** (prefixo usuarios_* — cor do botão/texto, fundo da página, cor do título, tamanho via ui.color_input; a cor do botão também define a primária da tela) e **config específica**: usuarios_senha_min (política de senha mínima, aplicada em criar_usuario/alterar_senha_admin via senha_minima()). Salvo via set_config, vale sem reiniciar.
- **Versionamento**: versao_modulo:usuarios = 1.0.260929 (seed em bd_conexao.init_db() + migrações `migracao_versao_usuarios_260918`, `_260929` e `_260929_seg` — a última é o bump da correção de segurança do seed de `master`, com marcador **próprio** por ser a 2ª entrega do dia), exibido no rodapé em /users (rota → chave usuarios).
- **Edição do módulo** (`campo_modulo` do helper `mod_intranet/tema_modulo.py`) — **RESTAURADO (06/09)**: após remoção acidental (regressão), o cupê voltou a aparecer na aba Administração — editar **nome de exibição, ícone e status (ativo/inativo)** do módulo (`mod_gest_cad_usuario/telas.py:705`); a edição também permanece no painel central `/configuracoes` (aba Módulo, admin geral).

### Adições recentes (06/09)

- **Aba Administração padronizada em cupês** (`telas.py:663`, `_painel_administracao`): o card/rodapé crus de aparência deram lugar ao cupê padrão **`tema_modulo.bloco_aparencia`** — 6 chaves de tema `usuarios_*` com **padrão do próprio módulo quando vazias** (`PADROES_TEMA["usuarios"]` = `#000000` — sem herança do tema do sistema); "Restaurar padrão" agora funciona via `tema["_defaults"]` (grava `""` nos campos de botão para voltar ao padrão do próprio módulo). O card **"Configurações específicas"** mantém o tamanho mínimo da senha (`usuarios_senha_min`, 4–32, padrão 6) e usa o rodapé padronizado **`ui_comum.rodape_salvar_restaurar`** (`telas.py:738`).
- **Cor do cabeçalho segue o tema** (`telas.py:100`): `cor_borda` usa `tema["cor_botao"]` resolvido (antes `#00838F` fixo), usando o padrão do próprio módulo quando a chave `usuarios_cor_botao` está vazia (`PADROES_TEMA["usuarios"]` = `#000000`).
- **Labels de senha dinâmicos** (`telas.py:549`, `telas.py:753`, `telas.py:892`): os diálogos de novo usuário (`_dlg_novo`), redefinir (`_dlg_senha`) e duplicar (`_dlg_duplicar`) exibem "mín. X" com `gest.senha_minima()` (chave `usuarios_senha_min`) em vez do "mín. 6" fixo.
- **Import atualizado** (`telas.py:28-31`): `btn_style` removido; `bloco_aparencia`, `rodape_salvar_restaurar` e `campo_modulo` importados de `mod_intranet.tema_modulo` (`campo_modulo` restaurado em 06/09 após remoção acidental).
- Cobertura: `test/verifica_ui_comum.py` — verificação **"gest_cad: painel adm via cupês padrão (bloco_aparencia + rodapé + campo_modulo)"** (`verifica_ui_comum.py:968-969`); suíte completa: **179 OK, 0 falhas**. Demais suítes: dashboard 31, config 50, boot 16, autenticação 19, permissões 13.

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Barra superior** `flex-nowrap` → `flex-wrap`, tabs `overflow-x-auto`, busca `flex-1 min-w` (`campo_busca` `grow min-w-[220px]`), dialogs `w-full max-w` — validado 320/768/1024 (`kbp-web-design`). Tabelas com `overflow-x-auto` (parcial). Proposta P0/P1/P2 por `container`/`row`/`grid` (header `flex-wrap` `truncate`, filtros `sm:grid-cols-2`) registrada na auditoria.

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| gest_cad_usuario | Sem `CrudBase` completo; `sqlite_master` em seed/migração; `GROUP_CONCAT` agregado | `mod_gest_cad_usuario/bd_manipulador.py:146`, `:181` (`sqlite_master`) · `:301-315` (`GROUP_CONCAT`) | Migrar para `CrudBase` + `conexao("usuarios")`; `_tabela_existe()` interno; manter `GROUP_CONCAT` (proxy traduz para `STRING_AGG`, só teste paridade) | Médio (seed `master`/`qacomum`/`qamaster` + troca forçada) |

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).

## Correção aplicada 24/09/2026 — WAL + paridade SQLite↔PostgreSQL

> EN: Fix applied 24/09/2026 in `mod_gest_cad_usuario/bd_manipulador.py` (code already patched, docs-only batch): uniqueness/retry helpers, full GROUP BY, FK per active SGBD, orphan cleanup, preserved seeds; tests 19/19 + 13/13 + 20/20, verdict PASS.

> Correção aplicada em 24/09/2026 em `mod_gest_cad_usuario/bd_manipulador.py` (código já corrigido, lote só-documentação): helpers de unicidade/retry, GROUP BY completo, FK por SGBD ativo, limpeza de órfãos, seeds preservados; testes 19/19 + 13/13 + 20/20, veredito APROVADO.

| Tema | Antes (pendência 24/09) | Depois (correção aplicada) — arquivo:linha |
|:---|:---|:---|
| Helpers unicidade/retry | Sem `CrudBase` completo; `database is locked` sem retry; `IntegrityError` genérico | `_eh_violacao_unicidade` (`bd_manipulador.py:47`) — `UNIQUE`/`duplicate key`/`23505` SQLite↔PG sem importar `sqlite3`/`psycopg2`; `_eh_bloqueio_banco` (`:71`); `_rollback_seguro` (`:79`, fail-soft AGENTS §3.2); `_commit_com_retry` (`:91`, 3 tentativas c/ backoff, `busy_timeout=5000` herdado de `banco_conexao.conexao`); `_conexao_segura` (`:121`, fail-soft → `None`); uso em `criar_usuario` (`:596,602-608`), `renomear_usuario` (`:726,740-746`), `editar/definir/excluir` |
| `GROUP BY` completo | `GROUP_CONCAT` agregado sem GROUP BY completo (quebra no PG) | `listar_usuarios` (`bd_manipulador.py:438`) — `GROUP_CONCAT(a.modulo_chave \|\| ':' \|\| a.papel)` (`:455`, proxy traduz → `STRING_AGG` no PG) + `GROUP BY` com todas as colunas não agregadas (`:464-466`) + `ORDER BY u.user_nome`; `_normalizar_data` (`:425`) normaliza `datetime` PG → string |
| FK por `sgbd_ativo` | `sqlite_master` em seed/migração; `ON UPDATE CASCADE` assumido nos dois backends | `_init_db_seguro` (`bd_manipulador.py:189`); ramo `sgbd_ativo()` (`:238-264`): SQLite reinspeciona `sqlite_master` e faz rebuild p/ `ON DELETE/UPDATE CASCADE`; PG só marca `PRAGMA table_info` (proxy → `information_schema`) e delega integridade à aplicação (UPDATE manual nas duas tabelas em `renomear_usuario` `:718-719`); `flags` via check-then-add portável (`:268-272`) |
| Limpeza de órfãos | Sem tratamento PG (FK removida pelo `_ddl_postgres` do núcleo) | `renomear_usuario` (`bd_manipulador.py:690`) — `DELETE FROM tb_acesso_usuario WHERE user_nome NOT IN (SELECT user_nome FROM tb_usuarios)` (`:723`, best-effort c/ `warning`); `definir_acesso` usa upsert `ON CONFLICT(user_nome, modulo_chave) DO UPDATE` (`:1037-1044`, portável PG) |
| Seeds preservados | Risco regressão: seed `master`/`qacomum`/`qamaster` + troca forçada | Preservados idempotentes: `ACESSO_PADRAO_NOVO_USUARIO` (`:23` = `editar_pdf`, `empenhos`, `solicita_impressao`); auto-cura `master` (`:343-350`); seed `master` (`:353-373`); seed/reconciliação `qacomum` (`:382-404`, remove `blog@sistema` legado) + `qamaster` (`:405-411`); `marcar_trocar_senha/credenciais` mantidos (AGENTS §8.2) |

### Testes e veredito

| Suíte | Resultado |
|:---|:---|
| `assets/test/teste_fluxo_autenticacao.py` (login → troca 1º acesso → sessão/logout → auditoria → soft delete → restauração) | 19/19 OK |
| `assets/test/teste_fluxo_permissoes.py` (concessão/atualização/revogação por módulo + auditoria exclusiva) | 13/13 OK |
| `assets/test/teste_flags_permissao.py` (catálogo `FLAGS_PERMISSAO`, grant/revoke em `qacomum@blog`, bypass admin, decorador `requer_flag`) | 20/20 OK |

**Veredito: APROVADO — sem regressão.** Pendência WAL+paridade do `gest_cad_usuario` (linha da tabela acima) considerada **superada**; demais módulos do plano permanecem pendentes conforme o arquivo consolidado.

---

# RF e RNF verificados no código — lote 1 (26/09/2026)

> Auditoria de requisitos **funcionais** (o que o sistema faz) e **não
> funcionais** (qualidade e restrições), com evidência `arquivo:linha` conferida
> no código em 26/09/2026.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-GEST-01 | Tela da Gestão de Usuários só para `administrador_geral` **ou** admin do módulo `usuarios` | `telas.py:85-87`; negação em `telas.py:154-161` `_acesso_negado` |
| RF-GEST-02 | **Soft CRUD**: criar, editar, bloquear/desbloquear, excluir lógico, duplicar e excluir definitivo | `telas.py:73` `_mostrar_tela_segura` → `_painel_usuarios` (`:233`), `_dlg_novo` (`:623`), `_dlg_editar` (`:712`), `_dlg_duplicar` (`:974`), `_dlg_excluir` (`:857`), `_dlg_excluir_definitivo` (`:914`); backend em `bd_manipulador.py:558`, `:613`, `:782`, `:819`, `:920`, `:977` |
| RF-GEST-03 | Coluna de ex soft-delete (`user_deletado`) + aba **1.5 Excluídos** com restauração/duplicação | `bd_manipulador.py:306-308` (migração da coluna) + `telas.py:972` |
| RF-GEST-04 | **Motivo de exclusão lógica** registrado no momento da exclusão | `bd_manipulador.py:319-321` (migração `user_motivo_exclusao`) + `soft_delete_usuario(..., motivo)` em `bd_manipulador.py:819` |
| RF-GEST-05 | Senha **provisória** obrigatória:_hash bcrypt_, troca forçada no 1º acesso | `bd_manipulador.py:558-611` `criar_usuario` (valida `senha_minima()`, grava `gerar_hash_senha`, chama `marcar_trocar_senha(..., True)`); `mod_intranet/autenticacao.py:447` |
| RF-GEST-06 | Tamanho mínimo da senha **configurável** (clamp 4–32, default 6), aplicado sem restart | `bd_manipulador.py:159-172` `senha_minima`; painel em `telas_administracao.py:78-122` |
| RF-GEST-07 | `administrador_geral` **não pode rebaixar nem bloquear o último** admin geral ativo (RF-26) | `bd_manipulador.py:626-640` (dentro de `editar_usuario`) |
| RF-GEST-08 | Nome de exibição / nome social (Decreto 8.727/2016) separado do login, com `nome_de_tratamento` | `bd_manipulador.py:309-315` (migração) + `:507-519` `nome_de_tratamento` |
| RF-GEST-09 | **Papel por módulo** (`tb_acesso_usuario.papel`): conceder, remover, consultar, validar | `bd_manipulador.py:1022-1055` `definir_acesso`, `:1057-1076` `remover_acesso`, `:1078-1102` `obter_papel_no_modulo`, `:1104-1119` `validar_acesso_modulo` |
| RF-GEST-10 | **Flags finas** de permissão por módulo (JSON em `tb_acesso_usuario.flags`) com whitelist de flags válidas | `bd_manipulador.py:1130-1143` `_flags_validas`, `:1145-1173` `obter_flags`, `:1175-1206` `definir_flags`, `:1208-1219` `tem_flag`; migração em `:266-272` |
| RF-GEST-11 | **Sessões ativas** listadas, contadas, agrupadas por usuário, com histórico e encerramento (individual ou todas) | `bd_manipulador.py:1234-1261`, `:1263-1280`, `:1282-1299`, `:1301-1327`, `:1329-1352` `encerrar_sessao`, `:1354-1363` `encerrar_todas_sessoes`; UI em `telas.py:1074` `_painel_sessoes` + `telas.py:510`/`525` diálogo |
| RF-GEST-12 | Sessão revogável: o `pagina_restrita` do núcleo revalida sessão e `user_ativo` **a cada request** | `mod_intranet/telas.py:74-93` (corta sessão e manda pro `/login`) |
| RF-GEST-13 | Renomear usuário propaga para **todos** os módulos (única limpeza cruzada de negócio→negócio autorizada) | `bd_manipulador.py:690-749` `renomear_usuario` + `:895-918` `_vinculos_cruzados_renomear` (filhos antes dos pais) |
| RF-GEST-14 | Excluir definitivamente remove os vínculos dos outros módulos antes dos próprios | `bd_manipulador.py:920-975` + `:857-893` `_vinculos_cruzados_excluir` |
| RF-GEST-15 | Detecção de **vínculos órfãos** (módulos que ainda referenciam o usuário) | `bd_manipulador.py:1367-1385` `listar_vinculos_orfaos` |
| RF-GEST-16 | Recusa de duplicidade de nome com mensagem amigável (não stack trace) | `bd_manipulador.py:47-69` `_eh_violacao_unicidade` + `:601-604` (`"Nome de usuário já existe"`) |
| RF-GEST-17 | Redesenhar senha pelo admin (`alterar_senha_admin`) com troca forçada | `bd_manipulador.py:751-780`; UI em `telas.py:814`/`830` |
| RF-GEST-18 | Fonte única do cadastro: os módulos consomem o Gestor por `mod_intranet/integracoes.py` (fachada), nunca import direto | `mod_intranet/integracoes.py:32-61` `obter_usuario_gestao` / `listar_usuarios_gestao`; `mod_intranet/autenticacao.py:292-294` `_gest()` |
| RF-GEST-19 | Seed idempotente `master` / `qacomum` / `qamaster` (AGENTS.md §8.2) com troca de senha e de credenciais forçada no 1º login | `bd_manipulador.py:339-420` (auto-cura do `master` em `:343-350`; `master` em `:353-373`; `qacomum`/`qamaster` em `:375-420`) |
| RF-GEST-20 | Reconciliação idempotente do `qacomum` (garante os 3 acessos comuns e remove o `blog` legado concedido por `sistema`, preservando concessão manual do admin) | `bd_manipulador.py:394-404` |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-GEST-PERS-01 | Banco próprio `db_mod_gest_cad_usuario.db` via `banco_conexao.conexao("gest_cad_usuario")` | `bd_manipulador.py:26-45` `get_connection` |
| RNF-GEST-PERS-02 | `PRAGMA journal_mode=WAL` + `foreign_keys=ON`; `busy_timeout=5000`/`synchronous=NORMAL` herdados do núcleo | `bd_manipulador.py:39-40`; docstring em `:31` |
| RNF-GEST-PERS-03 | **Retry 3×** em `database is locked` com rollback seguro, em **toda** transação de escrita | `bd_manipulador.py:91-119` `_commit_com_retry` + `:71-77` `_eh_bloqueio_banco` + `:79-89` `_rollback_seguro`; ex. `:228`, `:299`, `:362`, `:392` |
| RNF-GEST-PERS-04 | `init_db` **import-safe**: nunca levanta no import, erro só vai para o log | `bd_manipulador.py:174-187` `init_db` → `:189` `_init_db_seguro` (re-levanta para o chamador) com `finally` sempre fechando a conexão (`:332-337`) |
| RNF-GEST-PERS-05 | FK com `ON UPDATE CASCADE` para renomeio, reconstruída de forma **idempotente e só no SQLite** | `bd_manipulador.py:237-264` (guarda `sgbd_ativo() != "postgres"`, detecta ausência de `ON UPDATE` em `sqlite_master`, rebuild em 4 passos) |
| RNF-GEST-COMP-01 | Paridade SQLite ↔ PostgreSQL | DDL só `IF NOT EXISTS` (`:204-227`); migrações por **check-then-add** com `PRAGMA table_info` traduzido para `information_schema` no proxy (`:268`, `:304`, `:310`, `:317`); `INSERT OR IGNORE` traduzido; no PG a integridade da FK é gerida na aplicação (UPDATE manual em `renomear_usuario` + limpeza de órfãos) — comentário explícito em `:230-236` |
| RNF-GEST-SEG-01 | Senhas **nunca** em texto puro: só hash bcrypt | `bd_manipulador.py:360`, `:385`, `:408` (`gerar_hash_senha`); nenhuma coluna `user_senha` em claro |
| RNF-GEST-SEG-02 | Autorização de escrita auditada com ator + detalhe (perfil, nome de exibição) | `bd_manipulador.py:143-151` `_audit` → `tb_auditoria_gest_cad_usuario`; ex. `:600` `criar_usuario` |
| RNF-GEST-SEG-03 | **Isolamento de banco**: o módulo só toca o próprio `db_mod_gest_cad_usuario.db`; o acesso ao BD central é **exclusivamente de leitura** e só na migração do legado | `bd_manipulador.py:133-141` `_central()`; única leitura em `:280-301` (migração única) |
| RNF-GEST-SEG-04 | Sem `cross-query` entre bancos de negócio: a propagação para outros módulos é por **API pública** de cada módulo | `bd_manipulador.py:857-893` e `:895-918` chamam `remover_vinculos_usuario`/`renomear_usuario` de cada `mod_*` |
| RNF-GEST-RES-01 | `try/except` obrigatório em função, com retorno `(ok, msg)` + `log` — a UI sempre tem o que notificar | 100 % das funções de escrita retornam tupla; ex. `:573-577` (falha de conexão), `:601-604` (duplicidade), `:605-609` (erro inesperado) |
| RNF-GEST-RES-02 | **Fail-soft** nas leituras: `obter_papel_no_modulo`/`validar_acesso_modulo` devolvem `None`/`False` em exceção (nunca levantam), então uma falha de permissão **fecha** o acesso em vez de abrir | `bd_manipulador.py:1104-1119`, e o espelho no núcleo `mod_intranet/autenticacao.py:604-609`, `:629-633` |
| RNF-GEST-RES-03 | Toda tela/dialogo tem wrapper `*_seguro` com notificação de erro (fail-soft de UI) | `telas.py:73`, `:525`, `:639`, `:729`, `:830`, `:874`, `:931`, `:990`; `telas_administracao.py:53` |
| RNF-GEST-RES-04 | Sem `ui.notify` cru: só `tema_modulo.notificar` (respeita `notificacao_timeout`) | `grep ui.notify` → 0 ocorrências em `mod_gest_cad_usuario/*.py` |
| RNF-GEST-UX-01 | `data-testid` nas ações de QA | `telas.py:141` (`usuarios-busca`), `:145` (`usuarios-novo`), `:345` (`usuarios-filtro-situacao`) |
| RNF-GEST-I18N-01 | Docstrings bilíngue EN (topo) / PT-BR (abaixo) | `telas.py:1-4` (EN no topo), `telas_administracao.py:1-15` (bloco EN no **meio/fim**, não no topo — ver DIV-GEST-02), `bd_manipulador.py:1-24` |
| RNF-GEST-I18N-02 | Toda a UI em PT-BR, com mensagens de erro operacionais (não stack traces) | `bd_manipulador.py:572-609`, `telas.py:154-161` |
| RNF-GEST-PERF-01 | Consultas de lista **paginate/limitadas** e sem N+1 no painel de sessões | `bd_manipulador.py:438-480` `listar_usuarios` (1 consulta) + `:1234-1261` (1 consulta) |
| RNF-GEST-PERF-02 | `_conexao_segura()` evita abrir conexão quando a anterior está sob lock | `bd_manipulador.py:121-131` |
| RNF-GEST-RESP-01 | Responsividade com `flex-wrap` e `min-w` nos campos | `telas.py:165-206` (`_seletores_de_acesso`) |

## Divergências e riscos

### Código faz, doc não diz

| # | Achado | Evidência |
|:---|:---|:---|
| DIV-GEST-01 | `_vinculos_cruzados_excluir`/`_vinculos_cruzados_renomear` tocam os módulos **por lista explícita de funções importadas** — a lista de módulos participantes está hardcoded no arquivo. Um módulo novo que guarde `user_nome` **não** entra na propagação sem editar este arquivo. | `bd_manipulador.py:857-918` |
| DIV-GEST-02 | `telas_administracao.py` põe o bloco **EN depois** do PT-BR (linhas 11-14), contrariando o padrão "EN no topo" do AGENTS.md | `telas_administracao.py:1-15` |
| DIV-GEST-03 | `validar_acesso_modulo_compat` existe como **alias de compatibilidade** (`bd_manipulador.py:1387-1395`) e é usada por `mod_intranet/autenticacao.py:607-631` — a doc não registra essa camada de indireção | `bd_manipulador.py:1387-1400` |
| DIV-GEST-04 | A migração do legado lê `sqlite_master` da tabela `tb_usuarios` **no banco central** — se `banco_tipo=postgres`, o proxy devolve vazio e a migração é pulada silenciosamente (há `finally` fechando, mas sem `log` explícito do pulo) | `bd_manipulador.py:283-284` |

### Doc diz, código não faz

| # | Alegação da doc | Estado real |
|:---|:---|:---|
| DIV-GEST-05 | "`telas_administracao.mostrar_administracao` — **exclusivo do admin geral**" (docstring em `telas_administracao.py:3-4` e `:14`) | A função **não recebe nem checa perfil** (`telas_administracao.py:30`). O gate real é só a rota: `main.py:1031-1037` chama `pagina_restrita(nome_modulo, chave_modulo="usuarios")`, que exige **acesso ao módulo** — não papel de admin. Ver RISCO-GEST-01. |
| DIV-GEST-06 | Doc sugere que "admin do módulo" e "admin geral" são equivalentes para a aba Administração | Não são: a tela de negócio (`telas.py:85-87`) aceita os dois; o painel `/admin/usuarios` aceita **qualquer** um dos dois, **e também um `comum` com acesso ao módulo**. |

### Riscos

| # | Risco | Severidade | Evidência |
|:---|:---|:---|:---|
| **RISCO-GEST-01** | **`/admin/usuarios` sem gate de administrador.** `main.py:1031-1037` chama `mostrar_administracao(nome)` sem o flag `eh_admin` (ao contrário de `auditoria` e `solicita_impressao`, que o recebem). Efeito: um usuário `comum` com liberação do módulo `usuarios` **altera `usuarios_senha_min` (4–32) e o tema** e vê o painel de backup. Alterar o tamanho mínimo da senha é uma mudança de política de segurança de contas. | 🔴 Alta | `main.py:1031-1037` + `mod_gest_cad_usuario/telas_administracao.py:30` + `:84-102` |
| **RISCO-GEST-02** | **Zero `async` / `run.io_bound` / `ui.spinner`** no módulo (0 ocorrências). Todos os handlers são `def` síncrono e fazem I/O de banco (`criar_usuario`, `editar_usuario`, `renomear_usuario`, `excluir_usuario_definitivo`, `encerrar_todas_sessoes`, `duplicar_usuario`) diretamente no event-loop. some walks sobre nomes de usuário + dezenas de `UPDATE`s cross-módulo no caso de `renomear_usuario`/`excluir_usuario_definitivo`. Viola AGENTS.md §5.1. | 🟠 Média | ausência de `async def` em `mod_gest_cad_usuario/*.py` |
| **RISCO-GEST-03** | `except Exception: pass` engole erro **em silêncio** em pontos de migração, contrariando AGENTS.md §3.2 ("SEMPRE registre/logue a causa"). | 🟡 Baixa | `bd_manipulador.py:220-221`, `:242-243` (blocos de migração de `limite`/`cota` com `except Exception: pass`, sem `log`) |
| **RISCO-GEST-04** | `modulo_acesso TEXT` (coluna CSV legada) permanece em `tb_usuarios` e continua sendo lido/escrito, ao mesmo tempo que `tb_acesso_usuario` é a fonte de verdade. Duas fontes para a mesma informação. | 🟡 Baixa | `bd_manipulador.py:214` (DDL) + `:285-298` (migração converte CSV→linhas, mas não zera a coluna) |
| **RISCO-GEST-05** | Sem `CrudBase`: SQL cru com `conn.cursor()`. A atomicidade depende de `_commit_com_retry` manual, e a propagação cross-módulo (RF-GEST-13/14) **não é transacional** — se o módulo 3 de 8 falhar, os 2 anteriores já foram alterados e não há compensação. | 🟠 Média | `bd_manipulador.py:690-749` e `:920-975` |
