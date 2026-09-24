# Filas — `mod_filas` (Multi-filas + TV por etapa + Mídia por fila + Lista única + Ordem da fala + Papel de fundo)

> Queue/call manager multi-queue: routes `/filas` + `/tv?grupo=` (shared) + `/tv/{id}` (isolated) + `?etapa=` per-room replica · own database `db_mod_filas.db` · tables `tb_fila` (voice `voz_ordem` + text columns) / `tb_fila_etapa` / `tb_chamada` (priority+manchester) / `tb_fila_nomes` (one list per queue) / `tb_midia` (per-queue + global ambient + `fundo` backdrop) / `tb_tv_estado` (claim+remote) / `tb_fila_acesso` / `tb_config_filas` · project starts with NO queues (no `Geral` seed) · `tv_grupo` URL slug + in-use group list · collapsible `Cadastro de fila` + `Etapas/lista` + `Anexos` cards, `delay=1000` tooltips, voice order `voz_ordem` via `normalizar_voz_ordem` · media per queue (mp3/mp4/photos, default volume 40, real duration via mutagen, photos split audio time, `Fundo` backdrop absolute only over media area) + global ambient audio on every TV via `midias_para_tv` · `datahora_nomeFila` always (`renomear_arquivos_fila` on rename) · `nomes.txt`/CSV tagged via `csv_para_tags` (`#prioridade #manchester #etapa`), transfer within same TV, round-robin + Manchester dominating (no sensitive words on screen, only background color) · wait/call per step/room, serialized voice without cutting (claim per step), 50% ducking, full/half hour · per-user access (`tb_fila_acesso` + management search), Edit (in-panel) / Access buttons on cards, news up to 200 · admin via hamburger (`/admin/filas`).

---

# Filas — `mod_filas` (Multi-filas + TV por etapa + Mídia por fila + Lista única + Ordem da fala + Papel de fundo)

> Gestor de filas/chamadas multi-filas: rotas `/filas` + `/tv?grupo=` (compartilhada) + `/tv/{id}` (isolada) + `?etapa=` réplica por sala · banco próprio `db_mod_filas.db` · tabelas `tb_fila` (colunas voz `voz_ordem` + textos) / `tb_fila_etapa` / `tb_chamada` (prioridade+manchester) / `tb_fila_nomes` (uma lista por fila) / `tb_midia` (por fila + ambiente global + `fundo` papel de fundo) / `tb_tv_estado` (claim+remoto) / `tb_fila_acesso` / `tb_config_filas` · projeto nasce SEM filas (sem seed `Geral`) · `tv_grupo` slug de URL + lista de grupos em uso · cards recolhíveis (`Cadastro de fila`, `Etapas/lista`, `Anexos`), `delay=1000` em todos os campos, ordem da fala `voz_ordem` via `normalizar_voz_ordem` · mídia por fila (mp3/mp4/fotos, volume padrão 40, duração real via mutagen, fotos dividem tempo do áudio, foto `Fundo` absoluta só na área de mídia) + áudio ambiente global em todas as TVs via `midias_para_tv` · `datahora_nomeFila` sempre (`renomear_arquivos_fila` ao renomear) · `nomes.txt`/CSV com tags via `csv_para_tags` (`#prioridade #manchester #etapa`), transferência dentro da mesma TV, revezamento + Manchester dominando (sem termos sensíveis nas telas, só cor de fundo) · espera/chamar por etapa/sala, voz serializada sem cortar (claim por etapa), ducking à metade, hora cheia/meia · acesso liberado por usuário (`tb_fila_acesso` + busca na gestão), botões Editar (no painel) / Acesso nos cards, notícias até 200 · admin via hambúrguer (`/admin/filas`).

## Propósito

