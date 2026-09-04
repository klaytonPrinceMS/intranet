"""
Renomeador de Empenhos - Prefeitura de Monte Santo de Minas
--------------------------------------------------------------
O QUE ESSE PROGRAMA FAZ:
1. Modo manual: você escolhe um PDF avulso pra processar.
2. Modo automático: você escolhe uma pasta pra "vigiar". Todo PDF novo que
   aparecer nela com nome DOC_XXXX.pdf (padrão da impressora, sem nada
   depois) é detectado sozinho e entra numa FILA de processamento.
3. Em qualquer um dos dois modos, ele lê o texto da primeira página do PDF,
   tenta identificar os campos configurados, e mostra uma tela de
   confirmação pra você conferir/corrigir antes de salvar (isso não é
   automático "sem revisão" de propósito, pra evitar erro).
4. Ao confirmar, ele renomeia o arquivo (mantendo o prefixo DOC_XXXX)
   para o padrão configurado em montar_novo_nome().

SOBRE O MODO AUTOMÁTICO (IMPORTANTE):
Os arquivos detectados na pasta são processados UM DE CADA VEZ, numa fila
(queue.Queue), nunca ao mesmo tempo. Isso evita o bug clássico de um
arquivo novo "atropelar" os dados do arquivo anterior antes de ele ser
salvo - se vários PDFs chegarem juntos, eles esperam na fila e você
confirma um por um, na ordem de chegada.

IMPORTANTE - PARTE QUE PRECISA SER AJUSTADA COM O DOCUMENTO REAL:
Os "padrões de busca" (regex) na seção CONFIGURAÇÃO DE EXTRAÇÃO abaixo
foram ajustados com base num documento de teste (Portal da Transparência).
Quando você tiver o PDF real de um empenho do seu sistema, provavelmente
vamos precisar ajustar esses padrões de novo.
"""

import os
import re
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import pdfplumber
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# =========================================================================
# CONFIGURAÇÃO DE EXTRAÇÃO
# Ajuste os padrões abaixo quando tivermos o texto real do PDF.
# Cada campo tem uma LISTA de padrões. Se o mesmo campo aparecer em mais
# de um lugar do documento com padrões diferentes, o programa tenta todos
# e avisa se os valores encontrados não baterem entre si.
# =========================================================================

PADROES = {
    "ficha": [
        r"da\s*Ficha[\s\S]*?(\d{6,7})/\d{4}",
    ],
    "empenho": [
        r"do\s*Empenho[\s\S]*?(\d{6,7})/\d{4}",
        r"EMPENHO\s*PARCELA\s*[:,]\s*(\d+)\s*-\s*\d+",
    ],
    "parcela": [
        r"EMPENHO\s*PARCELA\s*[:,]\s*\d+\s*-\s*(\d+)",
    ],
    "ano": [
        r"Exerc[íi]cio\s*de\s*(\d{4})",
        r"EMPENHO\s*PARCELA\s*[:,]\s*\d+\s*-\s*\d+\s*/\s*(\d{4})",
        r"da\s*Ficha[\s\S]*?\d{6,7}/(\d{4})",
        r"do\s*Empenho[\s\S]*?\d{6,7}/(\d{4})",
    ],
}

# Campos cujo valor deve ter os zeros à esquerda removidos
# (ex: "0000237" -> "237"), porque é assim que aparece no nome do arquivo.
CAMPOS_SEM_ZERO_ESQUERDA = {"ficha", "empenho"}

# Prefixo que a impressora gera (ex: DOC_0072) - usado para manter o
# início do nome do arquivo igual ao original.
PADRAO_PREFIXO = r"^(DOC_\d+)"

# Nome de arquivo "cru" que a impressora gera - usado no modo automático
# pra saber quais arquivos ainda NÃO foram processados (ainda não têm nada
# além de DOC_XXXX no nome).
PADRAO_ARQUIVO_NAO_PROCESSADO = re.compile(r"^DOC_\d+\.pdf$", re.IGNORECASE)


