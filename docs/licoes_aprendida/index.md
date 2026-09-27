# Lessons Learned — Intranet Modular

> Lessons learned during development. Seed document — to be expanded as the team records post-mortems and improvements.

---

# Lições Aprendidas — Intranet Modular

> Lições aprendidas durante o desenvolvimento. Documento-semente — expandir com registros de post-mortem e melhorias.

## Lição em destaque (27/09/2026) — `!important` dentro de cascade layer: só o token vence

O Quasar declara `.bg-primary { background: var(--q-primary) !important }` e
`.text-primary { color: var(--q-primary) !important }` **dentro de uma cascade
layer**. Em `!important`, a **camada** vence **qualquer** regra fora de camada —
por mais específica que ela seja, e **por mais `!important` que esteja**, inclusive
um `!important` universal. Ou seja: a tentativa "pintar o botão por fora" — via
`.classes()`, `.style()`, seletor específico ou universal — **não tem como vencer**.

A única saída é mexer no **TOKEN** `--q-primary`, que é o mesmo mecanismo de
rebrand do próprio Quasar (`ui.colors`). Passou a ser a regra de ouro de qualquer
trabalho com cor neste projeto: **a cor primária entra pelo token; as fábricas com
`bg-primary`/`text-primary` são impossíveis de recolorar por CSS externo.** Quando
a cor *é* a informação (botão ativo × inativo), o controle tem de ser nosso e
redefinir o token no próprio elemento.