Gestor **multi-filas por local** com TV dedicada por fila, por grupo ou por etapa/sala. O projeto **nasce sem filas** — cada usuário com acesso cria as suas (isoladas por `criado_por` + liberadas via `tb_fila_acesso`); `administrador_geral` vê todas. Cada fila tem **numeração própria** (`prefixo` + `senha_inicio`→`senha_fim`, com `fim=0` = infinito circular) e **sequência de etapas/salas** (`tb_fila_etapa`: ex. Recepção | 01 → Triagem | 02 → Consultório 3 | 03 — cada etapa é subfila com guichê próprio, painel de "próximo" e TV replicável só dela via `?etapa=`). A TV pode ser **isolada** (`/tv/{fila_id}`), **compartilhada por grupo** (`/tv?grupo=recepcao` — slug de URL, sem acento/espaço) ou **replicada por etapa** (`/tv/{id}?etapa=Triagem`). Quando ociosa, reproduz playlist de **mídias da fila** (áudio/foto/vídeo em `/midia_filas`, fotos dividem o tempo real do áudio, volume padrão 40) + **áudio ambiente global** do admin (toca em todas as TVs via `midias_para_tv`); foto marcada como **papel de fundo** fica fixa atrás de tudo só na área de mídia. Ao chamar, toca **bip 880Hz + voz** (`SpeechSynthesis` `pt-BR`) serializada por claim (uma por vez, sem cortar) na **ordem `voz_ordem`**, com **ducking à metade** da música, repetição configurável e **hora cheia/meia**. Carrossel **notícias do Agregador** no rodapé (até 200, filtrado por `conteudo_palavras_bloqueadas`). Painel com **cards recolhíveis** e **`delay=1000`** em todos os campos; **Editar** carrega no `Cadastro de fila`; admin via **hambúrguer**.

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `banco_conexao.conexao("filas")`. Criador: `init_db()` em `bd_manipulador.py` (sem seed — **nenhuma fila fixa**; migra grupos legados para slug via `normalizar_tv_grupo`; garante `voz_ordem` + `fundo` + `volume` 40; limpa `stage_*` órfão +24h).

**`tb_fila`**: `id` PK, `nome` UNIQUE, `senha_atual` TEXT, `status` TEXT (`ativa`), `guiche` TEXT, `data_criacao` + `endereco` TEXT, `descricao` TEXT (legado no banco, ocultos na UI), `prefixo` TEXT (`A`), `criado_por` TEXT, `senha_inicio` INTEGER (1), `senha_fim` INTEGER (0=infinito), `tv_grupo` TEXT (vazio=isolada, slug `a-z0-9-`, máx 40, reservados bloqueados) + **voz** `voz_nome/voz_senha/voz_destino/voz_guiche/voz_fila/voz_hora` (1/0 quais campos são falados) + `voz_ordem` TEXT (`DEFAULT 'fila,senha,nome,destino,guiche'`) + `voz_repetir` (0–10) + `voz_intervalo` (1–60s) + **textos TV** `tv_titulo/tv_subtitulo/tv_aguardando ('AGUARDE CHAMADA')/tv_midia_legenda/tv_noticias_titulo ('Notícias')` + `prio_turno` (revezamento). Migração `_garantir_coluna` para colunas novas. Constantes `VOZ_ORDEM_PADRAO` + `VOZ_CAMPOS`.

**`tb_fila_etapa`**: `id` PK, `fila_id` FK CASCADE, `ordem` INTEGER, `nome` TEXT, `guiche` TEXT, `ativo` INTEGER. Índice `idx_fila_etapa_fila(fila_id,ordem)`.

**`tb_chamada`**: `id` PK, `fila_id` FK CASCADE, `senha` TEXT, `guiche` TEXT (snapshot), `chamado_em`, `chamado_por` TEXT + `paciente_nome` TEXT, `etapa_nome` TEXT, `fila_nome` TEXT + `prioridade` TEXT (`comum/gestante/idoso/deficiente`) + `manchester` TEXT (`vermelho/laranja/amarelo/verde/azul`).

**`tb_fila_nomes`** (lista única por fila): `id` PK, `fila_id` FK CASCADE, `nome` TEXT, `ordem` INTEGER, `usado` INTEGER, `criado_em` + `prioridade` + `manchester` + `etapa` TEXT (etapa vinculada — nasce direto nela). Índice `idx_fila_nomes_fila(fila_id,usado,ordem)`. Arquivo salvo no servidor como `datahora_nomeFila.txt` (`salvar_lista_nomes`).

**`tb_midia`** (por fila + global + fundo): `id` PK, `nome` TEXT, `tipo` CHECK(`audio`/`video`/`imagem`), `caminho` TEXT (`/midia_filas/...`), `arquivo_original` TEXT, `ordem` INTEGER, `ativo` INTEGER, `criado_em` + `fila_id` NULL (NULL=global) + `volume` (padrão 40) + `duracao` (foto, 3–120s, padrão 8) + `slot` (exibição — mesmo número toca junto) + `duracao_real` REAL (extraída via `mutagen`, fallback WAV nativo) + `fundo` INTEGER (0/1 — só `imagem`, uma por fila/global). Nome no servidor **sempre** `datahora_nomeFila.ext` (`nome_arquivo_midia`); `renomear_arquivos_fila` reaplica ao renomear a fila. Índice `idx_midia_fila_slot(fila_id,slot,ordem)`. Pasta `mod_filas/midia/` → `/midia_filas/*` via `montar_rotas_static()`.

