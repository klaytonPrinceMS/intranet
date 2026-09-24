# Queue Module — `mod_filas` (Multi-queue + TV per step + Media per queue + Single list + Voice order + Backdrop)

> Queue/call manager module (multi-queue): routes `/filas` (key `filas`) + `/tv?grupo=` (shared slug) + `/tv/{fila_id}` (isolated) + `?etapa=` (per-room replica) · own database `db_mod_filas.db` (WAL) · tables `tb_fila` (voice `voz_ordem` + text columns) / `tb_fila_etapa` / `tb_chamada` (priority+manchester) / `tb_fila_nomes` (one list per queue) / `tb_midia` (per-queue + global ambient + `fundo` backdrop) / `tb_tv_estado` (claim+remote) / `tb_fila_acesso` / `tb_config_filas` · project starts with NO queues · slug `tv_grupo` + in-use group list · collapsible `Cadastro de fila` (create or in-panel Edit + `Salvar alterações`/`Cancelar`) with `Etapas, lista inicial e arquivos` + `Anexos` stage cards · configurable voice order `voz_ordem` via `normalizar_voz_ordem` (`fila,senha,nome,destino,guiche`) · `delay=1000` tooltips on every field · media per queue (mp3/mp4/photos, default volume 40, real duration via mutagen, photos split audio time, `Fundo` backdrop photo absolute only over media area) + global ambient audio on every TV via `midias_para_tv` · file pattern `datahora_nomeFila` always (reapplied by `renomear_arquivos_fila` on rename) · tagged `nomes.txt`/CSV via `csv_para_tags`, transfer within same TV, round-robin + dominating Manchester (no sensitive words on screen, background color only) · wait/call per step/room, serialized voice by claim (no cut), 50% ducking, full/half hour · per-user access + Edit/Access buttons (`tb_fila_acesso`), news up to 200 · admin via hamburger (`/admin/filas`, panel button removed).

---

# Módulo Filas — `mod_filas` (Mídia por fila + Lista única + Ordem da fala + Papel de fundo)

> Módulo gestor de filas/chamadas (multi-filas): rotas `/filas` (chave `filas`) + `/tv?grupo=` (compartilhada, slug) + `/tv/{fila_id}` (isolada) + `?etapa=` (réplica por sala) · banco próprio `db_mod_filas.db` (WAL) · tabelas `tb_fila` (colunas voz `voz_ordem` + textos) / `tb_fila_etapa` / `tb_chamada` (prioridade+manchester) / `tb_fila_nomes` (uma lista por fila) / `tb_midia` (por fila + ambiente global + `fundo` papel de fundo) / `tb_tv_estado` (claim+remoto) / `tb_fila_acesso` / `tb_config_filas` · projeto nasce SEM filas · slug `tv_grupo` + lista de grupos em uso · criação com sequência de etapas (Nome | Guichê), voz configurável, textos da TV editáveis, lista inicial opcional · mídia por fila (mp3/mp4/fotos, volume padrão 40, duração real via mutagen, fotos dividem tempo do áudio, foto `Fundo` fixa atrás de tudo só na área de mídia) + áudio ambiente global em todas as TVs via `midias_para_tv` · padrão `datahora_nomeFila` sempre (reaplicado por `renomear_arquivos_fila` ao renomear) · `nomes.txt`/CSV com tags via `csv_para_tags`, transferência na mesma TV, revezamento + Manchester dominando (sem termos sensíveis nas telas, só cor de fundo) · espera/chamar por etapa/sala, voz serializada por claim (sem cortar) na ordem `voz_ordem`, ducking 50%, hora cheia/meia · `delay=1000` em todos os campos + cards recolhíveis (`Cadastro de fila`, `Etapas/lista`, `Anexos`) · acesso por usuário + botões Editar/Acesso (`tb_fila_acesso`), notícias até 200 · admin via hambúrguer (`/admin/filas`, botão removido do painel) · auditoria central LGPD.

## Propósito

