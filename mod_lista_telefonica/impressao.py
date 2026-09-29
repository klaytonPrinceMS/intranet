"""EN: PDF printing of the phone directory — 3 columns, pymupdf, built-in fonts.
Route /lista-telefonica/pdf serves the current slice (unit or everything) as a
download; no temporary file on disk, the bytes are produced on the request.

PT-BR: Impressão em PDF da Lista Telefônica — 3 colunas, pymupdf, fontes
embutidas. A rota /lista-telefonica/pdf entrega o recorte atual (a unidade
selecionada ou tudo) como download; nada é gravado em disco, os bytes saem na
própria requisição.
"""

import datetime
import os
import re

# ============ CONSTANTES DE LAYOUT (A4) ============

PAGINA_LARGURA = 595.28          # A4 retrato, em pontos
PAGINA_ALTURA = 841.89
MARGEM = 34.0
NUM_COLUNAS = 3                  # 3 colunas por página (pedido do usuário)
GAPEAMENTO = 13.0
ALTURA_CABECALHO = 46.0
ALTURA_RODAPE = 26.0

FONTE = "helv"                   # Helvetica — fonte embutida do pymupdf
FONTE_NEGRITO = "hebo"           # Helvetica-Bold
TAM_GRUPO = 8.6                  # secretaria
TAM_SUBGRUPO = 8.0               # setor/subsetor
TAM_CONTATO = 7.9
TAM_CABECALHO = 13.0
TAM_RODAPE = 7.4

CINZA = (0.35, 0.35, 0.35)
PRETO = (0.0, 0.0, 0.0)
CINZA_CLARO = (0.78, 0.78, 0.78)

ROTA_PDF = "/lista-telefonica/pdf"
_ROTA_REGISTRADA = False


def _log():
    """EN: Module logger (fail-soft). PT-BR: logger do módulo (fail-soft)."""
    try:
        from mod_intranet import observabilidade
        return observabilidade.get_logger("lista_telefonica")
    except Exception:
        try:
            import logging
            return logging.getLogger("lista_telefonica")
        except Exception:
            return None


def _registrar_falha(mensagem, funcao):
    """EN: Log an unexpected failure in the project's cascading pattern.

    PT-BR: Registra uma falha inesperada no padrão em cascata do projeto
    (`_log()` -> `log` -> `observabilidade`) sem derrubar a tela.
    """
    try:
        try:
            _log().exception("%s falhou: %s", funcao, mensagem)
        except NameError:
            try:
                import logging
                logging.getLogger("lista_telefonica").exception(
                    "%s falhou: %s", funcao, mensagem)
            except NameError:
                pass
    except Exception:
        pass


def _largura_texto(texto, fonte=FONTE, tamanho=TAM_CONTATO):
    """EN: Text width in points. PT-BR: Largura do texto em pontos."""
    try:
        import pymupdf
        return float(pymupdf.get_text_length(texto or "", fontname=fonte,
                                            fontsize=tamanho))
    except Exception:
        # Aproximação da Helvetica: ~0.5 em por caractere.
        return len(texto or "") * tamanho * 0.5


def _cortar(texto, largura_max, fonte=FONTE, tamanho=TAM_CONTATO):
    """EN: Truncate with ellipsis to fit the column. PT-BR: Corta com reticências."""
    try:
        texto = texto or ""
        if _largura_texto(texto, fonte, tamanho) <= largura_max:
            return texto
        corte = texto
        while corte and _largura_texto(corte + "…", fonte, tamanho) > largura_max:
            corte = corte[:-1]
        return (corte.rstrip() + "…") if corte else ""
    except Exception:
        return texto or ""


def _linhas(arvore):
    """EN: Flattens the unit tree into printable blocks (group + contacts).

    PT-BR: Achata a árvore de unidades em blocos imprimíveis (grupo + contatos).
    A ordem vem do banco (secretaria → setor → subsetor → contato, tudo
    alfabético), então aqui não se reordena nada: só se navega.
    """
    blocos = []
    try:
        for raiz in arvore or []:
            blocos.extend(_bloco_unidade(raiz, 0, ""))
    except Exception:
        _registrar_falha("achatar arvore", "_linhas")
    return blocos


