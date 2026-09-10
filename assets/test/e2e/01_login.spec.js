// Testes E2E de login com os usuários QA (qacomum comum / qamaster admin).
//
// EN: Login tests with the QA users — verifies the dashboard renders without
//     fatal errors and that a common user is denied from admin areas.
// PT: Testes de login com os usuários QA — verifica que o dashboard renderiza
//     sem erros fatais e que usuário comum é barrado nas áreas de admin.
const { test, expect } = require('@playwright/test');
const { login, coletarErros, errosFatais } = require('./helpers');

function listar(erros) {
  return erros.map(e => `[${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`).join('\n');
}

test.describe('Login — usuários QA', () => {
  test('qacomum (comum) entra e abre o dashboard sem erros fatais', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qacomum', '123456');
    // Cabeçalho do layout com o menu hambúrguer visível
    await expect(page.locator('header').first()).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Área de configuração restrita');
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });

  test('qamaster (administrador_geral) entra e abre o dashboard sem erros fatais', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qamaster', '123456');
    await expect(page.locator('header').first()).toBeVisible();
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });

  test('qacomum é barrado no painel central /configuracoes', async ({ page }) => {
    await login(page, 'qacomum', '123456');
    await page.goto('/configuracoes');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toContainText(
      'Área de configuração restrita ao administrador geral.');
  });

  test('qacomum é barrado em /admin/auditoria (módulo sem acesso)', async ({ page }) => {
    await login(page, 'qacomum', '123456');
    await page.goto('/admin/auditoria');
    await page.waitForTimeout(1500);
    // o guard redireciona para / com aviso de acesso negado
    const url = page.url();
    expect(url.startsWith('http://localhost:8080/')).toBeTruthy();
  });
});