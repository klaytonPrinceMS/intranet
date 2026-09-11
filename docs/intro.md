# Intranet Modular — Introduction

> The Intranet Modular is a corporate intranet built with Python 3.12 + NiceGUI 3.15 for the rede interna. It runs only on the internal network (no CDN), uses one SQLite (WAL) database per module, has an LGPD audit trail (exclusive audit database, one table per module) and modular packages (`mod_*`). This page describes what the system is, its context and target audience.

---

# Intranet Modular — Introdução

> A Intranet Modular é uma intranet corporativa desenvolvida em Python 3.12 + NiceGUI 3.15 para a rede interna. Roda apenas na rede interna (sem CDN), usa um banco SQLite (WAL) por módulo, possui trilha de auditoria LGPD (banco exclusivo de auditoria, uma tabela por módulo) e pacotes modulares (`mod_*`). Esta página descreve o que é o sistema, seu contexto e o público-alvo.

## Sumário

1. [O que é o sistema](#o-que-e-o-sistema)
2. [Contexto](#contexto)
3. [Público-alvo](#publico-alvo)
4. [Organização da documentação](#organizacao-da-documentacao)

## O que é o sistema

A **Intranet Modular** é um software de servidor para **rede interna** (intranet) da rede interna. Foi desenvolvida pelo Analista de Sistemas **PRINCE, K.B.** e versionada no padrão `1.0.AAMMDD` (atual: `1.0.260908` — seed `versao_sistema` em `tb_config`).

Características centrais:

| Característica | Descrição |
|:---|:---|
| Framework web | **NiceGUI 3.15** (FastAPI/WebSockets) servido localmente |
| Interface | Tailwind CSS **servido localmente** (sem CDN — rede interna) |
| Persistência | **SQLite em modo WAL**, um banco por módulo (`db_mod_*`) |
| Autenticação | Login com **bcrypt** + sessões revogáveis (cookie HTTP-Only) |
| Auditoria | Trilha LGPD em banco exclusivo (`db_mod_auditoria.db`, uma tabela por módulo — IP, user-agent, dispositivo, hash SHA-256) |
| Automação | APScheduler: backups por módulo (12 h), cleanups (1 min), monitor de pasta (60 s), poda da auditoria (24 h) |
| Documentação | MkDocs embutido e servido na própria aplicação em `/documentacao` |

O sistema é **modular por pacote**: cada funcionalidade vive em um pacote `mod_<nome>` com banco próprio e tela própria, integrados a um núcleo (`mod_intranet`) que centraliza autenticação, configurações, auditoria e agendamentos.

## Contexto

O sistema nasceu da necessidade de organizar processos internos da prefeitura em uma única plataforma acessível pela rede interna:

- **Comunicação interna** — publicação de avisos e novidades (Blog).
- **Gestão de acesso** — cadastro de usuários com perfis e papéis granulares por módulo.
- **Arquivo físico/digital** — renomeação automática de empenhos (PDFs) e organização em caixas/subpastas.
- **Ofimática** — edição de PDFs (reduzir, juntar, cortar, dividir) em espaço temporário por usuário.
- **Serviços administrativos** — solicitação de impressão com cotas mensais hierárquicas e autorização.
- **Governança** — auditoria central de todas as ações relevantes (LGPD) e observabilidade (loguru).

Tudo roda **em uma única aplicação** (entry point `main.py`, porta `8080`), sem necessidade de infraestrutura externa além do servidor local.

## Público-alvo

| Público | Interesse | Documentos recomendados |
|:---|:---|:---|
| **Administradores do sistema** | implantar, configurar, resolver problemas | [Início Rápido](inicio_rapido.md), [Configurações](configuracoes.md), [Arquitetura](arquitetura.md) |
| **Desenvolvedores / mantenedores** | entender e alterar o código | [Arquitetura](arquitetura.md), [Referência de API](api_referencia.md), [Convenções de Código](convencoes_codigo.md), [Módulos](modulos/intranet.md) |
| **Usuários finais (servidores)** | usar as funcionalidades do dia a dia | [Visão Geral](visao_geral.md), [Módulos](modulos/intranet.md) (por módulo) |
| **Equipe de QA / testes** | validar fluxos e permissões | [Visão Geral](visao_geral.md) (perfis), usuários de teste `qacomum`/`qamaster` |

## Organização da documentação

- **Índice geral:** [index.md](index.md) (página inicial da build; o arquivo fonte `README.md` da pasta `docs/` não é publicado).
- **Visão macro:** [Visão Geral](visao_geral.md) — módulos, fluxos e perfis.
- **Operação:** [Início Rápido](inicio_rapido.md), [Requisitos](requisitos.md) e [Configurações](configuracoes.md).
- **Técnica:** [Arquitetura](arquitetura.md), [Referência de API e Código](api_referencia.md) e [Convenções de Criação de Código](convencoes_codigo.md).
- **Detalhe por módulo:** pasta `modulos/` — um documento conciso por módulo, compilado das análises completas (`analise_mod_*.md`).

> **Convenção:** em conflito entre documentação e código, prevalece o **código executável**.