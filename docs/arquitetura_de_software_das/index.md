# Software Architecture — Intranet Modular

> Technical architecture: single entry point, modular package layout, per-module WAL databases, the centralized audit model and the background schedulers.

---

# Arquitetura de Software (DAS) — Intranet Modular

> Arquitetura técnica: entry point único, layout de pacotes modulares, bancos WAL por módulo, modelo de auditoria centralizada e agendadores em segundo plano.

## Entry point

- **`main.py`** é o único ponto de entrada. Sobe o servidor NiceGUI na porta `8080` (`reload=False`, `show=False`).
- No boot chama `inicializar_bancos()` (`mod_intranet/mod_intranet_inicializacao_bd.py`), que cria o banco central **antes** de importar `mod_gest_cad_usuario`.

## Layout de pacotes

Cada módulo é um pacote `mod_<nome>/` com `telas.py` (obrigatório: `mostrar_tela(nome, perfil)`), `manipulador_bd.py` e `criador_bd.py` (legado/morto). Acesso a dados concentra-se em `manipulador_bd.py`.

## Banco de dados

- **Central** `db_mod_intranet.db`: `tb_auditoria`, `tb_config`, `tb_sessoes`, `tb_modulos`.
- Cada módulo tem seu `.db` na raiz em modo **WAL** (`*.db-wal`, `*.db-shm`).
- **Não cross-query**: consultar via o `manipulador_bd` do próprio módulo.
- Auditoria central em `tb_auditoria` para toda escrita; operações de PDF registram hash SHA-256 (`hash_arquivo`).

## Agendadores (APScheduler)

- **Backups:** a cada 12 h por módulo (chave `backup_horas:<modulo>`), retenção de 10 cópias em `backup/`.
- **Expiração do editor PDF:** varredura a cada 1 min, independente de usuários.
- **Limpeza de solicitação de impressão:** `cleanup_solicita` a cada 1 min (`mod_intranet/rotinas.py`).
- **Observabilidade:** `loguru` com rotação/retenção/compressão, por módulo (`mod_intranet/observabilidade.py`).

## Autenticação e sessões

- `mod_intranet/autenticacao.py`: login, hash bcrypt, registro de sessão, guarda de revalidação.
- Sessão via cookie `HTTP-Only` com hash único por sessão (`secrets`); revogável individualmente ou em massa.
- Rastreabilidade: IP (`X-Forwarded-For`), User-Agent, rótulo de dispositivo, MAC best-effort.

Veja [Guia de API](../guia_API/index.md) para rotas e funções-chave.