**`tb_tv_estado`** (claim + controle remoto): `chave` PK (`grupo:<slug>` / `fila:<id>` / `geral`, + `+<etapa>` por sala), `slot_atual`, `pausado`, `comando` (`pausar|retomar|proximo|anterior|slot:<n>`), `fala_ate` REAL (reserva de voz), `ultima_falada` INTEGER. Funções: `chave_tv`/`chave_tv_etapa`, `obter_estado_tv`, `tv_livre`/`tv_bloquear`, `tv_claim_fala` (compare-and-swap — um anuncia por vez, sem cortar), `buscar_proxima_fala` (mais antigo não falado por escopo), `enviar/consumir_comando_tv`.

**`tb_fila_acesso`**: `fila_id` FK CASCADE + `user_nome` (UNIQUE par) + `criado_em`. Índice por `user_nome`. Funções: `filas_liberadas`, `listar_acessos`, `liberar_acesso` (só usuário cadastrado na gestão), `remover_acesso`. Botão **Acesso** nos cards (`dialogo_acesso_fila`).

**`tb_config_filas`**: `filas_modo_tv` (`1`), `filas_senha_prefixo` (`A`), `filas_guiche_padrao` (`01`).

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- `mostrar_tela(nome, perfil)` (`telas.py`): gate `_pode_acessar`, `ler_tema("filas")` + `cabecalho`, `ui.expansion("Cadastro de fila")` (nome/prefixo/início/fim/guichê + `TV grupo em uso` + `Nova TV grupo` lado a lado + checkboxes voz + `Ordem da fala` + repetir/intervalo + `ui.expansion("Etapas, lista inicial e arquivos (opcional)")` com `_preencher_lista` + `ui.expansion("Anexar vídeos, áudios e fotos (opcional)")` com `_anexar_midia`/`midias_stage`/`_render_stage` + expansão textos TV + `Criar fila` / `Salvar alterações` / `Cancelar` via `_salvar_cadastro`/`_salvar_edicao`/`_cancelar_edicao`/`_limpar_form`/`_carregar_edicao`/`_editar_no_painel`), `render_filas()` com `listar_filas_visiveis` (próprias + liberadas + legado sem dono; admin vê todas), card por fila com botões **TV grupo/Abrir TV + Excluir + Editar (carrega no cadastro) + Acesso** + badges de etapas + Chamar (`Paciente avulso` + `select Etapa` + `select Grupo avulso` + `gerar_senha`) + Histórico isolado (5, com ajuste de Manchester + `Avançar` sequencial) + `bloco_etapas` (por sala: próximo/nome/Manchester/TV da etapa) + `bloco_nomes_fila` (lista única + transferência mesma TV) + `bloco_midia_fila` (upload por fila + `Fundo`, **Salvar** com `data-testid=filas-midia-salvar`) + `bloco_controle_tv` (pausar/retomar/retornar/avançar remoto). Botão `Excluir todas (minhas)` com dialog (sem fila preservada). **Sem botão Administração no painel** — admin via hambúrguer (`/admin/filas` com edição inline e etapas em `ui.expansion` recolhíveis). **Tooltips `delay=1000`** em todos os campos (rótulo curto + detalhe no tooltip/`info_outline`); `endereco`/`descricao` fora da UI.
- `mostrar_tv(fila_id=None, tv_grupo=None, etapa=None)` (`telas.py`): área de mídia `position: relative; overflow: hidden` + `div` de fundo absoluta (`cover`, `opacity:0.22`, `z-index:0`) quando há `fundo=1` (excluído do loop; conteúdo em `z-index:1`) + faixa lateral 240px (senha/paciente/destino/guichê + 3 últimos) + rodapé notícias escuro (título+descrição+fonte+contador). `slots` por `slot` (mesmo número = juntos, com cabeçalho `— Exibição N (juntos) —` no painel); `_render_slot()` com `calcular_passo` (tempo real); `refresh_chamada` (`3.0` + imediata) usa **fila de voz** (`buscar_proxima_fala` + `tv_claim_fala` por `chave_tv_etapa` — anuncia o mais antigo não falado, um por vez, sem cortar; repetição só com voz livre) + `_texto_chamada` na ordem `voz_ordem` (via `normalizar_voz_ordem`, fallback `VOZ_CAMPOS`) + `_js_duck_e_voz` (música à metade — `data-vol` `0.4` → `×0.5` 2s antes, bip 880Hz 0.35s, `speechSynthesis pt-BR 0.9`, restaura 2s depois) + `_falar_hora_se_hora` (cheia/meia, só sem chamada há 60s); `carregar_noticias` (`listar_para_tv(limite=200)`, fallback elegante nunca vazio) + `_mostrar_noticia` (`15.0`) + `ui.timer 120.0`; `rotacionar_midia` auto-sustentada (pausado adia 5s, erro cai em 8s, reagenda pela duração real; vídeo com fallback `muted`); comando remoto `consumir_comando_tv` (pausar/retomar/próximo/anterior/slot). **Discrição**: nenhuma palavra de grupo/cor na tela — só o fundo colorido (`_estilo_manchester`) orienta.
- Rotas `/tv` pública (sem `pagina_restrita`) + `/tv/{fila_id}` (`main.py`) — `?grupo=` compartilhada, `/{id}` isolada, `?etapa=` réplica por sala.
- Blocos reutilizáveis (`telas.py`, usados em `/filas` e `/admin/filas`): `bloco_midia_fila` (com `Fundo`), `bloco_nomes_fila`, `bloco_etapas`, `dialogo_editar_fila` (legado — Editar atual carrega no cadastro), `bloco_liberar_acesso`, `dialogo_acesso_fila`, `bloco_controle_tv`.

