# Technical Module — `mod_tecnico`

> Technical module: route `/tecnico` (key `tecnico`) · own database `db_mod_tecnico.db` (WAL) · physical folders `software/` (download) and `backup/` (owner-isolated `YYYYMMDD_HHMM_nomePc_ip`) · multi-select zip · `webkitdirectory` 1-click backup · central LGPD audit.

---

# Módulo Técnico — `mod_tecnico`

> Módulo técnico: rota `/tecnico` (chave `tecnico`) · banco próprio `db_mod_tecnico.db` (WAL) · pastas físicas `software/` (download) e `backup/` (isolamento por dono `YYYYMMDD_HHMM_nomePc_ip`) · zip multi-seleção · backup 1-clique `webkitdirectory` · auditoria central LGPD.

## Propósito

Ferramentas de T.I. para manutenção e formatação de PCs da rede interna. O técnico acessa do **próprio PC a formatar** (browser local) com dois fluxos:

1. **Software** — lista recursiva de executáveis/portáteis já deixados pelo admin em `mod_tecnico/software/` (ex.: drivers, utilitários) com seleção por checkbox e download em zip recursivo.
2. **Backup** — cria no servidor uma pasta nomeada automaticamente `YYYYMMDD_HHMM_nomePc_ip` em `mod_tecnico/backup/` e envia os arquivos do usuário (Documentos/Imagens/Vídeos etc.) com estrutura de subpastas preservada — **1-clique via `webkitdirectory`** quando no PC alvo.

Isolamento total por **dono** (owner): cada técnico vê/só baixa seu próprio backup; LGPD via `remover_vinculos_usuario`/`renomear_usuario`.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:71-116` (bootstrap central + `init_db()` no import).

| Tabela | Conteúdo |
|:---|:---|
| `tb_backup` | `id` PK, `pasta_nome` UNIQUE (`YYYYMMDD_HHMM_nomePc_ip`), `owner` (login dono), `ip`, `hostname` (nomePc), `tamanho_total`, `status` (`criado`/`em_envio`), `data_criacao` |
| `tb_backup_arquivo` | `id` PK, `backup_id` FK CASCADE → `tb_backup`, `nome`, `caminho_relativo` (preserva `webkitdirectory`), `tamanho`, `hash_sha256` |
| `tb_config_tecnico` | chave-valor local (`tecnico_pasta_software`, `tecnico_pasta_backup`, `tecnico_max_zip_mb` default 1024, `tecnico_quota_gb` default 10) |

⚠️ O `bd_criador.py` do módulo é **legado/morto** — não executar (o schema real está em `bd_manipulador.py`).

Pastas físicas (dentro do módulo, garantidas em runtime + `.gitkeep`):

| Pasta | Conteúdo | No `.gitignore`? |
|:---|:---|:---:|
| `mod_tecnico/software/` | executáveis/portáteis disponibilizados (download) — versionável, `.gitkeep` | não (conteúdo commitável sob critério do admin) |
| `mod_tecnico/backup/YYYYMMDD_HHMM_nomePc_ip/` | pastas por PC/técnico, uma por dono (ex.: `20260918_1430_NOTE07_192_168_1_10`) | conteúdo runtime (não commitado — backups são dados) |

Conexão via `mod_intranet/banco_conexao.conexao("tecnico")` (backend duplo SQLite/PostgreSQL, WAL + `foreign_keys=ON`). Auditoria via `audit_log` → banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_tecnico`.

## Funcionalidades

### Aba Software — download multi-seleção com zip recursivo

- **Listagem recursiva** (`listar_software` + `listar_software_recursivo`): varre `software/` ignorando `.gitkeep`; combina pastas (exibidas como `folder`) + arquivos folhas (`description`) numa lista plana ordenada com dedup — `todos_itens = pastas + arquivos` (`telas.py:90-108`).
- **Checkbox por relativo** (`tecnico-soft-{safe_id}`): cada linha tem `ui.checkbox` com `data-testid=tecnico-soft-*` ligado a `selecionados[rel]`. Pasta marcada baixa **todo o conteúdo recursivo** dela.
- **Baixar selecionados** (`criar_zip_selecionados` — `bd_manipulador.py:165-206`): cria zip temporário em `tempfile` com `ZIP_DEFLATED`; para diretório marcado walks recursivo; para arquivo inclui direto; arco = relativo a `software/` (preserva subpasta); segurança `..` ignorado; limite `tecnico_max_zip_mb` (default 1024 MB, lido de `tb_config` central via `get_config`; excedeu → `ValueError`); audita `download_software` com `owner` + `total bytes` + zip path.
- **Fluxo UI** (`_painel_software` — `telas.py:69-151`): header + `ui.row` `w-full justify-center` + botão `Baixar selecionados` (`data-testid=tecnico-baixar`, `variante="primario"`, `chave_modulo="tecnico"`, `min-w-[220px]`) + `Atualizar` (`texto`). Sem arquivos → "Nenhum arquivo em software/." + botão Atualizar.
- **Helpers**: `_fmt_bytes` (B/KB/MB/GB) e `_safe_id` (sanitiza relativo para `data-testid`).

