# Intranet Modular — Documentation Index

> Central index of the technical documentation for the Intranet Modular (NiceGUI) of the Prefeitura Municipal de Monte Santo de Minas. Each entry links to a focused document; the convention is an English summary followed by the Portuguese (Brazil) summary at the top of every page.

---

# Intranet Modular — Índice de Documentação

> Índice central da documentação técnica da Intranet Modular (NiceGUI). Cada entrada aponta para um documento focado; o padrão adotado é um resumo em inglês seguido do resumo em português (Brasil) no topo de cada página.

## Sumário

- [Introdução](intro.md) — o que é o sistema, contexto e público-alvo.
- [Visão Geral](visao_geral.md) — módulos, fluxo de alto nível e perfis de usuário.
- [Guia de Início Rápido](inicio_rapido.md) — instalação do `.venv`, subir o servidor e primeiros acessos.
- [Requisitos do Sistema](requisitos.md) — SO, Python, dependências e restrições de rede.
- [Configurações e Variáveis de Ambiente](configuracoes.md) — `storage_secret`, portas, caminhos de banco e parâmetros do `main.py`.
- [Arquitetura](arquitetura.md) — entry point, separação em módulos e agendadores.
- [Referência de API e Código](api_referencia.md) — rotas, funções-chave (`arquivo:linha`) e tabelas por módulo.
- [Convenções de Criação de Código](convencoes_codigo.md) — nomenclatura, modelo de módulos e padrões de tela/banco.
- [Módulos](modulos/) — um documento de análise por módulo:
  - [Intranet (núcleo)](modulos/intranet.md)
  - [Gestão de Cadastro de Usuários](modulos/gest_cad_usuario.md)
  - [Blog](modulos/blog.md)
  - [Edição de PDF](modulos/edit_pdf.md)
  - [Renomeador de Empenho](modulos/renomear_empenho.md)
  - [Auditoria](modulos/auditoria.md)
  - [Solicitação de Impressão](modulos/solicitacao_impressao.md)

## Documentos-raiz de apoio

- `README.md` — cartão de visitas do projeto.
- `PLANO.md` — checklist por fases de implementação.
- `analise.md` — levantamento de requisitos e notas de engenharia.
- `AGENTS.md` — regras de edição e perfis de IA (QA, documentação).

## Padrão de documentação

1. Cabeçalho **Inglês + Português do Brasil** no topo de cada página.
2. Sumário no topo de documentos longos.
3. Seções com headings consistentes, tabelas para dados estruturados e blocos de código com linguagem explícita.
4. Links relativos entre documentos.
5. Em conflito de informação, prevalece o código executável sobre a documentação.
