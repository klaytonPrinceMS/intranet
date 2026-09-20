# Filas — `mod_filas` (Multi-filas + TV por etapa + Mídia por fila + Lista única)

> Queue/call manager multi-queue: routes `/filas` + `/tv?grupo=` (shared) + `/tv/{id}` (isolated) + `?etapa=` per-room replica · own database `db_mod_filas.db` · tables `tb_fila` (voice/text columns) / `tb_fila_etapa` / `tb_chamada` (priority+manchester) / `tb_fila_nomes` (one list per queue) / `tb_midia` (per-queue + global ambient) / `tb_tv_estado` (claim+remote) / `tb_fila_acesso` / `tb_config_filas` · project starts with NO queues (no `Geral` seed) · `tv_grupo` URL slug + in-use group list · queue creation with step sequence (Name | Desk), configurable voice, editable TV texts, optional initial list · media per queue (mp3/mp4/photos, default volume 20, real duration via mutagen, photos split audio time) + global ambient audio on every TV · `nomes.txt` tagged (`#prioridade #manchester #etapa`), transfer within same TV, round-robin + Manchester dominating (no sensitive words on screen, only background color) · wait/call per step/room, serialized voice without cutting (claim), 50% ducking, full/half hour · per-user access (`tb_fila_acesso` + management search), Edit/Access buttons on cards, news up to 200.

---

# Filas — `mod_filas` (Multi-filas + TV por etapa + Mídia por fila + Lista única)

> Gestor de filas/chamadas multi-filas: rotas `/filas` + `/tv?grupo=` (compartilhada) + `/tv/{id}` (isolada) + `?etapa=` réplica por sala · banco próprio `db_mod_filas.db` · tabelas `tb_fila` (colunas voz/textos) / `tb_fila_etapa` / `tb_chamada` (prioridade+manchester) / `tb_fila_nomes` (uma lista por fila) / `tb_midia` (por fila + ambiente global) / `tb_tv_estado` (claim+remoto) / `tb_fila_acesso` / `tb_config_filas` · projeto nasce SEM filas (sem seed `Geral`) · `tv_grupo` slug de URL + lista de grupos em uso · criação com sequência de etapas (Nome | Guichê), voz configurável, textos da TV editáveis, lista inicial opcional · mídia por fila (mp3/mp4/fotos, volume padrão 20, duração real via mutagen, fotos dividem tempo do áudio) + áudio ambiente global em todas as TVs · `nomes.txt` com tags (`#prioridade #manchester #etapa`), transferência dentro da mesma TV, revezamento + Manchester dominando (sem termos sensíveis nas telas, só cor de fundo) · espera/chamar por etapa/sala, voz serializada sem cortar (claim), ducking 50%, hora cheia/meia · acesso liberado por usuário (`tb_fila_acesso` + busca na gestão), botões Editar/Acesso nos cards, notícias até 200.

## Propósito

Gestor **multi-filas por local** com TV dedicada por fila, por grupo ou por etapa/sala. O projeto **nasce sem filas** — cada usuário com acesso cria as suas (isoladas por `criado_por` + liberadas via `tb_fila_acesso`); `administrador_geral` vê todas. Cada fila tem **numeração própria** (`prefixo` + `senha_inicio`→`senha_fim`, com `fim=0` = infinito circular) e **sequência de etapas/salas** (`tb_fila_etapa`: ex. Recepção | 01 → Triagem | 02 → Consultório 3 | 03 — cada etapa é subfila com guichê próprio, painel de "próximo" e TV replicável só dela via `?etapa=`). A TV pode ser **isolada** (`/tv/{fila_id}`), **compartilhada por grupo** (`/tv?grupo=recepcao` — slug de URL, sem acento/espaço) ou **replicada por etapa** (`/tv/{id}?etapa=Triagem`). Quando ociosa, reproduz playlist de **mídias da fila** (áudio/foto/vídeo em `/midia_filas`, fotos dividem o tempo real do áudio) + **áudio ambiente global** do admin (toca em todas as TVs); ao chamar, toca **bip 880Hz + voz** (`SpeechSynthesis` `pt-BR`) serializada por claim (uma por vez, sem cortar) com **ducking 50%** da música, repetição configurável e **hora cheia/meia**. Carrossel **notícias do Agregador** no rodapé (até 200, filtrado por `conteudo_palavras_bloqueadas`).

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `banco_conexao.conexao("filas")`. Criador: `init_db()` `bd_manipulador.py:113-277` (sem seed — **nenhuma fila fixa**; migra grupos legados para slug via `normalizar_tv_grupo`).