## Regras de negócio relevantes

- **Sem seed** (`init_db` em `bd_manipulador.py`): projeto nasce sem filas; `excluir_fila`/`excluir_todas_filas` sem exceção preservada.
- **`tv_grupo` slug** (`normalizar_tv_grupo` + `listar_grupos_tv`): minúsculo `a-z0-9-`, sem acento/espaço, 2–40 chars, reservados (`tv/admin/login/api/...`) bloqueados; migração de legados no boot; selects "TV grupo em uso" na criação/edição/admin (todos com `delay=1000`).
- **Ordem da fala** (`normalizar_voz_ordem` + `VOZ_ORDEM_PADRAO` + `VOZ_CAMPOS`): só `fila,senha,nome,destino,guiche`, sem repetir; vazia rejeita (`Ordem da fala vazia — use ex: senha,nome,destino`); faltantes completados no fim (`senha,nome` → `senha,nome,fila,destino,guiche`). `criar_fila`/`atualizar_fila` validam; `obter_extras_fila` devolve o default; `_texto_chamada` ordena por ela (só `voz_*` ligados; fallback `senha`).
- **Criar fila** (`criar_fila` em `bd_manipulador.py`): valida `nome*`, `prefixo ^[A-Za-z0-9]+$`, `inicio>=0`, `fim==0 || fim>=inicio`; slug de grupo; `voz_ordem` normalizada; `voz_repetir` 0–10 + `voz_intervalo` 1–60s; `senha_atual = prefixo + (inicio-1)` (03d/04d); **sequência `etapas=[(nome, guiche)]`**; `audit criar_fila`; UNIQUE → `Já existe fila com nome`. `endereco`/`descricao` aceitos no backend, ocultos na UI.
- **Atualizar fila** (`atualizar_fila`): `voz_ordem` opcional validada; **nome mudou → `renomear_arquivos_fila`** reaplica `datahora_nomeFila` em todas as mídias (rename `src→dst` + `UPDATE caminho`).
- **Listagem visível** (`listar_filas_visiveis`): admin geral/módulo → todas; senão próprias (`criado_por=user`) + liberadas (`tb_fila_acesso`) + legado sem dono. `liberar_acesso` exige usuário cadastrado (`mod_gest_cad_usuario.obter_usuario`); dono não se auto-libera.
- **Etapas/salas** (`bd_manipulador.py`): CRUD + `reordenar_etapas`; `espera_etapa` (senhas cuja última posição é a etapa, por chegada); `proximo_da_etapa` (reanuncia mais antigo aguardando, senão emite o vinculado à etapa); `avancar_chamada` sequencial (`Já está na última etapa`).
- **Incremento** (`gerar_senha` + `_proxima_senha` + `_emitir_senha`): vazio consome próximo elegível da lista (`_escolher_proximo_nome`); avulso usa grupo informado; nome com etapa vinculada nasce nela; snapshot guichê da etapa; `audit gerar_senha`.
- **Lista única + tags** (`bd_manipulador.py`): `csv_para_tags` (CSV `,`/`;` com cabeçalho `nome/grupo/cor/etapa` → linhas com tags); `_parse_nome_tags` (`Maria #gestante #vermelho #recepcao`, `[colchetes]`, `,`/`;`/`#` separadores, etapa por igualdade NFKD, desconhecidas ignoradas); `importar_nomes` (uma lista por fila — recusa se existe sem `substituir`); `transferir_nome`/`transferir_todos` (só mesma TV, destino sem lista); `definir_etapa_nome`/`definir_manchester_nome`/`definir_nome_senha` (vincula nome ao papelzinho)/`definir_manchester_senha` (qualquer atendente, a qualquer hora) /`definir_prioridade_nome`.
- **Revezamento + Manchester** (`_escolher_proximo_nome`): elegíveis = etapa `''` (geral) ou a pedida; com Manchester → cor domina (`vermelho>laranja>amarelo>verde>azul`, desempate demografia/chegada); sem Manchester e ≤3 → chegada; >3 → ciclo (`gestante, idoso, deficiente, comum, comum` via `prio_turno`).
- **Mídia** (`bd_manipulador.py`): `VOLUME_AMBIENTE_PADRAO = 40`; `tipo_por_extensao` (mp3/wav/ogg/m4a→audio, mp4/webm/mov→video, jpg/png/webp→imagem); `duracao_real_arquivo` (mutagen + fallback WAV); `calcular_passo` (áudio/vídeo valem tempo real; fotos dividem; sem real: fotos somam config, só vídeo=25s, nada=12s); `nome_arquivo_midia` (**sempre** `datahora_nomeFila.ext`, global=`global`); `listar_midias(fila_id=None→todas, X→só X)` (inclui `fundo`); `midias_para_tv` (próprias + áudios globais após as próprias; vídeo/foto global só na TV geral); `adicionar/atualizar/excluir/reordenar/set_midia_ativa` (volume 0–100 padrão 40, duração 3–120, slot 0–999); `set_midia_fundo` (só `imagem`, uma por fila/global — demais zeradas, `audit fundo_midia`); `renomear_arquivos_fila` (reaplica padrão ao renomear).
- **Última/Histórico TV** (`ultima_chamada`/`ultima_chamada_tv`/`listar_chamadas`/`listar_chamadas_tv` com `etapa_nome` opcional + `IN` por grupo).
- **LGPD**: `remover_vinculos_usuario` (limpa `tb_fila_acesso`), `renomear_usuario` (`tb_chamada`/`tb_fila`/`tb_fila_acesso`).
- **Censura**: TV filtra via `listar_para_tv` (`conteudo_palavras_bloqueadas`, `titulo_bloqueado`).

