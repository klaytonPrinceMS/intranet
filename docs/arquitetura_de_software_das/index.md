# Software Architecture — Intranet Modular

> Technical architecture: single entry point, modular package layout, per-module WAL databases, the centralized audit model and the background schedulers.

---

# Arquitetura de Software (DAS) — Intranet Modular

> Arquitetura técnica: entry point único, layout de pacotes modulares, bancos WAL por módulo, modelo de auditoria centralizada e agendadores em segundo plano.

## Entry point

- **`main.py`** é o único ponto de entrada. Sobe o servidor NiceGUI na porta `8080` (`reload=False`, `show=False`) e a documentação na porta `8000` (`porta_documentacao`, separada — `documentacao.iniciar_servidor`).
- No boot chama `inicializar_bancos()` (`mod_intranet/mod_intranet_inicializacao_bd.py:13` — ordem `init_central` → `garantir_rastreabilidade` → `init_db_auditoria` + `migrar_dados_existentes` → `init_blog` → `init_users` → `init_db_pdf` → `init_db_empenho` → `init_solicita` (importa `ORGANOGRAMA_BASE` do `mod_lista_telefonica` para cotas 1000/200) → `init_db` técnico → `init_db` filas → `init_db` lista telefônica), que cria o banco central **antes** de importar qualquer módulo. `mod_intranet/bd_criador.py` e `bd_criador.py` dos módulos são **LEGADO/MORTO** — não executar (schema real via `bd_manipulador.init_db*` + `banco_conexao.conexao(chave)`).

## Layout de pacotes

Cada módulo é um pacote `mod_<nome>/` com `telas.py` (obrigatório: `mostrar_tela(nome, perfil)`), `telas_administracao.py` (painel admin), `bd_manipulador.py` (único acesso ao DB) e `bd_criador.py` (legado/morto — o schema real é criado por `init_db*` no `bd_manipulador`). Acesso a dados concentra-se em `bd_manipulador.py`.

## Banco de dados

- **Central** `db_mod_intranet.db`: `tb_config` (incl. `conteudo_palavras_bloqueadas` censura central `mod_intranet/censura.py`), `tb_sessoes`, `tb_modulos` (seed `MODULOS_SISTEMA` com **9 de negócio + núcleo = 10** — 6 históricos + `tecnico` + `filas` multi-filas 09/2026 + `lista_telefonica` 19/09/2026 + `agregador_noticias` 19/09/2026; 11 módulos no `MODULOS_BD`).
- **Auditoria** `db_mod_auditoria.db`: `tb_auditoria_<modulo>` (uma tabela por módulo produtor, inclui `tecnico`/`filas`/`lista_telefonica`/`agregador_noticias` + `censura` `palavras_bloqueadas` em `audit_log`) + `tb_auditoria_meta` (criada via `mod_auditoria/bd_manipulador.py`).
- Cada módulo tem seu `.db` na raiz em modo **WAL** (`*.db-wal`, `*.db-shm`) — **novos** `db_mod_tecnico.db` (`tb_backup`/`tb_backup_arquivo` + pastas `software/`+`backup/YYYYMMDD_HHMM_nomePc_ip`, owner-isolation), `db_mod_filas.db` **multi-filas** (`tb_fila` com `endereco/prefixo/inicio→fim` `fim=0` infinito + `criado_por` + `tv_grupo`, `tb_fila_etapa`, `tb_chamada` com `paciente_nome/etapa_nome`, `tb_midia` global, `PASTA_MIDIA` `mod_filas/midia` → `/midia_filas/*`, rotas `/tv` + `/tv/{id}` + `/tv?grupo=`) e `db_mod_lista_telefonica.db` (`tb_unidade` `secretaria|setor|subsetor` + `tb_contato` alfabético + `ORGANOGRAMA_BASE` 12 secretarias, `tel:` no celular) e `db_mod_agregador_noticias.db` (`tb_noticia` com censura `titulo_bloqueado`/`limpar_censuradas` + `listar_para_tv` filtra `LIMIT*3`). Backend duplo SQLite/PostgreSQL via `mod_intranet/banco_conexao.conexao(chave)` (um `DATABASE db_mod_<chave>` por módulo no Postgres, espelhando o arquivo SQLite). **Censura central** (`mod_intranet/censura.py`, `conteudo_palavras_bloqueadas`) compartilhada Blog↔Agregador (filtrada na TV).
- **Não cross-query**: consultar via o `bd_manipulador` do próprio módulo (via `banco_conexao.conexao(chave)`, nunca `sqlite3.connect` cru em banco alheio); isolamento "um banco por módulo" válido nos dois backends.
- Auditoria LGPD via `audit_log` → banco exclusivo `db_mod_auditoria.db` (tabela por módulo) para toda escrita; operações de PDF e backup registram hash SHA-256 (`hash_arquivo`).

## Agendadores (APScheduler)

- **Backups:** a cada 12 h por módulo (chave `backup_horas:<modulo>`), retenção de 10 cópias em `backup/` — `MAPA_BACKUPS` inclui `tecnico` + `filas` 18/09/2026 + `lista_telefonica` 19/09/2026 (`rotinas.py:16-22`).
- **Expiração do editor PDF:** varredura a cada 1 min (`cleanup_pdf` → `expirar_antigos(cfg_expiracao_min())`, default 10 min; fallback `limpar_editor_pdf`).
- **Limpeza de solicitação de impressão:** `cleanup_solicita` a cada 1 min (`mod_intranet/rotinas.py` — remove rascunhos não confirmados e impressos vencidos).
- **Monitor de empenhos:** `monitor_empenho` a cada `empenhos_monitor_intervalo_seg` (60 s) — ver [Renomear Empenhos](../modulos/renomear_empenho.md).
- **Poda da auditoria:** `poda_auditoria` a cada 24 h (LGPD, `auditoria_retencao_dias` default 90 — varre `tb_auditoria_<modulo>`).
- **Observabilidade:** `loguru` com rotação/retenção/compressão, por módulo (`mod_intranet/observabilidade.py`); console `auto/sempre/nunca`, bridge OTel→Loki.

## Autenticação e sessões

- `mod_intranet/autenticacao.py`: login, hash bcrypt, registro de sessão, guarda de revalidação.
- Sessão via cookie `HTTP-Only` com hash único por sessão (`secrets`); revogável individualmente ou em massa.
- Rastreabilidade: IP (`X-Forwarded-For`), User-Agent, rótulo de dispositivo, MAC best-effort.

Veja [Guia de API](../guia_API/index.md) para rotas e funções-chave.
