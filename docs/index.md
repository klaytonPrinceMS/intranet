# Intranet Modular — Technical Documentation

> Central index of the Intranet Modular (NiceGUI) engineering documentation for the Prefeitura Municipal de Monte Santo de Minas. This site follows the "Documentos de Engenharia de Software" standard (MkDocs Material): every page carries an English summary followed by the Portuguese (Brazil) summary, and is organized into per-topic folders.

---

# Intranet Modular — Documentação Técnica

> Índice central da documentação de engenharia da Intranet Modular (NiceGUI) da Prefeitura Municipal de Monte Santo de Minas. Este sítio segue o padrão "Documentos de Engenharia de Software" (MkDocs Material): cada página traz um resumo em inglês seguido do resumo em português (Brasil) e é organizada em pastas por tema.

## Documentos de Engenharia de Software

- [Visão de Produto](visao_de_produto/index.md) — o que é, contexto, público, módulos
- [Levantamento de Requisitos](2_levantamento_requisitos/index.md) — RFs funcionais/não funcionais e backlog
- [Arquitetura de Software (DAS)](arquitetura_de_software_das/index.md) — entry point, pacotes, bancos WAL, agendadores
- [Guia de API](guia_API/index.md) — rotas, funções-chave (`arquivo:linha`), tabelas por módulo
- [Padrões de Codificação](padroes_codificacao/index.md) — nomenclatura, modelo de módulo, telas e banco
- [Manual de Instalação](manual_de_uso_instalacao/index.md) — setup do `.venv`, subir o servidor, primeiros acessos
- [Manual do Administrador](manual_de_uso_administrador/index.md) — perfis `administrador_geral` e `administrador_modulo` (config, usuários, auditoria, observabilidade)
- [Manual do Usuário Comum](manual_de_uso_usuario_comum/index.md) — perfil `comum` (Blog, PDF, Empenhos)
- [Manual do Renomeador de Empenho](manual_de_uso_renomear_empenho/index.md) — fluxo de almoxarifado (perfil `comum`) no renomeador de empenho
- [Plano de Projeto](plano_de_projeto/index.md) — fases e checklist (de `PLANO.md`)
- [Registro de Mudanças](registro_de_mudancas/index.md) — realizados/parciais/pendentes (backlog)
- [Versionamento](versionamento/index.md) — esquema `1.0.AAMMDD` e versões de módulo
- [Análise de Risco](analise_de_risco/index.md) — riscos conhecidos (semente)
- [Métricas de Software](metricas_software/index.md) — cobertura de testes (semente)
- [Lições Aprendidas](licoes_aprendida/index.md) — aprendizados do desenvolvimento (semente)
- [Contribuições](contribuicoes/index.md) — como adicionar módulo/alterar
- [Testes — Casos](testes_casos/index.md) — scripts em `test/`
- [Testes — Plano](testes_plano/index.md) — plano por fluxo
- [Testes — Relatórios](testes_relatorios/index.md) — resultados de execução (semente)

## Análises por módulo (detalhe)

- [Intranet (núcleo)](analise_mod_intranet.md)
- [Gestão de Cadastro de Usuários](analise_mod_gest_cad_usuario.md)
- [Blog](analise_mod_blog.md)
- [Edição de PDF](analise_mod_edit_pdf.md)
- [Renomear Empenho](analise_mod_renomear_empenho.md)
- [Auditoria](analise_mod_auditoria.md)
- [Solicitação de Impressão](analise_mod_solicita_impressao.md)

## Documentos-raiz de apoio

- `README.md` (cartão de visitas) · `PLANO.md` (checklist por fases) · `analise.md` (requisitos/roadmap) · `AGENTS.md` (regras de edição/IA)

## Convenção

Em conflito de informação, prevalece o código executável sobre a documentação. Cabeçalho EN+PT-BR em todas as páginas.