Gestor de **múltiplas filas por local** com chamadas sequenciais e TV dedicada por fila, grupo ou sala. O projeto **nasce sem filas** — cada usuário com acesso cria as suas; `administrador_geral` vê todas. Cada fila tem **numeração própria** (`prefixo` + `senha_inicio`→`senha_fim`, com `fim=0` = infinito circular) e **sequência de etapas/salas** (ex.: Recepção | 01 → Triagem | 02 → Consultório 3 | 03 — cada etapa é subfila com painel de "próximo" e TV replicável via `?etapa=`). A TV pode ser **isolada** (`/tv/{fila_id}`), **compartilhada por grupo** (`/tv?grupo=recepcao` — slug sem acento/espaço) ou **por sala** (`?etapa=Triagem`). Quando ociosa, reproduz **mídias da fila** + **áudio ambiente global** (volume padrão 40); ao chamar, toca **bip + voz** serializada por claim (sem cortar) na **ordem configurável `voz_ordem`**, com **ducking à metade**, repetição configurável e **hora cheia/meia**. O painel usa **cards recolhíveis** (`Cadastro de fila`, `Etapas, lista inicial e arquivos`, `Anexar vídeos, áudios e fotos`) e **tooltips `delay=1000`** em todos os campos.

> Status: **multi-filas + TV por etapa + lista única + ordem da fala + papel de fundo operacional**. Isolamento por criador/acesso + slug de grupo + voz serializada na ordem da fila + mídia por fila com fundo.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py` (bootstrap central + `init_db()` no import). **Sem seed** — nenhuma fila fixa. Migração via `_garantir_coluna` (inclui `voz_ordem`, `fundo`, `volume` 40) + migração de `tb_midia` para `imagem` + migração de grupos legados para slug + limpeza de staging órfão (`stage_*` com +24h).

| Tabela | Conteúdo |
|:---|:---|
| `tb_fila` | `id` PK, `nome` UNIQUE, `senha_atual`, `status` (`ativa`), `guiche`, `data_criacao` + `endereco`, `descricao` (legado no banco, ocultos na UI), `prefixo` (`A`), `criado_por`, `senha_inicio` (1), `senha_fim` (0 = infinito), `tv_grupo` (slug, vazio = isolada) + voz `voz_nome/voz_senha/voz_destino/voz_guiche/voz_fila/voz_hora` + `voz_ordem` (`TEXT DEFAULT 'fila,senha,nome,destino,guiche'`) + `voz_repetir` (0–10) + `voz_intervalo` (1–60s) + textos `tv_titulo/tv_subtitulo/tv_aguardando/tv_midia_legenda/tv_noticias_titulo` + `prio_turno` |
| `tb_fila_etapa` | `id` PK, `fila_id` FK CASCADE, `ordem`, `nome` (ex.: Recepção/Triagem/Consultório 3), `guiche`, `ativo` |
| `tb_chamada` | `id` PK, `fila_id` FK CASCADE, `senha`, `guiche` (snapshot), `chamado_em`, `chamado_por` + `paciente_nome`, `etapa_nome`, `fila_nome` + `prioridade` (`comum/gestante/idoso/deficiente`) + `manchester` (`vermelho/laranja/amarelo/verde/azul`) |
| `tb_fila_nomes` | `id` PK, `fila_id` FK CASCADE, `nome`, `ordem`, `usado`, `criado_em` + `prioridade` + `manchester` + `etapa` (vinculada) — uma lista por fila, arquivo `datahora_nomeFila.txt` |
| `tb_midia` | `id` PK, `nome`, `tipo` CHECK(`audio`/`video`/`imagem`), `caminho` (`/midia_filas/...`), `arquivo_original`, `ordem`, `ativo`, `criado_em` + `fila_id` (NULL = global) + `volume` (padrão 40) + `duracao` (foto, padrão 8) + `slot` (exibição) + `duracao_real` (mutagen) + `fundo` (0/1, só foto, uma por fila/global) — arquivo sempre `datahora_nomeFila.ext` (reaplicado por `renomear_arquivos_fila`) |
| `tb_tv_estado` | `chave` PK (`grupo:<slug>`/`fila:<id>`/`geral` + `+<etapa>`), `slot_atual`, `pausado`, `comando`, `fala_ate`, `ultima_falada` — claim de voz + controle remoto |
| `tb_fila_acesso` | `fila_id` FK CASCADE + `user_nome` (UNIQUE par) + `criado_em` — acesso liberado por usuário (botão **Acesso** nos cards) |
| `tb_config_filas` | chave-valor local (`filas_modo_tv`=`1`, `filas_senha_prefixo`=`A`, `filas_guiche_padrao`=`01`) |

Conexão via `mod_intranet/banco_conexao.conexao("filas")` (WAL + `foreign_keys=ON`, backend duplo). Auditoria via `audit_log` → `db_mod_auditoria.db`, tabela `tb_auditoria_filas`.

Pasta de mídia: `mod_filas/midia/` servida em `/midia_filas/*` via `montar_rotas_static()` (`app.add_static_files("/midia_filas", PASTA_MIDIA)`), montada no boot em `main.py`. Staging de anexos (`stage_*`) é limpo após 24h sem vínculo no `init_db`. Dependência `mutagen>=1.45` (`requirements.txt`) para duração real.

> `bd_criador.py` legado/morto — não executar.

Modelos: `Fila`/`Chamada` dataclass parcial (sem `map_imperatively` ainda).

## Funcionalidades

### Painel `/filas` — gestor multi-filas (próprias + liberadas)

- **Gate** (`_pode_acessar` — `telas.py`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "filas")`.
- **Cabeçalho** (`telas.py`): `ler_tema("filas")` + `cabecalho("Filas — Chamadas", chave_modulo="filas")`.
- **Cadastro de fila — card recolhível** (`ui.expansion("Cadastro de fila")` — `telas.py:mostrar_tela`): uma linha fechada; abre para criar ou carrega a fila ao clicar **Editar**. Campos: `Nome da fila *`, `Prefixo` (`A`), `Início` (1), `Fim (0=∞)` (0), `Guichê base` (01) + `TV grupo em uso` (select de grupos existentes) + `Nova TV grupo` (slug, vazio = isolada) lado a lado + `Falar na TV` (checkboxes senha/nome/destino/guichê/fila/hora cheia-meia + `Ordem da fala` + repetir 0–10 + intervalo 1–60s) + expansão `Personalizar textos da TV`. `endereco`/`descricao` seguem no banco mas **não aparecem mais na UI** (removidos do cadastro, da edição e dos cards). **Todo campo tem `ui.tooltip(...).props("delay=1000")`** (textos curtos no rótulo + detalhe no `info_outline`). `criar_fila(..., voz_ordem, etapas=[(nome, guiche)])` (`bd_manipulador.py`) → `senha_atual = prefixo + (inicio-1)` + etapas + `audit criar_fila`. Ao criar, exibe link TV + botão **Abrir TV desta fila**. Modo edição (`_carregar_edicao`/`_editar_no_painel`/`_salvar_cadastro`/`_salvar_edicao`/`_cancelar_edicao`/`_limpar_form`): esconde `Etapas/Anexos`, mostra `Editando: <nome>`, troca `Criar fila` por **Salvar alterações** + **Cancelar**.
- **Ordem da fala** (`voz_ordem`): texto livre com os campos `fila,senha,nome,destino,guiche` (ex.: `senha,nome` fala só senha+nome; `nome,senha` inverte). Validação em `normalizar_voz_ordem` (`bd_manipulador.py`: só campos válidos, sem repetir, completa faltantes no fim; vazia rejeita) com constantes `VOZ_ORDEM_PADRAO` e `VOZ_CAMPOS`. Vale em `criar_fila` e `atualizar_fila`; lida em `obter_extras_fila`; aplicada na TV por `_texto_chamada` (só campos habilitados em `voz_*`, fallback `senha`).
- **Etapas, lista inicial e arquivos — card recolhível** (`ui.expansion("Etapas, lista inicial e arquivos (opcional)")`): `Sequência de etapas (Etapa | Guichê)` + `Lista inicial (opcional)` lado a lado + `ui.upload` `nomes.txt`/`.csv` (`_preencher_lista` via `_ler_upload`: carrega o texto no textarea para conferir antes de criar). CSV com `,` ou `;` e cabeçalho (`nome/grupo/cor/etapa`) é convertido por `csv_para_tags` para linhas com tags.
- **Anexar vídeos, áudios e fotos — card recolhível** (`ui.expansion("Anexar vídeos, áudios e fotos (opcional)")`): `Volume` (padrão 40) + `Duração foto` + `Exibição` + `Papel de fundo (fotos)` + `ui.upload` múltiplo (`_anexar_midia`: valida por `tipo_por_extensao`, grava `stage_*` em `PASTA_MIDIA`, guarda em `midias_stage` com `_render_stage` + botão remover; ao criar, renomeia para `nome_arquivo_midia` e vincula com `adicionar_midia` + `set_midia_fundo` quando marcado).
- **Card por fila** (`render_filas` — `telas.py`): `nome • Senha atual • Prefixo • inicio→fim (∞) • Guichê base • TV • Dono • status` (sem `endereco`/`descricao`) + botões `TV grupo/Abrir TV` + **Excluir** (dono/admin) + **Editar** (quem vê a fila — carrega no `Cadastro de fila`, etapas/lista/mídias se gerenciam no card/administração) + **Acesso** (dono/admin — `dialogo_acesso_fila`: buscar cadastrados na gestão e chamar, tooltip explicativo) + `Link: /tv...`.
  Etapas: badges `ordem. nome (guiche)`; Chamar: `Paciente avulso` (vazio usa a lista) + `Etapa/Destino` + `Grupo avulso` + **Chamar próximo** → `gerar_senha` + `notificar`.
  Histórico isolado: `expansion Histórico desta fila (isolado)` com `listar_chamadas(5, fila_id)` + ajuste de Manchester por senha (qualquer atendente) + botão **Avançar** sequencial.
- **Por etapa/sala** (`bloco_etapas` — `telas.py`): rótulo curto + `info_outline` com `delay=1000`. Cada sala pede o **Próximo** (reanuncia o mais antigo aguardando ou chama o vinculado a ela), vincula nome ao papelzinho (`definir_nome_senha`), ajusta a cor (`definir_manchester_senha`) e abre a **TV só da etapa** (`?etapa=`) — qualquer atendente com acesso.
- **Nomes — lista única** (`bloco_nomes_fila` — `telas.py`): rótulo curto (`Um nome por linha + tags.`) + `info_outline` `delay=1000` com o exemplo (`maria #gestante #vermelho #recepcao`, ordem cor→grupo→chegada). Um por linha + tags (`#prioridade #manchester #etapa`, `[colchetes]`, `,`/`;`/`#`); importar colado ou `nomes.txt` (salvo como `datahora_nomeFila.txt`); prioridade/cor/etapa ajustáveis por nome; **transferência para outra fila da mesma TV** (um ou todos — destino sem lista); `Apagar lista`.
- **Mídias da fila** (`bloco_midia_fila` — `telas.py`): rótulo curto + `info_outline` `delay=1000`; cabeçalho por grupo (`— Exibição N (juntos) —`); upload mp3/mp4/fotos (sobe sozinho, renomeia sempre `datahora_nomeFila.ext`, só desta fila); `Exibição` (mesmo número toca junto), `Volume` (0–100, padrão 40, tooltip "na chamada cai à metade"), `Duração foto` (só foto sozinha; com áudio divide o tempo real); botão **Salvar** (`data-testid=filas-midia-salvar`) + botão **Fundo**/**Tirar fundo** (só foto, tooltip "Foto permanente atrás de tudo na TV") via `set_midia_fundo`; ativar/desativar, excluir, ↑/↓.
- **Volume com slider (22/09/2026)**: nos cards de **áudio/vídeo**, o botão speaker (`data-testid=filas-midia-som`, tooltip "Ajustar volume (abre o controle deslizante)") alterna um **slider 0–100** (`ui.slider`, `label-always`, `max-w-[300px]`, oculto por padrão) **sincronizado ao campo Volume** (`on_change` escreve em `inp_vol` e atualiza o rótulo `Volume: N`); o **Salvar** persiste volume/duração/exibição (`atualizar_midia`). Correção associada: `with inp.slot:` → `with inp_slot:` (o `with` deve abrir o **elemento**, não o atributo).
- **Controle da TV** (`bloco_controle_tv` — `telas.py`): vê o que está tocando + **Pausar/Retomar/Retornar/Avançar** remoto (a TV obedece via `tb_tv_estado.comando`).
- **Excluir em lote** (`telas.py`): `Excluir todas as filas` (admin) ou `Excluir todas minhas filas` (comum) → dialog → `excluir_todas_filas` (filtro `criado_por` quando não-admin). Sem fila preservada.
- **Administração via hambúrguer**: o botão `Administração` foi **removido do painel** — padrão dos módulos: menu hambúrguer → Administração (`/admin/filas`).

