# Hamburger Menu Security Audit — Intranet Modular (2026-09-12)

> Targeted DevSecOps audit of the hamburger menu authorization chain (`mod_intranet/telas.py`, `main.py`, `mod_intranet/autenticacao.py`, `rotas_modulos.py`). 4 High, 7 Medium and Low findings with file:line evidence, tool output and suggested fixes (documentation only — no code changed).

---

# Auditoria de Segurança do Menu Hambúrguer — Intranet Modular (12/09/2026)

> Auditoria DevSecOps direcionada à cadeia de autorização do menu hambúrguer (`mod_intranet/telas.py`, `main.py`, `mod_intranet/autenticacao.py`, `rotas_modulos.py`). 4 achados Altos, 7 Médios e Baixos com evidência arquivo:linha, saída de ferramentas e correção sugerida (somente documentação — nenhum código foi alterado).

## 1. Escopo e método

- **Data:** 12/09/2026
- **Escopo:** menu hambúrguer e guard central — `mod_intranet/telas.py` (`pagina_restrita`, `usuario_logado`), `main.py` (rotas `/`, `/admin/{chave_modulo}`, `/configuracoes`, `/documentacao`, JS de impressão, `storage_secret`), `mod_intranet/autenticacao.py` (papel no módulo, sessão, perfil global), `mod_intranet/rotas_modulos.py` (slugs customizados), `mod_intranet/documentacao.py` (montagem `/documentacao`), `mod_gest_cad_usuario/bd_manipulador.py` (`obter_papel_no_modulo`, `validar_acesso_modulo`).
- **Tipo:** revisão manual de autorização + SAST/varredura de segredos/dependências. Nenhum código foi alterado nesta tarefa — só documentação.
- **Referências internas:** [Ferramentas de Segurança](ferramentas_de_seguranca.md), [Riscos de IA/ML](riscos_ia_ml.md), [Relatório 06/09/2026](../testes_relatorios/seguranca_2026-09-06.md).

## 2. Resultado das ferramentas (evidência de comando)

| Ferramenta | Versão | Comando | Resultado no escopo |
|:---|:---|:---|:---|
| `bandit` | 1.9.4 | `bandit -r mod_intranet/telas.py main.py mod_intranet/autenticacao.py mod_intranet/rotas_modulos.py -q` | **0 High / 0 Medium** no escopo do menu (nada de `exec`/`eval`/`shell` no guard) |
| `semgrep` | 1.176.1 | `semgrep scan --config auto --error --timeout=30 -j 4 --quiet main.py mod_intranet/telas.py mod_intranet/autenticacao.py mod_intranet/rotas_modulos.py` | **0 achados** no escopo (regras auto não cobrem lógica de autorização — achados são de revisão manual abaixo) |
| `pip-audit` | 2.10.1 | `pip-audit -r requirements.txt` e `pip-audit -r requirements-dev.txt` | **13 vulns de ambiente** (dependências, fora do código do menu — atualizar conforme `pip-audit`/`safety`; sem `fix` aplicado aqui) |
| `safety` | 3.8.1 | `safety check` | Complementa o `pip-audit` acima (mesmas 13 vulns de ambiente) |
| `gitleaks` | 8.24.3 | `gitleaks detect --source . --redact` | **1 leak histórico** (credencial padrão `master:master` em `assets/docker/verify-credentials.sh:67` e eco em `:23`, `:71`, `:74`, `:158` — ambiente local de observabilidade, não vazamento de produção) |
| `k6` | — | não executado | Carga só contra **localhost/staging** por política; menu não tem endpoint crítico que justifique carga nesta rodada |

> Observação: `site/` (build do MkDocs) gera falsos positivos de `gitleaks` (`search_index.json`). Filtrar ao interpretar — ver relatório de 06/09.

## 3. Achados Altos (corrigir primeiro)

