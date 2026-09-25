# Técnico — `mod_tecnico`

> Technical module: route `/tecnico` (key `tecnico`) · own database `db_mod_tecnico.db` · physical folders `software/` + `backup/YYYYMMDD_HHMM_nomePc_ip_SS` · owner-isolated, webkitdirectory, SHA-256, FS+DB atomicity.

---

# Técnico — `mod_tecnico`

> Módulo técnico: rota `/tecnico` (chave `tecnico`) · banco próprio `db_mod_tecnico.db` · pastas físicas `software/` + `backup/YYYYMMDD_HHMM_nomePc_ip_SS` · isolamento por dono, webkitdirectory, SHA-256, atomicidade FS+DB.

## Propósito

Módulo de apoio à T.I. para formatação de PCs: disponibiliza executáveis em `software/` e recebe backups do PC a formatar em `backup/YYYYMMDD_HHMM_nomePc_ip_SS` com isolamento por dono. Desenhado para uso **no próprio PC a formatar** (browser local) com upload 1-clique via `webkitdirectory`.

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `mod_intranet/banco_conexao.conexao("tecnico")`. Criador vigente: `init_db()` em `bd_manipulador.py`, executado no import e pelo bootstrap central (`mod_intranet_inicializacao_bd.py`).

**`tb_backup`** (pastas nomeadas):

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `pasta_nome` | UNIQUE — `YYYYMMDD_HHMM_nomePc_ip_SS` (ex.: `20260925_1557_NOTE07_192_168_1_10_44`), sanitizado `[^a-zA-Z0-9_-]`→`_`. O sufixo de **segundos** (`%S`) elimina a colisão de duas pastas criadas no mesmo minuto sem quebrar o prefixo `YYYYMMDD_HHMM_` |
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

**`models/__init__.py`** (dataclasses tipadas, padrão imperativo): `Backup` (`id`, `pasta_nome`, `owner`, `ip`, `hostname`, `tamanho_total`, `status`, `data_criacao`) e `BackupArquivo` (`id`, `backup_id`, `nome`, `caminho_relativo`, `tamanho`, `hash_sha256`) — espelham `tb_backup`/`tb_backup_arquivo` para uso tipado futuro (hoje o acesso real é via `bd_manipulador` + `banco_conexao`).

Helpers internos: `_log()` (logger escopado `tecnico`), `_audit(ator, acao, alvo, detalhe)` (encaminha ao `audit_log` central → `tb_auditoria_tecnico`), `_hash_sha256(caminho)` (utilitário de arquivo; o envio atual calcula `hashlib.sha256(conteudo)` inline em `salvar_arquivos_backup`), `_pasta_backup_path(pasta_nome)` (canoniza com `basename` + regex + `commonpath`, nunca escapa de `PASTA_BACKUP`), `obter_backup(pasta_nome)` (busca uma linha de `tb_backup`), `listar_backups` ordena por `data_criacao ASC`.

⚠️ `bd_criador.py` é **código legado/morto**: não é importado; não executar.

## Fluxo da tela

- Gate `_pode_acessar` (`telas.py`): `administrador_geral` ou `validar_acesso_modulo(user,"tecnico")`; sem acesso → "Acesso restrito".
- `mostrar_tela(nome, perfil)` (`telas.py`): `ler_tema("tecnico")` + `ui.colors(primary)` + `cabecalho(chave_modulo="tecnico")` + `ui.tabs` `Software` (`apps`) | `Backup` (`backup`) → `_painel_software` / `_painel_backup`.
- **Software** (`_painel_software` em `telas.py`): lista `software/` recursiva com checkbox + `Baixar selecionados` → `criar_zip_selecionados` (zip recursivo, limite `tecnico_max_zip_mb`). Helpers `_fmt_bytes` (B/KB/MB/GB/TB) e `_safe_id` (sanitiza relativo para `data-testid`, máx. 40).
- **Backup** (`_painel_backup` em `telas.py`): cria pasta `YYYYMMDD_HHMM_*_*_*` + `ui.upload(multiple, auto_upload, on_multi_upload)` com JS `webkitdirectory` + lista owner-isolated + `Baixar pasta (zip)` + `_dlg_listar(pasta_nome, user)` (diálogo com até 200 arquivos).
- **Admin** (`mostrar_administracao` em `telas_administracao.py`, rota `/admin/tecnico`): `bloco_aparencia` + card "Configurações do Técnico" (`tecnico_max_zip_mb` via `get_config`/`set_config` + `rodape_salvar_restaurar`) + card "Backups recentes (todos os usuários)" (até 30, `listar_backups(apenas_owner=False)`) + `painel_backup(usuario, "tecnico")`.
- Responsividade: `w-full p-6`, `flex-wrap`, `min-w` nos inputs, `data-testid` para QA.

