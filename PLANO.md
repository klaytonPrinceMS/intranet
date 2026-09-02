# PLANO DE IMPLEMENTAÇÃO

> Checklist rastreável por fase. **Marcar `[x]` cada item concluído** para permitir retomada após interrupção. Versionamento: `1.0.AAMMDD`. Não executar `git commit` (responsabilidade do autor).
> Antes de Qualquer fase, obrigatorio, garantir que caso os bancos de dados db_mod_blog, db_mod_edit_pdf, db_modgest_cad_usuario, db_mod_intranet, db_mod_nomear_empenho, ou qualquer outro banco de dados nao exista na rais do sistema onde o script ou o exetuvel gerado no futuro estiver rodanto tiver os bancos de dados deve ser criado os bancos de dados do zero, e para o usuario deve ser inserio sempre o usuario master senha master inicialmente com permissao de administrador geral 

## Fase 0 — Scaffold e estrutura base

- [ ] Estrutura de pastas (`assets/`, `assets/css/`, `doc/`, `editorPDF/`, `organizadorPasta/`, `backup/`)
- [ ] Tailwind CSS servido localmente pelo próprio NiceGUI (`tailwindcss.min.js` embutido no pacote, `ui.run(tailwind=True)`) — sem CDN (rede interna)
- [ ] `requirements.txt` (NiceGUI, APScheduler, nh3, pdfplumber, pikepdf, pymupdf, pytesseract)
- [ ] Utilitário SQLite em modo WAL obrigatório
- [ ] `main.py` com bootstrap NiceGUI sobe a aplicação


## Fase 1 — mod_intranet (núcleo/centralizador)

- [ ] `db_mod_intranet.db` com tabela central `tb_auditoria` + `tb_config` (`mod_intranet_criador_bd.py`)
- [ ] Registro centralizado de auditoria (`mod_intranet_auditoria.py`)
- [ ] Tela de login (cookie HTTP-Only, sessão registrada em banco) — `mod_gest_cad_usuario_render_login.py`
- [ ] Usuário inicial `master`/`master` com **troca de senha obrigatória no 1º logon** (seed em `mod_gest_cad_usuario_criador_bd.py`)
- [ ] Layout 4 partes: menu superior, menu lateral retrátil, rodapé com versão, área principal (`mod_intranet_render_layout.py`)
- [ ] Dashboard home mobile-first (Tailwind, grid fluido 360–1440px, microinterações, feedback de 2s via setTimeout) — `mod_intranet_render_dashboard.py`
- [ ] Personalização do sistema (título, ícones, pasta raiz, paleta de cores, SMTP) lida de `tb_config`
- [ ] Backup automático dos bancos a cada 12h (configurável)
- [ ] Módulos secundários visíveis apenas para usuários autorizados; alerta para módulos removidos do `main.py`

## Fase 2 — mod_gest_cad_usuario (soft CRUD)

- [ ] `db_mod_gest_cad_usuario.db`: tabela `tb_usuario` (ID como chave primária), `tb_perfil`, vínculo usuário↔módulo↔perfil
- [ ] CRUD com soft delete: criar, alterar, bloquear, desbloquear (`user_nome`, `user_senha`, `user_email`, `user_fone`)
- [ ] Tela de gestão `/gestao-usuarios` com tabela de usuarios, modal de novos usuarios, toggle ativo/bloqueado
- [ ] Perfis por módulo (`administrador geral`, `administrador do módulo`, `comum`) e controle granular de acesso
- [ ] Senha provisória para novos usuarios + troca no primeiro acesso
- [ ] Auditoria central em `tb_auditoria` (criação/edição/exclusão/liberação, LGPD)

## Fase 2.5 — Testes do fluxo completo (pasta `testes/`)

- [ ] `testes/teste_boot.py`: servidor sobe, `/login` com Tailwind local + CSS custom
- [ ] `testes/teste_fluxo_autenticacao.py`: login master → senha provisória → troca obrigatória → sessão/logout → auditoria → soft delete (19/19 OK)
- [ ] `testes/teste_fluxo_permissoes.py`: concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (13/13 OK)
- [ ] Correções: inputs dentro do diálogo, evento `.value` do checkbox, senha provisória aleatória revelada ao admin, remoção de rascunho quebrado (`mod_gest_cad_usuario_api.py`)
- [ ] Controle granular aplicado no menu lateral, cards do dashboard e página `/modulo/{slug}` (acesso negado)

