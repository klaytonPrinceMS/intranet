# Queue Module — `mod_filas` (Multi-queue + TV per step + Media per queue + Single list)

> Queue/call manager module (multi-queue): routes `/filas` (key `filas`) + `/tv?grupo=` (shared slug) + `/tv/{fila_id}` (isolated) + `?etapa=` (per-room replica) · own database `db_mod_filas.db` (WAL) · tables `tb_fila` (voice/text columns) / `tb_fila_etapa` / `tb_chamada` (priority+manchester) / `tb_fila_nomes` (one list per queue) / `tb_midia` (per-queue + global ambient) / `tb_tv_estado` (claim+remote) / `tb_fila_acesso` / `tb_config_filas` · project starts with NO queues · slug `tv_grupo` + in-use group list · creation with step sequence (Name | Desk), configurable voice, editable TV texts, optional initial list · media per queue (mp3/mp4/photos, default volume 20, real duration via mutagen, photos split audio time) + global ambient audio on every TV · tagged `nomes.txt`, transfer within same TV, round-robin + dominating Manchester (no sensitive words on screen, background color only) · wait/call per step/room, serialized voice (claim), 50% ducking, full/half hour · per-user access + Edit/Access buttons, news up to 200.

---

# Módulo Filas — `mod_filas` (Multi-filas + TV por etapa + Mídia por fila + Lista única)

> Módulo gestor de filas/chamadas (multi-filas): rotas `/filas` (chave `filas`) + `/tv?grupo=` (compartilhada, slug) + `/tv/{fila_id}` (isolada) + `?etapa=` (réplica por sala) · banco próprio `db_mod_filas.db` (WAL) · tabelas `tb_fila` (colunas voz/textos) / `tb_fila_etapa` / `tb_chamada` (prioridade+manchester) / `tb_fila_nomes` (uma lista por fila) / `tb_midia` (por fila + ambiente global) / `tb_tv_estado` (claim+remoto) / `tb_fila_acesso` / `tb_config_filas` · projeto nasce SEM filas · slug `tv_grupo` + lista de grupos em uso · criação com sequência de etapas (Nome | Guichê), voz configurável, textos da TV editáveis, lista inicial opcional · mídia por fila (mp3/mp4/fotos, volume padrão 20, duração real via mutagen, fotos dividem tempo do áudio) + áudio ambiente global em todas as TVs · `nomes.txt` com tags, transferência na mesma TV, revezamento + Manchester dominando (sem termos sensíveis nas telas, só cor de fundo) · espera/chamar por etapa/sala, voz serializada (claim), ducking 50%, hora cheia/meia · acesso por usuário + botões Editar/Acesso, notícias até 200 · auditoria central LGPD.

## Propósito

Gestor de **múltiplas filas por local** com chamadas sequenciais e TV dedicada por fila, grupo ou sala. O projeto **nasce sem filas** — cada usuário com acesso cria as suas; `administrador_geral` vê todas. Cada fila tem **numeração própria** (`prefixo` + `senha_inicio`→`senha_fim`, com `fim=0` = infinito circular) e **sequência de etapas/salas** (ex.: Recepção | 01 → Triagem | 02 → Consultório 3 | 03 — cada etapa é subfila com painel de "próximo" e TV replicável via `?etapa=`). A TV pode ser **isolada** (`/tv/{fila_id}`), **compartilhada por grupo** (`/tv?grupo=recepcao` — slug sem acento/espaço) ou **por sala** (`?etapa=Triagem`). Quando ociosa, reproduz **mídias da fila** + **áudio ambiente global**; ao chamar, toca **bip + voz** serializada (claim, sem cortar) com **ducking 50%**, repetição configurável e **hora cheia/meia**.

