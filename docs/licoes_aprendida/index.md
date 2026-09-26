# Lessons Learned — Intranet Modular

> Lessons learned during development. Seed document — to be expanded as the team records post-mortems and improvements.

---

# Lições Aprendidas — Intranet Modular

> Lições aprendidas durante o desenvolvimento. Documento-semente — expandir com registros de post-mortem e melhorias.

## Lição em destaque (25/09/2026) — `try/except` esconde `NameError`

A regra "envolva toda função em `try/except`" (AGENTS.md §3.2) existe para nunca
derrubar o servidor — e está correta. Mas ela tem um custo invisível: **quando o
`except` termina em `pass`, um `NameError` é capturado e engolido**. A suíte passa,
o terminal fica limpo, e a funcionalidade está quebrada.

Foi o que aconteceu com **7 `undefined name` em 5 arquivos** no mesmo dia — `--otel`
nunca subia o OTel, o botão "Resetar" da cota não fazia nada, a aba de Configurações
do admin truncava antes do botão Salvar, o seletor de etapa da fila vinha vazio, ~60
erros do Renomeador sumiam sem log e 11 erros de login nunca chegavam ao log.

**Mitigação adotada:** `pyflakes` como análise estática **bloqueante** antes de
declarar o ciclo de testes verde. Ver
[Convenções — Análise estática obrigatória](../convencoes_codigo.md#analise-estatica-obrigatoria-pyflakes).

## Lições registradas (semente)

- **Integridade de `main.py`:** edições via PowerShell corromperam caracteres (`.`→`..`, `.`→`~`, `_`→`-`, `,`→`;;`). Mitigação: validar todo `.py` com `ast.parse` e revisar diffs.
- **`bd_criador.py` é legado/morto:** aponta para banco central e não reflete o banco por módulo. Usar `bd_manipulador.py` como fonte de verdade.
- **Sanitização de Blog:** `nh3` deve ser aplicado na gravação **e** na renderização para prevenir XSS.
- **Rastro de auditoria:** toda escrita relevante (incluindo PDF) deve registrar na trilha de auditoria (`audit_log` → banco exclusivo `db_mod_auditoria.db`) com `hash_arquivo` (SHA-256) para conformidade LGPD.
- **Ambiente virtual:** preferir `.venv/bin/python` (Linux) / `Scripts\python.exe` (Windows) para evitar conflitos de dependência.
- **Encoding UTF-8 + WSL (sessão "Ç não reconhecido no OpenCode via WSL", 14/09/2026):** todo `.py`/`.md` do projeto é **UTF-8 sem BOM**; ferramentas que reescrevem encoding por fora (PowerShell, edição via WSL com locale divergente) já corromperam caracteres — validar com `ast.parse(open(..., encoding='utf-8').read())` após qualquer alteração e revisar o diff antes de seguir (mesma mitigação da integridade do `main.py` acima).
- **Toggles `hidden sm:*`/`md:*` não funcionam neste stack (sessão header 14/09/2026):** o `tailwindcss.min.js` embutido no NiceGUI 3.15 resolve `hidden` acima de `sm:flex`/`md:block` mesmo em 1280 px — usar um único elemento sempre visível com `max-width` + ellipsis em vez de dois elementos desktop/mobile.
- **Scripts auxiliares e CWD (sessão 14/09/2026):** `fresh_install_test*.py`/`diag_db.py` criavam `.db` de 0 bytes na pasta anterior quando rodados com outro CWD — todo script standalone resolve caminhos por **absoluto a partir da raiz** (`_RAIZ`), nunca por CWD relativo.
- **`try/except` esconde `NameError` — `pyflakes` é obrigatório (25/09/2026):** o padrão obrigatório do AGENTS.md §3.2 (envolver toda função em `try/except` para nunca derrubar o servidor) tem um custo invisível: quando o `except` termina em `pass` ou só em notificação, **um `NameError` é capturado e engolido**. A suíte passa, o terminal fica limpo e a funcionalidade está quebrada. No dia 25/09/2026 foram **7 `undefined name` em 5 arquivos**, cada um com efeito real e nenhum sinal: `--otel` nunca subia o OTel (`_otel_auto_stack`), o botão "Resetar" da cota não fazia nada (`bd`), a aba de Configurações truncava antes do botão Salvar (`ler_tema`/`bloco_aparencia`), o seletor de etapa vinha vazio (`fid` × `fila_id`), ~60 erros do Renomeador sumiam sem log (`notificar`) e 11 erros de login não iam para o log (`_login_erro_log`). **Mitigação: `pyflakes` como análise estática BLOQUEANTE** (`requirements-dev.txt`, seção "Lint / análise estática") antes de declarar o ciclo verde, e **correção na fonte** — nunca um `except: pass` novo. Detalhe em [Convenções](../convencoes_codigo.md#analise-estatica-obrigatoria-pyflakes).
- **O `except` também é código — revise-o com a mesma atenção do caminho feliz (25/09/2026):** os piores `undefined name` estavam **dentro do tratamento de erro** (`except NameError:` encadeado para obter o logger). Quando o `except` é o caminho crítico — o que mais precisa funcionar — é também onde os erros de escopo se escondem, porque quase nunca é exercitado nos testes.
- **Nome usado por várias funções vai no escopo de módulo (25/09/2026):** o padrão que emerge de todos os casos corrigidos é importar **no topo do arquivo**, não repetir o import dentro de cada função. `mod_renomear_empenho/telas.py` chegou a usar `notificar` em ~60 call sites sem o import; `mod_solicita_impressao/telas.py` importava `bd` em uma função e usava em outra. Escopo de módulo é o que o `pyflakes` valida sem complaint.
- **Dado de configuração malformado no seed passa como "fonte que nunca traz notícia" (25/09/2026):** a fonte `Folha de S.Paulo` tinha `https:/s.folha.uol.com.br/...` (**uma barra só**), e a coleta morria com `Request URL is missing an 'http://' or 'https://' protocol` — engolido pelo `try/except` do coletor. Sintoma: "aquela fonte nunca traz nada", sem rastro. Além de corrigir o seed, a correção robusta é uma **migração idempotente** que só reescreve o que está de fato quebrado (regex ancorado com lookahead, para não tocar em URL válida nem em fonte customizada do usuário).
- **Card com `min-height`/`max-height` fica irregular; `height` fixa uniformiza (25/09/2026):** no Agregador, `min-height:160px; max-height:220px` fazia a altura depender do conteúdo e a página ficava com cards de tamanhos diferentes. `height` fixa (300px desktop / 260px celular) resolve, e o texto longo vai para uma caixa de altura fixa com `overflow-y: auto` em vez de truncamento com reticências.
- **`<style>` injetado dentro de `@ui.refreshable` duplica a cada refresh (25/09/2026):** `ui.add_head_html` dentro de um `@ui.refreshable` reemite o CSS a cada busca e a cada paginação. Mova para fora do decorado, emitido uma vez por página.
- **Clique em elemento que convive com um link exige `.stop` + hierarquia irma (25/09/2026):** no redesenho do card, a miniatura clicável fica **irmã** do `ui.link` do título (nunca dentro dele) e usa o modificador **nativo** `.stop` (`Vue.withModifiers`, sem JavaScript à mão). Sem as duas camadas, o clique era absorvido pelo `<a>` e a ampliação nunca acontecia.

## Sugestão de expansão

Adicionar retrospectivas por fase, decisões de arquitetura (ADR) e melhorias de desempenho (WAL, ProcessPoolExecutor).

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Padrões de Codificação](../padroes_codificacao/index.md).
