# Factory `master` Account Resurrection — Intranet Modular (2026-09-29)

> Security correction of 29/09/2026: the seed of the native `master` account brought the factory credentials back on **every restart** after the credential change, because the guard only looked at whether the login existed and not at the fact that the change had already happened. Fixed with a persistent marker (`forcar_troca_credenciais:master` = `'0'`), the legacy second creation path (`bd_criador.py`) was blocked, and the rename deadlock message now says what to do. Module version `usuarios` → `1.0.260929`.

---

# Conta de fábrica `master` ressuscitando a cada reinício — Intranet Modular (29/09/2026)

> Correção de segurança de 29/09/2026: o seed da conta nativa `master` trazia a
> credencial de fábrica de volta em **todo reinício** depois da troca de
> credenciais, porque a guarda olhava só se o login existia — e não se a troca
> já tinha acontecido. Corrigido com uma marca persistente
> (`forcar_troca_credenciais:master = '0'`), o segundo caminho de criação legado
> (`bd_criador.py`) foi bloqueado, e a mensagem do ciclo travado do rename passou
> a dizer o que fazer. Versão do módulo `usuarios` → `1.0.260929`.

## 1. O sintoma

> **EN:** The administrator finished the mandatory first-access dialog — chose a
> real login, typed a real password — restarted the server, and the factory
> account was **back**: same login, same factory password, same
> `administrador_geral` profile, with both "change your credentials" flags
> rearmed. The dialog reopened, forever.
>
> **PT-BR:** O administrador concluiu o diálogo obrigatório do primeiro acesso —
> escolheu um login real, digitou uma senha real — reiniciou o servidor, e a
> conta de fábrica estava **de volta**: mesmo login, mesma senha de fábrica, mesmo
> perfil `administrador_geral`, com as duas flags de "troque suas credenciais"
> rearmadas. O diálogo reabria, para sempre.

Não era falha de tela nem de sessão: era o **seed do boot seguinte** recriando a
conta que a troca de credenciais tinha acabado de remover.

## 2. Diagnóstico — verificado do zero, com evidência

| Momento | Fato | Onde |
|:---|:---|:---|
| Primeiro acesso | O `master` é **renomeado**: `renomear_usuario` faz `UPDATE` de `tb_usuarios.user_nome` e **preserva o `id`** | `mod_gest_cad_usuario/bd_manipulador.py:1903` |
| Resultado | `master` **sai da tabela** — o login deixa de existir; o que existe é o login novo, com o mesmo `id` e o perfil `administrador_geral` | idem |
| Boot seguinte | A guarda do seed era `if not obter_usuario("master")` — e essa condição **voltava a ser verdadeira**, porque o login `master` realmente não existia mais | `bd_manipulador.py:512` (antes da correção) |
| Consequência | O seed reinseria `master` com a senha de fábrica, perfil `administrador_geral`, e chamava `marcar_trocar_senha("master", True)` + `marcar_trocar_credenciais("master", True)` — rearmando o diálogo | `bd_manipulador.py:514-546` |

**Evidência real coletada nesta instalação:** a troca foi concluída às
**16:47:13** (trilha de auditoria: `usuário renomeado: master -> klayton`) e no
boot seguinte, às **16:48:35**, `master` **reapareceu** — confirmado por
`bcrypt.checkpw` contra o hash recriado, **não** por comparação de string. Com
a correção, o boot 3 deixou `master` **ausente**.

!!! danger "A guarda olhava a pergunta errada"
    `not obter_usuario("master")` responde *"o login `master` existe?"*. O que a
    segurança precisa saber é *"a troca de credenciais já aconteceu?"*. São
    perguntas diferentes, e no caminho feliz do sistema — a troca **concluída** —
    elas dão respostas **opostas**: a conta foi **removida de propósito**, e a
    guarda leu essa remoção como "falta criar".

## 3. A correção — a marca `forcar_troca_credenciais:master`

A guarda passou a ter **duas condições** (`bd_manipulador.py:535`):

```python
if not _troca_de_credencial_do_master_concluida() and not obter_usuario("master"):
```

A função nova (`bd_manipulador.py:190`) lê a chave
`forcar_troca_credenciais:master` do `tb_config` **central** e devolve `True`
quando ela vale `'0'`:

| Valor da chave | Significado | O seed semeia? |
|:---|:---|:---:|
| **não existe** | instalação nova — a troca ainda nem foi pedida | **sim** |
| `'1'` | troca **PENDENTE** (`marcar_trocar_credenciais(nome, True)`) | **sim**, se o login não existir |
| `'0'` | troca **CONCLUÍDA** (`trocar_credenciais_master` chama `marcar_trocar_credenciais(nome_atual, False)` **depois** do rename) | **não** |