def _bloco_unidade(unidade, nivel, prefixo):
    """EN: One unit block (title + its contacts) plus its children.

    PT-BR: Bloco de uma unidade (título + contatos) e das unidades filhas.
    """
    blocos = []
    try:
        nome = unidade.get("nome") or ""
        tipo = unidade.get("tipo") or ""
        caminho = f"{prefixo} > {nome}" if prefixo else nome
        contatos = list(unidade.get("contatos") or [])
        filhos = list(unidade.get("filhos") or [])
        blocos.append({"tipo": tipo or "subsetor", "nivel": nivel,
                       "nome": nome, "caminho": caminho,
                       "contatos": contatos, "telefone": unidade.get("telefone") or ""})
        for filho in filhos:
            blocos.extend(_bloco_unidade(filho, nivel + 1, caminho))
    except Exception:
        _registrar_falha("montar bloco", "_bloco_unidade")
    return blocos


class _Coluna:
    """EN: Cursor of one column on one page. PT-BR: Cursor de uma coluna da página."""

    def __init__(self, x, y, y_limite):
        try:
            self.x = x
            self.y = y
            self.y_limite = y_limite
        except Exception as exc:
            _registrar_falha(str(exc), "_Coluna")


class _Impressor:
    """EN: Flow layout in N columns, header per page, footer after all pages.

    PT-BR: Layout em colunas (fluxo de cima para baixo, coluna a coluna), cabeçalho
    em cada página e rodapé só no fim (quando o total de páginas já é conhecido).
    """

    def __init__(self, titulo, rodape, colunas=NUM_COLUNAS):
        try:
            self.titulo = titulo or "Lista Telefônica"
            self.rodape = rodape or ""
            self.colunas = max(1, int(colunas))
            self.largura_util = PAGINA_LARGURA - 2 * MARGEM
            self.largura_coluna = ((self.largura_util - GAPEAMENTO * (self.colunas - 1))
                                   / self.colunas)
            self.y_limite = PAGINA_ALTURA - MARGEM - ALTURA_RODAPE
            self.doc = None
            self.pagina = None
            self.coluna = None
            self.total_blocos = 0
            self.total_contatos = 0
        except Exception as exc:
            _registrar_falha(str(exc), "_Impressor")

    # ---------- infra de página ----------

    def _abrir_pagina(self):
        """EN: Starts a new page on its first column. PT-BR: Abre página na 1ª coluna."""
        try:
            self.pagina = self.doc.new_page(width=PAGINA_LARGURA, height=PAGINA_ALTURA)
            self._cabecalho()
            self.coluna = _Coluna(MARGEM, MARGEM + ALTURA_CABECALHO, self.y_limite)
        except Exception as exc:
            _registrar_falha(str(exc), "_abrir_pagina")

    def _nova_coluna(self):
        """EN: Moves to the next column, or to a new page when the last is full.

        PT-BR: Vai para a próxima coluna, ou para uma nova página quando a última
        acabou. A nova página já nasce na primeira coluna (senão a própria
        recursão entre os dois métodos não termina).
        """
        try:
            if self.coluna is None:
                self._abrir_pagina()
                return
            x_proxima = self.coluna.x + self.largura_coluna + GAPEAMENTO
            if x_proxima + self.largura_coluna > PAGINA_LARGURA - MARGEM + 0.5:
                self._abrir_pagina()
                return
            self.coluna = _Coluna(x_proxima, MARGEM + ALTURA_CABECALHO, self.y_limite)
        except Exception as exc:
            _registrar_falha(str(exc), "_nova_coluna")

    def _garantir_altura(self, altura):
        """EN: Breaks the column when the next block does not fit.

        PT-BR: Quebra a coluna quando o próximo bloco não cabe.
        """
        try:
            if self.pagina is None:
                self._abrir_pagina()
                return
            if self.coluna.y + altura > self.coluna.y_limite:
                self._nova_coluna()
        except Exception as exc:
            _registrar_falha(str(exc), "_garantir_altura")

    # ---------- cabeçalho e rodapé ----------

    def _cabecalho(self):
        """EN: Title + date + rule, on every page. PT-BR: Título + data + fio."""
        try:
            hoje = datetime.datetime.now().strftime("%d/%m/%Y")
            self.pagina.insert_text(
                (MARGEM, MARGEM + 8), _cortar(self.titulo, self.largura_util * 0.72,
                                              FONTE_NEGRITO, TAM_CABECALHO),
                fontname=FONTE_NEGRITO, fontsize=TAM_CABECALHO, color=PRETO)
            largura_data = _largura_texto(hoje, FONTE, TAM_RODAPE + 1.4)
            self.pagina.insert_text(
                (PAGINA_LARGURA - MARGEM - largura_data, MARGEM + 8), hoje,
                fontname=FONTE, fontsize=TAM_RODAPE + 1.4, color=CINZA)
            y = MARGEM + ALTURA_CABECALHO - 8
            self.pagina.draw_line((MARGEM, y), (PAGINA_LARGURA - MARGEM, y),
                                  color=CINZA_CLARO, width=0.6)
        except Exception as exc:
            _registrar_falha(str(exc), "_cabecalho")

    def _rodapes(self):
        """EN: Footer on every page once the total is known.

        PT-BR: Rodapé em todas as páginas, depois que o total é conhecido.
        """
        try:
            total = self.doc.page_count
            for indice, pagina in enumerate(self.doc, start=1):
                y = PAGINA_ALTURA - MARGEM + 6
                pagina.draw_line((MARGEM, y - 9), (PAGINA_LARGURA - MARGEM, y - 9),
                                 color=CINZA_CLARO, width=0.6)
                if self.rodape:
                    pagina.insert_text(
                        (MARGEM, y), _cortar(self.rodape, self.largura_util - 90),
                        fontname=FONTE, fontsize=TAM_RODAPE, color=CINZA)
                paginacao = f"Página {indice} de {total}"
                largura_pag = _largura_texto(paginacao, FONTE, TAM_RODAPE)
                pagina.insert_text(
                    (PAGINA_LARGURA - MARGEM - largura_pag, y), paginacao,
                    fontname=FONTE, fontsize=TAM_RODAPE, color=CINZA)
        except Exception:
            _registrar_falha("rodapes", "_rodapes")

    # ---------- blocos ----------
    # Convenção única: `self.coluna.y` é a LINHA DE BASE do próximo texto a
    # desenhar. Avançar a base (e não o topo) é o que impede a sobreposição de
    # linhas — o erro clássico de misturar "topo" em um método e "base" no outro.

    def _escrever_grupo(self, bloco):
        """EN: Unit title (secretaria/setor/subsetor) with hierarchy indent.

        PT-BR: Título da unidade (secretaria/setor/subsetor) com recuo por nível.
        """
        try:
            nivel = int(bloco.get("nivel") or 0)
            recuo = min(nivel, 2) * 7.0
            if nivel == 0:
                fonte, tamanho, cor = FONTE_NEGRITO, TAM_GRUPO, PRETO
                texto = (bloco.get("nome") or "").upper()
                espaco = 5.0
                self.total_blocos += 1
            elif nivel == 1:
                fonte, tamanho, cor = FONTE_NEGRITO, TAM_SUBGRUPO, PRETO
                texto = bloco.get("nome") or ""
                espaco = 2.6
            else:
                fonte, tamanho, cor = FONTE, TAM_SUBGRUPO, CINZA
                texto = bloco.get("nome") or ""
                espaco = 0.8
            passo = max(tamanho, TAM_CONTATO) + 2.6
            self._garantir_altura(espaco + passo)
            self.coluna.y += espaco
            disponivel = self.largura_coluna - recuo
            self.pagina.insert_text(
                (self.coluna.x + recuo, self.coluna.y),
                _cortar(texto, disponivel, fonte, tamanho),
                fontname=fonte, fontsize=tamanho, color=cor)
            if nivel == 0:
                self.pagina.draw_line(
                    (self.coluna.x + recuo, self.coluna.y + 2.4),
                    (self.coluna.x + self.largura_coluna, self.coluna.y + 2.4),
                    color=CINZA_CLARO, width=0.5)
            self.coluna.y += passo
        except Exception:
            _registrar_falha("escrever grupo", "_escrever_grupo")

    def _escrever_contato(self, contato):
        """EN: One contact line — name left, phone right-aligned.

        PT-BR: Uma linha de contato — nome à esquerda, telefone alinhado à direita.
        """
        try:
            tel = _telefone_exibicao(_campo_contato(contato, "telefone", 3))
            self._garantir_altura(TAM_CONTATO + 2.6)
            y = self.coluna.y
            if tel:
                largura_tel = _largura_texto(tel, FONTE, TAM_CONTATO)
                self.pagina.insert_text(
                    (self.coluna.x + self.largura_coluna - largura_tel, y), tel,
                    fontname=FONTE, fontsize=TAM_CONTATO, color=CINZA)
                nome_limite = self.largura_coluna - largura_tel - 6
            else:
                nome_limite = self.largura_coluna
            nome = _campo_contato(contato, "nome", 2)
            self.pagina.insert_text(
                (self.coluna.x, y), _cortar(nome or "", nome_limite),
                fontname=FONTE, fontsize=TAM_CONTATO, color=PRETO)
            self.coluna.y += TAM_CONTATO + 2.6
            self.total_contatos += 1
        except Exception:
            _registrar_falha("escrever contato", "_escrever_contato")

    def _escrever_telefone_unidade(self, telefone):
        """EN: Unit phone under the group title. PT-BR: Telefone da unidade sob o título."""
        try:
            if not telefone:
                return
            self._garantir_altura(TAM_SUBGRUPO + 2.6)
            self.pagina.insert_text(
                (self.coluna.x, self.coluna.y),
                _cortar(f"Tel. {telefone}", self.largura_coluna, FONTE, TAM_SUBGRUPO),
                fontname=FONTE, fontsize=TAM_SUBGRUPO, color=CINZA)
            self.coluna.y += TAM_SUBGRUPO + 2.6
        except Exception:
            _registrar_falha("telefone unidade", "_escrever_telefone_unidade")

    def montar(self, arvore):
        """EN: Fills the document. PT-BR: Preenche o documento."""
        import pymupdf
        self.doc = pymupdf.open()
        try:
            self.doc.set_metadata({
                "title": self.titulo, "author": "Intranet",
                "subject": "Lista Telefônica", "creator": "mod_lista_telefonica",
            })
        except Exception:
            _registrar_falha("metadata", "montar")
        blocos = _linhas(arvore)
        if not blocos:
            blocos = [{"tipo": "secretaria", "nivel": 0, "nome": self.titulo,
                       "caminho": self.titulo, "contatos": [], "telefone": ""}]
        for bloco in blocos:
            self._escrever_grupo(bloco)
            self._escrever_telefone_unidade(bloco.get("telefone"))
            for contato in bloco.get("contatos") or []:
                self._escrever_contato(contato)
        self._rodapes()
        return self.doc


