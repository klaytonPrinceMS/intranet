# Test Cases — Intranet Modular

> Test cases and scripts available under `test/`. Manual scripts executed with the venv Python (no framework).

---

# Testes — Casos — Intranet Modular

> Casos de teste e scripts disponíveis em `test/`. Scripts manuais executados com o Python do venv (sem framework).

## Scripts disponíveis

| Script | Escopo |
|:---|:---|
| `test_server.py` | Smoke test do servidor (sobe e valida) |
| `test_auditoria.py` | Auditoria (12 verificações: índices em `tb_auditoria`, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral, preferência de campos/ordem por usuário) |
| `test_editor_pdf.py` | Editor PDF ponta a ponta (20 verificações: hash SHA-256, redução, união, corte, divisão, cotas, auditoria, expiração) |
| `test_solicita_impressao.py` | Solicitação de impressão (fórmula, cadastros, fluxo, cota, marca d'água, rascunho/expiração) |
| `test_fase1_login.py` / `validar_fase1_login.py` | Login (fase 1) |
| `test_fresh_install.py` / `fresh_install_test2.py` | Boot/seed (move os `.db` reais temporariamente — não interromper) |
| `diag_db.py` / `diag_config.py` | Diagnóstico de banco/config |
| `step_boot.py` / `debug_boot.py` / `wtest.py` | Auxiliares de boot/depuração |

## Como executar

```bash
.venv/bin/python test/test_server.py
.venv/bin/python test/test_auditoria.py
.venv/bin/python test/test_editor_pdf.py
```

Veja [Testes — Plano](../testes_plano/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
