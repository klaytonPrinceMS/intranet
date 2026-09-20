# Filas — `mod_filas` (Multi-filas + Carrossel Notícias + Mídia TV)

> Queue/call manager multi-queue: routes `/filas` + `/tv?grupo=` (shared) + `/tv/{id}` (isolated) · own database `db_mod_filas.db` · tables `tb_fila`/`tb_fila_etapa`/`tb_chamada`/`tb_midia`/`tb_config_filas` · queue per local `endereco/prefixo/senha_inicio/fim` (fim=0 infinite) + `criado_por` + `tv_grupo` · isolated by creator vs `administrador_geral` · sequential steps + TV 40s media playlist + 3s beep/voice (new id only) + news carousel `listar_para_tv` 7s/120s (censorship filtered).

---

# Filas — `mod_filas` (Multi-filas + Carrossel Notícias + Mídia TV)

> Gestor de filas/chamadas multi-filas: rotas `/filas` + `/tv?grupo=` (compartilhada) + `/tv/{id}` (isolada) · banco próprio `db_mod_filas.db` · tabelas `tb_fila`/`tb_fila_etapa`/`tb_chamada`/`tb_midia`/`tb_config_filas` · fila por local `endereco/prefixo/senha_inicio/fim` (fim=0 infinito) + `criado_por` + `tv_grupo` · isolamento por criador vs `administrador_geral` · etapas sequenciais + TV playlist mídia 40s + 3s bip/voz (só novo id) + carrossel notícias `listar_para_tv` 7s/120s (filtrado por censura).

## Propósito

Gestor **multi-filas por local** com TV dedicada por fila ou por grupo. Cada fila isolada (não interfere em outra) com numeração `prefixo+inicio→fim` (infinito quando `fim=0`) e fluxo sequencial `Atendimento → Triagem → Consultório 3` (`tb_fila_etapa`). TV **isolada** `/tv/{fila_id}` ou **compartilhada** `/tv?grupo=xxx` (mesmo `tv_grupo` → mesma TV). Playlist **áudio elevador / vídeo propaganda** em `/midia_filas` (global, 40s rotação quando ociosa, pausada ao chamar com **bip 880Hz + voz `pt-BR` só no novo id**). Carrossel **notícias do Agregador** no rodapé (filtrado por `conteudo_palavras_bloqueadas`).

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `banco_conexao.conexao("filas")`. Criador: `init_db()` `bd_manipulador.py:56-141`.

**`tb_fila`**: `id` PK, `nome` UNIQUE, `senha_atual` TEXT (`A000`), `status` TEXT (`ativa`), `guiche` TEXT (`01`), `data_criacao` + `endereco` TEXT, `descricao` TEXT, `prefixo` TEXT (`A`), `criado_por` TEXT, `senha_inicio` INTEGER (1), `senha_fim` INTEGER (0=infinito), `tv_grupo` TEXT (vazio=isolada). Migração `_garantir_coluna` para colunas novas. Seed `Geral` (`A000`, `prefixo A`, `1→0`, `tv_grupo ''`, `criado_por ''`) + 3 etapas padrão.

**`tb_fila_etapa`**: `id` PK, `fila_id` FK CASCADE, `ordem` INTEGER, `nome` TEXT, `guiche` TEXT, `ativo` INTEGER. Índice `idx_fila_etapa_fila(fila_id,ordem)`.

**`tb_chamada`**: `id` PK, `fila_id` FK CASCADE, `senha` TEXT, `guiche` TEXT (snapshot), `chamado_em`, `chamado_por` TEXT + `paciente_nome` TEXT, `etapa_nome` TEXT, `fila_nome` TEXT. Migração `paciente_nome/etapa_nome/fila_nome`.

**`tb_midia`**: `id` PK, `nome` TEXT, `tipo` CHECK(`audio`/`video`), `caminho` TEXT (`/midia_filas/...`), `arquivo_original` TEXT, `ordem` INTEGER, `ativo` INTEGER, `criado_em`. Pasta `mod_filas/midia/` → `/midia_filas/*` via `montar_rotas_static()` (`app.add_static_files`).

