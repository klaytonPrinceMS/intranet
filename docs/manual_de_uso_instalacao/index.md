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

### 2.1 Assistente de ativação (boot)

Ao iniciar o `main.py` sem argumentos, o **assistente de ativação** (`mod_intranet/ativacao.py`) é exibido no terminal com dois caminhos:

- **Pressione ENTER** (ou rode em terminal não interativo / CI) → **modo BÁSICO**: sobe **apenas SQLite**, **sem PostgreSQL e sem OpenTelemetry** — boot rápido e autossuficiente. O padrão **ignora** a `tb_config` central (`_config_padrao()`, `ativacao.py:167` — `otel_ativo: False`; removidos `_config_persistida` e `preparar_servicos_padrao`).
- **Pressione `1` + ENTER** → **modo de ativação/configuração** (`iniciar()`, `ativacao.py:805`): o assistente pergunta, em sequência:
  1. **Banco de dados** — **ENTER/`0` = SQLite (básico)** | **`1` = PostgreSQL** (`_escolha_1_enter`, `ativacao.py:673` — `iniciar():845`). No caminho SQLite os serviços ficam **desativados** (sem perguntas de porta); no PostgreSQL os serviços vêm **ativos por padrão**;
  2. **Subir/ativar o PostgreSQL (container)? [1 = ativar | ENTER/0 = não]** (`_sim_nao`, `ativacao.py:696` — `iniciar():850`) — se ativar, pergunta a **porta** (padrão 5432) e monta o DSN `postgresql+psycopg2://intranet:intranet@localhost:<porta>/intranet`;
  3. **Subir/ativar o OpenTelemetry (Grafana+Loki+Tempo+Mimir)? [1 = ativar | ENTER/0 = não]** (`iniciar():866`) — se ativar, pergunta a **porta do Grafana** (padrão 3000) e instala o SDK OTel via pip quando ausente (`_garantir_sdk_otel`, `:623`);
  4. **Porta do SITE** (aplicação — padrão 8080);
  5. **Porta da DOCUMENTAÇÃO** (mkdocs — padrão 8000), **separada da porta do site** desde 11/09.

**Todas as perguntas binárias aceitam apenas `1` (ativar/configurar) ou ENTER/`0` (não/básico)** — respostas `sim`/`nao`/`s`/`n` e textos (`sqlite`/`postgres`) **não são mais aceitos**. O prompt inicial **repete até uma resposta válida** (apenas ENTER ou `1`; qualquer outra resposta re-pergunta — `iniciar():821-834`). As perguntas binárias usam os helpers estritos `_escolha_1_enter` (`ativacao.py:673`) e `_sim_nao` (`:696`): qualquer tecla diferente de `1`/ENTER/`0` (ex.: `s`, `sim`, `nao`, `x`) exibe o aviso `Opção inválida — digite 1 para <rotulo_1> ou apenas ENTER para <rotulo_padrao>.` e **repete a pergunta** até uma entrada válida; `EOFError`/`Ctrl+C` caem no padrão (sem loop infinito). As demais perguntas (portas) também **repetem até resposta válida** — ENTER usa o padrão, valor inválido re-pergunta (`perguntar()`, `:104`); portas são validadas na faixa 1–65535 (`_porta_valida`, `:138`). A escolha do OTel é persistida na `tb_config` (`set_config("otel_ativo", ...)`) — a opção "não" sobrevive ao restart.

**Exemplo — porta em uso (Postgres nativo na 5432):**

```text
$ .venv/bin/python main.py
  (banner) ...
  Pressione ENTER para entrar no modo BÁSICO — Banco SQLite, sem Grafana
  Pressione 1 + ENTER para configurar estes itens
> 1

===== MODO DE ATIVAÇÃO / CONFIGURAÇÃO =====
Banco de dados [1 = PostgreSQL | ENTER/0 = SQLite (básico)]: 1

Ativação dos serviços (independentes entre si):
  Subir/ativar o PostgreSQL (container)? [1 = ativar | ENTER/0 = não]: s
  Opção inválida — digite 1 para ativar ou apenas ENTER para não ativar.
  Subir/ativar o PostgreSQL (container)? [1 = ativar | ENTER/0 = não]: 1
  A porta padrão 5432 está em uso. Portas em uso no servidor:
    5432: postgres
    3000: grafana
  Portas livres (exemplos): 5433, 5434, 5435
  Porta do PostgreSQL (padrão 5432): 5444
  Subir/ativar o OpenTelemetry (Grafana+Loki+Tempo+Mimir)? [1 = ativar | ENTER/0 = não]: 0
  Porta do SITE (aplicação) (padrão 8080): 
  Porta da DOCUMENTAÇÃO (mkdocs) (padrão 8000): 
```

