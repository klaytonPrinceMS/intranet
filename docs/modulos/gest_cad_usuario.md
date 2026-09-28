# User Management Module — `mod_gest_cad_usuario`

> User management module: route `/users` (key `usuarios`) · own database `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, multi-profile/role, revocable sessions, cross-module LGPD cleanup · **the single user registry, consumed by other modules through the `mod_intranet/integracoes.py` facade (never a direct import)**.

---

# Módulo Gestão de Usuários — `mod_gest_cad_usuario`

> Módulo de gestão de usuários: rota `/users` (chave `usuarios`) · banco próprio `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, múltiplos perfis/papéis, sessões revogáveis, limpeza cruzada LGPD · **fonte única do cadastro, consumida pelos demais módulos pela fachada `mod_intranet/integracoes.py`**.

## Propósito

Soft CRUD completo de usuários: criar, editar, renomear, bloquear/desbloquear, excluir logicamente (com motivo) e excluir permanentemente (LGPD). Gerencia perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo, além de visualizar/revogar sessões ativas de todo o sistema. Acesso restrito ao administrador geral ou administrador do módulo `usuarios`.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:188` (executado no import e pelo bootstrap central).

- **`tb_usuarios`**: `id` PK AUTOINCREMENT, `user_nome` UNIQUE, `user_senha` (bcrypt), `user_email`, `user_fone`, `user_perfil`, `user_ativo`, `data_cadastro`, `user_deletado`, `user_nome_completo` (nome social, Decreto 8.727/2016), `user_motivo_exclusao`, e — desde 27/09/2026 — os **dados funcionais públicos** **`unidade`**, **`lotacao`** e **`cargo`**, a pendência **`telefone_pendente`** e a **liberação temporária** **`acesso_provisorio`** + **`provisorio_ate`** (`ALTER TABLE` guardado por `PRAGMA table_info`, idempotente; `bd_manipulador.py:291-307`). `matricula` não é coluna: o próprio **`user_nome` é a matrícula**. Ver as tabelas detalhadas abaixo.
- **`tb_acesso_usuario`** — vínculo usuário×módulo×papel (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE para `tb_usuarios`); `modulo_chave` é texto livre — origem dos vínculos órfãos (ver `listar_vinculos_orfaos(chaves_ativas)`; na tela aparecem como badge `INDISPONÍVEL` nos seletores). Coluna `flags` (JSON TEXT, default `'{}'`) guarda permissões finas por vínculo.
- **`tb_telefone_usuario`** (27/09/2026, DDL em `bd_manipulador.py:250-262`) — **telefone múltiplo por usuário**, que antes não cabia (só havia `tb_usuarios.user_fone`, um número): `id` PK, `user_nome` FK CASCADE, `numero`, **`papel`** (`empresa`|`pessoal`, default `empresa`), **`tipo`** (`celular`|`fixo`, default `celular`), **`principal`** (0/1, um por usuário), **`visivel`** (0/1, default 0 — o **consentimento** de exibição), **`recado`** (0/1, default 0 — o número é o **do setor**, a pessoa deixa recado) e `data_cadastro`. API: `telefone_e_publicavel` (`:615`), `telefone_de_recado` (`:641`), `telefone_e_recado` (`:654`), `telefones_de_recado_em_lote` (`:672`), `listar_telefones` (`:707`), `telefone_empresa_principal` (`:738`), `telefones_publicaveis_em_lote` (`:752`), `adicionar_telefone` (`:795`), `editar_telefone` (`:845`), `remover_telefone` (`:898`), `registrar_contatos_primeiro_acesso` (`:1023`), `telefone_pendente` (`:934`), com os validadores `_validar_papel` (`:599`) e `_validar_tipo` (`:609`). `principal=True` desmarca os outros, para só haver um principal por vez; papel desconhecido cai em `empresa` de propósito (o caminho seguro é o número ser publicável).

!!! warning "`listar_telefones` passou a devolver **9 campos** — `recado` no índice 7 (27/09/2026)"
    A tupla é agora `(id, user_nome, numero, papel, tipo, principal, visivel,
    **recado**, data_cadastro)`. O `recado` **entrou no índice 7** e
    **empurrou `data_cadastro` do 7 para o 8**. Quem lia `linha[7]` esperando
    a data recebe o `recado` — e quem lia `linha[2]` (o número) continua
    certo, porque o `recado` entrou **depois** de `principal`/`visivel`.
    Leitores por índice no projeto: `telefone_empresa_principal` (`:748`,
    `t[5]`=principal, `t[2]`=número) e `telefone_e_recado` (`:669`, `t[7]`
    com guarda de tamanho). Leitores por posição **fixa** de fora do módulo
    não existem — a ponte `leitura_lista.py` devolve **dicionários** justamente
    para isso.

### Colunas novas em `tb_usuarios` (27/09/2026)

| Coluna | Tipo | Default | Para quê |
|:---|:---|:---:|:---|
| `unidade` | `TEXT` | `''` | Secretaria / unidade organizacional do servidor — dado funcional **público** |
| `lotacao` | `TEXT` | `''` | Departamento dentro da unidade; quando repete a unidade (servidor ligado direto na secretaria, sem departamento), fica vazia |
| `cargo` | `TEXT` | `''` | Função exercida |
| `telefone_pendente` | `INTEGER NOT NULL` | `0` | `1` = o servidor ainda precisa registrar os telefones |
| `acesso_provisorio` | `INTEGER NOT NULL` | `0` | `1` = a conta entrou pelo **paliativo** e está no prazo de `DIAS_LIBERACAO_PROVISORIA` (4 dias) |
| `provisorio_ate` | `DATETIME` | `NULL` | **Quando** o prazo vence. Precisa existir separada do `acesso_provisorio`: só o flag não guarda o *quando*, e sem o *quando* não há prazo a fiscalizar |

As seis entram por `ALTER TABLE … ADD COLUMN` guardado por `PRAGMA table_info` (`bd_manipulador.py:291-307`) — **idempotente**, e portátil: o proxy `banco_conexao` traduz o `PRAGMA table_info` para `information_schema` no PostgreSQL.

`matricula` **não** entrou como coluna: o próprio `user_nome` **é** a matrícula. É o que o servidor reconhece na tela de login e o que o cartão do diretório mostra como `@user_nome`.

### A regra de consentimento do telefone — `telefone_e_publicavel`

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
| **Fixo da prefeitura** (`empresa`/`fixo`) | **SEMPRE** | Linha institucional: existe para ser achada. É o número que a prefeitura divulga em visita de rotina e em edital |
| **Celular da prefeitura** (`empresa`/`celular`) | **só se o servidor marcar** `visivel` | Quem atende é a pessoa, a qualquer hora. O responsável pela defesa civil precisa aparecer para todos; o prefeito, não. É consentimento, não configuração do sistema |
| **Celular particular** (`pessoal`/`celular`) | **NUNCA** | O prefeito pode não querer o número publicado |
| **Residencial** (`pessoal`/`fixo`) | **NUNCA** | Telefone de casa não entra em cadastro de servidor |

O corpo da função tem três linhas: `papel='pessoal'` ⇒ `False`; `tipo='fixo'` ⇒ `True`; senão ⇒ `bool(visivel)`. `visivel` tem **default 0** na tabela: a publicação é sempre uma decisão, nunca um efeito colateral de gravar o número.

!!! warning "`papel`/`tipo` corrompidos caem no lado **seguro**"
    `_validar_papel` devolve `empresa` para um papel desconhecido e
    `_validar_tipo` devolve `celular` para um tipo desconhecido
    (`bd_manipulador.py:567-581`). O par resultante é `empresa`/`celular`,
    que **exige consentimento explícito**. Dado corrompido nunca vira
    publicação automática.

!!! note "`apenas_empresa=True` filtra por `telefone_e_publicavel`"
    `listar_telefones(user_nome, apenas_empresa=True)` (`:707`) filtra em
    **Python**, não em `SQL WHERE papel='empresa'` — as duas coisas não são
    equivalentes (`empresa`/`celular` com `visivel=0` passaria pelo `WHERE`).
    Filtrar em Python também evita divergência entre backends.

### Telefone de recado — o número é do **setor**, não da pessoa

> **EN:** A server with no own line gives the **sector's** number: the waste
> collection one is the garage's, the school lunch one is the school
> secretary's. `recado` on `tb_telefone_usuario` says so, and the phone
> directory writes "deixe recado" under the number. Without the flag the
> sector's number enters the directory looking like a personal line of
> someone who never answers — and the person is discounted because of it.
>
> **PT-BR:** Quem não tem linha própria dá o telefone do **setor**: o da
> coleta de lixo é o da garagem, o da merenda escolar é o da secretaria da
> escola. A coluna `recado` em `tb_telefone_usuario` diz isso, e a lista
> telefônica escreve "deixe recado" abaixo do número. Sem a marcação, o
> número do setor entra parecendo linha pessoal de quem não atende — e a
> pessoa é desconsiderada por isso.

`recado` é um dado **de consentimento por linha**, não um papel novo: ele não muda
se o número publica (`telefone_e_publicavel` continua mandando), muda **o que está
escrito ao lado**. Por isso ele mora na tabela de telefones e não em `tb_usuarios`:
um servidor pode ter o fixo próprio **e** o do setor como recado, e cada um
responde a uma pergunta diferente.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `recado INTEGER NOT NULL DEFAULT 0` | `bd_manipulador.py:259` (DDL) · `:280-282` (`ALTER TABLE` guardado por `PRAGMA table_info`) | A marcação. Entra no `CREATE TABLE` e na migração idempotente — banco novo e banco antigo recebem a mesma coluna |
| `telefone_de_recado(numero, papel, tipo)` | `bd_manipulador.py:641` | Decide se **aquele** telefone é do setor. Delega a `_eh_telefone_da_prefeitura` (`:964`) — só `empresa`/`fixo` conta, porque o recado é o telefone de um **setor**, e setor tem linha fixa |
| `telefone_e_recado(user_nome)` | `bd_manipulador.py:654` | O telefone que a lista telefônica **vai mostrar** é um recado? Olha o publicável marcado `principal` (ou o primeiro) e devolve o `recado` dele — índice 7 da tupla de 9 campos |
| `telefones_de_recado_em_lote(user_nomes)` | `bd_manipulador.py:672` | **Uma** consulta para N pessoas. Devolve `{user_nome: True}` só para quem tem recado marcado |

!!! note "Por que `telefones_de_recado_em_lote` existe (e não `telefone_e_recado` em laço)"
    Mesmo papel de `telefones_publicaveis_em_lote`: a lista telefônica monta
    1.165 cartões e, perguntando um a um, abriria 1.165 conexões para montar a
    mesma tela. Com 60 usuários de demonstração ninguém notava; com a folha
    real a tela "carregando" não terminava. O filtro publicável acontece em
    **Python** por `telefone_e_publicavel` (`:695`), para a regra do fixo
    institucional valer igual nos dois backends; o `IN` é portátil (o proxy
    traduz os placeholders para o PostgreSQL) e os valores vão **sempre** por
    parâmetro.

A marca **chega ao diretório pelo núcleo**:
`mod_intranet/integracoes.telefones_de_recado_para_lista()` → `{user_nome: True}`
(ver [Fachada de Integração](../arquitetura_de_software_das/fachada_integracoes.md)).
A lista telefônica **não pode abrir o banco do cadastro** (AGENTS.md §2), então a
costura é no núcleo — igual ao espelhamento.

### A exigência de um telefone da prefeitura — `_eh_telefone_da_prefeitura`

> **EN:** Only `empresa`/`fixo` counts. A company **mobile does not satisfy** the
> requirement: a mobile is the person, and what the municipality has to
> guarantee is that a **line** reaches somewhere inside the building.
>
> **PT-BR:** Só `empresa`/`fixo` conta. O **celular da prefeitura não
> satisfaz** a exigência: celular é a pessoa, e o que a prefeitura precisa
> garantir é que exista uma **linha** que toque em algum lugar do prédio.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `_eh_telefone_da_prefeitura(papel, tipo)` | `bd_manipulador.py:964` | Uma linha: `_validar_papel(papel) == 'empresa' and _validar_tipo(tipo) == 'fixo'`. É o predicado **real** da exigência — celular da prefeitura, celular particular e residencial ficam de fora |
| `DIAS_LIBERACAO_PROVISORIA = 4` | `bd_manipulador.py:961` | Prazo do paliativo, em dias |
| `avaliar_telefones_primeiro_acesso(contatos)` | `bd_manipulador.py:974` | Avalia **sem gravar** |
| `registrar_contatos_primeiro_acesso(ator, user_nome, contatos, liberacao_provisoria=False)` | `bd_manipulador.py:1023` | Grava, aplica a exigência e devolve `(ok, msg, **detalhes**)` |
| `bloqueio_provisorio_pendente(user_nome)` | `bd_manipulador.py:1159` | `True` se o prazo **já venceu** e a conta está ativa |
| `liberar_acesso_definitivo(ator, user_nome)` | `bd_manipulador.py:1563` | O botão do DTI |
| `informacao_acesso_provisorio(user_nome)` | `bd_manipulador.py:1618` | O estado, para as telas e para o DTI |
| `_prazo(dias)` | `bd_manipulador.py:1148` | `datetime.now() + timedelta(dias)` no formato do banco, **sem** `strftime` do SQLite — para continuar funcionando no Postgres pelo proxy |

#### `avaliar_telefones_primeiro_acesso(contatos)` — avalia sem gravar

> **EN:** Evaluates the phones before saving, so the screen can warn about an
> out-of-range number **while the server types** instead of after he already
> saved and discovered the typo.
>
> **PT-BR:** Avalia os telefones antes de gravar, para a tela poder avisar
> sobre um número fora da faixa **enquanto o servidor digita**, e não depois
> que ele já salvou e descobriu o erro.

```python
{
  "tem_da_prefeitura": bool,   # existe fixo da prefeitura (próprio ou recado)
  "particulares":     int,     # quantos particulares o servidor informou
  "fora_da_faixa":    [(numero, descricao_da_faixa_mais_proxima)],
  "pode_prosseguir":  bool,    # tem_da_prefeitura OU particulares > 0
}
```

Separar a avaliação da gravação é o que torna possível o aviso **ao vivo** no
diálogo do primeiro acesso. `pode_prosseguir` existe para a primeira trava
distinguir *"não há telefone nenhum"* (que nem chega a abrir a trava) de *"há
particular, falta o da prefeitura"* (que abre as duas travas).

#### Mudança de assinatura — `registrar_contatos_primeiro_acesso` devolve **3 valores**

!!! warning "`(ok, msg)` → `(ok, msg, detalhes)` — quem desempacota 2 quebra"
    A função passou a devolver uma **tupla de três** valores. Todo chamador
    que faz `ok, msg = registrar_contatos_primeiro_acesso(...)` passa a
    levantar `ValueError: too many values to unpack`. O terceiro é
    `detalhes`, e o que a tela faz com ele é obrigatório, não cosmético: sem
    ele ela não sabe se mostra o **bilhete** de acesso provisório nem o
    **aviso** de número fora da faixa.

```python
detalhes = {
  "provisorio":   bool,                 # entrou pelo paliativo
  "fora_da_faixa": [(numero, descricao), ...],
  "ate":          "YYYY-MM-DD HH:MM:SS" | None,   # o prazo gravado
  "pode_prosseguir": bool,
}
```

| Situação | Retorno |
|:---|:---|
| Nenhum telefone informado | `(False, "Informe ao menos um telefone — sem ele você não aparece na lista telefônica.", detalhes)` |
| Sem fixo da prefeitura e **sem** `liberacao_provisoria` | `(False, "Falta um telefone da prefeitura (fixo). Se você usa o telefone do setor para recado, marque-o como telefone de recado.", detalhes)` |
| Sem fixo, `liberacao_provisoria=True` e **nenhum particular** | `(False, "Para liberar o acesso por um período você precisa informar um telefone particular de contato.", detalhes)` — o paliativo **exige** particular |
| Sem fixo, com `liberacao_provisoria=True` e particular informado | `(True, "Telefones registrados. Acesso liberado por 4 dias — depois disso a conta fica bloqueada até o DTI liberar.", detalhes)` com `detalhes["provisorio"] = True` e `detalhes["ate"]` preenchido |
| Com fixo da prefeitura | `(True, "Telefones registrados.", detalhes)` com `provisorio=False` e `ate=None` — o prazo anterior (se houve) deixa de valer |
| Telefone **fora da faixa** da prefeitura | **Salva** e devolve `ok=True`, com o número em `detalhes["fora_da_faixa"]` |

`contatos` é uma lista de dicionários com `numero`, `papel` (`empresa`/`pessoal`),
`tipo` (`celular`/`fixo`), `visivel` e **`recado`**. Campos em branco são
**ignorados** (o servidor optou por não informar). O `DELETE` dos telefones
anteriores acontece **antes** do `INSERT`, e tudo num commit único: cadastro pela
metade é pior do que cadastro recusado, porque o servidor fica sem saber o que já
preenchou. Se nenhum contato marcar `principal`, o **primeiro** da lista vira
principal.

!!! note "Telefone fora da faixa **não** é bloqueado — é avisado"
    É a regra que a prefeitura definiu, e ela está em
    `avaliar_telefones_primeiro_acesso` + no `detalhes`, não numa recusa. Bloquear
    puniria uma situação real: a unidade de saúde do distrito que atende no
    telefone da cidade vizinha, a escola que emprestou a linha. O número fica
    sinalizado, o sistema avisa, e o diretório continua funcionando. Fora da faixa
    o servidor ou corrige o número, ou marca como **recado**.

O diálogo que chama isso é `_dialogo_telefones` no núcleo (`mod_intranet/telas.py:982`) — ver
[Módulo Intranet](intranet.md#primeiro-acesso-senha-e-telefone-27092026).

### A liberação temporária de 4 dias — o paliativo

> **EN:** A server who does not know his own number confirms twice that he
> does not, and enters with a deadline: 4 days, and a **private number is
> mandatory**. After the deadline the account closes and only the DTI reopens
> it. Without the deadline the temporary release would be a permit nobody ever
> checks.
>
> **PT-BR:** O servidor que não sabe o próprio número confirma duas vezes que
> não sabe, e entra com prazo: 4 dias, e **telefone particular obrigatório**.
> Passado o prazo a conta fecha e só o DTI reabre. Sem o prazo, a liberação
> temporária seria uma autorização que ninguém nunca fiscaliza.

O prazo é curto **de propósito**: quatro dias é o bastante para o servidor
descobrir o número perguntando à secretaria da escola, à unidade de saúde, à
garagem ou ao almoxarifado, e curto o bastante para que a conta não vire
cadastro órfão no sistema.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `bloqueio_provisorio_pendente(user_nome)` | `bd_manipulador.py:1159` | `True` **só** se há `acesso_provisorio=1` **e** `provisorio_ate` no passado **e** `user_ativo=1`. Já bloqueada ⇒ `False` (nada a fazer) |
| `liberar_acesso_definitivo(ator, user_nome)` | `bd_manipulador.py:1563` | **Recusa** se ainda não houver `papel='empresa' AND tipo='fixo'` (`:1586-1589`). Reativa (`user_ativo=1`) e limpa `acesso_provisorio=0`, `provisorio_ate=NULL`, `telefone_pendente=0` |
| `informacao_acesso_provisorio(user_nome)` | `bd_manipulador.py:1618` | `{provisorio, ate, vencido, bloqueado, dias_restantes}` |

!!! danger "`vencido` é o **prazo**; `bloqueado` é a **conta** — são coisas diferentes"
    No começo estes dois campos eram o mesmo, e o efeito era uma conta
    recém-liberada aparecer como **vencida no primeiro dia**. Hoje
    `vencido = (provisorio_ate < agora)` (o prazo passou) e
    `bloqueado = (user_ativo == 0)` (a conta está fechada) — campos
    independentes, lidos de colunas diferentes. Uma conta no 4º dia tem
    `provisorio=True`, `vencido=False`, `bloqueado=False` e
    `dias_restantes=0`; no 5º dia `vencido=True` e o bloqueio é feito no login.

!!! note "A checagem que **falha** não bloqueia ninguém"
    Em `mod_intranet/autenticacao.autenticar` (`:355-368`) a chamada é
    envolvida em `try/except` e o `except` só passa. Um erro de banco ali
    transformaria **todo servidor** em "usuário bloqueado" no primeiro dia —
    o pior resultado possível para uma checagem de prazo. Ver
    [Módulo Intranet](intranet.md#a-liberacao-temporaria-e-o-paliativo-de-4-dias-27092026).

O botão do DTI **recusa** a liberação sem telefone da prefeitura. Sem essa
recusa, a conta ficaria "liberada" e sem número, e o paliativo recomeçaria de
zero no prazo seguinte — a verificação é feita **na função**, não na tela, para
que a regra valha para qualquer chamador.

### `telefone_pendente` e `registrar_contatos_primeiro_acesso`

> **EN:** `telefone_pendente` is 1 for every server created with
> `exigir_telefone=True`. The first access asks for the phones **after** the
> password change, and `registrar_contatos_primeiro_acesso` writes them in a
> single transaction and clears the flag.
>
> **PT-BR:** `telefone_pendente` fica em 1 para todo servidor criado com
> `exigir_telefone=True`. O primeiro acesso pede os telefones **depois** da
> troca de senha, e `registrar_contatos_primeiro_acesso` grava tudo numa
> transação só e baixa a pendência.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `criar_usuario(..., exigir_telefone=True)` | `bd_manipulador.py:1332` | `True` (padrão) grava `telefone_pendente=1`. Contas de serviço (robô, integração) passam `False` — não têm pessoa para atender o telefone |
| `telefone_pendente(user_nome)` | `bd_manipulador.py:934` | `True` se o servidor ainda precisa registrar os telefones |
| `registrar_contatos_primeiro_acesso(ator, user_nome, contatos, liberacao_provisoria=False)` | `bd_manipulador.py:1023` | Grava a lista inteira numa transação só, aplica a exigência do fixo (ou o paliativo), baixa a pendência, audita `contatos_primeiro_acesso` e devolve `(ok, msg, detalhes)` |
| `_limpar_pendencia_telefone(cur, user_nome)` | `bd_manipulador.py:921` | `UPDATE tb_usuarios SET telefone_pendente=0` — fica em SQL cru e recebe o cursor porque quem chama já está numa transação |

### `telefones_publicaveis_em_lote(user_nomes)` — correção de desempenho

> **EN:** `telefone_empresa_principal` opened one connection per row. With the
> real staff sheet that froze the directory screen, so
> `telefones_publicaveis_em_lote(user_nomes)` resolves every publicable number
> in a **single** query with an `IN` list of placeholders.
>
> **PT-BR:** `telefone_empresa_principal` abria uma conexão por linha. Com a
> folha real de servidores isso travava a tela do diretório, então
> `telefones_publicaveis_em_lote(user_nomes)` resolve todos os números
> publicáveis em **uma** consulta, com um `IN` de placeholders.

Com 60 usuários de demonstração ninguém notava; com a folha real (mais de mil servidores) a tela "carregando" nunca terminava. Devolve `{user_nome: numero}` **só para quem tem número publicável** — quem não liberou simplesmente não aparece no dicionário, que é o mesmo significado de "sem telefone" que o resto do sistema usa. O `IN` é portátil (o proxy traduz os placeholders para o PostgreSQL) e os valores vão **sempre** por parâmetro — não há concatenação de texto. Consumidora: `leitura_lista.listar_para_lista_telefonica()` (`leitura_lista.py:159`).

**Ponte de leitura para a Lista Telefônica** — `leitura_lista.py` (27/09/2026): arquivo **dentro deste módulo**, em página própria, que devolve **dicionários** (e não as tuplas de tamanho fixo de `obter_usuario`/`listar_usuarios`, que são lidas por índice em vários pontos do sistema). `nome_para_exibicao` (primeiro + último nome), `obter_usuario_para_lista`, `buscar_usuarios_para_lista` (só ativo e não excluído), `listar_para_vinculo` e **`listar_para_lista_telefonica`** (todos os ativos com o telefone publicável **e** a marca de recado, ambos vindos do lote — `telefones_publicaveis_em_lote` e `telefones_de_recado_em_lote`, duas consultas para a folha inteira). Expõe **só o telefone publicável** (`telefones_publicaveis_em_lote` + `telefone_e_publicavel`) — o particular existe no cadastro e **não sai daqui**: é a diferença entre o que a prefeitura publica e o que é do servidor. A normalização `_norm` é **local** (o banco é deste módulo e não pode depender do organograma; AGENTS.md §2) e o único import é o **próprio** `bd_manipulador`.

!!! warning "Quem consome a ponte é o **núcleo**, não a Lista Telefônica"
    A lista telefônica **não importa** este módulo (AGENTS.md §2, e
    `assets/test/check_integridade.py` reprova o import direto). Desde
    27/09/2026 quem chama `leitura_lista` são as **duas** funções da fachada
    do núcleo — `espelhar_cadastro_na_lista_telefonica(ator)` (o espelhamento)
    e `telefones_de_recado_para_lista()` (a marca de recado) — e ambas
    entregam o resultado ao diretório por parâmetro. Ver
    [Espelhamento do cadastro no diretório](lista_telefonica.md#espelhamento-do-cadastro-no-diretorio-27092026)
    e [Fachada de Integração](../arquitetura_de_software_das/fachada_integracoes.md).

### Nome de exibição — primeiro + último, e **não** a matrícula

> **EN:** The display name is the **first and the last name** of the register
> (which keeps the full or social name, Decreto 8.727/2016).
> `"Ana Beatriz Souza Rocha"` → `"Ana Rocha"`.
>
> **PT-BR:** O nome de exibição é o **primeiro e o último nome** do cadastro
> (que guarda o nome completo ou social, Decreto 8.727/2016).
> `"Ana Beatriz Souza Rocha"` → `"Ana Rocha"`.

| API | Arquivo:linha | O que faz |
|:---|:---|:---|
| `nome_de_tratamento(user_nome)` | `bd_manipulador.py:1269` | `primeiro + último` do `user_nome_completo`; cai no nome completo e **só depois** no login |
| `_primeiro_e_ultimo(nome_completo)` | `bd_manipulador.py:1250` | Quatro linhas: separa por espaço, e devolve `"primeiro ultimo"` |

!!! note "Por que primeiro + último, e por que o helper é **local**"
    O nome de usuário desta prefeitura é a **matrícula** (`MT-1234`). Mostrar
    isso no cabeçalho é mostrar um código de barras com nome de pessoa: não diz
    nada, e a pessoa se reconhece no número como se reconhece numa placa. E o
    nome completo em tela cheia empurra o rótulo do perfil para fora. Primeiro e
    último é o que a pessoa **ouve** quando é chamada.

    O helper é **local** (e não importado de `leitura_lista.nome_para_exibicao`)
    pelo mesmo motivo daquele arquivo: `leitura_lista` importa este módulo, e o
    caminho inverso fecharia um **ciclo de import**. São quatro linhas — a
    duplicação é o preço de não fechar o ciclo.

O cabeçalho da intranet consome esse nome em `mod_intranet/telas.py`
(`header-nome-usuario`, rótulo curto + `tooltip` com o nome completo) — ver
[Módulo Intranet](intranet.md).

**Flags finas (JSON por vínculo)** — catálogo `FLAGS_PERMISSAO`: `blog.publicar`, `blog.comentar`, `blog.configurar`. API: `obter_flags(user, modulo)` (fail-soft `{}`), `definir_flags(ator, user, modulo, flags)` (valida allowlist, exige vínculo prévio) e `tem_flag(user, modulo, flag)` (admin global/modular passa pelo papel). `duplicar_usuario` replica flags da origem junto com os papéis.

⚠️ `tb_modulo_perfil` existe apenas no `bd_criador.py` — **legado/morto** (aponta para o banco central); não confiar.

## Funcionalidades

- **CRUD soft**: criar (senha vazia/None → `123456` padrão inicial 18/09/2026 + mín. 6 + `forcar_troca`), editar (aplica só diferenças; login travado para `master`), renomear (replica em dependentes), bloquear/desbloquear, excluir em 2 estágios (soft com motivo ≥ 3 chars → DELETE físico, liberado nas linhas de excluídos via busca "excluído" **ou filtro Situação = Excluídos**).
- **Busca instantânea** (debounce 150 ms) insensível a acentos, com filtros situação/perfil e paginação 10/20/50/100. **Barra superior inline sem quebra 18/09/2026** (`telas.py:98-115` `flex-nowrap gap-4`, tabs `shrink overflow-x-auto`, busca `width:min(46%,620px) flex-nowrap shrink-0`). Busca em **todos os campos** (ID, login, perfil, e-mail, telefone, módulos:papel, nome completo) + palavras-chave de estado ("provisório", "bloqueado", "sessão", "excluído"). Filtro **Situação** (`SIT_OPCOES`) agora com 4 opções: `Todas`, `Ativos`, `Bloqueados`, **`Excluídos`** (`data-testid=usuarios-filtro-situacao`, `min-w-[170px]`, `tooltip` "Filtra por situação: Ativos, Bloqueados ou Excluídos (soft-delete)" — `telas.py:293`); lógica: `sit==excluidos` → só `user_deletado=1`; senão excluídos só entram quando `termo` contém `exclu` e `sit==""` (18/09/2026 `18690cb`). **A aba Excluídos foi removida** (redundante — substituída pelo filtro). Ordenação A→Z (nome/tratamento) ou numérica (ID) via seletor. **Senha padrão ao criar/duplicar** vazia caiu em `123456` (`bd_manipulador.py:366` + `telas.py:585/850`).
- **Papéis por módulo**: seletores de acesso com módulos inativos marcados INDISPONÍVEL (vínculos órfãos via `listar_vinculos_orfaos`). Tooltip no nome de tratamento expõe todos os campos (login, perfil, situação, contato, cadastro, acessos com nomes de exibição + badge de papel) — exibição compacta 4 colunas (ID | Tratamento | Senha provisória | Ações).
- **Telefone múltiplo, consentimento, recado e dados funcionais (27/09/2026)**: cada usuário tem vários telefones, cada um com **papel** (empresa/pessoal), **tipo** (celular/fixo), marcação de **principal** (um por usuário), o **consentimento de exibição** `visivel` e a marcação de **recado** (o número é o do setor), em `tb_telefone_usuario`; e o cadastro guarda **`unidade`**, **`lotacao`**, **`cargo`**, a pendência **`telefone_pendente`** e a liberação temporária **`acesso_provisorio`/`provisorio_ate`**. O que pode sair no diretório é decidido por **`telefone_e_publicavel`** (fixo institucional sempre, celular da prefeitura só com autorização, particular nunca) e chega ao diretório pelo espelhamento orquestrado no núcleo — **o particular nunca atravessa**. Ver [Lista Telefônica](lista_telefonica.md).
- **Exigência do fixo da prefeitura e o paliativo de 4 dias (27/09/2026)**: `_eh_telefone_da_prefeitura(papel, tipo)` (`:964`) só aceita `empresa`/`fixo` — o **celular da prefeitura não satisfaz**, porque celular é a pessoa e o que a prefeitura precisa garantir é que exista uma *linha* que toque no prédio. `avaliar_telefones_primeiro_acesso(contatos)` (`:974`) avalia **sem gravar**, para a tela mostrar o aviso de número fora da faixa **enquanto o servidor digita**. Sem fixo, o servidor confirma **duas vezes** que não sabe o número e entra com `liberacao_provisoria=True` — que **exige um telefone particular** e grava `acesso_provisorio=1` com `provisorio_ate` em 4 dias. O prazo é cumprido **no login** (`mod_intranet/autenticacao.autenticar` → `bloqueio_provisorio_pendente`, `:1159`), e só o DTI reabre, por `liberar_acesso_definitivo(ator, user_nome)` (`:1563`) — que **recusa** se ainda não houver fixo cadastrado. Detalhes: [A liberação temporária de 4 dias](#a-liberacao-temporaria-de-4-dias-o-paliativo) e [Módulo Intranet](intranet.md#a-liberacao-temporaria-e-o-paliativo-de-4-dias-27092026).
- **Primeiro acesso em DOIS passos (senha e telefone) (27/09/2026)**: todo servidor criado com `exigir_telefone=True` (padrão de `criar_usuario`) nasce com `telefone_pendente=1`, porque a folha de servidores do município **não traz ramal** — o número do diretório só existe se o próprio servidor informar. A senha provisória força **dois** diálogos em sequência, e o de telefone só abre depois que o de senha terminou: `_primeiro_acesso` (núcleo) → `_dialogo_troca_credenciais` / `_dialogo_troca_senha` (ambos com `ao_concluir`) → `_dialogo_telefones` (que grava por `registrar_contatos_primeiro_acesso`). Dentro do diálogo de telefone, salvar **sem** telefone da prefeitura abre ainda as **DUAS travas** do paliativo (`_travas_falta_numero` → `_travas_confirmar`), e só a segunda libera por prazo. Ver [Primeiro acesso no núcleo](intranet.md#primeiro-acesso-senha-e-telefone-27092026) e [as duas travas](intranet.md#as-duas-travas-27092026).
- **Duplicar usuário** (`duplicar_usuario` + `_dlg_duplicar`): novo login herda perfil global, papéis por módulo e flags finas da origem (pré-selecionados, ajustáveis antes de salvar).
- **Sessões Ativas**: todas as vivas do sistema lidas do `tb_sessoes` **central** (`id, usuario, modulo, login_timestamp, cookie_hash, ip, dispositivo, mac, logout_timestamp`; abertas = `logout_timestamp IS NULL`), com IP/dispositivo/MAC em tooltip, encerramento individual (`encerrar_sessao`) / em massa (`encerrar_todas_sessoes`, `_fechar_sessoes_central` em bloqueio/exclusão/reset) e histórico das 10 últimas encerradas por usuário (`listar_historico_sessoes`, duração calculada na tela). Agregados: `contar_sessoes_ativas(usuario)`, `sessoes_ativas_por_usuario()`.
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do Editor PDF e anonimiza empenhos como "(usuário excluído)"; auditoria sempre preservada.
- **Proteções**: vedado agir sobre a própria conta; `master` não é renomeado/excluído; último `administrador_geral` ativo protegido contra rebaixamento/bloqueio por outro admin (RF-26).
- **Aba Administração** (admin geral): card padrão **"Configurações de cores"** (`usuarios_*` — `cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`) + card "Configurações específicas" com a política `usuarios_senha_min`; card "Configurações de cores" padronizado via `tema_modulo.bloco_aparencia` (prévia ao vivo, rodapé 2 botões) e tela em área cheia (`w-full`). **Padrão próprio do tema de botões (06/09)**: os campos de botão exibem o rótulo "vazio = padrão do módulo" (`tema_modulo.bloco_aparencia` — `tema_modulo.py:319-322`) — com `usuarios_cor_botao`/`usuarios_cor_texto_botao`/`usuarios_btn_tamanho` vazios (padrão atual do banco), os botões usam o padrão do PRÓPRIO módulo (`PADROES_TEMA["usuarios"]` = `#000000` — sem herança do tema do sistema); os inputs mostram o valor resolvido e o "Restaurar padrão" grava `""` para voltar ao padrão do próprio módulo. O cabeçalho usa `chave_modulo="usuarios"` (`telas.py:97`): a borda de destaque é a **mesma cor dos botões do módulo** (`usuarios_cor_botao`, vazia = padrão do próprio módulo), título/fundo seguem o tema — sem hex hardcoded. **Cupê "Edição do módulo" restaurado (06/09)**: `campo_modulo(ator, "usuarios")` (`telas.py:705`) volta a permitir ao admin renomear o módulo, trocar o ícone e ativar/desativar (havia sido removido acidentalmente; a edição também permanece em `/configuracoes`).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: barra superior `flex-nowrap` → `flex-wrap`, tabs `overflow-x-auto`, busca `flex-1 min-w` (`campo_busca` `grow min-w-[220px]`), dialogs `w-full max-w`; tabelas parcialmente com `overflow-x-auto`; proposta P0/P1/P2 por `container`/`row`/`grid` (header `flex-wrap` `truncate`, filtros `sm:grid-cols-2`).
- **Versionamento**: `versao_modulo:usuarios = 1.0.260918` no rodapé de `/users`.

