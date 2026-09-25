# Technical Module — `mod_tecnico`

> Technical module: route `/tecnico` (key `tecnico`) · own database `db_mod_tecnico.db` (WAL) · physical folders `software/` (download) and `backup/` (owner-isolated `YYYYMMDD_HHMM_nomePc_ip_SS`) · multi-select zip · `webkitdirectory` 1-click backup with FS+DB atomicity · central LGPD audit.

---

# Módulo Técnico — `mod_tecnico`

> Módulo técnico: rota `/tecnico` (chave `tecnico`) · banco próprio `db_mod_tecnico.db` (WAL) · pastas físicas `software/` (download) e `backup/` (isolamento por dono `YYYYMMDD_HHMM_nomePc_ip_SS`) · zip multi-seleção · backup 1-clique `webkitdirectory` com **atomicidade FS+DB** · auditoria central LGPD.

## Propósito

Ferramentas de T.I. para manutenção e formatação de PCs da rede interna. O técnico acessa do **próprio PC a formatar** (browser local) com dois fluxos:

1. **Software** — lista recursiva de executáveis/portáteis já deixados pelo admin em `mod_tecnico/software/` (ex.: drivers, utilitários) com seleção por checkbox e download em **um único ZIP** recursivo — o que importa quando o técnico está copiando o pendrive para o PC que vai formatar e quer levar dezenas de executáveis de uma vez.
2. **Backup** — cria no servidor uma pasta nomeada automaticamente `YYYYMMDD_HHMM_nomePc_ip_SS` em `mod_tecnico/backup/` e envia os arquivos do usuário (Documentos/Imagens/Vídeos etc.) com estrutura de subpastas preservada — **1-clique via `webkitdirectory`** quando no PC alvo.

O backup precisa ser **autoidentificável sem metadado externo**: quem abrir a pasta depois, no PC novo, tem de saber de qual máquina e quando foi feito sem abrir banco de dados — daí o nome incorporate data, minuto, **segundos**, PC e IP.

Isolamento total por **dono** (owner): cada técnico vê/só baixa seu próprio backup; a autorização é por **tabela** (`tb_backup.owner` é a fonte da verdade, não o perfil) e **falha fechada** — se `perfil_global_de` não responder, o acesso é **negado**. LGPD via `remover_vinculos_usuario`/`renomear_usuario`.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py` (bootstrap central + `init_db()` no import).

| Tabela | Conteúdo |
|:---|:---|
| `tb_backup` | `id` PK, `pasta_nome` UNIQUE (`YYYYMMDD_HHMM_nomePc_ip_SS`), `owner` (login dono), `ip`, `hostname` (nomePc), `tamanho_total`, `status` (`criado`/`em_envio`), `data_criacao` |
| `tb_backup_arquivo` | `id` PK, `backup_id` FK CASCADE → `tb_backup`, `nome`, `caminho_relativo` (preserva `webkitdirectory`), `tamanho`, `hash_sha256` |
| `tb_config_tecnico` | chave-valor local — **fallback**; a fonte é o `tb_config` central (`tecnico_pasta_software`, `tecnico_pasta_backup`, `tecnico_max_zip_mb` default 1024, `tecnico_quota_gb` default 10 ⚠️ nunca lido) |
| `models/` (`Backup`, `BackupArquivo`) | dataclasses tipadas que espelham `tb_backup`/`tb_backup_arquivo` (mapeamento imperativo futuro; acesso real hoje via `bd_manipulador`) |

Helpers internos (`bd_manipulador.py`): `_log()` (logger `tecnico`), `_audit()` (→ `audit_log` central), `_hash_sha256(caminho)` (utilitário de arquivo — o envio atual usa `hashlib.sha256(conteudo)` inline), `_pasta_backup_path()` (blindagem `basename` + regex + `commonpath`), `obter_backup()` (uma linha por `pasta_nome`), `listar_backups()` ordena por `data_criacao ASC`. Docstrings bilíngues EN topo / PT-BR abaixo em todo o módulo.

⚠️ O `bd_criador.py` do módulo é **legado/morto** — não executar (o schema real está em `bd_manipulador.py`).

Pastas físicas (dentro do módulo, garantidas em runtime + `.gitkeep`):

| Pasta | Conteúdo | No `.gitignore`? |
|:---|:---|:---:|
| `mod_tecnico/software/` | executáveis/portáteis disponibilizados (download) — versionável, `.gitkeep` | não (conteúdo commitável sob critério do admin) |
| `mod_tecnico/backup/YYYYMMDD_HHMM_nomePc_ip_SS/` | pastas por PC/técnico, uma por dono (ex.: `20260925_1557_NOTE07_192_168_1_10_44`) | conteúdo runtime (não commitado — backups são **dados de usuário**) |

> **Estado real em disco (auditado 25/09/2026):** `software/` contém **apenas `.gitkeep`** — sem a pasta `instalador/` que a documentação anterior citava, então `listar_software_recursivo()` devolve `[]` e a tela mostra "Nenhum arquivo em software/." com botão **Atualizar**. `backup/` contém **`.gitkeep`**. Ambos são garantidos em runtime por `os.makedirs(exist_ok=True)` no `init_db()`.

Conexão via `mod_intranet/banco_conexao.conexao("tecnico")` (backend duplo SQLite/PostgreSQL, WAL + `foreign_keys=ON`). Auditoria via `audit_log` → banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_tecnico`.