### Aba Backup — pasta nomeada `YYYYMMDD_HHMM_nomePc_ip` + upload owner-isolated + `webkitdirectory`

- **Nome padrão** (`nome_pasta_backup` — `bd_manipulador.py:211-219`): `datetime.now().strftime("%Y%m%d_%H%M") + "_" + pc_sanitizado + "_" + ip_sanitizado` — `pc` e `ip` sanitizados por `_sanitizar_nome` (`[^a-zA-Z0-9_-]` → `_`, colapsa `__`, trim `_`, max 40); `ip` tem ponto→`_`. Ex.: `20260918_1430_NOTE07_192_168_1_10`.
- **Criar pasta** (`criar_pasta_backup` — `bd_manipulador.py:222-261`): valida `owner` (exige login), `nomePc` ≥2, `ip` ≥3; gera `pasta_nome`, checa colisão `os.path.exists`, `os.makedirs(..., exist_ok=False)`, insere `tb_backup(owner,ip,hostname)`, audita `criar_backup`, log `info`. Falha → rollback físico (`shutil.rmtree`).
- **Upload 1-clique** (`salvar_arquivos_backup` — `bd_manipulador.py:298-347`): valida `pasta_nome` existe; **owner-isolation**: `row.owner != owner` → checa `perfil_global_de(owner) == "administrador_geral"` senão `PermissionError`; sanitiza `nome` com `webkitdirectory` preservando subpastas (`nome.replace("\\","/").split("/")`, remove `..` e vazios, `nome_rel="/".join(partes)`, `dest=os.path.join(caminho,*partes)`, `os.makedirs(dirname, exist_ok=True)`); grava bytes + insere `tb_backup_arquivo` por arquivo com `hash_sha256(conteúdo)`; soma `tamanho_total` + `status='em_envio'`; audita `enviar_backup`.
- **Fluxo UI** (`_painel_backup` — `telas.py:172-310`): card "Criar pasta no servidor" com `inp_pc` (`data-testid=tecnico-backup-nomepc`) + `inp_ip` (`data-testid=tecnico-backup-ip`) + `lbl_prev` "Prévia: …/" (atualizada em `on_value_change`); botão `Criar pasta no servidor` (`data-testid=tecnico-criar-pasta`, `create_new_folder`, `primario`). Lista `listar_backups(owner, apenas_owner=True)` filtrada por dono (LGPD) — sem backups → "Nenhum backup seu ainda."; com backups → `select` destino (`data-testid=tecnico-backup-select`, opções `pasta — data bytes`) + card azul "Backup 1-clique (quando no PC a formatar)" explicando selecionar a pasta do usuário (ex.: `C:\Users\Joao\Documents`) no PC alvo — navegador envia estrutura preservada; fallback Ctrl+A. `ui.upload(multiple=True, auto_upload=True, on_multi_upload=ao_upload)` (`data-testid=tecnico-upload`, `accept=*/*`) + JS `setTimeout` que injeta `webkitdirectory`/`directory` no `input[type=file]` (fail-soft). Handler `async ao_upload` lê `await f.read()` e `f.name` (relativo com `webkitdirectory`), chama `salvar_arquivos_backup`. Lista de cards por backup com `Baixar pasta (zip)` (`data-testid=tecnico-baixar-{safe_id}`, `folder_zip`, `secundario`) via `criar_zip_backup` (`bd_manipulador.py:350-372`, owner-isolation idem, walks e zipa conteúdo) + `visibility` (`_dlg_listar`) com `dialogo_card` listando até 200 arquivos.
- **LGPD** (`remover_vinculos_usuario` — `bd_manipulador.py:375-396`): remove pastas físicas (`shutil.rmtree`) + `DELETE FROM tb_backup WHERE owner=?` (cascade apaga `tb_backup_arquivo`); audita `remover_vinculos_tecnico`. `renomear_usuario` propaga `UPDATE tb_backup SET owner=?`.
- **Borda temática**: `cabecalho("Técnico", ..., chave_modulo="tecnico")` — borda = `tema["cor_botao"]` (cor geral do módulo via `PADROES_TEMA` → `#000000` por padrão, editável no cupê Aparência); `ui.colors(primary=tema["cor_botao"])`.

