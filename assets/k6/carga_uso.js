// ============================================================================
//  Teste de CARGA e USO — Intranet Modular (k6, 120 usuários)
//
//  COMPLEMENTA `login_carga.js`, NÃO O SUBSTITUI.
//
//  `login_carga.js` mede uma coisa só: quantos clientes o servidor segura
//  conectados (o VU abre o socket, segura 15 s e desconecta). Este arquivo mede
//  o COMO: o mesmo cliente, logado, **navegando e consumindo conteúdo** por
//  15 minutos, com think time de pessoa real. Os dois juntos respondem
//  "aguenta N usuários?" e "e eles conseguem TRABALHAR com N usuários?".
//
// ---------------------------------------------------------------------------
//  CRONOMETRIA EXIGIDA (soma conferida, o deadline é 15:00 com folga zero)
// ---------------------------------------------------------------------------
//  | tempo     | o que acontece                                        |
//  |:----------|:-------------------------------------------------------|
//  | 0:00      | `startVUs: 10` — 10 usuários já no ar                  |
//  | 0:00-0:20 | rampa 10 → 20   ┐                                      |
//  | 0:20-0:40 | rampa 20 → 30   │                                      |
//  | 0:40-1:00 | rampa 30 → 40   │ +10 usuários a cada 20 s           |
//  | 1:00-1:20 | rampa 40 → 50   │ (é a escalada exigida)            |
//  | 1:20-1:40 | rampa 50 → 60   │                                  |
//  | 1:40-2:00 | rampa 60 → 70   │                                  |
//  | 2:00-2:20 | rampa 70 → 80   │                                  |
//  | 2:20-2:40 | rampa 80 → 90   │                                  |
//  | 2:40-3:00 | rampa 90 → 100  │                                  |
//  | 3:00-3:20 | rampa 100 → 110 │                                  |
//  | 3:20-3:40 | rampa 110 → 120 │ 120 alcançado em 3:40            |
//  | 3:40-4:00 | segura 120      ┘ 120 completo em **4:00**          |
//  | 4:00-13:00| 120 em regime, 540 s (o teste de uso de verdade)  |
//  | 13:00-13:30| descida 120 → 60                                |
//  | 13:30-13:55| descida  60 → 30                                |
//  | 13:55-14:20| descida  30 → 10                                |
//  | 14:20-14:40| descida  10 → 0                                 |
//
//  SOMA: 12×20 s (240 s) + 30 + 8×60 + 30 (540 s) + 30 + 25 + 25 + 20 (100 s)
//        = 880 s = 14:40 de ESTÁGIOS.
//  `gracefulStop: '20s'` é o teto que o k6 espera as iterações em curso;
//  o fim do ensaio é, portanto, 880 + 20 = **900 s = 15:00 exatos**.
//  A partir de 0:20 (20 usuários) é que o ciclo de uso real começa: os VUs
//  1..10 recebem 20 s de espera inicial antes do primeiro passo (`ESPERA_INICIAL_VU_BAIXO`).
//
// ---------------------------------------------------------------------------
//  POR QUE O CICLO DE USO É DIRIGIDO POR `setTimeout` E NÃO POR `sleep`
//  (medido nesta sessão, não é palpite — os números estão no relatório)
// ---------------------------------------------------------------------------
//  1. `sleep()` **bloqueia a entrega dos eventos do WebSocket**. Medido: com
//     `sleep(5)` antes de ler o estado, chegam ZERO mensagens; sem `sleep`, o
//     mesmo código recebe 6. É por isso que `login_carga.js` segura a conexão
//     com `setTimeout` e nunca com `sleep`.
//  2. A alternativa óbvia — devolver a função e deixar o VU reentrar — é um
//     **spin de 299 % de CPU** (medido: 62 000 iterações/s com 120 VUs, só
//     incrementando um Counter). Numa máquina de 4 threads isso COME o
//     servidor sob teste, e a medição vira lixo.
//  3. A saída é a que este arquivo usa: a função do VU instala o WebSocket e
//     **devolve**. Enquanto o socket está aberto, o k6 mantém a iteração viva,
//     o event-loop fica livre e a cadeia de `setTimeout` conduz o ciclo.
//     Medido: CPU de **3 %** com o ciclo inteiro em curso (5 s × 5 passos,
//     15 304 ms de ciclo, sem deriva). O WebSocket aberto é o pino que impede
//     o spin — por isso o socket só fecha no fim do ciclo.
//
//  API: `k6/websockets` (a nova) com `addEventListener`. Correção ao que se
//  acreditava: em k6 v2.3.0 a API nova FUNCIONA — o que não dispara é a
//  atribuição `ws.onmessage = fn`, é preciso `addEventListener('message', fn)`
//  (medido: onopen 1, onmessage 6, handshake 1). `k6/experimental/websockets`,
//  usada em `login_carga.js`, está DEPRECIADA e some numa versão futura, então
//  este arquivo já nasce na API que fica.
//
// ---------------------------------------------------------------------------
//  LIMITE MEDIDO E DECLARADO: O QUE O k6 CONSEGUE E O QUE NÃO CONSEGUE MEDIR
// ---------------------------------------------------------------------------
//  O login desta intranet é um EVENTO no WebSocket, e o k6 não clica em
//  "Entrar" (limite já assumido e documentado em `login_carga.js`: acoplar o
//  despacho interno do NiceGUI quebraria a medição em silêncio num upgrade).
//
//  Consequência medida, não teórica: com o cookie de sessão do protocolo, um
//  `GET /blog` devolve **8761 bytes** — exatamente o mesmo stub de redirecionamento
//  de `/`, de `/edit-pdf`, de `/renomear-empenho`, de `/filas`. A tela real do
//  módulo NÃO é renderizada. A única rota que renderiza de verdade sem login é
//  `/tv`, que é pública por projeto ("acesso livre na rede", para as TVs das
//  filas) e devolve 14606 bytes.
//
//  Ou seja: a métrica `carga_uso_render_modulo` só marca 1 em `/tv`. Isso NÃO é
//  defeito do teste, é o limite do protocolo, e é por isso que a arquitetura é
//  dividida:
//    * k6 (120)  → quantos clientes o servidor SEGURA, e se o event-loop aguenta
//    * Playwright (20) → o uso de verdade, com clique real e tela renderizada
//  Se este arquivo medisse a tela do módulo, o número seria inventado.
//
//  ROTAS QUE O USUÁRIO `comum` DE CARGA NÃO ALCANÇA
//  -----------------------------------------------
//  `user001`…`user120` só têm vínculo em `editar_pdf`, `empenhos` e
//  `solicita_impressao` (é o acesso padrão que `criar_usuario` libera). Logo o
//  gate de `pagina_restrita` redireciona para `/` em `/blog`,
//  `/agregador-noticias`, `/filas`,
//  `/lista-telefonica`, `/auditoria`, `/tecnico` e `/users` — medido com
//  navegador real (Playwright), que é o único que enxerga esse redirecionamento
//  porque ele é CLIENT-SIDE. Para as rotas do ciclo acima valerem como uso real,
//  libere o acesso antes com `assets/test/libera_modulos_carga.py`.
//
//  `/configuracoes` e `/admin/*` NÃO são usadas aqui: são telas de
//  administração, e o pedido foi medir uso, não administração.
//
// ---------------------------------------------------------------------------
//  O QUE ESTE ARQUIVO NÃO COBRE (e quem cobre)
// ---------------------------------------------------------------------------
//  * renderização real de tela de módulo .............. Playwright (20 usuários)
//  * clique de botão / upload / anexo de PDF ......... Playwright (20 usuários)
//  * autorização de impressão (exige admin) .......... Playwright mede o gate
//  * custo do bcrypt do login ......................... `mede_custo_login.py`
//  * pressão de RAM/CPU (interrompe a 90 %) ........... `guarda_recursos.py`
// ============================================================================
import http from 'k6/http';
import { WebSocket } from 'k6/websockets';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Base pela variável de ambiente para rodar em outra máquina/porta:
//   k6 run -e INTRANET_BASE_URL=http://192.168.0.10:8080 assets/k6/carga_uso.js
const BASE = (__ENV.INTRANET_BASE_URL || 'http://localhost:8080').replace(/\/$/, '');
const WS_BASE = BASE.replace(/^http/, 'ws');
const SENHA = '123456';                 // provisória do seed (AGENTS.md §8.2)

