# Queue Module — `mod_filas` (Skeleton + News Carousel)

> Queue/call manager module (skeleton, TV): routes `/filas` (key `filas`) + `/tv` (public) · own database `db_mod_filas.db` (WAL) · tables `tb_fila`/`tb_chamada`/`tb_config_filas` · next password `A000→A001` · TV auto-refresh 3s + beep + **news carousel** from `mod_agregador_noticias` (`listar_para_tv` 7s rotate / 120s reload) · central LGPD audit.

---

# Módulo Filas — `mod_filas` (Esqueleto TV + Carrossel Notícias)

> Módulo gestor de filas/chamadas (esqueleto, TV): rotas `/filas` (chave `filas`) + `/tv` (pública) · banco próprio `db_mod_filas.db` (WAL) · tabelas `tb_fila`/`tb_chamada`/`tb_config_filas` · próxima senha `A000→A001` · TV auto-refresh 3s + beep + **carrossel de notícias** do `mod_agregador_noticias` (`listar_para_tv` 7s/120s) · auditoria central LGPD.

## Propósito

Esqueleto **a título de conhecimento** do futuro gestor de chamadas para atendimento com TV na rede interna — rota `/filas` (painel de filas) + `/tv` (painel full-screen para TV). Já operacional com fluxo mínimo: uma fila "Geral" semeada, incremento de senha e display da última chamada. Regras completas (múltiplas filas, prioridade, guichês, som, integração) serão detalhadas em iteração futura.

> Status: `SKELETON = True` (`mod_filas/__init__.py:7`). Estrutura pronta (DB + telas + admin + rotas), sem impacto no core.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:34-68` (bootstrap central + `init_db()` no import).

| Tabela | Conteúdo |
|:---|:---|
| `tb_fila` | `id` PK, `nome` UNIQUE (`Geral` semeada), `senha_atual` (`A000` default), `status` (`ativa`), `guiche` (`01` default), `data_criacao` |
| `tb_chamada` | `id` PK, `fila_id` FK CASCADE → `tb_fila`, `senha` (ex.: `A001`), `guiche` (snapshot do `tb_fila.guiche`), `chamado_em` (timestamp), `chamado_por` (login ator) |
| `tb_config_filas` | chave-valor local (`filas_modo_tv`=`1`, `filas_senha_prefixo`=`A`, `filas_guiche_padrao`=`01`) |

Seed: `INSERT OR IGNORE INTO tb_fila (nome, senha_atual, status, guiche) VALUES ('Geral','A000','ativa','01')` (`bd_manipulador.py:66`). Conexão via `mod_intranet/banco_conexao.conexao("filas")` (WAL + `foreign_keys=ON`, backend duplo SQLite/PostgreSQL). Auditoria via `audit_log` → `db_mod_auditoria.db`, tabela `tb_auditoria_filas` (`gerar_senha`).

⚠️ O `bd_criador.py` do módulo é **legado/morto** — não executar (o schema real está em `bd_manipulador.py`).

Modelos tipados (`models/__init__.py` — dataclasses `Fila`/`Chamada`, sem `map_imperatively` ainda): `Fila(id, nome, senha_atual, status, guiche)`, `Chamada(id, fila_id, senha, guiche, chamado_em, chamado_por)`.

## Funcionalidades

### Painel `/filas` — gestor de chamadas (skeleton)

- **Gate** (`_pode_acessar` — `telas.py:16-22`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "filas")` — sem acesso → "Acesso restrito".
- **Cabeçalho temático** (`telas.py:31-36`): `ler_tema("filas", cor_botao="#000000", texto_header="Gestor de chamadas para atendimento (TV). Esqueleto a título de conhecimento.")` + `ui.colors(primary=tema["cor_botao"])` + `cabecalho("Filas — Chamadas", ..., chave_modulo="filas")` (borda = `cor_botao` via `PADROES_TEMA["filas"]` → `#000000`).
- **Card Filas (esqueleto)** (`telas.py:37-58`): `listar_filas()` (`SELECT id,nome,senha_atual,status,guiche`); por fila renderiza `nome` + `Senha atual: X • Guichê: Y • status` + botão `Chamar próximo` (`campaign`, `primario`, `chave_modulo="filas"`) que chama `gerar_senha(fid, ator=user)` + `ui.notify` + `render()`; botão `Abrir TV` (`tv`, `contorno`, `data-testid=filas-abrir-tv`, `ui.navigate.to("/tv")`).
- **Card Última chamada (preview TV)** (`telas.py:58-70`): `ultima_chamada()` (`SELECT senha,guiche,chamado_em ORDER BY id DESC LIMIT 1`); exibe `Senha: A001` (`text-h4 font-extrabold text-primary`) + `Guichê: 01 • data`; histórico 5 últimas (`listar_chamadas(5)` — `senha — guichê — por — data`). Sem chamada → "Nenhuma chamada ainda.".