### Administração (`/admin/tecnico`)

`telas_administracao.py:13-71` — `bloco_aparencia` (cupê "Aparência" `tecnico_*` + `com_texto_header=True`) + card "Configurações do Técnico" (`card_admin`, `grade=False`, `build`): `PASTA_SOFTWARE`/`PASTA_BACKUP` (disabled, `tooltip` fixo), `tecnico_max_zip_mb` (`ui.number` 10–10000, `get_config`/`set_config` central) com rodapé `rodape_salvar_restaurar` ("Aplicar" grava + `notificar` + `reload` 1s; "Restaurar" grava 1024 + reload) + card "Backups recentes (todos os usuários)" (lista até 30, `listar_backups(apenas_owner=False)`) + `painel_backup(usuario, "tecnico")` (intervalo de backup do banco do módulo).

- **Versionamento**: `versao_modulo:tecnico` exibido no rodapé de `/tecnico`.

## Permissões

| Ação | `comum` com `tecnico` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/tecnico` (Software + Backup) | ✓ | ✓ | ✗ (tela "Acesso restrito") |
| Baixar `software/` | ✓ | ✓ | — |
| Criar pasta `YYYYMMDD_HHMM_*` | ✓ (como `owner`) | ✓ | — |
| Enviar arquivos para pasta própria | ✓ (só dono) | ✓ (dono ou `administrador_geral`) | ✗ (outro dono → "Apenas o dono") |
| Baixar pasta backup como zip | ✓ (só dono) | ✓ (dono ou `administrador_geral`) | ✗ |
| Ver `/admin/tecnico` | ✗ | ✓ | ✗ |

Gate: `_pode_acessar(user, perfil)` (`telas.py:24-30`) — `administrador_geral` sempre; senão `autenticacao.validar_acesso_modulo(user, "tecnico")`.

## Rota e integrações

- Rota: `/tecnico` (chave `tecnico`, ícone `build`) — `main.py:717-728` (`pagina_restrita("Técnico", chave_modulo="tecnico")` + `REGISTRO_MODULOS["tecnico"] = page_tecnico`); slug customizável em `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Pastas: `mod_tecnico/software/` (leitura) e `mod_tecnico/backup/` (escrita owner-isolated) — regras via `PASTA_SOFTWARE`/`PASTA_BACKUP` (`bd_manipulador.py:24-25`).
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_tecnico` (`criar_backup`, `enviar_backup`, `download_backup`, `download_software`, `remover_vinculos_tecnico`).
- Backup do banco: job `backup:tecnico` (intervalo `backup_horas:tecnico` default 12h, `mod_intranet/rotinas.py:MAPA_BACKUPS` inclui `tecnico: db_mod_tecnico.db`).

## Testes

```bash
# Smoke do módulo (import + init_db + pastas + CRUD mínimo)
.venv/bin/python -c "from mod_tecnico.bd_manipulador import init_db, listar_software, nome_pasta_backup; init_db(); print(listar_software()[:2]); print(nome_pasta_backup('NOTE07','192.168.1.10'))"
# Playwright (quando coberto)
.venv/bin/pytest assets/test/teste_tecnico.py -k tecnico
```

Ver [Análise do Módulo](../analise_mod_tecnico.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- `mod_tecnico/backup/` é **dados de usuário** (não versionável além do `.gitkeep`); backups são removidos na LGPD (`remover_vinculos_usuario`). Nunca commitar `db_mod_tecnico.db` nem conteúdo de backup.
- `webkitdirectory` é atributo não-padrão (Chrome/Edge/Firefox modernos) — fallback é seleção múltipla com Ctrl+A; o JS do upload é fail-soft.
- `nome_pasta_backup` sanitiza `nomePc`/`ip` (`[^a-zA-Z0-9_-]` → `_`, max 40) para evitar path traversal; `_pasta_backup_path` revalida com regex `^[0-9]{8}_[0-9]{4}_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+$`.
- `criar_zip_selecionados` e `criar_zip_backup` usam `tempfile.NamedTemporaryFile(delete=False)` + `ZIP_DEFLATED` e devolvem o `tmp.name` para `ui.download`; limpeza do temp é do SO (ver `cleanup_pdf`).