## Funcionalidades

### Aba Software — download multi-seleção com zip recursivo

- **Listagem recursiva** (`listar_software` + `listar_software_recursivo` em `bd_manipulador.py`): `listar_software_recursivo()` faz `os.walk` de `software/` devolvendo **só folhas** (relativas, ignorando `.gitkeep`); `listar_software(relativo)` lista **um nível**, separando pastas (`eh_dir`) de arquivos e expondo `caminho_abs` + `tamanho`; a tela achata `pastas + arquivos` numa lista plana (`_painel_software` em `telas.py`).
- **Checkbox por relativo** (`tecnico-soft-{safe_id}`): cada linha tem `ui.checkbox` ligado a `selecionados[rel]`. Pasta marcada baixa **todo o conteúdo recursivo** dela.
- **Baixar selecionados** (`criar_zip_selecionados`): zip temporário em `tempfile` com `ZIP_DEFLATED`; pasta marcada → `os.walk`; arquivo → direto; **arco** = relativo a `software/` (preserva subpasta dentro do ZIP). **Blindagem dupla:** `rel` rejeitado se contém `..`, começa com `/` ou tem `\x00`, **e** `commonpath` revalidado contra `PASTA_SOFTWARE` — tanto no alvo quanto **dentro do walk, arquivo por arquivo** (cobre symlink apontando para fora). Limite `tecnico_max_zip_mb` (default 1024 MB, `get_config` central) verificado **incrementalmente** durante a escrita — reavaliar só no fim permitiria gravar dezenas de GB antes de estourar; no `except` o temp é **removido** antes de re-levantar. Audita `download_software`.
- **Fluxo UI** (`_painel_software` em `telas.py`): header + `ui.row` `w-full justify-center` + botão `Baixar selecionados` (`data-testid=tecnico-baixar`, `variante="primario"`, `chave_modulo="tecnico"`, `min-w-[220px]`) + `Atualizar` (`texto`). Sem arquivos → "Nenhum arquivo em software/." + botão Atualizar (estado **atual**, pois `software/` só tem `.gitkeep`).
- **Helpers**: `_fmt_bytes` (B/KB/MB/GB) e `_safe_id` (sanitiza relativo para `data-testid`, máx. 40 chars — **pode colidir** em caminhos longos distintos).

### Aba Backup — pasta nomeada `YYYYMMDD_HHMM_nomePc_ip_SS` + upload owner-isolated + `webkitdirectory`

