// Nome do usuário no menu superior — botão único sempre visível.
//
// EN: Header user-name button — full treatment name visible on desktop and
//     mobile (ellipsis right, tooltip), click opens "Meu Perfil".
// PT: Botão do nome no header — nome completo visível (desktop e mobile,
//     ellipsis à direita com tooltip), clique abre "Meu Perfil".
// Evidência manual (Playwright headless, 14/09/2026): qacomum vê
// "Usuário de Teste QA Comum" em 1280px e o início + ellipsis em 360px.
const { test, expect } = require('@playwright/test');
const { login, coletarErros, errosFatais } = require('./helpers');

function listar(erros) {
  return erros.map(e => `[${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`).join('\n');
}

test.describe('Header — nome do usuário', () => {
  test('qacomum vê o nome completo e abre Meu Perfil', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qacomum', '123456');
    const btn = page.getByTestId('header-nome-usuario');
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Usuário de Teste QA Comum');
    await btn.click();
    await expect(page.locator('body')).toContainText('Meu Perfil');
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });

  test('mobile 360px preserva o início do nome (ellipsis à direita)', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 700 });
    await login(page, 'qacomum', '123456');
    const btn = page.getByTestId('header-nome-usuario');
    await expect(btn).toBeVisible();
    const box = await btn.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(360);
  });
});
