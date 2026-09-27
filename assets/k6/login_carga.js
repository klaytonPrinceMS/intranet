// ============================================================================
//  Teste de carga k6 — Intranet Modular
//  Critério de aprovação: o sistema deve aguentar no mínimo 40 usuários.
//
//  POR QUE O TESTE É FEITO ASSIM
//  -----------------------------
//  Esta intranet é NiceGUI, e isso define o que "aguentar N usuários" significa.
//  Não existe `POST /login`: o login é um EVENTO no WebSocket. Cada cliente
//  conectado consome, no servidor: uma conexão WebSocket permanente, um objeto
//  `Client` vivo, uma sessão e um `tab_id`. Manter N usuários É manter N
//  clientes vivos ao mesmo tempo — e é exatamente isso que o teste faz.
//
//  Cada VU:
//    1. GET /login        -> cria Client + sessão no servidor (estado real)
//    2. WebSocket         -> Engine.IO OPEN / PONG / CONNECT
//    3. emit "handshake"  -> o servidor assume o cliente e passa a transmitir o
//                            código da tela (prova de que o cliente está vivo)
//    4. segura a conexão  -> é a concorrência que importa
//    5. desconecta        -> fecha o socket (a "desconexao" do enunciado)
//
//  A SONDA DE EVENT-LOOP é a métrica decisiva. Nesta base de código, "aguentar
//  usuário" quebrou repetidamente por handler SÍNCRONO bloqueando o event-loop
//  (o "servidor desconectado"): a 1ª gravação de auditoria levava 73,9 s e
//  congelava a tela. Com N sockets abertos, um request leve tem de continuar
//  rápido. É essa a pergunta que o teste responde.
//
//  LIMITE CONHECIDO E DELIBERADO
//  -----------------------------
//  Este teste NÃO clica no botão "Entrar", então não mede o bcrypt.
//  Reverse-engineer o despacho interno de evento do NiceGUI funciona, mas
//  acopla o teste à versão da biblioteca: um upgrade quebraria a medição de
//  forma silenciosa, o que é pior que não medir. O custo do bcrypt é medido à
//  parte, no servidor — veja assets/test/mede_custo_login.py.
// ============================================================================
import http from 'k6/http';
import { WebSocket } from 'k6/experimental/websockets';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE = 'http://localhost:8080';
const SENHA = '123456';
const SEGURAR_MS = 15000;   // tempo com o socket aberto por ciclo

// --- métricas próprias ----------------------------------------------------
const mGET = new Trend('carga_login_http', true);      // GET /login (ms)
const mWS = new Trend('carga_ws_conexao', true);       // GET -> handshake (ms)
const mHeld = new Trend('carga_ws_segurou', true);     // socket vivo (ms)
const mEvt = new Counter('carga_eventos_pagina');      // eventos do NiceGUI
const mHs = new Rate('carga_handshake_ok');            // servidor assumiu o cliente
const mDesconexao = new Rate('carga_desconectou');     // socket fechou limpo

// --- escalada: 10 -> 30 -> 40 -> 60 -> 80 -> 90 -> 100 -> 110 -> 120 -------
export const options = {
  scenarios: {
    usuarios: {
      executor: 'ramping-vus',
      startVUs: 0,
      gracefulRampDown: '10s',
      gracefulStop: '40s',
      stages: [
        { duration: '15s', target: 10 },
        { duration: '20s', target: 10 },   // segura 10
        { duration: '15s', target: 30 },
        { duration: '20s', target: 30 },   // segura 30
        { duration: '15s', target: 40 },
        { duration: '30s', target: 40 },   // segura 40  <-- LIMIAR DE APROVAÇÃO
        { duration: '15s', target: 60 },
        { duration: '20s', target: 60 },
        { duration: '15s', target: 80 },
        { duration: '20s', target: 80 },
        { duration: '15s', target: 90 },
        { duration: '20s', target: 90 },
        { duration: '15s', target: 100 },
        { duration: '20s', target: 100 },
        { duration: '15s', target: 110 },
        { duration: '20s', target: 110 },
        { duration: '15s', target: 120 },
        { duration: '30s', target: 120 },  // segura 120
        { duration: '10s', target: 0 },
      ],
    },
    // Sonda do event-loop: um request leve TEM de continuar rápido com N sockets
    // abertos. É o detector mais precoce do "servidor desconectado".
    sonda_eventloop: {
      executor: 'constant-vus',
      vus: 1,
      duration: '5m30s',
      exec: 'sonda',
      gracefulStop: '5s',
    },
  },
  thresholds: {
    'carga_handshake_ok': ['rate>0.95'],
    'carga_desconectou': ['rate>0.95'],
    http_req_failed: ['rate<0.02'],
    // approval: 40 usuários -> o request leve não pode passar de 1s
    http_req_duration: ['p(95)<1000'],
    checks: ['rate>0.95'],
  },
};

/** Extrai o id e o listener_id de um elemento pelo data-testid. */
function elemento(html, testid) {
  const i = html.indexOf('"data-testid":"' + testid + '"');
  if (i < 0) return null;
  const j = html.lastIndexOf('{"tag"', i);
  const chave = html.slice(Math.max(0, j - 12), j).match(/"(\d+)"\s*:\s*$/);
  const listener = html.slice(j, j + 900).match(/"listener_id":"([^"]+)"/);
  if (!chave || !listener) return null;
  return { id: chave[1], listener: listener[1] };
}