**`tb_fila`**: `id` PK, `nome` UNIQUE, `senha_atual` TEXT, `status` TEXT (`ativa`), `guiche` TEXT, `data_criacao` + `endereco` TEXT, `descricao` TEXT, `prefixo` TEXT (`A`), `criado_por` TEXT, `senha_inicio` INTEGER (1), `senha_fim` INTEGER (0=infinito), `tv_grupo` TEXT (vazio=isolada, slug `a-z0-9-`, máx 40, reservados bloqueados) + **voz** `voz_nome/voz_senha/voz_destino/voz_guiche/voz_fila/voz_hora` (1/0 quais campos são falados) + `voz_repetir` (0–10) + `voz_intervalo` (1–60s) + **textos TV** `tv_titulo/tv_subtitulo/tv_aguardando ('AGUARDE CHAMADA')/tv_midia_legenda/tv_noticias_titulo ('Notícias')` + `prio_turno` (revezamento). Migração `_garantir_coluna` para colunas novas.

**`tb_fila_etapa`**: `id` PK, `fila_id` FK CASCADE, `ordem` INTEGER, `nome` TEXT, `guiche` TEXT, `ativo` INTEGER. Índice `idx_fila_etapa_fila(fila_id,ordem)`.

**`tb_chamada`**: `id` PK, `fila_id` FK CASCADE, `senha` TEXT, `guiche` TEXT (snapshot), `chamado_em`, `chamado_por` TEXT + `paciente_nome` TEXT, `etapa_nome` TEXT, `fila_nome` TEXT + `prioridade` TEXT (`comum/gestante/idoso/deficiente`) + `manchester` TEXT (`vermelho/laranja/amarelo/verde/azul`).

**`tb_fila_nomes`** (lista única por fila): `id` PK, `fila_id` FK CASCADE, `nome` TEXT, `ordem` INTEGER, `usado` INTEGER, `criado_em` + `prioridade` + `manchester` + `etapa` TEXT (etapa vinculada — nasce direto nela). Índice `idx_fila_nomes_fila(fila_id,usado,ordem)`. Arquivo salvo no servidor como `datahora_nomeFila.txt` (`salvar_lista_nomes`).

**`tb_midia`** (por fila + global): `id` PK, `nome` TEXT, `tipo` CHECK(`audio`/`video`/`imagem`), `caminho` TEXT (`/midia_filas/...`), `arquivo_original` TEXT, `ordem` INTEGER, `ativo` INTEGER, `criado_em` + `fila_id` NULL (NULL=global) + `volume` (padrão 20) + `duracao` (foto, 3–120s, padrão 8) + `slot` (exibição — mesmo número toca junto) + `duracao_real` REAL (extraída via `mutagen`, fallback WAV nativo). Nome no servidor `datahora_nomeFila.ext` (`nome_arquivo_midia`). Índice `idx_midia_fila_slot(fila_id,slot,ordem)`. Pasta `mod_filas/midia/` → `/midia_filas/*` via `montar_rotas_static()`.

**`tb_tv_estado`** (claim + controle remoto): `chave` PK (`grupo:<slug>` / `fila:<id>` / `geral`, + `+<etapa>` por sala), `slot_atual`, `pausado`, `comando` (`pausar|retomar|proximo|anterior|slot:<n>`), `fala_ate` REAL (reserva de voz), `ultima_falada` INTEGER. Funções: `chave_tv`/`chave_tv_etapa`, `obter_estado_tv`, `tv_livre`/`tv_bloquear`, `tv_claim_fala` (compare-and-swap — um anuncia por vez, sem cortar), `buscar_proxima_fala` (mais antigo não falado por escopo), `enviar/consumir_comando_tv`.

**`tb_fila_acesso`**: `fila_id` FK CASCADE + `user_nome` (UNIQUE par) + `criado_em`. Índice por `user_nome`. Funções: `filas_liberadas`, `listar_acessos`, `liberar_acesso` (só usuário cadastrado na gestão), `remover_acesso`.