| ID | Título | Onde (arquivo:linha) | Evidência | Correção sugerida (sem aplicar) |
|:---|:---|:---|:---|:---|
| **A1** | `storage_secret` com fallback fraco em código | `main.py:616-617` — `storage_secret=os.environ.get("INTRANET_STORAGE_SECRET") or "intranet-secret-2026-mude-isto"` | Se `INTRANET_STORAGE_SECRET` não estiver definido, a sessão assinada do NiceGUI usa segredo público e previsível. Quem conhece o default pode forjar/ler `app.storage.user`. | Exigir a variável em produção: abortar o boot com mensagem se ausente (ex.: `if not os.environ.get("INTRANET_STORAGE_SECRET"): raise SystemExit(...)`); manter fallback apenas em dev com aviso explícito; documentar a variável em `docs/configuracoes.md`; rotacionar o segredo em qualquer ambiente que já rodou com o default. |
| **A2** | `/configuracoes` sem gate de papel no guard | `main.py:570-577` — `page_configuracoes()` chama `pagina_restrita("Administração")` **sem** `chave_modulo`; `mod_intranet/telas.py:33-92` — check de módulo só ocorre `if chave_modulo` (`:65`, `:74`) | Qualquer usuário autenticado que acertar a URL abre o painel central (5 abas, Restaurar/Aplicar por card, rebuild MkDocs). O guard valida sessão (`:44-63`) mas não valida papel. | Passar um `chave_modulo` dedicado (ex.: `"intranet"`) ou adicionar gate explícito em `page_configuracoes` (ex.: só `administrador_geral` ou `eh_admin_do_modulo(nome, "intranet")`); registrar `acesso_negado` no caminho negado como já faz `:74-83`. |
| **A3** | Perfil de sessão stale (troca de papel não derruba sessão) | `mod_intranet/telas.py:28-31` (`usuario_logado` lê `app.storage.user`), `:43-63` (revalida existência/ativo + hash de sessão, mas **não** compara `perfil`/papéis); `mod_intranet/autenticacao.py:550-553` (`perfil_global_de`), `:538-547` (`papel_no_modulo`) | Rebaixamento (`administrador_geral` → `comum`) ou remoção de `tb_acesso_usuario` não invalida a sessão viva: o dict em storage continua com `perfil` antigo até logout. Telas que confiam em `user.get("perfil")` (ex.: `main.py:504`) decidem com dado stale. | Revalidar `perfil` global + papéis por módulo a cada `pagina_restrita` e sobrescrever `app.storage.user["usuario"]`; ou versionar a sessão (coluna `versao_perfil`/`revogada_em`) e derrubar quando divergir; auditar `sessao_invalidada_por_mudanca_perfil`. |
| **A4** | `obter_papel_no_modulo` liberando chave inexistente | `mod_gest_cad_usuario/bd_manipulador.py:785-798` — `administrador_geral` retorna `"administrador"` para **qualquer** `modulo_chave` antes de checar `tb_acesso_usuario`; `mod_intranet/autenticacao.py:546-547` (`eh_admin_do_modulo` confia no retorno) | `eh_admin_do_modulo(nome_admin_geral, "chave_inexistente")` retorna `True`. Combinado com M1 (`/admin/{chave}` sem allowlist), chave arbitrária na URL pode ser tratada como administrável pelo admin geral e cair em ramo inesperado. | Validar a chave contra o catálogo (`modulos_registrados`/`tb_modulos`) antes do early-return do admin geral; retornar `None` para chave desconhecida; adicionar teste `obter_papel_no_modulo(admin, "inexistente") is None`. |

## 4. Achados Médios

| ID | Título | Onde (arquivo:linha) | Evidência | Correção sugerida (sem aplicar) |
|:---|:---|:---|:---|:---|
| **M1** | `/admin/{chave}` sem allowlist de chaves | `main.py:488-567` — `page_admin_modulo(chave_modulo)` com `if/elif` por chave conhecida e `else: ui.navigate.to("/configuracoes")` (`:566-567`) | Chave arbitrária passa pelo guard (`pagina_restrita` `:500`) e só no `else` é redirecionada — para `/configuracoes`, que por A2 também é fraca. Enumeração de chaves não é barrada na borda. | Allowlist explícita no topo (`if chave_modulo not in {...}: audit acesso_negado + navigate "/" + return`); não redirecionar desconhecido para `/configuracoes`. |
| **M2** | Slugs customizados sem reserva/bloqueio | `mod_intranet/rotas_modulos.py:33-58` (`_normalizar_rota`, `registrar_modulo` sem validação de colisão); `mod_intranet/autenticacao.py` (`modulos_registrados`, `tb_modulos.rota`) | Slug persistido em `tb_modulos.rota` pode sobrescrever `/admin`, `/configuracoes`, `/login`, `/documentacao` ou prefixos de API — `registrar_modulo` só evita duplicidade (`_registradas`), não reserva. | Lista reservada (`{"admin","configuracoes","login","documentacao","api",...}`) validada na gravação do slug e em `montar_rotas_ativas`; teste de colisão. |
| **M3** | `/documentacao` pública (site inteiro sem login) | `mod_intranet/documentacao.py:36-48` (`montar()` via `StaticFiles` sem auth), `:51-89` (servidor `ThreadingHTTPServer` em `0.0.0.0` sem auth); `main.py:596-603` (build+serve no boot); `mod_intranet/telas.py:308-312` (link público) | Todo o `site/` (incluindo estes relatórios de segurança) fica legível sem sessão, na rota interna e na porta dedicada. | Exigir sessão no mount (middleware/guard) ou servir docs só em localhost/porta dedicada com token; ou separar docs públicas vs. internas; documentar a decisão. |
| **M4** | PDF sem auditoria do acesso negado | `mod_edit_pdf` (guards de tela) vs. padrão `mod_intranet/telas.py:74-83` (`acesso_negado` com `audit_log`) | Negativas do Editor de PDF não seguem o padrão `audit_log(..., "acesso_negado", ...)` do guard central — trilha de quem tentou abrir o quê fica incompleta. | Chamar `audit_log(nome, chave, "acesso_negado", ...)` em todo `return None` por falta de permissão no PDF; padronizar mensagem com a chave. |
| **M5** | JS de impressão servido sem gate | `main.py:480-485` (`servir_js_impressao` lê `mod_solicita_impressao/src/impressao.js` e retorna `Response`) | Rota do JS não passa por `pagina_restrita` — qualquer request não autenticado baixa o asset (baixo impacto direto, mas quebra a invariante "tudo de módulo exige sessão"). | Servir o JS por rota que exige sessão ou embutir como static autenticado; se for propositalmente público, registrar a exceção aqui. |
| **M6** | Auditoria sem registro da negação interna | `mod_auditoria` (telas/guard) vs. `mod_intranet/telas.py:74-83` | Negativas dentro da Auditoria (ex.: não-`administrador_geral` em `main.py:525-530`) não geram `acesso_negado` — justamente o módulo que deveria ter a trilha mais completa. | `audit_log` em todo caminho negado da Auditoria (RF-35); incluir ator, chave e motivo. |
| **M7** | Seed `master:master` presente no repo | `assets/docker/verify-credentials.sh:23,67,71,74,158`, `assets/docker/setup-grafana-credentials.sh:5-6,28,76-79,111-114`, `assets/docker/start.sh:86` | Credencial padrão versionada (detectada pelo `gitleaks` como o único leak real). É ambiente local de observabilidade, mas o par aparece em 3 scripts e ecoa no terminal. | Mover para `.env` não versionado/`INTRANET_*`/Vault; gerar senha no setup; mascarar e-mails/logs; manter `master/master` só em exemplo com aviso. |

