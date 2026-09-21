# Product Vision — Intranet Modular

> What the system is, its context, target audience and the modules in operation. Companion to the [Requirements](../2_levantamento_requisitos/index.md).

---

# Visão de Produto — Intranet Modular

> O que é o sistema, seu contexto, público-alvo e os módulos em operação. Complementar ao [Levantamento de Requisitos](../2_levantamento_requisitos/index.md).

## O que é

Sistema intranet modularizado (NiceGUI/FastAPI) da rede interna, que centraliza o acesso a módulos Python interoperáveis em um único hub autenticado, restrito à rede local, com auditoria centralizada (LGPD).

## Contexto

- **Órgão:** DTI — Tecnologia da Informação.
- **Base legal:** Lei Municipal n.º 1.570/2007; conformidade LGPD.
- **Autor:** PRINCE, K.B.

## Público-alvo

- Desenvolvedores que estendam/mantenham módulos.
- Administradores gerais e de módulo (operação).
- Equipes de auditoria e conformidade.

## Módulos em operação

`mod_intranet` (núcleo) + 9 de negócio: `mod_gest_cad_usuario`, `mod_blog`, `mod_edit_pdf`, `mod_renomear_empenho`, `mod_auditoria`, `mod_solicita_impressao` (cotas 1000/200 via `ORGANOGRAMA_BASE`), `mod_tecnico` (**novo** 18/09/2026 — `software/` + `backup/YYYYMMDD_HHMM_nomePc_ip`, owner-isolation, `webkitdirectory`), `mod_filas` (multi-filas 09/2026 — `/filas` + `/tv` pública isolada/compartilhada/por sala, ordem da fala `voz_ordem`, volume 40, papel de fundo) e `mod_lista_telefonica` (**novo** 19/09/2026 — organograma 12 secretarias `Secretaria→Setor→Subsetor`, contatos alfabéticos, busca sem acentos, `tel:` no celular).

Total **10 módulos** (1 núcleo + 9 de negócio), semeados por `MODULOS_SISTEMA` em `mod_intranet/autenticacao.py:15-25` e `MODULOS_BD` em `mod_intranet/repositorio.py:57-68`.

## Propósito de negócio

Hub centralizador de acesso, gestão de identidade (soft CRUD, LGPD), comunicação (Blog), manipulação de PDF, gestão de empenhos e solicitação de impressão (cotas 1000/200), apoio de T.I. (software + backup owner-isolated), gestor de filas/TV e lista telefônica/organograma — tudo com trilha de auditoria unificada (banco exclusivo `db_mod_auditoria.db`, uma tabela por módulo).

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Manual de Instalação](../manual_de_uso_instalacao/index.md).