**`tb_config_filas`**: `filas_modo_tv` (`1`), `filas_senha_prefixo` (`A`), `filas_guiche_padrao` (`01`).

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- `mostrar_tela(nome, perfil)` (`telas.py:28-188`): gate `_pode_acessar`, `ler_tema("filas")` + `cabecalho`, card **Nova fila por local** (inputs nome/endereco/descricao/prefixo/inicio/fim/guiche/tv_grupo + `criar_fila` + link TV isolada/compartilhada + `notificar`), `render_filas()` com `listar_filas_visiveis` (isolamento por criador vs admin), card por fila com `Senha atual • Prefixo • inicio→fim (∞) • Guichê • TV • Dono • status` + `TV grupo`/`Abrir TV desta fila` + `Excluir` (dono/admin, Geral bloqueada) + etapas badges + Chamar (`Paciente` + `select Etapa` + `gerar_senha`) + Histórico isolado (`listar_chamadas(5, fila_id)`) + `Avançar` sequencial. Botão `Excluir todas` com dialog (`excluir_todas_filas` filtrada por criador).
- `mostrar_tv(fila_id=None, tv_grupo=None)` (`telas.py:191-370`): `w-full h-screen bg-black`, header com **ícone padrão intranet** (`get_config icone_sistema/titulo_sistema`, `hub`/`INTRANET`) + `TV — Grupo`/`Fila`/`Todas as filas` + `lbl_topo` + `lbl_senha 10vw` + `lbl_paciente` + `lbl_destino` + `lbl_guiche` + `media_container` (`media_html` audio/video) + rodapé notícias `bg-grey-900 min-height:14vh`. `estado {ultimo_id, midia_idx}` + `noticias_tv {lista, idx}`. `refresh_chamada` (`3.0` + imediata) lê `ultima_chamada_tv` (agregada por `tv_grupo` quando grupo) e só toca **bip+voz se `cid != ultimo_id`** (`_js_beep_e_voz` `AudioContext` 880Hz 0.35s + `speechSynthesis pt-BR 0.9 cancel`); `carregar_noticias` (`listar_para_tv` censura filtrada) + `_mostrar_noticia` (`7.0`) + `ui.timer 120.0`; `rotacionar_midia` (`40.0`, só ociosa).
- Rota `/tv` pública (sem `pagina_restrita`) + `/tv/{fila_id}` (`main.py:753-778`) — `?grupo=` compartilhada, `/{id}` isolada (resolve grupo se pertence).

## Regras de negócio relevantes

- **Criar fila** (`criar_fila` `bd_manipulador.py:208-255`): valida `nome*`, `prefixo ^[A-Za-z0-9]+$`, `inicio>=0`, `fim==0 || fim>=inicio`; `senha_atual = prefixo + (inicio-1):03d` (04d se >999); 3 etapas padrão; `audit criar_fila` com `endereco/prefixo/inicio/fim/tv=/tv/{fid}`; UNIQUE → `Já existe fila com nome`.
- **Listagem isolada** (`listar_filas_visiveis` `bd_manipulador.py:157-175`): `eh_admin_geral` ou `eh_admin_modulo` → `listar_filas()` todas 13 colunas; senão `WHERE criado_por=user OR criado_por='' OR IS NULL` (legado visível a todos até ser assumido).
- **Atualizar/Excluir** (`atualizar_fila` `258-313` com `senha_inicio/fim/tv_grupo`, `excluir_fila` `316-332` bloqueia `Geral`, `excluir_todas_filas` `335-356` com filtro `criado_por` quando não-admin).
- **Etapas** (`359-436`): `listar_etapas ORDER BY ordem`, `criar_etapa` max ordem+1, `atualizar_etapa`, `excluir_etapa`, `reordenar_etapas`.
- **Incremento** (`gerar_senha` `462-501` + `_proxima_senha` `440-459`): `SELECT ... senha_atual,prefixo,guiche,senha_inicio,senha_fim` → `_proxima_senha(atual,prefixo,inicio,fim)` (regex `([A-Za-z]*)(\d+)` + `prox>fim→inicio` circular, width 3/4) → resolve guichê da etapa → `UPDATE tb_fila` + `INSERT tb_chamada` com `paciente_nome/etapa_nome/fila_nome` + `audit gerar_senha`.
- **Avançar** (`avancar_chamada` `504-542`): sequencial por `ordem`; já está na última → `Já está na última etapa`.
- **Última/Histórico TV** (`ultima_chamada` `545-555`, `ultima_chamada_tv` `558-573` com `tv_grupo IN`, `listar_chamadas` `576-587`, `listar_chamadas_tv` `589-603` idem).
- **Mídia** (`606-694`): `listar_midias` (ativas), `adicionar_midia` max ordem+1, `excluir_midia` (remove arquivo só se dentro de `PASTA_MIDIA`), `reordenar_midias`, `set_midia_ativa`, `montar_rotas_static` `/midia_filas` (mod_filas/midia, `os.makedirs`).
- **LGPD**: `remover_vinculos_usuario` (0), `renomear_usuario` (`UPDATE tb_chamada/ tb_fila criado_por`).
- **Censura**: TV filtra via `listar_para_tv` (`conteudo_palavras_bloqueadas`, `titulo_bloqueado`).