## Regras de negócio relevantes

- **Nome da pasta** (`nome_pasta_backup`): `YYYYMMDD_HHMM` + `_SS` (segundos) do servidor + `pc`/`ip` sanitizados (`_sanitizar_nome`: `[^a-zA-Z0-9_-]`→`_`, `__`→`_`, trim, 40 chars); `ip` com `.`→`_`. Ex.: `20260925_1557_NOTE07_192_168_1_10_44`.
- **Criação** (`criar_pasta_backup`): valida `owner`, `pc≥2`, `ip≥3`; checa colisão **no FS** (`os.path.exists`) **e no banco** (`obter_backup`) antes de `os.makedirs(exist_ok=False)`; falha física → `shutil.rmtree` de rollback; falha de `UNIQUE` → mesma mensagem de colisão.
- **Envio** (`salvar_arquivos_backup`): owner-isolation (só dono ou `administrador_geral` via `perfil_global_de`, fail-**closed**); sanitiza `webkitdirectory` preservando subpastas; fase FS grava + memoiza `escritos`; fase DB em transação curta com 3× retry em `database is locked`; **compensa o FS removendo os arquivos desta chamada** se o DB falhar; audita `enviar_backup`.
- **Download software** (`criar_zip_selecionados`): zip recursivo de relativos selecionados; `..` e byte nulo rejeitados; `commonpath` revalidado **dentro** do walk (anti-symlink-escape); limite `tecnico_max_zip_mb` (lido do `tb_config` central) verificado **incrementalmente**; audita `download_software`.
- **Download backup** (`criar_zip_backup`): owner-isolation idem; `os.walk` + `zipfile.ZIP_DEFLATED`; audita `download_backup`.
- **Sanitização/path traversal**: `_sanitizar_nome`, `_pasta_backup_path` com regex `^[0-9]{8}_[0-9]{4}(_[0-9]{2})?_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+(_[0-9]{2})?$` (aceita legado sem segundos e o novo `_SS`), `caminho_relativo` com `..` removido.
- **LGPD**: `remover_vinculos_usuario` apaga pastas físicas + `tb_backup_arquivo` e `tb_backup WHERE owner` (filhos **antes** dos pais, porque o proxy Postgres remove `REFERENCES` e não há cascata implícita); `renomear_usuario` propaga `owner`.

## Referência funcional — ferramentas, software e backup de PCs

### Ferramentas — para que serve o módulo

`mod_tecnico` é o conjunto de **ferramentas de apoio à T.I.** para manutenção e, principalmente,
**formatação de PCs da rede interna**. O desenho é deliberadamente **não-web**: o técnico acessa
a intranet **do próprio PC que está formatando**, com o browser em modo local, e faz duas
coisas:

1. **Baixar software** —Drivers, utilitários, portáteis que o admin deixou em
   `mod_tecnico/software/`. Seleção múltipla → **um ZIP só**, o que importa quando a pessoa
   está copiando o pendrive para o PC que vai formatar e quer levar 30 executáveis de uma vez.
2. **Salvar o backup do PC** — antes de formatar, envia Documentos/Imagens/Vídeos do usuário para
   uma pasta nomeada no servidor, **preservando a árvore de subpastas**, para restaurar depois.

O segundo fluxo é o que dá o nome ao formato da pasta: o backup precisa ser **autoidentificável
na ausência de qualquer metadado externo** — quem abrir a pasta depois, no PC novo, tem de saber
de qual máquina e quando foi feito, sem abrir banco de dados.

### Aba Software — download multi-seleção em ZIP