> Status: **multi-filas + TV por etapa + lista única operacional**. Isolamento por criador/acesso + slug de grupo + voz serializada + mídia por fila.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:113-277` (bootstrap central + `init_db()` no import). **Sem seed** — nenhuma fila fixa. Migração via `_garantir_coluna` + migração de `tb_midia` para `imagem` + migração de grupos legados para slug.

| Tabela | Conteúdo |
|:---|:---|
| `tb_fila` | `id` PK, `nome` UNIQUE, `senha_atual`, `status` (`ativa`), `guiche`, `data_criacao` + `endereco`, `descricao`, `prefixo` (`A`), `criado_por`, `senha_inicio` (1), `senha_fim` (0 = infinito), `tv_grupo` (slug, vazio = isolada) + voz `voz_nome/voz_senha/voz_destino/voz_guiche/voz_fila/voz_hora` + `voz_repetir` (0–10) + `voz_intervalo` (1–60s) + textos `tv_titulo/tv_subtitulo/tv_aguardando/tv_midia_legenda/tv_noticias_titulo` + `prio_turno` |
| `tb_fila_etapa` | `id` PK, `fila_id` FK CASCADE, `ordem`, `nome` (ex.: Recepção/Triagem/Consultório 3), `guiche`, `ativo` |
| `tb_chamada` | `id` PK, `fila_id` FK CASCADE, `senha`, `guiche` (snapshot), `chamado_em`, `chamado_por` + `paciente_nome`, `etapa_nome`, `fila_nome` + `prioridade` (`comum/gestante/idoso/deficiente`) + `manchester` (`vermelho/laranja/amarelo/verde/azul`) |
| `tb_fila_nomes` | `id` PK, `fila_id` FK CASCADE, `nome`, `ordem`, `usado`, `criado_em` + `prioridade` + `manchester` + `etapa` (vinculada) — uma lista por fila, arquivo `datahora_nomeFila.txt` |
| `tb_midia` | `id` PK, `nome`, `tipo` CHECK(`audio`/`video`/`imagem`), `caminho` (`/midia_filas/...`), `arquivo_original`, `ordem`, `ativo`, `criado_em` + `fila_id` (NULL = global) + `volume` (padrão 20) + `duracao` (foto, padrão 8) + `slot` (exibição) + `duracao_real` (mutagen) — arquivo `datahora_nomeFila.ext` |
| `tb_tv_estado` | `chave` PK (`grupo:<slug>`/`fila:<id>`/`geral` + `+<etapa>`), `slot_atual`, `pausado`, `comando`, `fala_ate`, `ultima_falada` — claim de voz + controle remoto |
| `tb_fila_acesso` | `fila_id` FK CASCADE + `user_nome` (UNIQUE par) + `criado_em` — acesso liberado por usuário |
| `tb_config_filas` | chave-valor local (`filas_modo_tv`=`1`, `filas_senha_prefixo`=`A`, `filas_guiche_padrao`=`01`) |

Conexão via `mod_intranet/banco_conexao.conexao("filas")` (WAL + `foreign_keys=ON`, backend duplo). Auditoria via `audit_log` → `db_mod_auditoria.db`, tabela `tb_auditoria_filas`.

Pasta de mídia: `mod_filas/midia/` servida em `/midia_filas/*` via `montar_rotas_static()` (`bd_manipulador.py:1822-1832`, `app.add_static_files("/midia_filas", PASTA_MIDIA)`), montada no boot em `main.py:152-156`. Dependência `mutagen>=1.45` (`requirements.txt:37-38`) para duração real.

> `bd_criador.py` legado/morto — não executar.

Modelos: `Fila`/`Chamada` dataclass parcial (sem `map_imperatively` ainda).

## Funcionalidades

### Painel `/filas` — gestor multi-filas (próprias + liberadas)

- **Gate** (`_pode_acessar` — `telas.py:23-29`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "filas")`.
- **Cabeçalho** (`telas.py:584-592`): `ler_tema("filas")` + `cabecalho("Filas — Chamadas", chave_modulo="filas")`.
- **Criar fila** (`telas.py:595-721`): qualquer usuário com acesso cria a **sua** fila. Campos: `Nome*`, `Endereço`, `Descrição`, `Prefixo` (`A`), `Início` (1), `Fim (0=infinito)` (0), `Guichê base` (01) + `TV grupo em uso` (select de grupos existentes) + `Nova TV grupo` (slug, vazio = isolada) + `Falar na TV` (checkboxes nome/senha/destino/guichê/fila/hora cheia-meia + repetir 0–10 + intervalo 1–60s) + `Sequência de etapas (Etapa | Guichê)` + `Lista inicial (opcional)` + expansão `Personalizar textos da TV`. `criar_fila(..., etapas=[(nome, guiche)])` (`bd_manipulador.py:428-497`) → `senha_atual = prefixo + (inicio-1)` + etapas + `audit criar_fila`. Ao criar, exibe link TV + botão **Abrir TV desta fila**.
- **Card por fila** (`render_filas` — `telas.py:725-831`): `nome • endereco • descricao • Senha atual • Prefixo • inicio→fim (∞) • Guichê • TV • Dono • status` + botões `TV grupo/Abrir TV` + **Excluir** (dono/admin) + **Editar** (quem vê a fila — `dialogo_editar_fila`: volta e altera tudo da criação + liberar acesso) + **Acesso** (dono/admin — `dialogo_acesso_fila`: buscar cadastrados na gestão e chamar) + `Link: /tv...`.
  Etapas: badges `ordem. nome (guiche)`; Chamar: `Paciente avulso` (vazio usa a lista) + `Etapa/Destino` + `Grupo avulso` + **Chamar próximo** → `gerar_senha` + `notificar`.
  Histórico isolado: `expansion Histórico desta fila (isolado)` com `listar_chamadas(5, fila_id)` + ajuste de Manchester por senha (qualquer atendente) + botão **Avançar** sequencial.
- **Por etapa/sala** (`bloco_etapas` — `telas.py:338-395`): cada sala pede o **Próximo** (reanuncia o mais antigo aguardando ou chama o vinculado a ela), vincula nome ao papelzinho (`definir_nome_senha`), ajusta a cor (`definir_manchester_senha`) e abre a **TV só da etapa** (`?etapa=`) — qualquer atendente com acesso.
- **Nomes — lista única** (`bloco_nomes_fila` — `telas.py:209-335`): um por linha + tags (`maria #gestante #vermelho #recepcao`, `[colchetes]`, `,`/`;`/`#`); importar colado ou `nomes.txt` (salvo como `datahora_nomeFila.txt`); prioridade/cor/etapa ajustáveis por nome; **transferência para outra fila da mesma TV** (um ou todos — destino sem lista); `Apagar lista`.
- **Mídias da fila** (`bloco_midia_fila` — `telas.py:92-163`): upload mp3/mp4/fotos (sobe sozinho, renomeia `datahora_nomeFila.ext`, só desta fila); `Exibição` (mesmo número toca junto), `Volume` (0–100, padrão 20), `Duração foto` (foto sozinha usa a configurada; com áudio/vídeo, fotos dividem o tempo real); ativar/desativar, excluir, ↑/↓.
- **Controle da TV** (`bloco_controle_tv` — `telas.py:548-574`): vê o que está tocando + **Pausar/Retomar/Retornar/Avançar** remoto (a TV obedece via `tb_tv_estado.comando`).
- **Excluir em lote** (`telas.py:835-852`): `Excluir todas as filas` (admin) ou `Excluir todas minhas filas` (comum) → dialog → `excluir_todas_filas` (filtro `criado_por` quando não-admin). Sem fila preservada.
- **Admin link** → `/admin/filas`.

#### `gerar_senha` + `_proxima_senha` (`bd_manipulador.py:699-778`)

```python
_proxima_senha(atual, prefixo, inicio, fim): regex r"([A-Za-z]*)(\d+)" → pref+num+1 com :03d/04d; se fim>0 e prox>fim → prox=inicio (circular); infinito quando fim=0
gerar_senha(fila_id, ator, paciente_nome, etapa_nome, prioridade, manchester): vazio consome próximo elegível (_escolher_proximo_nome: Manchester domina; sem Manchester ≤3 chegada, >3 revezamento) → _emitir_senha (snapshot guichê da etapa, INSERT tb_chamada) + audit
```

#### Revezamento + Manchester (`_escolher_proximo_nome` — `bd_manipulador.py:1292-1333`)

Elegíveis: etapa `''` (geral) ou a pedida. Com Manchester: cor domina tudo (`vermelho>laranja>amarelo>verde>azul`, desempate demografia/chegada). Sem Manchester e até 3 elegíveis: chegada. Acima disso: ciclo `gestante → idoso → deficiente → comum → comum` (`prio_turno`, `CICLO_PRIORIDADE`).

### Painel `/tv` + `/tv/{fila_id}` + `?grupo=` + `?etapa=` — display com voz serializada e mídia

- **Rotas** (`main.py:755-789`): `/tv` pública (sem `pagina_restrita`) com `?grupo=` (compartilhada) + `?etapa=` (réplica por sala) + `/tv/{fila_id}` isolada (resolve grupo se pertence).
- **Layout `mostrar_tv(fila_id=None, tv_grupo=None, etapa=None)`** (`telas.py:858-1362`): textos do criador (título/subtítulo/aguardando/legenda/título notícias) + ícone/título do sistema; corpo mídia (>90%, `max-height:62vh`, sem controles) + faixa lateral 240px (senha/paciente/destino/guichê + 3 últimos); rodapé notícias escuro (título+descrição+fonte+contador, `min-height:22vh`). **Discrição**: nenhum termo de grupo/cor na tela — só o fundo colorido orienta.
- **Voz serializada** (`refresh_chamada`, `ui.timer 3.0`): `buscar_proxima_fala` (mais antigo não falado por TV/etapa) + `tv_claim_fala` (compare-and-swap — um anuncia por vez, **sem cortar** o atual; fila de voz independente por etapa via `chave_tv_etapa`); repetição (`voz_repetir` × `voz_intervalo`) só com voz livre; `_js_duck_e_voz` (música à **metade 2s antes**, bip 880Hz 0.35s, `speechSynthesis` `pt-BR` `0.9`, restaura 2s depois); `_falar_hora_se_hora` (cheia/meia, só sem chamada há 60s, uma vez por horário). Ordem da fala = ordem da tela: fila → senha → nome → destino → guichê (só campos habilitados em `voz_*`).
- **Carrossel notícias** (`carregar_noticias` + `_mostrar_noticia`, `ui.timer 15.0` rotate + `120.0` reload): `listar_para_tv(limite=200)` filtrando censuradas + fallback elegante (rodapé nunca vazio: pausado/sem manchetes).
- **Playlist mídia** (`_render_slot` + `rotacionar_midia` encadeado pela duração real): `midias_para_tv` (próprias + áudios globais após as próprias; vídeo/foto global só na geral) → `calcular_passo` (áudio/vídeo valem tempo **real** via mutagen; fotos dividem; sem real: fotos somam config, só vídeo=25s, nada=12s) → imagens alternadas por foto + áudio oculto + vídeo; comando remoto (pausar/retomar/próximo/anterior/slot) obedece `tb_tv_estado`.

### Administração (`/admin/filas`)

`telas_administracao.py:24-295` — `bloco_aparencia` (cupê "Aparência" `filas_*`, `com_texto_header=True`) + 2 cards + `painel_backup`.

**Card "Filas — por local/endereço"** (`queue`, `grade=False`, `telas_administracao.py:37-192`): admin vê todas; edição inline (nome/endereço/descrição/prefixo/início/fim/guichê + TV grupo em uso/nova) + etapas (editar/excluir/adicionar) + expansão **Voz e textos da TV** + `bloco_nomes_fila` + `bloco_midia_fila` + `bloco_controle_tv` por fila. Botões: `Recarregar`, `Abrir TV geral` (`/tv`), `Excluir todas as filas` (dialog).

**Card "Áudio ambiente global — toca em todas as filas"** (`queue_music`, `grade=False`, `telas_administracao.py:195-292`): áudios aqui tocam em **TODAS** as TVs após as mídias de cada fila (vídeos/fotos globais só na TV geral); volume por áudio; upload automático (`datahora_global.ext`); `Recarregar mídia` + `Preview TV` (`/tv`).

- **Versionamento**: `versao_modulo:filas` no rodapé de `/filas`.

## Permissões

| Ação | `comum` com `filas` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/filas` | ✓ (próprias + liberadas + legado sem dono) | ✓ (todas) | ✗ ("Acesso restrito") |
| `Criar fila` | ✓ (sua) | ✓ | — |
| `Chamar próximo` / `Avançar` / etapa / Manchester | ✓ nas que vê (qualquer atendente) | ✓ todas | — |
| `Editar` (tudo da criação) | ✓ nas que vê | ✓ todas | — |
| `Acesso` (liberar usuários) | ✓ só dono (nas suas) | ✓ | — |
| `Excluir` (uma fila) | ✓ só suas | ✓ | — |
| `Excluir todas` | `Excluir todas minhas filas` | `Excluir todas as filas` | — |
| `Abrir TV` (`/tv/{id}`, `/tv?grupo=`, `?etapa=`) | ✓ (pública, sem login) | ✓ | ✓ |
| Ver `/admin/filas` (todas + mídia + áudio global) | ✗ | ✓ | ✗ |

Gate `/filas`: `_pode_acessar` (admin geral ou `validar_acesso_modulo(user,"filas")`). `/tv` sem gate. `liberar_acesso` exige usuário **cadastrado** (busca na gestão). LGPD: `remover_vinculos_usuario` (limpa acessos) + `renomear_usuario` (`tb_chamada`/`tb_fila`/`tb_fila_acesso`).

## Rota e integrações

- Rotas: `/filas` (chave `filas`, ícone `queue`) — `main.py:741-752` (`pagina_restrita("Filas")`); `/tv` — `main.py:755-778` (`?grupo=` + `?etapa=`) + `/tv/{fila_id}` — `main.py:780-789` (isolada, resolve grupo). `REGISTRO_MODULOS["filas"]=page_filas`. Slugs via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` → `tb_auditoria_filas` (`criar_fila`, `atualizar_fila`, `excluir_fila`, `gerar_senha`, `avancar_chamada`, `excluir_todas_filas`, `criar_etapa`, `importar_nomes`, `transferir_*`, `liberar/remover_acesso`, `adicionar/excluir_midia`, `definir_*` etc.).
- Backup: job `backup:filas` (`backup_horas:filas` 12h, `MAPA_BACKUPS` `filas: db_mod_filas.db`).
- **Integração Agregador**: TV consome `listar_para_tv(limite=200)` filtrando `conteudo_palavras_bloqueadas` (censura) + fallback nunca vazio.
- **Mídia**: `PASTA_MIDIA = mod_filas/midia` + `app.add_static_files("/midia_filas", ...)` (áudio `mp3/wav/ogg/m4a`, vídeo `mp4/webm/mov`, imagem `jpg/png/webp`) + `mutagen>=1.45`.
- Cadastro: `MODULOS_SISTEMA` (`autenticacao.py`→`("filas","Filas","queue","/filas")`), `MODULOS_BD` (`filas: db_mod_filas.db`), `PADROES_TEMA["filas"]` (`#000000`).

## Testes

```bash
.venv/bin/python -c "from mod_filas.bd_manipulador import init_db, listar_filas, gerar_senha, criar_fila; init_db(); print(listar_filas()); print(criar_fila('Ambulatório', 'xyz', 'desc', 'A', '01', 'master', 1, 0, 'recepcao')); print(gerar_senha(1,'master'))"
.venv/bin/python -c "from mod_filas.bd_manipulador import normalizar_tv_grupo; print(normalizar_tv_grupo('Ambulatório Geral'))"
.venv/bin/python -c "from mod_filas.bd_manipulador import calcular_passo; print(calcular_passo([('audio',8,40.0)]+[('imagem',8,None)]*4))"
.venv/bin/pytest assets/test/test_seg_novos_modulos.py -q  # seções D–D6 (filas)
```

Seções D–D6 em `assets/test/test_seg_novos_modulos.py`: D (incremento + slug + sem seed), D2 (lista única + prioridades + revezamento + transferência mesma TV), D3 (Manchester domina + etapas + espera + nome/Manchester na senha + voz extras), D4 (duração real + fotos dividem + wav 40s), D5 (liberar acesso + visibilidade), D6 (claim de voz + etapa vinculada `[maria #... #recepção]`, tag desconhecida ignorada).

Ver [Análise do Módulo](../analise_mod_filas.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Projeto sem filas fixas**: nasce vazio; excluir tudo é permitido.
- **`tv_grupo` slug** (`recepcao-2`): use a lista "em uso" para compartilhar; vazio = isolada.
- **Numeração infinita**: `senha_fim=0` = circular; `_proxima_senha` reinicia em `inicio`.
- **TV grupo vs isolada vs etapa**: `tv_grupo` vazio → `/tv/{id}`; preenchido → `/tv?grupo=`; `?etapa=` replica só a sala (voz independente).
- **Voz serializada**: `tv_claim_fala` evita cortar; repetição e hora cheia/meia respeitam voz ocupada; ducking 50%.
- **Mídia por fila + ambiente global**: `slot` igual = juntos; fotos dividem o tempo real do áudio; volume padrão 20.
- **Discrição**: telas mostram só cor de fundo para prioridade/Manchester; termos só nos controles de edição.
- `/tv` pública — TV na recepção sem sessão; se expor fora da rede, adicionar `ACL`.
- `tb_chamada.guiche` snapshot — não retroage.
- `bd_criador.py` morto.