**`tb_config_filas`**: `filas_modo_tv` (`1`), `filas_senha_prefixo` (`A`), `filas_guiche_padrao` (`01`).

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- `mostrar_tela(nome, perfil)` (`telas.py:577-855`): gate `_pode_acessar`, `ler_tema("filas")` + `cabecalho`, card **Nova fila por local** (nome/endereço/descrição/prefixo/início/fim/guichê + `TV grupo em uso` select de grupos existentes + `Nova TV grupo` slug + checkboxes voz nome/senha/destino/guichê/fila/hora cheia-meia + repetir/intervalo + textarea sequência `Etapa | Guichê` + textarea lista inicial opcional + expansão textos TV + `criar_fila` + link TV isolada/compartilhada), `render_filas()` com `listar_filas_visiveis` (próprias + liberadas + legado sem dono; admin vê todas), card por fila com botões **TV grupo/Abrir TV + Excluir + Editar + Acesso** + badges de etapas + Chamar (`Paciente avulso` + `select Etapa` + `select Grupo avulso` + `gerar_senha`) + Histórico isolado (5, com ajuste de Manchester + `Avançar` sequencial) + `bloco_etapas` (por sala: próximo/nome/Manchester/TV da etapa) + `bloco_nomes_fila` (lista única + transferência mesma TV) + `bloco_midia_fila` (upload por fila) + `bloco_controle_tv` (pausar/retomar/retornar/avançar remoto). Botão `Excluir todas (minhas)` com dialog (sem fila preservada — projeto pode ficar sem filas).
- `mostrar_tv(fila_id=None, tv_grupo=None, etapa=None)` (`telas.py:858-1362`): layout mídia >90% + faixa lateral 240px (senha/paciente/destino/guichê + 3 últimos) + rodapé notícias escuro (título+descrição+fonte+contador). `slots` por `slot` (mesmo número = juntos); `_render_slot()` com `calcular_passo` (tempo real); `refresh_chamada` (`3.0` + imediata) usa **fila de voz** (`buscar_proxima_fala` + `tv_claim_fala` por `chave_tv_etapa` — anuncia o mais antigo não falado, um por vez, sem cortar; repetição via `_rep` só com voz livre) + `_js_duck_e_voz` (música à metade 2s antes, bip 880Hz 0.35s, `speechSynthesis pt-BR 0.9`, restaura 2s depois) + `_falar_hora_se_hora` (cheia/meia, só sem chamada há 60s); `carregar_noticias` (`listar_para_tv(limite=200)`, fallback elegante nunca vazio) + `_mostrar_noticia` (`15.0`) + `ui.timer 120.0`; `rotacionar_midia` encadeado pela duração real do slot; comando remoto `consumir_comando_tv` (pausar/retomar/próximo/anterior/slot). **Discrição**: nenhuma palavra de grupo/cor na tela — só o fundo colorido (`_estilo_manchester`) orienta.
- Rotas `/tv` pública (sem `pagina_restrita`) + `/tv/{fila_id}` (`main.py:755-789`) — `?grupo=` compartilhada, `/{id}` isolada, `?etapa=` réplica por sala.
- Blocos reutilizáveis (`telas.py:55-575`, usados em `/filas` e `/admin/filas`): `bloco_midia_fila`, `bloco_nomes_fila`, `bloco_etapas`, `dialogo_editar_fila`, `bloco_liberar_acesso`, `dialogo_acesso_fila`, `bloco_controle_tv`.

## Regras de negócio relevantes

