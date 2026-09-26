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

---

# RF e RNF verificados no código — lote 1 (26/09/2026)

> Auditoria de requisitos **funcionais** (o que o sistema faz) e **não
> funcionais** (qualidade e restrições), com evidência `arquivo:linha` conferida
> no código em 26/09/2026.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-TEC-01 | Acesso à tela só para `administrador_geral` **ou** usuário com liberação no módulo `tecnico` | `telas.py:24-34` `_pode_acessar` (admin geral retorna `True`; senão `autenticacao.validar_acesso_modulo`); negação visual em `telas.py:44-49` |
| RF-TEC-02 | Abas **Software** \| **Backup** com `ui.tabs` + `ui.tab_panels` | `telas.py:62-70` |
| RF-TEC-03 | Listagem recursiva de `software/` com pastas intermediárias derivadas e dedupe estável | `telas.py:101-116` (`listar_software_recursivo` + `pastas` + `vistos`); `bd_manipulador.py:292` |
| RF-TEC-04 | Seleção múltipla (arquivo **ou** pasta marcada baixa tudo dentro) por `data-testid` estável | `telas.py:132-135` (checkbox `data-testid=tecnico-soft-<rel sanitizado>`) + `_safe_id` em `telas.py:179-184` |
| RF-TEC-05 | Tamanho em arquivo exibido como B/KB/MB/GB/TB | `telas.py:126-130` (`os.path.getsize`) + `_fmt_bytes` em `telas.py:163-176` |
| RF-TEC-06 | **Baixar selecionados** gera ZIP no servidor e dispara `ui.download`; recusa seleção vazia com aviso | `telas.py:141-152` (`criar_zip_selecionados` → `ui.download`); `bd_manipulador.py:315` |
| RF-TEC-07 | Limite de tamanho do ZIP configurável (`tecnico_max_zip_mb`, 10–10000 MB, fallback 1024) | `bd_manipulador.py:144-153` `_obter_max_zip_mb`; painel em `telas_administracao.py:50-59` |
| RF-TEC-08 | Criar pasta de backup com nome automático `YYYYMMDD_HHMM_nomePc_ip` (+ sufixo `_SS` de segundos) e prévia ao vivo enquanto o usuário digita | `bd_manipulador.py:393` `nome_pasta_backup` + `:424` `criar_pasta_backup`; prévia em `telas.py:222-230` |
| RF-TEC-09 | Upload 1-clique do PC a formatar via `webkitdirectory` (multi-pasta, estrutura preservada) | `telas.py:268-289` `ao_upload` (lê bytes e usa `f.name` com caminho relativo) + `telas.py:294-302` `run_javascript` fail-soft aplicando `webkitdirectory` |
| RF-TEC-10 | Seletor de pasta destino do upload, populado só com backups **do próprio usuário** | `telas.py:245-258` (`listar_backups(owner=user_nome, apenas_owner=True)`) |
| RF-TEC-11 | **Baixar pasta (zip)** de um backup, com spinner, trava de reentrância e I/O fora do event-loop | `telas.py:316-344` `async _baixar` + `run.io_bound(tec.criar_zip_backup)` + `ui.spinner` + `_occ["sim"]` |
| RF-TEC-12 | Prévia do conteúdo da pasta em diálogo (até 200 arquivos + "… e mais N") | `telas.py:358-388` `_dlg_listar` (`os.walk` + `sorted(arquivos)[:200]`) |
| RF-TEC-13 | `/admin/tecnico`: aparência (cores, tamanho de botão, cabeçalho), limite de ZIP, backups recentes (todos os usuários, 30) e painel de backup | `telas_administracao.py:17-78` (`bloco_aparencia` + card config + `listar_backups(owner=None, apenas_owner=False)` + `painel_backup`) |
| RF-TEC-14 | Painéis de backup: "Atualizar" (re-render) e "Atualizar" na aba Software | `telas.py:92`, `:158`, `:353` |
| RF-TEC-15 | Falha de backup **nunca** derruba o handler — `OSError`→`None` e retorno `(ok, msg)` | `bd_manipulador.py:592-620` (`salvar_arquivos_backup` devolve tupla) + `telas.py:287` (`notificar` com `positive`/`negative` conforme `ok`) |
| RF-TEC-16 | Hash **SHA-256** por arquivo enviado (rastreabilidade do conteúdo) | `bd_manipulador.py:89-101` `_hash_sha256`; gravado em `tb_backup_arquivo.hash_sha256` |
| RF-TEC-17 | LGPD: exclusão/renomeio de usuário limpa os vínculos de backup (filhos antes dos pais) | `bd_manipulador.py:790` `remover_vinculos_usuario` + `:853` `renomear_usuario` |
| RF-TEC-18 | Auditoria de todos os eventos do módulo na tabela do próprio módulo (`tb_auditoria_tecnico`) | `bd_manipulador.py:61-73` `_audit` → `mod_intranet.bd_manipulador.audit_log` |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-TEC-PERS-01 | Banco próprio, um `db_mod_<chave>.db` por módulo | `get_connection` → `banco_conexao.conexao("tecnico")` (`bd_manipulador.py:41-59`) → `caminho_db("tecnico")` |
| RNF-TEC-PERS-02 | `PRAGMA journal_mode=WAL` + `foreign_keys=ON` | `bd_manipulador.py:50-51` (falha de PRAGMA só gera `warning`, não derruba) |
| RNF-TEC-PERS-03 | `busy_timeout=5000` + `synchronous=NORMAL` herdados do núcleo | `banco_conexao.py:705-708`; `mod_tecnico` não repete (herda) |
| RNF-TEC-PERS-04 | Retry em `database is locked` nas transações curtas de upload | `bd_manipulador.py:597-601` (docstring) — 3 tentativas + rollback + **compensação no FS** |
| RNF-TEC-PERS-05 | DDL idempotente e import-safe (`init_db` nunca levanta) | `bd_manipulador.py:156-243` (`CREATE TABLE IF NOT EXISTS`, seed com fallback se `INSERT OR IGNORE` falhar, `except` → `log.exception` + `return`) |
| RNF-TEC-COMP-01 | Paridade SQLite ↔ PostgreSQL (proxy `_CursorPostgres`) | DDL só `IF NOT EXISTS` (`:172-206`); `INSERT OR IGNORE` com **fallback explícito** `SELECT`+`INSERT` (`:206-212`); `REFERENCES ... ON DELETE CASCADE` traduzido |
| RNF-TEC-SEG-01 | Blindagem de **path traversal** em toda pasta física | `bd_manipulador.py:557-589` `_pasta_backup_path`: `os.path.basename` + regex `^[\w.-]+$` + **`os.path.commonpath`** revalidado, com fallback seguro para dentro de `PASTA_BACKUP` |
| RNF-TEC-SEG-02 | Sanitização de `nomePc`/`ip` (só `[A-Za-z0-9_-]`, 40 chars) | `bd_manipulador.py:76-86` `_sanitizar_nome` |
| RNF-TEC-SEG-03 | **Só o dono** envia arquivo; `administrador_geral` é exceção | `bd_manipulador.py:607-614` (`row[2] != owner` → `perfil_global_de(owner) != "administrador_geral"` → recusa) |
| RNF-TEC-SEG-04 | **Isolamento por dono** na listagem (`apenas_owner=True` como default) | `bd_manipulador.py:504-517` `listar_backups`; chamada da tela em `telas.py:245` |
| RNF-TEC-SEG-05 | Autorização de escrita auditada | `bd_manipulador.py:61-73` `_audit` (falha de auditoria só gera `warning`, não bloqueia a ação) |
| RNF-TEC-RES-01 | `try/except` obrigatório em função, com `notificar` + `log` (AGENTS.md §3.2) | 100 % das funções de `bd_manipulador.py` e `telas.py` protegem; **zero** `ui.notify` cru (só `tema_modulo.notificar`) |
| RNF-TEC-RES-02 | Fail-soft: falha de auditoria/conexão/config não derruba a operação | `_audit` (`:69-73`), `_hash_sha256` → `""` (`:100-101`), `_obter_config_tecnico` → central e depois fallback local e depois `padrao` (`:104-141`) |
| RNF-TEC-UX-01 | Anti-disconnect: I/O pesado em `async` + `run.io_bound` + spinner + trava (§5.1) | ✅ `telas.py:316-344` (ZIP do backup) — referência canônica do módulo |
| RNF-TEC-UX-02 | `data-testid` via `.props('data-testid=...')` em todas as ações | `telas.py:134` (checkbox), `:157` (Baixar), `:216`/`:218` (Nome do PC / IP), `:242` (Criar pasta), `:256` (select), `:292` (upload), `:346` (Baixar pasta) |
| RNF-TEC-UX-03 | `aria-label` no spinner de I/O pesado | `telas.py:329-330` (`aria-label=Gerando ZIP de <pasta>`) |
| RNF-TEC-UX-04 | Rótulos PT-BR e docstrings bilíngue EN (topo) / PT-BR (abaixo) | `telas.py:1-4`, `telas_administracao.py:1-4`, `bd_manipulador.py:1-10` |
| RNF-TEC-PERF-01 | Sem N+1: listagem em 2 consultas (`listar_software` + `listar_software_recursivo`) | `telas.py:88-89`, `:101` |
| RNF-TEC-PERF-02 | Teto de renderização no diálogo de prévia (200 arquivos) | `telas.py:382-385` |
| RNF-TEC-RESP-01 | Responsividade com `flex-wrap` + `min-w-[220px]` nos campos | `telas.py:215-218` |
| RNF-TEC-CFG-01 | Configuração dual com fonte única de verdade (central) e fallback local | `bd_manipulador.py:104-141`; escrita só no central (`telas_administracao.py:53`, `:57`) |