- **Nome padrão** (`nome_pasta_backup`): `YYYYMMDD_HHMM` + **`_SS` (segundos)** + `pc` sanitizado + `ip` sanitizado — ex.: `20260925_1557_NOTE07_192_168_1_10_44`. O **sufixo de segundos** existe porque o formato antigo colidia quando o técnico criava duas pastas no mesmo minuto para o mesmo PC/IP (o caso real ao varrer a rede e achar dois problemas). Ele resolve a colisão **sem quebrar** o prefixo `YYYYMMDD_HHMM_`, que continua ordenável e continua casando com a regex de validação. Sanitização: `pc`/`ip` por `_sanitizar_nome` (`[^a-zA-Z0-9_-]`→`_`, colapsa `__`, trim, 40 chars), com o IP tratado à parte para **preservar o ponto** antes de trocar por `_`.
- **Criar pasta** (`criar_pasta_backup`): valida `owner` (obrigatório), `nomePc` ≥2, `ip` ≥3; checa colisão em **duas camadas** — `os.path.exists` no FS **e** `obter_backup` no banco — antes de `os.makedirs(exist_ok=False)`; falha física → `shutil.rmtree` de rollback; `UNIQUE` violado → mesma mensagem de colisão. **Nunca sobrescreve pasta alheia.** A mensagem de recusa é *"Pasta já existe: `<nome>` — aguarde alguns segundos e tente novamente (nome inclui segundos para evitar colisão)"*.
- **Owner-isolated** — a regra que sustenta o módulo (o backup contém dados pessoais de uma pessoa):

  | Operação | Regra |
  |:---|:---|
  | Listar | `listar_backups(owner, apenas_owner=True)` → `WHERE owner=?`; a tela do técnico **sempre** filtra por dono |
  | Enviar | `row.owner != owner` → só passa se `perfil_global_de(owner) == "administrador_geral"`; senão `"Apenas o dono do backup pode enviar arquivos"` |
  | Baixar (zip) | mesma checagem, via `raise PermissionError` — e o `except` do handler **re-levanta** `PermissionError` explicitamente, para o tratamento genérico não engolir permissão como falha técnica |
  | Admin | card "Backups recentes (todos os usuários)" usa `listar_backups(apenas_owner=False)` — **exceção declarada**, restrita a `/admin/tecnico` |

  A autorização é por **tabela**, não por perfil (`tb_backup.owner` é a fonte da verdade), e é **fail-closed**: se `perfil_global_de` falhar, o padrão é **negar**.
- **Upload 1-clique** (`salvar_arquivos_backup`): valida `pasta_nome`; sanitiza o nome vindo do `webkitdirectory` (`replace("\\","/")` → split → remove `..`/vazios/`\x00` → cada segmento `[^A-Za-z0-9._-]`→`_` e `strip("._")` → `os.makedirs(dirname)` + `open(dest,"wb")`), gravando `hash_sha256(conteúdo)` por arquivo; soma `tamanho_total` e marca `status='em_envio'`; audita `enviar_backup`.
- **Atomicidade FS + DB (24/09/2026)** — o backup é a operação feita **uma vez, antes de uma ação irreversível**, então estado intermediário quebrado é o pior resultado possível (arquivo no disco sem registro, ou registro sem arquivo e perda na restauração). Daí as duas fases:

  1. **Fase 1 (FS, fora da transação)** — grava os arquivos e memoiza cada caminho em `escritos` (o banco não transaciona disco; escrever "dentro" da transação deixaria os arquivos de qualquer forma se o commit falhasse).
  2. **Fase 2 (DB, transação curta com retry)** — `INSERT tb_backup_arquivo` por arquivo + `UPDATE tb_backup` num único `commit`, com até **3 tentativas** em `database is locked` (`rollback` + `sleep(0.05 × tentativa)`) — o `rollback` antes do retry é obrigatório, senão a tentativa 2 falha por constraint pendente e não por lock.
  3. **Compensação** — se o DB falhar, `os.remove()` de **todos** os arquivos de `escritos` (desta chamada), log da contagem removida e retorno de falha. O recorte por chamada garante que um reenvio do usuário **não apaga** os arquivos válidos da tentativa anterior.