#### `gerar_senha` + `_proxima_senha` (`bd_manipulador.py`)

```python
_proxima_senha(atual, prefixo, inicio, fim): regex r"([A-Za-z]*)(\d+)" → pref+num+1 com :03d/04d; se fim>0 e prox>fim → prox=inicio (circular); infinito quando fim=0
gerar_senha(fila_id, ator, paciente_nome, etapa_nome, prioridade, manchester): vazio consome próximo elegível (_escolher_proximo_nome: Manchester domina; sem Manchester ≤3 chegada, >3 revezamento) → _emitir_senha (snapshot guichê da etapa, INSERT tb_chamada) + audit
```

#### Revezamento + Manchester (`_escolher_proximo_nome` — `bd_manipulador.py`)

Elegíveis: etapa `''` (geral) ou a pedida. Com Manchester: cor domina tudo (`vermelho>laranja>amarelo>verde>azul`, desempate demografia/chegada). Sem Manchester e até 3 elegíveis: chegada. Acima disso: ciclo `gestante → idoso → deficiente → comum → comum` (`prio_turno`, `CICLO_PRIORIDADE`).

#### Ordem da fala (`normalizar_voz_ordem` — `bd_manipulador.py`)

```python
VOZ_ORDEM_PADRAO = "fila,senha,nome,destino,guiche"
VOZ_CAMPOS = ("fila", "senha", "nome", "destino", "guiche")
normalizar_voz_ordem(valor): filtra só VOZ_CAMPOS sem repetir; vazia → (False, msg); completa faltantes no fim → (True, "senha,nome,fila,destino,guiche")
```