## Integrações com o núcleo

`autenticacao.validar_acesso_modulo`/`perfil_global_de`/`eh_admin_do_modulo`, `banco_conexao.conexao`/`get_config`, `tema_modulo.ler_tema`/`notificar`/`bloco_aparencia`, `ui_comum.botao`/`card_admin`/`rodape_salvar_restaurar`/`painel_backup`, `observabilidade.get_logger`. Auditoria → `tb_auditoria_filas`. `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA` com `filas`. **Integração Agregador**: `mod_filas/telas.py` consome `listar_para_tv(limite=200)` → carrossel título+descrição+fonte+contador (`15s` rotate, `120s` reload, fallback elegante nunca vazio) no rodapé escuro da TV. **Mídia**: `PASTA_MIDIA` + `/midia_filas` + `mutagen>=1.45` (`requirements.txt`). Ver `mod_agregador_noticias`.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-FILAS-01 | Multi-filas por local, projeto sem filas fixas | `tb_fila` + `criar_fila`; sem seed; excluir sem exceção |
| RF-FILAS-02 | Numeração configurável `prefixo+inicio→fim` com `fim=0` infinito | `_proxima_senha` `prox>fim→inicio`, width 3/4, `fim=0` circular |
| RF-FILAS-03 | Sequência de etapas na criação + fluxo sequencial | `etapas=[(nome,guiche)]` no criar + CRUD + `avancar_chamada` |
| RF-FILAS-04 | TV isolada `/tv/{id}` vs compartilhada `/tv?grupo=` (slug) vs réplica `?etapa=` | `tv_grupo` slug + `mostrar_tv(fila_id/tv_grupo/etapa)` + `main.py` + `chave_tv_etapa` |
| RF-FILAS-05 | Mídia por fila + áudio ambiente global em todas as TVs | `tb_midia` `fila_id` NULL=global + `midias_para_tv` (áudios globais após próprias) + `calcular_passo` + `mutagen` |
| RF-FILAS-06 | Isolamento por dono + acesso liberado por usuário | `criado_por` + `tb_fila_acesso` + `listar_filas_visiveis` + busca na gestão (`bloco_liberar_acesso`) |
| RF-FILAS-07 | Censura de títulos na TV (até 200 notícias) | `listar_para_tv(limite=200)` filtrado + fallback nunca vazio |
| RF-FILAS-08 | Exclusão uma/todas sem fila preservada | `excluir_fila` + `excluir_todas_filas` com filtro `criado_por` quando não-admin |
| RF-FILAS-09 | Lista única com tags + CSV + transferência mesma TV | `csv_para_tags` + `_parse_nome_tags` + `importar_nomes` (uma por fila) + `transferir_nome/todos` (mesma TV) + upload `nomes.txt`/`.csv` |
| RF-FILAS-10 | Revezamento + Manchester dominando, sem termos sensíveis | `_escolher_proximo_nome` (cor>demografia>chegada; ciclo) + telas só com cor de fundo |
| RF-FILAS-11 | Espera/chamar por etapa/sala (qualquer atendente) | `espera_etapa` + `proximo_da_etapa` + `bloco_etapas` (próximo/nome/cor/TV etapa) |
| RF-FILAS-12 | Voz serializada por claim sem cortar + ordem + ducking + hora cheia/meia | `tv_claim_fala` + `buscar_proxima_fala` + `normalizar_voz_ordem`/`_texto_chamada` + `_js_duck_e_voz` (metade, `0.4`) + `_falar_hora_se_hora` + repetir/intervalo |
| RF-FILAS-13 | Voz configurável (inclui ordem) + textos TV editáveis + lista inicial + anexos | `voz_*` + `voz_ordem` em criar/atualizar + `obter_extras_fila` + textarea lista inicial + `midias_stage`/`stage_*` |
| RF-FILAS-14 | Controle remoto da TV pela edição | `tb_tv_estado` comando + `bloco_controle_tv` (pausar/retomar/retornar/avançar) + `consumir_comando_tv` na TV |
| RF-FILAS-15 | Botões Editar (no painel) / Acesso nos cards | `_editar_no_painel`/`_carregar_edicao`/`_salvar_edicao` + `dialogo_acesso_fila` (buscar e chamar) + `tb_fila_acesso` |
| RF-FILAS-16 | Papel de fundo (foto fixa só na área de mídia) | `tb_midia.fundo` + `set_midia_fundo` (só imagem, uma por fila/global) + backdrop absoluto (`opacity:0.22`) fora do loop |
| RF-FILAS-17 | Arquivos sempre `datahora_nomeFila` (inclusive ao renomear) | `nome_arquivo_midia` + `renomear_arquivos_fila` (chamado em `atualizar_fila` quando nome muda) |
| RF-FILAS-18 | UX: cards recolhíveis + `delay=1000` + admin via hambúrguer | `ui.expansion("Cadastro de fila"/"Etapas, lista inicial e arquivos"/"Anexar vídeos, áudios e fotos")` + `ui.tooltip(...).props("delay=1000")` + botão Administração removido |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-PERS-01 | Persistência por módulo com `banco_conexao` | `banco_conexao.conexao("filas")` (`get_connection`) + `PRAGMA journal_mode=WAL` + `foreign_keys=ON` |
| RNF-PERS-02 | WAL + auditoria central | `audit_log` → `db_mod_auditoria.db` `tb_auditoria_filas` (`_audit`) |
| RNF-SEG-01 | Validação prefixo/slug/ordem/isolamento | `prefixo ^[A-Za-z0-9]+$`, slug 2–40 + reservados, `normalizar_voz_ordem` só `VOZ_CAMPOS`, isolamento `criado_por` + `tb_fila_acesso` |
| RNF-SEG-02 | XSS (nh via censura) | Títulos do agregador filtrados via `titulo_bloqueado` antes de exibir; `listar_para_tv` censura |
| RNF-PERF-01 | Poll TV 3s + rotação auto-sustentada + notícias 15s/120s | `ui.timer 3.0 refresh_chamada` + `rotacionar_midia` (pausado adia 5s, erro 8s) + `15.0 _mostrar_noticia` + `120.0 carregar_noticias` |
| RNF-PERF-02 | Duração real sem travar (mutagen fail-soft) | `duracao_real_arquivo` try/except + fallback WAV + preenchimento melhor-esforço no `init_db` |
| RNF-USAB-01 | Voz `pt-BR` serializada + ordem + ducking + hora | `tv_claim_fala` (sem cortar) + `_texto_chamada` (`voz_ordem`) + `_js_duck_e_voz` (metade, `0.4`, bip 880Hz 0.35s, `pt-BR 0.9`) + `_falar_hora_se_hora` |
| RNF-USAB-02 | Links TV + grupos em uso + ícone padrão intranet + tooltips | `get_config icone_sistema/titulo_sistema` + `listar_grupos_tv` nos selects + links `/tv?grupo=`/`/tv/{id}`/`?etapa=` + `delay=1000` |
| RNF-COMP-01 | Compatibilidade SQLite ↔ PostgreSQL | `banco_conexao.conexao(chave)` roteia; DDL `CREATE TABLE IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS`, `INSERT OR IGNORE`→`ON CONFLICT`, `?`→`%s` |
| RNF-RESP-01 | Responsividade | `w-full flex-wrap` `min-w` nos cards; TV mídia `max-height:62vh` + lateral 240px + rodapé `min-height:22vh`; fundo absoluto só na área de mídia |
| RNF-DISC-01 | Discrição (sem termos sensíveis) | Telas exibem só cor de fundo (`_estilo_manchester`); palavras de grupo/cor só nos controles de edição |

