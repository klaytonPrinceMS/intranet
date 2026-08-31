# Intranet Core Module — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (WAL: unified audit, config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru).

---

# Módulo Núcleo Intranet — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (auditoria unificada em WAL, configurações, sessões e cadastro de módulos) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru).

## Propósito

Pacote núcleo que centraliza o que todos os módulos compartilham: banco central (auditoria LGPD, configurações, sessões e cadastro de módulos), autenticação com sessões revogáveis, layout padrão de 4 partes com guarda de página, rotinas agendadas e a tela de personalização `/configuracoes`. **Não possui `telas.py` próprio** — suas telas são montadas pelas rotas de `main.py`.

## Banco central `db_mod_intranet.db`

Toda conexão executa `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` (`conexao_bd.py:27-31`). Tabelas:

| Tabela | Conteúdo |
|:---|:---|
| `tb_auditoria` | trilha unificada LGPD (`ip`/`user_agent` por migração) |
| `tb_config` | chave/valor — aparência, cotas, `versao_modulo:*`, `log_*`, `smtp_*` |
| `tb_sessoes` | sessões com `cookie_hash`, `ip`, `user_agent`, `dispositivo`, `mac` |
| `tb_modulos` | cadastro de módulos (nome, ícone, rota, ativo, nativo) |

## Funcionalidades

- **Autenticação bcrypt + sessões revogáveis**: `autenticar` → `registrar_login` (cookie_hash via `secrets`) → `sessao_ativa` revalidada a cada request; encerrar sessão pelo admin derruba o navegador.
- **Guarda de página** (`pagina_restrita`): revalida usuário/sessão/permissão e monta o layout de 4 partes (header, drawer lateral, rodapé com versões, área principal).
- **Dashboard `/`**: saudação, **feed do Blog por padrão** (RF-09) e estatísticas (usuários ativos, postagens, auditoria p/ admin).
- **Login `/login`**: customizável por `tb_config`; com favicon dinâmico (`favicon_versao`).
- **Configurações `/configuracoes`** (só `administrador_geral`): cores, ícone, título, textos, favicon, páginas/módulos, SMTP, backup, sessão, observabilidade — "SALVAR TUDO" e "Restaurar padrão".
- **Backup por módulo** (12 h default, reagendável sem restart) + retenção das 10 cópias em `backup/`.
- **Observabilidade (loguru)**: sinks em `logs/` com rotação/retenção/compressão; `get_logger("<modulo>")` por módulo; excepthook global.
- **Documentação embutida**: `documentacao.py` builda o MkDocs e monta `/documentacao`.

## Permissões

| Área | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Login/Dashboard | ✓ | ✓ | ✓ |
| Meu Perfil / troca de senha | ✓ | ✓ | ✓ |
| Drawer lateral | módulos liberados | módulos liberados | todos |
| `/configuracoes` | ✗ | ✗ | ✓ |

## Rota e integrações

- Rotas: `/` (`main.py:112`), `/login` (`main.py:51`), `/configuracoes` (`main.py:306`), `/documentacao` (mount).
- Consumido por todos: `pagina_restrita`, `get_connection`/`get_config`/`set_config`, `audit_log`, `gerar_hash_senha`, `validar_acesso_modulo`.
- Jobs: `backup:<chave>` (12 h), `cleanup_pdf`/`cleanup_solicita` (1 min), `poda_auditoria` (24 h), `monitor_empenho` (10 s).

## Testes

```bash
.venv/bin/python test/test_fase1_login.py
.venv/bin/python test/test_server.py
```

## Pontos de atenção

- `inicializar_bancos()` roda o central **antes** de importar módulos (ordem crítica — `main.py:16-17`).
- `storage_secret` é placeholder (`main.py:336`) — trocar em produção.
- `backup_interval_hours` é seed legada; os jobs usam `backup_horas:<modulo>`.

Ver [Análise do Núcleo](../analise_mod_intranet.md) (detalhe completo, incluindo reconstrução de `conexao_bd.py`/`manipulador_bd.py` a partir de `*.pyc`).