# Técnico — `mod_tecnico`

> Technical module: route `/tecnico` (key `tecnico`) · own database `db_mod_tecnico.db` · physical folders `software/` + `backup/YYYYMMDD_HHMM_nomePc_ip` · owner-isolated, webkitdirectory, SHA-256.

---

# Técnico — `mod_tecnico`

> Módulo técnico: rota `/tecnico` (chave `tecnico`) · banco próprio `db_mod_tecnico.db` · pastas físicas `software/` + `backup/YYYYMMDD_HHMM_nomePc_ip` · isolamento por dono, webkitdirectory, SHA-256.

## Propósito

Módulo de apoio à T.I. para formatação de PCs: disponibiliza executáveis em `software/` e recebe backups do PC a formatar em `backup/YYYYMMDD_HHMM_nomePc_ip` com isolamento por dono. Desenhado para uso **no próprio PC a formatar** (browser local) com upload 1-clique via `webkitdirectory`.

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `mod_intranet/banco_conexao.conexao("tecnico")`. Criador vigente: `init_db()` em `bd_manipulador.py:71-116`, executado no import e pelo bootstrap central (`mod_intranet_inicializacao_bd.py`).

**`tb_backup`** (pastas nomeadas):

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `pasta_nome` | UNIQUE — `YYYYMMDD_HHMM_nomePc_ip` (ex.: `20260918_1430_NOTE07_192_168_1_10`), sanitizado `[^a-zA-Z0-9_-]`→`_` |
| `owner` | login dono (LGPD: filtro `apenas_owner=True`) |
| `ip`, `hostname` | IP e nomePc informados na criação |
| `tamanho_total` | soma dos arquivos enviados |
| `status` | `criado` → `em_envio` |
| `data_criacao` | `CURRENT_TIMESTAMP` |

**`tb_backup_arquivo`** (arquivos dentro do backup):

| Coluna | Observação |
|:---|:---|
| `id` | PK |
| `backup_id` | FK CASCADE → `tb_backup.id` |
| `nome` | último segmento (ex.: `foto.jpg`) |
| `caminho_relativo` | relativo preservando `webkitdirectory` (ex.: `Documents/foto.jpg`) |
| `tamanho` | bytes (`len(conteúdo)`) |
| `hash_sha256` | `sha256(conteúdo)` para auditoria |

**`tb_config_tecnico`** (local do módulo): `tecnico_pasta_software`, `tecnico_pasta_backup`, `tecnico_max_zip_mb` (1024), `tecnico_quota_gb` (10) — seeds `INSERT OR IGNORE`.

⚠️ `bd_criador.py` é **código legado/morto**: não é importado; não executar.

## Fluxo da tela

- Gate `_pode_acessar` (`telas.py:24-30`): `administrador_geral` ou `validar_acesso_modulo(user,"tecnico")`; sem acesso → "Acesso restrito".
- `mostrar_tela(nome, perfil)` (`telas.py:33-65`): `ler_tema("tecnico")` + `ui.colors(primary)` + `cabecalho(chave_modulo="tecnico")` + `ui.tabs` `Software` (`apps`) | `Backup` (`backup`) → `_painel_software` / `_painel_backup`.
- **Software** (`telas.py:69-151`): lista `software/` recursiva com checkbox + `Baixar selecionados` → `criar_zip_selecionados` (zip recursivo, limite `tecnico_max_zip_mb`).
- **Backup** (`telas.py:172-310`): cria pasta `YYYYMMDD_HHMM_*` + `ui.upload(multiple, auto_upload, on_multi_upload)` com JS `webkitdirectory` + lista owner-isolated + `Baixar pasta (zip)` + `_dlg_listar` (dialogo com até 200 arquivos).
- Responsividade: `w-full p-6`, `flex-wrap`, `min-w` nos inputs, `data-testid` para QA.

## Regras de negócio relevantes

- **Nome da pasta** (`nome_pasta_backup`): `YYYYMMDD_HHMM` do servidor + `pc`/`ip` sanitizados (`_sanitizar_nome`: `[^a-zA-Z0-9_-]`→`_`, `__`→`_`, trim, 40 chars); `ip` com `.`→`_`.
- **Criação** (`criar_pasta_backup`): valida `owner`, `pc≥2`, `ip≥3`; `os.makedirs(exist_ok=False)` + `INSERT tb_backup`; colisão → erro; falha física → `shutil.rmtree` rollback.
- **Envio** (`salvar_arquivos_backup`): owner-isolation (só dono ou `administrador_geral` via `perfil_global_de`); sanitiza `webkitdirectory` preservando subpastas; `os.makedirs(dirname)` + `open(dest,"wb")` + `INSERT tb_backup_arquivo` por arquivo + `UPDATE tb_backup SET tamanho_total+status`; audita `enviar_backup`.
- **Download software** (`criar_zip_selecionados`): zip recursivo de relativos selecionados; `..` ignorado; limite por `tecnico_max_zip_mb` (lido de `tb_config` central); audita `download_software`.
- **Download backup** (`criar_zip_backup`): owner-isolation idem; `os.walk` + `zipfile.ZIP_DEFLATED`; audita `download_backup`.
- **Sanitização/path traversal**: `_sanitizar_nome`, `_pasta_backup_path` com regex `^[0-9]{8}_[0-9]{4}_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+$`, `caminho_relativo` com `..` removido.
- **LGPD**: `remover_vinculos_usuario` apaga pastas físicas + `DELETE tb_backup WHERE owner` (cascade); `renomear_usuario` propaga `owner`.

## Integrações com o núcleo

Importa `autenticacao.validar_acesso_modulo`/`perfil_global_de`, `banco_conexao.conexao`, `tema_modulo.ler_tema`/`notificar`, `ui_comum.botao`. Grava via `audit_log` → `tb_auditoria_tecnico`. Backup do banco via `rotinas.painel_backup`/`MAPA_BACKUPS` (`tecnico: db_mod_tecnico.db`). Pastas físicas `PASTA_SOFTWARE`/`PASTA_BACKUP` garantidas em `init_db()`.

## Pontos de atenção

- `mod_tecnico/backup/*` é runtime (não commitado além do `.gitkeep`); `mod_tecnico/software/*` é conteúdo opcional versionável.
- `webkitdirectory` é não-padrão — JS fail-soft; fallback Ctrl+A múltiplo.
- Zips temporários via `tempfile.NamedTemporaryFile(delete=False)` — limpeza SO; `cleanup_pdf` não afeta este módulo.
- `tb_backup.pasta_nome` UNIQUE impede colisão mesmo com clocks iguais (segunda tentativa no mesmo minuto falha com "Pasta já existe").

## Status

| Item | Situação |
|:---|:---|
| Banco WAL + CRUD owner-isolated | Implementado |
| Pastas físicas `software/` + `backup/` | Implementado (`.gitkeep` + `makedirs`) |
| Software multi-seleção + zip | Implementado (`criar_zip_selecionados`) |
| Backup `YYYYMMDD_HHMM_nomePc_ip` + webkitdirectory | Implementado (`criar_pasta_backup` + `salvar_arquivos_backup`) |
| LGPD (`remover/renomear`) + auditoria | Implementado |
| Painel `/admin/tecnico` | Implementado (`bloco_aparencia` + `tecnico_max_zip_mb` + `painel_backup`) |
