# Risk Analysis — Intranet Modular

> Risk analysis for the Intranet Modular. Seed document — to be expanded with a full risk register (likelihood × impact, mitigations).

---

# Análise de Risco — Intranet Modular

> Análise de riscos do sistema. Documento-semente — expandir com registro de riscos completo (probabilidade × impacto, mitigações).

## Riscos conhecidos (semente)

| Risco | Impacto | Mitigação atual |
|:---|:---|:---|
| `storage_secret` placeholder em `main.py` | Segredo fraco em produção | Trocar antes de produção (ver `AGENTS.md`) |
| Rede interna exposta à internet | Vazamento/intrusão | Operação restrita a intranet; sem CDN |
| Corrupção de caracteres em `main.py` (histórico PowerShell) | Quebra de boot | Validar com `ast.parse` todo `.py` |
| `criador_bd.py` legado aponta para banco central | Dados incorretos se usado | Não confiar como fonte; usar `manipulador_bd.py` |
| Retenção de sessões/auditoria (LGPD) | Conformidade | `tb_sessoes` podada (50/usuário); `tb_auditoria` podada diariamente por `auditoria_retencao_dias` (default 90, configurável no módulo) |

## Sugestão de expansão

Adicionar matriz de riscos por módulo, plano de contingência de backup e teste de recuperação (restore de `backup/`).

Veja [Plano de Projeto](../plano_de_projeto/index.md) e [Registro de Mudanças](../registro_de_mudancas/index.md).