Isso não é teoria: custou uma rodada inteira de tentativa-e-erro na implementação
do estilo visual. Registrado em
[Estilo Visual — §7](../estilo_visual.md#7-a-armadilha-do-quasar-cascade-layer).

## Lição (27/09/2026) — falha silenciosa é a pior falha

`nicegui.context.request` **não existe mais** no NiceGUI 3 (o request foi para
`context.client.request`). A leitura devolvia vazio, o cookie nunca chegava — e
**nada quebrava de forma visível**: a tela abria, o rodapé desenhava, o clique
gravava o cookie, o log ficava limpo. Só o estilo não mudava. O conserto foi um
helper de 6 linhas que faz a cadeia (acesso novo primeiro, antigo como reserva),
com o motivo do "porque" no docstring.

A lição transversal: **`try/except` + retorno vazio escondem falha de API**.
Quando um valor "opcional" (cookie, header, query param) é a **entrada** de uma
feature, o fallback silencioso não é robustez — é a feature quebrada sem
diagnóstico. Registrar a versão da biblioteca consultada e testar o caminho real.

## Lição (27/09/2026) — preferência de tela: cookie, não `localStorage`, não banco

Duas decisões de escopo que valem para qualquer preferência **visual** daqui em
diante:

1. **Não no banco.** O estilo pertence ao *navegador* (cookie `estilo_visual`),
   não ao *usuário* — não viaja para outra máquina, não aparece para outra pessoa
   no mesmo login, e não polui a `tb_config` com algo que é do aparelho.
2. **Não `localStorage`.** O estilo é aplicado na **renderização, no servidor**.
   Com `localStorage` só existe JS no cliente: o servidor teria de pintar a tela
   no padrão errado e o navegador trocaria depois — piscada em toda troca, mais um
   round-trip, mais JS direto (proibido em AGENTS.md §5). O cookie é lido no
   request, então a página **já nasce** no estilo certo.

E a consequência que ninguém pergunta: a troca virou uma **rota HTTP de verdade**
(`303` + `Set-Cookie`), porque só uma resposta HTTP pode mandar cabeçalho — num
evento de WebSocket não há resposta para anexá-lo.

3. **Não no servidor, o "Padrão".** Quando o responsável definiu que "Padrão" seria
   uma opção do menu, a leitura ingênua seria tratá-lo como um **quinto estilo** com
   uma cor fixa. Isso é um erro de modelagem: "Padrão" significa **não impor
   imposição nenhuma**, e a cor que aparece passa a ser a que o **administrador do
   módulo** configurou. O código que materializa isso é um `if` de uma linha em
   `_montar_layout` — `if estilo_visual_usuario: aplicar(...)` — e o
   `estilo_efetivo()` passou a poder devolver `""`. Três efeitos que só aparecem
   depois da inversão:

   - o rótulo que mostra o que está valendo não pode mais mostrar um nome de
     estilo; sem estilo ele mostra a **procedência** ("cor do módulo"), porque
     dizer "verde" seria mentir sobre quem escolheu a cor;
   - a hierarquia de resolução **encolhe** de três degraus para um só, e a função
     que existia para dar o padrão do administrador (`estilo_padrao_sistema()`)
     ficou **código morto** — e perigoso, porque ainda devolvia um estilo. Como
     uma função morta desse tipo é convite para alguém voltar a chamá-la, ela
     foi **removida** (junto de `CONFIG_PADRAO_SISTEMA`, `aplicar_se_escolhido()`
     e `aplicar_para_usuario()`): a guarda `if estilo_visual_usuario:` ficou em
     `telas.py`, ao lado de quem monta a tela;
   - a chave no banco que existia para isso passou a ser semeada com o **nome da
     opção** (`'padrao'`), que é o valor que não impõe nada.

   O padrão de tela que **não** é uma tela: a lição é que uma opção de menu que
   significa "nada" precisa ser representada por um valor **vazio/válido** no
   fluxo inteiro, nunca por um valor sentinela que alguém possa ler como escolha.
   Ver [Estilo Visual — §4](../estilo_visual.md#4-hierarquia-de-resolucao-do-estilo).

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
- **`!important` em cascade layer só se vence pelo TOKEN `--q-primary` (27/09/2026):** `.bg-primary`/`.text-primary` do Quasar são `!important` **dentro de uma cascade layer** — em `!important` a camada ganha de **qualquer** regra fora de camada, por mais específica ou `!important` que seja (inclusive universal). **Impossível recolorir por fora**; a saída é o token `--q-primary` no `.q-layout` (mesmo mecanismo de `ui.colors`). Uma regra "não funciona" neste stack quase sempre foi **layer + `!important`**, não especificidade insuficiente — vale para qualquer biblioteca CSS que crie cascade layers.
- **Falha silenciosa é a pior falha (27/09/2026):** `nicegui.context.request` deixou de existir no NiceGUI 3 (vai para `context.client.request`); a leitura vazia fazia o cookie nunca chegar, **sem erro, sem log** — tela abria, clique gravava, estilo não mudava. Regra: quando um valor "opcional" (cookie, header, query param) é a **entrada** de uma feature, o fallback silencioso não é robustez — é a feature quebrada sem diagnóstico. Fixar a versão da lib consultada e exercitar o caminho real.
- **Preferência de tela vai no COOKIE, não no banco e não em `localStorage` (27/09/2026):** o estilo pertence ao *navegador*, não ao *usuário* (não viaja de máquina, não aparece para outro login no mesmo aparelho, não polui `tb_config`); e, como o estilo é aplicado **no servidor na renderização**, `localStorage` obrigaria a tela a nascer no padrão errado e piscar — além de exigir JS direto, proibido em AGENTS.md §5. Consequência: a troca virou **rota HTTP de verdade** (`303` + `Set-Cookie`), já que só resposta HTTP manda cabeçalho.
- **Paleta de marca: valide contraste ANTES de adotar o verde/ciano oficial (27/09/2026):** o verde vivo do WhatsApp `#25D366` dá **1,98:1** com branco e **reprova** a WCAG AA (4,5:1). A solução foi manter a identidade usando o **tom mais escuro da própria marca** (`#0F7A6D`, 5,22:1) como cor de ação e reservar o `#25D366` como acento. O mesmo valeu para o azul (`#1668D8`, 5,24:1, em vez de `#1877F2`, 4,23:1). A medição continua válida mesmo depois de o tema do sistema ter voltado ao preto no mesmo dia: a regra é sobre **qualquer** cor que vá virar fundo de botão com texto branco, e o `preto` do estilo (`#111111`, 18,88:1) e o do tema (`#000000`, 21:1) passam com folga. Lição maior: **paleta de tela e paleta de marca são coisas diferentes** — oferecer uma paleta de marca como *opção* é válido; oferecê-la como *padrão do sistema* mistura as duas e briga com quem administra a configuração do sistema por conta própria.

## Sugestão de expansão

Adicionar retrospectivas por fase, decisões de arquitetura (ADR) e melhorias de desempenho (WAL, ProcessPoolExecutor).

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Padrões de Codificação](../padroes_codificacao/index.md).
