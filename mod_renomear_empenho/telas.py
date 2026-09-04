"""Tela do módulo Renomear Empenhos — 6 abas: Navegar, Fila, Pesquisar,
Organizador (admin), Solicitação e Configurações (admin)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet import observabilidade
_log = observabilidade.get_logger("renomear_empenho")

from mod_renomear_empenho.manipulador_bd import (
    rodar_monitor, listar_empenhos, pesquisar, listar_quarentena,
    reprocesse_quarentena, salvar_regra, listar_regras, organizar_pastas,
    pasta_monitorada, pastas_monitoradas, salvar_pastas_monitoradas,
    alternar_regra, listar_arquivos_auditoria, listar_eventos_arquivo,
    listar_campos_busca, salvar_campo_busca, excluir_campo_busca,
    restaurar_campos_busca_padrao, template_nome_atual, montar_nome_final,
    NOME_FINAL_PADRAO, extrair_dados_empenho,
    ferramenta_cortar, ferramenta_juntar, ferramenta_reduzir, ferramenta_fontes,
    PASTA_TEMP_FERR, gerar_matriz_organizador, validar_presenca_matriz,
    PASTA_ORGANIZADOR,
    listar_navegacao, listar_pendentes, status_arquivo, renomear_manual,
    raizes_navegacao, criar_solicitacao, listar_solicitacoes_acao_pendente,
    listar_solicitacoes, obter_solicitacao, marcar_solicitacao_enviada,
    marcar_solicitacoes_zip_gerado, marcar_solicitacao_pendente,
    marcar_solicitacao_recusada, gerar_zip_solicitacoes,
    enviar_solicitacao_por_email, agrupar_solicitacoes_em_lote,
)
from mod_intranet import rotinas as _rotinas
from mod_intranet import email_util
from mod_intranet.manipulador_bd import audit_log
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import campo_modulo
from mod_intranet.autenticacao import eh_admin_do_modulo
import zipfile, shutil


def _tema_s(get_config, chave, default):
    try:
        return (get_config(chave, default) or "").strip() or default
    except Exception:
        return default


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

    eh_admin = perfil == "administrador_geral" or eh_admin_do_modulo(usuario_logado, "empenhos") \
        or (perfil and "admin" in perfil)
    autorizado = get_config("renomear_autorizar_download", "0") == "1"

    pastas_msg = ", ".join(pastas_monitoradas()) or pasta_monitorada()
    texto_header = _tema_s(get_config, "empenhos_texto_header",
                           f"Monitora as pastas <code>{pastas_msg}</code> (local ou rede/UNC), "
                           "extrai o nº do empenho por regex (inclui tipos EC/EE/EG/AE), renomeia "
                           "e organiza em caixas.")

    cabecalho("Renomeador de Empenhos", texto_header, cor_borda="#2E7D32",
              cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

    _icones = {
        "navegar": "folder_open", "fila": "move_to_inbox", "pesquisa": "search",
        "organizador": "inventory_2", "solicitacao": "mail", "config": "settings",
    }
    with ui.tabs().classes("w-full") as tabs_el:
        for key, label in (("navegar", "Navegar"), ("fila", "Fila Renomeação"),
                           ("pesquisa", "Pesquisar"), ("organizador", "Organizador"),
                           ("solicitacao", "Solicitação"), ("config", "Configurações")):
            ui.tab(key, label, icon=_icones.get(key))
    with ui.tab_panels(tabs_el, value="navegar").classes("w-full"):
        with ui.tab_panel("navegar"):
            _tela_navegar(usuario_logado, eh_admin, autorizado, _btn_cls, _btn_style)
        with ui.tab_panel("fila"):
            _tela_fila(usuario_logado, eh_admin, _btn_cls, _btn_style)
        with ui.tab_panel("pesquisa"):
            _tela_pesquisar(usuario_logado, _btn_cls, _btn_style)
        with ui.tab_panel("organizador"):
            if eh_admin:
                _tela_organizador(usuario_logado, _btn_cls, _btn_style)
            else:
                ui.label("Acesso restrito ao administrador do módulo.").classes("text-negative")
        with ui.tab_panel("solicitacao"):
            _tela_solicitacao(usuario_logado, eh_admin, _btn_cls, _btn_style)
        with ui.tab_panel("config"):
            if eh_admin:
                _tela_config(usuario_logado, eh_admin, t_cor_botao, t_cor_txt_botao,
                             t_cor_fundo, t_cor_titulo, t_tamanho, texto_header,
                             _btn_cls, _btn_style)
            else:
                ui.label("Acesso restrito ao administrador do módulo.").classes("text-negative")


# ============================================================ ABA NAVEGAR
def _tela_navegar(usuario_logado, eh_admin, autorizado, _btn_cls, _btn_style):
    from mod_intranet.conexao_bd import get_config
    pasta_atual = {}

    def _baixar(caminho):
        if os.path.exists(caminho):
            ui.download(caminho, os.path.basename(caminho))

    def _revisar_renomear(caminho):
        nome = os.path.basename(caminho)
        with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
            ui.label(f"Revisar / renomear — {nome}").classes("text-h6")
            ui.label("O sistema normalizará o nome conforme o conteúdo e o tipo do "
                     "documento (DOC, EC, EE, EG, AE).").classes("text-caption text-grey-6")
            res = ui.column().classes("w-full mt-1")

            def _confirmar():
                try:
                    ok, msg = renomear_manual(usuario_logado, caminho)
                    if ok:
                        ui.notify(f"Renomeado → {msg}", type="positive")
                        dlg.close()
                        _carregar()
                    else:
                        with res:
                            ui.label(f"Não foi possível renomear: {msg}").classes("text-negative")
                except Exception as e:
                    with res:
                        ui.label(f"Erro: {e}").classes("text-negative")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Renomear (normalizar)", icon="auto_fix_high", on_click=_confirmar) \
                    .props("unelevated").classes(_btn_cls()).style(_btn_style())
        dlg.open()

    def _solicitar(caminho):
        nome = os.path.basename(caminho)
        with ui.dialog() as dlg, ui.card().classes("w-[460px]"):
            ui.label(f"Solicitar envio — {nome}").classes("text-h6")
            inp_mail = ui.input("Seu e-mail", placeholder="usuario@dominio.com", value=usuario_logado) \
                .props("outlined dense").classes("w-full")
            inp_msg = ui.textarea("Mensagem (opcional)").props("outlined dense").classes("w-full")

            def _enviar():
                dest = (inp_mail.value or "").strip()
                if "@" not in dest:
                    ui.notify("Informe um e-mail válido", type="negative")
                    return
                criar_solicitacao(caminho, nome, usuario_logado, dest, inp_msg.value or "")
                ui.notify("Solicitação registrada — aguardando o administrador.", type="positive")
                dlg.close()

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Solicitar", icon="send", on_click=_enviar).props("unelevated")
        dlg.open()

    def _carregar():
        wrap.clear()
        pasta = pasta_atual.get("caminho")
        nav = listar_navegacao(pasta)
        pasta_atual["caminho"] = nav["atual"]
        with wrap:
            # breadcrumb (trilha)
            raiz = raizes_navegacao()[0] if raizes_navegacao() else pasta_monitorada()
            with ui.row().classes("w-full items-center gap-1 flex-wrap"):
                ui.button(icon="arrow_upward", on_click=_subir).props("flat round dense size=sm") \
                    .tooltip("Pasta anterior")
                if nav["atual"] != raiz:
                    ui.button("Raiz", on_click=lambda: _ir(raiz)).props("flat dense size=sm")
                    rel = os.path.relpath(nav["atual"], raiz)
                    ui.label("/ " + rel).classes("text-caption text-grey-7")
                else:
                    ui.label("Raiz (pastas monitoradas)").classes("text-caption text-grey-7")
            # subpastas
            if nav["dirs"]:
                ui.label("Pastas").classes("text-subtitle2 font-bold text-grey-7 mt-2")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for d in nav["dirs"]:
                        ui.button(icon="folder", text=" " + d["nome"],
                                  on_click=lambda cam=d["caminho"]: _ir(cam)) \
                            .props("flat outline dense").classes("text-left")
            # pdfs
            ui.label("Documentos (PDF)").classes("text-subtitle2 font-bold text-grey-7 mt-3")
            if not nav["pdfs"]:
                ui.label("Nenhum PDF nesta pasta.").classes("text-caption text-grey-5")
            for p in nav["pdfs"]:
                with ui.card().classes("w-full p-3 mt-1"):
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.icon("picture_as_pdf")
                        ui.label(p["nome"]).classes("font-medium flex-1 text-wrap")
                        cor = {"processado": "green", "pendente": "orange"}.get(p["status"], "grey")
                        ui.badge(p["status"], color=cor)
                        ui.button(icon="download", on_click=lambda c=p["caminho"]: _baixar(c)) \
                            .props("flat round dense size=sm").tooltip("Baixar")
                        if p["status"] == "pendente":
                            ui.button(icon="edit", on_click=lambda c=p["caminho"]: _revisar_renomear(c)) \
                                .props("flat round dense size=sm").tooltip("Revisar / renomear")
                            ui.button(icon="mail", on_click=lambda c=p["caminho"]: _solicitar(c)) \
                                .props("flat round dense size=sm").tooltip("Solicitar envio")
                        elif autorizado:
                            ui.button(icon="mail", on_click=lambda c=p["caminho"]: _solicitar(c)) \
                                .props("flat round dense size=sm").tooltip("Solicitar envio")

    def _ir(cam):
        pasta_atual["caminho"] = cam
        _carregar()

    def _subir():
        p = pasta_atual.get("caminho") or pasta_monitorada()
        pai = os.path.dirname(p)
        if pais_navegavel(pai):
            _ir(pai)
        else:
            _ir(raizes_navegacao()[0] if raizes_navegacao() else pasta_monitorada())

    def pais_navegavel(pai):
        try:
            return pai in raizes_navegacao() or qualquer_raiz_tem(pai)
        except Exception:
            return False

    def qualquer_raiz_tem(pai):
        for r in raizes_navegacao():
            if pai == r or pai.startswith(r + os.sep):
                return True
        return False

    with ui.row().classes("w-full gap-2 flex-wrap items-center"):
        ui.button("Processar pasta agora", icon="play_arrow",
                  on_click=lambda: _processar()).props("unelevated").classes(_btn_cls()).style(_btn_style())
        ui.button("Atualizar", icon="refresh", on_click=_carregar).props("outline")
    wrap = ui.column().classes("w-full")

    def _processar():
        try:
            res = rodar_monitor(usuario_logado)
            ok = sum(1 for r in res if r.get("ok"))
            qtd = len(res)
            if qtd == 0:
                ui.notify("Nenhum PDF novo nas pastas monitoradas", type="info")
            else:
                ui.notify(f"{ok}/{qtd} processado(s). Falhas → quarentena.", type="positive" if ok else "warning")
            _carregar()
        except Exception:
            _log.exception("erro no handler _processar")

    _carregar()


# ============================================================ ABA FILA
def _tela_fila(usuario_logado, eh_admin, _btn_cls, _btn_style):
    wrap = ui.column().classes("w-full")

    def _carregar():
        wrap.clear()
        pendentes = listar_pendentes(recursivo=True)
        with wrap:
            ui.label(f"Fila de renomeação — {len(pendentes)} pendente(s)").classes("text-subtitle1 font-bold")
            if not pendentes:
                ui.label("Nenhum documento aguardando renomeação.").classes("text-caption text-grey-5")
            for p in pendentes:
                with ui.card().classes("w-full p-3 mt-1"):
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.icon("description")
                        ui.label(p["nome"]).classes("flex-1 text-wrap font-medium")
                        ui.badge("pendente", color="orange")

                        def _renomear(cam=p["caminho"]):
                            ok, msg = renomear_manual(usuario_logado, cam)
                            ui.notify(f"Renomeado → {msg}" if ok else f"Falha: {msg}",
                                      type="positive" if ok else "negative")
                            _carregar()

                        ui.button(icon="auto_fix_high", text="Processar", on_click=_renomear) \
                            .props("unelevated dense").classes(_btn_cls()).style(_btn_style())

    with ui.row().classes("w-full gap-2"):
        ui.button("Processar todos", icon="play_arrow",
                  on_click=lambda: _processar_todos()).props("unelevated").classes(_btn_cls()).style(_btn_style())
        ui.button("Atualizar", icon="refresh", on_click=_carregar).props("outline")

    def _processar_todos():
        pendentes = listar_pendentes(recursivo=True)
        ok = 0
        for p in pendentes:
            try:
                okr, _msg = renomear_manual(usuario_logado, p["caminho"])
                ok += 1 if okr else 0
            except Exception:
                pass
        ui.notify(f"{ok}/{len(pendentes)} processado(s)", type="positive" if ok else "warning")
        _carregar()

    _carregar()


# ============================================================ ABA PESQUISAR
def _tela_pesquisar(usuario_logado, _btn_cls, _btn_style):
    from mod_intranet.conexao_bd import get_config
    autorizado = get_config("renomear_autorizar_download", "0") == "1"

    with ui.input(placeholder="Pesquisar conteúdo…").props("outlined dense clearable").classes("w-full") as busca:
        pass
    resultados_wrap = ui.column().classes("w-full")

    def _pesq(e):
        resultados_wrap.clear()
        termo = e.args if isinstance(e.args, str) else (e.args and e.args[0]) or ""
        rs = pesquisar(termo) or []
        with resultados_wrap:
            if not rs:
                ui.label("Nada encontrado.").classes("text-caption text-grey-5")
                return
            for eid, final, num, parc, usr, dt, caminho in rs[:25]:
                with ui.item().classes("w-full border rounded-lg mb-1"):
                    with ui.item_section().props("avatar"):
                        ui.icon("description").classes("text-green-8")
                    with ui.item_section():
                        ui.item_label(final)
                        ui.item_label(f"empenho {num} • parcela {parc} • {usr}").props("caption")

    busca.on("update:model-value", _pesq)

    ui.separator().classes("my-3")
    ui.label("Empenhos renomeados").classes("text-subtitle1 font-bold")
    colunas = [
        {"name": "final", "label": "Nome final", "field": "final", "align": "left"},
        {"name": "num", "label": "Empenho", "field": "num"},
        {"name": "parc", "label": "Parcela", "field": "parc"},
        {"name": "tipo", "label": "Tipo", "field": "tipo"},
        {"name": "usr", "label": "Usuário", "field": "usr"},
        {"name": "dt", "label": "Data", "field": "dt"},
    ]
    tabela = ui.table(columns=colunas, rows=[], row_key="id").props("flat bordered dense").classes("w-full")

    def _refresh():
        linhas = []
        for r in listar_empenhos(status="ativo", limite=500):
            linhas.append({"id": r[0], "final": r[2], "num": r[3] or "—",
                           "parc": r[4] or "—", "tipo": r[8] if len(r) > 8 else "—",
                           "usr": r[5] or "—", "dt": (r[6] or "")[:16]})
        tabela.rows = linhas
        tabela.update()

    _refresh()


# ============================================================ ABA ORGANIZADOR (admin)
def _tela_organizador(usuario_logado, _btn_cls, _btn_style):
    def _organizar():
        ok, msg = organizar_pastas()
        ui.notify(msg, type="positive" if ok else "negative")

    def _gerar_matriz():
        ok, msg = gerar_matriz_organizador()
        ui.notify(msg, type="positive" if ok else "negative")

    def _validar_matriz():
        ok, faltando = validar_presenca_matriz()
        if ok:
            ui.notify("Todos os documentos da matriz estão presentes.", type="positive")
        else:
            ui.notify("Faltando na matriz: " + ", ".join(faltando[:10]), type="warning")

    with ui.row().classes("w-full gap-3 flex-wrap"):
        ui.button("Organizar caixas", icon="inventory_2", on_click=_organizar) \
            .props("unelevated").classes(_btn_cls()).style(_btn_style())
        ui.button("Gerar capas/matriz", icon="description", on_click=_gerar_matriz) \
            .props("outline").classes(_btn_cls()).style(_btn_style())
        ui.button("Validar matriz", icon="rule", on_click=_validar_matriz) \
            .props("outline").classes(_btn_cls()).style(_btn_style())

    with ui.expansion("Inventário — caixas e subpastas", icon="folder_open").classes("w-full mt-2"):
        inv_wrap = ui.column().classes("w-full")

        def _listar_inv():
            inv_wrap.clear()
            import os as _os
            if not _os.path.isdir(PASTA_ORGANIZADOR):
                with inv_wrap:
                    ui.label("Nada organizado ainda.").classes("text-caption text-grey-5")
                return
            with inv_wrap:
                for caixa in sorted(_os.listdir(PASTA_ORGANIZADOR)):
                    dc = _os.path.join(PASTA_ORGANIZADOR, caixa)
                    if not _os.path.isdir(dc) or not caixa.startswith("caixa"):
                        continue
                    with ui.expansion(f"📦 {caixa}", icon=None).classes("w-full"):
                        with ui.column().classes("w-full pl-4"):
                            for sub in sorted(_os.listdir(dc)):
                                ds = _os.path.join(dc, sub)
                                if not _os.path.isdir(ds):
                                    continue
                                docs = [f for f in sorted(_os.listdir(ds)) if f.lower().endswith(".pdf")]
                                ui.label(f"• {sub}: {len(docs)} doc(s)").classes("text-caption")

        _listar_inv()

    # ===== Ferramentas de PDF (corte/mesclar/reduzir) =====
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


# ============================================================ ABA SOLICITAÇÃO
def _tela_solicitacao(usuario_logado, eh_admin, _btn_cls, _btn_style):
    lista = ui.column().classes("w-full")

    def _recarregar():
        lista.clear()
        itens = listar_solicitacoes_acao_pendente()
        lotes, avulsas = agrupar_solicitacoes_em_lote(itens)
        with lista:
            if not itens:
                ui.label("Nenhuma solicitação pendente de envio.").classes("text-caption text-grey-5")

            def _card(grupo, titulo):
                primeiro = grupo[0]
                status = primeiro.get("status", "pendente")
                nome_dest = primeiro.get("solicitante_nome", "")
                email_dest = primeiro.get("solicitante_email", "")
                with ui.card().classes("w-full p-3 mt-1"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"📄 {titulo}").classes("font-bold flex-1")
                        ui.badge(status.upper(), color="orange" if status == "zip_gerado" else "blue")
                    ui.label(f"Solicitante: {nome_dest} <{email_dest}>").classes("text-caption")
                    ui.separator().classes("my-1")
                    for it in grupo:
                        existe = os.path.exists(it.get("arquivo_caminho") or "")
                        ui.label(f"• {it.get('nome_arquivo')}" + ("" if existe else "  ⚠️ não encontrado")) \
                            .classes("text-sm")
                    if status == "zip_gerado":
                        ui.label(f"📂 ZIP: {primeiro.get('caminho_zip')}").classes("text-caption bg-yellow-50 p-2 rounded")
                    with ui.row().classes("w-full mt-2 gap-2"):
                        if eh_admin:
                            if status == "pendente":
                                ui.button("Enviar por e-mail", icon="mail",
                                          on_click=lambda g=grupo: _envia_email(g)).props("unelevated") \
                                    .classes(_btn_cls()).style(_btn_style())
                                ui.button("Gerar ZIP", icon="folder_zip",
                                          on_click=lambda g=grupo: _gera_zip(g)).props("oe") \
                                    .classes(_btn_cls()).style(_btn_style())
                            elif status == "zip_gerado":
                                ui.button("Confirmar envio manual", icon="check_circle",
                                          on_click=lambda g=grupo: _confirma(g)).props("unelevated") \
                                    .classes(_btn_cls()).style(_btn_style())
                                ui.button("Cancelar ZIP", icon="undo",
                                          on_click=lambda g=grupo: _volta(g)).props("flat orange")
                            if status in ("pendente", "zip_gerado"):
                                ui.button("Recusar", icon="block",
                                          on_click=lambda g=grupo: _recusa(g)).props("flat negative")
                        else:
                            ui.label("Aguardando ação do administrador.").classes("text-caption text-grey-5")

            for lote_id, grupo in lotes.items():
                _card(grupo, f"Lote de {len(grupo)} arquivo(s) — {grupo[0].get('solicitante_nome')}")
            for s in avulsas:
                _card([s], s.get("nome_arquivo"))

    def _envia_email(grupo):
        ok, msg = enviar_solicitacao_por_email(grupo)
        if ok:
            for s in grupo:
                marcar_solicitacao_enviada(s["id"], usuario_logado, metodo="email")
            ui.notify("E-mail enviado!", type="positive")
        else:
            ui.notify(f"Falha: {msg}", type="negative")
        _recarregar()

    def _gera_zip(grupo):
        ok, res = gerar_zip_solicitacoes(grupo)
        if ok:
            ids = [s["id"] for s in grupo]
            marcar_solicitacoes_zip_gerado(ids, res, usuario_logado)
            ui.notify(f"ZIP gerado: {os.path.basename(res)}", type="positive")
            ui.download(res, os.path.basename(res))
        else:
            ui.notify(f"Erro ZIP: {res}", type="negative")
        _recarregar()

    def _confirma(grupo):
        for s in grupo:
            marcar_solicitacao_enviada(s["id"], usuario_logado, metodo="zip_manual")
        ui.notify("Envio manual confirmado!", type="positive")
        _recarregar()

    def _volta(grupo):
        for s in grupo:
            marcar_solicitacao_pendente(s["id"])
        ui.notify("ZIP cancelado, voltou a pendente", type="warning")
        _recarregar()

    def _recusa(grupo):
        with ui.dialog() as dlg, ui.card().classes("w-[400px]"):
            ui.label("Recusar solicitação").classes("text-h6")
            motivo = ui.input("Motivo (opcional)").props("outlined dense").classes("w-full")

            def conf():
                for s in grupo:
                    marcar_solicitacao_recusada(s["id"], motivo.value or "", usuario_logado)
                ui.notify("Solicitação recusada", type="warning")
                dlg.close()
                _recarregar()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Recusar", on_click=conf).props("unelevated negative")
        dlg.open()

    with ui.row().classes("w-full gap-2"):
        ui.button("Atualizar", icon="refresh", on_click=_recarregar).props("outline")

    with ui.expansion("📜 Histórico completo", icon="history").classes("w-full mt-4"):
        hist_wrap = ui.column().classes("w-full")

        def _hist():
            hist_wrap.clear()
            with hist_wrap:
                for s in listar_solicitacoes():
                    ui.label(
                        f"[{s.get('timestamp_solicitacao','')[:16]}] {s.get('nome_arquivo')} — "
                        f"{s.get('solicitante_nome') or s.get('solicitante_email')} → {s.get('status')} "
                        f"({s.get('metodo_envio') or '—'})").classes("text-caption")

        _hist()

    _recarregar()


# ============================================================ ABA CONFIG (admin)
def _tela_config(usuario_logado, eh_admin, t_cor_botao, t_cor_txt_botao, t_cor_fundo,
                 t_cor_titulo, t_tamanho, texto_header, _btn_cls, _btn_style):
    from mod_intranet.conexao_bd import get_config, set_config
    from mod_renomear_empenho.manipulador_bd import _PASTA_MONITORADA_PADRAO

    with ui.expansion("Administração — configurações dos Empenhos", icon="settings"
                      ).classes("w-full mt-4"):
        with ui.expansion("Pastas monitoradas (inclui rede/UNC)", icon="folder_open").classes("w-full"):
            ui.label("Uma pasta por linha. Caminhos locais ou de rede/UNC "
                     "(ex.: \\\\servidor\\empenhos ou E:\\scan). Cada linha é monitorada "
                     "na raiz (não recursivo), permitindo vários computadores/scaners.") \
                .classes("text-caption text-grey-6")
            inp_pastas = ui.textarea(
                "Pastas monitoradas (uma por linha)",
                value="\n".join(pastas_monitoradas())).props("outlined dense").classes("w-full")

            def salvar_pastas():
                linhas = [l.strip() for l in (inp_pastas.value or "").splitlines() if l.strip()]
                salvar_pastas_monitoradas(linhas)
                ui.notify("Pastas monitoradas salvas (valem sem reiniciar)", type="positive")
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Salvar pastas", icon="save", on_click=salvar_pastas) \
                    .props("unelevated").classes(_btn_cls()).style(_btn_style())

        ui.separator().classes("my-3")
        ui.label("Aparência — temas dos botões desta tela").classes("text-subtitle2 text-grey-7")
        inp_cor_botao = ui.color_input(label="Cor dos botões", value=t_cor_botao)
        inp_cor_txt = ui.color_input(label="Cor do texto dos botões", value=t_cor_txt_botao)
        inp_cor_fundo = ui.color_input(label="Cor de fundo da página (vazio = herda)", value=t_cor_fundo)
        inp_cor_titulo = ui.color_input(label="Cor dos títulos", value=t_cor_titulo)
        sel_tamanho = ui.select(
            {0: "Pequeno", 1: "Médio", 2: "Grande"},
            label="Tamanho dos botões",
            value={"small": 0, "medium": 1, "large": 2}.get(t_tamanho, 1),
        ).props("outlined dense")

        ui.separator().classes("my-3")
        ui.label("Configurações específicas").classes("text-subtitle2 text-grey-7")
        inp_texto = ui.input("Texto do cabeçalho", value=texto_header).props("outlined dense").classes("w-full")
        inp_intervalo = ui.input("Intervalo do monitor automático (segundos — recomendado 60)",
                                 value=str(_rotinas.intervalo_monitor_empenho())) \
            .props("outlined dense").classes("w-full") \
            .tooltip("Varredura automática das pastas monitoradas (RF-40). Aplicado sem reiniciar.")

        sw_autorizar = ui.switch(
            "Autorizar download/ZIP/e-mail para usuários comuns",
            value=get_config("renomear_autorizar_download", "0") == "1") \
            .props("dense") \
            .tooltip("Quando ativo, usuários comuns podem baixar/enviar os empenhos (RF-39).")

        _tamanhos = {0: "small", 1: "medium", 2: "large"}

        def salvar():
            try:
                set_config("empenhos_cor_botao", inp_cor_botao.value or "")
                set_config("empenhos_cor_texto_botao", inp_cor_txt.value or "")
                set_config("empenhos_cor_fundo", inp_cor_fundo.value or "")
                set_config("empenhos_cor_titulo", inp_cor_titulo.value or "")
                set_config("empenhos_btn_tamanho", _tamanhos[sel_tamanho.value])
                set_config("empenhos_texto_header", (inp_texto.value or "").strip())
                set_config("renomear_autorizar_download", "1" if sw_autorizar.value else "0")
                try:
                    iv = max(1, int((inp_intervalo.value or "60").strip() or 60))
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

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Salvar", icon="save", on_click=salvar).props("unelevated") \
                .classes(_btn_cls()).style(_btn_style())

    # ================= Template de nome final =================
    with ui.expansion("Nome final do arquivo (template configurável)",
                      icon="drive_file_rename_outline").classes("w-full mt-2"):
        ui.label("Formato do nome atribuído aos PDFs renomeados. Variáveis: "
                 "{contador}, {empenho}, {empenho_cru}, {parcela}, {ficha}, {ano}. "
                 "Suporta formatação de largura, ex.: {contador:04d}, {parcela:03d}.") \
            .classes("text-caption text-grey-6")
        ui.label("Tipos especiais (EC/EE/EG/AE) usam nome próprio: EC_0024.pdf, "
                 "EE_9570.pdf, EG_0089.pdf.").classes("text-caption text-grey-6")
        inp_template = ui.input(
            "Template do nome final", value=template_nome_atual()).props("outlined dense").classes("w-full") \
            .tooltip(f"Padrão: {NOME_FINAL_PADRAO}")

        def _preview_template():
            try:
                preview_nome = montar_nome_final(
                    inp_template.value or NOME_FINAL_PADRAO, 7,
                    {"empenho": "0000345", "ficha": "0000331", "ano": "2026"})
            except Exception as e:
                preview_nome = f"(erro: {e})"
            lbl_preview.set_text(f"Nome de exemplo: {preview_nome}")

        lbl_preview = ui.label("")
        inp_template.on("update:model-value", lambda e: _preview_template())
        _preview_template()

        def salvar_template():
            t = (inp_template.value or "").strip()
            if not t:
                set_config("empenhos_template_nome", "")
                ui.notify("Template vazio — usando o padrão do módulo", type="info")
            else:
                try:
                    montar_nome_final(t, 1, {"empenho": "1", "ficha": "1", "ano": "2026"})
                except Exception as e:
                    ui.notify(f"Template inválido: {e}", type="negative")
                    return
                set_config("empenhos_template_nome", t)
            try:
                audit_log(usuario_logado, "renomear-empenho", "configuracao",
                          "template de nome atualizado")
            except Exception:
                pass
            ui.notify("Template de nome salvo (vale sem reiniciar)", type="positive")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            def restaurar_template():
                set_config("empenhos_template_nome", "")
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
            ui.button("Usar padrão", on_click=restaurar_template).props("flat")
            ui.button("Salvar template", icon="save", on_click=salvar_template) \
                .props("unelevated").classes(_btn_cls()).style(_btn_style())

    # ================= Campos de busca configuráveis =================
    with ui.expansion("Campos de busca (regex de identificação)",
                      icon="manage_search").classes("w-full mt-2"):
        ui.label("Regex usadas para identificar cada campo. O 1º grupo é o valor; "
                 "o 2º, se houver, é o ano. Edite sem reiniciar.").classes("text-caption text-grey-6")
        lista_campos = ui.column().classes("w-full mt-1")

        def _refresh_campos():
            lista_campos.clear()
            if not listar_campos_busca():
                with lista_campos:
                    ui.label("Sem campos cadastrados — clique em 'Restaurar padrão'.") \
                        .classes("text-caption text-grey-5")
                return
            with lista_campos:
                for cid, campo, rotulo, padrao, ativo in listar_campos_busca():
                    with ui.row().classes("w-full items-center gap-2 py-1"):
                        ui.icon("bolt" if ativo else "block").classes(
                            "text-green-7" if ativo else "text-grey-5")
                        ui.label(f"{rotulo}").classes("font-medium w-28")
                        ui.code(padrao).style("flex:1; overflow-x:auto")
                        if not ativo:
                            ui.badge("inativa", color="grey")
                        ui.button(icon="delete", on_click=lambda c=cid: _del_campo(c)) \
                            .props("flat round dense size=sm").tooltip("Excluir campo")

        def _del_campo(cid):
            excluir_campo_busca(cid)
            _refresh_campos()

        _refresh_campos()

        with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
            f_campo = ui.input("Campo (chave)").props("outlined dense").classes("w-36")
            f_rotulo = ui.input("Rótulo").props("outlined dense").classes("w-40")
            f_padrao = ui.input("Regex (o 1º grupo é o valor)", placeholder=r"...(\d+)...") \
                .props("outlined dense").classes("grow min-w-[240px]")
            f_ativo = ui.switch("Ativa", value=True).props("dense")

            def salvar_campo():
                ok, msg = salvar_campo_busca(
                    f_campo.value or "", f_rotulo.value or "",
                    f_padrao.value or "", bool(f_ativo.value))
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    f_campo.set_value(None); f_rotulo.set_value(None)
                    f_padrao.set_value(None); _refresh_campos()

            ui.button("Salvar campo", icon="save", on_click=salvar_campo) \
                .props("unelevated").classes(_btn_cls()).style(_btn_style())

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            def restaurar_campos():
                restaurar_campos_busca_padrao()
                _refresh_campos()
                ui.notify("Campos de busca restaurados ao padrão", type="positive")
            ui.button("Restaurar padrão", icon="restore", on_click=restaurar_campos) \
                .props("outline").classes(_btn_cls())

    # ================= Auditoria e quarentena (admin) =================
    with ui.expansion("Auditoria dos arquivos escaneados / renomeados",
                      icon="manage_search").classes("w-full mt-2"):
        colunas_aud = [
            {"name": "nome_orig", "label": "Origem", "field": "nome_orig", "align": "left"},
            {"name": "nome_final", "label": "Nome final", "field": "nome_final", "align": "left"},
            {"name": "num", "label": "Empenho", "field": "num", "align": "left"},
            {"name": "parc", "label": "Parc", "field": "parc"},
            {"name": "ficha", "label": "Ficha", "field": "ficha"},
            {"name": "ano", "label": "Ano", "field": "ano"},
            {"name": "status", "label": "Status", "field": "status"},
            {"name": "usr", "label": "Usuário", "field": "usr"},
            {"name": "dt", "label": "Renomeado em", "field": "dt"},
        ]
        filtro_status = ui.select(
            {"": "Todos", "renomeado": "Renomeado", "detectado": "Detectado",
             "erro": "Erro", "removido": "Removido"},
            label="Status", value="").props("outlined dense").classes("w-56")
        tabela_aud = ui.table(columns=colunas_aud, rows=[], row_key="id").props("flat bordered dense").classes("w-full")

        def _refresh_aud():
            sel = filtro_status.value or None
            tabela_aud.rows = [
                {"id": r[0], "nome_orig": r[1] or "—", "nome_final": r[2] or "—",
                 "num": r[3] or "—", "parc": r[4] or "—", "ficha": r[5] or "—",
                 "ano": r[6] or "—", "status": r[7] or "—", "usr": (r[8] or "—")[:12],
                 "dt": (r[10] or "")[:16]}
                for r in listar_arquivos_auditoria(status=sel)
            ]
            tabela_aud.update()

        filtro_status.on("update:model-value", lambda e: _refresh_aud())
        _refresh_aud()

    with ui.expansion("Quarentena", icon="block").classes("w-full mt-2"):
        colunas_q = [
            {"name": "arquivo", "label": "Arquivo", "field": "arquivo", "align": "left"},
            {"name": "motivo", "label": "Motivo", "field": "motivo", "align": "left"},
            {"name": "data", "label": "Recebido em", "field": "data"},
            {"name": "qid", "label": "", "field": "qid"},
        ]
        tabela_q = ui.table(columns=colunas_q, rows=[], row_key="qid").props("flat bordered dense").classes("w-full")

        def _refresh_q():
            tabela_q.rows = [
                {"qid": r[0], "arquivo": r[1], "motivo": (r[2] or "")[:80], "data": (r[3] or "")[:16]}
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
                        ui.notify(("Sucesso: " + msg) if ok else ("Falha: " + msg),
                                  type="positive" if ok else "warning")
                        dlg.close(); _refresh_q()
                    except Exception:
                        _log.exception(f"erro ao reprocessar quarentena qid={linha['qid']}")

                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancelar", on_click=dlg.close).props("flat")
                    ui.button("Reprocessar", on_click=tentar).props("unelevated").classes(_btn_cls()).style(_btn_style())
            dlg.open()

        tabela_q.on("row-click", on_q_click)
        _refresh_q()

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
                            ui.badge(f"→ {destino}", color="purple").props("outline")
                        if not ativo:
                            ui.badge("inativa", color="grey")

                    def _toggle(r=rid, a=ativo):
                        ok, msg = alternar_regra(r, not a)
                        ui.notify(msg, type="positive" if ok else "negative")
                        _refresh_regras()

                    ui.button("Inativar" if ativo else "Ativar", on_click=_toggle).props("flat dense size=sm")

        _refresh_regras()

        with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
            n_nome = ui.input("Nome da regra").props("outlined dense").classes("w-44")
            n_padrao = ui.input("Padrão (regex)", placeholder=r"empenho\s*n[ºo]?\s*(\d+)") \
                .props("outlined dense").classes("grow min-w-[240px]")
            n_destino = ui.input("Campo FTS destino (opcional)") \
                .props("outlined dense").classes("w-56")

            def salvar():
                if not n_nome.value or not n_padrao.value:
                    ui.notify("Informe nome e padrão", type="warning"); return
                ok, msg = salvar_regra(n_nome.value.strip(), n_padrao.value.strip(),
                                       campo_destino=(n_destino.value or "").strip() or None)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.set_value(None); n_padrao.set_value(None); n_destino.set_value(None)
                    _refresh_regras()

            ui.button("Salvar regra", icon="save", on_click=salvar) \
                .props("unelevated").classes(_btn_cls()).style(_btn_style())

    campo_modulo(usuario_logado, "empenhos")