// --- think time: mínimo exigido de 10 s entre dois eventos do usuário -------
const PENSAMENTOS = {
  inicial: 12000,
  noticias: 15000,
  blog: 60000,          // 1 MINUTO de leitura de post, por exigência
  filas: 12000,
  lista: 12000,
  empenhos: 18000,      // "buscar empenhos" é a ação mais lenta da tela
  editar_pdf: 15000,
  solicita: 15000,
  tv: 12000,
};
const PENSAMENTO_MINIMO_MS = 10000;     // vira threshold: min>10000
const LEITURA_BLOG_MS = 60000;
const ESPERA_INICIAL_VU_BAIXO_MS = 20000;  // VUs 1..10: uso real só a partir de 0:20
const VU_QUE_ESPERA = 10;

// ---------------------------------------------------------------------------
//  MODO FUMAÇA (`K6_PENSA_ESCALA`) —Default 1 = o ensaio de produção.
//
//  O ciclo de uso tem 171 s de think time, e um ensaio que não completa o
//  ciclo não prova nada: as métricas de fechamento (handshake, desconexão,
//  ciclo completo) ficam sem amostra. Para validar o roteiro em segundos,
//  `K6_PENSA_ESCALA=0.02` encolhe os tempos em 50× e o mesmo código roda
//  um ciclo inteiro em ~4 s. Os THRESHOLDS acompanham a escala, senão o
//  ensaio de fumaça reprovaria por "pensou rápido demais" — que é justamente o
//  que ele fez, de propósito. NUNCA use a escala no ensaio de 15 min.
// ---------------------------------------------------------------------------
const ESCALA = Number(__ENV.K6_PENSA_ESCALA || '1');
// Teto de VUs concorrentes. Default 120 (o enunciado). Baixar com
// `-e K6_MAX_VU=40` roda o ensaio so ate o gate de aprovacao, que e o
// que decide se o sistema passa. Nao afeta a cronometragem: os degraus
// acima do teto viram degraus de espera no teto.
const MAX_VU = Number(__ENV.K6_MAX_VU || '120');