## Permissões

| Ação | `comum` | Admin `usuarios` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Ver tela de gestão | ✗ | ✓ | ✓ |
| Criar/editar/bloquear/renomear | ✗ | ✓ | ✓ |
| Exclusão definitiva (via busca "excluído") | ✗ | ✗ | ✓ |
| Encerrar sessões | ✗ | ✓ | ✓ |
| Aba Administração | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/users` (chave `usuarios`) — gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user, 'usuarios')`. Rota `/admin/usuarios` — painel `mostrar_administracao` em `telas_administracao.py` (só admin geral): cupê de cores `bloco_aparencia` + `usuarios_senha_min` (4–32, padrão 6, via `senha_minima()`/`set_config`, vale sem restart) + `painel_backup`.
- Importa `autenticacao` (hash/papéis), `get_connection` central e `audit_log`; escreve/lê `tb_sessoes` central.
- **Fonte única do cadastro — consumida pela fachada do núcleo (25/09/2026)**: os demais módulos **não importam mais** este módulo. `mod_intranet/integracoes.py` expõe `obter_usuario_gestao(user_nome)`, `listar_usuarios_gestao(filtro_ativo=None)`, `espelhar_cadastro_na_lista_telefonica(ator)` e **`telefones_de_recado_para_lista()`** (imports lazy + fail-soft: devolvem `None`/`[]`/`{}` + `logger.warning` em vez de derrubar a tela). Consumidores: `mod_filas/bd_manipulador.py:454,483` (autorização e liberação de fila), `mod_filas/telas.py:631` (busca de usuário cadastrado) e `mod_lista_telefonica/telas_administracao.py:689,745` (busca de contato e preenchimento de nome/telefone). O SQL continua rodando **só** no banco deste módulo, pelo `bd_manipulador` dele — a fachada atravessa uma fronteira de **código**, nunca de **dados**. Detalhes: [Fachada de Integração](../arquitetura_de_software_das/fachada_integracoes.md).
- **Única exceção de negócio→negócio**: a cascata LGPD (`_vinculos_cruzados_excluir`/`_vinculos_cruzados_renomear`) chama a API pública de limpeza do Blog, do Editor de PDF e do Renomeador de Empenhos — cada módulo toca só o seu banco. É a allowlist `CASCATA_LGPD` do `assets/test/check_integridade.py`.
- Seed idempotente em `init_db` (fonte única deste módulo): conta nativa `master` (`administrador_geral`) e contas de QA (`qacomum` perfil `comum`, `qamaster` `administrador_geral`); credenciais provisórias com **troca forçada no 1º login** (`marcar_trocar_senha`, auto-cura do `master` a cada boot) e renomeação obrigatória do `master` (`marcar_trocar_credenciais`). Por segurança, os valores das senhas provisórias **não são publicados nesta doc** — ver `bd_manipulador.py` e a tabela de seeds no [AGENTS.md §8.2](../analise_mod_gest_cad_usuario.md#seeds-idempotentes-de-contas-agentsmd-82) (contexto interno).
- Acesso padrão de todo usuário novo (`ACESSO_PADRAO_NOVO_USUARIO`, `bd_manipulador.py:36`): papel `comum` em **`editar_pdf`, `empenhos`, `solicita_impressao`, `lista_telefonica` e `agregador_noticias`** (27/09/2026 — os dois últimos entraram na lista). A lista é o trabalho diário de quem trabalha na prefeitura; servidor que chega sem nenhum destes cai em tela vazia e acha que o sistema quebrou. Ficam **fora** `usuarios`, `auditoria` e `blog`: os dois primeiros mexem em conta e registro de todo mundo e são do administrador; o `blog` foi deixado de fora deliberadamente, porque publicar na intranet é ato de comunicação do município, não privilégio de estar com matrícula ativa — se a prefeitura quiser, o admin libera na tela de usuários, e é melhor que a liberação seja uma decisão visível do que um padrão que ninguém nota.

## Carga da folha de servidores — `assets/populacao/sincroniza_servidores.py` (27/09/2026)

> **EN:** `sincroniza_servidores.py` reads the municipality's staff sheet (a JSON
> file) and writes every server into the register, creating what is new and
> updating what changed. It also mirrors the **organogram** into the phone
> directory. Without `--aplicar` it is a dry run and writes nothing.
>
> **PT-BR:** `sincroniza_servidores.py` lê a folha de servidores do município
> (um arquivo JSON) e grava cada servidor no cadastro, criando o que é novo e
> atualizando o que mudou. Ele também sincroniza o **organograma** no
> diretório telefônico. Sem `--aplicar` é só um ensaio e nada é gravado.