def extrair_texto_primeira_pagina(caminho_pdf):
    with pdfplumber.open(caminho_pdf) as pdf:
        primeira_pagina = pdf.pages[0]
        return primeira_pagina.extract_text() or ""


def buscar_campo(texto, lista_padroes, remover_zero_esquerda=False):
    """
    Tenta todos os padrões de um campo no texto.
    Retorna (valor_encontrado, houve_divergencia).
    """
    valores_encontrados = []
    for padrao in lista_padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            valores_encontrados.append(m.group(1))

    if not valores_encontrados:
        return None, False

    if remover_zero_esquerda:
        valores_normalizados = [str(int(v)) for v in valores_encontrados]
    else:
        valores_normalizados = valores_encontrados

    houve_divergencia = len(set(valores_normalizados)) > 1
    return valores_normalizados[0], houve_divergencia


def extrair_dados(caminho_pdf):
    texto = extrair_texto_primeira_pagina(caminho_pdf)

    resultado = {}
    divergencias = []

    for campo, padroes in PADROES.items():
        remover_zero = campo in CAMPOS_SEM_ZERO_ESQUERDA
        valor, divergiu = buscar_campo(texto, padroes, remover_zero_esquerda=remover_zero)
        resultado[campo] = valor or ""
        if divergiu:
            divergencias.append(campo)

    return resultado, divergencias, texto


def obter_prefixo(nome_arquivo):
    m = re.match(PADRAO_PREFIXO, nome_arquivo)
    if m:
        return m.group(1)
    # Se não encontrar o padrão DOC_XXXX, usa o nome original sem extensão
    return os.path.splitext(nome_arquivo)[0]


def sanitizar_para_nome_arquivo(valor):
    """Troca caracteres que não podem aparecer em nome de arquivo no Windows."""
    return valor.replace("/", "-").replace("\\", "-")


def montar_novo_nome(prefixo, ficha, empenho, parcela, ano):
    return f"{prefixo}_{ficha}_{empenho}_({parcela})_{ano}.pdf"


def arquivo_esta_estavel(caminho, checagens=3, intervalo=0.5):
    """
    Espera o tamanho do arquivo parar de mudar antes de processar.
    Evita ler um PDF que o scanner ainda está gravando.
    """
    tamanho_anterior = -1
    estavel_desde = 0
    while estavel_desde < checagens:
        try:
            tamanho_atual = os.path.getsize(caminho)
        except OSError:
            return False
        if tamanho_atual == tamanho_anterior and tamanho_atual > 0:
            estavel_desde += 1
        else:
            estavel_desde = 0
        tamanho_anterior = tamanho_atual
        time.sleep(intervalo)
    return True


# =========================================================================
# MONITORAMENTO DE PASTA (MODO AUTOMÁTICO)
# =========================================================================

class VigiaDePasta(FileSystemEventHandler):
    """
    Fica de olho na pasta escolhida. Quando aparece um arquivo novo que
    bate com o padrão DOC_XXXX.pdf (ainda não processado), ele espera o
    arquivo terminar de ser escrito e coloca o caminho na fila.
    Cada arquivo é tratado de forma independente - nada de variável
    global compartilhada entre eventos.
    """

    def __init__(self, fila_saida):
        super().__init__()
        self.fila_saida = fila_saida

    def on_created(self, event):
        if event.is_directory:
            return
        nome_arquivo = os.path.basename(event.src_path)
        if not PADRAO_ARQUIVO_NAO_PROCESSADO.match(nome_arquivo):
            return

        # Roda a espera de estabilidade numa thread separada, pra não
        # travar o watchdog, e só bota na fila quando o arquivo estiver
        # pronto de verdade.
        def esperar_e_enfileirar(caminho):
            if arquivo_esta_estavel(caminho):
                self.fila_saida.put(caminho)

        threading.Thread(
            target=esperar_e_enfileirar, args=(event.src_path,), daemon=True
        ).start()


# =========================================================================
# INTERFACE GRÁFICA
# =========================================================================

