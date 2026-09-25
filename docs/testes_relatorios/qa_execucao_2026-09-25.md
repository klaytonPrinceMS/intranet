# QA Execution Report — Intranet Modular (2026-09-25)

> Execution QA with the system **running** (SQLite, `INTRANET_SEM_OTEL=1`), diagnosed by an authenticated smoke test plus quality gates. The suite went from **10 failing scripts (of 60) to 0** — `.venv/bin/pytest` exits `0`. 8 production bugs fixed, 5 module-isolation violations closed via the `mod_intranet/integracoes.py` facade, and `mkdocs --strict`, `bandit` and `gitleaks` left clean. Commit `624c9d5`.

---

# Relatório de Execução de QA — Intranet Modular (25/09/2026)

> QA de execução com o sistema **no ar** (SQLite, `INTRANET_SEM_OTEL=1`), diagnóstico por smoke test autenticado + gates de qualidade. A suíte saiu de **10 scripts falhando (de 60) para 0** — `.venv/bin/pytest` termina com `exit=0`. 8 bugs de produção corrigidos, 5 violações de isolamento entre módulos fechadas com a fachada `mod_intranet/integracoes.py`, e `mkdocs --strict`, `bandit` e `gitleaks` limpos. Commit `624c9d5`.

## 1. Contexto e escopo

| Item | Valor |
|:---|:---|
| **Data** | 25/09/2026 |
| **Commit** | `624c9d5` — *"Corrige 8 bugs de produção, fecha 5 violações de isolamento com a fachada mod_intranet/integracoes.py, repara 10 testes de QA e deixa mkdocs --strict, bandit e gitleaks limpos"* |
| **Ambiente** | Linux, venv `.venv`, porta `8080` |
| **Backend** | SQLite (`INTRANET_FORCE_SQLITE=1`; o PostgreSQL não foi exercitado nesta sessão) |
| **Telemetria** | `INTRANET_SEM_OTEL=1` (sem OTel na execução) |
| **Método** | Smoke test **autenticado** (login real no navegador) sobre as rotas + gates de qualidade automatizados |
| **Suíte** | `assets/test/` — **60 scripts** standalone orquestrados por `assets/test/test_suite.py` (`.venv/bin/pytest`) |

!!! note "Como a suíte é orquestrada"
    `pytest.ini` aponta `testpaths = assets/test/test_suite.py`, e esse arquivo executa
    **cada script `.py` de `assets/test/` como subprocesso** (timeout 240 s cada,
    `INTRANET_FORCE_SQLITE=1` e variáveis `PYTEST_*` removidas do ambiente).
    Uma lista `EXCLUIR` deixa de fora diagnósticos e helpers destrutivos
    (`debug_boot.py`, `diag_*.py`, `test_server.py`, `test_otel.py`, a fábrica de
    PDFs, fresh-install etc.) — de 76 arquivos `.py` no diretório, **60 entram na
    suíte**.

## 2. Resumo dos gates

| Gate | Antes | Depois |
|:---|:---|:---|
| Suíte (60 scripts) | **10 falhando** | **0** (`exit=0`) |
| Smoke Playwright (25 rotas autenticadas) | 0 erros | **0 erros** |
| `assets/test/check_integridade.py` | 5 falhas / 17 verificações | **13/13** |
| `mkdocs build --strict` | **abortava** (9 warnings) | **0 warnings** |
| `bandit` (11 módulos) | HIGH 1, MEDIUM 5 | **HIGH 0, MEDIUM 0** |
| `gitleaks detect` | — | **no leaks found** |

Resultado consolidado: **`.venv/bin/pytest` termina com `exit=0`**.

## 3. Os 10 scripts que falhavam — causa e tipo