## Divergências e riscos

### Código faz, doc não diz

| # | Achado | Evidência |
|:---|:---|:---|
| DIV-TEC-01 | Sufixo `_SS` (segundos) no nome da pasta **e** a variante `YYYYMMDD_HHMM_SS_pc_ip` são aceitos na blindagem — a doc só cita `YYYYMMDD_HHMM_nomePc_ip` | `bd_manipulador.py:569-572` (regex com `(_[0-9]{2})?` nos dois formatos) |
| DIV-TEC-02 | O `run_javascript` que injeta `webkitdirectory` é uma **dependência de JS direto**, que o AGENTS.md §5 proíbe; está em `try/except` e é fail-soft, mas é JS no caminho crítico do upload 1-clique | `telas.py:294-302` |
| DIV-TEC-03 | `telas.py:196-203` importa `nicegui.client.Client` e **não usa** — o comentário diz *"Não há acesso síncrono ao request aqui; usaremos placeholder"*, então `ip_sugerido` é **sempre vazio** e o campo IP nasce em branco. Código morto. | `telas.py:196-203` |
| DIV-TEC-04 | `tecnico_quota_gb` é semeada em `tb_config_tecnico` e **nunca lida** (já registrado como "não implementada" na seção Status) | `bd_manipulador.py:201` (seed) — nenhuma leitura no módulo |
| DIV-TEC-05 | `/admin/tecnico` é alcançável por **qualquer usuário com acesso ao módulo**, não só por administrador | ver RISCO-TEC-01 |
| DIV-TEC-06 | `telas_administracao.py:42-48` mostra os dois caminhos de pasta em campos **desabilitados** (`inp_soft.disable()`), com tooltip explicando que são fixos — a doc não registra que a edição é impossível por design | `telas_administracao.py:42-48` |

