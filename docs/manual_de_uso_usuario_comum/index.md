# Common User Manual — Intranet Modular



---

# Manual de Uso — Usuário Comum — Intranet Modular

> Guia operacional para o perfil `comum` (e usuários liberados em módulos): o que é visível e permitido nos módulos Blog, Editor de PDF e Empenhos. Este manual cobre o perfil **`comum`** (antigamente chamado de "operador"); o sistema não possui perfil "operador".

## Acesso

- O `comum` vê apenas os módulos expressamente liberados (ex.: `qacomum` → editar_pdf, empenhos, solicita_impressao — SEM blog, removido do seed vigente).
- Login em `/login`; sessão via cookie; logout encerra apenas o dispositivo atual.

## Estilo visual (rodapé da tela)

- A **tela de login é sempre a mesma** para todo mundo (padrão `verde`, na estética do WhatsApp).
- Dentro dos módulos, a escolha de estilo fica no **rodapé**, que aparece quando o mouse passa na
  **faixa de 5 px** na base da janela (ou por `Tab`/toque). As opções são **Azul**, **Verde**,
  **Roxo**, **Preto** e **Padrão**.
- O menu fica **exatamente no meio** da faixa do rodapé, entre o nome do sistema (à esquerda) e a
  versão (à direita), que continuam aparecendo normalmente.
- A escolha vale **só neste navegador e neste computador** — não viaja para outra máquina, e outro
  login no mesmo aparelho tem a própria escolha.
- **"Padrão"** significa **"não impor cor nenhuma"**: a tela fica com a cor que o **administrador
  configurou para aquele módulo** (por padrão, o preto do sistema). Não é o mesmo que escolher um
  estilo — é o contrário disso. É por isso que, nesse caso, o rótulo à direita do menu mostra
  **"cor do módulo"** em vez do nome de um estilo.
- Trocar o estilo **não** tira você da página nem do módulo em que está, e **não** precisa reiniciar
  o servidor. Detalhe técnico em [Estilo Visual e Tema do Sistema](../estilo_visual.md).

## Blog (`/blog`)

- Leitura de publicações e histórico (somente leitura).
- Controles de criação/edição/exclusão/comentário ficam ocultos **e** bloqueados no backend para `comum` (publicar é exclusivo do administrador — ver [Manual do Administrador](../manual_de_uso_administrador/index.md), seção "Blog — publicar com o editor WYSIWYG").
- Postagens podem conter **imagens** (exibidas no corpo do texto, ajustadas à largura do card) e **diagramas Mermaid** (bloco ```mermaid ... ```) renderizados no navegador — o `comum` apenas visualiza.

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