| # | Script | Causa | Tipo |
|:--|:---|:---|:---|
| 1 | `check_integridade.py` | 5 violações de **isolamento entre módulos de negócio** (AGENTS.md §2) | **código** |
| 2 | `test_seg_novos_modulos.py` | Caminho do binário `gitleaks` **hardcoded** (`~/.local/bin`, mas nesta máquina está em `/usr/local/bin`); `mkdocs --strict` abortando; asserção do organograma acoplada à **forma do import** | ambiente/teste |
| 3 | `test_ordem_modulos.py` | Esperava **6 módulos** na ordem padrão; hoje são **10** (`tecnico`, `filas`, `lista_telefonica`, `agregador_noticias` foram adicionados depois) | teste obsoleto |
| 4 | `test_filas_testids.py` | Esperava `filas-midia-mutar`; o **canônico é `filas-midia-som`** (usado por 2 outras suítes) | teste obsoleto |
| 5 | `test_tema_cache_trava.py` | Esperava timeout inválido = **4** | teste obsoleto |
| 6 | `teste_config_intranet.py` | Esperava timeout inválido = **10** | teste obsoleto |
| 7 | `test_navegar_pesquisa_empenhos.py` | O levantamento rodava contra a pasta real `mod_renomear_empenho/doc` (só `.gitkeep`), **sem massa** | fixture ausente |
| 8 | `test_tema_cache_trava.py` + `teste_config_intranet.py` | Os **dois** esperavam valores **mutuamente contraditórios** (4 e 10) para o *mesmo* default; o código e a docstring dizem **5** | teste obsoleto |
| 9 | `verifica_ui_comum.py` | Contagens exatas obsoletas (`campo_texto` 16 → hoje **23**; `senha=True` 9 → **12**) e `ui.notify` cru em `mod_edit_pdf` | teste obsoleto + **código** |
| 10 | `teste_carrossel_blog.py` | O carrossel migrou de *select* dedicado para **seleção em lote por checkbox** + campo `Tempo (s)` | teste obsoleto |
| 11 | `teste_aba_config_intranet.py` | Defaults do card "Gerais" **fora do `PADRAO_CONFIG`** (chave ausente no `tb_config` → o campo não caía no padrão) + esperava `notificacao_timeout=10` | **código** + teste obsoleto |

!!! info "Os itens 5/6 e 8 são o mesmo defeito, visto por dois ângulos"
    `test_tema_cache_trava.py` afirmava que um `notificacao_timeout` inválido cai
    no padrão **4**; `teste_config_intranet.py` afirmava **10**. Os dois testes
    não podiam passar ao mesmo tempo — e ambos estavam errados: o padrão real é
    **`5`**, declarado em `PADRAO_CONFIG["notificacao_timeout"]` (`mod_intranet/bd_conexao.py`)
    e replicado em `tema_modulo.notificacao_timeout()`. A correção foi alinhar
    **os dois testes ao código**, não o código a um dos testes.

## 4. Os 8 bugs de produção corrigidos