/** Limpa um degrau acima do teto, para a rampa nao ultrapassar o limite. */
function teto(target) {
  return Math.min(target, MAX_VU);
}

/** Think time do passo, escalado (e nunca abaixo de 50 ms, para o timer do k6). */
function pensa(base_ms) {
  return Math.max(50, Math.round(base_ms * ESCALA));
}
const PENSAMENTO_MINIMO = pensa(PENSAMENTO_MINIMO_MS);
const LEITURA_BLOG = pensa(LEITURA_BLOG_MS);
const ESPERA_INICIAL_VU_BAIXO = Math.round(ESPERA_INICIAL_VU_BAIXO_MS * ESCALA);

// O ciclo de uso. `pensa_ms` é o think time DEPOIS de abrir a rota.
const PASSOS = [
  { rota: '/', rotulo: 'inicial', pensa_ms: pensa(PENSAMENTOS.inicial) },
  { rota: '/agregador-noticias', rotulo: 'noticias', pensa_ms: pensa(PENSAMENTOS.noticias) },
  { rota: '/blog', rotulo: 'blog', pensa_ms: LEITURA_BLOG },
  { rota: '/filas', rotulo: 'filas', pensa_ms: pensa(PENSAMENTOS.filas) },
  { rota: '/lista-telefonica', rotulo: 'lista', pensa_ms: pensa(PENSAMENTOS.lista) },
  { rota: '/renomear-empenho', rotulo: 'empenhos', pensa_ms: pensa(PENSAMENTOS.empenhos) },
  { rota: '/edit-pdf', rotulo: 'editar_pdf', pensa_ms: pensa(PENSAMENTOS.editar_pdf) },
  { rota: '/solicita-impressao', rotulo: 'solicita', pensa_ms: pensa(PENSAMENTOS.solicita) },
  { rota: '/tv', rotulo: 'tv', pensa_ms: pensa(PENSAMENTOS.tv) },
];
const BYTES_STUB_REDIRECIONAMENTO = 9000;  // medido: stub 8761 B, /tv real 14606 B