É um **script de administração**, executado no terminal — não é item de menu, não é rota e não aparece na tela. O servidor não o executa e não depende dele para entrar no sistema.

```bash
python assets/populacao/sincroniza_servidores.py            # ensaio: nada é gravado
python assets/populacao/sincroniza_servidores.py --aplicar   # grava de verdade
python assets/populacao/sincroniza_servidores.py --aplicar --arquivo <folha.json>
```

| Opção | Padrão | Efeito |
|:---|:---|:---|
| *(nenhuma)* | — | **Ensaio.** Imprime o que faria (quantos usuários, quantos bloqueados, quantas unidades) e sai com 0 |
| `--aplicar` | desligado | Grava de verdade: organograma + usuários |
| `--arquivo` | `assets/populacao/servidores_coletados.json` | Folha de servidores a ler |

O **modo padrão é ensaio por desenho**: sem `--aplicar` o script não abre nenhuma transação de escrita.

### O que é gravado

| Onde | O que |
|:---|:---|
| `user_nome` | A **matrícula**, só dígitos (`_matricula`) — é o login |
| `user_nome_completo` | O nome completo da folha |
| `unidade`, `lotacao`, `cargo` | Via `definir_dados_funcionais(ator, user_nome, unidade=…, lotacao=…, cargo=…)` |
| `user_senha` | Senha provisória `123456`, com `marcar_trocar_senha` e **`telefone_pendente=1`** (`exigir_telefone=True`) |
| `user_perfil` | `comum` |

