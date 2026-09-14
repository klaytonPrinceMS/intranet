# Manual de Uso — Administrador — Intranet Modular

> Guia operacional para `administrador_geral` e `administrador do módulo`: configurações, gestão de usuários, auditoria e observabilidade.

## Perfis do sistema

O sistema possui exatamente **três perfis globais** (campo `user_perfil` em `tb_usuarios`, constante `PERFIS_GLOBAIS` em `mod_gest_cad_usuario/bd_manipulador.py:15`):

| Perfil | Chave técnica | Acesso |
|:---|:---|:---|
| Administrador geral | `administrador_geral` | Acesso total a todos os módulos; único perfil com acesso a `/configuracoes`, `/users` e `/auditoria` (RF-35). |
| Administrador de módulo | `administrador_modulo` | Acesso restrito aos módulos que gerencia (vinculados com papel `administrador`). |
| Comum | `comum` | Acesso limitado às funcionalidades básicas dos módulos que lhe são liberados. |

> Importante: **não existem perfis "administrador", "almoxarife" nem "operador"** no sistema. O termo "administrador do módulo" (papel por módulo, `PAPEIS_MODULO = ["comum", "administrador"]`) é o papel que um usuário — normalmente `administrador_modulo` — exerce dentro de um módulo específico. A função de almoxarifado não é um perfil, e sim um fluxo do módulo Renomeador de Empenho disponível ao usuário `comum` autorizado. Veja o [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md).

## Acesso

- `administrador_geral`: vê todos os módulos, incluindo `/configuracoes`, `/users` e `/auditoria`.
- `administrador_modulo` (administrador do módulo): alteração/restrição limitada aos módulos vinculados.

## Dashboard `/` — Home redesenhada (09/2026, Water escopado só no card)

- **Sem botão Atualizar** — o Resumo é recalculado **a cada acesso** (`_orquestrar_resumo_dados()` `main.py:250`): sem `lbl_fb_resumo/atualizar_resumo`, altura `gap-1 px-2 py-1` ícone 36px (`home_visual.injetar_water_card()` `home_visual.py:176` `.home-resumo-water/.home-stat-water` border `#dfe8f0` bg `#fafcfd`, `page_dashboard` fixa `modelo="water"` `main.py:502`), tooltip único no card (`Usuarios/Sessões/Noticias/Logs/Visitas/Fila geral/Para autorizar/Quarentena/PDFs/Auditoria 24h` + `Logs>9999` alerta backup `db_mod_auditoria.db`).
- **"Resumo do sistema"** (8 métricas, **só `administrador_geral`/`administrador_modulo`**): Usuários, Sessões, **Visitas** (`contador_acessos_total` — só logins, `bd_conexao.incrementar_contador_acessos()` `main.py:229`, `contador_acessos_inicio` `YYYY-MM-DD` tooltip simplificado `"Visitas"`), Postagens, Quarentena pendente (`tb_quarentena processado=0`), PDFs ativos (`tb_arquivos ativo=1`), Logs, Auditoria 24h (`SUM WHERE timestamp >= -1 day`).
- **"Resumo do sistema — Impressão"** (2 métricas, **só autorizador** `tb_responsaveis_autorizacao ativo=1` via `_eh_autorizador_impressao()` `main.py:446` **ou `administrador_geral`**): Fila geral e Para autorizar (por secretaria/setor, `main.py:460` `_contar_fila_para_autorizar()`; admin geral = fila geral). Serviço `http://localhost:8080` water OK; comparativo `/home-*` revertido e hambúrguer sem seção comparativa.

## Configurações (`/configuracoes`, apenas geral)

- Personalização: cor primária, título, ícones, botões do sistema (cor/texto/tamanho), pasta raiz.
- **Páginas do sistema — ordem do menu (aba Módulo, 14/09/2026)**: a lista é ÚNICA e reordenável com ↑/↓ (salva de imediato). Ordem padrão: `Blog → Editor PDF → Empenhos → Solicitação de Impressão → Usuários → Auditoria` (vale para instalações novas e "Restaurar padrão"). Após reordenar, a ordem **permanece após reinícios** — personalização nunca é sobrescrita no boot.
- Banco de dados (aba **Config**, ao final, após "Ícones"): card **"Banco de dados — SQLite ou PostgreSQL"** — SQLite é o padrão; PostgreSQL é opcional. A troca **exige reiniciar o servidor** (sem reload ao aplicar).
- Observabilidade (loguru + OTel): nível, rotação, retenção, compressão, console (auto/sempre/nunca), envio ao Loki; endpoint OTLP local ou remoto, stack local (Docker) ou dedicada, URL do Grafana; "Limpar TODOS os logs". Troca de endpoint/OTel exige restart.
- Backup: chave `backup_horas:<modulo>` (padrão 12 h); `backup_interval_horas` e `sessao_retencao` (roadmap).
- **Blog — diagramas Mermaid**: no admin do módulo (`/admin/blog` → "Configurações específicas") o switch **"Permitir diagramas Mermaid (```mermaid) nas postagens"** liga/desliga a renderização de blocos ```mermaid ... ``` nas postagens (habilitado por padrão, chave local `blog_habilitar_mermaid`).