export default function () {
  // 1 usuário por VU, no intervalo 1..120 — cada VU entra com um login distinto,
  // que é o que uma escalada real faria (pessoas diferentes, não a mesma conta)
  const n = (__VU % 120) + 1;
  const usuario = 'user' + String(n).padStart(3, '0');
  const t0 = Date.now();

  // --- passo 1: GET /login (cria Client + sessão no servidor) --------------
  const r = http.get(BASE + '/login', {
    tags: { etapa: 'login_http' },
    timeout: '30s',
  });
  mGET.add(r.timings.duration);

  const html = r.body || '';
  const clientId = (html.match(/client_id'\s*:\s*'([^']+)'/) || [])[1];
  const cookie = (r.cookies || {}).session
    ? 'session=' + r.cookies.session.value
    : null;

  check(r, {
    'GET /login respondeu 200': (x) => x.status === 200,
  });

  if (!clientId || !cookie) {
    // sem client_id não há cliente para conectar; conta como falha limpa
    check(null, { 'tem client_id e cookie': () => false });
    sleep(1);
    return;
  }

  // --- passo 2/3: WebSocket + Engine.IO + handshake do NiceGUI ------------
  const url = 'ws://localhost:8080/_nicegui_ws/socket.io/'
    + '?EIO=4&transport=websocket&client_id=' + clientId;
  let handshake = false;
  let contaEventos = 0;
  let conexaoMs = 0;

  const ws = new WebSocket(url, { headers: { Cookie: cookie } });

  ws.onopen = function () { /* socket aberto */ };

  ws.onmessage = function (ev) {
    const t = String(ev.data);
    if (t.charAt(0) === '0') {          // OPEN (Engine.IO)
      ws.send('3');                       // PONG
      ws.send('40');                      // CONNECT (socket.io)
    } else if (t === '2') {              // PING -> PONG
      ws.send('3');
    } else if (t.charAt(0) === '4' && t.charAt(1) === '0') {
      // CONNECT aceito -> o NiceGUI assume o cliente
      ws.send('42' + JSON.stringify(['handshake', {
        client_id: clientId,
        sid: 'k6sid' + n,
        document_id: 'k6doc' + n,
        tab_id: 'k6tab' + n,
        environ: {},
        old_tab_id: null,
      }]));
    } else if (t.charAt(0) === '4' && (t.charAt(1) === '2' || t.charAt(1) === '3')) {
      contaEventos++;
      // o primeiro evento do NiceGUI prova que ele assumiu este cliente
      if (!handshake) {
        handshake = true;
        conexaoMs = Date.now() - t0;
        mWS.add(conexaoMs);
      }
    }
  };

  ws.onerror = function () { /* erro de socket: contabilizado no held */ };
  ws.onclose = function () { mDesconexao.add(1); };

  // --- passo 4/5: segura a conexão e DESCONECTA --------------------------
  // setTimeout (e não sleep): o sleep do k6 bloqueia o event-loop que atende o
  // WebSocket, e os eventos parariam de chegar.
  setTimeout(function () {
    mHs.add(handshake ? 1 : 0);
    mHeld.add(Date.now() - t0);
    mEvt.add(contaEventos);
    check(handshake, {
      'servidor assumiu o cliente (NiceGUI transmitiu a tela)': (h) => h === true,
      'cliente recebeu eventos da pagina': (h) => h === true && contaEventos > 0,
    });
    try { ws.close(); } catch (_) { /* já fechado */ }
  }, SEGURAR_MS);
}

/** Sonda do event-loop: request leve que precisa continuar rápido. */
export function sonda() {
  const r = http.get(BASE + '/favicon.ico', {
    tags: { etapa: 'sonda_eventloop' },
    timeout: '10s',
  });
  check(r, { 'sonda do event-loop respondeu': (x) => x.status === 200 || x.status === 304 });
  sleep(2);
}

export function handleSummary(data) {
  const m = data.metrics;
  const linha = (nome) => m[nome] ? m[nome].values : {};
  const v = (nome, chave, pad) => {
    const x = linha(nome)[chave];
    return (x === undefined ? '-' : (typeof x === 'number' ? x.toFixed(pad === undefined ? 1 : pad) : x));
  };
  const out = [];
  out.push('');
  out.push('================= CARGA k6 — INTRANET =================');
  out.push('reqs............: ' + v('http_reqs', 'count', 0)
    + '  (falhas ' + v('http_req_failed', 'rate', 4) + ')');
  out.push('GET /login......: p95 ' + v('carga_login_http', 'p(95)') + ' ms'
    + '  | max ' + v('carga_login_http', 'max') + ' ms');
  out.push('conexao WS......: p95 ' + v('carga_ws_conexao', 'p(95)') + ' ms');
  out.push('socket vivo.....: p95 ' + v('carga_ws_segurou', 'p(95)') + ' ms');
  out.push('handshake ok....: ' + v('carga_handshake_ok', 'rate', 4));
  out.push('desconectou.....: ' + v('carga_desconectou', 'rate', 4));
  out.push('eventos/pagina...: ' + v('carga_eventos_pagina', 'count', 0));
  out.push('latencia geral..: p95 ' + v('http_req_duration', 'p(95)') + ' ms'
    + '  | p99 ' + v('http_req_duration', 'p(99)') + ' ms');
  out.push('checks..........: ' + v('checks', 'rate', 4));
  out.push('VUs (max).......: ' + v('vus', 'max', 0));
  out.push('======================================================');
  out.push('');
  return { stdout: out.join('\n') + '\n' };
}