| Etapa | Implementação |
|:---|:---|
| Listagem | `listar_software_recursivo()` faz `os.walk(PASTA_SOFTWARE)` e devolve **só folhas**, relativo a `software/`, ignorando `.gitkeep`, ordenado |
| Listagem por pasta | `listar_software(relativo)` lista um nível, separando `eh_dir` (pastas) de arquivos; a tela achata `pastas + arquivos` numa lista só |
| Seleção | `ui.checkbox` por item com `data-testid=tecnico-soft-{safe_id}` ligado a `selecionados[rel]`. Marcar uma **pasta** baixa **todo o conteúdo recursivo** dela |
| Zip | `criar_zip_selecionados(relativos, owner)`: `tempfile.NamedTemporaryFile(delete=False, suffix=".zip")` + `ZIP_DEFLATED`. Pasta marcada → `os.walk`; arquivo → direto. O **arco** é o caminho relativo a `software/`, então a subpasta é preservada dentro do ZIP |
| Limite | `tecnico_max_zip_mb` (default **1024** MB). A verificação é **incremental dentro do laço** (`if total > max_mb * 1024*1024: raise ValueError`) — um limite reavaliado só no fim permitiria gravar dezenas de GB em disco antes de descobrir que estourou |
| Auditoria | `download_software` com owner + total em bytes + caminho do zip |

**Blindagem de path traversal (dupla):** `rel` é rejeitado se contém `..`, começa com `/` ou tem
`\x00`; e o `abs_path` é conferido com `os.path.commonpath` contra `PASTA_SOFTWARE`. O
`commonpath` é revalidado **dentro** do `os.walk` para cada arquivo folha — a "dobra de
verificação" documentada no código, que cobre o caso de **symlink** apontando para fora de
`software/`: o filtro de `rel` passaria, mas o `commonpath` do arquivo real não.

Se qualquer coisa der errado, o `except` **remove o zip temporário** antes de re-levantar — um
`tela.py` quebrado não deixa lixo de centenas de MB em `/tmp` por request.

### Aba Backup — pasta `YYYYMMDD_HHMM_nomePc_ip_SS`, owner-isolated

#### Nome da pasta — com sufixo de segundos (correção importante)

O formato real é **`YYYYMMDD_HHMM_nomePc_ip_SS`**, com **sufixo de segundos** (`%S`, 00–59):

```
20260925_1557_NOTE07_192_168_1_10_44
 └─ data ─┘ └min┘ └─ PC ──┘ └─ IP ────┘ └s┘
```

O motivo está na docstring de `nome_pasta_backup` (`bd_manipulador.py:393-422`): o formato antigo
`YYYYMMDD_HHMM` **colidia** quando o técnico criava duas pastas no mesmo minuto para o mesmo
PC/IP — o que é exatamente o caso de uso real (varrer a rede, achar dois Problems, criar backup
dos dois em sequência). O sufixo de segundos resolve **sem quebrar** o prefixo `YYYYMMDD_HHMM_`:
continua ordenável alfabeticamente e continua casando com a regex de validação.

!!! warning "A documentação anterior dizia `YYYYMMDD_HHMM_nomePc_ip` (sem segundos) — e a colisão no mesmo minuto era tratada como erro"
    A versão antiga documentava que o `UNIQUE` de `pasta_nome` "impedia colisão mesmo com clocks
    iguais (segunda tentativa no mesmo minuto falha com 'Pasta já existe')". Hoje o sufixo
    `_SS` **elimina** a colisão na origem, e a mensagem de recusa mudou para
    *"Pasta já existe: `<nome>` — aguarde alguns segundos e tente novamente (nome inclui segundos
    para evitar colisão)"*. A recusa agora só acontece em **condição de corrida real** (dois
    requests no mesmo segundo, ou retry), e é verificada em **duas camadas** — `os.path.exists`
    no FS e `obter_backup` no banco — antes do `os.makedirs(exist_ok=False)`. **Nunca sobrescreve
    pasta alheia.**

- **Sanitização:** `_sanitizar_nome` aplica `[^a-zA-Z0-9_-]`→`_`, colapsa `__`→`_`, faz trim e
  corta em 40 chars. O IP é tratado à parte (`re.sub(r"[^a-zA-Z0-9._-]", "_")` **preservando o
  ponto**, depois ponto→`_`), senão `192.168.1.10` viraria `192_168_1_10` já na etapa errada e o
  fallback `sem_ip` nunca seria distinguível.