def _telefone_exibicao(valor):
    """EN: Formatted phone for print (falls back to the raw text).

    PT-BR: Telefone formatado para o papel (cai no texto cru se o núcleo falhar).
    """
    try:
        from mod_intranet import telefone as _tel
        return _tel.formatar_para_exibicao(valor) or (valor or "")
    except Exception:
        return (valor or "").strip()


def gerar_pdf_lista(destino, nos, titulo, rodape=""):
    """EN: Writes the phone directory PDF (3 columns) to `destino`.

    PT-BR: Grava o PDF da lista telefônica (3 colunas) em `destino`.

    `nos` is the tree of `listar_arvore_contatos` (already alphabetical);
    `titulo` goes in the header and `rodape` in the footer. Uses only the
    pymupdf built-in fonts (helv/hebo) — nothing is downloaded. Returns
    `(True, path)` or `(False, short message)`.
    """
    doc = None
    try:
        impressor = _Impressor(titulo, rodape)
        doc = impressor.montar(nos or [])
    except ImportError:
        return False, "Biblioteca de PDF (pymupdf) indisponível"
    except Exception as exc:
        _registrar_falha(str(exc), "gerar_pdf_lista")
        return False, "Não foi possível gerar o PDF. Tente novamente."
    try:
        pasta = os.path.dirname(os.path.abspath(destino))
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        doc.save(destino, garbage=3, deflate=True)
        return True, destino
    except Exception as exc:
        _registrar_falha(str(exc), "gerar_pdf_lista")
        return False, "Não foi possível gravar o PDF. Tente novamente."
    finally:
        try:
            if doc is not None:
                doc.close()
        except Exception:
            pass


