# Intranet Modular — Configuration and Environment

> Configuration guide: the `storage_secret` placeholder (must be replaced in production), the `8080` port, the `db_mod_*` database paths, and the parameters of `main.py` and `inicializar_bancos()`. There are no `.env` variables — all settings live in the central `tb_config` table, seedable by `PADRAO_CONFIG`.

---

# Intranet Modular — Configurações e Variáveis de Ambiente

> Guia de configuração: o placeholder `storage_secret` (deve ser trocado em produção), a porta `8080`, os caminhos dos bancos `db_mod_*` e os parâmetros do `main.py` e de `inicializar_bancos()`. Não existem variáveis `.env` — as configurações vivem na tabela central `tb_config`, semeada por `PADRAO_CONFIG`.

## Sumário

1. [Visão geral](#visao-geral)
2. [`storage_secret` (curinga do NiceGUI)](#storage_secret-curinga-do-nicegui)
3. [Porta e execução](#porta-e-execucao)
4. [Caminhos de banco de dados](#caminhos-de-banco-de-dados)
5. [Parâmetros do `main.py`](#parametros-do-mainpy)
6. [Bootstrap: `inicializar_bancos()`](#bootstrap-inicializar_bancos)
7. [Chaves de configuração (`tb_config`)](#chaves-de-configuracao-tb_config)
8. [Sem variáveis de ambiente `.env`](#sem-variaveis-de-ambiente-env)

## Visão geral

A aplicação não usa arquivo `.env` nem variáveis de ambiente: a configuração é **persistida no banco central** `db_mod_intranet.db` (tabela `tb_config`, chave/valor) e lida via `get_config(chave, default)` / `set_config(chave, valor)` (`mod_intranet/conexao_bd.py:87-107`). As únicas "constantes de execução" estão hardcoded no `main.py`.

## `storage_secret` (curinga do NiceGUI)

Em `main.py:336`:

```python
ui.run(
    title=...,
    favicon="assets/favicon_atual.ico",
    storage_secret="intranet-secret-2026-mude-isto",  # ← placeholder
    reload=False,
    port=8080,
    show=False,
)
```

> ⚠️ **Obrigatório trocar antes de produção.** `storage_secret` é a chave usada pelo NiceGUI para assinar os dados de sessão em `app.storage.user`. O valor atual é um placeholder hardcoded. Troque por uma string longa e aleatória (ex.: gerada com `secrets.token_hex(32)`).

## Porta e execução

| Parâmetro | Valor atual | Local |
|:---|:---|:---|
| `port` | `8080` | `main.py:338` |
| `reload` | `False` | `main.py:337` |
| `show` | `False` | `main.py:339` |
| `favicon` | `assets/favicon_atual.ico` (arquivo vivo) | `main.py:335` |
| `title` | lido de `tb_config` (`texto_login_titulo`) | `main.py:334` |

## Caminhos de banco de dados

Os bancos são criados na **raiz do projeto** (mesma pasta do `main.py`):

| Banco | Módulo | Onde é declarado |
|:---|:---|:---|
| `db_mod_intranet.db` | núcleo (auditoria, config, sessões, módulos) | `mod_intranet/conexao_bd.py:11` |
| `db_mod_gest_cad_usuario.db` | gestão de usuários | `mod_gest_cad_usuario/manipulador_bd.py` |
| `db_mod_blog.db` | blog | `mod_blog/manipulador_bd.py:41-45` |
| `db_mod_edit_pdf.db` | editor de PDF | `mod_edit_pdf/manipulador_bd.py:23` |
| `db_mod_renomear_empenho.db` | renomear empenho | `mod_renomear_empenho/manipulador_bd.py:20` |
| `db_mod_solicita_impressao.db` | solicitação de impressão | `mod_solicita_impressao/manipulador_bd.py:25` |

Todos operam em **modo WAL** (`PRAGMA journal_mode=WAL`), gerando arquivos `*.db-wal` e `*.db-shm` ao lado do `.db`.

## Parâmetros do `main.py`

| Item | Descrição | Local |
|:---|:---|:---|
| `sys.path.insert` | garante que a raiz esteja no path (imports `mod_*`) | `main.py:5` |
| `inicializar_bancos()` | cria todos os `db_mod_*` no boot **antes** de qualquer import de módulo | `main.py:16-17` |
| Verificação de `telas.py` | aborta com `RuntimeError` se algum `mod_*` não tiver `telas.py` | `main.py:22-24` |
| Favicon customizado | copia o favicon nativo para `assets/favicon_atual.ico` se ausente | `main.py:42-48` |
| `iniciar_agendador()` | delega ao `rotinas.iniciar_agendador()` (jobs de backup, cleanup, monitor, poda) | `main.py:28-32` e `323` |
| Observabilidade | `observabilidade.configurar()` + `instalar_excepthook()` antes do `ui.run` | `main.py:319-321` |
| CSS frameworks embarcados | `tema_css.montar_rotas_static()` — serve `assets/css/frameworks/` em `/css/frameworks/*` (sem CDN), com fallback silencioso | `main.py:64-71` |
| Documentação | `construir_e_montar_documentacao()` — build MkDocs + mount em `/documentacao` | `main.py:330-331` |
| `ui.run(...)` | sobe o NiceGUI (parâmetros da tabela acima) | `main.py:333-339` |

## Bootstrap: `inicializar_bancos()`

Definida em `mod_intranet/mod_intranet_inicializacao_bd.py:13-35`. Ordem **crítica** (o central SEMPRE primeiro):

1. `init_central()` — cria `tb_auditoria`, `tb_config`, `tb_sessoes` + seeds (`db_mod_intranet.db`).
2. `garantir_rastreabilidade()` — migração de colunas LGPD (`ip`, `user_agent`, `dispositivo`, `mac`) + índices + seed `sessao_retencao`.
3. `init_blog()` → `db_mod_blog.db`.
4. `init_users()` → `db_mod_gest_cad_usuario.db` + seed `master`/`master`.
5. `init_db_pdf()` → `db_mod_edit_pdf.db`.
6. `init_db_empenho()` → `db_mod_renomear_empenho.db`.
7. `init_solicita()` → `db_mod_solicita_impressao.db`.

O processo é **idempotente** (nunca apaga dados) e pode ser rodado novamente para aplicar seeds sem reiniciar nada.

## Chaves de configuração (`tb_config`)

As principais chaves, agrupadas por dono:

| Grupo | Chave | Default | Descrição |
|:---|:---|:---|:---|
| Sistema | `versao_sistema` | `1.0.260827` | versão global exibida no rodapé |
| Sistema | `cotadisco_global_gb` | `10` | cota global do editor PDF (GB) |
| Sistema (legada) | `backup_interval_hours` | `12` | semente legada; os jobs usam `backup_horas:<modulo>` |
| Sistema | `sessao_retencao` | `50` | histórico de sessões retido por usuário |
| Aparência | `titulo_sistema`, `icone_sistema`, `cor_principal` (`#1565C0`), `cor_fundo` (`#EEEEEE`) | `PADRAO_CONFIG` | personalização global |
| Textos | `texto_login_titulo`, `texto_login_subtitulo`, `texto_login_hint`, `texto_home_saudacao`, `texto_home_subtitulo`, `texto_rodape` | `PADRAO_CONFIG` | textos fixos |
| Versão por módulo | `versao_modulo:<chave>` | seeds em `conexao_bd.py:70-79` | versão individual no rodapé |
| Backup | `backup_horas:<modulo>` | `12` | intervalo em horas por módulo (mín. 1 h) |
| Editor PDF | `editpdf_lote_arquivos`, `editpdf_lote_mb`, `editpdf_usuario_gb`, `editpdf_expiracao_min` | — | cotas/limites/expiração |
| Editor PDF (tema) | `editpdf_cor_botao`, `editpdf_cor_texto_botao`, `editpdf_cor_fundo`, `editpdf_cor_titulo`, `editpdf_btn_tamanho` | — | aparência da tela |
| Blog | `blog_modo_exibicao`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header` + tema `blog_*` | — | comportamento/aparência |
| Usuários | `usuarios_senha_min`, tema `usuarios_*` | `6` | política de senha mínima |
| Auditoria | `auditoria_limite` (1000), `auditoria_retencao_dias` (90), `auditoria_texto_header`, `auditoria_campos:<usuario>` (JSON) | — | paginação/retirada/campos |
| Empenhos | `empenhos_monitor_intervalo_seg` (10), `empenhos_pasta_monitorada`, `empenhos_texto_header`, tema `empenhos_*` | — | monitor/aparência |
| Impressão | variáveis de tempo e padrões na aba Administração → Configurações do módulo | — | ver [Módulo de Solicitação de Impressão](modulos/solicitacao_impressao.md) |
| E-mail/SMTP | `smtp_*` | — | credenciais (aba "E-mail" de Configurações) |
| Logs | `log_ativo`, `log_nivel`, `log_rotacao` (`1 month`), `log_retencao` (`4 months`) | — | observabilidade loguru |

> Os padrões de aparência vivem em `PADRAO_CONFIG` (`mod_intranet/conexao_bd.py:13-24`) e são restaurados via tela de configurações (abas com "Restaurar padrão" por cartão).

### Aba "Módulo" — Páginas do sistema

Na aba **Módulo → Páginas do sistema** (renomeada de "Registro/Nome de módulo" em 05/09 — `tela_configuracoes.py:165`) o administrador edita o **nome exibido** (menu lateral e título do cabeçalho), o **ícone** (Material Icons) e a **ORDEM** de cada página usando as setas ↑/↓ (a ordem é salva imediatamente). Desde 05/09:

- **Reordenação com ↑/↓** — a lista de páginas é **ÚNICA** (substituiu os grupos separados "Indispensáveis"/"Demais") e todos os módulos são reordenáveis: `refresh_modulos()` (`tela_configuracoes.py:566-636`) remonta a lista na ordem vigente de `tb_modulos.ordem` e `_mover(idx, direcao)` (`tela_configuracoes.py:638-669`) troca o vizinho, persiste de imediato via `autenticacao.reordenar_modulos` e preserva edições pendentes (nome/ícone/ativo) entre remontagens. A 1ª coluna do grid (56px) exibe a posição e os botões ↑/↓.
- **Campo de ícone editável com seletor visual** — `_campo_icone` (`tela_configuracoes.py:519-546`): input livre do nome do Material Icon + **pré-visualização viva** (o ícone é atualizado em tempo real na linha) + **seletor visual** (`ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS` — 31 ícones, `tela_configuracoes.py:33-39`) + botão `grid_view`. Reutilizado no campo "Ícone Material" do registro de novo módulo (`tela_configuracoes.py:762`).
- **Alinhamento corrigido** — constante compartilhada `COLUNAS_MODULOS` (`tela_configuracoes.py:45`) entre cabeçalho e linhas (mesmo columns/gap/padding; antes o cabeçalho não tinha gap).
- **Indispensáveis destacados, porém reordenáveis** (`tela_configuracoes.py:595-630`): `auditoria` e `usuarios` (`MODULOS_INDISPENSAVEIS` — `tela_configuracoes.py:30` e `autenticacao.py:216`) aparecem com fundo âmbar + cadeado e **não podem ser desativados**: a tentativa é recusada no backend (`set_modulo_ativo` retorna `(False, msg)` e audita `modulo_desativado_bloqueado` — `autenticacao.py:227-229`); `set_chaves_desativadas` também os filtra (`autenticacao.py:481`); `salvar_tudo` força `ativo=1` (`tela_configuracoes.py:123`). O switch fica oculto/disabled com valor fixo `True`.
- **"Restaurar padrão" também restaura a ordem** — `restaurar_paginas_padrao()` (`tela_configuracoes.py:673-720`) volta os nativos ao nome/ícone codificados, reativados e na sequência de `MODULOS_SISTEMA`, renumerando os não-nativos após os nativos em ordem alfabética.
- **Campo "URL da página" (slug editável, 05/09)** — cada linha da lista ganhou um campo **"URL da página"** editável (`_campo_empilhado("URL da página", rota, ...)` em `tela_configuracoes.py:660-662`), ligado em `campos_url[chave] = inp_url` / `estado_campos["urls"]` (`tela_configuracoes.py:593-594`). Ao salvar, `salvar_tudo()` (`tela_configuracoes.py:139-158`) compara o valor com a rota vigente no BD e chama `autenticacao.alterar_rota_modulo` (`autenticacao.py:196-232`), que valida a URL (regex `[a-z0-9_\-/]+`), impede colisão entre módulos, grava `tb_modulos.rota` e **re-registra a página ao vivo** via `rotas_modulos.registrar_modulo` — sem restart. A notificação informa "N URL(s) alterada(s) — recarregue com F5". O registro dinâmico de rotas vive em `mod_intranet/rotas_modulos.py` (`DEFAULT_ROTAS`, `REGISTRO_MODULOS`, `_registradas`, `_normalizar_rota`, `registrar_modulo`, `montar_rotas_ativas`), com `REGISTRO_MODULOS["chave"] = page_*` preenchido em `main.py` após cada decorator fixo e `montar_rotas_ativas()` antes do START (`main.py:426`). Os decorators fixos são mantidos — links antigos continuam válidos.
- **Grid responsivo (05/09)** — `COLUNAS_MODULOS` (`tela_configuracoes.py:44-47`) deixou de usar `columns=` inline e agora é **responsiva**: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]` — 6 colunas em desktop (setas, chave, nome, URL, ícone, situação), empilhando em telas pequenas. O cabeçalho é oculto em sm/md (`hidden lg:grid`, `tela_configuracoes.py:619`), o `overflow-x-auto` foi removido e os inputs usam `w-full max-w-[30ch]`.
- O grid ganhou cabeçalho com **tooltips** explicando cada coluna e colunas `56px minmax(30ch, 1fr) minmax(30ch, 1fr) minmax(30ch, 1fr) 150px` (`tela_configuracoes.py:581-593`).

## Sem variáveis de ambiente `.env`

Diferente de muitos projetos NiceGUI, a Intranet **não lê `.env` nem variáveis de ambiente**. Toda configuração operacional é:

1. **Hardcoded** no `main.py` (porta, `storage_secret`, favicon) — editar o arquivo para mudar; ou
2. **Persistida** na `tb_config` central — alterável em runtime pelas telas de administração (Configurações e abas "Administração" de cada módulo), valendo **sem reiniciar o servidor**.