## Complementos auditados (lote 3)

- `_fundo_rodape_escuro` (`telas.py`): fundo do rodapé de notícias deriva da `cor_botao` do tema se escura (luminância < 0,45), senão `#1b1b1b`.
- Primitivas de voz: `tv_livre`/`tv_bloquear`/`definir_estado_tv`/`obter_estado_tv`/`buscar_proxima_fala` + chaves `chave_tv`/`chave_tv_etapa` + `ids_do_grupo` + `montar_rotas_static` (`/midia_filas`).
- Nomes: `listar_nomes`/`salvar_lista_nomes` (`datahora_nomeFila.txt`) + `remover_nome`/`limpar_nomes`; LGPD `remover_vinculos_usuario`/`renomear_usuario`.
- Massa 70 nomes (`massa_nomes_teste.py`, `GeradorMassaNomes`): 10 `#gestante` + 10 `#idoso` + 50 comuns, 12 com Manchester; `contar_distribuicao`/`validar_massa`/`gerar_massa_teste` + CLI `--semente/--saida` em `mod_filas/midia/`.

## Gaps conhecidos (código ↔ docs)

- `dialogo_editar_fila` (`telas.py`) legado — Editar atual carrega no `Cadastro de fila`; admin usa edição inline.
- Sem função de relatório em `telas_administracao.py` — "relatório" = histórico isolado + auditoria `tb_auditoria_filas` + `painel_backup`.
- Footer `versao_modulo:filas` citado antes não existe no código atual.