## Integrações com o núcleo

`autenticacao.validar_acesso_modulo`/`perfil_global_de`/`eh_admin_do_modulo`, `banco_conexao.conexao`/`get_config`, `tema_modulo.ler_tema`/`notificar`, `ui_comum.botao`/`card_admin`/`rodape_salvar_restaurar`, `observabilidade.get_logger`. Auditoria → `tb_auditoria_filas`. `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA` com `filas`. **Integração Agregador**: `mod_filas/telas.py:330-357` consome `listar_para_tv(limite=10, censura filtrada)` → carrossel título+descrição (`7s` rotate, `120s` reload) no rodapé da TV (`bg-grey-900`). **Mídia**: `PASTA_MIDIA` + `/midia_filas` (isFormats `mp3/wav/ogg/m4a`→audio, `mp4/webm`→video) + upload sanitizado + `uuid6`. Ver `mod_agregador_noticias`.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-FILAS-01 | Multi-filas por local | `tb_fila` com `endereco/descricao` + `criar_fila(endereco,...)` (`bd_manipulador.py:208-255`) + `listar_filas_visiveis` por criador |
| RF-FILAS-02 | Numeração configurável `prefixo+inicio→fim` com `fim=0` infinito | `_proxima_senha(atual,prefixo,inicio,fim)` (`bd_manipulador.py:440-459`) `prox>fim→inicio`, width 3/4, `fim=0` circular |
| RF-FILAS-03 | Fluxo sequencial por etapas | `tb_fila_etapa` `ordem` + `criar/listar/atualizar/reordenar` (`359-436`) + `avancar_chamada` (`504-542`) `Já está na última etapa` |
| RF-FILAS-04 | TV isolada `/tv/{id}` vs compartilhada `/tv?grupo=` | `tv_grupo` (`tb_fila`) + `mostrar_tv(fila_id/tv_grupo)` (`telas.py:191-370`) + `main.py:753-778` `?grupo=` + `ultima_chamada_tv` `IN` (`558-573`) |
| RF-FILAS-05 | Mídia ambiente áudio elevador / vídeo propaganda | `tb_midia` + `PASTA_MIDIA` `mod_filas/midia` → `/midia_filas/*` (`684-694`) + `listar_midias` + `rotacionar_midia` `40s` ociosa + pausada ao chamar |
| RF-FILAS-06 | Isolamento por dono vs `administrador_geral` vê tudo | `criado_por` + `listar_filas_visiveis(user,perfil,eh_admin_modulo)` (`157-175`) `WHERE criado_por=? OR '' OR NULL` |
| RF-FILAS-07 | Censura de títulos na TV | `listar_para_tv` filtrado por `conteudo_palavras_bloqueadas` (`mod_agregador_noticias`) — `titulo_bloqueado` `lower+NFD` |
| RF-FILAS-08 | Exclusão uma/todas (Geral preservada) | `excluir_fila` bloqueia `Geral` (`316-332`) + `excluir_todas_filas` com dialog (`335-356`) filtro `criado_por` quando não-admin |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-PERS-01 | Persistência por módulo com `banco_conexao` | `banco_conexao.conexao("filas")` (`get_connection` `bd_manipulador.py:24-34`) + `PRAGMA journal_mode=WAL` + `foreign_keys=ON` |
| RNF-PERS-02 | WAL + auditoria central | `audit_log` → `db_mod_auditoria.db` `tb_auditoria_filas` (`_audit` `37-39`) `criar_fila`/`gerar_senha`/`avancar` |
| RNF-SEG-01 | Validação prefixo / isolamento | `re.match ^[A-Za-z0-9]+$` (`216`), `inicio>=0`, `fim==0||fim>=inicio` + isolamento `criado_por` |
| RNF-SEG-02 | XSS (nh via censura) | Títulos do agregador/blog filtrados via `titulo_bloqueado` antes de `nh3`/`INSERT`; `listar_para_tv` censura `LIMIT*3` |
| RNF-PERF-01 | Poll TV 3s + rotação mídia 40s + notícias 7s/120s | `ui.timer 3.0 refresh_chamada` + `40.0 rotacionar_midia` (só ociosa) + `7.0 _mostrar_noticia` + `120.0 carregar_noticias` |
| RNF-PERF-02 | Limpeza 24h agregador | `limpar_antigas(24)` em `coletar_todas` (`mod_agregador_noticias`) + `reiniciar_banco` `DELETE` 06:00 |
| RNF-USAB-01 | Voz `pt-BR` bip 880Hz só novo id | `_js_beep_e_voz` `AudioContext` 880Hz 0.35s + `speechSynthesis` `pt-BR` `0.9` `cancel` + `estado["ultimo_id"]` guarda |
| RNF-USAB-02 | Links TV + ícone padrão intranet | `get_config icone_sistema/titulo_sistema` (`hub`/`INTRANET`) + link `tv_grupo ? /tv?grupo= : /tv/{id}` no criar e no card |
| RNF-COMP-01 | Compatibilidade SQLite ↔ PostgreSQL | `banco_conexao.conexao(chave)` roteia; DDL `CREATE TABLE IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS`, `INSERT OR IGNORE`→`ON CONFLICT`, `?`→`%s` |
| RNF-RESP-01 | Responsividade + `data-testid` | `w-full flex-wrap` `min-w` nos cards, `data-testid` em admin (censura, TV); TV `10vw`/`2.5vw` escalável |