class App:
    INTERVALO_VERIFICACAO_FILA_MS = 800

    def __init__(self, root):
        self.root = root
        self.root.title("Renomeador de Empenhos")
        self.root.geometry("500x460")
        self.caminho_pdf = None

        self.campos = {}  # nome_campo -> tk.StringVar

        self.fila_arquivos = queue.Queue()
        self.observer = None
        self.pasta_monitorada = None
        self.processando_da_fila = False
        self.modo_auto = False
        self.pendentes = []  # lista de (caminho, motivo) que precisam revisão manual

        self._montar_tela_inicial()

    def _limpar_tela(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ---------------------------------------------------------------
    # TELA INICIAL
    # ---------------------------------------------------------------
    def _montar_tela_inicial(self):
        self._limpar_tela()

        tk.Label(
            self.root,
            text="Renomeador de Empenhos",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(25, 5))

        tk.Label(
            self.root,
            text="Escolha como processar os PDFs escaneados:",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 20))

        tk.Button(
            self.root,
            text="Selecionar um PDF avulso",
            font=("Segoe UI", 11),
            width=30,
            command=self.selecionar_pdf,
        ).pack(pady=8)

        tk.Button(
            self.root,
            text="Monitorar uma pasta (com confirmação)",
            font=("Segoe UI", 11),
            width=34,
            command=self.selecionar_pasta_para_monitorar,
        ).pack(pady=8)

        tk.Button(
            self.root,
            text="Monitorar uma pasta (100% automático)",
            font=("Segoe UI", 11),
            width=34,
            command=self.selecionar_pasta_para_monitorar_auto,
        ).pack(pady=8)

    # ---------------------------------------------------------------
    # MODO MANUAL
    # ---------------------------------------------------------------
    def selecionar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o PDF do empenho",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not caminho:
            return
        self._processar_arquivo(caminho, voltar_para="inicial")

    # ---------------------------------------------------------------
    # MODO AUTOMÁTICO (MONITORAR PASTA)
    # ---------------------------------------------------------------
    def selecionar_pasta_para_monitorar(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar")
        if not pasta:
            return

        self.modo_auto = False
        self.pasta_monitorada = pasta
        self._iniciar_monitoramento(pasta)
        self._montar_tela_monitorando()

    def _iniciar_monitoramento(self, pasta):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()

        handler = VigiaDePasta(self.fila_arquivos)
        self.observer = Observer()
        self.observer.schedule(handler, pasta, recursive=False)
        self.observer.start()

        self.root.after(self.INTERVALO_VERIFICACAO_FILA_MS, self._verificar_fila)

    def _parar_monitoramento(self):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.pasta_monitorada = None
        self.modo_auto = False
        self.pendentes = []
        self._montar_tela_inicial()

    def _montar_tela_monitorando(self):
        self._limpar_tela()
        self.root.geometry("500x460")

        tk.Label(
            self.root,
            text="Monitorando pasta (com confirmação):",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(25, 2))

        tk.Label(
            self.root,
            text=self.pasta_monitorada,
            font=("Segoe UI", 9),
            wraplength=460,
            fg="darkblue",
        ).pack(pady=(0, 15))

        self.status_var = tk.StringVar(
            value="Aguardando novos arquivos DOC_XXXX.pdf..."
        )
        tk.Label(
            self.root, textvariable=self.status_var, font=("Segoe UI", 10)
        ).pack(pady=10)

        tk.Label(
            self.root,
            text=(
                "Assim que um novo PDF aparecer nessa pasta com o nome "
                "DOC_XXXX.pdf, a tela de confirmação abre sozinha."
            ),
            font=("Segoe UI", 9),
            fg="gray30",
            wraplength=460,
            justify="left",
        ).pack(pady=10, padx=20)

        tk.Button(
            self.root,
            text="Parar monitoramento",
            font=("Segoe UI", 11),
            command=self._parar_monitoramento,
        ).pack(pady=20)

    # ---------------------------------------------------------------
    # MODO 100% AUTOMÁTICO (SEM CONFIRMAR)
    # ---------------------------------------------------------------
    def selecionar_pasta_para_monitorar_auto(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar")
        if not pasta:
            return

        self.modo_auto = True
        self.pasta_monitorada = pasta
        self.pendentes = []
        self._iniciar_monitoramento(pasta)
        self._montar_tela_monitorando_auto()

    def _montar_tela_monitorando_auto(self):
        self._limpar_tela()
        self.root.geometry("560x600")

        tk.Label(
            self.root,
            text="Monitorando pasta (100% automático):",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(20, 2))

        tk.Label(
            self.root,
            text=self.pasta_monitorada,
            font=("Segoe UI", 9),
            wraplength=520,
            fg="darkblue",
        ).pack(pady=(0, 10))

        tk.Label(
            self.root,
            text=(
                "Quando os 4 dados forem encontrados sem divergência, o "
                "arquivo é renomeado sozinho, sem precisar confirmar. Se "
                "algo vier incompleto, o arquivo cai na lista de "
                "\"Precisa revisar\" abaixo, sem risco de salvar errado."
            ),
            font=("Segoe UI", 9),
            fg="gray30",
            wraplength=520,
            justify="left",
        ).pack(pady=(0, 10), padx=20)

        tk.Label(self.root, text="Histórico:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=20
        )
        log_frame = tk.Frame(self.root)
        log_frame.pack(padx=20, pady=(2, 10), fill="both", expand=False)
        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        tk.Label(
            self.root, text="Precisa revisar manualmente:", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=20, pady=(5, 2))
        self.pendentes_frame = tk.Frame(self.root)
        self.pendentes_frame.pack(padx=20, pady=(0, 10), fill="both", expand=True)

        tk.Button(
            self.root,
            text="Parar monitoramento",
            font=("Segoe UI", 11),
            command=self._parar_monitoramento,
        ).pack(pady=15)

        self._atualizar_lista_pendentes()

    def _log_auto(self, texto):
        if not hasattr(self, "log_text"):
            return
        self.log_text.config(state="normal")
        self.log_text.insert("end", texto + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _adicionar_pendente(self, caminho, motivo):
        self.pendentes.append((caminho, motivo))
        self._atualizar_lista_pendentes()

    def _atualizar_lista_pendentes(self):
        if not hasattr(self, "pendentes_frame"):
            return
        for widget in self.pendentes_frame.winfo_children():
            widget.destroy()

        if not self.pendentes:
            tk.Label(
                self.pendentes_frame,
                text="Nenhum arquivo pendente no momento.",
                font=("Segoe UI", 9),
                fg="gray40",
            ).pack(anchor="w", pady=4)
            return

        for caminho, motivo in list(self.pendentes):
            linha = tk.Frame(self.pendentes_frame)
            linha.pack(fill="x", pady=3)
            texto = f"{os.path.basename(caminho)} — {motivo}"
            tk.Label(
                linha, text=texto, font=("Segoe UI", 9), wraplength=380, justify="left"
            ).pack(side="left", fill="x", expand=True)
            tk.Button(
                linha,
                text="Revisar",
                font=("Segoe UI", 9),
                command=lambda c=caminho: self._revisar_pendente(c),
            ).pack(side="right", padx=5)

    def _revisar_pendente(self, caminho):
        self.pendentes = [(c, m) for c, m in self.pendentes if c != caminho]
        self._atualizar_lista_pendentes()
        self.processando_da_fila = True
        self._processar_arquivo(caminho, voltar_para="monitorando_auto")

    def _processar_arquivo_auto(self, caminho):
        nome_arquivo = os.path.basename(caminho)
        try:
            dados, divergencias, texto = extrair_dados(caminho)
        except Exception as e:
            self._log_auto(f"❌ Erro ao ler {nome_arquivo}: {e}")
            self._adicionar_pendente(caminho, "erro ao ler o PDF")
            return

        campos_faltando = [chave for chave, valor in dados.items() if not valor]
        if campos_faltando or divergencias:
            partes = []
            if campos_faltando:
                partes.append("não encontrado: " + ", ".join(campos_faltando))
            if divergencias:
                partes.append("divergência em: " + ", ".join(divergencias))
            motivo = "; ".join(partes)
            self._log_auto(f"⚠ {nome_arquivo} precisa de revisão ({motivo})")
            self._adicionar_pendente(caminho, motivo)
            return

        prefixo = obter_prefixo(nome_arquivo)
        novo_nome = montar_novo_nome(
            prefixo, dados["ficha"], dados["empenho"], dados["parcela"], dados["ano"]
        )
        pasta = os.path.dirname(caminho)
        novo_caminho = os.path.join(pasta, novo_nome)

        if os.path.exists(novo_caminho):
            base, ext = os.path.splitext(novo_nome)
            contador = 2
            while os.path.exists(os.path.join(pasta, f"{base}_v{contador}{ext}")):
                contador += 1
            novo_nome = f"{base}_v{contador}{ext}"
            novo_caminho = os.path.join(pasta, novo_nome)

        try:
            os.rename(caminho, novo_caminho)
        except Exception as e:
            self._log_auto(f"❌ Erro ao renomear {nome_arquivo}: {e}")
            self._adicionar_pendente(caminho, "erro ao renomear")
            return

        self._log_auto(f"✅ {nome_arquivo} → {novo_nome}")

    def _verificar_fila(self):
        if self.pasta_monitorada is None:
            return

        if self.modo_auto:
            if not self.processando_da_fila:
                while True:
                    try:
                        caminho = self.fila_arquivos.get_nowait()
                    except queue.Empty:
                        break
                    self._processar_arquivo_auto(caminho)
        else:
            # Só processa um arquivo por vez. Se já tiver uma confirmação
            # aberta, não faz nada agora - o próximo ciclo tenta de novo.
            if not self.processando_da_fila:
                try:
                    caminho = self.fila_arquivos.get_nowait()
                except queue.Empty:
                    caminho = None

                if caminho is not None:
                    self.processando_da_fila = True
                    if hasattr(self, "status_var"):
                        self.status_var.set(
                            f"Novo arquivo detectado: {os.path.basename(caminho)}"
                        )
                    self._processar_arquivo(caminho, voltar_para="monitorando")

        # Continua verificando a fila enquanto a pasta estiver sendo
        # monitorada (mesmo com a tela de confirmação aberta, o after
        # continua rodando em paralelo).
        if self.pasta_monitorada is not None:
            self.root.after(self.INTERVALO_VERIFICACAO_FILA_MS, self._verificar_fila)

    # ---------------------------------------------------------------
    # PROCESSAMENTO COMUM (usado pelos dois modos)
    # ---------------------------------------------------------------
    def _processar_arquivo(self, caminho, voltar_para):
        self.caminho_pdf = caminho
        self.voltar_para = voltar_para  # "inicial" ou "monitorando"

        try:
            dados, divergencias, texto = extrair_dados(caminho)
        except Exception as e:
            messagebox.showerror("Erro ao ler PDF", f"Não consegui ler o PDF:\n{e}")
            self.processando_da_fila = False
            return

        self.dados_extraidos = dados
        self.divergencias = divergencias
        self._montar_tela_confirmacao()

    def _montar_tela_confirmacao(self):
        self._limpar_tela()

        nome_arquivo = os.path.basename(self.caminho_pdf)
        prefixo = obter_prefixo(nome_arquivo)
        self.prefixo = prefixo

        tk.Label(
            self.root,
            text=f"Arquivo: {nome_arquivo}",
            font=("Segoe UI", 10, "bold"),
        ).pack(pady=(15, 5))

        if self.divergencias:
            aviso = (
                "⚠ Atenção: encontrei valores diferentes para: "
                + ", ".join(self.divergencias)
                + ". Confira com cuidado abaixo."
            )
            tk.Label(
                self.root,
                text=aviso,
                fg="darkred",
                wraplength=460,
                justify="left",
                font=("Segoe UI", 9),
            ).pack(pady=5, padx=20)

        campos_frame = tk.Frame(self.root)
        campos_frame.pack(pady=10, padx=20, fill="x")

        rotulos = {
            "ficha": "Ficha",
            "empenho": "Empenho",
            "parcela": "Parcela",
            "ano": "Ano",
        }

        self.campos = {}
        for i, (chave, rotulo) in enumerate(rotulos.items()):
            tk.Label(campos_frame, text=f"{rotulo}:", font=("Segoe UI", 10)).grid(
                row=i, column=0, sticky="w", pady=6
            )
            var = tk.StringVar(value=self.dados_extraidos.get(chave, ""))
            self.campos[chave] = var
            entry = tk.Entry(campos_frame, textvariable=var, font=("Segoe UI", 10), width=22)
            entry.grid(row=i, column=1, pady=6, padx=10)
            var.trace_add("write", lambda *args: self._atualizar_preview())

        tk.Label(self.root, text="Nome final do arquivo:", font=("Segoe UI", 10, "bold")).pack(
            pady=(15, 2)
        )
        self.preview_var = tk.StringVar()
        tk.Label(
            self.root,
            textvariable=self.preview_var,
            font=("Segoe UI", 10),
            fg="darkblue",
            wraplength=460,
        ).pack(pady=2, padx=20)

        botoes_frame = tk.Frame(self.root)
        botoes_frame.pack(pady=20)

        tk.Button(
            botoes_frame,
            text="Confirmar e renomear",
            font=("Segoe UI", 11),
            bg="#2e7d32",
            fg="white",
            command=self.confirmar_renomear,
        ).grid(row=0, column=0, padx=10)

        tk.Button(
            botoes_frame,
            text="Cancelar",
            font=("Segoe UI", 11),
            command=self._cancelar_confirmacao,
        ).grid(row=0, column=1, padx=10)

        self._atualizar_preview()

    def _cancelar_confirmacao(self):
        self.processando_da_fila = False
        if self.voltar_para == "monitorando" and self.pasta_monitorada is not None:
            self._montar_tela_monitorando()
        elif self.voltar_para == "monitorando_auto" and self.pasta_monitorada is not None:
            self._montar_tela_monitorando_auto()
        else:
            self._montar_tela_inicial()

    def _atualizar_preview(self):
        ficha = self.campos["ficha"].get().strip()
        empenho = self.campos["empenho"].get().strip()
        parcela = self.campos["parcela"].get().strip()
        ano = self.campos["ano"].get().strip()
        novo_nome = montar_novo_nome(self.prefixo, ficha, empenho, parcela, ano)
        self.preview_var.set(novo_nome)

    def confirmar_renomear(self):
        ficha = self.campos["ficha"].get().strip()
        empenho = self.campos["empenho"].get().strip()
        parcela = self.campos["parcela"].get().strip()
        ano = self.campos["ano"].get().strip()

        if not all([ficha, empenho, parcela, ano]):
            messagebox.showwarning(
                "Campos incompletos",
                "Preencha todos os campos antes de confirmar.",
            )
            return

        novo_nome = montar_novo_nome(self.prefixo, ficha, empenho, parcela, ano)
        pasta = os.path.dirname(self.caminho_pdf)
        novo_caminho = os.path.join(pasta, novo_nome)

        if os.path.exists(novo_caminho):
            resposta = messagebox.askyesno(
                "Arquivo já existe",
                f"Já existe um arquivo chamado:\n{novo_nome}\n\nDeseja sobrescrever?",
            )
            if not resposta:
                return

        try:
            os.rename(self.caminho_pdf, novo_caminho)
        except Exception as e:
            messagebox.showerror("Erro ao renomear", f"Não consegui renomear:\n{e}")
            return

        messagebox.showinfo("Pronto!", f"Arquivo renomeado para:\n{novo_nome}")

        self.processando_da_fila = False
        if self.voltar_para == "monitorando" and self.pasta_monitorada is not None:
            self._montar_tela_monitorando()
        elif self.voltar_para == "monitorando_auto" and self.pasta_monitorada is not None:
            self._log_auto(f"✅ {os.path.basename(self.caminho_pdf)} → {novo_nome} (revisado manualmente)")
            self._montar_tela_monitorando_auto()
        else:
            self._montar_tela_inicial()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