### Doc diz, código não faz

| # | Alegação da doc | Estado real |
|:---|:---|:---|
| DIV-TEC-07 | "Configuração dual com fonte única de verdade" (implica que o local é só cache) | Correto no caminho de **leitura**, mas `_obter_config_tecnico` continua able to ler o local — se alguém escrever direto em `tb_config_tecnico`, o valor local ganha. Não há job de reconciliação. |

### Riscos

| # | Risco | Severidade | Evidência |
|:---|:---|:---|:---|
| **RISCO-TEC-01** | **`/admin/tecnico` sem gate de administrador.** `main.py:1080-1086` calcula `eh_admin` (geral **ou** admin do módulo) e **não usa**: chama `mostrar_administracao(nome)` sem o flag e **sem** o `if not eh_admin: notificar + navigate` que `lista_telefonica` (`main.py:1102-1105`) e `agregador_noticias` (`main.py:1115-1117`) têm. `telas_administracao.py:17` também não recebe nem checa perfil. Efeito: um usuário `comum` com liberação do módulo Técnico **altera `tecnico_max_zip_mb` e o tema** e **vê a lista de backups de todos os usuários** (card "Backups recentes (todos os usuários)"). | 🔴 Alta | `main.py:1080-1086` + `mod_tecnico/telas_administracao.py:17`
| **RISCO-TEC-02** | **`baixar()` do ZIP de software é `def` síncrono** (`telas.py:141`) e chama `criar_zip_selecionados` (walk + `zipfile` de N arquivos) direto no event-loop — exatamente o padrão que o AGENTS.md §5.1 proíbe e que o próprio módulo já corrige em `_baixar` (`telas.py:316`). Zip grande ⇒ derruba o WebSocket do cliente. | 🟠 Média | `telas.py:141-152` vs. `telas.py:316-344` |
| **RISCO-TEC-03** | `salvar_arquivos_backup` grava **bytes em memória** (`arquivos = [(nome, conteudo)]`, `telas.py:274-280`) antes de tocar o disco. Backup de usuário com GB vira RAM do servidor. Sem teto de tamanho por arquivo nem total. | 🟠 Média | `telas.py:268-286` |
| **RISCO-TEC-04** | Sem `CrudBase`: o módulo faz SQL cru via `conn.cursor()`. Funciona (o proxy traduz), mas não usa a transação atômica `crud.transacao()` que o AGENTS.md §4 oferece, e a "atomicidade FS+DB" é **compensação manual** (remove o que gravou) — janela em que FS e DB divergem se o processo cair entre os dois passos. | 🟡 Baixa | `bd_manipulador.py:597-601` + ausência de `CrudBase` |
| **RISCO-TEC-05** | `tb_backup.status` só tem **dois** estados reais: `'criado'` (default, `bd_manipulador.py:177`) e `'em_envio'` (gravado em `bd_manipulador.py:682` no fim da fase 2). Não existe estado "concluído"/"restaurado", então a coluna mostrada em `telas.py:311` fica presa em `em_envio` mesmo depois que o backup terminou — o usuário não tem como saber se a cópia ficou completa. | 🟡 Baixa | `bd_manipulador.py:177` + `:682` |