- **Sem seed** (`init_db` `bd_manipulador.py:224-233`): projeto nasce sem filas; `excluir_fila`/`excluir_todas_filas` sem exceção preservada.
- **`tv_grupo` slug** (`normalizar_tv_grupo` `1635-1659` + `listar_grupos_tv`): minúsculo `a-z0-9-`, sem acento/espaço, 2–40 chars, reservados (`tv/admin/login/api/...`) bloqueados; migração de legados no boot; selects "TV grupo em uso" na criação/edição/admin.
- **Criar fila** (`criar_fila` `428-497`): valida `nome*`, `prefixo ^[A-Za-z0-9]+$`, `inicio>=0`, `fim==0 || fim>=inicio`; slug de grupo; `voz_repetir` 0–10 + `voz_intervalo` 1–60s; `senha_atual = prefixo + (inicio-1)` (03d/04d); **sequência `etapas=[(nome, guiche)]`** (default Atendimento/Triagem/Consultório 3); `audit criar_fila`; UNIQUE → `Já existe fila com nome`.
- **Listagem visível** (`listar_filas_visiveis` `293-311`): admin geral/módulo → todas; senão próprias (`criado_por=user`) + liberadas (`tb_fila_acesso`) + legado sem dono. `liberar_acesso` exige usuário cadastrado (`mod_gest_cad_usuario.obter_usuario`); dono não se auto-libera.
- **Etapas/salas** (`620-694` + `917-970`): CRUD + `reordenar_etapas`; `espera_etapa` (senhas cuja última posição é a etapa, por chegada); `proximo_da_etapa` (reanuncia mais antigo aguardando, senão emite o vinculado à etapa); `avancar_chamada` sequencial (`Já está na última etapa`).
- **Incremento** (`gerar_senha` `740-778` + `_proxima_senha` `699-718` + `_emitir_senha` `721-737`): vazio consome próximo elegível da lista (`_escolher_proximo_nome`); avulso usa grupo informado; nome com etapa vinculada nasce nela; snapshot guichê da etapa; `audit gerar_senha`.
- **Lista única + tags** (`990-1185`): `_parse_nome_tags` (`Maria #gestante #vermelho #recepcao`, `[colchetes]`, `,`/`;`/`#` separadores, etapa por igualdade NFKD, desconhecidas ignoradas); `importar_nomes` (uma lista por fila — recusa se existe sem `substituir`); `transferir_nome`/`transferir_todos` (só mesma TV, destino sem lista); `definir_etapa_nome`/`definir_manchester_nome`/`definir_nome_senha` (vincula nome ao papelzinho)/`definir_manchester_senha` (qualquer atendente, a qualquer hora) /`definir_prioridade_nome`.
- **Revezamento + Manchester** (`_escolher_proximo_nome` `1292-1333`): elegíveis = etapa `''` (geral) ou a pedida; com Manchester → cor domina (`vermelho>laranja>amarelo>verde>azul`, desempate demografia/chegada); sem Manchester e ≤3 → chegada; >3 → ciclo (`gestante, idoso, deficiente, comum, comum` via `prio_turno`).
- **Mídia** (`1341-1626`): `tipo_por_extensao` (mp3/wav/ogg/m4a→audio, mp4/webm/mov→video, jpg/png/webp→imagem); `duracao_real_arquivo` (mutagen + fallback WAV); `calcular_passo` (áudio/vídeo valem tempo real; fotos dividem; sem real: fotos somam config, só vídeo=25s, nada=12s); `nome_arquivo_midia` (`datahora_nomeFila.ext`, global=`global`); `listar_midias(fila_id=None→todas, X→só X)`; `midias_para_tv` (próprias + áudios globais após as próprias; vídeo/foto global só na TV geral); `adicionar/atualizar/excluir/reordenar/set_midia_ativa` (volume 0–100 padrão 20, duração 3–120, slot 0–999).
- **Última/Histórico TV** (`ultima_chamada`/`ultima_chamada_tv`/`listar_chamadas`/`listar_chamadas_tv` com `etapa_nome` opcional + `IN` por grupo).
- **LGPD**: `remover_vinculos_usuario` (limpa `tb_fila_acesso`), `renomear_usuario` (`tb_chamada`/`tb_fila`/`tb_fila_acesso`).
- **Censura**: TV filtra via `listar_para_tv` (`conteudo_palavras_bloqueadas`, `titulo_bloqueado`).

## Integrações com o núcleo

