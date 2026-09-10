# Test Cases — Intranet Modular

> Test cases and scripts available under `test/`. Manual scripts executed with the venv Python (no framework).

---

# Testes — Casos — Intranet Modular

> Casos de teste e scripts disponíveis em `test/`. Scripts manuais executados com o Python do venv (sem framework).

## Scripts disponíveis

| Script | Escopo |
|:---|:---|
| `test_server.py` | Smoke test do servidor (sobe e valida) |
| `test/teste_aba_config_intranet.py` | Aba Config de `/configuracoes` campo a campo (render headless da tela real: ativação/habilitação/editabilidade — BASE_DIR readonly, valores iniciais do `tb_config`, APLICAR sem editar com anti-zeramento + reconfiguração de observabilidade + reagendamento de backups + reload, edição dos 19 campos → chaves corretas, saneamento 0/-3/99/"abc"/"gigante"/cor vazia, "Restaurar padrão" dos 4 cards + páginas nativas da aba Módulo, upload de favicon (.ico aplica; .png e vazio recusados) e acesso restrito a não-admin; autocontido — snapshot/restore de `tb_config`, favicon e `tb_modulos`) |
| `test_auditoria.py` | Auditoria (12 verificações: banco exclusivo `db_mod_auditoria.db`/tabela por módulo, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral, preferência de campos/ordem por usuário) |
| `test_editor_pdf.py` | Editor PDF ponta a ponta (32 verificações: hash SHA-256, redução, união, corte, divisão, cotas, auditoria, expiração) |
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
.venv/bin/python test/teste_aba_config_intranet.py
```

Veja [Testes — Plano](../testes_plano/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