- **Fluxo UI** (`_painel_backup` em `telas.py`): card "Criar pasta no servidor" com `inp_pc` (`tecnico-backup-nomepc`) + `inp_ip` (`tecnico-backup-ip`) + `lbl_prev` "Prévia: …/" (atualizada em `on_value_change`); botão `Criar pasta no servidor` (`tecnico-criar-pasta`, `create_new_folder`, `primario`). Lista `listar_backups(owner, apenas_owner=True)`; sem backups → "Nenhum backup seu ainda."; com backups → `select` destino (`tecnico-backup-select`) + card azul "Backup 1-clique (quando no PC a formatar)". `ui.upload(multiple=True, auto_upload=True, on_multi_upload=ao_upload)` (`tecnico-upload`, `accept=*/*`) + JS `setTimeout` que injeta `webkitdirectory`/`directory` no `input[type=file]`, **ancorado em `[data-testid=tecnico-upload]`** para não pegar o input de outro upload. O `setTimeout` existe porque o `<input type=file>` **ainda não existe** quando o `ui.upload` retorna (só é materializado no tick seguinte). Handler `async ao_upload` faz `await f.read()` e chama `salvar_arquivos_backup`. Cards por backup com `Baixar pasta (zip)` (`tecnico-baixar-{safe_id}`, `folder_zip`, `secundario`) + `visibility` (`_dlg_listar` — até 200 arquivos).
- **Fallback do `webkitdirectory`:** o atributo não é padrão (Chrome/Edge/Firefox modernos aceitam; outros ignoram em silêncio) e a injeção é **fail-soft** (`if (inp)` sem `else`, sem exceção) — onde não funciona, o upload **continua funcionando** com Ctrl+A múltiplo, e o rótulo da tela explica as duas opções. A **perda** nesse caso é a árvore: sem o atributo, `f.name` é um nome simples e o arquivo cai na raiz da pasta (backup achatado).
- **LGPD** (`remover_vinculos_usuario`): remove pastas físicas (`shutil.rmtree`) + `tb_backup_arquivo` **e** `tb_backup WHERE owner` — **filhos antes dos pais**, porque o proxy Postgres remove a cláusula `REFERENCES` e não existe cascata implícita lá. `renomear_usuario` propaga `UPDATE tb_backup SET owner=?`.
- **Borda temática**: `cabecalho("Técnico", ..., chave_modulo="tecnico")` — borda = `tema["cor_botao"]` (cor geral do módulo via `PADROES_TEMA` → `#000000` por padrão, editável no cupê Aparência); `ui.colors(primary=tema["cor_botao"])`.
- **Configuração dual**: `_obter_config_tecnico` lê o `tb_config` **central** primeiro (é onde o painel grava) e só cai em `tb_config_tecnico` (legado) depois — ler o local primeiro faria os dois divergirem silenciosamente. Escrita sempre no central (`set_config`).

### Administração (`/admin/tecnico`)

`telas_administracao.py` — `mostrar_administracao(usuario_logado)`: `bloco_aparencia` (cupê "Aparência" `tecnico_*` + `com_texto_header=True`) + card "Configurações do Técnico" (`card_admin`, `grade=False`, `build`): `PASTA_SOFTWARE`/`PASTA_BACKUP` (disabled, `tooltip` fixo), `tecnico_max_zip_mb` (`ui.number` 10–10000, `get_config`/`set_config` central) com rodapé `rodape_salvar_restaurar` ("Aplicar" grava + `notificar` + `reload` 1s; "Restaurar" grava 1024 + reload) + card "Backups recentes (todos os usuários)" (lista até 30, `listar_backups(apenas_owner=False)`) + `painel_backup(usuario, "tecnico")` (intervalo de backup do banco do módulo).

