# Queue Module — `mod_filas` (Multi-queue + News Carousel + Media)

> Queue/call manager module (multi-queue): routes `/filas` (key `filas`) + `/tv` (public shared `?grupo=`) + `/tv/{fila_id}` (isolated) · own database `db_mod_filas.db` (WAL) · tables `tb_fila`/`tb_fila_etapa`/`tb_chamada`/`tb_midia`/`tb_config_filas` · queue per local with `endereco/prefixo/senha_inicio/fim` (fim=0 infinite) + `criado_por` + `tv_grupo` · isolated by creator vs `administrador_geral` · sequential steps + TV carousel + elevator audio / propaganda video `/midia_filas` · central LGPD audit.

---

# Módulo Filas — `mod_filas` (Multi-filas + Carrossel Notícias + Mídia TV)

> Módulo gestor de filas/chamadas (multi-filas): rotas `/filas` (chave `filas`) + `/tv?grupo=` (compartilhada) + `/tv/{fila_id}` (isolada) · banco próprio `db_mod_filas.db` (WAL) · tabelas `tb_fila`/`tb_fila_etapa`/`tb_chamada`/`tb_midia`/`tb_config_filas` · fila por local com `endereco/prefixo/senha_inicio/fim` (fim=0 infinito) + `criado_por` + `tv_grupo` · isolamento por criador vs `administrador_geral` · etapas sequenciais + TV carrossel + áudio elevador / vídeo propaganda `/midia_filas` · auditoria central LGPD.

## Propósito

Gestor de **múltiplas filas por local** com chamadas sequenciais e TV dedicada. Cada fila é isolada (não interfere em outra) e tem **numeração própria** (`prefixo` + `senha_inicio`→`senha_fim`, com `fim=0` = infinito circular) e **etapas sequenciais** (`tb_fila_etapa`: Atendimento → Triagem → Consultório 3). A TV pode ser **isolada** (`/tv/{fila_id}`) ou **compartilhada por grupo** (`/tv?grupo=recepcao` — todas as filas com mesmo `tv_grupo` aparecem na mesma TV). Quando ociosa, reproduz playlist de **áudio elevador (MP3)** / **vídeo propaganda (MP4)** em `/midia_filas`; ao chamar, toca **bip + voz** (SpeechSynthesis `pt-BR`) somente no novo `id`.