def pdf_bytes(nos, titulo, rodape=""):
    """EN: Same layout, returned as bytes (nothing touches the disk).

    PT-BR: Mesmo layout, devolvido em bytes (nada toca o disco). É o caminho do
    download pela rota, que monta o PDF na requisição em vez de deixar
    arquivo temporário no módulo.
    Returns `(bytes, "")` or `(None, mensagem)`.
    """
    doc = None
    try:
        doc = _Impressor(titulo, rodape).montar(nos or [])
        return doc.tobytes(garbage=3, deflate=True), ""
    except ImportError:
        return None, "Biblioteca de PDF (pymupdf) indisponível"
    except Exception as exc:
        _registrar_falha(str(exc), "pdf_bytes")
        return None, "Não foi possível gerar o PDF. Tente novamente."
    finally:
        try:
            if doc is not None:
                doc.close()
        except Exception:
            pass


def titulo_para_impressao(nome_unidade=""):
    """EN: Header title — 'Lista Telefônica — <unit>'. PT-BR: Título do cabeçalho."""
    try:
        base = "Lista Telefônica"
        return f"{base} — {nome_unidade}" if nome_unidade else base
    except Exception:
        return "Lista Telefônica"


def rodape_para_impressao(quantidade, unidade_nome=""):
    """EN: Footer text with the contact count and the emission date.

    PT-BR: Texto do rodapé com a quantidade de contatos e a data de emissão.
    """
    try:
        hoje = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")
        partes = [f"{quantidade} contato(s)"]
        if unidade_nome:
            partes.append(unidade_nome)
        partes.append(f"emitido em {hoje}")
        return " · ".join(partes)
    except Exception:
        return ""