`autenticacao.validar_acesso_modulo`/`perfil_global_de`/`eh_admin_do_modulo`, `banco_conexao.conexao`/`get_config`, `tema_modulo.ler_tema`/`notificar`/`bloco_aparencia`, `ui_comum.botao`/`card_admin`/`rodape_salvar_restaurar`/`painel_backup`, `observabilidade.get_logger`. Auditoria → `tb_auditoria_filas`. `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA` com `filas`. **Integração Agregador**: `mod_filas/telas.py:1268-1338` consome `listar_para_tv(limite=200)` → carrossel título+descrição+fonte+contador (`15s` rotate, `120s` reload, fallback elegante nunca vazio) no rodapé escuro da TV. **Mídia**: `PASTA_MIDIA` + `/midia_filas` + `mutagen>=1.45` (`requirements.txt:37-38`). Ver `mod_agregador_noticias`.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-FILAS-01 | Multi-filas por local, projeto sem filas fixas | `tb_fila` + `criar_fila` (`428-497`); sem seed (`224`); excluir sem exceção (`577-615`) |
| RF-FILAS-02 | Numeração configurável `prefixo+inicio→fim` com `fim=0` infinito | `_proxima_senha` (`699-718`) `prox>fim→inicio`, width 3/4, `fim=0` circular |
| RF-FILAS-03 | Sequência de etapas na criação + fluxo sequencial | `etapas=[(nome,guiche)]` no criar (`475-488`) + CRUD (`620-694`) + `avancar_chamada` (`781-821`) |
| RF-FILAS-04 | TV isolada `/tv/{id}` vs compartilhada `/tv?grupo=` (slug) vs réplica `?etapa=` | `tv_grupo` slug (`1635-1659`) + `mostrar_tv(fila_id/tv_grupo/etapa)` (`858-1362`) + `main.py:755-789` + `chave_tv_etapa` |
| RF-FILAS-05 | Mídia por fila + áudio ambiente global | `tb_midia` `fila_id` NULL=global + `midias_para_tv` (`1481-1497`) + `calcular_passo` + `mutagen` |
| RF-FILAS-06 | Isolamento por dono + acesso liberado por usuário | `criado_por` + `tb_fila_acesso` + `listar_filas_visiveis` (`293-311`) + busca na gestão (`bloco_liberar_acesso`) |
| RF-FILAS-07 | Censura de títulos na TV (até 200 notícias) | `listar_para_tv(limite=200)` filtrado (`1268-1306`) + fallback nunca vazio |
| RF-FILAS-08 | Exclusão uma/todas sem fila preservada | `excluir_fila` + `excluir_todas_filas` com filtro `criado_por` quando não-admin |
| RF-FILAS-09 | Lista única com tags + transferência mesma TV | `_parse_nome_tags` + `importar_nomes` (uma por fila) + `transferir_nome/todos` (mesma TV) |
| RF-FILAS-10 | Revezamento + Manchester dominando, sem termos sensíveis | `_escolher_proximo_nome` (cor>demografia>chegada; ciclo) + telas só com cor de fundo |
| RF-FILAS-11 | Espera/chamar por etapa/sala (qualquer atendente) | `espera_etapa` + `proximo_da_etapa` + `bloco_etapas` (próximo/nome/cor/TV etapa) |
| RF-FILAS-12 | Voz serializada sem cortar + ducking + hora cheia/meia | `tv_claim_fala` + `buscar_proxima_fala` + `_js_duck_e_voz` (50%) + `_falar_hora_se_hora` + repetir/intervalo |
| RF-FILAS-13 | Voz configurável + textos TV editáveis + lista inicial | `voz_*` + `tv_*` em criar/atualizar + `obter_extras_fila` + textarea lista inicial |
| RF-FILAS-14 | Controle remoto da TV pela edição | `tb_tv_estado` comando + `bloco_controle_tv` (pausar/retomar/retornar/avançar) + `consumir_comando_tv` na TV |
| RF-FILAS-15 | Botões Editar/Acesso nos cards | `dialogo_editar_fila` (tudo editável) + `dialogo_acesso_fila` (buscar e chamar) |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-PERS-01 | Persistência por módulo com `banco_conexao` | `banco_conexao.conexao("filas")` (`get_connection` `32-42`) + `PRAGMA journal_mode=WAL` + `foreign_keys=ON` |
| RNF-PERS-02 | WAL + auditoria central | `audit_log` → `db_mod_auditoria.db` `tb_auditoria_filas` (`_audit` `45-47`) |
| RNF-SEG-01 | Validação prefixo/slug/isolamento | `prefixo ^[A-Za-z0-9]+$`, slug 2–40 + reservados, isolamento `criado_por` + `tb_fila_acesso` |
| RNF-SEG-02 | XSS (nh via censura) | Títulos do agregador filtrados via `titulo_bloqueado` antes de exibir; `listar_para_tv` censura |
| RNF-PERF-01 | Poll TV 3s + rotação pela duração real + notícias 15s/120s | `ui.timer 3.0 refresh_chamada` + `rotacionar_midia` encadeado por `calcular_passo` + `15.0 _mostrar_noticia` + `120.0 carregar_noticias` |
| RNF-PERF-02 | Duração real sem travar (mutagen fail-soft) | `duracao_real_arquivo` try/except + fallback WAV + preenchimento melhor-esforço no `init_db` |
| RNF-USAB-01 | Voz `pt-BR` serializada + ducking + hora | `tv_claim_fala` (sem cortar) + `_js_duck_e_voz` (50%, bip 880Hz 0.35s, `pt-BR 0.9`) + `_falar_hora_se_hora` |
| RNF-USAB-02 | Links TV + grupos em uso + ícone padrão intranet | `get_config icone_sistema/titulo_sistema` + `listar_grupos_tv` nos selects + links `/tv?grupo=`/`/tv/{id}`/`?etapa=` |
| RNF-COMP-01 | Compatibilidade SQLite ↔ PostgreSQL | `banco_conexao.conexao(chave)` roteia; DDL `CREATE TABLE IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS`, `INSERT OR IGNORE`→`ON CONFLICT`, `?`→`%s` |
| RNF-RESP-01 | Responsividade | `w-full flex-wrap` `min-w` nos cards; TV mídia `max-height:62vh` + lateral 240px + rodapé `min-height:22vh` |
| RNF-DISC-01 | Discrição (sem termos sensíveis) | Telas exibem só cor de fundo (`_estilo_manchester`); palavras de grupo/cor só nos controles de edição |