- **Validação de entrada:** `owner` obrigatório, `nomePc` ≥ 2 chars, `ip` ≥ 3 chars — mensagens
  em português, sem exceção estourada.
- **Rollback:** se o `INSERT` em `tb_backup` falhar depois do `os.makedirs`, o código faz
  `shutil.rmtree(caminho, ignore_errors=True)` — **não deixa pasta órfã no disco sem registro no
  banco** (e vice-versa, o `UNIQUE` protege o registro órfão).

#### Owner-isolated — a regra que sustenta o módulo

O backup de um PC contém **dados pessoais de uma pessoa** (Documentos, imagens, vídeos). O
módulo aplica o mesmo gate nos três lugares que tocam o conteúdo:

| Operação | Regra |
|:---|:---|
| Listar | `listar_backups(owner, apenas_owner=True)` → `WHERE owner=?`; a tela do técnico **sempre** passa `apenas_owner=True` |
| Enviar | `salvar_arquivos_backup`: `row.owner != owner` → só passa se `perfil_global_de(owner) == "administrador_geral"`; senão `False, "Apenas o dono do backup pode enviar arquivos"` |
| Baixar (zip) | `criar_zip_backup`: mesma checagem, mas via `raise PermissionError("Apenas o dono do backup pode baixar")` — **e o `except` do próprio handler re-levanta `PermissionError` explicitamente** (`except (FileNotFoundError, PermissionError): raise`), para o tratamento genérico não engolir a exceção de permissão como se fosse falha técnica |
| Admin | o card "Backups recentes (todos os usuários)" usa `listar_backups(apenas_owner=False)` — é a **exceção declarada**, restrita a quem tem acesso a `/admin/tecnico` |

A checagem é **por tabela, não por perfil** (o mesmo padrão do `mod_solicita_impressao`): o dono é
gravado no `tb_backup` no momento da criação e é a **fonte da verdade** da autorização, não o
papel do usuário. Se o `perfil_global_de` falhar, o padrão é **negar** (`return False`), não
permitir — fail-closed.

#### `webkitdirectory` — envio de pasta inteira

O atalho é `ui.upload(multiple=True, auto_upload=True)` + uma injeção de atributo não-padrão:

```javascript
setTimeout(() => {
  const inp = document.querySelector('[data-testid=tecnico-upload] input[type=file]');
  if (inp) { inp.setAttribute('webkitdirectory',''); inp.setAttribute('directory',''); }
}, …)
```

- O `setTimeout` existe porque o `<input type=file>` **ainda não existe** no momento em que o
  `ui.upload` retorna — o elemento só é materializado depois do próximo tick do loop.
- O seletor ancorado em `[data-testid=tecnico-upload]` evita pegar o input de **outro** upload da
  página.
- É **fail-soft de propósito**: `webkitdirectory`/`directory` não estão em nenhum padrão
  (Chrome/Edge/Firefox modernos aceitam; outros ignoram o atributo silenciosamente). O
  `if (inp)` sem `else` e sem exceção significa que, onde o atributo não funciona, o upload
  **continua funcionando** — o técnico só precisa segurar Ctrl e selecionar os arquivos, e o
  rótulo da tela explica as duas opções.
- **Efeito no backend:** com `webkitdirectory` ativo, `f.name` vem como caminho **relativo**
  (`Documents/foto.jpg`), não só o nome do arquivo. É isso que `salvar_arquivos_backup`
  normaliza (`replace("\\","/")` → split → remove `..`/vazios/`\x00` → sanitiza cada segmento com
  `[^A-Za-z0-9._-]`→`_` e `strip("._")` → `os.makedirs(dirname)` + escrita), preservando a
  árvore. Sem o atributo, `f.name` é um nome simples e o arquivo cai na raiz da pasta — o backup
  funciona, mas **achatado**, o que é a principal perda de qualidade desse fluxo.

#### Atomicidade FS + DB (24/09/2026) — por que importa num upload de backup

Backup é a **operação que o técnico faz uma vez, antes de uma ação irreversível**. Um estado
intermediário quebrado é o pior resultado possível: ou o arquivo está no disco sem registro (e
ninguém sabe que ele existe), ou está no banco sem o arquivo (e a restauração perde dado).

