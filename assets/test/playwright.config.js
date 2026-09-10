// Playwright configuration for the Intranet Modular E2E tests.
//
// EN: Runs the E2E suite defined in ./e2e against the NiceGUI app on
//     http://localhost:8080 (starts it via webServer if not already running,
//     reusing an existing server when available). Credentials for the QA
//     users (qacomum/qamaster = 123456) are ensured by the global setup.
//
// PT: Roda a suíte E2E definida em ./e2e contra o app NiceGUI em
//     http://localhost:8080 (o webServer inicia o app caso não esteja de pé,
//     reutilizando um servidor já ativo quando houver). As credenciais dos
//     usuários QA (qacomum/qamaster = 123456) são garantidas no global setup.
//
// Executar (na raiz do projeto):
//   npm run test:e2e                 # roda toda a suíte
//   npx playwright test --config test/playwright.config.js --headed
//   npx playwright show-report       # abre o relatório HTML
const path = require('path');
const { defineConfig } = require('@playwright/test');

const root = path.resolve(__dirname, '..', '..');
const venvPython = path.join(root, '.venv', 'bin', 'python');

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 60000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: 'http://localhost:8080',
    headless: true,
    viewport: { width: 1366, height: 768 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: 'test-results',
  globalSetup: './e2e/_global_setup.js',
  webServer: {
    command: `cd "${root}" && "${venvPython}" main.py`,
    url: 'http://localhost:8080/login',
    reuseExistingServer: true,
    timeout: 120000,
  },
});