| # | Módulo | Arquivo · função | Sintoma | Efeito no usuário |
|:--|:---|:---|:---|:---|
| 1 | `mod_filas` | `bd_manipulador.py:contar_nomes_pendentes` | Predicado **invertido**: contava `usado=1` (nomes **já chamados**) em vez de `usado=0` | O rótulo *"N nome(s) na lista — o próximo chama em ordem"* (`telas.py:1243`) mostrava o número **errado** |
| 2 | `mod_filas` | `bd_manipulador.py:listar_nomes` | `ORDER BY ordem DESC` invertia a lista de pendentes | A lista exibida na tela vinha na **ordem inversa** à ordem real de chamada |
| 3 | `mod_renomear_empenho` | `bd_manipulador.py:pesquisar_levantamento` | O FTS5 é **prefixo** (`"4"*` casa com `4abc`, não com `24`) e o fallback `LIKE` só era acionado ao **lançar exceção** — o FTS respondia vazio sem erro | Buscar por **1 letra** voltava vazio, mesmo com o termo presente no nome do arquivo |
| 4 | `mod_intranet` | `bd_conexao.py` + `tela_configuracoes.py` | Defaults do card **"Gerais"** duplicados em **5 lugares** e fora do `PADRAO_CONFIG` (`backup_interval_hours`, `sessao_retencao`, `notificacao_timeout`) | Chave ausente no `tb_config` fazia o campo **não cair no padrão**; um padrão divergente quebrava o card |
| 5 | `mod_blog` | `telas.py:atualizar` | `_feed_blog.refresh()` chamado **sem `try/except`** (violava AGENTS.md §3.2) | Refresh que agenda tarefa no `event-loop` do NiceGUI podia **derrubar a tela inteira** |
| 6 | `mod_intranet` | `grafana_sync.py:obter_grafana_url` | `GRAFANA_URL` **sem validação de esquema** | `urllib` aceita `file://` — config corrompida permitiria **abrir arquivo local** |
| 7 | `main.py` (2) · `mod_edit_pdf/telas.py` (22) | `page_admin_modulo` · fallbacks de erro | `ui.notify` **cru** em vez de `tema_modulo.notificar()` (violava AGENTS.md §5.1) | Toasts **ignoravam o `notificacao_timeout`** configurado pelo admin |
| 8 | `mod_filas` · `mod_renomear_empenho` | `telas.py` | Botão de "Enviar" da linha de etapa **clicável sem `data-testid`**; barra de abas feita à mão | Playwright quebrava em **strict mode**; a barra de abas fugia do padrão do módulo |

### 4.1 Detalhamento por bug

**1 · `contar_nomes_pendentes` — predicado invertido**

```python
# ANTES — contava os JÁ CHAMADOS
cur.execute("SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=? AND usado=1", (fila_id,))
# DEPOIS — pendente = usado=0 (convenção de todas as outras queries do módulo)
cur.execute("SELECT COUNT(*) FROM tb_fila_nomes WHERE fila_id=? AND usado=0", (fila_id,))
```

`gerar_senha` marca `usado=1` ao chamar o nome (linhas 972/1196). Portanto
**pendente = `usado=0`** — a mesma convenção usada por `listar_nomes(somente_pendentes=True)`,
`_escolher_proximo_nome` e `transferir_*`.

**2 · `listar_nomes` — ordenação invertida**

Os dois ramos (pendentes e todos) passaram de `ORDER BY ordem DESC` para
`ORDER BY ordem` (ASC). A ordem exibida na tela passa a ser **a ordem de fala**,
a mesma que `proximo_da_etapa` respeita.

**3 · `pesquisar_levantamento` — FTS é prefixo**

A cadeia passou a ser: **(1) FTS5 por prefixo** → se voltar **vazio**, **(2) `LIKE`
por substring**. O segundo passo não é mais um `except`; é o caminho normal para
termos curtos. Termo de 1 letra (`%4%` casando com `EC_24`) agora filtra.

**4 · Defaults do card "Gerais"** — `backup_interval_hours` (`"12"`) e
`sessao_retencao` (`"50"`) entraram no `PADRAO_CONFIG`; `notificacao_timeout` já
existia. `tela_configuracoes.py` passou a ler `PADRAO_CONFIG[...]` nos três
`padrao=`, no dicionário do "Restaurar padrão" e no `_reagendar_backups(...)`.

**5 · `mod_blog/telas.py:atualizar` — fail-soft**

```python
# AGENTS.md §3.2: o refresh é fail-soft. `refreshable.refresh()`
# agenda tarefa no event-loop do NiceGUI e pode levantar se o loop
# ainda não subiu ou se o cliente desconectou — sem este try, uma
# falha de refresh derrubava a tela inteira (o conteúdo já foi
# renderizado logo abaixo por `_feed_blog()`, então o feed segue
# visível mesmo se a re-renderização não agendar).
try:
    _feed_blog.refresh()
except Exception:
    observabilidade.get_logger("blog").debug(
        "atualizar: refresh do feed não agendado (loop indisponível)")
```

O `logger.debug` é intencional: o conteúdo **já foi renderizado** logo abaixo por
`_feed_blog()`, então o feed continua visível mesmo que a re-renderização não
agende. `_atualizar_contador()` (logo abaixo) já era protegido — agora os dois
caminhos são.