## Permissões

| Ação | `comum` com `tecnico` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/tecnico` (Software + Backup) | ✓ | ✓ | ✗ (tela "Acesso restrito") |
| Baixar `software/` | ✓ | ✓ | — |
| Criar pasta `YYYYMMDD_HHMM_*` | ✓ (como `owner`) | ✓ | — |
| Enviar arquivos para pasta própria | ✓ (só dono) | ✓ (dono ou `administrador_geral`) | ✗ (outro dono → "Apenas o dono") |
| Baixar pasta backup como zip | ✓ (só dono) | ✓ (dono ou `administrador_geral`) | ✗ |
| Ver `/admin/tecnico` | ✗ | ✓ | ✗ |

Gate: `_pode_acessar(user, perfil)` (em `telas.py`) — `administrador_geral` sempre; senão `autenticacao.validar_acesso_modulo(user, "tecnico")`.

## Rota e integrações

- Rota: `/tecnico` (chave `tecnico`, ícone `build`) — `main.py` (`pagina_restrita("Técnico", chave_modulo="tecnico")` + `REGISTRO_MODULOS["tecnico"] = page_tecnico`); slug customizável em `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Pastas: `mod_tecnico/software/` (leitura — **estado atual: apenas `.gitkeep`**) e `mod_tecnico/backup/` (escrita owner-isolated — `.gitkeep`) — regras via `PASTA_SOFTWARE`/`PASTA_BACKUP` (em `bd_manipulador.py`).
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_tecnico` (`criar_backup`, `enviar_backup`, `download_backup`, `download_software`, `remover_vinculos_tecnico`).
- Backup do banco: job `backup:tecnico` (intervalo `backup_horas:tecnico` default 12h, `mod_intranet/rotinas.py` `MAPA_BACKUPS` inclui `tecnico: db_mod_tecnico.db`).

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
- **`tecnico_quota_gb` é chave morta** — semeada com valor `"10"` e **nunca lida**. Não há cota de disco por usuário no fluxo de backup: o único teto é o espaço do servidor. Se a intenção era limitar por técnico, falta implementar (referência de padrão: `mod_edit_pdf.verificar_quota`).
- `webkitdirectory` é atributo não-padrão (Chrome/Edge/Firefox modernos) — fallback é seleção múltipla com Ctrl+A (backup **achatado**, sem subpastas); o JS do upload é fail-soft e ancorado em `[data-testid=tecnico-upload]`.
- `nome_pasta_backup` sanitiza `nomePc`/`ip` (`[^a-zA-Z0-9_-]` → `_`, max 40) para evitar path traversal; `_pasta_backup_path` revalida com regex `^[0-9]{8}_[0-9]{4}(_[0-9]{2})?_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+(_[0-9]{2})?$` (aceita o formato legado sem segundos **e** o novo com `_SS`). Nome fora do padrão não é rejeitado — é truncado em 80 chars, e o `commonpath` ainda garante contenção em `backup/`.
- `criar_zip_selecionados` e `criar_zip_backup` usam `tempfile.NamedTemporaryFile(delete=False)` + `ZIP_DEFLATED` e devolvem o `tmp.name` para `ui.download`; **removem o temp no `except`** antes de re-levantar (cleanup é do SO no caminho feliz).
- `_safe_id` corta em 40 chars ao montar `data-testid` — **pode colidir** entre caminhos longos distintos; o Playwright deve preferir o checkbox pelo texto visível em caso de dúvida.
- ✅ **`ui.notify` cru: zero** neste módulo (0 ocorrências em `telas.py` e `telas_administracao.py`; 12 chamadas a `notificar(`) — aderente ao AGENTS.md §5.1, ao contrário de `mod_edit_pdf` (parcial) e `mod_renomear_empenho` (117 + 23).