!!! note "A matrícula é o login — e por quê"
    A prefeitura já tem um identificador único e público para cada
    servidor. Usar a matrícula como login dispensa senha inventada para
    memorizar, elimina colisão entre homônimos (que no interior do
    Brasil não é raro) e o servidor reconhece o próprio número na tela
    de login. `_matricula` deixa **só dígitos**: uma matrícula com
    pontuação seria um login diferente conforme o usuário digita.

`_bonito` normaliza **só a caixa** — `Secretaria Municipal De Educacao Publica` vira `Secretaria Municipal de Educacao Publica` (preposições e artigos em minúscula). Os acentos **não** são inventados: a fonte não os traz, e acrescentar seria fabricar um dado que a fonte não disse. A comparação, essa sim, é sem acento e sem caixa (`_sem_acento`), porque é assim que o casamento de nomes funciona.

**A lotação que repete a unidade é zerada.** Quando `lotacao == unidade` (servidor ligado direto na secretaria, sem departamento), o campo fica `''` — repetir na ficha é ruído.

### Quem nasce bloqueado

> **EN:** Pensioners, inactive staff and elected officials enter the register
> (the record is mandatory and the history matters) but are **blocked** — they
> cannot log in. Blocking is reversible by the administrator; deleting would not
> be.
>
> **PT-BR:** Pensionista, inativo e eleito entram no cadastro — o registro é
> obrigatório e o histórico importa — mas **bloqueados**: não entram no
> sistema. Bloquear é reversível pelo administrador; apagar não seria.

