// Helpers compartilhados da suíte E2E (Playwright).
//
// EN: Shared helpers for the E2E suite — error collection (console,
//     pageerror, failed requests, HTTP >= 400) and the login flow.
// PT: Helpers compartilhados da suíte E2E — coleta de erros (console,
//     pageerror, requisições falhas, HTTP >= 400) e o fluxo de login.

// Mensagens de console conhecidas como ruído (não representam erro real).
const RUIDO_CONSOLE = [
  'favicon',
  'ResizeObserver',
  'Vue Devtools',
  'Download the Vue Devtools',
  'Autofocus processing was blocked',
  'Using the main thread is often a performance issue',
];

function ehRuido(texto) {
  return RUIDO_CONSOLE.some(r => texto.includes(r));
}

// Anexa os listeners de captura e devolve a lista de erros (mutável).
function coletarErros(page) {
  const erros = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !ehRuido(msg.text())) {
      erros.push({ tipo: 'console', texto: msg.text() });
    }
  });
  page.on('pageerror', err =>
    erros.push({ tipo: 'pageerror', texto: String(err) }));
  page.on('requestfailed', req =>
    erros.push({
      tipo: 'requestfailed',
      url: req.url(),
      erro: req.failure()?.errorText ?? '',
    }));
  page.on('response', res => {
    const status = res.status();
    if (status >= 400) {
      erros.push({ tipo: 'http', status, url: res.url() });
    }
  });
  return erros;
}

// Erros que fazem o teste falhar de fato (pageerror / requestfailed /
// HTTP 4xx-5xx, exceto o 404 do favicon). Console é reportado sem falhar,
// para o relatório ajudar a diagnosticar sem falsos positivos.
function errosFatais(erros) {
  return erros.filter(e => {
    if (e.tipo === 'pageerror' || e.tipo === 'requestfailed') {
      return true;
    }
    if (e.tipo === 'http') {
      if (e.status === 404 && /favicon/i.test(e.url)) {
        return false;
      }
      return true;
    }
    return false;
  });
}

// Faz login no app e aguarda a volta para o dashboard.
// Obs.: NÃO usa networkidle — apps NiceGUI mantêm websocket/timers ativos e
// o networkidle nunca assenta; usamos domcontentloaded + espera fixa.
async function login(page, usuario, senha) {
  await page.goto('/login');
  await page.getByTestId('login-usuario').fill(usuario);
  await page.getByTestId('login-senha').fill(senha);
  await page.getByTestId('login-entrar').click();
  await page.waitForURL(url => !url.pathname.startsWith('/login'), {
    timeout: 20000,
  });
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1500);
}

module.exports = { coletarErros, errosFatais, login, RUIDO_CONSOLE };