def _bytes_do_recorte(recorte=None, termo="", nome="", telefone="", unidade=""):
    """EN: Builds the PDF bytes of the current slice (unit or everything).

    PT-BR: Monta os bytes do PDF do recorte atual (unidade ou tudo), aplicando
    o filtro UNICO de busca (`termo`) ou os campos separados, como antes.
    Returns `(bytes, nome_arquivo)` or `(None, "")`.
    """
    try:
        from mod_lista_telefonica import bd_manipulador as lista

        arvore = lista.listar_arvore_contatos(raiz_id=recorte)
        arvore = filtrar_arvore(arvore, termo=termo, nome=nome,
                                telefone=telefone, unidade=unidade)
        nome_unidade = ""
        if recorte:
            uni = lista.obter_unidade(recorte)
            nome_unidade = uni[1] if uni else ""
        total = contar(arvore)
        if not total:
            return None, "Nenhum contato no recorte — nada para imprimir."
        dados, erro = pdf_bytes(arvore, titulo_para_impressao(nome_unidade),
                                rodape_para_impressao(total, nome_unidade))
        if not dados:
            return None, erro
        marca = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        return dados, f"lista-telefonica-{marca}.pdf"
    except Exception as exc:
        _registrar_falha(str(exc), "_bytes_do_recorte")
        return None, ""


def contar(arvore):
    """EN: Counts contacts in a tree (screen footer and print footer).

    PT-BR: Conta contatos de uma árvore (rodapé da tela e da impressão).
    """
    total = 0
    try:
        for raiz in arvore or []:
            total += len(raiz.get("contatos") or [])
            total += contar(raiz.get("filhos") or [])
    except Exception:
        _registrar_falha("contar", "contar")
    return total


def filtrar_arvore(arvore, termo="", nome="", telefone="", unidade=""):
    """EN: Single-term search over name, phone and unit path, order preserved.

    PT-BR: Busca por UM termo, no nome, no telefone ou no caminho da unidade,
    preservando a ordem que veio do banco.

    O termo é o filtro da tela: a busca é UM campo só, e o mesmo texto casa
    com nome ("Ana"), telefone ("3591") ou unidade ("Saúde"). A comparação é
    OU entre os três, não E — quem digita "Saúde" quer os servidores da Saúde,
    e quem digita "3591" quer os telefones, não a interseção dos dois.

    `nome`/`telefone`/`unidade` continuam aceitos para quem chama com campos
    separados (impressão de um recorte, testes): aí o comportamento é E, como
    era. `termo` tem precedência.

    Reaproveita `bd_manipulador._norm` (sem acentos e sem pontuação — é ela que
    faz "ti" achar "T.I.") e devolve cópias rasas das unidades: o banco não é
    alterado.
    """
    try:
        from mod_lista_telefonica import bd_manipulador as lista
        norm = lista._norm
        alvo_termo = norm(termo) if (termo or "").strip() else ""
        alvo_nome = norm(nome) if (nome or "").strip() else ""
        alvo_tel = _digitos(telefone)
        alvo_unidade = norm(unidade) if (unidade or "").strip() else ""
        if alvo_termo:
            return _filtrar_termo(arvore or [], "", alvo_termo, norm)
        if not (alvo_nome or alvo_tel or alvo_unidade):
            return arvore or []
        return _filtrar(arvore or [], "", alvo_nome, alvo_tel, alvo_unidade, norm)
    except Exception:
        _registrar_falha("filtrar arvore", "filtrar_arvore")
        return arvore or []