| Regra | Conjunto (`sincroniza_servidores.py:58-59`) |
|:---|:---|
| **Vínculo bloqueado** | `pensionista`, `inativo`, `eleito`, `exonerado` |
| **Situação bloqueada** | `demitido`, `exonerado`, `afastado` |

`_bloqueado(reg)` devolve o par `(bool, motivo)`, e o motivo entra no resumo. Um servidor já existente que esteja na folha é **bloqueado também** — a regra não vale só para quem está sendo criado.

### Política do organograma — desativar, nunca apagar

> **EN:** The database already ships with a 12-secretaria demonstration
> organogram seeded by `init_db`. In front of the real sheet those become empty
> folders in a real municipality's phone directory — pure confusion. But
> deleting is final, and an empty folder sometimes has a purpose: the
> administrator may be building an organogram the sheet does not describe yet.
> So: `ativo=0`, which disappears from the list and can come back with an
> `UPDATE`. **Nothing is destroyed.**
>
> **PT-BR:** O banco já vem com um organograma de demonstração (12 secretarias
> semeado por `init_db`). Diante da folha real, elas viram pastas vazias na
> lista telefônica de uma prefeitura de verdade — confusão pura. Mas apagar é
> definitivo, e pasta vazia tem vez: o administrador pode estar montando um
> organograma que a folha ainda não descreve. Então: `ativo=0`, que some da
> lista e pode voltar com um `UPDATE`. **Nada é destruído.**