## 5. Achados Baixos / hardening

| ID | Título | Onde | Correção sugerida (sem aplicar) |
|:---|:---|:---|:---|
| **B1** | Mensagens de negado genéricas vs. enumeráveis | `mod_intranet/telas.py:81-82` | Manter mensagem genérica ao usuário e detalhar só no `audit_log` (`:77-78`) — já é o padrão correto; replicar em todos os módulos. |
| **B2** | `user["sessao"]` adotado tardiamente | `mod_intranet/telas.py:59-63` (sessões legadas sem hash ganham hash "agora") | Forçar re-login de sessões sem hash em vez de adotar; expirar sessões antigas por retenção LGPD (`Repositorio.podiar_sessoes`). |
| **B3** | Docs servidas em `0.0.0.0` | `mod_intranet/documentacao.py:76` (`ThreadingHTTPServer(("0.0.0.0", p), ...)`) | Bind em `127.0.0.1` por padrão; `0.0.0.0` só com flag explícita. |
| **B4** | Favicon/tema mutável sem versionamento | `main.py:615`, `mod_intranet/tema_modulo.py` | Versionar uploads (`?v=hash`) e validar MIME/tamanho no upload do `/configuracoes`. |

## 6. Ações priorizadas (sem ordem de implementação em código — decisão do mantenedor)

1. **Alta:** `INTRANET_STORAGE_SECRET` obrigatório em produção + rotação (A1); gate de papel em `/configuracoes` (A2).
2. **Alta:** revalidação de perfil/papel por request (A3); validação de chave desconhecida em `obter_papel_no_modulo` (A4).
3. **Média:** allowlist em `/admin/{chave}` (M1); reserva de slugs (M2); decisão de acesso à `/documentacao` (M3).
4. **Média/Baixa:** `acesso_negado` no PDF e na Auditoria (M4, M6); gate do JS (M5); remover `master:master` versionado (M7); bind docs em loopback (B3).
5. **Ambiente:** tratar as 13 vulns de `pip-audit`/`safety` (`pip-audit -r requirements.txt -r requirements-dev.txt`) e acompanhar `gitleaks` filtrando `site/`.

## 7. Reprodução (somente leitura — nenhum `fix` aplicado)

```bash
# SAST no escopo do menu
bandit -r mod_intranet/telas.py main.py mod_intranet/autenticacao.py mod_intranet/rotas_modulos.py -q
semgrep scan --config auto --error --timeout=30 -j 4 --quiet main.py mod_intranet/telas.py mod_intranet/autenticacao.py mod_intranet/rotas_modulos.py

# Dependências e segredos
pip-audit -r requirements.txt
pip-audit -r requirements-dev.txt
safety check
gitleaks detect --source . --redact

# Build da documentação (validação desta página)
.venv/bin/python -m mkdocs build
```

> `k6` restrito a **localhost/staging** por política do repositório — não executado nesta auditoria.

## 8. Histórico

- 06/09/2026 — [Relatório de Varredura](../testes_relatorios/seguranca_2026-09-06.md): 0 High (bandit/semgrep), 1 segredo real (`master:master`).
- 12/09/2026 — esta auditoria (foco menu hambúrguer): 4 Altas + 7 Médias de **lógica de autorização** (invisíveis ao SAST por regras auto).

Veja também: [Ferramentas de Segurança](ferramentas_de_seguranca.md) · [Análise de Risco](../analise_de_risco/index.md).