Por isso `salvar_arquivos_backup` é o único ponto do módulo com **duas fases e compensação**:

```
FASE 1 — FS (fora da transação, não dá para transacionar disco)
  para cada (nome, conteudo):
    sanitiza caminho → commonpath confere → makedirs(dirname) → open(dest,"wb")
    pendentes.append((nome, nome_rel, tamanho, sha256(conteúdo)))
    escritos.append(abspath(dest))          ← memo para a compensação
FASE 2 — DB (transação CURTA, com retry)
  até 3 tentativas: INSERT tb_backup_arquivo por arquivo
                    UPDATE tb_backup SET tamanho_total += total, status='em_envio'
                    commit
    se "locked" no erro e ainda há tentativa: rollback, sleep(0.05 × tentativa), repete
SE A FASE 2 FALHAR (qualquer caminho: último_erro ou exceção externa)
  COMPENSAÇÃO: os.remove() de TODOS os arquivos de `escritos` (desta chamada)
  loga a contagem removida e retorna (False, msg)
```

Três decisões merecem registro:

1. **Fase 1 fora da transação** — o SQLite controla transação de banco, não de sistema de
   arquivos. Escrever dentro da transação e depois descobrir que o commit falhou deixaria os
   arquivos no disco de qualquer forma; a ordem "FS primeiro, DB depois, compensa o FS se o DB
   falhar" é a única que fecha o problema.
2. **Retry em `database is locked`** (3×, `sleep` crescente 0.05/0.10/0.15 s) — o módulo roda em
   SQLite com WAL e `busy_timeout=5000` herdado do núcleo, mas um `INSERT` de backup pode competir
   com o job `cleanup_pdf`, com o monitor de empenhos ou com outro upload. O `rollback` antes do
   retry é obrigatório: sem ele a tentativa 2 falha porconstraint pendente, não por lock.
3. **A compensação apaga só o que esta chamada escreveu** (`escritos` é preenchido durante a
   fase 1). Um retry do usuário que reenvia arquivos já existentes **não** apaga os arquivos da
   tentativa anterior, que continuam válidos e registrados.

O `tecnico_quota_gb` **não participa** disso: ele é semeado em `tb_config_tecnico` mas **não é
lido em lugar nenhum do módulo** (ver "Pontos de atenção").

### Configuração — fonte central com fallback local

`_obter_config_tecnico(chave, padrao)` implementa uma leitura **dual**, e a ordem é deliberada:

1. `mod_intranet.bd_conexao.get_config(chave)` — **fonte** (é onde o painel `/admin/tecnico`
   grava, via `set_config`).
2. `tb_config_tecnico` local — **fallback/legado** (seedado no `init_db`).
3. `padrao` do chamador.

O motivo está na docstring: a tabela local nasceu como seed, mas o painel e o `criar_zip_selecionados`
usam o central — ler o local primeiro faria os dois divergirem silenciosamente. O
`tecnico_max_zip_mb` é a única chave efetivamente **consumida**; o painel grava sempre no central.

### Integrações com o núcleo

Importa `autenticacao.validar_acesso_modulo`/`perfil_global_de`, `banco_conexao.conexao`,
`tema_modulo.ler_tema`/`notificar`, `ui_comum.botao`. Grava via `audit_log` → `tb_auditoria_tecnico`. Backup do banco via `rotinas.painel_backup`/`MAPA_BACKUPS` (`tecnico: db_mod_tecnico.db`). Pastas físicas `PASTA_SOFTWARE`/`PASTA_BACKUP` garantidas em `init_db()`.

## Pontos de atenção