| Comportamento | Regra |
|:---|:---|
| **Cria** as unidades que a folha conhece | Secretaria (`unidade`) como `secretaria`; departamento (`lotacao`, quando difere da secretaria) como `setor` sob ela |
| **Desativa** (`ativo=0`) o que a folha não conhece | Só as **ativas** que não estão na folha; as já desligadas ficam como estão, para rodar de novo não inflar o contador |
| **Reativa** (`ativo=1`) o que voltou | Unidade que existe e estava desligada |
| **Idempotente** | Casa por nome normalizado, a mesma regra de `mod_lista_telefonica.bd_manipulador._norm` |

O resumo é `{secretarias_criadas, setores_criados, reativadas, desativadas, erros}`. Na última execução real (competência `08/2026`, 1.165 servidores) o resultado foi **9 secretarias e 9 departamentos** — mais 124 servidores ligados direto na secretaria, sem departamento, e que por isso não geram unidade própria.

!!! warning "A ordem de `--aplicar` importa"
    O organograma roda **antes** dos usuários (`sincronizar_unidades` e depois
    `sincronizar`, em `main()`). Sem as unidades criadas primeiro, o
    espelhamento posterior do diretório não teria onde casar os servidores e
    contaria todos como `sem_unidade`.

### Idempotência e o que o script evita reescrever