**Detecção de porta em uso (11/09):** quando a porta padrão do serviço (5432/3000) está ocupada, o assistente mostra o aviso completo de **`_msg_porta_em_uso(porta)`** (`ativacao.py:190`): **TODAS as portas em uso no servidor com o serviço de cada uma** (scanner local de `mod_intranet/port_scanner.py` — `ss -ltnp`/`lsof` no Linux, `netstat -ano` no Windows, enriquecido com `docker ps`; processos sem permissão aparecem como `desconhecido`) + **exemplos de portas livres** (`_portas_livres`, `ativacao.py:148`) antes de aceitar a porta digitada (`iniciar():988-1008`). O mesmo aviso completo é usado no retry de `_executar_e_persistir` (`:1039-1044`). Ao subir, se a porta continua ocupada, o assistente pede OUTRA porta, reescreve o compose (`aplicar_portas`, `:315` — regex sobre `"<orig>:5432"`/`"3000:..."`), roda `docker-compose down` + `up -d` e aguarda o serviço online com **até 5 tentativas** (`_executar_e_persistir():1054`); se não subir de verdade, cai em **fallback SQLite** confirmado explicitamente por `_confirmar_fallback_sqlite` (`:825`). A conexão é confirmada por `_verificar_postgres(dsn)` (`:490`), que remove o sufixo SQLAlchemy `+psycopg2` (psycopg2 só entende `postgresql://`).

**Reuso de containers Docker (11/09):** se o container `intranet_postgres` (ou a stack OTel `intranet-grafana/loki/tempo/mimir/otel-collector`) **já está rodando**, o assistente **apenas CONECTA** — ajusta a porta/DSN e valida a acessibilidade — **sem baixar imagens nem subir container de novo** (`_postgres_docker_ativo`, `ativacao.py:204`; `_otel_docker_ativo`, `:224`; `iniciar_postgres`, `:668`; `iniciar_stack_otel`, `:741`). Quando é preciso subir, `iniciar_postgres`/`iniciar_stack_otel` abrem **um terminal próprio para cada docker** que executa `cd <dir> && docker compose pull && docker compose up -d && docker logs -f <container>` — o usuário vê o pull e depois os logs ao vivo (`:700-705`, `:766-771`); sem terminal disponível, o pull + `up -d` rodam no console principal (`_pre_pull`, `:656`).

### 2.2 Inicialização por linha de comando (Typer)

Sem assistente, é possível configurar e subir direto por argumentos (**Typer**):

```bash
.venv/bin/python main.py --help
.venv/bin/python main.py --postgres --portapostgres 5444 --otel --portatelemetria 3000 --portasite 8080 --portadocumentacao 8001
.venv/bin/python main.py --scan-ports   # lista portas/serviços locais e encerra (exit 0)
```

| Flag | Padrão | Efeito |
|:---|:---|:---|
| `--postgres` | desligado | usa PostgreSQL (sobe o container) em vez do SQLite |
| `--portapostgres` | `5432` | porta do PostgreSQL (a 5432 costuma estar ocupada por um Postgres nativo — use outra, ex.: 5444) |
| `--otel` | desligado | ativa o OpenTelemetry (Grafana+Loki+Tempo+Mimir) |
| `--portatelemetria` | `3000` | porta do painel Grafana/telemetria |
| `--portasite` | `8080` | porta do **site/aplicação** (separada da documentação) |
| `--portadocumentacao` | `8000` | porta da **documentação (mkdocs)**, separada do site (padrão 8000; o site fica em 8080) |
| `--scan-ports` | desligado | lista as **portas em uso no servidor e o serviço de cada uma** (segurança/instalação, apenas localhost) e **encerra com exit 0** |

- `--help` explica cada chamada **em PT-BR** e encerra.
- **Sem argumentos**, o assistente interativo assume (ver 2.1).
- Com flags, `main.py:36-39` monta `ativacao.config_do_cli(**ativacao.cli_opcoes())` e sobe direto (`iniciar(cli_cfg=...)`, `ativacao.py:939`), reaproveitando o mesmo `_executar_e_persistir(cfg)` (`:1028`) do assistente.
- `--scan-ports` é processado em `cli_opcoes()` (`ativacao.py:885`): imprime `port_scanner.resumo_portas()` (`port_scanner.py:144`) e sai com **exit 0** (`:902-905`) — mesmo escopo do assistente: apenas `127.0.0.1`, nunca redes externas.
- Valores de porta fora da faixa 1–65535 caem no padrão (`_porta_valida`).

## 3. Primeiro acesso (seed)

- `master` / `master` — troca obrigatória de senha aplicada automaticamente no 1º logon (`mod_gest_cad_usuario/bd_manipulador.py:136-156`). Recomenda-se alterar manualmente.

## 4. Usuários de teste

| Usuário | Senha | Perfil | Módulos |
|:---|:---|:---|:---|
| `qacomum` | `123456` | `comum` | blog, editar_pdf, empenhos |
| `qamaster` | `123456` | `administrador_geral` | todos |

> **Perfis do sistema** — existem exatamente três (constante `PERFIS_GLOBAIS` em `mod_gest_cad_usuario/bd_manipulador.py:15`): `comum`, `administrador_modulo` e `administrador_geral`. Não há perfis "administrador", "almoxarife" ou "operador". O acesso por módulo é controlado por papel (`comum`/`administrador`) em `tb_acesso_usuario`; `administrador_geral` obtém papel `administrador` em todos os módulos e acesso exclusivo a `/auditoria`.

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
