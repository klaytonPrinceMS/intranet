# Manual de Uso — Instalação — Intranet Modular

> Como preparar o ambiente, subir o servidor e realizar o primeiro acesso com o administrador seed e os usuários de teste.

## Pré-requisitos

- Python 3.12; ambiente virtual em `.venv/` na raiz.
- Rede interna (intranet); sem acesso externo.

## 1. Ambiente virtual

```bash
.venv/bin/python -m pip install -r requirements.txt   # se necessário
```
No Windows use `Scripts\python.exe`.

## 2. Subir a aplicação

```bash
.venv/bin/python main.py
```
Porta `8080`, `reload=False`, `show=False`. No boot, `inicializar_bancos()` cria os `db_mod_*` em WAL. Acesse **http://localhost:8080**.

## 3. Primeiro acesso (seed)

- `master` / `master` — troca obrigatória de senha aplicada automaticamente no 1º logon (`mod_gest_cad_usuario/manipulador_bd.py:136-156`). Recomenda-se alterar manualmente.

## 4. Usuários de teste

| Usuário | Senha | Perfil | Módulos |
|:---|:---|:---|:---|
| `qacomum` | `123456` | `comum` | blog, editar_pdf, empenhos |
| `qamaster` | `123456` | `administrador_geral` | todos |

> **Perfis do sistema** — existem exatamente três (constante `PERFIS_GLOBAIS` em `mod_gest_cad_usuario/manipulador_bd.py:15`): `comum`, `administrador_modulo` e `administrador_geral`. Não há perfis "administrador", "almoxarife" ou "operador". O acesso por módulo é controlado por papel (`comum`/`administrador`) em `tb_acesso_usuario`; `administrador_geral` obtém papel `administrador` em todos os módulos e acesso exclusivo a `/auditoria`.

## 5. Smoke test

```bash
.venv/bin/python test/test_server.py
```

## Documentação local (MkDocs)

```bash
.venv/bin/python -m mkdocs serve   # http://localhost:8000
.venv/bin/python -m mkdocs build   # gera site/
```

Veja [Manual do Administrador](../manual_de_uso_administrador/index.md) e [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md).
