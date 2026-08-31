# Common User Manual — Intranet Modular



---

# Manual de Uso — Usuário Comum — Intranet Modular

> Guia operacional para o perfil `comum` (e usuários liberados em módulos): o que é visível e permitido nos módulos Blog, Editor de PDF e Empenhos. Este manual cobre o perfil **`comum`** (antigamente chamado de "operador"); o sistema não possui perfil "operador".

## Acesso

- O `comum` vê apenas os módulos expressamente liberados (ex.: `qacomum` → blog, editar_pdf, empenhos).
- Login em `/login`; sessão via cookie; logout encerra apenas o dispositivo atual.

## Blog (`/blog`)

- Leitura de publicações e histórico (somente leitura).
- Controles de criação/edição/exclusão/comentário ficam ocultos **e** bloqueados no backend para `comum`.

## Editor de PDF (`/edit-pdf`)

- Upload de `.pdf` (até 10 arquivos / 1 GB por lote; cota de 10 arquivos `upload` simultâneos).
- Operações sobre a seleção: reduzir, juntar, cortar, dividir, verificar integridade, ZIP, excluir.
- Arquivos expiram em 10 min (`M:SS` na coluna "Expira em"); cada usuário vê apenas os próprios.

## Renomeador de Empenho (`/renomear-empenho`)

- Pesquisar documentos monitorados; solicitar envio por e-mail ou download ZIP (se o admin autorizar).
- Visualizar/baixar PDFs conforme autorização do administrador do módulo.
- Fluxo completo de almoxarifado (não é um perfil): ver [Manual do Renomeador de Empenho](../manual_de_uso_renomear_empenho/index.md).

## Solicitação de Impressão (`/solicita-impressao`)

- Enviar PDF, preencher fórmula (páginas = qtd × cópias × fator), rascunho com expiração, autorização por responsável, acompanhamento de cota.

Veja [Manual do Administrador](../manual_de_uso_administrador/index.md) para permissões e [Padrões de Codificação](../padroes_codificacao/index.md).