## Pontos de atenção

- Multi-filas isoladas por `criado_por` — `listar_filas_visiveis` implementa; comum vê só suas + legadas.
- Numeração infinita `fim=0` circular (`_proxima_senha`).
- TV `tv_grupo` vazio=isolada `/tv/{id}`, preenchido=compartilhada `/tv?grupo=` agregada por `IN`.
- Bip+voz só no novo `id` (`estado["ultimo_id"]` + `speechSynthesis.cancel`).
- Mídia global (`tb_midia` ordem/ativo) — playlist ociosa 40s, pausada ao chamar.
- `/tv` pública — adicionar `ACL` se expor fora da rede.
- `Geral` nunca excluível; `Excluir todas` preserva Geral com filtro por criador.
- `tb_chamada.guiche` snapshot.

## Status

| Item | Situação |
|:---|:---:|
| Banco WAL `tb_fila` + `tb_fila_etapa` + `tb_chamada` + `tb_midia` + seed `Geral` + `Geral` 3 etapas | Implementado (multi-filas) |
| `criar_fila` endereço/prefixo/inicio/fim/tv_grupo + `listar_filas_visiveis` isolamento + `atualizar/excluir` + `excluir_todas_filas` | Implementado |
| `gerar_senha` + `_proxima_senha` infinito + `avancar_chamada` sequencial + `ultima_chamada_tv` grupo | Implementado |
| Painel `/filas` multi-filas + etapas + histórico isolado + `Excluir todas` | Implementado |
| TV `/tv` + `/tv/{id}` + `?grupo=` com ícone padrão intranet + 3s bip/voz só novo id + 40s mídia playlist + carrossel notícias filtrado | Implementado (`mostrar_tv` 191-370, `main.py` 753-778) |
| Admin `/admin/filas` 2 cards (Filas por local + Mídia TV global) | Implementado (218 linhas, `queue` + `queue_music`) |
| Mídia `/midia_filas` (`PASTA_MIDIA` `mod_filas/midia`, `/midia_filas/*`, upload sanitizado + uuid) | Implementado |
| LGPD + auditoria `tb_auditoria_filas` | Implementado |
| Integração TV Agregador (censura filtrada) | Implementado |

