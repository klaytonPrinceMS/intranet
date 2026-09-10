# AI / ML Security Risks — Intranet Modular

> Risks of language models and machine learning applied to the system: prompt injection, data exfiltration/leakage, jailbreak, data poisoning and adversarial defense. Based on Microsoft Learn "Fundamentals of AI security".

---

# Riscos de Segurança em IA / Aprendizado de Máquina — Intranet Modular

> Riscos de modelos de linguagem e aprendizado de máquina aplicados ao sistema: injeção de comandos (prompt injection), vazamento/exfiltração de dados, jailbreak, envenenamento de dados e defesa adversarial. Baseado no módulo "Fundamentos de IA de segurança" da Microsoft Learn.

## Contexto

A intranet é um sistema **multiusuário com dados sensíveis** (gestão de usuários,
auditoria, documentos). Qualquer integração futura com **modelos de linguagem**
(chat, sumarização, busca semântica, assistentes administrativos) ou **modelos
de ML** (classificação, OCR/visão, recomendação) amplia a superfície de ataque.
Este documento cataloga os riscos e as **defesas** a aplicar.

Referência principal: **Microsoft Learn — Fundamentos de segurança de IA**
(https://learn.microsoft.com/pt-br/training/modules/fundamentals-ai-security/).

## Riscos de modelos de linguagem (LLM)

| # | Risco | Descrição | Impacto no projeto | Defesa |
|:--|:---|:---|:---|:---|
| 1 | **Prompt Injection (injeção de comandos)** | O usuário (ou conteúdo externo) insere instruções no texto que "sequestram" o modelo, fazendo-o ignorar regras e executar ações não autorizadas | Modelo pode expor o system prompt, alterar dados ou acionar comandos | Tratar todo input como **dado**, não instrução; separar instruções de dados; permitlist de comandos; **confirmação humana** antes de ações |
| 2 | **Exfiltração / vazamento de dados** | Modelo devolve dados de outros usuários, do system prompt ou de dados de treinamento (memória) | Vazamento de dados pessoais (LGPD) | Menor privilégio; **não incluir dados sensíveis** no contexto se desnecessário; tokenização/mascaramento |
| 3 | **Jailbreak** | Prompts criativos (personas, "modo dev") contornam os filtros de conteúdo | Saída inadequada/ilegal | Filtros de entrada e saída em camadas; monitoramento; rate limiting |
| 4 | **Injeção indireta** | Conteúdo externo (documento, URL, e-mail) carregado no contexto carrega instrução maliciosa | Documentos do módulo de PDF/blog podem manipular o modelo | Marcar conteúdo externo como **dado não confiável** (delimitadores); não executar instruções vindas de documentos |
| 5 | **Alucinação** | Resposta factualmente errada apresentada como verdade | Decisões administrativas erradas | Citar fontes; restringir domínio; revisão humana |
| 6 | **Prompt poisoning / data poisoning** | Dados maliciosos no contexto/treinamento mudam o comportamento do modelo | Modelo enviesado/instrumentalizado | Validar fontes de dados; trust boundaries; re-treino controlado |

## Riscos de modelos de ML clássico (visão/OCR/classificação)

| Risco | Descrição | Defesa |
|:---|:---|:---|
| **Ataques adversariais (adversarial examples)** | Perturbações imperceptíveis em imagens/texto enganam o modelo (ex. OCR erra um valor em PDF) | Validação cruzada com regras de negócio; revisão humana em valores críticos |
| **Fuga de dados de treinamento** | Modelo memoriza e reproduz dados de treinamento sensíveis | Não treinar com dados pessoais reais; anonimização |
| **Espelhamento (model inversion)** | Inferir dados de treino a partir de saídas | Restringir API de predição; rate limiting |
| **Robustez** | Entradas fora da distribuição causam falhas silenciosas | Testes com dados adversarial; limites de confiança |

## Defesa Adversarial — regras obrigatórias de implementação

1. **Nunca executar comandos/operações** baseadas em saída de IA sem confirmação
   humana (toda ação destrutiva ou alteração de dados exige o usuário confirmar).
2. **Menor privilégio**: o modelo/IA tem acesso restrito, sem credenciais
   administrativas nem acesso direto a bancos de outros módulos.
3. **Escapar/sanitizar a entrada** antes de interpolar em prompt — o conteúdo do
   usuário é tratado como dado entre delimitadores, nunca como instrução.
4. **Filtro de conteúdo na saída** antes de renderizar (ex.: reutilizar o padrão
   `nh3` do projeto para HTML gerado por IA).
5. **Auditar e logar interações** com IA sem gravar dados pessoais nos logs
   (padrão loguru do projeto).
6. **Rate limiting** nas chamadas ao modelo para mitigar scraping/envenenamento.
7. **Não incluir dados sensíveis no contexto** se a tarefa não precisar deles.
8. **Configurabilidade** (regra do projeto): limites, filtros e tempos como chaves
   em `tb_config`, não fixados em código.

## Checklist de aceite para qualquer integração de IA/ML

- [ ] Entrada do usuário tratada como dado, não instrução (anti prompt injection).
- [ ] Ações sensíveis exigem confirmação humana.
- [ ] Acesso do modelo restrito por perfil/permissões (menor privilégio).
- [ ] Sem dados pessoais/detalhados nos logs de IA.
- [ ] Saída filtrada antes de renderização (XSS/saneamento).
- [ ] Rate limiting e monitoramento configurados.
- [ ] Retenção/logs de auditoria das interações configurável.

Veja [Ferramentas de Segurança](../seguranca/ferramentas_de_seguranca.md),
[Análise de Risco](../analise_de_risco/index.md) e o subagente
`.opencode/agent/qa_seguranca.md`.