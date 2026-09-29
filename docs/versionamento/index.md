# Versioning — Intranet Modular

> Versioning scheme, the module-version keys in `tb_config`, the mandatory bump rule for every code change (AGENTS.md §4.2) and the migration that filled the six keys that were missing (28/09/2026). Format: `1.0.AAMMDD` (major.minor.date).

---

# Versionamento — Intranet Modular

> Esquema de versionamento, as chaves de versão dos módulos em `tb_config`, a
> regra de bump obrigatório a cada alteração de código (AGENTS.md §4.2) e a
> migração que preencheu as seis chaves que faltavam (28/09/2026). Formato:
> `1.0.AAMMDD` (major.menor.data).

## Padrão

- `1` — mudanças de paradigma de projeto.
- `0` — mudanças complexas.
- `AAMMDD` — ano, mês e dia de alterações pontuais.

Ex.: `1.0.260908` = 08/set/2026.

## Onde a versão mora

| Chave | Onde | Quem escreve |
|:---|:---|:---|
| `versao_sistema` | `tb_config` do banco **central** (`db_mod_intranet.db`) | seed em `bd_conexao.init_db()` (só quando a tabela nasce vazia) + campo na aba Config |
| `versao_modulo:<chave>` | `tb_config` do banco **central** | seed em `bd_conexao.init_db()` (`bd_conexao.py:171-191`) **+** migrações idempotentes |