#### `gerar_senha` — incremento simples (`bd_manipulador.py:79-107`)

```python
atual = SELECT senha_atual FROM tb_fila WHERE id=?
# regex r"([A-Za-z]*)(\d+)" → pref + num+1 com :03d
nova = f"{pref}{num+1:03d}"  # A000→A001, sem letra → A001
UPDATE tb_fila SET senha_atual=nova
INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por)
  VALUES (?, nova, (SELECT guiche FROM tb_fila WHERE id=?), ator)
_audit(ator, "gerar_senha", nova, f"fila={fila_id}")
```

Fail-soft: `try/except` + log `filas` + `(False, str(e))`.

### Painel `/tv` — display full-screen (público) + carrossel de notícias

- **Rota** `/tv` (`main.py:745-749`): **sem `pagina_restrita`** — acesso livre na rede (TV na recepção); `from mod_filas.telas import mostrar_tv; mostrar_tv()`.
- **Layout** (`mostrar_tv` — `telas.py:72-137`): `ui.column` `w-full h-screen bg-black text-white gap-4 p-4` + topo `lbl_topo` `"FILA — AGUARDE CHAMADA"` (`text-[2vw] tracking-widest text-grey-4`) + `lbl_senha` (`text-[10vw] font-extrabold`) + `lbl_guiche` (`text-[4vw] font-bold`) (`flex-1` centralizado); **rodapé notícias** `card bg-grey-900 text-white p-4 gap-2 min-height:18vh` com `lbl_n_titulo` (`text-[1.6vw] font-bold`), `lbl_n_desc` (`text-[1vw] text-grey-3`), `lbl_n_fonte` (`text-caption text-grey-5`) + label `"Notícias — agregador"` (`text-caption tracking-widest text-grey-4`); `tema = ler_tema("filas")` + `ui.colors(primary=...)`.
- **Auto-refresh 3s** (chamada): `ui.timer(3.0, refresh_chamada)` + `refresh_chamada()` imediato — `ultima_chamada()` → `lbl_senha`/`lbl_guiche` + beep via `ui.run_javascript("new AudioContext().createOscillator()...")` (fail-soft). Sem chamada mantém "—".
- **Carrossel de notícias 7s + reload 120s** (`telas.py:84-136`): `noticias_tv={"lista":[], "idx":0}` + `carregar_noticias()` (`telas.py:103-119`) → `from mod_agregador_noticias.bd_manipulador import listar_para_tv, habilitado` → se `not habilitado()` → `"Agregador desabilitado — ative em /admin/agregador_noticias"`; senão `listar_para_tv(limite=10)` (`SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY data_coleta DESC LIMIT ?` → `[{"titulo","descricao":desc or titulo,"url","imagem","fonte","tema"}]`) → `noticias_tv["lista"]=lst` + `_mostrar_noticia()`; se vazio → `"Nenhuma notícia ainda — aguarde coleta"`; `ui.timer(7.0, _mostrar_noticia)` rotaciona `idx % len` com `lbl_n_titulo[:120]` + `lbl_n_desc[:180]` + `fonte • tema`; `ui.timer(120.0, carregar_noticias)` recarrega lista a cada 2 min (fail-soft `try/except`); inicial `carregar_noticias()` imediata.