Isto é, **"a chave existe e vale `0`" = "o `master` nativo já foi renomeado"** —
e um login que não existe mais é exatamente o que **não** deve ser ressuscitado.
A marca é a mesma peça conceitual do marcador de migração do versionamento
(AGENTS.md §4.2 — ver
[Versionamento §3.1](../versionamento/index.md#31-o-modelo-da-migracao-de-bump)):
**estado que, uma vez gravado, não se desfaz sozinho**. A chave vive no
`tb_config` central porque a troca acontece no **núcleo**
(`mod_intranet/autenticacao.py:583`), e o seed acontece no **módulo de
cadastro** — nenhum dos dois módulos abre o banco do outro (AGENTS.md §2), então
o estado compartilhado mora no central.

### 3.1 Fail-soft deliberado — semear é o lado seguro

Se a leitura da marca falhar, a função devolve `False` e o seed **semeia**:

```python
except Exception as e:
    _log().warning(f"... falha ao ler a marca; assumindo troca pendente | {e}")
    return False
```

Os dois erros possíveis e o porque de escolher o menor:

| Situação | O que acontece | Gravidade |
|:---|:---|:---|
| Instalação **nova**, leitura falhou e **não** semeou | Ninguém tem conta de administrador. O sistema **tranca o admin para fora**, sem conta de fábrica | **Catastrófico** |
| Instalação **já trocou**, leitura falhou e semeou | A conta de fábrica reaparece; o diálogo de troca reabre e o administrador refaz a troca | **Transtorno** |

Na dúvida, **a conta existe**. O critério não é "seguro" em abstrato: é *qual dos
dois erros ainda tem saída*.

## 4. A REGRA: o seed do `master` existe só para **nascer** o sistema

> **EN:** The `master` seed exists so the system can be **born** with a way in.
> Once that first access happened, the seed must never create it again — not on
> restart, not on restore, not on any other path. The account is a **bootstrap
> device**, not a user.
>
> **PT-BR:** O seed do `master` existe para o sistema **nascer** com um caminho
> de entrada. Feito o primeiro acesso, ele nunca mais pode criar essa conta — nem
> no reinício, nem numa restauração, nem por qualquer outro caminho. A conta é um
> **dispositivo de partida**, não um usuário.

Três regras que decorrem disso:

| Regra | Onde vale |
|:---|:---|
| **A guarda é o fato, não a existência do login** | Qualquer seed que recrie o que um fluxo de segurança removeu tem de ler a **marca do fluxo**, não a ausência da linha |
| **A marca é gravada uma vez e é consultada sempre** | `forcar_troca_credenciais:master` no `tb_config` central — igual ao marcador de migração do versionamento |
| **Um caminho de criação por vez** | Se existirem dois lugares que criam a conta de fábrica, os dois precisam da marca; melhor ainda: um deles deixa de criar |

!!! note "Onde esta regra está escrita hoje"
    · [Módulo Gestão de Usuários — seeds](../modulos/gest_cad_usuario.md#a-regra-do-seed-de-master) ·
    [Análise do módulo de Gestão de Usuários — seeds idempotentes](../analise_mod_gest_cad_usuario.md#seeds-idempotentes-de-contas-agentsmd-82) ·
    [Análise de Risco — riscos conhecidos](../analise_de_risco/index.md) ·
    AGENTS.md §8.2 (conta de fábrica) e §4.2 (padrão do marcador).

## 5. O segundo caminho de criação — `bd_criador.py` bloqueado

`mod_gest_cad_usuario/bd_criador.py:72` tinha um **`INSERT` próprio de `master`**
com senha de fábrica — **sem** a marca que impede a ressurreição. Ele **não roda
no boot** (`mod_intranet/bd_criador.py:46` chama só
`mod_gest_cad_usuario.bd_manipulador.init_db()`), mas era uma **segunda porta
aberta para a mesma falha**: basta alguém chamá-lo, ou um `import` novo, e a
conta de fábrica volta sem nenhum dos controles.

O AGENTS.md §2.1 já marca `bd_criador.py` como **MORTO** desde a reestruturação
modular. Agora o código diz o mesmo que o AGENTS.md diz, em vez de depender de
quem lê a regra:

```python
# mod_gest_cad_usuario/bd_criador.py:39
def init_db():
    raise RuntimeError(
        "mod_gest_cad_usuario.bd_criador.init_db() isolado/morto — "
        "usar mod_gest_cad_usuario.bd_manipulador.init_db()")
```

O corpo legado foi preservado, renomeado para `_init_db_legado_morto()` (`:54`),
para que a leitura do que ele fazia — inclusive o `INSERT` de `master` — não se
perda. É **fail-loud**, o mesmo padrão já adotado em
`mod_edit_pdf/bd_criador.py:21`.

| Item | Onde |
|:---|:---|
| Criador **vigente** do esquema | `mod_gest_cad_usuario/bd_manipulador.py:init_db` |
| Criador **morto** (levanta) | `mod_gest_cad_usuario/bd_criador.py:init_db` |
| Corpo legado preservado | `mod_gest_cad_usuario/bd_criador.py:_init_db_legado_morto` |
| Precedente | `mod_edit_pdf/bd_criador.py:init_db` |

## 6. O ciclo travado do rename

A recusa de `renomear_usuario` passou a **dizer o que fazer**
(`bd_manipulador.py:1934`):

```python
return False, (f"'{novo_nome}' já é o login de outro usuário. "
               f"Escolha um nome de usuário diferente.")
```

Isso importava porque o diálogo de troca de credenciais traz o nome de usuário
**pré-preenchido num valor fixo** (`mod_intranet/telas.py:764` e `:1102`). Se
esse nome já existisse, o rename falhava — e as flags de troca **só caem depois
de um rename bem-sucedido** (`autenticacao.py:582-583`). O diálogo reabriria no
boot seguinte e falharia igual, **sem caminho de saída**.

Foi o que aconteceu na sessão anterior: existiam `klayton` e `master` ao mesmo
tempo, e a trilha de auditoria mostrava um
`renomear_usuario: master → klayton` bem-sucedido que **não correspondia a
nenhuma linha atual** — o login novo existia, mas a troca não tinha sido
persistida como concluída.

!!! warning "A mensagem de recusa é regra, não cortesia"
    Quando um fluxo **pré-preenche** um valor e o servidor só pode **avançar**
    depois de um `UPDATE` bem-sucedido, a recusa precisa **dizer qual valor
    mudar**. "Já existe" deixa quem instala sem saber que o campo é editável;
    a frase nova diz o campo, o motivo e a saída.

## 7. A armadilha do "estado que se auto-restaura" — como padrão

> **EN:** A seed that recreates what the credential change removed. The guard
> looked at the **existence of the login** and not at the **fact that the change
> happened** — so the removal the security flow had just performed was read as
> "missing" and undone on the next boot. Same family as the migration-order bug
> of the versioning: a guard that cannot tell "never happened" from "already
> happened" will always be wrong on one of the two.
>
> **PT-BR:** O seed que recria o que a troca de credenciais removeu. A guarda
> olhava a **existência do login** e não o **fato de a troca ter ocorrido** — e a
> remoção que o fluxo de segurança acabara de fazer foi lida como "falta" e
> desfeita no boot seguinte. É da mesma família do bug de ordem de migração do
> versionamento: uma guarda que não distingue "nunca aconteceu" de "já
> aconteceu" acerta uma das duas por acaso.

O padrão, escrito para ser reutilizado:

| Passo | Regra |
|:--:|:---|
| 1 | **Identifique o fato**, não o estado observável. A pergunta é *"a troca
concluiu?"*, não *"o login existe?"* |
| 2 | **Grave o fato** num lugar que **sobrevive ao reinício** — `tb_config`
central para estado que cruza módulos; nunca no código |
| 3 | **Faça a guarda ler o fato** antes de qualquer `INSERT` de seed, em **todo**
caminho que cria a mesma coisa |
| 4 | **Conte os caminhos.** Dois lugares que criam a mesma conta são duas
portas; tranque as duas, ou elimine uma |
| 5 | **Falhe para o lado recuperável.** Em dúvida de leitura, o estado que se
pode desfazer à mão é melhor do que o que tranca o admin para fora |

!!! tip "O mesmo padrão, três vezes no projeto"
    · **Migração de bump** (`bd_conexao.py`): marcador
    `migracao_versao_<chave>_AAMMDD` distingue "bump ainda não aplicado" de
    "já aplicado" — sem ele, o bump rebaixa a versão toda vez que roda
    ([Versionamento §3.1](../versionamento/index.md#31-o-modelo-da-migracao-de-bump)). ·
    · **Ordem das migrações** (`versionamento/index.md`, aviso da §1): a
    `migracao_padronizacao_260908` roda **depois** do seed e rebaixa em lote o
    que o seed criou — por isso a `migracao_versao_pendentes_260928` existe
    para desfazer. ·
    · **Esta correção**: a marca `forcar_troca_credenciais:master` distingue
    "troca pendente" de "troca concluída" — sem ela, o seed desfaz a troca.

## 8. Bump de versão (AGENTS.md §4.2)

Marcador **próprio** — `migracao_versao_usuarios_260929_seg` em
`mod_intranet/bd_conexao.py:318-333`. O `migracao_versao_usuarios_260929` que já
existia é da **primeira entrega do dia** (o `dialogo_formulario`), não desta
correção de segurança; dois deliveries no mesmo dia precisam de dois marcadores,
ou o segundo bump é engolido pelo primeiro.

```python
cur.execute("SELECT COUNT(*) FROM tb_config "
            "WHERE chave='migracao_versao_usuarios_260929_seg'")
if (cur.fetchone()[0] or 0) == 0:
    cur.execute("INSERT INTO tb_config (chave, valor) "
                "VALUES ('versao_modulo:usuarios', '1.0.260929') "
                "ON CONFLICT DO NOTHING")
    cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                "WHERE chave='versao_modulo:usuarios'")
    cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                "('migracao_versao_usuarios_260929_seg', '1') ON CONFLICT DO NOTHING")
```

`versao_modulo:usuarios` fica em **`1.0.260929`**, visível no rodapé de `/users`.
O SQL é portátil SQLite ↔ PostgreSQL pelo proxy `_CursorPostgres`
(AGENTS.md §4.1) e a idempotência é a do marcador.

## 9. Arquivos tocados

| Arquivo | Mudança |
|:---|:---|
| `mod_gest_cad_usuario/bd_manipulador.py` | `_troca_de_credencial_do_master_concluida()` (`:190`) · guarda do seed com duas condições (`:535`) · recusa de `renomear_usuario` com texto que orienta (`:1934`) |
| `mod_gest_cad_usuario/bd_criador.py` | `init_db()` levanta `RuntimeError`; corpo legado em `_init_db_legado_morto()` (`:39`, `:54`) |
| `mod_intranet/bd_conexao.py` | migração `migracao_versao_usuarios_260929_seg` (`:318-333`) |

**Nenhum banco foi tocado** por esta entrega: os `db_mod_*.db` não são
versionados, e a instalação em uso já foi limpa à mão (backup em `backup/`,
conferência em `logs/confere_bump_seguranca.py` e `logs/limpa_master.py`).

!!! note "Credenciais fora desta documentação"
    Os valores das senhas de fábrica e provisórias **não** são transcritos aqui.
    A conta nativa e as contas de teste estão descritas por **login + perfil +
    regra**; os valores vivem no código
    (`mod_gest_cad_usuario/bd_manipulador.py::init_db`, contexto interno do
    AGENTS.md §8.2). A senha padrão é **provisória**: qualquer fluxo de teste
    deve supor que ela **já pode ter sido trocada**.

## 10. Como conferir, sem escrever no banco

```python
# 1. a marca decide a ressurreição (leitura pura, sem escrita)
from mod_gest_cad_usuario.bd_manipulador import _troca_de_credencial_do_master_concluida
_troca_de_credencial_do_master_concluida()   # True = troca já concluída, não semeia

# 2. o estado do login, sem travar a senha na tela
from mod_gest_cad_usuario.bd_manipulador import obter_usuario
bool(obter_usuario("master"))   # False = a conta de fábrica saiu e não voltou

# 3. a versão do módulo no rodapé (leitura do tb_config central)
from mod_intranet.bd_conexao import get_config
get_config("versao_modulo:usuarios", "")      # '1.0.260929'
get_config("forcar_troca_credenciais:master", "")   # '0' = troca concluída
```

!!! warning "A verificação honesta é a do ciclo, não do instante"
    Confirmar que `master` está ausente **logo depois** da correção não prova
    nada — o seed só roda no boot. A prova é: **trocar → reiniciar → conferir →
    reiniciar de novo → conferir de novo**. Foi assim que o defeito apareceu
    (16:47:13 → 16:48:35) e foi assim que se confirmou que sumiu (boot 3 sem
    `master`).

## 11. O que fica escrito onde

| Assunto | Onde o leitor procura |
|:---|:---|
| Por que o `master` voltava, e a marca que impede | esta página |
| A **regra** do seed que só existe para nascer o sistema | [Módulo Gestão de Usuários](../modulos/gest_cad_usuario.md#a-regra-do-seed-de-master) |
| A tabela de seeds (login, perfil, regra) | [Análise do módulo — seeds idempotentes](../analise_mod_gest_cad_usuario.md#seeds-idempotentes-de-contas-agentsmd-82) |
| O marcador como padrão (mesma peça conceitual) | [Versionamento §3.1](../versionamento/index.md#31-o-modelo-da-migracao-de-bump) |
| O risco catalogado | [Análise de Risco](../analise_de_risco/index.md) |
| A entrega no histórico | [Registro de Mudanças](../registro_de_mudancas/index.md) |
| A conta de fábrica, para quem agenta | AGENTS.md §8.2 (contexto interno) |

Veja também: [Auditoria do Menu](auditoria_menu_2026-09-12.md) ·
[Ferramentas de Segurança](ferramentas_de_seguranca.md) ·
[Análise de Risco](../analise_de_risco/index.md).