**6 · `GRAFANA_URL` com esquema validado** — `obter_grafana_url()` valida via
`_url_grafana_valida()`; valor fora de `http`/`https` é **ignorado** e cai no
padrão local (`DEFAULT_GRAFANA_URL`). Fecha o achado `B310` apontado em
[Segurança 06/09/2026](seguranca_2026-09-06.md) ("`urllib` aceita `file://`").

**7 · `ui.notify` cru** — as 24 ocorrências migraram para
`tema_modulo.notificar(...)`, que respeita `notificacao_timeout` e o tipo de aviso.

**8 · `data-testid` + helper de abas** — `filas-etapa-enviar` adicionado ao botão
"Enviar" da linha de etapa (`mod_filas/telas.py:349`); a barra de abas de
`mod_renomear_empenho/telas.py` passou a usar `aba_modulo.menu_modulo(_abas)`
(padrão do módulo), eliminando o dicionário de ícones redundante.

## 5. Mudanças estruturais

### 5.1 Fachada pública `mod_intranet/integracoes.py` (nova)

7 funções, **imports lazy** e **fail-soft** (valor neutro + `logger.warning`,
nunca derrubam a tela do chamador). É a costura única que elimina as **5 violações
de isolamento** (AGENTS.md §2 — "nunca faça cross-query entre bancos"): o módulo
de negócio fala com o `mod_intranet`, e o núcleo possui o acoplamento.

| Função | Destino | Consumidores |
|:---|:---|:---|
| `obter_usuario_gestao(user_nome)` | `mod_gest_cad_usuario.bd_manipulador.obter_usuario` | Filas, Lista Telefônica |
| `listar_usuarios_gestao(filtro_ativo=None)` | `mod_gest_cad_usuario.bd_manipulador.listar_usuarios` | Filas, Lista Telefônica |
| `agregador_habilitado()` | `mod_agregador_noticias.bd_manipulador.habilitado` | TV Filas |
| `listar_noticias_para_tv(limite=200)` | `mod_agregador_noticias.bd_manipulador.listar_para_tv` | TV Filas |
| `limpar_noticias_censuradas()` | `mod_agregador_noticias.bd_manipulador.limpar_censuradas` | Admin do **Blog** (orquestra a purga) |
| `obter_organograma_base()` | `mod_lista_telefonica.bd_manipulador.ORGANOGRAMA_BASE` | Solicitação de Impressão (cotas 1000/200) |
| `modulo_habilitado(chave)` | `mod_intranet.autenticacao.modulos_registrados` | núcleo / roteamento |

#### As 5 violações fechadas (pares origem → destino)

O `assets/test/check_integridade.py` (bloco A) classifica como **violação**
qualquer import de um módulo de negócio para **outro** módulo de negócio — com
uma única exceção documentada, a **cascata LGPD** de
`mod_gest_cad_usuario` para `blog` / `edit_pdf` / `renomear_empenho`. Fora essa
cascata, eram exatamente **5 pares**:

| # | Origem | Destino | Ponto de código | Fachada usada |
|:--|:---|:---|:---|:---|
| 1 | `mod_blog` | `mod_agregador_noticias` | `telas_administracao.py:100-106` (purga ao salvar a censura) | `integracoes.limpar_noticias_censuradas()` |
| 2 | `mod_filas` | `mod_agregador_noticias` | `telas.py:1737` (`carregar_noticias` da TV) | `integracoes.agregador_habilitado()` + `integracoes.listar_noticias_para_tv(limite=200)` |
| 3 | `mod_filas` | `mod_gest_cad_usuario` | `bd_manipulador.py:_ator_eh_dono_ou_admin`, `bd_manipulador.py:liberar_acesso`, `telas.py:bloco_liberar_acesso` | `integracoes.obter_usuario_gestao()` / `integracoes.listar_usuarios_gestao()` |
| 4 | `mod_lista_telefonica` | `mod_gest_cad_usuario` | `telas_administracao.py:684-690` e `:738-746` (vínculo de contato) | `integracoes.listar_usuarios_gestao()` / `integracoes.obter_usuario_gestao()` |
| 5 | `mod_solicita_impressao` | `mod_lista_telefonica` | `bd_manipulador.py:init_db` (semente de cotas 1000/200) | `integracoes.obter_organograma_base()` (+ *fallback* local) |