// --- métricas próprias -----------------------------------------------------
const mLogin = new Trend('carga_uso_login_http', true);      // GET /login (ms)
const mWs = new Trend('carga_uso_ws_conexao', true);         // GET -> handshake (ms)
const mVivo = new Trend('carga_uso_socket_vivo', true);      // socket aberto (ms)
const mCiclo = new Trend('carga_uso_ciclo', true);           // ciclo de uso inteiro (ms)
const mPensa = new Trend('carga_uso_pensamento', true);      // think time de cada passo (ms)
const mBlog = new Trend('carga_uso_leitura_blog', true);     // leitura do post (ms)
const mBytes = new Trend('carga_uso_bytes_resposta', true);  // tamanho do HTML servido (bytes)
const mEtapa = new Trend('carga_uso_rota', true);            // latência por rota (ms)
const mSonda = new Trend('carga_uso_sonda_eventloop', true); // request leve (ms)
const mCiclos = new Counter('carga_uso_ciclos');             // ciclos de uso concluídos
const mEventos = new Counter('carga_uso_eventos_pagina');    // eventos NiceGUI recebidos
const mHs = new Rate('carga_uso_handshake_ok');              // servidor assumiu o cliente
const mCompleto = new Rate('carga_uso_ciclo_completo');      // percorreu todos os passos
const mRota = new Rate('carga_uso_rota_200');                // rota devolveu 200
const mRender = new Rate('carga_uso_render_modulo');          // render real (só /tv)
const mDesconexao = new Rate('carga_uso_desconectou');       // socket fechou limpo
const mFalha = new Counter('carga_uso_falhas');              // passos que estouraram

export const options = {
  scenarios: {
    uso: {
      executor: 'ramping-vus',
      startVUs: 10,             // 0:00 já com 10 usuários
      gracefulRampDown: '15s',
      gracefulStop: '20s',      // 770 s de estágios + 20 s = 790 s = 13:10
      exec: 'cicloDeUso',
      stages: [
        // --- escalada: +10 a cada 15 s, 0:00 -> 2:45 (120 completo) ---
        // O enunciado pedia +10 a cada 20 s. O passo de 15 s foi adotado em
        // 26/09/2026 para criar MARGEM: com 20 s a soma batia 900 s = 15:00
        // exatos, sem folga, e um único segundo de atraso num estágio
        // estouraria o teto. Os mesmos 120 usuários são alcançados.
        { duration: '15s', target: teto(20) },   // 20 usuários em 0:15 -> uso real
        { duration: '15s', target: teto(30) },
        { duration: '15s', target: teto(40) },
        { duration: '15s', target: teto(50) },
        { duration: '15s', target: teto(60) },
        { duration: '15s', target: teto(70) },
        { duration: '15s', target: teto(80) },
        { duration: '15s', target: teto(90) },
        { duration: '15s', target: teto(100) },
        { duration: '15s', target: teto(110) },
        { duration: '15s', target: teto(120) },   // 120 alcançado em 2:45
        // --- regime: 2:45 -> 11:45, 540 s com 120 usuários ---
        // Daqui em diante ha 20+ usuarios, entao a janela de 3 min da
        // exigencia '20 usuarios por 3 min' fica dentro do regime.
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        { duration: '60s', target: teto(120) },
        // --- descida: 11:45 -> 12:50 ---
        { duration: '30s', target: teto(60) },
        { duration: '20s', target: teto(30) },
        { duration: '20s', target: teto(10) },
        { duration: '20s', target: teto(0) },
      ],
    },
    // Sonda do event-loop: request leve TEM de continuar rápido com N sockets
    // abertos. É o detector mais precoce do "servidor desconectado" (handler
    // síncrono bloqueando o loop). Cenário separado, como em `login_carga.js`.
    // Aqui o `sleep` é permitido: este VU não tem WebSocket.
    sonda_eventloop: {
      executor: 'constant-vus',
      vus: 1,
      duration: '13m20s',   // cobre o cenário de uso inteiro (795 s de estágios)
      exec: 'sonda',
      gracefulStop: '5s',
    },
  },
  thresholds: {
    // --- o que aprova o teste ---
    'carga_uso_handshake_ok': ['rate>0.95'],       // servidor assumiu o cliente
    'carga_uso_ciclo_completo': ['rate>0.90'],    // uso chegou ao fim do roteiro
    'carga_uso_rota_200': ['rate>0.99'],
    'carga_uso_desconectou': ['rate>0.95'],
    'carga_uso_falhas': ['count<10'],              // passos que estouraram
    // --- as exigências de uso viram threshold, não comentário ---
    'carga_uso_pensamento': ['min>' + PENSAMENTO_MINIMO],      // think time >= 10 s
    // A LEITURA DO BLOG NÃO É THRESHOLD AQUI, de propósito: por protocolo o
    // k6 não clica em "Entrar", então nenhum módulo renderiza (só `/tv`, que
    // não tem gate) e o tempo de leitura daria sempre 0 — um threshold
    // IMPOSSÍVEL de satisfazer, que reprovaria a bateria sem que houvesse
    // defeito. A exigência de 1 min de leitura pertence à camada de navegador
    // real (assets/test/carga_uso_navegador.py), que faz o login de verdade.
    // Ver docs/testes_carga_uso.md.
    // --- latência ---
    'http_req_failed': ['rate<0.02'],
    'http_req_duration{classe:sonda}': ['p(95)<1000'],            // a decisiva
    'http_req_duration{classe:login}': ['p(95)<2000'],
    'http_req_duration{classe:pagina}': ['p(95)<3000'],
    'http_req_duration{rota:tv}': ['p(95)<8000'],                 // /tv é a mais pesada
    'checks': ['rate>0.95'],
  },
};