## Fase 3 — mod_blog

- [ ] `db_mod_blog.db` + CRUD de postagens (soft delete, publicar/despublicar, `tb_config` local do módulo)
- [ ] Sanitização obrigatória com `nh3` (na gravação e na renderização; `data:`/relativas permitidas para imagens)
- [ ] Formatação: títulos em negrito/centralizado, imagens 200–400px alinhadas à esquerda, texto puro/Markdown/HTML
- [ ] Exibição única ou histórico cronológico; auditoria central
- [ ] Página `/blog` com editor (pré-visualização), configurações (modo + largura de imagem) e gestão restrita a admin geral/admin. do módulo
- [ ] `testes/teste_fluxo_blog.py`: sanitização XSS, conversores, CRUD, soft delete, config local, auditoria central (33/33 OK)

## Fase 4 — mod_renomear_empenho

### 4a. Monitor, extração e indexação

- [ ] Monitor de pastas (live ou intervalo configurável, padrão 10s), somente `.pdf` (`mod_renomear_empenho_monitor_pasta.py`, APScheduler)
- [ ] Extração com fallback automático `pytesseract` → `pdfplumber` → `pikepdf` → `pymupdf` (tratar encoding cp1252/Latin-1 e OCR em páginas-imagem) — mojibake neutralizado via texto tolerante (`?`)
- [ ] Indexação FTS5 `tb_indexador_pesquisa_fts5` (mín. 30 campos: 38 definidos) + campos customizados por Regex dinâmico em `tb_regras_regex`
- [ ] Documento-modelo `DOC_0201.pdf` processado ponta a ponta (fixture de teste — `testes/teste_fluxo_renameador.py`, 31/31 OK)

### 4b. Quarentena e regras dinâmicas

- [ ] Fila de quarentena para PDFs com erro de leitura/corrupção/Regex não reconhecido (tela `/renomeador`)
- [ ] Interface do administrador: identificação manual + cadastro de Regex dinâmico com reprocessamento sem reiniciar (`promover_quarentena`/`reprocessar_fila`, botão "Reprocessar fila")

### 4c. Renomeação e organizador físico

- [ ] Renomeação automática (somente campos validados sem divergência) e sequencial com contador em banco (`doc_0032_numEmpenho_numParcela.pdf`)
- [ ] Organizador: subpastas ~200 páginas, 4 pastas/caixa, capas PDF/TXT em `organizadorPasta/` (`mod_renomear_empenho_organizador.py`, 16/16 OK)
- [ ] Validação de presença via `matrizDeDocumentos.pdf`

### 4d. Ferramentas de edição embutidas

- [ ] Corte (pares/ímpares/intervalo), merge e redução de tamanho (DPI/qualidade); saídas em `datahora_mergePDF/`, `datahora_cortePDF/`, `datahora_reducaoPDF/` (18/18 OK)
- [ ] Ações do usuário comum: pesquisa (FTS5 na tela), ZIP; auditoria com hash SHA-256 em todas as operações

## Fase 5 — mod_edit_pdf

- [ ] `db_mod_edit_pdf.db` + `editorPDF/` com cota global 10 GB e limites por lote (10 arquivos/1 GB)
- [ ] Expiração automática após 10 min (rotina agendada) e prefixo `dataHora_usuario_operacao_nomeArquivo.pdf`
- [ ] Operações: reduzir (DPI 50–400, qualidade 10–100%, escolha de biblioteca), juntar, dividir, verificar integridade, ZIP, excluir
- [ ] Auditoria central com hash SHA-256 (origem/destino)

## Fase 6 — mod_auditoria

- [ ] Leitura/filtro da `tb_auditoria` central (data, hora, usuário, tipo de ação, módulo de origem)
- [ ] Acesso exclusivo `administrador geral`