- `mod_tecnico/backup/*` é runtime (**dados de usuário** — nunca versionar além do `.gitkeep`); `mod_tecnico/software/*` é conteúdo opcional versionável. **Estado real auditado em 25/09/2026:** `software/` contém **apenas `.gitkeep`** (sem a pasta `instalador/` que a documentação anterior citava → `listar_software_recursivo()` devolve `[]` e a tela mostra "Nenhum arquivo em software/." com botão Atualizar) e `backup/` contém **`.gitkeep`** (a documentação anterior afirmava "sem `.gitkeep`"). Ambos são garantidos em runtime por `os.makedirs(exist_ok=True)` no `init_db()`.
- **`tecnico_quota_gb` é chave morta** — semeada em `tb_config_tecnico` com valor `"10"` e **nunca lida** em nenhum ponto do módulo (nem em `salvar_arquivos_backup`, nem na tela, nem no painel). Não há, portanto, **cota de disco por usuário** no fluxo de backup: o único teto é o espaço do servidor. Se a intenção era limitar o backup por técnico, falta implementar a verificação (o padrão de referência está em `mod_edit_pdf.verificar_quota`).
- **Regex de validação de pasta** — a documentação anterior registrava `^[0-9]{8}_[0-9]{4}_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+$`; o código atual é `^[0-9]{8}_[0-9]{4}(_[0-9]{2})?_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+(_[0-9]{2})?$`, que aceita o formato legado sem segundos **e** o novo com `_SS`. Nome fora do padrão não é rejeitado — é truncado em 80 chars e usado, e o `commonpath` ainda garante contenção em `backup/`.
- `data-testid` para QA: `tecnico-soft-{safe_id}`, `tecnico-baixar`, `tecnico-backup-nomepc`, `tecnico-backup-ip`, `tecnico-criar-pasta`, `tecnico-backup-select`, `tecnico-upload`, `tecnico-baixar-{safe_id}`. `_safe_id` sanitiza o relativo e corta em 40 chars — **pode colidir** para dois caminhos longos diferentes; o seletor de teste deve preferir o checkbox pelo texto visível quando houver dúvida.
- `webkitdirectory` é não-padrão — JS fail-soft; fallback Ctrl+A múltiplo (backup fica achatado, sem subpastas).
- Zips temporários via `tempfile.NamedTemporaryFile(delete=False)` — limpeza SO; `cleanup_pdf` não afeta este módulo. `criar_zip_selecionados` e `criar_zip_backup` removem o temp no `except` antes de re-levantar.
- `tb_backup.pasta_nome` UNIQUE + prefixo de segundos `_SS` — a colisão real só ocorre em request concorrente no mesmo segundo, e é detectada no FS **e** no banco antes do `makedirs`.
- **`remover_vinculos_usuario` apaga filhos antes dos pais** (`tb_backup_arquivo` e depois `tb_backup`) em vez de confiar em `ON DELETE CASCADE`: o proxy Postgres remove a cláusula `REFERENCES`, então cascata implícita não existe lá. O `salvar_arquivos_backup` faz o mesmo no caminho inverso.
- ✅ **`ui.notify` cru: zero** neste módulo (0 ocorrências em `telas.py` e `telas_administracao.py`; 12 chamadas a `notificar(`). É um dos módulos já aderentes ao AGENTS.md §5.1 — ao contrário de `mod_edit_pdf` (parcial) e `mod_renomear_empenho` (117 + 23).

## Status

| Item | Situação |
|:---|:---|
| Banco WAL + CRUD owner-isolated | Implementado |
| Pastas físicas `software/` + `backup/` | Implementado (`.gitkeep` + `makedirs`) |
| Software multi-seleção + zip | Implementado (`criar_zip_selecionados`, com `commonpath` revalidado no walk) |
| Backup `YYYYMMDD_HHMM_nomePc_ip_SS` + webkitdirectory | Implementado (`criar_pasta_backup` + `salvar_arquivos_backup`) |
| **Atomicidade FS+DB no envio** (2 fases + compensação + retry em lock) | Implementado (24/09/2026) |
| LGPD (`remover/renomear`) + auditoria | Implementado (filhos antes dos pais) |
| Painel `/admin/tecnico` | Implementado (`bloco_aparencia` + `tecnico_max_zip_mb` + `painel_backup`) |
| `ui.notify` cru | **Zero** — 100 % via `tema_modulo.notificar()` |
| Cota de disco por usuário (`tecnico_quota_gb`) | ⚠️ **Não implementada** — chave semeada e nunca lida |

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| tecnico | Sem `CrudBase`; sem quebra PG localizada (varredura fina pendente) | `mod_tecnico/bd_manipulador.py` (sem `CrudBase` — verificado por busca) | Migrar para `CrudBase` + `conexao("tecnico")`; varredura `GROUP BY`/`COLLATE`/`strftime` SQL no módulo | Baixo-médio (ZIP + backup `YYYYMMDD_HHMM_nomePc_ip_SS`) |

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).
