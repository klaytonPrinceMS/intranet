"""Seed of "how-to" blog posts for the common user (Editor PDF, Print Request, Empenhos).

Seed de postagens de "como usar" para o Blog (módulos Editor PDF, Solicitação de
Impressão e Empenhos). Insere postagens voltadas ao usuário comum (fluxo de uso,
não administrativo), cada uma iniciando com um fluxograma Mermaid (```mermaid).
Reutiliza a função `criar_postagem` do módulo blog (sanitização nh3, permissão e
auditoria). Falhas por postagem são registradas no loguru e não interrompem o
restante do seed (fail-soft).

Executar com o venv: `source .venv/bin/activate && python test/criar_postagens_blog.py`
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mod_blog.bd_manipulador import criar_postagem

AUTOR = "master"


def _log():
    """Logger do seed (loguru) — arquivo dedicado logs/blog_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("blog")

POSTAGENS = [
    {
        "titulo": "Editor de PDF — Como usar",
        "conteudo": """**Editor de PDF** — um espaço pessoal e rápido para trabalhar com seus PDFs: enviar, reduzir, juntar, cortar, dividir, verificar e baixar. Cada usuário só enxerga os próprios arquivos.

```mermaid
flowchart TD
    A[Entrar em Editor de PDF] --> B[Enviar um ou mais PDFs]
    B --> C[Selecionar os arquivos na lista]
    C --> D[Escolher a operação]
    D -->|Juntar| E[Juntar selecionados]
    D -->|Reduzir| F[Reduzir tamanho]
    D -->|Cortar ou dividir| G[Cortar / Dividir páginas]
    E --> H[Baixar o resultado]
    F --> H
    G --> H
    H --> I[Baixar ou excluir ao terminar]
```

# Como usar
- **Envie** seus PDFs pelo campo *Envie um ou mais PDFs* (arraste ou clique; só aceita .pdf).
- **Marque** na tabela os arquivos que quer usar. A ordem de marcação é a ordem do **Juntar**.
- Escolha a operação: **Juntar**, **Reduzir**, **Cortar** ou **Dividir**.
- **Baixe** o resultado (ZIP ou arquivos individuais).
- **Exclua** o que não precisa para liberar espaço.

# Dicas
- Os arquivos **expirem automaticamente** em alguns minutos — conclua o trabalho com calma, mas não deixe para depois.
- Para reduzir, use o modo **Leve** no dia a dia; o **Agressivo** transforma texto em imagem (perde a busca no texto).
- Você tem uma **cota de espaço** por usuário — exclua PDFs antigos para liberar.

# Limites
- Cada usuário **só vê os próprios arquivos**.
- O upload em lote tem limite de arquivos e de tamanho por vez.""",
    },
    {
        "titulo": "Solicitação de Impressão — Como usar",
        "conteudo": """**Solicitação de Impressão** — central de pedidos de impressão. Anexe seus PDFs, escolha as opções e envie a solicitação. O pedido pode precisar de **autorização** e é impresso pelo setor responsável.

```mermaid
flowchart TD
    A[Entrar em Solicitação de Impressão] --> B[Aba Nova Solicitação]
    B --> C[Anexar PDFs]
    C --> D[Preencher opções: cópias, papel, cor, frente e verso]
    D --> E[Escolher secretaria / setor]
    E --> F[Enviar solicitação]
    F --> G{Acompanhar status}
    G -->|Aguardando autorização| H[Responsável autoriza]
    G -->|Autorizado| I[Setor imprime]
    G -->|Excedente de cota| J[Depende de autorização]
    G -->|Recusado ou cancelado| K[Revisar e enviar de novo]
```

# Como usar
- Na aba **Nova Solicitação**, **anexe os PDFs** (até 10 por solicitação).
- Preencha: **quantidade de cópias**, **tamanho do papel**, **cor** e, se aplicável, **frente e verso**.
- Se desmarcar *papel sulfite*, você deve **levar o papel**.
- Escolha a **secretaria** (e o setor, se houver) e clique **Enviar solicitação**.
- Acompanhe em **Minhas Solicitações** o andamento de cada pedido.

# Status possíveis
- **Autorizado** — pronto para impressão.
- **Aguardando autorização** — o responsável vai avaliar.
- **Excedente de cota** — ultrapassou a cota do mês; precisa de autorização.
- **Recusado / Cancelado / Impresso** — fim do fluxo.

# Dicas
- Enquanto o pedido estiver pendente/aguardando, você pode **cancelar** em *Minhas Solicitações*.
- Baixe o **PDF com marca d'água** se precisar conferir.
- Cada arquivo anexado gera **uma solicitação separada** com as mesmas opções.""",
    },
    {
        "titulo": "Empenhos — Como usar",
        "conteudo": """**Empenhos** — o módulo monitora as pastas com PDFs de empenhos, **extrai automaticamente** o número e organiza/renomeia os documentos. Você pode navegar, processar, pesquisar e solicitar o envio de um documento.

```mermaid
flowchart TD
    A[Entrar em Empenhos] --> B[Aba Navegar: abrir pastas]
    B --> C{PDF pendente?}
    C -->|Sim| D[Processar / revisar renomeação]
    C -->|Não| E[Ver arquivos processados]
    D --> F[Baixar ou solicitar envio]
    E --> F
    F --> G[Pesquisar na aba Pesquisar]
```

# Como usar
- Na aba **Navegar**, abra as pastas monitoradas e veja os PDFs com status **processado** (verde) ou **pendente** (laranja).
- **Processe** os pendentes (na aba **Fila Renomeação** ou pela ação na pasta) — o módulo renomeia e organiza sozinho.
- Use o botão **Baixar** para obter o documento já processado.
- **Solicite o envio** por e-mail quando precisar que o documento seja enviado a alguém.
- Na aba **Pesquisar**, busque por conteúdo nos empenhos indexados.

# Dicas
- A renomeação usa o **número do empenho** lido do próprio PDF (texto ou OCR).
- Documentos **pendentes** podem ser solicitados sempre; **processados** dependem de liberação do administrador.
- O histórico das solicitações fica na aba **Solicitação**.""",
    },
]


def main():
    """Runs the seed, creating each how-to post and reporting the result.

    Executa o seed criando cada postagem de "como usar" via `criar_postagem`
    (autor `master`). Cada postagem é tratada isoladamente: falha em uma não
    interrompe as demais (fail-soft) e é registrada no loguru. Ao final imprime
    o total criado e retorna o número de postagens inseridas com sucesso."""
    criadas = 0
    try:
        for p in POSTAGENS:
            try:
                pid = criar_postagem(p["titulo"], p["conteudo"], AUTOR)
                if pid:
                    criadas += 1
                    _log().info(f"seed: postagem criada #{pid} '{p['titulo']}' por {AUTOR}")
                    print(f"OK  #{pid}  {p['titulo']}  (autor: {AUTOR})")
                else:
                    _log().warning(f"seed: falha ao criar '{p['titulo']}' (sem permissão ou erro)")
                    print(f"FALHA  {p['titulo']}")
            except Exception as e:
                _log().exception(f"seed: erro ao criar '{p['titulo']}': {e}")
                print(f"FALHA  {p['titulo']}  ({e})")
        print(f"\nTotal criadas: {criadas}/{len(POSTAGENS)}")
        return criadas
    except Exception as e:
        _log().exception(f"seed: falha geral ao executar: {e}")
        return criadas


if __name__ == "__main__":
    main()