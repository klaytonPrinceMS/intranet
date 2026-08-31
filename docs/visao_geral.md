# Intranet Modular — Visão Geral

> Visão de alto nível da Intranet Modular: os 7 módulos, o fluxo principal de uso (login → dashboard → módulos) e os 3 perfis de usuário (`comum`, `administrador_modulo`, `administrador_geral`) com papéis por módulo e validação de acesso.

## Sumário

1. [Objetivos](#objetivos)
2. [Módulos do sistema](#modulos-do-sistema)
3. [Fluxo de alto nível](#fluxo-de-alto-nivel)
4. [Perfis de usuário](#perfis-de-usuario)
5. [Autorização por módulo](#autorizacao-por-modulo)

## Objetivos

- Centralizar serviços internos da prefeitura em **uma única aplicação** acessível pela rede interna.
- Garantir **rastreabilidade** (auditoria central LGPD) de todas as ações relevantes.
- Permitir **evolução incremental**: cada funcionalidade é um módulo independente com banco próprio.
- Operar **sem internet**: interface com Tailwind local, bibliotecas empacotadas e documentação embutida.

## Módulos do sistema

O sistema é composto por um **núcleo** (`mod_intranet`) e **6 módulos de negócio**:

| Módulo | Chave | Rota | Banco | Função |
|:---|:---|:---|:---|:---|
| **Intranet (núcleo)** | `intranet` | `/`, `/login`, `/configuracoes`, `/documentacao` | `db_mod_intranet.db` | autenticação, sessões, auditoria central, configurações, backups, observabilidade |
| **Gestão de Usuários** | `usuarios` | `/users` | `db_mod_gest_cad_usuario.db` | CRUD soft de usuários, perfis, papéis por módulo, sessões ativas |
| **Blog** | `blog` | `/blog` | `db_mod_blog.db` | postagens/comentários HTML sanitizados (`nh3`) |
| **Editor de PDF** | `editar_pdf` | `/edit-pdf` | `db_mod_edit_pdf.db` | reduzir, juntar, cortar, dividir, verificar, ZIP — com cotas e expiração |
| **Renomear Empenhos** | `empenhos` | `/renomear-empenho` | `db_mod_renomear_empenho.db` | extração de texto, regex dinâmicas, FTS5, quarentena, renomeação sequencial, organizador |
| **Auditoria** | `auditoria` | `/auditoria` | — (lê o central) | visualização/filtro/exportação da `tb_auditoria` |
| **Solicitação de Impressão** | `solicita_impressao` | `/solicita-impressao` | `db_mod_solicita_impressao.db` | envio de PDF, contagem de páginas, cotas mensais, autorização, impressão |

> O cadastro real de módulos vive em `tb_modulos` (banco central), semeado por `MODULOS_SISTEMA` em `mod_intranet/autenticacao.py:15-22`.

## Fluxo de alto nível

```text
Usuário ──(/login)──▶ Autenticação bcrypt ──▶ Sessão revogável (tb_sessoes)
        ──▶ Dashboard "/" ──▶ Drawer lateral (módulos liberados)
        ──▶ /blog · /users · /edit-pdf · /renomear-empenho · /auditoria · /solicita-impressao
        ──▶ Auditoria central (tb_auditoria)
```

1. O usuário acessa `/login` e informa usuário/senha (`autenticar` → bcrypt).
2. Login bem-sucedido cria uma **sessão revogável** (`registrar_login`) amarrada a um cookie HTTP-Only (`cookie_hash`).
3. O usuário é levado ao **Dashboard** `/` (saudação + feed do Blog + estatísticas).
4. A navegação por módulos ocorre pelo **menu lateral** (drawer), que só mostra módulos liberados ao usuário.
5. Toda rota de módulo passa pela guarda `pagina_restrita` (autenticação + permissão + layout de 4 partes).
6. Ações relevantes gravam **auditoria central** (`audit_log`) com IP/user-agent/hash quando aplicável.
7. Em segundo plano, **APScheduler** executa backups por módulo, limpezas e monitor de pasta.

## Perfis de usuário

Existem **3 perfis globais** (coluna `user_perfil` de `tb_usuarios`):

| Perfil | Acesso | Exemplos de capacidades |
|:---|:---|:---|
| `comum` | módulos liberados (papel por módulo) | ler Blog, editar PDFs, renomear/consultar empenhos, solicitar impressão |
| `administrador_modulo` | admin de **módulos específicos** | gerenciar o módulo (publicar, imprimir, configurar aparência do módulo) |
| `administrador_geral` | **todos** os módulos + auditoria + configurações | ver tudo, excluir usuários (LGPD), configurar sistema, visualizar auditoria |

Além do perfil global, existe o **papel por módulo** (`tb_acesso_usuario`): vínculo `usuário × módulo × papel` (ex.: `comum` ou `administrador` dentro de `solicita_impressao`). A combinação perfil global + papel por módulo define o que aparece no menu e o que é aceito pela guarda.

### Perfis × módulos (visão resumida)

| Módulo | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Blog | somente leitura | criar/editar/publicar | tudo |
| Editor de PDF | usar editor | — | cotas/expiração (aba Administração) |
| Renomear Empenhos | processar/pesquisar/ZIP | regras/quarentena | tudo |
| Auditoria | ✗ | ✗ | somente este perfil |
| Configurações | ✗ | ✗ | somente este perfil |
| Gestão de Usuários | ✗ | admin do módulo `usuarios` | tudo |
| Solicitação de Impressão | solicitar/acompanhar | imprimir/gerenciar | tudo |

## Autorização por módulo

- A visibilidade no **menu lateral** usa `listar_modulos_permitidos` / `modulos_do_usuario`.
- O **gate de rota** usa `validar_acesso_modulo` (núcleo delega ao manipulador do módulo de usuários).
- Tentativa sem permissão gera `acesso_negado` na `tb_auditoria` (`layout_tela.pagina_restrita` — choke point único).
- Dentro de cada módulo, a tela valida novamente o papel antes de qualquer escrita (dupla camada UI + backend).

> Usuários de teste prontos: `qacomum`/`123456` (comum) e `qamaster`/`123456` (administrador_geral) — ver [Guia de Início Rápido](inicio_rapido.md).