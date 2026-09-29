# Risk Analysis — Intranet Modular

> Risk analysis for the Intranet Modular. Seed document — to be expanded with a full risk register (likelihood × impact, mitigations).

---

# Análise de Risco — Intranet Modular

> Análise de riscos do sistema. Documento-semente — expandir com registro de riscos completo (probabilidade × impacto, mitigações).

## Riscos conhecidos (semente)

| Risco | Impacto | Mitigação atual |
|:---|:---|:---|
| **Conta de fábrica `master` ressurreita pelo seed a cada reinício** (ocorrido em 29/09/2026) | **Alto** — credencial de fábrica de volta, com perfil `administrador_geral`, logo após a troca de credenciais; o diálogo de troca reabre em ciclo | **Corrigido.** A guarda do seed passou a ter duas condições: respeita a marca `forcar_troca_credenciais:master` no `tb_config` central (`'0'` = troca concluída), e não só a ausência do login. O `bd_criador.py` — segundo caminho de criação da conta — passou a **levantar**. Detalhes: [Conta de fábrica `master` ressuscitando (29/09/2026)](../seguranca/conta_de_fabrica_master_2026-09-29.md) |
| **Estado que se auto-restaura** — padrão, não só este caso | Médio/alto — qualquer seed que recrie o que um fluxo de segurança removeu desfaz a remoção no boot seguinte | **Padrão documentado:** o seed lê a **marca do fluxo**, não a ausência da linha; a marca, uma vez gravada, não se desfaz sozinha. Mesma peça conceitual do marcador de migração do versionamento ([§3.1](../versionamento/index.md#31-o-modelo-da-migracao-de-bump)) |
| **Ciclo travado na troca de credenciais** — nome pré-preenchido já em uso | Médio — a recusa de `renomear_usuario` impedia o rename, e as flags de troca só caem **depois** de um rename bem-sucedido: sem caminho de saída | **Corrigido:** a recusa passou a dizer o que fazer (`'x' já é o login de outro usuário. Escolha um nome de usuário diferente.`) |
| `storage_secret` placeholder em `main.py` | Segredo fraco em produção | Trocar antes de produção (ver `../../AGENTSadf.md`) |
| Rede interna exposta à internet | Vazamento/intrusão | Operação restrita a intranet; sem CDN |
| Corrupção de caracteres em `main.py` (histórico PowerShell) | Quebra de boot | Validar com `ast.parse` todo `.py` |
| `bd_criador.py` legado aponta para banco central | Dados incorretos se usado | Não confiar como fonte; usar `bd_manipulador.py`. **Em `mod_gest_cad_usuario` e `mod_edit_pdf` o `init_db()` legado já levanta `RuntimeError`** |
| Retenção de sessões/auditoria (LGPD) | Conformidade | `tb_sessoes` podada (50/usuário); tabelas de auditoria (`db_mod_auditoria.db`) podadas diariamente por `auditoria_retencao_dias` (default 90, configurável no módulo) |

## Sugestão de expansão

Adicionar matriz de riscos por módulo, plano de contingência de backup e teste de recuperação (restore de `backup/`).

Veja [Plano de Projeto](../plano_de_projeto/index.md) e [Registro de Mudanças](../registro_de_mudancas/index.md).