def _campo_contato(c, chave, indice_padrao):
    """Lê um campo do contato por NOME, com a posição antiga como reserva.

    Contato é dict (28/09/2026); o código antigo lia por índice e levantava
    KeyError em toda linha de contato do PDF — a impressão saía em branco sem
    erro visível. Aceitar as duas formas evita isso e ainda tolera uma árvore
    vinda de outro ponto do módulo.
    """
    if isinstance(c, dict):
        return c.get(chave) or ""
    try:
        return c[indice_padrao] or ""
    except Exception:
        return ""


def _texto_do_contato(c):
    """Todo o texto pesquisável de um contato, em uma string só.

    O contato é DICT (mudou de tupla para dict em 28/09/2026, quando a lista
    passou a trazer cargo, vínculo e situação e a gravar servidor sem
    telefone). Indexar por posição aqui levantava `KeyError: 2`, o `except`
    devolvia a árvore INTEIRA sem filtrar, e a busca "funcionava" — devolvendo
    sempre a lista toda. Por isso a busca precisa ler por NOME de chave, e não
    por índice.

    Aceita tupla também, para uma árvore antiga vinda de outro ponto do módulo
    não virar `KeyError` agora.
    """
    if isinstance(c, dict):
        partes = [c.get("nome"), c.get("nome_completo"), c.get("telefone"),
                  c.get("user_nome"), c.get("cargo"), c.get("lotacao"),
                  c.get("vinculo"), c.get("situacao")]
    else:
        try:
            partes = [c[2], c[3], c[4]]
            if len(c) > 6:
                partes += [c[6], c[7], c[8], c[9], c[10]]
        except Exception:
            partes = []
    return " ".join(str(p or "") for p in partes)


def _filtrar_termo(arvore, prefixo, alvo, norm):
    """EN: Keeps a unit if the term hits its path or any of its contacts.

    PT-BR: Mantém a unidade se o termo casar com o caminho dela ou com algum
    contato. A unidade continua na árvore mesmo sem contato casado, para o
    diretório não "pular" a secretaria e deixar o usuário sem contexto de onde
    o contato veio.

    O termo casa com nome, nome completo, telefone, matrícula, CARGO, LOTAÇÃO,
    VÍNCULO e SITUAÇÃO (28/09/2026) — quem procura "Agente Administrativo" ou
    "Efetivo" precisa achar a pessoa, e não só quem tem número.

    A UNIDADE sobrevive ao filtro (é o que dá contexto de onde veio o contato),
    mas os CONTATOS que não casam são removidos dela. Sem isso, buscar um nome
    devolvia a secretaria INTEIRA: a unidade casava porque tinha um contato
    certo, e os outros trinta ficavam junto — "Guerzoni" trazia 304 pessoas.
    """
    saida = []
    try:
        for no in arvore or []:
            nome = no.get("nome") or ""
            caminho = f"{prefixo} > {nome}" if prefixo else nome
            filhos = _filtrar_termo(no.get("filhos") or [], caminho, alvo, norm)
            todos = no.get("contatos") or []
            if alvo:
                # só os contatos que casam; a unidade continua de pé se algum
                # casou OU se algum filho casou
                contatos = [c for c in todos if alvo in norm(_texto_do_contato(c))]
            else:
                contatos = list(todos)
            unidade_casou = alvo in norm(caminho)
            if unidade_casou or contatos or filhos:
                copia = dict(no)
                # se a própria unidade casou pelo nome, ela mostra quem tem:
                # quem busca "Educacao" quer os servidores da Educação, não a
                # lista dos que não são.
                copia["contatos"] = list(todos) if unidade_casou else contatos
                copia["filhos"] = filhos
                saida.append(copia)
        return saida
    except Exception:
        _registrar_falha("filtrar por termo", "filtro de termo")
        return arvore or []