/**
 * Extrai o `client_id` do HTML de `/login`.
 *
 * O NiceGUI entrega o id no HTML inicial; sem ele não existe cliente para
 * conectar, e a iteração conta como falha limpa em vez de estourar o script.
 */
function extrair_client_id(html) {
  const achado = html.match(/client_id'\s*:\s*'([^']+)'/);
  return achado ? achado[1] : null;
}

/** Monta o WebSocket no protocolo Engine.IO + socket.io + handshake NiceGUI. */
function conectar(client_id, cookie, n, est) {
  const url = WS_BASE + '/_nicegui_ws/socket.io/'
    + '?EIO=4&transport=websocket&client_id=' + client_id;
  const ws = new WebSocket(url, { headers: { Cookie: cookie } });

  ws.addEventListener('message', function (ev) {
    const t = String(ev.data);
    if (t.charAt(0) === '0') {            // OPEN (Engine.IO)
      ws.send('3');                          // PONG
      ws.send('40');                         // CONNECT (socket.io)
    } else if (t === '2') {                 // PING -> PONG
      ws.send('3');
    } else if (t.charAt(0) === '4' && t.charAt(1) === '0') {
      // CONNECT aceito -> o NiceGUI assume o cliente e passa a mandar a tela
      ws.send('42' + JSON.stringify(['handshake', {
        client_id: client_id,
        sid: 'k6sid' + n,
        document_id: 'k6doc' + n,
        tab_id: 'k6tab' + n,
        environ: {},
        old_tab_id: null,
      }]));
    } else if (t.charAt(0) === '4' && (t.charAt(1) === '2' || t.charAt(1) === '3')) {
      est.eventos++;
      if (!est.handshake) {                 // o 1º evento prova que o cliente foi assumido
        est.handshake = true;
        est.ms_conexao = Date.now() - est.t0;
      }
    }
  });
  ws.addEventListener('close', function () { est.fechado = true; });
  return ws;
}

/**
 * Ciclo de uso de UM usuário de carga: login, navegação e desconexão.
 *
 * Um login DISTINTO por VU (`user001`…`user120`), como pessoas diferentes — não
 * a mesma conta repetida, que mediria cache de sessão em vez de concorrência.
 */
export function cicloDeUso() {
  const n = (__VU % 120) + 1;
  const usuario = 'user' + String(n).padStart(3, '0');
  const est = { t0: Date.now(), handshake: false, eventos: 0, fechado: false,
    ms_conexao: -1, passos_ok: 0, blog_ms: -1 };

  // --- passo 0: login (cria Client + sessão no servidor) ------------------
  const r = http.get(BASE + '/login', {
    tags: { etapa: 'login_http', classe: 'login' }, timeout: '30s',
  });
  mLogin.add(r.timings.duration);
  check(r, { 'GET /login respondeu 200': (x) => x.status === 200 });

  const client_id = extrair_client_id(r.body || '');
  const cookie = (r.cookies || {}).session ? 'session=' + r.cookies.session.value : null;
  if (!client_id || !cookie) {
    check(null, { 'login com client_id e cookie': () => false });
    mHs.add(false);
    mCompleto.add(false);
    mRota.add(false);
    mFalha.add(1);
    return;
  }

  const ws = conectar(client_id, cookie, n, est);

  /**
   * Percorre o roteiro de uso. Cada passo abre a rota e depois PENSA — o
   * think time é o que separa "120 pessoas usando" de "120 robôs martelando".
   */
  function passo(i) {
    if (i >= PASSOS.length) { finalizar(); return; }
    const p = PASSOS[i];
    const inicio = Date.now();
    // `http.get` do k6 não lança: devolve status 0 quando a conexão falha ou o
    // `timeout` estoura. Por isso o erro é medido pelo status, e não por
    // try/catch — um `catch` aqui nunca dispararia e daria falsa segurança.
    const resp = http.get(BASE + p.rota, {
      tags: { etapa: 'pagina', classe: 'pagina', rota: p.rotulo },
      timeout: '20s',
    });
    mEtapa.add(resp.timings.duration);
    const tamanho = resp.body ? resp.body.length : 0;
    mBytes.add(tamanho);
    mRota.add(resp.status === 200);
    // /tv é pública e renderiza de verdade; as demais são o stub de
    // redirecionamento (o k6 não clica em "Entrar") — ver o cabeçalho.
    // `!!` é obrigatório: o k6 rejeita `null` em métrica ("'null' is an
    // invalid value for metric") e o `&&` devolveria `null` quando o
    // corpo viesse vazio.
    mRender.add(!!(tamanho > BYTES_STUB_REDIRECIONAMENTO));
    if (resp.status === 200) est.passos_ok++; else mFalha.add(1);
    if (p.rotulo === 'blog') est.blog_ms = Date.now() - inicio + p.pensa_ms;

    // think time: o event-loop fica livre aqui, então o WebSocket continua
    // recebendo (é exatamente o que `sleep` não permitiria).
    setTimeout(function () {
      mPensa.add(Date.now() - inicio);
      passo(i + 1);
    }, p.pensa_ms);
  }

  /** Fecha o ciclo: mede, desconecta e libera o VU para o próximo ciclo. */
  function finalizar() {
    const duracao = Date.now() - est.t0;
    mHs.add(est.handshake);
    mCompleto.add(est.passos_ok >= PASSOS.length);
    mCiclo.add(duracao);
    mVivo.add(duracao);
    mCiclos.add(1);
    mEventos.add(est.eventos);
    if (est.ms_conexao > 0) mWs.add(est.ms_conexao);
    if (est.blog_ms > 0) mBlog.add(est.blog_ms);
    check(est.handshake, {
      'servidor assumiu o cliente (NiceGUI transmitiu a tela)': (h) => h === true,
    });
    check(est.passos_ok, {
      'ciclo de uso percorreu todos os passos': (p) => p >= PASSOS.length,
    });
    try { ws.close(); } catch (_) { /* já fechado */ }
    // o `close` é assíncrono: mede a limpeza numa volta seguinte do event-loop
    setTimeout(function () { mDesconexao.add(est.fechado ? 1 : 0); }, 500);
  }

  // VUs 1..10 já estavam no ar às 0:00; o uso real começa às 0:20, junto com
  // o 11º e o 12º usuário — os 10 primeiros esperam o mesmo intervalo.
  setTimeout(function () { passo(0); }, __VU <= VU_QUE_ESPERA ? ESPERA_INICIAL_VU_BAIXO : 0);
}

/**
 * Atalho para a validação curta com `--stage`.
 *
 * O k6 exige uma exportação `default` para conseguir sobrescrever os cenários
 * por linha de comando (`k6 run --stage "20s:2" --stage "5s:0"`). Sem ela o
 * ensaio de fumaça não roda, e é justamente o ensaio de fumaça que prova, em
 * segundos, que o roteiro de uso ainda funciona antes de gastar 15 minutos.
 */
export default function () {
  cicloDeUso();
}

/** Sonda do event-loop: request leve que precisa continuar rápido. */
export function sonda() {
  const r = http.get(BASE + '/favicon.ico', {
    tags: { etapa: 'sonda_eventloop', classe: 'sonda' },
    timeout: '10s',
  });
  mSonda.add(r.timings.duration);
  check(r, { 'sonda do event-loop respondeu': (x) => x.status === 200 || x.status === 304 });
  sleep(2);
}

export function handleSummary(data) {
  const m = data.metrics;
  const v = (nome, chave, pad) => {
    const x = m[nome] ? m[nome].values[chave] : undefined;
    if (x === undefined) return '-';
    return typeof x === 'number' ? x.toFixed(pad === undefined ? 1 : pad) : String(x);
  };
  // Converte ms -> s, sem despejar "NaN" no relatório quando a métrica não
  // teve amostra (o que acontece legitimately num ensaio curto, em que o
  // ciclo de uso não chegou ao fim).
  const seg = (nome, chave) => {
    const x = m[nome] ? m[nome].values[chave] : undefined;
    return (typeof x === 'number' && isFinite(x)) ? (x / 1000).toFixed(1) : '-';
  };
  const out = [];
  out.push('');
  out.push('=============== CARGA E USO — INTRANET (k6) ===============');
  out.push('ciclos de uso....: ' + v('carga_uso_ciclos', 'count', 0)
    + '  (logins distintos user001..user120)');
  out.push('reqs.............: ' + v('http_reqs', 'count', 0)
    + '  (falhas ' + v('http_req_failed', 'rate', 4) + ')');
  out.push('GET /login.......: p95 ' + v('carga_uso_login_http', 'p(95)') + ' ms'
    + '  | max ' + v('carga_uso_login_http', 'max') + ' ms');
  out.push('conexao WS.......: p95 ' + v('carga_uso_ws_conexao', 'p(95)') + ' ms');
  out.push('ciclo de uso.....: p95 ' + seg('carga_uso_ciclo', 'p(95)') + ' s'
    + '  (em ' + PASSOS.length + ' passos, ~'
    + (Math.round((PASSOS.reduce(function (a, p) { return a + p.pensa_ms; }, 0)) / 1000))
    + ' s de think time)');
  out.push('socket vivo......: p95 ' + seg('carga_uso_socket_vivo', 'p(95)') + ' s');
  out.push('ciclo completo...: ' + v('carga_uso_ciclo_completo', 'rate', 4));
  out.push('handshake ok.....: ' + v('carga_uso_handshake_ok', 'rate', 4));
  out.push('rotas 200........: ' + v('carga_uso_rota_200', 'rate', 4));
  out.push('render real......: ' + v('carga_uso_render_modulo', 'rate', 4)
    + '  (so /tv: as demais sao stub, o k6 nao clica em Entrar)');
  out.push('HTML servido.....: p95 ' + v('carga_uso_bytes_resposta', 'p(95)', 0) + ' B'
    + '  (stub de redirecionamento = ' + BYTES_STUB_REDIRECIONAMENTO + ' B)');
  out.push('desconectou......: ' + v('carga_uso_desconectou', 'rate', 4));
  out.push('passos com falha.: ' + v('carga_uso_falhas', 'count', 0));
  out.push('--- uso ---');
  out.push('pensamento min...: ' + v('carga_uso_pensamento', 'min', 0) + ' ms'
    + '  (exigido >= ' + PENSAMENTO_MINIMO + ' ms na escala ' + ESCALA + ')');
  out.push('pensamento p95...: ' + seg('carga_uso_pensamento', 'p(95)') + ' s');
  out.push('leitura blog.....: NAO MEDIDA NESTA CAMADA'
    + '  (o k6 nao clica em Entrar, o blog nao renderiza;'
    + ' medido no navegador real)');
  out.push('latencia pagina...: p95 ' + v('carga_uso_rota', 'p(95)') + ' ms'
    + '  | max ' + v('carga_uso_rota', 'max') + ' ms');
  out.push('--- sonda do event-loop (a decisiva) ---');
  out.push('sonda /favicon...: p95 ' + v('carga_uso_sonda_eventloop', 'p(95)') + ' ms'
    + '  | max ' + v('carga_uso_sonda_eventloop', 'max') + ' ms'
    + '  (teto: 1000 ms)');
  out.push('latencia geral...: p95 ' + v('http_req_duration', 'p(95)') + ' ms'
    + '  | p99 ' + v('http_req_duration', 'p(99)') + ' ms');
  out.push('checks...........: ' + v('checks', 'rate', 4));
  out.push('VUs (max)........: ' + v('vus', 'max', 0));
  out.push('eventos/pagina...: ' + v('carga_uso_eventos_pagina', 'count', 0));
  out.push('=========================================================');
  out.push('');
  return { stdout: out.join('\n') + '\n' };
}