O rodapé exibe as duas da esquerda para a direita: `v<versao_sistema>` e, quando
o usuário está dentro de um módulo, `v<versao_modulo:<chave>>`
(`mod_intranet/telas.py::_obter_versao_modulo`). Sem a chave do módulo, a
função devolve o fallback **`1.0`** — é exatamente o que aconteceu com seis
módulos e é o defeito que a [§4](#4-migracao-dos-modulos-sem-versao-28092026)
corrige.
## 1. As 13 chaves de módulo e quem as semeia

`MODULOS_BD` (`mod_intranet/repositorio.py`) tem **13 chaves**. Antes de
28/09/2026, **seis** delas não tinham `versao_modulo:<chave>` em `tb_config` e
caíam no fallback `1.0` do rodapé. Hoje as **13 têm chave**.

| Chave | Versão no seed | Versão efetiva | Origem da linha |
|:---|:---|:---|:---|
| `usuarios` | `1.0.260918` | `1.0.260929` | seed + `migracao_versao_usuarios_260918` + bump `260929` |
| `intranet` | — | `1.0.260929` | `migracao_versao_intranet_260913` + bump `260929` |
| `estoque` | `1.0.260928` | `1.0.260929` | seed + `migracao_versao_pendentes_260928` + bump `260929` |
| `lista_telefonica` | `1.0.260928` | `1.0.260929` | seed + `migracao_versao_pendentes_260928` + bump `260929` |
| `tecnico` | `1.0.260928` | `1.0.260929` | seed + `migracao_versao_pendentes_260928` + bump `260929` |
| `empenhos` | `1.0.260913` | `1.0.260913` | seed + `migracao_versao_empenhos_260913` |
| `solicita_impressao` | `1.0.260913` | `1.0.260913` | seed + bump 260913 |
| `agregador_noticias` | `1.0.260928` | `1.0.260928` | seed + `migracao_versao_pendentes_260928` |
| `filas` | `1.0.260928` | `1.0.260928` | seed + `migracao_versao_pendentes_260928` |
| `os` | `1.0.260928` | `1.0.260928` | seed + `migracao_versao_pendentes_260928` |
| `auditoria` | `1.0.260908` | `1.0.260908` | seed |
| `editar_pdf` | `1.0.260908` | `1.0.260908` | seed |
| `blog` | `1.0.260908` | `1.0.260908` | seed |

!!! danger "O seed sozinho NÃO alcança banco em uso"
    O `INSERT ... ON CONFLICT DO NOTHING` do seed roda em **todo** boot, mas só
    **insere** o que falta — ele nunca **corrige** uma chave que já existe com
    valor errado (nem vazio). Um módulo que entrou em `MODULOS_BD` **depois** de
    o tuple de seed existir precisa de uma **migração** para o banco já criado;
    sem ela, a instalação em uso fica com `1.0` no rodapé para sempre.

!!! warning "A ordem das migrações importa — e a 260928 foi escrita pensando nisso"
    A migração **`migracao_padronizacao_260908`** faz um **UPDATE em lote**:

    ```sql
    UPDATE tb_config SET valor='1.0.260908' WHERE chave LIKE 'versao_modulo:%'
    ```

    Ela roda **depois** do seed e rebaixa **todas** as linhas `versao_modulo:*`
    para `1.0.260908` — inclusive as seis que o seed de 28/09 acabou de criar
    com `1.0.260928`. É essa colisão que a `migracao_versao_pendentes_260928`
    existe para desfazer, e ela resolve porque o filtro do `UPDATE` **inclui
    `1.0.260908` na lista de placeholders**:

    ```python
    cur.execute("UPDATE tb_config SET valor='1.0.260928' "
                "WHERE chave=? AND (valor IS NULL OR valor='' "
                "OR valor IN ('1.0', '1.0.260908'))", (f"versao_modulo:{_chave_mod}",))
    ```

    Sem o `'1.0.260908'` nessa lista a correção **não entraria numa instalação
    nova**: o `INSERT` não faz nada (a chave já existe, criada pelo seed) e o
    `UPDATE` não casa com o valor rebaixado. Isso **foi** o bug real — a
    primeira versão do filtro aceitava só `NULL`/vazio/`1.0`, e o caminho de
    instalação nova não era exercitado por teste nenhum, porque o banco de
    desenvolvimento já existia e o `INSERT` pegava. Verificação 4 do
    `assets/test/teste_versionamento_modulo.py`: roda `init_db()` num banco
    inexistente e compara o resultado com o que o código declara.

    O que **não** entra nesse filtro é uma versão que já evoluiu para outra
    data — essa é bump futuro, e bump futuro não é da conta desta migração.

## 2. Por que `os` e `estoque` nasceram sem versão

Os dois módulos chegaram no commit `9a7d57d` (28/09) e o `MODULOS_BD` os
listou — mas **nenhuma linha correspondente entrou no tuple de seed** de
`bd_conexao.init_db()`. Sem a chave, `_obter_versao_modulo` caía no fallback
`1.0` e o rodapé mostrava `v1.0.260913 · v1.0`, sem distinguir o código de hoje
do de amanhã.

Os outros quatro (`agregador_noticias`, `lista_telefonica`, `filas`,
`tecnico`) tinham **débito anterior**: entraram em `MODULOS_BD` antes de o
tuple de seed existir.

## 3. A regra do bump obrigatório (AGENTS.md §4.2)

> **REGRA: toda e qualquer alteração de código em `mod_<nome>/` obriga a
> atualizar a versão daquele módulo. Sem exceção — nem correção de uma linha,
> nem docstring, nem comentário.**

A versão responde, no rodapé de qualquer tela do módulo, **qual código o banco
espera**. Sem ela não existe como distinguir "o banco está velho" de "o código
está velho" — que é exatamente a pergunta que se faz quando algo quebra depois
de uma entrega.

| Item | Regra |
|:---|:---|
| **Onde mora** | chave `versao_modulo:<chave>` na `tb_config` do banco **CENTRAL** (`db_mod_intranet.db`) — é dela que o rodapé lê (`_obter_versao_modulo`/`_formatar_versao_rodape`, `mod_intranet/telas.py`) |
| **Qual `<chave>`** | a de `MODULOS_BD` (`mod_intranet/repositorio.py`) — `usuarios` para `mod_gest_cad_usuario`, `empenhos` para `mod_renomear_empenho`. **O prefixo do diretório não é a chave** — é onde mais se erra |
| **Formato** | `X.Y.AAMMDD`, patch = **a data do dia**. Várias mudanças no mesmo dia = mesma versão, e está tudo bem: a versão data o CÓDIGO, não conta revisão |
| **Como aplicar** | **seed + migração**, os dois. O seed cobre banco novo; a migração cobre banco em uso. **Nenhum dos dois sozinho basta** |
| **SQL** | portátil SQLite ↔ PostgreSQL (AGENTS.md §4.1) — `ON CONFLICT DO NOTHING` e `SELECT COUNT(*)` já são traduzidos pelo proxy. **Nunca `sqlite3` cru** |
| **Idempotência** | marcador `migracao_versao_<chave>_AAMMDD` garante uma execução só. Teste rodando `init_db()` **duas vezes** e conferindo que a segunda não muda nada nem sobrescreve versão que o admin tenha mexido |
| **Quem faz** | quem altera o código. Commit que toca `mod_<nome>/` e não mexe na versão é commit incompleto |
| **Vários módulos** | cada módulo alterado ganha a **própria** migração. `mod_estoque/` + `mod_os/` no mesmo commit = dois bumps |

### 3.1 O modelo da migração de bump

```python
# mod_intranet/bd_conexao.py — formato já usado por migracao_versao_usuarios_260918
# Migração AAMMDD — bump de versão do módulo <chave> (<motivo curto>).
cur.execute("SELECT COUNT(*) FROM tb_config "
            "WHERE chave='migracao_versao_<chave>_AAMMDD'")
if (cur.fetchone()[0] or 0) == 0:
    cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '1.0.AAMMDD') "
                "ON CONFLICT DO NOTHING", (f"versao_modulo:<chave>",))
    cur.execute("UPDATE tb_config SET valor='1.0.AAMMDD' "
                "WHERE chave='versao_modulo:<chave>'")
    cur.execute("INSERT INTO tb_config (chave, valor) "
                "VALUES ('migracao_versao_<chave>_AAMMDD', '1') ON CONFLICT DO NOTHING")
```

!!! info "`migracao_versao_pendentes_260928` é a exceção, não o modelo"
    Ela é uma **migração de preenchimento**: cria a chave que faltava e só
    escreve onde ainda há placeholder. Existe porque seis módulos estavam sem
    versão e a 260908 rebaixa em lote — recover o valor rebaixado é o serviço
    dela. Para "mudei o código hoje" o modelo é o **acima**, sem condição de
    valor no `UPDATE`: a intenção é **sobrescrever** a versão anterior.

    E atenção ao detalhe que faz a §4.2 verificável: os marcadores de bump são
    escritos **literais**, um bloco por módulo, e não num `for` com f-string. Numa
    f-string o código-fonte tem `{_chave_mod}` e não `intranet` — o marcador
    some da leitura estática, e nem o `teste_versionamento_modulo.py` nem
    quem lê o diff consegue dizer que o bump existe.

### 3.2 Conferência antes de fechar a alteração

```bash
# 1. quais módulos foram tocados no diff
git diff --name-only HEAD~1 | grep -oE '^mod_[a-z_]+' | sort -u

# 2. para cada um, a versão em tela bate com a data de hoje?
.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('db_mod_intranet.db')
for k, v in c.execute(\"SELECT chave, valor FROM tb_config WHERE chave LIKE 'versao_modulo:%'\"):
    print(f'{k:<34}{v}')"
```

Faltou módulo no passo 1, ou a versão não é `1.0.<hoje>`? A alteração está
incompleta — faça o bump **antes** de commit.

### 3.3 Os três mecanismos que existem hoje

| Mecanismo | Onde | Situação |
|:---|:---|:---|
| **`tb_config` central** — `versao_modulo:<chave>` | `mod_intranet/bd_conexao.py` (seed + migrações) | ✅ **padrão** — é o que o rodapé lê |
| `_semear_versao_modulo()` | `mod_auditoria/bd_manipulador.py:761` e `mod_edit_pdf/bd_manipulador.py:278` | ⚠️ escreve a **MESMA chave central** — está de acordo, mas o número tem que **bater** nos dois |
| `versao_modulo` na `tb_configuracoes_modulo` | `mod_solicita_impressao/bd_manipulador.py:614` | ⚠️ chave **separada, no banco do próprio módulo** — exceção ainda não migrada. Ao tocar nele, migrar para a central em vez de criar uma terceira via |

### 3.4 Módulo novo

Ao criar `mod_<nome>/`:

1. declarar a chave em `MODULOS_BD` (`mod_intranet/repositorio.py`);
2. declarar a linha `("<chave>", "1.0.AAMMDD")` no tuple de seed de
   `bd_conexao.init_db()`;
3. gravar a **migração de bump** (§3.1) — o seed, sozinho, não alcança banco em
   uso.

!!! tip "Como conferir se alguma chave ainda falta (chave, não valor)"
    ```bash
    .venv/bin/python -c "
    import sqlite3
    from mod_intranet.repositorio import MODULOS_BD, DB_PATH
    c = sqlite3.connect(DB_PATH)
    faltando = [ch for ch in MODULOS_BD
                if not c.execute('SELECT valor FROM tb_config WHERE chave=?',
                                 (f'versao_modulo:{ch}',)).fetchone()]
    print('total de modulos:', len(MODULOS_BD))
    print('sem chave de versao:', faltando or 'nenhum')"
    ```

## 4. Migração dos módulos sem versão (28/09/2026)

Marcador **`migracao_versao_pendentes_260928`** — roda **uma vez** e é
idempotente nos dois backends (o proxy `_CursorPostgres` traduz
`ON CONFLICT DO NOTHING` e o `SELECT COUNT(*)` do marcador, AGENTS.md §4.1).

```python
# mod_intranet/bd_conexao.py:264-276
cur.execute("SELECT COUNT(*) FROM tb_config "
            "WHERE chave='migracao_versao_pendentes_260928'")
if (cur.fetchone()[0] or 0) == 0:
    for _chave_mod in ("agregador_noticias", "lista_telefonica", "filas",
                       "tecnico", "os", "estoque"):
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '1.0.260928') "
                    "ON CONFLICT DO NOTHING",
                    (f"versao_modulo:{_chave_mod}",))
        cur.execute("UPDATE tb_config SET valor='1.0.260928' "
                    "WHERE chave=? AND (valor IS NULL OR valor='' OR valor='1.0')",
                    (f"versao_modulo:{_chave_mod}",))
    cur.execute("INSERT INTO tb_config (chave, valor) "
                "VALUES ('migracao_versao_pendentes_260928', '1') ON CONFLICT DO NOTHING")
```

| Passo | O que faz | Por quê |
|:---|:---|:---|
| `INSERT ... ON CONFLICT DO NOTHING` | cria a chave se não existir | **não** sobrescreve nada |
| `UPDATE ... WHERE valor IS NULL OR valor='' OR valor='1.0'` | preenche só onde ainda está vazio/NULL/**`1.0`** | uma versão que o administrador já ajustou **não** é tocada |
| marcador `migracao_versao_pendentes_260928 = '1'` | trava a execução | a migração é de uma vez; o seed segue responsável pelas linhas novas |

!!! note "Por que `1.0` conta como 'vazio' para esta migração"
    `1.0` é o **fallback** de `_obter_versao_modulo` — o valor que aparece
    quando a chave não existe. Tratar `1.0` como "ainda não versionado" é o que
    faz a migração alcançar justamente o banco onde o defeito está, sem
    arriscar sobrescrever uma versão cadastrada de verdade (que nunca seria
    `1.0`, já que o formato do projeto é `1.0.AAMMDD`).

!!! note "Esta migração é de PREENCHIMENTO, não de bump"
    Ela cria a chave que faltava. O bump de código de hoje é outro mecanismo —
    ver [§3.1](#31-o-modelo-da-migracao-de-bump), que **sobrescreve** a versão
    em vez de só preencher a lacuna.

## 5. Versionamento do produto

- README: `version-1.0.260908` (badge).
- Build MkDocs em `site/`, montado em `/documentacao`.

Veja [Registro de Mudanças](../registro_de_mudancas/index.md) para o histórico
de alterações e [Módulos (resumo) — Intranet](../modulos/intranet.md) para a
fábrica de componentes onde a versão é exibida.