def _digitos(texto):
    """EN: Digits only (phone search ignores punctuation). PT-BR: Só dígitos."""
    try:
        return re.sub(r"\D", "", texto or "")
    except Exception:
        return ""


def _filtrar(arvore, prefixo, alvo_nome, alvo_tel, alvo_unidade, norm):
    """EN: Recursive filter of the tree. PT-BR: Filtro recursivo da árvore."""
    saida = []
    try:
        for no in arvore or []:
            nome = no.get("nome") or ""
            caminho = f"{prefixo} > {nome}" if prefixo else nome
            if alvo_unidade and alvo_unidade not in norm(caminho):
                # A unidade não casa: só os filhos podem casar (subsetor da vez).
                filhos = _filtrar(no.get("filhos") or [], caminho, alvo_nome,
                                  alvo_tel, alvo_unidade, norm)
                if filhos:
                    copia = dict(no)
                    copia["filhos"] = filhos
                    saida.append(copia)
                continue
            contatos = []
            for contato in no.get("contatos") or []:
                nome_contato = _campo_contato(contato, "nome", 2)
                telefone_contato = _campo_contato(contato, "telefone", 3)
                if alvo_nome and alvo_nome not in norm(nome_contato):
                    continue
                if alvo_tel and alvo_tel not in _digitos(telefone_contato):
                    continue
                contatos.append(contato)
            filhos = _filtrar(no.get("filhos") or [], caminho, alvo_nome,
                              alvo_tel, alvo_unidade, norm)
            if contatos or filhos:
                copia = dict(no)
                copia["contatos"] = contatos
                copia["filhos"] = filhos
                saida.append(copia)
    except Exception:
        _registrar_falha("filtrar no", "_filtrar")
    return saida


def registrar_rota_pdf():
    """EN: Registers GET /lista-telefonica/pdf (download, same session).

    PT-BR: Registra `GET /lista-telefonica/pdf` (download, mesma sessão).
    Idempotente: a segunda chamada não duplica a rota. A guarda de acesso é a
    mesma da tela (sessão viva + `validar_acesso_modulo`) — o recorte vem da
    query string, e nenhum dado de outro usuário é exposto (a lista é do
    módulo inteiro, igual à tela).
    """
    global _ROTA_REGISTRADA
    if _ROTA_REGISTRADA:
        return True
    try:
        from fastapi.responses import RedirectResponse, Response
        from nicegui import app

        @app.get(ROTA_PDF)
        def baixar_pdf_lista(recorte: int = None, termo: str = "", nome: str = "",
                            telefone: str = "", unidade: str = ""):
            """EN: Streams the PDF of the requested slice. PT-BR: Envia o PDF do recorte."""
            try:
                from mod_intranet import autenticacao
                from mod_intranet.telas import usuario_logado
                user = usuario_logado()
                if not user:
                    return RedirectResponse("/login")
                nome_user = user.get("nome", "")
                linha = autenticacao.usuario_existe(nome_user)
                if not linha or not linha[2]:
                    return RedirectResponse("/login")
                perfil = autenticacao.perfil_global_de(nome_user)
                if perfil != "administrador_geral" and \
                        not autenticacao.validar_acesso_modulo(nome_user, "lista_telefonica"):
                    return RedirectResponse("/lista-telefonica")
                dados, arquivo = _bytes_do_recorte(recorte, termo, nome,
                                                    telefone, unidade)
                if not dados:
                    return RedirectResponse("/lista-telefonica")
                # `Response` (e não `FileResponse`) porque o PDF é montado na
                # requisição: o arquivo nasce em memória e não toca o disco.
                return Response(
                    content=dados, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})
            except Exception as exc:
                _registrar_falha(str(exc), "baixar_pdf_lista")
                return RedirectResponse("/lista-telefonica")

        _ROTA_REGISTRADA = True
        return True
    except Exception as exc:
        _registrar_falha(str(exc), "registrar_rota_pdf")
        return False