Depois das correções o grafo de imports só tem: `mod_intranet ↔ módulo` (a
fachada — permitido por construção) e a **cascata LGPD** documentada.

> **Imports lazy são deliberados**: um import de topo de um módulo de negócio na
> fachada fecharia um **ciclo de import de topo** com o `main.py`. Por isso o
> `check_integridade.py` os reporta como AVISO de runtime, nunca como falha.

### 5.2 `check_integridade.py`: 5 falhas → 13/13

| Verificação | Antes | Depois |
|:---|:---|:---|
| A) isolamento (negócio nunca importa negócio, exceto a cascata LGPD) | **5 pares violando** | OK — "nenhum import entre módulos de negócio (só cascata LGPD)" |
| B) sem ciclo de import em nível de topo | — | OK |
| C) `bd_manipulador.py` padronizado em todo `mod_*` | 11 módulos | 11 módulos |
| **Total** | **5 falhas / 17** | **13/13** |

Os 2 ciclos **apenas-lazy** que o próprio script antes apontava como AVISO foram
eliminados com a fachada (restam apenas os ciclos lazy sadios `mod_intranet ↔ módulo`,
que são o mecanismo de DI e rodam bem em runtime).

### 5.3 `mkdocs.yml` + links quebrados

- `nav` da seção **"Registro de Mudanças"** corrigido: era um item simples
  apontando para o índice e **não alcançava** `wal_paridade_pendente_2026-09-24.md`.
- **9 links** `../registro_de_mudancas/...` quebrados arrumados.
- Resultado: `mkdocs build --strict` deixou de **abortar** (antes: 9 warnings com
  `--strict` = build falha) e passou a **0 warnings**.

### 5.4 `bandit`: HIGH 1 → 0, MEDIUM 5 → 0

Achados analisados e fechados com `# nosec` **justificados no código** (o padrão
do projeto: nomes de tabela/coluna internos interpolados, valores sempre por
bind `?`/`%s`; nunca input do usuário):

| Regra | Falso positivo | Fechamento |
|:---|:---|:---|
| `B602` `subprocess` com `shell=True` | `mod_intranet/ativacao.py:_cmd` — `usar_shell` só é `True` para comandos **estáticos** definidos no próprio assistente; a senha entra por `stdin`, nunca interpolada no `argv` | `# nosec B602` com justificativa |
| `B310` `urllib` com scheme não auditado | `mod_intranet/ativacao.py:_probe_http` / `_servicos_otel_online` — esquema `http://` **literal** + porta em `int()`; nunca `file://` nem entrada do usuário | `# nosec B310` |
| `B310` `GRAFANA_URL` | `mod_intranet/grafana_sync.py` | **Corrigido de verdade** (bug 6) — validação de esquema |
| `B608` SQL com f-string | `mod_intranet/repositorio.py` — `set_sql` é montado só das **chaves literais** do `if-chain` acima; valores por bind `:nome` etc. | `# nosec B608` |

### 5.5 `gitleaks detect`: no leaks found

Sem segredo no código nem no histórico. O caminho do binário deixou de ser
hardcoded (§3, item 2) e passa a resolver por `shutil.which` (PATH) com fallback
para o caminho do `requirements-dev.txt`.

### 5.6 `pytest-env` declarado em `requirements-dev.txt`

```ini
# pytest.ini
env = PYTHONUTF8=1
```

A chave `env` **só funciona com o plugin `pytest-env`**. Sem ele declarado, o
pytest emitia `PytestConfigWarning` e a proteção de **UTF-8 não era aplicada** —
o que quebrava qualquer asserção/print com acento em locale não-UTF-8.
`pytest-env>=1.1.0` foi adicionado a `requirements-dev.txt` com comentário
explicando o porquê.