## Pontos de atenção

- Projeto nasce SEM filas — `init_db` sem seed; `excluir_todas` pode zerar tudo.
- `tv_grupo` é slug (`recepcao-2`): selects mostram grupos em uso; legados com acento/espaço são migrados no boot.
- Numeração infinita `fim=0` circular (`_proxima_senha`).
- TV `tv_grupo` vazio=isolada `/tv/{id}`, preenchido=compartilhada `/tv?grupo=`, `?etapa=` replica só a sala (fila de voz independente por etapa).
- Voz em fila (`buscar_proxima_fala` + `tv_claim_fala`): anuncia o mais antigo não falado, um por vez, sem cortar; ordem por `voz_ordem` (`normalizar_voz_ordem`); repetição só com voz livre.
- Volume ambiente 40 com ducking à metade na chamada (`data-vol` `0.4` → `×0.5`).
- Mídia por fila (`fila_id`) + áudio global (NULL, todas as TVs via `midias_para_tv`); vídeo/foto global só na TV geral; `slot`/`Exibição` igual = juntos; fotos dividem o tempo real do áudio.
- Papel de fundo: só foto, uma por fila/global (`set_midia_fundo`); backdrop absoluto só na área de mídia, fora do loop.
- Arquivos sempre `datahora_nomeFila` — `renomear_arquivos_fila` reaplica ao renomear a fila.
- Uma lista de nomes por fila (`csv_para_tags` converte CSV); transferência só dentro da mesma TV; destino de `transferir_todos` deve estar sem lista.
- Manchester domina demografia e chegada; telas nunca exibem os termos — só cor de fundo.
- UX: `delay=1000` em todos os campos; cards recolhíveis; **Editar** carrega no `Cadastro de fila`; admin via hambúrguer (botão removido do painel); `endereco`/`descricao` ocultos na UI.
- `/tv` pública — adicionar `ACL` se expor fora da rede.
- `tb_chamada.guiche` snapshot — não retroage.
- `tb_tv_estado.fala_ate` usa relógio do servidor — múltiplas TVs sincronizam pelo banco.
- **Reparo sintático de `telas.py` (22/09/2026)**: o arquivo chegou com corrupção sintática (placeholders `nicegui_`, `ui_.`, `arqui_.o`, `gui_.he`, `exclui_.`, `.class(`, `validar.acesso_modulo`) e nem importava — reparo sistemático validado contra o `bd_manipulador` (fonte de verdade), `COMPILE_OK` (`ast.parse`) + `IMPORT_OK`. Evidência do estado anterior preservada em `/tmp/telas_filas_pre_reparo.py` (fora do repo).
- **Volume com slider (22/09/2026)**: botão speaker `filas-midia-som` alterna slider 0–100 sincronizado ao campo `Volume`; Salvar persiste (`atualizar_midia`); `with inp.slot:` corrigido para `with inp_slot:`.