## Blog — publicar com o editor WYSIWYG (admin, 14/09/2026)

- Só o administrador geral e o administrador do módulo `blog` veem o card **"Nova publicação"** em `/blog` (o `comum` tem somente leitura — controles ocultos e bloqueados no backend).
- **Escrever**: preencha **Título\*** e o **editor** (recebe com `Olá, <seu nome>! ...`). Use a barra de ferramentas para negrito/itálico/listas/links, ou digite HTML simples/Markdown leve e blocos ```mermaid. **Markdown funciona dentro do editor**: linhas como `# Título`, `## Seção`, `- item` e `**negrito**` são convertidas ao publicar/pré-visualizar (o editor gera a 1ª linha solta e as demais em `<div>`, preservadas na sanitização); blocos de código (`code`/`pre`) não são convertidos e `#hashtag` no meio do texto não vira título. **Atenção — `#` exige espaço**: `# Título` vira título, mas `#texto` (sem espaço) fica literal — padrão CommonMark, como no GitHub.
- **Anexar imagem**: clique em **"Selecionar imagem (JPG/PNG, até 5 MB)"**, escolha o arquivo e clique em **Enviar** — a imagem entra no texto na posição do cursor (redimensionada para a largura do card). Só `.jpg`/`.jpeg`/`.png` de até 5 MB; outro formato ou arquivo inválido mostra aviso e não entra no texto.
- **Ajustar a imagem (alinhar/redimensionar)**: na linha **"Imagem:"** abaixo do upload, use os botões **esquerda/centro/direita** para alinhar e o seletor **"Largura da imagem"** (25%, 50%, 75%, 100% ou Original 200–400px) para redimensionar — sempre aplicados à **última imagem** do texto (envie primeiro, ajuste depois; repita a cada imagem). O restante da formatação que você aplicou é preservado. Sem imagem no texto, os botões avisam "Nenhuma imagem no texto — envie uma primeiro".
- **Pré-visualizar / publicar**: confira em **Pré-visualização** (o que aparece é o que o leitor vê, já sanitizado), depois **Publicar** (ou **Salvar** ao editar, **Cancelar** para limpar). Para editar, use o ícone de lápis no rodapé do card; para retirar do ar, **despublicar** (a postagem vai para a aba **Despublicadas**, de onde pode ser republicada); **excluir** é lógico (`ativo=0`).
- Imagens enviadas e **não usadas** em nenhuma postagem são apagadas sozinhas após **5 min** (limpeza automática a cada 1 min) — publique em seguida ou reenvie.

## Gestão de Usuários (`/users`, admin de módulo/geral)

- CRUD soft: criar, alterar, bloquear, desbloquear, soft delete (com motivo), restauração.
- Perfis por módulo (`administrador_geral`, `administrador do módulo`, `comum`); controle granular.
- Senha provisória para novos usuários + troca no 1º acesso.
- Proteções: não bloquear/rebaixar a própria conta; último `administrador_geral` protegido; `master` não pode ser excluído/renomeado.
- Exclusão em dois estágios (LGPD): lógica (reversível) → permanente (aba `Excluídos`, só geral).

## Auditoria (`/auditoria`, apenas geral)

- Leitura/filtro da trilha de auditoria (banco exclusivo `db_mod_auditoria.db`, uma tabela por módulo) por data, hora, usuário, tipo de ação e módulo.
- Colunas IP e resumo de dispositivo.

## Observabilidade e Logs

- `mod_intranet/observabilidade.py`: logs por módulo em `logs/`, captura de exceções (`excepthook`), reconfiguração em runtime; telemetria OTel com endpoint local ou remoto (`otel_endpoint`) e URL do Grafana configuráveis.

## Sessões

- Encerrar sessões ativas individualmente ou em massa (usuário deslogado na próxima interação).

Veja [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md) e [Arquitetura](../arquitetura_de_software_das/index.md).