> Status: **multi-filas operacional** (antes esqueleto). Isolamento por criador + TV grupo + mídia global.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:56-141` (bootstrap central + `init_db()` no import). Migração via `_garantir_coluna` para colunas novas.

| Tabela | Conteúdo |
|:---|:---|
| `tb_fila` | `id` PK, `nome` UNIQUE, `senha_atual` (`A000` default), `status` (`ativa`), `guiche` (`01` default), `data_criacao` + `endereco` TEXT, `descricao` TEXT, `prefixo` TEXT (`A`), `criado_por` TEXT (login do criador), `senha_inicio` INTEGER (1), `senha_fim` INTEGER (0 = infinito), `tv_grupo` TEXT (vazio = TV isolada) |
| `tb_fila_etapa` | `id` PK, `fila_id` FK CASCADE, `ordem` INTEGER, `nome` TEXT (ex.: Atendimento/Triagem/Consultório 3), `guiche` TEXT, `ativo` INTEGER |
| `tb_chamada` | `id` PK, `fila_id` FK CASCADE, `senha` (ex.: `A001`), `guiche` (snapshot), `chamado_em`, `chamado_por` + `paciente_nome` TEXT, `etapa_nome` TEXT, `fila_nome` TEXT |
| `tb_midia` | `id` PK, `nome` TEXT, `tipo` CHECK(`audio`/`video`), `caminho` TEXT (`/midia_filas/...`), `arquivo_original` TEXT, `ordem` INTEGER, `ativo` INTEGER, `criado_em` |
| `tb_config_filas` | chave-valor local (`filas_modo_tv`=`1`, `filas_senha_prefixo`=`A`, `filas_guiche_padrao`=`01`) |

Seed: `INSERT OR IGNORE INTO tb_fila (Geral, A000, ativa, 01, '', 'Fila geral de atendimento', 'A', '', 1, 0, '')` + 3 etapas padrão para `Geral` (Atendimento 01, Triagem 02, Consultório 3). Conexão via `mod_intranet/banco_conexao.conexao("filas")` (WAL + `foreign_keys=ON`, backend duplo). Auditoria via `audit_log` → `db_mod_auditoria.db`, tabela `tb_auditoria_filas` (`criar_fila`, `atualizar_fila`, `excluir_fila`, `gerar_senha`, `avancar_chamada`).

Pasta de mídia: `mod_filas/midia/` servida em `/midia_filas/*` via `montar_rotas_static()` (`bd_manipulador.py:684-694`, `app.add_static_files("/midia_filas", PASTA_MIDIA)`), montada no boot em `main.py:152-156`.

> `bd_criador.py` legado/morto — não executar.

Modelos: `Fila`/`Chamada` dataclass parcial (sem `map_imperatively` ainda).

## Funcionalidades

### Painel `/filas` — gestor multi-filas isolado por criador

- **Gate** (`_pode_acessar` — `telas.py:19-25`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "filas")`.
- **Cabeçalho** (`telas.py:35-43`): `ler_tema("filas")` + `cabecalho("Filas — Chamadas", chave_modulo="filas")`.
- **Criar fila** (`telas.py:45-93`): qualquer usuário com acesso cria a **sua** fila; `admin geral` cria para qualquer local. Campos: `Nome*`, `Endereço`, `Descrição`, `Prefixo` (`A`), `Início` (1), `Fim (0=infinito)` (0), `Guichê base` (01), `TV grupo` (vazio = isolada). Validação: prefixo `^[A-Za-z0-9]+$`, `inicio>=0`, `fim==0` ou `fim>=inicio`. `criar_fila(nome, endereco, descricao, prefixo, guiche, ator, senha_inicio, senha_fim, tv_grupo)` (`bd_manipulador.py:208-255`) → `senha_atual = prefixo + (inicio-1):03d` (04d se >999) + 3 etapas padrão + `audit criar_fila`.
  Ao criar, exibe link TV: `tv_grupo ? /tv?grupo={grupo} (compartilhada) : /tv/{fid} (isolada)` + botão **Abrir TV desta fila** + `notificar`.
- **Listagem isolada** (`render_filas` — `telas.py:97-165`): `listar_filas_visiveis(user_nome, perfil_global, eh_admin_modulo)` (`bd_manipulador.py:157-175`) — dono (`criado_por=user_nome`) ou legado vazio **ou** `admin geral/modulo` vê **todas**; senão só as suas. Card por fila: `nome • endereco • descricao • Senha atual • Prefixo • inicio→fim (∞ se 0) • Guichê base • TV isolada/grupo • Dono • status` + botão `TV grupo {tv_grupo}` (`/tv?grupo=`) ou `Abrir TV desta fila` (`/tv/{fid}`) + **Excluir** (só dono/admin, `excluir_fila` bloqueia `Geral`) + `Link: /tv...` (caption). 
  Etapas: badges `ordem. nome (guiche)`; Chamar: `Paciente (opcional p/ voz)` + `select Etapa/Destino` (primeira por padrão) + **Chamar próximo** → `gerar_senha(fid, ator, paciente_nome, etapa_nome)` (`bd_manipulador.py:462-501`, `_proxima_senha` com `fim=0` infinito, padding 3/4, snapshot guichê da etapa) + `notificar` + `render_filas`.
  Histórico isolado: `expansion Histórico desta fila (isolado)` com `listar_chamadas(5, fila_id=fid)` (isolado) + botão **Avançar** sequencial (`avancar_chamada`, só dono/admin e se não for última etapa).
- **Excluir em lote** (`telas.py:167-185`): `Excluir todas as filas` (admin) ou `Excluir todas minhas filas` (comum) → dialog confirmação → `excluir_todas_filas(ator, somente_do_criador, eh_admin)` (`bd_manipulador.py:335-356`, `DELETE WHERE nome<>'Geral'` com filtro `criado_por` quando não-admin) → `notificar` + `render_filas`. **Geral preservada** sempre.
- **Admin link** → `/admin/filas`.

#### `gerar_senha` + `_proxima_senha` (`bd_manipulador.py:79-107` + `440-501`)

```python
_proxima_senha(atual, prefixo, inicio, fim): regex r"([A-Za-z]*)(\d+)" → pref+num+1 com :03d/04d; se fim>0 e prox>fim → prox=inicio (circular); infinito quando fim=0
gerar_senha(fila_id, ator, paciente_nome, etapa_nome): SELECT fila → _proxima_senha → resolve guichê da etapa (SELECT guiche FROM tb_fila_etapa) → UPDATE tb_fila senha_atual → INSERT tb_chamada (..., paciente_nome, etapa_nome, fila_nome) + audit
```

#### Etapas sequenciais (`bd_manipulador.py:359-436`)

`listar_etapas(fila_id)` `ORDER BY ordem`; `criar_etapa(fila_id, nome, guiche)` (max ordem +1); `atualizar_etapa`; `excluir_etapa`; `reordenar_etapas(fila_id, ordem_ids)` (SAVEPOINT por statement).

### Painel `/tv` e `/tv/{fila_id}` + `?grupo=` — display full-screen com voz, bip e mídia

- **Rotas** (`main.py:753-778`): `/tv` pública (sem `pagina_restrita`) com `?grupo=xxx` (compartilhada) + `/tv/{fila_id}` isolada. `page_tv()` lê `query_params.get("grupo")` e chama `mostrar_tv(tv_grupo=grupo)`; `page_tv_fila(fila_id)` chama `mostrar_tv(fila_id=fila_id)` (resolve `tv_grupo` se fila pertence a grupo).
- **Layout `mostrar_tv(fila_id=None, tv_grupo=None)`** (`telas.py:191-370`): `ler_tema("filas")` + ícone/título do sistema (`get_config("icone_sistema"/"titulo_sistema", "hub"/"INTRANET")`, **ícone padrão intranet da TV**) + header `bg-grey-900` com `icone_sistema` 28px + `titulo_sistema` + `TV — Grupo {tv_grupo} (compartilhada)` ou `TV — Fila {nome} (isolada)` ou `TV — Todas as filas` (sem filtro). Corpo central: `lbl_topo AGUARDE CHAMADA` + `lbl_senha 10vw` + `lbl_paciente 2.5vw yellow-3` + `lbl_destino 3vw` + `lbl_guiche 2vw`. **Mídia**: `media_container` + `media_html` (audio/video). **Rodapé notícias**: `Notícias — agregador` + `lbl_n_titulo 1.4vw` + `lbl_n_desc 0.9vw` + `lbl_n_fonte`.
- **Chamada com bip+voz só no novo id** (`refresh_chamada`, `telas.py:296-328`, `ui.timer 3.0`): `ultima_chamada_tv(fila_id/tv_grupo)` (`bd_manipulador.py:544-603`) → se `cid == estado["ultimo_id"]` **return** (não repete bip/voz); senão atualiza labels + `_js_beep_e_voz(texto)` (`AudioContext` oscilador 880Hz 0.35s + `speechSynthesis` `pt-BR` `rate 0.9` cancelando anterior, sanitize `'`/`"`/`\n`) + `media_html = "🔊 Chamada em andamento — mídia pausada"` + `ui.timer 12.0 _render_midia` (retoma). Texto de voz: `paciente, senha X, dirigir-se a etapa, fila Y, guichê Z`.
- **Carrossel notícias** (`carregar_noticias` + `_mostrar_noticia`, `telas.py:330-357`, `ui.timer 7.0` rotate + `120.0` reload): `listar_para_tv(limite=10)` filtrando censuradas (`conteudo_palavras_bloqueadas`).
- **Playlist mídia** (`telas.py:282-363`): `listar_midias(somente_ativas=True)` → `_render_midia(idx)` com `src /midia_filas/{basename}` (audio `controls autoplay loop`, video `autoplay muted loop controls playsinline max-height:32vh`); `rotacionar_midia` `ui.timer 40.0` (só quando `ultimo_id is None` = ociosa) + inicial `_render_midia(0)`.

### Administração (`/admin/filas`)

`telas_administracao.py:18-218` — `bloco_aparencia` (cupê "Aparência" `filas_*`, `com_texto_header=True`) + 2 cards + `painel_backup`.

**Card "Filas — por local/endereço (isoladas por criador, TV por fila ou grupo)"** (`queue`, `grade=False`, `telas_administracao.py:31-124`):
- Lista **admin vê todas** (`listar_filas()` todas 13 colunas); card por fila com `nome (prefixo+senha) • endereco • descricao • Guichê base • TV isolada/grupo • inicio→fim (∞) • Dono • status` + `Link TV: /tv...` + `Abrir TV` + `Excluir` (`delete`, `negative`) + edição inline (`Nome/Endereço/Descrição/Prefixo/Início/Fim/Guichê/TV grupo` + **Salvar** → `atualizar_fila` com `ator`). Etapas: por etapa `ordem. + input nome + guichê + Salvar/Excluir` (`atualizar_etapa`/`excluir_etapa`), nova etapa `input + Adicionar etapa` (`criar_etapa`). Botões: `Recarregar`, `Abrir TV geral` (`/tv`), `Excluir todas as filas` (dialog, `excluir_todas_filas(eh_admin=True)`, Geral preservada).

**Card "Mídia da TV — áudios e vídeos (global para todas as TVs)"** (`queue_music`, `grade=False`, `telas_administracao.py:126-216`):
- Legenda áudio elevador `MP3/WAV/OGG/M4A` e vídeo propaganda `MP4/WEBM` em `mod_filas/midia/` servidos em `/midia_filas/*` (global para todas as TVs isoladas/compartilhadas; quando ociosa reproduz playlist em loop, ao chamar pausa). Preview `audio controls`/`video controls` + `Ativar/Desativar` (`set_midia_ativa`) + `Excluir` (`excluir_midia` remove arquivo se dentro de `PASTA_MIDIA`) + `↑/↓` (`reordenar_midias`). Upload `ui.upload` `accept=.mp3,.wav,.ogg,.m4a,.mp4,.webm` `multiple` `auto_upload=True` → sanitiza nome `[^a-zA-Z0-9._-]→_` + `uuid6` + `adicionar_midia(nome, tipo, /midia_filas/..., ator)`; `Recarregar mídia` + `Preview TV` (`/tv`).

- **Versionamento**: `versao_modulo:filas` no rodapé de `/filas`.

## Permissões

| Ação | `comum` com `filas` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/filas` (multi-filas isoladas) | ✓ (só suas) | ✓ (todas) | ✗ ("Acesso restrito") |
| `Criar fila` (por local) | ✓ (sua) | ✓ | — |
| `Chamar próximo` / `Avançar` (por fila) | ✓ só nas suas | ✓ todas | — |
| `Excluir` (uma fila) | ✓ só suas (exceto Geral) | ✓ (exceto Geral) | — |
| `Excluir todas` | `Excluir todas minhas filas` | `Excluir todas as filas` | — |
| `Abrir TV` (`/tv/{id}` isolada ou `/tv?grupo=xxx` compartilhada) | ✓ (pública, sem login) | ✓ | ✓ |
| Ver `/tv` / `/tv/{id}` | ✓ (pública) | ✓ | ✓ |
| Ver `/admin/filas` (todas + mídia global) | ✗ | ✓ | ✗ |

Gate `/filas`: `_pode_acessar` (admin geral ou `validar_acesso_modulo(user,"filas")`). `/tv` sem gate. LGPD: `remover_vinculos_usuario` (0) + `renomear_usuario` (`UPDATE tb_chamada/ tb_fila criado_por`).

## Rota e integrações

- Rotas: `/filas` (chave `filas`, ícone `queue`) — `main.py:739-751` (`pagina_restrita("Filas")`); `/tv` — `main.py:753-771` (`?grupo=` compartilhada) + `/tv/{fila_id}` — `main.py:773-778` (isolada, resolve grupo). `REGISTRO_MODULOS["filas"]=page_filas`. Slugs via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` → `tb_auditoria_filas` (`criar_fila`, `atualizar_fila`, `excluir_fila`, `gerar_senha`, `avancar_chamada`, `excluir_todas_filas`, `criar_etapa` etc.).
- Backup: job `backup:filas` (`backup_horas:filas` 12h, `MAPA_BACKUPS` `filas: db_mod_filas.db`).
- **Integração Agregador**: TV consome `listar_para_tv` filtrando `conteudo_palavras_bloqueadas` (censura).
- **Mídia**: `PASTA_MIDIA = mod_filas/midia` + `app.add_static_files("/midia_filas", ...)` (isFormats `mp3/wav/ogg/m4a`→`audio`, `mp4/webm`→`video`).
- Cadastro: `MODULOS_SISTEMA` (`autenticacao.py`→`("filas","Filas","queue","/filas")`), `MODULOS_BD` (`filas: db_mod_filas.db`), `PADROES_TEMA["filas"]` (`#000000`).

## Testes

```bash
.venv/bin/python -c "from mod_filas.bd_manipulador import init_db, listar_filas, gerar_senha, criar_fila; init_db(); print(listar_filas()); print(gerar_senha(1,'master')); print(criar_fila('Ambulatório','xyz','desc','A','01','master',1,0,'recepcao'))"
.venv/bin/python -c "from mod_filas.bd_manipulador import listar_filas_visiveis; print(listar_filas_visiveis('qacomum','comum',False))"
.venv/bin/python -c "from mod_intranet.censura import definir_palavras_bloqueadas; definir_palavras_bloqueadas(['tinder'], ator='master'); from mod_agregador_noticias.bd_manipulador import listar_para_tv; print(listar_para_tv(3))"
```

Ver [Análise do Módulo](../analise_mod_filas.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Isolamento por criador**: filas são isoladas por `criado_por`; comum vê só as suas + legadas (`criado_por=''`) até serem assumidas; admin geral vê todas. `listar_filas_visiveis` implementa.
- **Numeração infinita**: `senha_fim=0` = infinito circular; `_proxima_senha` reinicia em `inicio` quando `prox>fim`.
- **TV grupo vs isolada**: `tv_grupo` vazio → `/tv/{id}`; preenchido → `/tv?grupo=xxx` compartilhada entre todas do mesmo grupo; `ultima_chamada_tv` agrega por `IN` quando `tv_grupo`.
- **Bip+voz só no novo id**: `estado["ultimo_id"]` evita repetir bip/SpeechSynthesis a cada 3s; `speechSynthesis.cancel()` + `AudioContext` 880Hz.
- **Mídia global**: playlist `tb_midia` é global (todas TVs); upload sanitiza + `uuid6`; `excluir_midia` só remove dentro de `PASTA_MIDIA`.
- `Geral` nunca excluível (regra `excluir_fila`).
- `/tv` pública — TV na recepção sem sessão; se expor fora da rede, adicionar `ACL`.
- `tb_chamada.guiche` snapshot — não retroage.
- `bd_criador.py` morto.

