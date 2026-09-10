// Regression: exclusão de postagem no Blog não pode derrubar a conexão.
// Reproduz o bug "sistema trava + servidor desconectado + post não some".
const { test, expect } = require('@playwright/test');
const { login } = require('./helpers');

const MARCA = `REPRO-${Date.now()}`;

test('excluir postagem não desconecta nem deixa o post na tela', async ({
  page,
}) => {
  const erros = [];
  let websocketFechado = false;

  page.on('console', (m) => {
    if (m.type() === 'error') erros.push(`console: ${m.text()}`);
  });
  page.on('pageerror', (e) => erros.push(`pageerror: ${e.message}`));
  page.on('websocket', (ws) => {
    ws.on('close', () => {
      websocketFechado = true;
    });
  });

  await login(page, 'qamaster', '123456');
  await page.goto('/blog');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1500);

  // Cria uma postagem marcada
  await page.getByTestId('blog-titulo').fill(`Exclusão ${MARCA}`);
  await page.getByPlaceholder('Conteúdo*').fill(`Conteúdo de teste ${MARCA}`);
  await page.getByTestId('blog-publicar').click();
  await page.waitForTimeout(2000);

  const aparece = await page.getByText(`Exclusão ${MARCA}`).count();
  expect(aparece).toBeGreaterThan(0);

  // Exclui a postagem recém-criada
  await page.getByTestId('blog-excluir').first().click();
  await page.waitForTimeout(4000);

  const aindaPresente = await page.getByText(`Exclusão ${MARCA}`).count();
  expect(aindaPresente).toBe(0, `post ${MARCA} deveria ter sumido da tela`);

  // Depois de excluir, a conexão continua viva: navega e segue funcionando
  await page.goto('/blog');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1500);
  expect(page.url()).toContain('/blog');

  expect(websocketFechado, 'websocket não deveria ter fechado').toBe(false);
  expect(erros, 'sem erros no console do navegador').toEqual([]);
});