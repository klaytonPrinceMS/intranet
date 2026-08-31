# Product Vision — Intranet Modular

> What the system is, its context, target audience and the modules in operation. Companion to the [Requirements](../2_levantamento_requisitos/index.md).

---

# Visão de Produto — Intranet Modular

> O que é o sistema, seu contexto, público-alvo e os módulos em operação. Complementar ao [Levantamento de Requisitos](../2_levantamento_requisitos/index.md).

## O que é

Sistema intranet modularizado (NiceGUI/FastAPI) da Prefeitura Municipal de Monte Santo de Minas, que centraliza o acesso a módulos Python interoperáveis em um único hub autenticado, restrito à rede local, com auditoria centralizada (LGPD).

## Contexto

- **Órgão:** Prefeitura Municipal de Monte Santo de Minas — DTI.
- **Base legal:** Lei Municipal n.º 1.570/2007; conformidade LGPD.
- **Autor:** PRINCE, K.B.

## Público-alvo

- Desenvolvedores que estendam/mantenham módulos.
- Administradores gerais e de módulo (operação).
- Equipes de auditoria e conformidade.

## Módulos em operação

`mod_intranet` (núcleo), `mod_gest_cad_usuario`, `mod_blog`, `mod_edit_pdf`, `mod_renomear_empenho`, `mod_auditoria`, `mod_solicita_impressao`.

## Propósito de negócio

Hub centralizador de acesso, gestão de identidade (soft CRUD, LGPD), comunicação (Blog), manipulação de PDF, gestão de empenhos e solicitação de impressão — tudo com trilha de auditoria unificada.

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Manual de Instalação](../manual_de_uso_instalacao/index.md).