### Administração (`/admin/filas`)

`telas_administracao.py:13-30` — `bloco_aparencia` (cupê "Aparência" `filas_*`, `com_texto_header=True`, defaults `cor_botao=""` → `PADROES_TEMA["filas"]` `#000000`) + `card_admin("Fila — Esqueleto", icone="queue", chave_modulo="filas", grade=False)`: notas "Esqueleto a título de conhecimento…" + "Tabela tb_fila (Geral) já semeada…" + `painel_backup(usuario, "filas")` (backup do banco `db_mod_filas.db`, job `backup:filas` 12h).

- **Versionamento**: `versao_modulo:filas` no rodapé de `/filas`.

## Permissões

| Ação | `comum` com `filas` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/filas` | ✓ | ✓ | ✗ ("Acesso restrito") |
| `Chamar próximo` (gera senha) | ✓ | ✓ | — |
| `Abrir TV` | ✓ | ✓ | — |
| Ver `/tv` | ✓ (público, sem login) | ✓ | ✓ |
| Ver `/admin/filas` | ✗ | ✓ | ✗ |

Gate `/filas`: `_pode_acessar` (admin geral ou `validar_acesso_modulo(user,"filas")`). `/tv` sem gate.

LGPD: `remover_vinculos_usuario` (esqueleto, retorna 0 — sem vínculo por usuário ainda), `renomear_usuario` propaga `UPDATE tb_chamada SET chamado_por`.

## Rota e integrações

- Rotas: `/filas` (chave `filas`, ícone `queue`) — `main.py:731-743` (`pagina_restrita("Filas", chave_modulo="filas")` + `REGISTRO_MODULOS["filas"] = page_filas`); `/tv` — `main.py:745-749` (sem guarda, **com carrossel do Agregador**). Slugs customizáveis via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_filas` (`gerar_senha` com `fila=id`).
- Backup do banco: job `backup:filas` (`backup_horas:filas` default 12h, `MAPA_BACKUPS` inclui `filas: db_mod_filas.db`).
- **Integração Agregador de Notícias — TV** (`mod_filas/telas.py:103-136` + `mod_agregador_noticias/bd_manipulador.py:232-242`): a TV consome `listar_para_tv(limite=10)` do Agregador e exibe carrossel `título+descrição` no rodapé (`bg-grey-900`, `7s` rotação, `120s` reload); `habilitado()==False` → placeholder desabilitado; sem notícias → placeholder aguarde. Ver [Módulo Agregador](agregador_noticias.md).
- Cadastro central: `MODULOS_SISTEMA` (`autenticacao.py:22` → `("filas","Filas","queue","/filas")`), `MODULOS_BD` (`repositorio.py:66` → `filas: db_mod_filas.db`), `PADROES_TEMA["filas"]` (`tema_modulo.py:76` → `#000000`).

## Testes

```bash
# Smoke do módulo (import + init_db + CRUD mínimo)
.venv/bin/python -c "from mod_filas.bd_manipulador import init_db, listar_filas, gerar_senha; init_db(); print(listar_filas()); print(gerar_senha(1,'master'))"
# Playwright (quando coberto)
.venv/bin/pytest assets/test/teste_filas.py -k filas
```

Ver [Análise do Módulo](../analise_mod_filas.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Esqueleto**: fluxo mínimo validado (Geral + A000→A001 + TV); múltiplas filas/prioridade/guichês/som serão acrescidos sem quebrar o contrato `gerar_senha(fila_id, ator) → (bool,str)` nem a tabela `tb_fila` (já com `status`/`guiche`).
- `/tv` é **pública** (sem login) propositalmente — TV na recepção não tem sessão; se expor fora da rede interna, adicionar gate ou rede/ACL.
- `tb_chamada.guiche` é snapshot do `tb_fila.guiche` no momento do `INSERT ... SELECT guiche FROM tb_fila` — mudança posterior de guichê não retroage chamadas.
- `bd_criador.py` morto — nunca executar; schema real é `init_db()` do `bd_manipulador`.