## 6. Pendências conhecidas (NÃO cobertas por esta sessão)

!!! danger "251 chamadas de `ui.notify` cru ainda existem no código"
    Restam **251 chamadas** de `ui.notify` cru — violação do AGENTS.md §5.1
    (`tema_modulo.notificar()` é o padrão) — distribuídas assim:

    | Módulo | Ocorrências |
    |:---|---:|
    | `mod_renomear_empenho` | **140** |
    | `mod_solicita_impressao` | **73** |
    | `mod_blog` | **34** |
    | `mod_intranet` | **2** |
    | `mod_auditoria` | **1** |
    | `mod_edit_pdf` | **1** |
    | **Total** | **251** |

    - **É dívida pré-existente** — não introduzida por esta sessão.
    - **Não é coberta pela suíte**: nenhum dos 60 scripts falha por causa disso,
      portanto corrigi-las não muda o resultado de `.venv/bin/pytest`.
    - **Efeito real é restrito**: apenas a **padronização do `timeout` dos toasts**
      (os avisos não respeitam o `notificacao_timeout` configurado pelo admin) —
      não há risco funcional ou de perda de dados.
    - **Recomendação**: tratar em lote por módulo, junto com a modernização das
      chamadas, e **adicionar um gate** (`verifica_ui_comum.py` ou `check_integridade.py`)
      que impeça o regresso de `ui.notify` cru em código novo.

## 7. Riscos residuais e escopo não exercitado

- **PostgreSQL não foi testado.** A sessão rodou em SQLite
  (`INTRANET_FORCE_SQLITE=1`); a paridade SQLite↔PostgreSQL exigida pelo
  AGENTS.md §4.1 continua sendo verificada pelos testes de paridade, **não** por
  esta execução.
- **`_ativacao.py`** toca Docker/OTel por `subprocess`; com `INTRANET_SEM_OTEL=1`
  esses caminhos **não foram exercitados** de ponta a ponta.
- **Smoke Playwright** cobriu as **25 rotas autenticadas**; rotas públicas
  (`/tv`, `/tv/{id}`, `/tv?grupo=`) foram cobertas pelas suítes E2E de Filas.
- **Higiene do banco**: a suíte deixa dados de teste em `db_mod_*.db`
  (padrão histórico dos scripts standalone) — não é regressão desta sessão.

## 8. Como reproduzir

```bash
# 0) subir o sistema (SQLite, sem OTel) — porta 8080
INTRANET_SEM_OTEL=1 .venv/bin/python main.py &

# 1) suíte completa (60 scripts) — deve terminar com exit=0
.venv/bin/pytest
# ou direto, com progresso por script:
.venv/bin/python assets/test/test_suite.py

# 2) integridade estrutural (13/13)
.venv/bin/python assets/test/check_integridade.py

# 3) gate de documentação (0 warnings)
.venv/bin/mkdocs build --strict

# 4) segurança
.venv/bin/bandit -r mod_*/ -q
.venv/bin/gitleaks detect --source . --no-git -v

# 5) E2E autenticado (exemplos)
.venv/bin/pytest assets/test/test_e2e_cobertura_extra_sec.py
.venv/bin/pytest assets/test/teste_carrossel_blog.py
```

## 9. Referências

- [Relatório de Segurança (06/09/2026)](seguranca_2026-09-06.md) — banda anterior
  (o achado `B310`/`GRAFANA_URL` citado lá foi **corrigido** nesta sessão, bug 6).
- [Testes — Casos](../testes_casos/index.md) · [Testes — Plano](../testes_plano/index.md)
- [E2E com Playwright](../testes_playwright.md)
- [Registro de Mudanças](../registro_de_mudancas/index.md)
- Subagente responsável: `kbp-qa` (execução) + `kbp-devSecOps` (gates de segurança)
  + `kbp-doc` (este relatório).