Rodar duas vezes não duplica ninguém. Para quem já existe, o script compara o nome e, **só se mudou**, chama `editar_usuario(…, auditar=False)` — senão gera uma linha de auditoria por usuário e o rastro fica ilegível. `definir_dados_funcionais` é chamado nos dois casos, porque ele só altera os campos que lhe são passados.

## Testes

```bash
.venv/bin/python assets/test/teste_boot.py            # 16 verificações
.venv/bin/python assets/test/teste_fluxo_autenticacao.py  # login, troca obrigatória, sessão/auditoria (19 OK)
.venv/bin/python assets/test/teste_fluxo_permissoes.py    # perfis/papéis por módulo (13 OK)
.venv/bin/python assets/test/test_fase1_login.py
.venv/bin/python assets/test/test_fresh_install.py
.venv/bin/python assets/test/test_telefone_consentimento.py  # 51 asserções: consentimento, pendência, recado, faixas, lote, paliativo
.venv/bin/python assets/test/test_primeiro_acesso_e2e.py    # 20 asserções: Playwright Python (servidor no ar)
```

| Teste | Asserções | O que prova |
|:---|:--:|:---|
| `assets/test/test_telefone_consentimento.py` (27/09/2026, era 31) | **51** | `teste_regra_publicavel` (a regra pura de `telefone_e_publicavel`, inclusive entrada corrompida) · `teste_pendencia_e_registro` (ciclo da pendência, gravação dos quatro telefones, idempotência, usuário bloqueado fora do diretório) · `teste_ponte_da_lista` (o lote) · **`teste_recado_e_faixas`** (novo) |
| `assets/test/test_primeiro_acesso_e2e.py` (27/09/2026, **novo**) | **20** | O diálogo, o aviso de faixa **ao vivo**, as **DUAS travas**, o bilhete e o estado no banco |