## Status

| Item | Situação |
|:---|:---:|
| Banco WAL 8 tabelas, sem seed, slug migrado + `voz_ordem` + `fundo` + volume 40 | Implementado |
| `criar_fila` sequência etapas + voz (inclui ordem) + textos + lista inicial + anexos stage + `atualizar/excluir` (rename reaplica padrão) + `excluir_todas` | Implementado |
| `gerar_senha` + `_proxima_senha` + `avancar` + `espera/proximo_da_etapa` + revezamento/Manchester + `csv_para_tags` | Implementado |
| `nomes.txt`/CSV tags + 1 lista/fila + transferência mesma TV + vincular nome/Manchester | Implementado |
| `tb_fila_acesso` + busca gestão + botões Editar (no painel) / Acesso | Implementado |
| Painel `/filas` recolhível + `delay=1000` + blocos reutilizáveis + controle remoto TV (sem botão Administração) | Implementado |
| TV `/tv` + `/tv/{id}` + `?grupo=` + `?etapa=` + claim por etapa + ordem + ducking metade (40) + hora cheia/meia + notícias 200 + fundo | Implementado |
| Mídia por fila + ambiente global (`midias_para_tv`) + `mutagen` + `calcular_passo` + `datahora_nomeFila` sempre + `set_midia_fundo` | Implementado |
| Admin `/admin/filas` via hambúrguer (filas + voz/ordem/textos + nomes + mídia/fundo + controle + áudio global + backup) | Implementado |
| LGPD + auditoria `tb_auditoria_filas` (inclui `fundo_midia`) | Implementado |
| Testes `assets/test/test_seg_novos_modulos.py` seções D–D8 | Implementado |
| Reparo sintático de `telas.py` + slider de volume `filas-midia-som` (22/09/2026) | Implementado |

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| filas | Sem `CrudBase`; `sqlite_master` em migração de `tb_midia` | `mod_filas/bd_manipulador.py:75` (`sqlite_master`) · sem `CrudBase` (verificado por busca) | Migrar para `CrudBase`; `_tabela_existe()` interno; testar `/tv`, `/tv/{id}`, `/tv?grupo=` nos dois backends | Médio (voz claim + ducking + `/midia_filas`) |

Detalhe consolidado em [Plano WAL + Paridade](../registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).