Usada em `criar_fila(..., voz_ordem)`, `atualizar_fila(..., voz_ordem=None)`, `obter_extras_fila` (default `VOZ_ORDEM_PADRAO`) e na TV (`_texto_chamada` monta fragmentos e ordena por `voz_ordem`; inválida cai em `VOZ_CAMPOS`).

### Painel `/tv` + `/tv/{fila_id}` + `?grupo=` + `?etapa=` — display com voz serializada e mídia

- **Rotas** (`main.py`): `/tv` pública (sem `pagina_restrita`) com `?grupo=` (compartilhada) + `?etapa=` (réplica por sala) + `/tv/{fila_id}` isolada (resolve grupo se pertence).
- **Layout `mostrar_tv(fila_id=None, tv_grupo=None, etapa=None)`** (`telas.py`): textos do criador (título/subtítulo/aguardando/legenda/título notícias) + ícone/título do sistema; corpo mídia (>90%, `max-height:62vh`, sem controles, `position: relative; overflow: hidden` só na área de mídia) + faixa lateral 240px (senha/paciente/destino/guichê + 3 últimos); rodapé notícias escuro (título+descrição+fonte+contador, `min-height:22vh`). **Papel de fundo**: foto marcada com `tb_midia.fundo=1` (uma por fila/global via `set_midia_fundo`, só `imagem`) renderiza como `div` absoluta (`inset:0`, `cover`, `opacity:0.22`, `z-index:0`, `pointer-events:none`) atrás do conteúdo (`z-index:1`); fundo **não entra no loop** de fotos. **Discrição**: nenhum termo de grupo/cor na tela — só o fundo colorido orienta.
- **Voz serializada por claim** (`refresh_chamada`, `ui.timer 3.0`): `buscar_proxima_fala` (mais antigo não falado por TV/etapa) + `tv_claim_fala` (compare-and-swap — um anuncia por vez, **sem cortar** o atual; fila de voz independente por etapa via `chave_tv_etapa`); repetição (`voz_repetir` × `voz_intervalo`) só com voz livre; `_js_duck_e_voz` (música à **metade — `data-vol` padrão `0.4`, cai a `×0.5` 2s antes**, bip 880Hz 0.35s, `speechSynthesis` `pt-BR` `0.9`, restaura 2s depois); `_falar_hora_se_hora` (cheia/meia, só sem chamada há 60s, uma vez por horário). Ordem da fala = `voz_ordem` da fila (só campos habilitados em `voz_*`).
- **Carrossel notícias** (`carregar_noticias` + `_mostrar_noticia`, `ui.timer 15.0` rotate + `120.0` reload): `listar_para_tv(limite=200)` filtrando censuradas + fallback elegante (rodapé nunca vazio: pausado/sem manchetes).
- **Playlist mídia** (`_render_slot` + `rotacionar_midia` auto-sustentada pela duração real): `midias_para_tv` (próprias + **áudios globais após as próprias**; vídeo/foto global só na geral) → `calcular_passo` (áudio/vídeo valem tempo **real** via mutagen; fotos dividem; sem real: fotos somam config, só vídeo=25s, nada=12s) → imagens alternadas por foto + áudio oculto + vídeo (fallback `muted` autoplay); comando remoto (pausar/retomar/próximo/anterior/slot) obedece `tb_tv_estado`. `rotacionar_midia` nunca morre: pausado só adia 5s, erro cai em 8s e reagenda.