`teste_recado_e_faixas` (o acréscimo de 27/09/2026) cobre, em sete blocos: o
celular particular **não** satisfaz a exigência da prefeitura · o **fixo do setor
marcado como recado** satisfaz · número **fora da faixa é sinalizado e mesmo assim
salva** · o administrador cadastra **mais de uma** faixa e as duas casam ·
o **paliativo** libera com prazo de no máximo 4 dias, particular fora da lista ·
o prazo vencido **bloqueia no login** (`aut.autenticar`) e a conta fica com
`user_ativo=0` · o DTI **não** libera em definitivo sem telefone da prefeitura.

!!! note "Os dois rodam como **script standalone** (sem pytest)"
    Ambos usam o próprio `_OK`/`_FALHAS` e saem com `0` ou `1`. O
    `test_telefone_consentimento.py` cria os usuários com prefixo de teste
    (`TESTE_TEL_001`, `TESTE_RECADO`) e apaga tudo no fim; o
    `test_primeiro_acesso_e2e.py` usa `TESTE_E2E_TEL` e **exige o servidor no ar**
    em `http://localhost:8080` — ele sobe o navegador de verdade.

!!! note "Por que **Playwright Python** e não o pacote npm"
    O `sync_api` do pacote **Python** está instalado no ambiente; o pacote **npm**
    do Playwright não está. Um evento sintético (`new Event('input')`, `.click()`
    por JavaScript) também não chegaria ao `v-model` do Vue — o NiceGUI liga os
    handlers no `v-model`, e foi assim que o aviso de faixa pareceu quebrado
    quando estava certo: o evento nunca saiu do navegador. Com `fill()` e `click()`
    de verdade, o teste percorre o mesmo caminho que o dedo da pessoa.

## Pontos de atenção

- Tabela real é `tb_usuarios` (não `tb_usuario`); rota real é `/users` (não `/gestao-usuarios`).
- `bd_criador.py` é morto — não executar.
- Todos os testes de fluxo existem em `assets/test/` (local canónico; `test/` e `testes/` não existem na raiz): `teste_boot.py`, `teste_fluxo_autenticacao.py`, `teste_fluxo_permissoes.py` (Fase 2.5).
- Consumidores externos dependem do **formato posicional das tuplas**, e os dois formatos **não são o mesmo**: `listar_usuarios` devolve 11 campos (`[1]` login, `[4]` **e-mail**, `[9]` nome completo) e `obter_usuario` devolve 10 (`[1]` login, `[4]` **telefone**, `[9]` nome completo). Reordenar as colunas de qualquer uma das duas QUEBRAS a fachada de forma silenciosa.
- Senhas dos seeds são **provisórias**: assuma que já foram trocadas em qualquer fluxo de teste.
- **`telefone_pendente` só baixa por `registrar_contatos_primeiro_acesso`.** Se um servidor fica com a pendência ligada e o diálogo nunca é concluído, ele entra no sistema e não aparece no diretório — o espelhamento conta esse servidor como `sem_telefone`.
- **`visivel` default 0 é uma decisão, não um oversight.** Um telefone gravado por `adicionar_telefone` sem `visivel` nasce restrito; o fixo institucional é a única categoria que publica sozinha, e mesmo assim a decisão fica no `telefone_e_publicavel`, não no default da coluna.
- **`telefone_empresa_principal` continua existindo** (`bd_manipulador.py:738`) e é o caminho para **um** usuário. Para montar a lista inteira, use `telefones_publicaveis_em_lote` (`:752`) e `telefones_de_recado_em_lote` (`:672`) — é a diferença entre uma consulta e uma por linha.
- **`listar_telefones` desempacota por índice e a tupla ganhou um campo.** São 9 campos desde 27/09/2026: `recado` entrou no **7** e `data_cadastro` foi para o **8**. `telefone_e_recado` (`:669`) é o único leitor de `recado` e tem guarda de tamanho (`len(principal) > 7`); quem ler `t[7]` esperando a data recebe o flag. A ponte `leitura_lista.py` devolve **dicionários** justamente para que nenhum consumidor externo dependa de posição fixa.
- **`registrar_contatos_primeiro_acesso` desempacota TRÊS valores** (`:1023`). `ok, msg = ...` levanta `ValueError`. O terceiro (`detalhes`) é o que permite à tela mostrar o bilhete do acesso provisório e o aviso de número fora da faixa — não é cosmético.
- **`bloqueio_provisorio_pendente` é fail-soft por convicção.** Devolve `False` em qualquer falha, e o `except` em `autenticar` só passa: uma checagem de prazo que bloqueia todo mundo por causa de um erro de banco é pior do que um prazo que passa.
- **`sincroniza_servidores.py` toca em DOIS bancos** (o deste módulo e o do diretório, via `mod_lista_telefonica.bd_manipulador`). É o **único** lugar do projeto em que um processo de manutenção opera assim — a regra de isolamento do AGENTS.md §2 vale para os módulos em execução, e este script é ferramenta de administração, não tela. Ainda assim, cada lado escreve **só** no banco dele.

Ver [Análise do Módulo](../analise_mod_gest_cad_usuario.md).