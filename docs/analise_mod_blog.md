# Blog — `mod_blog`

> Corporate blog module: route `/blog` (key `blog`) · own database `db_mod_blog.db` · HTML sanitized with nh3 · read-only for common users · central LGPD audit.

---

# Blog — `mod_blog`

> Módulo de blog corporativo: rota `/blog` (chave `blog`) · banco próprio `db_mod_blog.db` · HTML sanitizado com nh3 · somente-leitura para usuário comum · auditoria central LGPD.

## Propósito

Blog corporativo com postagens e comentários em HTML sanitizado por `nh3`. Regra central: usuário `comum` tem acesso **somente leitura** — publicar, comentar e excluir são restritos ao administrador geral e ao administrador do módulo `blog`, validados na UI **e** no backend. Exclusão de postagem é lógica (`ativo=0`).

## Banco próprio

Criador vigente: `init_db()` em `manipulador_bd.py:25-50` (bootstrap central).

- **`tb_postagens`**: id PK, titulo, conteudo (gravado sanitizado), autor, data_criacao, data_atualizacao, `ativo` (soft delete / publicar-despublicar).
- **`tb_comentarios`**: id PK, postagem_id FK CASCADE → tb_postagens, autor, conteudo (sanitizado), data_criacao.
- **`tb_config` (local do módulo)**: `blog_modo_exibicao`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header` (Fase 3).

⚠️ O `criador_bd.py` do blog é **legado/morto**: conecta no banco **central**, duplica os CRUDs com bugs próprios (sanitização sem whitelist, ordenação sem efeito) e importa `audit_log` sem chamar.

## Fluxo da tela

- Editor "Nova publicação/Edition" (Título*, Conteúdo* — HTML simples/Markdown aceito e sanitizado) com **pré-visualização** e botão Publicar/Salvar: **somente admins**. Permite criar e **editar** postagem existente.
- Todos veem lista de postagens ativas em ordem cronológica DESC (modo **histórico**) **ou** apenas a mais recente (modo **única**), alternável na tela e persistido em config local.
- Cada card: título, autor, data, conteúdo injetado via `ui.html` **re-sanitizado**, comentários em `ui.expansion` com contador.
- Campo de comentário apenas para admins; comum lê "Somente administradores podem comentar." Exclusão de postagem só por admin; botões de **editar**, **despublicar** e **excluir**.

## Regras de negócio relevantes

- **Dupla camada de permissão**: UI esconde controles e backend valida em toda escrita (`criar/atualizar/excluir_postagem`, `criar_comentario` → `autenticacao.pode_publicar_no_blog`).
- **Sanitização nh3 na gravação E na renderização** — porém as whitelists **divergem**: gravação aceita 16 tags incluindo `a`/`img`; renderização aceita ~10 tags sem links/imagem. Resultado: imagens e links gravados são removidos na exibição. Nenhum `clean` configura atributos/`url_schemes` (permitir `data:`/relativas p/ imagens, pedido do PLANO, não implementado).
- **Formatos**: apenas HTML simples. Markdown prometido no README/PLANO **não tem conversor no código**.
- **Formatação rica** (títulos negrito/centralizados, imagens 200–400px à esquerda): `formatar_conteudo_para_exibicao()` **REALIZADO** — aplica estilos (h1/h2/h3 centralizados e em negrito, `<img>` flutuando à esquerda com limites 200–400px responsivos, texto justificado) sobre o HTML sanitizado; texto puro/Markdown também é justificado.
- **Modo de exibição**: sempre histórico completo; modo "publicação única" do README **não existe**.
- Soft delete: postagens inativas somem da lista; não há UI para listar/restaurar/republicar (funções de BD existem sem superfície).

## Integrações com o núcleo

Importa `autenticacao.pode_publicar_no_blog` e `eh_admin_do_modulo`. Grava em `tb_auditoria` via `audit_log` para criar/alterar/excluir postagens (conforme README/PLANO). Nenhuma chave `tb_config` local usada. Consumido pelo núcleo: bootstrap cria o banco, scheduler faz backup e o dashboard usa `contar_postagens(ativo=True)`.

## Pontos de atenção

- Auditoria central já implementada; whitelists nh3 alinhadas entre gravação (`_sanitizar_texto`) e exibição (`_sanitizar`/`tags_permitidas()`) — ambas usam `tags_permitidas()` de `tb_config`. RF-32 **REALIZADO**.
- Comentários só são removidos fisicamente por cascade quando a postagem é deletada fisicamente (fluxo da limpeza cruzada do módulo de usuários).
- Comentários só são removidos fisicamente por cascade quando a postagem é deletada fisicamente (fluxo da limpeza cruzada do módulo de usuários).

## Status — Fase 3 do PLANO.md

| Item | Situação |
|:---|:---|
| Banco WAL + CRUD com soft delete | Implementado |
| Sanitização nh3 (gravação + renderização) | Implementado (whitelists alinhadas via `tags_permitidas()`; aceita `data:`/relativas p/ imagens) |
| Somente-leitura para `comum` (UI + backend) | Implementado |
| Exibição de postagens/comentários | Implementado |
| Auditoria central (`tb_auditoria`) | Implementado |
| `tb_config` local (modo/largura de imagem) | **Implementado** (tabela `tb_config` do módulo) |
| Permitir `data:`/URLs relativas para imagens | **Implementado** (`url_schemes`/`url_relative`) |
| Formatação rica (títulos negrito/centralizados, imagens configuraveis) + Markdown | **REALIZADO (RF-32)** — `formatar_conteudo_para_exibicao()` aplica estilos; largura de imagem configurável |
| Exibição única OU histórico alternável | **Implementado** (`blog_modo_exibicao` local) |
| Editor com pré-visualização | **Implementado** (editor com preview, criar/editar) |
| Publicar/Despublicar + restauração de inativas | **Implementado** (aba Administração lista inativas) |
| `test/teste_fluxo_blog.py` (33/33) | **Implementado** (em `test/` — 33/33 OK) |

> Fase 3 **REALIZADO** e validado. O teste `test/teste_fluxo_blog.py` (33/33 OK)
> cobre sanitização XSS (nh3), conversores HTML/Markdown, CRUD, publicar/
> despublicar, soft delete, config local, modo única/histórico, largura de
> imagem e auditoria central. A checagem de auditoria foi atualizada para o
> banco exclusivo `db_mod_auditoria.db` (tabela `tb_auditoria_blog` — a
> `tb_auditoria` central virou legado, migrada via `migrar_dados_existentes`).

### Adições recentes (26/08)

- **Painel "Administração"** (expansão, exclusivo do admin do blog): bloco **Aparência** (prefixo blog_* — cor do botão/texto, tamanho via ui.color_input) e **config específica**: blog_tags_permitidas (CSV das tags HTML aceitas na sanitização NH3, aplicada via tags_permitidas()), blog_texto_header. Salvo via set_config, vale sem reiniciar.
- **Versionamento**: versao_modulo:blog = 1.0.260827 (seed em conexao_bd.init_db()), exibido no rodapé em /blog.
- **Edição do módulo** (`campo_modulo` do helper `mod_intranet/tema_modulo.py`): permite ao admin editar **nome de exibição, ícone e status (ativo/inativo)** do blog em `tb_modulos`.
