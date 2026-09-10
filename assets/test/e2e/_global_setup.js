// Global setup for the Playwright E2E suite.
//
// EN: Runs once before the whole suite — ensures the QA test credentials
//     (qacomum/qamaster = 123456) via the venv Python script.
// PT: Executa uma única vez antes da suíte — garante as credenciais de teste
//     QA (qacomum/qamaster = 123456) via o script Python do venv.
const { execSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const venvPython = path.join(root, '.venv', 'bin', 'python');
const script = path.join(__dirname, '_garantir_credenciais.py');

module.exports = async function globalSetup() {
  execSync(`"${venvPython}" "${script}"`, { cwd: root, stdio: 'inherit' });
};