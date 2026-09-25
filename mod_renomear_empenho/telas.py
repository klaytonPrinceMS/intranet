"""Empenho renaming module screen — 6 tabs: Browse, Queue, Search,
Organizer (admin), Request and Settings (admin).

Tela do módulo Renomear Empenhos — 6 abas: Navegar, Fila, Pesquisar,
Organizador (admin), Solicitação e Configurações (admin)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui, run

from mod_intranet import observabilidade
_log = observabilidade.get_logger("renomear_empenho")

# Visual switcher PIC (Quasar nativo suave) vs Bootstrap 5.3.8 local
from mod_renomear_empenho import visual as _visual

from mod_renomear_empenho.bd_manipulador import (
    rodar_monitor, listar_empenhos, pesquisar, listar_quarentena,
    reprocesse_quarentena, reprocessar_fila, promover_quarentena, separar_documentos_quarentena, salvar_regra, listar_regras, organizar_pastas,
    pasta_monitorada, pastas_monitoradas, salvar_pastas_monitoradas,
    alternar_regra, listar_arquivos_auditoria, listar_eventos_arquivo,
    listar_campos_busca, salvar_campo_busca, excluir_campo_busca,
    restaurar_campos_busca_padrao,     template_nome_atual, montar_nome_final, montar_nome_tipo_especial,
    NOME_FINAL_PADRAO, extrair_dados_empenho, extrair_texto_pdf,
    detectar_tipo_especial, extrair_dados_tipo_especial,
    ferramenta_cortar, ferramenta_juntar, ferramenta_reduzir, ferramenta_fontes,
    PASTA_TEMP_FERR, gerar_matriz_organizador, validar_presenca_matriz,
    PASTA_ORGANIZADOR,
    listar_navegacao, listar_pendentes, status_arquivo, renomear_manual,
    arquivo_ja_processado, pesquisar_levantamento,
    raizes_navegacao, criar_solicitacao, listar_solicitacoes_acao_pendente,
    listar_solicitacoes, obter_solicitacao, marcar_solicitacao_enviada,
    marcar_solicitacoes_zip_gerado, marcar_solicitacao_pendente,
    marcar_solicitacao_recusada, gerar_zip_solicitacoes,
    enviar_solicitacao_por_email, agrupar_solicitacoes_em_lote,
)
from mod_intranet import rotinas as _rotinas
from mod_intranet import email_util
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.aba_modulo import cabecalho, menu_modulo
from mod_intranet.ui_comum import botao, botao_icone, campo_cor, campo_selecao

from mod_intranet.autenticacao import eh_admin_do_modulo
import zipfile, shutil
from uuid import uuid4


def _tema_s(get_config, chave, default):
    """Reads a theme key from tb_config, falling back to the default (fail-soft)."""
    try:
        return (get_config(chave, default) or "").strip() or default
    except Exception:
        return default


def mostrar_tela(usuario_logado: str, perfil: str):
    """Renders the Empenhos screen with its 6 internal tabs.

    Monta a tela: tema/aparência pelas chaves `empenhos_*` (herdando o tema
    do sistema quando vazias), cabeçalho padrão (`cabecalho` com
    `chave_modulo="empenhos"`) e as abas Navegar, Fila Renomeação,
    Pesquisar, Organizador (admin), Solicitação e Configurações (admin).
    Admin = `administrador_geral` ou administrador do módulo `empenhos`.

    Modelos visuais (tb_config `empenhos_modelo_visual`): uma tela por CSS
    em `assets/css/frameworks` (bootstrap, bulma, daisyui, pico, picnic) +
    `pic` nativo e `hibrido` (padrão — mistura PIC+Bootstrap)."""
    try:
        from mod_intranet.bd_conexao import get_config, set_config
        # --- modelo visual comutável (híbrido default, uma tela por CSS) ---
        _modelo = _visual.ler_modelo(get_config)
        _bootstrap = _modelo == "bootstrap"
        _hibrido = _modelo == "hibrido"
        _framework = _modelo if _modelo in _visual.FRAMEWORKS else None
        if _hibrido:
            _visual.injetar_hibrido()
            try:
                ui.add_head_html('<div class="empenho-hibrido" style="display:none"></div>')
            except Exception:
                pass
        elif _framework:
            _visual.aplicar_framework(_framework)
            try:
                ui.add_head_html(f'<div class="empenho-framework empenho-{_framework}" style="display:none"></div>')
            except Exception:
                pass
        elif _bootstrap:
            _visual.aplicar_framework(True)
            _visual.injetar_bootstrap_overrides()
            try:
                ui.add_head_html('<div class="empenho-bootstrap" style="display:none"></div>')
            except Exception:
                pass
        else:
            _visual.injetar_pic_suave()

        # ================= TEMA (Aparência, prefixo empenhos_) =================
        def _tema(chave, default):
            try:
                return (get_config(f"empenhos_{chave}", default) or "").strip() or default
            except Exception:
                return default

        t_cor_botao = _tema("cor_botao", "#000000")
        ui.colors(primary=t_cor_botao)
        t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
        t_cor_fundo = _tema("cor_fundo", "")
        t_cor_titulo = _tema("cor_titulo", "#212121")
        t_tamanho = _tema("btn_tamanho", "medium")

        def _btn_cls():
            try:
                if t_tamanho == "small":
                    return "min-w-[140px] text-sm"
                if t_tamanho == "large":
                    return "min-w-[220px] text-lg"
                return "min-w-[180px]"
            except Exception as e:
                try:
                    _log.exception(f"_btn_cls falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _btn_cls: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _btn_cls", type="negative")
                    except Exception:
                        pass
                return None

        def _btn_style():
            try:
                st = ""
                if t_cor_botao:
                    st += f"background-color:{t_cor_botao};"
                if t_cor_txt_botao:
                    st += f"color:{t_cor_txt_botao};"
                return st
            except Exception as e:
                try:
                    _log.exception(f"_btn_style falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _btn_style: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _btn_style", type="negative")
                    except Exception:
                        pass
                return None

        eh_admin = perfil == "administrador_geral" or eh_admin_do_modulo(usuario_logado, "empenhos") \
            or (perfil and "admin" in perfil)
        autorizado = get_config("empenhos_autorizar_download", "0") == "1"

        pastas_msg = ", ".join(pastas_monitoradas()) or pasta_monitorada()
        texto_header = _tema_s(get_config, "empenhos_texto_header",
                               f"Monitora as pastas <code>{pastas_msg}</code> (local ou rede/UNC), "
                               "extrai o nº do empenho por regex (inclui tipos EC/EE/EG/AE), renomeia "
                               "e organiza em caixas.")

        cabecalho("Renomeador de Empenhos", texto_header, chave_modulo="empenhos",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        # Permissões: comum vê só Navegar (com busca integrada, pode selecionar e solicitar);
        # Fila, Organizador e Solicitação são exclusivas do admin. Pesquisar removido — busca foi para o Navegar.
        # Padrão de menu segue Solicitação de Impressão: row bg-white rounded-lg shadow-sm com tabs dense inline-label.
        if eh_admin:
            _abas = [
                ("navegar", "Navegar", "folder_open"),
                ("fila", "Fila Renomeação", "move_to_inbox"),
                ("organizador", "Organizador", "inventory_2"),
                ("solicitacao", "Solicitação", "mail"),
            ]
        else:
            _abas = [
                ("navegar", "Navegar", "folder_open"),
            ]
        # Barra de abas no padrão do módulo (aba_modulo.menu_modulo): os ícones
        # já vêm dentro de `_abas`, então o dict de ícones separado era redundante.
        with ui.row().classes("w-full items-center justify-between flex-nowrap bg-white rounded-lg shadow-sm px-3 py-1").style("gap: 1rem; min-width: 0"):
            # TEMPORARIO-25-ARQUIVOS-REMOVER-EM-PRODUCAO: botão totalmente à direita do menu_mod;
            # cada clique cria 25 arquivos na pasta doc do módulo via fábrica do sistema.
            tabs_el = menu_modulo(_abas)
            async def _gerar_25_temp():
                from mod_intranet.tema_modulo import notificar as _notificar
                try:
                    def _criar():
                        try:
                            import sys as _sys, os as _os
                            _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'assets', 'test'))
                            from fabrica_documentos import criar_lote_principal
                            from mod_renomear_empenho.bd_manipulador import pastas_monitoradas as _pastas
                            _dest = (_pastas() or [None])[0]
                            if not _dest:
                                from mod_renomear_empenho.bd_manipulador import _PASTA_MONITORADA_PADRAO as _pad
                                _dest = _pad
                            return criar_lote_principal(_dest, quantidade=25)
                        except Exception as e:
                            try:
                                _log.exception(f"_criar falhou: {e}")
                            except Exception:
                                pass
                            try:
                                notificar(f"Erro em _criar: {e}", tipo="error")
                            except Exception:
                                try:
                                    ui.notify(f"Erro em _criar", type="negative")
                                except Exception:
                                    pass
                            return None
                    criados = await run.io_bound(_criar)
                    audit_log(usuario_logado, "empenhos", "gerar_massa_temp", f"{len(criados)} arquivos TEMP criados")
                    _notificar(f"{len(criados)} arquivos criados na pasta doc.", type="positive")
                except Exception as e:
                    _log().exception(f"massa TEMP: falha ao criar 25 arquivos: {e}")
                    try:
                        from mod_intranet.tema_modulo import notificar as _n2
                        _n2(f"Falha ao criar arquivos: {e}", type="negative")
                    except Exception:
                        pass
            _btn_25 = botao("Gerar 25 (TEMP)", icone="science", on_click=_gerar_25_temp,
                  variante="secundario", chave_modulo="empenhos")
            if _btn_25 is not None:
                _btn_25.props('data-testid=empenhos-gerar-25-temp')
                _btn_25.classes("shrink-0 ml-auto")
        with ui.tab_panels(tabs_el, value="navegar").classes("w-full bg-transparent"):
            with ui.tab_panel("navegar"):
                _tela_navegar(usuario_logado, eh_admin, autorizado, _btn_cls, _btn_style)
            if eh_admin:
                with ui.tab_panel("fila"):
                    _tela_fila(usuario_logado, eh_admin, _btn_cls, _btn_style)
                with ui.tab_panel("organizador"):
                    _tela_organizador(usuario_logado, _btn_cls, _btn_style)
                with ui.tab_panel("solicitacao"):
                    _tela_solicitacao(usuario_logado, eh_admin, _btn_cls, _btn_style)
    except Exception as e:
        try:
            _log.exception(f"mostrar_tela falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em mostrar_tela: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em mostrar_tela", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA NAVEGAR
def _tela_navegar(usuario_logado, eh_admin, autorizado, _btn_cls, _btn_style):
    """Browse tab: protected navigation of monitored folders (PDFs only).

    Navegação com breadcrumb e anti-travessia (só raízes protegidas), status
    por arquivo (processado/pendente). Todo PDF exibe os três ícones:
    baixar, revisar/renomear (editar) e solicitar envio — em qualquer pasta
    monitorada. O download respeita a permissão (`empenhos_autorizar_download`
    ou admin); bloqueado apenas avisa. Checkbox por arquivo monta o lote
    para solicitar e/ou baixar (ZIP quando múltiplo). Campo de pesquisa
    filtra os documentos da pasta atual por nome (a pesquisa global de
    conteúdo continua na aba Pesquisar).

    Dois modelos: PIC (Quasar nativo suave) ativa sombras/bordas arredondadas
    e badges Quasar; Bootstrap (flag) usa card shadow, badge bg-* e input-group
    quando empenhos_modelo_visual=bootstrap."""
    try:
        from mod_intranet.bd_conexao import get_config
        pasta_atual = {}
        selecionados = {}
        filtro_nome = {"texto": ""}
        filtro_pendente = {"ativo": False}
        pode_baixar = bool(eh_admin or autorizado)
        # modelo visual capturado por closure (híbrido default — uma tela por CSS)
        def _eh_bs():
            try:
                return _visual.eh_bootstrap(get_config)
            except Exception:
                return _bootstrap
        def _eh_hibrido():
            try:
                return _visual.eh_hibrido(get_config)
            except Exception:
                return _hibrido
        def _modelo_atual():
            try:
                return _visual.ler_modelo(get_config)
            except Exception:
                return _modelo

        def _baixar(caminho):
            try:
                if not (eh_admin or autorizado):
                    ui.notify("Download bloqueado pelo administrador — use Solicitar envio.",
                              type="warning")
                    return
                if os.path.exists(caminho):
                    ui.download(caminho, os.path.basename(caminho))
            except Exception as e:
                try:
                    _log.exception(f"_baixar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _baixar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _baixar", type="negative")
                    except Exception:
                        pass
                return None

        def _revisar_renomear(caminho):
            if not eh_admin:
                ui.notify("Ação restrita ao administrador do módulo.", type="warning")
                return
            nome = os.path.basename(caminho)
            # Extrai valores atuais (podem vir parciais quando o OCR falha);
            # todos os campos ficam editáveis, inclusive os reconhecidos.
            try:
                texto = extrair_texto_pdf(caminho) or ""
            except Exception:
                texto = ""
            try:
                tipo_detectado = detectar_tipo_especial(texto)
            except Exception:
                tipo_detectado = None
            dados_doc, dados_esp = {}, {}
            try:
                dados_doc = extrair_dados_empenho(texto) or {}
            except Exception:
                dados_doc = {}
            if tipo_detectado:
                try:
                    dados_esp = extrair_dados_tipo_especial(texto, tipo_detectado) or {}
                except Exception:
                    dados_esp = {}
            eh_especial = bool(tipo_detectado)
            with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
                ui.label(f"Revisar / renomear — {nome}").classes("text-h6")
                ui.label("Confira os campos extraídos do conteúdo (DOC, EC, EE, EG, AE). "
                         "Campos não identificados ficam vazios para preenchimento manual — "
                         "a renomeação usa os valores desta tela.").classes("text-caption text-grey-6")
                sel_tipo = ui.select(
                    {"": "DOC (empenho de parcela)", "EC": "EC — Complementação",
                     "EE": "EE — Estimativo", "EG": "EG — Global", "AE": "AE — Anulação"},
                    label="Tipo de documento",
                    value=tipo_detectado or "").props("outlined dense").classes("w-full") \
                    .props("data-testid=empenhos-revisar-tipo")
                inp_ficha = ui.input("Ficha", value=str(dados_doc.get("ficha") or "")) \
                    .props("outlined dense").classes("w-full") \
                    .props("data-testid=empenhos-revisar-ficha")
                inp_empenho = ui.input(
                    "Nº empenho / Nº documento especial",
                    value=str(dados_esp.get("numero") if eh_especial and dados_esp.get("numero")
                              else (dados_doc.get("empenho") or ""))) \
                    .props("outlined dense").classes("w-full") \
                    .props("data-testid=empenhos-revisar-empenho")
                inp_parcela = ui.input("Parcela (só DOC)",
                                       value=str(dados_doc.get("parcela") or "")) \
                    .props("outlined dense").classes("w-full") \
                    .props("data-testid=empenhos-revisar-parcela")
                inp_ano = ui.input(
                    "Ano", value=str(dados_esp.get("ano") if eh_especial and dados_esp.get("ano")
                                     else (dados_doc.get("ano") or ""))) \
                    .props("outlined dense").classes("w-full") \
                    .props("data-testid=empenhos-revisar-ano")
                if not (dados_doc.get("empenho") or dados_esp.get("numero")):
                    ui.label("Nº não identificado automaticamente — informe manualmente.").classes("text-caption text-orange-8")
                if not dados_doc.get("parcela") and not (sel_tipo.value or ""):
                    ui.label("Parcela não identificada — informe manualmente (padrão 1).").classes("text-caption text-orange-8")
                res = ui.column().classes("w-full mt-1")

                def _confirmar():
                    try:
                        tipo = (sel_tipo.value or "").strip() or None
                        ficha = (inp_ficha.value or "").strip() or None
                        ano = (inp_ano.value or "").strip() or None
                        num_txt = (inp_empenho.value or "").strip()
                        parc_txt = (inp_parcela.value or "").strip()
                        if tipo:
                            if not num_txt:
                                raise ValueError("Informe o nº do documento especial")
                            ok, msg = renomear_manual(usuario_logado, caminho,
                                                     novo_numero=num_txt,
                                                     tipo_especial=tipo)
                        else:
                            if not num_txt:
                                raise ValueError("Informe o nº do empenho")
                            ok, msg = renomear_manual(
                                usuario_logado, caminho, novo_numero=num_txt,
                                novo_parcela=parc_txt or None,
                                nova_ficha=ficha, novo_ano=ano)
                        if ok:
                            ui.notify(f"Renomeado → {msg}", type="positive")
                            dlg.close()
                            _carregar()
                        else:
                            with res:
                                ui.label(f"Não foi possível renomear: {msg}").classes("text-negative")
                    except ValueError as ve:
                        with res:
                            ui.label(str(ve)).classes("text-negative")
                    except Exception as e:
                        with res:
                            ui.label(f"Erro: {e}").classes("text-negative")

                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                    botao("Renomear (normalizar)", icone="auto_fix_high", on_click=_confirmar,
                          variante="solido", chave_modulo="empenhos")
            dlg.open()

        def _processar_auto(caminho):
            try:
                if not eh_admin:
                    ui.notify("Ação restrita ao administrador do módulo.", type="warning")
                    return
                ok, msg = renomear_manual(usuario_logado, caminho)
                ui.notify(f"Renomeado → {msg}" if ok else f"Falha: {msg}",
                          type="positive" if ok else "negative")
                if ok:
                    _carregar()
            except Exception as e:
                try:
                    _log.exception(f"_processar_auto falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _processar_auto: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _processar_auto", type="negative")
                    except Exception:
                        pass
                return None

        def _email_cadastrado():
            try:
                from mod_intranet.autenticacao import obter_email_usuario
                return obter_email_usuario(usuario_logado)
            except Exception:
                return ""

        def _solicitar(caminho):
            try:
                nome = os.path.basename(caminho)
                with ui.dialog() as dlg, ui.card().classes("w-[460px]"):
                    ui.label(f"Solicitar envio — {nome}").classes("text-h6")
                    email_padrao = _email_cadastrado()
                    inp_mail = ui.input("Seu e-mail", placeholder="usuario@dominio.com", value=email_padrao) \
                        .props("outlined dense clearable").classes("w-full").props("data-testid=empenhos-solicitar-email") \
                        .tooltip("Preenchido com seu e-mail cadastrado; edite se desejar outro")
                    if not email_padrao:
                        ui.label("Nenhum e-mail cadastrado — digite o destino.").classes("text-caption text-orange-7")
                    inp_msg = ui.textarea("Mensagem (opcional)").props("outlined dense").classes("w-full")

                    def _enviar():
                        try:
                            dest = (inp_mail.value or "").strip()
                            if "@" not in dest:
                                ui.notify("Informe um e-mail válido", type="negative")
                                return
                            criar_solicitacao(caminho, nome, usuario_logado, dest, inp_msg.value or "")
                            ui.notify("Solicitação registrada — aguardando o administrador.", type="positive")
                            dlg.close()
                        except Exception as e:
                            try:
                                _log.exception(f"_enviar falhou: {e}")
                            except Exception:
                                pass
                            try:
                                notificar(f"Erro em _enviar: {e}", tipo="error")
                            except Exception:
                                try:
                                    ui.notify(f"Erro em _enviar", type="negative")
                                except Exception:
                                    pass
                            return None

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                        botao("Solicitar", icone="send", on_click=_enviar,
                              variante="solido", chave_modulo="empenhos")
                dlg.open()
            except Exception as e:
                try:
                    _log.exception(f"_solicitar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _solicitar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _solicitar", type="negative")
                    except Exception:
                        pass
                return None

        def _alternar_selecao(marcado, caminho, nome):
            try:
                if marcado:
                    selecionados[caminho] = nome
                else:
                    selecionados.pop(caminho, None)
                _atualizar_lote()
            except Exception as e:
                try:
                    _log.exception(f"_alternar_selecao falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _alternar_selecao: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _alternar_selecao", type="negative")
                    except Exception:
                        pass
                return None

        def _atualizar_lote():
            try:
                lbl_lote.text = f"{len(selecionados)} selecionado(s)"
            except Exception:
                pass

        def _solicitar_lote():
            try:
                if not selecionados:
                    ui.notify("Selecione ao menos 1 arquivo (checkbox).", type="warning")
                    return
                with ui.dialog() as dlg, ui.card().classes("w-[460px]"):
                    ui.label(f"Solicitar envio em lote — {len(selecionados)} arquivo(s)").classes("text-h6")
                    email_padrao = _email_cadastrado()
                    inp_mail = ui.input("Seu e-mail", placeholder="usuario@dominio.com",
                                        value=email_padrao).props("outlined dense clearable").classes("w-full") \
                        .props("data-testid=empenhos-lote-email") \
                        .tooltip("Preenchido com seu e-mail cadastrado; edite se desejar outro")
                    if not email_padrao:
                        ui.label("Nenhum e-mail cadastrado — digite o destino.").classes("text-caption text-orange-7")
                    inp_msg = ui.textarea("Mensagem (opcional)").props("outlined dense").classes("w-full")

                    async def _enviar_lote():
                        # Anti-disconnect (§5.1): N solicitações × ~0,35 s (SQLite +
                        # auditoria) travavam o event-loop e derrubavam o websocket
                        # ("sistema desconectado"). Roda o I/O em run.io_bound.
                        if getattr(_enviar_lote, "ocupado", False):
                            ui.notify("Aguarde o lote em andamento…", type="warning")
                            return
                        dest = (inp_mail.value or "").strip()
                        if "@" not in dest:
                            ui.notify("Informe um e-mail válido", type="negative")
                            return
                        _enviar_lote.ocupado = True
                        btn_confirmar.disable()
                        with ui.row().classes("w-full items-center justify-center") \
                                .style("gap: 0.5rem") as linha_status:
                            ui.spinner(size="lg").props("aria-label=Registrando lote")
                            ui.label("Registrando solicitações…").classes("text-caption text-grey-7")

                        def _gravar():
                            try:
                                lote_id = uuid4().hex
                                feitas = 0
                                for cam, nom in list(selecionados.items()):
                                    try:
                                        criar_solicitacao(cam, nom, usuario_logado, dest,
                                                          inp_msg.value or "", lote_id=lote_id)
                                        feitas += 1
                                    except Exception:
                                        _log.exception("falha ao criar solicitação em lote")
                                return feitas
                            except Exception as e:
                                try:
                                    _log.exception(f"_gravar falhou: {e}")
                                except Exception:
                                    pass
                                try:
                                    notificar(f"Erro em _gravar: {e}", tipo="error")
                                except Exception:
                                    try:
                                        ui.notify(f"Erro em _gravar", type="negative")
                                    except Exception:
                                        pass
                                return None

                        try:
                            feitas = await run.io_bound(_gravar)
                        finally:
                            _enviar_lote.ocupado = False
                        try:
                            linha_status.clear()
                        except Exception:
                            pass
                        selecionados.clear()
                        ui.notify(f"{feitas} solicitação(ões) registrada(s) — aguardando o administrador.",
                                  type="positive")
                        dlg.close()
                        _carregar()

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                        btn_confirmar = botao("Solicitar lote", icone="send", on_click=_enviar_lote,
                               variante="solido", chave_modulo="empenhos") \
                            .props("data-testid=empenhos-lote-confirmar")
                dlg.open()
            except Exception as e:
                try:
                    _log.exception(f"_solicitar_lote falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _solicitar_lote: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _solicitar_lote", type="negative")
                    except Exception:
                        pass
                return None

        def _baixar_lote():
            try:
                if not selecionados:
                    ui.notify("Selecione ao menos 1 arquivo (checkbox).", type="warning")
                    return
                if not (eh_admin or autorizado):
                    ui.notify("Download bloqueado pelo administrador — use Solicitar envio.",
                              type="warning")
                    return
                existentes = [(c, n) for c, n in list(selecionados.items()) if os.path.exists(c)]
                if not existentes:
                    ui.notify("Nenhum arquivo selecionado existe mais.", type="negative")
                    return
                if len(existentes) == 1:
                    ui.download(existentes[0][0], os.path.basename(existentes[0][0]))
                    return
                itens = [{"arquivo_caminho": c, "nome_arquivo": n,
                          "solicitante_nome": usuario_logado} for c, n in existentes]
                ok, res = gerar_zip_solicitacoes(itens)
                if ok:
                    ui.download(res, os.path.basename(res))
                else:
                    ui.notify(f"Erro ZIP: {res}", type="negative")
            except Exception as e:
                try:
                    _log.exception(f"_baixar_lote falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _baixar_lote: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _baixar_lote", type="negative")
                    except Exception:
                        pass
                return None

        def _limpar_selecao():
            try:
                selecionados.clear()
                _carregar()
            except Exception as e:
                try:
                    _log.exception(f"_limpar_selecao falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _limpar_selecao: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _limpar_selecao", type="negative")
                    except Exception:
                        pass
                return None

        def _marcar_visiveis():
            try:
                for p in (pasta_atual.get("pdfs") or []):
                    selecionados[p["caminho"]] = p["nome"]
                _carregar()
            except Exception as e:
                try:
                    _log.exception(f"_marcar_visiveis falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _marcar_visiveis: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _marcar_visiveis", type="negative")
                    except Exception:
                        pass
                return None

        def _detalhes_linha(p):
            try:
                # Empenho/parcela/usuário/data da leitura do reconhecimento (levantamento)
                # ou do processamento (tb_empenhos) — já anexados por anotar_arquivos;
                # cai para o nome final e o mtime quando ausentes.
                nome = p.get("nome") or ""
                empenho = p.get("numero_empenho") or p.get("empenho") or "—"
                parcela = p.get("parcela") or "—"
                if isinstance(empenho, str) and empenho.isdigit():
                    empenho = empenho.lstrip("0") or "0"
                if isinstance(parcela, str) and parcela.isdigit():
                    parcela = parcela.lstrip("0") or "0"
                elif isinstance(parcela, int):
                    parcela = str(parcela)
                usuario = (p.get("usuario") or "").strip() if isinstance(p.get("usuario"), str) else (p.get("usuario") or "—")
                if not usuario:
                    usuario = "—"
                data = p.get("data") or p.get("dt") or "—"
                # parse doc_0001_345_001.pdf
                import re as _re
                m = _re.match(r"doc_\d+_(\d+)_(\d+)\.pdf$", nome, _re.I)
                if m:
                    if empenho == "—":
                        empenho = m.group(1).lstrip("0") or "0"
                    if parcela == "—":
                        parcela = m.group(2).lstrip("0") or "0"
                # fallback mtime
                if data == "—":
                    try:
                        import datetime as _dt
                        ts = os.path.getmtime(p.get("caminho") or "")
                        data = _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    except Exception:
                        data = "—"
                return empenho, parcela, usuario, data
            except Exception as e:
                try:
                    _log.exception(f"_detalhes_linha falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _detalhes_linha: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _detalhes_linha", type="negative")
                    except Exception:
                        pass
                return None

        def _card_pdf(p, sub=None, presente=1):
            try:
                # Linha estilo Excel — mesmas infos/botões do Navegar, visual do Pesquisar (border, hover)
                empenho, parcela, usuario, data = _detalhes_linha(p)
                _hb = _eh_hibrido()
                _bs = _eh_bs()
                _mod = _modelo_atual()
                # linha Excel: borda inferior, hover, padding — como tabela Pesquisar (flat bordered dense)
                with ui.row().classes("w-full items-center bg-white hover:bg-grey-2 border-b border-grey-3 px-2 py-1").style("gap: 0.5rem; min-width: 0"):
                    ui.checkbox("", value=p["caminho"] in selecionados,
                                on_change=lambda e, cam=p["caminho"], nom=p["nome"]:
                                _alternar_selecao(e.value, cam, nom)) \
                        .props("dense").props("data-testid=empenhos-selecionar") \
                        .tooltip("Selecionar para o lote")
                    ui.icon("picture_as_pdf").classes("text-primary shrink-0").props('aria-hidden="true"')
                    with ui.column().classes("flex-1").style("min-width: 0"):
                        ui.label(p["nome"]).classes("font-medium text-wrap").style("min-width: 0; overflow-wrap: anywhere; font-size: 0.9rem")
                        if sub:
                            ui.label(sub).classes("text-caption text-grey-6").style("min-width: 0")
                    # colunas Excel — empenho / parcela / usuário / data (largura fixa, como Pesquisar)
                    ui.label(str(empenho)).classes("text-caption shrink-0").style("min-width: 5ch; text-align: center").tooltip("Empenho")
                    ui.label(str(parcela)).classes("text-caption shrink-0").style("min-width: 4ch; text-align: center").tooltip("Parcela")
                    ui.label(str(usuario)).classes("text-caption shrink-0").style("min-width: 10ch; max-width: 18ch; overflow: hidden; text-overflow: ellipsis; text-align: center").tooltip(f"Usuário: {usuario}")
                    ui.label(str(data)).classes("text-caption text-grey-7 shrink-0").style("min-width: 10ch; text-align: center").tooltip("Data")
                    # badges
                    if _hb:
                        bg = {"processado": "bg-success", "pendente": "bg-warning text-dark"}.get(p["status"], "bg-secondary")
                        ui.html(f'<span class="badge empenho-badge-hibrido {bg} rounded-pill">{p["status"]}</span>').classes("shrink-0")
                        if presente is not None:
                            if presente:
                                ui.html('<span class="badge empenho-badge-hibrido bg-success rounded-pill">na pasta</span>').classes("shrink-0")
                            else:
                                ui.html('<span class="badge empenho-badge-hibrido bg-secondary rounded-pill">fora da pasta</span>').classes("shrink-0")
                    elif _bs or _modelo_atual() in _visual.FRAMEWORKS:
                        bg = {"processado": "bg-success", "pendente": "bg-warning text-dark"}.get(p["status"], "bg-secondary")
                        ui.html(f'<span class="badge {bg} rounded-pill">{p["status"]}</span>').classes("shrink-0")
                        if presente is not None:
                            if presente:
                                ui.html('<span class="badge bg-success rounded-pill">na pasta</span>').classes("shrink-0")
                            else:
                                ui.html('<span class="badge bg-secondary rounded-pill">fora da pasta</span>').classes("shrink-0")
                    else:
                        cor = _visual.cor_badge_pic(p["status"])
                        ui.badge(p["status"], color=cor).classes("empenho-badge-soft shrink-0").props('aria-label=status')
                        if presente is not None:
                            if presente:
                                ui.badge("na pasta", color="green").classes("empenho-badge-soft shrink-0")
                            else:
                                ui.badge("fora da pasta", color="grey").classes("empenho-badge-soft shrink-0")
                    with ui.row().classes("items-center shrink-0").style("gap: 0.25rem"):
                        botao_icone("download", on_click=lambda c=p["caminho"]: _baixar(c),
                                     chave_modulo="empenhos").tooltip("Baixar")
                        if eh_admin:
                            botao_icone("edit", on_click=lambda c=p["caminho"]: _revisar_renomear(c),
                                     chave_modulo="empenhos").tooltip("Editar campos (lápis — livre)") \
                                .props("data-testid=empenhos-navegar-editar")
                            botao_icone("auto_fix_high", on_click=lambda c=p["caminho"]: _processar_auto(c),
                                     chave_modulo="empenhos").tooltip("Processar (auto)") \
                                .props("data-testid=empenhos-navegar-processar")
                        botao_icone("mail", on_click=lambda c=p["caminho"]: _solicitar(c),
                                 chave_modulo="empenhos").tooltip("Solicitar envio")
            except Exception as e:
                try:
                    _log.exception(f"_card_pdf falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _card_pdf: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _card_pdf", type="negative")
                    except Exception:
                        pass
                return None

        def _buscar_dados(termo, raiz):
            """Coleta resultados na árvore da pasta atual (nome + presença).

            Combina o FTS5 dos processados (banco do módulo, 42+ campos) com o
            levantamento (detectados/pendentes anotados pelo monitor, com nome,
            campos e conteúdo). Só caminhos sob a raiz navegável atual; mostra
            só o nome do arquivo + se ainda está nas pastas monitoradas.
            """
            achados, vistos = [], set()

            def _dentro(caminho):
                try:
                    real = os.path.realpath(caminho or "")
                    if not real or not (real == raiz or real.startswith(raiz + os.sep)):
                        return None
                    return real
                except Exception as e:
                    try:
                        _log.exception(f"_dentro falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _dentro: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _dentro", type="negative")
                        except Exception:
                            pass
                    return None

            def _sub(real):
                try:
                    rel = os.path.relpath(os.path.dirname(real), raiz)
                    return None if rel == "." else rel
                except Exception as e:
                    try:
                        _log.exception(f"_sub falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _sub: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _sub", type="negative")
                        except Exception:
                            pass
                    return None
            # processados (FTS5 do módulo)
            try:
                fileiras = pesquisar(termo, limite=100) or []
            except Exception:
                _log.exception("pesquisa FTS5 falhou no navegar")
                fileiras = []
            for eid, final, num, parc, usr, dt, caminho in fileiras:
                try:
                    real = _dentro(caminho)
                    if not real or real.lower() in vistos:
                        continue
                    if not os.path.exists(real):
                        continue
                    vistos.add(real.lower())
                    achados.append({"nome": os.path.basename(final or "") or os.path.basename(real),
                                    "caminho": real, "status": status_arquivo(real),
                                    "sub": _sub(real), "presente": 1,
                                    "numero_empenho": num, "parcela": parc, "usuario": usr, "data": (dt or "")[:10]})
                except Exception:
                    continue
            # levantamento (pendentes/detectados com nome, campos e conteúdo)
            try:
                fileiras_lev = pesquisar_levantamento(termo, limite=100) or []
            except Exception:
                _log.exception("pesquisa no levantamento falhou no navegar")
                fileiras_lev = []
            for lid, nome, caminho, presente, status, numero, parcela, ficha, ano, usr in fileiras_lev:
                try:
                    real = _dentro(caminho)
                    if not real or real.lower() in vistos:
                        continue
                    vistos.add(real.lower())
                    em_disco = os.path.exists(real)
                    achados.append({"nome": os.path.basename(nome or "") or os.path.basename(real),
                                    "caminho": real, "status": status or status_arquivo(real),
                                    "sub": _sub(real),
                                    "presente": 1 if (presente and em_disco) else 0,
                                    "numero_empenho": numero, "parcela": parcela, "usuario": usr, "data": ""})
                except Exception:
                    continue
            return achados

        async def _filtrar(e):
            termo = e.args if isinstance(e.args, str) else (e.args and e.args[0]) or ""
            filtro_nome["texto"] = termo
            filtro_nome["seq"] = filtro_nome.get("seq", 0) + 1
            minha_vez = filtro_nome["seq"]
            if not termo.strip():
                _carregar()
                return
            raiz = os.path.realpath(pasta_atual.get("caminho") or pasta_monitorada())
            wrap.clear()
            with wrap:
                with ui.row().classes("w-full items-center justify-center") \
                        .style("gap: 0.5rem") as linha_status:
                    ui.spinner(size="lg").props("aria-label=Pesquisando empenhos")
                    ui.label("Pesquisando (FTS5 + conteúdo)…").classes("text-caption text-grey-7")
            try:
                achados = await run.io_bound(_buscar_dados, termo, raiz)
            except Exception:
                _log.exception("busca no navegar falhou")
                achados = []
            if minha_vez != filtro_nome.get("seq"):
                return  # tecla mais nova já disparou outra busca
            # filtro "só pendentes" também na busca
            _total_achados = len(achados)
            if filtro_pendente.get("ativo"):
                achados = [p for p in achados if (p.get("status") or "") == "pendente"]
            wrap.clear()
            with wrap:
                if filtro_pendente.get("ativo") and _total_achados:
                    ui.label(f"Pesquisa '{termo.strip()}': {len(achados)} pendente(s) de {_total_achados} resultado(s) "
                             f"nesta pasta e subpastas (só a renomear).") \
                        .classes("text-caption text-orange-7") \
                        .props("data-testid=empenhos-navegar-contagem")
                else:
                    ui.label(f"Pesquisa '{termo.strip()}': {len(achados)} resultado(s) "
                             f"nesta pasta e subpastas (nome + presença).") \
                        .classes("text-caption text-grey-7") \
                        .props("data-testid=empenhos-navegar-contagem")
                if not achados:
                    ui.label("Nada encontrado.").classes("text-caption text-grey-5")
                else:
                    with ui.row().classes("w-full bg-grey-3 border border-grey-3 rounded-t px-2 py-1 font-bold text-caption").style("gap: 0.5rem"):
                        ui.label("").style("min-width: 2ch")
                        ui.icon("picture_as_pdf").classes("text-grey-7 shrink-0").props('aria-hidden="true"')
                        ui.label("Arquivo").classes("flex-1").style("min-width: 0")
                        ui.label("Empenho").style("min-width: 5ch; text-align: center")
                        ui.label("Parcela").style("min-width: 4ch; text-align: center")
                        ui.label("Usuário").style("min-width: 10ch; text-align: center")
                        ui.label("Data").style("min-width: 10ch; text-align: center")
                        ui.label("Status").style("min-width: 8ch; text-align: center")
                        ui.label("Pasta").style("min-width: 7ch; text-align: center")
                        ui.label("Ações").style("min-width: 8ch; text-align: center")
                    with ui.column().classes("w-full border border-t-0 border-grey-3 rounded-b overflow-hidden").style("gap: 0"):
                        for p in achados:
                            _card_pdf(p, sub=p.get("sub"), presente=p.get("presente", 1))

        def _carregar():
            try:
                wrap.clear()
                pasta = pasta_atual.get("caminho")
                nav = listar_navegacao(pasta)
                pasta_atual["caminho"] = nav["atual"]
                # filtro "só pendentes" — aplica antes de exibir e de alimentar Marcar visíveis/lote
                _todos = nav.get("pdfs") or []
                if filtro_pendente.get("ativo"):
                    _exibir = [p for p in _todos if (p.get("status") or "") == "pendente"]
                else:
                    _exibir = _todos
                pasta_atual["pdfs"] = _exibir
                pasta_atual["pdfs_total"] = _todos
                with wrap:
                    # Navegação contida num único card — [seta RAIZ(pastas monitoradas), pastas(...)]
                    _bs_bc = _eh_bs()
                    raiz = raizes_navegacao()[0] if raizes_navegacao() else pasta_monitorada()
                    with ui.card().classes("w-full bg-white border rounded-lg shadow-sm p-3 mt-2"):
                        with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem"):
                            botao_icone("arrow_upward", on_click=_subir, chave_modulo="empenhos").tooltip("Pasta anterior")
                            if nav["atual"] != raiz:
                                botao("•", on_click=lambda: _ir(raiz), variante="texto", compacto=True, chave_modulo="empenhos").tooltip("Pasta raiz (pastas monitoradas)").props('data-testid=empenhos-raiz-dot')
                                rel = os.path.relpath(nav["atual"], raiz)
                                ui.label("/ " + rel).classes("text-caption text-grey-7").style("min-width: 0; overflow-wrap: anywhere")
                            else:
                                ui.label("•").classes("text-caption font-bold text-grey-7").props('data-testid=empenhos-raiz-dot').tooltip("Pasta raiz (pastas monitoradas)")
                            if nav["dirs"]:
                                ui.separator().props("vertical").classes("mx-1")
                                for d in nav["dirs"]:
                                    botao(d["nome"], icone="folder", on_click=lambda cam=d["caminho"]: _ir(cam),
                                           variante="texto", compacto=True, chave_modulo="empenhos", extra_classes="text-left").props(f'data-testid=empenhos-pasta-{d["nome"]}')
                    # pdfs da pasta atual — visual Excel do Pesquisar (linhas com borda, hover)
                    if not _exibir:
                        if _todos and filtro_pendente.get("ativo"):
                            ui.label(f"Nenhum pendente nesta pasta — {len(_todos)} já processado(s). Desative o filtro para ver todos.").classes("text-caption text-grey-5")
                        else:
                            ui.label("Nenhum PDF nesta pasta.").classes("text-caption text-grey-5")
                    else:
                        if filtro_pendente.get("ativo") and _todos:
                            ui.label(f"Filtro ativo — mostrando {len(_exibir)} pendente(s) de {len(_todos)} nesta pasta.").classes("text-caption text-orange-7") \
                                .props("data-testid=empenhos-filtro-info")
                        # cabeçalho Excel
                        with ui.row().classes("w-full bg-grey-3 border border-grey-3 rounded-t px-2 py-1 font-bold text-caption").style("gap: 0.5rem"):
                            ui.label("").style("min-width: 2ch")
                            ui.icon("picture_as_pdf").classes("text-grey-7 shrink-0").props('aria-hidden="true"')
                            ui.label("Arquivo").classes("flex-1").style("min-width: 0")
                            ui.label("Empenho").style("min-width: 5ch; text-align: center")
                            ui.label("Parcela").style("min-width: 4ch; text-align: center")
                            ui.label("Usuário").style("min-width: 10ch; text-align: center")
                            ui.label("Data").style("min-width: 10ch; text-align: center")
                            ui.label("Status").style("min-width: 8ch; text-align: center")
                            ui.label("Pasta").style("min-width: 7ch; text-align: center")
                            ui.label("Ações").style("min-width: 8ch; text-align: center")
                        with ui.column().classes("w-full border border-t-0 border-grey-3 rounded-b overflow-hidden").style("gap: 0"):
                            for p in _exibir:
                                _card_pdf(p)
            except Exception as e:
                try:
                    _log.exception(f"_carregar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _carregar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _carregar", type="negative")
                    except Exception:
                        pass
                return None

        def _ir(cam):
            try:
                pasta_atual["caminho"] = cam
                _carregar()
            except Exception as e:
                try:
                    _log.exception(f"_ir falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _ir: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _ir", type="negative")
                    except Exception:
                        pass
                return None

        def _subir():
            try:
                p = pasta_atual.get("caminho") or pasta_monitorada()
                pai = os.path.dirname(p)
                if pais_navegavel(pai):
                    _ir(pai)
                else:
                    _ir(raizes_navegacao()[0] if raizes_navegacao() else pasta_monitorada())
            except Exception as e:
                try:
                    _log.exception(f"_subir falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _subir: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _subir", type="negative")
                    except Exception:
                        pass
                return None

        def pais_navegavel(pai):
            try:
                return pai in raizes_navegacao() or qualquer_raiz_tem(pai)
            except Exception:
                return False

        def qualquer_raiz_tem(pai):
            try:
                for r in raizes_navegacao():
                    if pai == r or pai.startswith(r + os.sep):
                        return True
                return False
            except Exception as e:
                try:
                    _log.exception(f"qualquer_raiz_tem falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em qualquer_raiz_tem: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em qualquer_raiz_tem", type="negative")
                    except Exception:
                        pass
                return None

        def _alternar_filtro():
            try:
                filtro_pendente["ativo"] = not filtro_pendente["ativo"]
                ui.notify("Mostrando apenas pendentes" if filtro_pendente["ativo"] else "Mostrando todos", type="info")
                # reaplica filtro na listagem atual (sem perder pesquisa)
                if filtro_nome.get("texto", "").strip():
                    # se há pesquisa ativa, refaz a busca com o filtro
                    try:
                        ui.timer(0.1, lambda: _filtrar(type("e", (), {"args": filtro_nome["texto"]})()), once=True)
                    except Exception:
                        _carregar()
                else:
                    _carregar()
            except Exception as e:
                try:
                    _log.exception(f"_alternar_filtro falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _alternar_filtro: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _alternar_filtro", type="negative")
                    except Exception:
                        pass
                return None

        # Barra combinada — [{campo de pesquisa}, x selecionados, marcar ... limpar, baixar, solicitar] — processar/atualizar dentro do card do pesquisar
        # (processar=run, atualizar=refresh já dentro da barra acima)
        _hb_pesq = _eh_hibrido()
        _bs_pesq = _eh_bs()
        _mod_pesq = _modelo_atual()
        _fw_pesq = _mod_pesq in _visual.FRAMEWORKS
        with ui.row().classes("w-full items-center flex-wrap bg-white border rounded-lg shadow-sm px-3 py-2 mt-2").style("gap: 0.5rem"):
            # campo de pesquisa dentro da barra — 25ch visíveis, expande até 70ch conforme espaço
            if _hb_pesq:
                with ui.element("div").classes("input-group flex-1 empenho-hibrido").style("min-width: 25ch; max-width: 70ch; flex: 1 1 25ch"):
                    ui.html('<span class="input-group-text"><i class="q-icon notranslate material-icons" aria-hidden="true">search</i></span>')
                    inp_pesquisa = ui.input(placeholder="Pesquisar (conteúdo + todos os campos)",
                                            label="Pesquisar") \
                        .props("outlined dense clearable debounce=300").classes("w-full empenho-hibrido") \
                        .props("data-testid=empenhos-navegar-pesquisa") \
                        .tooltip("Busca FTS5 no banco do módulo + levantamento: pasta atual e subpastas")
            elif _bs_pesq or _fw_pesq:
                with ui.element("div").classes("input-group flex-1").style("min-width: 25ch; max-width: 70ch; flex: 1 1 25ch"):
                    ui.html('<span class="input-group-text bg-white"><i class="q-icon notranslate material-icons" aria-hidden="true">search</i></span>')
                    inp_pesquisa = ui.input(placeholder="Pesquisar (conteúdo + todos os campos)",
                                            label="Pesquisar") \
                        .props("outlined dense").classes("w-full").props("data-testid=empenhos-navegar-pesquisa") \
                        .tooltip("Busca FTS5 no banco do módulo + levantamento: pasta atual e subpastas")
            else:
                inp_pesquisa = ui.input(placeholder="Pesquisar (conteúdo + todos os campos)",
                                        label="Pesquisar") \
                    .props("outlined dense clearable debounce=300").classes("flex-1 empenho-input-soft").style("min-width: 25ch; max-width: 70ch; flex: 1 1 25ch") \
                    .props("data-testid=empenhos-navegar-pesquisa") \
                    .tooltip("Busca FTS5 no banco do módulo + levantamento: pasta atual e subpastas")
            inp_pesquisa.on("update:model-value", _filtrar)

            async def _toggle_pendentes(e):
                try:
                    filtro_pendente["ativo"] = bool(e.value)
                    termo = (filtro_nome.get("texto") or "").strip()
                    if termo:
                        # re-executa a pesquisa com o novo filtro (pendente)
                        class _Ev:
                            args = termo
                        await _filtrar(_Ev())
                    else:
                        _carregar()
                except Exception as e:
                    try:
                        _log.exception(f"_toggle_pendentes falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _toggle_pendentes: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _toggle_pendentes", type="negative")
                        except Exception:
                            pass
                    return None

            sw_pendentes = ui.switch("Só pendentes", value=False).props("dense").classes("shrink-0 ml-1") \
                .props("data-testid=empenhos-filtro-pendentes") \
                .tooltip("Mostrar somente o que precisa ser renomeado (pendente) nesta pasta — oculta processados") \
                .on("update:model-value", _toggle_pendentes)
            botao_icone("filter_alt", on_click=lambda: sw_pendentes.set_value(not sw_pendentes.value), chave_modulo="empenhos").tooltip("Filtro: todos / apenas pendentes").props("data-testid=empenhos-filtro-icone").classes("ml-1")
            if eh_admin:
                botao_icone("directions_run", on_click=lambda: _processar(), chave_modulo="empenhos").tooltip("Processar pasta agora").props("data-testid=empenhos-processar")
            botao_icone("refresh", on_click=lambda: _carregar(), chave_modulo="empenhos").tooltip("Atualizar").props("data-testid=empenhos-atualizar")
            ui.separator().props("vertical").classes("mx-1")
            lbl_lote = ui.label("0 selecionados").classes("font-bold text-caption shrink-0").props("data-testid=empenhos-lote-contador")
            botao_icone("checklist", on_click=_marcar_visiveis, chave_modulo="empenhos").tooltip("Marcar visíveis").props("data-testid=empenhos-lote-marcar")
            with ui.element("div").classes("flex-1"):
                pass
            botao_icone("cleaning_services", on_click=_limpar_selecao, chave_modulo="empenhos").tooltip("Limpar seleção").props("data-testid=empenhos-lote-limpar")
            botao_icone("download", on_click=_baixar_lote, chave_modulo="empenhos").tooltip("Baixar lote").props("data-testid=empenhos-lote-baixar")
            botao_icone("mail", on_click=_solicitar_lote, chave_modulo="empenhos").tooltip("Solicitar lote por e-mail").props("data-testid=empenhos-lote-solicitar")
        wrap = ui.column().classes("w-full")

        def _processar():
            if not eh_admin:
                ui.notify("Ação restrita ao administrador do módulo.", type="warning")
                return
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
    except Exception as e:
        try:
            _log.exception(f"_tela_navegar falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_navegar: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_navegar", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA FILA
def _tela_fila(usuario_logado, eh_admin, _btn_cls, _btn_style):
    """Queue tab: recursive list of pending PDFs with individual/bulk processing."""
    try:
        from mod_intranet.bd_conexao import get_config as _gc_fila
        def _eh_bs_fila():
            try:
                return _visual.eh_bootstrap(_gc_fila)
            except Exception:
                return False
        wrap = ui.column().classes("w-full")

        def _carregar():
            try:
                wrap.clear()
                pendentes = listar_pendentes(recursivo=True)
                _bs = _eh_bs_fila()
                with wrap:
                    ui.label(f"Fila de renomeação — {len(pendentes)} pendente(s)").classes("text-subtitle1 font-bold")
                    if not pendentes:
                        with ui.element("div").classes("alert alert-light border rounded-3 text-center py-4 w-full" if _bs else "w-full text-center py-4 bg-grey-1 rounded-xl"):
                            ui.icon("inbox").classes("text-grey-5")
                            ui.label("Nenhum documento aguardando renomeação.").classes("text-caption text-grey-5")
                    # Visual Excel igual ao Navegar — mesma linha com bordas, hover e colunas
                    def _detalhes_fila(p):
                        nome = p.get("nome") or ""
                        empenho = p.get("numero_empenho") or "—"
                        parcela = p.get("parcela") or "—"
                        if isinstance(empenho, str) and empenho.isdigit():
                            empenho = empenho.lstrip("0") or "0"
                        if isinstance(parcela, str) and parcela.isdigit():
                            parcela = parcela.lstrip("0") or "0"
                        elif isinstance(parcela, int):
                            parcela = str(parcela)
                        usuario = (p.get("usuario") or "").strip() if isinstance(p.get("usuario"), str) else ""
                        if not usuario:
                            usuario = "—"
                        import re as _re
                        m = _re.match(r"doc_\d+_(\d+)_(\d+)\.pdf$", nome, _re.I)
                        if m:
                            if empenho == "—":
                                empenho = m.group(1).lstrip("0") or "0"
                            if parcela == "—":
                                parcela = m.group(2).lstrip("0") or "0"
                        try:
                            import datetime as _dt
                            ts = os.path.getmtime(p.get("caminho") or "")
                            data = _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        except Exception:
                            data = p.get("data") or "—"
                        return empenho, parcela, usuario, data

                    def _editar_fila(caminho):
                        # Lápis — permite escrever o que quiser nos campos (mesma tela do Navegar)
                        nome = os.path.basename(caminho)
                        try:
                            texto = extrair_texto_pdf(caminho) or ""
                        except Exception:
                            texto = ""
                        try:
                            tipo_detectado = detectar_tipo_especial(texto)
                        except Exception:
                            tipo_detectado = None
                        dados_doc, dados_esp = {}, {}
                        try:
                            dados_doc = extrair_dados_empenho(texto) or {}
                        except Exception:
                            dados_doc = {}
                        if tipo_detectado:
                            try:
                                dados_esp = extrair_dados_tipo_especial(texto, tipo_detectado) or {}
                            except Exception:
                                dados_esp = {}
                        eh_especial = bool(tipo_detectado)
                        with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
                            ui.label(f"Editar — {nome}").classes("text-h6")
                            ui.label("Preencha livremente os campos — a renomeação usa o que for digitado.").classes("text-caption text-grey-6")
                            sel_tipo = ui.select(
                                {"": "DOC (empenho de parcela)", "EC": "EC — Complementação",
                                 "EE": "EE — Estimativo", "EG": "EG — Global", "AE": "AE — Anulação"},
                                label="Tipo de documento", value=tipo_detectado or "").props("outlined dense").classes("w-full")
                            inp_ficha = ui.input("Ficha", value=str(dados_doc.get("ficha") or "")).props("outlined dense").classes("w-full")
                            inp_empenho = ui.input("Nº empenho / Nº documento especial",
                                value=str(dados_esp.get("numero") if eh_especial and dados_esp.get("numero") else (dados_doc.get("empenho") or ""))).props("outlined dense").classes("w-full")
                            inp_parcela = ui.input("Parcela (só DOC)", value=str(dados_doc.get("parcela") or "")).props("outlined dense").classes("w-full")
                            inp_ano = ui.input("Ano", value=str(dados_esp.get("ano") if eh_especial and dados_esp.get("ano") else (dados_doc.get("ano") or ""))).props("outlined dense").classes("w-full")
                            res = ui.column().classes("w-full mt-1")
                            def _confirmar():
                                try:
                                    tipo = (sel_tipo.value or "").strip() or None
                                    ficha = (inp_ficha.value or "").strip() or None
                                    ano = (inp_ano.value or "").strip() or None
                                    num_txt = (inp_empenho.value or "").strip()
                                    parc_txt = (inp_parcela.value or "").strip()
                                    if tipo:
                                        if not num_txt:
                                            raise ValueError("Informe o nº do documento especial")
                                        ok, msg = renomear_manual(usuario_logado, caminho, novo_numero=num_txt, tipo_especial=tipo)
                                    else:
                                        if not num_txt:
                                            raise ValueError("Informe o nº do empenho")
                                        ok, msg = renomear_manual(usuario_logado, caminho, novo_numero=num_txt, novo_parcela=parc_txt or None, nova_ficha=ficha, novo_ano=ano)
                                    if ok:
                                        ui.notify(f"Renomeado → {msg}", type="positive")
                                        dlg.close()
                                        _carregar()
                                    else:
                                        with res:
                                            ui.label(f"Não foi possível renomear: {msg}").classes("text-negative")
                                except ValueError as ve:
                                    with res:
                                        ui.label(str(ve)).classes("text-negative")
                                except Exception as e:
                                    with res:
                                        ui.label(f"Erro: {e}").classes("text-negative")
                            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                                botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                                botao("Renomear", icone="auto_fix_high", on_click=_confirmar, variante="solido", chave_modulo="empenhos")
                        dlg.open()

                    if pendentes:
                        # cabeçalho Excel — mesmo do Navegar
                        with ui.row().classes("w-full bg-grey-3 border border-grey-3 rounded-t px-2 py-1 font-bold text-caption").style("gap: 0.5rem"):
                            ui.icon("description").classes("text-grey-7 shrink-0").props('aria-hidden="true"')
                            ui.label("Arquivo").classes("flex-1").style("min-width: 0")
                            ui.label("Empenho").style("min-width: 5ch; text-align: center")
                            ui.label("Parcela").style("min-width: 4ch; text-align: center")
                            ui.label("Usuário").style("min-width: 10ch; text-align: center")
                            ui.label("Data").style("min-width: 10ch; text-align: center")
                            ui.label("Status").style("min-width: 8ch; text-align: center")
                            ui.label("Ações").style("min-width: 12ch; text-align: center")
                        with ui.column().classes("w-full border border-t-0 border-grey-3 rounded-b overflow-hidden").style("gap: 0"):
                            for p in pendentes:
                                empenho, parcela, usuario, data = _detalhes_fila(p)
                                with ui.row().classes("w-full items-center bg-white hover:bg-grey-2 border-b border-grey-3 px-2 py-1").style("gap: 0.5rem; min-width: 0"):
                                    ui.icon("description").classes("text-orange-7 shrink-0")
                                    ui.label(p["nome"]).classes("flex-1 text-wrap font-medium").style("min-width: 0; overflow-wrap: anywhere; font-size: 0.9rem")
                                    ui.label(str(empenho)).classes("text-caption shrink-0").style("min-width: 5ch; text-align: center")
                                    ui.label(str(parcela)).classes("text-caption shrink-0").style("min-width: 4ch; text-align: center")
                                    ui.label(str(usuario)).classes("text-caption shrink-0").style("min-width: 10ch; max-width: 18ch; overflow: hidden; text-overflow: ellipsis; text-align: center").tooltip(f"Usuário: {usuario}")
                                    ui.label(str(data)).classes("text-caption text-grey-7 shrink-0").style("min-width: 10ch; text-align: center")
                                    if _bs:
                                        ui.html('<span class="badge bg-warning text-dark rounded-pill">pendente</span>').classes("shrink-0")
                                    else:
                                        ui.badge("pendente", color="orange").classes("empenho-badge-soft shrink-0")
                                    with ui.row().classes("items-center shrink-0").style("gap: 0.25rem"):
                                        botao_icone("edit", on_click=lambda c=p["caminho"]: _editar_fila(c), chave_modulo="empenhos").tooltip("Editar campos (lápis — livre)").props("data-testid=empenhos-fila-editar")
                                        def _renomear(cam=p["caminho"]):
                                            try:
                                                ok, msg = renomear_manual(usuario_logado, cam)
                                                ui.notify(f"Renomeado → {msg}" if ok else f"Falha: {msg}", type="positive" if ok else "negative")
                                                _carregar()
                                            except Exception as e:
                                                try:
                                                    _log.exception(f"_renomear falhou: {e}")
                                                except Exception:
                                                    pass
                                                try:
                                                    notificar(f"Erro em _renomear: {e}", tipo="error")
                                                except Exception:
                                                    try:
                                                        ui.notify(f"Erro em _renomear", type="negative")
                                                    except Exception:
                                                        pass
                                                return None
                                        botao_icone("auto_fix_high", on_click=_renomear, chave_modulo="empenhos").tooltip("Processar (auto)").props("data-testid=empenhos-fila-processar")
            except Exception as e:
                try:
                    _log.exception(f"_carregar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _carregar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _carregar", type="negative")
                    except Exception:
                        pass
                return None

        with ui.row().classes("w-full flex-wrap").style("gap: 0.5rem"):
            botao("Processar todos", icone="play_arrow",
                      on_click=lambda: _processar_todos(), variante="solido",
                      chave_modulo="empenhos")
            botao("Atualizar", icone="refresh", on_click=_carregar,
                  variante="contorno", chave_modulo="empenhos")

        def _processar_todos():
            try:
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
            except Exception as e:
                try:
                    _log.exception(f"_processar_todos falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _processar_todos: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _processar_todos", type="negative")
                    except Exception:
                        pass
                return None

        _carregar()
    except Exception as e:
        try:
            _log.exception(f"_tela_fila falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_fila: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_fila", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA PESQUISAR
def _tela_pesquisar(usuario_logado, _btn_cls, _btn_style):
    """Search tab: live FTS5 search (fallback LIKE) + renamed empenhos table."""
    try:
        from mod_intranet.bd_conexao import get_config
        autorizado = get_config("empenhos_autorizar_download", "0") == "1"
        _bs_pesq = _visual.eh_bootstrap(get_config)
        if _bs_pesq:
            with ui.element("div").classes("input-group w-full shadow-sm rounded-3 overflow-hidden"):
                ui.html('<span class="input-group-text bg-white border-end-0"><i class="q-icon notranslate material-icons" aria-hidden="true">search</i></span>')
                with ui.input(placeholder="Pesquisar conteúdo…").props("outlined dense clearable borderless") \
                    .classes("w-full").props('data-testid=empenhos-busca') as busca:
                    pass
        else:
            with ui.input(placeholder="Pesquisar conteúdo…").props("outlined dense clearable debounce=300") \
                .classes("w-full empenho-input-soft shadow-sm rounded-xl").props('data-testid=empenhos-busca') as busca:
                pass
        resultados_wrap = ui.column().classes("w-full")

        def _pesq(e):
            try:
                resultados_wrap.clear()
                termo = e.args if isinstance(e.args, str) else (e.args and e.args[0]) or ""
                rs = pesquisar(termo) or []
                _bs2 = _visual.eh_bootstrap(get_config)
                with resultados_wrap:
                    if not rs:
                        if _bs2:
                            ui.html('<div class="alert alert-light border text-center small text-muted">Nada encontrado.</div>')
                        else:
                            ui.label("Nada encontrado.").classes("text-caption text-grey-5")
                        return
                    for eid, final, num, parc, usr, dt, caminho in rs[:25]:
                        item_cls = "w-full border rounded-3 mb-1 shadow-sm card" if _bs2 else "w-full border rounded-xl mb-1 shadow-sm empenho-card-pic"
                        with ui.item().classes(item_cls):
                            with ui.item_section().props("avatar"):
                                ui.icon("description").classes("text-green-8")
                            with ui.item_section():
                                ui.item_label(final).classes("font-medium").style("min-width: 0; overflow-wrap: anywhere")
                                ui.item_label(f"empenho {num} • parcela {parc} • {usr}").props("caption")
            except Exception as e:
                try:
                    _log.exception(f"_pesq falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _pesq: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _pesq", type="negative")
                    except Exception:
                        pass
                return None

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
            try:
                linhas = []
                for r in listar_empenhos(status="ativo", limite=500):
                    linhas.append({"id": r[0], "final": r[2], "num": r[3] or "—",
                                   "parc": r[4] or "—", "tipo": r[8] if len(r) > 8 else "—",
                                   "usr": r[5] or "—", "dt": (r[6] or "")[:16]})
                tabela.rows = linhas
                tabela.update()
            except Exception as e:
                try:
                    _log.exception(f"_refresh falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _refresh: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _refresh", type="negative")
                    except Exception:
                        pass
                return None

        _refresh()
    except Exception as e:
        try:
            _log.exception(f"_tela_pesquisar falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_pesquisar: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_pesquisar", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA ORGANIZADOR (admin)
def _tela_organizador(usuario_logado, _btn_cls, _btn_style):
    """Organizer tab (admin): boxes, covers/matrix, inventory and PDF tools."""
    try:
        def _organizar():
            try:
                ok, msg = organizar_pastas()
                ui.notify(msg, type="positive" if ok else "negative")
            except Exception as e:
                try:
                    _log.exception(f"_organizar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _organizar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _organizar", type="negative")
                    except Exception:
                        pass
                return None

        def _gerar_matriz():
            try:
                ok, msg = gerar_matriz_organizador()
                ui.notify(msg, type="positive" if ok else "negative")
            except Exception as e:
                try:
                    _log.exception(f"_gerar_matriz falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _gerar_matriz: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _gerar_matriz", type="negative")
                    except Exception:
                        pass
                return None

        def _validar_matriz():
            try:
                ok, faltando = validar_presenca_matriz()
                if ok:
                    ui.notify("Todos os documentos da matriz estão presentes.", type="positive")
                else:
                    ui.notify("Faltando na matriz: " + ", ".join(faltando[:10]), type="warning")
            except Exception as e:
                try:
                    _log.exception(f"_validar_matriz falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _validar_matriz: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _validar_matriz", type="negative")
                    except Exception:
                        pass
                return None

        with ui.row().classes("w-full gap-3 flex-wrap"):
            botao("Organizar caixas", icone="inventory_2", on_click=_organizar,
                  variante="solido", chave_modulo="empenhos")
            botao("Gerar capas/matriz", icone="description", on_click=_gerar_matriz,
                  variante="contorno", chave_modulo="empenhos")
            botao("Validar matriz", icone="rule", on_click=_validar_matriz,
                  variante="contorno", chave_modulo="empenhos")

        with ui.expansion("Inventário — caixas e subpastas", icon="folder_open").classes("w-full mt-2"):
            inv_wrap = ui.column().classes("w-full")

            def _listar_inv():
                try:
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
                except Exception as e:
                    try:
                        _log.exception(f"_listar_inv falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _listar_inv: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _listar_inv", type="negative")
                        except Exception:
                            pass
                    return None

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
                try:
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
                except Exception as e:
                    try:
                        _log.exception(f"_up falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _up: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _up", type="negative")
                        except Exception:
                            pass
                    return None

            up.on("multi-upload", _up)

            def _fontes_atuais():
                try:
                    caminhos = []
                    for fid in (sel_fontes.value or []):
                        for f in ferramenta_fontes():
                            if str(f[0]) == str(fid):
                                caminhos.append(f[2])
                    return caminhos + list(up_paths)
                except Exception as e:
                    try:
                        _log.exception(f"_fontes_atuais falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _fontes_atuais: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _fontes_atuais", type="negative")
                        except Exception:
                            pass
                    return None

            with ui.row().classes("w-full gap-3 flex-wrap items-end"):
                modo = ui.select({"pares": "Pares", "impares": "Ímpares"},
                                 label="Corte", value="pares").props("outlined dense")
                interv = ui.input("Ou intervalo (ex.: 2-5,8)").props("outlined dense")
                qual = ui.slider(min=10, max=100, value=50, step=5).props("label ticks").classes("w-48")
                modo_red = ui.select({"leve": "Leve (recompressar)", "agressivo": "Agressivo (rasterizar)"},
                                     label="Redução", value="leve").props("outlined dense")

            res_ferr = ui.column().classes("w-full")

            def _mostrar(ok, res, acao):
                try:
                    res_ferr.clear()
                    if ok:
                        with res_ferr:
                            ui.label(f"{acao}: {os.path.basename(res)}").classes("text-caption text-green-8")
                            ui.link("Baixar arquivo", res, new_tab=True)
                    else:
                        ui.notify(f"{acao} falhou: {res}", type="negative")
                except Exception as e:
                    try:
                        _log.exception(f"_mostrar falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _mostrar: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _mostrar", type="negative")
                        except Exception:
                            pass
                    return None

            def _cortar():
                try:
                    srcs = _fontes_atuais()
                    if not srcs:
                        ui.notify("Selecione ao menos 1 fonte", type="warning"); return
                    filtro = interv.value.strip() if interv.value and interv.value.strip() else modo.value
                    ok, res = ferramenta_cortar(srcs[0], filtro, usuario_logado)
                    _mostrar(ok, res, "Corte")
                except Exception as e:
                    try:
                        _log.exception(f"_cortar falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _cortar: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _cortar", type="negative")
                        except Exception:
                            pass
                    return None

            def _juntar():
                try:
                    srcs = _fontes_atuais()
                    if len(srcs) < 2:
                        ui.notify("Selecione ao menos 2 fontes para mesclar", type="warning"); return
                    ok, res = ferramenta_juntar(srcs, usuario_logado)
                    _mostrar(ok, res, "Mescla")
                except Exception as e:
                    try:
                        _log.exception(f"_juntar falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _juntar: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _juntar", type="negative")
                        except Exception:
                            pass
                    return None

            def _reduzir():
                try:
                    srcs = _fontes_atuais()
                    if not srcs:
                        ui.notify("Selecione ao menos 1 fonte", type="warning"); return
                    ok, res = ferramenta_reduzir(srcs[0], usuario_logado, qualidade=qual.value, modo=modo_red.value)
                    _mostrar(ok, res, "Redução")
                except Exception as e:
                    try:
                        _log.exception(f"_reduzir falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _reduzir: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _reduzir", type="negative")
                        except Exception:
                            pass
                    return None

            with ui.row().classes("w-full gap-2 mt-2"):
                botao("Cortar", icone="content_cut", on_click=_cortar,
                    variante="solido", chave_modulo="empenhos")
                botao("Mesclar", icone="merge", on_click=_juntar,
                    variante="solido", chave_modulo="empenhos")
                botao("Reduzir", icone="compress", on_click=_reduzir,
                    variante="solido", chave_modulo="empenhos")
    except Exception as e:
        try:
            _log.exception(f"_tela_organizador falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_organizador: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_organizador", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA SOLICITAÇÃO
def _tela_solicitacao(usuario_logado, eh_admin, _btn_cls, _btn_style):
    """Request tab: common→admin document delivery flow (e-mail/ZIP/refusal).

    Cards agrupados por lote (`lote_id`) ou avulsos; admin envia por e-mail
    (SMTP central), gera ZIP, confirma envio manual, cancela ZIP ou recusa
    com motivo; expansão com o histórico completo."""
    try:
        lista = ui.column().classes("w-full")

        def _recarregar():
            try:
                lista.clear()
                itens = listar_solicitacoes_acao_pendente()
                lotes, avulsas = agrupar_solicitacoes_em_lote(itens)
                with lista:
                    if not itens:
                        ui.label("Nenhuma solicitação pendente de envio.").classes("text-caption text-grey-5")

                    def _card(grupo, titulo):
                        try:
                            primeiro = grupo[0]
                            status = primeiro.get("status", "pendente")
                            nome_dest = primeiro.get("solicitante_nome", "")
                            email_dest = primeiro.get("solicitante_email", "")
                            _bs_card = _visual.eh_bootstrap()
                            card_cls = _visual.classes_card_pdf(_bs_card)
                            with ui.card().classes(card_cls):
                                with ui.row().classes("w-full justify-between items-center").style("gap: 0.5rem"):
                                    ui.label(f"📄 {titulo}").classes("font-bold flex-1").style("min-width: 0; overflow-wrap: anywhere")
                                    if _bs_card:
                                        bg = "bg-warning text-dark" if status == "zip_gerado" else "bg-primary"
                                        ui.html(f'<span class="badge {bg} rounded-pill">{status.upper()}</span>')
                                    else:
                                        ui.badge(status.upper(), color="orange" if status == "zip_gerado" else "blue").classes("empenho-badge-soft")
                                ui.label(f"Solicitante: {nome_dest} <{email_dest}>").classes("text-caption").style("min-width: 0; overflow-wrap: anywhere")
                                ui.separator().classes("my-1")
                                for it in grupo:
                                    existe = os.path.exists(it.get("arquivo_caminho") or "")
                                    ui.label(f"• {it.get('nome_arquivo')}" + ("" if existe else "  ⚠️ não encontrado")) \
                                        .classes("text-sm").style("overflow-wrap: anywhere")
                                if status == "zip_gerado":
                                    if _bs_card:
                                        ui.html(f'<div class="alert alert-warning py-2 small mb-1">📂 ZIP: {primeiro.get("caminho_zip")}</div>')
                                    else:
                                        ui.label(f"📂 ZIP: {primeiro.get('caminho_zip')}").classes("text-caption bg-yellow-50 p-2 rounded").style("overflow-wrap: anywhere")
                                with ui.row().classes("w-full mt-2 flex-wrap").style("gap: 0.5rem"):
                                    if eh_admin:
                                        if status == "pendente":
                                            botao("Enviar por e-mail", icone="mail",
                                                      on_click=lambda g=grupo: _envia_email(g),
                                                      variante="solido", chave_modulo="empenhos")
                                            botao("Gerar ZIP", icone="folder_zip",
                                                      on_click=lambda g=grupo: _gera_zip(g),
                                                      variante="solido", chave_modulo="empenhos")
                                        elif status == "zip_gerado":
                                            botao("Confirmar envio manual", icone="check_circle",
                                                      on_click=lambda g=grupo: _confirma(g),
                                                      variante="solido", chave_modulo="empenhos")
                                            botao("Cancelar ZIP", icone="undo",
                                                      on_click=lambda g=grupo: _volta(g),
                                                      variante="texto", cor="orange-9",
                                                      chave_modulo="empenhos")
                                        if status in ("pendente", "zip_gerado"):
                                            botao("Recusar", icone="block",
                                                      on_click=lambda g=grupo: _recusa(g),
                                                      variante="perigo", chave_modulo="empenhos")
                                    else:
                                        ui.label("Aguardando ação do administrador.").classes("text-caption text-grey-5")
                        except Exception as e:
                            try:
                                _log.exception(f"_card falhou: {e}")
                            except Exception:
                                pass
                            try:
                                notificar(f"Erro em _card: {e}", tipo="error")
                            except Exception:
                                try:
                                    ui.notify(f"Erro em _card", type="negative")
                                except Exception:
                                    pass
                            return None

                    for lote_id, grupo in lotes.items():
                        _card(grupo, f"Lote de {len(grupo)} arquivo(s) — {grupo[0].get('solicitante_nome')}")
                    for s in avulsas:
                        _card([s], s.get("nome_arquivo"))
            except Exception as e:
                try:
                    _log.exception(f"_recarregar falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _recarregar: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _recarregar", type="negative")
                    except Exception:
                        pass
                return None

        def _envia_email(grupo):
            try:
                ok, msg = enviar_solicitacao_por_email(grupo)
                if ok:
                    for s in grupo:
                        marcar_solicitacao_enviada(s["id"], usuario_logado, metodo="email")
                    ui.notify("E-mail enviado!", type="positive")
                else:
                    ui.notify(f"Falha: {msg}", type="negative")
                _recarregar()
            except Exception as e:
                try:
                    _log.exception(f"_envia_email falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _envia_email: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _envia_email", type="negative")
                    except Exception:
                        pass
                return None

        def _gera_zip(grupo):
            try:
                ok, res = gerar_zip_solicitacoes(grupo)
                if ok:
                    ids = [s["id"] for s in grupo]
                    marcar_solicitacoes_zip_gerado(ids, res, usuario_logado)
                    ui.notify(f"ZIP gerado: {os.path.basename(res)}", type="positive")
                    ui.download(res, os.path.basename(res))
                else:
                    ui.notify(f"Erro ZIP: {res}", type="negative")
                _recarregar()
            except Exception as e:
                try:
                    _log.exception(f"_gera_zip falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _gera_zip: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _gera_zip", type="negative")
                    except Exception:
                        pass
                return None

        def _confirma(grupo):
            try:
                for s in grupo:
                    marcar_solicitacao_enviada(s["id"], usuario_logado, metodo="zip_manual")
                ui.notify("Envio manual confirmado!", type="positive")
                _recarregar()
            except Exception as e:
                try:
                    _log.exception(f"_confirma falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _confirma: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _confirma", type="negative")
                    except Exception:
                        pass
                return None

        def _volta(grupo):
            try:
                for s in grupo:
                    marcar_solicitacao_pendente(s["id"])
                ui.notify("ZIP cancelado, voltou a pendente", type="warning")
                _recarregar()
            except Exception as e:
                try:
                    _log.exception(f"_volta falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _volta: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _volta", type="negative")
                    except Exception:
                        pass
                return None

        def _recusa(grupo):
            try:
                with ui.dialog() as dlg, ui.card().classes("w-[400px]"):
                    ui.label("Recusar solicitação").classes("text-h6")
                    motivo = ui.input("Motivo (opcional)").props("outlined dense").classes("w-full")

                    def conf():
                        try:
                            for s in grupo:
                                marcar_solicitacao_recusada(s["id"], motivo.value or "", usuario_logado)
                            ui.notify("Solicitação recusada", type="warning")
                            dlg.close()
                            _recarregar()
                        except Exception as e:
                            try:
                                _log.exception(f"conf falhou: {e}")
                            except Exception:
                                pass
                            try:
                                notificar(f"Erro em conf: {e}", tipo="error")
                            except Exception:
                                try:
                                    ui.notify(f"Erro em conf", type="negative")
                                except Exception:
                                    pass
                            return None

                    with ui.row().classes("w-full justify-end gap-2"):
                        botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                        botao("Recusar", on_click=conf, variante="primario", cor="negative",
                              chave_modulo="empenhos")
                dlg.open()
            except Exception as e:
                try:
                    _log.exception(f"_recusa falhou: {e}")
                except Exception:
                    pass
                try:
                    notificar(f"Erro em _recusa: {e}", tipo="error")
                except Exception:
                    try:
                        ui.notify(f"Erro em _recusa", type="negative")
                    except Exception:
                        pass
                return None

        with ui.row().classes("w-full gap-2"):
            botao("Atualizar", icone="refresh", on_click=_recarregar,
                  variante="contorno", chave_modulo="empenhos")

        with ui.expansion("📜 Histórico completo", icon="history").classes("w-full mt-4"):
            hist_wrap = ui.column().classes("w-full")

            def _hist():
                try:
                    hist_wrap.clear()
                    with hist_wrap:
                        for s in listar_solicitacoes():
                            ui.label(
                                f"[{s.get('timestamp_solicitacao','')[:16]}] {s.get('nome_arquivo')} — "
                                f"{s.get('solicitante_nome') or s.get('solicitante_email')} → {s.get('status')} "
                                f"({s.get('metodo_envio') or '—'})").classes("text-caption")
                except Exception as e:
                    try:
                        _log.exception(f"_hist falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _hist: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _hist", type="negative")
                        except Exception:
                            pass
                    return None

            _hist()

        _recarregar()
    except Exception as e:
        try:
            _log.exception(f"_tela_solicitacao falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_solicitacao: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_solicitacao", type="negative")
            except Exception:
                pass
        return None


# ============================================================ ABA CONFIG (admin)
def _tela_config(usuario_logado, eh_admin, t_cor_botao, t_cor_txt_botao, t_cor_fundo,
                 t_cor_titulo, t_tamanho, texto_header, _btn_cls, _btn_style):
    """Settings tab (admin): folders, appearance, template, fields, audit, rules.

    Expansões: pastas monitoradas (multi-pasta local/UNC), aparência
    (`empenhos_*`), intervalo do monitor e autorização de download para
    comuns, template do nome final (com pré-visualização), campos de busca
    por regex, auditoria dos arquivos, quarentena reprocessável e regras
    regex dinâmicas (com campo FTS destino)."""
    try:
        from mod_intranet.bd_conexao import get_config, set_config
        from mod_renomear_empenho.bd_manipulador import _PASTA_MONITORADA_PADRAO

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
                    try:
                        linhas = [l.strip() for l in (inp_pastas.value or "").splitlines() if l.strip()]
                        salvar_pastas_monitoradas(linhas)
                        ui.notify("Pastas monitoradas salvas (valem sem reiniciar)", type="positive")
                        ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                    except Exception as e:
                        try:
                            _log.exception(f"salvar_pastas falhou: {e}")
                        except Exception:
                            pass
                        try:
                            notificar(f"Erro em salvar_pastas: {e}", tipo="error")
                        except Exception:
                            try:
                                ui.notify(f"Erro em salvar_pastas", type="negative")
                            except Exception:
                                pass
                        return None

                with ui.row().classes("w-full justify-end gap-2"):
                    botao("Salvar pastas", icone="save", on_click=salvar_pastas,
                        variante="solido", chave_modulo="empenhos")

            ui.separator().classes("my-3")
            ui.label("Aparência — temas dos botões desta tela").classes("text-subtitle2 text-grey-7")
            inp_cor_botao = campo_cor("Cor geral do módulo", valor=t_cor_botao)
            inp_cor_txt = campo_cor("Cor do texto do módulo", valor=t_cor_txt_botao)
            inp_cor_fundo = campo_cor("Cor de fundo da página (vazio = herda)",
                                      valor=t_cor_fundo)
            inp_cor_titulo = campo_cor("Cor dos títulos", valor=t_cor_titulo)
            sel_tamanho = campo_selecao(
                "Tamanho dos botões",
                {0: "Pequeno", 1: "Médio", 2: "Grande"},
                valor={"small": 0, "medium": 1, "large": 2}.get(t_tamanho, 1))

            ui.separator().classes("my-3")
            ui.label("Configurações específicas").classes("text-subtitle2 text-grey-7")
            inp_texto = ui.input("Texto do cabeçalho", value=texto_header).props("outlined dense").classes("w-full")
            inp_intervalo = ui.input("Intervalo do monitor automático (segundos — recomendado 600 = 10 min)",
                                     value=str(_rotinas.intervalo_monitor_empenho())) \
                .props("outlined dense").classes("w-full") \
                .tooltip("Varredura automática das pastas monitoradas (RF-40). Aplicado sem reiniciar.")

            sw_autorizar = ui.switch(
                "Autorizar download/ZIP/e-mail para usuários comuns",
                value=get_config("empenhos_autorizar_download", "0") == "1") \
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
                    set_config("empenhos_autorizar_download", "1" if sw_autorizar.value else "0")
                    try:
                        iv = max(1, int((inp_intervalo.value or "600").strip() or 600))
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
                botao("Salvar", icone="save", on_click=salvar,
                    variante="solido", chave_modulo="empenhos")

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
                    try:
                        set_config("empenhos_template_nome", "")
                        ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                    except Exception as e:
                        try:
                            _log.exception(f"restaurar_template falhou: {e}")
                        except Exception:
                            pass
                        try:
                            notificar(f"Erro em restaurar_template: {e}", tipo="error")
                        except Exception:
                            try:
                                ui.notify(f"Erro em restaurar_template", type="negative")
                            except Exception:
                                pass
                        return None
                botao("Usar padrão", on_click=restaurar_template,
                      variante="texto", chave_modulo="empenhos")
                botao("Salvar template", icone="save", on_click=salvar_template,
                      variante="solido", chave_modulo="empenhos")

        # ================= Campos de busca configuráveis =================
        with ui.expansion("Campos de busca (regex de identificação)",
                          icon="manage_search").classes("w-full mt-2"):
            ui.label("Regex usadas para identificar cada campo. O 1º grupo é o valor; "
                     "o 2º, se houver, é o ano. Edite sem reiniciar.").classes("text-caption text-grey-6")
            lista_campos = ui.column().classes("w-full mt-1")

            def _refresh_campos():
                try:
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
                                botao_icone("delete", on_click=lambda c=cid: _del_campo(c),
                                                chave_modulo="empenhos").tooltip("Excluir campo")
                except Exception as e:
                    try:
                        _log.exception(f"_refresh_campos falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _refresh_campos: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _refresh_campos", type="negative")
                        except Exception:
                            pass
                    return None

            def _del_campo(cid):
                try:
                    excluir_campo_busca(cid)
                    _refresh_campos()
                except Exception as e:
                    try:
                        _log.exception(f"_del_campo falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _del_campo: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _del_campo", type="negative")
                        except Exception:
                            pass
                    return None

            _refresh_campos()

            with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
                f_campo = ui.input("Campo (chave)").props("outlined dense").classes("w-36")
                f_rotulo = ui.input("Rótulo").props("outlined dense").classes("w-40")
                f_padrao = ui.input("Regex (o 1º grupo é o valor)", placeholder=r"...(\d+)...") \
                    .props("outlined dense").classes("grow min-w-[240px]")
                f_ativo = ui.switch("Ativa", value=True).props("dense")

                def salvar_campo():
                    try:
                        ok, msg = salvar_campo_busca(
                            f_campo.value or "", f_rotulo.value or "",
                            f_padrao.value or "", bool(f_ativo.value))
                        ui.notify(msg, type="positive" if ok else "negative")
                        if ok:
                            f_campo.set_value(None); f_rotulo.set_value(None)
                            f_padrao.set_value(None); _refresh_campos()
                    except Exception as e:
                        try:
                            _log.exception(f"salvar_campo falhou: {e}")
                        except Exception:
                            pass
                        try:
                            notificar(f"Erro em salvar_campo: {e}", tipo="error")
                        except Exception:
                            try:
                                ui.notify(f"Erro em salvar_campo", type="negative")
                            except Exception:
                                pass
                        return None

                botao("Salvar campo", icone="save", on_click=salvar_campo,
                    variante="solido", chave_modulo="empenhos")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                def restaurar_campos():
                    try:
                        restaurar_campos_busca_padrao()
                        _refresh_campos()
                        ui.notify("Campos de busca restaurados ao padrão", type="positive")
                    except Exception as e:
                        try:
                            _log.exception(f"restaurar_campos falhou: {e}")
                        except Exception:
                            pass
                        try:
                            notificar(f"Erro em restaurar_campos: {e}", tipo="error")
                        except Exception:
                            try:
                                ui.notify(f"Erro em restaurar_campos", type="negative")
                            except Exception:
                                pass
                        return None
                botao("Restaurar padrão", icone="restore", on_click=restaurar_campos,
                    variante="restaurar", chave_modulo="empenhos")

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
                try:
                    sel = filtro_status.value or None
                    tabela_aud.rows = [
                        {"id": r[0], "nome_orig": r[1] or "—", "nome_final": r[2] or "—",
                         "num": r[3] or "—", "parc": r[4] or "—", "ficha": r[5] or "—",
                         "ano": r[6] or "—", "status": r[7] or "—", "usr": (r[8] or "—")[:12],
                         "dt": (r[10] or "")[:16]}
                        for r in listar_arquivos_auditoria(status=sel)
                    ]
                    tabela_aud.update()
                except Exception as e:
                    try:
                        _log.exception(f"_refresh_aud falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _refresh_aud: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _refresh_aud", type="negative")
                        except Exception:
                            pass
                    return None

            filtro_status.on("update:model-value", lambda e: _refresh_aud())
            _refresh_aud()

        with ui.expansion("Quarentena", icon="block").classes("w-full mt-2"):
            ui.label("Falhas de leitura/extração vão para a quarentena com motivo. Clique na linha para reprocessar individualmente (com regex alternativa) ou use o lote abaixo. Separe múltiplos documentos quando o motivo indicar 2+ empenhos.").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2 mt-1 mb-1"):
                def _reprocessar_fila_lote():
                    try:
                        ok, msg, _det = reprocessar_fila(usuario=usuario_logado)
                        ui.notify(msg, type="positive" if ok else "warning")
                        _refresh_q()
                    except Exception:
                        _log.exception("erro ao reprocessar fila da quarentena em lote")
                        ui.notify("Falha ao reprocessar fila", type="negative")
                botao("Reprocessar fila", icone="replay", on_click=_reprocessar_fila_lote, variante="solido", chave_modulo="empenhos").tooltip("Tenta reprocessar todos os pendentes com as regex ativas, sem reiniciar").props('data-testid=empenhos-reprocessar-fila')
                botao("Atualizar", icone="refresh", on_click=lambda: _refresh_q(), variante="contorno", chave_modulo="empenhos")
            colunas_q = [
                {"name": "arquivo", "label": "Arquivo", "field": "arquivo", "align": "left"},
                {"name": "motivo", "label": "Motivo", "field": "motivo", "align": "left"},
                {"name": "data", "label": "Recebido em", "field": "data"},
                {"name": "qid", "label": "", "field": "qid"},
            ]
            tabela_q = ui.table(columns=colunas_q, rows=[], row_key="qid").props("flat bordered dense").classes("w-full")

            def _refresh_q():
                try:
                    tabela_q.rows = [
                        {"qid": r[0], "arquivo": r[1], "motivo": (r[2] or "")[:80], "data": (r[3] or "")[:16]}
                        for r in listar_quarentena() if not r[4]
                    ]
                    tabela_q.update()
                except Exception as e:
                    try:
                        _log.exception(f"_refresh_q falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _refresh_q: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _refresh_q", type="negative")
                        except Exception:
                            pass
                    return None

            def on_q_click(e):
                try:
                    linha = e.args[1]
                    eh_multi = "Múltiplos documentos" in (linha.get("motivo") or "")
                    with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
                        ui.label("Múltiplos documentos — separar" if eh_multi else "Reprocessar com nova regex").classes("text-h6")
                        ui.label(linha["arquivo"]).classes("text-caption text-grey-6")
                        if eh_multi:
                            ui.label("Este PDF contém 2+ empenhos (ex.: lote escaneado). Separe em um arquivo por documento e reprocesse.").classes("text-caption text-orange-8 mt-1")
                            ui.label(linha.get("motivo") or "").classes("text-caption bg-yellow-50 p-2 rounded w-full")
                        padrao = ui.input("Regex alternativa (opcional)").props("outlined dense").classes("w-full") if not eh_multi else None

                        def tentar():
                            try:
                                ok, msg = reprocesse_quarentena(linha["qid"], (padrao.value if padrao else None) or None, usuario_logado)
                                ui.notify(("Sucesso: " + msg) if ok else ("Falha: " + msg),
                                          type="positive" if ok else "warning")
                                dlg.close(); _refresh_q()
                            except Exception:
                                _log.exception(f"erro ao reprocessar quarentena qid={linha['qid']}")

                        def separar():
                            try:
                                ok, msg = separar_documentos_quarentena(linha["qid"], usuario_logado)
                                ui.notify(msg, type="positive" if ok else "negative")
                                dlg.close(); _refresh_q()
                            except Exception:
                                _log.exception(f"erro ao separar quarentena qid={linha['qid']}")

                        with ui.row().classes("w-full justify-end gap-2 mt-2"):
                            botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="empenhos")
                            if eh_multi:
                                botao("Separar documentos", icone="content_cut", on_click=separar, variante="solido", chave_modulo="empenhos")
                            botao("Reprocessar", on_click=tentar, variante="solido" if not eh_multi else "texto", chave_modulo="empenhos")
                    dlg.open()
                except Exception as e:
                    try:
                        _log.exception(f"on_q_click falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em on_q_click: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em on_q_click", type="negative")
                        except Exception:
                            pass
                    return None

            tabela_q.on("row-click", on_q_click)
            _refresh_q()

        # ================= Regras regex =================
        with ui.expansion("Regras de extração (regex dinâmicas)", icon="rule").classes("w-full mt-2"):
            lista_regras = ui.column().classes("w-full")

            def _refresh_regras():
                try:
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
                                try:
                                    ok, msg = alternar_regra(r, not a)
                                    ui.notify(msg, type="positive" if ok else "negative")
                                    _refresh_regras()
                                except Exception as e:
                                    try:
                                        _log.exception(f"_toggle falhou: {e}")
                                    except Exception:
                                        pass
                                    try:
                                        notificar(f"Erro em _toggle: {e}", tipo="error")
                                    except Exception:
                                        try:
                                            ui.notify(f"Erro em _toggle", type="negative")
                                        except Exception:
                                            pass
                                    return None

                            botao("Inativar" if ativo else "Ativar", on_click=_toggle,
                                  variante="texto", compacto=True, chave_modulo="empenhos")
                except Exception as e:
                    try:
                        _log.exception(f"_refresh_regras falhou: {e}")
                    except Exception:
                        pass
                    try:
                        notificar(f"Erro em _refresh_regras: {e}", tipo="error")
                    except Exception:
                        try:
                            ui.notify(f"Erro em _refresh_regras", type="negative")
                        except Exception:
                            pass
                    return None

            _refresh_regras()

            with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
                n_nome = ui.input("Nome da regra").props("outlined dense").classes("w-44")
                n_padrao = ui.input("Padrão (regex)", placeholder=r"empenho\s*n[ºo]?\s*(\d+)") \
                    .props("outlined dense").classes("grow min-w-[240px]")
                n_destino = ui.input("Campo FTS destino (opcional)") \
                    .props("outlined dense").classes("w-56")

                def salvar():
                    try:
                        if not n_nome.value or not n_padrao.value:
                            ui.notify("Informe nome e padrão", type="warning"); return
                        ok, msg = salvar_regra(n_nome.value.strip(), n_padrao.value.strip(),
                                               campo_destino=(n_destino.value or "").strip() or None)
                        ui.notify(msg, type="positive" if ok else "negative")
                        if ok:
                            n_nome.set_value(None); n_padrao.set_value(None); n_destino.set_value(None)
                            _refresh_regras()
                    except Exception as e:
                        try:
                            _log.exception(f"salvar falhou: {e}")
                        except Exception:
                            pass
                        try:
                            notificar(f"Erro em salvar: {e}", tipo="error")
                        except Exception:
                            try:
                                ui.notify(f"Erro em salvar", type="negative")
                            except Exception:
                                pass
                        return None

                botao("Salvar regra", icone="save", on_click=salvar,
                    variante="solido", chave_modulo="empenhos")
    except Exception as e:
        try:
            _log.exception(f"_tela_config falhou: {e}")
        except Exception:
            pass
        try:
            notificar(f"Erro em _tela_config: {e}", tipo="error")
        except Exception:
            try:
                ui.notify(f"Erro em _tela_config", type="negative")
            except Exception:
                pass
        return None


