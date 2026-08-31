# Manual de Uso — Administrador — Intranet Modular

> Guia operacional para `administrador_geral` e `administrador do módulo`: configurações, gestão de usuários, auditoria e observabilidade.

## Perfis do sistema

O sistema possui exatamente **três perfis globais** (campo `user_perfil` em `tb_usuarios`, constante `PERFIS_GLOBAIS` em `mod_gest_cad_usuario/manipulador_bd.py:15`):

| Perfil | Chave técnica | Acesso |
|:---|:---|:---|
| Administrador geral | `administrador_geral` | Acesso total a todos os módulos; único perfil com acesso a `/configuracoes`, `/users` e `/auditoria` (RF-35). |
| Administrador de módulo | `administrador_modulo` | Acesso restrito aos módulos que gerencia (vinculados com papel `administrador`). |
| Comum | `comum` | Acesso limitado às funcionalidades básicas dos módulos que lhe são liberados. |

> Importante: **não existem perfis "administrador", "almoxarife" nem "operador"** no sistema. O termo "administrador do módulo" (papel por módulo, `PAPEIS_MODULO = ["comum", "administrador"]`) é o papel que um usuário — normalmente `administrador_modulo` — exerce dentro de um módulo específico. A função de almoxarifado não é um perfil, e sim um fluxo do módulo Renomeador de Empenho disponível ao usuário `comum` autorizado. Veja o [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md).

## Acesso

- `administrador_geral`: vê todos os módulos, incluindo `/configuracoes`, `/users` e `/auditoria`.
- `administrador_modulo` (administrador do módulo): alteração/restrição limitada aos módulos vinculados.

## Configurações (`/configuracoes`, apenas geral)

- Personalização: cor primária, título, ícones, pasta raiz.
- Observabilidade (loguru): nível, rotação, retenção, compressão; "Limpar TODOS os logs".
- Backup: chave `backup_horas:<modulo>` (padrão 12 h); `backup_interval_hours` e `sessao_retencao` (roadmap).

## Gestão de Usuários (`/users`, admin de módulo/geral)

- CRUD soft: criar, alterar, bloquear, desbloquear, soft delete (com motivo), restauração.
- Perfis por módulo (`administrador_geral`, `administrador do módulo`, `comum`); controle granular.
- Senha provisória para novos usuários + troca no 1º acesso.
- Proteções: não bloquear/rebaixar a própria conta; último `administrador_geral` protegido; `master` não pode ser excluído/renomeado.
- Exclusão em dois estágios (LGPD): lógica (reversível) → permanente (aba `Excluídos`, só geral).

## Auditoria (`/auditoria`, apenas geral)

- Leitura/filtro de `tb_auditoria` por data, hora, usuário, tipo de ação e módulo.
- Colunas IP e resumo de dispositivo.

## Observabilidade e Logs

- `mod_intranet/observabilidade.py`: logs por módulo em `logs/`, captura de exceções (`excepthook`), reconfiguração em runtime.

## Sessões

- Encerrar sessões ativas individualmente ou em massa (usuário deslogado na próxima interação).

Veja [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md) e [Arquitetura](../arquitetura_de_software_das/index.md).
