// Editor WYSIWYG do Blog — upload, controles da imagem e Markdown.
//
// EN: Blog editor — image upload with dataHora_user naming, alignment/width
//     controls on the last image, Markdown headings rendered on preview.
// PT: Editor do Blog — envio de imagem (JPG/PNG), alinhamento/largura na
//     última imagem e Markdown (#/##/###) rendendo na pré-visualização.
// Evidência manual (Playwright headless, 14/09/2026): upload gerou
// `AAMMDDHHMM_qamaster.png` + tag inserida; centro+50% rendeu sem
// `float:left`; preview de `# Título` rendeu h1.
// NOTA: usa upload real — as imagens órfãs expiram via `cleanup_blog_imagens`
// em até ~6 min; a publicação de QA deve ser excluída ao final do teste.
const { test, expect } = require('@playwright/test');
const { login, coletarErros, errosFatais } = require('./helpers');
const fs = require('fs');
const os = require('os');
const path = require('path');

function listar(erros) {
  return erros.map(e => `[${e.tipo}] ${e.texto || `${e.status} ${e.url}`} ${e.erro || ''}`).join('\n');
}

// PNG mínimo válido (1x1) para o validador de assinatura do servidor.
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64');

test.describe('Blog — editor com imagens e Markdown', () => {
  test('controles visíveis e Markdown rende na pré-visualização', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qamaster', '123456');
    await page.goto('/blog');
    await page.waitForLoadState('networkidle');
    for (const tid of ['blog-img-esq', 'blog-img-centro', 'blog-img-dir', 'blog-img-largura']) {
      await expect(page.getByTestId(tid)).toBeVisible();
    }
    await page.evaluate(() => {
      const ed = document.querySelector("[data-testid='blog-conteudo'] .q-editor__content");
      ed.focus();
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, '# Titulo QA\n\nTexto **forte**');
    });
    await page.getByText('Pré-visualizar').click();
    await expect(page.locator('h1').first()).toContainText('Titulo QA');
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });

  test('upload insere a tag e centro+50% rende sem float:left', async ({ page }) => {
    const erros = coletarErros(page);
    await login(page, 'qamaster', '123456');
    await page.goto('/blog');
    await page.waitForLoadState('networkidle');
    const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'blogqa-')), 'qa.png');
    fs.writeFileSync(tmp, PNG_1X1);
    await page.locator("[data-testid='blog-imagem-selecionar'] input[type=file]")
      .setInputFiles(tmp);
    await page.getByTestId('blog-imagem-enviar').click();
    await expect.poll(async () => page.evaluate(() =>
      document.querySelector("[data-testid='blog-conteudo'] .q-editor__content").innerHTML
        .includes('/img_postagens/')), { timeout: 15000 }).toBe(true);
    await page.getByTestId('blog-img-centro').click();
    await page.getByTestId('blog-titulo').fill('QA e2e imagem centro 50');
    await page.locator("[data-testid='blog-img-largura']").click();
    await page.locator('.q-menu .q-item:has-text("50%")').click();
    await page.getByTestId('blog-publicar').click();
    const img = page.locator('img[src*=img_postagens]').first();
    await expect(img).toBeVisible({ timeout: 15000 });
    const style = await img.getAttribute('style');
    expect(style).toContain('max-width:50%');
    expect(style).not.toContain('float:left');
    const fatais = errosFatais(erros);
    expect(fatais, listar(fatais)).toEqual([]);
  });
});
