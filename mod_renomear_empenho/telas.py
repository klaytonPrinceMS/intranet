"""Tela do módulo Renomear Empenhos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet import observabilidade
_log = observabilidade.get_logger("renomear_empenho")

from mod_renomear_empenho.manipulador_bd import (
    rodar_monitor, listar_empenhos, pesquisar, listar_quarentena,
    reprocesse_quarentena, salvar_regra, listar_regras, organizar_pastas,
    pasta_monitorada, alternar_regra,
    ferramenta_cortar, ferramenta_juntar, ferramenta_reduzir, ferramenta_fontes,
    PASTA_TEMP_FERR, gerar_matriz_organizador, validar_presenca_matriz,
    PASTA_ORGANIZADOR,
)
from mod_intranet import rotinas as _rotinas
from mod_intranet import email_util
from mod_intranet.manipulador_bd import audit_log
from mod_intranet.aba_modulo import cabecalho, abas
import zipfile, shutil


def mostrar_tela(usuario_logado: str, perfil: str):
    from mod_intranet.conexao_bd import get_config, set_config

    # ================= TEMA (Aparência, prefixo empenhos_) =================
    def _tema(chave, default):
        try:
            return (get_config(f"empenhos_{chave}", default) or "").strip() or default
        except Exception:
            return default

    t_cor_botao = _tema("cor_botao", "#2E7D32")
    t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
    t_cor_fundo = _tema("cor_fundo", "")
    t_cor_titulo = _tema("cor_titulo", "#212121")
    t_tamanho = _tema("btn_tamanho", "medium")

    def _btn_cls():
        if t_tamanho == "small":
            return "min-w-[140px] text-sm"
        if t_tamanho == "large":
            return "min-w-[220px] text-lg"
        return "min-w-[180px]"

    def _btn_style():
        st = ""
        if t_cor_botao:
            st += f"background-color:{t_cor_botao};"
        if t_cor_txt_botao:
            st += f"color:{t_cor_txt_botao};"
        return st

    texto_header = _tema_s(get_config, "empenhos_texto_header",
                           f"Monitora a pasta <code>{pasta_monitorada()}</code>, extrai o nº do empenho "
                           "por regex, renomeia como <b>doc_0001_numEmpenho_123456_p001.pdf</b> e organiza em caixas.")

    cabecalho("Renomeador de Empenhos", texto_header, cor_borda="#2E7D32",
              cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)
    eh_admin = perfil == "administrador_geral" or (perfil and "admin" in perfil)
    tabs_el = abas("Renomeador", "receipt_long", admin=eh_admin)
    with ui.tab_panels(tabs_el, value="principal").classes("w-full"):
        with ui.tab_panel("principal"):

            # ================= Ações rápidas =================
            with ui.row().classes("w-full gap-3 flex-wrap"):
                def _rodar_monitor():
                    try:
                        res = rodar_monitor(usuario_logado)
                        ok = sum(1 for r in res if r.get("ok"))
                        qtd = len(res)
                        _log.info(f"monitor disparado por {usuario_logado}: {ok}/{qtd} processado(s)")
                        if qtd == 0:
                            ui.notify("Nenhum PDF novo na pasta monitorada", type="info")
                        else:
                            ui.notify(f"{ok}/{qtd} processado(s). Falhas → quarentena.", type="positive" if ok else "warning")
                        atualizar_tudo()
                    except Exception:
                        _log.exception("erro no handler _rodar_monitor")

                ui.button("Processar pasta agora", icon="play_arrow",
                          on_click=_rodar_monitor).props("unelevated").classes(_btn_cls()).style(_btn_style())

                def _organizar():
                    try:
                        ok, msg = organizar_pastas()
                        _log.info(f"organizar caixas por {usuario_logado}: {msg}")
                        ui.notify(msg, type="positive" if ok else "negative")
                        atualizar_tudo()
                    except Exception:
                        _log.exception("erro no handler _organizar")

                ui.button("Organizar caixas", icon="inventory_2",
                          on_click=_organizar).props("unelevated").classes(_btn_cls()).style(_btn_style())

                def _gerar_matriz():
                    try:
                        ok, msg = gerar_matriz_organizador()
                        ui.notify(msg, type="positive" if ok else "negative")
                    except Exception:
                        _log.exception("erro ao gerar matriz")

                ui.button("Gerar capas/matriz", icon="description", on_click=_gerar_matriz) \
                    .props("outline").classes(_btn_cls()).style(_btn_style())

                def _validar_matriz():
                    try:
                        ok, faltando = validar_presenca_matriz()
                        if ok:
                            ui.notify("Todos os documentos da matriz estão presentes.", type="positive")
                        else:
                            ui.notify("Faltando na matriz: " + ", ".join(faltando[:10]), type="warning")
                    except Exception:
                        _log.exception("erro ao validar matriz")

                ui.button("Validar matriz", icon="rule", on_click=_validar_matriz) \
                    .props("outline").classes(_btn_cls()).style(_btn_style())

                with ui.input(placeholder="Pesquisar conteúdo…").props("outlined dense clearable").classes("w-64") as busca:

                    def _pesq(e):
                        resultados_wrap.clear()
                        termo = e.args if isinstance(e.args, str) else (e.args and e.args[0]) or ""
                        _log.debug(f"pesquisa: {termo}")
                        rs = pesquisar(termo)
                        with resultados_wrap:
                            for r in rs[:20]:
                                eid, final, num, parc, usr, dt, caminho = r
                                with ui.item().classes("w-full border rounded-lg mb-1"):
                                    with ui.item_section().props("avatar"):
                                        ui.icon("description").classes("text-green-8")
                                    with ui.item_section():
                                        ui.item_label(final)
                                        ui.item_label(f"empenho {num} • parcela {parc} • {usr}").props("caption")
                                # clique abre arquivo se existir
                        if not rs:
                            with resultados_wrap:
                                ui.label("Nada encontrado.").classes("text-caption text-grey-5")

                busca.on("update:model-value", _pesq)
                resultados_wrap = ui.column().classes("w-full")

            # ================= Empenhos =================
            colunas = [
                {"name": "final", "label": "Nome final", "field": "final", "align": "left"},
                {"name": "num", "label": "Empenho", "field": "num"},
                {"name": "parc", "label": "Parcela", "field": "parc"},
                {"name": "usr", "label": "Usuário", "field": "usr"},
                {"name": "dt", "label": "Data", "field": "dt"},
            ]
            tabela = ui.table(columns=colunas, rows=[], row_key="id").props("flat bordered dense").classes("w-full")

            def _refresh_empenhos():
                tabela.rows = [
                    {"id": r[0], "final": r[2], "num": r[3], "parc": r[4],
                     "usr": r[5] or "—", "dt": (r[6] or "")[:16]}
                    for r in listar_empenhos()
                ]
                tabela.update()

            # ================= Quarentena =================
            ui.label("Quarentena").classes("text-h6 font-bold text-grey-8 mt-4")
            colunas_q = [
                {"name": "arquivo", "label": "Arquivo", "field": "arquivo", "align": "left"},
                {"name": "motivo", "label": "Motivo", "field": "motivo", "align": "left"},
                {"name": "data", "label": "Recebido em", "field": "data"},
                {"name": "qid", "label": "", "field": "qid"},
            ]
            tabela_q = ui.table(columns=colunas_q, rows=[], row_key="qid").props("flat bordered dense").classes("w-full")

            def _refresh_quarentena():
                tabela_q.rows = [
                    {"qid": r[0], "arquivo": r[1], "motivo": (r[2] or "")[:80],
                     "data": (r[3] or "")[:16]}
                    for r in listar_quarentena() if not r[4]
                ]
                tabela_q.update()

            def on_q_click(e):
                linha = e.args[1]
                with ui.dialog() as dlg, ui.card().classes("w-[480px]"):
                    ui.label("Reprocessar com nova regex").classes("text-h6")
                    ui.label(linha["arquivo"]).classes("text-caption text-grey-6")
                    padrao = ui.input("Regex alternativa (opcional)").props("outlined dense").classes("w-full")

                    def tentar():
                        try:
                            ok, msg = reprocesse_quarentena(linha["qid"], padrao.value or None, usuario_logado)
                            _log.info(f"reprocessar quarentena qid={linha['qid']} por {usuario_logado}: ok={ok} {msg}")
                            ui.notify(("Sucesso: " + msg) if ok else ("Falha: " + msg),
                                      type="positive" if ok else "warning")
                            dlg.close(); atualizar_tudo()
                        except Exception:
                            _log.exception(f"erro ao reprocessar quarentena qid={linha['qid']}")

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        ui.button("Reprocessar", on_click=tentar).props("unelevated").classes(_btn_cls()).style(_btn_style())
                dlg.open()

            tabela_q.on("row-click", on_q_click)

            # ================= Regras regex =================
            with ui.expansion("Regras de extração (regex dinâmicas)", icon="rule").classes("w-full mt-2"):
                lista_regras = ui.column().classes("w-full")

                def _refresh_regras():
                    lista_regras.clear()
                    with lista_regras:
                        for rid, nome, padrao, ativo, destino in listar_regras():
                            with ui.row().classes("w-full items-center gap-2 py-1"):
                                ui.icon("bolt" if ativo else "block").classes("text-orange-7" if ativo else "text-grey-5")
                                ui.label(nome).classes("font-medium w-40")
                                ui.code(padrao).style("flex:1; overflow-x:auto")
                                if destino:
                                    ui.badge(f"→ {destino}", color="purple").props("outline") \
                                        .tooltip("Campo FTS customizado alimentado por esta regex")
                                if not ativo:
                                    ui.badge("inativa", color="grey")

                    def _toggle(r=rid, a=ativo):
                        try:
                            ok, msg = alternar_regra(r, not a)
                            _log.info(f"regra {r} alternada por {usuario_logado}: ok={ok} {msg}")
                            ui.notify(msg, type="positive" if ok else "negative")
                            _refresh_regras()
                        except Exception:
                            _log.exception(f"erro ao alternar regra {r}")

                    ui.button("Inativar" if ativo else "Ativar", on_click=_toggle) \
                                    .props("flat dense size=sm")

                _refresh_regras()

                with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
                    n_nome = ui.input("Nome da regra").props("outlined dense").classes("w-44")
                    n_padrao = ui.input("Padrão (regex)", placeholder=r"empenho\s*n[ºo]?\s*(\d+)") \
                        .props("outlined dense").classes("grow min-w-[240px]")
                    n_destino = ui.input("Campo FTS destino (opcional)") \
                        .props("outlined dense").classes("w-56") \
                        .tooltip("Nome do campo do índice FTS5 alimentado pelo 1º grupo capturado "
                                 "desta regex (ex.: cpf_cnpj, orgao, valor). Deixe vazio para só extrair o nº.")

                    def salvar():
                        if not n_nome.value or not n_padrao.value:
                            ui.notify("Informe nome e padrão", type="warning"); return
                        try:
                            ok, msg = salvar_regra(n_nome.value.strip(), n_padrao.value.strip(),
                                                   campo_destino=(n_destino.value or "").strip() or None)
                            _log.info(f"regra salva por {usuario_logado}: ok={ok} {msg}")
                            ui.notify(msg, type="positive" if ok else "negative")
                            if ok:
                                n_nome.set_value(None); n_padrao.set_value(None); n_destino.set_value(None)
                                _refresh_regras()
                        except Exception:
                            _log.exception("erro ao salvar regra")

                    ui.button("Salvar regra", icon="save", on_click=salvar) \
                        .props("unelevated").classes(_btn_cls()).style(_btn_style())

            # ================= FERRAMENTAS DE PDF (RF-45) =================
            with ui.expansion("Ferramentas de PDF — corte / mesclar / reduzir", icon="picture_as_pdf") \
                    .classes("w-full mt-2"):
                ui.label("Opera sobre empenhos já processados ou PDFs enviados. Saídas em "
                         "datahora_cortePDF/, datahora_mergePDF/ e datahora_reducaoPDF/.") \
                    .classes("text-caption text-grey-6")
                fontes_opts = {str(fid): f"{final}  (#{fid})" for fid, final, _ in ferramenta_fontes()}
                sel_fontes = ui.select(
                    fontes_opts, label="Empenhos processados (use Ctrl/⌘ para vários)", multiple=True
                ).props("outlined dense use-chips").classes("w-full")
                up = ui.upload(label="Enviar PDFs (opcional)").props("multiple accept=.pdf auto-upload outlined dense")
                up_paths = []

                def _up(event):
                    import datetime as _dt
                    for arquivo in (getattr(event, "args", None) or []):
                        try:
                            arquivo.content.seek(0)
                            os.makedirs(PASTA_TEMP_FERR, exist_ok=True)
                            dest = os.path.join(
                                PASTA_TEMP_FERR,
                                f"{_dt.datetime.now():%Y%m%d%H%M%S}_{os.path.basename(arquivo.name)}")
                            with open(dest, "wb") as f:
                                f.write(arquivo.content.read())
                            up_paths.append(dest)
                            _log.info(f"ferramenta upload: {dest}")
                        except Exception as ex:
                            _log.warning(f"ferramenta upload falhou: {ex}")

                up.on("multi-upload", _up)

                def _fontes_atuais():
                    caminhos = []
                    for fid in (sel_fontes.value or []):
                        for f in ferramenta_fontes():
                            if str(f[0]) == str(fid):
                                caminhos.append(f[2])
                    return caminhos + list(up_paths)

                with ui.row().classes("w-full gap-3 flex-wrap items-end"):
                    modo = ui.select({"pares": "Pares", "impares": "Ímpares"},
                                     label="Corte", value="pares").props("outlined dense")
                    interv = ui.input("Ou intervalo (ex.: 2-5,8)").props("outlined dense")
                    qual = ui.slider(min=10, max=100, value=50, step=5).props("label ticks").classes("w-48")
                    modo_red = ui.select({"leve": "Leve (recompressar)", "agressivo": "Agressivo (rasterizar)"},
                                         label="Redução", value="leve").props("outlined dense")

                res_ferr = ui.column().classes("w-full")

                def _mostrar(ok, res, acao):
                    res_ferr.clear()
                    if ok:
                        with res_ferr:
                            ui.label(f"{acao}: {os.path.basename(res)}").classes("text-caption text-green-8")
                            ui.link("Baixar arquivo", res, new_tab=True)
                    else:
                        ui.notify(f"{acao} falhou: {res}", type="negative")

                def _cortar():
                    srcs = _fontes_atuais()
                    if not srcs:
                        ui.notify("Selecione ao menos 1 fonte", type="warning"); return
                    filtro = interv.value.strip() if interv.value and interv.value.strip() else modo.value
                    ok, res = ferramenta_cortar(srcs[0], filtro, usuario_logado)
                    _mostrar(ok, res, "Corte")

                def _juntar():
                    srcs = _fontes_atuais()
                    if len(srcs) < 2:
                        ui.notify("Selecione ao menos 2 fontes para mesclar", type="warning"); return
                    ok, res = ferramenta_juntar(srcs, usuario_logado)
                    _mostrar(ok, res, "Mescla")

                def _reduzir():
                    srcs = _fontes_atuais()
                    if not srcs:
                        ui.notify("Selecione ao menos 1 fonte", type="warning"); return
                    ok, res = ferramenta_reduzir(srcs[0], usuario_logado, qualidade=qual.value, modo=modo_red.value)
                    _mostrar(ok, res, "Redução")

                with ui.row().classes("w-full gap-2 mt-2"):
                    ui.button("Cortar", icon="content_cut", on_click=_cortar) \
                        .props("unelevated").classes(_btn_cls()).style(_btn_style())
                    ui.button("Mesclar", icon="merge", on_click=_juntar) \
                        .props("unelevated").classes(_btn_cls()).style(_btn_style())
                    ui.button("Reduzir", icon="compress", on_click=_reduzir) \
                        .props("unelevated").classes(_btn_cls()).style(_btn_style())

            def atualizar_tudo():
                _refresh_empenhos(); _refresh_quarentena(); _refresh_regras()

            atualizar_tudo()
            # ================= AÇÕES DE USUÁRIO COMUM (RF-39) =================
            def _zip_organizador():
                if not os.path.isdir(PASTA_ORGANIZADOR):
                    return None, "Pasta organizada não encontrada — rode 'Organizar caixas'."
                os.makedirs(PASTA_TEMP_FERR, exist_ok=True)
                dest = os.path.join(PASTA_TEMP_FERR, "empenhos_organizados.zip")
                if os.path.exists(dest):
                    os.remove(dest)
                with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
                    for raiz, _, arquivos in os.walk(PASTA_ORGANIZADOR):
                        for arq in arquivos:
                            caminho = os.path.join(raiz, arq)
                            z.write(caminho, os.path.relpath(caminho, PASTA_ORGANIZADOR))
                return dest, "ZIP dos empenhos organizados gerado"

            autorizado = get_config("renomear_autorizar_download", "0") == "1"

            with ui.card().classes("w-full mt-4"):
                ui.label("Ações de usuário comum (download / ZIP / e-mail)").classes(
                    "text-subtitle1 font-bold")
                if not autorizado:
                    ui.label("Download, ZIP e envio por e-mail estão aguardando autorização "
                              "de um administrador.").classes("text-caption text-orange-8")
                inp_email = ui.input("E-mail para envio (opcional)",
                                     placeholder="usuario@dominio.com") \
                    .props("outlined dense").classes("w-full")

                def _autorizado():
                    return get_config("renomear_autorizar_download", "0") == "1"

                def _baixar_zip():
                    if not _autorizado():
                        ui.notify("Aguardando autorização de um administrador.", type="warning")
                        return
                    caminho, msg = _zip_organizador()
                    if not caminho:
                        ui.notify(msg, type="negative")
                        return
                    ui.download(caminho, "empenhos_organizados.zip")
                    ui.notify(msg, type="positive")

                def _enviar_email():
                    if not _autorizado():
                        ui.notify("Aguardando autorização de um administrador.", type="warning")
                        return
                    dest = (inp_email.value or "").strip()
                    if "@" not in dest:
                        ui.notify("Informe um e-mail válido para envio.", type="negative")
                        return
                    caminho, msg = _zip_organizador()
                    if not caminho:
                        ui.notify(msg, type="negative")
                        return
                    ok, res = email_util.enviar_email(
                        dest, "Empenhos renomeados",
                        "Segue em anexo os empenhos organizados.",
                        anexos=[caminho])
                    ui.notify(res, type="positive" if ok else "negative")

                with ui.row().classes("w-full gap-3 flex-wrap"):
                    ui.button("Baixar ZIP", icon="download", on_click=_baixar_zip) \
                        .props("unelevated no-caps" + ("" if autorizado else " disable")) \
                        .classes(_btn_cls()).style(_btn_style())
                    ui.button("Enviar por e-mail", icon="mail", on_click=_enviar_email) \
                        .props("outline no-caps" + ("" if autorizado else " disable")) \
                        .classes(_btn_cls()).style(_btn_style())

        with ui.tab_panel("adm"):
            if perfil == "administrador_geral" or (perfil and "admin" in perfil):
                from mod_renomear_empenho.manipulador_bd import _PASTA_MONITORADA_PADRAO
                with ui.expansion("Administração — configurações dos Empenhos", icon="settings"
                                  ).classes("w-full mt-4"):
                    ui.label("Aparência — temas dos botões desta tela").classes("text-subtitle2 text-grey-7")
                    inp_cor_botao = ui.color_input(label="Cor dos botões", value=t_cor_botao)
                    inp_cor_txt = ui.color_input(label="Cor do texto dos botões", value=t_cor_txt_botao)
                    inp_cor_fundo = ui.color_input(label="Cor de fundo da página (vazio = herda)",
                                                   value=t_cor_fundo)
                    inp_cor_titulo = ui.color_input(label="Cor dos títulos", value=t_cor_titulo)
                    sel_tamanho = ui.select(
                        {0: "Pequeno", 1: "Médio", 2: "Grande"},
                        label="Tamanho dos botões",
                        value={"small": 0, "medium": 1, "large": 2}.get(t_tamanho, 1),
                    ).props("outlined dense")

                    with ui.separator().classes("my-3"):
                        pass
                    ui.label("Configurações específicas").classes("text-subtitle2 text-grey-7")
                    inp_pasta = ui.input("Pasta monitorada (caminho absoluto ou relativo à raiz)",
                                         value=pasta_monitorada()).props("outlined dense").classes("w-full") \
                        .tooltip("Ex.: doc, ou C:\\arquivos\\empenhos")
                    inp_texto = ui.input("Texto do cabeçalho", value=texto_header).props("outlined dense").classes("w-full")
                    inp_intervalo = ui.input("Intervalo do monitor automático (segundos)",
                                             value=str(_rotinas.intervalo_monitor_empenho())) \
                        .props("outlined dense").classes("w-full") \
                        .tooltip("Varredura automática da pasta monitorada (RF-40). Aplicado sem reiniciar.")

                    sw_autorizar = ui.switch(
                        "Autorizar download/ZIP/e-mail para usuários comuns",
                        value=get_config("renomear_autorizar_download", "0") == "1") \
                        .props("dense") \
                        .tooltip("Quando ativo, usuários comuns podem baixar/enviar os empenhos organizados (RF-39).")

                    _tamanhos = {0: "small", 1: "medium", 2: "large"}

                    def salvar():
                        try:
                            v_pasta = (inp_pasta.value or "").strip()
                            set_config("empenhos_pasta_monitorada", v_pasta)
                            set_config("empenhos_cor_botao", inp_cor_botao.value or "")
                            set_config("empenhos_cor_texto_botao", inp_cor_txt.value or "")
                            set_config("empenhos_cor_fundo", inp_cor_fundo.value or "")
                            set_config("empenhos_cor_titulo", inp_cor_titulo.value or "")
                            set_config("empenhos_btn_tamanho", _tamanhos[sel_tamanho.value])
                            set_config("empenhos_texto_header", (inp_texto.value or "").strip())
                            set_config("renomear_autorizar_download", "1" if sw_autorizar.value else "0")
                            try:
                                iv = max(1, int((inp_intervalo.value or "10").strip() or 10))
                                set_config("empenhos_monitor_intervalo_seg", str(iv))
                                _rotinas.reagendar_monitor_empenho(iv)
                            except Exception as ex:
                                _log.warning(f"intervalo monitor não aplicado: {ex}")
                            try:
                                audit_log(usuario_logado, "renomear-empenho", "configuracao",
                                          "configurações do módulo salvas")
                            except Exception:
                                pass
                            _log.info(f"configurações salvas por {usuario_logado}")
                            ui.notify("Configurações salvas (valem sem reiniciar)", type="positive")
                            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                        except Exception:
                            _log.exception("erro ao salvar configurações de empenhos")

                    def resetar():
                        try:
                            set_config("empenhos_pasta_monitorada", _PASTA_MONITORADA_PADRAO)
                            for chave, valor in (("cor_botao", "#2E7D32"), ("cor_texto_botao", "#FFFFFF"),
                                                 ("cor_fundo", ""), ("cor_titulo", "#212121"),
                                                 ("btn_tamanho", "medium"), ("texto_header", ""),
                                                 ("monitor_intervalo_seg", "10")):
                                set_config(f"empenhos_{chave}", valor)
                            try:
                                audit_log(usuario_logado, "renomear-empenho", "configuracao",
                                          "configurações do módulo restauradas ao padrão")
                            except Exception:
                                pass
                            _log.info(f"configurações restauradas por {usuario_logado}")
                            ui.notify("Padrões restaurados", type="positive")
                            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                        except Exception:
                            _log.exception("erro ao resetar configurações de empenhos")

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button("Restaurar padrão", on_click=resetar).props("flat") \
                            .classes(_btn_cls()).style(_btn_style())
                        ui.button("Salvar", icon="save", on_click=salvar).props("unelevated") \
                            .classes(_btn_cls()).style(_btn_style())
def _tema_s(get_config, chave, default):
    try:
        return (get_config(chave, default) or "").strip() or default
    except Exception:
        return default
