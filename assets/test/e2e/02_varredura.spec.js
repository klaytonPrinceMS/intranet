// Varredura E2E: percorre as principais rotas do sistema e identifica erros.
//
// EN: Walks the main system routes (pages, modules and admin panels) as
//     qamaster (administrator) and collects console errors, page errors,
//     failed requests and HTTP 4xx/5xx to identify problems.
// PT: Percorre as principais rotas do sistema (páginas, módulos e painéis de
//     administração) como qamaster (administrador) e coleta erros de console,
//     erros de página, requisições falhas e HTTP 4xx/5xx para identificar
//     problemas no sistema.
const { test, expect } = require('@playwright/test');
const { login, coletarErros, errosFatais } = require('./helpers');

const ROTAS = [
  '/',
  '/configuracoes',
  '/blog',
  '/edit-pdf',
  '/renomear-empenho',
  '/auditoria',
  '/users',
  '/solicita-impressao',
  '/admin/blog',
  '/admin/auditoria',
  '/admin/usuarios',
  '/admin/editar_pdf',
  '/admin/empenhos',
  '/admin/solicita_impressao',
];

test.describe('Varredura de erros nas rotas (qamaster)', () => {
  test('visita todas as rotas e não encontra erros fatais', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qamaster', '123456');

    for (const rota of ROTAS) {
      await page.goto(rota);
      // NiceGUI não fica "network idle" (websocket + timers contínuos):
      // espera-se o DOM carregado + tempo fixo para a página assentar.
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500);
    }

    const fatais = errosFatais(erros);
    console.log(`\n=== ERROS COLETADOS (${erros.length}) ===`);
    for (const e of erros) {
      console.log(` [${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`);
    }
    expect(fatais.length, `Erros fatais encontrados:\n${fatais.map(e => `[${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`).join('\n')}`)
      .toEqual(0);
  });
});