### Administração (`/admin/filas`)

`telas_administracao.py` — `bloco_aparencia` (cupê "Aparência" `filas_*`, `com_texto_header=True`) + 2 cards + `painel_backup`. Acesso pelo **menu hambúrguer → Administração**.

**Card "Filas"** (`queue`, `grade=False`): admin vê todas; edição inline em `ui.expansion(f"Editar fila — {nome}")` recolhível (nome/prefixo/início/fim/guichê + TV grupo em uso/nova, todos com `delay=1000`; `endereco`/`descricao` removidos da UI) + etapas em `ui.expansion(f"Etapas sequenciais — {nome}")` recolhível + expansão **Voz e textos da TV** (checkboxes + `Ordem da fala` + repetir/intervalo com `delay=1000`) + `bloco_nomes_fila` + `bloco_midia_fila` (com botão **Fundo**/**Tirar fundo**) + `bloco_controle_tv` por fila. Botões: `Recarregar`, `Abrir TV geral` (`/tv`), `Excluir todas as filas` (dialog).

**Card "Áudio ambiente global — toca em todas as filas"** (`queue_music`, `grade=False`): áudios aqui tocam em **TODAS** as TVs após as mídias de cada fila (vídeos/fotos globais só na TV geral); volume por áudio (padrão 40); botão **Fundo**/**Tirar fundo** nas fotos; upload automático (`datahora_global.ext`); `Recarregar mídia` + `Preview TV` (`/tv`).

- **Versionamento**: sem `versao_modulo:filas` próprio — o rodapé central exibe só a versão global em `/filas` (ver Gaps conhecidos abaixo).

## Permissões

| Ação | `comum` com `filas` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/filas` | ✓ (próprias + liberadas + legado sem dono) | ✓ (todas) | ✗ ("Acesso restrito") |
| `Criar fila` | ✓ (sua) | ✓ | — |
| `Chamar próximo` / `Avançar` / etapa / Manchester | ✓ nas que vê (qualquer atendente) | ✓ todas | — |
| `Editar` (carrega no `Cadastro de fila`) | ✓ nas que vê | ✓ todas | — |
| `Acesso` (liberar usuários, `tb_fila_acesso`) | ✓ só dono (nas suas) | ✓ | — |
| `Excluir` (uma fila) | ✓ só suas | ✓ | — |
| `Excluir todas` | `Excluir todas minhas filas` | `Excluir todas as filas` | — |
| `Abrir TV` (`/tv/{id}`, `/tv?grupo=`, `?etapa=`) | ✓ (pública, sem login) | ✓ | ✓ |
| Ver `/admin/filas` (todas + mídia + áudio global) | ✗ | ✓ (via hambúrguer) | ✗ |

Gate `/filas`: `_pode_acessar` (admin geral ou `validar_acesso_modulo(user,"filas")`). `/tv` sem gate. `liberar_acesso` exige usuário **cadastrado** (busca na gestão). LGPD: `remover_vinculos_usuario` (limpa acessos) + `renomear_usuario` (`tb_chamada`/`tb_fila`/`tb_fila_acesso`).

## Rota e integrações

- Rotas: `/filas` (chave `filas`, ícone `queue`) — `main.py` (`pagina_restrita("Filas")`); `/tv` — `main.py` (`?grupo=` + `?etapa=`) + `/tv/{fila_id}` (isolada, resolve grupo). `REGISTRO_MODULOS["filas"]=page_filas`. Slugs via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` → `tb_auditoria_filas` (`criar_fila`, `atualizar_fila`, `excluir_fila`, `gerar_senha`, `avancar_chamada`, `excluir_todas_filas`, `criar_etapa`, `importar_nomes`, `transferir_*`, `liberar/remover_acesso`, `adicionar/excluir_midia`, `fundo_midia`, `definir_*` etc.).
- Backup: job `backup:filas` (`backup_horas:filas` 12h, `MAPA_BACKUPS` `filas: db_mod_filas.db`).
- **Integração Agregador**: TV consome `listar_para_tv(limite=200)` filtrando `conteudo_palavras_bloqueadas` (censura) + fallback nunca vazio.
- **Mídia**: `PASTA_MIDIA = mod_filas/midia` + `app.add_static_files("/midia_filas", ...)` (áudio `mp3/wav/ogg/m4a`, vídeo `mp4/webm/mov`, imagem `jpg/png/webp`) + `mutagen>=1.45`. Padrão `datahora_nomeFila.ext` sempre; `atualizar_fila` com nome novo chama `renomear_arquivos_fila`.
- Cadastro: `MODULOS_SISTEMA` (`autenticacao.py`→`("filas","Filas","queue","/filas")`), `MODULOS_BD` (`filas: db_mod_filas.db`), `PADROES_TEMA["filas"]` (`#000000`).

## Testes

```bash
.venv/bin/python -c "from mod_filas.bd_manipulador import init_db, listar_filas, gerar_senha, criar_fila; init_db(); print(listar_filas()); print(criar_fila('Ambulatório', prefixo='A', guiche='01', ator='master', senha_inicio=1, senha_fim=0, tv_grupo='recepcao')); print(gerar_senha(1,'master'))"
.venv/bin/python -c "from mod_filas.bd_manipulador import normalizar_tv_grupo, normalizar_voz_ordem; print(normalizar_tv_grupo('Ambulatório Geral')); print(normalizar_voz_ordem('senha,nome'))"
.venv/bin/python -c "from mod_filas.bd_manipulador import calcular_passo; print(calcular_passo([('audio',8,40.0)]+[('imagem',8,None)]*4))"
.venv/bin/pytest assets/test/test_seg_novos_modulos.py -q  # seções D–D8 (filas)
```

Seções D–D8 em `assets/test/test_seg_novos_modulos.py`: D (incremento + slug + sem seed), D2 (lista única + prioridades + revezamento + transferência mesma TV), D3 (Manchester domina + etapas + espera + nome/Manchester na senha + voz extras), D4 (duração real + fotos dividem + wav 40s), D5 (liberar acesso + visibilidade), D6 (claim de voz + etapa vinculada `[maria #... #recepção]`, tag desconhecida ignorada), D7 (ordem da fala: `normalizar_voz_ordem` válida/inválida + `criar_fila(voz_ordem)` completa faltantes + `atualizar_fila(voz_ordem)` troca), D8 (papel de fundo + volume 40: `VOLUME_AMBIENTE_PADRAO == 40`, só foto vira fundo, só um fundo por fila, renomear reaplica `datahora_nomeFila`).

Ver [Análise do Módulo](../analise_mod_filas.md) e [Arquitetura](../arquitetura.md).

## Complementos auditados (lote 3)

- **Rodapé escuro da TV** (`_fundo_rodape_escuro` — `telas.py`): deriva o fundo do rodapé de notícias da `cor_botao` do tema quando ela já é escura (luminância < 0,45); com tema claro cai em `#1b1b1b` para manter contraste com o texto claro.
- **Primitivas de voz da TV** (`bd_manipulador.py`): `tv_livre(chave)` (voz sem anúncio em andamento), `tv_bloquear(chave, dur_seg)` (reserva a voz), `definir_estado_tv(chave, slot_atual, pausado)` (persiste slot/pausa), `obter_estado_tv(chave)` (cria a linha se inexistir), `buscar_proxima_fala(...)` (anúncio mais antigo com `id > apos_id` no escopo TV/etapa). Chaves: `chave_tv(fila_id/tv_grupo)` (`grupo:<slug>`/`fila:<id>`/`geral`) e `chave_tv_etapa(...)` (`<base>+<etapa>`, voz independente por sala); `ids_do_grupo(tv_grupo)` lista as filas da TV compartilhada; `montar_rotas_static()` serve `mod_filas/midia/` em `/midia_filas/*`.
- **Lista de nomes — persistência** (`bd_manipulador.py`): `listar_nomes(fila_id, somente_pendentes)`, `salvar_lista_nomes(fila_id, conteudo)` (grava `datahora_nomeFila.txt` em `mod_filas/midia/`), `remover_nome`/`limpar_nomes`/`definir_prioridade_nome`/`definir_etapa_nome`/`definir_manchester_nome`.
- **LGPD** (`bd_manipulador.py`): `remover_vinculos_usuario(user_nome)` (limpa `tb_fila_acesso`) e `renomear_usuario(nome_atual, novo_nome)` (`tb_chamada`/`tb_fila`/`tb_fila_acesso`).
- **Massa de teste — 70 nomes** (`mod_filas/massa_nomes_teste.py`, classe `GeradorMassaNomes`): gera sob demanda `mod_filas/midia/massa_nomes_teste_70.txt` com 10 `#gestante` + 10 `#idoso` + 50 comuns e exatamente 12 linhas com cor Manchester (`vermelho 3/laranja 3/amarelo 2/verde 2/azul 2`); helpers `contar_distribuicao`/`validar_massa`/`gerar_massa_teste` + CLI `--semente/--saida`; usa `faker pt_BR` quando disponível, senão lista determinística (semente 42).

## Gaps conhecidos (código ↔ docs)

- `dialogo_editar_fila` existe em `telas.py` mas está **legado** (o Editar atual carrega no `Cadastro de fila`); no `/admin/filas` a edição é inline — docs citam o legado apenas como referência.
- `telas_administracao.py` **não tem função de relatório** — o card final é `painel_backup` (job `backup:filas`); "relatório" do lote refere-se ao histórico isolado por fila + auditoria `tb_auditoria_filas`.
- Rodapé `versao_modulo:filas` citado em versões anteriores **não existe no código atual** (`telas.py`/`telas_administracao.py` sem footer de versão).

## Pontos de atenção

- **Projeto sem filas fixas**: nasce vazio; excluir tudo é permitido.
- **`tv_grupo` slug** (`recepcao-2`): use a lista "em uso" para compartilhar; vazio = isolada.
- **Numeração infinita**: `senha_fim=0` = circular; `_proxima_senha` reinicia em `inicio`.
- **TV grupo vs isolada vs etapa**: `tv_grupo` vazio → `/tv/{id}`; preenchido → `/tv?grupo=`; `?etapa=` replica só a sala (voz independente).
- **Ordem da fala**: `voz_ordem` (`fila,senha,nome,destino,guiche`) define a sequência; `normalizar_voz_ordem` rejeita vazia e completa faltantes; só campos habilitados em `voz_*` são falados.
- **Voz serializada por claim**: `tv_claim_fala` evita cortar (fila independente por etapa); repetição e hora cheia/meia respeitam voz ocupada; ducking à metade (volume 40 → ~20 na chamada).
- **Mídia por fila + ambiente global**: `slot`/`Exibição` igual = juntos (com cabeçalho por grupo); fotos dividem o tempo real do áudio; volume padrão 40; `midias_para_tv` põe áudios globais após as próprias em todas as TVs.
- **Papel de fundo**: só foto (`set_midia_fundo`), uma por fila/global; backdrop absoluto só na área de mídia (`opacity:0.22`), fora do loop.
- **Arquivos sempre `datahora_nomeFila`**: `nome_arquivo_midia` no upload/stage; `renomear_arquivos_fila` reaplica ao renomear a fila.
- **UX**: `delay=1000` em todos os campos (rótulo curto + detalhe no tooltip/`info_outline`); cards recolhíveis (`Cadastro de fila`, `Etapas/lista`, `Anexos`); **Editar** carrega no cadastro; admin via hambúrguer (botão removido do painel).
- **Discrição**: telas mostram só cor de fundo para prioridade/Manchester; termos só nos controles de edição.
- `/tv` pública — TV na recepção sem sessão; se expor fora da rede, adicionar `ACL`.
- `tb_chamada.guiche` snapshot — não retroage.
- `bd_criador.py` morto.
