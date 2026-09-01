# Blog Module — `mod_blog`

> Corporate blog module: route `/blog` (key `blog`) · own database `db_mod_blog.db` (WAL) · HTML sanitized with `nh3` · read-only for `comum` · central LGPD audit.

---

# Módulo Blog — `mod_blog`

> Módulo de blog corporativo: rota `/blog` (chave `blog`) · banco próprio `db_mod_blog.db` (WAL) · HTML sanitizado com `nh3` · somente-leitura para `comum` · auditoria central LGPD.

## Propósito

Blog corporativo para publicação de avisos, novidades e orientações. O usuário `comum` tem acesso **somente leitura** — publicar, comentar, editar e excluir são restritos ao administrador geral e ao administrador do módulo `blog`, validados na UI **e** no backend.

## Banco de dados

- **`tb_postagens`**: `id` PK, `titulo`, `conteudo` (gravado sanitizado), `autor`, `data_criacao`, `data_atualizacao`, `ativo` (soft delete / publicar).
- **`tb_comentarios`**: `id` PK, `postagem_id` FK CASCADE, `autor`, `conteudo` (sanitizado), `data_criacao`.
- **`tb_config` (local do módulo)**: chave-valor com os padrões do blog (`blog_modo_exibicao`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header`).

A configuração visual (cor/tamanho dos botões, cor de fundo/título e texto do cabeçalho) permanece na `tb_config` central (prefixo `blog_*` — `blog_cor_botao`, `blog_cor_texto_botao`, `blog_cor_fundo`, `blog_cor_titulo`, `blog_btn_tamanho`, `blog_texto_header`), no cupê **"Aparência"** da aba Administração, seguindo o padrão do módulo exemplo (Editor de PDF). A tela ocupa a área cheia (`w-full`).

## Funcionalidades

- **CRUD com soft delete e publicar/despublicar**: criar, editar, despublicar, republicar e excluir (lógica) postagens.
- **Sanitização nh3** na gravação **e** na renderização, com whitelist configurável (`blog_tags_permitidas`, CSV). Aceita `http`/`https`, URLs relativas e `data:` para imagens.
- **Formatação rica**: títulos centralizados/negrito, imagens à esquerda com largura configurável (min–max em px), texto justificado.
- **Conversores**: HTML simples e Markdown leve (`#`, `**negrito**`, `- item`).
- **Editor com pré-visualização** do conteúdo antes de publicar.
- **Modo de exibição**: histórico (lista completa DESC) **ou** publicação única (mais recente), alternável e persistido em config local.
- **Gestão de despublicadas**: lista de postagens inativas com botão de republicar (aba Administração).
- **Somente-leitura para `comum`**: controles ocultos na UI e bloqueados no backend.
- **Auditoria central** (`tb_auditoria`) para criar/atualizar/despublicar/republicar/excluir postagens e comentários.
- **Versionamento**: `versao_modulo:blog` exibido no rodapé de `/blog`.

## Permissões

| Ação | `comum` | Admin | Observação |
|:---|:---:|:---:|:---|
| Ler postagens/comentários | ✓ | ✓ | — |
| Criar postagem | ✗ | ✓ | backend valida |
| Editar postagem | ✗ | ✓ | backend valida |
| Comentar | ✗ | ✓ | backend valida |
| Despublicar/Republicar | ✗ | ✓ | aba Administração |
| Excluir (soft delete) | ✗ | ✓ | só admin |

## Rota e integrações

- Rota: `/blog` (chave `blog`) — permissão via `validar_acesso_modulo`.
- Consumido pelo núcleo: bootstrap cria o banco, scheduler faz backup e o dashboard usa `contar_postagens(ativo=True)`.
- Testes: `testes/teste_fluxo_blog.py` (33/33 OK).

## Testes

```bash
.venv/bin/python testes/teste_fluxo_blog.py
```

Ver [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md), [Manual do Administrador](../manual_de_uso_administrador/index.md) e [Análise do Módulo](../analise_mod_blog.md).