## Pontos de atenção

- Projeto nasce SEM filas — `init_db` sem seed; `excluir_todas` pode zerar tudo.
- `tv_grupo` é slug (`recepcao-2`): selects mostram grupos em uso; legados com acento/espaço são migrados no boot.
- Numeração infinita `fim=0` circular (`_proxima_senha`).
- TV `tv_grupo` vazio=isolada `/tv/{id}`, preenchido=compartilhada `/tv?grupo=`, `?etapa=` replica só a sala (fila de voz independente por etapa).
- Voz em fila (`buscar_proxima_fala` + `tv_claim_fala`): anuncia o mais antigo não falado, um por vez, sem cortar; repetição só com voz livre.
- Mídia por fila (`fila_id`) + áudio global (NULL, todas as TVs); vídeo/foto global só na TV geral; `slot` igual = juntos; fotos dividem o tempo real do áudio.
- Uma lista de nomes por fila; transferência só dentro da mesma TV; destino de `transferir_todos` deve estar sem lista.
- Manchester domina demografia e chegada; telas nunca exibem os termos — só cor de fundo.
- `/tv` pública — adicionar `ACL` se expor fora da rede.
- `tb_chamada.guiche` snapshot — não retroage.
- `tb_tv_estado.fala_ate` usa relógio do servidor — múltiplas TVs sincronizam pelo banco.

## Status

| Item | Situação |
|:---|:---:|
| Banco WAL 8 tabelas, sem seed, slug migrado | Implementado |
| `criar_fila` sequência etapas + voz + textos + lista inicial + `atualizar/excluir` + `excluir_todas` | Implementado |
| `gerar_senha` + `_proxima_senha` + `avancar` + `espera/proximo_da_etapa` + revezamento/Manchester | Implementado |
| `nomes.txt` tags + 1 lista/fila + transferência mesma TV + vincular nome/Manchester | Implementado |
| `tb_fila_acesso` + busca gestão + botões Editar/Acesso | Implementado |
| Painel `/filas` + blocos reutilizáveis + controle remoto TV | Implementado |
| TV `/tv` + `/tv/{id}` + `?grupo=` + `?etapa=` + claim + ducking 50% + hora cheia/meia + notícias 200 | Implementado |
| Mídia por fila + ambiente global + `mutagen` + `calcular_passo` + `datahora_nomeFila` | Implementado |
| Admin `/admin/filas` (filas + voz/textos + nomes + mídia + controle + áudio global + backup) | Implementado |
| LGPD + auditoria `tb_auditoria_filas` | Implementado |
| Testes `assets/test/test_seg_novos_modulos.py` seções D–D6 | Implementado |
