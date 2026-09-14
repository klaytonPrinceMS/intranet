// Rodapé escondido com reveal no hover.
//
// EN: Auto-hide footer — opacity 0 with a 5px hint strip, revealed on hover
//     at full size with texts intact.
// PT: Rodapé escondido — opacity 0 com faixa de 5px, revela no hover no
//     tamanho original com os textos preservados.
// Evidência manual (Playwright headless, 14/09/2026): opacity 0 → 1.
const { test, expect } = require('@playwright/test');
const { login, coletarErros, errosFatais } = require('./helpers');

function listar(erros) {
  return erros.map(e => `[${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`).join('\n');
}

test.describe('Rodapé — escondido com reveal no hover', () => {
  test('inicia oculto e revela no hover com os textos', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qacomum', '123456');
    const rodape = page.getByTestId('rodape-sistema');
    await expect(rodape).toContainText('INTRANET Básica');
    await expect(await rodape.evaluate(e => getComputedStyle(e).opacity)).toBe('0');
    await rodape.hover();
    await expect.poll(
      () => rodape.evaluate(e => getComputedStyle(e).opacity),
      { timeout: 5000 }).toBe('1');
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });
});
